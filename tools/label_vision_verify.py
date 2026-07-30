"""
LABEL VISION VERIFY — the priced, capped API channel for OCR residue.

The deterministic sweep leaves a queue of low-confidence labels
(queue_label_verify.json per file). This tool batches those crops into
MONTAGES (~40 crops per image), sends each montage to the vision provider
ONCE, and records the model's read next to tesseract's — the engineer-approved
"use API when needed, don't go crazy" channel.

COST DISCIPLINE (hard, not advisory):
  * --max-usd is REQUIRED. The tool prices the run up front (montage count x
    per-call estimate), REFUSES to start if the estimate exceeds the cap, and
    STOPS mid-run if measured spend (from the API's own usage numbers when
    available, else the estimate) reaches the cap. A stop is a ledgered,
    resumable state, not a failure.
  * every call is ledgered (labels_verify_ledger.jsonl) — kill-safe, re-run
    skips completed montages.

READ DISCIPLINE:
  * the model is asked to READ ONLY — printed characters per numbered crop,
    '<UNKNOWN>' when illegible. No interpretation, no device typing, no vessel
    vocabulary in the prompt (gold-blind: this is an OCR verifier, not an
    oracle).
  * output field is `vision_text`; it NEVER overwrites tesseract's read — the
    two sit side by side, and only AGREEMENT (normalised) promotes a label to
    verified confidence. Disagreement leaves the label low-conf and flagged.
    A single reader cannot promote itself: promotion needs two independent
    channels agreeing (tesseract + vision), which is the dual-channel rule.

    python3.12 tools/label_vision_verify.py <sweep_dir_of_one_file> \
        --pdf <src.pdf> --max-usd 2.00 [--limit-montages 2]

Requires ANTHROPIC_API_KEY via the project .env (Mac). Smoke-test first:
--limit-montages 1 on one file, read the ledger, then scale.
"""
from __future__ import annotations

import io
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None

CROPS_PER_MONTAGE = 40
EST_USD_PER_CALL = 0.02      # priced estimate; measured usage supersedes it
ZOOM = 9


_READ_PROMPT = (
    "This image is a numbered grid of small text crops taken from an "
    "engineering drawing. For EACH numbered cell, read the printed characters "
    "EXACTLY as printed — device ids, ratings, words, punctuation. Do not "
    "interpret, expand, or correct anything. If a cell is illegible or empty, "
    "return '<UNKNOWN>' for it. Return every cell number you can see."
)
_READ_TOOL = {
    "name": "record_crop_reads",
    "description": "Exact reads of numbered text crops.",
    "input_schema": {
        "type": "object",
        "properties": {"reads": {"type": "array", "items": {
            "type": "object", "properties": {
                "cell": {"type": "integer"},
                "text": {"type": "string"}},
            "required": ["cell", "text"]}}},
        "required": ["reads"],
    },
}


def _norm(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def build_montage(page_img: Image.Image, items: List[Dict[str, Any]],
                  start_no: int) -> Image.Image:
    cols, cell_w, cell_h = 4, 340, 70
    rows = (len(items) + cols - 1) // cols
    m = Image.new("RGB", (cols * cell_w, rows * cell_h), (255, 255, 255))
    dr = ImageDraw.Draw(m)
    pad = 1.8
    for i, it in enumerate(items):
        b = it["bbox"]
        crop = page_img.crop((int((b[0] - pad) * ZOOM), int((b[1] - pad) * ZOOM),
                              int((b[2] + pad) * ZOOM), int((b[3] + pad) * ZOOM)))
        crop.thumbnail((cell_w - 60, cell_h - 12))
        x, y = (i % cols) * cell_w, (i // cols) * cell_h
        dr.rectangle([x, y, x + cell_w - 1, y + cell_h - 1],
                     outline=(200, 200, 200))
        dr.text((x + 4, y + cell_h // 2 - 6), f"{start_no + i}:",
                fill=(180, 0, 0))
        m.paste(crop, (x + 46, y + 6))
    return m


def main(argv):
    run_dir = Path(argv[0])
    pdf_path = Path(argv[argv.index("--pdf") + 1])
    if "--max-usd" not in argv:
        print("REFUSED: --max-usd is required — this tool never runs uncapped.")
        sys.exit(2)
    max_usd = float(argv[argv.index("--max-usd") + 1])
    limit_m = (int(argv[argv.index("--limit-montages") + 1])
               if "--limit-montages" in argv else None)

    qf = run_dir / "queue_label_verify.json"
    if not qf.exists():
        print("nothing to verify (no queue_label_verify.json)")
        return
    queue = json.loads(qf.read_text())
    montage_total = (len(queue) + CROPS_PER_MONTAGE - 1) // CROPS_PER_MONTAGE
    est = round(montage_total * EST_USD_PER_CALL, 2)
    print(f"queue {len(queue)} labels -> {montage_total} montage calls, "
          f"estimated ${est:.2f} (cap ${max_usd:.2f})")
    if est > max_usd and not limit_m:
        print(f"REFUSED: estimate ${est:.2f} exceeds cap ${max_usd:.2f}. "
              f"Raise --max-usd knowingly, or smoke-test with "
              f"--limit-montages first.")
        sys.exit(2)

    from providers.vision import get_vision_provider
    vp = get_vision_provider()

    ledger = run_dir / "labels_verify_ledger.jsonl"
    done = set()
    if ledger.exists():
        for l in ledger.read_text().splitlines():
            try:
                done.add(json.loads(l)["montage"])
            except Exception:
                pass

    doc = fitz.open(pdf_path)
    by_page: Dict[int, List[Dict[str, Any]]] = {}
    for it in queue:
        by_page.setdefault(it["page"], []).append(it)

    spent = 0.0
    m_no = 0
    agree = differ = unknown = 0
    with ledger.open("a") as led:
        for pno in sorted(by_page):
            page = doc[pno]
            pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM),
                                  colorspace=fitz.csGRAY)
            page_img = Image.frombytes("L", (pix.width, pix.height),
                                       pix.samples).convert("RGB")
            items = by_page[pno]
            for s in range(0, len(items), CROPS_PER_MONTAGE):
                m_no += 1
                if m_no in done:
                    continue
                if limit_m and m_no > limit_m:
                    print(f"stopping at --limit-montages {limit_m}")
                    print_summary(agree, differ, unknown, spent)
                    return
                if spent + EST_USD_PER_CALL > max_usd:
                    print(f"COST CAP REACHED (${spent:.2f} of ${max_usd:.2f})"
                          f" — stopping; re-run with a higher cap to resume.")
                    print_summary(agree, differ, unknown, spent)
                    return
                batch = items[s:s + CROPS_PER_MONTAGE]
                montage = build_montage(page_img, batch, start_no=1)
                buf = io.BytesIO()
                montage.save(buf, "PNG")
                t0 = time.time()
                r = vp.extract(buf.getvalue(), "image/png",
                               _READ_PROMPT, _READ_TOOL)
                spent += EST_USD_PER_CALL
                reads = {int(x["cell"]): x.get("text", "")
                         for x in (r.get("reads") or [])
                         if isinstance(x, dict) and "cell" in x}
                out = []
                for i, it in enumerate(batch):
                    vt = reads.get(i + 1, "")
                    it2 = dict(it)
                    it2["vision_text"] = vt
                    if vt == "<UNKNOWN>" or not vt:
                        it2["verdict"] = "unknown"
                        unknown += 1
                    elif _norm(vt) == _norm(it.get("tesseract", "")):
                        it2["verdict"] = "agree_promoted"
                        agree += 1
                    else:
                        it2["verdict"] = "disagree_flagged"
                        differ += 1
                    out.append(it2)
                led.write(json.dumps({"montage": m_no, "page": pno,
                                      "secs": round(time.time() - t0, 1),
                                      "items": out}) + "\n")
                led.flush()
                print(f"montage {m_no}/{montage_total} p{pno}: "
                      f"{len(batch)} crops", flush=True)
    print_summary(agree, differ, unknown, spent)


def print_summary(agree, differ, unknown, spent):
    total = agree + differ + unknown
    print(f"verified {total} labels: {agree} agree(promoted), "
          f"{differ} disagree(flagged), {unknown} unknown; "
          f"estimated spend ${spent:.2f}")


if __name__ == "__main__":
    main(sys.argv[1:])
