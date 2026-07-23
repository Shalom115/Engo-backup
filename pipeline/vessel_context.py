"""
VESSEL KNOWLEDGE SUBSTRATE — the "intrinsic truth" layer (engineer-mandated
2026-07-20).

The BEL lesson: BEL is defined in the owner's manual, the glossary, and the
locked facts — yet a pipeline pass called it unknown because that pass's
prompt happened not to include the glossary. The fix is architectural, not a
patch: EVERY equipment-knowledge pass (composition, disposition, HyDE,
node-write reasoning) draws from ONE substrate assembled here. Extraction
stays gold-blind (it reads structure, not vessel facts); everything after
extraction is vessel-aware BY CONSTRUCTION.

Substrate parts:
  - acronym glossary (glossary_<vessel>.json — authoritative expansions)
  - register index (equipment_id — name/make/model/subsystem)
  - established facts lookup: facts already on nodes, keyed by the
    identifiers they mention (EV-x.y, device ids) so a later sheet can never
    contradict or downgrade an earlier sheet's established truth unseen.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any, Dict, List

import config


def _reg() -> Dict[str, Any]:
    return json.loads(
        (config.STATE_DIR / f"register_{config.VESSEL_NAMESPACE}.json").read_text())


def glossary_block() -> str:
    """Authoritative acronym expansions. Never call one of these unknown."""
    path = config.STATE_DIR / f"glossary_{config.VESSEL_NAMESPACE}.json"
    if not path.exists():
        return "(no glossary file)"
    g = json.loads(path.read_text())
    entries = g.get("acronyms", g if isinstance(g, dict) else {})
    lines: List[str] = []
    if isinstance(entries, dict):
        for k, v in entries.items():
            exp = v.get("expansion") if isinstance(v, dict) else v
            if exp:
                lines.append(f"{k} = {exp}")
    elif isinstance(entries, list):
        for e in entries:
            if isinstance(e, dict) and e.get("acronym"):
                lines.append(f"{e['acronym']} = {e.get('expansion', '')}")
    return "\n".join(lines) if lines else "(empty glossary)"


def register_index() -> str:
    """One line per active node: id — name make model (subsystem)."""
    lines = []
    for e in _reg()["entries"]:
        if e.get("retired"):
            continue
        bits = [e.get("name") or ""]
        if e.get("make"):
            bits.append(e["make"])
        if e.get("model"):
            bits.append(e["model"])
        if e.get("subsystem_label"):
            bits.append(f"({e['subsystem_label']})")
        lines.append(f"{e['equipment_id']} — {' '.join(b for b in bits if b)}")
    return "\n".join(lines)


_IDENT_RE = re.compile(r"\bEV[-\s]?\d+\.\d+\b|\b[A-Z]{2,6}[-\s]?\d+(?:\.\d+)?\b")


def established_facts_for(text: str, max_facts: int = 40) -> str:
    """
    Cross-sheet truth: facts already written to nodes that mention any
    identifier appearing in `text` (e.g. 'EV-10.2'). A later pass must build
    on these, never re-derive or downgrade them (the EV-10.2 'solenoid'
    lesson — the deck-door PVEO fact already existed on the node).
    """
    def norm(s: str) -> str:
        return s.replace(" ", "").replace("-", "").upper()

    idents = set()
    for m in _IDENT_RE.finditer(text):
        n = norm(m.group(0))
        idents.add(n)
        # EV10.2A (a solenoid side) must also match the function EV10.2
        stripped = n.rstrip("ABCDEFGH")
        if stripped != n and len(stripped) >= 4:
            idents.add(stripped)
    if not idents:
        return "(none)"
    # ENGINEER-authority facts first — a red-pen traced loop must never lose
    # its slot to a routine extraction fact (the 114a plug-C-6/7 lesson:
    # one-fact-per-node truncation dropped the engineer's control_loop fact).
    hits: List[tuple] = []   # (priority, line)
    for e in _reg()["entries"]:
        if e.get("retired"):
            continue
        per_node = 0
        for f in e.get("facts") or []:
            blob = norm(json.dumps(f, default=str))
            if any(i in blob for i in idents):
                val = str(f.get("value", ""))
                prov = f.get("provenance") or {}
                src = prov.get("source_doc", "")
                pri = 0 if prov.get("authority") == "engineer" else 1
                dclass = prov.get("drawing_class") or prov.get("source_type") or "?"
                hits.append((pri,
                             f"[{e['equipment_id']}] [{dclass}] {f.get('kind','fact')}: "
                             f"{val[:300]}" + (f"  (source: {src})" if src else "")))
                per_node += 1
                if per_node >= 3:   # up to 3 facts per node, not 1
                    break
    hits.sort(key=lambda h: h[0])
    out = [line for _, line in hits[:max_facts]]
    return "\n".join(out) if out else "(none)"


# ---------------------------------------------------------------------------
# WP1 — RELATIONSHIP-TRIGGERED FACT EXCHANGE (engineer-approved wording,
# 2026-07-20): "Whenever a pass establishes ANY relationship between a drawn
# element and an equipment or system (controls, actuates, feeds, cools,
# monitors, part-of), it must at that moment: (a) resolve the related
# node(s); (b) pull their established facts into the reasoning BEFORE
# composing — never re-derive or downgrade what a node already knows;
# (c) attach what was newly learned to the correct side of the relationship.
# Identifier codes are merely one trigger; the RELATIONSHIP is the trigger."
#
# Implementation: pre-resolve candidate nodes by NAME/EQUIPMENT-WORD overlap
# with the sheet text (so 'GALVANIC PROTECTION CONTROL UNIT' pulls the
# galvanic node's facts even though no identifier code appears), union with
# the identifier-triggered set, engineer-authority facts first.
# ---------------------------------------------------------------------------

_STOPWORDS = {"system", "unit", "control", "controller", "pump", "valve",
              "panel", "port", "stbd", "main", "the", "and", "with", "for"}


def resolve_candidates(text: str, max_nodes: int = 150) -> List[str]:
    """Node ids whose NAME tokens appear in the sheet text (relationship
    trigger — no identifier needed). Distinctive tokens only."""
    low = text.lower()
    out: List[str] = []
    for e in _reg()["entries"]:
        if e.get("retired"):
            continue
        name_bits = " ".join(str(x) for x in (
            e.get("name"), e.get("make"), e.get("model")) if x).lower()
        toks = [t for t in re.split(r"[^a-z0-9]+", name_bits)
                if len(t) >= 5 and t not in _STOPWORDS]
        if toks and any(t in low for t in toks):
            out.append(e["equipment_id"])
        if len(out) >= max_nodes:
            break
    return out


def facts_for_nodes(node_ids: List[str], per_node: int = 4,
                    max_facts: int = 60) -> str:
    """Established facts of the given nodes, engineer-authority first.

    Fix (2026-07-22, the recurring truncation class): sort a node's OWN facts
    engineer-authority-first BEFORE the per_node cut, so a red-pen fact (e.g.
    the EV-9.3 '70 bar LS relief' answer) is never dropped because it happened
    to be the 4th fact written on the node."""
    wanted = set(node_ids)
    hits: List[tuple] = []
    for e in _reg()["entries"]:
        if e["equipment_id"] not in wanted or e.get("retired"):
            continue
        node_facts = []
        for f in e.get("facts") or []:
            prov = f.get("provenance") or {}
            pri = 0 if prov.get("authority") == "engineer" else 1
            node_facts.append((pri, f))
        node_facts.sort(key=lambda x: x[0])   # engineer facts first WITHIN node
        for pri, f in node_facts[:per_node]:
            val = str(f.get("value", ""))
            prov = f.get("provenance") or {}
            src = prov.get("source_doc", "")
            # tag the source CLASS so composition never weaves a different-class
            # fact into a new scenario (the fire-pump remote-start invention:
            # an [electrical] control_loop got woven into a fluid P&ID scenario)
            dclass = prov.get("drawing_class") or prov.get("source_type") or "?"
            hits.append((pri, f"[{e['equipment_id']}] [{dclass}] {f.get('kind','fact')}: "
                              f"{val[:400]}" + (f"  (source: {src})" if src else "")))
    hits.sort(key=lambda h: h[0])
    return "\n".join(line for _, line in hits[:max_facts]) or "(none)"


def relationship_context(text: str) -> str:
    """The WP1 substrate block: identifier-triggered facts UNION
    relationship-triggered facts of every name-resolved candidate node."""
    ident_block = established_facts_for(text)
    rel_ids = resolve_candidates(text)
    rel_block = facts_for_nodes(rel_ids) if rel_ids else "(none)"
    if ident_block == "(none)" and rel_block == "(none)":
        return "(none)"
    parts = []
    if ident_block != "(none)":
        parts.append(ident_block)
    if rel_block != "(none)":
        parts.append(rel_block)
    # dedupe lines, preserve order
    seen, out = set(), []
    for line in "\n".join(parts).split("\n"):
        if line not in seen:
            seen.add(line)
            out.append(line)
    return "\n".join(out)
