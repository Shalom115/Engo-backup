"""
Authority-flagged ingest for the "80, Handover notes" folder (Block C).

These are engineer-knowledge / delivery-condition documents OUTSIDE the SWS
108-01 system tree, so they carry no inherited placement and need an explicit
authority tier (the system prompt's HANDOVER NOTES AUTHORITY hierarchy acts on
it), procedure-aware chunking (numbered procedures / reference tables stay whole),
and a dating treatment.

Dating treatment (engineer mandate): a document is dated by its OWN internal /
authored date — extracted from its title or content — not by its file mtime
(which only reflects when it was last touched in Drive). A doc with no internal
date is marked authored_date="unknown" and doc_temporality="standing_reference"
so the recency logic treats it as timeless procedural content, never as a dated
snapshot.

Reconciled against the live folder (1xEO3Yc…, 7 files). Per engineer:
  SY Gelliceaux Hand Over.pdf              high    procedure-aware (local, already in)
  HANDOVER April 2024.docx                 medium  recently-modified -> currency_flag
  Diagnostics and testing with BAE.docx    medium  plain text (terse), reviewed: no vision
  108-01_Lanzarote_list_20231123.xlsx      low     dated snag list, supersedes undated IDs
  3x Tasks PreHandOver xlsx                 —       PM content, no eng value: EXCLUDE
  (2 undated Lanzarote IDs)                 —       SUPERSEDED by the dated list

Excluded / superseded files are written to reviewed_files_<vessel>.json so the
standing audit gate treats them as deliberate dispositions, not silent gaps.

CLI:
    python -m pipeline.ingest_handover            # apply everything
    python -m pipeline.ingest_handover --dry-run  # resolve + date + report, no writes
"""
from __future__ import annotations

import argparse
import calendar
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Optional

import config
from pipeline.chunk import chunk_procedures
from pipeline.ingest import ingest_file
from providers.embeddings import get_embedding_provider
from providers.structure import GoogleDriveStructureProvider
from providers.vectorstore import get_vectorstore_provider

HANDOVER_FOLDER_ID = "1xEO3Yc49tKazxEt5dcUGHvXZMp8VrKm_"  # "80, Handover notes"

_HANDOVER_PLACEMENT = {
    "region_code": "001", "region_label": "General Condition",
    "subsystem_code": "080", "subsystem_label": "Handover notes",
    "sfi_section": "001", "source_kind": "handover", "doc_type": "handover",
}
_SNAG_PLACEMENT = {
    "region_code": "001", "region_label": "General Condition",
    "sfi_section": "001", "source_kind": "snag", "doc_type": "snag_list",
}
_PROC_CHUNKER = partial(chunk_procedures, chunk_size_tokens=1200, overlap_tokens=80)

_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}


def extract_authored_date(text: str, filename: str = "") -> Optional[str]:
    """
    The document's own authored date from its title/content. Returns an ISO-ish
    string (YYYY, YYYY-MM, or YYYY-MM-DD) or None if no internal date is present.
    Boundaries are digit-aware so 'list_20231123' resolves (underscore is a word
    char, so \\b would miss it). Most→least specific.
    """
    hay = (filename or "") + "\n" + (text or "")[:4000]
    m = re.search(r"(?<!\d)(20[12]\d)[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])(?!\d)", hay)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(?<!\d)(20[12]\d)(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)", hay)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"\b(" + "|".join(_MONTHS) + r")\s+(20[12]\d)\b", hay, re.I)
    if m:
        return f"{m.group(2)}-{_MONTHS[m.group(1).lower()]:02d}"
    m = re.search(r"(?<!\d)(20(1[89]|2[0-7]))(?!\d)", hay)
    if m:
        return m.group(1)
    return None


def _peek_text(path: Path) -> str:
    """Cheap content peek for date extraction when the title carries none."""
    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf":
            from pipeline.parsers import parse_pdf
            return " ".join(p["text"] for p in parse_pdf(path)["pages"][:3])
        if suffix == ".docx":
            from pipeline.parsers import parse_docx
            return " ".join(s["text"] for s in parse_docx(path)["sections"][:6])
        if suffix == ".xlsx":
            from pipeline.parsers import parse_xlsx
            return " ".join(r["text"] for r in parse_xlsx(path)["rows"][:12])
    except Exception:
        return ""
    return ""


def _dating_meta(path: Path, display_name: str) -> Dict[str, Any]:
    """authored_date + doc_temporality, title first then a content peek."""
    date = extract_authored_date("", display_name) or extract_authored_date(_peek_text(path), display_name)
    if date:
        return {"authored_date": date, "doc_temporality": "dated_snapshot"}
    return {"authored_date": "unknown", "doc_temporality": "standing_reference"}


# ---- Specs ------------------------------------------------------------------

def _ingest_specs() -> List[Dict[str, Any]]:
    return [
        {
            "label": "Hand Over PDF",
            "local": str(Path("~/Downloads/SY Gelliceaux Hand Over.pdf").expanduser()),
            "display_name": "SY Gelliceaux Engineering Handover Notes 2025.pdf",
            "drive_id": "1URsSPh4ShhQpn1hzROPtpCyJJqnBHqzX",
            "replace_names": ["SY Gelliceaux Engineering Handover Notes 2025.pdf",
                              "SY Gelliceaux Hand Over.pdf"],
            "chunker": _PROC_CHUNKER,
            "metadata": {**_HANDOVER_PLACEMENT, "authority": "high",
                         "equipment_name": "Engineering Handover Notes"},
        },
        {
            "label": "HANDOVER April 2024.docx",
            "drive_id": "1PdG0bt99vENTRocL883r0jWlzxzSeO8R",
            "display_name": "HANDOVER April 2024.docx",
            "metadata": {**_HANDOVER_PLACEMENT, "authority": "medium",
                         "currency_flag": True,
                         "equipment_name": "Handover (working doc)"},
        },
        {
            "label": "Diagnostics and testing with BAE.docx",
            "drive_id": "1MFslS1QcpLohoLGr1i1l1WhUuGuwWq4h",
            "display_name": "Diagnostics and testing with BAE.docx",
            "metadata": {**_HANDOVER_PLACEMENT, "authority": "medium",
                         "doc_type": "procedure",
                         "equipment_name": "BAE diagnostics & testing"},
        },
        {
            "label": "Lanzarote snag list (dated 2023-11-23)",
            "drive_id": "10G3k2rj0BUjqXRbuismQ19YlN5p1oXUi",
            "display_name": "108-01_Lanzarote_list_20231123.xlsx",
            "metadata": {**_SNAG_PLACEMENT, "authority": "low", "delivery_only": True,
                         "equipment_name": "Lanzarote delivery snag list"},
        },
    ]


# Reviewed dispositions (no ingest). Written to reviewed_files_<vessel>.json.
_EXCLUDED = {
    "1Pvx7Dpbp2kvdcVr4LaO7UCSqlQs7CRrA": "SWS108-01 - Tasks PreHandOver - 26MAY2023.xlsx",
    "1hL2qmRVyux8eXO-ndw-fiFjEJ8gcAhQT": "SWS108-01 - Tasks PreHandOver - 28 APR2023.xlsx",
    "1qrUQCouO9wEfzhf1k0gmPf3R4WPyamCl": "SWS108-01 - Tasks PreHandOver - 31MAR2023SA.xlsx",
}
_SUPERSEDED = {
    "1QrdQXoYXE5T5o8vSderPQJSX6Xr6HuWx": "Lanzarote list (undated, no STATUS column)",
    "1PrwrheGWD5Lw8FPhfD5xWZ7LDOn29eG_": "Lanzarote list (undated, no STATUS column)",
}
# The terse-but-complete text doc that must not be flagged text_poor or vision-queued.
_REVIEWED_TEXT_OK = {
    "1MFslS1QcpLohoLGr1i1l1WhUuGuwWq4h": "Diagnostics and testing with BAE.docx",
}


def _write_registry() -> Path:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    files: Dict[str, Any] = {}
    for fid, name in _REVIEWED_TEXT_OK.items():
        files[fid] = {"name": name, "disposition": "text_ok_terse",
                      "note": "plain structured text, terse — confirmed no vision needed",
                      "reviewed_at": now}
    for fid, name in _EXCLUDED.items():
        files[fid] = {"name": name, "disposition": "excluded_no_value",
                      "note": "pre-delivery PM content (contracts/spares/insurance) — no engineering value",
                      "reviewed_at": now}
    for fid, name in _SUPERSEDED.items():
        files[fid] = {"name": name, "disposition": "superseded",
                      "note": "replaced by 108-01_Lanzarote_list_20231123.xlsx (dated, has STATUS; CAN bus H resolved 2023)",
                      "reviewed_at": now}
    reg = {"vessel_namespace": config.VESSEL_NAMESPACE, "updated_at": now, "files": files}
    out = config.STATE_DIR / f"reviewed_files_{config.VESSEL_NAMESPACE}.json"
    out.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def _resolve_drive(provider, spec) -> Optional[Path]:
    try:
        meta = provider.file_meta(spec["drive_id"])
    except Exception as e:
        spec["error"] = f"{type(e).__name__}: {str(e).splitlines()[0][:120]}"
        return None
    data, suffix = provider.download_bytes(meta["id"], meta["mimeType"])
    ext = suffix or Path(spec["display_name"]).suffix
    tmp = Path(tempfile.gettempdir()) / f"engo_handover_{spec['drive_id']}{ext}"
    tmp.write_bytes(data)
    return tmp


def run(dry_run: bool = False) -> Dict[str, Any]:
    store = get_vectorstore_provider()
    embedder = get_embedding_provider()
    drive: Optional[GoogleDriveStructureProvider] = None
    report: Dict[str, Any] = {"ingested": [], "inaccessible": [], "dry_run": dry_run}

    for spec in _ingest_specs():
        label = spec["label"]
        if "local" in spec and Path(spec["local"]).exists():
            path = Path(spec["local"])
        elif "drive_id" in spec:
            if drive is None:
                drive = GoogleDriveStructureProvider(root_id=HANDOVER_FOLDER_ID)
            path = _resolve_drive(drive, spec)
            if path is None:
                report["inaccessible"].append({"label": label, "drive_id": spec["drive_id"],
                                               "reason": spec.get("error")})
                print(f"  INACCESSIBLE  {label}: {spec.get('error')}")
                continue
        else:
            report["inaccessible"].append({"label": label, "reason": "no reachable source"})
            print(f"  INACCESSIBLE  {label}: no reachable source")
            continue

        meta = dict(spec["metadata"])
        meta.update(_dating_meta(path, spec["display_name"]))
        if "drive_id" in spec:
            meta["drive_file_id"] = spec["drive_id"]

        if dry_run:
            print(f"  OK (dry-run)  {label} -> {path.name}  authority={meta['authority']} "
                  f"authored_date={meta['authored_date']} ({meta['doc_temporality']})")
            continue

        purged = 0
        for name in spec.get("replace_names", []):
            purged += store.delete_by_source(name)
        if "drive_id" in spec:
            purged += store.delete_where({"drive_file_id": spec["drive_id"]})

        summary = ingest_file(
            path, extra_metadata=meta,
            display_name=spec["display_name"],
            display_path=spec.get("local") or f"gdrive://{spec['drive_id']}",
            chunker_override=spec.get("chunker"),
            store=store, embedder=embedder,
        )
        report["ingested"].append({
            "label": label, "display_name": spec["display_name"],
            "authority": meta["authority"], "authored_date": meta["authored_date"],
            "doc_temporality": meta["doc_temporality"],
            "chunks": summary["chunks_created"], "tokens": summary["tokens_total"],
            "purged": purged, "skipped": summary["skipped"],
        })
        print(f"  INGESTED      {label}: {summary['chunks_created']} chunks "
              f"(purged {purged}), authority={meta['authority']}, "
              f"date={meta['authored_date']}")

    reg_path = _write_registry()
    report["registry"] = str(reg_path)
    print(f"\n  reviewed-files registry -> {reg_path}")
    print(f"    text_ok_terse: {len(_REVIEWED_TEXT_OK)}  excluded: {len(_EXCLUDED)}  superseded: {len(_SUPERSEDED)}")

    out = config.STATE_DIR / f"handover_ingest_{config.VESSEL_NAMESPACE}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  report -> {out}")
    return report


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.ingest_handover")
    ap.add_argument("--dry-run", action="store_true", help="resolve + date + report, no writes")
    args = ap.parse_args(argv)
    print(f"=== Handover/delivery ingest ({config.VESSEL_NAMESPACE}) ===")
    rep = run(dry_run=args.dry_run)
    print(f"\nSUMMARY: ingested={len(rep['ingested'])}  inaccessible={len(rep['inaccessible'])}")
    return 1 if rep["inaccessible"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
