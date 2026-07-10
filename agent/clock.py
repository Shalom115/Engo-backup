"""
System-clock sanity check.

'Today' drives the recent-event window in the diagnostic prompt (Step 0's
1-month carve-out). On an offline boat laptop the clock can drift or be reset,
and a wrong clock would silently mislead the agent about how recent a logged
repair is. There is no internet time source to trust, so instead we derive a
FLOOR from data the vessel already wrote: the most recent recorded ingest/build
timestamp in data/state. The clock cannot legitimately predate that — you can't
run a query before your last ingest.

If now() < floor, the clock is wrong. We do NOT correct it (we don't know the
true date) — we FLAG it, so the injected date line tells the agent not to trust
recency. This fails toward caution: a clock running behind makes recent events
look older, so the agent under-mentions rather than fabricates a false 'recent'.

GNSS CROSS-CHECK (Ch 4.1 S2, layered ON TOP of the floor + forward-jump
heuristics above — it never replaces or weakens them): once the Exocet poller
(sensors/poller.py) is running, data/state/exocet_rolling.json carries a
`gnss` block — GNSS_UTCdate/UTCtime (the locked-fact authoritative timestamp
source) alongside the host clock at the moment of that poll. The drift
between the two is a HARD measurement of host-clock error in BOTH directions;
|drift| beyond a few minutes flags the clock suspect. A drift measured at
poll time stays valid until the clock is changed, and the next poll
re-measures — so a fresh poll aboard closes both drift directions with no
dormancy false-positives. Checks only ever ADD suspicion; a healthy GNSS
reading never clears a flag raised by the floor or forward-jump checks.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

import config

logger = logging.getLogger("agent.clock")

# (state filename, top-level field) pairs that carry a recorded UTC ISO timestamp
# written at ingest/build time. The floor is the max across whatever exists.
_TIMESTAMP_SOURCES = [
    ("audit_report_corpus.json", "ran_at"),
    (f"structure_{config.VESSEL_NAMESPACE}.json", "walked_at"),
    (f"ingestion_report_{config.VESSEL_NAMESPACE}.json", "ran_at"),
    (f"ingestion_report_suppliers_{config.VESSEL_NAMESPACE}.json", "ran_at"),
    (f"reclassify_report_{config.VESSEL_NAMESPACE}.json", "ran_at"),
    # The poller stamps its own write time — you can't query before your last poll.
    ("exocet_rolling.json", "updated_at"),
]


def _parse_iso(value: object) -> Optional[datetime]:
    """Parse an ISO-8601 string to a tz-aware UTC datetime, or None."""
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def clock_floor() -> Optional[datetime]:
    """
    Most recent recorded ingest/build timestamp in data/state — the moment the
    system clock cannot legitimately read earlier than. None if no artifact
    carries a parseable timestamp (fresh project, nothing ingested yet).
    """
    floor: Optional[datetime] = None
    for name, field in _TIMESTAMP_SOURCES:
        path = config.STATE_DIR / name
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        dt = _parse_iso(data.get(field)) if isinstance(data, dict) else None
        if dt and (floor is None or dt > floor):
            floor = dt
    return floor


# --- GNSS cross-check (Ch 4.1 S2) -------------------------------------------

# Rolling state written by sensors/poller.py; its `gnss` block carries the
# authoritative GNSS UTC and the host clock at the moment of that poll.
_GNSS_STATE_FILE = "exocet_rolling.json"

# "Drift > a few minutes → suspect, both directions." 5 minutes tolerates
# HTTP latency, poll jitter and honest sub-minute drift; a genuinely wrong
# clock (CMOS reset, manual mis-set) is off by hours-to-years.
_GNSS_DRIFT_TOLERANCE_SECONDS = 300.0


def gnss_drift(state_path: Optional[Path] = None) -> Optional[Tuple[float, datetime]]:
    """
    Host-clock drift measured against GNSS UTC at the last Exocet poll.

    Returns (drift_seconds, measured_at) where drift_seconds > 0 means the
    host clock ran AHEAD of GNSS at poll time and measured_at is the host
    clock's reading at that poll. Returns None when the poller state, its
    `gnss` block, or either timestamp is missing/unparseable — the check
    simply doesn't apply then (the floor + forward-jump heuristics still do).

    Drift is recomputed from the two stored timestamps, not trusted from the
    stored float.
    """
    path = state_path if state_path is not None else (config.STATE_DIR / _GNSS_STATE_FILE)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    gnss = data.get("gnss") if isinstance(data, dict) else None
    if not isinstance(gnss, dict):
        return None
    gnss_utc = _parse_iso(gnss.get("utc"))
    host_at_read = _parse_iso(gnss.get("host_at_read"))
    if gnss_utc is None or host_at_read is None:
        return None
    return (host_at_read - gnss_utc).total_seconds(), host_at_read


def _gnss_suspect() -> bool:
    """True when the last measured GNSS drift exceeds tolerance (either direction)."""
    result = gnss_drift()
    if result is None:
        return False
    drift, measured_at = result
    if abs(drift) > _GNSS_DRIFT_TOLERANCE_SECONDS:
        logger.warning(
            "Host clock drifts %+.0f s from GNSS UTC (measured at last Exocet "
            "poll, host time %s) — clock %s; recency judgements flagged as "
            "untrusted.",
            drift, measured_at.isoformat(),
            "AHEAD of GNSS" if drift > 0 else "BEHIND GNSS",
        )
        return True
    return False


# Forward-jump tolerance: how far ahead of the agent's own last outbound call
# the clock may read before being flagged. Soft by design — a legitimately
# dormant laptop looks identical to a CMOS reset into the future, so we flag
# (stop trusting recency) rather than hard-block. 45 days accommodates a yard
# period / long delivery gap; a BIOS-default jump is typically years.
_FORWARD_JUMP_TOLERANCE_DAYS = 45


def _last_agent_activity() -> Optional[datetime]:
    """Timestamp of the agent's own most recent logged call (logs/agent.log,
    JSON-lines, each with an ISO 'timestamp'). None if no log yet."""
    path = config.LOGS_DIR / "agent.log"
    if not path.exists():
        return None
    last: Optional[datetime] = None
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    dt = _parse_iso(json.loads(line).get("timestamp"))
                except (json.JSONDecodeError, AttributeError):
                    continue
                if dt and (last is None or dt > last):
                    last = dt
    except OSError:
        return None
    return last


def clock_status(now: Optional[datetime] = None) -> Tuple[datetime, bool, Optional[datetime]]:
    """
    Return (now, suspect, floor).

    `now` defaults to the live system clock (UTC). `suspect` is True when the
    clock cannot be trusted to judge how recent an event is, in either direction:

    BEHIND (hard): now < floor, where floor is the most recent recorded
    ingest/build timestamp — you can't query before your last ingest. Fails
    toward caution (old-looking events are under-mentioned, never fabricated
    as recent).

    AHEAD (soft): now runs more than _FORWARD_JUMP_TOLERANCE_DAYS past the
    agent's own last logged call AND past the ingest floor. A forward-jumped
    clock is the MORE dangerous direction — it makes genuinely old documented
    patterns compute as 'recent', re-introducing the Step-0 priming risk. A
    genuinely dormant laptop trips this too, which is acceptable: the cost is
    the agent not volunteering recency, never a wrong fact.

    GNSS (hard, both directions): the last Exocet poll measured host clock vs
    GNSS UTC (the authoritative source — locked fact); |drift| beyond
    _GNSS_DRIFT_TOLERANCE_SECONDS flags suspect. Layered on top of the two
    heuristics above — it only ever ADDS suspicion, never clears it.

    `floor` is the behind-check reference (or None if nothing ingested yet).
    """
    now = now or datetime.now(timezone.utc)
    floor = clock_floor()
    suspect = floor is not None and now < floor
    if suspect:
        logger.warning(
            "System clock (%s) predates last recorded ingest (%s) — 'today' is "
            "unreliable; recent-event window flagged to the agent.",
            now.date().isoformat(), floor.date().isoformat(),
        )
        return now, suspect, floor

    last_call = _last_agent_activity()
    refs = [t for t in (last_call, floor) if t is not None]
    if refs:
        newest = max(refs)
        ahead_days = (now - newest).total_seconds() / 86400.0
        if ahead_days > _FORWARD_JUMP_TOLERANCE_DAYS:
            suspect = True
            logger.warning(
                "System clock (%s) runs %.0f days past the last recorded "
                "activity (%s) — possible forward clock jump (or long dormancy); "
                "recency judgements flagged as untrusted either way.",
                now.date().isoformat(), ahead_days, newest.date().isoformat(),
            )

    # GNSS cross-check — layered last, additive only. A healthy GNSS reading
    # never clears suspicion raised above; an out-of-tolerance drift adds it.
    if _gnss_suspect():
        suspect = True
    return now, suspect, floor
