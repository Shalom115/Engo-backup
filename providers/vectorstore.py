"""
Vector store provider abstraction.

Same pattern as llm.py and embeddings.py — abstract interface, concrete
providers behind it, factory reads env to select. ChromaDB today, anything
tomorrow. Code outside providers/ never imports chromadb.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import config


class VectorStore(ABC):
    """Abstract vector store interface. All concrete providers must implement this."""

    @abstractmethod
    def add(
        self,
        ids: List[str],
        vectors: List[List[float]],
        texts: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """Insert chunks. Atomic per call: either all succeed or the call raises."""
        ...

    @abstractmethod
    def search(
        self,
        vector: List[float],
        k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Nearest-neighbour search.

        Returns a list of dicts: {id, text, metadata, distance}.
        Empty list if collection is empty or no results match filters.
        """
        ...

    @abstractmethod
    def exists(self, file_hash: str) -> bool:
        """True if any chunk with this file_hash is already stored."""
        ...

    @abstractmethod
    def count(self) -> int:
        """Total chunks in the active collection. Useful for diagnostics."""
        ...

    @abstractmethod
    def delete_by_source(self, file_name: str) -> int:
        """
        Delete all chunks whose metadata field ``file_name`` matches the given
        value.  Returns the number of chunks deleted.  Used by the ingest
        ``--refresh`` path to purge stale chunks before re-ingesting a live
        document.
        """
        ...

    @abstractmethod
    def get_all(
        self,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch all chunks, optionally filtered by a metadata where-clause.
        Returns a list of {id, text, metadata} dicts.
        Used by the HyDE pipeline to iterate over ingested chunks.
        """
        ...


class ChromaProvider(VectorStore):
    """Concrete ChromaDB implementation. Persistent client at config.CHROMA_DIR."""

    def __init__(self, persist_dir: str, collection_name: str):
        import chromadb
        from chromadb.config import Settings

        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        # cosine distance is the right default for normalized embedding vectors.
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._collection_name = collection_name

    def add(
        self,
        ids: List[str],
        vectors: List[List[float]],
        texts: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        if not (len(ids) == len(vectors) == len(texts) == len(metadatas)):
            raise ValueError(
                f"add() length mismatch: ids={len(ids)} vectors={len(vectors)} "
                f"texts={len(texts)} metadatas={len(metadatas)}"
            )
        if not ids:
            return
        # Chroma rejects None values in metadata — strip them defensively.
        clean_metas = [{k: v for k, v in m.items() if v is not None} for m in metadatas]
        self._collection.upsert(
            ids=ids,
            embeddings=vectors,
            documents=texts,
            metadatas=clean_metas,
        )

    def search(
        self,
        vector: List[float],
        k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if self._collection.count() == 0:
            return []
        kwargs: Dict[str, Any] = {
            "query_embeddings": [vector],
            "n_results": k,
        }
        if filters:
            kwargs["where"] = filters
        res = self._collection.query(**kwargs)
        # Chroma returns lists-of-lists keyed by query; we send one query, take index 0.
        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        return [
            {"id": i, "text": d, "metadata": m, "distance": float(dist)}
            for i, d, m, dist in zip(ids, docs, metas, dists)
        ]

    def exists(self, file_hash: str) -> bool:
        res = self._collection.get(where={"file_hash": file_hash}, limit=1)
        return bool(res.get("ids"))

    def count(self) -> int:
        return self._collection.count()

    def delete_by_source(self, file_name: str) -> int:
        """
        Delete every chunk where metadata ``file_name`` matches the given value.
        Fetches IDs first (so we can count them), then deletes by ID list.
        Returns deleted count.
        """
        res = self._collection.get(where={"file_name": file_name})
        ids = res.get("ids") or []
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)

    def delete_where(self, where: Dict[str, Any]) -> int:
        """
        Delete every chunk matching a metadata where-clause. Fetches IDs first
        (for the count), then deletes by ID list. Returns deleted count.
        """
        res = self._collection.get(where=where)
        ids = res.get("ids") or []
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)

    def set_metadata_where(self, where: Dict[str, Any], updates: Dict[str, Any]) -> int:
        """
        Merge ``updates`` into the metadata of every chunk matching ``where``,
        in place (no re-embedding). Fetches matching ids + current metadata,
        merges, and writes back via Chroma's update. Returns updated count.
        """
        res = self._collection.get(where=where, include=["metadatas"])
        ids = res.get("ids") or []
        metas = res.get("metadatas") or []
        if not ids:
            return 0
        merged = [{**(m or {}), **updates} for m in metas]
        self._collection.update(ids=ids, metadatas=merged)
        return len(ids)

    def get_all(
        self,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch all chunks (or a filtered subset).  Returns {id, text, metadata}
        per chunk.  Fetches documents and metadatas explicitly; embeddings are
        not returned (no need, and they are large).
        """
        kwargs: Dict[str, Any] = {"include": ["documents", "metadatas"]}
        if where:
            kwargs["where"] = where
        res = self._collection.get(**kwargs)
        ids = res.get("ids") or []
        docs = res.get("documents") or []
        metas = res.get("metadatas") or []
        return [
            {"id": i, "text": d, "metadata": m}
            for i, d, m in zip(ids, docs, metas)
        ]


def get_vectorstore_provider() -> VectorStore:
    """Factory: read env, return configured provider."""
    provider = os.getenv("VECTOR_DB_PROVIDER", "chromadb").lower()

    if provider in ("chromadb", "chroma"):
        return ChromaProvider(
            persist_dir=str(config.CHROMA_DIR),
            collection_name=config.VESSEL_NAMESPACE,
        )

    raise NotImplementedError(
        f"VECTOR_DB_PROVIDER='{provider}' not implemented yet. "
        f"Add a new class extending VectorStore and wire it in here."
    )
