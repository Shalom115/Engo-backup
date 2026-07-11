"""
GM-BOOK RE-EXTRACTION (batch 3) — engineer GO 2026-07-10.

Re-reads the GM electrical book's wiring pages with the full corrected stack:
  1. LEGENDS-FIRST     — the sheet's own legends/tables read up front, injected
                         into every read prompt (authoritative over generics).
  2. SYMBOL GLOSSARY   — fleet-general conventions from the engineer's red-pen
                         batches ride in every prompt automatically (via _ctx).
  3. COVERAGE READ     — survey regions (reused from the batch-2a ledger; the
                         geometry didn't change) + the fixed 3x3 grid, deduped.
  4. CROSS-REFERENCE   — every merged element list is ENRICHED against the full
                         page (the validated two-call design), in bounded chunks,
                         reconciled through _merge_enriched (never invent/drop).

Kill-safe: append-only ledger data/ledgers/batch3_reextract_ledger.jsonl; a
re-run skips pages already present. Topology is NOT re-extracted (reuse batch-2a
— the flags under repair came from wiring elements).

CLI:
    python3.12 -m pipeline.reextract_gm --pilot          # one page (bilge sheet)
    python3.12 -m pipeline.reextract_gm                  # full run (resumes)
    python3.12 -m pipeline.reextract_gm --pages 19 20    # specific pages (0-idx)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import config
from pipeline import electrical_extract as ee
from pipeline import legend_first

OLD_LEDGER = Path("data/ledgers/batch2a_v2_ledger.jsonl")
NEW_LEDGER = Path("data/ledgers/batch3_reextract_ledger.jsonl")
BOOK_PDF = Path("data/documents/gm_book_cache.pdf")
BOOK_ID = "1YAmYWTTes5AD7NGLCGXRG86OENBH22Pl"
PILOT_PAGE = 19  # GMMS 108'-114a BILGE SYSTEM — the gold-#2 family sheet
ENRICH_CHUNK = 25  # elements per enrichment call (output-token safety)


def _load_book() -> bytes:
    if BOOK_PDF.exists():
        return BOOK_PDF.read_bytes()
    from providers.structure import GoogleDriveStructureProvider
    sp = GoogleDriveStructureProvider(root_id=BOOK_ID, root_name="gm_book")
    for attempt in range(3):
        try:
            data, _ = sp.download_bytes(BOOK_ID, "application/pdf")
            break
        except Exception as e:  # noqa: BLE001 — retry then fail loud
            print(f"download attempt {attempt + 1} failed: {e}", flush=True)
            if attempt == 2:
                raise
            time.sleep(5)
    BOOK_PDF.parent.mkdir(parents=True, exist_ok=True)
    BOOK_PDF.write_bytes(data)
    return data


def _old_pages() -> List[Dict[str, Any]]:
    return [json.loads(l) for l in OLD_LEDGER.read_text().splitlines() if l.strip()]


def _survey_regions_from_old(rec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Distinct survey-region bboxes recovered from the batch-2a elements —
    reusing them keeps geometry comparable and saves a survey call per page."""
    seen = set()
    out = []
    for e in rec.get("wiring_elements") or []:
        if isinstance(e, dict) and e.get("_via") == "survey_region" and e.get("_bbox"):
            k = tuple(round(x, 4) for x in e["_bbox"])
            if k not in seen:
                seen.add(k)
                out.append({"bbox": list(e["_bbox"])})
    return out


def _enrich_all(elements: List[Dict[str, Any]], pdf: bytes, page_index: int,
                legend_ctx: str) -> Dict[str, Any]:
    """Cross-reference the page's MERGED element list against the full page,
    in bounded chunks, reconciled per chunk (never invent / never drop)."""
    merged: List[Dict[str, Any]] = []
    dropped = invented = 0
    for i in range(0, len(elements), ENRICH_CHUNK):
        chunk = elements[i:i + ENRICH_CHUNK]
        try:
            enriched = ee.enrich_region_against_full_page(
                chunk, pdf, page_index, [0.0, 0.0, 1.0, 1.0],
                legend_context=legend_ctx)
        except Exception as e:  # noqa: BLE001 — enrich failure keeps crop reads
            print(f"    enrich chunk @{i} failed ({e}) — crop reads kept", flush=True)
            merged.extend(chunk)
            continue
        rec = ee._merge_enriched({"elements": chunk}, enriched.get("elements") or [])
        merged.extend(rec["elements"])
        dropped += rec.get("_enrich_dropped_kept_from_crop", 0)
        invented += rec.get("_enrich_invented_discarded", 0)
    return {"elements": merged, "enrich_dropped_kept": dropped,
            "enrich_invented_discarded": invented}


def run(pages: List[int] | None = None) -> None:
    pdf = _load_book()
    old = {r["page"]: r for r in _old_pages()}
    done = set()
    if NEW_LEDGER.exists():
        for l in NEW_LEDGER.read_text().splitlines():
            if l.strip():
                done.add(json.loads(l)["page"])

    targets = pages if pages is not None else sorted(
        p for p, r in old.items() if (r.get("wiring_elements")))
    todo = [p for p in targets if p not in done]
    print(f"pages to process: {len(todo)} (done already: {len(done)})", flush=True)

    NEW_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    for n, pidx in enumerate(todo, 1):
        rec = old[pidx]
        t0 = time.time()
        print(f"[{n}/{len(todo)}] page {pidx} {rec.get('drawing_no')} "
              f"{rec.get('title')}", flush=True)
        legends = legend_first.from_pdf(pdf, pidx)
        ctx = legends.get("context_block", "")
        regions = _survey_regions_from_old(rec)
        els = ee.read_wiring_coverage(pdf, pidx, regions, legend_context=ctx)
        print(f"    coverage read: {len(els)} elements "
              f"({len(regions)} regions + 9 grid tiles); legends: "
              f"{len(legends.get('tables') or [])} tables", flush=True)
        enr = _enrich_all(els, pdf, pidx, ctx)
        out = {
            "page": pidx,
            "drawing_no": rec.get("drawing_no"),
            "title": rec.get("title"),
            "stack": "legends_first+glossary_v2+coverage+cross_reference",
            "legend_tables": [t.get("title_as_printed") for t in (legends.get("tables") or [])],
            "wiring_elements": enr["elements"],
            "enrich_dropped_kept": enr["enrich_dropped_kept"],
            "enrich_invented_discarded": enr["enrich_invented_discarded"],
            "elapsed_s": round(time.time() - t0, 1),
        }
        with NEW_LEDGER.open("a") as f:
            f.write(json.dumps(out) + "\n")
        print(f"    enriched: {len(enr['elements'])} elements "
              f"(kept-from-crop {enr['enrich_dropped_kept']}, "
              f"invented-discarded {enr['enrich_invented_discarded']}) "
              f"in {out['elapsed_s']}s — ledger flushed", flush=True)
    print("RE-EXTRACTION COMPLETE", flush=True)


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="GM book re-extraction (batch 3).")
    ap.add_argument("--pilot", action="store_true", help=f"one page only ({PILOT_PAGE})")
    ap.add_argument("--pages", type=int, nargs="*", default=None)
    a = ap.parse_args(argv)
    run([PILOT_PAGE] if a.pilot else a.pages)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
