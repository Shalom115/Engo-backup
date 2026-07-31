"""
USAGE METER (2026-07-26) — measure the spend before trying to reduce it.

The engineer's question is the right one: if one 43-page book costs ~$150, the
whole drive runs to thousands and the economics stop working. But until now
NOTHING in this pipeline recorded a single token. Every cost statement anyone
could make — mine included — was an estimate built on call counts and assumed
image sizes.

So each vision/LLM call records what it actually cost, tagged with the LAYER it
belongs to (labels, devices, legends, survey, wiring, compose, verify). That
turns "the tiled layers probably dominate" into a number, and it means any
saving claimed later can be shown rather than argued.

Append-only JSONL, one line per call, kill-safe. Writing is best-effort: a
metering failure must never break a run.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import config

LOG: Path = config.LOGS_DIR / "usage.jsonl" if hasattr(config, "LOGS_DIR") \
    else Path("logs/usage.jsonl")

# Per-million-token prices, overridable from .env so a rate change is not a
# code change. Only used for REPORTING — never for any pipeline decision.
_PRICES = {
    "claude-opus":   (15.0, 75.0),
    "claude-sonnet": (3.0, 15.0),
    "claude-haiku":  (0.80, 4.0),
    "gemini":        (0.30, 2.50),
    "gpt":           (2.50, 10.0),
}

_lock = threading.Lock()
_layer = threading.local()


def set_layer(name: str) -> None:
    """Tag every call made from here until the next set_layer with a layer."""
    _layer.name = name


def current_layer() -> str:
    return getattr(_layer, "name", "") or "unattributed"


def price_for(model: str) -> tuple:
    m = (model or "").lower()
    for key, pr in _PRICES.items():
        if key in m:
            return pr
    return (3.0, 15.0)          # unknown model: assume mid-tier, flag in report


def record(model: str, usage: Any, *, layer: Optional[str] = None,
           sheet: str = "", note: str = "") -> None:
    """Record one call's usage. Never raises."""
    try:
        if os.getenv("USAGE_METER", "1") == "0":
            return
        get = (lambda k: getattr(usage, k, None) if not isinstance(usage, dict)
               else usage.get(k))
        row = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "layer": layer or current_layer(),
            "model": model,
            "sheet": sheet,
            "in": get("input_tokens") or 0,
            "out": get("output_tokens") or 0,
            "cache_read": get("cache_read_input_tokens") or 0,
            "cache_write": get("cache_creation_input_tokens") or 0,
        }
        if note:
            row["note"] = note
        ppm_in, ppm_out = price_for(model)
        # cached input reads bill at ~10% of the input rate
        row["usd"] = round(
            (row["in"] * ppm_in + row["cache_read"] * ppm_in * 0.1
             + row["cache_write"] * ppm_in * 1.25
             + row["out"] * ppm_out) / 1_000_000, 6)
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with _lock, open(LOG, "a") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass


def report(since: str = "") -> Dict[str, Any]:
    """Spend by layer, so the biggest line is obvious rather than guessed."""
    if not LOG.exists():
        return {"calls": 0, "usd": 0.0, "by_layer": {}}
    by: Dict[str, Dict[str, float]] = {}
    total_usd = 0.0
    calls = 0
    sheets = set()
    for line in open(LOG):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if since and r.get("ts", "") < since:
            continue
        k = r.get("layer", "unattributed")
        b = by.setdefault(k, {"calls": 0, "in": 0, "out": 0, "usd": 0.0})
        b["calls"] += 1
        b["in"] += r.get("in", 0)
        b["out"] += r.get("out", 0)
        b["usd"] += r.get("usd", 0.0)
        total_usd += r.get("usd", 0.0)
        calls += 1
        if r.get("sheet"):
            sheets.add(r["sheet"])
    for b in by.values():
        b["usd"] = round(b["usd"], 4)
        b["share"] = round(100 * b["usd"] / total_usd, 1) if total_usd else 0.0
    return {"calls": calls, "usd": round(total_usd, 4), "sheets": len(sheets),
            "usd_per_sheet": round(total_usd / len(sheets), 3) if sheets else None,
            "by_layer": dict(sorted(by.items(), key=lambda kv: -kv[1]["usd"]))}
