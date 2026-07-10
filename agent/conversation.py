"""
Conversation store for multi-turn agent memory.

One JSON file per conversation at data/state/conversations/<id>.json:

    {
      "conversation_id": str,
      "created_at":  ISO-8601 UTC,
      "updated_at":  ISO-8601 UTC,
      "turns_compressed": int,        # turns folded into the summary so far
      "summary": str | None,          # compact block covering compressed turns
      "summary_meta": dict | None,    # {model, updated_at, input_tokens, output_tokens}
      "turns": [                      # recent turns kept verbatim
        {"turn_index": int, "timestamp": ISO, "question": str, "answer": str}
      ]
    }

Token budget: the most recent RECENT_TURNS_VERBATIM turns replay verbatim as
alternating user/assistant messages; anything older lives in ONE compact
summary block produced by a single claude-haiku-4-5 call (same
get_llm_provider(model=...) override mechanism pipeline/hyde.py uses).
Compression fires when the verbatim turn count exceeds COMPRESS_WHEN_OVER.

The cached system prompt is untouched — history rides entirely on the
messages/user side, so Anthropic prompt caching on the system block survives.

Failure behaviour: a MISSING conversation file is created fresh; a CORRUPT
one (bad JSON / wrong shape) raises ValueError — fail loud, never silently
start over on top of damaged history.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import config
from providers.llm import get_llm_provider

logger = logging.getLogger("agent.conversation")

CONVERSATIONS_DIR: Path = config.STATE_DIR / "conversations"

# Keep this many most-recent turns verbatim in the replay.
RECENT_TURNS_VERBATIM = 3
# Compress when the stored verbatim turn count exceeds this (spec: 3-4 turns).
COMPRESS_WHEN_OVER = 4
# Model for the one-shot history compression (cheapest capable tier).
SUMMARY_MODEL = os.getenv("CONVERSATION_SUMMARY_MODEL", "claude-haiku-4-5")
_SUMMARY_MAX_TOKENS = 700  # headroom above the ~250-word target so the
                           # summary never truncates mid-sentence

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

_SUMMARY_SYSTEM = (
    "You compress marine-engineering troubleshooting dialogue into a compact "
    "working summary. Preserve facts exactly; never invent or embellish."
)

_SUMMARY_INSTRUCTIONS = (
    "Update the running summary of this troubleshooting conversation.\n"
    "Fold the turns below into ONE plain-text summary (max ~250 words) that "
    "preserves:\n"
    "- the equipment / fault under discussion\n"
    "- key findings, eliminations and conclusions so far, keeping any document "
    "citations exactly as written (e.g. [CM-26-2024, p.4])\n"
    "- open questions or pending actions\n"
    "No preamble, no headings, no markdown — just compact summary text. "
    "Stay under 250 words; end with a complete sentence."
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conversation_path(conversation_id: str) -> Path:
    """Resolve the on-disk path for a conversation id (validated)."""
    if not _ID_RE.match(conversation_id):
        raise ValueError(
            f"Invalid conversation_id {conversation_id!r}: use 1-64 chars of "
            f"letters, digits, '.', '_' or '-' (must start alphanumeric)."
        )
    return CONVERSATIONS_DIR / f"{conversation_id}.json"


def load_conversation(conversation_id: str) -> Dict[str, Any]:
    """
    Load a conversation, creating a fresh in-memory one if the file is missing.

    Raises:
        ValueError: the file exists but is corrupt (bad JSON or wrong shape).
    """
    path = conversation_path(conversation_id)
    if not path.exists():
        now = _now_iso()
        return {
            "conversation_id": conversation_id,
            "created_at": now,
            "updated_at": now,
            "turns_compressed": 0,
            "summary": None,
            "summary_meta": None,
            "turns": [],
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"Corrupt conversation file {path}: {e}") from e
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("turns"), list)
        or not isinstance(data.get("turns_compressed"), int)
    ):
        raise ValueError(
            f"Corrupt conversation file {path}: missing/invalid "
            f"'turns' list or 'turns_compressed' int."
        )
    return data


def save_conversation(conv: Dict[str, Any]) -> Path:
    """Atomically persist a conversation (tmp file + os.replace)."""
    path = conversation_path(conv["conversation_id"])
    CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
    conv["updated_at"] = _now_iso()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(conv, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(tmp, path)
    return path


def append_turn(conv: Dict[str, Any], question: str, answer: str) -> int:
    """Append one Q/A turn; returns its global turn_index (0-based)."""
    turn_index = conv["turns_compressed"] + len(conv["turns"])
    conv["turns"].append({
        "turn_index": turn_index,
        "timestamp": _now_iso(),
        "question": question,
        "answer": answer,
    })
    return turn_index


def history_messages(conv: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Prior verbatim turns as alternating user/assistant messages for replay.

    Only the QUESTION of each prior turn replays on the user side — past
    retrieval context is deliberately dropped (retrieval is per-question;
    replaying old <context> blocks would blow the token budget). Answers
    replay verbatim (they carry the citations the dialogue builds on).
    """
    messages: List[Dict[str, str]] = []
    for turn in conv["turns"]:
        messages.append({"role": "user", "content": turn["question"]})
        messages.append({"role": "assistant", "content": turn["answer"]})
    return messages


def summary_block(conv: Dict[str, Any]) -> str:
    """The compressed-history block for the user message, or '' if none."""
    if not conv.get("summary"):
        return ""
    return (
        "<conversation_summary turns_compressed="
        f"\"{conv['turns_compressed']}\">\n"
        f"{conv['summary']}\n"
        "</conversation_summary>"
    )


def _render_turns(turns: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for t in turns:
        parts.append(f"Engineer: {t['question']}")
        parts.append(f"Engo: {t['answer']}")
    return "\n\n".join(parts)


def maybe_compress(conv: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Compress oldest turns into the summary when the verbatim count exceeds
    COMPRESS_WHEN_OVER. One claude-haiku-4-5 call folds them (plus any prior
    summary) into an updated summary; the folded turns are dropped from the
    verbatim list.

    Returns compression info {turns_compressed_now, model, input_tokens,
    output_tokens} when it fired, else None. Raises on LLM failure — a failed
    compression must not silently drop history.
    """
    if len(conv["turns"]) <= COMPRESS_WHEN_OVER:
        return None

    n_fold = len(conv["turns"]) - RECENT_TURNS_VERBATIM
    to_fold = conv["turns"][:n_fold]

    prior = (
        f"EXISTING SUMMARY (earlier turns already compressed):\n{conv['summary']}\n\n"
        if conv.get("summary") else ""
    )
    user_prompt = (
        f"{_SUMMARY_INSTRUCTIONS}\n\n"
        f"{prior}"
        f"TURNS TO FOLD IN:\n\n{_render_turns(to_fold)}"
    )

    llm = get_llm_provider(model=SUMMARY_MODEL)
    full = llm.complete_full(
        system=_SUMMARY_SYSTEM,
        user=user_prompt,
        max_tokens=_SUMMARY_MAX_TOKENS,
    )

    conv["summary"] = full["text"].strip()
    conv["turns_compressed"] += n_fold
    conv["turns"] = conv["turns"][n_fold:]
    conv["summary_meta"] = {
        "model": llm.model_name,
        "updated_at": _now_iso(),
        "input_tokens": int(full.get("input_tokens", 0)),
        "output_tokens": int(full.get("output_tokens", 0)),
    }
    logger.info(
        "Compressed %d turn(s) into summary (conversation=%s, model=%s).",
        n_fold, conv["conversation_id"], llm.model_name,
    )
    return {
        "turns_compressed_now": n_fold,
        "model": llm.model_name,
        "input_tokens": conv["summary_meta"]["input_tokens"],
        "output_tokens": conv["summary_meta"]["output_tokens"],
    }
