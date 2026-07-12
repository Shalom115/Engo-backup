"""
Exocet HTTP poller + per-channel rolling summarizer (Ch 4.1 S1).

READ-ONLY BY CONSTRUCTION (architecture rule 2: never write to vessel
systems). The only network operation in this module is an HTTP GET of the
Exocet /data endpoint; there is no code path that sends a body, POSTs, or
opens any other vessel address. Fire and bilge systems are never queried —
this module talks to exactly one URL, the Exocet aggregator.

Flow, once per minute:
  1. GET config.EXOCET_URL (default http://192.168.1.101/data). The response
     MUST parse as a JSON object — anything else fails loud (the live
     endpoint served the web-app HTML shell on 2026-07-10, so the real JSON
     path may differ; EXOCET_URL is the knob to point at it).
  2. Flatten the payload to one scalar per channel. RAW ARRAYS ARE NEVER
     FORWARDED: a list value is reduced to its most recent scalar element
     (+ a length note); the array itself is dropped before anything is
     persisted or summarized.
  3. Feed the sample into a RollingSummarizer: per-channel min/max/mean/last
     over 15-minute and 24-hour windows (numeric channels), last-value-only
     for text channels.
  4. Persist rolling state to data/state/exocet_rolling.json (atomic write)
     and append one JSON line to logs/exocet_YYYYMMDD.jsonl (append-only).

Locked vessel facts honoured here:
  - SBG timestamps are garbage (IMU clock unset, reports 2015-05-03) —
    SBG_UTC_Date / SBG_UTC_Time are dropped and flagged, never summarized,
    never used as a time source. Other SBG_* channels (accelerations etc.)
    are real sensor values and are summarized normally.
  - GNSS_UTCdate + GNSS_UTCtime are the authoritative timestamp source. Each
    poll stores a `gnss` block {utc, host_at_read, drift_seconds} in the
    state file; agent/clock.py layers its cross-check on that block.

Channel vocabulary verified against a real PSM export
(psm4-20260217-000000.csv, 254 columns): BAE_Motor_LoadPower_pt/_stbd,
BAE_EMRAX1/2_*, GNSS_UTCdate ('2026-02-16'), GNSS_UTCtime ('23:59:59.897'),
SBG_UTC_Date (stuck '2015-05-03'). The JSON *envelope* of the live /data
endpoint is NOT yet verified — see module note above.

CLI:
    python3.12 -m sensors.poller --once            # single poll, fail-loud
    python3.12 -m sensors.poller                   # 1/min daemon loop
    python3.12 -m sensors.poller --url http://...  # override endpoint
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

import config

logger = logging.getLogger("sensors.poller")

# --- Constants ---------------------------------------------------------------

WINDOWS: Dict[str, int] = {"15m": 15 * 60, "24h": 24 * 60 * 60}
RETENTION_SECONDS = WINDOWS["24h"]  # keep samples no older than the widest window

# Locked fact: the SBG IMU clock is unset (reports 2015-05-03 consistently).
# These channels are dropped at ingest and flagged in the state file. They are
# never summarized and never used as a time source.
SBG_TIMESTAMP_CHANNELS = frozenset({"SBG_UTC_Date", "SBG_UTC_Time"})

GNSS_DATE_CHANNEL = "GNSS_UTCdate"
GNSS_TIME_CHANNEL = "GNSS_UTCtime"
# A GNSS date before this is not a plausible live fix for this vessel (built
# 2023) — treat as invalid rather than feeding a broken receiver's clock into
# the drift check.
_GNSS_MIN_PLAUSIBLE_YEAR = 2023

DEFAULT_STATE_PATH = config.STATE_DIR / "exocet_rolling.json"
DEFAULT_HTTP_TIMEOUT_SECONDS = 10.0

# Daily JSONL logs carry the full flattened sample every minute (~250 channels)
# — that grows to multi-GB per year on the boat laptop if never pruned. Files
# older than this are deleted by prune_daily_logs(); 0 disables pruning.
LOG_RETENTION_DAYS = int(os.getenv("EXOCET_LOG_RETENTION_DAYS", "90"))

_STATE_VERSION = 1


class ExocetPayloadError(RuntimeError):
    """The endpoint answered, but not with a JSON object we can use."""


# --- Fetch (the ONLY network touch in this module; GET, read-only) -----------

def fetch_payload(url: str, timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """
    GET `url` and parse the body as a JSON object. Fails loud on network
    errors, non-JSON bodies (e.g. the Exocet web-app HTML shell), and JSON
    that isn't an object.
    """
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        content_type = resp.headers.get("Content-Type", "")
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        snippet = body[:120].decode("utf-8", errors="replace")
        raise ExocetPayloadError(
            f"Exocet endpoint {url} did not return JSON "
            f"(Content-Type={content_type!r}, body starts {snippet!r}). "
            "If this is the web-app HTML shell, the JSON data path differs — "
            "set EXOCET_URL to the real endpoint."
        ) from e
    if not isinstance(payload, dict):
        raise ExocetPayloadError(
            f"Exocet endpoint {url} returned JSON of type "
            f"{type(payload).__name__}, expected an object of channels."
        )
    return payload


# --- Flatten -----------------------------------------------------------------

def flatten_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten a (possibly nested) payload into {channel: scalar}.

    - Nested dicts flatten with dotted keys.
    - RAW ARRAYS NEVER PASS: a list is reduced to its LAST scalar element
      (the most recent value in Exocet's rolling arrays); the array itself is
      dropped. Non-scalar list elements are skipped with a debug note.
    - None values are dropped (channel absent this poll).
    """
    flat: Dict[str, Any] = {}
    _flatten_into(payload, "", flat)
    return flat


def _flatten_into(node: Any, prefix: str, out: Dict[str, Any]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            _flatten_into(value, name, out)
    elif isinstance(node, list):
        # Summarize-on-arrival: keep the most recent scalar, drop the array.
        for element in reversed(node):
            if isinstance(element, (int, float, str, bool)):
                out[prefix] = element
                return
        logger.debug("Channel %s: array had no scalar elements, dropped", prefix)
    elif node is None:
        return
    elif isinstance(node, (int, float, str, bool)):
        out[prefix] = node
    else:
        logger.debug("Channel %s: unsupported type %s, dropped", prefix, type(node).__name__)


def _coerce_float(value: Any) -> Optional[float]:
    """Numeric value or numeric-looking string ('0.00000') -> float, else None."""
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


# --- Rolling summarizer -------------------------------------------------------

class RollingSummarizer:
    """
    Per-channel rolling stats over the configured windows.

    Numeric channels keep (epoch_seconds, value) samples for up to
    RETENTION_SECONDS; text channels keep only (epoch_seconds, last value).
    Raw arrays must be reduced BEFORE reaching this class — a list here is a
    bug and raises.
    """

    def __init__(self) -> None:
        self._samples: Dict[str, Deque[Tuple[float, float]]] = {}
        self._text_last: Dict[str, Tuple[float, str]] = {}
        self._sbg_dropped: Dict[str, str] = {}  # channel -> last (ignored) raw value

    def add_poll(self, sample: Dict[str, Any], at: datetime) -> None:
        """Ingest one flattened poll sample taken at `at` (tz-aware UTC)."""
        if at.tzinfo is None:
            raise ValueError("add_poll requires a tz-aware datetime")
        ts = at.timestamp()
        for channel, value in sample.items():
            if isinstance(value, (list, dict)):
                raise TypeError(
                    f"Raw array/object reached the summarizer on channel "
                    f"{channel!r} — flatten_payload must reduce it first."
                )
            if channel in SBG_TIMESTAMP_CHANNELS:
                # Locked fact: SBG clock is unset/garbage. Flag, never use.
                self._sbg_dropped[channel] = str(value)
                continue
            num = _coerce_float(value)
            if num is not None:
                dq = self._samples.setdefault(channel, deque())
                dq.append((ts, num))
            else:
                self._text_last[channel] = (ts, str(value))
        self._trim(ts)

    def _trim(self, now_ts: float) -> None:
        cutoff = now_ts - RETENTION_SECONDS
        for dq in self._samples.values():
            while dq and dq[0][0] < cutoff:
                dq.popleft()

    def summary(self, now: datetime) -> Dict[str, Any]:
        """Compact per-channel summary — the ONLY form that ever reaches the LLM."""
        now_ts = now.timestamp()
        channels: Dict[str, Any] = {}
        for channel, dq in self._samples.items():
            if not dq:
                continue
            last_ts, last_val = dq[-1]
            entry: Dict[str, Any] = {
                "last": last_val,
                "last_at": _iso(last_ts),
                "windows": {},
            }
            for wname, wseconds in WINDOWS.items():
                cutoff = now_ts - wseconds
                vals = [v for t, v in dq if t >= cutoff]
                if vals:
                    entry["windows"][wname] = {
                        "min": min(vals),
                        "max": max(vals),
                        "mean": sum(vals) / len(vals),
                        "n": len(vals),
                    }
                else:
                    entry["windows"][wname] = None
            channels[channel] = entry
        for channel, (ts, text) in self._text_last.items():
            channels[channel] = {"last": text, "last_at": _iso(ts), "windows": {}}
        return channels

    # --- persistence ---

    def to_state(self, now: datetime) -> Dict[str, Any]:
        """Serializable rolling state (samples included so restarts resume)."""
        self._trim(now.timestamp())
        return {
            "version": _STATE_VERSION,
            "updated_at": now.isoformat(),
            "samples": {ch: [[t, v] for t, v in dq] for ch, dq in self._samples.items()},
            "text_last": {ch: [t, s] for ch, (t, s) in self._text_last.items()},
            "sbg_timestamps_ignored": dict(self._sbg_dropped),
            "summary": self.summary(now),
        }

    @classmethod
    def from_state(cls, state: Dict[str, Any]) -> "RollingSummarizer":
        """Rebuild from a previously persisted state dict. Fails loud on shape errors."""
        if state.get("version") != _STATE_VERSION:
            raise ValueError(f"Unsupported exocet_rolling state version: {state.get('version')!r}")
        rs = cls()
        for ch, pairs in state.get("samples", {}).items():
            rs._samples[ch] = deque((float(t), float(v)) for t, v in pairs)
        for ch, (t, s) in state.get("text_last", {}).items():
            rs._text_last[ch] = (float(t), str(s))
        rs._sbg_dropped = dict(state.get("sbg_timestamps_ignored", {}))
        return rs


def _iso(epoch_seconds: float) -> str:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()


# --- GNSS block ----------------------------------------------------------------

def parse_gnss_utc(sample: Dict[str, Any]) -> Optional[datetime]:
    """
    Combine GNSS_UTCdate ('2026-02-16') + GNSS_UTCtime ('23:59:59.897') into a
    tz-aware UTC datetime. Returns None (with a warning) when absent,
    unparseable, or implausibly old — a broken GNSS clock must not feed the
    drift check.
    """
    date_raw = sample.get(GNSS_DATE_CHANNEL)
    time_raw = sample.get(GNSS_TIME_CHANNEL)
    if not isinstance(date_raw, str) or not isinstance(time_raw, str):
        return None
    try:
        dt = datetime.fromisoformat(f"{date_raw.strip()}T{time_raw.strip()}")
    except ValueError:
        logger.warning("GNSS timestamp unparseable: date=%r time=%r", date_raw, time_raw)
        return None
    dt = dt.replace(tzinfo=timezone.utc)
    if dt.year < _GNSS_MIN_PLAUSIBLE_YEAR:
        logger.warning(
            "GNSS UTC reads %s — implausibly old (receiver clock not set?); ignored.",
            dt.isoformat(),
        )
        return None
    return dt


def build_gnss_block(sample: Dict[str, Any], host_now: datetime) -> Optional[Dict[str, Any]]:
    """State-file `gnss` block: authoritative UTC vs host clock at read time."""
    gnss_utc = parse_gnss_utc(sample)
    if gnss_utc is None:
        return None
    drift = (host_now - gnss_utc).total_seconds()  # positive = host clock ahead
    return {
        "utc": gnss_utc.isoformat(),
        "host_at_read": host_now.isoformat(),
        "drift_seconds": round(drift, 3),
    }


# --- Persistence ----------------------------------------------------------------

def write_state(state: Dict[str, Any], path: Path) -> None:
    """Atomic write (tmp + rename) so a mid-write kill never corrupts the state."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def load_state(path: Path) -> Optional[Dict[str, Any]]:
    """
    Load persisted rolling state, or None if the file doesn't exist yet.

    A CORRUPT state file (truncated write, disk glitch) is QUARANTINED — renamed
    to <name>.corrupt-<timestamp> with a loud error log — and None is returned
    so the monitor starts fresh instead of staying down until a human deletes
    the file. Losing the rolling window is recoverable; a monitor that can't
    restart isn't. The quarantined file is kept on disk for inspection.
    """
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        quarantine = path.with_name(f"{path.name}.corrupt-{stamp}")
        os.replace(path, quarantine)
        logger.error(
            "Rolling state file %s is CORRUPT (%s) — quarantined to %s; "
            "starting with a fresh rolling window.", path, e, quarantine,
        )
        return None


def prune_daily_logs(logs_dir: Path, now: datetime,
                     retention_days: int = LOG_RETENTION_DAYS) -> int:
    """Delete exocet_YYYYMMDD.jsonl files older than `retention_days`.
    Returns the number of files removed. retention_days <= 0 disables pruning."""
    if retention_days <= 0:
        return 0
    removed = 0
    cutoff = now.timestamp() - retention_days * 86400
    for f in logs_dir.glob("exocet_*.jsonl"):
        try:
            day = datetime.strptime(f.stem, "exocet_%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue  # not one of ours — never delete what we didn't write
        if day.timestamp() < cutoff:
            f.unlink()
            removed += 1
    if removed:
        logger.info("Pruned %d daily log file(s) older than %d days.", removed, retention_days)
    return removed


def append_daily_log(record: Dict[str, Any], logs_dir: Path, now: datetime) -> Path:
    """Append one JSON line to logs/exocet_YYYYMMDD.jsonl (append-only, flushed)."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / f"exocet_{now.strftime('%Y%m%d')}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()
    return path


# --- Poll orchestration -----------------------------------------------------------

def poll_once(
    url: str = config.EXOCET_URL,
    summarizer: Optional[RollingSummarizer] = None,
    state_path: Path = DEFAULT_STATE_PATH,
    logs_dir: Path = config.LOGS_DIR,
    now: Optional[datetime] = None,
    timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """
    One full poll cycle: fetch -> flatten -> summarize -> persist state ->
    append daily log. Returns the state dict written. Fails loud on fetch or
    payload errors (the caller decides whether to retry — the daemon loop
    logs and continues; --once propagates).

    If `summarizer` is None, rolling state is resumed from `state_path` when
    present (restart-safe), else started fresh.
    """
    now = now or datetime.now(timezone.utc)
    if summarizer is None:
        prior = load_state(state_path)
        summarizer = RollingSummarizer.from_state(prior) if prior else RollingSummarizer()

    payload = fetch_payload(url, timeout=timeout)
    sample = flatten_payload(payload)
    summarizer.add_poll(sample, now)

    state = summarizer.to_state(now)
    state["source"] = url
    gnss = build_gnss_block(sample, now)
    if gnss is not None:
        state["gnss"] = gnss
    write_state(state, state_path)

    append_daily_log(
        {
            "timestamp": now.isoformat(),
            "ok": True,
            "channels": len(sample),
            "gnss_drift_seconds": gnss["drift_seconds"] if gnss else None,
            "sample": sample,  # flattened scalars only; raw arrays already reduced
        },
        logs_dir,
        now,
    )
    return state


def run(
    url: str = config.EXOCET_URL,
    interval_seconds: int = config.EXOCET_POLL_INTERVAL_SECONDS,
    state_path: Path = DEFAULT_STATE_PATH,
    logs_dir: Path = config.LOGS_DIR,
) -> None:
    """
    Daemon loop: one poll per `interval_seconds` (baseline 1/min). A failed
    poll is logged (stderr + daily log) and the loop continues — a dropped
    sample must not kill the monitor. Never retries inside an interval, so
    the endpoint is never hammered.
    """
    prior = load_state(state_path)
    summarizer = RollingSummarizer.from_state(prior) if prior else RollingSummarizer()
    logger.info(
        "Exocet poller starting: %s every %ds (state=%s, resumed=%s)",
        url, interval_seconds, state_path, prior is not None,
    )
    prune_daily_logs(logs_dir, datetime.now(timezone.utc))
    last_prune_date = datetime.now(timezone.utc).date()
    while True:
        started = time.monotonic()
        now = datetime.now(timezone.utc)
        if now.date() != last_prune_date:  # once per day, on rollover
            prune_daily_logs(logs_dir, now)
            last_prune_date = now.date()
        try:
            poll_once(url, summarizer, state_path, logs_dir, now)
        except (urllib.error.URLError, OSError, ExocetPayloadError) as e:
            logger.error("Poll failed: %s", e)
            append_daily_log(
                {"timestamp": now.isoformat(), "ok": False, "error": f"{type(e).__name__}: {e}"},
                logs_dir,
                now,
            )
        elapsed = time.monotonic() - started
        time.sleep(max(0.0, interval_seconds - elapsed))


# --- CLI --------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Exocet read-only poller + summarizer")
    parser.add_argument("--once", action="store_true", help="single poll then exit (fail-loud)")
    parser.add_argument("--url", default=config.EXOCET_URL, help="Exocet data endpoint")
    parser.add_argument("--interval", type=int, default=config.EXOCET_POLL_INTERVAL_SECONDS,
                        help="seconds between polls (daemon mode)")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH,
                        help="rolling state JSON path")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )

    if args.once:
        state = poll_once(url=args.url, state_path=args.state)
        n = len(state.get("summary", {}))
        gnss = state.get("gnss")
        print(f"OK: {n} channels summarized -> {args.state}")
        if gnss:
            print(f"GNSS UTC {gnss['utc']}  host drift {gnss['drift_seconds']:+.1f}s")
    else:
        run(url=args.url, interval_seconds=args.interval, state_path=args.state)


if __name__ == "__main__":
    main()
