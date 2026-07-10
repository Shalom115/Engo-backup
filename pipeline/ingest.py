"""
Document ingestion orchestrator + CLI.

Supports three file types (extensible via pipeline.parsers.PARSER_REGISTRY):
  .pdf  → parse_pdf → chunk_pages → embed → store
  .xlsx → parse_xlsx (one chunk per row, no chunking step) → embed → store
  .docx → parse_docx → chunk_sections → embed → store

Pipeline per file:
  1. Compute SHA256 (streamed).
  2. Skip if vector store already has chunks for this file_hash.
  3. Parse via the registry-dispatched parser for the file extension.
  4. Chunk-build: if parser needs_chunking, run chunk_pages(); else use
     the parser's row output directly (one row = one chunk).
  5. Embed chunks in batches (default 128, token-budget-aware).
  6. Write to vector store with full metadata.

Idempotency limitation (Phase 1):
  Idempotency is determined by file_hash existence in the collection.
  If a previous run was killed mid-batch, partial chunks remain under
  that hash and `exists()` will return True forever. Recovery: use
  ``--refresh`` to delete stale chunks and re-ingest.

Refresh (live documents):
  Use ``--refresh`` for documents that change over time (running logs,
  inventory, maintenance records).  Before ingesting, all existing
  chunks whose ``file_name`` matches the file's basename are deleted,
  clearing orphaned chunks left behind by a previous version of the file.
  Ingest then proceeds normally (hash idempotency applies to the new
  file's hash).

CLI:
    python -m pipeline.ingest <path> [<path> ...]
    python -m pipeline.ingest 'data/documents/*.pdf'   # quote to defer expansion
    python -m pipeline.ingest data/documents/          # directory: recurses .pdf + .xlsx
    python -m pipeline.ingest --refresh <path>         # purge stale + re-ingest

Logs: logs/ingest.log (INFO) plus stderr (INFO).
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import config
from pipeline.parsers import PARSER_REGISTRY
from pipeline.chunk import chunk_pages, chunk_sections
from pipeline.classify import extract_metadata
from providers.embeddings import get_embedding_provider
from providers.vectorstore import get_vectorstore_provider

# --- Logging setup (file + console) ---
_LOG_PATH = config.LOGS_DIR / "ingest.log"
_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=_LEVEL,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler(_LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger("pipeline.ingest")

# --- Constants ---
EMBED_BATCH_SIZE = 128
MAX_BATCH_TOKENS = 100_000
EMBED_RETRY_ATTEMPTS = 3
EMBED_RETRY_BACKOFF = (1.0, 2.0, 4.0)  # seconds

# Chunker dispatch for needs_chunking=True types. Kept here (not in
# PARSER_REGISTRY) to avoid pipeline.parsers importing from pipeline.chunk
# — parsers are conceptually upstream of chunkers. Adding a new chunked
# type means one entry here and one in PARSER_REGISTRY.
CHUNKERS = {
    ".pdf":  (chunk_pages,    "pages"),
    ".docx": (chunk_sections, "sections"),
    ".pptx": (chunk_sections, "sections"),   # one slide = one section (parse_pptx)
}


def _file_sha256(path: Path) -> str:
    """SHA256 of file contents, streamed in 1 MB blocks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _embed_with_retry(provider, texts: List[str]) -> List[List[float]]:
    """Call the embedder with bounded retries. Raises on persistent failure."""
    last_exc: Exception | None = None
    for attempt in range(EMBED_RETRY_ATTEMPTS):
        try:
            return provider.embed(texts, input_type="document")
        except Exception as e:
            last_exc = e
            backoff = EMBED_RETRY_BACKOFF[min(attempt, len(EMBED_RETRY_BACKOFF) - 1)]
            logger.warning("Embed attempt %d/%d failed (%s). Retrying in %.1fs.",
                           attempt + 1, EMBED_RETRY_ATTEMPTS, e, backoff)
            time.sleep(backoff)
    assert last_exc is not None
    raise last_exc


def _batched(chunks: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Split chunks into batches respecting both count and token-budget caps."""
    batches: List[List[Dict[str, Any]]] = []
    cur: List[Dict[str, Any]] = []
    cur_tokens = 0
    for c in chunks:
        c_tokens = int(c["token_count"])
        would_exceed_count = len(cur) >= EMBED_BATCH_SIZE
        would_exceed_tokens = cur_tokens + c_tokens > MAX_BATCH_TOKENS
        if cur and (would_exceed_count or would_exceed_tokens):
            batches.append(cur)
            cur = []
            cur_tokens = 0
        cur.append(c)
        cur_tokens += c_tokens
    if cur:
        batches.append(cur)
    return batches


def ingest_file(
    path: Path,
    *,
    extra_metadata: Optional[Dict[str, Any]] = None,
    display_name: Optional[str] = None,
    display_path: Optional[str] = None,
    chunker_override: Optional[Any] = None,
    store=None,
    embedder=None,
) -> Dict[str, Any]:
    """
    Ingest one supported document. Returns a summary dict whose keys vary
    slightly by file type (PDF carries pages_*; xlsx carries rows_total
    and sheets_total) but always includes:
        file, skipped, file_hash, chunks_created, tokens_total,
        embedding_calls, errors.

    Optional keyword args (used by the Drive ingest):
        extra_metadata  merged into every chunk's metadata, overriding the
                        folder-path classifier (placement: region/subsystem/
                        equipment/doc_type). When given, the path-based SFI
                        classifier is skipped (the temp path has no folder
                        structure to read).
        display_name    real document name for metadata/citation (temp paths
                        carry meaningless names).
        display_path    real source path for metadata.
        chunker_override a pre-bound callable f(units) -> chunks, used instead
                        of the suffix-mapped chunker (e.g. procedure-aware
                        chunking for handover notes). Already carries its own
                        chunk_size/overlap. Only consulted for chunked types.
        store, embedder reuse a single provider instance across a batch run.
    """
    path = Path(path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    suffix = path.suffix.lower()
    if suffix not in PARSER_REGISTRY:
        raise ValueError(
            f"Unsupported file type {path.suffix}. "
            f"Supported: {sorted(PARSER_REGISTRY)}"
        )
    parser_config = PARSER_REGISTRY[suffix]

    summary: Dict[str, Any] = {
        "file": str(path),
        "skipped": False,
        "file_hash": "",
        "chunks_created": 0,
        "tokens_total": 0,
        "embedding_calls": 0,
        "errors": 0,
    }
    # Parser-specific summary fields (presentational; suffix-branched per spec).
    if suffix == ".pdf":
        summary.update({"pages_total": 0, "pages_with_text": 0, "pages_skipped": 0})
    elif suffix in (".xlsx", ".csv"):
        summary.update({"rows_total": 0, "sheets_total": 0})
    elif suffix == ".docx":
        summary.update({"sections_total": 0, "images_skipped": 0})

    logger.info("Ingest start: %s", path.name)

    # 1. Hash + idempotency check
    file_hash = _file_sha256(path)
    summary["file_hash"] = file_hash
    store = store or get_vectorstore_provider()
    if store.exists(file_hash):
        logger.info("Skip (already ingested): %s [hash=%s]", path.name, file_hash[:12])
        summary["skipped"] = True
        return summary

    # 2. Parse (registry-dispatched)
    try:
        parsed = parser_config["parser"](path)
    except Exception as e:
        logger.error("Parse failed for %s: %s", path.name, e)
        summary["errors"] += 1
        raise

    # Populate parser-specific summary fields (presentational; suffix-branched).
    if suffix == ".pdf":
        summary["pages_total"] = int(parsed["total_pages"])
        summary["pages_with_text"] = len(parsed["pages"])
        summary["pages_skipped"] = summary["pages_total"] - summary["pages_with_text"]
        logger.info(
            "Parsed %s: pages_with_text=%d/%d, pages_skipped=%d",
            path.name, summary["pages_with_text"], summary["pages_total"],
            summary["pages_skipped"],
        )
    elif suffix in (".xlsx", ".csv"):
        summary["rows_total"] = int(parsed["total_rows"])
        summary["sheets_total"] = int(parsed["total_sheets"])
        rows_kept = len(parsed["rows"])
        logger.info(
            "Parsed %s: rows ingested: %d from %d sheets (%d empty rows skipped)",
            path.name, rows_kept, summary["sheets_total"],
            summary["rows_total"] - rows_kept,
        )
    elif suffix == ".docx":
        summary["sections_total"] = int(parsed["total_sections"])
        summary["images_skipped"] = int(parsed["total_images_skipped"])
        logger.info(
            "Parsed %s: %d sections, %d inline images skipped",
            path.name, summary["sections_total"], summary["images_skipped"],
        )

    # 3. Chunk-build (control flow driven by needs_chunking; chunker
    # selected from the CHUNKERS table above).
    if parser_config["needs_chunking"]:
        chunker, source_key = CHUNKERS[suffix]
        units = parsed[source_key]
        if not units:
            logger.warning("No usable %s in %s — nothing to ingest.",
                           source_key, path.name)
            return summary
        if chunker_override is not None:
            chunks = chunker_override(units)
        else:
            chunks = chunker(
                units,
                chunk_size_tokens=config.CHUNK_SIZE_TOKENS,
                overlap_tokens=config.CHUNK_OVERLAP_TOKENS,
            )
        if not chunks:
            logger.warning("Chunker returned 0 chunks for %s.", path.name)
            return summary
    else:
        rows = parsed["rows"]
        if not rows:
            logger.warning("No usable rows in %s — nothing to ingest.", path.name)
            return summary
        chunks = [
            {
                "text": r["text"],
                "chunk_index": i,
                "token_count": int(r["token_count"]),
                "sheet_name": r["sheet_name"],
                "row_number": int(r["row_number"]),
            }
            for i, r in enumerate(rows)
        ]

    summary["chunks_created"] = len(chunks)
    summary["tokens_total"] = sum(int(c["token_count"]) for c in chunks)

    # 4. Per-file metadata (classification + provenance). When placement
    # metadata is supplied (Drive ingest), it is authoritative — skip the
    # folder-path classifier (the temp path has no readable structure).
    classification = {} if extra_metadata else extract_metadata(path)
    embedder = embedder or get_embedding_provider()
    ingested_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    base_meta: Dict[str, Any] = {
        "file_hash": file_hash,
        "file_path": display_path or str(path),
        "file_name": display_name or path.name,
        "ingested_at": ingested_at,
        "vessel_namespace": config.VESSEL_NAMESPACE,
        "embedding_model": embedder.model_name,
        **classification,
        **(extra_metadata or {}),
    }

    # 5. Embed in batches and write
    batches = _batched(chunks)
    logger.info("Embedding %d chunks in %d batch(es) (cap %d / %d tokens).",
                len(chunks), len(batches), EMBED_BATCH_SIZE, MAX_BATCH_TOKENS)

    for bi, batch in enumerate(batches, start=1):
        texts = [str(c["text"]) for c in batch]
        try:
            vectors = _embed_with_retry(embedder, texts)
        except Exception as e:
            summary["errors"] += 1
            logger.error("Embedding batch %d/%d failed permanently: %s", bi, len(batches), e)
            raise
        summary["embedding_calls"] += 1

        ids = [f"{file_hash}:{int(c['chunk_index'])}" for c in batch]
        metadatas = []
        for c in batch:
            m = dict(base_meta)
            m["chunk_index"] = int(c["chunk_index"])
            m["token_count"] = int(c["token_count"])
            # Branch on detected fields (presentational per spec).
            if "page_start" in c:
                m["page_start"] = int(c["page_start"])
                m["page_end"] = int(c["page_end"])
            if "sheet_name" in c:
                m["sheet_name"] = c["sheet_name"]
                m["row_number"] = int(c["row_number"])
            if "section_index" in c:
                m["section_index"] = int(c["section_index"])
            # section_title rides with docx sections AND procedure-aware PDF
            # chunks (which have no section_index). Carry it whenever present;
            # "" (preamble) is omitted to keep metadata clean.
            if c.get("section_title"):
                m["section_title"] = c["section_title"]
            metadatas.append(m)

        try:
            store.add(ids=ids, vectors=vectors, texts=texts, metadatas=metadatas)
        except Exception as e:
            summary["errors"] += 1
            logger.error("Vector store write failed on batch %d/%d: %s", bi, len(batches), e)
            raise

        logger.info("Batch %d/%d: %d chunks written.", bi, len(batches), len(batch))

    logger.info(
        "Ingest done: %s | chunks=%d tokens=%d embed_calls=%d errors=%d",
        path.name, summary["chunks_created"], summary["tokens_total"],
        summary["embedding_calls"], summary["errors"],
    )
    return summary


def _expand_paths(args: List[str]) -> List[Path]:
    """Expand a list of CLI args (paths or globs) into concrete file paths."""
    out: List[Path] = []
    for a in args:
        p = Path(a).expanduser()
        if any(ch in a for ch in "*?["):
            # User passed an unexpanded glob (quoted on CLI) — expand here.
            out.extend(sorted(Path().glob(a)))
        elif p.is_dir():
            out.extend(sorted(p.rglob("*.pdf")))
            out.extend(sorted(p.rglob("*.xlsx")))
            out.extend(sorted(p.rglob("*.docx")))
        else:
            out.append(p)
    return out


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="pipeline.ingest",
        description="Ingest documents into the Engo vector store.",
    )
    parser.add_argument(
        "paths", nargs="*",
        help="Document paths, globs, or directories to ingest.",
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help=(
            "For each file, delete all existing chunks with the same filename "
            "before ingesting.  Use for live documents (running logs, inventory, "
            "maintenance records) that change over time."
        ),
    )
    args = parser.parse_args(argv)

    if not args.paths:
        parser.print_help()
        return 2

    paths = _expand_paths(args.paths)
    if not paths:
        logger.error("No matching files for: %s", args.paths)
        return 1

    grand: Dict[str, int] = {
        "files_total": len(paths),
        "files_skipped": 0,
        "files_ingested": 0,
        "chunks_created": 0,
        "errors": 0,
    }

    for p in paths:
        if args.refresh:
            store = get_vectorstore_provider()
            n_deleted = store.delete_by_source(p.name)
            logger.info("--refresh: deleted %d stale chunks for '%s'", n_deleted, p.name)

        try:
            s = ingest_file(p)
            if s["skipped"]:
                grand["files_skipped"] += 1
            else:
                grand["files_ingested"] += 1
            grand["chunks_created"] += int(s["chunks_created"])
            grand["errors"] += int(s["errors"])
        except Exception as e:
            grand["errors"] += 1
            logger.exception("Ingest failed for %s: %s", p, e)

    logger.info("RUN SUMMARY: %s", grand)
    return 0 if grand["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
