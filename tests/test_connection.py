"""
Smoke test.

Confirms:
  1. .env is loaded correctly
  2. Anthropic API key is valid and we can talk to Claude
  3. Voyage API key is valid and we can embed text
  4. The model-agnostic abstraction layer is wired correctly

Run from project root:
    python tests/test_connection.py

If both checks pass, the foundation is sound. We can build on it.
"""
import sys
from pathlib import Path

# Make project root importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: F401  -- triggers .env loading
from providers.llm import get_llm_provider
from providers.embeddings import get_embedding_provider


def test_llm() -> None:
    print("=" * 60)
    print("LLM CHECK")
    print("=" * 60)
    llm = get_llm_provider()
    print(f"Provider model: {llm.model_name}")
    print("Calling API...")

    response = llm.complete(
        system=(
            "You are an experienced marine engineer aboard SY Gelliceaux, "
            "a Southern Wind 108 hybrid sailing yacht. Reply in one short sentence."
        ),
        user="What does ACTM stand for in BAE HybriGen propulsion?",
        max_tokens=200,
    )
    print(f"Response: {response}")
    print("LLM check: OK\n")


def test_embeddings() -> None:
    print("=" * 60)
    print("EMBEDDINGS CHECK")
    print("=" * 60)
    emb = get_embedding_provider()
    print(f"Provider model: {emb.model_name} ({emb.dimensions} dimensions)")
    print("Calling API...")

    sample = "BAE HDS 200 traction motor cooling fault during HEV mode"
    vectors = emb.embed([sample], input_type="document")
    print(f"Got {len(vectors)} vector(s) of {len(vectors[0])} dimensions")
    print(f"First 5 values: {[round(v, 4) for v in vectors[0][:5]]}")
    print("Embeddings check: OK\n")


if __name__ == "__main__":
    print("\nGelliceaux smoke test")
    print("-" * 60)
    print("Confirms API keys work + abstraction layer is wired.\n")

    try:
        test_llm()
        test_embeddings()
        print("=" * 60)
        print("ALL SYSTEMS GO. Foundation is sound.")
        print("=" * 60)
    except Exception as e:
        print(f"\nFAILED: {type(e).__name__}: {e}")
        sys.exit(1)
