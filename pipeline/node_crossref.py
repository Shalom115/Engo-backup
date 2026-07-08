"""
NODE CROSS-REFERENCE STEP (engineer-mandated 2026-07-06).

The gap this closes, in the engineer's own words: "if I hadn't told you, you
wouldn't have cross-referenced the 114a drawing with the P&ID and the ONYX
together." Every fact-attaching pass built so far (hydraulic, electrical,
PMS) writes facts onto a node from ONE source at a time and stops — nothing
in the pipeline ever went back and asked "now that this node has facts from
several different doc classes, do they agree, and are any expected classes
still missing?" This module is that step, run explicitly after fact-writing,
not left to happen only when a human notices.

TWO THINGS THIS STEP DOES, mirroring §9d's existing completeness checklist
(Decision 2) but making it ACTIVE rather than just a bookkeeping field:

1. COMPLETENESS CHECK — is this node's expected doc-class set covered yet?
   The engineer's own answer for a typical system-equipment node: PMS,
   inventory, manual, hydraulic/piping schematic, electrical schematic,
   monitoring system (e.g. ONYX) — "every system will be a bit different,"
   so this is a DEFAULT, not a hardcoded universal rule; a system archetype
   (see prompts/system_archetypes.md) may narrow or widen the set.

2. CROSS-REFERENCE — for a node that already has facts from more than one
   doc class, do those facts actually agree? Identity-bearing fact kinds
   (make, model, block_identity, hydraulic_control_function, etc.) get
   compared PAIRWISE across source_types using the same token-boundary
   matching already validated in node_match.py (never raw substring — same
   bug class fixed there applies here). Agreement across independent
   sources is a CONFIDENCE BOOST (the corroboration Decision-... already
   values); disagreement is a FINDING, not a silent pick — same discipline
   as the existing conflict/confirmation-list mechanism, reused here rather
   than re-invented.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# The engineer's own default set, 2026-07-06: "for the bilge example ONLY it
# will be the PMS, inventory, manuals, schematics, the electrical drawings,
# the onyx and that's pretty much it." A system archetype may override this
# (see prompts/system_archetypes.md per-system notes on which classes apply/
# don't) but this is the sensible starting point for any system-equipment node.
DEFAULT_EXPECTED_DOC_CLASSES = [
    "pms", "inventory", "manual", "hydraulic_schematic",
    "electrical_schematic", "monitoring_system",
]

# Existing source_type strings already in use across the pipeline's history
# map onto the 6-class vocabulary above (naming drifted across sessions —
# this reconciles it rather than requiring a rename of everything already
# written to the Register).
_SOURCE_TYPE_ALIASES = {
    "schematic": "hydraulic_schematic",
    "hydraulic_schematic": "hydraulic_schematic",
    "system_schematic": "hydraulic_schematic",
    "bom_table": "hydraulic_schematic",  # a BOM is read off the same schematic set
    "electrical_schematic": "electrical_schematic",
    "pms": "pms",
    "inventory": "inventory",
    "manual": "manual",
    "onyx": "monitoring_system",
    "monitoring_system": "monitoring_system",
}

# Fact kinds worth cross-checking for agreement across sources — all of
# these answer "what specific equipment IS this", so they're compared as ONE
# group rather than kept in separate per-kind buckets: a `make`/`model` pair
# from one source and a free-text `identity` sentence from another are both
# identity claims about the SAME node and must be checked against each other
# (found live 2026-07-06: keeping them in separate kind-buckets meant a real
# BOM-sourced `identity` fact and a test `make` fact never got compared at
# all — the cross-reference silently found nothing to say). Deliberately
# excludes function/role facts (e.g. `hydraulic_control_function`) — those
# describe what a component DOES, not what it IS, a different question.
_IDENTITY_KINDS = {"make", "model", "block_identity", "identity"}


def _norm_class(source_type: Optional[str]) -> Optional[str]:
    return _SOURCE_TYPE_ALIASES.get((source_type or "").lower())


def check_completeness(node: Dict[str, Any],
                       expected: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Which of the expected doc classes has this node actually seen facts from,
    and which are still missing? Reads real fact provenance (source_type on
    each fact), not just the node's own possibly-stale `fact_classes_present`
    list, so this stays correct even if that field drifts.
    """
    expected = expected or DEFAULT_EXPECTED_DOC_CLASSES
    seen = set()
    for f in node.get("facts", []):
        cls = _norm_class((f.get("provenance") or {}).get("source_type"))
        if cls:
            seen.add(cls)
    missing = [c for c in expected if c not in seen]
    return {
        "expected": expected,
        "present": sorted(seen),
        "missing": missing,
        "complete": not missing,
    }


def _token_contains(needle: str, haystack: str) -> bool:
    """Same discipline as node_match._token_contains — contiguous token
    match, never raw substring (the 'crew' inside 'screw' bug applies here
    exactly as it did in §9e)."""
    nt = [t for t in re.split(r"[^a-z0-9]+", (needle or "").lower()) if t]
    ht = [t for t in re.split(r"[^a-z0-9]+", (haystack or "").lower()) if t]
    if not nt or not ht:
        return False
    for i in range(len(ht) - len(nt) + 1):
        if ht[i:i + len(nt)] == nt:
            return True
    return False


def _values_agree(a: str, b: str) -> bool:
    a, b = (a or "").strip(), (b or "").strip()
    if not a or not b:
        return False
    return a.lower() == b.lower() or _token_contains(a, b) or _token_contains(b, a)


def cross_reference(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Compare identity-bearing facts across DIFFERENT source_types on the same
    node. Returns a list of findings:
      {"kind", "status": "corroborated"|"disagreement",
       "values": [{"value", "source_type", "source_doc"}, ...]}
    Corroboration (independent sources agreeing) is itself worth recording —
    it's the confidence boost this project's Master Spec §2 already treats
    as the point of multi-source ingestion, made explicit here instead of
    implicit. Disagreement is surfaced, never silently resolved — same rule
    as the existing identity_status='conflict' mechanism in node_write.py,
    which this function feeds rather than replaces.
    """
    entries: List[Dict[str, Any]] = []
    # Every Register node already carries make/model set at the ORIGINAL
    # folder-walk build (pipeline/register.py) — a real, distinct identity
    # signal (the yard's own file/folder naming) that predates the facts[]
    # array entirely. Found live 2026-07-06: this was invisible to
    # cross-reference (only facts[] was scanned), so a node could have a
    # perfectly good folder-walk identity AND a new PMS/schematic identity
    # fact and never have them compared — undercounting real corroboration
    # opportunities that already exist in EVERY node, not just ones that
    # happen to have two facts[] entries. Included here as a synthetic
    # "register_seed" entry, kept OUT of DEFAULT_EXPECTED_DOC_CLASSES
    # (it's not something to go fetch, it's already on every node) but very
    # much part of what gets cross-referenced.
    for key, kind in (("make", "make"), ("model", "model")):
        val = node.get(key)
        if val:
            entries.append({
                "fact_kind": kind, "value": str(val), "source_type": "register_seed",
                "source_doc": f"Register folder-walk build ({node.get('equipment_id')})",
            })
    for f in node.get("facts", []):
        kind = f.get("kind")
        if kind not in _IDENTITY_KINDS:
            continue
        cls = _norm_class((f.get("provenance") or {}).get("source_type"))
        if not cls:
            continue
        val = f.get("value")
        val_str = val if isinstance(val, str) else str(val)
        entries.append({
            "fact_kind": kind, "value": val_str, "source_type": cls,
            "source_doc": (f.get("provenance") or {}).get("source_doc"),
        })

    distinct_sources = {e["source_type"] for e in entries}
    if len(distinct_sources) < 2:
        return []  # nothing to cross-reference -- only one doc class has made an identity claim

    # pairwise compare across DIFFERENT source_types only (same-source
    # duplicates aren't a cross-reference question); a `make` fact from one
    # source IS compared against an `identity` fact from another -- both are
    # claims about the same node's identity, regardless of their own kind.
    agree_pairs, disagree_pairs = [], []
    seen_pairs = set()
    for i, e1 in enumerate(entries):
        for e2 in entries[i + 1:]:
            if e1["source_type"] == e2["source_type"]:
                continue
            key = tuple(sorted([e1["source_type"], e2["source_type"]]))
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            if _values_agree(e1["value"], e2["value"]):
                agree_pairs.append((e1, e2))
            else:
                disagree_pairs.append((e1, e2))

    values_out = [{"value": e["value"], "fact_kind": e["fact_kind"],
                  "source_type": e["source_type"], "source_doc": e["source_doc"]}
                 for e in entries]
    if disagree_pairs:
        return [{"kind": "identity", "status": "disagreement", "values": values_out}]
    if agree_pairs:
        return [{"kind": "identity", "status": "corroborated", "values": values_out}]
    return []


def report(node: Dict[str, Any], expected: Optional[List[str]] = None) -> Dict[str, Any]:
    """One-call entry point: completeness + cross-reference, ready to log or
    attach as a node-level summary fact."""
    return {
        "equipment_id": node.get("equipment_id"),
        "completeness": check_completeness(node, expected),
        "cross_reference": cross_reference(node),
    }
