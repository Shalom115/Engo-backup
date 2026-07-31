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
from pipeline import legend_first
from pipeline import symbol_glossary
from providers.vision import get_vision_provider


def _ctx(legend_context: str, prompt: str) -> str:
    """Prompt assembly order: sheet's own legends (authoritative) -> fleet-general
    symbol glossary -> task prompt. The glossary text itself states the sheet
    legend overrides it."""
    return legend_first.with_context(legend_context, symbol_glossary.with_glossary(prompt))

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


def survey(pdf_bytes: bytes, page_index: int = 0, *, dpi: int = 200,
           legend_context: str = "") -> Dict[str, Any]:
    """PASS 1 — classify sub-type + detect regions (gold-blind, structural only)."""
    from pipeline import meter
    meter.set_layer("survey")
    vp = get_vision_provider("electrical")
    img = vx.rasterize_pdf_page(pdf_bytes, page_index, dpi=dpi)
    r = vp.extract(img, "image/png",
                   _ctx(legend_context, _SURVEY_PROMPT), _SURVEY_TOOL)
    r["_pass1_dpi"] = dpi
    return r


def read_schedule_region(pdf_bytes: bytes, bbox: List[float], page_index: int = 0,
                         *, dpi: int = 600, legend_context: str = "") -> Dict[str, Any]:
    """PASS 2 (sub-type A) — tight-crop a schedule region and read its rows."""
    vp = get_vision_provider("electrical")
    page = vx.rasterize_pdf_page(pdf_bytes, page_index, dpi=dpi)
    tile = _crop_box(page, bbox)
    return vp.extract(tile, "image/png",
                      _ctx(legend_context, _SCHEDULE_PROMPT), _SCHEDULE_TOOL)


# ---------------------------------------------------------------- PASS 2 (C) tool
_WIRING_PROMPT = (
    "This is a tightly-cropped region of an electrical RELAY/TERMINAL WIRING diagram. "
    "Read every labelled element. DEVICE DISCIPLINE IS MANDATORY: a breaker is not a "
    "fuse is not a relay is not a contactor is not a terminal; a status/monitoring "
    "signal tap is a SIGNAL, not a power line. SIGNAL-vs-POWER (critical): numbered "
    "junction/tap blocks whose wires collect per-circuit taps and route them to a "
    "central monitoring/alarm/supervision system are STATUS SIGNALS "
    "(element_type=status_signal) even when drawn as terminal blocks, connector "
    "strips, or module/controller tap ports — the tag block belongs to the "
    "monitoring loom, so record block+pin in the id and type it status_signal, "
    "NOT controller_module and NOT annotation. Supply-protection devices (breakers/fuses "
    "with ampere ratings) often sit at the TOP or LEFT EDGE of the sheet feeding the "
    "circuit — do not skip edge devices. For each element record:\n"
    " - element_type: terminal_strip | terminal | relay | controller_module | device "
    "(motor/valve/sender/pump/light-circuit endpoint) | status_signal | plug_pin | "
    "fuse | breaker | switch | annotation | unknown\n"
    "ANNOTATIONS are drawing markup, not circuit elements: wire-gauge callouts "
    "(a diamond with a number = conductor mm²), captions describing the device "
    "below them, and cross-drawing pointers. A cross-drawing pointer is ONLY a "
    "text that EXPLICITLY names another drawing/sheet ('see DWG 117', 'ref sheet "
    "110b') AND carries no wire. If the referencing element is WIRED into this "
    "sheet (a flagged source/target feeding a terminal, a terminal strip "
    "continuing elsewhere), it STAYS an element typed by its electrical function, "
    "with the drawing reference in its label/connections — never annotation-only, "
    "never dropped. A letters+digits TAG BLOCK on a stub wire that taps a circuit and "
    "routes to a central monitoring/alarm loom is a STATUS SIGNAL "
    "(element_type=status_signal), NOT an annotation and NOT a drawing pointer — "
    "even though its wire 'goes elsewhere'. When in doubt between status_signal "
    "and annotation for a wired tag: it carries a wire = status_signal.\n"
    " - id (as printed, e.g. a relay number, terminal number, module model), the "
    "function/label text near it, and its connections as printed (from -> to).\n"
    "COILS HAVE TWO POWER SIDES (engineer rule — read electricity side to "
    "side): a relay/contactor COIL is a rectangle with a slash/divider; the "
    "label ON TOP names the function it activates. Every coil has TWO "
    "activation lines — on DC a POSITIVE feed and a NEGATIVE return, on AC an "
    "L and an N. Capture BOTH in connections: where the + (or L) comes FROM "
    "(often a fused terminal on a terminal strip) and where the - (or N) "
    "returns TO (often another terminal strip -> a multi-core wire -> a plug "
    "pin, closed by a switch). Do not record only the output/status line; the "
    "supply and return lines are what make the coil energise. Trace each side "
    "to the element it reaches on this crop.\n"
    "FUSED TERMINALS (engineer rule): a terminal drawn as an OUTER rectangle "
    "containing a SMALLER rectangle crossed by a line has a BUILT-IN REPLACEABLE "
    "FUSE — set has_builtin_fuse=true on that terminal (type stays terminal). "
    "These are prime troubleshooting suspects; never skip the marker.\n"
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
                    "switch", "annotation", "unknown"]},
                "id": {"type": "string"}, "label": {"type": "string"},
                "connections": {"type": "array", "items": {"type": "string"}},
                "has_builtin_fuse": {"type": "boolean"},
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


# Full-page CROSS-REFERENCE (engineer-mandated 2026-07-10): reading a tight crop
# in isolation misreads elements that are obvious with the whole sheet in view —
# a block the crop calls a "switch" that the full sheet shows is a multi-pin
# harness connector, a signal
# tap whose destination is only labelled elsewhere on the page, a partial label
# ("DINN…") that the full sheet completes. The fix: send BOTH a downsampled full
# page (region outlined) for CONTEXT and the high-res crop for DETAIL, and tell
# the reader to resolve the crop using the full sheet. Resolution for reading
# stays in the crop (the §4 finding); context comes free from the overview.
def _full_page_with_box(pdf_bytes: bytes, page_index: int, bbox: List[float],
                        *, dpi: int = 200) -> bytes:
    """Render the whole page at a moderate DPI and outline `bbox` in red — the
    CONTEXT image for a cross-referenced crop read."""
    from PIL import ImageDraw
    page_png = vx.rasterize_pdf_page(pdf_bytes, page_index, dpi=dpi)
    im = Image.open(io.BytesIO(page_png)).convert("RGB")
    w, h = im.size
    x0, y0, x1, y1 = bbox
    box = (int(min(x0, x1) * w), int(min(y0, y1) * h),
           int(max(x0, x1) * w), int(max(y0, y1) * h))
    draw = ImageDraw.Draw(im)
    draw.rectangle(box, outline=(220, 0, 0), width=max(3, w // 300))
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


def read_wiring_region(pdf_bytes: bytes, bbox: List[float], page_index: int = 0,
                       *, dpi: int = 600, legend_context: str = "",
                       cross_reference: bool = False) -> Dict[str, Any]:
    """PASS 2 (sub-type C) — read a wiring region.

    Default (1 call): tight high-res crop, glossary-boosted — already corrects
    the core crop misreads (a multi-pin block the crop calls a 'switch' read as a
    harness connector; interlock signals, fuses, wire-gauge diamonds typed right).

    cross_reference=True (2 calls, VALIDATED 2026-07-10 on the GMMS-110 SWITCH
    region): read the crop, THEN enrich each element against the full page via
    enrich_region_against_full_page(). This is the engineer-mandated crop↔full-
    page cross-reference. It is a TWO-CALL flow on purpose: a single call with
    two images makes Claude return a region SUMMARY and omit the elements array
    (finding, see extract_multi note) — call 2 gets the element LIST to correct,
    so it enumerates reliably AND resolves types/connections from the whole
    sheet (validated: a control-module block →controller_module with 15
    connections, diamonds→annotation, CAN HI/LO/shield identified, all elements
    returned — vs the crop-only read that under-typed them).
    Costs one extra call per region — apply selectively to ambiguous sheets."""
    vp = get_vision_provider("electrical")
    page = vx.rasterize_pdf_page(pdf_bytes, page_index, dpi=dpi)
    crop = _crop_box(page, bbox)
    r = vp.extract(crop, "image/png",
                   _ctx(legend_context, _WIRING_PROMPT), _WIRING_TOOL)
    if cross_reference and (r.get("elements") or []):
        enriched = enrich_region_against_full_page(
            r["elements"], pdf_bytes, page_index, bbox, legend_context=legend_context)
        r = _merge_enriched(r, enriched.get("elements") or [])
    return r


def _norm_id(v: Any) -> str:
    import re as _re
    return _re.sub(r"[^a-z0-9]+", "", str(v or "").lower())


def _merge_enriched(r: Dict[str, Any], enriched: List[Dict[str, Any]]) -> Dict[str, Any]:
    """RECONCILE the enrich pass against the crop read — the enrich prompt says
    'never invent or drop', but a prompt is not a guarantee, so enforce it here:
    each crop element is REPLACED by its id-matched enriched version and KEPT
    as-is when the enrich pass dropped it; enriched entries with ids the crop
    never read are DISCARDED (an enrich pass may only correct, never originate —
    a full-page-only 'element' at overview resolution is exactly the kind of
    low-res read the §4 finding forbids trusting). Counters record what happened
    so a systematic drift shows up in review, not silently."""
    # Both lists come from vision tool-use output — the JSON-schema "items":
    # {"type":"object"} is a request, not a guarantee; a malformed array entry
    # (bare string) has been observed in practice. Same isinstance guard used
    # throughout this module (read_wiring_coverage / read_schedule_coverage).
    crop_els = [e for e in (r.get("elements") or []) if isinstance(e, dict)]
    enriched = [e for e in enriched if isinstance(e, dict)]
    if not enriched:
        return {**r, "elements": crop_els, "_cross_referenced": False,
                "_enrich_note": "enrich pass returned no usable elements — crop-only read kept"}
    by_id: Dict[str, Dict[str, Any]] = {}
    for e in enriched:
        by_id.setdefault(_norm_id(e.get("id")), e)
    merged, dropped = [], 0
    used: set = set()
    for e in crop_els:
        k = _norm_id(e.get("id"))
        if k and k in by_id and k not in used:
            merged.append({**e, **by_id[k]})   # enriched fields win; crop fields survive where absent
            used.add(k)
        else:
            merged.append(e)                    # enrich dropped it -> keep the crop read
            dropped += 1
    invented = sum(1 for k in by_id if k not in used)
    return {**r, "elements": merged, "_cross_referenced": True,
            "_enrich_dropped_kept_from_crop": dropped,
            "_enrich_invented_discarded": invented}


_ENRICH_PROMPT = (
    "This image is the WHOLE electrical sheet (the region under study is outlined "
    "in red). Below is a list of elements ALREADY READ from a high-resolution crop "
    "of that region. Your job is NOT to re-read the crop and NOT to summarize — it "
    "is to CORRECT and ENRICH each listed element using the full sheet:\n"
    " - fix element_type where the full sheet makes it clear (e.g. a block the crop "
    "called a 'switch' that the whole sheet shows is a multi-pin harness "
    "connector/plug; a tap the crop called a signal that is actually a power bus);\n"
    " - complete any label cut off at the crop edge (e.g. a partial maker name);\n"
    " - fill connections: what each element connects to across the sheet, which "
    "enclosure/section (dotted boundary) it sits in, and any cross-drawing "
    "reference.\n"
    "Return the SAME elements, corrected — one entry per input element, preserving "
    "its id. Change a type only when the full sheet genuinely shows the crop was "
    "wrong; otherwise keep it. Never invent new elements or drop existing ones."
)


def enrich_region_against_full_page(
        elements: List[Dict[str, Any]], pdf_bytes: bytes, page_index: int,
        bbox: List[float], *, legend_context: str = "", dpi: int = 200) -> Dict[str, Any]:
    """
    TWO-CALL cross-reference, call 2 (the designed fix for the summarize failure
    of the two-image single call): given the crop-only element list, send the
    FULL PAGE + that list and ask the model to CORRECT each element's type/label/
    connections against the whole sheet. Because call 2 receives a concrete list
    to fix (not a blank enumerate), it does not collapse into a region summary.
    Returns the corrected {elements: [...]}.
    """
    if not elements:
        return {"elements": []}
    vp = get_vision_provider("electrical")
    overview = _full_page_with_box(pdf_bytes, page_index, bbox)
    listing = "\n".join(
        f"- id={e.get('id')!r} type={e.get('element_type')!r} label={e.get('label')!r}"
        for e in elements)
    prompt = _ctx(legend_context, _ENRICH_PROMPT) + "\n\nELEMENTS READ FROM THE CROP:\n" + listing
    return vp.extract_multi([(overview, "image/png")], prompt, _WIRING_TOOL)


def _row_key(row: Dict[str, Any]) -> tuple:
    import re as _re
    n = lambda s: _re.sub(r"[^a-z0-9]+", "", str(s or "").lower())
    return (n(row.get("device_id")), n(row.get("load_name"))[:24])


def read_schedule_coverage(pdf_bytes: bytes, page_index: int,
                           survey_regions: Optional[List[Dict[str, Any]]] = None,
                           *, dpi: int = 600, legend_context: str = "") -> List[Dict[str, Any]]:
    """Schedule read with the same COVERAGE GUARANTEE as read_wiring_coverage —
    survey-detected panel/breaker regions PLUS a fixed full-sheet grid, merged with
    dedupe. Same root cause applies here: the survey's region detection is
    stochastic, so a schedule reader keyed only on it can silently miss rows."""
    from pipeline import meter
    meter.set_layer("schedule")
    page = vx.rasterize_pdf_page(pdf_bytes, page_index, dpi=dpi)
    vp = get_vision_provider("electrical")
    _prompt = _ctx(legend_context, _SCHEDULE_PROMPT)
    seen: Dict[tuple, Dict[str, Any]] = {}
    panel_label = None
    skipped = 0
    for rg in (survey_regions or []):
        r = vp.extract(_crop_box(page, rg["bbox"]), "image/png", _prompt, _SCHEDULE_TOOL)
        panel_label = panel_label or r.get("panel_label")
        for row in r.get("rows", []):
            if not isinstance(row, dict):
                skipped += 1
                continue
            row["_via"] = "survey_region"
            row["_bbox"] = rg["bbox"]
            seen.setdefault(_row_key(row), row)
    for gb in grid_boxes():
        r = vp.extract(_crop_box(page, gb), "image/png", _prompt, _SCHEDULE_TOOL)
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
                         *, dpi: int = 600, legend_context: str = "") -> List[Dict[str, Any]]:
    """Wiring read with the COVERAGE GUARANTEE: reads the survey's wiring regions
    (tight crops, best resolution) PLUS a fixed full-sheet grid, then merges with
    dedupe. An element found by either path is kept; grid-only finds are marked."""
    from pipeline import meter
    meter.set_layer("wiring")
    page = vx.rasterize_pdf_page(pdf_bytes, page_index, dpi=dpi)
    vp = get_vision_provider("electrical")
    _prompt = _ctx(legend_context, _WIRING_PROMPT)
    seen: Dict[tuple, Dict[str, Any]] = {}
    skipped = 0
    for rg in (survey_regions or []):
        r = vp.extract(_crop_box(page, rg["bbox"]), "image/png", _prompt, _WIRING_TOOL)
        for e in r.get("elements", []):
            if not isinstance(e, dict):
                skipped += 1
                continue
            e["_via"] = "survey_region"
            e["_bbox"] = rg["bbox"]
            seen.setdefault(_el_key(e), e)
    for gb in grid_boxes():
        r = vp.extract(_crop_box(page, gb), "image/png", _prompt, _WIRING_TOOL)
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
                        *, dpi: int = 400, legend_context: str = "") -> Dict[str, Any]:
    """PASS 2 (sub-type B) — read the topology of a one-line region."""
    from pipeline import meter
    meter.set_layer("oneline")
    vp = get_vision_provider("electrical")
    page = vx.rasterize_pdf_page(pdf_bytes, page_index, dpi=dpi)
    return vp.extract(_crop_box(page, bbox), "image/png",
                      _ctx(legend_context, _ONELINE_PROMPT), _ONELINE_TOOL)


def _node_key(n: Dict[str, Any]) -> tuple:
    import re as _re
    norm = lambda s: _re.sub(r"[^a-z0-9]+", "", str(s or "").lower())
    return (n.get("node_type"), norm(n.get("id")), norm(n.get("label"))[:24])


def read_oneline_coverage(pdf_bytes: bytes, page_index: int,
                         survey_regions: Optional[List[Dict[str, Any]]] = None,
                         *, dpi: int = 500, legend_context: str = "") -> Dict[str, Any]:
    """One-line topology read with the same COVERAGE GUARANTEE as wiring/schedule —
    survey-detected topology_network regions PLUS a fixed full-sheet grid, merged
    with dedupe on (node_type, id, label). Same root cause: survey region-detection
    is stochastic, a reader keyed only on it can silently miss nodes/edges."""
    page = vx.rasterize_pdf_page(pdf_bytes, page_index, dpi=dpi)
    vp = get_vision_provider("electrical")
    _prompt = _ctx(legend_context, _ONELINE_PROMPT)
    seen: Dict[tuple, Dict[str, Any]] = {}
    edges: List[str] = []
    skipped = 0
    for rg in (survey_regions or []):
        r = vp.extract(_crop_box(page, rg["bbox"]), "image/png", _prompt, _ONELINE_TOOL)
        for n in r.get("nodes", []):
            if not isinstance(n, dict):
                skipped += 1
                continue
            n["_via"] = "survey_region"; n["_bbox"] = rg["bbox"]
            seen.setdefault(_node_key(n), n)
        edges.extend(x for x in r.get("edges", []) if isinstance(x, str))
    for gb in grid_boxes():
        r = vp.extract(_crop_box(page, gb), "image/png", _prompt, _ONELINE_TOOL)
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


def extract_sheet(pdf_bytes: bytes, page_index: int = 0, *,
                  legends_first: bool = True) -> Dict[str, Any]:
    """
    Full electrical extraction. LEGENDS FIRST (mandatory by default — the
    engineer-mandated protocol, 2026-07-06): every legend/reference table on the
    sheet is inventoried and read verbatim BEFORE any diagram symbol, and the
    result is prepended to every extraction prompt so classification uses THIS
    sheet's own definitions. Then survey + dispatch a detail reader PER REGION
    TYPE: schedule reader (breaker_bank/panel_column), wiring reader
    (terminal_strip/relay_bank/controller_module), one-line topology reader
    (topology_network).
    """
    legends: Dict[str, Any] = {"tables": [], "context_block": ""}
    if legends_first:
        legends = legend_first.from_pdf(pdf_bytes, page_index)
    ctx = legends.get("context_block", "")
    s = survey(pdf_bytes, page_index, legend_context=ctx)
    result: Dict[str, Any] = {"legends": legends.get("tables", []),
                              "legend_context": ctx,
                              "survey": s, "sub_type": s.get("sub_type"),
                              "regions_read": [], "scoped_next": []}
    for rg in s.get("regions", []):
        rtype = rg.get("type")
        if rtype in _SCHEDULE_REGIONS:
            rows = read_schedule_region(pdf_bytes, rg["bbox"], page_index, legend_context=ctx)
            result["regions_read"].append({
                "region": rg.get("label"), "region_type": rtype, "bbox": rg["bbox"],
                "reader": "schedule", "panel_label": rows.get("panel_label"),
                "rows": rows.get("rows", [])})
        elif rtype in _WIRING_REGIONS:
            # COVERAGE GUARANTEE (fix 2026-07-22): read_wiring_coverage was built
            # and validated (264 elements on GM-114a incl. the T/S B fused
            # terminals) but extract_sheet still called the region-only reader,
            # so ~2/3 of a wiring sheet went unread — T/S B never reached the
            # graph and the relay coils lost their + feed. Dispatch through the
            # coverage reader; handled ONCE per sheet, not per region.
            continue  # wiring regions handled after the loop, in one coverage pass
        elif rtype in _ONELINE_REGIONS:
            topo = read_oneline_region(pdf_bytes, rg["bbox"], page_index, legend_context=ctx)
            result["regions_read"].append({
                "region": rg.get("label"), "region_type": rtype, "bbox": rg["bbox"],
                "reader": "oneline", "nodes": topo.get("nodes", []),
                "edges": topo.get("edges", [])})
        # legend regions are no longer skipped — they were read UP FRONT by
        # legend_first and their content rides in every prompt above.

    # WIRING: one COVERAGE pass for the whole sheet (survey wiring regions
    # UNION a full-sheet grid, merged+deduped) — guarantees nothing is left
    # unread, which the region-only path could not.
    wiring_regions = [rg for rg in s.get("regions", [])
                      if rg.get("type") in _WIRING_REGIONS]
    if wiring_regions:
        els = read_wiring_coverage(pdf_bytes, page_index, wiring_regions,
                                   legend_context=ctx)
        result["regions_read"].append({
            "region": "ALL WIRING (coverage: survey regions + full-sheet grid)",
            "region_type": "relay_terminal_wiring", "bbox": [0, 0, 1, 1],
            "reader": "wiring_coverage", "elements": els})
    return result
