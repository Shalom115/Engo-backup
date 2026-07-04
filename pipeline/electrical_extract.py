"""
ELECTRICAL EXTRACTOR — gold-blind, two-pass, sub-type-aware. The non-hydraulic
analogue of schematic_extract.discover_structure, built AFTER rendering 5 real GM
sheets (render-before-designing standing rule).

Grounded taxonomy (GM set):
  A DISTRIBUTION SCHEDULE   — rows [device][rating]->[load] in panel columns (GM-111)
  B POWER ONE-LINE          — source/bus topology + breaker banks + glossary (GM-110b)
  C RELAY/TERMINAL WIRING   — terminal strips + relays + modules + device endpoints
                              + status signals (GM-114a/116/119); dense, §6-critical

PASS 1 SKELETON (whole sheet, low res): read the title block, CLASSIFY the sub-type,
DETECT the structural regions + bboxes + cross-refs. Classifying FIRST is what stops
this extractor being built for A and silently failing on C (the discover_structure
mistake). Gold-blind: no vessel-specific token in any prompt.

PASS 2 DETAIL is sub-type-specific. Built now: the SCHEDULE reader (sub-type A),
grounded on GM-111. The one-line (B) and wiring (C) readers are SCOPED-NEXT — each
needs its own grounding + grading before it is trusted (they are NOT the row reader).

§6 device discipline is mandatory in the read prompts: breaker != fuse != relay !=
contactor != terminal; a status/signal line != a power line; mark ambiguous, never
guess; return <UNKNOWN> for illegible, never fabricate.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

from PIL import Image

from pipeline import visual_extract as vx
from providers.vision import get_vision_provider

# ---------------------------------------------------------------- PASS 1 tool
_SURVEY_PROMPT = (
    "You are performing a STRUCTURAL SURVEY of one electrical drawing sheet. Do NOT "
    "transcribe every label — identify the sheet's structure so a detail pass can tile it.\n"
    "1. Read the title block (drawing number, title, drafter) if present.\n"
    "2. CLASSIFY the sheet's dominant layout as ONE of:\n"
    "   - 'distribution_schedule': repeated horizontal rows, each a protective device "
    "(breaker/fuse) with a rating feeding a NAMED load, grouped into panel columns.\n"
    "   - 'power_one_line': a connected topology of sources (batteries/generators), "
    "isolators and buses feeding loads — interconnection matters — possibly with "
    "breaker banks and an on-sheet glossary.\n"
    "   - 'relay_terminal_wiring': terminal strips with numbered terminals, relays, "
    "logic/controller modules and device endpoints joined by wiring; often status/signal "
    "lines to a monitoring bus.\n"
    "   - 'mixed' or 'unknown' if it does not cleanly fit.\n"
    "3. DETECT the major structural REGIONS (panel columns, breaker banks, terminal "
    "strips, relay banks, controller modules, topology networks, legends). For each give "
    "a normalized bounding box [x0,y0,x1,y1] in 0..1 and an approximate count of its "
    "repeated units.\n"
    "4. List cross-references to other drawings or signal buses.\n"
    "Do NOT invent device IDs, ratings or load names — this is a structural survey only. "
    "Note anything illegible at this resolution."
)
_SURVEY_TOOL = {
    "name": "record_electrical_survey",
    "description": "Structural survey of an electrical sheet.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title_block": {"type": "object", "properties": {
                "drawing_no": {"type": "string"}, "title": {"type": "string"},
                "drafter": {"type": "string"}}},
            "sub_type": {"type": "string", "enum": [
                "distribution_schedule", "power_one_line", "relay_terminal_wiring",
                "mixed", "unknown"]},
            "sub_type_reason": {"type": "string"},
            "regions": {"type": "array", "items": {"type": "object", "properties": {
                "type": {"type": "string", "enum": [
                    "panel_column", "breaker_bank", "terminal_strip", "relay_bank",
                    "controller_module", "topology_network", "legend", "other"]},
                "label": {"type": "string"},
                "bbox": {"type": "array", "items": {"type": "number"}},
                "approx_unit_count": {"type": "integer"}},
                "required": ["type", "bbox"]}},
            "cross_refs": {"type": "array", "items": {"type": "string"}},
            "notes": {"type": "string"},
        },
        "required": ["sub_type", "regions"],
    },
}

# ---------------------------------------------------------------- PASS 2 (A) tool
_SCHEDULE_PROMPT = (
    "This is a tightly-cropped region of an electrical DISTRIBUTION SCHEDULE. Read each "
    "circuit ROW top to bottom. For each row record:\n"
    " - device_type: the protective-device kind. DISTINGUISH breaker vs fuse vs "
    "emergency breaker vs circuit-breaker vs switch vs current-transformer by symbol and "
    "ID prefix. NEVER conflate breaker / fuse / relay / switch. If unsure, mark ambiguous.\n"
    " - device_id, rating (as printed, e.g. '10A'), and the NAME of the LOAD it feeds.\n"
    " - cross_ref: any referenced drawing or signal bus on that row.\n"
    "Read ONLY what is printed. Return '<UNKNOWN>' for any illegible field — never guess "
    "or fabricate an ID, rating, or load name."
)
_SCHEDULE_TOOL = {
    "name": "record_schedule_rows",
    "description": "Rows of a distribution-schedule region.",
    "input_schema": {
        "type": "object",
        "properties": {
            "panel_label": {"type": "string"},
            "rows": {"type": "array", "items": {"type": "object", "properties": {
                "device_type": {"type": "string", "enum": [
                    "breaker", "fuse", "emergency_breaker", "circuit_breaker",
                    "switch", "current_transformer", "link", "unknown"]},
                "device_id": {"type": "string"}, "rating": {"type": "string"},
                "load_name": {"type": "string"}, "cross_ref": {"type": "string"},
                "ambiguous": {"type": "boolean"}},
                "required": ["device_type", "load_name"]}},
        },
        "required": ["rows"],
    },
}


def _crop_box(png: bytes, bbox: List[float], pad: float = 0.01) -> bytes:
    im = Image.open(io.BytesIO(png))
    w, h = im.size
    x0, y0, x1, y1 = bbox
    l = max(0, int((min(x0, x1) - pad) * w)); r = min(w, int((max(x0, x1) + pad) * w))
    t = max(0, int((min(y0, y1) - pad) * h)); b = min(h, int((max(y0, y1) + pad) * h))
    out = io.BytesIO(); im.crop((l, t, r, b)).save(out, "PNG")
    return out.getvalue()


def survey(pdf_bytes: bytes, page_index: int = 0, *, dpi: int = 200) -> Dict[str, Any]:
    """PASS 1 — classify sub-type + detect regions (gold-blind, structural only)."""
    vp = get_vision_provider()
    img = vx.rasterize_pdf_page(pdf_bytes, page_index, dpi=dpi)
    r = vp.extract(img, "image/png", _SURVEY_PROMPT, _SURVEY_TOOL)
    r["_pass1_dpi"] = dpi
    return r


def read_schedule_region(pdf_bytes: bytes, bbox: List[float], page_index: int = 0,
                         *, dpi: int = 600) -> Dict[str, Any]:
    """PASS 2 (sub-type A) — tight-crop a schedule region and read its rows."""
    vp = get_vision_provider()
    page = vx.rasterize_pdf_page(pdf_bytes, page_index, dpi=dpi)
    tile = _crop_box(page, bbox)
    return vp.extract(tile, "image/png", _SCHEDULE_PROMPT, _SCHEDULE_TOOL)


# ---------------------------------------------------------------- PASS 2 (C) tool
_WIRING_PROMPT = (
    "This is a tightly-cropped region of an electrical RELAY/TERMINAL WIRING diagram. "
    "Read every labelled element. DEVICE DISCIPLINE IS MANDATORY: a breaker is not a "
    "fuse is not a relay is not a contactor is not a terminal; a status/monitoring "
    "signal tap is a SIGNAL, not a power line. SIGNAL-vs-POWER (critical): numbered "
    "junction/tap blocks whose wires collect per-circuit taps and route them to a "
    "central monitoring/alarm/supervision system are STATUS SIGNALS "
    "(element_type=status_signal) even when drawn as terminal blocks or connector "
    "strips — record block+pin in the id. Supply-protection devices (breakers/fuses "
    "with ampere ratings) often sit at the TOP or LEFT EDGE of the sheet feeding the "
    "circuit — do not skip edge devices. For each element record:\n"
    " - element_type: terminal_strip | terminal | relay | controller_module | device "
    "(motor/valve/sender/pump/light-circuit endpoint) | status_signal | plug_pin | "
    "fuse | breaker | switch | unknown\n"
    " - id (as printed, e.g. a relay number, terminal number, module model), the "
    "function/label text near it, and its connections as printed (from -> to).\n"
    "Read ONLY what is printed. '<UNKNOWN>' for illegible fields. Mark ambiguous "
    "elements ambiguous=true. Never guess or invent ids."
)
_WIRING_TOOL = {
    "name": "record_wiring_elements",
    "description": "Elements of a relay/terminal wiring region.",
    "input_schema": {
        "type": "object",
        "properties": {
            "region_label": {"type": "string"},
            "elements": {"type": "array", "items": {"type": "object", "properties": {
                "element_type": {"type": "string", "enum": [
                    "terminal_strip", "terminal", "relay", "controller_module",
                    "device", "status_signal", "plug_pin", "fuse", "breaker",
                    "switch", "unknown"]},
                "id": {"type": "string"}, "label": {"type": "string"},
                "connections": {"type": "array", "items": {"type": "string"}},
                "ambiguous": {"type": "boolean"}},
                "required": ["element_type"]}},
        },
        "required": ["elements"],
    },
}

# ---------------------------------------------------------------- PASS 2 (B) tool
_ONELINE_PROMPT = (
    "This is a region of an electrical POWER ONE-LINE / distribution schematic. "
    "Extract the TOPOLOGY: the power sources (batteries, generators, shore inlets, "
    "alternators), buses/boards, converters, and the protective/switching devices "
    "in each path (DISTINGUISH fuse vs breaker vs isolator/switch vs shunt vs "
    "current-transformer by symbol and id prefix — never conflate). Record each "
    "NODE {node_type, id, label, rating} and each EDGE as printed "
    "('source -> device -> destination'). Read ONLY what is printed; '<UNKNOWN>' "
    "for illegible; never invent connectivity."
)
_ONELINE_TOOL = {
    "name": "record_oneline_topology",
    "description": "Topology of a power one-line region.",
    "input_schema": {
        "type": "object",
        "properties": {
            "nodes": {"type": "array", "items": {"type": "object", "properties": {
                "node_type": {"type": "string", "enum": [
                    "source", "bus", "board", "converter", "fuse", "breaker",
                    "isolator", "switch", "shunt", "current_transformer", "load",
                    "unknown"]},
                "id": {"type": "string"}, "label": {"type": "string"},
                "rating": {"type": "string"}},
                "required": ["node_type"]}},
            "edges": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["nodes", "edges"],
    },
}


def read_wiring_region(pdf_bytes: bytes, bbox: List[float], page_index: int = 0,
                       *, dpi: int = 600) -> Dict[str, Any]:
    """PASS 2 (sub-type C) — tight-crop a wiring region and read its elements."""
    vp = get_vision_provider()
    page = vx.rasterize_pdf_page(pdf_bytes, page_index, dpi=dpi)
    return vp.extract(_crop_box(page, bbox), "image/png", _WIRING_PROMPT, _WIRING_TOOL)


def _row_key(row: Dict[str, Any]) -> tuple:
    import re as _re
    n = lambda s: _re.sub(r"[^a-z0-9]+", "", str(s or "").lower())
    return (n(row.get("device_id")), n(row.get("load_name"))[:24])


def read_schedule_coverage(pdf_bytes: bytes, page_index: int,
                           survey_regions: Optional[List[Dict[str, Any]]] = None,
                           *, dpi: int = 600) -> List[Dict[str, Any]]:
    """Schedule read with the same COVERAGE GUARANTEE as read_wiring_coverage —
    survey-detected panel/breaker regions PLUS a fixed full-sheet grid, merged with
    dedupe. Same root cause applies here: the survey's region detection is
    stochastic, so a schedule reader keyed only on it can silently miss rows."""
    page = vx.rasterize_pdf_page(pdf_bytes, page_index, dpi=dpi)
    vp = get_vision_provider()
    seen: Dict[tuple, Dict[str, Any]] = {}
    panel_label = None
    skipped = 0
    for rg in (survey_regions or []):
        r = vp.extract(_crop_box(page, rg["bbox"]), "image/png", _SCHEDULE_PROMPT, _SCHEDULE_TOOL)
        panel_label = panel_label or r.get("panel_label")
        for row in r.get("rows", []):
            if not isinstance(row, dict):
                skipped += 1
                continue
            row["_via"] = "survey_region"
            row["_bbox"] = rg["bbox"]
            seen.setdefault(_row_key(row), row)
    for gb in grid_boxes():
        r = vp.extract(_crop_box(page, gb), "image/png", _SCHEDULE_PROMPT, _SCHEDULE_TOOL)
        panel_label = panel_label or r.get("panel_label")
        for row in r.get("rows", []):
            if not isinstance(row, dict):
                skipped += 1
                continue
            k = _row_key(row)
            if k not in seen:
                row["_via"] = "grid_tile"
                row["_bbox"] = gb
                seen[k] = row
    if skipped:
        print(f"  [read_schedule_coverage] skipped {skipped} malformed (non-dict) row entries", flush=True)
    return list(seen.values()), panel_label


def grid_boxes(rows: int = 3, cols: int = 3, overlap: float = 0.08) -> List[List[float]]:
    """Fixed full-sheet tile grid (normalized boxes). COVERAGE GUARANTEE: unlike
    survey-detected regions (whose recall is stochastic — a pass can simply not
    hand an area to the readers), these tiles always cover the whole sheet."""
    boxes = []
    for r in range(rows):
        for c in range(cols):
            x0 = max(0.0, c / cols - overlap / 2)
            x1 = min(1.0, (c + 1) / cols + overlap / 2)
            y0 = max(0.0, r / rows - overlap / 2)
            y1 = min(1.0, (r + 1) / rows + overlap / 2)
            boxes.append([x0, y0, x1, y1])
    return boxes


def _el_key(e: Dict[str, Any]) -> tuple:
    import re as _re
    n = lambda s: _re.sub(r"[^a-z0-9]+", "", str(s or "").lower())
    return (e.get("element_type"), n(e.get("id")), n(e.get("label"))[:24])


def read_wiring_coverage(pdf_bytes: bytes, page_index: int,
                         survey_regions: Optional[List[Dict[str, Any]]] = None,
                         *, dpi: int = 600) -> List[Dict[str, Any]]:
    """Wiring read with the COVERAGE GUARANTEE: reads the survey's wiring regions
    (tight crops, best resolution) PLUS a fixed full-sheet grid, then merges with
    dedupe. An element found by either path is kept; grid-only finds are marked."""
    page = vx.rasterize_pdf_page(pdf_bytes, page_index, dpi=dpi)
    vp = get_vision_provider()
    seen: Dict[tuple, Dict[str, Any]] = {}
    skipped = 0
    for rg in (survey_regions or []):
        r = vp.extract(_crop_box(page, rg["bbox"]), "image/png", _WIRING_PROMPT, _WIRING_TOOL)
        for e in r.get("elements", []):
            if not isinstance(e, dict):
                skipped += 1
                continue
            e["_via"] = "survey_region"
            e["_bbox"] = rg["bbox"]
            seen.setdefault(_el_key(e), e)
    for gb in grid_boxes():
        r = vp.extract(_crop_box(page, gb), "image/png", _WIRING_PROMPT, _WIRING_TOOL)
        for e in r.get("elements", []):
            if not isinstance(e, dict):
                skipped += 1
                continue
            k = _el_key(e)
            if k not in seen:
                e["_via"] = "grid_tile"
                e["_bbox"] = gb
                seen[k] = e
    if skipped:
        print(f"  [read_wiring_coverage] skipped {skipped} malformed (non-dict) element entries", flush=True)
    return list(seen.values())


def read_oneline_region(pdf_bytes: bytes, bbox: List[float], page_index: int = 0,
                        *, dpi: int = 400) -> Dict[str, Any]:
    """PASS 2 (sub-type B) — read the topology of a one-line region."""
    vp = get_vision_provider()
    page = vx.rasterize_pdf_page(pdf_bytes, page_index, dpi=dpi)
    return vp.extract(_crop_box(page, bbox), "image/png", _ONELINE_PROMPT, _ONELINE_TOOL)


def _node_key(n: Dict[str, Any]) -> tuple:
    import re as _re
    norm = lambda s: _re.sub(r"[^a-z0-9]+", "", str(s or "").lower())
    return (n.get("node_type"), norm(n.get("id")), norm(n.get("label"))[:24])


def read_oneline_coverage(pdf_bytes: bytes, page_index: int,
                         survey_regions: Optional[List[Dict[str, Any]]] = None,
                         *, dpi: int = 500) -> Dict[str, Any]:
    """One-line topology read with the same COVERAGE GUARANTEE as wiring/schedule —
    survey-detected topology_network regions PLUS a fixed full-sheet grid, merged
    with dedupe on (node_type, id, label). Same root cause: survey region-detection
    is stochastic, a reader keyed only on it can silently miss nodes/edges."""
    page = vx.rasterize_pdf_page(pdf_bytes, page_index, dpi=dpi)
    vp = get_vision_provider()
    seen: Dict[tuple, Dict[str, Any]] = {}
    edges: List[str] = []
    skipped = 0
    for rg in (survey_regions or []):
        r = vp.extract(_crop_box(page, rg["bbox"]), "image/png", _ONELINE_PROMPT, _ONELINE_TOOL)
        for n in r.get("nodes", []):
            if not isinstance(n, dict):
                skipped += 1
                continue
            n["_via"] = "survey_region"; n["_bbox"] = rg["bbox"]
            seen.setdefault(_node_key(n), n)
        edges.extend(x for x in r.get("edges", []) if isinstance(x, str))
    for gb in grid_boxes():
        r = vp.extract(_crop_box(page, gb), "image/png", _ONELINE_PROMPT, _ONELINE_TOOL)
        for n in r.get("nodes", []):
            if not isinstance(n, dict):
                skipped += 1
                continue
            k = _node_key(n)
            if k not in seen:
                n["_via"] = "grid_tile"; n["_bbox"] = gb
                seen[k] = n
        edges.extend(x for x in r.get("edges", []) if isinstance(x, str))
    if skipped:
        print(f"  [read_oneline_coverage] skipped {skipped} malformed (non-dict) node entries", flush=True)
    # dedupe edges as plain strings, normalized
    import re as _re
    seen_e, uniq_edges = set(), []
    for e in edges:
        k = _re.sub(r"\s+", " ", str(e).strip().lower())
        if k and k not in seen_e:
            seen_e.add(k); uniq_edges.append(e)
    return {"nodes": list(seen.values()), "edges": uniq_edges}


# Detail readers dispatch by REGION type, NOT by the whole-sheet sub_type label.
# The A/B boundary is genuinely non-deterministic (a schedule with supply topology,
# e.g. GM-111, classifies as A or B across runs) — but a breaker_bank region is a
# breaker_bank whichever label the sheet gets, and a one-line sheet's banks are still
# schedule-readable. Dispatching per region is robust to that boundary.
_SCHEDULE_REGIONS = ("panel_column", "breaker_bank")
_WIRING_REGIONS = ("terminal_strip", "relay_bank", "controller_module")
_ONELINE_REGIONS = ("topology_network",)


def extract_sheet(pdf_bytes: bytes, page_index: int = 0) -> Dict[str, Any]:
    """
    Full electrical extraction. Survey first, then dispatch a detail reader PER REGION
    TYPE: schedule reader (breaker_bank/panel_column), wiring reader (terminal_strip/
    relay_bank/controller_module), one-line topology reader (topology_network). All
    three grounded on rendered sheets (GM-111 / 114a-116-119 / 110b + GA-001b + BAE).
    """
    s = survey(pdf_bytes, page_index)
    result: Dict[str, Any] = {"survey": s, "sub_type": s.get("sub_type"),
                              "regions_read": [], "scoped_next": []}
    for rg in s.get("regions", []):
        rtype = rg.get("type")
        if rtype in _SCHEDULE_REGIONS:
            rows = read_schedule_region(pdf_bytes, rg["bbox"], page_index)
            result["regions_read"].append({
                "region": rg.get("label"), "region_type": rtype, "bbox": rg["bbox"],
                "reader": "schedule", "panel_label": rows.get("panel_label"),
                "rows": rows.get("rows", [])})
        elif rtype in _WIRING_REGIONS:
            els = read_wiring_region(pdf_bytes, rg["bbox"], page_index)
            result["regions_read"].append({
                "region": rg.get("label"), "region_type": rtype, "bbox": rg["bbox"],
                "reader": "wiring", "elements": els.get("elements", [])})
        elif rtype in _ONELINE_REGIONS:
            topo = read_oneline_region(pdf_bytes, rg["bbox"], page_index)
            result["regions_read"].append({
                "region": rg.get("label"), "region_type": rtype, "bbox": rg["bbox"],
                "reader": "oneline", "nodes": topo.get("nodes", []),
                "edges": topo.get("edges", [])})
        # legend / other regions are skipped
    return result
