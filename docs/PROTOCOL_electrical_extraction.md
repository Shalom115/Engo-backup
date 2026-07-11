# PROTOCOL — Electrical Schematic Extraction & Routing

Consolidated reference (Ch 3.1 S1). The rules below were learned the hard way
across the GM-book work and the engineer's red-pen sessions; they lived scattered
in CLAUDE.md. This is the single place to read before touching electrical
extraction on this vessel or the next. Fleet-general unless marked [VESSEL].

Version 1.0 — 2026-07-12. Every rule traces to code + a scar.

---

## A. Reading a sheet (the pipeline, in order)

1. **Render before designing.** Never build a handler for a new sheet class from
   memory — render 2-3 real examples first. (`discover_structure` was built for
   hydraulic slices from memory and silently failed on every other class.)
2. **Legends first.** `legend_first.from_pdf` reads the sheet's OWN legends/tables
   before any symbol. The sheet's legend OVERRIDES the general glossary.
3. **Classify sub-type** (`electrical_extract.survey`): distribution_schedule /
   power_one_line / relay_terminal_wiring / mixed. The read strategy differs per
   sub-type — classifying first is what stops a reader built for one class
   failing silently on another.
4. **Coverage-guaranteed detail read.** Survey regions ∪ a fixed 3×3 grid, merged
   with dedupe (`read_wiring_coverage`). Region detection is stochastic; the grid
   guarantees no blind spot.
5. **Cross-reference against the full page** (`read_wiring_region(cross_reference=
   True)`) — TWO calls: crop-enumerate, then enrich the list against the full page.
   A single two-image call makes the model summarize and drop the element array.
   The enrich merge (`_merge_enriched`) enforces never-invent / never-drop **in
   code** — corrected-on-id-match, kept-from-crop-when-dropped, invented ids
   discarded, all guarded against non-dict vision output.

## B. Typing symbols (the §6 device discipline + the glossary)

- **breaker ≠ fuse ≠ relay ≠ contactor ≠ terminal ≠ switch; signal ≠ power.**
  Mark ambiguous, never guess; `<UNKNOWN>` for illegible, never fabricate.
- The engineer-confirmed symbol conventions live in
  `prompts/drawing_symbol_glossary.md` (injected into every prompt). Highlights:
  - Diamond + number on a wire = **wire-gauge callout (annotation)**, not a signal.
  - HI + LO + shield twisted = **CAN bus** (status signal), not power.
  - HVIL = high-voltage interlock signal.
  - A multi-pin block labelled "SWITCH" on an HV/motor feed = **harness
    connector/plug**, not a mechanical switch. (The plug-mistaken-for-switch trap.)
  - "ISOLATOR" + ampere rating = **breaker**.
  - CT = current transformer (a monitor), routes to the monitoring system.
  - EARTH LEAKAGE n = earth-leak breaker (protection).
  - A cross-drawing pointer is annotation ONLY if it carries no wire. **THE WIRE
    IS THE TEST** — a wired element with a "see DWG n" reference stays an element,
    typed by its function. (The CP-SW over-correction, engineer-caught.)
- **[VESSEL] Sheet-scoped vocabulary:** a device prefix can mean different things
  on different sheets — e.g. CBx on GMMS 110b/d/e = **retractable fuse**, not a
  breaker. Read the sheet's own convention.

## C. Routing an element to a node (node_write)

Role from `element_type`, never guessed from the label:
- **SUPPLY** (breaker/fuse/…) → `write_electrical_row`: the LOAD is the equipment.
  Resolution order: engineer-confirmed **load map** (`_load_map_lookup`: exact →
  device-prefix-stripped → whole-word containment) → §9e semantic matcher →
  `create_flagged`. The protective device becomes an `electrical_supply` fact on
  the load's node.
- **FEEDER ≠ LOAD:** if the "load" is a sub-distribution box, attach a
  `feeder_supply` fact + `feeds` cross-link on the panel — never invent an
  equipment identity for a distribution box.
- **INDICATOR** (status_signal) → `has_status_indicator_on` cross-link to the
  monitoring node ([VESSEL] ONYX / `652-onyx-monitoring`), NEVER a control fact.
- **CONTROL** (switch) → `control_element` fact / `controls` cross-link.
- **Structural** (terminal, relay, controller_module, plug_pin, device) → NOT
  routed as loads; either `not_routed` (surfaced) or assembled by the power-path
  protocol into `power_path` facts on resolved equipment.
- **Source-type gate:** the hydraulic control map applies ONLY to
  `source_type ∈ {schematic, hydraulic_schematic}`. Electrical sheets never hit it.
- **Revision gate:** facts from a superseded drawing id are refused outright.

## D. The engineer's routing logic (from the load-map red-pens)

These are how the engineer thinks — encode them, don't relearn them per vessel:
- **Full-path hierarchy:** a node lives at the end of region→subsystem→equipment,
  matching how systems nest (BEL → 600 Electrical → 620 Power conversion → 629).
- **Pins attach to their plug's owner** — a connector pin/wire tag is not a load;
  follow the line to the labeled header box; the pin is a fact on that equipment.
- **Equipment belongs to its SYSTEM, not its power source** — a BAE cooling pump
  is 595 cooling, cross-linked to the BAE side; a pump belongs to its system.
- **Cooling topology** and **control chains** are first-class cross-links
  (cools/cooled_by; switch→relay→pump links controller AND actuated equipment).
- **Earth-leak breakers are protection FOR something** — attach to the protectee
  when it names an equipment; stay with the panel when it protects a line.
- **CT → monitoring node**, cross-linked to what it measures.
- **[VESSEL, safety] Navigation/steaming lights are ALWAYS their own node**,
  separate from general lighting.
- **"Disregard" / "skip" are real dispositions** — record them, don't force-route.

## E. Node creation rules (Decision-5 + SFI, now in `sfi_allocate.py`)

- **R1 occupancy check** before assigning a logical SFI — yard tree + Register,
  yard has priority. (The "651 mistake": 650+1 assigned blindly hit BAE/ONYX.)
- **R2 allocate in a range** — lowest free code checked against both sources;
  exhausted → raise, never overflow.
- **R3 auto-create gate** — auto-create WITHOUT flagging only when make + model +
  known equipment class all resolve from one authoritative source; else
  create_flagged with the specific gap named.
- **Parent/child** where a section holds multiple physical instances of the same
  type (per-installation nodes for fault isolation).

## F. Standing verification discipline

- **"Clean" means verified, not "didn't crash."** Every re-extraction page is
  reconciled against the flagged list (`compare_reextraction` / `verify_page_live`):
  unanimous-retype / same-type(+suspects) / multi-instance / lost.
- **A "lost" item is dispositioned by RENDERING the region, never from labels.**
  (CP-SW = real loss; SW-3/4 = real improvement — only the drawing told them apart.)
- **Never report "done/passed" without re-reading the actual run output** and
  quoting real numbers. (The fabricated Gold-#2 entry scar.)
- **Guard every vision-output consumer against non-dict array entries** — the
  JSON-schema `items:{type:object}` is a request, not a guarantee (crashed twice).

---

### Pointers to the live code
`pipeline/legend_first.py` · `electrical_extract.py` · `symbol_glossary.py` ·
`node_write.py` · `node_match.py` (§9e) · `power_path.py` · `revision_gate.py` ·
`sfi_allocate.py` · `abbrev.py` · `compare_reextraction.py` · `verify_page_live.py`
Prompts: `prompts/drawing_symbol_glossary.md` · `prompts/system_archetypes.md`
