"""
Engo agent loop — single-turn query() + CLI.

Per query:
  1. Retrieve top-k chunks (pipeline.retrieve.search).
  2. Format chunks as <context> XML.
  3. Build user message (context + question + answering instructions).
  4. Call LLM with cached system prompt (Anthropic prompt caching, 5-min TTL).
  5. Append one JSON line to logs/agent.log.
  6. Return result dict.

No conversation memory. Each call is independent.

Prompt caching: the system prompt is passed as a structured block with
cache_control={"type": "ephemeral"}. Anthropic caches it for ~5 minutes;
subsequent queries pay ~10% of the uncached input-token cost on it.
Cache hit/miss is recorded in the JSON log.

CLI:
    python -m agent.loop "your question"
    python -m agent.loop "your question" --verbose
    python -m agent.loop "your question" -k 8
    python -m agent.loop "your question" --threshold 0.7
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import config
from agent.clock import clock_status
from agent.prompt import SYSTEM_PROMPT, format_context
from pipeline.retrieve import search
from providers.llm import get_llm_provider

# --- Logging: stderr only for status. JSONL records go to logs/agent.log via _log_record. ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("agent.loop")

_LOG_PATH = config.LOGS_DIR / "agent.log"
_MAX_TOKENS_OUT = 1500  # Engo answers are typically tight; bump per call if needed.


def _log_record(record: Dict[str, Any]) -> None:
    """Append one JSON line to logs/agent.log. Best-effort — never raises."""
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning("Failed to write agent.log record: %s", e)


def _build_user_message(
    context_xml: str,
    question: str,
    today: str,
    *,
    clock_suspect: bool = False,
    floor_iso: Optional[str] = None,
) -> str:
    if clock_suspect:
        ref = f" (its last data update is dated {floor_iso})" if floor_iso else ""
        date_line = (
            f"Today's date per the host clock: {today} (UTC). "
            f"WARNING: this clock looks WRONG — it reads earlier than the "
            f"vessel's most recent data update{ref}, which is impossible. Do NOT "
            f"use it to judge how recent a logged event is. If recency matters to "
            f"the answer, say the clock is unreliable and ask the engineer to "
            f"confirm today's date."
        )
    else:
        date_line = (
            f"Today's date: {today} (UTC). Use it to judge how recent any "
            f"logged event or timestamp is."
        )
    return (
        f"{date_line}\n\n"
        f"{context_xml}\n\n"
        f"Question: {question}\n\n"
        f"Answer using only the context above and the locked vessel facts in "
        f"your system prompt. Cite sources inline using the attributes shown "
        f"in each <chunk> tag — [filename, p.X] for documents with pages, "
        f"[filename, sheet=NAME, row=N] for spreadsheet rows, "
        f"[filename, section='Section Title'] for document sections, "
        f"[filename] when none of the above apply. If the context is empty or "
        f"insufficient, follow your uncertainty rules."
    )


def query(
    question: str,
    k: int = 5,
    filters: Optional[Dict[str, Any]] = None,
    distance_threshold: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Run one Engo query end-to-end.

    Returns:
        {
          "question": str,
          "answer": str,
          "chunks_used": list[{id, file, location, distance}],
          "tokens_input": int,
          "tokens_output": int,
          "duration_ms": int,
        }

    Raises:
        ValueError: empty question.
        Any LLM-side error after retrieval failure recovery (fail loud,
        no fake answers).
    """
    if not question or not question.strip():
        raise ValueError("Empty question.")

    started = time.monotonic()
    started_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    errors: List[str] = []

    # 1. Retrieve (recoverable — if it fails we still answer with empty context)
    try:
        chunks = search(
            question,
            k=k,
            filters=filters,
            distance_threshold=distance_threshold,
        )
    except Exception as e:
        logger.exception("Retrieval failed: %s", e)
        errors.append(f"retrieval: {type(e).__name__}: {e}")
        chunks = []

    chunks_used = []
    for c in chunks:
        meta = c.get("metadata") or {}
        # Three-branch location: PDF pages, xlsx sheet/row, or neither.
        page_start = meta.get("page_start")
        page_end = meta.get("page_end")
        sheet_name = meta.get("sheet_name")
        row_number = meta.get("row_number")
        if page_start is not None and page_end is not None:
            location = f"p.{page_start}-{page_end}"
        elif sheet_name and row_number is not None:
            location = f"sheet={sheet_name} row={row_number}"
        elif meta.get("section_title"):
            location = f"section='{meta['section_title']}'"
        else:
            location = "-"
        chunks_used.append({
            "id": c.get("id"),
            "file": meta.get("file_name"),
            "location": location,
            "distance": round(float(c.get("distance", 0.0)), 4),
        })

    # 2 & 3. Format context, build user message (with today's date so the
    # agent can apply the recent-event window in its diagnostic rules). The
    # clock guard flags a host clock that predates the last ingest — fails
    # toward caution instead of silently trusting a wrong date.
    context_xml = format_context(chunks)
    now, clock_suspect, floor = clock_status()
    today = now.date().isoformat()
    user_message = _build_user_message(
        context_xml, question, today,
        clock_suspect=clock_suspect,
        floor_iso=floor.date().isoformat() if floor else None,
    )

    # 4. LLM call — cached system prompt
    system_block = [
        {
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    llm = get_llm_provider()
    try:
        full = llm.complete_full(
            system=system_block,
            user=user_message,
            max_tokens=_MAX_TOKENS_OUT,
        )
    except Exception as e:
        # LLM failure is non-recoverable — fail loud, no fake answers.
        errors.append(f"llm: {type(e).__name__}: {e}")
        _log_record({
            "timestamp": started_iso,
            "question": question,
            "retrieval_k": k,
            "chunks_returned": len(chunks_used),
            "chunks_used": chunks_used,
            "tokens_input": 0,
            "tokens_output": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "errors": errors,
        })
        logger.exception("LLM call failed: %s", e)
        raise

    answer = full["text"]
    tokens_input = int(full.get("input_tokens", 0))
    tokens_output = int(full.get("output_tokens", 0))
    cache_read = int(full.get("cache_read_input_tokens", 0))
    cache_created = int(full.get("cache_creation_input_tokens", 0))
    duration_ms = int((time.monotonic() - started) * 1000)

    _log_record({
        "timestamp": started_iso,
        "question": question,
        "retrieval_k": k,
        "chunks_returned": len(chunks_used),
        "chunks_used": chunks_used,
        "tokens_input": tokens_input,
        "tokens_output": tokens_output,
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_created,
        "duration_ms": duration_ms,
        "errors": errors,
    })

    return {
        "question": question,
        "answer": answer,
        "chunks_used": chunks_used,
        "tokens_input": tokens_input,
        "tokens_output": tokens_output,
        "duration_ms": duration_ms,
    }


def _parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="agent.loop",
        description="Run a single Engo query against the local library.",
    )
    p.add_argument("question", help="Natural-language question for Engo.")
    p.add_argument("-k", "--k", type=int, default=5,
                   help="Top-k retrieval (default 5).")
    p.add_argument("--threshold", type=float, default=None,
                   help="Cosine distance threshold; results above are dropped.")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="Print retrieval results and token usage before the answer.")
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = _parse_args(argv)
    result = query(
        args.question,
        k=args.k,
        distance_threshold=args.threshold,
    )

    if args.verbose:
        print(f"RETRIEVAL (k={args.k}, threshold={args.threshold}):")
        if not result["chunks_used"]:
            print("  (no chunks returned)")
        else:
            for i, ch in enumerate(result["chunks_used"], start=1):
                print(f"  [{i}] {ch['file']}  {ch['location']}  "
                      f"distance={ch['distance']:.4f}")
        print()
        print(f"TOKENS: input={result['tokens_input']} "
              f"output={result['tokens_output']} "
              f"duration={result['duration_ms']}ms")
        print()
        print("ANSWER:")
    print(result["answer"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
