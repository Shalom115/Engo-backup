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
    """One line per active node: id — name make model (subsystem).

    NO AUTOMATIC DUPLICATE COLLAPSING. It was attempted (2026-07-31) and
    withdrawn: grouping nodes by shared id tokens merges transitively through
    short generic ids, so `460-thruster-system` pulled the BOW and STERN
    thrusters into one node, `695-fire-alarm` swallowed both fire pumps, and
    `690-lts-crew` absorbed the crew-mess fancoil and the crew medical locker.
    That is the third time token matching has produced confident nonsense on
    equipment identity, and no threshold fixes it.

    The Register genuinely does carry duplicate ids for the same machine
    (`620-modular-accessory-power-system-maps` beside `626-maps`,
    `620-system-control-unit-scu3` beside `628-scu3`). That is a real problem
    and it belongs on the engineer's red-pen list as a MERGE decision, not to
    a heuristic. What removes the routing ambiguity safely is the engineer's
    own load map, resolved against the sheet's labels in code — see
    `pipeline/map_resolve.py`.
    """
    lines = []
    for e in _reg()["entries"]:
        if e.get("retired"):
            continue
        lines.append(_index_line(e))
    return "\n".join(lines)


def _index_line(e: Dict[str, Any]) -> str:
    bits = [e.get("name") or ""]
    if e.get("make"):
        bits.append(e["make"])
    if e.get("model"):
        bits.append(e["model"])
    if e.get("subsystem_label"):
        bits.append(f"({e['subsystem_label']})")
    return f"{e['equipment_id']} — {' '.join(b for b in bits if b)}"


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


# ---------------------------------------------------------------------------
# CORPUS KNOWLEDGE (2026-07-26) — the gap the engineer found on the aft
# companionway: "the fact there is an inflatable seal on both companionways is
# GIVEN IN THE OWNER MANUAL and should have been known to engo."
#
# It was not known because this substrate only ever read the REGISTER (nodes +
# facts) and the glossary. The ingested DOCUMENT CORPUS — owner's manual,
# handover, OEM manuals — sat in the vector store and was never queried during
# composition. A drawing tells you what is wired; the manual tells you what the
# thing IS and DOES. Composition needs both.
# ---------------------------------------------------------------------------

# Anything above this cosine distance is not really about the subject — it is
# the embedder returning "best of what's there" (a known behaviour of this
# store). Measured on real sheet subjects: genuine hits land 0.35-0.46
# (bilge valves -> Burkert selection valves, companionway -> the Likon seal,
# hydraulic panels -> the MYT function list), while off-topic filler starts
# around 0.53 (a nav-lights sheet pulling another project's propeller-pitch
# alarm list, a Finnish hand-pump manual). Weak context is NOT harmless here:
# it is exactly the material a composition weaves into an invented scenario,
# which is the cross-class contamination failure already fixed once. An empty
# corpus block is a good outcome; a plausible irrelevant one is not.
# Set at 0.45: across the sheet subjects measured so far every genuinely
# on-subject hit landed at or below 0.424 while generic OEM catalogue filler
# (a Finnish hand-pump manual, a Danfoss pump catalogue) started at 0.452 —
# a clean gap, not a hairline. PROVISIONAL: this is a handful of observations,
# not an eval harness, and should be re-set against one when it exists. It is
# deliberately biased toward precision — a missing corpus line costs a naming
# hint, a plausible irrelevant one costs an invented scenario.
CORPUS_MAX_DISTANCE = 0.45


def corpus_context(subject: str, k: int = 4, max_chars: int = 1600,
                   max_distance: float = CORPUS_MAX_DISTANCE) -> str:
    """
    What the vessel's own documentation says about this sheet's subject.

    Retrieval failure is never fatal to a composition — it degrades to "(no
    corpus context)" rather than killing the run.
    """
    if not subject or not subject.strip():
        return ""
    try:
        from pipeline.retrieve import search
        hits = search(subject.strip(), k=k, distance_threshold=max_distance)
    except Exception:
        return ""
    if not hits:
        return ""
    out = ["VESSEL DOCUMENTATION on this subject (from the ingested corpus — "
           "the manuals already know things the drawing does not spell out; "
           "use this to name equipment and understand what a circuit is FOR, "
           "but never let it override what the drawing actually shows):"]
    used = 0
    seen = set()
    for h in hits:
        txt = " ".join((h.get("text") or h.get("document") or "").split())
        src = (h.get("metadata") or {}).get("file_name", "")
        if not txt:
            continue
        # The vessel keeps the same list under several filenames (inventory
        # exports, Sealogs snapshots, AutoRecovered copies). The same row
        # arriving four times both burns the budget and READS AS CORROBORATION
        # from four sources when it is one fact copied — so collapse them and
        # name every file it came from.
        key = txt[:140].lower()
        if key in seen:
            continue
        seen.add(key)
        snippet = txt[:400]
        used += len(snippet)
        out.append(f"  [{src}] {snippet}")
        if used >= max_chars:
            break
    return "\n".join(out)
