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
                hits.append((pri,
                             f"[{e['equipment_id']}] {f.get('kind','fact')}: "
                             f"{val[:300]}" + (f"  (source: {src})" if src else "")))
                per_node += 1
                if per_node >= 3:   # up to 3 facts per node, not 1
                    break
    hits.sort(key=lambda h: h[0])
    out = [line for _, line in hits[:max_facts]]
    return "\n".join(out) if out else "(none)"
