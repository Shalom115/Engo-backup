"""
Retrieval evaluation harness (Ch 4.4 S2).

Query set × expected source documents × scored relevance, at the RETRIEVAL
level only: calls pipeline.retrieve.search() (one Voyage embedding per query
+ local Chroma search). No Anthropic calls, no agent loop.

HARD RULE (documented in CLAUDE.md "Known unresolved questions"): assert
"expected document appears in top-k", NEVER exact rank — Voyage embeddings
are non-deterministic across calls, so near-equal distances reorder.

Query set lives in tests/eval_queries_gelliceaux.json so the engineer can
extend it without touching code. Entries with empty ``expected_files`` are
known-absent probes: no relevance assertion; the harness records the best
distance (the data point for the deferred ~0.6 distance-threshold decision).

Run:
    PYTHONPATH=. python3.12 -m tests.eval_harness
    PYTHONPATH=. python3.12 -m tests.eval_harness --queries path/to/other.json

Output: data/state/eval_baseline_<YYYYMMDD>.json with per-query results
(hit@k, matched_file, best_distance, all top-k distances) + aggregate
hit-rate + distance-distribution stats for the threshold decision.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import config
from pipeline.retrieve import search

QUERIES_PATH = Path(__file__).parent / "eval_queries_gelliceaux.json"


def _chunk_file_name(metadata: Dict[str, Any]) -> str:
    """Best-available source-file identifier for a retrieved chunk."""
    return str(
        metadata.get("file_name")
        or metadata.get("display_name")
        or metadata.get("source")
        or ""
    )


def _match_expected(file_name: str, patterns: List[str]) -> Optional[str]:
    """Return the first pattern that matches (case-insensitive substring), else None."""
    lower = file_name.lower()
    for p in patterns:
        if p.lower() in lower:
            return p
    return None


def run_query(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run one eval query through the real retrieval path.

    Returns a result dict: {id, query, k, expected_files, retrieved:[...],
    hit_at_k, matched_file, matched_pattern, best_distance, distances}.
    For known-absent entries (expected_files == []), hit_at_k is None and
    only distances are recorded.
    """
    query: str = entry["query"]
    k: int = int(entry.get("k", 5))
    expected: List[str] = entry.get("expected_files", [])

    results = search(query, k=k)

    retrieved = []
    matched_file: Optional[str] = None
    matched_pattern: Optional[str] = None
    matched_rank: Optional[int] = None  # informational only — NEVER asserted on
    for rank, r in enumerate(results, start=1):
        fname = _chunk_file_name(r.get("metadata") or {})
        retrieved.append(
            {
                "rank": rank,
                "file_name": fname,
                "chunk_id": r["id"],
                "distance": round(float(r["distance"]), 4),
            }
        )
        if expected and matched_file is None:
            pat = _match_expected(fname, expected)
            if pat is not None:
                matched_file = fname
                matched_pattern = pat
                matched_rank = rank

    distances = [r["distance"] for r in retrieved]
    return {
        "id": entry["id"],
        "query": query,
        "k": k,
        "expected_files": expected,
        "known_absent": not expected,
        # membership-in-top-k only; None for known-absent probes.
        "hit_at_k": (matched_file is not None) if expected else None,
        "matched_file": matched_file,
        "matched_pattern": matched_pattern,
        "matched_rank_informational": matched_rank,
        "best_distance": distances[0] if distances else None,
        "distances": distances,
        "retrieved": retrieved,
        "notes": entry.get("notes", ""),
    }


def _distance_stats(values: List[float]) -> Dict[str, float]:
    if not values:
        return {}
    return {
        "n": len(values),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "mean": round(statistics.fmean(values), 4),
        "median": round(statistics.median(values), 4),
    }


def run(queries_path: Path = QUERIES_PATH) -> Dict[str, Any]:
    """Run the full query set; return the report dict (also written to data/state/)."""
    spec = json.loads(queries_path.read_text())
    entries: List[Dict[str, Any]] = spec["queries"]

    results = [run_query(e) for e in entries]

    scored = [r for r in results if not r["known_absent"]]
    hits = [r for r in scored if r["hit_at_k"]]
    misses = [r for r in scored if not r["hit_at_k"]]

    # Distance distributions for the deferred ~0.6 threshold decision:
    # - matched-chunk distances (relevant material — a threshold must keep these)
    # - known-absent best distances (irrelevant best-of-what's-there — a
    #   threshold would ideally drop these)
    hit_match_distances = [
        r["distances"][r["matched_rank_informational"] - 1] for r in hits
    ]
    absent_best_distances = [
        r["best_distance"] for r in results if r["known_absent"] and r["best_distance"] is not None
    ]

    report: Dict[str, Any] = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "vessel_namespace": config.VESSEL_NAMESPACE,
        "queries_file": str(queries_path),
        "retrieval_distance_threshold_in_effect": config.RETRIEVAL_DISTANCE_THRESHOLD,
        "assertion_policy": "expected document appears in top-k; exact rank NEVER asserted (Voyage non-determinism)",
        "aggregate": {
            "scored_queries": len(scored),
            "hits": len(hits),
            "misses": len(misses),
            "hit_rate": round(len(hits) / len(scored), 4) if scored else None,
            "known_absent_probes": len(results) - len(scored),
            "miss_ids": [r["id"] for r in misses],
        },
        "threshold_stats": {
            "matched_chunk_distances": _distance_stats(hit_match_distances),
            "matched_chunk_distance_values": [round(d, 4) for d in hit_match_distances],
            "known_absent_best_distances": [round(d, 4) for d in absent_best_distances],
            "note": (
                "A distance threshold must sit ABOVE max(matched_chunk_distances) "
                "and ideally BELOW min(known_absent_best_distances). Observation "
                "only — tuning stays deferred per CLAUDE.md until the engineer decides."
            ),
        },
        "results": results,
    }

    date_tag = datetime.now(timezone.utc).strftime("%Y%m%d")
    out_path = config.STATE_DIR / f"eval_baseline_{date_tag}.json"
    out_path.write_text(json.dumps(report, indent=2))
    report["report_path"] = str(out_path)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Engo retrieval eval harness (retrieval-level only).")
    ap.add_argument("--queries", type=Path, default=QUERIES_PATH, help="Path to the query-set JSON.")
    args = ap.parse_args()

    report = run(args.queries)

    agg = report["aggregate"]
    print(f"\n=== Retrieval eval baseline — {report['ran_at']} ===")
    print(f"Collection: {report['vessel_namespace']}   "
          f"threshold in effect: {report['retrieval_distance_threshold_in_effect']}")
    print(f"{'id':38} {'hit@k':6} {'match_d':8} {'best_d':7} matched_file")
    for r in report["results"]:
        if r["known_absent"]:
            flag, match_d = "ABSENT", "-"
        else:
            flag = "HIT" if r["hit_at_k"] else "MISS"
            match_d = (
                f"{r['distances'][r['matched_rank_informational'] - 1]:.4f}"
                if r["hit_at_k"] else "-"
            )
        best = f"{r['best_distance']:.4f}" if r["best_distance"] is not None else "-"
        print(f"{r['id']:38} {flag:6} {match_d:8} {best:7} {r['matched_file'] or '-'}")
    print(f"\nHit rate: {agg['hits']}/{agg['scored_queries']} = {agg['hit_rate']}")
    if agg["miss_ids"]:
        print(f"MISSES (findings, not pattern-loosening targets): {agg['miss_ids']}")
    ts = report["threshold_stats"]
    print(f"Matched-chunk distances: {ts['matched_chunk_distance_values']}")
    print(f"Known-absent best distances: {ts['known_absent_best_distances']}")
    print(f"Report: {report['report_path']}")
    return 0 if not agg["miss_ids"] else 1


if __name__ == "__main__":
    sys.exit(main())
