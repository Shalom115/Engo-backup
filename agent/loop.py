"""
Engo agent loop — query() + CLI, single-turn or multi-turn.

Per query:
  1. Retrieve top-k chunks (pipeline.retrieve.search) — always on the NEW
     question only, never on conversation history.
  2. Format chunks as <context> XML.
  3. Build user message (context + question + answering instructions).
  4. Call LLM with cached system prompt (Anthropic prompt caching, 5-min TTL).
  5. Append one JSON line to logs/agent.log.
  6. Return result dict.

Conversation memory (opt-in): pass conversation_id and the turn is appended
to data/state/conversations/<id>.json. Recent turns replay verbatim as
alternating user/assistant messages (question + answer only — past retrieval
context is NOT replayed); older turns are compressed into one summary block
by a single claude-haiku-4-5 call once the verbatim count exceeds 4 turns
(see agent/conversation.py). Without conversation_id behaviour is exactly
the original single-turn path.

Prompt caching: the system prompt is passed as a structured block with
cache_control={"type": "ephemeral"}. Anthropic caches it for ~5 minutes;
subsequent queries pay ~10% of the uncached input-token cost on it.
Cache hit/miss is recorded in the JSON log. Conversation history rides on
the messages/user side only, so it never invalidates the system-prompt cache.

CLI:
    python -m agent.loop "your question"
    python -m agent.loop "your question" --verbose
    python -m agent.loop "your question" -k 8
    python -m agent.loop "your question" --threshold 0.7
    python -m agent.loop "follow-up question" -c bel-fault-2026-07
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
from agent import conversation as convo
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
    summary_xml: str = "",
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
    summary_part = (
        f"{summary_xml}\n(The block above summarises earlier turns of this "
        f"conversation that were compressed to save space. Treat it as prior "
        f"dialogue, not as a document source — do not cite it.)\n\n"
        if summary_xml else ""
    )
    return (
        f"{date_line}\n\n"
        f"{summary_part}"
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
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run one Engo query end-to-end.

    Args:
        question: the engineer's question for this turn.
        k: top-k retrieval (on this question only, even in a conversation).
        filters: optional metadata filter for retrieval.
        distance_threshold: optional cosine-distance cutoff.
        conversation_id: optional multi-turn memory. When given, prior turns
            of data/state/conversations/<id>.json replay into the LLM call
            and this turn is appended after answering. Omitted → the original
            single-turn behaviour, unchanged.

    Returns:
        {
          "question": str,
          "answer": str,
          "chunks_used": list[{id, file, location, distance}],
          "tokens_input": int,
          "tokens_output": int,
          "duration_ms": int,
          # only when conversation_id was given:
          "conversation_id": str,
          "turn_index": int,
          "compression": dict | None,
        }

    Raises:
        ValueError: empty question, or a corrupt conversation file
            (fail loud — a missing file is created fresh instead).
        Any LLM-side error after retrieval failure recovery (fail loud,
        no fake answers).
    """
    if not question or not question.strip():
        raise ValueError("Empty question.")

    started = time.monotonic()
    started_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    errors: List[str] = []

    # 0. Conversation memory (optional). Corrupt file → ValueError before we
    # spend anything on retrieval or the LLM. Missing file → fresh conversation.
    conv: Optional[Dict[str, Any]] = None
    if conversation_id is not None:
        conv = convo.load_conversation(conversation_id)

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
        summary_xml=convo.summary_block(conv) if conv else "",
    )

    # 4. LLM call — cached system prompt. Conversation history (if any)
    # replays as alternating user/assistant messages BEFORE this turn's
    # user message; the system block is byte-identical either way, so the
    # prompt cache is never invalidated by memory.
    system_block = [
        {
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    messages = (convo.history_messages(conv) if conv else []) + [
        {"role": "user", "content": user_message}
    ]

    turn_index = (
        conv["turns_compressed"] + len(conv["turns"]) if conv else None
    )

    llm = get_llm_provider()
    try:
        full = llm.complete_messages(
            system=system_block,
            messages=messages,
            max_tokens=_MAX_TOKENS_OUT,
        )
    except Exception as e:
        # LLM failure is non-recoverable — fail loud, no fake answers.
        errors.append(f"llm: {type(e).__name__}: {e}")
        _log_record({
            "timestamp": started_iso,
            "question": question,
            "conversation_id": conversation_id,
            "turn_index": turn_index,
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

    # 5. Persist the turn + compress older history if the conversation has
    # grown past the verbatim window (one Haiku call — see agent/conversation).
    compression: Optional[Dict[str, Any]] = None
    if conv is not None:
        convo.append_turn(conv, question, answer)
        compression = convo.maybe_compress(conv)
        convo.save_conversation(conv)

    duration_ms = int((time.monotonic() - started) * 1000)

    record: Dict[str, Any] = {
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
    }
    if conversation_id is not None:
        record["conversation_id"] = conversation_id
        record["turn_index"] = turn_index
        if compression:
            record["compression"] = compression
    _log_record(record)

    result: Dict[str, Any] = {
        "question": question,
        "answer": answer,
        "chunks_used": chunks_used,
        "tokens_input": tokens_input,
        "tokens_output": tokens_output,
        "duration_ms": duration_ms,
    }
    if conversation_id is not None:
        result["conversation_id"] = conversation_id
        result["turn_index"] = turn_index
        result["compression"] = compression
    return result


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
    p.add_argument("--conversation", "-c", default=None, metavar="ID",
                   help="Conversation id for multi-turn memory "
                        "(stored under data/state/conversations/).")
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = _parse_args(argv)
    result = query(
        args.question,
        k=args.k,
        distance_threshold=args.threshold,
        conversation_id=args.conversation,
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
        if result.get("conversation_id") is not None:
            comp = result.get("compression")
            comp_str = (
                f" (compressed {comp['turns_compressed_now']} turn(s) via "
                f"{comp['model']})" if comp else ""
            )
            print(f"CONVERSATION: id={result['conversation_id']} "
                  f"turn={result['turn_index']}{comp_str}")
        print()
        print("ANSWER:")
    print(result["answer"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
