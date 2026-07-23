"""
P&ID TOPOLOGY EXTRACTOR (engineer-mandated 2026-07-20) — the fluid analog of
the wiring graph: extract components AND pipe connections so composition can
WALK each fluid loop instead of narrating blind (the 515 failure: an empty
extraction left composition to guess from one raster — merged sea chests,
crossed cooling loops).

Gold-blind, two-pass, general (no vessel tokens):
  PASS 1 — survey: title block, BOM/table regions, legend regions, diagram
           region(s). The BOM is the identity authority.
  PASS 2 — (a) BOM tables read verbatim (tiled, per the proven table
           protocol); (b) TOPOLOGY: every component symbol (with its item tag
           where printed) and every pipe connection as drawn — a walkable
           graph.
Then `fluid_loops()` walks the graph: each intake/source traced to its
discharges; one continuous line = one loop; parallel loops NEVER merged.
"""

from __future__ import annotations

import io
import json
from typing import Any, Dict, List, Optional

_SURVEY_PROMPT = (
    "This is a fluid-system P&ID / plumbing schematic. Survey the WHOLE sheet: "
    "read the title block (title, drawing number, revision); locate every "
    "TABLE region (bill of materials / item list / valve schedule), every "
    "LEGEND/notes region, and the main DIAGRAM region(s). Report each region "
    "with its normalized bbox [x0,y0,x1,y1]. Read only what is printed; "
    "'<UNKNOWN>' for illegible fields."
)
_SURVEY_TOOL = {
    "name": "record_pid_survey",
    "description": "Survey of a P&ID sheet.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "drawing_no": {"type": "string"},
            "revision": {"type": "string"},
            "regions": {"type": "array", "items": {"type": "object", "properties": {
                "kind": {"type": "string",
                         "enum": ["bom_table", "legend", "notes", "diagram",
                                  "title_block", "other"]},
                "label": {"type": "string"},
                "bbox": {"type": "array", "items": {"type": "number"},
                         "minItems": 4, "maxItems": 4}},
                "required": ["kind", "bbox"]}},
        },
        "required": ["regions"],
    },
}

_TABLE_PROMPT = (
    "This crop contains a TABLE from a fluid-system schematic (bill of "
    "materials / item list / valve schedule). Transcribe it VERBATIM, row by "
    "row, keeping the printed item tags exactly as written. '<UNKNOWN>' for "
    "illegible cells. Do not summarize, do not skip rows."
)
_TABLE_TOOL = {
    "name": "record_pid_table",
    "description": "Verbatim rows of one table region.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title_as_printed": {"type": "string"},
            "rows": {"type": "array", "items": {"type": "object", "properties": {
                "item_tag": {"type": "string"},
                "description": {"type": "string"},
                "make_model": {"type": "string"},
                "qty": {"type": "string"},
                "raw": {"type": "string"}},
                "required": ["raw"]}},
        },
        "required": ["rows"],
    },
}

_TOPOLOGY_PROMPT = (
    "This is the DIAGRAM region of a fluid-system P&ID. Extract the walkable "
    "TOPOLOGY:\n"
    "COMPONENTS — every drawn component symbol: pumps, valves (type from the "
    "SYMBOL only — a number like 2\" or DN50 on a line is a PIPE SIZE, never a "
    "valve type), strainers/filters, heat exchangers, tanks, sea "
    "chests/intakes, overboard/discharge points, sensors/alarms, manifolds. "
    "Record: component_type, item_tag (as printed, '<UNKNOWN>' if none), "
    "label text near it, and bbox. VALVE STATE: if the legend or the valve "
    "symbol marks it NO (normally open) or NC (normally closed), record "
    "valve_state — these states define which paths carry flow in the normal "
    "lineup; missing them makes every scenario wrong.\n"
    "CONNECTIONS — every pipe line as DRAWN. FLOW ARROWS ARE THE AUTHORITY: "
    "the arrowheads printed on lines define the flow direction — from_component "
    "-> to_component MUST follow the arrow, never your reading order. If a "
    "line has no arrow, set direction_unconfirmed=true instead of guessing. "
    "PUMP SIDES: the suction side and discharge side of a pump are fixed by "
    "the arrows (and check valves); record which side each connection meets. "
    "A line drawn INTO a component supplies that component; lines join ONLY "
    "where the drawing shows them meeting. Separate intakes/sources are "
    "SEPARATE — never bridge two lines that do not touch: a connection that "
    "is not a drawn pipe is the worst possible failure of this pass.\n"
    "Read only what is drawn/printed; '<UNKNOWN>' for illegible; mark "
    "ambiguous=true rather than guess."
)
_TOPOLOGY_TOOL = {
    "name": "record_pid_topology",
    "description": "Components and pipe connections of a P&ID diagram region.",
    "input_schema": {
        "type": "object",
        "properties": {
            "components": {"type": "array", "items": {"type": "object", "properties": {
                "component_type": {"type": "string"},
                "item_tag": {"type": "string"},
                "label": {"type": "string"},
                "valve_state": {"type": "string",
                                "enum": ["NO", "NC", "unknown"]},
                "bbox": {"type": "array", "items": {"type": "number"},
                         "minItems": 4, "maxItems": 4},
                "ambiguous": {"type": "boolean"}},
                "required": ["component_type"]}},
            "connections": {"type": "array", "items": {"type": "object", "properties": {
                "from_component": {"type": "string"},
                "to_component": {"type": "string"},
                "line_label": {"type": "string"},
                "pipe_size": {"type": "string"},
                "direction_unconfirmed": {"type": "boolean",
                    "description": "true when the line carries NO printed arrow"},
                "pump_side": {"type": "string",
                              "enum": ["suction", "discharge", "n/a"]},
                "ambiguous": {"type": "boolean"}},
                "required": ["from_component", "to_component"]}},
        },
        "required": ["components", "connections"],
    },
}


def _render(pdf_bytes: bytes, page: int, dpi: int,
            bbox: Optional[List[float]] = None) -> bytes:
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf_bytes)
    pil = doc[page].render(scale=dpi / 72).to_pil()
    if bbox:
        W, H = pil.size
        x0, y0, x1, y1 = bbox
        pil = pil.crop((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)))
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue()


def extract_pid(pdf_bytes: bytes, page: int = 0, *,
                survey_dpi: int = 150, detail_dpi: int = 400) -> Dict[str, Any]:
    """Full P&ID extraction: survey -> tables verbatim -> diagram topology."""
    from providers.vision import get_vision_provider
    vp = get_vision_provider("plumbed_diagram")

    survey = vp.extract(_render(pdf_bytes, page, survey_dpi), "image/png",
                        _SURVEY_PROMPT, _SURVEY_TOOL) or {}
    tables: List[Dict[str, Any]] = []
    topology: Dict[str, Any] = {"components": [], "connections": []}
    for reg in survey.get("regions", []):
        kind, bbox = reg.get("kind"), reg.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        if kind == "bom_table":
            t = vp.extract(_render(pdf_bytes, page, detail_dpi, bbox),
                           "image/png", _TABLE_PROMPT, _TABLE_TOOL) or {}
            t["bbox"] = bbox
            tables.append(t)
        elif kind == "diagram":
            topo = vp.extract(_render(pdf_bytes, page, detail_dpi, bbox),
                              "image/png", _TOPOLOGY_PROMPT, _TOPOLOGY_TOOL) or {}
            topology["components"].extend(topo.get("components", []))
            topology["connections"].extend(topo.get("connections", []))
    return {"survey": survey, "tables": tables, "topology": topology}


# ---------------------------------------------------------------- loop walk

_SOURCE_WORDS = ("sea chest", "seachest", "intake", "inlet", "pickup",
                 "suction", "tank", "supply")


def _key(name: str) -> str:
    return (name or "").strip().lower()


def fluid_loops(extraction: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Walk the extracted topology from each source outward. One source = one
    loop; branches are walked to their own ends; loops are NEVER merged even
    when they carry the same medium (the cardinal P&ID rule).
    """
    topo = extraction.get("topology") or {}
    comps = {(_key(c.get("label") or c.get("item_tag") or "")): c
             for c in topo.get("components", [])}
    adj: Dict[str, List[Dict[str, Any]]] = {}
    for con in topo.get("connections", []):
        a, b = _key(con.get("from_component")), _key(con.get("to_component"))
        if a and b:
            adj.setdefault(a, []).append({"to": b, "con": con})
    sources = [k for k, c in comps.items()
               if any(w in k or w in _key(c.get("component_type"))
                      for w in _SOURCE_WORDS)]
    # terminal sinks: consumers / discharge / overboard / sprinkler ends
    _SINK_WORDS = ("overboard", "discharge", "hydrant", "sprinkler", "spray",
                   "sea", "consumer", "outlet", "tank")

    def _is_sink(name: str) -> bool:
        c = comps.get(name, {})
        blob = name + " " + _key(c.get("component_type"))
        return (not adj.get(name)) or any(w in blob for w in _SINK_WORDS)

    def _enumerate(src: str, max_paths: int = 12, max_len: int = 12):
        """Distinct source->sink LINEUPS (the engineer's per-scenario paths:
        fire pump -> hydrants / sprinkler / bilge-overboard = 3 lineups).
        Bounded simple-path DFS."""
        paths: List[List[str]] = []
        stack = [(src, [src])]
        while stack and len(paths) < max_paths:
            node, path = stack.pop()
            outs = adj.get(node, [])
            if (_is_sink(node) and len(path) > 1) or not outs:
                if len(path) > 1:
                    paths.append(path)
                continue
            if len(path) >= max_len:
                paths.append(path)
                continue
            for ed in outs:
                if ed["to"] not in path:
                    stack.append((ed["to"], path + [ed["to"]]))
        return paths

    loops: List[Dict[str, Any]] = []
    for src in sources:
        visited = {src}
        segments: List[str] = []
        frontier = [src]
        while frontier:
            nxt = []
            for node in frontier:
                for ed in adj.get(node, []):
                    if ed["to"] in visited:
                        continue
                    visited.add(ed["to"])
                    size = ed["con"].get("pipe_size") or ""
                    lbl = ed["con"].get("line_label") or ""
                    ann = " ".join(x for x in (size, lbl) if x)
                    segments.append(f"{node} -> {ed['to']}"
                                    + (f"  [{ann}]" if ann else ""))
                    nxt.append(ed["to"])
            frontier = nxt
        lineups = [" -> ".join(p) for p in _enumerate(src)]
        loops.append({"source": src, "reached": sorted(visited - {src}),
                      "segments": segments, "lineups": lineups})
    return loops


def loops_digest(extraction: Dict[str, Any]) -> str:
    """Prompt block for composition — the walked loops, sources kept apart."""
    loops = fluid_loops(extraction)
    if not loops:
        return "(no fluid topology to walk — extraction carried no connections)"
    out = ["WALKED FLUID LOOPS (traced from each drawn source; each source's "
           "loop is SEPARATE — never merge loops even when the medium is the "
           "same):"]
    for lp in loops:
        out.append(f"\n• SOURCE: {lp['source']}")
        for lu in lp.get("lineups", [])[:12]:
            out.append(f"  LINEUP (one scenario): {lu}")
        for seg in lp["segments"][:20]:
            out.append(f"  seg: {seg}")
        if len(lp["segments"]) > 20:
            out.append(f"  …(+{len(lp['segments'])-20} more segments)")
    return "\n".join(out)
