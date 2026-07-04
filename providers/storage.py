"""
Object storage provider abstraction — same pattern as llm.py / embeddings.py /
vectorstore.py: abstract interface, concrete providers behind it, factory reads
env to select. Code outside providers/ never imports a storage vendor SDK.

Architecture decision (2026-07-04, engineer-confirmed): the LIVE boat-side agent
stays local-first / offline-safe — LocalFsStorage is the default and requires no
network. Object storage (Supabase) is for the BACK-OFFICE side (ingestion/vision
pipeline output review) which already requires internet (Drive + Claude API), so
it is never a new offline dependency. Never used for anything the live retrieval
path needs to answer a question while the vessel is offline.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import config


class ObjectStorage(ABC):
    """Abstract object storage interface. All concrete providers must implement this."""

    @abstractmethod
    def put(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        """Store bytes under `key`. Returns a locator (path or URL) to read it back."""
        ...

    @abstractmethod
    def get(self, key: str) -> Optional[bytes]:
        """Fetch bytes for `key`. None if not found."""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    def url(self, key: str) -> Optional[str]:
        """A reference for humans/logs (local path or a signed/public URL). May be None."""
        ...


class LocalFsStorage(ObjectStorage):
    """Default provider — plain files under data/images/<vessel>/. No network,
    no credentials, works fully offline. This is what the vessel-side agent uses."""

    def __init__(self, root: Optional[Path] = None):
        self.root = root or (config.DATA_DIR / "images" / config.VESSEL_NAMESPACE)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / key

    def put(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return str(p)

    def get(self, key: str) -> Optional[bytes]:
        p = self._path(key)
        return p.read_bytes() if p.exists() else None

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def url(self, key: str) -> Optional[str]:
        p = self._path(key)
        return str(p) if p.exists() else None


class SupabaseStorage(ObjectStorage):
    """
    Supabase Storage (S3-compatible object storage over Postgres/Auth). Intended
    for the BACK-OFFICE side — derived vision-pipeline images (rendered schematic
    crops, described figures) reviewed during ingestion — NOT a dependency of the
    live vessel-side retrieval path.

    Requires SUPABASE_URL + SUPABASE_SERVICE_KEY (or SUPABASE_ANON_KEY for
    read-only) in .env — never hardcoded, never committed. Bucket name defaults
    to the vessel namespace so multiple vessels don't collide.
    """

    def __init__(self, bucket: Optional[str] = None):
        try:
            from supabase import create_client
        except ImportError as e:
            raise ImportError(
                "SupabaseStorage requires the 'supabase' package. "
                "pip install supabase, and set SUPABASE_URL / SUPABASE_SERVICE_KEY in .env."
            ) from e
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY (or SUPABASE_ANON_KEY) must be set in .env "
                "to use SupabaseStorage. Never commit these — .env is gitignored."
            )
        self._client = create_client(url, key)
        self.bucket = bucket or config.VESSEL_NAMESPACE

    def put(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        self._client.storage.from_(self.bucket).upload(
            key, data, {"content-type": content_type, "upsert": "true"})
        return self.url(key) or key

    def get(self, key: str) -> Optional[bytes]:
        try:
            return self._client.storage.from_(self.bucket).download(key)
        except Exception:
            return None

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def url(self, key: str) -> Optional[str]:
        try:
            return self._client.storage.from_(self.bucket).get_public_url(key)
        except Exception:
            return None


def get_storage_provider() -> ObjectStorage:
    """Factory: read env, return configured provider. Defaults to local (offline-safe)."""
    provider = os.getenv("OBJECT_STORAGE_PROVIDER", "local").lower()
    if provider == "local":
        return LocalFsStorage()
    if provider == "supabase":
        return SupabaseStorage()
    raise NotImplementedError(
        f"OBJECT_STORAGE_PROVIDER='{provider}' not implemented. "
        f"Add a new class extending ObjectStorage and wire it in here."
    )
