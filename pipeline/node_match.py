"""
§9e SEMANTIC MATCHER — resolve a discovered component against the existing
Register node tree. The structural prerequisite for the §9d node writer and for
nameplate→node registration.

THE ONE QUESTION IT ANSWERS: is the component just found (in a drawing, a
nameplate, a CAN topology, an Exocet channel) the SAME PHYSICAL THING as a node
already in the Register, or is it new?

IDENTITY IS SEMANTIC, NOT TAG-BASED. Different drafting houses tag the same
physical component differently (the bilge-valve proof: the SWS hydraulic
schematic's 026-xx tags appear nowhere on the GM electrical sheet, which uses
zone names). So the match key is the STABLE semantic identity — function +
zone + equipment type — with make / model / acronym as strong corroborators.
A tag number is never the key.

RESOLVE-FIRST CONTRACT (what the §9d writer calls per discovered component):
  confident match  → ATTACH the new source's facts to the existing node
                     (this is the §2 multi-source cross-reference in action).
  no match         → CREATE a new node FLAGGED for engineer review. "New
                     equipment discovered with no Register counterpart" is a
                     FINDING worth surfacing, never a silent create.

Reusable: the same resolve() serves CAN-topology↔Register and Exocet-channel
matching — the component dict and the candidate set are the only things that
change.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import config

_STOP = {"the", "and", "of", "a", "for", "to", "system", "unit", "general",
         "features", "appliances", "applicances", "drive"}
ATTACH_THRESHOLD = 0.45  # >= this on the best candidate → confident attach

# GENERIC/PLACEHOLDER model-or-make VALUES that carry no real identity signal —
# excluded from scoring entirely (caught 2026-07-05 via the PMS cross-reference:
# a YMP equipment entry with model="custom" scored 0.5 against an unrelated
# Register node whose model field happened to be "Custom Flat Rack Proposal...").
_GENERIC_VALUES = {"custom", "n a", "na", "asstd", "tbc", "standard", "generic",
                   "various", "assorted", "unknown", "n/a"}


def _token_contains(needle: str, haystack: str) -> bool:
    """True if needle's tokens appear as a CONTIGUOUS run within haystack's
    tokens (word-boundary safe) — NOT a raw substring check. A raw substring
    check lets a short string falsely match inside an unrelated longer word
    (caught 2026-07-05 via the PMS cross-reference: model 'crew' is a raw
    substring of 'screw', so a pump entry mentioning '...Single Screw...'
    falsely scored against the Register's 'Crew' node). Same fix already
    applied to pipeline/power_path.py's connection matching the same day."""
    nt, ht = needle.split(), haystack.split()
    if not nt or not ht:
        return False
    for i in range(len(ht) - len(nt) + 1):
        if ht[i:i + len(nt)] == nt:
            return True
    return False


def load_register(vessel: Optional[str] = None) -> List[Dict[str, Any]]:
    vessel = vessel or config.VESSEL_NAMESPACE
    data = json.loads((config.STATE_DIR / f"register_{vessel}.json").read_text())
    return data["entries"]


def _n(s: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _terms(*parts: Any) -> set:
    """Token set from free-text identity parts (name/type/function/category)."""
    toks: set = set()
    for p in parts:
        if p is None:
            continue
        if isinstance(p, (list, tuple)):
            for x in p:
                toks |= _terms(x)
            continue
        for t in _n(str(p)).split():
            if len(t) >= 2 and t not in _STOP:
                toks.add(t)
    return toks


def _comp_terms(comp: Dict[str, Any]) -> set:
    return _terms(comp.get("name"), comp.get("equipment_type"),
                  comp.get("function"), comp.get("category"))


def _entry_terms(e: Dict[str, Any]) -> set:
    return _terms(e.get("name"), e.get("category"), e.get("functions"),
                  e.get("subsystem_label"))


def _score(comp: Dict[str, Any], e: Dict[str, Any]) -> tuple:
    """Score one Register entry against the discovered component. Returns (score, reasons)."""
    s = 0.0
    why: List[str] = []
    cmodel, emodel = _n(comp.get("model")), _n(e.get("model"))
    cmake, emake = _n(comp.get("make")), _n(e.get("make"))
    cacr = _n(comp.get("acronym"))
    eacr = {_n(a) for a in (e.get("acronyms") or [])}

    model_ok = (cmodel and emodel and cmodel not in _GENERIC_VALUES and emodel not in _GENERIC_VALUES
                and (cmodel == emodel or _token_contains(cmodel, emodel) or _token_contains(emodel, cmodel)))
    if model_ok:
        s += 0.5; why.append("model")
    make_ok = (cmake and emake and cmake not in _GENERIC_VALUES and emake not in _GENERIC_VALUES
               and (cmake == emake or _token_contains(cmake, emake) or _token_contains(emake, cmake)))
    if make_ok:
        s += 0.25; why.append("make")
    if cacr and cacr in eacr:
        s += 0.45; why.append("acronym")

    ct, et = _comp_terms(comp), _entry_terms(e)
    if ct and et:
        j = len(ct & et) / len(ct | et)
        if j > 0:
            s += 0.4 * j; why.append(f"terms={j:.2f}")

    if comp.get("region_code") and e.get("region_code") == comp.get("region_code"):
        s += 0.10; why.append("region")
    if comp.get("subsystem_code") and e.get("subsystem_code") == comp.get("subsystem_code"):
        s += 0.15; why.append("subsystem")
    return round(s, 3), why


_MIN_DISTINCTIVE_MAKE_LEN = 4  # 'BAE' (3 chars) stays excluded from this boost


def _exact_make_boost(comp: Dict[str, Any],
                      register: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    An EXACT (full-string, not just token-contains), DISTINCTIVE make match is
    a strong identity signal even when surrounding term-overlap is weak — a
    PMS/document entry titled "...System" often shares few words with a
    Register node's own name, but the manufacturer name alone can still be
    unambiguous. Real case, 2026-07-06: a PMS entry with make="Termodinamica"
    scored only 0.294 against the Register's aircon nodes (below the 0.45
    threshold) despite "Termodinamica" being a distinctive manufacturer name
    with no unrelated collisions elsewhere in the Register.

    Fires ONLY when:
      - comp's make normalizes to an EXACT full-string match with a
        candidate's make (containment alone is already handled by the
        normal scorer and is deliberately NOT enough here — exact only);
      - that make string clears a minimum length and isn't in the generic
        stoplist (no boosting on "BAE" or a bare "marine");
      - every Register entry sharing that exact make belongs to ONE
        equipment FAMILY (one parent + its children, or a single standalone
        node). If the same exact make is shared across UNRELATED families
        (e.g. "Gianneschi" appears on a bilge pump AND a fire pump AND a
        generic pumps bucket — three unrelated pieces of equipment), this
        does NOT fire — surfaced as ambiguous instead of guessed. When it
        does fire and multiple nodes tie within the one family, prefers the
        PARENT node over a sibling/child — never picks a leaf arbitrarily.
    Returns an alternate resolve()-shaped result, or None if it doesn't apply.
    """
    cmake = _n(comp.get("make"))
    if not cmake or cmake in _GENERIC_VALUES or len(cmake) < _MIN_DISTINCTIVE_MAKE_LEN:
        return None
    exact_matches = [e for e in register if _n(e.get("make")) == cmake]
    if not exact_matches:
        return None
    families = {e.get("parent_id") or e["equipment_id"] for e in exact_matches}
    if len(families) != 1:
        return None  # shared across unrelated families -- don't guess which one
    parent_id = next(iter(families))
    target = next((e for e in exact_matches if e["equipment_id"] == parent_id), exact_matches[0])
    return {
        "action": "attach", "match": target, "match_id": target["equipment_id"],
        "confidence": 0.25, "reason": ["make_exact_distinctive"],
        "candidates": [(0.25, e["equipment_id"], ["make_exact_distinctive"]) for e in exact_matches[:3]],
    }


def resolve(comp: Dict[str, Any], register: Optional[List[Dict[str, Any]]] = None,
            *, threshold: float = ATTACH_THRESHOLD) -> Dict[str, Any]:
    """
    Resolve a discovered component against the Register.

    comp: any of {name, equipment_type, function, category, make, model, acronym,
    region_code, subsystem_code}. Returns:
      {action: "attach"|"create_flagged", match: entry|None, confidence,
       reason, candidates:[(score, equipment_id, reasons)]}
    """
    register = load_register() if register is None else register
    scored = sorted(((*_score(comp, e), e) for e in register),
                    key=lambda x: -x[0])
    top_score, top_why, top_e = scored[0]
    confident = top_score >= threshold
    # guard: a bare zone/region-only match (no identity signal) is NOT confident
    identity_signal = any(w.startswith(("model", "make", "acronym", "terms")) for w in top_why)
    confident = confident and identity_signal
    if not confident:
        boost = _exact_make_boost(comp, register)
        if boost:
            return boost
    return {
        "action": "attach" if confident else "create_flagged",
        "match": top_e if confident else None,
        "match_id": top_e["equipment_id"] if confident else None,
        "confidence": top_score,
        "reason": top_why,
        "candidates": [(sc, e["equipment_id"], wy) for sc, wy, e in scored[:3]],
    }
