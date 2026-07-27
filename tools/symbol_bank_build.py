"""
SYMBOL BANK BUILDER — cluster every repeated symbol shape across a book and
render a CONTACT SHEET for the engineer's one-sitting red-pen.

The per-drafting-house leverage move: a breaker symbol is the identical vector
path sequence on every sheet GM ever drew. Classify the SHAPE once and every
instance inherits the type — the engineer corrects ~dozens of rows once per
house instead of thousands of instances per book. The confirmed bank becomes
`data/state/symbol_bank_<house>.json`, a durable fleet asset.

Two symbol sources (matching vector_extract_poc's primitive split):
  * closed-loop stroke paths (terminal boxes, fuse bodies, diamonds, relays)
  * curve-built glyph clusters ABOVE text height (lamp circles, twisted pairs)
Each instance is fingerprinted by its normalized path geometry (rotation kept
— a ground symbol rotated 90° reads differently); identical fingerprints
cluster; each cluster gets one contact-sheet cell: rendered example (with a
little surrounding context), instance count, page spread.

    python tools/symbol_bank_build.py <book.pdf> <out_dir>

Outputs: <out_dir>/symbol_bank_DRAFT.json  (fingerprint -> instances, unlabeled)
         <out_dir>/symbol_contact_sheet_<n>.png (engineer red-pens these)
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None

CELL = 150          # contact-sheet cell size px
CTX_PAD_PT = 9.0    # context around the symbol in the render
MIN_INSTANCES = 3   # clusters below this go to a residue list, not the sheet


def _pts(it):
    out = []
    for q in it[1:]:
        if hasattr(q, "x"):
            out.append((q.x, q.y))
        elif hasattr(q, "x0"):
            out += [(q.x0, q.y0), (q.x1, q.y1)]
        elif hasattr(q, "ul"):
            out += [(q.ul.x, q.ul.y), (q.lr.x, q.lr.y)]
    return out


def path_fingerprint(d, R):
    """Normalized shape signature of one drawing path (rotation-corrected to
    render space, translation-invariant, 0.1pt quantized)."""
    sig = []
    origin = None
    for it in d["items"]:
        pts = [( (fitz.Point(x, y) * R).x, (fitz.Point(x, y) * R).y)
               for (x, y) in _pts(it)]
        if not pts:
            continue
        if origin is None:
            origin = pts[0]
        sig.append((it[0],) + tuple(
            (round(x - origin[0], 1), round(y - origin[1], 1)) for (x, y) in pts))
    return hash(tuple(sig)) if sig else None, origin


def collect_symbol_instances(doc: fitz.Document):
    """Every closed small stroke-loop + every multi-curve compact path,
    fingerprinted, across all pages."""
    instances = defaultdict(list)   # fp -> [(page, bbox)]  (symbol-sized)
    glyph_pool = defaultdict(list)  # fp -> [(page, bbox)]  (font-decode input)
    for pno in range(doc.page_count):
        page = doc[pno]
        R = page.rotation_matrix
        for d in page.get_drawings():
            items = d["items"]
            kinds = {it[0] for it in items}
            all_pts = []
            for it in items:
                all_pts += [((fitz.Point(x, y) * R).x, (fitz.Point(x, y) * R).y)
                            for (x, y) in _pts(it)]
            if not all_pts:
                continue
            xs = [p[0] for p in all_pts]; ys = [p[1] for p in all_pts]
            w, h = max(xs) - min(xs), max(ys) - min(ys)
            # SYMBOL-sized: above glyph height (text here is ~2.5-7pt), below
            # frame scale. Glyph-sized repeated shapes are NOT discarded — they
            # are the FONT-DECODE pool, collected separately below.
            if not (7.5 <= max(w, h) <= 45):
                if 1.0 <= max(w, h) < 7.5:
                    fp, _ = path_fingerprint(d, R)
                    if fp is not None:
                        glyph_pool[fp].append((pno, [min(xs), min(ys),
                                                     max(xs), max(ys)]))
                continue
            # stroke loops and curve-built marks; skip single tiny lines
            if kinds == {"l"} and len(items) < 3:
                continue
            fp, _ = path_fingerprint(d, R)
            if fp is None:
                continue
            instances[fp].append((pno, [min(xs), min(ys), max(xs), max(ys)]))
    return instances, glyph_pool


def render_cell(doc, pno, bbox, zoom=6.0):
    page = doc[pno]
    x0, y0, x1, y1 = bbox
    clip_rot = fitz.Rect(x0 - CTX_PAD_PT, y0 - CTX_PAD_PT,
                         x1 + CTX_PAD_PT, y1 + CTX_PAD_PT)
    # get_pixmap(clip=) expects UNROTATED coords: map back through derotation
    clip = clip_rot * page.derotation_matrix
    clip.normalize()
    clip = clip & page.rect if page.rotation == 0 else clip
    try:
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        if page.rotation:
            img = img.rotate(-page.rotation, expand=True)
        img.thumbnail((CELL - 8, CELL - 26))
        return img
    except Exception:
        return Image.new("RGB", (CELL - 8, CELL - 26), (255, 220, 220))


def main(argv):
    pdf_path, out_dir = argv[0], Path(argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    inst, glyph_pool = collect_symbol_instances(doc)
    # font-decode pool: repeated glyph-sized shapes = the drafting house's
    # plotted FONT. Saved for the glyph-decode build (deterministic OCR kill).
    gp = sorted(((str(fp), len(v)) for fp, v in glyph_pool.items()
                 if len(v) >= 5), key=lambda kv: -kv[1])
    (out_dir / "glyph_pool_summary.json").write_text(json.dumps(
        {"unique_glyph_shapes_ge5": len(gp),
         "total_instances": sum(c for _, c in gp),
         "top": gp[:120]}, indent=1))
    print(f"font-decode pool: {len(gp)} repeated glyph shapes "
          f"({sum(c for _, c in gp)} instances) -> glyph_pool_summary.json")
    clusters = sorted(inst.items(), key=lambda kv: -len(kv[1]))
    main_clusters = [(fp, v) for fp, v in clusters if len(v) >= MIN_INSTANCES]
    residue = [(fp, v) for fp, v in clusters if len(v) < MIN_INSTANCES]
    print(f"symbol instances: {sum(len(v) for v in inst.values())} -> "
          f"{len(clusters)} unique shapes; {len(main_clusters)} with >= "
          f"{MIN_INSTANCES} instances (residue shapes: {len(residue)})")
    bank = []
    for k, (fp, v) in enumerate(main_clusters):
        pages = sorted({p for p, _ in v})
        bank.append({"cluster": k, "fingerprint": str(fp),
                     "instances": len(v), "pages": pages[:20],
                     "example": {"page": v[0][0],
                                 "bbox": [round(x, 1) for x in v[0][1]]},
                     "engineer_type": "",   # <- the red-pen field (§6 taxonomy)
                     "engineer_note": ""})
    (out_dir / "symbol_bank_DRAFT.json").write_text(json.dumps(
        {"source": Path(pdf_path).name, "clusters": bank,
         "residue_shapes": len(residue)}, indent=1))
    # contact sheets: 8 x 6 grid per sheet
    cols, rows = 8, 6
    per = cols * rows
    for sheet_no in range(0, len(main_clusters), per):
        batch = main_clusters[sheet_no:sheet_no + per]
        W, H = cols * CELL, rows * CELL
        sheet = Image.new("RGB", (W, H), (255, 255, 255))
        dr = ImageDraw.Draw(sheet)
        for i, (fp, v) in enumerate(batch):
            cx, cy = (i % cols) * CELL, (i // cols) * CELL
            cell_img = render_cell(doc, v[0][0], v[0][1])
            sheet.paste(cell_img, (cx + 4, cy + 22))
            cid = sheet_no + i
            dr.rectangle([cx, cy, cx + CELL - 1, cy + CELL - 1],
                         outline=(180, 180, 180))
            dr.text((cx + 5, cy + 4),
                    f"#{cid}  x{len(v)}  p{v[0][0]}", fill=(160, 0, 0))
        fn = out_dir / f"symbol_contact_sheet_{sheet_no // per}.png"
        sheet.save(fn)
        print("sheet:", fn)


if __name__ == "__main__":
    main(sys.argv[1:])
