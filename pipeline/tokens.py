"""
Lazy, offline-safe token counting (tiktoken cl100k_base).

WHY THIS EXISTS: tiktoken downloads its encoding data file from the internet
the first time get_encoding() runs. The old pattern — calling it at MODULE
IMPORT in chunk.py and parsers.py — meant the whole ingestion pipeline could
not even be imported on a machine without network + a warm cache (verified
live 2026-07-12: `import pipeline.chunk` failed offline). That violates the
offline-first principle for anything the boat laptop runs.

Fixes here:
  1. The encoder loads LAZILY on first use, never at import.
  2. The cache directory is pinned INSIDE the repo (data/tiktoken_cache, via
     config.TIKTOKEN_CACHE_DIR) so a seeded cache travels with the project
     and survives OS cache cleanup.
  3. Failure is loud and actionable: the error names the one-time seeding
     command instead of a bare urllib traceback.

Seed once while online:  python3 -m tools.seed_tiktoken_cache
"""
from __future__ import annotations

import functools

import config  # sets TIKTOKEN_CACHE_DIR before tiktoken ever loads


@functools.lru_cache(maxsize=1)
def get_encoder():
    """The shared cl100k_base encoder, loaded on first use (cached)."""
    import tiktoken
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        raise RuntimeError(
            "tiktoken could not load its cl100k_base encoding data. On first "
            "use it downloads a file from the internet; offline it needs a "
            "pre-seeded cache. Run once while online: "
            "python3 -m tools.seed_tiktoken_cache  "
            f"(cache dir: {config.TIKTOKEN_CACHE_DIR})"
        ) from e


def count_tokens(text: str) -> int:
    """Token count of `text` under cl100k_base."""
    return len(get_encoder().encode(text))
