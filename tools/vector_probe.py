"""
VECTOR PROBE — $0 structural triage for drawing PDFs + proof-of-concept
netlist overlay. Part of the vector-first audit (docs/AUDIT_vector_first_
protocol_20260726.md).

Answers two questions per PDF, without any API call:
  1. Is each page a pure VECTOR plot (A1: geometry-first path applies) or a
     RASTER scan/export (A2: stays on the vision-tiling path)?
  2. For a vector page: what does the free geometry give us? (wire segments,
     glyph-stroke count, label clusters, connected nets) — optionally rendering
     a colored net-trace overlay PNG the engineer can eyeball.

Usage:
  python tools/vector_probe.py <file.pdf>                    # per-page triage
  python tools/vector_probe.py <file.pdf> --overlay 13       # + net overlay PNG
  python tools/vector_probe.py <dir>                         # triage every PDF

Dependencies: pymupdf, pillow (both local, offline).
"""
from __future__ import annotations

import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import fitz  # PyMuPDF

WIRE_MIN_PT = 4.0       # segment length threshold: >= is wire/frame, < is glyph stroke
JOIN_TOL_PT = 1.2       # endpoint / point-on-segment join tolerance
NET_MIN_TOTAL_PT = 30.0 # ignore fragments below this total length
VECTOR_MIN_PATHS = 100  # fewer paths than this + images present => raster page


def probe_page(page: fitz.Page) -> Dict[str, Any]:
    """Classify one page A1 (vector plot) / A2 (raster) and count its geometry."""
    n_images = len(page.get_images())
    drawings = page.get_drawings()
    wires = 0
    glyphs = 0
    for d in drawings:
        for it in d["items"]:
            if it[0] == "l":
                a, b = it[1], it[2]
                if math.hypot(b.x - a.x, b.y - a.y) >= WIRE_MIN_PT:
                    wires += 1
                else:
                    glyphs += 1
            elif it[0] == "c":
                glyphs += 1
    text_chars = len(page.get_text().strip())
    is_vector = len(drawings) >= VECTOR_MIN_PATHS and n_images == 0
    return {
        "class": "A1_vector" if is_vector else "A2_raster",
        "images": n_images,
        "paths": len(drawings),
        "wire_segments": wires,
        "glyph_strokes": glyphs,
        "text_chars": text_chars,
    }


def _segments(page: fitz.Page) -> List[Tuple[float, float, float, float]]:
    """Wire segments in RENDER space. get_drawings() returns coordinates in the
    UNROTATED page space while get_pixmap() renders the rotated view — on a
    /Rotate page (p13 of the GM book is Rotate 270) that mismatch put every
    overlay line ~90° off. THE ENGINEER CAUGHT THIS (2026-07-26, ink-hit rate
    was 6.4%); rotation_matrix maps to render space (measured 96.2% after)."""
    R = page.rotation_matrix
    segs = []
    for d in page.get_drawings():
        for it in d["items"]:
            if it[0] == "l":
                a, b = it[1], it[2]
                if math.hypot(b.x - a.x, b.y - a.y) >= WIRE_MIN_PT:
                    A = fitz.Point(a.x, a.y) * R
                    B = fitz.Point(b.x, b.y) * R
                    segs.append((A.x, A.y, B.x, B.y))
    return segs


def ink_hit_rate(page: fitz.Page, segs: List[Tuple[float, float, float, float]],
                 zoom: float = 2.2, sample_n: int = 300) -> float:
    """MANDATORY self-check before any overlay is shown to a human: fraction of
    points sampled along the extracted segments that land on rendered ink.
    An eyeball is not a gate — this number is. <0.90 means a transform bug."""
    import random
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csGRAY)
    w, h, buf = pix.width, pix.height, pix.samples

    def dark(x: float, y: float) -> bool:
        xi, yi = int(x), int(y)
        return 0 <= xi < w and 0 <= yi < h and buf[yi * w + xi] < 128

    random.seed(0)
    hits = tot = 0
    for (x0, y0, x1, y1) in random.sample(segs, min(sample_n, len(segs))):
        for s in range(1, 10):
            t = s / 10
            X, Y = (x0 + t * (x1 - x0)) * zoom, (y0 + t * (y1 - y0)) * zoom
            if any(dark(X + dx, Y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                hits += 1
            tot += 1
    return hits / max(1, tot)


def _pt_seg_dist(px, py, x0, y0, x1, y1) -> float:
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def build_nets(segs: List[Tuple[float, float, float, float]]) -> List[List[int]]:
    """Union-find over segments: endpoint-touch + T-joint (endpoint-on-segment)
    join; plain crossings do NOT join (no shared endpoint) — the correct default
    for schematic wires. Returns nets above the fragment floor, largest first."""
    n = len(segs)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    cell = 8.0
    grid: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for i, (x0, y0, x1, y1) in enumerate(segs):
        steps = max(1, int(math.hypot(x1 - x0, y1 - y0) / cell))
        for s in range(steps + 1):
            t = s / steps
            grid[(int((x0 + t * (x1 - x0)) / cell),
                  int((y0 + t * (y1 - y0)) / cell))].append(i)
    for i, (x0, y0, x1, y1) in enumerate(segs):
        cand = set()
        for (ex, ey) in ((x0, y0), (x1, y1)):
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    cand.update(grid.get((int(ex / cell) + dx,
                                          int(ey / cell) + dy), []))
        for j in cand:
            if j == i:
                continue
            if (_pt_seg_dist(x0, y0, *segs[j]) <= JOIN_TOL_PT
                    or _pt_seg_dist(x1, y1, *segs[j]) <= JOIN_TOL_PT):
                union(i, j)
    comp: Dict[int, List[int]] = defaultdict(list)
    for i in range(n):
        comp[find(i)].append(i)
    nets = [
        v for v in comp.values()
        if sum(math.hypot(segs[i][2] - segs[i][0], segs[i][3] - segs[i][1])
               for i in v) > NET_MIN_TOTAL_PT
    ]
    nets.sort(key=len, reverse=True)
    return nets


def overlay(pdf_path: Path, page_index: int, out_png: Path, zoom: float = 2.2) -> str:
    """Render the page light-grey with each traced net drawn in its own color —
    the engineer-eyeball artifact for the Phase-1 gate."""
    from PIL import Image, ImageDraw

    doc = fitz.open(pdf_path)
    page = doc[page_index]
    segs = _segments(page)
    nets = build_nets(segs)
    rate = ink_hit_rate(page, segs, zoom=zoom)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img = (Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
           .convert("L").point(lambda v: 150 + v * 105 // 255).convert("RGB"))
    dr = ImageDraw.Draw(img)
    palette = [(220, 30, 30), (20, 110, 220), (20, 160, 60), (200, 120, 0),
               (150, 30, 180), (0, 150, 150), (180, 0, 90), (120, 120, 0),
               (0, 60, 180), (230, 80, 160)]
    for k, net in enumerate(nets[:60]):
        col = palette[k % len(palette)]
        for i in net:
            x0, y0, x1, y1 = segs[i]
            dr.line([x0 * zoom, y0 * zoom, x1 * zoom, y1 * zoom],
                    fill=col, width=2)
    verdict = "OK" if rate >= 0.90 else "FAILED — DO NOT TRUST THIS OVERLAY"
    dr.text((20, 20), f"ALIGNMENT SELF-CHECK: {rate:.1%} of drawn samples on "
                      f"sheet ink [{verdict}] (rotation={page.rotation})",
            fill=(180, 0, 0))
    img.save(out_png)
    return (f"p{page_index}: {len(segs)} wire segments -> {len(nets)} nets "
            f"(top sizes {[len(v) for v in nets[:6]]}) ink-hit={rate:.1%} "
            f"[{verdict}] -> {out_png}")


def probe_pdf(pdf_path: Path) -> None:
    doc = fitz.open(pdf_path)
    classes = Counter()
    print(f"\n== {pdf_path.name} ({doc.page_count}pp) ==")
    for i in range(doc.page_count):
        r = probe_page(doc[i])
        classes[r["class"]] += 1
        if doc.page_count <= 12 or r["class"] == "A2_raster":
            print(f"  p{i}: {r['class']}  paths={r['paths']} "
                  f"wires={r['wire_segments']} glyphs={r['glyph_strokes']} "
                  f"images={r['images']} text={r['text_chars']}")
    print(f"  SUMMARY: {dict(classes)}")


def main(argv: List[str]) -> None:
    if not argv:
        print(__doc__)
        return
    target = Path(argv[0])
    if "--overlay" in argv:
        idx = int(argv[argv.index("--overlay") + 1])
        out = target.with_suffix(f".net_overlay_p{idx}.png")
        print(overlay(target, idx, out))
        return
    if target.is_dir():
        for pdf in sorted(target.glob("**/*.pdf")):
            probe_pdf(pdf)
    else:
        probe_pdf(target)


if __name__ == "__main__":
    main(sys.argv[1:])
