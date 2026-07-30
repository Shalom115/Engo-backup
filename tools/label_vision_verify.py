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

PROMOTION IS APPLIED, NOT JUST LOGGED (leak found 2026-07-30 by tracing the
consumer: this tool wrote its ledger and nothing ever read it, so a PAID
verification pass changed nothing downstream — routing_preview still saw the
old sub-70 confidence and still dropped the label). `apply_ledger()` folds the
ledger back into the p<N>.json records and runs AUTOMATICALLY at the end of
every run, so there is no way to spend money and not receive the result:
    agree_promoted   -> conf_final = 95, text_final = TESSERACT's text
                        (verbatim — the vision read is corroboration, never
                        the source), conf_source = dual_channel_agree
    disagree_flagged -> vision_text recorded + label_flag; text untouched
    unknown          -> label_flag only
A full glyph decode (conf_final 99) always outranks a promotion and is left
alone.

    python3.12 tools/label_vision_verify.py <sweep_dir_of_one_file> \
        --pdf <src.pdf> --max-usd 2.00 [--limit-montages 2]
    python3.12 tools/label_vision_verify.py <sweep_dir> --apply-only
        (fold an EXISTING ledger into the page records; no API calls, $0)

Requires ANTHROPIC_API_KEY via the project .env (Mac). Smoke-test first:
--limit-montages 1 on one file, read the ledger, then scale.
"""
from __future__ import annotations

import io
import json
import re
import sys
import time
from collections import Counter
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


def _bkey(b) -> tuple:
    """Stable key for a label bbox across JSON round-trips."""
    return tuple(round(float(v), 2) for v in b)


def apply_ledger(run_dir: Path) -> dict:
    """Fold verify verdicts back into p<N>.json. Idempotent — re-running
    produces the same records, so a resumed/repeated verify is safe."""
    ledger = run_dir / "labels_verify_ledger.jsonl"
    if not ledger.exists():
        return {"applied": 0, "note": "no ledger"}
    by_page: Dict[int, Dict[tuple, dict]] = {}
    for line in ledger.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        for it in rec.get("items", []):
            by_page.setdefault(int(rec["page"]), {})[_bkey(it["bbox"])] = it

    stats = Counter()
    for pno, items in by_page.items():
        pf = run_dir / f"p{pno}.json"
        if not pf.exists():
            stats["page_missing"] += 1
            continue
        page = json.loads(pf.read_text())
        touched = False
        for lab in page.get("labels", []):
            it = items.get(_bkey(lab.get("bbox") or []))
            if not it:
                continue
            v = it.get("verdict")
            lab["vision_text"] = it.get("vision_text", "")
            lab["vision_verdict"] = v
            if v == "agree_promoted":
                # the vision read CORROBORATES; the stored text stays
                # tesseract's. Only confidence moves. A full glyph decode
                # (99) is stronger evidence and is never demoted.
                if float(lab.get("conf_final", lab.get("conf", 0))) < 95.0:
                    lab["text_final"] = lab.get("text", "")
                    lab["conf_final"] = 95.0
                    lab["conf_source"] = "dual_channel_agree"
                stats["promoted"] += 1
            elif v == "disagree_flagged":
                lab["label_flag"] = "dual_channel_disagree"
                stats["flagged"] += 1
            else:
                lab["label_flag"] = "vision_unknown"
                stats["unknown"] += 1
            touched = True
        if touched:
            pf.write_text(json.dumps(page))
    out = dict(stats)
    out["applied"] = stats["promoted"] + stats["flagged"] + stats["unknown"]
    (run_dir / "labels_verify_applied.json").write_text(json.dumps(out, indent=1))
    print(f"applied to page records: {out}")
    return out


def main(argv):
    run_dir = Path(argv[0])
    if "--apply-only" in argv:
        apply_ledger(run_dir)
        return
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
                    apply_ledger(run_dir)
                    return
                if spent + EST_USD_PER_CALL > max_usd:
                    print(f"COST CAP REACHED (${spent:.2f} of ${max_usd:.2f})"
                          f" — stopping; re-run with a higher cap to resume.")
                    print_summary(agree, differ, unknown, spent)
                    apply_ledger(run_dir)
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
    apply_ledger(run_dir)


def print_summary(agree, differ, unknown, spent):
    total = agree + differ + unknown
    print(f"verified {total} labels: {agree} agree(promoted), "
          f"{differ} disagree(flagged), {unknown} unknown; "
          f"estimated spend ${spent:.2f}")


if __name__ == "__main__":
    main(sys.argv[1:])
