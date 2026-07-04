"""
Manufacturer part-number GLOSSARY + 3-bucket ROUTER + format validation (3a).

Replaces the seed partnum_format.py. Three jobs, all POST-extraction (the
gold-blind extractor in schematic_extract never imports this):

  BUILD 1 — route_text(): every located text → exactly one of three buckets
    A = a manufacturer part-number (the cross-source JOIN KEY), sub-typed by
        item-type (valve-body vs solenoid-cartridge vs spool vs coil vs seal —
        physically different parts, different schemes).
    B = a named component / model (e.g. "PVG 32") OR a component-type token
        (PVEU, solenoid, spool…). EQUIPMENT, not noise — gets its own manual
        lookup. "not a part number" must NEVER mean "not equipment".
    C = descriptive context (rail tags, settings, flow ratings, labels).

  BUILD 2 — the GLOSSARY: per manufacturer → per item-type → {scheme, example,
    system, source}. A PRIOR that VALIDATES a read's shape; it NEVER originates
    a value. Unknown scheme → FLAG, never discard (next vessel has new makers).
    Generic third-party standards (SKF bearings) tagged not-a-join-key.

  BUILD 4 — validate_read(): 3a. On a scheme-miss where one glyph substitution
    (B/8, O/0, S/5, I/1) would make it valid, return a reread_suggestion — a
    STRUCTURED, un-launderable object (not a bare value) the node writer is
    incapable of persisting as a fact. Search/manual-fetch (3b) is NOT here.

§0.5: schemes/categories are manufacturer-general (transfer to any vessel using
that maker), seeded from Gelliceaux inventory as PRIORS — not Gelliceaux gold
locks. Extend per vessel; flag the unknown.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# ---- BUILD 2: manufacturer glossary -----------------------------------------
# Per manufacturer: system, models (Bucket-B tokens), and item_types each with a
# shape regex + example + where the pattern was learned. Patterns are PRIORS.
GLOSSARY: Dict[str, Dict[str, Any]] = {
    "danfoss": {
        "system": "hydraulics",
        "models": ["pvg 32", "pvg32", "pvg"],
        "item_types": {
            "valve_body":        {"re": r"^157B\d{4}$",  "eg": "157B5111", "src": "drawings"},
            "solenoid_cartridge":{"re": r"^1116\d{4}$",  "eg": "11166832", "src": "drawings"},
        },
    },
    "finder": {  # pattern from INVENTORY, not drawings
        "system": "electrical_relays",
        "models": [],
        "item_types": {
            "relay": {"re": r"^\d{2}\.\d{2}(?:\.\d{1,4}){0,3}$", "eg": "56.32.9.024.0040", "src": "inventory"},
        },
    },
    "hundested": {
        "system": "propulsion_cpp",
        "models": ["pcu"],
        "item_types": {
            "seal_shim_filter": {"re": r"^\d{6}F$", "eg": "203720F", "src": "inventory"},
        },
    },
    "oms": {
        "system": "thrusters",
        "models": ["h-0300-s", "h-0250-s"],
        "item_types": {
            "oring":    {"re": r"^SLO-\d{3}-\d{2,3}$",       "eg": "SLO-395-30",     "src": "inventory"},
            "seal_kit": {"re": r"^[A-Z]{3}-\d{2}-S-\d{2}-SK$","eg": "OBA-10-S-03-SK", "src": "inventory"},
            "anode":    {"re": r"^ANZ-\d{2}-\d{2}$",          "eg": "ANZ-12-01",      "src": "inventory"},
            "gasket":   {"re": r"^GST-\d{2}-S-\d{2}$",        "eg": "GST-10-S-01",    "src": "inventory"},
        },
    },
    "bae": {
        "system": "propulsion_power_electronics",
        "models": [],
        "item_types": {
            "part": {"re": r"^\d{3}[A-Z]\d{4}[PG]\d$", "eg": "235C9755P1", "src": "drawings"},
        },
    },
    "akasol": {
        "system": "ess_battery", "models": [],
        "item_types": {"part": {"re": r"^P\d{12}$", "eg": "P103000100010", "src": "inventory"}},
    },
    "parker_racor": {
        "system": "fuel_filtration", "models": [],
        "item_types": {"kit": {"re": r"^RK\d{5}$|^RK\d{2}-\d{4}$", "eg": "RK15211", "src": "inventory"}},
    },
    "gianneschi": {
        "system": "pumps", "models": [],
        "item_types": {"pump": {"re": r"^KACB[A-Z0-9]+$|^\d{2}AAC\d{3}[A-Z]?$", "eg": "KACB430101C", "src": "inventory"}},
    },
    "onyx": {
        "system": "automation", "models": [],
        "item_types": {"module": {"re": r"^OM\d{3}[ABFG]$", "eg": "OM960B", "src": "inventory"}},
    },
    "omega": {
        "system": "fuses", "models": [],
        "item_types": {"fuse": {"re": r"^F5X\d{3}A$", "eg": "F5X100A", "src": "inventory"}},
    },
}

# Generic third-party standards — a "part number" but NOT a proprietary join key.
GENERIC_PATTERNS: List[tuple] = [
    (re.compile(r"^600\d(?:-2RS[L]?)?$"), "SKF-style bearing"),  # 6006, 6004, 6005-2RSL
]

# Bucket-B component-type tokens — generic equipment words + maker actuation types.
# These are EQUIPMENT, not part numbers and not noise.
_COMPONENT_TOKENS = {
    "pveu", "pved", "spool", "solenoid", "coil", "cartridge", "valve", "sensor",
    "relay", "contactor", "breaker", "fuse", "manifold", "pump", "filter",
    "relief", "shuttle", "orifice", "check", "compensator",
}

# Bucket-C descriptive cues.
_RAIL_RE = re.compile(r"^(?:[MPTX]|LS|LS[_ ]?[AB]|[AB]|P[12]?|T[12]?)$", re.I)
_SETTING_RE = re.compile(r"^\d{1,4}\s*(?:bar|psi|lt/?min|l/?min|v|°|deg)?$", re.I)
_RATING_RE = re.compile(r"lt\s*/?\s*min|l\s*/?\s*min|\bbar\b|\bpsi\b", re.I)
# Reference designator: an in-drawing component tag (EV-6.1, Q13, Re4, F3, S23) —
# the SEMANTIC cross-link key (§5a), NOT a manufacturer part number.
_REFDES_RE = re.compile(r"^[A-Za-z]{1,3}-?\d+(?:\.\d+)*$")
# A token that LOOKS like a part code: alphanumeric, >=4 chars, has a digit.
_CODE_LIKE = re.compile(r"^[A-Z0-9][A-Z0-9.\-/]{3,}$")

_GLYPH_CONFUSIONS = {"8": "B", "B": "8", "0": "O", "O": "0", "5": "S", "S": "5", "1": "I", "I": "1"}


def _norm(s: str) -> str:
    return (s or "").strip().upper().replace(" ", "")


def classify_partnum(text: str) -> Optional[Dict[str, Any]]:
    """Match `text` against the glossary schemes. Returns the first hit:
    {manufacturer, item_type, scheme, generic, join_key} or None (no scheme)."""
    v = _norm(text)
    for pat, label in GENERIC_PATTERNS:
        if pat.match(v):
            return {"manufacturer": None, "item_type": label, "scheme": pat.pattern,
                    "generic": True, "join_key": False}
    for maker, info in GLOSSARY.items():
        for itype, spec in info["item_types"].items():
            if re.match(spec["re"], v):
                return {"manufacturer": maker, "item_type": itype, "scheme": spec["re"],
                        "generic": False, "join_key": True, "system": info["system"]}
    return None


def _is_model(text: str) -> Optional[str]:
    low = (text or "").lower()
    for maker, info in GLOSSARY.items():
        for m in info.get("models", []):
            if m and m in low:
                return maker
    return None


def route_text(text: str) -> Dict[str, Any]:
    """
    BUILD 1 — route one located text into bucket A / B / C by general rule.
    Returns {text, bucket, ...}: A→part number (join key), B→component/model,
    C→descriptive. A code-like token matching no scheme is bucket A but FLAGGED
    (never discarded). Nothing is dropped.
    """
    raw = (text or "").strip()
    out: Dict[str, Any] = {"text": raw}
    hit = classify_partnum(raw)
    if hit:
        out.update(bucket="A", **hit)
        return out
    maker = _is_model(raw)
    if maker:
        out.update(bucket="B", kind="model", manufacturer=maker)
        return out
    low = raw.lower()
    # a flow/pressure rating phrase ("spool 40 lt/min", "220 bar") is descriptive
    if _RATING_RE.search(low):
        out.update(bucket="C", kind="rating")
        return out
    if any(tok in low.split() or tok == low for tok in _COMPONENT_TOKENS) or low in _COMPONENT_TOKENS:
        out.update(bucket="B", kind="component_type")
        return out
    if _RAIL_RE.match(raw):
        out.update(bucket="C", kind="rail")
        return out
    if _REFDES_RE.match(raw):  # in-drawing component tag (EV-6.1, Q13, Re4) — §5a key
        out.update(bucket="B", kind="reference_designator")
        return out
    if _SETTING_RE.match(raw):
        out.update(bucket="C", kind="setting")
        return out
    # code-like but no scheme → bucket A, FLAGGED for review (don't discard)
    if _CODE_LIKE.match(_norm(raw)) and any(c.isdigit() for c in raw):
        out.update(bucket="A", flagged="code-like but matches no known scheme — review",
                   join_key=False)
        return out
    out.update(bucket="C", kind="descriptive")
    return out


def _reread_suggestion(value: str, expected_re: str) -> Optional[Dict[str, Any]]:
    """If one glyph substitution makes `value` match `expected_re`, return an
    UN-LAUNDERABLE structured suggestion (Build 4) — never a bare value."""
    v = _norm(value)
    for i, ch in enumerate(v):
        alt = _GLYPH_CONFUSIONS.get(ch)
        if not alt:
            continue
        cand = v[:i] + alt + v[i + 1:]
        if re.match(expected_re, cand):
            return {"candidate": cand, "must_reread": True, "is_value": False,
                    "note": "glyph-substitution candidate — RE-READ the crop to confirm; NOT a fact value"}
    return None


def validate_read(text: str, *, system: Optional[str] = None) -> Dict[str, Any]:
    """
    3a — validate a read against the expected manufacturer scheme for `system`
    (or any scheme if system unknown). Returns {value, valid, item_type?,
    reread_suggestion?, flag?}. reread_suggestion is structured + un-launderable;
    the node writer must persist a part number ONLY from valid=True.value.
    """
    out: Dict[str, Any] = {"value": text}
    hit = classify_partnum(text)
    if hit:
        out.update(valid=True, manufacturer=hit.get("manufacturer"),
                   item_type=hit["item_type"], join_key=hit.get("join_key", True))
        return out
    out.update(valid=False, flag="matches no known manufacturer scheme — re-read / review")
    # try a glyph re-read against the schemes for the known system (most likely)
    candidates = []
    for maker, info in GLOSSARY.items():
        if system and info["system"] != system:
            continue
        for spec in info["item_types"].values():
            candidates.append(spec["re"])
    for expected_re in candidates:
        sug = _reread_suggestion(text, expected_re)
        if sug:
            out["reread_suggestion"] = sug
            break
    return out
