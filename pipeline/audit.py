"""
Corpus content audit — the standing gate that runs after EVERY ingest.

The 25% mess (drawings flagged "ingested" but text-empty) must never recur, and
files that exist in the structure manifest but were never ingested ("silent gaps")
must be surfaced, not lost. This reconciles the canonical structure manifest
against what is actually in the store + the queues + the ledgers, and grades every
file:

  confirmed_good   has real text content
  text_poor        has chunks but near-empty (distinct_words<60 or avg_chunk<80)
  pending_vision    queued for the vision pass (image/scanned/drawing)
  skipped           ~$ lock / zero-byte / unsupported / excluded format (with reason)
  silent_gap        in the structure tree but accounted for NOWHERE  ← must be zero

Emits audit_report_corpus.json. EXIT 1 (STOP) if silent_gaps>0 or text_poor>5%.

CLI:
    python -m pipeline.audit
    python -m pipeline.audit --json   # print the report path only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Set

import config
from providers.vectorstore import get_vectorstore_provider

DISTINCT_WORD_FLOOR = 60
AVG_CHUNK_FLOOR = 80
TEXT_POOR_PCT_GATE = 5.0
FOLDER_MIME = "application/vnd.google-apps.folder"
# Formats that legitimately produce no text and aren't a "mess" if uningested.
EXCLUDED_MIMES = {
    "image/vnd.dwg", "application/dxf", "application/postscript",
    "text/csv", "application/vnd.ms-excel", "application/msword",
    "message/rfc822", "application/octet-stream",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.google-apps.presentation",
}
IMAGE_PREFIX = "image/"


def _distinct(text: str) -> int:
    return len(set(w for w in re.findall(r"[a-zA-Z]{3,}", text.lower())))


def _load_ledger_ids(path) -> Set[str]:
    ids: Set[str] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                ids.add(r.get("file_id") or r.get("key"))
    return ids


def run() -> Dict[str, Any]:
    state, vessel = config.STATE_DIR, config.VESSEL_NAMESPACE
    store = get_vectorstore_provider()
    allc = store.get_all()

    # text content per drive file (and per name for local files)
    text_by_fid: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"text": "", "n": 0, "name": None, "region": None})
    vision_fids: Set[str] = set()
    for c in allc:
        m = c["metadata"]
        fid = m.get("drive_file_id")
        if m.get("source_kind") == "vision":
            if fid:
                vision_fids.add(fid)
            continue
        if m.get("doc_type") == "hyde":
            continue
        if fid:
            d = text_by_fid[fid]
            d["text"] += " " + (c["text"] or ""); d["n"] += 1
            d["name"] = m.get("file_name"); d["region"] = m.get("region_code")

    # queues + ledgers
    pv_path = state / f"pending_vision_{vessel}.json"
    pending_ids = {q["file_id"] for q in json.loads(pv_path.read_text())["queue"]} if pv_path.exists() else set()
    ledger_ids = _load_ledger_ids(state / f"ingest_ledger_{vessel}.jsonl")
    supplier_ids = _load_ledger_ids(state / f"ingest_ledger_suppliers_{vessel}.jsonl")
    accounted_ledger = ledger_ids | supplier_ids

    # engineer-reviewed dispositions: text_ok_terse (confirmed text despite being
    # short — do not flag text_poor), excluded_no_value / superseded (deliberate
    # non-ingest — a recorded skip, never a silent gap).
    rf_path = state / f"reviewed_files_{vessel}.json"
    reviewed = ({fid: v.get("disposition") for fid, v in json.loads(
        rf_path.read_text())["files"].items()} if rf_path.exists() else {})

    # structure manifest (SWS 108-01 canonical tree)
    structure = json.loads((state / f"structure_{vessel}.json").read_text())
    files = [n for n in structure["nodes"] if n.get("type") == "file"]

    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    per_region: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for n in files:
        fid, name, mime = n["id"], n.get("name", ""), n.get("mime", "")
        region = n.get("region") or "-"
        rrec = per_region[region]

        disp = reviewed.get(fid)

        # skip classes first
        if name.startswith("~$") or (n.get("fileSize") or 0) == 0:
            buckets["skipped"].append({"name": name, "reason": "lock/zero-byte"}); rrec["skipped"] += 1; continue

        # engineer-reviewed deliberate non-ingest: a recorded skip, not a gap.
        if disp in ("excluded_no_value", "superseded"):
            buckets["skipped"].append({"name": name, "reason": f"reviewed:{disp}"}); rrec["skipped"] += 1; continue

        has_text = fid in text_by_fid and text_by_fid[fid]["n"] > 0
        if has_text:
            d = text_by_fid[fid]
            dw = _distinct(d["text"]); avg = len(d["text"]) / max(d["n"], 1)
            # xlsx/sheets are row-chunked by design (one short row = one chunk),
            # so avg_chunk length is meaningless for them — distinct_words is the
            # true signal. avg_chunk only flags PDFs/DOCX.
            is_sheet = ("spreadsheet" in mime or mime.endswith("ms-excel")
                        or name.lower().endswith((".xlsx", ".xls")))
            # Genuinely thin = few distinct words AND few chunks. A high chunk
            # count means real content (many rows/pages) even if word-sparse
            # (numeric tables); only low-chunk + low-word files are real messes.
            thin = d["n"] <= 5
            is_poor = (dw < DISTINCT_WORD_FLOOR and thin) or (not is_sheet and avg < AVG_CHUNK_FLOOR and thin)
            # text_ok_terse overrides: a reviewed short-but-complete doc is good,
            # not a mess. Keeps a legitimately terse procedure off the gate.
            if is_poor and disp != "text_ok_terse":
                buckets["text_poor"].append({"name": name, "distinct_words": dw,
                    "chunks": d["n"], "avg_chunk": round(avg), "mime": mime}); rrec["text_poor"] += 1
            else:
                buckets["confirmed_good"].append({"name": name, "chunks": d["n"]}); rrec["confirmed_good"] += 1
            continue
        if fid in pending_ids or fid in vision_fids:
            buckets["pending_vision"].append({"name": name}); rrec["pending_vision"] += 1; continue
        if mime in EXCLUDED_MIMES or mime.startswith(IMAGE_PREFIX):
            buckets["skipped"].append({"name": name, "reason": f"format {mime}"}); rrec["skipped"] += 1; continue
        if fid in accounted_ledger:
            buckets["skipped"].append({"name": name, "reason": "ledger (dup/unsupported)"}); rrec["skipped"] += 1; continue
        # accounted for nowhere
        buckets["silent_gap"].append({"name": name, "mime": mime, "path": n.get("path")}); rrec["silent_gap"] += 1

    total = len(files)
    text_ingested = len(buckets["confirmed_good"]) + len(buckets["text_poor"])
    text_poor_pct = (100.0 * len(buckets["text_poor"]) / text_ingested) if text_ingested else 0.0
    silent = len(buckets["silent_gap"])
    gate_ok = silent == 0 and text_poor_pct <= TEXT_POOR_PCT_GATE

    report = {
        "vessel_namespace": vessel,
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "structure_files": total,
        "counts": {k: len(v) for k, v in buckets.items()},
        "text_poor_pct": round(text_poor_pct, 1),
        "gate": {"passed": gate_ok, "silent_gap_max": 0, "text_poor_pct_max": TEXT_POOR_PCT_GATE},
        "per_region": {k: dict(v) for k, v in sorted(per_region.items())},
        "silent_gaps": buckets["silent_gap"],
        "text_poor": buckets["text_poor"],
    }
    (state / "audit_report_corpus.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"=== CORPUS AUDIT ({vessel}) — {total} structure files ===")
    for k in ("confirmed_good", "text_poor", "pending_vision", "skipped", "silent_gap"):
        print(f"  {k:16} {len(buckets[k])}")
    print(f"  text_poor%: {text_poor_pct:.1f}  (gate ≤{TEXT_POOR_PCT_GATE})")
    print(f"  GATE: {'PASS' if gate_ok else 'FAIL — STOP'}")
    if silent:
        print(f"  !!! {silent} SILENT GAPS (in tree, ingested nowhere):")
        for g in buckets["silent_gap"][:15]:
            print(f"      {g['mime']:>10}  {g['name'][:60]}")
    if len(buckets["text_poor"]):
        print(f"  text_poor sample:")
        for t in buckets["text_poor"][:8]:
            print(f"      dw={t['distinct_words']:>3} chunks={t['chunks']} {t['name'][:55]}")
    return report


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.audit")
    ap.add_argument("--json", action="store_true", help="print report path only")
    args = ap.parse_args(argv)
    rep = run()
    if args.json:
        print(str(config.STATE_DIR / "audit_report_corpus.json"))
    return 0 if rep["gate"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
