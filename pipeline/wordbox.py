"""
VECTOR WORD-BOX EXTRACTION — every text string on a vector PDF page with its
exact position, deterministically, for FREE (no vision call).

The economics fix (Fable's gap #1): we were paying vision to re-read text that
sits in the PDF as vectors. On a vector sheet (yard drawings, OEM Class-B sheets,
BOM tables) this returns every label + its bounding box in milliseconds, so:
  - BOM ↔ diagram joins become geometry lookups, not model guesses.
  - callout positions are exact (no locate-recall lottery).
  - vision is reserved for what actually needs it: symbols and line-work.

Deterministic + gold-blind (no vessel token). Returns coordinates normalized to
[0,1] to match the bbox convention used everywhere else in the pipeline.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def has_text_layer(pdf_bytes: bytes, page_index: int = 0) -> bool:
    """True if the page carries a machine-readable text layer worth extracting.
    Image-only scans (GM, BAE) return False — those still need vision."""
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if page_index >= doc.page_count:
            return False
        return len(doc[page_index].get_text("text").strip()) >= 20
    finally:
        doc.close()


def word_boxes(pdf_bytes: bytes, page_index: int = 0) -> List[Dict[str, Any]]:
    """
    Every word on the page as {text, bbox:[x0,y0,x1,y1] normalized 0..1,
    block, line}. Empty list on an image-only page (no text layer).
    """
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if page_index >= doc.page_count:
            return []
        page = doc[page_index]
        w, h = page.rect.width, page.rect.height
        if not w or not h:
            return []
        out: List[Dict[str, Any]] = []
        # words(): (x0, y0, x1, y1, "text", block_no, line_no, word_no)
        for x0, y0, x1, y1, text, block, line, _word in page.get_text("words"):
            if not text.strip():
                continue
            out.append({
                "text": text,
                "bbox": [round(x0 / w, 5), round(y0 / h, 5),
                         round(x1 / w, 5), round(y1 / h, 5)],
                "block": block, "line": line,
            })
        return out
    finally:
        doc.close()


def text_in_bbox(pdf_bytes: bytes, page_index: int, bbox: List[float],
                 *, pad: float = 0.0) -> str:
    """All words whose center falls inside the normalized bbox, in reading order
    — the geometry primitive for 'read the label at this callout / in this table
    cell'. bbox is [x0,y0,x1,y1] in 0..1."""
    x0, y0, x1, y1 = bbox
    x0 -= pad; y0 -= pad; x1 += pad; y1 += pad
    hits = []
    for wbx in word_boxes(pdf_bytes, page_index):
        bx0, by0, bx1, by1 = wbx["bbox"]
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            hits.append(wbx)
    hits.sort(key=lambda wbx: (round(wbx["bbox"][1], 2), wbx["bbox"][0]))
    return " ".join(h["text"] for h in hits)


def group_lines(words: List[Dict[str, Any]], *, y_tol: float = 0.004) -> List[Dict[str, Any]]:
    """Merge word boxes into text LINES (label reconstruction) by shared block+line
    then y-proximity. Returns [{text, bbox, words:[…]}] left-to-right, top-to-bottom."""
    from collections import defaultdict
    groups: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for wbx in words:
        groups[(wbx["block"], wbx["line"])].append(wbx)
    lines = []
    for ws in groups.values():
        ws.sort(key=lambda w: w["bbox"][0])
        x0 = min(w["bbox"][0] for w in ws); y0 = min(w["bbox"][1] for w in ws)
        x1 = max(w["bbox"][2] for w in ws); y1 = max(w["bbox"][3] for w in ws)
        lines.append({"text": " ".join(w["text"] for w in ws),
                      "bbox": [x0, y0, x1, y1], "words": ws})
    lines.sort(key=lambda l: (round(l["bbox"][1], 2), l["bbox"][0]))
    return lines
