"""
HyDE (Hypothetical Document Embedding) Q&A generation pipeline.

For each ingested source chunk, generates synthetic engineer-phrased questions,
embeds them, and stores them in the vector store with the original chunk's text
as the document.  This bridges the cross-vocabulary gap: manufacturer documents
use formal technical terms; engineers use operational shorthand.

Example gap fixed: CM-22-702 uses "concurrent operation" and "ACTM engagement
sequence"; an engineer typing "simultaneous load on BAE motor port and stbd"
would fail to retrieve it without HyDE.

Storage design:
    id:        {original_chunk_id}:q{n}
    document:  original chunk text        ← what the LLM sees on retrieval
    embedding: embed(synthetic_question)  ← drives similarity search
    metadata:  original metadata + {
                 doc_type      = "hyde",
                 hyde_question = "<the question>",
                 hyde_source_id = original_chunk_id,
               }

Retrieval deduplication is handled in pipeline/retrieve.py — it strips the :qN
suffix and keeps the best-distance hit per canonical chunk ID, so each source
chunk appears at most once in the returned context.

CLI:
    python -m pipeline.hyde --all              # backfill all source chunks
    python -m pipeline.hyde --file CM-22-702_HVPDU_Requirements_Rev1.pdf
    python -m pipeline.hyde --all --dry-run    # preview only, no writes

Configuration (env or .env):
    HYDE_MODEL   LLM for question generation (default: claude-haiku-4-5)
    HYDE_N_PDF   Questions per PDF/DOCX chunk  (default: 5)
    HYDE_N_XLSX  Questions per spreadsheet row (default: 3)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import config
from providers.embeddings import get_embedding_provider
from providers.llm import get_llm_provider
from providers.vectorstore import get_vectorstore_provider

# --- Logging setup ---
_LOG_PATH = config.LOGS_DIR / "hyde.log"
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler(_LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger("pipeline.hyde")

# --- Constants / configuration ---
HYDE_MODEL     = os.getenv("HYDE_MODEL", "claude-haiku-4-5")
N_QUESTIONS_PDF  = int(os.getenv("HYDE_N_PDF",  "5"))
N_QUESTIONS_XLSX = int(os.getenv("HYDE_N_XLSX", "3"))

EMBED_BATCH_SIZE = 64   # questions per embedding call (smaller than ingest — questions are short)
RETRY_ATTEMPTS   = 3
RETRY_BACKOFF    = (1.0, 2.0, 4.0)

# ---------------------------------------------------------------------------
# Prompt templates + vocabulary layers
#
# The vocabulary injected into question generation is LAYERED (the seam):
#   1. BASE LEXICON  — fleet-general, multilingual equipment vocabulary
#      (prompts/equipment_lexicon.md, maintained outside this pipeline).
#      Only the section matching the chunk's SFI region is injected.
#   2. VESSEL CONTEXT — per-vessel free-text vocabulary/context
#      (prompts/hyde_vessel_context.md — sensor channel names, system quirks).
#   3. VESSEL ACRONYMS — harvested from the folder tree at register build
#      (data/state/vocab_<vessel>.json).
# build_vocab_block() is the single named insertion point for all three.
# ---------------------------------------------------------------------------
LEXICON_PATH = Path(os.getenv(
    "LEXICON_PATH", str(config.PROJECT_ROOT / "prompts" / "equipment_lexicon.md")))
VESSEL_CONTEXT_PATH = Path(os.getenv(
    "HYDE_VESSEL_CONTEXT", str(config.PROJECT_ROOT / "prompts" / "hyde_vessel_context.md")))

_SYSTEM = """\
You are generating synthetic retrieval questions for a marine engineering AI \
assistant aboard a sailing yacht.

Your output bridges the vocabulary gap between manufacturer documentation and how \
working engineers talk, type, and read sensor data — across regions and languages.\
"""

_USER_TEMPLATE = """\
{vocab_block}

Given this documentation chunk, write {n} questions a marine engineer would \
naturally ask that this chunk answers directly.

Rules:
- Use the language an engineer would type under pressure, not formal document style
- Vary the angle: symptom-based, procedure-based, specification-based, shorthand
- Draw on the vocabulary above where it fits the content: nicknames and slang
- When the vocabulary lists non-English terms, EXACTLY ONE of the {n} questions must
  be written in one of those languages (rotate which language across chunks)
- Be specific to this content — avoid questions so generic they could match anything
- Each question must be answerable from the chunk content alone

Document: {file_name}
Content:
{text}

Output exactly {n} questions, one per line. No numbering, bullets, or preamble.\
"""

_REGION_HEADER_RE = re.compile(r"^##\s+([\d\s/]+)—")


def _load_lexicon_sections() -> Dict[str, str]:
    """
    Parse the base lexicon markdown into {region_code: section_text}.
    Headers like '## 400 — Propulsion & Machinery' map to '400'; combined
    headers like '## 200 / 800 — Deck & Rigging' map to both codes.
    Returns {} if the lexicon file is absent (the seam degrades gracefully).
    """
    if not LEXICON_PATH.exists():
        return {}
    sections: Dict[str, str] = {}
    current_codes: List[str] = []
    lines: List[str] = []
    for line in LEXICON_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            for c in current_codes:
                sections[c] = "\n".join(lines).strip()
            m = _REGION_HEADER_RE.match(line)
            current_codes = re.findall(r"\d{3}", m.group(1)) if m else []
            lines = []
        elif current_codes:
            lines.append(line)
    for c in current_codes:
        sections[c] = "\n".join(lines).strip()
    return sections


def _load_vessel_acronyms() -> Dict[str, str]:
    """
    Per-vessel acronym authority. Prefers the reconciled glossary_<vessel>.json
    (extracted from the Owner's Manual + handover acronym tables) over the raw
    folder-harvested vocab — the glossary is the source of truth.
    """
    g = config.STATE_DIR / f"glossary_{config.VESSEL_NAMESPACE}.json"
    if g.exists():
        gl = json.loads(g.read_text(encoding="utf-8")).get("acronyms", {})
        return {k: v["expansion"] for k, v in gl.items() if v.get("expansion")}
    p = config.STATE_DIR / f"vocab_{config.VESSEL_NAMESPACE}.json"
    return json.loads(p.read_text(encoding="utf-8")).get("acronyms", {}) if p.exists() else {}


def build_vocab_block(
    region_code: Optional[str],
    lexicon_sections: Dict[str, str],
    vessel_context: str,
    vessel_acronyms: Dict[str, str],
) -> str:
    """
    The vocabulary insertion point: base lexicon (region-matched section) +
    per-vessel context + per-vessel acronym glossary, as one prompt block.
    """
    parts: List[str] = []
    sec = lexicon_sections.get(region_code or "")
    if sec:
        parts.append("EQUIPMENT VOCABULARY for this system (formal terms, nicknames, "
                     "slang, other languages):\n" + sec)
    if vessel_context:
        parts.append("VESSEL CONTEXT:\n" + vessel_context)
    if vessel_acronyms:
        acr = " · ".join(f"{k}={v}" if v else k for k, v in sorted(vessel_acronyms.items()))
        parts.append("VESSEL ACRONYMS: " + acr)
    return "\n\n".join(parts) if parts else "(no extra vocabulary for this chunk)"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _n_questions(metadata: Dict[str, Any]) -> int:
    """Return target question count based on chunk origin."""
    if "sheet_name" in metadata:   # xlsx row — short, already human-readable
        return N_QUESTIONS_XLSX
    return N_QUESTIONS_PDF


def generate_questions(
    text: str,
    file_name: str,
    n: int,
    llm,
    vocab_block: str = "",
) -> List[str]:
    """
    Call the LLM to generate n synthetic engineer questions for a chunk.

    ``vocab_block`` is the layered vocabulary (base lexicon section + vessel
    context + acronyms) from build_vocab_block().

    Retries on transient errors.  Returns [] on permanent failure (caller
    increments its error counter and skips this chunk).
    """
    prompt = _USER_TEMPLATE.format(n=n, file_name=file_name, text=text,
                                   vocab_block=vocab_block)
    last_exc: Optional[Exception] = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            response = llm.complete(
                system=_SYSTEM,
                user=prompt,
                max_tokens=512,   # 5 questions × ~80 tokens, some headroom
            )
            # Parse: one question per non-empty line; trim numbering/bullets defensively
            questions: List[str] = []
            for line in response.splitlines():
                line = line.strip().lstrip("0123456789.-) ")
                if line and line != "?":
                    questions.append(line)
            return questions[:n]  # guard against over-generation
        except Exception as e:
            last_exc = e
            backoff = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
            logger.warning(
                "Question generation attempt %d/%d failed (%s). Retry in %.1fs.",
                attempt + 1, RETRY_ATTEMPTS, e, backoff,
            )
            time.sleep(backoff)
    logger.error("Question generation failed permanently: %s", last_exc)
    return []


def hyde_id(original_id: str, question_index: int) -> str:
    """Deterministic ID for a HyDE question entry."""
    return f"{original_id}:q{question_index}"


def store_hyde_questions(
    original_id: str,
    original_text: str,
    original_metadata: Dict[str, Any],
    questions: List[str],
    embedder,
    store,
) -> int:
    """
    Embed a list of synthetic questions and write them to the vector store.

    The stored document is the original chunk text (not the question) — so
    when a HyDE entry is retrieved, the LLM receives the source content.
    Returns the number of entries actually written.
    """
    if not questions:
        return 0

    ids = [hyde_id(original_id, i) for i in range(len(questions))]
    try:
        vectors = embedder.embed(questions, input_type="document")
    except Exception as e:
        logger.error("Embedding failed for chunk %s: %s", original_id, e)
        return 0

    # Document = original text so retrieval yields original content.
    texts = [original_text] * len(questions)
    metadatas: List[Dict[str, Any]] = []
    for i, q in enumerate(questions):
        m = {k: v for k, v in original_metadata.items()}  # shallow copy
        m["doc_type"]       = "hyde"
        m["hyde_question"]  = q
        m["hyde_source_id"] = original_id
        metadatas.append(m)

    try:
        store.add(ids=ids, vectors=vectors, texts=texts, metadatas=metadatas)
    except Exception as e:
        logger.error("Store write failed for chunk %s: %s", original_id, e)
        return 0

    return len(questions)


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------

def build_hyde(
    file_name: Optional[str] = None,
    skip_existing: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Generate HyDE questions for source chunks and write them to the store.

    Args:
        file_name:      limit to chunks from this file (by file_name metadata).
                        None = all source chunks.
        skip_existing:  skip chunks that already have HyDE entries.
        dry_run:        generate questions but do not write to the store.

    Returns a summary dict: chunks_processed, chunks_skipped, questions_generated,
    questions_stored, errors.
    """
    store    = get_vectorstore_provider()
    embedder = get_embedding_provider()
    llm      = get_llm_provider(model=HYDE_MODEL)

    # Load the vocabulary layers once per run.
    lexicon_sections = _load_lexicon_sections()
    vessel_context = (VESSEL_CONTEXT_PATH.read_text(encoding="utf-8").strip()
                      if VESSEL_CONTEXT_PATH.exists() else "")
    vessel_acronyms = _load_vessel_acronyms()

    logger.info(
        "HyDE build start | model=%s n_pdf=%d n_xlsx=%d dry_run=%s | "
        "lexicon_regions=%d vessel_context=%s acronyms=%d",
        HYDE_MODEL, N_QUESTIONS_PDF, N_QUESTIONS_XLSX, dry_run,
        len(lexicon_sections), bool(vessel_context), len(vessel_acronyms),
    )

    # --- Fetch all chunks (filtered by file if requested) ---
    where = {"file_name": file_name} if file_name else None
    all_chunks = store.get_all(where=where)

    # Separate source chunks from existing HyDE entries (Python-side filter —
    # safer than a Chroma $ne on a field that's absent from original chunks).
    source_chunks = [c for c in all_chunks if c["metadata"].get("doc_type") != "hyde"]
    hyde_chunks   = [c for c in all_chunks if c["metadata"].get("doc_type") == "hyde"]

    logger.info(
        "Collection: %d total chunks — %d source, %d existing HyDE.",
        len(all_chunks), len(source_chunks), len(hyde_chunks),
    )

    # --- Build skip set from existing HyDE coverage ---
    covered_ids: set = set()
    if skip_existing:
        for c in hyde_chunks:
            src = c["metadata"].get("hyde_source_id", "")
            if src:
                covered_ids.add(src)
        if covered_ids:
            logger.info("Skipping %d already-covered source chunks.", len(covered_ids))

    summary: Dict[str, Any] = {
        "chunks_processed":   0,
        "chunks_skipped":     0,
        "questions_generated": 0,
        "questions_stored":   0,
        "errors":             0,
    }

    for chunk in source_chunks:
        original_id = chunk["id"]
        if skip_existing and original_id in covered_ids:
            summary["chunks_skipped"] += 1
            continue

        n        = _n_questions(chunk["metadata"])
        file_nm  = chunk["metadata"].get("file_name", "unknown")
        vocab    = build_vocab_block(
            region_code=chunk["metadata"].get("region_code"),
            lexicon_sections=lexicon_sections,
            vessel_context=vessel_context,
            vessel_acronyms=vessel_acronyms,
        )

        questions = generate_questions(
            text=chunk["text"],
            file_name=file_nm,
            n=n,
            llm=llm,
            vocab_block=vocab,
        )
        summary["chunks_processed"] += 1

        if not questions:
            summary["errors"] += 1
            logger.warning("No questions generated for chunk %s — skipping.", original_id[:32])
            continue

        summary["questions_generated"] += len(questions)
        logger.debug("Chunk %-36s → %d questions", original_id[:36], len(questions))

        if dry_run:
            for q in questions:
                logger.info("[DRY RUN] %s | %s", file_nm, q)
            summary["questions_stored"] += len(questions)
        else:
            stored = store_hyde_questions(
                original_id=original_id,
                original_text=chunk["text"],
                original_metadata=chunk["metadata"],
                questions=questions,
                embedder=embedder,
                store=store,
            )
            summary["questions_stored"] += stored
            if stored < len(questions):
                summary["errors"] += 1

    logger.info("HyDE build done: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="pipeline.hyde",
        description="Generate and store HyDE synthetic questions for ingested chunks.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all", action="store_true",
        help="Process all source chunks in the collection.",
    )
    group.add_argument(
        "--file", metavar="FILENAME",
        help="Limit to chunks whose file_name metadata matches FILENAME.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Generate questions but do not write to the vector store.",
    )
    parser.add_argument(
        "--no-skip", action="store_true",
        help="Regenerate HyDE questions even if they already exist.",
    )
    args = parser.parse_args(argv)

    summary = build_hyde(
        file_name=args.file,
        skip_existing=not args.no_skip,
        dry_run=args.dry_run,
    )
    logger.info("RUN SUMMARY: %s", summary)
    return 0 if summary["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
