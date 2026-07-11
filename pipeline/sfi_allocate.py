"""
SFI ALLOCATION + AUTONOMOUS NODE-CREATION RULES (Ch 3.1 S2).

Codifies the rules the engineer taught across the load-map red-pen sessions —
until now recorded only as prose in CLAUDE.md, applied by hand. This module is
the pipeline path so vessel #2 (and Engo's own autonomous node creation) obeys
them by construction, not by a human remembering.

THE RULES (each traced to the engineer statement it came from):

  R1 OCCUPANCY CHECK BEFORE ASSIGNING (2026-07-02, "651 mistake" retro).
     Never assign a logical SFI by mechanical N+1. Check what the YARD TREE and
     the REGISTER already hold at every code first. The 651 error happened
     because 650+1 was assigned without checking the tree — 651 was BAE, 652 was
     ONYX. Yard occupancy has priority; the Register is the secondary signal.

  R2 LOGICAL-SFI ALLOCATION IN A RANGE (2026-07-11, "allocate a free SFI between
     510-515", "between 360-370"). Given a target range, return the LOWEST code
     in it that is free in BOTH the yard tree and the Register. Free means: no
     yard folder starts with that code AND no active Register node sits at that
     subsystem code. Exhausted range -> raise, never silently overflow.

  R3 DECISION-5 AUTONOMOUS-CREATE GATE (2026-06-27). Auto-create a node WITHOUT
     flagging ONLY when all three resolve from a single authoritative source:
     (a) make, (b) model, (c) a known equipment class. Any one missing/ambiguous
     -> create FLAGGED (surfaced for the engineer, never a silent guess). Same
     >=80%-disposition logic as the Part-Identity rule.

Gold-blind / fleet-general: no vessel-specific token here. Occupancy is read from
whatever structure + register the caller passes.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

_SFI_FOLDER = re.compile(r"^(\d{3})\b")


# --------------------------------------------------------------- occupancy
def yard_occupied_codes(structure: Dict[str, Any]) -> Set[str]:
    """SFI codes that have a YARD FOLDER (name starts with the 3-digit code).
    The authoritative occupancy signal (R1: yard has priority)."""
    codes: Set[str] = set()
    for n in structure.get("nodes") or []:
        m = _SFI_FOLDER.match(str(n.get("name", "")))
        if m:
            codes.add(m.group(1))
    return codes


def register_occupied_codes(register: Dict[str, Any]) -> Set[str]:
    """SFI subsystem codes held by an ACTIVE Register node (secondary signal)."""
    codes: Set[str] = set()
    for e in register.get("entries") or []:
        if e.get("retired"):
            continue
        sc = e.get("subsystem_code")
        if sc:
            codes.add(str(sc))
        m = re.match(r"^(\d{3})", str(e.get("equipment_id", "")))
        if m:
            codes.add(m.group(1))
    return codes


def occupancy(structure: Dict[str, Any], register: Dict[str, Any]) -> Dict[str, Dict[str, bool]]:
    """Per-code occupancy across both sources — the R1 evidence a caller must see
    before assigning. {code: {yard: bool, register: bool}}."""
    yard = yard_occupied_codes(structure)
    reg = register_occupied_codes(register)
    out: Dict[str, Dict[str, bool]] = {}
    for c in yard | reg:
        out[c] = {"yard": c in yard, "register": c in reg}
    return out


def is_free(code: str, structure: Dict[str, Any], register: Dict[str, Any]) -> bool:
    """R1: a code is free only when NEITHER the yard tree NOR the Register uses it."""
    return code not in yard_occupied_codes(structure) and code not in register_occupied_codes(register)


def allocate_in_range(low: int, high: int, structure: Dict[str, Any],
                      register: Dict[str, Any], *, inclusive: bool = True) -> str:
    """
    R2: lowest free 3-digit code in [low, high] (inclusive by default), checked
    against BOTH sources. Raises ValueError if the range is exhausted — never
    silently returns an occupied or out-of-range code.
    """
    if low > high:
        low, high = high, low
    yard = yard_occupied_codes(structure)
    reg = register_occupied_codes(register)
    last = high if inclusive else high - 1
    for c in range(low, last + 1):
        code = f"{c:03d}"
        if code not in yard and code not in reg:
            return code
    raise ValueError(
        f"No free SFI code in [{low:03d}-{high:03d}] — all occupied "
        f"(yard: {sorted(yard & {f'{c:03d}' for c in range(low, last+1)})}, "
        f"register: {sorted(reg & {f'{c:03d}' for c in range(low, last+1)})}). "
        "Engineer must widen the range or reuse a code.")


# --------------------------------------------------------------- auto-create gate
_KNOWN_CLASS_HINT = re.compile(
    r"\b(pump|valve|motor|breaker|fuse|relay|contactor|charger|inverter|converter|"
    r"battery|compressor|heater|cooler|fridge|refrigerat|light|lamp|switch|sensor|"
    r"transformer|filter|winch|windlass|thruster|actuator|cylinder|display|controller|"
    r"module|panel|gauge|meter|alarm|fan|blower|extractor|steriliser|sterilizer|"
    r"watermaker|purifier|antenna|radar|camera|horn|generator|alternator|"
    r"starter|isolator|manifold|block|furler|gearbox|coupling|bearing|seal)\b", re.I)


def classify_creation(make: Optional[str], model: Optional[str],
                      equipment_class: Optional[str]) -> Dict[str, Any]:
    """
    R3: decide auto-create vs create-flagged for a proposed node.

    Returns {action: 'auto_create'|'create_flagged', confidence, missing:[...],
    reason}. auto_create ONLY when make AND model AND a recognizable equipment
    class are all present; otherwise create_flagged with the specific gap named.
    """
    missing: List[str] = []
    if not (make and str(make).strip()):
        missing.append("make")
    if not (model and str(model).strip()):
        missing.append("model")
    klass = str(equipment_class or "").strip()
    class_known = bool(klass) and bool(_KNOWN_CLASS_HINT.search(klass))
    if not klass:
        missing.append("equipment_class")
    elif not class_known:
        missing.append("recognizable_equipment_class")

    if not missing:
        return {"action": "auto_create", "confidence": "high", "missing": [],
                "reason": "make + model + known equipment class all resolved from source (Decision-5)"}
    return {"action": "create_flagged", "confidence": "low", "missing": missing,
            "reason": f"Decision-5 gate: missing/ambiguous {', '.join(missing)} — surfaced, not guessed"}


def next_free_after(code: str, structure: Dict[str, Any], register: Dict[str, Any],
                    *, window: int = 20) -> str:
    """Convenience for the common 'section N is a parent, I need the next free
    child code near it' case: lowest free code in [code, code+window]."""
    base = int(code)
    return allocate_in_range(base, base + window, structure, register)
