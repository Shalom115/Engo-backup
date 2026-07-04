"""
Folder / file name parsing for the Equipment Register backbone.

The vessel library is organised as an ordered numeric tree — the details that
matter are almost always in the names:

    X00 region  (main vessel category, e.g. "400, Propulsion and Machinery spaces")
      └ XX0 subsystem  (inner layer, e.g. "460, Thrusters")
          └ Equipment  ("Maker (Function) [SFI]"  |  "Product Name"  |  "Name (ACRONYM)")
              └ Documents  (Manuals / Schematics / Spares / Photos / ...)

This module is pure: name string in, structured fields out. No I/O. It is
deliberately vessel-agnostic — no hard-coded maker or equipment names. The only
fixed vocabularies are (a) the SFI region map (an industry standard) and (b) the
set of generic document-type / non-equipment folder words, which are structural,
not vessel-specific.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

# --- SFI region backbone (X00). Industry-standard, not vessel-specific. ---
REGION_LABELS: Dict[str, str] = {
    "000": "General Condition",
    "100": "Structure, Rudder and Keel",
    "200": "Deck",
    "300": "Interiors",
    "400": "Propulsion and Machinery spaces",
    "500": "Systems",
    "600": "Electric Systems",
    "700": "Navigation, Communication, Entertainment",
    "800": "Rigging and Sailing",
    "900": "Miscellaneous",
}

# Generic document-type folders — structural routing, never equipment. Matched
# case-insensitively after stripping any leading numeric code. These tell Part 2
# (vision) where the schematics / photos live.
DOC_TYPE_FOLDERS = {
    "manuals", "manual", "schematics", "schematic", "spares", "spare parts",
    "inventory", "information", "drawings", "drawing", "photos", "photo",
    "operations", "operation", "mapping", "testing", "test", "wiring details",
    "performance", "preformance", "bearing", "base", "specification",
    "specifications", "general items", "passage logs", "old - archive",
    "farr designs",
}

# Top-level groups that are documentation / operational, not equipment systems.
NON_EQUIPMENT_GROUPS = {
    "general condition", "inventory and consumables", "checklists and logs",
    "planning and research", "works and plans", "handover notes",
    "acceptance trials", "class and compliance", "weight and stability",
    "owners manuals", "owner's manuals",
}

# An acronym/nickname token: short, upper-case, may carry digits or a hyphen
# (MPCS, MAPS, BEL, SCU3, EDN-S, ISG). Requires at least one A–Z letter so pure
# numbers don't qualify.
_ACRONYM_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{1,7}$")

# Leading numeric code: "400, ...", "460, ...", "00 Weight...", "651, BAE...".
_LEADING_CODE_RE = re.compile(r"^\s*(\d{2,3})\s*(?:[,\.\-]|\s)\s*(.*)$")

# Trailing SFI tag in square brackets: "... [410]", "... [BAE]".
_BRACKET_RE = re.compile(r"\[([^\]]+)\]\s*$")

# Parenthetical: "Maker (Function)" / "Name (ACRONYM)".
_PAREN_RE = re.compile(r"^(.*?)\s*\(([^)]+)\)\s*(.*)$")


def strip_leading_code(name: str) -> Tuple[Optional[str], str]:
    """
    Split a leading numeric code from a folder name.

    "460, Thrusters"            -> ("460", "Thrusters")
    "00 Weight and Stability"   -> ("00",  "Weight and Stability")
    "GPM-12 drive motor"        -> (None,  "GPM-12 drive motor")
    """
    m = _LEADING_CODE_RE.match(name)
    if m:
        return m.group(1), m.group(2).strip()
    return None, name.strip()


def region_for_code(code: Optional[str]) -> Optional[str]:
    """Map any SFI code to its X00 region code (e.g. '460' -> '400')."""
    if not code:
        return None
    digits = re.sub(r"\D", "", code)
    if not digits:
        return None
    n = int(digits)
    if n < 100:           # 001 General Condition uses 00/10/20… sub-codes
        return "000"
    return f"{n // 100}00"


def is_acronym(token: str) -> bool:
    """True if a token looks like an equipment acronym / nickname."""
    t = token.strip()
    return bool(_ACRONYM_RE.match(t) and re.search(r"[A-Z]", t))


def is_doc_type_folder(name: str) -> bool:
    """True if a folder is a generic document-type routing folder."""
    _, rest = strip_leading_code(name)
    return rest.strip().lower() in DOC_TYPE_FOLDERS


def is_non_equipment_group(name: str) -> bool:
    """True if a folder is a documentation / operational group, not equipment."""
    _, rest = strip_leading_code(name)
    return rest.strip().lower() in NON_EQUIPMENT_GROUPS


def parse_equipment_name(name: str) -> Dict[str, object]:
    """
    Parse an equipment folder/file name into structured fields.

    Returns a dict:
        name        cleaned descriptive name (code + bracket stripped)
        make        maker, when the parenthetical is a FUNCTION (Maker (Function))
        model       product/model, for product-named folders (no maker pattern)
        category    function/category, when identifiable
        acronyms    list of harvested acronym tokens (nicknames)
        sfi_tag     contents of a trailing [..] tag, if any

    Heuristics (vessel-agnostic):
      - "Mastervolt (Batteries & Chargers)" -> make=Mastervolt, category=Batteries & Chargers
        (parenthetical is Title-Case words = a FUNCTION; text before = the MAKER)
      - "Modular Propulsion Control System (MPCS)" -> name kept, acronyms=[MPCS]
      - "Inverter (BEL)" -> category=Inverter, acronyms=[BEL]
        (parenthetical is acronym-shaped = a NICKNAME; text before describes the unit)
      - "GPM-12 drive motor" / "EDN-S" / "Generators" -> model/name only
    """
    raw = name.strip()

    # 1. Trailing [SFI] tag.
    sfi_tag: Optional[str] = None
    bm = _BRACKET_RE.search(raw)
    if bm:
        sfi_tag = bm.group(1).strip()
        raw = _BRACKET_RE.sub("", raw).strip()

    # 2. Leading numeric code (kept out of the descriptive fields).
    _, raw = strip_leading_code(raw)

    out: Dict[str, object] = {
        "name": raw, "make": None, "model": None,
        "category": None, "acronyms": [], "sfi_tag": sfi_tag,
    }

    # 3. Parenthetical.
    pm = _PAREN_RE.match(raw)
    if pm:
        before = pm.group(1).strip()
        inside = pm.group(2).strip()
        after = pm.group(3).strip()
        if is_acronym(inside):
            # Nickname/acronym. Text before is the descriptive identifier; keep it
            # as the model so the unit counts as identified (e.g. "Inverter (BEL)"
            # -> model="Inverter", acronyms=["BEL"]).
            out["acronyms"] = [inside]
            label = (before + (" " + after if after else "")).strip() or inside
            out["name"] = label
            out["model"] = label
        else:
            # Function. Text before is the maker.
            out["make"] = before or None
            out["category"] = inside or None
            out["name"] = before or raw
        return out

    # 4. No parenthetical. Bare product / model / generic category name.
    if is_acronym(raw):
        out["acronyms"] = [raw]
    out["model"] = raw
    return out


def harvest_acronyms(name: str) -> Dict[str, str]:
    """
    Extract acronym → expansion pairs from a single name.

    "Modular Propulsion Control System (MPCS)" -> {"MPCS": "Modular Propulsion Control System"}
    "EDN-S"                                     -> {"EDN-S": ""}   (no expansion available)
    "Inverter (BEL)"                            -> {"BEL": "Inverter"}
    """
    glossary: Dict[str, str] = {}
    _, rest = strip_leading_code(name)
    rest = _BRACKET_RE.sub("", rest).strip()

    pm = _PAREN_RE.match(rest)
    if pm:
        before = pm.group(1).strip()
        inside = pm.group(2).strip()
        if is_acronym(inside):
            glossary[inside] = before
    elif is_acronym(rest):
        glossary[rest] = ""
    return glossary
