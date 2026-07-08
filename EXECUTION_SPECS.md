# EXECUTION SPECS — per-task detail for every open TODO.md item
Written by Fable (2026-07-08) so a cold-start Sonnet/Opus session can execute any task
without this project's conversation history. **Read §0 before touching anything.**
Structure mirrors `TODO.md` (Milestones → Chapters → Sessions). Each spec: GOAL /
STATUS / CONTEXT / INPUTS / PROCEDURE / VERIFY / GATES / TRAPS / MODEL (suggested tier
per the engineer's economy rule: cheapest model that can do the job).

---

## §0 — MANDATORY PREAMBLE FOR THE EXECUTING MODEL

**Who you work for:** a marine engineer (zero coding experience) building "Engo", an AI
engineering assistant for SY Gelliceaux (Southern Wind 108 hybrid). He directs, you build.
Ruthless-mentor honesty; concise engineer-to-engineer tone; cite sources; never validate
reflexively.

**Environment:**
- Repo: `/Users/captain/projects/gelliceaux` (GitHub `engineergelliceaux/Engo`, branch `main`).
- Run everything as: `PYTHONPATH=/Users/captain/projects/gelliceaux python3.12 …`
  (**TRAP:** bare `python3` is system 3.9 and fails on `X | None` type syntax. Homebrew 3.12 only.)
- Secrets live in `.env` (gitignored, NEVER commit): Anthropic, Voyage, Supabase,
  YMP PMS API, Google Drive service-account JSON path.
- Google Drive (read-only SA): vessel root `SWS 108-01` id `1fgqcB_CfoaJxW6hHB8p6zFBQggGUYgM-`.
  Connector: `providers/structure.py :: GoogleDriveStructureProvider.download_bytes(fid, mime)`.
  **Always wrap downloads in a 3-4 attempt retry loop with sleep** (a missing retry once
  crashed a gold run mid-script).
- GM electrical book (43pp, CURRENT revision): id `1YAmYWTTes5AD7NGLCGXRG86OENBH22Pl`.
- Structure manifest (every Drive file + path): `data/state/structure_gelliceaux_001.json`.
- The Register (the equipment node tree, ~319 active entries):
  `data/state/register_gelliceaux_001.json`.

**Key modules (prior art to MIMIC, not reinvent):**
- `pipeline/legend_first.py` — legends-first protocol (inventory + verbatim-read ALL
  legends/tables on a sheet; context block prepended to every extraction prompt).
  **Runs BY DEFAULT** inside both extractors. Never bypass it.
- `pipeline/schematic_extract.py` — hydraulic two-pass discovery (skeleton → per-slice
  600 DPI detail), `locate_and_read` for per-callout bboxes. Gold-blind.
- `pipeline/electrical_extract.py` — survey → per-REGION-type readers (schedule /
  wiring / one-line) + COVERAGE GUARANTEE (`read_*_coverage`: survey regions ∪ 3×3
  grid, deduped) because survey region-detection is stochastic.
- `pipeline/node_match.py` (§9e) — semantic resolve, ATTACH_THRESHOLD 0.45, token-boundary
  matching (never substring), generic-value stoplist, exact-distinctive-make boost.
- `pipeline/node_write.py` (§9d) — resolve-first writer. Hydraulic control-map path,
  electrical load-map path, FEEDER≠LOAD + CONTROL≠INDICATOR≠SUPPLY rules, revision gate,
  per-installation block rule, conflict-on-node + confirmation list, cross-reference step
  (`node_crossref`), `write_sheet()` (whole-sheet routing + power-path facts + raw-label
  proximity resolution). `dry_run=True` by default; `save()` refuses in dry-run.
- `pipeline/power_path.py` — wiring-graph assembly from extracted `connections` text
  (region-scoped, token-boundary, rails, activation roles, DC-fuse check).
- `pipeline/node_crossref.py` — doc-class completeness + identity corroboration/conflict
  across sources (includes the node's own folder-walk make/model as `register_seed`).
- `pipeline/revision_gate.py` — refuses facts from superseded drawing revisions.
- `pipeline/subsystem_seed.py` — breadth-first file ranking + the split-trigger test.
- `providers/pms.py` — LIVE YMP API (read-only; forces `www.` host; jobs path is
  `/api/worklist/` singular — the vendor doc's plural path returns HTML).
- `prompts/system_archetypes.md` — fleet-general: SHEET-READING SEQUENCE (mandatory),
  standing rules, symbol reference, per-system component archetypes + loop definitions.
  **Read the relevant archetype before extracting any system drawing.**

**Standing disciplines (violations have all actually happened; each rule is a scar):**
1. **No fabrication, ever.** Extracted values are printed-on-sheet or `<UNKNOWN>`.
   Never force an expected count. A fabricated "PASSED" entry was once written to the
   log and caught by the engineer — always re-read real tool output before reporting.
2. **Engineer gates (🔴) are hard STOPs.** Report and wait. No self-certification;
   the engineer grades every new protocol before it scales.
3. **Register writes:** backup file first (`cp register… register…backup_<date>_<tag>.json`)
   → dry-run → report → engineer go → real write → integrity check (no dangling
   parent/children/cross-links) → update both ledgers.
4. **Ledgers updated ON THE SPOT:** `ENGO_1.0_TRACKER.md` (Phase-1 statuses) and
   `ENGO_2.0_BACKLOG.md` (fleet items). `CLAUDE.md` is the detailed log.
5. **Gold-blind:** extraction prompts/code carry NO vessel-specific tokens. Gold values
   live only in `tests/`.
6. **Render before designing:** never design a document-class handler without viewing
   2-3 real rendered examples first.
7. **Legends first:** every legend/table on a sheet is read before any diagram symbol
   (now enforced in code — do not disable `legends_first`).
8. **Long runs:** run under the Monitor tool (bare background tasks die at turn end)
   with an append-only resumable ledger (`.jsonl`, flush per record).
9. **Cost economy:** vision calls cost real money and the engineer watches usage.
   Estimate call counts before a batch; anything > ~$5 needs an explicit engineer go.
10. **Scratchpads are ephemeral.** Any artifact worth keeping goes in the repo
    (`data/state/`, `data/ledgers/`) and gets committed. Extraction ledgers are
    expensive to regenerate — persist them immediately.
11. **Commit/push only when the engineer asks** (he usually says "push when finished").

**Known misread traps (check the relevant one before classifying anything):**
- Pickup/strum-box symbol ≠ valve (position at a branch dead-end is diagnostic).
- Motor-actuated vs manual valve = the small M-circle above the bowtie, easy to miss.
- Same equipment, two names on one sheet (BOM "AIR HANDLER" == plan-view "FANCOIL") —
  join tables by MODEL NUMBER, never by descriptive name.
- Pipe legend tells you what the system IS (GAS supply/return = direct-refrigerant VRV,
  not chilled water).
- "crew" is a substring of "screw"; model="custom" matches nothing — token-boundary +
  generic-stoplist matching only.
- Same model ≠ same physical unit (per-installation rule: a second Danfoss PVG 32 on a
  different sheet is a DIFFERENT unit).
- BOM tag suffixes like `016-01/016-02` are UNIT INSTANCE numbers (unit 1, unit 2) of
  BOM item 016, not zone codes.

---

## M1 — KNOWLEDGE BASE

### Ch 1.1 Text corpus ✅ / Ch 1.2 Node architecture ✅
Done and engineer-graded. Prior art lives in `pipeline/` (ingest, chunk, classify,
register, node_match, node_write). Nothing to execute; mimic these when building new.

### Ch 1.3 S2 — Ingest residue cleanup ⬜  (MODEL: Haiku/Sonnet)
GOAL: close the last ingestion gaps: (a) `._` AppleDouble skip-list, (b) 3 CSV sealogs,
(c) 5 `.gsheet/.gdoc` pointer files 🔴.
CONTEXT: the full-corpus ingest reconciled 1,689 files with 6 "errors" — all macOS
`._` resource-fork stubs, not real docs. 12 "unsupported": 5 octet-stream Google-pointer
files + legacy `.doc/.xls/.eml/.pptx/.csv` (`.pptx` since handled — parser exists).
PROCEDURE:
1. (a) In `pipeline/ingest_drive.py` find the skip logic (search `skip`); add: any file
   whose basename starts with `._` → disposition `skipped_appledouble` (counted, never
   `error`). Re-run the audit gate (`pipeline/audit.py`) — expect errors 6→0, counts
   still reconcile exactly.
2. (b) Find the 3 CSV sealogs in `structure_gelliceaux_001.json` (search name `.csv`).
   Add `parse_csv` to `pipeline/parsers.py` (mimic `parse_xlsx`: header row = first row
   with ≥2 non-empty cells; one chunk per row, "Header: value" format) + register in
   `PARSER_REGISTRY` and `CHUNKERS` in `ingest.py`. Ingest with placement (mimic how
   `ingest_drive.py` passes `extra_metadata`). VERIFY: chunk counts = row counts; a
   retrieval query for a known sealog entry returns it.
3. (c) 🔴 STOP: list the 5 `.gsheet/.gdoc` pointer names to the engineer, ask which
   matter. If none: record them in `reviewed_files_gelliceaux_001.json` as
   `excluded_pointer_file` so the audit never re-flags them.
VERIFY: `pipeline/audit.py` gate PASS, 0 silent gaps. TRAPS: run audit through the real
dispatcher path, not a shortcut.

### Ch 1.3 S3 — Operational/live lists channel 🔨 → partially superseded by PMS  (MODEL: Sonnet)
GOAL: keep living docs (Running log / tools / inventory xlsx) fresh + correctly placed.
CONTEXT CHANGE since TODO.md was written: **the YMP PMS API is now LIVE**
(`providers/pms.py`) and carries 615 inventory items + 142 equipment + 229 jobs — it is
the better live source for inventory/maintenance than the xlsx exports.
PROCEDURE:
1. Reconcile: pull YMP inventory via `get_pms_provider().list_inventory()`; compare
   against the ingested `Gelliceaux inventory.xlsx` chunks (name-level match is enough).
   Report overlap % to the engineer.
2. 🔴 STOP: propose to the engineer: YMP becomes the canonical live channel (poll/refresh
   script) and the xlsx files stay as static snapshots; he decides placement + cadence
   (he earlier said daily/bi-daily refresh).
3. Build the refresh per his answer: a small script `pipeline/refresh_operational.py`
   that re-pulls YMP (and/or re-ingests changed xlsx via existing `--refresh` flag on
   `pipeline/ingest.py`).
GATES: placement red-pen 🔴. TRAPS: YMP `status` field semantics are UNKNOWN (engineer
never answered) — do not filter on it.

### Ch 1.4 PMS/YMP (NEW since TODO.md) ✅ read side / ⬜ write side (FUTURE, gated)
Read-only provider live; 21 equipment matches written as Register facts. The engineer
WANTS an eventual write path (Engo fills log/work cards from chat) — explicitly
deferred; do not build without a fresh gate. Anything PMS-write = 🔴.

---

## M2 — EXTRACTION PROTOCOLS

### Ch 2.0 Cross-class layer (NEW) ✅
`prompts/system_archetypes.md` (sheet-reading sequence, loop-following, symbol traps)
+ `pipeline/legend_first.py` (code enforcement). Every task below inherits these.

### Ch 2.1 Hydraulic ✅
Template class; real writes done for 10 sheets. Remaining piece (the `General` overview
sheet's 25+ item parts list) folds into Ch 2.4.

### Ch 2.2 Electrical

**S6 batch 2a — wiring extraction ✅ DONE (update TODO.md).** Output preserved at
`data/ledgers/batch2a_v2_ledger.jsonl`: all 41 wiring/one-line pages of the GM book,
10,196 elements (89% with `connections` text), topology for 26 pages, 0 errors.
This ledger is the INPUT for S7/S8 — do not re-extract (it cost real money).

**S7 batch 2b — wiring routing 🔨 half done.**  (MODEL: Sonnet)
DONE: `write_sheet()` real pass (supply anchors, 62 power_path facts, 5 raw-label
proximity attaches); GM-111 loads routed via engineer-confirmed load map v1 (79 rows).
REMAINING: the 2,868 `create_flagged` elements (durable list:
`data/state/flagged_electrical_gelliceaux_001.json`) stay unrouted until (i) the
engineer red-pens load map v2 (S9) and (ii) the Register grows more anchors.
PROCEDURE (after S9 lands):
1. Backup Register. `NodeWriter(dry_run=True)`; iterate `data/ledgers/batch2a_v2_ledger.jsonl`
   pages (skip `error`-carrying pages — there are none left); call
   `w.write_sheet(elements, src)` with
   `src={"source_doc": f"SW108-01-600 Electrical schematics - GM Marine 06 Oct 2023.pdf — {drawing_no} {title}", "drive_file_id": "1YAmYWTTes5AD7NGLCGXRG86OENBH22Pl", "page": page+1, "source_type": "electrical_schematic"}`.
2. Compare attach/flag counts vs the durable flagged list — the delta IS the yield of
   the new load map. Report per-sheet.
3. 🔴 engineer grades the dry-run report → real write (`dry_run=False`, `save()`,
   `flush_confirmation_flags()`, integrity check).
VERIFY: idempotency — re-run one sheet, expect 0 new facts (already_attached guard).
TRAPS: strip `_via`/`_bbox` handling is inside write_sheet already; don't pre-filter
elements yourself.

**S8 batch 2c — one-line topology routing ⬜ (the router does NOT exist).**  (MODEL: Opus for design, Sonnet for run)
GOAL: turn the 26 pages of topology (`topology_nodes`/`topology_edges` in the ledger)
into Register facts + cross-links (batteries→isolators→buses→chargers→loads).
DESIGN (write it, get it graded 🔴, then build):
1. Cross-sheet node reconciliation is the hard part: "NEG_BUS"/"600V DC BUS" appear
   independently on many sheets and are THE SAME physical bus — merge key = normalized
   label + node_type (mimic `power_path._token_contains` matching; never raw substring).
2. Buses/rails become facts + cross-links, NOT new equipment nodes (equipment-not-
   actuator analogue: a busbar is infrastructure; a charger/battery is equipment).
   Batteries/chargers/isolators resolve via §9e + the electrical load map; unresolvable
   → create_flagged (never guess).
3. Each edge = a `topology_edge` fact on BOTH endpoint nodes with full provenance
   (source_doc, page, the edge's verbatim text).
4. Dry-run whole book → engineer grade 🔴 → real write.
VERIFY: pick Q1/Q2/Q3 + F1/F2 on the shore-power sheet (page 2, GMMS 108'-101) — the
known chain Q1→600V DC BUS→EDN-P must reproduce.

**S9 — load map v2 red-pen 🔴 engineer, then apply.**  (MODEL: Sonnet)
INPUT: `data/state/load_map_gelliceaux_001.EXTENSION.DRAFT_v2.json` (21 sheets / 324
loads / 133 auto-proposed / 191 unknown) — the engineer edits `engineer_decision` fields.
PROCEDURE once returned: mimic the v1 apply (see CLAUDE.md "ELECTRICAL LOAD MAP
RED-PENNED + APPLIED" entry): create approved nodes (LOGICAL-SFI rule: check yard-tree
occupancy BEFORE assigning a free number — 651 collision lesson), merge mappings into
the ACTIVE `load_map_gelliceaux_001.json`, then re-run S7. Every new node needs
region/subsystem codes + `origin` + provenance. Integrity check after.

**S10 — BAE 47pp ⬜.**  (MODEL: Sonnet run; Opus if reader changes needed)
CONTEXT: BAE Wiring Diagrams = 47pp, Class A (image-only), drawn ROTATED 90°; 6 Drive
copies are ONE revision; prefer the LANDSCAPE byte-variant (md5 2f36b5d8, the
625/Schematics copy). Title page = full sheet INDEX (use it to route/name sheets).
Two page families: block-interconnect one-lines (MPCS/HVPDU/BELs/ESS, colour-coded
HV-AC/HV-DC/24V/CAN buses) and connector-pinout pages (`G3-K4xx` wire ids).
PROCEDURE:
1. Locate the landscape variant's Drive id (hash-check via the ingest ledger or
   download+md5 the 625/Schematics copy). Download once, cache to `data/ledgers/`.
2. Render pages 1-3 + one of each family FIRST (render-before-designing; also confirms
   rotation). If rotated: rotate the PNG before extraction (mimic
   `schematic_extract._rotate_png`) — check whether `electrical_extract` needs a
   rotation wrapper (it currently has none). Legends-first stays on.
3. Pilot: `extract_sheet` on ONE one-line page + ONE pinout page. 🔴 STOP — engineer
   grades the pilot before the 47-page run (estimate ≈ 6-10 calls/page ≈ $15-30 total;
   state the estimate when asking).
4. Full run under Monitor with an append-only ledger `data/ledgers/bae_ledger.jsonl`.
5. Cross-validate pinout pages against the text-ingested `HV Wiring.xlsx` /
   `LV Wiring list.xlsx` chunks (query the vector store or re-parse the xlsx): sampled
   wire ids must match; mismatches are FINDINGS to surface.
6. Routing: BEL/MAPS/SCU/EDN/MPCS nodes already exist (`629-bel`+children, `626-maps`,
   `628-scu3`, `627-edn`, …). Dry-run → 🔴 grade → real write.

### Ch 2.3 PLC (MYT Wago) ⬜  (MODEL: Sonnet)
CONTEXT: MAST (25pp) + ENGINE ROOM (12pp) + AFT PLC sets; image-only exports; page 0 =
cover; rack-layout pages (Wago modules 750-362 coupler / 750-1405 DI / 750-455 AI /
750-508 DO in slots X0-X8) + I/O channel pages. Text-bearing siblings
(`SWS_108-1 *_Rev4`) exist for cross-validation. These are MYT's electrical I/O — the
hydraulic system's control layer.
PROCEDURE:
1. S1 rack pages: they are schedule-LIKE (slot | module part-no | function). Render one
   first; if the schedule reader's row schema fits, use it with legend context; if not,
   write a small `_RACK_PROMPT` variant in `electrical_extract` style (gold-blind).
   Facts land on the MYT PLC node (create `653-…` card if absent — 653 is MYT
   monitoring's yard section; CHECK OCCUPANCY first).
2. S2 I/O pages: wiring reader (`read_wiring_coverage`). Signal names like
   `pb_innerstay_rta`, `pb_vang` are CONTROL signals.
3. S3 cross-validation: each `pb_*` signal should map to a hydraulic control-map
   function (`data/state/control_map_gelliceaux_001.json`, 39 rows) — join via
   `pipeline/abbrev.py` expansion + token match. Output a mapping table: signal →
   function → equipment node. Mismatches = findings. This is pure local compute, free.
4. S4 🔴 blocked external: the MYT program itself (engineer chasing MYT). When it
   arrives: parse (CODESYS-family), plain-language function descriptions, engineer
   red-pens, ingest as placed 570 chunks.
VERIFY: sampled module part-numbers re-read from a 600-DPI crop match; zero fabricated
slot contents.

### Ch 2.4 P&ID / BOM-compound sheets ⬜  (MODEL: Opus design → Sonnet run)
CONTEXT: fuel (108-01-550-001), blackwater, bilge/fire, hydraulic `General` — compound
sheets: GA plan + flow diagram + BOM + legends. `legend_first` already reads the BOM
and legends verbatim (brick #1 proven on the bilge sheet — engineer-ground-truth match).
The MISSING piece is the JOIN: BOM item-tag ↔ diagram symbol ↔ loop position.
PROCEDURE:
1. S1: render fuel + blackwater + hydraulic General at ~200 DPI, view, confirm layout
   variants (render-before-designing). All three already have on-disk renders from the
   2026-07-06 survey — check `ls /private/tmp/...` first, else re-render.
2. S2 design (🔴 grade before build): for each BOM row (item No., qty, class,
   make/model), locate its diagram callouts (the blue `NNN-NN` unique numbers — these
   are ITEM-INSTANCE tags: item 016 qty 5 appears as 016-01…016-05). Use
   `locate_and_read`-style targeted crops per zone, guided by the LOOP definitions in
   `system_archetypes.md` (trace each pipe-legend line type; catalogue components in
   path order). Output per sheet: `{bom_rows, instances:[{tag, zone/position,
   loop_segment}], loops:[{line_type, path:[tags…]}]}`.
3. S3 route: instances resolve via §9e + parent/child per-installation rules (5 bilge
   valve instances = 5 children under `520-bilge-valves`, zones per the loop trace).
   Dry-run → 🔴 grade → real write.
TRAPS: the bilge BOM prints FEIT for the main pump — a documented printed ERROR
(engineer says Gianneschi); conflicts surface, never auto-resolve. Qty on a BOM row is
the vessel-wide TOTAL, not per-zone.

### Ch 2.5 Building/structural drawings ⬜  (MODEL: Opus design → Sonnet run)
CONTEXT: Hall Spars mast layout (P03818-01), hull structure, GAs. Class A vector +
positioned callouts; callout TEXT is extractable but POSITION IS SEMANTIC ("V1 C6-210"
near the masthead tang = the V1 shroud spec). One drawing fans out to MANY nodes.
The 10-sheet sweep proved the hydraulic control map FALSE-POSITIVES on these
("RUNNING BACKSTAY CABLE"→cylinder) — the source-type gate already blocks that; this
class needs its own router.
PROCEDURE:
1. S1 design doc (🔴 grade): callout schema {text, bbox, nearest_anchor_feature};
   anchor features from a skeleton pass (masthead, spreader N, gooseneck, frame refs);
   route each callout via §9e with the anchor as zone context; position (mm from datum,
   frame station) recorded as a FACT with bbox provenance (Rule 3: position is a fact).
   Rig-package facts target 810 (spar/section), 830 (standing rigging), 850 (locks/
   sheaves/cars) — never create per-callout nodes (a dimension is a fact, not equipment).
2. S2 build + validate on the Hall Spars mast layout: expect shroud specs (V1/D1…),
   spreader positions, HYD exit heights. Engineer knows this rig — he grades quickly.
3. S3 real write after grade.

### Ch 2.6 Vision queue backlog ⬜  (MODEL: Sonnet; big-batch cost 🔴)
CONTEXT: 762 `pending_vision` files (photos/certs/scanned docs/figures) +
188 legacy describe-only chunks (flagged `legacy_describe_only=true`) + CM-24-1732's
25 investigation figures + the Akasol cert set.
PROCEDURE:
1. Classify the 762 by `route_kind` (in `pipeline/vision_ingest.py`) WITHOUT burning:
   produce a manifest {file, kind, proposed treatment} first. 🔴 engineer approves the
   manifest + budget (rough: 762 × ~$0.02-0.15 depending on class = state a real number).
2. Burn in 50-file engineer-graded batches (Master Spec §12): photos/certs →
   describe+store (glossary correction ON, `describe_store` path — images go to
   object storage via `providers/storage.py`); schematic-class strays → the proper
   extractor instead of describe.
3. The 188 legacy describe chunks: after their files reprocess correctly, purge the
   old chunks (replace→verify→purge pattern from the legacy cleanup, kill-safe ledger).
4. CM-24-1732 figures: treat as investigation-figure class — describe + LOCATE (bbox)
   because they carry the evidentiary core (scope traces, wiring photos); attach as
   facts/links on the BEL/grounding-related nodes.
VERIFY: audit gate still PASS; sampled describes contain zero invented part numbers.

### Ch 2.7 Retrieval layer refresh ⬜  (MODEL: Sonnet)
S1 full-corpus HyDE rebuild: `pipeline/hyde.py --all` after Ch 2.6 lands (one pass
covers text + vision). Component-level extension (§9h): also generate questions FROM
Register facts (power_path, electrical_supply, control functions) so queries like
"what breaker feeds the aux bilge pump" retrieve the node's facts — write these as
retrievable chunks with `doc_type="node_fact"`, id = `node:{equipment_id}:{fact_idx}`,
embedding = question, document = fact rendering + provenance. Budget ≈ $10-15 Haiku +
embeddings 🔴 confirm.
S2 node-tree → retrieval wiring: in `agent/loop.py`, add a node-lookup step (resolve
query terms via §9e against the Register; if a node matches confidently, inject its
facts + `jump-to` provenance (source_doc, page, bbox) into context alongside vector
hits). This is the describe-AND-LOCATE end feature: answers cite the sheet+bbox so the
engineer can jump to and mark the exact component. VERIFY with validation-case queries
(BEL, GPM-12, bilge pump supply).

---

## M3 — PROTOCOL LOCK + BLIND RUN

### Ch 3.1 S1 — protocol docs ⬜  (MODEL: Sonnet, writing task)
Distill CLAUDE.md's decisions into clean per-class specs under `docs/protocols/`:
one doc per document class (hydraulic, electrical A/B/C, PLC, P&ID, building, photo/cert),
each: applicability test → reading procedure (legends-first + loops) → extraction
schema → routing rules → validation gates → known traps. Source material: CLAUDE.md
"Open items" + `ENGO_1.0_TRACKER.md` + `prompts/system_archetypes.md`. No new
decisions — if something is ambiguous, flag it, don't invent policy.

### Ch 3.1 S2 — rules into code ⬜  (MODEL: Sonnet)
(a) Logical-SFI occupancy check into the auto-create path: `node_write._create_flagged_node`
currently slugs blindly; add a helper that, given a proposed subsystem code, checks the
yard tree (structure manifest folder names) + existing Register codes and picks the next
FREE logical number (the 650/651/654 lesson). (b) Feeder/indicator rules are ALREADY in
`write_wiring_element` — verify with a unit test, don't rebuild. (c) Unit tests for both
under `tests/` exercising the REAL dispatcher path.

### Ch 3.2 — the blind run 🔴 (engineer schedules; MODEL: Opus orchestrating)
GOAL: prove the protocols transfer without the engineer in the loop — the 2.0 rehearsal.
PROCEDURE:
1. Fresh namespace (`VESSEL_NAMESPACE=gelliceaux_blind` or a separate state dir —
   NEVER touch the live Register): run walk → classify → register-build → extract →
   route, protocols only, no engineer answers; every would-be question goes to a
   red-pen list instead.
2. Diff vs the engineer-graded live Register: wrong-attaches (target 0), flag
   precision/recall, red-pen size vs this build's baseline. Write the diff script
   (`tests/blind_diff.py`): match nodes by (subsystem, make/model tokens), compare
   facts by (kind, normalized value).
3. Report → engineer signs → tweak protocols from the diff → re-run affected classes.
EXIT: red-pen list small + conflict-only. Full vision re-extraction is expensive —
reuse cached ledgers for extraction and re-run only classify+route blind where
extraction is deterministic-from-ledger; state clearly which stages were truly blind.

---

## M4 — LIVE AGENT LAYER (offline-first: everything here runs on the boat MacBook, no cloud dependency)

### Ch 4.1 Sensors ⬜  (MODEL: Sonnet)
S1 `sensors/poller.py`: GET `http://192.168.1.101/data` 1/min (READ-ONLY — architecture
rule 2: never write to vessel systems; fire/bilge systems are never queried).
Summarizer: per-channel rolling stats (min/max/mean/last, 15-min + 24-h windows) →
compact JSON the agent can ingest (raw arrays NEVER go to the LLM). Persist rolling
state to `data/state/exocet_rolling.json`; append-only daily log `logs/exocet_YYYYMMDD.jsonl`.
Channels of known interest: `BAE_Motor_*_pt/_stbd` (only ONE side non-zero is normal;
both = fault), `GNSS_UTCdate/UTCtime` (authoritative clock), EMRAX1/2 = MYT hydraulic
powerpack motors NOT propulsion. SBG timestamps are garbage (stuck 2015-05-03) — ignore.
S2 GNSS clock cross-check: extend `agent/clock.py` — compare `now()` against GNSS UTC
from the poller state; drift > few minutes → suspect flag both directions (closes the
forward-jump backlog item). Fail toward caution.
S3 anomaly flags: threshold/trend rules (start dumb: out-of-range vs a per-channel
baseline file the engineer red-pens 🔴) → queue messages for Ch 4.3.

### Ch 4.2 Conversation ⬜  (MODEL: Sonnet)
S1 multi-turn: `agent/loop.py` is single-turn. Add a conversation store
(`data/state/conversations/<id>.json`), replay recent turns, and compress history after
3-4 turns (summarize older turns via one Haiku call) per the token budget. This
activates the system prompt's diagnostic dialogue flow (Step 0 clarifiers etc.) which
already expects multi-turn. VERIFY: re-run validation case #1 as a 3-turn dialogue.
S2 operational modes: mode fact (HARBOUR/PASSAGE/RACE…) from a small engineer-editable
file or calendar 🔴 + the VCP mode-switch facts (S3/S4/S5 on `641-vessel-control-panel`);
inject current mode into the user-message context (NOT the cached system prompt).

### Ch 4.3 Comms ⬜  (MODEL: Sonnet)
Twilio WhatsApp Sandbox behind `providers/messaging.py` (`MessagingProvider` ABC —
architecture rule 1; Meta Business API is the 2.0 swap). `comms/whatsapp.py`: webhook
(Flask, local) for inbound → `agent.loop.query()`; scheduled morning/evening check-in
using the Ch 4.1 summary + any anomaly flags; follow-up loop = anomaly message asks a
question, reply routes back into the same conversation id. Secrets to `.env`
(`TWILIO_SID/TOKEN/FROM/TO`). 🔴 engineer supplies Twilio credentials.

### Ch 4.4 Validation ⬜  (MODEL: Sonnet)
S1 Case #3: pick from the build plan candidates (MAPS-P/S contactor pattern, BEL
overloading 50A peaks, GPM-12 alignment/orbiting — all documented in CM-26-2024 §6 +
running log). Run through the REAL agent path (`agent/loop.py`), grade against: correct
diagnosis direction, citations, no fabrication, Step-0 budget respected. 🔴 engineer grades.
S2 eval harness `tests/eval_harness.py`: query set (start: the 3 validation cases +
xlsx lookups + cross-vocabulary Exocet queries + 10 new engineer-supplied 🔴) × expected
source docs × scored relevance. **Assert "expected chunk appears in top-k", NEVER exact
rank** (Voyage embeddings are non-deterministic — documented). Baseline before/after
any threshold/chunk tuning; this harness UNLOCKS the deferred tuning decisions
(distance threshold ~0.6, chunk_size for sparse manuals).

---

## M5 — ENGO 2.0 FOUNDATIONS
Gated on M3 exit. Full list in `ENGO_2.0_BACKLOG.md`. Do not start any of it without
an explicit engineer instruction.

---

## AUDIT PLAN
Unchanged from TODO.md — every session ends with its VERIFY; per-milestone audits;
standing gates (engineer grades, gold-blind, revision gate, conflicts surface, ledgers
on the spot). The audit plan applies to every spec above even where not restated.
