"""
SUBSYSTEM SEEDING PROTOCOL (engineer-mandated 2026-07-05) — combines two rules
proven the same day on the aircon/Termodinamica test case:

RULE A — BREADTH-FIRST FILE ORDER. When a subsystem has little or no existing
Register presence, read the BROADEST / most SYSTEM-LEVEL document in that
subsystem's folder FIRST — before narrower detail/spec/test documents — so the
node backbone gets seeded at the correct granularity before anything enriches
it. Proven directly: reading "Aircon Cabin Volumes for Supplier.pdf" (a sizing
reference) first gave 18 zone names with NO per-unit identity; re-reading
"Aircon System Schematic.pdf" (the system-level document) instead gave 10
individually-labeled fancoil units (FCU-01..FCU-10) each with its own zone —
a materially better foundation for deciding node structure. File NAME is the
real-world signal engineers already use for this (an engineer choosing which
file to open would reach for the same document, for the same reason).

RULE B — THE SPLIT-TRIGGER TEST. Given a set of discovered equipment
instances of the same class, decide whether they warrant PARENT + PER-
INSTANCE CHILDREN (mirroring the winch/thruster/BEL per-installation pattern,
Decision 3) or a single node. Split when ALL of:
  1. multiple physical installations of the same equipment CLASS exist;
  2. each carries a DISTINCT location/zone identity stated by an
     AUTHORITATIVE SOURCE (read off a drawing/table, never inferred/guessed);
  3. (the WHY, not independently computable — the justification for 1+2
     mattering): an engineer troubleshooting ONE instance needs that
     instance's OWN facts (its own supply/control path, own serial/address,
     own location) to fix it — the instances are independently FAULT-
     ISOLATABLE. Conflating them into one node would make "my OWNERS CABIN
     aircon won't cool" route to a bucket mixing every cabin's facts.
Proven directly: the aircon system schematic's 10 FCUs satisfy 1+2 cleanly
(same class, 10 distinct zone-stated identities) — they should split. The
bilge valves case (session 1) satisfies 1 but NOT yet 2 at production
confidence (zone names corroborated twice, independently; the CALLOUT TAGS
tying a specific valve id to a specific zone are not yet legible at the
resolution read so far) — correctly held, not split, pending a tighter re-read.

Both rules are GOLD-BLIND — everything here operates on filenames, zone
labels, and counts generically; no vessel-specific token is hardcoded.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# RULE A: filename signal, broadest first. Two keyword tiers rather than a
# single score — a file can be neither (falls to the middle, read in
# whatever order) but never has both a BROAD and a NARROW hit push it to a
# false middle score.
_BROAD_KEYWORDS = re.compile(
    r"\b(system schematic|systems? schematic|electric(al)? schematic|"
    r"general arrangement|\bga\b|layout|overview|one[- ]line|"
    r"wiring diagram|schematic)\b", re.I)
_NARROW_KEYWORDS = re.compile(
    r"\b(spare parts?|spares?|for supplier|acceptance trial|commissioning|"
    r"test(ing)?|checklist|volumes?|cabin volumes?|datasheet|data sheet|"
    r"quote|proposal|invoice)\b", re.I)


def _breadth_score(filename: str) -> int:
    """+1 for a broad/system-level signal, -1 for a narrow/detail signal,
    0 if neither (or both, which cancels rather than guesses)."""
    broad = bool(_BROAD_KEYWORDS.search(filename))
    narrow = bool(_NARROW_KEYWORDS.search(filename))
    if broad and not narrow:
        return 1
    if narrow and not broad:
        return -1
    return 0


def rank_files_by_breadth(filenames: List[str]) -> List[str]:
    """
    Sort a subsystem folder's file names so the BROADEST / most system-level
    document comes first (Rule A). Stable sort — files with the same breadth
    score keep their original relative order, since breadth is the only
    signal this function has an opinion about.
    """
    scored = sorted(enumerate(filenames), key=lambda x: (-_breadth_score(x[1]), x[0]))
    return [f for _, f in scored]


@dataclass
class SplitDecision:
    should_split: bool
    reason: str
    instance_count: int
    zones: List[str] = field(default_factory=list)
    missing_zone_instances: List[Any] = field(default_factory=list)


def evaluate_split(instances: List[Dict[str, Any]], *, zone_key: str = "zone") -> SplitDecision:
    """
    Rule B, as a computable gate. `instances` is a list of discovered
    equipment-instance dicts (e.g. the fancoil_units list from a vision read);
    each should carry a `zone_key` field (default "zone") holding the
    location/zone AS STATED BY THE SOURCE — never inferred here. Criterion 3
    (fault-isolation need) is the documented WHY behind 1+2, not an
    independently checkable condition — see module docstring.

    NEVER guesses a zone: an instance with an empty/missing zone field counts
    against splitting cleanly and is reported in `missing_zone_instances`
    rather than silently dropped or assumed to share a zone with a neighbor.
    """
    n = len(instances)
    if n < 2:
        return SplitDecision(False, "only one (or zero) instance found — nothing to split", n)

    zones: List[str] = []
    missing = []
    for inst in instances:
        z = (inst.get(zone_key) or "").strip()
        if z:
            zones.append(z)
        else:
            missing.append(inst)

    if missing:
        return SplitDecision(
            False,
            f"{len(missing)}/{n} instance(s) have no stated zone/location — "
            "criterion 2 (distinct authoritative identity) unmet; re-read at "
            "higher resolution or from a more specific source before splitting",
            n, zones, missing,
        )

    distinct = len(set(z.lower() for z in zones))
    if distinct < n:
        return SplitDecision(
            False,
            f"only {distinct} distinct zone(s) stated across {n} instances — "
            "some instances share a zone label, which is either a real "
            "multi-unit-per-zone situation (needs its own sub-grouping, not "
            "assumed here) or a read error; not splitting on ambiguous zones",
            n, zones,
        )

    return SplitDecision(
        True,
        f"{n} instances of one equipment class, each with its own distinct "
        "source-stated zone — split into parent + per-instance children "
        "(same pattern as the winch/thruster/BEL per-installation nodes)",
        n, zones,
    )
