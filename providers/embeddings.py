"""
Embedding provider abstraction.

Same pattern as llm.py — abstract interface, concrete providers behind it,
factory reads env to select. Voyage today, anything tomorrow.
"""
from abc import ABC, abstractmethod
from typing import List
import os


class EmbeddingProvider(ABC):
    """Abstract embedding interface. All concrete providers must implement this."""

    @abstractmethod
    def embed(self, texts: List[str], input_type: str = "document") -> List[List[float]]:
        """
        Convert texts into vectors.
        input_type: 'document' for indexing, 'query' for retrieval.
        """
        ...

    @property
    @abstractmethod
    def dimensions(self) -> int:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...


class VoyageProvider(EmbeddingProvider):
    """Concrete Voyage AI implementation."""

    # Known Voyage model dimensions. Update if Voyage adds new models.
    _MODEL_DIMS = {
        "voyage-3": 1024,
        "voyage-3-large": 2048,
        "voyage-3-lite": 512,
        "voyage-code-3": 1024,
    }

    def __init__(self, api_key: str, model: str):
        import voyageai
        self._client = voyageai.Client(api_key=api_key)
        self._model = model
        self._dims = self._MODEL_DIMS.get(model, 1024)

    def embed(self, texts: List[str], input_type: str = "document") -> List[List[float]]:
        result = self._client.embed(texts, model=self._model, input_type=input_type)
        return result.embeddings

    @property
    def dimensions(self) -> int:
        return self._dims

    @property
    def model_name(self) -> str:
        return self._model


def get_embedding_provider() -> EmbeddingProvider:
    """Factory: read env, return configured provider."""
    provider = os.getenv("EMBEDDING_PROVIDER", "voyage").lower()

    if provider == "voyage":
        api_key = os.getenv("VOYAGE_API_KEY")
        if not api_key:
            raise RuntimeError("VOYAGE_API_KEY not set in .env")
        model = os.getenv("VOYAGE_MODEL", "voyage-3")
        return VoyageProvider(api_key=api_key, model=model)

    raise NotImplementedError(
        f"EMBEDDING_PROVIDER='{provider}' not implemented yet. "
        f"Add a new class extending EmbeddingProvider in this file and wire it in here."
    )
