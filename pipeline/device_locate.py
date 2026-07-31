"""
DEVICE LOCATOR (2026-07-22) — the missing layer-3 input.

`netlist.bind_devices` can bind a device symbol to the conductors it touches,
but only if it is TOLD where each symbol sits. The wiring extractor names
device TYPES without coordinates, so the binding had nothing to consume. This
module returns the symbols WITH boxes, so the terminal->device question becomes
geometry, not association.

Tiled, high-DPI, gold-blind. Emits page-point boxes, same convention as
label_ocr, so both feed the netlist in one coordinate space.
"""

from __future__ import annotations

import config  # loads .env on import
from typing import Any, Dict, List, Tuple

from pipeline import label_ocr

_DEV_PROMPT = (
    "This crop is part of an electrical wiring diagram. Locate every DEVICE "
    "SYMBOL and give each a bounding box [x0,y0,x1,y1] normalized 0-1 WITHIN "
    "THIS CROP, plus its type and any printed id. Device types to find: "
    "relay/contactor COIL (rectangle with a divider; the label on top names "
    "what it drives), VALVE ACTUATOR / MOTOR (an 'M' in a circle or a motor "
    "symbol on a valve), FUSE (rectangle with a line through a conductor), "
    "TERMINAL STRIP (a labelled row/column of numbered terminals — give one "
    "box for the strip and its name e.g. 'T/S B'), PLUG/CONNECTOR (a "
    "multi-pin block, e.g. 'PLUG C'), SWITCH, PUMP MOTOR, INDICATOR LAMP "
    "(circle, often with an X), MULTI-CORE CABLE (a thick line with equal "
    "numbered legs both sides — box the cable and read its 'MUx' label). "
    "For each: type, id (as printed, '' if none), and the function label "
    "printed on/above it if any.\n"
    "RELAY CONTACT STATE (engineer rule — decisive, read it every time): a "
    "relay's CONTACTS are drawn near its coil, joined to it by a DOTTED LINE. "
    "If a contact is drawn OPEN with the dotted line, it is NORMALLY OPEN (NO) "
    "— energising the coil CLOSES it. If a contact is drawn CLOSED with the "
    "dotted line, it is NORMALLY CLOSED (NC) — energising the coil OPENS it. "
    "For every relay contact you find, set contact_state to 'NO' or 'NC' (or "
    "'unknown' only if truly illegible), and set coil_id to the id of the coil "
    "its dotted line reaches. This decides whether energising the relay turns "
    "its load ON or OFF — getting it wrong inverts the function.\n"
    "Read only what is drawn; do not invent; mark ambiguous=true rather than guess."
)
_DEV_TOOL = {
    "name": "record_devices",
    "description": "Device symbols with boxes in this crop.",
    "input_schema": {
        "type": "object",
        "properties": {
            "devices": {"type": "array", "items": {"type": "object", "properties": {
                "kind": {"type": "string"},
                "id": {"type": "string"},
                "function_label": {"type": "string"},
                "contact_state": {"type": "string", "enum": ["NO", "NC", "unknown"]},
                "coil_id": {"type": "string"},
                "bbox": {"type": "array", "items": {"type": "number"},
                         "minItems": 4, "maxItems": 4},
                "ambiguous": {"type": "boolean"}},
                "required": ["kind", "bbox"]}},
        },
        "required": ["devices"],
    },
}


def locate_devices(pdf_bytes: bytes, page_index: int = 0, *,
                   rows: int = 4, cols: int = 4, dpi: int = 400,
                   overlap: float = 0.04,
                   use_cache: bool = True) -> List[Dict[str, Any]]:
    """Every device symbol on the page, boxed in PAGE POINTS.

    CACHED BY CONTENT for the same reason as the label layer: the symbols
    printed on a sheet do not change between runs, so a red-pen cycle must not
    re-buy ~16 tiled vision calls to rediscover them."""
    import hashlib
    from pipeline import vcache
    params = {"rows": rows, "cols": cols, "dpi": dpi, "overlap": overlap,
              "prompt": hashlib.sha256(_DEV_PROMPT.encode()).hexdigest()[:12]}
    return vcache.get_or_compute(
        "devices", pdf_bytes, page_index, params,
        lambda: _locate_devices_uncached(pdf_bytes, page_index, rows=rows,
                                         cols=cols, dpi=dpi, overlap=overlap),
        enabled=use_cache)


def _locate_devices_uncached(pdf_bytes: bytes, page_index: int = 0, *,
                             rows: int = 4, cols: int = 4, dpi: int = 400,
                             overlap: float = 0.04) -> List[Dict[str, Any]]:
    """The real tiled locate pass (cache miss path)."""
    from pipeline import meter
    meter.set_layer("devices")
    from providers.vision import get_vision_provider
    vp = get_vision_provider("electrical", layer="devices")
    W, H = label_ocr.page_size(pdf_bytes, page_index)
    out: List[Dict[str, Any]] = []
    for r in range(rows):
        for c in range(cols):
            bx = [max(0.0, c / cols - overlap), max(0.0, r / rows - overlap),
                  min(1.0, (c + 1) / cols + overlap),
                  min(1.0, (r + 1) / rows + overlap)]
            try:
                png = label_ocr._crop_png(pdf_bytes, page_index, bx, dpi)
                res = vp.extract(png, "image/png", _DEV_PROMPT, _DEV_TOOL,
                                 max_tokens=8192) or {}
            except Exception:
                continue
            items = res.get("devices")
            if isinstance(items, str):
                import json as _j
                try:
                    items = _j.loads(items)
                except Exception:
                    items = []
            cw = (bx[2] - bx[0]) * W
            ch = (bx[3] - bx[1]) * H
            ox, oy = bx[0] * W, bx[1] * H
            for dv in items or []:
                if not isinstance(dv, dict):
                    continue
                b = dv.get("bbox")
                if not b or len(b) != 4:
                    continue
                label = (dv.get("id") or "").strip() or (dv.get("function_label") or "").strip()
                out.append({
                    "label": label,
                    "kind": (dv.get("kind") or "").strip(),
                    "function_label": (dv.get("function_label") or "").strip(),
                    "contact_state": (dv.get("contact_state") or "").strip(),
                    "coil_id": (dv.get("coil_id") or "").strip(),
                    "bbox": [ox + b[0] * cw, oy + b[1] * ch,
                             ox + b[2] * cw, oy + b[3] * ch],
                    "ambiguous": bool(dv.get("ambiguous"))})
    return _dedupe_devices(out)


def _dedupe_devices(devs: List[Dict[str, Any]], tol: float = 6.0) -> List[Dict[str, Any]]:
    """Overlapping tiles repeat symbols — one per (kind, id, position)."""
    seen: Dict[Tuple[str, str, int, int], Dict[str, Any]] = {}
    for d in devs:
        b = d["bbox"]
        key = (d["kind"].lower(), d["label"].lower(),
               int((b[0] + b[2]) / 2 / tol), int((b[1] + b[3]) / 2 / tol))
        seen.setdefault(key, d)
    return list(seen.values())
