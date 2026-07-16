"""
Gold-blind structure-discovery extractor for dense schematic sheets (§4, §9c).

GOVERNING PRINCIPLE (§0.5): this module DISCOVERS the structure of a schematic
by GENERAL rules and must transfer to any vessel/shipyard/brand. It therefore
contains NO vessel-specific token — no manifold brand, no part-number pattern,
no function label, no expected slice count. Every prompt is phrased generally.
The gold-standard values used to grade this output live ONLY in the separate
tests/ harness and are never imported here. If a Gelliceaux-specific value ever
appears in this file, the design has failed — remove it and generalize.

Two passes (§4):
  SKELETON (~200 DPI, whole sheet): read the header (manifold make/model, title,
    revision, sheet), the shared rails, and DETECT the repeated vertical
    sub-circuits ("function slices") — reporting how many were FOUND (never an
    assumed count) plus each slice's approximate horizontal extent so it can be
    cropped. Also reports whether the manifold's OWN block-level capacity is
    printed on the sheet (it usually is not — it lives in the manual).
  DETAIL (600 DPI, per discovered slice): crop each slice and read the fine
    print now legible — cartridge/part identifiers, limiter/relief settings,
    actuation, ports. This is where tiling earns its place: data invisible at
    whole-sheet resolution becomes readable.

Output: a slice-keyed catalog + a plain-language STRUCTURE-DISCOVERY REPORT
(graded first, on reasoning, per §0.5). No comparison to any gold value happens
here.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

from pipeline import visual_extract as vx
from pipeline import legend_first
from providers.vision import get_vision_provider

# ---- Gold-blind prompts (general hydraulic-sheet language only) -------------

_SKELETON_PROMPT = """\
You are reading a hydraulic or pneumatic manifold/valve-block schematic sheet at
LOW resolution. Map its STRUCTURE only — do not guess fine print you cannot read
at this resolution; list illegible items in `notes` instead.

This kind of sheet is typically organized as a ROW of REPEATED vertical
sub-circuits, each controlling ONE function (an actuator / winch / ram / valve),
all sharing common supply / return / sense rails at the sheet edges. DETECT that
repetition and report what you actually find — do NOT assume any particular
number of sub-circuits.

Report:
- header: any manifold / valve-block make and model printed in the title block
  or header; the sheet title; revision; sheet number/position. (Read only what
  is printed.)
- rails: the shared lines running across the whole sheet that every sub-circuit
  taps (e.g. pressure / tank-return / load-sense / gauge). Name each as labelled.
- function_slices: one entry per repeated sub-circuit you can distinguish, each:
    label (function name as printed), identifier (e.g. a valve/EV number if
    printed), rating (flow/spool rating if printed, with units), actuation
    (e.g. proportional vs on/off if printed), neutral (rest position if printed),
    x_left and x_right = approximate horizontal extent normalized 0..1 across the
    sheet width, so the region can be cropped for a high-resolution read.
  ALSO report elements that are NOT one of the repeated function slices — inlet/
  end sections, a whole-block pressure relief, standalone auxiliary valves with
  their own EV/identifier — as entries with is_block_level=true (same fields;
  label = what is printed, or a plain description if unlabeled). These belong to
  the BLOCK as a whole, not to any one function; do not skip them and do not
  force them into a function-slice interpretation.
- block_capacity_printed: true ONLY if this sheet prints the MANIFOLD's OWN
  overall flow/pressure capacity (a property of the whole block) — as opposed to
  the per-function ratings. If only per-function ratings are shown, set false.
- notes: anything visibly present but NOT legible at this resolution (so it gets
  re-read at higher resolution): cartridge part numbers, pressure settings, etc.
"""

_SKELETON_TOOL = {
    "name": "record_skeleton",
    "description": "Record the discovered structure of the schematic sheet.",
    "input_schema": {
        "type": "object",
        "properties": {
            "header": {
                "type": "object",
                "properties": {
                    "make_model": {"type": "string"}, "title": {"type": "string"},
                    "revision": {"type": "string"}, "sheet": {"type": "string"},
                },
            },
            "rails": {"type": "array", "items": {"type": "string"}},
            "function_slices": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "identifier": {"type": "string"},
                        "rating": {"type": "string"},
                        "actuation": {"type": "string"},
                        "neutral": {"type": "string"},
                        "x_left": {"type": "number"},
                        "x_right": {"type": "number"},
                        "is_block_level": {"type": "boolean"},
                    },
                    "required": ["label"],
                },
            },
            "block_capacity_printed": {"type": "boolean"},
            "notes": {"type": "string"},
        },
        "required": ["header", "function_slices", "block_capacity_printed"],
    },
}

# FUNCTION-OVER-PART-NUMBER (engineer protocol correction 2026-07-12): the
# diagnostic knowledge is each cartridge's ROLE in the circuit and the OIL PATH
# per operating scenario — NOT its part-number string. Part numbers caused the
# whole confabulation/locate-recall saga and the engineer can read one himself
# the moment Engo highlights the region (bbox provenance). So: role + flow are
# REQUIRED; the printed id is recorded only when clearly legible, never chased,
# and its absence is not a failure.
_DETAIL_PROMPT = """\
You are reading ONE vertical sub-circuit (one function) of a hydraulic manifold
schematic, cropped at HIGH resolution. Your job is to UNDERSTAND THE CIRCUIT:
what each valve/cartridge DOES and how oil flows in each operating scenario.
Report ONLY what the drawing actually shows; mark anything ambiguous or
illegible rather than guessing.

Report:
- function: the function label/name and its identifier as printed.
- rating: flow/spool rating with units.
- actuation: actuation type; neutral/rest position.
- cartridges: one entry per valve/cartridge in this sub-circuit. For each, the
  ROLE is what matters: what it does in the circuit (main directional spool,
  work-port relief, load-holding/counterbalance, pilot-operated check, LS
  pressure limiter, inlet relief, shuttle, orifice...) and WHERE it sits in the
  flow (pressure line, A/B work port, tank return, LS line).
  DERIVE THE ROLE FROM THE DRAWN CONNECTIONS ONLY: trace where the cartridge's
  inlet comes from and where its outlet line actually goes in THIS crop — an
  outlet drawn to the tank/return rail makes it a port RELIEF dumping to tank;
  an element sitting in the load-sense line makes it an LS limiter. Never assign
  a role from typical manifold architecture or from what similar sections
  usually contain. State the traced connection in position_in_flow (e.g.
  "outlet runs to T return rail"). If the connections are not traceable in this
  crop, say role="unconfirmed — connections not traceable" rather than guessing.
  Record the printed part identifier ONLY if clearly legible — do not strain
  for it; an omitted id with a correct role is a GOOD read.
- flow_scenarios: the oil path through this sub-circuit per scenario, as the
  symbols show it: e.g. "energized A: P->spool->A port, B->tank; load held by
  counterbalance on B" / "neutral: spool open-center, flow to tank" / "relief:
  A-port relief opens to tank above its setting". One entry per distinct
  scenario the drawing supports.
- settings: any pressure-limiter / relief / threshold values with units.
- ports: work ports and what each connects to; note if a connection runs off
  the crop edge (off-sheet).
- illegible: anything present but not readable even at this resolution.
"""

_DETAIL_TOOL = {
    "name": "record_slice_detail",
    "description": "Record the high-resolution detail of one function slice.",
    "input_schema": {
        "type": "object",
        "properties": {
            "function": {"type": "string"},
            "rating": {"type": "string"},
            "actuation": {"type": "string"},
            "neutral": {"type": "string"},
            "cartridges": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string"},
                        "position_in_flow": {"type": "string"},
                        "id": {"type": "string"},
                        "setting": {"type": "string"},
                    },
                    "required": ["role"],
                },
            },
            "flow_scenarios": {"type": "array", "items": {"type": "string"}},
            "settings": {"type": "array", "items": {"type": "string"}},
            "ports": {"type": "array", "items": {"type": "string"}},
            "illegible": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["function", "cartridges", "flow_scenarios"],
    },
}


def _crop_x(png_bytes: bytes, x_left: float, x_right: float, pad: float = 0.02) -> bytes:
    """Crop a full vertical band [x_left, x_right] (normalized) from a page raster."""
    from PIL import Image
    img = Image.open(io.BytesIO(png_bytes))
    w, h = img.size
    l = max(0, int((x_left - pad) * w))
    r = min(w, int((x_right + pad) * w))
    if r <= l:
        l, r = 0, w
    crop = img.crop((l, 0, r, h))
    buf = io.BytesIO()
    crop.save(buf, format="PNG")
    return buf.getvalue()


# ---- Discovered-targeting: locate callouts, then crop+read each (gold-blind) ----

_LOCATE_PROMPT = """\
This image is a vertical strip of a hydraulic/pneumatic schematic. Find every
small alphanumeric CALLOUT / part-identifier code printed on the drawing — the
short codes printed near valve symbols, along rails, or along component bodies
(the kind an engineer zooms in to read). For EACH one you can SEE — whether or
not you can read it — return:
- bbox: bounding box normalized 0..1 within THIS image, [x0, y0, x1, y1]
- text: the code verbatim ONLY if fully legible; otherwise leave empty
- confident: true only if the text is fully legible
Report the LOCATION even when the text is illegible — locating it lets it be
re-cropped at higher resolution. Do not invent codes; an empty text is correct
when you cannot read it.
"""

_LOCATE_TOOL = {
    "name": "record_callouts",
    "description": "Record the location of every small alphanumeric callout.",
    "input_schema": {
        "type": "object",
        "properties": {
            "callouts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "bbox": {"type": "array", "items": {"type": "number"}},
                        "text": {"type": "string"},
                        "confident": {"type": "boolean"},
                    },
                    "required": ["bbox"],
                },
            },
        },
        "required": ["callouts"],
    },
}

_READ_PROMPT = """\
This is a tight crop around one or more small printed codes on a schematic. Read
each alphanumeric part-number / identifier verbatim. If genuinely illegible,
return it in `illegible` and do NOT put anything in `codes`. Never guess a code.
"""

_READ_TOOL = {
    "name": "record_codes",
    "description": "Read the printed code(s) in a tight crop.",
    "input_schema": {
        "type": "object",
        "properties": {
            "codes": {"type": "array", "items": {"type": "string"}},
            "illegible": {"type": "boolean"},
        },
        "required": ["codes"],
    },
}


def _rotate_png(png_bytes: bytes, deg: int) -> bytes:
    from PIL import Image
    img = Image.open(io.BytesIO(png_bytes))
    if deg:
        img = img.rotate(-deg, expand=True)  # PIL rotates CCW; -deg = clockwise
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _read_with_rotation(vp, tile: bytes) -> Dict[str, Any]:
    """
    BUILD 3 — rotation handling. Read at 0°; if illegible (no codes), retry at
    90°/270°/180° (vertical labels are standard on drawings). Cheap: rotations
    fire only when the upright read is empty. Returns {deg, codes}.
    """
    rd = vp.extract(tile, "image/png", _READ_PROMPT, _READ_TOOL)
    codes = [c.strip() for c in (rd.get("codes") or []) if c and c.strip()]
    if codes:
        return {"deg": 0, "codes": codes}
    for deg in (90, 270, 180):
        rd = vp.extract(_rotate_png(tile, deg), "image/png", _READ_PROMPT, _READ_TOOL)
        codes = [c.strip() for c in (rd.get("codes") or []) if c and c.strip()]
        if codes:
            return {"deg": deg, "codes": codes}
    return {"deg": None, "codes": []}


def locate_and_read(
    pdf_bytes: bytes,
    page_index: int,
    x0: float, x1: float,
    *,
    n_bands: int = 5,
    dpi: int = 600,
    margin: float = 0.008,
    band_overlap: float = 0.15,
    x_pad: float = 0.012,
) -> List[Dict[str, Any]]:
    """
    DISCOVERED-TARGETING (Master Spec item 2): for a slice [x0,x1], systematically
    band the slice (no human choosing the band), run a LOCATE pass per band to get
    callout bboxes, then crop EACH discovered bbox tight at full DPI and READ it
    (with rotation). Bands OVERLAP and the slice is x-padded so edge/boundary
    callouts aren't clipped. De-duplicated by location. Returns
    [{sheet_bbox, read, deg, locate_text}]. Fully automated.
    """
    vp = get_vision_provider("hydraulic_schematic")
    page = vx.rasterize_pdf_page(pdf_bytes, page_index, dpi=dpi)
    px0, px1 = max(0.0, x0 - x_pad), min(1.0, x1 + x_pad)
    out: List[Dict[str, Any]] = []
    seen: set = set()
    step = 1.0 / n_bands
    for b in range(n_bands):
        by0 = max(0.0, b * step - band_overlap * step)
        by1 = min(1.0, (b + 1) * step + band_overlap * step)
        band, _ = _crop_box(page, px0, by0, px1, by1)
        loc = vp.extract(band, "image/png", _LOCATE_PROMPT, _LOCATE_TOOL)
        for c in loc.get("callouts") or []:
            bb = c.get("bbox")
            if not bb or len(bb) < 4:
                continue
            sx0 = px0 + bb[0] * (px1 - px0); sx1 = px0 + bb[2] * (px1 - px0)
            sy0 = by0 + bb[1] * (by1 - by0); sy1 = by0 + bb[3] * (by1 - by0)
            key = (round(sx0, 2), round(sy0, 2), round(sx1, 2), round(sy1, 2))
            if key in seen:  # same callout located in overlapping bands
                continue
            seen.add(key)
            tile, _ = _crop_box(page, max(0.0, sx0 - margin), max(0.0, sy0 - margin),
                                min(1.0, sx1 + margin), min(1.0, sy1 + margin))
            rr = _read_with_rotation(vp, tile)
            for code in rr["codes"]:
                out.append({"sheet_bbox": [round(sx0, 3), round(sy0, 3),
                                           round(sx1, 3), round(sy1, 3)],
                            "read": code, "deg": rr["deg"], "locate_text": c.get("text", "")})
    return out


def _crop_box(png_bytes: bytes, x0: float, y0: float, x1: float, y1: float):
    """Crop a normalized box [x0,y0,x1,y1] from a page raster. Returns (png, (w,h))."""
    from PIL import Image
    img = Image.open(io.BytesIO(png_bytes))
    w, h = img.size
    box = (max(0, int(x0 * w)), max(0, int(y0 * h)),
           min(w, int(x1 * w)), min(h, int(y1 * h)))
    crop = img.crop(box)
    buf = io.BytesIO()
    crop.save(buf, format="PNG")
    return buf.getvalue(), crop.size


def detail_subtile(
    pdf_bytes: bytes,
    page_index: int,
    x0: float, x1: float, y0: float, y1: float,
    *,
    dpi: int = 600,
) -> Dict[str, Any]:
    """
    Read ONE tight sub-tile (normalized box) from a high-DPI page render.

    CROP FOOTPRINT, not render DPI, is the binding constraint: the provider caps
    the long edge to its max_side (1568px on pre-4.7 Claude, 2576px on Sonnet 5 /
    Opus 4.8, 3072px Gemini, 2048px OpenAI), so an oversized crop crushes the
    cartridge text to noise. Keep the box's long edge at/under the cap (and ideally
    make WIDTH the long edge by limiting height) so the small labels survive.
    Returns {detail, crop_px, phys_mm, eff_dpi_after_cap}.
    """
    vp = get_vision_provider("hydraulic_schematic")
    page = vx.rasterize_pdf_page(pdf_bytes, page_index, dpi=dpi)
    tile, (cw, ch) = _crop_box(page, x0, y0, x1, y1)
    res = vp.extract(tile, "image/png", _DETAIL_PROMPT, _DETAIL_TOOL)
    long_edge = max(cw, ch)
    cap = min(1.0, vp.max_side / long_edge)  # provider downscale factor (model-dependent)
    return {
        "detail": res,
        "crop_px": [cw, ch],
        "phys_mm": [round(cw / dpi * 25.4, 1), round(ch / dpi * 25.4, 1)],
        "eff_dpi_after_cap": round(dpi * cap),
    }


def discover_structure(
    pdf_bytes: bytes,
    page_index: int = 0,
    *,
    do_detail: bool = True,
    skeleton_dpi: int = 200,
    detail_dpi: int = 600,
    legends_first: bool = True,
    legend_context: str = "",
) -> Dict[str, Any]:
    """
    Run the gold-blind two-pass discovery on one schematic page.
    LEGENDS FIRST (mandatory by default, engineer-mandated 2026-07-06): every
    legend/reference table on the sheet is read verbatim BEFORE the skeleton
    pass and prepended to both passes' prompts, so symbol/line classification
    uses THIS sheet's own definitions. Pass legend_context to reuse an
    already-built block; legends_first=False only for deliberate A/B testing.
    Returns {header, rails, block_capacity_printed, slices:[{...skeleton + detail}],
    legends, notes, passes}. Detail pass is per DISCOVERED slice (count is
    never assumed).
    """
    vp = get_vision_provider("hydraulic_schematic")

    # PASS 0 — legends first (steps 0-2 of the sheet-reading sequence)
    legends: Dict[str, Any] = {"tables": [], "context_block": legend_context}
    if legends_first and not legend_context:
        legends = legend_first.from_pdf(pdf_bytes, page_index, vp=vp)
    ctx = legends.get("context_block", legend_context)

    # PASS 1 — skeleton (whole sheet, low res)
    skel_img = vx.rasterize_pdf_page(pdf_bytes, page_index, dpi=skeleton_dpi)
    skel = vp.extract(skel_img, "image/png",
                      legend_first.with_context(ctx, _SKELETON_PROMPT), _SKELETON_TOOL)
    slices = skel.get("function_slices") or []

    result: Dict[str, Any] = {
        "header": skel.get("header", {}),
        "rails": skel.get("rails", []),
        "block_capacity_printed": skel.get("block_capacity_printed"),
        "notes": skel.get("notes", ""),
        "slices": [dict(s) for s in slices],
        "legends": legends.get("tables", []),
        "legend_context": ctx,
        "passes": {"skeleton_dpi": skeleton_dpi, "detail_dpi": None,
                   "slices_found": len(slices), "detail_calls": 0},
        "model": skel.get("_model"),
    }
    if not do_detail or not slices:
        return result

    # PASS 2 — detail, one tile per DISCOVERED slice at high res
    page_hi = vx.rasterize_pdf_page(pdf_bytes, page_index, dpi=detail_dpi)
    detail_calls = 0
    detail_prompt = legend_first.with_context(ctx, _DETAIL_PROMPT)
    for s in result["slices"]:
        xl, xr = s.get("x_left"), s.get("x_right")
        if xl is None or xr is None:
            s["detail"] = {"skipped": "no x-extent from skeleton"}
            continue
        tile = _crop_x(page_hi, float(xl), float(xr))
        det = vp.extract(tile, "image/png", detail_prompt, _DETAIL_TOOL)
        # settings may come back as a single string — normalize to list so
        # consumers never iterate characters (observed live: exploded chars)
        if isinstance(det.get("settings"), str):
            det["settings"] = [det["settings"]]
        s["detail"] = det
        # 600-DPI detail beats 200-DPI skeleton: promote fine-print fields the
        # skeleton can only squint at (a PVEO/PVED one-letter misread lived at
        # skeleton resolution — engineer-confirmed PVEO, 2026-07-13)
        for fld in ("actuation", "rating", "neutral"):
            v = det.get(fld)
            if v and str(v).strip() and "UNKNOWN" not in str(v).upper():
                if s.get(fld) != v:
                    s[f"{fld}_skeleton"] = s.get(fld)
                    s[fld] = v
        detail_calls += 1
    result["passes"]["detail_dpi"] = detail_dpi
    result["passes"]["detail_calls"] = detail_calls
    return result


def discovery_report(r: Dict[str, Any]) -> str:
    """Plain-language structure-discovery report (graded first, per §0.5)."""
    h = r.get("header", {})
    lines = [
        "STRUCTURE-DISCOVERY REPORT (gold-blind)",
        f"  manifold model (from header): {h.get('make_model') or '— not read —'}",
        f"  sheet: {h.get('title','')} | rev {h.get('revision','')} | {h.get('sheet','')}",
        f"  shared rails detected: {', '.join(r.get('rails') or []) or '—'}",
        f"  function slices DISCOVERED: {len(r.get('slices') or [])} "
        f"(detected by repetition, not assumed)",
        f"  block-level capacity printed on sheet? {r.get('block_capacity_printed')} "
        f"(if false → lives in the manifold manual, not the schematic)",
    ]
    for i, s in enumerate(r.get("slices") or [], 1):
        d = s.get("detail") or {}
        carts = ", ".join(
            (c.get("role") or c.get("id") or "?") for c in (d.get("cartridges") or [])) or "—"
        setts = ", ".join(d.get("settings") or []) or "—"
        lines.append(
            f"  slice {i}: {s.get('label','?')} [{s.get('identifier','')}] "
            f"rating={s.get('rating','?')} actuation={s.get('actuation','?')} "
            f"| tiled cartridges={carts} | settings={setts}")
    if r.get("notes"):
        lines.append(f"  skeleton notes (illegible at low res → tiled): {r['notes']}")
    return "\n".join(lines)
