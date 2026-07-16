# Changelog

## 2026-07-12 (2) — Multi-LLM vision routing + benchmark harness

Engineer decision: use the best model per task — Claude for backbone/orchestration,
the best vision model per DRAWING CLASS for reading, decided empirically by an
engineer-graded benchmark (2 sheets per category × 3 providers through the full
existing protocols). Plan: /root plan 'Multi-LLM Vision Routing'.

### Added

- **`providers/vision.py`** — (a) `extract`/`extract_multi` formalized on the
  `VisionProvider` ABC (provider swap now fails at the interface, closing part
  of deferred finding #6); (b) **`GeminiVisionProvider`** (google-genai SDK,
  response_schema structured output, schema-cleaning for unsupported JSON-Schema
  keys, max_side 3072) and **`OpenAIVisionProvider`** (openai SDK, forced
  function-calling mirroring the Anthropic tool mechanism, max_side 2048), both
  with the same transient-retry policy and the caller-owned gold-blind prompts
  untouched; (c) **per-class routing**: `get_vision_provider(task_class)` reads
  `VISION_ROUTES` (e.g. `electrical:gemini,hydraulic_schematic:anthropic`),
  default vendor `VISION_PROVIDER`; model ids env-tunable
  (`VISION_MODEL`/`GEMINI_VISION_MODEL`/`OPENAI_VISION_MODEL`).
- **Claude vision upgrade**: default `VISION_MODEL` → `claude-sonnet-5`;
  `max_side` is now model-dependent — **2576px** on Opus 4.7/4.8, Sonnet 5,
  Fable 5 (high-res vision) vs 1568px on older models. The §4 crop-footprint
  cap in `pipeline/schematic_extract.py` now derives from `vp.max_side`
  instead of a hardcoded 1568. Part of the perceived 'Claude ceiling' was an
  old-model resolution cap.
- **`tests/vision_bench.py` + `tests/vision_bench_manifest.json`** — the
  full-protocol benchmark: per (category × sheet × provider) runs the ENTIRE
  existing loop (hydraulic discover_structure / electrical extract_sheet /
  describe for classes without extractors), kill-safe ledger, per-run JSON
  outputs, side-by-side engineer-grading report with agreement/unique-read
  highlighting. 10 categories skeleton; engineer fills 2 sheets each.
- **`tests/test_vision_providers.py`** — 8 offline tests (max_side by model,
  prepare respects instance cap, ABC contract enforced, routing default/per-class/
  unknown-vendor, Gemini schema cleaning, manifest sanity). Suite now 52/52.
- `pipeline/schematic_extract.py` routes as `hydraulic_schematic`,
  `pipeline/electrical_extract.py` as `electrical`.
- `requirements.txt`: + `google-genai`, `openai`.

### Notes / honest caveats

- Gemini/OpenAI default model ids (`gemini-3-pro`, `gpt-5.2`) are env-tunable
  and FAIL LOUD if renamed by the vendor — verify on the first cheap plumbing
  run before the full benchmark.
- Benchmark cost ≈ $40–100 full, ~$3 single-sheet plumbing check (engineer GO).
- Deferred by design: deterministic word-box OCR provider (the locate-recall
  fix), consensus/dual-read mode (built after routing results show which pairs
  disagree usefully).


## 2026-07-12 — Sanity-pass hardening (full-code review fixes)

Full codebase sanity review (all ~13.6K lines) ran on 2026-07-12; these are the
approved fixes for findings #1-5 + #8a/#10/#11. 12 new regression tests in
`tests/test_sanity_fixes.py`; full suite 44/44 green.

### Fixed

- **`providers/vision.py`** — bounded retry/backoff (4 attempts, 2/5/15s) on
  TRANSIENT Anthropic API errors (429/5xx/529/connection) in `describe()`,
  `extract()`, `extract_multi()`. Permanent 4xx still fails loud immediately.
  Closes the Gold-#2 crash class at the provider so every caller is covered.
- **`providers/structure.py`** — same retry treatment for every Drive API call
  (walk pagination, `file_meta`, `download_bytes`). 403/404 not retried.
- **`pipeline/node_write.py`** — (a) Register + confirmation-list saves are now
  ATOMIC (tmp + `os.replace`); a mid-write kill can no longer corrupt
  `register_<vessel>.json`. (b) `_attach_fact` is idempotent on exact re-run
  duplicates (same kind+value+source doc/sheet/page; bbox excluded from the key
  since discovery re-runs drift coordinates) — re-processing a hydraulic sheet
  no longer duplicates rating/actuation/cartridges/settings facts.
- **`pipeline/node_match.py`** — retired nodes are never match targets
  (`resolve()` + `_exact_make_boost`); 18 retired debris nodes could previously
  win a match and silently receive facts. Also: empty-register guard.
- **`pipeline/tokens.py` (new) + `pipeline/chunk.py` + `pipeline/parsers.py`** —
  tiktoken encoder now loads LAZILY via a shared `get_encoder()`; module import
  no longer downloads from the internet (verified live: `import pipeline.chunk`
  failed offline pre-fix). Cache dir pinned repo-local
  (`data/tiktoken_cache`, set in config.py). One-time online seeding:
  `python3 -m tools.seed_tiktoken_cache` (new script; cache is committable).
- **`providers/llm.py`** — `complete_messages` joins ALL text blocks instead of
  trusting `content[0]`; raises a clear error if the response carries no text.
- **`sensors/poller.py`** — (a) daily JSONL logs pruned after
  `EXOCET_LOG_RETENTION_DAYS` (default 90; 0 disables) at startup + daily
  rollover. (b) a CORRUPT rolling-state file is quarantined
  (`.corrupt-<timestamp>`, loud error) and the monitor starts fresh instead of
  staying down until a human deletes the file.
- **`pipeline/ingest.py`** — directory ingest now recurses every
  `PARSER_REGISTRY` type (was pdf/xlsx/docx only; missed .pptx/.csv).
- **`pipeline/retrieve.py`** — HyDE dedup over-fetch 3x → 6x (full HyDE coverage
  = up to 5 questions + self per chunk; 3x could under-fill top-k).
- **`pipeline/ingest_suppliers.py` / `pipeline/visual_extract.py`** — two
  genuinely silent `except` blocks now log.
- **`requirements.txt`** — completed with everything the code actually imports
  (Pillow, google-api-python-client, google-auth, python-pptx, requests,
  matplotlib, pytest; supabase noted optional).

### Deferred by engineer decision

- #6 (abstract-interface drift: extract/extract_multi/delete_where/
  set_metadata_where not on the ABCs) and #7 (vessel tokens hardcoded in
  revision_gate/node_write defaults) → before vessel #2.
- #9 (CLAUDE.md 153KB slimming) → needs engineer editorial call.
- #8b/8c (Voyage silent dims default; LocalFsStorage key sanitization) → minor,
  not done this pass.


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

## 2026-07-16 — Full-command-chain rule generalized (engineer)
The PLC-linkage note (keel example) is now a GENERAL rule for ALL hydraulic functions
(winch, ram, furler, door, keel, thruster — any function): once the MYT PLC program is
ingested, each function's equipment node carries the complete chain
control input → PLC module/channel → energised cartridge/EV → actuator → motion,
every hop a provenanced fact from its owning source. Tracker updated (FULL-COMMAND-CHAIN RULE).
