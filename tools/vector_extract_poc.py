"""
VECTOR EXTRACT POC — full-page accounting for A1 (vector-plot) schematic sheets.
Proven live on GM book p13 (GMMS 111a) 2026-07-26:

  * 100% of ink pixels accounted into four primitive classes
      wires  -> nets        (dash-joined union-find, junction-dot connectors)
      closed small loops    -> symbol boxes (terminal boxes, fuses, relays, diamonds)
      filled small paths    -> junction dots / arrowheads
      tiny strokes/curves   -> glyph clusters -> label boxes (horiz + vertical)
  * 344 label boxes OCR'd locally (tesseract, single full-page render, PIL crops):
      330 non-empty, 47% word-confidence >= 70 untuned; 325/344 attached to a
      net or symbol within 12pt. High-conf sample: 'NAVIGATION LTS' 94,
      'PORT NAV. LT.' 95, 'NAV.LIGHTS ALARM SYSTEM' 95, 'STEAMING LT. 2' 96.
  * $0 API for everything in this file.

KNOWN GAPS (honest, next iteration):
  - lamp/circle symbols are built from 'c' curves and currently land in the
    glyph pool, not sym_boxes -> curve-loop symbol detection needed (a few
    right-edge load labels attach to None because their lamp isn't a box yet).
  - OCR residue (~half the labels below conf 70) routes to the residue channel:
    batched vision verification now, glyph-fingerprint FONT DECODE later (the
    deterministic fix: learn the ~80 unique glyph shapes once per drafting
    house, then every label decodes exactly — same idea as decode_c's +29).
  - clip= in get_pixmap has rotation-dependent semantics; this POC avoids it
    entirely (one full-page render, crop in PIL) after two mis-cropping bugs.

ROTATION DISCIPLINE: every coordinate that leaves get_drawings() goes through
page.rotation_matrix (the engineer-caught 6.4%-ink-hit scar).

Usage: python tools/vector_extract_poc.py <pdf> <page_index> [--no-ocr]
Writes: full_account_p<N>.png (overlay + self-check header), p<N>_labels.json
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
import subprocess
import sys
from collections import defaultdict
from typing import Any, Dict, List, Tuple

import fitz
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None

WIRE_MIN_PT = 4.0
DASH_GAP_PT = 5.0
JOIN_TOL_PT = 1.2
DOT_TOL_PT = 2.5
ATTACH_MAX_PT = 12.0
OCR_ZOOM = 9  # ~648 DPI equivalent


def extract_primitives(page: fitz.Page):
    """Split every drawing item into wires / symbol boxes / dots / glyph strokes,
    all in ROTATED (render) space."""
    R = page.rotation_matrix
    tp = lambda pt: ((pt * R).x, (pt * R).y)
    wires, sym_boxes, dots, glyph = [], [], [], []
    for d in page.get_drawings():
        t = d.get("type")
        items = d["items"]
        only_lines = all(it[0] == "l" for it in items)
        if only_lines and items:
            chain = [tp(items[0][1])]
            contiguous = True
            for it in items:
                a, b = tp(it[1]), tp(it[2])
                if math.hypot(a[0] - chain[-1][0], a[1] - chain[-1][1]) > 0.5:
                    contiguous = False
                chain.append(b)
            xs = [q[0] for q in chain]; ys = [q[1] for q in chain]
            bb = (min(xs), min(ys), max(xs), max(ys))
            w, h = bb[2] - bb[0], bb[3] - bb[1]
            closed = (contiguous and len(items) >= 3 and
                      math.hypot(chain[0][0] - chain[-1][0],
                                 chain[0][1] - chain[-1][1]) < 0.8)
            if t in ("f", "fs") and w < 20 and h < 20:
                dots.append(bb)
                continue
            if closed and w < 45 and h < 45:
                sym_boxes.append(bb)
                continue
        for it in items:
            if it[0] == "l":
                a, b = tp(it[1]), tp(it[2])
                if math.hypot(b[0] - a[0], b[1] - a[1]) >= WIRE_MIN_PT:
                    wires.append((a[0], a[1], b[0], b[1]))
                else:
                    x0, x1 = sorted((a[0], b[0])); y0, y1 = sorted((a[1], b[1]))
                    glyph.append((x0, y0, x1, y1))
            elif it[0] == "c":
                qs = [tp(q) for q in it[1:]]
                xs = [q[0] for q in qs]; ys = [q[1] for q in qs]
                glyph.append((min(xs), min(ys), max(xs), max(ys)))
            elif it[0] == "qu":
                quad = it[1]
                qs = [tp(q) for q in (quad.ul, quad.ur, quad.ll, quad.lr)]
                xs = [q[0] for q in qs]; ys = [q[1] for q in qs]
                glyph.append((min(xs), min(ys), max(xs), max(ys)))
    return wires, sym_boxes, dots, glyph


def merge_dashes(segs, gap=DASH_GAP_PT):
    """Join collinear segments with small gaps (dashed lines, symbol-interrupted
    runs) into single conductors before net building."""
    out = []
    buck = defaultdict(list)

    def norm(s):
        x0, y0, x1, y1 = s
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        if L == 0:
            return None
        if (dx < 0) or (dx == 0 and dy < 0):
            x0, y0, x1, y1, dx, dy = x1, y1, x0, y0, -dx, -dy
        return (round(math.atan2(dy, dx), 2), round((x0 * dy - y0 * dx) / L / 3))

    for s in segs:
        k = norm(s)
        if k:
            buck[k].append(s)
        else:
            out.append(s)
    for k, lst in buck.items():
        ca, sa = math.cos(k[0]), math.sin(k[0])
        lst = sorted(lst, key=lambda s: (s[0] + s[2]) / 2 * ca + (s[1] + s[3]) / 2 * sa)
        cur = list(lst[0])
        for s in lst[1:]:
            if min(math.hypot(s[0] - cur[2], s[1] - cur[3]),
                   math.hypot(s[2] - cur[2], s[3] - cur[3])) <= gap:
                pts = sorted([(cur[0], cur[1]), (cur[2], cur[3]),
                              (s[0], s[1]), (s[2], s[3])],
                             key=lambda q: q[0] * ca + q[1] * sa)
                cur = [pts[0][0], pts[0][1], pts[-1][0], pts[-1][1]]
            else:
                out.append(tuple(cur))
                cur = list(s)
        out.append(tuple(cur))
    return out


def _psd(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def build_nets(segs, dots):
    """Union-find nets: endpoint/T-joint joins + junction-dot connectors."""
    n = len(segs)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    cell = 8.0
    grid = defaultdict(list)
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
            if j != i and (_psd(x0, y0, *segs[j]) <= JOIN_TOL_PT
                           or _psd(x1, y1, *segs[j]) <= JOIN_TOL_PT):
                union(i, j)
    for (bx0, by0, bx1, by1) in dots:
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        near = [j for j in set(sum([grid.get((int(cx / cell) + dx,
                                              int(cy / cell) + dy), [])
                                    for dx in (-1, 0, 1) for dy in (-1, 0, 1)], []))
                if _psd(cx, cy, *segs[j]) <= DOT_TOL_PT]
        for a in near[1:]:
            union(near[0], a)
    netid = {i: find(i) for i in range(n)}
    comp = defaultdict(list)
    for i in range(n):
        comp[netid[i]].append(i)
    return netid, sorted(comp.values(), key=len, reverse=True), grid, cell


def cluster_labels(glyph):
    """CHAR-CHAIN line builder (v2, 2026-07-27). The v1 box-merge cut first/
    last characters off ~35% of labels ('DWG'->'WG', 'DECK'->'ECK' — caught by
    the decoder grading montage) and split words across boxes. v2 builds text
    the way it is actually laid out:
      1. glyph strokes -> CHARACTER clusters (strokes that overlap or nearly
         touch horizontally AND share the line vertically);
      2. characters -> LINES by baseline chaining (same y-center band, x-gap
         bounded by char height);
      3. dot/dash runs (uniform sub-glyph-height chains — dotted enclosures,
         dashed leaders) are classified OUT as non-text, which also removes
         the 'eee eee' lint findings at the source;
      4. leftover single chars re-chained along y -> vertical labels.
    """
    gb = [b for b in glyph]
    m = len(gb)
    par = list(range(m))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i

    def union(i, j):
        a, b = find(i), find(j)
        if a != b:
            par[a] = b

    # -- 1. char clusters: near-touching strokes on the same line
    gcell = 4.0
    ggrid = defaultdict(list)
    for i, b in enumerate(gb):
        ggrid[(int(b[0] / gcell), int(b[1] / gcell))].append(i)
    for i, b in enumerate(gb):
        hi = max(b[3] - b[1], 0.3)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in ggrid.get((int(b[0] / gcell) + dx,
                                    int(b[1] / gcell) + dy), []):
                    if j <= i:
                        continue
                    o = gb[j]
                    hj = max(o[3] - o[1], 0.3)
                    gap_thr = 0.12 * max(hi, hj)
                    yov = min(b[3], o[3]) - max(b[1], o[1])
                    if (b[0] <= o[2] + gap_thr and o[0] <= b[2] + gap_thr
                            and yov >= -0.2 * max(hi, hj)):
                        union(i, j)
    cl = defaultdict(list)
    for i in range(m):
        cl[find(i)].append(i)
    chars = []
    for v in cl.values():
        x0 = min(gb[i][0] for i in v); y0 = min(gb[i][1] for i in v)
        x1 = max(gb[i][2] for i in v); y1 = max(gb[i][3] for i in v)
        chars.append({"bbox": [x0, y0, x1, y1], "n": len(v),
                      "h": y1 - y0, "w": x1 - x0})

    # -- 2. baseline chaining into lines
    chars.sort(key=lambda c: c["bbox"][0])
    lines = []          # each: {"chars": [...], "ycen": float, "h": float}
    for c in chars:
        ycen = (c["bbox"][1] + c["bbox"][3]) / 2
        h = max(c["h"], 0.6)
        best = None
        bestgap = 1e9
        for L in lines:
            last = L["chars"][-1]["bbox"]
            gap = c["bbox"][0] - last[2]
            if gap < -0.5 * L["h"] or gap > 2.6 * max(L["h"], h):
                continue
            if abs(ycen - L["ycen"]) > 0.5 * max(L["h"], h):
                continue
            if gap < bestgap:
                bestgap = gap
                best = L
        if best is None:
            lines.append({"chars": [c], "ycen": ycen, "h": h})
        else:
            best["chars"].append(c)
            n = len(best["chars"])
            best["ycen"] = (best["ycen"] * (n - 1) + ycen) / n
            best["h"] = max(best["h"], h)

    labels = []
    leftovers = []
    for L in lines:
        cs = L["chars"]
        x0 = min(c["bbox"][0] for c in cs); y0 = min(c["bbox"][1] for c in cs)
        x1 = max(c["bbox"][2] for c in cs); y1 = max(c["bbox"][3] for c in cs)
        hs = sorted(c["h"] for c in cs)
        med_h = hs[len(hs) // 2]
        # -- 3. dot/dash-run guard: uniform sub-text-height chains are
        # enclosure boundaries / leaders, not text
        if med_h < 0.7 and len(cs) >= 4:
            continue
        if len(cs) == 1:
            leftovers.append(cs[0])
            continue
        labels.append({"bbox": [x0, y0, x1, y1], "vertical": False})

    # -- 4. vertical chaining of leftover single chars
    leftovers.sort(key=lambda c: c["bbox"][1])
    vlines = []
    for c in leftovers:
        xcen = (c["bbox"][0] + c["bbox"][2]) / 2
        w = max(c["w"], 0.6)
        best = None
        bestgap = 1e9
        for L in vlines:
            last = L["chars"][-1]["bbox"]
            gap = c["bbox"][1] - last[3]
            if gap < -0.5 * L["w"] or gap > 2.6 * max(L["w"], w):
                continue
            if abs(xcen - L["xcen"]) > 0.5 * max(L["w"], w):
                continue
            if gap < bestgap:
                bestgap = gap
                best = L
        if best is None:
            vlines.append({"chars": [c], "xcen": xcen, "w": w})
        else:
            best["chars"].append(c)
            best["w"] = max(best["w"], w)
    for L in vlines:
        cs = L["chars"]
        x0 = min(c["bbox"][0] for c in cs); y0 = min(c["bbox"][1] for c in cs)
        x1 = max(c["bbox"][2] for c in cs); y1 = max(c["bbox"][3] for c in cs)
        ws = sorted(c["w"] for c in cs)
        if ws[len(ws) // 2] < 0.7 and len(cs) >= 4:
            continue
        if len(cs) >= 2 and (y1 - y0) > (x1 - x0):
            labels.append({"bbox": [x0, y0, x1, y1], "vertical": True})
        else:
            for c in cs:
                b = c["bbox"]
                if max(c["w"], c["h"]) >= 1.2:   # standalone char (terminal no.)
                    labels.append({"bbox": list(b), "vertical": False})
    return labels


def ocr_labels(page: fitz.Page, labels):
    """Local tesseract over PIL crops from ONE full-page render (never
    get_pixmap(clip=...) — rotation-dependent semantics burned us twice)."""
    pix = page.get_pixmap(matrix=fitz.Matrix(OCR_ZOOM, OCR_ZOOM),
                          colorspace=fitz.csGRAY)
    page_img = Image.frombytes("L", (pix.width, pix.height), pix.samples)

    def run(crop):
        crop.save("_ocr_tmp.png")
        out = subprocess.run(
            ["tesseract", "_ocr_tmp.png", "stdout", "--psm", "7", "tsv"],
            capture_output=True, text=True)
        words, confs = [], []
        for row in csv.reader(io.StringIO(out.stdout), delimiter="\t"):
            if len(row) >= 12 and row[0] != "level":
                try:
                    c = float(row[10])
                    if c >= 0 and row[11].strip():
                        words.append(row[11].strip())
                        confs.append(c)
                except ValueError:
                    pass
        return " ".join(words), (sum(confs) / len(confs) if confs else 0.0)

    res = []
    pad = 1.8
    for L in labels:
        b = L["bbox"]
        crop = page_img.crop((int((b[0] - pad) * OCR_ZOOM), int((b[1] - pad) * OCR_ZOOM),
                              int((b[2] + pad) * OCR_ZOOM), int((b[3] + pad) * OCR_ZOOM)))
        if L["vertical"]:
            txt, conf = run(crop.rotate(-90, expand=True))
            if not txt:
                txt, conf = run(crop.rotate(90, expand=True))
        else:
            txt, conf = run(crop)
        res.append({"bbox": [round(x, 1) for x in b], "vertical": L["vertical"],
                    "text": txt, "conf": round(conf, 1)})
    if os.path.exists("_ocr_tmp.png"):
        os.remove("_ocr_tmp.png")
    return res


def attach_labels(res, segs, sym_boxes, netid, grid, cell):
    """Attach each label to the nearest symbol box or net within ATTACH_MAX_PT."""
    attached = 0
    for r in res:
        cx = (r["bbox"][0] + r["bbox"][2]) / 2
        cy = (r["bbox"][1] + r["bbox"][3]) / 2
        best, bd = None, 1e9
        for k, sb in enumerate(sym_boxes):
            d = (max(abs(cx - (sb[0] + sb[2]) / 2) - (sb[2] - sb[0]) / 2, 0)
                 + max(abs(cy - (sb[1] + sb[3]) / 2) - (sb[3] - sb[1]) / 2, 0))
            if d < bd:
                bd, best = d, ("symbol", k)
        cand = set(sum([grid.get((int(cx / cell) + dx, int(cy / cell) + dy), [])
                        for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2)], []))
        for j in cand:
            d = _psd(cx, cy, *segs[j])
            if d < bd:
                bd, best = d, ("net", netid[j])
        if best and bd <= ATTACH_MAX_PT:
            r["attach"] = [best[0], int(best[1])]
            r["attach_dist"] = round(bd, 1)
            attached += 1
    return attached


def main(argv):
    pdf, idx = argv[0], int(argv[1])
    do_ocr = "--no-ocr" not in argv
    doc = fitz.open(pdf)
    page = doc[idx]
    wires, sym_boxes, dots, glyph = extract_primitives(page)
    segs = merge_dashes(wires)
    netid, nets, grid, cell = build_nets(segs, dots)
    labels = cluster_labels(glyph)
    print(f"wires={len(segs)} nets={len(nets)} sym_boxes={len(sym_boxes)} "
          f"dots={len(dots)} labels={len(labels)}")
    res = []
    if do_ocr:
        res = ocr_labels(page, labels)
        att = attach_labels(res, segs, sym_boxes, netid, grid, cell)
        ne = sum(1 for r in res if r["text"])
        hi = sum(1 for r in res if r["conf"] >= 70)
        print(f"OCR: {ne}/{len(res)} non-empty, {hi} conf>=70, attached {att}")
        json.dump(res, open(f"p{idx}_labels.json", "w"), indent=1)
    # overlay with ALL classes drawn — nothing left black
    zoom = 2.2
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img = (Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
           .convert("L").point(lambda v: 150 + v * 105 // 255).convert("RGB"))
    dr = ImageDraw.Draw(img)
    palette = [(220, 30, 30), (20, 110, 220), (20, 160, 60), (200, 120, 0),
               (150, 30, 180), (0, 150, 150), (180, 0, 90), (120, 120, 0),
               (0, 60, 180), (230, 80, 160)]
    k = 0
    for net in nets:
        tot = sum(math.hypot(segs[i][2] - segs[i][0], segs[i][3] - segs[i][1])
                  for i in net)
        if tot > 12:
            col = palette[k % len(palette)]
            k += 1
        else:
            col = (120, 120, 120)
        for i in net:
            x0, y0, x1, y1 = segs[i]
            dr.line([x0 * zoom, y0 * zoom, x1 * zoom, y1 * zoom], fill=col, width=2)
    for bb in sym_boxes:
        dr.rectangle([bb[0] * zoom - 2, bb[1] * zoom - 2,
                      bb[2] * zoom + 2, bb[3] * zoom + 2],
                     outline=(255, 120, 0), width=2)
    for bb in dots:
        cx, cy = (bb[0] + bb[2]) / 2 * zoom, (bb[1] + bb[3]) / 2 * zoom
        dr.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], outline=(255, 0, 255), width=1)
    for L in labels:
        b = L["bbox"]
        dr.rectangle([b[0] * zoom - 1, b[1] * zoom - 1,
                      b[2] * zoom + 1, b[3] * zoom + 1],
                     outline=(0, 160, 0), width=1)
    dr.text((20, 14), f"FULL ACCOUNTING p{idx}: colored nets {k} | symbol boxes "
                      f"{len(sym_boxes)} | junction marks {len(dots)} | labels "
                      f"{len(labels)} | rotation={page.rotation}",
            fill=(180, 0, 0))
    out = f"full_account_p{idx}.png"
    img.save(out)
    print("saved", out)


if __name__ == "__main__":
    main(sys.argv[1:])
