"""
Drive-aware corpus ingest with Register placement + reconciliation.

Reads placements_<vessel>.json (every file + its region->subsystem->equipment->
doc_type lineage), pulls each text-extractable file live from Drive, and ingests
it through the existing pipeline with the placement merged into every chunk's
metadata. Images / CAD / scanned-PDFs are recorded in a pending_vision queue for
Part 2 — counted and placed, never dropped.

RESUMABLE: every processed file is appended to a ledger (ingest_ledger_<vessel>.
jsonl) with its outcome bucket. A re-run loads the ledger and skips processed
files WITHOUT re-downloading, so a killed run resumes cheaply and the final report
can be rebuilt from the ledger at any time. The store is also scanned for
drive_file_ids ingested before the ledger existed (seeded in).

Every file lands in exactly one bucket, and the run reconciles or STOPS:

    placements == ingested + already_present + pending_vision + unsupported + errors

Outputs:
  ingest_ledger_<vessel>.jsonl     append-only processed log (survives kills)
  ingestion_report_<vessel>.json   per-bucket + per-region counts, skip reasons
  pending_vision_<vessel>.json     queue for the Part 2 vision pipeline

CLI:
    python -m pipeline.ingest_drive --dry-run     # classify only, no cost
    python -m pipeline.ingest_drive               # full run (resumes if interrupted)
    python -m pipeline.ingest_drive --report-only # rebuild report from the ledger
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import config
from providers.structure import GoogleDriveStructureProvider
from providers.embeddings import get_embedding_provider
from providers.vectorstore import get_vectorstore_provider
from pipeline.ingest import ingest_file

_LOG_PATH = config.LOGS_DIR / "ingest_drive.log"
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[logging.FileHandler(_LOG_PATH, encoding="utf-8"),
              logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("pipeline.ingest_drive")

MIN_USEFUL_TOKENS = 120   # whole-file token floor; below = text-poor → route to vision

TEXT_MIMES = {
    "application/pdf": ("pdf", ".pdf"),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ("xlsx", ".xlsx"),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ("docx", ".docx"),
    "application/vnd.google-apps.document": ("gdoc", ".docx"),
    "application/vnd.google-apps.spreadsheet": ("gsheet", ".xlsx"),
    "text/csv": ("csv", ".csv"),
}
VISION_PREFIXES = ("image/",)
VISION_MIMES = {"application/dxf", "application/postscript"}
UNSUPPORTED_REASON = {
    "application/vnd.ms-excel": "legacy .xls (unsupported)",
    "application/msword": "legacy .doc (unsupported)",
    "message/rfc822": "email (unsupported)",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "no pptx parser",
    "application/vnd.google-apps.presentation": "no pptx parser",
    "application/octet-stream": "unknown binary type",
}


def _classify(mime: str) -> str:
    if mime in TEXT_MIMES:
        return "text"
    if mime.startswith(VISION_PREFIXES) or mime in VISION_MIMES:
        return "vision"
    return "unsupported"


def _placement_metadata(p: Dict[str, Any]) -> Dict[str, Any]:
    raw = {
        "sfi_section": p.get("region_code"),
        "region_code": p.get("region_code"),
        "region_label": p.get("region_label"),
        "subsystem_code": p.get("subsystem_code"),
        "subsystem_label": p.get("subsystem_label"),
        "equipment_id": p.get("equipment_id"),
        "equipment_name": p.get("equipment_name"),
        "doc_type": p.get("doc_type"),
        "drive_file_id": p.get("file_id"),
        "source_kind": "drive",
    }
    return {k: v for k, v in raw.items() if v not in (None, "")}


def _load_placements(regions, limit):
    state, vessel = config.STATE_DIR, config.VESSEL_NAMESPACE
    structure = json.loads((state / f"structure_{vessel}.json").read_text())
    placements = json.loads(
        (state / f"placements_{vessel}.json").read_text())["placements"]
    if regions:
        placements = [p for p in placements if p.get("region_code") in regions]
    if limit:
        placements = placements[:limit]
    return structure, placements


def _build_report(placements, ledger) -> Dict[str, Any]:
    """Reconcile in-scope placements against the ledger."""
    scope = {p["file_id"] for p in placements}
    recs = [ledger[fid] for fid in scope if fid in ledger]
    buckets: Dict[str, int] = defaultdict(int)
    per_region: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    chunks = 0
    for r in recs:
        buckets[r["bucket"]] += 1
        per_region[r.get("region", "—")][r["bucket"]] += 1
        chunks += int(r.get("chunks", 0))
    total = len(placements)
    accounted = len(recs)
    pending = [r for r in recs if r["bucket"] == "pending_vision"]
    return {
        "vessel_namespace": config.VESSEL_NAMESPACE,
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_in_scope": total,
        "accounted": accounted,
        "remaining": total - accounted,
        "reconciled": accounted == total,
        "chunks_ingested": chunks,
        "buckets": dict(buckets),
        "per_region": {k: dict(v) for k, v in per_region.items()},
        "unsupported": [r for r in recs if r["bucket"] == "unsupported"],
        "errors": [r for r in recs if r["bucket"] == "error"],
        "pending_vision_count": len(pending),
    }, pending


def _write_outputs(report, pending):
    state, vessel = config.STATE_DIR, config.VESSEL_NAMESPACE
    (state / f"ingestion_report_{vessel}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (state / f"pending_vision_{vessel}.json").write_text(
        json.dumps({"vessel_namespace": vessel, "count": len(pending),
                    "queue": pending}, indent=2, ensure_ascii=False),
        encoding="utf-8")


def run(regions: Optional[List[str]] = None, limit: Optional[int] = None,
        dry_run: bool = False, report_only: bool = False) -> Dict[str, Any]:
    state, vessel = config.STATE_DIR, config.VESSEL_NAMESPACE
    structure, placements = _load_placements(regions, limit)
    total = len(placements)
    ledger_path = state / f"ingest_ledger_{vessel}.jsonl"

    # Load existing ledger.
    ledger: Dict[str, Dict[str, Any]] = {}
    if ledger_path.exists():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                ledger[r["file_id"]] = r

    if dry_run:
        kinds = defaultdict(int)
        for p in placements:
            kinds[_classify(p.get("mime", ""))] += 1
        logger.info("[DRY RUN] %d files: %s", total, dict(kinds))
        return {"total": total, "classification": dict(kinds)}

    if report_only:
        report, pending = _build_report(placements, ledger)
        _write_outputs(report, pending)
        logger.info("[REPORT ONLY] %s", report["buckets"])
        return report

    store = get_vectorstore_provider()
    embedder = get_embedding_provider()
    provider = GoogleDriveStructureProvider(structure["root_id"], structure["root_name"])

    ledger_fh = open(ledger_path, "a", encoding="utf-8")

    def record(rec: Dict[str, Any]) -> None:
        ledger[rec["file_id"]] = rec
        ledger_fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        ledger_fh.flush()

    # Seed ledger from files already in the store (ingested before the ledger).
    for c in store.get_all(where={"source_kind": "drive"}):
        fid = c["metadata"].get("drive_file_id")
        if fid and fid not in ledger:
            record({"file_id": fid, "bucket": "ingested",
                    "region": c["metadata"].get("region_code") or "—",
                    "name": c["metadata"].get("file_name", ""), "seeded": True})

    tmpdir = Path(tempfile.mkdtemp(prefix="engo_ingest_"))
    start_done = sum(1 for p in placements if p["file_id"] in ledger)
    logger.info("Resume: %d/%d already processed; %d to go.",
                start_done, total, total - start_done)

    for i, p in enumerate(placements, 1):
        fid = p["file_id"]
        if fid in ledger:
            continue
        mime = p.get("mime", "")
        kind = _classify(mime)
        region = p.get("region_code") or "—"

        # macOS AppleDouble resource-fork stubs ('._<name>') are not documents —
        # the 2026-06-09 run's 6 "errors" were all these. Skip explicitly.
        if p.get("name", "").startswith("._"):
            record({"file_id": fid, "bucket": "skipped", "region": region,
                    "name": p["name"], "reason": "macOS AppleDouble stub (._)"})
            continue

        if kind == "vision":
            record({"file_id": fid, "bucket": "pending_vision", "region": region,
                    "name": p["name"], "path": p["path"], "mime": mime,
                    "equipment_name": p.get("equipment_name")})
            continue
        if kind == "unsupported":
            record({"file_id": fid, "bucket": "unsupported", "region": region,
                    "name": p["name"], "reason": UNSUPPORTED_REASON.get(mime, "unsupported")})
            continue

        _, suffix = TEXT_MIMES[mime]
        tmp = tmpdir / f"{fid}{suffix}"
        try:
            data, _ = provider.download_bytes(fid, mime)
            tmp.write_bytes(data)
            summary = ingest_file(
                tmp, extra_metadata=_placement_metadata(p),
                display_name=p["name"], display_path=p["path"],
                store=store, embedder=embedder)
            # A vector drawing / scan can parse to a FEW garbage chars (a logo,
            # stray coordinates) → >0 chunks but no usable text. Gate on content,
            # not just chunk count: text-poor files go to vision, and the garbage
            # chunk is purged so it can't pollute retrieval.
            text_poor = (0 < summary["chunks_created"]
                         and summary.get("tokens_total", 0) < MIN_USEFUL_TOKENS)
            if summary["skipped"]:
                record({"file_id": fid, "bucket": "already_present",
                        "region": region, "name": p["name"]})
            elif summary["chunks_created"] == 0 or text_poor:
                if text_poor:
                    store.delete_where({"file_hash": summary["file_hash"]})
                record({"file_id": fid, "bucket": "pending_vision", "region": region,
                        "name": p["name"], "path": p["path"], "mime": mime,
                        "reason": ("text-poor (<%d tokens) — vector drawing/scan"
                                   % MIN_USEFUL_TOKENS) if text_poor
                                  else "no extractable text (scanned)",
                        "equipment_name": p.get("equipment_name")})
            else:
                record({"file_id": fid, "bucket": "ingested", "region": region,
                        "name": p["name"], "chunks": summary["chunks_created"]})
        except Exception as e:
            record({"file_id": fid, "bucket": "error", "region": region,
                    "name": p["name"], "error": str(e)})
            logger.warning("ingest failed: %s — %s", p["name"], e)
        finally:
            tmp.unlink(missing_ok=True)

        done = sum(1 for q in placements if q["file_id"] in ledger)
        if done % 25 == 0:
            logger.info("progress %d/%d done", done, total)

    ledger_fh.close()
    report, pending = _build_report(placements, ledger)
    _write_outputs(report, pending)
    logger.info("DONE. total=%d accounted=%d reconciled=%s buckets=%s",
                report["total_in_scope"], report["accounted"],
                report["reconciled"], report["buckets"])
    if not report["reconciled"]:
        logger.error("RECONCILE: %d remaining — re-run to finish.", report["remaining"])
    return report


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.ingest_drive")
    ap.add_argument("--region", action="append", default=[])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args(argv)
    rep = run(regions=args.region or None, limit=args.limit,
              dry_run=args.dry_run, report_only=args.report_only)
    if args.dry_run:
        return 0
    return 0 if rep.get("reconciled") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
