# DESIGN — One-Line Topology Router (Ch 2.2 S8)

Status: **DESIGN, awaiting engineer grade before build.** Author: Fable, 2026-07-12.
Free (no API cost) — the input already exists.

## What it does

Turns the 26 topology-bearing pages of the GM book into Register **facts +
cross-links** — the power-distribution backbone (batteries → isolators → buses →
converters/chargers → loads) — so Engo can answer "what feeds the 600V DC bus?"
and "trace the port propulsion supply" from the node graph, not from a drawing.

Input already extracted (NO re-extraction — it cost real money):
`data/ledgers/batch2a_v2_ledger.jsonl` — **5,279 topology_nodes + 4,368
topology_edges** across 26 pages. Node shape:
`{node_type, id, label, rating, _bbox, _via}`; edge shape: `"W1 -> W2"` (verbatim
source→target by node id, scoped to the sheet).

## The hard part (grounded in the real data)

Buses are **infrastructure that recurs across sheets and is physically ONE thing**.
Measured from the ledger: `600V DC BUS` appears on **6** sheets, `+24V SERVICE
BAT.` on **8**, `NEGATIVE BUS` on **5**. A router that treats each sheet's bus as
a separate node produces 6 disconnected "600V DC BUS" fragments and the trace
breaks at every sheet edge. So the router's core job is **cross-sheet bus
reconciliation** — the same problem the cross-drawing loop-follower solved for
wires, applied to rails.

## Design

### 1. Two populations, handled oppositely (the equipment-vs-infrastructure split)

- **INFRASTRUCTURE** (bus, rail, ground, neutral, negative) — NOT equipment
  nodes. They become **shared junction points** the router reconciles across
  sheets and records as `topology_edge` facts on the equipment they connect.
  Rule of thumb = a busbar is infrastructure; a charger/battery/converter is
  equipment. `node_type` ∈ {bus, rail, ground} OR a label matching
  `BUS|RAIL|NEG|GND|GROUND|NEUTRAL` → infrastructure.
- **EQUIPMENT** (battery, generator, charger, isolator, converter, shunt, CT,
  load) — resolve to a Register node via §9e + the electrical load map
  (`_load_map_lookup`, the prefix-strip+containment path just built). Unresolvable
  → `create_flagged`, never guessed (flag-never-guess, unchanged).

### 2. Cross-sheet bus merge key (reuse the proven matcher, never raw substring)

Merge key = **normalized label + node_type**, matched on whole tokens (mimic
`power_path._toks` / token-boundary — NEVER raw substring; "NEG" must not hit
inside "GENERATOR"). Normalization: uppercase, collapse whitespace, strip a
leading side-word (PORT/STBD) into a `side` attribute so `PORT 600V DC BUS` and
`STBD 600V DC BUS` stay DISTINCT (they are — 3× each in the data) while
`600V DC BUS` on six sheets merges to one.
- Merge is **conservative**: identical normalized label + same node_type + at
  least one shared connected-equipment token → merge. Ambiguous (same label,
  different voltage/side) → keep separate + record a `possible_same_as` note for
  the engineer, never auto-merge across a voltage/side difference.
- Output: a `bus_registry` (vessel-scoped JSON) — one entry per reconciled
  physical bus, listing every (sheet, node id) that maps to it. This is the join
  table the edge writer uses.

### 3. Edges become facts on BOTH endpoints (with provenance)

Each `"A -> B"` edge, once both ends resolve (equipment node id or reconciled
bus id), is written as a `topology_edge` fact on **both** endpoint nodes:
`{from, to, via_bus?, source_doc, page, edge_text_verbatim, bbox?}`. Bidirectional
so a trace from either end finds it. A bus that connects equipment X and Y yields
`X --(600V DC BUS)--> Y` reconstructable from either node.
- Unresolved endpoint (bus not reconciled, or equipment not in Register) → the
  edge is kept in a `topology_unresolved` list with its verbatim text, surfaced
  not dropped (P6, same discipline as power_path).

### 4. Direction / polarity (best-effort, never invented)

Edge text is directional as printed (`source -> dest`). Tag rail polarity from
the label keywords the way `power_path.infer_rail` already does
(positive/negative/ground/signal). Where the drawing doesn't say, leave `unknown`
— do not infer current direction from position.

## Build plan (after grade)

`pipeline/topology_router.py`:
1. `build_bus_registry(pages)` — pure data, no API. Reconcile buses across the 26
   pages per §2; emit `data/state/bus_registry_<vessel>.json`.
2. `route_topology(pages, register, bus_registry, dry_run=True)` — resolve
   equipment endpoints (§9e + load map), write `topology_edge` facts on both
   ends, collect unresolved. Mirror `node_write` conventions (provenance, dry-run
   default, integrity check, create_flagged for unresolved equipment).
3. Dry-run whole book → **engineer grades** → real write (`dry_run=False`).

## Verify (the acceptance test, from the spec)

Shore-power sheet (page 2, GMMS 108'-101): the known chain **Q1 → 600V DC BUS →
EDN-P** must reproduce as edges on the Q1 breaker fact, the reconciled 600V DC bus,
and the `627-edn` node — with `600V DC BUS` being the SAME reconciled entry that
appears on the other 5 sheets, not a page-2-local fragment.

## Cost / risk

- **$0 to build and dry-run** — operates entirely on the existing ledger + the
  live Register. No vision calls.
- Risk: over-merging buses of different voltage/side. Mitigated by the
  conservative merge key (voltage + side kept distinct) + `possible_same_as`
  flagging instead of silent merge. The engineer sees every merge decision in the
  `bus_registry` before the real write.
- Gold-blind / fleet-general: no vessel token in the router; bus vocabulary is
  read from the sheet, not hardcoded.

## Open question for the engineer

The 17 pages WITHOUT topology (schedule/wiring-only sheets) contribute no rails —
expected. But 3 label pairs are genuinely ambiguous in the data
(`+24V SERVICE BAT.` vs `+24V SERVICE BUS` — is the battery-terminal node the same
junction as the service bus, or one hop apart?). Design choice: keep them
**separate** and let the edge between them express the hop, rather than merge a
battery terminal into a bus. Flag for confirmation.
