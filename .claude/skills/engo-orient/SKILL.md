---
name: engo-orient
description: Orient a fresh session on the Engo/Gelliceaux build fast — where the state lives, the non-negotiable disciplines, and which other skill to load for the task. Load this FIRST when picking up any Engo work (ingestion, extraction, red-pen, node writing, retrieval) instead of reading the whole 150KB CLAUDE.md.
---

# Engo orientation

Engo is a local AI engineering assistant for SY Gelliceaux (Southern Wind 108).
This skill is the fast path into the build. Read it, then load the specific skill
for your task. Only fall back to CLAUDE.md / EXECUTION_SPECS.md for deep history.

## Where state lives (all under `data/state/`, vessel = `gelliceaux_001`)

- `register_<vessel>.json` — the equipment node graph (the Register). Entries keyed
  by `equipment_id`; carries facts, cross_links, parent/child, provenance.
- `load_map_<vessel>.json` — active engineer-confirmed load-name → node map (+ `rules`,
  `non_node_dispositions`).
- `structure_<vessel>.json` — the live Drive folder walk (SFI tree, every file).
- `placements_<vessel>.json` — every file + its region→subsystem→equipment lineage.
- `flagged_electrical_<vessel>*.json` — unrouted wiring elements awaiting red-pen.
- `data/ledgers/*.jsonl` — append-only extraction ledgers (expensive; NEVER re-extract
  without checking these first).
- `ENGO_1.0_TRACKER.md` — at-a-glance Phase-1 status. `ENGO_2.0_BACKLOG.md` — Phase-2.
- `EXECUTION_SPECS.md` §0.5 — the "where we are now" snapshot + engineer queue.
- `docs/PROTOCOL_electrical_extraction.md` — the consolidated extraction rules.

## Non-negotiable disciplines (violating these has caused real scars)

1. **Flag, never guess.** Unresolvable → `create_flagged` / `<UNKNOWN>`. A wrong
   attach misdirects an engineer mid-repair; an honest flag doesn't.
2. **"Clean" means VERIFIED, not "didn't crash."** Reconcile against the flagged
   list. → `verify-gate` skill.
3. **Never report done/passed without re-reading the ACTUAL run output** and quoting
   real numbers. (A fabricated "Gold-#2 PASSED" entry is a permanent scar.)
4. **A "lost"/uncertain item is dispositioned by RENDERING the region, not from
   labels.** (CP-SW was a real loss; SW-3/4 a real improvement — only the drawing
   told them apart.)
5. **Guard every vision-output consumer against non-dict array entries.** The JSON
   schema `items:{type:object}` is a request, not a guarantee (crashed 3×).
6. **Gold-blind extractors.** No vessel-specific token (part numbers, tags) in
   extractor prompts/code. The glossary + agent prompt are separate channels.
7. **Provenance on every fact.** `{source_doc, page/sheet, bbox, source_type,
   authority, as_of}`. Nothing unsourced.
8. **Persist expensive artifacts immediately** (ledgers → `data/ledgers/`, committed).
   Background bare tasks die at turn end; run long jobs under Monitor + a kill-safe
   ledger.
9. **Engineer's raw red-pen is saved VERBATIM** (his exact words = the provenance),
   never paraphrased.
10. **python3.12, `PYTHONPATH=.`** for all pipeline scripts. Load `.env` via
    `import config` before any provider call.

## Which skill to load next

- Applying engineer red-pen answers (load map, symbols, identities) → **redpen-roundtrip**
- Extracting a document class (electrical/PLC/P&ID/BAE/vision) → **extraction-campaign**
- Checking a re-extraction/routing pass actually worked → **verify-gate**
- Creating nodes / writing facts / allocating SFIs → **register-write**

## Environment quick facts

- Drive connector: `providers.structure.GoogleDriveStructureProvider` (service account,
  read-only). GM book id `1YAmYWTTes5AD7NGLCGXRG86OENBH22Pl`.
- Model economy rule: cheapest capable model for the task; Opus for genuine design,
  Sonnet for execution, Haiku for bulk. Parallel workers ≤2 per session window.
- Scratchpad for temp files: the session scratchpad dir, never `/tmp` unless asked.
