"""
LABEL OCR WITH COORDINATES (2026-07-22).

The net tracer knows every conductor but not its NAME: on these drawings the
lettering is drawn as vector outlines, so the PDF text layer is empty. This
module produces `{text, bbox}` in PAGE POINT coordinates so labels can be bound
to the geometry.

Two sources, in order of trust:
  1. the PDF's own text layer, when it has one (free, exact);
  2. tiled vision OCR that returns normalized boxes, converted to points.

Tiling matters: a whole-sheet OCR pass crushes 6-8pt terminal numbers. Reading
in a grid at high DPI keeps small numerals legible — the same lesson that made
the tiling protocol necessary for cartridge IDs.
"""

from __future__ import annotations

import io
import config  # loads .env (API keys) on import
from typing import Any, Dict, List, Optional, Tuple

_OCR_PROMPT = (
    "This crop is part of an engineering drawing. Transcribe EVERY piece of "
    "text you can read — terminal numbers, device ids, wire numbers, labels, "
    "headers — and give each one a bounding box as [x0,y0,x1,y1] normalized "
    "0-1 WITHIN THIS CROP. Include short numeric labels (single and double "
    "digits) — they are terminal and wire numbers and they matter most. Do not "
    "translate, do not expand abbreviations, do not invent text. Skip nothing "
    "that is legible."
)
_OCR_TOOL = {
    "name": "record_labels",
    "description": "Every legible text item in the crop with its box.",
    "input_schema": {
        "type": "object",
        "properties": {
            "labels": {"type": "array", "items": {"type": "object", "properties": {
                "text": {"type": "string"},
                "bbox": {"type": "array", "items": {"type": "number"},
                         "minItems": 4, "maxItems": 4}},
                "required": ["text", "bbox"]}},
        },
        "required": ["labels"],
    },
}


def page_size(pdf_bytes: bytes, page_index: int = 0) -> Tuple[float, float]:
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    r = doc[page_index].rect
    return (r.width, r.height)


def labels_from_text_layer(pdf_bytes: bytes,
                           page_index: int = 0) -> List[Dict[str, Any]]:
    """Exact labels when the PDF actually carries text (free, no vision)."""
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    out: List[Dict[str, Any]] = []
    for w in doc[page_index].get_text("words"):
        x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
        if text.strip():
            out.append({"text": text.strip(), "bbox": [x0, y0, x1, y1],
                        "source": "text_layer"})
    return out


def _crop_png(pdf_bytes: bytes, page_index: int, box: List[float],
              dpi: int) -> bytes:
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_index]
    r = page.rect
    clip = fitz.Rect(r.x0 + box[0] * r.width, r.y0 + box[1] * r.height,
                     r.x0 + box[2] * r.width, r.y0 + box[3] * r.height)
    pix = page.get_pixmap(dpi=dpi, clip=clip)
    return pix.tobytes("png")


def labels_from_vision(pdf_bytes: bytes, page_index: int = 0, *,
                       rows: int = 4, cols: int = 4, dpi: int = 400,
                       overlap: float = 0.04) -> List[Dict[str, Any]]:
    """Tiled OCR returning labels in PAGE POINTS."""
    from providers.vision import get_vision_provider
    vp = get_vision_provider("electrical")
    W, H = page_size(pdf_bytes, page_index)
    out: List[Dict[str, Any]] = []
    for r in range(rows):
        for c in range(cols):
            bx = [max(0.0, c / cols - overlap), max(0.0, r / rows - overlap),
                  min(1.0, (c + 1) / cols + overlap),
                  min(1.0, (r + 1) / rows + overlap)]
            try:
                png = _crop_png(pdf_bytes, page_index, bx, dpi)
                res = vp.extract(png, "image/png", _OCR_PROMPT, _OCR_TOOL,
                                 max_tokens=8192) or {}
            except Exception:
                continue
            items = res.get("labels")
            if isinstance(items, str):      # stringified-array guard
                import json as _j
                try:
                    items = _j.loads(items)
                except Exception:
                    items = []
            for lb in items or []:
                if not isinstance(lb, dict):
                    continue
                b = lb.get("bbox")
                t = (lb.get("text") or "").strip()
                if not t or not b or len(b) != 4:
                    continue
                # crop-normalized -> page points
                cw = (bx[2] - bx[0]) * W
                ch = (bx[3] - bx[1]) * H
                ox = bx[0] * W
                oy = bx[1] * H
                out.append({"text": t,
                            "bbox": [ox + b[0] * cw, oy + b[1] * ch,
                                     ox + b[2] * cw, oy + b[3] * ch],
                            "source": "vision"})
    return _dedupe(out)


def _dedupe(labels: List[Dict[str, Any]], tol: float = 3.0) -> List[Dict[str, Any]]:
    """Overlapping tiles repeat labels — keep one per (text, position)."""
    seen: Dict[Tuple[str, int, int], Dict[str, Any]] = {}
    for lb in labels:
        b = lb["bbox"]
        key = (lb["text"].lower(),
               int((b[0] + b[2]) / 2 / tol), int((b[1] + b[3]) / 2 / tol))
        seen.setdefault(key, lb)
    return list(seen.values())


def get_labels(pdf_bytes: bytes, page_index: int = 0,
               **kw) -> List[Dict[str, Any]]:
    """Text layer when present, else tiled vision OCR."""
    lbs = labels_from_text_layer(pdf_bytes, page_index)
    if len(lbs) >= 25:          # a real text layer, not a stray title
        return lbs
    return labels_from_vision(pdf_bytes, page_index, **kw)
