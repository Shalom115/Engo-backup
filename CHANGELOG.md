# Changelog

## 2026-06-09 → 2026-06-10 — Full-corpus ingest + Suppliers fold-in

Everything changed since the previous CLAUDE.md save (which ended at "Equipment
Register backbone + live Drive connector built; full SWS 108-01 ingest pending").

### New files

- **`pipeline/ingest_suppliers.py`** — Ingests the `Suppliers` vendor master index
  (the flat ~75-vendor folder under `SWS 108 › SWS`, outside the 108-01 system
  tree). Walks it live via the connector, places each vendor under the SFI
  subsystem the backbone already assigns that maker (vendor→subsystem map learned
  from `register_<vessel>.json`), ingests text files hash-deduped against the
  existing store, queues images/scanned PDFs to `pending_vision`, and reconciles.
  Resumable (own ledger). Holds the engineer-adjudicated `VENDOR_OVERRIDE` for
  the 6 vendors the auto-map couldn't place.

- **`CHANGELOG.md`** — this file.

### Modified files

- **`providers/vectorstore.py`** — added `delete_where(where) -> int`: delete all
  chunks matching a metadata filter (Chroma `where`). Used to remove the 6
  flagged vendors' chunks before re-ingesting them with corrected placement.

- **`pipeline/ingest_drive.py`** — (this window) made fully resumable: append-only
  ledger `ingest_ledger_<vessel>.jsonl` records every file's outcome bucket so a
  resume skips done files *without re-downloading* and the report survives a kill.
  This is what let the full 1,689-file run actually finish after repeated
  idle-kills.

- **`pipeline/ingest.py`** — `ingest_file()` extended with `extra_metadata`
  (placement that overrides the folder-path classifier), `display_name` /
  `display_path` (real names for temp-file ingests), and shared `store`/`embedder`
  (reuse one provider instance across a batch run).

- **`providers/structure.py`** — `GoogleDriveStructureProvider.download_bytes()`:
  fetch a Drive file's content (get_media, or export for Google-native types).

- **`CLAUDE.md`** — added the Exocet=Pixel-Sur-Mer locked fact; added "Full SWS
  108-01 corpus ingested" and "Suppliers vendor-index folded in" to Built-and-
  working; rewrote Drive-index-status (full corpus now ingested, pending_vision
  762); marked the document-ingestion and Equipment-Register open items done.

### Data / state artifacts produced

- `structure_<vessel>.json` — canonical manifest of the live walk (2,238 nodes).
- `register_<vessel>.json`, `vocab_<vessel>.json`, `placements_<vessel>.json` —
  the backbone: 206 equipment entries, 13 acronyms, every file's lineage.
- `ingest_ledger_<vessel>.jsonl`, `ingestion_report_<vessel>.json`,
  `pending_vision_<vessel>.json` — the system-tree ingest record + reconciliation.
- `placements_suppliers_<vessel>.json`, `ingest_ledger_suppliers_<vessel>.jsonl`,
  `ingestion_report_suppliers_<vessel>.json` — the Suppliers ingest record.

### Reconciliation outcomes (both balance exactly)

- **SWS 108-01 system tree: 1,689 = 628 ingested + 709 pending_vision + 334
  already_present + 12 unsupported + 6 errors.** 15,977 placed chunks. (The 6
  "errors" were all `._` macOS AppleDouble stubs, not real documents.)
- **Suppliers: 310 = 58 ingested + 189 duplicate + 53 pending_vision + 10
  unsupported.** 189 duplicates confirm Suppliers heavily overlaps the system tree
  (same manuals, filed by vendor); the 58 unique adds include Farr naval-
  architecture (187 chunks) and the Exocet manual (12).
- Collection total now ~21,305 chunks. Combined pending_vision queue = 762.

### Vessel knowledge added

- **Exocet = Pixel Sur Mer** (locked fact): the onboard data aggregator that taps
  every CAN bus/network (hydraulic load cells, B&G, propulsion) into one local
  source at `192.168.1.101/data`, sampled ≤1 min for trend/anomaly monitoring.
  Core to the sensor-poller; likely v2 architecture pivot. Manual placed under 900.
- **Vessel identity:** naval architect = Farr, builder = Southern Wind — recorded
  for future fleet cross-referencing.
- **6 engineer-adjudicated vendor placements:** Wartsila Shaft Seal→400/430,
  DIVERSE Loadpin→800, Farr→100, Future Automation→300, Pixel-Sur-Mer/Exocet→900,
  SENSORS→500/570.

### Decisions & corrections (the "no assumptions" wins)

- **Cancelled the legacy-chunk purge.** Verification (path/content-based, not
  fragile filename matching) showed the ~2,125 "legacy" chunks are mostly UNIQUE
  local content, not Drive duplicates — purging would have deleted the BAE manuals,
  owner's manual, and operational spreadsheets. They stay; re-placement folds into
  the HyDE rebuild (Part 2.2).
- **Expanded scope to include Suppliers.** The spec said ignore it; verification
  proved it holds unique critical manuals (the GPM-12 maintenance manuals Block 1
  relies on). Included it deduped + placed instead.
- **Operational lesson:** long ingest runs must run under the Monitor tool (keeps
  the session alive) + a ledger (resumable). Bare background tasks get idle-killed
  at turn end — this cost two false "done" reports before it was fixed.

### v2 notes (recorded, not built)

- Equipment-alias / ontology DB: per equipment, its possible system/subsystem
  names + common industry manufacturers — to make backbone-building faster on
  vessel #2+.
- Per-file routing for multi-subsystem vendors (Farr design files, SENSORS).
- Naval-architect/builder cross-referencing across the future fleet.
- Exocet/Pixel-Sur-Mer as a potential v2 monitoring-architecture pivot.
