"""
EXTRACT DOCUMENT — the single entry point for the full-drive run.

Given any PDF, probe it and dispatch to the right pipeline. This is what turns
the class protocols (docs/PROTOCOL_vector_first_classes.md) from prose into a
routing decision the machine makes per file, with no curated file list and no
engineer in the loop.

    python tools/extract_document.py <file.pdf> <out_dir> [--pages A-B]
    python tools/extract_document.py --plan <file.pdf>      # classify only, $0

ROUTING (decided by probe_corpus.classify_pdf_bytes + content signals):

  vector_drawing     A1 vector/hybrid, no usable text layer
                     -> full geometry path: nets + labels + LEGENDS-FIRST +
                        symbol typing from the confirmed bank + lint.
                        This is the validated path.

  text_layer_drawing real PDF text layer (>= TEXT_LAYER_MIN_PER_PAGE DISTINCT
                     chars/page — repeated boilerplate does not count)
                     -> labels come FREE with positions via get_text('words'):
                        no OCR at all. Geometry still gives nets/symbols.
                        (ONYX 104k chars, Steering GA 2.5k, Nav layout 2.2k.)

  (P&ID and GA are NOT separate routes: both run the vector/text geometry
   path, and their SPECIALISATIONS — per-service stroke-colour split + BOM
   tag-join for P&ID; positioned-callout leader-line routing for GA — are
   DESIGNED BUT NOT BUILT. `plan()` names them in `specialisations_pending`
   so a run reports what it did not do instead of implying full coverage.
   The hydraulic control map is never applied to these (source-type gate —
   the RUNNING BACKSTAY CABLE false positive).)

  manual_with_figures  text-dominant document containing embedded images
                     -> text already ingested elsewhere; here we inventory the
                        FIGURES (page, bbox, caption from the text layer) so
                        they can be queued, with provenance, for vision.

  raster             little/no vector content
                     -> NOT handled here. Returns a queue record for the
                        existing vision-tiling path. Never silently attempted.

Every route reports what it did and what it refused. Nothing writes to the
Register — routing_preview.py stays the only proposal surface, and it writes
nothing either.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz

from probe_corpus import classify_pdf_bytes  # noqa: E402

# DISTINCT chars per page, not total. The GM book's text layer is the SAME
# string ("G M MARINE SERVICES") on all 43 pages = 1,074 chars total, which a
# whole-doc threshold read as "has a text layer" and routed away from the
# geometry path. Distinct-per-page defeats the repeated-title-block trap that
# CLAUDE.md flagged for the §9a classifier.
TEXT_LAYER_MIN_PER_PAGE = 120
FIGURE_MIN_PX = 100         # ignore logos/rules when inventorying figures


def _legend_signal(page: fitz.Page) -> bool:
    """Cheap check for a legend heading in the text layer (a P&ID signal)."""
    t = (page.get_text() or "").upper()
    return any(k in t for k in ("LEGEND", "SYMBOLS", "BILL OF MATERIAL",
                                "PIPING DETAILS"))


def distinct_text_per_page(doc: fitz.Document) -> float:
    """Mean DISTINCT characters per page: the same boilerplate repeated on
    every page counts once. Defeats the repeated-title-block trap."""
    seen, total = set(), 0
    for i in range(doc.page_count):
        t = (doc[i].get_text() or "").strip()
        if t and t not in seen:
            seen.add(t)
            total += len(t)
    return total / max(1, doc.page_count)


def plan(pdf_bytes: bytes, name: str = "") -> Dict[str, Any]:
    """Classify + choose a route. $0, no rendering, no API."""
    cls = classify_pdf_bytes(pdf_bytes)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text_chars = cls["text_layer_chars"]
    dpp = distinct_text_per_page(doc)
    images = sum(len(doc[i].get_images()) for i in range(doc.page_count))
    wires = sum(p.get("wire_segments", 0) for p in cls["pages"])
    wpp = wires / max(1, doc.page_count)
    legend = any(_legend_signal(doc[i]) for i in range(min(3, doc.page_count)))
    vector_pages = (cls["class_counts"].get("A1_vector", 0)
                    + cls["class_counts"].get("A1_hybrid", 0))
    has_text_layer = dpp >= TEXT_LAYER_MIN_PER_PAGE

    if vector_pages == 0:
        route = "raster"
    elif has_text_layer and wpp < 200 and images >= doc.page_count:
        route = "manual_with_figures"
    elif has_text_layer:
        # labels come free; geometry still runs
        route = "text_layer_drawing"
    else:
        route = "vector_drawing"

    # SPECIALISATIONS that are DESIGNED but NOT BUILT — named so the run
    # reports what it did not do, instead of implying full coverage.
    pending = []
    if legend or (wires > 8000 and doc.page_count == 1):
        pending.append("pid: per-service stroke-colour split + BOM tag-join")
    if wpp < 6000 and images > 3 and doc.page_count <= 3:
        pending.append("ga: positioned-callout router (leader-line tracing)")

    return {"name": name, "route": route, "pages": doc.page_count,
            "file_class": cls["file_class"], "class_counts": cls["class_counts"],
            "text_layer_chars": text_chars,
            "distinct_text_per_page": round(dpp, 1),
            "has_text_layer": has_text_layer,
            "images": images, "wire_segments": wires,
            "wires_per_page": round(wpp), "legend_signal": legend,
            "specialisations_pending": pending,
            "page_classes": [{"page": pg["page"], "class": pg["class"],
                              "wires": pg.get("wire_segments", 0),
                              "text": pg.get("text_chars", 0)}
                             for pg in cls["pages"]]}


def harvest_text_layer(page: fitz.Page) -> List[Dict[str, Any]]:
    """Labels FREE from the PDF text layer, with positions, in render space.
    No OCR, no confidence guessing — these reads are exact."""
    R = page.rotation_matrix
    out = []
    for (x0, y0, x1, y1, word, *_rest) in page.get_text("words"):
        a = fitz.Point(x0, y0) * R
        b = fitz.Point(x1, y1) * R
        out.append({"bbox": [round(min(a.x, b.x), 1), round(min(a.y, b.y), 1),
                             round(max(a.x, b.x), 1), round(max(a.y, b.y), 1)],
                    "text": word, "conf": 100.0, "vertical": False,
                    "source": "pdf_text_layer"})
    return out


def inventory_figures(doc: fitz.Document) -> List[Dict[str, Any]]:
    """Embedded figures with page + bbox + nearest caption from the text
    layer — the manual-with-drawings route (protocol §5). Free; the figures
    themselves are queued for the existing vision path, not read here."""
    figs = []
    for pno in range(doc.page_count):
        page = doc[pno]
        text = page.get_text("words")
        for img in page.get_images(full=True):
            xref = img[0]
            try:
                rects = page.get_image_rects(xref)
            except Exception:
                rects = []
            for r in rects:
                if r.width < FIGURE_MIN_PX / 4 or r.height < FIGURE_MIN_PX / 4:
                    continue
                caption = ""
                best = 1e9
                for (x0, y0, x1, y1, w, *_x) in text:
                    if not w or w.lower().rstrip(".:").rstrip("0123456789") \
                            not in ("fig", "figure", "table", "dwg", "drawing"):
                        continue
                    d = abs(y0 - r.y1) + abs(x0 - r.x0) * 0.1
                    if d < best:
                        best, caption = d, w
                figs.append({"page": pno, "xref": xref,
                             "bbox": [round(r.x0, 1), round(r.y0, 1),
                                      round(r.x1, 1), round(r.y1, 1)],
                             "caption_hint": caption,
                             "queued_for": "vision_describe"})
    return figs


def main(argv):
    if "--plan" in argv:
        pdf = argv[argv.index("--plan") + 1]
        p = plan(Path(pdf).read_bytes(), Path(pdf).name)
        print(json.dumps(p, indent=1))
        return
    pdf_path, out_dir = argv[0], Path(argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    data = Path(pdf_path).read_bytes()
    p = plan(data, Path(pdf_path).name)
    print(f"ROUTE: {p['route']}  ({p['pages']}pp, {p['file_class']}, "
          f"distinct-text/page={p['distinct_text_per_page']}, "
          f"wires/page={p['wires_per_page']}, images={p['images']})", flush=True)
    for s_ in p["specialisations_pending"]:
        print(f"  NOT BUILT (reported, not silently skipped): {s_}")
    (out_dir / "plan.json").write_text(json.dumps(p, indent=1))

    if p["route"] == "raster":
        rec = {"route": "raster", "handled": False,
               "queued_for": "vision_tiling_path",
               "reason": "no usable vector content — the geometry path does "
                         "not apply; NOT attempted rather than attempted badly"}
        (out_dir / "queue_vision.json").write_text(json.dumps(rec, indent=1))
        print("REFUSED (correctly): raster document queued for the vision path")
        return

    if p["route"] == "manual_with_figures":
        doc = fitz.open(stream=data, filetype="pdf")
        figs = inventory_figures(doc)
        (out_dir / "figures.json").write_text(json.dumps(figs, indent=1))
        print(f"figures inventoried: {len(figs)} (page+bbox+caption hint) "
              f"-> queued for vision with provenance; text already ingested")
        # 80%-TEXT / 20%-SCHEMATIC MANUALS (engineer, 2026-07-28): schematic
        # pages INSIDE a text manual must not be missed. Any page whose wire
        # count says "drawing" gets the geometry pass, individually.
        draw_pages = [pg["page"] for pg in p["page_classes"]
                      if pg["wires"] >= 300 and pg["class"].startswith("A1")]
        if draw_pages:
            print(f"DRAWING PAGES inside the manual -> geometry pass: "
                  f"{draw_pages}")
            from run_book_extract import main as run_main
            for dp in draw_pages:
                run_main([pdf_path, str(out_dir), "--pages", f"{dp}-{dp}"])
        rp = [pg["page"] for pg in p["page_classes"]
              if pg["class"] == "A2_raster"]
        if rp:
            (out_dir / "queue_vision_pages.json").write_text(json.dumps(
                {"file": Path(pdf_path).name, "pages": rp,
                 "queued_for": "vision_tiling_path"}, indent=1))
            print(f"raster pages queued for vision: {rp}")
        return

    # every remaining route runs the geometry pipeline; the differences are
    # WHERE labels come from and WHICH extras run.
    from run_book_extract import main as run_main
    args = [pdf_path, str(out_dir)]
    if "--pages" in argv:
        args += ["--pages", argv[argv.index("--pages") + 1]]
    run_main(args)

    # PER-PAGE MIXED-DOCUMENT HANDLING (leak found in pre-flight audit):
    # routing was per-DOCUMENT, but pages differ. Two real cases:
    #  (a) BAE book = 40 vector + 7 RASTER pages -> the raster pages went
    #      through geometry and produced silently near-empty output;
    #  (b) the engineer's 80%-text/20%-schematic manual -> schematic pages
    #      inside a text doc must not be missed "just because it was sampled".
    # Every page below the vector floor is queued for the vision path, per
    # page, with provenance — reported, never silently empty.
    raster_pages = [pg["page"] for pg in p["page_classes"]
                    if pg["class"] == "A2_raster"]
    if raster_pages:
        (out_dir / "queue_vision_pages.json").write_text(json.dumps(
            {"file": Path(pdf_path).name, "pages": raster_pages,
             "queued_for": "vision_tiling_path",
             "reason": "raster pages inside a vector/text document — geometry "
                       "does not apply to these pages"}, indent=1))
        print(f"RASTER PAGES QUEUED FOR VISION (not silently empty): "
              f"{raster_pages}")

    # GLYPH FONT DECODE — in the PATH (the audit-F1 lesson applied to the
    # decoder too: it previously lived only in the caller). Multi-page books
    # can self-train; a per-house font table is reused/extended when present.
    ran_pages = sorted(int(q.stem[1:]) for q in out_dir.glob("p*.json")
                       if q.stem[1:].isdigit())
    if len(ran_pages) >= 6 and p["route"] == "vector_drawing":
        from glyph_font_decode import main as decode_main
        # FONT TABLE SCOPE, stated honestly: keyed by --house when given,
        # else by the DOCUMENT stem. A document-keyed table is per-BOOK, not
        # per-drafting-house — book 2 from the same house only inherits book
        # 1's font if the caller passes the same --house. Pass --house gm to
        # group the GM books; the sweep can group by folder when a house
        # identifier exists. (Never key it off a temp filename: doing so
        # merged every book into one table.)
        house = (argv[argv.index("--house") + 1] if "--house" in argv
                 else "".join(ch for ch in Path(pdf_path).stem.lower()
                              if ch.isalnum())[:24])
        ft = Path(__file__).resolve().parent.parent / "data" / "state" /              f"font_table_{house}.json"
        dargs = [pdf_path, str(out_dir), str(out_dir), "--font-table", str(ft)]
        decode_main(dargs)
        # persist the (merged) house font for the next book from this house
        src = out_dir / "font_table.json"
        if src.exists():
            ft.write_text(src.read_text())
            print(f"house font persisted: {ft.name}")
    elif p["route"] == "vector_drawing":
        print(f"decode skipped: {len(ran_pages)} page(s) ran — too few to "
              f"self-train (needs >= 6); tesseract reads stand, low-conf "
              f"labels go to the vision-verify queue")

    if p["route"] == "text_layer_drawing":
        doc = fitz.open(stream=data, filetype="pdf")
        n = 0
        # p<digits>.json only — plan.json matches "p*.json" too (same
        # collision that crashed the lint; fixed at every consumer)
        for pf in sorted(q for q in out_dir.glob("p*.json")
                         if q.stem[1:].isdigit()):
            rec = json.loads(pf.read_text())
            free = harvest_text_layer(doc[rec["page"]])
            if free:
                rec["text_layer_labels"] = free
                rec["counts"]["text_layer_labels"] = len(free)
                pf.write_text(json.dumps(rec))
                n += len(free)
        print(f"text-layer harvest: {n} exact labels added at $0 (no OCR)")
    print(f"-> {out_dir}  (nothing written to the Register)")


if __name__ == "__main__":
    main(sys.argv[1:])
