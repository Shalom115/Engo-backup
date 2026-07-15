"""
Retrieval — query string → top-k chunks with metadata.

Embeds the query with input_type='query' (NOT 'document' — Voyage uses
different prompts for the two sides of the retrieval pair), then queries
the configured vector store.

Optional metadata pre-filter (Chroma where=) and optional distance
threshold filter (drops weak matches rather than returning them).
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import config
from providers.embeddings import get_embedding_provider
from providers.vectorstore import get_vectorstore_provider

logger = logging.getLogger("pipeline.retrieve")

_HYDE_SUFFIX_RE = re.compile(r":q\d+$")


def _dedup_hyde(results: List[Dict[str, Any]], k: int) -> List[Dict[str, Any]]:
    """
    Deduplicate HyDE question entries from a raw search result list.

    HyDE chunks share the same source text as their original chunk and carry IDs
    of the form ``{original_id}:qN``.  Multiple HyDE entries for the same source
    chunk can occupy several slots in the raw top-k, which would waste context
    window with repeated text.

    Strategy: strip the ``:qN`` suffix to get the canonical chunk ID; keep only
    the first (lowest-distance) hit per canonical ID; normalise the returned ID
    to the canonical form.  Stop once ``k`` distinct chunks are collected.
    """
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for r in results:
        canonical = _HYDE_SUFFIX_RE.sub("", r["id"])
        if canonical not in seen:
            seen.add(canonical)
            out.append({**r, "id": canonical})
            if len(out) == k:
                break
    return out


def search(
    query: str,
    k: int = 5,
    filters: Optional[Dict[str, Any]] = None,
    distance_threshold: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Run a retrieval query.

    Args:
        query: natural-language query string.
        k: number of nearest neighbours to return.
        filters: optional Chroma `where` filter on metadata
                 (e.g. {"sfi_section": "400"}).
        distance_threshold: if provided, results with distance > threshold
                            are dropped. If `None`, falls back to
                            config.RETRIEVAL_DISTANCE_THRESHOLD (which is
                            also `None` unless set in .env). When the
                            effective threshold is None, no filtering.

    Returns:
        List of dicts: {id, text, metadata, distance}, sorted by distance
        ascending. Empty list if collection is empty or no result clears
        the threshold.
    """
    if not query or not query.strip():
        raise ValueError("Empty query string.")
    if k <= 0:
        raise ValueError(f"k must be > 0, got {k}")

    embedder = get_embedding_provider()
    store = get_vectorstore_provider()

    vec = embedder.embed([query], input_type="query")[0]
    # Over-fetch by 6× so deduplication (HyDE entries per source chunk) still
    # yields k distinct source chunks after filtering. With full HyDE coverage
    # a chunk carries up to 5 question entries + itself, so a 3× over-fetch
    # could collapse to fewer than k distinct chunks in the worst case.
    results = store.search(vector=vec, k=k * 6, filters=filters)
    results = _dedup_hyde(results, k)

    # Cosine distance in ChromaDB is in [0, 2]: 0 = identical, 1 = orthogonal, 2 = opposite.
    # Lower is closer. Typical "good match" threshold for voyage-3 is around 0.3–0.5; tune empirically.
    effective_threshold = (
        distance_threshold
        if distance_threshold is not None
        else config.RETRIEVAL_DISTANCE_THRESHOLD
    )
    if effective_threshold is not None:
        before = len(results)
        results = [r for r in results if r["distance"] <= effective_threshold]
        logger.debug(
            "Distance filter %.4f: %d/%d kept.",
            effective_threshold, len(results), before,
        )

    return results
