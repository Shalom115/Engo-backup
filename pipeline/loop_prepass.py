"""
LOOP PRE-PASS (engineer-mandated 2026-07-20): let composition DISCOVER a
control loop instead of waiting for red pen.

The 114a failure: composition consumed a flat element list, so one physical
circuit (main-panel switch OR ONYX XA11, both closing the same contactor coil
that runs the bilge pump) fragmented into three separate uncertainties. The
graph was in the `connections` field all along — nobody walked it.

This pre-pass walks the wiring graph with pipeline.power_path BEFORE
composition and hands composition assembled LOOPS (anchor equipment + every
activation path that reaches it + the terminals/fuses on the way), so the
narration is discovered from the drawn lines, not invented and not fragmented.

Used for the electrical wiring class. Fluid P&ID gets its own loop-walk once a
real P&ID topology extractor exists (515 showed composition cannot walk a loop
that was never extracted).
"""

from __future__ import annotations

from typing import Any, Dict, List

from pipeline import power_path


def _wiring_elements(extraction: Dict[str, Any]) -> List[Dict[str, Any]]:
    els: List[Dict[str, Any]] = []
    for r in extraction.get("regions_read", []) or []:
        els.extend(e for e in r.get("elements", []) if isinstance(e, dict))
    # some extractions carry a flat wiring_elements list instead
    els.extend(e for e in extraction.get("wiring_elements", []) or []
               if isinstance(e, dict))
    return els


def _is_activation_anchor(el: Dict[str, Any]) -> bool:
    """Anchor the walk at the DRIVEN EQUIPMENT — a motor/pump/solenoid/valve
    or the contactor COIL that switches it — the end of a control loop. Not
    bare terminals or relay contacts (those are waypoints, not anchors)."""
    t = (el.get("element_type") or "").lower()
    lbl = (el.get("label") or "").lower()
    if t in ("terminal", "terminal_strip", "plug_pin"):
        return False  # waypoints, never anchors — even if the label says "coil"
    if t in ("device", "motor", "solenoid", "valve", "actuator"):
        return True
    # a relay COIL is an anchor; a plain relay contact is not
    if any(w in lbl for w in ("pump", "motor", "solenoid", "valve", "actuator",
                              "contactor", "coil")):
        return True
    return False


def assemble_loops(extraction: Dict[str, Any],
                   max_hops: int = 4) -> List[Dict[str, Any]]:
    """
    Return one entry per activation anchor: {anchor, paths, terminals_on_path,
    fused_terminals, activation_sources, trace_text}. `paths` lists every
    distinct route that reaches the anchor — the multi-switch answer as ONE
    structure.
    """
    els = _wiring_elements(extraction)
    if not els:
        return []
    edges = power_path.build_edges(els)
    loops: List[Dict[str, Any]] = []
    for i, el in enumerate(els):
        if not _is_activation_anchor(el):
            continue
        trace = power_path.trace_power_path(i, els, edges, max_hops=max_hops)
        hops = trace.get("hops", [])
        if not hops and not trace.get("unresolved_refs"):
            continue
        terminals, fused = [], []
        activation_sources = []
        for h in hops:
            to = h.get("to", {})
            frm = h.get("from", {})
            for node in (to, frm):
                ntype = (node.get("type") or "").lower()
                nid = node.get("id") or node.get("label")
                if ntype in ("terminal", "terminal_strip") and nid:
                    terminals.append(nid)
                    # fused-terminal marker: the extractor's per-terminal flag
                    # (has_builtin_fuse), with label fallback for extractions
                    # made before the flag existed
                    if node.get("has_builtin_fuse") or \
                       "fus" in (node.get("label") or "").lower():
                        fused.append(nid)
                if ntype in ("switch", "status_signal", "relay") and nid:
                    role = h.get("role") or ""
                    if "activ" in role or ntype in ("switch", "status_signal"):
                        activation_sources.append(f"{nid} ({ntype})")
        loops.append({
            "anchor": el.get("label") or el.get("id") or f"element_{i}",
            "anchor_type": el.get("element_type"),
            "paths": power_path.render_trace(el.get("label") or "anchor", trace),
            "terminals_on_path": sorted(set(terminals)),
            "fused_terminals": sorted(set(fused)),
            "activation_sources": sorted(set(activation_sources)),
            "unresolved": [u.get("raw") for u in trace.get("unresolved_refs", [])][:6],
        })
    return loops


def loops_digest(extraction: Dict[str, Any]) -> str:
    """Human-readable block for the composition prompt."""
    loops = assemble_loops(extraction)
    if not loops:
        return "(no wiring graph to walk — extraction carried no connections)"
    out = ["ASSEMBLED CONTROL LOOPS (walked from the drawn `connections` — "
           "each anchor is ONE device; all its activation paths belong to ONE "
           "loop scenario, never separate flags):"]
    for lp in loops:
        out.append(f"\n• ANCHOR: {lp['anchor']} ({lp['anchor_type']})")
        if lp["activation_sources"]:
            out.append(f"  activation paths: {', '.join(lp['activation_sources'])}")
        terms = lp["terminals_on_path"]
        if terms:
            shown = ", ".join(terms[:14]) + (f" …(+{len(terms)-14} more)" if len(terms) > 14 else "")
            out.append(f"  terminals on path: {shown}")
        if lp["fused_terminals"]:
            out.append(f"  FUSED terminals (troubleshooting culprits): "
                       f"{', '.join(lp['fused_terminals'])}")
        if lp["unresolved"]:
            out.append(f"  unresolved off-sheet refs: {', '.join(lp['unresolved'])}")
    return "\n".join(out)
