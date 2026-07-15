"""
DETERMINISTIC SYMBOL DETECTION (Fable gap #3).

Classical CV (OpenCV) finds geometric symbols on a rendered sheet — every one,
every time, for zero API cost — so the vision model's only job becomes "read the
label inside this box I already found," which is what it is good at. This kills
the documented locate-recall lottery (the model returns different callout
coverage per pass) for shapes that are geometrically trivial.

Built now: DIAMOND detection (wire-gauge callouts — the single biggest misread
class, 1,630 annotations book-wide) + an extensible shape scaffold. Fuse-
rectangle / breaker-circle detectors slot into SHAPE_DETECTORS the same way.

Deterministic + gold-blind. bboxes returned normalized [0,1] to match the
pipeline convention. No vision, no vessel token.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List


def _render_gray(pdf_bytes: bytes, page_index: int, dpi: int):
    """Render a PDF page to an OpenCV grayscale image."""
    import io
    import numpy as np
    from PIL import Image
    from pipeline.visual_extract import rasterize_pdf_page
    png = rasterize_pdf_page(pdf_bytes, page_index, dpi=dpi)
    img = Image.open(io.BytesIO(png)).convert("L")
    return np.array(img)


def detect_diamonds(pdf_bytes: bytes, page_index: int = 0, *, dpi: int = 200,
                    min_side_px: int = 8, max_side_px: int = 90) -> List[Dict[str, Any]]:
    """
    Find diamond glyphs (rotated squares — wire-gauge callouts) on the page.
    Returns [{bbox:[x0,y0,x1,y1] normalized, center, side_px, confidence}] — one
    per diamond, ready to hand to `wordbox.text_in_bbox` (free) or a vision read
    of just that crop for the number inside. Size gates keep title-block boxes
    and large panel rectangles out.
    """
    import cv2
    import numpy as np
    gray = _render_gray(pdf_bytes, page_index, dpi)
    h, w = gray.shape
    # binarize: line-work is dark on white
    _th, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    out: List[Dict[str, Any]] = []
    for cnt in contours:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
        if len(approx) != 4:
            continue
        x, y, bw, bh = cv2.boundingRect(approx)
        side = max(bw, bh)
        if not (min_side_px <= side <= max_side_px):
            continue
        # a DIAMOND (rotated square): roughly equal w/h AND vertices near edge
        # midpoints (not corners, which would be an axis-aligned square).
        if not (0.6 <= bw / max(bh, 1) <= 1.6):
            continue
        pts = approx.reshape(-1, 2)
        cx, cy = pts[:, 0].mean(), pts[:, 1].mean()
        # diamond vertices sit near the top/bottom/left/right MIDPOINTS of the
        # bbox — i.e. each vertex is close to a bbox-edge center line.
        near_mid = 0
        for px, py in pts:
            on_vert_mid = abs(px - (x + bw / 2)) < bw * 0.25 and (abs(py - y) < bh * 0.25 or abs(py - (y + bh)) < bh * 0.25)
            on_horz_mid = abs(py - (y + bh / 2)) < bh * 0.25 and (abs(px - x) < bw * 0.25 or abs(px - (x + bw)) < bw * 0.25)
            if on_vert_mid or on_horz_mid:
                near_mid += 1
        if near_mid < 3:
            continue
        area = cv2.contourArea(approx)
        fill = area / max(bw * bh, 1)  # a diamond fills ~0.5 of its bbox
        if not (0.30 <= fill <= 0.75):
            continue
        # REJECT CIRCLES (gauges/lamps): circularity 4*pi*A/P^2 is ~1.0 for a
        # circle, ~0.79 for a diamond. A circle's approxPolyDP also yields 4
        # points, so this is the discriminator that keeps voltmeter/lamp glyphs
        # out. (Found the hard way: the first pass caught a 'V' gauge.)
        circ = 4 * np.pi * cv2.contourArea(cnt) / max(cv2.arcLength(cnt, True) ** 2, 1)
        if circ > 0.82:
            continue
        out.append({
            "shape": "diamond",
            "bbox": [round(x / w, 5), round(y / h, 5),
                     round((x + bw) / w, 5), round((y + bh) / h, 5)],
            "center": [round(cx / w, 5), round(cy / h, 5)],
            "side_px": int(side),
            "confidence": round(min(1.0, near_mid / 4 * fill / 0.5), 2),
        })
    # dedupe near-identical detections (overlapping contours of one glyph)
    out.sort(key=lambda d: (-d["confidence"], d["bbox"][0]))
    kept: List[Dict[str, Any]] = []
    for d in out:
        cx, cy = d["center"]
        if any(abs(cx - k["center"][0]) < 0.01 and abs(cy - k["center"][1]) < 0.01 for k in kept):
            continue
        kept.append(d)
    return kept


import re as _re
_NUMERIC = _re.compile(r"^\d{1,3}([.,]\d)?$")


def confirm_wire_gauge_diamonds(detections: List[Dict[str, Any]], pdf_bytes: bytes,
                                page_index: int) -> Dict[str, List[Dict[str, Any]]]:
    """
    Separate true wire-gauge diamonds from gauge/lamp false-positives by reading
    what's INSIDE each detected diamond via word-boxes (Tool 1, free) — a
    wire-gauge diamond holds a NUMBER (4, 16, 120); a gauge holds a LETTER
    (V, Hz, A). This closes the loop deterministically on VECTOR sheets.

    Returns {confirmed:[…+gauge_mm2], rejected_nonnumeric:[…], no_text:[…]}.
    On an IMAGE-only sheet (GM/BAE, no text layer) everything lands in `no_text`
    — there the detector still gives vision the exact WHERE (no locate lottery)
    and the same number-vs-letter check filters gauges at the vision-read step.
    """
    from pipeline import wordbox
    has_text = wordbox.has_text_layer(pdf_bytes, page_index)
    confirmed, rejected, no_text = [], [], []
    for d in detections:
        if not has_text:
            no_text.append(d)
            continue
        inside = wordbox.text_in_bbox(pdf_bytes, page_index, d["bbox"], pad=0.002).strip()
        if not inside:
            no_text.append(d)
        elif _NUMERIC.match(inside.replace(" ", "")):
            confirmed.append({**d, "gauge_mm2": inside})
        else:
            rejected.append({**d, "inside_text": inside})
    return {"confirmed": confirmed, "rejected_nonnumeric": rejected, "no_text": no_text}


# Extensible registry — fuse-rectangle / breaker-circle detectors slot in here
# with the same signature and normalized-bbox output.
SHAPE_DETECTORS: Dict[str, Callable[..., List[Dict[str, Any]]]] = {
    "diamond": detect_diamonds,
}


def detect(pdf_bytes: bytes, page_index: int = 0, *, shapes=("diamond",),
           dpi: int = 200) -> Dict[str, List[Dict[str, Any]]]:
    """Run the requested shape detectors on a page; returns {shape: [dets]}."""
    return {s: SHAPE_DETECTORS[s](pdf_bytes, page_index, dpi=dpi)
            for s in shapes if s in SHAPE_DETECTORS}
