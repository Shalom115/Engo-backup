"""
FUSED TILE PASS (2026-07-26) — read each tile ONCE, not three times.

MEASURED WASTE. A wiring sheet costs $1.39 over 47 vision calls. Three of the
layers look at overlapping regions of the SAME sheet at similar resolution and
ask three different questions of the same ink:

    label OCR        16 calls   $0.25   "what text is printed here?"
    device locate    16 calls   $0.25   "what symbols are here, and where?"
    wiring coverage  11 calls   $0.47   "what elements are here and what do
                                         they connect to?"
                     ----------------
                     43 of 47   $0.96 of $1.39   (69%)

Nothing about a drawing changes between those three looks. Fusing them into one
tiled pass that returns labels + symbols + elements together removes roughly
two thirds of the calls.

QUALITY IS THE REASON, NOT JUST COST. Today the model reads "Re7" in one call
and sees the relay symbol in a different call; the link between them is
reconstructed afterwards from bounding-box geometry, and when that fails the
composition gets "contact=unknown" and a coil with no id. Seen together in one
look, the model can state directly that this label belongs to that symbol, and
which contact the dotted line reaches — the association that keeps coming back
empty. Connectivity still comes from the vector tracer, which is not a model
and does not guess; this pass supplies naming and typing only.

Gold-blind: the prompt describes general drawing conventions and no vessel
token.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Tuple

import config  # loads .env
from pipeline import label_ocr

_FUSED_PROMPT = (
    "This crop is part of an electrical wiring diagram. Report EVERYTHING "
    "printed in it, in one pass, as three lists.\n\n"
    "1) LABELS — every piece of printed text: terminal numbers, device ids, "
    "function names, ratings, cable ids, plug/pin numbers, notes. Give each a "
    "bounding box [x0,y0,x1,y1] normalized 0-1 WITHIN THIS CROP. Transcribe "
    "exactly as printed; do not expand abbreviations, do not tidy up.\n\n"
    "2) SYMBOLS — every device symbol, with a bounding box in the same "
    "coordinates: relay/contactor COIL (rectangle with a divider), RELAY "
    "CONTACT, VALVE ACTUATOR / MOTOR ('M' in a circle or a motor symbol on a "
    "valve), FUSE (rectangle interrupting a conductor), BREAKER, SWITCH, "
    "TERMINAL STRIP (a labelled row/column of numbered terminals — one box for "
    "the strip plus its name), PLUG/CONNECTOR, INDICATOR LAMP, PUMP MOTOR, "
    "MULTI-CORE CABLE (thick line with equal numbered legs on both sides).\n\n"
    "3) ELEMENTS — for each device that has a function, one record joining "
    "what it IS to what it is CALLED and what it is drawn as serving: the "
    "device type, its printed id, the function label printed on or above it, "
    "and the ids/terminal numbers its own conductors visibly run to.\n\n"
    "BECAUSE YOU SEE THE TEXT AND THE SYMBOLS TOGETHER, SAY WHICH LABEL "
    "BELONGS TO WHICH SYMBOL. Set `owner_symbol` on a label when it names a "
    "specific symbol, and `id`/`function_label` on a symbol from the text "
    "printed on or immediately above it. This association is the reason both "
    "are read in one pass — do not leave a symbol unnamed when its name is "
    "printed beside it.\n\n"
    "DEVICE DISCIPLINE (decisive, apply every time): a breaker is not a fuse "
    "is not a relay is not a contactor is not a plain terminal. A monitoring "
    "or status tag block is not a power feed. Where a symbol is genuinely "
    "ambiguous set ambiguous=true — never guess a type.\n\n"
    "RELAY CONTACT STATE: a relay's CONTACTS sit near its coil, joined to it "
    "by a DOTTED line. A contact drawn OPEN with that dotted line is NORMALLY "
    "OPEN (NO) — energising the coil CLOSES it. Drawn CLOSED, it is NORMALLY "
    "CLOSED (NC) — energising the coil OPENS it. For every relay contact set "
    "contact_state to 'NO' or 'NC' (or 'unknown' only if truly illegible) and "
    "coil_id to the coil its dotted line reaches. This decides whether "
    "energising the relay turns its load on or off.\n\n"
    "Read only what is drawn. Do not invent, do not complete a partly visible "
    "item from expectation."
)

_FUSED_TOOL = {
    "name": "record_tile",
    "description": "Labels, symbols and elements found in this crop.",
    "input_schema": {
        "type": "object",
        "properties": {
            "labels": {"type": "array", "items": {"type": "object", "properties": {
                "text": {"type": "string"},
                "owner_symbol": {"type": "string"},
                "bbox": {"type": "array", "items": {"type": "number"},
                         "minItems": 4, "maxItems": 4}},
                "required": ["text", "bbox"]}},
            "symbols": {"type": "array", "items": {"type": "object", "properties": {
                "kind": {"type": "string"},
                "id": {"type": "string"},
                "function_label": {"type": "string"},
                "contact_state": {"type": "string",
                                  "enum": ["NO", "NC", "unknown"]},
                "coil_id": {"type": "string"},
                "bbox": {"type": "array", "items": {"type": "number"},
                         "minItems": 4, "maxItems": 4},
                "ambiguous": {"type": "boolean"}},
                "required": ["kind", "bbox"]}},
            "elements": {"type": "array", "items": {"type": "object", "properties": {
                "device_type": {"type": "string"},
                "id": {"type": "string"},
                "function_label": {"type": "string"},
                "rating": {"type": "string"},
                "connections": {"type": "string"},
                "ambiguous": {"type": "boolean"}},
                "required": ["device_type"]}},
        },
        "required": ["labels", "symbols"],
    },
}


def _to_page(items: List[Dict[str, Any]], bx: List[float],
             W: float, H: float) -> List[Dict[str, Any]]:
    """Crop-normalized boxes -> page points (same convention as label_ocr)."""
    out = []
    cx0, cy0 = bx[0] * W, bx[1] * H
    cw, ch = (bx[2] - bx[0]) * W, (bx[3] - bx[1]) * H
    for it in items:
        if not isinstance(it, dict):
            continue
        b = it.get("bbox")
        if not b or len(b) != 4:
            continue
        it = dict(it)
        it["bbox"] = [cx0 + b[0] * cw, cy0 + b[1] * ch,
                      cx0 + b[2] * cw, cy0 + b[3] * ch]
        out.append(it)
    return out


def read_tiles(pdf_bytes: bytes, page_index: int = 0, *,
               rows: int = 4, cols: int = 4, dpi: int = 400,
               overlap: float = 0.04,
               use_cache: bool = True) -> Dict[str, List[Dict[str, Any]]]:
    """One tiled pass returning {labels, symbols, elements} in PAGE POINTS."""
    from pipeline import vcache
    params = {"rows": rows, "cols": cols, "dpi": dpi, "overlap": overlap,
              "prompt": hashlib.sha256(_FUSED_PROMPT.encode()).hexdigest()[:12]}
    return vcache.get_or_compute(
        "fused", pdf_bytes, page_index, params,
        lambda: _read_tiles_uncached(pdf_bytes, page_index, rows=rows,
                                     cols=cols, dpi=dpi, overlap=overlap),
        enabled=use_cache)


def _read_tiles_uncached(pdf_bytes: bytes, page_index: int = 0, *,
                         rows: int = 4, cols: int = 4, dpi: int = 400,
                         overlap: float = 0.04) -> Dict[str, List[Dict[str, Any]]]:
    from providers.vision import get_vision_provider
    from pipeline import meter
    meter.set_layer("fused")
    vp = get_vision_provider("electrical", layer="tiles")
    W, H = label_ocr.page_size(pdf_bytes, page_index)
    labels: List[Dict[str, Any]] = []
    symbols: List[Dict[str, Any]] = []
    elements: List[Dict[str, Any]] = []
    for r in range(rows):
        for c in range(cols):
            bx = [max(0.0, c / cols - overlap), max(0.0, r / rows - overlap),
                  min(1.0, (c + 1) / cols + overlap),
                  min(1.0, (r + 1) / rows + overlap)]
            try:
                png = label_ocr._crop_png(pdf_bytes, page_index, bx, dpi)
                res = vp.extract(png, "image/png", _FUSED_PROMPT, _FUSED_TOOL,
                                 max_tokens=8192) or {}
            except Exception:
                continue
            for key, sink in (("labels", labels), ("symbols", symbols)):
                items = res.get(key)
                if isinstance(items, str):
                    import json as _j
                    try:
                        items = _j.loads(items)
                    except Exception:
                        items = []
                sink.extend(_to_page(items or [], bx, W, H))
            els = res.get("elements")
            if isinstance(els, str):
                import json as _j
                try:
                    els = _j.loads(els)
                except Exception:
                    els = []
            elements.extend([e for e in (els or []) if isinstance(e, dict)])
    return {"labels": label_ocr._dedupe(labels),
            "symbols": _dedupe_symbols(symbols),
            "elements": elements}


def _dedupe_symbols(symbols: List[Dict[str, Any]],
                    tol: float = 6.0) -> List[Dict[str, Any]]:
    """Overlapping tiles re-detect the same symbol; keep the richer record.

    'Richer' means the one that actually carries an id / function / contact
    state — an overlap must never lose the copy that read the label."""
    out: List[Dict[str, Any]] = []
    for s in symbols:
        b = s.get("bbox")
        if not b:
            continue
        hit = None
        for o in out:
            ob = o["bbox"]
            if (abs(ob[0] - b[0]) < tol and abs(ob[1] - b[1]) < tol
                    and abs(ob[2] - b[2]) < tol and abs(ob[3] - b[3]) < tol
                    and (o.get("kind") or "") == (s.get("kind") or "")):
                hit = o
                break
        if hit is None:
            out.append(dict(s))
            continue
        score = lambda d: sum(1 for k in ("id", "function_label", "coil_id")
                              if d.get(k)) + (
            1 if (d.get("contact_state") or "unknown") != "unknown" else 0)
        if score(s) > score(hit):
            hit.update({k: v for k, v in s.items() if v})
    return out


def as_netlist_inputs(tiles: Dict[str, List[Dict[str, Any]]]) -> Tuple[list, list]:
    """(labels, devices) in the shapes netlist.build already consumes, so the
    fused pass is a drop-in replacement for the two separate layers."""
    devices = [{"label": s.get("id") or s.get("function_label") or "",
                "kind": s.get("kind", ""),
                "contact_state": s.get("contact_state", ""),
                "coil_id": s.get("coil_id", ""),
                "bbox": s["bbox"]}
               for s in tiles.get("symbols", []) if s.get("bbox")]
    return tiles.get("labels", []), devices
