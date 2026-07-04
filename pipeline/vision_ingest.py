"""
Vision ingestion — drains the pending_vision queue and mines figures out of
already-text-ingested documents. Block 2 Part 2.

Two queues, one discipline (ledger-resumable, reconcile-or-stop, checkpointed):

  QUEUE A — pending_vision_<vessel>.json: standalone images, scanned PDFs, and
            schematic PDFs that yielded no text. DWG/DXF/PS are EXCLUDED with
            per-equipment visibility in the report (format not convertible yet).
  QUEUE B — figure-bearing pages hiding inside documents the TEXT ingest already
            processed (investigation-report figures, schematics with text layers).
            Classified free first (--classify-b), priced, then described.

Identity: everything keys on file_hash (same identity the text ingest uses), with
drive_file_id carried alongside. Queue B compares the downloaded hash against the
file_hash on the document's existing text chunks — a mismatch flags `stale_text`
(file changed since text ingest) rather than silently proceeding.

CHECKPOINT (engineer-mandated second gate): a full run STOPS after the first
--checkpoint N files (default 75), writes vision_checkpoint_<vessel>.json with a
random sample of the descriptions it just stored, and exits. The engineer
spot-checks quality before the remaining spend is authorized (resume = rerun).

Chunks: description (+verbatim transcription) is the searchable text; metadata
carries placement (region/subsystem/equipment/doc_type), locator (page for PDF,
figure_index+section_title for DOCX), content_type, image_path (original render
kept on disk for the mark-the-component feature), and vision_components (JSON:
label/bbox/confidence/note per component — the locate layer).

CLI:
    python -m pipeline.vision_ingest --validate          # the 5-gate slice
    python -m pipeline.vision_ingest --queue-a [--checkpoint 75]
    python -m pipeline.vision_ingest --classify-b        # free, emits queue+price
    python -m pipeline.vision_ingest --queue-b [--checkpoint 75]
    python -m pipeline.vision_ingest --report-only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import random
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import config
from providers.structure import GoogleDriveStructureProvider
from providers.embeddings import get_embedding_provider
from providers.vectorstore import get_vectorstore_provider
from providers.vision import get_vision_provider
from providers.storage import get_storage_provider
from pipeline import visual_extract as vx
from pipeline.glossary_correct import (correct_text, correct_components,
                                       load_glossary, CorrectionsLog)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[logging.FileHandler(config.LOGS_DIR / "vision_ingest.log", encoding="utf-8"),
              logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("pipeline.vision_ingest")

IMAGES_DIR = config.DATA_DIR / "images" / config.VESSEL_NAMESPACE
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

EXCLUDED_FORMATS = {"image/vnd.dwg": "dwg", "application/dxf": "dxf",
                    "application/postscript": "ps"}
SCANNED_TEXT_THRESHOLD = 50      # chars/page below this = no usable text layer
IMAGE_MIMES_PREFIX = "image/"


# ---------------------------------------------------------------------------
# Kind routing — the placement's doc_type folder + name decide the prompt.
# ---------------------------------------------------------------------------

# Drawing kinds get whole-page rasterization (vector or scanned). _PROTOCOL_KINDS
# are the kinds that carry their own reading protocol and must NOT be downgraded to
# the generic document_page/figure prompt when routed through a multi-page PDF.
_WHOLEPAGE_KINDS = ("schematic", "electrical_diagram", "plumbed_diagram",
                    "general_arrangement")
_PROTOCOL_KINDS = _WHOLEPAGE_KINDS + ("certificate",)


def route_kind(name: str, mime: str, doc_type: Optional[str],
               region: Optional[str] = None) -> str:
    """Pick the reading protocol from the file name, doc-type folder, and region."""
    n = name.lower()
    dt = (doc_type or "").lower()
    is_drawing = (any(k in dt for k in ("schematic", "drawing")) or
                  any(k in n for k in ("schematic", "wiring", "diagram", "p&id", "p&amp;id")))
    # General arrangement (system/vessel-level map)
    if "general arrangement" in n or re.search(r"\bga\b", n) or n.endswith("-general") \
       or "-general" in n or " ga." in n:
        return "general_arrangement"
    # Plumbed systems — fluid side
    if any(k in n for k in ("bilge", "fire", "fuel", "water", "hydraulic",
                            "pneumatic", "cooling", "sea water", "seawater", "exhaust")) \
       and (is_drawing or "schematic" in n or "diagram" in n):
        return "plumbed_diagram"
    # Electrical — anything with cables; region 600 drawings default here
    if is_drawing and (region == "600" or any(k in n for k in
            ("electric", "wiring", "gmms", "gm marine", "lvpdu", "hvpdu", "panel",
             "power", "dc ", "ac ", "24v", "230v", "battery", "bae"))):
        return "electrical_diagram"
    if is_drawing:
        return "schematic"
    if any(k in n for k in ("cert", "doc_", "declaration", "approval", "booklet")):
        return "certificate"
    if mime.startswith(IMAGE_MIMES_PREFIX) or "photo" in dt:
        return "photo"
    return "document_page"


def _placement_meta(p: Dict[str, Any]) -> Dict[str, Any]:
    raw = {
        "sfi_section": p.get("region_code"), "region_code": p.get("region_code"),
        "region_label": p.get("region_label"),
        "subsystem_code": p.get("subsystem_code"),
        "subsystem_label": p.get("subsystem_label"),
        "equipment_id": p.get("equipment_id"),
        "equipment_name": p.get("equipment_name"),
        "doc_type": p.get("doc_type"),
        "drive_file_id": p.get("file_id"),
    }
    return {k: v for k, v in raw.items() if v not in (None, "")}


# ---------------------------------------------------------------------------
# Core: describe one image and store it as a placed chunk.
# ---------------------------------------------------------------------------

class VisionWriter:
    def __init__(self):
        self.store = get_vectorstore_provider()
        self.embedder = get_embedding_provider()
        self.vp = get_vision_provider()
        self.image_storage = get_storage_provider()
        self.glossary = load_glossary()          # authoritative acronym expansions
        self.corrections: List[Dict[str, str]] = []  # all glossary fixes this run
        self.corr_log = CorrectionsLog()         # durable before->after audit trail
        self.stored: List[Dict[str, Any]] = []   # this-run sample pool

    def describe_store(self, image_bytes: bytes, media_type: str, kind: str, *,
                       file_hash: str, file_name: str, file_path: str,
                       locator: Dict[str, Any], placement: Dict[str, Any],
                       figure_label: str = "") -> Dict[str, Any]:
        loc_suffix = locator.get("suffix", "v0")
        image_key = f"{file_hash[:16]}_{loc_suffix}.png"
        img_path = self.image_storage.put(image_key, image_bytes, content_type=media_type)

        ctx = {"file_name": file_name,
               "system": placement.get("subsystem_label"),
               "equipment": placement.get("equipment_name")}
        desc = self.vp.describe(image_bytes, media_type, kind, context=ctx)

        # Correct free-invented acronym expansions against the vessel glossary
        # before storing (the model reads "MPCS-S" right but invents the words).
        # Transcription is left verbatim — only the model's prose is corrected.
        desc["description"], dcorr = correct_text(desc["description"], self.glossary)
        if desc.get("components"):
            desc["components"], ccorr = correct_components(desc["components"], self.glossary)
        else:
            ccorr = []
        fixes = dcorr + ccorr
        self.corrections.extend(fixes)
        if fixes:
            self.corr_log.record(fixes, context={
                "file_name": file_name,
                "drive_file_id": placement.get("drive_file_id"),
                "page": locator.get("page_number"),
                "figure": figure_label or None,
            })

        text = desc["description"]
        if desc.get("transcription"):
            text += "\n\nVisible text (verbatim): " + desc["transcription"]
        if not text.strip():
            raise ValueError("empty description")

        chunk_id = f"{file_hash}:{loc_suffix}"
        meta: Dict[str, Any] = {
            "file_hash": file_hash, "file_name": file_name, "file_path": file_path,
            "source_kind": "vision",
            "content_type": desc.get("content_type", kind),
            "read_protocol": kind,
            "figure_label": figure_label,
            "image_path": str(img_path),
            "vision_components": json.dumps(desc.get("components", [])),
            "glossary_corrections": len(fixes),
            "vision_model": desc.get("model", self.vp.model_name),
            "embedding_model": self.embedder.model_name,
            "vessel_namespace": config.VESSEL_NAMESPACE,
            "ingested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **{k: v for k, v in locator.items() if k != "suffix"},
            **placement,
        }
        vec = self.embedder.embed([text], input_type="document")[0]
        self.store.add(ids=[chunk_id], vectors=[vec], texts=[text], metadatas=[meta])
        rec = {"chunk_id": chunk_id, "file": file_name,
               "read_protocol": kind, "page_scanned": locator.get("page_scanned"),
               "figure": figure_label or loc_suffix,
               "content_type": meta["content_type"],
               "components": len(desc.get("components", [])),
               "glossary_corrections": fixes,
               "desc_preview": desc["description"][:240]}
        self.stored.append(rec)
        return rec


# ---------------------------------------------------------------------------
# Per-document processors
# ---------------------------------------------------------------------------

def process_pdf(writer: VisionWriter, pdf_bytes: bytes, *, kind_hint: str,
                file_hash: str, file_name: str, file_path: str,
                placement: Dict[str, Any]) -> Dict[str, int]:
    """Classify pages and describe what needs vision. Returns counters."""
    n_pages = vx.pdf_page_count(pdf_bytes)
    text_lens = vx.pdf_page_text_lens(pdf_bytes)
    counters = defaultdict(int)
    for i in range(n_pages):
        scanned = text_lens[i] < SCANNED_TEXT_THRESHOLD
        if kind_hint in _WHOLEPAGE_KINDS or scanned:
            # whole-page raster: drawings (vector or scanned) and scanned pages.
            png = vx.rasterize_pdf_page(pdf_bytes, i)
            # Preserve the specialized reading protocol (electrical/plumbed/GA/
            # schematic/certificate); only fall back to generic when the hint
            # carries no protocol of its own.
            kind = kind_hint if kind_hint in _PROTOCOL_KINDS \
                else ("document_page" if scanned else "figure")
            writer.describe_store(
                png, "image/png", kind,
                file_hash=file_hash, file_name=file_name, file_path=file_path,
                locator={"page_number": i + 1, "suffix": f"v{i+1}", "page_scanned": scanned},
                placement=placement, figure_label=f"p.{i+1}")
            counters["pages_described"] += 1
        else:
            # text page — describe only embedded figures
            figures = vx.pdf_embedded_images(pdf_bytes, i)
            for fn, (img, ext) in enumerate(figures, start=1):
                png, mt = vx.load_image_bytes(img, ext)
                writer.describe_store(
                    png, mt, "figure",
                    file_hash=file_hash, file_name=file_name, file_path=file_path,
                    locator={"page_number": i + 1, "suffix": f"v{i+1}f{fn}"},
                    placement=placement, figure_label=f"p.{i+1} fig {fn}")
                counters["figures_described"] += 1
    return dict(counters)


def process_docx(writer: VisionWriter, docx_bytes: bytes, *, file_hash: str,
                 file_name: str, file_path: str,
                 placement: Dict[str, Any]) -> Dict[str, int]:
    figures = vx.docx_images(docx_bytes)
    counters = defaultdict(int)
    for f in figures:
        png, mt = vx.load_image_bytes(f["bytes"], f["ext"])
        writer.describe_store(
            png, mt, "figure",
            file_hash=file_hash, file_name=file_name, file_path=file_path,
            locator={"figure_index": f["figure_index"],
                     "section_title": f["section_title"],
                     "suffix": f"vd{f['figure_index']}"},
            placement=placement, figure_label=f"figure {f['figure_index']}")
        counters["figures_described"] += 1
    return dict(counters)


def process_image(writer: VisionWriter, data: bytes, ext: str, *, kind: str,
                  file_hash: str, file_name: str, file_path: str,
                  placement: Dict[str, Any]) -> Dict[str, int]:
    png, mt = vx.load_image_bytes(data, ext)
    writer.describe_store(
        png, mt, kind,
        file_hash=file_hash, file_name=file_name, file_path=file_path,
        locator={"suffix": "v1"}, placement=placement, figure_label="image")
    return {"images_described": 1}


# ---------------------------------------------------------------------------
# Ledger + checkpoint
# ---------------------------------------------------------------------------

class Ledger:
    def __init__(self, name: str):
        self.path = config.STATE_DIR / name
        self.entries: Dict[str, Dict[str, Any]] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    self.entries[r["key"]] = r
        self._fh = open(self.path, "a", encoding="utf-8")

    def done(self, key: str) -> bool:
        return key in self.entries

    def record(self, key: str, bucket: str, **kw):
        rec = {"key": key, "bucket": bucket, **kw}
        self.entries[key] = rec
        self._fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._fh.flush()


def _targeted_sample(stored: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    A review sample that DELIBERATELY surfaces the quality-critical cases, not a
    blind random draw: one of each content_type (schematic/electrical, scanned
    document_page, figure, photo…), every CM-24-1732 investigation figure, and
    every chunk where a glossary correction fired — then random fill.
    """
    picked: Dict[str, Dict[str, Any]] = {}  # chunk_id -> rec (dedup)

    def take(rec):
        picked.setdefault(rec["chunk_id"], rec)

    # one representative per content_type (covers schematic + scanned + figure)
    seen_types: set = set()
    for r in stored:
        ct = r.get("content_type")
        if ct not in seen_types:
            seen_types.add(ct); take(r)
    # every investigation-report figure + every glossary-correction event
    for r in stored:
        if "cm-24-1732" in (r.get("file", "").lower()):
            take(r)
        if r.get("glossary_corrections"):
            take(r)
    # protocol-preservation proof: scanned pages that kept a diagram protocol
    # (pre-fix these were downgraded to document_page). Scanned ones first.
    diagram = ("electrical_diagram", "general_arrangement", "plumbed_diagram")
    proof = sorted((r for r in stored if r.get("read_protocol") in diagram),
                   key=lambda r: not r.get("page_scanned"))
    for r in proof[:3]:
        take(r)
    # random fill up to ~15
    rest = [r for r in stored if r["chunk_id"] not in picked]
    for r in random.sample(rest, min(max(0, 15 - len(picked)), len(rest))):
        take(r)
    return list(picked.values())


def _write_checkpoint(writer: VisionWriter, processed_files: int):
    out = config.STATE_DIR / f"vision_checkpoint_{config.VESSEL_NAMESPACE}.json"
    out.write_text(json.dumps({
        "written_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files_processed_this_run": processed_files,
        "chunks_stored_this_run": len(writer.stored),
        "content_type_counts": dict(_count_by(writer.stored, "content_type")),
        "glossary_corrections_total": len(writer.corrections),
        "glossary_corrections": writer.corrections[:40],
        "sample": _targeted_sample(writer.stored),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.warning("CHECKPOINT HARD STOP after %d files. Run halted — review %s "
                   "(targeted sample + glossary corrections), then re-run to continue.",
                   processed_files, out.name)


def _count_by(recs: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    c: Dict[str, int] = defaultdict(int)
    for r in recs:
        c[r.get(key, "?")] += 1
    return c


# ---------------------------------------------------------------------------
# Queue A — the pending_vision queue
# ---------------------------------------------------------------------------

def run_queue_a(checkpoint: Optional[int]) -> int:
    state, vessel = config.STATE_DIR, config.VESSEL_NAMESPACE
    queue = json.loads((state / f"pending_vision_{vessel}.json").read_text())["queue"]
    structure = json.loads((state / f"structure_{vessel}.json").read_text())
    prov = GoogleDriveStructureProvider(structure["root_id"], structure["root_name"])
    writer = VisionWriter()
    ledger = Ledger(f"vision_ledger_{vessel}.jsonl")
    exclusions: Dict[str, List[str]] = defaultdict(list)
    buckets = defaultdict(int)
    new_files = 0

    for p in queue:
        fid = p["file_id"]
        if ledger.done(fid):
            continue
        mime = p.get("mime", "")
        if mime in EXCLUDED_FORMATS:
            fmt = EXCLUDED_FORMATS[mime]
            ledger.record(fid, "excluded_format", name=p["name"], format=fmt,
                          equipment=p.get("equipment_name") or p.get("subsystem_label") or "?")
            exclusions[p.get("equipment_name") or "?"].append(f"{p['name']} ({fmt})")
            buckets["excluded_format"] += 1
            continue
        try:
            data, _ = prov.download_bytes(fid, mime)
            file_hash = hashlib.sha256(data).hexdigest()
            placement = _placement_meta(p)
            kind = route_kind(p["name"], mime, p.get("doc_type"), p.get("region_code"))
            if mime == "application/pdf":
                c = process_pdf(writer, data, kind_hint=kind, file_hash=file_hash,
                                file_name=p["name"], file_path=p["path"],
                                placement=placement)
            elif mime.startswith(IMAGE_MIMES_PREFIX):
                ext = p.get("ext") or mime.split("/")[-1]
                c = process_image(writer, data, ext, kind=kind, file_hash=file_hash,
                                  file_name=p["name"], file_path=p["path"],
                                  placement=placement)
            else:
                ledger.record(fid, "excluded_format", name=p["name"], format=mime)
                buckets["excluded_format"] += 1
                continue
            ledger.record(fid, "described", name=p["name"], file_hash=file_hash, **c)
            buckets["described"] += 1
            new_files += 1
        except Exception as e:
            ledger.record(fid, "error", name=p["name"], error=str(e)[:300])
            buckets["errors"] += 1
            logger.warning("vision failed: %s — %s", p["name"], e)

        if checkpoint and new_files >= checkpoint:
            _write_checkpoint(writer, new_files)
            _report(queue_len=len(queue), ledger=ledger, exclusions=exclusions)
            return 3

        done = sum(1 for q in queue if ledger.done(q["file_id"]))
        if done % 20 == 0:
            logger.info("queue A progress %d/%d %s", done, len(queue), dict(buckets))

    _report(queue_len=len(queue), ledger=ledger, exclusions=exclusions)
    return 0


def _report(queue_len: int, ledger: Ledger, exclusions: Dict[str, List[str]]):
    state, vessel = config.STATE_DIR, config.VESSEL_NAMESPACE
    buckets = defaultdict(int)
    chunks = 0
    for r in ledger.entries.values():
        buckets[r["bucket"]] += 1
        chunks += int(r.get("pages_described", 0)) + int(r.get("figures_described", 0)) \
                  + int(r.get("images_described", 0))
    accounted = len(ledger.entries)
    report = {
        "vessel_namespace": vessel,
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "queue_total": queue_len, "accounted": accounted,
        "reconciled": accounted >= queue_len,
        "buckets": dict(buckets), "vision_chunks": chunks,
        "exclusions_by_equipment": {k: v for k, v in sorted(exclusions.items())},
    }
    (state / f"vision_report_{vessel}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("VISION REPORT: %s", {k: report[k] for k in
                ("queue_total", "accounted", "reconciled", "buckets", "vision_chunks")})
    if exclusions:
        logger.info("EXCLUDED (format) by equipment:")
        for eq, files in sorted(exclusions.items()):
            logger.info("  %s: %s", eq, "; ".join(files))


# ---------------------------------------------------------------------------
# Queue B — figure pages inside text-ingested documents
# ---------------------------------------------------------------------------

def classify_queue_b() -> int:
    """FREE pass: find figure-bearing pages in text-ingested PDFs; price the work."""
    state, vessel = config.STATE_DIR, config.VESSEL_NAMESPACE
    structure = json.loads((state / f"structure_{vessel}.json").read_text())
    prov = GoogleDriveStructureProvider(structure["root_id"], structure["root_name"])
    store = get_vectorstore_provider()

    # text-ingested drive files (pdf/docx) from the text ledger
    text_ledger = state / f"ingest_ledger_{vessel}.jsonl"
    candidates: List[Dict[str, Any]] = []
    for line in text_ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("bucket") == "ingested" and not r.get("seeded"):
            candidates.append(r)

    placements = {p["file_id"]: p for p in json.loads(
        (state / f"placements_{vessel}.json").read_text())["placements"]}

    out: List[Dict[str, Any]] = []
    total_figures = 0
    stale = 0
    for i, r in enumerate(candidates, 1):
        fid = r["key"] if "key" in r else r["file_id"]
        p = placements.get(fid)
        if not p or p.get("mime") != "application/pdf":
            continue
        try:
            data, _ = prov.download_bytes(fid, p["mime"])
            h = hashlib.sha256(data).hexdigest()
            # stale_text: compare with the hash on the existing text chunks
            existing = store.get_all(where={"drive_file_id": fid})
            old_hash = existing[0]["metadata"].get("file_hash") if existing else None
            is_stale = bool(old_hash and old_hash != h)
            stale += int(is_stale)
            lens = vx.pdf_page_text_lens(data)
            fig_pages = []
            for pi in range(len(lens)):
                if lens[pi] >= SCANNED_TEXT_THRESHOLD:
                    n_figs = len(vx.pdf_embedded_images(data, pi))
                    if n_figs:
                        fig_pages.append({"page": pi + 1, "figures": n_figs})
                        total_figures += n_figs
            if fig_pages:
                out.append({"file_id": fid, "name": p["name"], "path": p["path"],
                            "file_hash": h, "stale_text": is_stale,
                            "figure_pages": fig_pages})
        except Exception as e:
            logger.warning("classify failed: %s — %s", p.get("name", fid), e)
        if i % 50 == 0:
            logger.info("classify-b progress %d/%d (figures so far: %d)",
                        i, len(candidates), total_figures)

    est_low, est_high = total_figures * 0.02, total_figures * 0.05
    (state / f"queue_b_{vessel}.json").write_text(
        json.dumps({"files": out, "total_figures": total_figures,
                    "stale_text_files": stale,
                    "est_cost_usd": [round(est_low, 2), round(est_high, 2)]},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("QUEUE B classified: %d files carry %d embedded figures. "
                "stale_text=%d. Est cost $%.2f–%.2f. Wrote queue_b_%s.json",
                len(out), total_figures, stale, est_low, est_high, vessel)
    return 0


def run_queue_b(checkpoint: Optional[int]) -> int:
    state, vessel = config.STATE_DIR, config.VESSEL_NAMESPACE
    qb = json.loads((state / f"queue_b_{vessel}.json").read_text())["files"]
    structure = json.loads((state / f"structure_{vessel}.json").read_text())
    prov = GoogleDriveStructureProvider(structure["root_id"], structure["root_name"])
    placements = {p["file_id"]: p for p in json.loads(
        (state / f"placements_{vessel}.json").read_text())["placements"]}
    writer = VisionWriter()
    ledger = Ledger(f"vision_ledger_b_{vessel}.jsonl")
    new_files = 0
    for f in qb:
        fid = f["file_id"]
        if ledger.done(fid):
            continue
        p = placements[fid]
        try:
            data, _ = prov.download_bytes(fid, p["mime"])
            c = process_pdf(writer, data, kind_hint="figure",
                            file_hash=f["file_hash"], file_name=p["name"],
                            file_path=p["path"], placement=_placement_meta(p))
            ledger.record(fid, "described", name=p["name"],
                          stale_text=f.get("stale_text", False), **c)
            new_files += 1
        except Exception as e:
            ledger.record(fid, "error", name=p["name"], error=str(e)[:300])
        if checkpoint and new_files >= checkpoint:
            _write_checkpoint(writer, new_files)
            return 3
    logger.info("queue B done: %d files described.", new_files)
    return 0


# ---------------------------------------------------------------------------
# Validation slice — the 5 gates, on known targets
# ---------------------------------------------------------------------------

def run_validate() -> int:
    state, vessel = config.STATE_DIR, config.VESSEL_NAMESPACE
    writer = VisionWriter()
    results: List[str] = []

    def local_hash(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()

    # Gate 1+: CM-26-2024 (local pdf — same file_hash identity as its text chunks)
    p1 = config.DOCUMENTS_DIR / "108-01_BAE-report-20260403.pdf"
    c = process_pdf(writer, p1.read_bytes(), kind_hint="figure",
                    file_hash=local_hash(p1), file_name=p1.name, file_path=str(p1),
                    placement={"sfi_section": "600", "region_code": "600",
                               "subsystem_code": "625", "subsystem_label": "BAE System",
                               "equipment_name": "BAE System"})
    results.append(f"CM-26-2024: {c}")

    # Gate 2: CM-24-1732 (local docx, 25 figures)
    p2 = config.DOCUMENTS_DIR / "CM-24-1732_Investigation_Report.docx"
    c = process_docx(writer, p2.read_bytes(), file_hash=local_hash(p2),
                     file_name=p2.name, file_path=str(p2),
                     placement={"sfi_section": "600", "region_code": "600",
                                "subsystem_code": "625", "subsystem_label": "BAE System",
                                "equipment_name": "BAE System"})
    results.append(f"CM-24-1732: {c}")

    # Gate 3: scanned Akasol certificate (Drive, from the pending queue)
    structure = json.loads((state / f"structure_{vessel}.json").read_text())
    prov = GoogleDriveStructureProvider(structure["root_id"], structure["root_name"])
    queue = json.loads((state / f"pending_vision_{vessel}.json").read_text())["queue"]
    cert = next(q for q in queue if "DoC_Akasystem" in q["name"])
    data, _ = prov.download_bytes(cert["file_id"], cert["mime"])
    c = process_pdf(writer, data, kind_hint="certificate",
                    file_hash=hashlib.sha256(data).hexdigest(),
                    file_name=cert["name"], file_path=cert["path"],
                    placement=_placement_meta(cert))
    results.append(f"Akasol cert: {c}")

    # Gate 4: DENSE schematic — first 2 pages of BAE Wiring Diagrams (Drive)
    placements = {p["file_id"]: p for p in json.loads(
        (state / f"placements_{vessel}.json").read_text())["placements"]}
    dense = next(p for p in placements.values() if p["name"] == "BAE Wiring Diagrams.pdf")
    data, _ = prov.download_bytes(dense["file_id"], dense["mime"])
    h = hashlib.sha256(data).hexdigest()
    for page in (0, 1):
        png = vx.rasterize_pdf_page(data, page)
        writer.describe_store(png, "image/png", "schematic",
                              file_hash=h, file_name=dense["name"],
                              file_path=dense["path"],
                              locator={"page_number": page + 1, "suffix": f"v{page+1}"},
                              placement=_placement_meta(dense),
                              figure_label=f"p.{page+1}")
    results.append("BAE Wiring Diagrams: 2 dense pages described")

    # Gate 4b: a photo (GPM-12 motor png from the queue)
    photo = next(q for q in queue if q["name"] == "BAE Systems GPM-12 Motor.png")
    data, _ = prov.download_bytes(photo["file_id"], photo["mime"])
    c = process_image(writer, data, photo.get("ext") or "png", kind="photo",
                      file_hash=hashlib.sha256(data).hexdigest(),
                      file_name=photo["name"], file_path=photo["path"],
                      placement=_placement_meta(photo))
    results.append(f"GPM-12 photo: {c}")

    out = state / f"vision_validation_{vessel}.json"
    out.write_text(json.dumps({"results": results, "stored": writer.stored},
                              indent=2, ensure_ascii=False), encoding="utf-8")
    for r in results:
        logger.info("VALIDATE %s", r)
    logger.info("stored %d vision chunks; details in %s", len(writer.stored), out.name)
    return 0


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.vision_ingest")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--validate", action="store_true")
    g.add_argument("--queue-a", action="store_true")
    g.add_argument("--classify-b", action="store_true")
    g.add_argument("--queue-b", action="store_true")
    g.add_argument("--report-only", action="store_true")
    ap.add_argument("--checkpoint", type=int, default=75,
                    help="STOP after N new files for engineer spot-check (0 = off).")
    args = ap.parse_args(argv)
    cp = args.checkpoint or None
    if args.validate:
        return run_validate()
    if args.queue_a:
        return run_queue_a(cp)
    if args.classify_b:
        return classify_queue_b()
    if args.queue_b:
        return run_queue_b(cp)
    ledger = Ledger(f"vision_ledger_{config.VESSEL_NAMESPACE}.jsonl")
    _report(queue_len=0, ledger=ledger, exclusions=defaultdict(list))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
