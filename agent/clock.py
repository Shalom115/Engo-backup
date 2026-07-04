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
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
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


def clock_status(now: Optional[datetime] = None) -> Tuple[datetime, bool, Optional[datetime]]:
    """
    Return (now, suspect, floor).

    `now` defaults to the live system clock (UTC). `suspect` is True when the
    clock reads earlier than the most recent recorded ingest — i.e. it cannot be
    trusted to judge how recent an event is. `floor` is that reference timestamp
    (or None if nothing has been ingested yet, in which case suspect is False).
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
