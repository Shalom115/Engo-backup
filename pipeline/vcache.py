"""
VISION-LAYER CACHE (2026-07-26) — content-addressed, on disk.

WHY THIS EXISTS. A wiring sheet costs roughly 45 vision calls: ~16 tiled OCR
calls for labels, ~16 tiled calls to locate device symbols, ~12 extraction
reads, and 1 composition. Of those, the label and device layers are PURE
FUNCTIONS OF THE DRAWING — they depend on the page bytes, the tiling and the
DPI, and on nothing else. No protocol rule, no register state, no red-pen
change alters what letters are printed on a page.

Yet every red-pen cycle re-paid them. In this session alone three sheets were
composed twice, re-buying ~96 tile calls that could only return what they had
already returned. Across a whole drive, re-runs are not the exception — they
are the method: the engineer red-pens, the protocol changes, the sheet is
composed again.

So the deterministic layers are cached by CONTENT. The key is a hash of the
page bytes plus every parameter that could change the answer (including a
PROMPT VERSION, so improving a prompt correctly invalidates its cache and
nothing else). A cache hit costs a disk read; a miss costs exactly what it
costs today.

This buys nothing in quality by itself — but it makes re-running cheap enough
to iterate freely, which is where quality actually comes from.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import config

CACHE_DIR: Path = config.STATE_DIR / "cache" / "vision"


def _key(layer: str, pdf_bytes: bytes, page_index: int,
         params: Dict[str, Any]) -> str:
    h = hashlib.sha256()
    h.update(pdf_bytes)
    h.update(str(page_index).encode())
    h.update(json.dumps(params, sort_keys=True, default=str).encode())
    return f"{layer}_{h.hexdigest()[:32]}"


def get_or_compute(layer: str, pdf_bytes: bytes, page_index: int,
                   params: Dict[str, Any],
                   compute: Callable[[], Any],
                   *, enabled: bool = True) -> Any:
    """
    Return the cached result for this exact page+params, else compute and store.

    A cache write failure is never fatal — the result is returned regardless.
    A corrupt cache file is deleted and recomputed rather than crashing a run
    (a half-written file from a killed run must not poison every later run).
    """
    if not enabled:
        return compute()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{_key(layer, pdf_bytes, page_index, params)}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())["result"]
        except Exception:
            try:
                path.unlink()
            except OSError:
                pass
    result = compute()
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"layer": layer, "page": page_index,
                                   "params": params, "result": result},
                                  default=str))
        tmp.replace(path)
    except Exception:
        pass
    return result


def stats() -> Dict[str, Any]:
    """What is cached, and how much re-computation it stands to save."""
    if not CACHE_DIR.exists():
        return {"entries": 0, "bytes": 0, "by_layer": {}}
    by_layer: Dict[str, int] = {}
    total = 0
    for f in CACHE_DIR.glob("*.json"):
        total += f.stat().st_size
        by_layer[f.name.split("_")[0]] = by_layer.get(f.name.split("_")[0], 0) + 1
    return {"entries": sum(by_layer.values()), "bytes": total,
            "by_layer": by_layer}


def clear(layer: Optional[str] = None) -> int:
    """Drop cached results (all, or one layer). Use when a prompt changes in a
    way its version string did not capture."""
    if not CACHE_DIR.exists():
        return 0
    n = 0
    for f in CACHE_DIR.glob("*.json"):
        if layer and not f.name.startswith(layer + "_"):
            continue
        f.unlink()
        n += 1
    return n
