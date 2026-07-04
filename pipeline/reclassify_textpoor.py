"""
Reclassify text-poor files: drawings/scans that text-ingestion reduced to near-
nothing (logo, stray coordinates) but were flagged "ingested". Purge their garbage
chunks and add them to the pending_vision queue so the vision pass reads them
properly.

This is the remediation for the 173-file mess the content audit found; the gate in
ingest_drive (MIN_USEFUL_TOKENS) prevents recurrence going forward.

CLI:
    python -m pipeline.reclassify_textpoor --dry-run   # list, no changes
    python -m pipeline.reclassify_textpoor             # purge + re-queue
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

import config
from providers.vectorstore import get_vectorstore_provider

DISTINCT_WORD_FLOOR = 60   # files below this many distinct alphabetic words are text-poor


def _distinct(text: str) -> int:
    return len(set(w for w in re.findall(r"[a-zA-Z]{3,}", text.lower())))


def run(dry_run: bool = False) -> Dict[str, Any]:
    state, vessel = config.STATE_DIR, config.VESSEL_NAMESPACE
    store = get_vectorstore_provider()
    allc = store.get_all()

    # Group non-vision, non-hyde chunks by file.
    byfile: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"text": "", "n": 0, "hash": None, "drive_id": None, "meta": None})
    for c in allc:
        m = c["metadata"]
        if m.get("doc_type") == "hyde" or m.get("source_kind") == "vision":
            continue
        f = m.get("file_name")
        if not f:
            continue
        d = byfile[f]
        d["text"] += " " + (c["text"] or "")
        d["n"] += 1
        d["hash"] = m.get("file_hash")
        d["drive_id"] = m.get("drive_file_id")
        d["meta"] = m

    text_poor = {f: d for f, d in byfile.items() if _distinct(d["text"]) < DISTINCT_WORD_FLOOR}

    # placements give mime/ext/path for queue entries.
    placements = {p["file_id"]: p for p in json.loads(
        (state / f"placements_{vessel}.json").read_text())["placements"]}

    to_queue: List[Dict[str, Any]] = []
    local_only: List[str] = []      # text-poor but not a Drive file → needs local-vision path
    non_visual: List[str] = []      # text-poor xlsx/docx → genuinely sparse data, NOT a drawing
    for f, d in text_poor.items():
        fid = d["drive_id"]
        if not fid:
            local_only.append(f)
            continue
        p = placements.get(fid)
        m = d["meta"]
        mime = (p or {}).get("mime", "application/pdf")
        if not (mime == "application/pdf" or mime.startswith("image/")):
            non_visual.append(f)      # spreadsheet/doc that's just sparse — vision won't help
            continue
        to_queue.append({
            "file_id": fid, "name": f,
            "path": (p or {}).get("path") or m.get("file_path"),
            "mime": (p or {}).get("mime", "application/pdf"),
            "ext": (p or {}).get("ext"),
            "region_code": m.get("region_code"), "region_label": m.get("region_label"),
            "subsystem_code": m.get("subsystem_code"),
            "subsystem_label": m.get("subsystem_label"),
            "equipment_id": m.get("equipment_id"), "equipment_name": m.get("equipment_name"),
            "doc_type": m.get("doc_type"),
            "reason": "reclassified: text-poor drawing/scan (audit)",
        })

    print(f"text-poor files: {len(text_poor)}  | drive-requeued (pdf/image): {len(to_queue)}  | "
          f"non-visual flagged (xlsx/docx): {len(non_visual)}  | local-only: {len(local_only)}")
    if dry_run:
        for q in to_queue[:12]:
            print(f"  REQUEUE  {q['name'][:60]}")
        for f in non_visual:
            print(f"  NON-VISUAL (review)  {f[:60]}")
        for f in local_only:
            print(f"  LOCAL    {f[:60]}")
        return {"text_poor": len(text_poor), "requeued": len(to_queue),
                "non_visual": non_visual, "local_only": local_only}

    # 1) Purge garbage chunks ONLY for files being re-queued to vision (their
    #    logo/coordinate chunk is worthless and will be replaced). Leave the
    #    non-visual/local flagged files untouched for review.
    requeued_names = {q["name"] for q in to_queue}
    purged = 0
    for f, d in text_poor.items():
        if f in requeued_names and d["hash"]:
            purged += store.delete_where({"file_hash": d["hash"]})

    # 2) Merge into the pending_vision queue (dedup by file_id).
    pv_path = state / f"pending_vision_{vessel}.json"
    existing = json.loads(pv_path.read_text())["queue"] if pv_path.exists() else []
    have = {q["file_id"] for q in existing}
    added = [q for q in to_queue if q["file_id"] not in have]
    merged = existing + added
    pv_path.write_text(json.dumps({"vessel_namespace": vessel, "count": len(merged),
                                   "queue": merged}, indent=2, ensure_ascii=False),
                       encoding="utf-8")

    report = {
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "text_poor_files": len(text_poor), "chunks_purged": purged,
        "added_to_vision_queue": len(added), "new_queue_total": len(merged),
        "non_visual_flagged": non_visual, "local_only_flagged": local_only,
    }
    (state / f"reclassify_report_{vessel}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"PURGED {purged} garbage chunks · added {len(added)} files to vision queue "
          f"(now {len(merged)}) · {len(local_only)} local-only flagged")
    return report


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.reclassify_textpoor")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    run(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
