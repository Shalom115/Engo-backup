"""
FULL-BOOK VECTOR EXTRACTION RUNNER — ledgered, kill-safe, parallel-OCR.

Runs the vector_extract_poc pipeline (primitives -> dash-join -> nets ->
labels -> local OCR -> geometric attach) over EVERY page of an A1 book and
writes one JSON per page + an append-only ledger, so a killed run resumes
without recomputation (the ingest_drive lesson).

    python tools/run_book_extract.py <book.pdf> <out_dir> [--pages 0-42]

Per page -> <out_dir>/p<N>.json:
  {page, rotation, counts{wires,nets,sym_boxes,dots,labels},
   nets:[{net_id, n_segs, total_len, bbox}],
   sym_boxes:[[x0,y0,x1,y1],...], labels:[{bbox,text,conf,attach,...}]}
Ledger -> <out_dir>/ledger.jsonl (one line per completed page, real counts).

OCR is BATCHED: all of a page's label crops go into one multipage TIFF and
one tesseract invocation (OMP_THREAD_LIMIT=1). Measured p13: 4.3 s for the
full page including OCR — vs ~1.85 s/LABEL when 4 concurrent tesseracts
thrash 4 cores with per-crop processes. $0 API.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

from vector_extract_poc import (  # noqa: E402
    extract_primitives, merge_dashes, build_nets, cluster_labels,
    attach_labels, OCR_ZOOM,
)
from symbol_typing import load_bank, type_page_symbols  # noqa: E402
from sheet_legend import read_sheet_legend, legend_override_map  # noqa: E402

WORKERS = 4


def _tsv_per_tiff_page(tsv: str):
    """Parse tesseract TSV into {tiff_page_index: (text, mean_conf)}."""
    by_page = {}
    for line in tsv.splitlines():
        parts = line.split("\t")
        if len(parts) >= 12 and parts[0] != "level":
            try:
                pg = int(parts[1]) - 1
                cf = float(parts[10])
            except ValueError:
                continue
            if cf >= 0 and parts[11].strip():
                by_page.setdefault(pg, [[], []])
                by_page[pg][0].append(parts[11].strip())
                by_page[pg][1].append(cf)
    return {pg: (" ".join(w), round(sum(c) / len(c), 1))
            for pg, (w, c) in by_page.items()}


def _run_tesseract_tiff(frames):
    """One tesseract invocation over a multipage TIFF of crops. Startup cost
    is paid ONCE per call instead of once per label; OMP_THREAD_LIMIT=1 stops
    concurrent tesseracts thrashing the cores (measured 1.85 s/label without
    it vs the batch path's ~0.05-0.1 s/label)."""
    if not frames:
        return {}
    with tempfile.NamedTemporaryFile(suffix=".tiff", delete=False) as f:
        fn = f.name
    try:
        frames[0].save(fn, save_all=True, append_images=frames[1:],
                       compression="tiff_deflate")
        env = dict(os.environ, OMP_THREAD_LIMIT="1")
        out = subprocess.run(
            ["tesseract", fn, "stdout", "--psm", "7", "tsv"],
            capture_output=True, text=True, env=env)
        return _tsv_per_tiff_page(out.stdout)
    finally:
        os.unlink(fn)


def ocr_labels_batch(page: fitz.Page, labels):
    """Batch-OCR all label crops of a page: horizontal labels in one multipage
    TIFF; vertical labels tried at -90 then +90 in two further batches."""
    pix = page.get_pixmap(matrix=fitz.Matrix(OCR_ZOOM, OCR_ZOOM),
                          colorspace=fitz.csGRAY)
    page_img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    pad = 1.8

    def crop_of(L):
        b = L["bbox"]
        return page_img.crop((int((b[0] - pad) * OCR_ZOOM),
                              int((b[1] - pad) * OCR_ZOOM),
                              int((b[2] + pad) * OCR_ZOOM),
                              int((b[3] + pad) * OCR_ZOOM)))

    horiz = [(i, L) for i, L in enumerate(labels) if not L["vertical"]]
    vert = [(i, L) for i, L in enumerate(labels) if L["vertical"]]
    results = {}
    hr = _run_tesseract_tiff([crop_of(L) for _, L in horiz])
    for k, (i, _) in enumerate(horiz):
        results[i] = hr.get(k, ("", 0.0))
    if vert:
        vm = _run_tesseract_tiff([crop_of(L).rotate(-90, expand=True)
                                  for _, L in vert])
        vp = _run_tesseract_tiff([crop_of(L).rotate(90, expand=True)
                                  for _, L in vert])
        for k, (i, _) in enumerate(vert):
            a, b = vm.get(k, ("", 0.0)), vp.get(k, ("", 0.0))
            results[i] = a if a[1] >= b[1] else b
    out = []
    for i, L in enumerate(labels):
        txt, conf = results.get(i, ("", 0.0))
        out.append({"bbox": [round(x, 1) for x in L["bbox"]],
                    "vertical": L["vertical"], "text": txt, "conf": conf})
    return out


def process_page(doc: fitz.Document, idx: int, bank=None) -> dict:
    page = doc[idx]
    wires, sym_boxes, dots, glyph = extract_primitives(page)
    segs = merge_dashes(wires)
    netid, nets, grid, cell = build_nets(segs, dots)
    labels = cluster_labels(glyph)
    res = ocr_labels_batch(page, labels)
    attached = attach_labels(res, segs, sym_boxes, netid, grid, cell)
    # SYMBOL TYPING — in the PATH, not the caller (audit F11 + the
    # legends-first lesson: a mandated step that lives in whatever script
    # happens to call it is a step that goes missing). Every symbol instance
    # gets its engineer-confirmed type by fingerprint; unknown shapes are
    # flagged, never guessed.
    # LEGENDS FIRST — read the sheet's own legend BEFORE typing any symbol,
    # inside the path (audit F1). The sheet's legend overrides the bank.
    legend = read_sheet_legend(page, res)
    typed_symbols = []
    if bank:
        typed_symbols = type_page_symbols(page, bank,
                                          legend_map=legend_override_map(legend))
    # NET MEMBERSHIP — what each conductor actually TOUCHES.
    #
    # Until 2026-07-30 a net was persisted as {net_id, n_segs, total_len,
    # bbox} only. The union-find had already worked out the full conductor
    # topology from the real line segments, and then the page record kept a
    # bounding box and threw the graph away. So after a complete sweep you
    # could not walk a circuit: the engineer's "follow L to N through every
    # terminal, breaker and relay" was computed on every page and forgotten.
    # Persisting membership costs a few KB per page and is the difference
    # between a sweep you can trace and a sweep you would have to re-run.
    #
    # A symbol/label belongs to a net if the net passes through its box (or
    # within TOUCH pt of it). Touching is geometric evidence of connection —
    # the DOT RULE still governs whether two crossing conductors are joined,
    # and that was already applied when the nets were built.
    TOUCH = 2.0

    def _hits(bb, x0, y0, x1, y1):
        """Does segment (x0,y0)-(x1,y1) come within TOUCH of box bb?"""
        return not (max(x0, x1) < bb[0] - TOUCH or min(x0, x1) > bb[2] + TOUCH
                    or max(y0, y1) < bb[1] - TOUCH or min(y0, y1) > bb[3] + TOUCH)

    net_rows = []
    for net in nets:
        xs, ys = [], []
        tot = 0.0
        members = [segs[i] for i in net]
        for x0, y0, x1, y1 in members:
            xs += [x0, x1]; ys += [y0, y1]
            tot += math.hypot(x1 - x0, y1 - y0)
        nb = [min(xs), min(ys), max(xs), max(ys)]
        touch_sym, touch_lab = [], []
        for si, s in enumerate(typed_symbols):
            bb = s.get("bbox")
            if not bb or bb[2] < nb[0] - TOUCH or bb[0] > nb[2] + TOUCH \
                    or bb[3] < nb[1] - TOUCH or bb[1] > nb[3] + TOUCH:
                continue          # cheap reject on the net's own bbox first
            if any(_hits(bb, *m) for m in members):
                touch_sym.append(si)
        for li, lab in enumerate(res):
            bb = lab.get("bbox")
            if not bb or not lab.get("text"):
                continue
            if bb[2] < nb[0] - TOUCH or bb[0] > nb[2] + TOUCH \
                    or bb[3] < nb[1] - TOUCH or bb[1] > nb[3] + TOUCH:
                continue
            if any(_hits(bb, *m) for m in members):
                touch_lab.append(li)
        net_rows.append({"net_id": int(netid[net[0]]), "n_segs": len(net),
                         "total_len": round(tot, 1),
                         "bbox": [round(v, 1) for v in nb],
                         "symbols": touch_sym, "labels": touch_lab})
    ne = sum(1 for r in res if r["text"])
    hi = sum(1 for r in res if r["conf"] >= 70)
    n_typed = sum(1 for s in typed_symbols if s.get("type"))
    n_verify = sum(1 for s in typed_symbols if s.get("verify_required"))
    return {
        "page": idx, "rotation": page.rotation,
        "counts": {"wires": len(segs), "nets": len(nets),
                   "sym_boxes": len(sym_boxes), "dots": len(dots),
                   "labels": len(labels), "ocr_nonempty": ne,
                   "ocr_conf70": hi, "attached": attached,
                   "symbols": len(typed_symbols), "symbols_typed": n_typed,
                   "symbols_unknown": len(typed_symbols) - n_typed,
                   "symbols_need_verify": n_verify,
                   "legend_entries": len(legend.get("entries", []))},
        "legend": legend,
        "nets": net_rows,
        "sym_boxes": [[round(v, 1) for v in bb] for bb in sym_boxes],
        "typed_symbols": typed_symbols,
        "labels": res,
    }


def main(argv):
    pdf_path, out_dir = argv[0], Path(argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    bank = load_bank()
    print(f"symbol bank: {len(bank)} engineer-confirmed shapes", flush=True)
    pages = range(doc.page_count)
    if "--pages" in argv:
        a, b = argv[argv.index("--pages") + 1].split("-")
        pages = range(int(a), int(b) + 1)
    ledger = out_dir / "ledger.jsonl"
    done = set()
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            try:
                done.add(json.loads(line)["page"])
            except Exception:
                pass
    with ledger.open("a") as led:
        for idx in pages:
            if idx in done:
                continue
            t0 = time.time()
            try:
                rec = process_page(doc, idx, bank=bank)
                (out_dir / f"p{idx}.json").write_text(json.dumps(rec))
                line = {"page": idx, "ok": True,
                        "secs": round(time.time() - t0, 1), **rec["counts"]}
            except Exception as e:
                line = {"page": idx, "ok": False, "error": str(e)[:300],
                        "secs": round(time.time() - t0, 1)}
            led.write(json.dumps(line) + "\n")
            led.flush()
            print(json.dumps(line), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
