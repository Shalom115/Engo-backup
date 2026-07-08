# System Archetypes — fleet-general reference (v0.4, 2026-07-06)

**Scope: this file is FLEET-GENERAL.** No vessel-specific brands, part
numbers, Register IDs, or "on this vessel" asides belong here — that
content lives in the Register. This file answers two questions only:
(1) what components does a system of this TYPE normally contain, and
(2) what does each symbol commonly look like and get confused with.
Gelliceaux is the first vessel this gets used on; Phase 2 uses the same
file, unchanged, for every vessel after it. Improve it over time — don't
narrow it to one boat's specifics.

Symbol conventions below are grounded in ISA 5.1 / ISO 14617 (the standards
actual P&ID symbols follow) and confirmed directly against a real drawing's
own legend. **A specific drawing's legend always wins if it differs** —
these are the common-case defaults and disambiguation cues, not a
substitute for reading the sheet's own legend.

Sources: [P&ID Symbols List (Projectmaterials)](https://blog.projectmaterials.com/epc-projects/engineering/pid-symbols-list/), [Valve Symbols in P&ID (Tango Valve)](https://www.tangovalve.com/understanding-valve-symbols-in-pid/), [ISO 14726 (marine piping colour ID)](https://www.iso.org/standard/44744.html)

---

## SHEET-READING SEQUENCE (mandatory, in this order, for EVERY system drawing)

This is the executable protocol. It is not optional and does not wait to be
prompted — every schematic/system-drawing read starts here, step 0 first.

0. **Inventory the sheet's reference material.** Scan the whole sheet and
   list EVERY legend and table present before reading any of the diagram:
   symbols legend, pipe/line legend, text/tag legend, BOM/parts table,
   equipment data tables (pump data, fan data, compressor data...), tank
   connection details, operating-modes panels, notes blocks. A typical
   system sheet carries 5-8 of these.
1. **Read every one of them, fully, line by line** — before classifying a
   single diagram symbol. The pipe/line legend and the BOM are the two most
   often skipped and the two that have caused real failures.
2. **Establish what the system IS** from the pipe legend + title block
   (e.g. gas/refrigerant vs. chilled water; seawater vs. closed coolant).
3. **Recall the matching archetype** (below) — what components a system of
   this type should contain, its loop shape, its known naming traps.
4. **Trace the loops** per the Loop-Following Protocol — one line type at a
   time, origin to termination, cataloguing components in path order.
5. **Reconcile against the BOM by MODEL NUMBER** — every BOM line should
   map to traced components; every traced component should appear in the
   BOM. Name mismatches joined by model number (Standing Rule 5); count
   mismatches are findings to surface, not force.
6. **Only then extract/route components to nodes** — with the loop context
   and legend definitions attached as provenance.

---

## STANDING RULES (apply to every drawing read)

1. **Read EVERY legend and table on the sheet — not just the first or most
   obvious one.** A single P&ID-style drawing commonly carries SEVERAL
   distinct reference tables, each answering a different question: a
   SYMBOLS legend (what each icon means), a TEXT/numbering legend (how tags
   are formatted), a **PIPE/LINE legend** (what each line COLOR or style
   represents — easy to miss because it looks decorative, but it's the key
   to tracing flow paths — see the Loop-Following Protocol below), a BOM/
   parts table, and sometimes an operating-modes table. Missing the pipe
   legend specifically was a real, documented failure on this project —
   reading only the symbols legend gave the components, but missed how they
   connect. **Go through each legend/table you find line by line, item by
   item, and confirm it against the diagram** — this is slower than
   skimming but is what actually makes the diagram make sense as a whole,
   not just as a pile of labeled icons.
2. **Garbled text does not block a clear drawing.** If a sheet's TEXT layer
   is corrupted/unreadable (a known failure mode — see the Class-C text
   corruption pattern already documented in this pipeline) but the DRAWING
   itself is visually clear, still extract what the drawing shows: symbol
   shapes, component count, layout, connections. Don't discard a
   perfectly-readable drawing because its labels are garbled — get the idea
   from the picture, note the labels as unreadable, and don't force a text
   read that isn't there.
3. **Symbols that look similar are the highest-risk misread.** See the
   Symbol Reference below for the specific look-alike pairs. When two
   candidates are both plausible, say so — don't force one.
4. **A component role's symbol convention varies more by drafting house
   for LESS-standardized items** (suction/pickup points, strum boxes,
   proprietary sensor blocks) **than for well-standardized ones** (ball
   valves, motor/solenoid actuators, pumps). Trust the legend more, and your
   own prior, less, for the less-standardized categories.
5. **The SAME physical equipment may appear under DIFFERENT NAMES in
   different parts of one drawing — cross-reference by MODEL NUMBER (the
   stable key), never by descriptive name (which varies).** A real,
   documented failure on this project: a BOM listed items as "AIR HANDLER
   (with a BTU rating)" while the plan view labeled the IDENTICAL model
   numbers as "FANCOIL UNIT" — reading the two names without matching
   the model numbers invented a phantom extra component ("an air handler"
   separate from "the fancoils") that does not physically exist. **Rule:
   before treating a name in one table as a new/distinct component, check
   whether its model/tag number already appears elsewhere on the sheet
   under a different descriptive name — if the model matches, it is the
   SAME equipment, not a new one.** This is why reading every table AND
   joining them by model number (not by name) matters — a component list
   built from names alone will double-count or invent equipment.
6. **Read the PIPE/LINE legend to know what the system actually IS, not
   just how it connects.** The line contents are diagnostic of system type:
   a legend reading "GAS SUPPLY / GAS RETURN" means a direct-refrigerant
   (gas) system; "CHILLED WATER SUPPLY/RETURN" means a chilled-water system;
   these look similar on the diagram but are fundamentally different systems.
   A real failure here: an aircon system was labeled "chilled-water" when
   its pipe legend plainly said GAS supply/return (a VRV direct-refrigerant
   system) — the legend was the single fact that would have prevented the
   mislabel.

---

## LOOP-FOLLOWING PROTOCOL

**The core method for reading any P&ID-style drawing correctly: identify
each distinct line/circuit type from the pipe/line legend, then FOLLOW it
from its origin to its termination, cataloguing every component you pass
on the way.** This is the same discipline already proven for electrical
wiring (trace a circuit from supply, through every breaker/relay/terminal,
to the load, and back through the return/negative path) — applied here to
fluid, air, and signal systems generally. A component list alone (five
valves, three pumps) doesn't tell you how they relate; the LOOP does. This
is what turns a pile of labeled icons into the correct node structure.

### How to do it

1. **Find the pipe/line legend first.** It defines the line colors/styles
   (e.g. metallic vs. flex, main vs. auxiliary, supply vs. return, service-
   specific colors) — this is your map of how many DISTINCT loops exist on
   the sheet before you trace any of them.
2. **Pick one line type. Find where it starts.** The origin is usually a
   source: a tank, a seachest, a compressor, a pickup point — read the
   diagram at that point first.
3. **Follow that exact line color/style across the whole sheet** (and onto
   a referenced sheet if the line continues there), noting every component
   it passes through in order: valves, pumps, filters, sensors, junctions.
   Don't jump to a same-colored line elsewhere in the drawing without
   confirming it's actually the same physical run, not a second, separate
   instance of the same line TYPE (a second bilge zone's main line is drawn
   in the same colour as the first — same TYPE, different physical run).
4. **Note the termination** — overboard, a tank, a distribution point, a
   user-facing fixture, or back to the same source it started from.
5. **Repeat for every distinct line type on the sheet.** A single system
   drawing commonly contains 2+ independent loops (e.g. a main line AND an
   auxiliary line, each its own color) — tracing only one and assuming it
   covers the whole system is a real, easy mistake.
6. **If an OPERATING-MODES drawing exists, use it — it hands you the loops
   pre-traced.** Many systems have a companion "operating modes" sheet
   (commonly: fuel, bilge/fire, grey/black water, fresh water, raw water,
   cooling, pneumatic). It shows the SAME system several times, once per
   mode (Normal / Emergency / Transfer / Bunkering / etc.), with the ACTIVE
   path for that mode highlighted in a mode-specific COLOR and the valve
   states shown (open / closed / crossed-out = not used in this mode), plus
   a mode→color legend. This is the single best source for "which path is
   actually live when" — read it before or alongside the main schematic;
   each mode's colored path IS a loop, already traced for you, including
   which valves must be open for it. A system's "normal operation" loop is
   just its Mode-1 colored path.

### OPEN loops vs. CLOSED loops — the endpoint differs, know which you're tracing

- **OPEN** (most fluid-waste and once-through systems): starts at a source,
  ends by LEAVING the system entirely — overboard, to a tank for later
  discharge, to a user fixture that consumes it. Bilge, grey water, black
  water, fresh water (distribution side), fuel, deck drains.
- **CLOSED** (most machinery/climate circuits): starts at a source and
  RETURNS to that same source — a reservoir, a compressor, a chiller.
  Power hydraulics, refrigeration/aircon refrigerant or chilled-water side,
  cooling water (machinery coolant loop). Tracing one of these "to the end"
  means tracing it all the way back to where it started, not to an exit
  point that doesn't exist.
- Ventilation is a third shape: two INDEPENDENT one-way paths (supply IN,
  extraction OUT) that don't connect to each other as a single loop.

### Worked example (already proven, generalize the method from it)

The power-path protocol built for electrical wiring is this exact method
applied to circuits: anchor at a resolved piece of equipment, walk outward
along the wire, through every breaker/fuse/relay/terminal, tag which leg is
positive/negative/signal, and record the whole path as one structured
trace on the node. The fluid/pneumatic version is the same shape: anchor at
a component, walk along the correctly-identified line color, through every
valve/pump/sensor, tag which segment is supply vs. return (for closed
loops) or main vs. auxiliary (for systems with parallel lines), and record
the path on the node it belongs to.

### Per-archetype loop definitions

See each system's own entry below for its specific loop(s) — the general
method above applies uniformly; what differs per system is the loop's
actual origin, termination, and whether it's open or closed.

---

## SYMBOL REFERENCE (general — confirm against the sheet's own legend)

### Valves

| Symbol | Typical shape | Confused with | How to tell apart |
|---|---|---|---|
| Ball valve (2-way), manual | A bowtie/hourglass (two triangles meeting at a point) representing the valve body | 3-way ball valve; a motor/solenoid-actuated valve of the same base type | 3-way adds a third port/leg (often drawn as a 4-pointed "propeller" shape, not just two triangles); actuated valves add a mark ABOVE the bowtie — check for that mark before calling something manual |
| Ball valve (3-way) | A 4-pointed cross/propeller shape, or a bowtie with a third leg | 2-way ball valve | Count the ports/legs — 2-way has two, 3-way has three |
| Motor-actuated valve | The base valve bowtie PLUS a small circle or square marked "M" directly above it, usually joined by a short vertical line | A plain manual valve of the same base shape; a solenoid-actuated valve | The letter inside the actuator mark is the tell: "M" = motor, "S" = solenoid, no mark = manual. Don't assume from the base bowtie shape alone — the actuator mark is often small and easy to miss in a dense drawing |
| Solenoid-actuated valve | Base valve shape plus a small coil symbol or a mark labeled "S", sometimes drawn as a diamond | Motor-actuated valve | Same rule — read the letter/coil symbol, don't guess from silhouette |
| Non-return / check valve | An arrow or flap shape inside the line, allowing flow one way only | A flow-direction arrow printed alongside a pipe (which is just a direction indicator, not a valve) | A check valve is an in-line component with its own tag/BOM number; a flow arrow is just an annotation |
| Pressure relief valve | A valve symbol with an angled/spring-loaded cap element, often drawn with a small arrow showing relief direction | A standard check valve | Relief valves typically have a spring/angle element and a stated set pressure nearby |
| Gate / globe valve | A bowtie or a valve-body outline with a visible stem/handwheel line | Ball valve | Less common in marine plumbing than ball valves; check for a distinct handwheel/stem line |

### Pumps

| Symbol | Typical shape | Confused with | How to tell apart |
|---|---|---|---|
| Electric-motor-driven pump | A circle (the pump body) with a small square/box marked "M" attached | I.C.E.-driven pump; manually operated pump | The letter in the attached box: "M" = electric motor, "E" = internal combustion engine; a manual pump has a hand-lever/crank element instead of a motor box |
| I.C.E.(diesel/engine)-driven pump | Same pump-circle base, box marked "E" instead of "M" | Electric-motor-driven pump | Check the letter, not the circle shape — they're often otherwise identical |
| Manually operated pump | Pump-circle base with a hand-lever or crank symbol, no motor box | Electric/engine-driven pump | Absence of any motor-box mark, presence of a lever/handle element |

### Strainers, filters, suction points

| Symbol | Typical shape | Confused with | How to tell apart |
|---|---|---|---|
| Strainer / filter | An open diamond/rhombus outline, sometimes with internal cross-hatching | A pickup/suction-point triangle; a valve bowtie | A strainer's diamond is a single closed shape with no "bowtie pinch point"; check the legend, this category varies by drafting house |
| Pipe suction / pickup point | Often a simple filled or outlined triangle at a pipe end, OR (in some marine drafting conventions) a "strum box" — a distinct basket/funnel-shaped icon representing a strainer basket with an integrated non-return valve | A valve; a strainer | A pickup point sits at the END of a branch (drawing a dead-end intake), not in-line on a through-flow path — position in the drawing is as diagnostic as the shape itself. **This category is the LEAST standardized — always confirm against the specific sheet's legend before naming it a valve.** |

### Sensors, switches, indicators

| Symbol | Typical shape | Confused with | How to tell apart |
|---|---|---|---|
| Level switch / float switch | A vertical or horizontal line with a small circle (the float) and a contact/switch mark; often shown inside or beside a tank outline | A level indicator (a passive gauge, no switch contact) or a level transducer (continuous signal, not a discrete switch point) | A SWITCH triggers at a discrete level (high/low) and drives an alarm or pump on/off; an INDICATOR/TRANSDUCER reports a continuous value. Check the text legend (LS=level switch, LI=level indicator, LT=level transducer are common abbreviations, but confirm per-sheet) |
| Pressure switch | A circle or box marked "PS", often with a small diaphragm/bellows element | Pressure gauge (PG) or pressure transducer (PT) | Again, letter-in-symbol is the tell — switch (discrete trigger) vs. gauge (local readout) vs. transducer (continuous electronic signal) |
| Control panel | Commonly a circled abbreviation (e.g. "CP") in a distinct color, placed near the equipment it operates | A local switch (a smaller, single-function control point) | A control panel groups multiple controls/indicators for a zone or piece of equipment; a local switch is usually a single on/off point, often drawn as a filled square |
| Status/alarm indicator (electrical) | Varies widely — a lamp symbol, a tagged terminal, or a small labeled box on a wiring diagram | A CONTROL element (something that commands an action) | An indicator only REPORTS state (e.g. a high-water alarm lamp); a control element CAUSES an action (e.g. a switch that starts a pump). Getting this backwards is a real, documented failure mode — treat every wiring-diagram element as exactly one of {supply, control, indicator} and verify which before routing it |

### Actuator vs. equipment (a modeling principle, not a symbol)

An actuator (a motor, cylinder, or solenoid that MOVES something) is not
the equipment it moves. A motorized valve's actuator and the valve body
are one physical unit for identification purposes, but a hydraulic
cylinder that opens a door is a SEPARATE thing from the door itself —
the door has its own operating limits/procedures independent of what
happens to move it. Don't route facts about the actuator onto the thing
it actuates, or vice versa, without checking which one a fact actually
describes.

---

## SYSTEM ARCHETYPES

For each system type: typical component roles broken out individually (not
summarized away), known real-world variants per component, and which
document class tends to be authoritative for which fact. A vessel's actual
system may vary — these are the common-case expectations that make a
narrow read ("just find the valves") give way to a complete one ("check
for the sensor, the pickup, the pump, and the valve, because a system of
this type usually has all four").

### Bilge System

**Per zone/compartment, expect ALL of:**
- **Level/high-water alarm sensor** — one per zone; a float or capacitive
  switch, triggers a local and/or monitored alarm.
- **Main suction pickup point** — often a strainer basket with an
  integrated non-return valve ("strum box" in some drafting conventions);
  feeds a common bilge line to the main pump. Sits at a branch DEAD END,
  not in-line — position is as diagnostic as symbol shape here.
- **Auxiliary pickup** — present in SOME zones, not necessarily all.
  **Variant:** some vessels instead fit a dedicated submersible pump per
  zone rather than a second pickup — same redundancy goal, different
  physical solution; don't expect one specific form.
- **Isolation valve(s)** — manual and/or electrically-actuated. Which
  zones get which type varies by design intent (harder-to-reach or
  higher-risk compartments more likely to get remote/electric isolation) —
  not a fixed ratio to expect.

**Centrally, expect:**
- **Main bilge pump** (one, primary capacity).
- **One or more auxiliary bilge pumps** (smaller capacity, may serve
  multiple zones or be zone-dedicated).
- **A "crash pump"** — diesel-driven, portable or fixed, dual-purpose:
  serves BOTH bilge emergency-flood response AND fire suppression (a hand-
  deployed pickup hose for flood, the same pump feeding the fire line for
  fire). Expect to find it referenced from both systems — that's not a
  duplicate, it's one physical pump with two roles.
- **Strainers** upstream of pumps.
- **A control panel.**

**Where to look:** a hydraulic/piping schematic shows the full physical
inventory (valves, pickups, pumps) correctly IF its legend is read
properly (misreading a pickup as a valve is a documented, real failure
mode — check the legend, not the silhouette). An electrical/wiring diagram
confirms what's actually motor-driven and shows the control chain
(breaker → relay → terminal → motor limit switches). A monitoring-system
drawing (e.g. an automation/alarm platform) is typically authoritative for
which sensor reports to which monitored point, and often uses different
zone-naming conventions than the hydraulic drawing — cross-reference by
function and rough position, not exact string match. No single one of
these three is complete alone.

**Loop(s) to follow (OPEN):** two independent lines to trace separately —
MAIN bilge line: pickup (per zone) → main line → main bilge pump →
overboard. AUXILIARY bilge line: aux pickup (only the zones that have one)
→ aux line → aux bilge pump (or a dedicated submersible pump, per the
variant above) → overboard. The two lines are usually a different color/
style in the pipe legend specifically so they don't get traced as one.

### Fire Suppression & Detection

**Commonly split across MULTIPLE unrelated drawings/folders — check for
this before concluding the system is covered; a single folder search will
likely miss real content.**

- **Fire line (ring main)** — runs the length of the vessel (often along
  both sheers), metallic pipe, fed by the fire pump(s), with **hydrant
  connections at intervals** (frame-station spacing is common).
- **Electric fire pump** — normal-operation pressure source for the line.
- **Crash pump** — the SAME diesel pump used for bilge emergencies (see
  Bilge System) — don't model it twice.
- **Fixed gas suppression** — a cylinder + release mechanism in high-value
  enclosed spaces (machinery spaces, battery/energy-storage compartments).
  Its own GA/mounting drawing, usually SEPARATE from the fire line
  schematic entirely. **Watch for text corruption on this drawing type
  specifically** — a documented, recurring pattern; if the text is garbled
  but the drawing is clear, use the drawing (see Standing Rules).
- **Local spray heads** — fixed nozzles in specific compartments (e.g. a
  tender/vehicle garage), independent of both the ring main and the gas
  system — a third, separate suppression mechanism, not a variant of the
  other two.
- **Smoke/heat detection network** — roughly one detector per accommodation
  space, PLUS a denser array around higher-risk machinery spaces. Its own
  drawing class ("fire detection layout"), reports to a dedicated fire
  alarm panel.
- **Gas alarm / ventilation interlock** — in fuel-adjacent enclosed spaces
  (e.g. a garage housing a fuel-powered tender), ties a gas detector to
  the space's ventilation fan.

**Where to look:** the general bilge/fire hydraulic schematic (line,
hydrants, spray heads, crash pump); a SEPARATE fixed-suppression folder
(cylinder GA + detection layout); the vessel's general alarm/monitoring
inventory for which panel each alarm actually reports to (a system may
report to BOTH a dedicated fire panel AND the central monitoring platform).

**Paths to follow:** THREE separate circuits here, don't conflate them.
(1) OPEN fluid loop: seawater suction (seachest) → fire pump → fire line
(ring main, its own color in the pipe legend) → every hydrant/spray head
branch off it. (2) Fixed gas suppression, a short one-way path: cylinder →
release mechanism → the one protected enclosure — trace source→target, no
return. (3) Detection, a SIGNAL circuit, not fluid: each detector →
wiring → alarm panel — traced with the electrical power-path method, not
the fluid method.

### Fresh Water System

- **Tank(s)** — commonly a port/stbd pair.
- **Pressure pump(s)** with an accumulator/pressure switch, maintaining
  line pressure on demand.
- **Distribution manifold** → per-fixture distribution, typically THREE
  lines per fixture: hot, cold, and a dedicated/sterilized line (not just
  hot+cold — check for the third line before assuming a simpler layout).
- **Watermaker** — main unit, sometimes plus a backup unit — feeds the
  tanks from seawater.
- **In-line sterilizer** (e.g. silver-ion) on the distribution line.
- **Water heater(s)** — often one per side/circuit.
- **Shore/dock fill connection** and a separate **bunker line**.
- **Electrically-actuated mixing valves** at showers (temperature control).

**Where to look:** this system is often unusually complete in ONE
document — GA + distribution schematic + full legend set + BOM together.
Cross-reference is mainly needed for tank construction/location specifics
from a separate structural drawing, not for the operational plumbing
itself.

**Loop(s) to follow (OPEN, and note the direction runs BOTH ways):**
DISTRIBUTION direction: tank → pressure pump → manifold → each fixture
endpoint (shower/sink/equipment/hose connection) — trace per line type
(hot/cold/dedicated are usually 3 distinct colors/styles, trace each
separately, don't assume hot and cold share a path). FILL direction (the
reverse): watermaker OR shore/dock connection OR bunker line → into the
tank — a genuinely separate loop from distribution, easy to skip if you
only trace outward from the tank.

### Raw (Sea) Water System

The seawater-side cooling supply — NOT drinking/domestic water. Feeds:
- **Main engine / generator cooling** — raw water through heat exchangers.
- **Other heat exchangers** — hydraulics, propulsion shaft seal, any other
  machinery needing seawater cooling.
- **Seawater feed to consumer systems** — watermaker intake, aircon
  condenser cooling.
- **Seachest(s)** — one or more, the actual seawater source, each with its
  own strainer.
- **Galvanic protection** — an impressed-current anode/protection unit,
  present because this is the seawater-wetted backbone of the vessel.
- Each heat exchanger typically has its own breather routed to a vent box.

**Where to look:** typically its own schematic, referencing consumer
systems (aircon, watermaker, hydraulics) by drawing number rather than
repeating their internal detail — follow those references rather than
assuming the raw-water schematic is self-contained.

**Loop(s) to follow (OPEN — intake to discharge, not a return-to-source
loop despite serving "cooling"):** seachest (source) → strainer → each
consumer branch in turn (main engine/generator heat exchanger, hydraulics
heat exchanger, shaft seal cooling, watermaker feed, aircon condenser
feed) → overboard discharge (or onward into the consumer system's own
loop, at which point that system's OWN loop definition takes over — follow
the reference to the other drawing rather than assuming this schematic
shows it too).

### Grey Water System

- **Fixture drains** — showers (direct-gravity OR sump-collected variants
  — a sump implies a local pump since gravity drainage isn't possible
  there), sinks, laundry (washer/dryer), refrigeration condensate.
- **Local sump + pump** where gravity drainage isn't possible.
- **A transfer unit per zone** moving collected water toward the tank(s).
- **Tank(s)** — commonly split fwd/aft.
- **Level switches** gating the discharge pump: a rising level triggers
  "pump on", a falling level triggers "pump off" — an automatic on/off
  pair, not a single switch.
- **High-level alarm**, separate from the on/off switches.
- **Overboard discharge.**

Structurally similar in SHAPE to a bilge system (zone → pickup/transfer →
tank → pump → overboard) but a completely different purpose — don't
conflate the two just because the flow pattern rhymes.

**Loop(s) to follow (OPEN):** fixture drain (shower/sink/laundry/
condensate) → local sump + pump (only where gravity alone can't reach the
tank) → per-zone transfer unit → tank → discharge pump → overboard. Trace
per zone separately — each zone's drain path is independent until it
reaches the shared tank.

### Black Water System

- **Toilets** — each typically with an INTEGRATED macerator pump (the
  pump is part of the toilet unit, not a separate component to look for
  elsewhere).
- **Collection line(s)** from each toilet to the tank(s).
- **Tank(s)** — commonly fwd/aft split.
- **Discharge** — either overboard (where legally permitted) or to a
  shore pump-out fitting.
- **Anti-siphon protection** on the discharge/vent lines.
- **Tank-level switches** (full / low).

**The discharge MODE currently selected (overboard vs. holding) is an
operational fact worth capturing on its own** — the schematic shows the
plumbing that makes both modes possible, not which one is currently
active. Look for a separate "operating modes" document; don't assume the
schematic alone answers "where is the waste going right now."

**Loop(s) to follow (OPEN, with a MODE-DEPENDENT termination):** toilet
(WC unit, integrated macerator) → collection line → tank. From the tank,
the loop has TWO possible endpoints depending on the operating mode
selected — overboard discharge, or a shore pump-out fitting — trace BOTH
branches off the tank even though only one is active at a time; which one
is currently selected is a separate fact, not read off the pipe path
itself.

### Fuel and Oil System

- **Fuel tank(s)** — commonly 4 (port/stbd × inboard/outboard), sometimes
  fewer; sizes vary.
- **Day tank** — a smaller intermediate tank feeding the engines directly.
- **Fuel transfer pump(s)** — moving fuel between tanks (not the same as
  the supply pump feeding the engines).
- **Fuel supply pump(s)** — feeding engines/generators.
- **SWITCHABLE/redundant filter pairs** — one filter operates while the
  other is spare/ready for changeover. **Expect this pattern — a filter
  branch that looks "unused" in a reading is normal, not a fault.**
- **Oil-change unit** — often portable, for engine oil service (a separate
  fluid system that commonly rides on the same folder/schematic).
- **Tender/auxiliary-craft fueling provisions**, where applicable.
- **Level sensors + high/low alarms**, per tank.

**Where to look:** frequently complete in one dense document (GA +
schematic + BOM). Tank CONSTRUCTION detail (coatings, structural
lamination) is typically a separate document from the operational plumbing
system — don't expect coating/construction specs on the schematic.

**Loop(s) to follow (OPEN, and check an operating-modes sheet FIRST if one
exists):** fuel tank → transfer pump → day tank → supply pump → the
active filter of a switchable pair → engine/generator. **General
principle, not fuel-specific: whenever a system has an "operating modes"
document, read it before tracing the loop** — it tells you which of
several possible paths is actually in use (which tank feeds which engine,
which filter is live), information the schematic's plumbing alone won't
give you.

### Power Hydraulic System

**Distinctive pattern, worth naming explicitly: the system folder's own
top-level schematic is often a GA/ROUTING map ONLY** — it shows where
hydraulic blocks and main supply/return/leak-off lines physically run
through the vessel, then EXPLICITLY defers ("refer to the following
drawings...") to other, separately-titled documents for the actual
function-level schematics: manifolds, cartridge valves, per-function flow/
pressure ratings. **Don't mistake the routing GA for the complete system —
follow its own references to the real detail documents.** Those detail
documents are commonly supplied by a specialist hydraulics subcontractor,
not the yard directly, and a separate document from the propulsion
gearbox/pitch-control vendor may exist if the vessel has controllable
pitch propulsion — a THIRD document family for this one system class.

- **Hydraulic power pack(s)/pump(s)** — the pressure source.
- **Manifold blocks** — one per functional group (e.g. a mast/deck-gear
  block, a steering/keel block) — each block is its own equipment
  identity, not interchangeable with another block of the same model
  elsewhere on the vessel (a real, previously-caught mistake: same model
  on a different sheet = a different physical unit).
- **Function-level cartridge valves** within each block — each serves ONE
  named function (a winch, a ram, a furler) and is a control fact
  belonging to that piece of equipment, not a separate equipment identity
  of its own.
- **Reservoir/oil tank.**
- **Distribution lines** (pressure, return, leak-off — commonly
  colour-/line-coded, check the pipe legend).

**Loop(s) to follow (CLOSED — returns to its own reservoir, does not
discharge anywhere):** reservoir → pump → PRESSURE line → manifold block
→ the specific function (a winch motor, a ram) it's routed to → RETURN
line → back to the reservoir. Pressure and return are normally distinct
line colors in the pipe legend — trace them as two halves of one loop, not
two separate systems. A leak-off/drain line (if present) is a third,
usually low-flow path back to the reservoir, worth tracing separately from
the main return.

### Pneumatic System

- **Compressed-air-actuated features** — commonly watertight door seals
  and cylinders (with an "emergency open" manual override), air horns,
  or other pneumatically-actuated hardware.
- **Main air compressor** + **backup compressor**.
- **Air receiver tank(s)** — local storage near point of use.
- **Filter-regulator-lubricator (FRL) units** — condition the air before
  use.
- **Quick-couplers** at usage/service points.
- **Solenoid valves** controlling cylinder extend/retract.

Typically compact and fully documented in a single schematic on most
vessels — a system where "check three drawings" is less likely to apply
than for bilge/fire.

**Loop(s) to follow (OPEN — air is used and vented, not returned):**
compressor → receiver tank → FRL unit → distribution line → each user
point (a door cylinder's extend/retract solenoid valves, an air horn).
Trace each user branch off the main distribution line separately — a door
seal circuit and the horn are independent branches, not a single path.

### Refrigeration System (galley/food storage)

**Do not conflate with Aircon (climate control)** — same underlying
refrigerant-circuit technology, different purpose, and typically a
completely separate control system with its own panel.

- **Multiple individual fridge/freezer units** — galley, deck-mounted,
  and sometimes a dedicated unit in an unusual location (e.g. a bilge-area
  freezer) — don't assume all units are in the galley.
- **Compressor per unit (or small group)** — single-compressor units are
  common; refrigerant type varies by unit/vintage, don't assume uniformity
  across units on the same vessel.
- **Condenser(s)** — often outboard-mounted, tied to the compressor.
- **Refrigerant distribution board** — ties multiple units' refrigerant
  lines together.
- **Dedicated control panel** — separate from the aircon control system.

**Loop(s) to follow (CLOSED, HUB structure — verified against a real
drawing 2026-07-06):** the pipe legend typically splits the refrigerant
path into distinct FUNCTION lines — trace each: compressor → *delivery to
distribution board* → refrigerant distribution board (the hub) → *delivery
to fridge/freezers* → each unit's evaporator → *suction* line → back to the
compressor. Separately, a *condenser cooling* line (its own pipe-legend
color) rejects the heat — off the compressor to the condenser and back (may
itself be seawater- or air-cooled). Note there may be MORE THAN ONE
compressor, each with its OWN distribution board + condenser, serving a
different GROUP of units (e.g. a water-cooled compressor for the main
units, a separate air-cooled compressor for a remote deck fridge) — trace
each compressor's hub separately, don't assume one compressor feeds
everything.

### Aircon System (climate control)

- **Central compressor/condensing unit(s)** — in a machinery space. Confirm
  from the PIPE LEGEND whether this is a CHILLED-WATER loop (legend says
  water supply/return) or a direct-refrigerant VRV/VRF system (legend says
  GAS supply/return) — they look similar on the diagram but are different
  systems; the pipe legend is the deciding fact, don't assume. Often
  seawater-cooled (a raw-water line through the condenser's heat exchanger).
- **Per-zone fancoil units** — one per cabin/space, each independently
  identifiable with its own tag. **CRITICAL NAMING TRAP (real, documented):
  the BOM may call these "AIR HANDLER" units while the plan view labels the
  IDENTICAL model numbers "FANCOIL UNIT" — they are the SAME equipment
  under two names. There is typically NO separate "air handler" in the
  machinery space; if a read produces "N fancoils PLUS an air handler",
  suspect it double-counted a fancoil under its BOM name. Join by model
  number.** This per-unit identity is what a sizing/volumes reference
  document LACKS (it gives zone names + cooling load, not unit tags).
- **Per-zone refrigerant/water control valve** — each fancoil has a valve
  (often with a ball valve tag) that admits refrigerant/water to that zone;
  the zone thermostat commands it. This is the "decide whether to cool this
  room" control point.
- **Per-cabin thermostat + one master touchscreen** — the cabin thermostats
  are the local zone controls; the master is the system-level control,
  usually in the machinery space near the compressors. On their own control
  bus, separate from the refrigerant/water piping.

**Where to look:** the system-LEVEL schematic (not a sizing/volumes
reference) gives real per-unit identity AND the pipe legend that tells you
the system type. Read the BOM and plan-view labels together, joined by
model number, or you will double-count fancoils (see the naming trap above).

**Loop(s) to follow (CLOSED, and note it's really TWO coupled loops):**
The REFRIGERANT/WATER loop (the cooling delivery): compressor/condensing
unit → supply line → each zone's fancoil (via its control valve) → return
line → back to the compressor. Trace supply and return as two halves of
one loop. Separately, the CONDENSER COOLING loop (usually seawater): raw
water in → through the condenser heat exchanger → overboard — this is what
rejects the heat the refrigerant picked up, and is a distinct line
(different pipe-legend color) from the refrigerant itself. For a VRV/direct-
refrigerant system the "supply/return" is refrigerant gas; for a chilled-
water system it's water — same loop shape, different fluid, per the pipe
legend.

### Cooling Water System (closed machinery/electrical coolant loop)

**Distinct from Raw Water — this is a CLOSED glycol/water loop, not
seawater** — serving power-dense machinery and electronics: motors,
inverters, generators, power-control electronics, battery/energy-storage
cooling. Each major component gets its OWN heat exchanger on this loop.

- **Mirrored redundant circuits** — commonly port/stbd — each fully
  independent.
- **Primary + standby circulation pump PER circuit** — expect a spare
  pump as the normal pattern here, not a redundancy anomaly worth
  flagging.
- **Shared reservoir / fill point.**
- **Coolant-condition sensors** — conductivity and/or salinity, monitoring
  coolant health (contamination, seawater ingress via a failed exchanger).
- **Heat exchangers** — one per major cooled component, not a single
  shared unit.

High-value cross-reference target on any vessel with electric or hybrid
propulsion — this loop touches nearly every major power-electronics
component on such a vessel.

**Loop(s) to follow (CLOSED, and there are usually TWO independent copies
— trace each side separately):** reservoir/fill point → primary
circulation pump → each cooled component's heat exchanger in turn (motor,
inverter, generator, power-control electronics, battery cooling) → return
line → back to the reservoir. Trace the port circuit and the stbd circuit
as two entirely separate loops even though they're mirror images of each
other — don't assume tracing one tells you the other is populated the
same way.

### Ventilation System

- **General interior extraction + supply fans.**
- **Galley extraction** — often with a FIRE-RATED DOOR INTERLOCK on the
  extraction path — a real, deliberate cross-system link to fire safety,
  not incidental.
- **Machinery-space fans** — higher-capacity inlet + outlet PAIR (not
  just one fan) for engine rooms and similar spaces.
- **Battery/energy-storage enclosure ventilation** — DEDICATED, independent
  of general interior ventilation. These compartments need their own
  airflow specifically — don't assume they share a duct run with
  accommodation spaces.
- **Enclosed-space ventilation** — e.g. a tender/vehicle garage — its own
  fan(s), separate from the general system.
- **Fire dampers** — interlocked with fire detection/suppression (another
  real cross-system link).
- **Mist eliminators** on outside-air inlets.

**Path(s) to follow (NOT a loop — two independent one-way paths, don't try
to connect them into a single circuit):** SUPPLY: outside air inlet →
(mist eliminator, if fitted) → fan → the space it serves. EXTRACTION:
the space → fan → (fire damper, if interlocked) → exhaust outlet to
atmosphere. Trace supply and extraction separately for every space —
a galley or machinery space's inlet and outlet are not the same path run
in reverse.

### Deck Drains (passive — not a powered system)

Gravity-fed drain routing from deck-level collection points (cockpit,
lockers, anchor bay, hardware troughs) to thru-hull discharge — no pumps,
sensors, or control panels typically involved. The "components" here are
drain ROUTING PATHS and thru-hull fittings, not equipment to register.
Low priority for node-building; relevant mainly as a thru-hull
cross-reference for other systems.

**Path to follow (OPEN, gravity only, no source equipment):** each deck
collection point → its own drain line → thru-hull discharge. Trace each
collection point's path individually — there's no shared pump or manifold
to anchor the trace from, unlike every powered system above.

### Through-Hull Fittings (cross-reference class, not its own system)

Not a system in its own right — a reference covering every hull
penetration used by EVERY other system: seachests, raw-water intakes,
seawater feeds to consumer systems, overboard discharges (grey/black/
bilge), depth/speed sensors, underwater cameras, galvanic/grounding
plates. Useful whenever another system's schematic references a thru-hull
fitting by number without giving its type/size/valve arrangement — this
document class typically has that detail, cross-referenced by fitting
number.

**Role in loop-following (not a loop of its own):** every OTHER system's
loop that crosses the hull boundary passes through an entry here — when a
loop you're tracing terminates at (or originates from) a thru-hull
fitting, that fitting's entry in this document class is where you confirm
its type/size/valve arrangement, not a new loop to trace independently.

---

*(Extend with further system types as encountered — electrical
distribution, steering gear, generators/gensets, watermaker internal
detail, etc. — same shape: individually-broken-out component roles +
variants + symbol disambiguation + where to look, at the SAME depth for
every entry, not a thin summary for some and a deep one for others. Refine
and correct entries with time; the goal is a fleet-usable baseline from
day one, not a finished document.)*
