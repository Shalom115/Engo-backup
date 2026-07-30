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

import hashlib
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


def stable_hash(obj) -> str:
    """PERSISTENT fingerprint. Python's built-in hash() is randomised per
    process for strings (PYTHONHASHSEED), so a fingerprint written to a bank
    file in one run can NEVER match the same shape fingerprinted in the next
    run — the bank silently types 0% of everything. Caught 2026-07-28 by
    actually running symbol_typing against the confirmed bank (0/159 typed).
    blake2b over a canonical repr is stable across processes and machines."""
    return hashlib.blake2b(repr(obj).encode("utf-8"), digest_size=12).hexdigest()


def path_fingerprint(d, R):
    """Normalized shape signature of one drawing path (rotation-corrected to
    render space, translation-invariant, 0.1pt quantized). Returns a STABLE
    (cross-process) hex fingerprint — see stable_hash."""
    sig = []
    origin = None
    for it in d["items"]:
        pts = [( (fitz.Point(x, y) * R).x, (fitz.Point(x, y) * R).y)
               for (x, y) in _pts(it)]
        if not pts:
            continue
        if origin is None:
            origin = pts[0]
        # `+ 0.0` normalises -0.0 to 0.0: hash(-0.0)==hash(0.0) but
        # repr(-0.0)!="0.0", so without this the stable hash SPLITS clusters
        # the old hash() merged (observed: 136 -> 137 clusters on rebuild).
        sig.append((it[0],) + tuple(
            (round(x - origin[0], 1) + 0.0, round(y - origin[1], 1) + 0.0)
            for (x, y) in pts))
    return (stable_hash(tuple(sig)) if sig else None), origin


def _page_wires(page, R):
    """Wire segments (render space) + a coarse spatial grid, for the
    WIRE-TOUCH FILTER."""
    segs = []
    for d in page.get_drawings():
        for it in d["items"]:
            if it[0] == "l":
                a, b = fitz.Point(*_pts(it)[0]) * R, fitz.Point(*_pts(it)[1]) * R
                if math.hypot(b.x - a.x, b.y - a.y) >= 4.0:
                    segs.append((a.x, a.y, b.x, b.y))
    grid = defaultdict(list)
    cell = 10.0
    for i, (x0, y0, x1, y1) in enumerate(segs):
        steps = max(1, int(math.hypot(x1 - x0, y1 - y0) / cell))
        for s in range(steps + 1):
            t = s / steps
            grid[(int((x0 + t * (x1 - x0)) / cell),
                  int((y0 + t * (y1 - y0)) / cell))].append(i)
    return segs, grid, cell


def _near_wire(bb, segs, grid, cell, tol=3.0):
    cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
    cand = set()
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            cand.update(grid.get((int(cx / cell) + dx, int(cy / cell) + dy), []))
    hw, hh = (bb[2] - bb[0]) / 2 + tol, (bb[3] - bb[1]) / 2 + tol
    for j in cand:
        x0, y0, x1, y1 = segs[j]
        # segment bbox vs padded symbol bbox overlap (cheap, adequate)
        if not (max(x0, x1) < cx - hw or min(x0, x1) > cx + hw
                or max(y0, y1) < cy - hh or min(y0, y1) > cy + hh):
            return True
    return False


def collect_symbol_instances(doc: fitz.Document):
    """Every closed small stroke-loop + every multi-curve compact path,
    fingerprinted, across all pages.

    v2 QUALITY FILTERS (engineer red-pen 2026-07-27 — the bank was full of
    junk: the GM-logo 'M', pushbutton caption art, title-block furniture):
      * WIRE-TOUCH: an electrical symbol sits ON or immediately AT a
        conductor. Shapes that touch no wire segment (logos, decorative art,
        caption boxes floating in text) are excluded from the bank.
      * TITLE-BLOCK EXCLUSION: shapes inside the bottom-right title-block
        region are furniture, never devices."""
    instances = defaultdict(list)   # fp -> [(page, bbox)]  (symbol-sized)
    glyph_pool = defaultdict(list)  # fp -> [(page, bbox)]  (font-decode input)
    dropped_unwired = 0
    for pno in range(doc.page_count):
        page = doc[pno]
        R = page.rotation_matrix
        segs, wgrid, wcell = _page_wires(page, R)
        pr = page.rect * page.rotation_matrix
        W, H = abs(pr.width), abs(pr.height)
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
            bb = [min(xs), min(ys), max(xs), max(ys)]
            # SYMBOL-sized: above glyph height (text here is ~2.5-7pt), below
            # frame scale. Glyph-sized repeated shapes are NOT discarded — they
            # are the FONT-DECODE pool, collected separately below.
            if not (7.5 <= max(w, h) <= 45):
                if 1.0 <= max(w, h) < 7.5:
                    fp, _ = path_fingerprint(d, R)
                    if fp is not None:
                        glyph_pool[fp].append((pno, bb))
                continue
            # stroke loops and curve-built marks; skip single tiny lines
            if kinds == {"l"} and len(items) < 3:
                continue
            # LINE-FRAGMENT FILTER: a device symbol is two-dimensional; a
            # shape thinner than 2.5pt in either axis is dash/leader debris
            if w < 2.5 or h < 2.5:
                continue
            # TITLE-BLOCK EXCLUSION (bottom-right furniture region)
            if bb[1] > 0.84 * H and bb[0] > 0.45 * W:
                continue
            # WIRE-TOUCH FILTER: no conductor at the shape = not a device
            if not _near_wire(bb, segs, wgrid, wcell):
                dropped_unwired += 1
                continue
            fp, _ = path_fingerprint(d, R)
            if fp is None:
                continue
            instances[fp].append((pno, bb))
    print(f"  wire-touch filter dropped {dropped_unwired} unwired shapes")
    return instances, glyph_pool


_PAGE_CACHE: dict = {}


def render_cell(doc, pno, bbox, zoom=6.0):
    """Crop from ONE cached full-page render per page — never
    get_pixmap(clip=): its rotation-dependent clip semantics produced blank
    cells on every rotated page (the same trap that broke OCR crops)."""
    key = (pno, zoom)
    if key not in _PAGE_CACHE:
        page = doc[pno]
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        if len(_PAGE_CACHE) >= 4:   # bound memory (~54MB per cached page)
            _PAGE_CACHE.pop(next(iter(_PAGE_CACHE)))
        _PAGE_CACHE[key] = Image.frombytes(
            "RGB", (pix.width, pix.height), pix.samples)
    img = _PAGE_CACHE[key]
    x0, y0, x1, y1 = bbox
    crop = img.crop((int((x0 - CTX_PAD_PT) * zoom), int((y0 - CTX_PAD_PT) * zoom),
                     int((x1 + CTX_PAD_PT) * zoom), int((y1 + CTX_PAD_PT) * zoom)))
    crop.thumbnail((CELL - 8, CELL - 26))
    return crop


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
    # --classify (run on the machine holding the API key, e.g. the Mac):
    # one vision call per unique cluster against the STANDARD symbol
    # vocabulary (IEC 60617 device families) — the 'reliable source' half of
    # the engineer's both-sources directive; his red-pen of the result is the
    # other half. Gold-blind: vocabulary only, no expected answers.
    iec_vocab = [
        "terminal", "terminal_strip_cell", "breaker", "emergency_breaker",
        "fuse", "retractable_fuse", "relay_coil", "contact_NO", "contact_NC",
        "changeover_contact", "switch", "pushbutton", "selector_switch",
        "lamp_indicator", "led", "motor", "pump", "solenoid_valve",
        "current_transformer", "shunt", "battery", "converter", "inverter",
        "charger", "diode", "earth_ground", "chassis_ground", "plug_pin",
        "connector", "junction_dot", "wire_gauge_diamond", "meter_gauge",
        "horn_buzzer", "heater_resistive", "not_a_device_annotation",
        "unknown"]
    if "--classify" in sys.argv:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from providers.vision import get_vision_provider
        vp = get_vision_provider()
        _CLS_PROMPT = (
            "This is one repeated symbol from a marine electrical schematic, "
            "shown with a little surrounding context. Classify the SYMBOL at "
            "the center against standard electrical drawing conventions "
            "(IEC 60617 families). DEVICE DISCIPLINE: breaker != fuse != "
            "relay != contactor != terminal; a NO contact != NC contact; "
            "status/annotation marks are not devices. If it is drawing "
            "annotation (wire-gauge diamond, caption art), say so. If genuinely "
            "unclear, return 'unknown' — never guess.")
        _CLS_TOOL = {"name": "classify_symbol", "description": "one symbol",
                     "input_schema": {"type": "object", "properties": {
                         "symbol_type": {"type": "string", "enum": iec_vocab},
                         "confidence": {"type": "string",
                                        "enum": ["high", "medium", "low"]},
                         "reason": {"type": "string"}},
                         "required": ["symbol_type", "confidence"]}}
        import io as _io
        for k, (fp, v) in enumerate(main_clusters):
            img = render_cell(doc, v[0][0], v[0][1])
            buf = _io.BytesIO(); img.save(buf, "PNG")
            try:
                r = vp.extract(buf.getvalue(), "image/png", _CLS_PROMPT, _CLS_TOOL)
            except Exception as e:
                r = {"symbol_type": "unknown", "confidence": "low",
                     "reason": f"vision error {str(e)[:80]}"}
            main_clusters[k] = (fp, v, r)
    bank = []
    for k, entry in enumerate(main_clusters):
        fp, v = entry[0], entry[1]
        auto = entry[2] if len(entry) > 2 else None
        pages = sorted({p for p, _ in v})
        row = {"cluster": k, "fingerprint": str(fp),
               "instances": len(v), "pages": pages[:20],
               "example": {"page": v[0][0],
                           "bbox": [round(x, 1) for x in v[0][1]]},
               "engineer_type": "",   # <- the red-pen field (final authority)
               "engineer_note": ""}
        if auto:
            row["auto_type"] = auto.get("symbol_type")
            row["auto_confidence"] = auto.get("confidence")
        bank.append(row)
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
        for i, entry in enumerate(batch):
            fp, v = entry[0], entry[1]
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
