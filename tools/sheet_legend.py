"""
SHEET LEGEND — read the sheet's OWN legend before typing any symbol, and let
it OVERRIDE the fleet glossary and the symbol bank.

Closes audit flag F1: the vector-first audit claimed "legends-first survives
untouched", but grepping the 8 vector tools for `legend` returned exactly one
hit — a comment. The step existed only in the raster path's caller. This is
the same failure shape as the fused-tiles arm (a mandated step living in the
caller instead of the path), so it is fixed the same way: legend reading is
called from INSIDE the typing path, and `symbol_typing.type_page_symbols`
takes the legend as an argument it cannot silently skip.

Precedence (protocol §A2):
    1. THIS SHEET'S OWN LEGEND        <-- read here, always wins
    2. confirmed symbol bank (fingerprint -> engineer type)
    3. fleet glossary shape/prefix rules
    4. <UNKNOWN>

How a legend is found, geometrically ($0, no vision):
  * a label whose text matches a legend heading (LEGEND / SYMBOLS / KEY /
    PIPE LEGEND / TEXT LEGEND / SYMBOL LEGEND / NOTES) anchors a region;
  * the region extends down/right from that heading to the sheet edge or the
    next heading, bounded by a generous box;
  * inside it, each symbol-sized shape is paired with the nearest label to
    its RIGHT (the drafting convention on these sheets: symbol left,
    meaning right) — the pairing distance is bounded, and an unpaired symbol
    is reported, never guessed.

Vessel-agnostic: only generic legend vocabulary, no Gelliceaux tokens.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz

from symbol_bank_build import _pts, path_fingerprint, _page_wires  # noqa: E402

# TRUNCATION-TOLERANT. A legend heading is often clipped by label
# segmentation — the bilge P&ID's real heading OCR'd as 'SYMBOLS LEGE', which
# an exact \bLEGEND\b regex missed entirely, silently reporting "no legend on
# a sheet that has one". Heading detection must not require a perfect read.
LEGEND_HEADING_RE = re.compile(
    r"(LEGE\w*|KEY\s+TO\s+SYMBOL\w*|SYMBOL\w*\s+KEY|ABBREVIAT\w*)",
    re.IGNORECASE)
PAIR_MAX_DX = 90.0     # pt: how far right of a symbol its meaning may sit
PAIR_MAX_DY = 6.0      # pt: vertical alignment tolerance for the pairing


def find_legend_regions(labels: List[Dict[str, Any]],
                        page_rect) -> List[Dict[str, Any]]:
    """Legend heading labels -> regions extending below them."""
    W, H = abs(page_rect.width), abs(page_rect.height)
    regions = []
    heads = [l for l in labels
             if l.get("text") and LEGEND_HEADING_RE.search(l["text"])]
    for h in heads:
        x0, y0, x1, y1 = h["bbox"]
        regions.append({
            "heading": h["text"],
            "heading_bbox": h["bbox"],
            # generous box below/right of the heading, clipped to the sheet
            "bbox": [max(0.0, x0 - 20.0), y0 - 2.0,
                     min(W, x1 + 260.0), min(H, y1 + 320.0)],
        })
    return regions


_MEANING_MIN_LETTERS = 4


def _usable_meaning(text: str) -> bool:
    """A legend meaning must look like a word, not an OCR crumb."""
    t = (text or "").strip()
    letters = sum(ch.isalpha() for ch in t)
    if letters < _MEANING_MIN_LETTERS or len(t) < 4:
        return False
    # must start with a letter (fragments often start with punctuation)
    return t[0].isalpha()


def _in(bb, region) -> bool:
    cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
    r = region["bbox"]
    return r[0] <= cx <= r[2] and r[1] <= cy <= r[3]


def read_sheet_legend(page: fitz.Page, labels: List[Dict[str, Any]]
                      ) -> Dict[str, Any]:
    """-> {regions, entries:[{fingerprint, meaning, bbox}], unpaired:[...]}.

    `entries` is the sheet's own symbol->meaning map, keyed by the SAME
    fingerprint symbol_typing looks up, so an override is a dict hit."""
    pr = page.rect * page.rotation_matrix
    regions = find_legend_regions(labels, pr)
    result: Dict[str, Any] = {"regions": [r["heading"] for r in regions],
                              "entries": [], "unpaired": []}
    if not regions:
        return result
    R = page.rotation_matrix
    # symbol-sized shapes inside a legend region (legend symbols are NOT
    # wired, so the wire-touch filter must NOT be applied here)
    cands = []
    for d in page.get_drawings():
        items = d["items"]
        all_pts = []
        for it in items:
            all_pts += [((fitz.Point(x, y) * R).x, (fitz.Point(x, y) * R).y)
                        for (x, y) in _pts(it)]
        if not all_pts:
            continue
        xs = [p[0] for p in all_pts]; ys = [p[1] for p in all_pts]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        if not (4.0 <= max(w, h) <= 60.0):
            continue
        bb = [min(xs), min(ys), max(xs), max(ys)]
        if not any(_in(bb, r) for r in regions):
            continue
        fp, _ = path_fingerprint(d, R)
        if fp:
            cands.append((fp, bb))
    # pair each legend symbol with the nearest label to its RIGHT
    legend_labels = [l for l in labels
                     if l.get("text") and any(_in(l["bbox"], r) for r in regions)
                     and not LEGEND_HEADING_RE.search(l["text"])]
    for fp, bb in cands:
        cy = (bb[1] + bb[3]) / 2
        best, bestdx = None, 1e9
        for l in legend_labels:
            lx0, ly0, lx1, ly1 = l["bbox"]
            lcy = (ly0 + ly1) / 2
            dx = lx0 - bb[2]
            if dx < -2.0 or dx > PAIR_MAX_DX:
                continue
            if abs(lcy - cy) > PAIR_MAX_DY:
                continue
            if dx < bestdx:
                bestdx, best = dx, l
        if best and _usable_meaning(best["text"]):
            result["entries"].append({"fingerprint": str(fp),
                                      "meaning": best["text"].strip(),
                                      "bbox": [round(v, 1) for v in bb],
                                      "distance": round(bestdx, 1)})
        else:
            # QUALITY GUARD: an OCR fragment ('[OL', 'rma', 'oR') is not a
            # legend meaning. A legend entry OVERRIDES the engineer-confirmed
            # bank, so a junk pair would be worse than no pair at all — it
            # would silently retype a device from garbage. Unusable pairs are
            # reported as unpaired, never promoted.
            result["unpaired"].append([round(v, 1) for v in bb])
    return result


def legend_override_map(legend: Dict[str, Any]) -> Dict[str, str]:
    """{fingerprint: meaning} — what the sheet itself says a shape means."""
    return {e["fingerprint"]: e["meaning"] for e in legend.get("entries", [])}


def main(argv):
    pdf, pno = argv[0], int(argv[1])
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from vector_extract_poc import extract_primitives, cluster_labels
    from run_book_extract import ocr_labels_batch
    doc = fitz.open(pdf)
    page = doc[pno]
    _, _, _, glyph = extract_primitives(page)
    labels = ocr_labels_batch(page, cluster_labels(glyph))
    lg = read_sheet_legend(page, labels)
    print(f"page {pno}: legend regions {lg['regions'] or 'NONE'}; "
          f"{len(lg['entries'])} symbol->meaning pairs, "
          f"{len(lg['unpaired'])} unpaired (reported, not guessed)")
    for e in lg["entries"][:20]:
        print(f"    {e['fingerprint'][:10]}  ->  {e['meaning']!r}")


if __name__ == "__main__":
    main(sys.argv[1:])
