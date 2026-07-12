"""
One-time (online) seeding of the repo-local tiktoken cache.

Run this ONCE on a machine with internet access:

    python3 -m tools.seed_tiktoken_cache

It downloads tiktoken's cl100k_base encoding data into data/tiktoken_cache/
(pinned by config.TIKTOKEN_CACHE_DIR). After that, every import and token
count works fully offline — including on the boat laptop.

The cache directory is safe to commit to git (~1.7 MB, one static data file)
so fresh clones are offline-ready without ever running this script.
"""
from __future__ import annotations

import sys

import config
from pipeline.tokens import get_encoder


def main() -> int:
    print(f"Cache dir: {config.TIKTOKEN_CACHE_DIR}")
    config.TIKTOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        enc = get_encoder()
    except RuntimeError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        print("This script needs internet access the first time it runs.", file=sys.stderr)
        return 1
    n = enc.encode("seed check: SY Gelliceaux")
    files = sorted(p.name for p in config.TIKTOKEN_CACHE_DIR.iterdir())
    print(f"OK: encoder live ({len(n)} tokens on the check string).")
    print(f"Cache files: {files or 'NONE — encoder loaded from elsewhere (already-warm OS cache?)'}")
    if not files:
        print("NOTE: if the list is empty, tiktoken found an old cache outside the repo. "
              "Clear it or ignore — but the repo-local cache only becomes portable "
              "once files land here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
