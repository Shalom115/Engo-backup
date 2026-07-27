"""
PHASE-0 CORPUS PROBE — autonomous A1/A2 triage of EVERY PDF in the vessel
library. This is Phase-0 as CODE, not as a session: no file list to curate,
no engineer in the loop. Run it on the machine that holds the service-account
key (the boat MacBook):

    python tools/probe_corpus.py                # probes every PDF in the manifest
    python tools/probe_corpus.py --limit 50     # first N (smoke run)

What it does:
  1. reads the canonical structure manifest (structure_<vessel>.json — every
     node walked LIVE, per the standing rule);
  2. for every application/pdf file, downloads bytes via the existing read-only
     Drive connector (providers/structure.py — no new access path);
  3. probes every page with vector_probe.probe_page: pure-vector plot (A1) vs
     raster/image (A2), plus wire/glyph/path counts;
  4. emits data/state/corpus_probe_<vessel>.json: per-file class, per-class
     totals, and the routing decision the ingest pipeline should apply
     (A1 -> geometry-first pipeline; A2 -> vision tiling path).

Kill-safe: appends one JSONL line per file to corpus_probe_ledger_<vessel>.jsonl
and skips already-probed ids on resume. Network retry with backoff (the
Gold-#2 crash lesson).

This file is also the seed for the route_kind integration: the ingest
pipeline calls classify_pdf_bytes() below instead of running this script.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz  # PyMuPDF

from vector_probe import probe_page  # noqa: E402

VESSEL = "gelliceaux_001"
STATE = Path(__file__).resolve().parent.parent / "data" / "state"
MANIFEST = STATE / f"structure_{VESSEL}.json"
LEDGER = STATE / f"corpus_probe_ledger_{VESSEL}.jsonl"
REPORT = STATE / f"corpus_probe_{VESSEL}.json"


def classify_pdf_bytes(pdf_bytes: bytes) -> dict:
    """The route_kind-callable core. Per-page classes (v2 — 'has images' is
    NOT raster; the Electrical System GA has 21k vector wire segments AND 17
    embedded logo/render images):
      A1_vector : vector linework, no raster images -> geometry-first path
      A1_hybrid : vector linework + embedded images -> geometry-first for
                  lines/labels; images inventoried (equipment photos/logos)
                  for one-shot vision classification
      A2_raster : little/no vector content -> vision tiling path
    Plus text_layer: chars in the PDF text layer (a real text layer means
    labels come FREE with positions via get_text('words') — no OCR at all;
    Nav layout 2,188 chars / Steering GA 2,575 chars proved this class)."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for i in range(doc.page_count):
        r = probe_page(doc[i])
        p = doc[i]
        if len(p.get_drawings()) >= VECTOR_MIN_PATHS:
            r["class"] = "A1_hybrid" if r["images"] > 0 else "A1_vector"
        else:
            r["class"] = "A2_raster"
        pages.append({"page": i, **r})
    classes = Counter(p["class"] for p in pages)
    file_class = (list(classes)[0] if len(classes) == 1 else "mixed")
    return {"file_class": file_class, "page_count": doc.page_count,
            "class_counts": dict(classes),
            "text_layer_chars": sum(p["text_chars"] for p in pages),
            "pages": pages}


def _download_with_retry(connector, file_id: str, tries: int = 4) -> bytes:
    delay = 2.0
    for attempt in range(tries):
        try:
            return connector.download_bytes(file_id)
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def main(argv):
    limit = None
    if "--limit" in argv:
        limit = int(argv[argv.index("--limit") + 1])
    from providers.structure import get_structure_provider
    provider = get_structure_provider()

    manifest = json.loads(MANIFEST.read_text())
    nodes = manifest.get("nodes") or manifest  # tolerate either shape
    pdfs = [n for n in nodes
            if isinstance(n, dict) and n.get("mime") == "application/pdf"]
    done = set()
    if LEDGER.exists():
        for line in LEDGER.read_text().splitlines():
            try:
                done.add(json.loads(line)["id"])
            except Exception:
                pass
    todo = [n for n in pdfs if n.get("id") not in done]
    if limit:
        todo = todo[:limit]
    print(f"PDFs in manifest: {len(pdfs)}; already probed: {len(done)}; "
          f"this run: {len(todo)}")
    with LEDGER.open("a") as led:
        for k, node in enumerate(todo):
            fid, name = node.get("id"), node.get("name")
            try:
                data = _download_with_retry(provider, fid)
                r = classify_pdf_bytes(data)
                rec = {"id": fid, "name": name, "path": node.get("path"),
                       **{k2: r[k2] for k2 in
                          ("file_class", "page_count", "class_counts")}}
            except Exception as e:
                rec = {"id": fid, "name": name, "error": str(e)[:200]}
            led.write(json.dumps(rec) + "\n")
            led.flush()
            if (k + 1) % 25 == 0:
                print(f"  {k+1}/{len(todo)}")
    # roll the ledger into the report
    rows = [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]
    by_class = Counter(r.get("file_class", "error") for r in rows)
    REPORT.write_text(json.dumps({
        "vessel": VESSEL, "probed": len(rows), "split": dict(by_class),
        "files": rows}, indent=1))
    print(f"SPLIT: {dict(by_class)} -> {REPORT}")


if __name__ == "__main__":
    main(sys.argv[1:])
