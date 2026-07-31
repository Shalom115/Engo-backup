"""
MAP RESOLVE — apply the engineer's maps to THIS sheet's labels, in code.

WHY. `compose` was handed all 205 load-map rows as raw text under the line
"use when a label matches", and left to do the matching itself. Measured on
GM-110a: the sheet prints `MAPS-1/2  2x5KW` and the map key is `MAPS-1/2`.
Those are not equal, nothing "matched", and the model fell back on its own
judgement and dumped the MAPS converters on the BAE hub — a node that has
existed for months, on a sheet the engineer had red-penned more than once.

The map is the engineer's authority. Deciding whether a printed label is an
instance of a mapped load is STRING WORK, and string work belongs in code
where it is deterministic, inspectable and testable — not in a prompt where it
is re-attempted from scratch on every call.

So: resolve here, and hand composition a short list of DECISIONS —
"on this sheet, these labels resolve to these nodes" — instead of a long list
of rules and the hope it applies them.

MATCHING IS TOLERANT OF WHAT DRAWINGS ACTUALLY PRINT, and nothing else:
  * ratings and sizes appended to a name  (MAPS-1/2  2x5KW  ->  MAPS-1/2)
  * a trailing colon or full stop         (MAPS:  /  NEG. BUS)
  * doubled internal whitespace
  * case
It is NOT fuzzy. There is no edit distance, no token overlap, no scoring — the
three previous attempts to route equipment by token similarity each produced
confident nonsense (a start key switch routed to "service reports and
invoices"; a bow thruster merged with a stern thruster). A key matches when it
appears as a whole phrase in the label, on word boundaries, or not at all.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

import config

# Values the engineer writes in a map that are NOT node ids.
NON_NODE = {"CLARIFY", "UNKNOWN", "TBC", "", "NONE", "N/A"}
# A key this short matches too much to be trusted as a phrase ("S", "N", "L1").
MIN_KEY = 3


def _norm(s: str) -> str:
    """Upper-case, punctuation-flattened, single-spaced — the form in which a
    printed label and a map key can be compared as phrases."""
    s = (s or "").upper().replace("—", "-").replace("–", "-")
    s = re.sub(r"[^A-Z0-9/&.+-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.rstrip(".: ")


def _phrase_in(key: str, label: str) -> bool:
    """Is `key` present in `label` as a whole phrase, on word boundaries?"""
    if not key or len(key) < MIN_KEY:
        return False
    if key == label:
        return True
    return re.search(rf"(?<![A-Z0-9]){re.escape(key)}(?![A-Z0-9])", label) is not None


def load_maps(drawing_class: str) -> List[Tuple[str, str, str]]:
    """[(key, node_id, which_map)] for this class, engineer-authored only."""
    out: List[Tuple[str, str, str]] = []
    ns = config.VESSEL_NAMESPACE
    if drawing_class in ("hydraulic", "plc"):
        p = config.STATE_DIR / f"control_map_{ns}.json"
        if p.exists():
            for m in json.loads(p.read_text()).get("mappings", []):
                tgt = m.get("target_node_id")
                if not tgt or str(tgt).upper() in NON_NODE:
                    continue
                for k in [m.get("function")] + list(m.get("aliases") or []):
                    if k:
                        out.append((_norm(k), tgt, "control_map"))
    if drawing_class in ("electrical", "interconnect", "plc"):
        p = config.STATE_DIR / f"load_map_{ns}.json"
        if p.exists():
            lm = json.loads(p.read_text())
            if lm.get("status") == "active":
                for k, v in (lm.get("mappings") or {}).items():
                    if v and str(v).upper() not in NON_NODE:
                        out.append((_norm(k), v, "load_map"))
    # Longest key first: "PORT MAPS-1/2" must win over "MAPS-1/2".
    out.sort(key=lambda t: -len(t[0]))
    return out


def resolve(labels: Iterable[str], drawing_class: str,
            register_ids: Optional[set] = None) -> Dict[str, Any]:
    """Which of THIS sheet's labels the engineer's maps already decide.

    Returns {resolved: [{label, key, node, via}], unmapped_labels: [...],
             dead_targets: [...]}.

    `dead_targets` are map rows pointing at a node id that is not in the
    Register — an engineer decision that can no longer land. Silently dropping
    those is how a map row stops working without anyone noticing.
    """
    pairs = load_maps(drawing_class)
    seen_labels = []
    for l in labels:
        n = _norm(l)
        if n and n not in seen_labels:
            seen_labels.append(n)

    resolved: List[Dict[str, str]] = []
    matched_labels = set()
    dead: List[str] = []
    for key, node, via in pairs:
        if register_ids is not None and node not in register_ids:
            if node not in dead:
                dead.append(f"{key} -> {node} (no such node in the Register)")
            continue
        for lab in seen_labels:
            if lab in matched_labels:
                continue                    # longest key already claimed it
            if _phrase_in(key, lab):
                resolved.append({"label": lab, "key": key, "node": node,
                                 "via": via})
                matched_labels.add(lab)
    return {"resolved": resolved,
            "unmapped_labels": [l for l in seen_labels
                                if l not in matched_labels],
            "dead_targets": dead}


def digest(res: Dict[str, Any], max_rows: int = 60) -> str:
    """The prompt block: decisions already made, not rules to apply."""
    rows = res.get("resolved") or []
    if not rows:
        return ("RESOLVED MAPPINGS FOR THIS SHEET: none of this sheet's labels "
                "matched an engineer-confirmed map entry. Route from the "
                "register index and the drawing's own evidence.")
    by_node: Dict[str, List[str]] = {}
    for r in rows:
        by_node.setdefault(r["node"], []).append(r["label"])
    out = ["RESOLVED MAPPINGS FOR THIS SHEET (the engineer's own maps, already "
           "matched against the labels printed on THIS sheet — these are "
           "DECISIONS, not suggestions). Where a label below appears on this "
           "sheet, its facts attach to the node named here. Do NOT route any "
           "of these to a system/hub node instead:"]
    for node, labs in list(by_node.items())[:max_rows]:
        uniq = sorted(set(labs))[:6]
        out.append(f"  {node}  <-  {', '.join(uniq)}")
    if res.get("dead_targets"):
        out.append("MAP ROWS THAT CANNOT LAND (target node missing from the "
                   "Register — report, do not substitute):")
        for d in res["dead_targets"][:10]:
            out.append(f"  {d}")
    return "\n".join(out)
