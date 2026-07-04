"""
Structure provider abstraction — the read-only source of a vessel's folder tree.

Same pattern as llm / embeddings / vectorstore: an abstract interface with
swappable concrete providers. The Equipment Register builder consumes a
``StructureProvider`` and never knows or cares where the tree came from — Google
Drive today, a local NAS dump, SharePoint, or a zip tomorrow. This is the
model-agnostic rule (architecture rule #1) applied to the document source.

A node is a plain dict (uniform across providers):
    {id, name, type ("folder"|"file"), mime, parentId, path,
     region, fileSize, ext, modifiedTime}

Two providers ship here:
  - SnapshotStructureProvider: reads a materialised structure_<vessel>.json
    (produced by the agent-mediated walk via pipeline.walk_assemble). Pure,
    offline, deterministic — used to build/validate the Register and for the
    folder-only onboarding seam.
  - GoogleDriveStructureProvider: walks a live Drive folder via the Drive API.
    Requires a read-only credential (see setup guide). This is the Phase-2
    multi-vessel path; it produces the same node shape as the snapshot.

VIDEO/FLEET SEAM: nodes are source-tagged dicts, so a future video provider
(frames + transcript) or a cross-vessel fleet index can produce/consume the same
shape without re-architecting.
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

import config

FOLDER_MIME = "application/vnd.google-apps.folder"


class StructureProvider(ABC):
    """Abstract read-only vessel-structure source."""

    @abstractmethod
    def walk(self) -> List[Dict[str, Any]]:
        """
        Return every node (folders AND files) as a flat list of dicts with at
        least {id, name, type, mime, parentId, path}. Order is not guaranteed;
        consumers build their own parent/child index.
        """
        ...

    @property
    @abstractmethod
    def root_id(self) -> str:
        ...


class SnapshotStructureProvider(StructureProvider):
    """Reads a materialised structure_<vessel>.json produced by walk_assemble."""

    def __init__(self, structure_path: Optional[Path] = None):
        self._path = Path(structure_path) if structure_path else (
            config.STATE_DIR / f"structure_{config.VESSEL_NAMESPACE}.json"
        )
        if not self._path.exists():
            raise FileNotFoundError(
                f"Structure snapshot not found: {self._path}. "
                f"Run the Drive walk first (pipeline.walk_assemble --emit)."
            )
        self._data = json.loads(self._path.read_text(encoding="utf-8"))

    def walk(self) -> List[Dict[str, Any]]:
        return list(self._data.get("nodes", []))

    @property
    def root_id(self) -> str:
        return self._data["root_id"]

    @property
    def walked_at(self) -> str:
        return self._data.get("walked_at", "")

    @property
    def unwalked(self) -> List[Dict[str, Any]]:
        """Folders discovered but not yet walked (incomplete-snapshot guard)."""
        return list(self._data.get("unwalked", []))


class GoogleDriveStructureProvider(StructureProvider):
    """
    Live read-only walk of a Google Drive folder tree via the Drive API.

    Requires a read-only credential. Two supported credential modes (env):
      GDRIVE_SERVICE_ACCOUNT_JSON = /path/to/service-account.json   (recommended)
      GDRIVE_OAUTH_TOKEN_JSON     = /path/to/authorized-user.json

    The Drive folder must be shared with the service-account email (viewer).
    Walks breadth-first, paginating each folder, and emits the same node shape as
    the snapshot provider. Heavy lifting (downloads) lives in the ingest layer;
    this class only enumerates the tree.
    """

    def __init__(self, root_id: str, root_name: str = ""):
        self._root_id = root_id
        self._root_name = root_name or root_id
        self._service = self._build_service()

    def _build_service(self):
        # Lazy imports so the rest of the system runs without google libs installed.
        sa = os.getenv("GDRIVE_SERVICE_ACCOUNT_JSON")
        oauth = os.getenv("GDRIVE_OAUTH_TOKEN_JSON")
        try:
            from googleapiclient.discovery import build  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "google-api-python-client not installed. "
                "pip install google-api-python-client google-auth"
            ) from e

        if sa:
            from google.oauth2 import service_account  # type: ignore
            creds = service_account.Credentials.from_service_account_file(
                sa, scopes=["https://www.googleapis.com/auth/drive.readonly"]
            )
        elif oauth:
            from google.oauth2.credentials import Credentials  # type: ignore
            creds = Credentials.from_authorized_user_file(
                oauth, scopes=["https://www.googleapis.com/auth/drive.readonly"]
            )
        else:
            raise RuntimeError(
                "No Drive credential set. Set GDRIVE_SERVICE_ACCOUNT_JSON "
                "or GDRIVE_OAUTH_TOKEN_JSON in .env."
            )
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    def walk(self) -> List[Dict[str, Any]]:
        nodes: Dict[str, Dict[str, Any]] = {
            self._root_id: {
                "id": self._root_id, "name": self._root_name, "type": "folder",
                "mime": FOLDER_MIME, "parentId": None,
            }
        }
        frontier = [self._root_id]
        while frontier:
            parent = frontier.pop()
            page_token = None
            while True:
                resp = self._service.files().list(
                    q=f"'{parent}' in parents and trashed=false",
                    fields=("nextPageToken, files(id, name, mimeType, "
                            "size, fileExtension, modifiedTime)"),
                    pageSize=1000,
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                ).execute()
                for f in resp.get("files", []):
                    is_folder = f["mimeType"] == FOLDER_MIME
                    nodes[f["id"]] = {
                        "id": f["id"], "name": f.get("name", ""),
                        "type": "folder" if is_folder else "file",
                        "mime": f["mimeType"], "parentId": parent,
                        "fileSize": int(f["size"]) if f.get("size") else None,
                        "ext": f.get("fileExtension"),
                        "modifiedTime": f.get("modifiedTime"),
                    }
                    if is_folder:
                        frontier.append(f["id"])
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break

        # Compute paths.
        def path_of(nid: str) -> str:
            parts: List[str] = []
            seen: set = set()
            cur: Optional[str] = nid
            while cur and cur in nodes and cur not in seen:
                seen.add(cur)
                parts.append(nodes[cur]["name"])
                cur = nodes[cur]["parentId"]
            return "/".join(reversed(parts))

        for nid, n in nodes.items():
            n["path"] = path_of(nid)
        return list(nodes.values())

    @property
    def root_id(self) -> str:
        return self._root_id

    # Google-native types must be exported to a parseable format.
    _EXPORT = {
        "application/vnd.google-apps.document":
            ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
        "application/vnd.google-apps.spreadsheet":
            ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
        "application/vnd.google-apps.presentation":
            ("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
    }

    def file_meta(self, file_id: str) -> Dict[str, Any]:
        """
        Name / mimeType / size for a single file id. For loose files referenced
        by id that were never part of a tree walk (e.g. handover docs outside
        SWS 108-01), so the caller can route the parser without guessing.
        """
        return self._service.files().get(
            fileId=file_id,
            fields="id, name, mimeType, size, fileExtension, modifiedTime",
            supportsAllDrives=True,
        ).execute()

    def download_bytes(self, file_id: str, mime: str):
        """
        Fetch a Drive file's content as bytes. Google-native files are exported
        to an Office format; everything else is downloaded as-is. Returns
        (data, suffix) where suffix is set only for exported native files.
        """
        if mime in self._EXPORT:
            target, suffix = self._EXPORT[mime]
            data = self._service.files().export_media(
                fileId=file_id, mimeType=target).execute()
            return data, suffix
        data = self._service.files().get_media(
            fileId=file_id, supportsAllDrives=True).execute()
        return data, None


def get_structure_provider(**kwargs) -> StructureProvider:
    """
    Factory. STRUCTURE_PROVIDER env selects the source:
        "snapshot" (default) -> SnapshotStructureProvider
        "gdrive"             -> GoogleDriveStructureProvider (needs root_id, creds)
    """
    provider = os.getenv("STRUCTURE_PROVIDER", "snapshot").lower()
    if provider == "snapshot":
        return SnapshotStructureProvider(kwargs.get("structure_path"))
    if provider in ("gdrive", "googledrive", "drive"):
        return GoogleDriveStructureProvider(
            root_id=kwargs["root_id"], root_name=kwargs.get("root_name", ""),
        )
    raise NotImplementedError(f"STRUCTURE_PROVIDER='{provider}' not implemented.")
