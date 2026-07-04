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

    if cmodel and emodel and (cmodel == emodel or cmodel in emodel or emodel in cmodel):
        s += 0.5; why.append("model")
    if cmake and emake and (cmake == emake or cmake in emake or emake in cmake):
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
    return {
        "action": "attach" if confident else "create_flagged",
        "match": top_e if confident else None,
        "match_id": top_e["equipment_id"] if confident else None,
        "confidence": top_score,
        "reason": top_why,
        "candidates": [(sc, e["equipment_id"], wy) for sc, wy, e in scored[:3]],
    }
