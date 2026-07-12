---
name: register-write
description: Write to the Engo/Gelliceaux Register safely — create nodes, attach facts, add cross-links, allocate SFI codes — with backup, provenance, occupancy checks, and an integrity gate. Use whenever adding or modifying equipment nodes or facts, whether from red-pen, extraction routing, or autonomous creation. Encodes the node schema and the flag-never-guess / occupancy / parent-child rules the engineer taught.
---

# Register write

The Register (`data/state/register_<vessel>.json`) is the equipment node graph — the
project's core asset. Every write follows this discipline. Read `engo-orient` first.

## Before any write
1. **Back up**: `cp register_<vessel>.json register_<vessel>.backup_<what>_<ts>.json`.
2. Load `by_id = {e['equipment_id']: e for e in reg['entries']}`.

## Node schema (match existing entries exactly)
```
{equipment_id, name, make, model, category, acronyms, region_code, region_label,
 subsystem_code, subsystem_label, functions, source_paths, source_folder_ids,
 doc_subfolders, file_count, flags, confidence, parent_id, children, cross_links,
 expected_fact_classes, fact_classes_present, retired, merged_from, origin,
 node_provenance, facts, note}
```
- `equipment_id` = `<sfi>-<make-or-function-slug>` (e.g. `510-fresh-water-pump-1`).
- `facts`: list of `{kind, value, confidence, note, provenance}`. `value` may be a
  string or a dict — consumers MUST guard `isinstance(value, dict)` before `.get()`
  (a string-valued fact crashed the router once).
- `cross_links`: `{relation, target, source}`, written BIDIRECTIONALLY (relation on A,
  reverse on B). Common pairs: cools/cooled_by, charges/charged_by, controls/
  controlled_by, actuated_by/actuates, part_of_system/system_component, powers/
  powered_by, monitors/monitored_by.
- Every fact/link/node carries `provenance`: `{source_doc, page/sheet, bbox,
  source_type, authority, as_of}`.

## The rules (from `pipeline/sfi_allocate.py` — call it, don't hand-roll)

- **R1 Occupancy check** before assigning a logical SFI: `sfi_allocate.is_free(code,
  structure, register)` — yard tree AND Register, yard has priority. NEVER assign N+1
  blindly (the "651 mistake": 650+1 collided with BAE/ONYX).
- **R2 Allocate in a range**: `sfi_allocate.allocate_in_range(low, high, structure,
  register)` when the engineer says "a free SFI between X-Y". Exhausted → it raises;
  surface that, don't overflow.
- **R3 Auto-create gate**: `sfi_allocate.classify_creation(make, model, class)` →
  `auto_create` only when make + model + known class all resolve from one authoritative
  source; else `create_flagged` with the gap named. Never a silent guess.
- **Parent/child**: where a section holds multiple physical instances of one type,
  make the section a parent and each instance a child (per-installation, for fault
  isolation) — e.g. `595-emp-glycol-pumps` parent → ECP1/2/3/4/MCP/BCP/HCP children.
- **Identity conflict / multi-model → the engineer, never silently resolve.** Surface
  on the confirmation list with both values + sources inline on the node
  (`identity_status: conflict`), and mirror the state on-node (not log-only). Case A
  (same thing, two claims — e.g. FEIT vs Gianneschi) = defer. Case B (a recorded
  convention confirms two expected units) = may split with `pattern_split` provenance.

## The write, then the gate (ALWAYS)
- Prefer `pipeline.node_write.NodeWriter` for extraction routing (dry_run=True default;
  handles load-map/§9e/revision-gate/feeder/idempotency). For red-pen application a
  direct script is fine — mirror its provenance + guards.
- **Integrity check before saving** — no dangling cross_links / parent_id / children;
  every target exists in `ids`. Only `json.dump` the file if 0 issues. Print
  `Register N (M active), integrity 0` and confirm before reporting done.

## Routing specifics (node_write)
- Role from `element_type`, never the label. SUPPLY → load-map (`_load_map_lookup`:
  exact → device-prefix-stripped → whole-word containment) → §9e → flag. INDICATOR →
  `has_status_indicator_on` cross-link to the monitoring node, never a control fact.
  CONTROL → control_element. Structural → not_routed (surfaced) or power_path assembly.
- Source-type gate: hydraulic control map only for `source_type ∈ {schematic,
  hydraulic_schematic}`. Revision gate: refuse facts from superseded drawing ids.

## Report
`Register N entries (M active), integrity 0`. Then: nodes created, facts/links added,
anything flagged for the engineer (conflicts, uncertain allocations), backup path.
