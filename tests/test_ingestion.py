"""
Ingestion smoke test.

Usage:
    python tests/test_ingestion.py <path/to/pdf> "<query string>"

Steps:
  1. Ingest the PDF.
  2. Print the ingest summary.
  3. Run the query.
  4. Print the top 3 results: filename, page range, distance, first 200 chars.

Idempotency: re-running on the same file should report `skipped: True`.
"""
import sys
from pathlib import Path

# Make project root importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: F401  -- triggers .env loading
from pipeline.ingest import ingest_file
from pipeline.retrieve import search


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python tests/test_ingestion.py <pdf_path> <query>")
        sys.exit(2)

    pdf_path = Path(sys.argv[1]).expanduser().resolve()
    query = sys.argv[2]

    print("=" * 60)
    print(f"INGEST: {pdf_path.name}")
    print("=" * 60)
    summary = ingest_file(pdf_path)
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print()

    print("=" * 60)
    print(f"QUERY: {query}")
    print("=" * 60)
    results = search(query, k=3)
    if not results:
        print("  No results.")
        sys.exit(1)

    for i, r in enumerate(results, start=1):
        meta = r["metadata"]
        snippet = r["text"][:200].replace("\n", " ")
        print(f"\n  [{i}] {meta.get('file_name', '?')}  "
              f"pages {meta.get('page_start')}–{meta.get('page_end')}  "
              f"distance={r['distance']:.4f}")
        print(f"      {snippet}{'...' if len(r['text']) > 200 else ''}")
    print()


if __name__ == "__main__":
    main()
