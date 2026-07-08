"""
PMS (Planned Maintenance System) provider abstraction — same pattern as
storage.py / vectorstore.py / llm.py: abstract interface, concrete providers
behind it, factory reads env to select. Code outside providers/ never talks
to a PMS vendor SDK/API directly.

READ-ONLY BY DESIGN (architecture rule #2 extended): Engo never writes to the
PMS, same as it never writes to vessel systems — it reads schedules/history/
open-jobs to CROSS-REFERENCE against the Equipment Register, never to log
completions or edit records back. The PMS is authoritative for "what
maintenance is due / has been done"; the Register is authoritative for
"what equipment exists and how it's wired." §9e node_match.resolve() is the
join between them — a PMS equipment entry is a discovered component like
any other (nameplate, schematic, CAN topology): confident match -> attach
its schedule/history as facts on the existing node; no match -> create_
flagged (new equipment PMS knows about that the Register doesn't, or a
naming mismatch worth an engineer look), never silently guessed. Conflicts
(PMS says one model, Register says another) go through the existing
end-of-sweep confirmation-list mechanism, not a bespoke path.

VENDOR CONFIRMED 2026-07-05: **YMP (Yacht Maintenance Program)**, `www.ymponline.com`,
key-based REST API (`x-api-key` header). `YMPPMSProvider` below is the live
implementation. `LocalExportPMSProvider` (CSV-based) stays as the fallback
pattern for a future vessel whose PMS has no API access — the engineer's own
stated plan for "most boats."
"""
from __future__ import annotations

import csv
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

import config


class MaintenanceRecord(dict):
    """A single PMS record — job/history/schedule line. Kept as a plain dict
    subclass (not a rigid schema) because PMS export column names vary widely
    across vendors; callers read by key with .get()."""


class PMSProvider(ABC):
    """Abstract read-only PMS interface. All concrete providers implement this."""

    @abstractmethod
    def list_equipment(self) -> List[Dict[str, Any]]:
        """Every distinct equipment/component entry the PMS knows about.
        Each dict should carry at least a name/description field usable by
        §9e node_match.resolve() (name, make, model if present)."""
        ...

    @abstractmethod
    def get_schedule(self, equipment_ref: str) -> List[MaintenanceRecord]:
        """Planned/due maintenance items for one PMS equipment reference
        (as returned by list_equipment)."""
        ...

    @abstractmethod
    def get_history(self, equipment_ref: str) -> List[MaintenanceRecord]:
        """Completed maintenance history for one PMS equipment reference."""
        ...

    @abstractmethod
    def list_open_jobs(self) -> List[MaintenanceRecord]:
        """All currently open/outstanding jobs across the whole PMS, regardless
        of equipment — the fleet-wide 'what's due' view."""
        ...


class LocalExportPMSProvider(PMSProvider):
    """
    Reads CSV exports dropped in data/pms_export/<vessel>/. Expected files
    (any subset may be absent — missing files just mean that query returns
    empty, not an error, since PMS onboarding is expected to be incremental):
      equipment.csv   — one row per equipment/component
      schedule.csv    — one row per planned/due item, with an equipment_ref column
      history.csv     — one row per completed job, with an equipment_ref column
    Column names are read as-is from the CSV header — no fixed schema is
    assumed beyond an `equipment_ref` join column on schedule.csv/history.csv,
    since export formats vary by vendor.
    """

    def __init__(self, vessel: Optional[str] = None):
        self.vessel = vessel or config.VESSEL_NAMESPACE
        self.root = config.DATA_DIR / "pms_export" / self.vessel
        self.root.mkdir(parents=True, exist_ok=True)

    def _read_csv(self, filename: str) -> List[Dict[str, Any]]:
        path = self.root / filename
        if not path.exists():
            return []
        with path.open(newline="", encoding="utf-8-sig") as f:
            return [dict(row) for row in csv.DictReader(f)]

    def list_equipment(self) -> List[Dict[str, Any]]:
        return self._read_csv("equipment.csv")

    def get_schedule(self, equipment_ref: str) -> List[MaintenanceRecord]:
        rows = self._read_csv("schedule.csv")
        return [MaintenanceRecord(r) for r in rows if r.get("equipment_ref") == equipment_ref]

    def get_history(self, equipment_ref: str) -> List[MaintenanceRecord]:
        rows = self._read_csv("history.csv")
        return [MaintenanceRecord(r) for r in rows if r.get("equipment_ref") == equipment_ref]

    def list_open_jobs(self) -> List[MaintenanceRecord]:
        rows = self._read_csv("schedule.csv")
        return [MaintenanceRecord(r) for r in rows
                if str(r.get("status", "")).strip().lower() not in ("done", "completed", "closed")]


class YMPPMSProvider(PMSProvider):
    """
    Live YMP (Yacht Maintenance Program) API. Three endpoints, all GET, all
    read-only, all authenticated with a single `x-api-key` header:
      equipment  -> /api/group/custom/<boatID>     -> list of equipment groups
      jobs       -> /api/worklist/custom/<boatID>   -> list of maintenance job
                    templates, each with an embedded `groupID` (the equipment
                    it belongs to) and `workHistory` (completed occurrences)
      inventory  -> /api/inventory/custom/<boatID>  -> list of spares/stock

    TWO CONNECTIVITY FIXES confirmed live 2026-07-05 (not obvious from the
    vendor's own instructions doc, so documented here rather than silently
    baked in): (1) the bare "ymponline.com" hostname fails TLS/SNI — the
    server returns a TLS alert (unrecognized_name) for that exact SNI value;
    "www.ymponline.com" works. Requests are forced onto the www host
    regardless of what's configured in .env, so a future env edit back to the
    vendor doc's bare-domain URLs won't silently break this again.
    (2) the vendor doc's jobs path is `/api/worklists/custom/...` (plural) —
    that path returns the site's HTML shell, not the API; the real path is
    `/api/worklist/` (singular).

    FIELD MAPPING: list_equipment() normalizes YMP's `manufacturer`/
    `modelNumber`/`_id` to `make`/`model`/`equipment_ref` (for §9e node_match)
    while preserving every original field, including `equipmentFiles` — YMP
    links each equipment group to its actual manual PDFs (hosted on Firebase
    Storage), which is a real, usable citation source once cross-referenced.

    OPEN QUESTION, NOT GUESSED (2026-07-05): job entries carry a `status`
    boolean (~106 true / ~123 false across 229 live entries) with no
    documented meaning, plus `dateNext`/`unplanned`/`repeating`/`days` fields
    that look like a recurring-schedule model. Nothing observed yet
    distinguishes "done" from "not yet due" from "template disabled".
    `list_open_jobs()` deliberately does NOT filter on `status` — it returns
    everything, unfiltered, until the engineer confirms what the field means;
    filtering on a guessed interpretation would be exactly the kind of
    fabrication this project's discipline forbids elsewhere.
    """

    def __init__(self):
        import requests
        self._requests = requests
        self.key = os.getenv("YMP_API_KEY")
        if not self.key:
            raise RuntimeError("YMP_API_KEY must be set in .env to use YMPPMSProvider.")
        self._equipment_url = self._force_www(os.getenv("YMP_EQUIPMENT_URL"))
        self._jobs_url = self._force_www(os.getenv("YMP_JOBS_URL")).replace(
            "/api/worklists/", "/api/worklist/")
        self._inventory_url = self._force_www(os.getenv("YMP_INVENTORY_URL"))
        self._equipment_cache: Optional[List[Dict[str, Any]]] = None
        self._jobs_cache: Optional[List[Dict[str, Any]]] = None
        self._inventory_cache: Optional[List[Dict[str, Any]]] = None

    @staticmethod
    def _force_www(url: Optional[str]) -> str:
        if not url:
            raise RuntimeError("YMP endpoint URL missing from .env.")
        return url.replace("https://ymponline.com", "https://www.ymponline.com")

    def _get(self, url: str) -> List[Dict[str, Any]]:
        r = self._requests.get(url, headers={"x-api-key": self.key}, timeout=30)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list):
            raise ValueError(f"YMP API returned unexpected shape from {url}: {type(data)}")
        return data

    def list_equipment(self) -> List[Dict[str, Any]]:
        if self._equipment_cache is None:
            raw = self._get(self._equipment_url)
            self._equipment_cache = [
                {**e, "name": e.get("name"), "make": e.get("manufacturer"),
                 "model": e.get("modelNumber"), "equipment_ref": e.get("_id")}
                for e in raw
            ]
        return self._equipment_cache

    def _jobs(self) -> List[Dict[str, Any]]:
        if self._jobs_cache is None:
            self._jobs_cache = self._get(self._jobs_url)
        return self._jobs_cache

    def get_schedule(self, equipment_ref: str) -> List[MaintenanceRecord]:
        return [MaintenanceRecord(j) for j in self._jobs()
                if (j.get("groupID") or {}).get("_id") == equipment_ref]

    def get_history(self, equipment_ref: str) -> List[MaintenanceRecord]:
        out: List[MaintenanceRecord] = []
        for j in self._jobs():
            if (j.get("groupID") or {}).get("_id") != equipment_ref:
                continue
            for h in (j.get("workHistory") or []):
                out.append(MaintenanceRecord(h))
        return out

    def list_open_jobs(self) -> List[MaintenanceRecord]:
        return [MaintenanceRecord(j) for j in self._jobs()]

    def list_inventory(self) -> List[Dict[str, Any]]:
        """Not part of the abstract interface (inventory isn't schedule/
        history/equipment) but real and useful — exposed as an extra method
        on this concrete provider. 615 live items, each with locationBox/
        locationID (named stowage location) and newCategory groupings."""
        if self._inventory_cache is None:
            self._inventory_cache = self._get(self._inventory_url)
        return self._inventory_cache


def get_pms_provider() -> PMSProvider:
    """Factory: read env, return configured provider. Defaults to the local
    export reader (offline-safe, no vendor credentials required)."""
    provider = os.getenv("PMS_PROVIDER", "local_export").lower()
    if provider == "local_export":
        return LocalExportPMSProvider()
    if provider == "ymp":
        return YMPPMSProvider()
    raise NotImplementedError(
        f"PMS_PROVIDER='{provider}' not implemented. "
        f"Add a new class extending PMSProvider and wire it in here once a vendor is confirmed."
    )
