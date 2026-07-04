# Equipment Ontology — v0.4

*Fleet-general. The frame Engo fills, per vessel, during onboarding — to produce that vessel's Equipment Register. Lives in the shared layer of the system prompt. Living document.*

---

## 1. What this is

This is the **expected-equipment frame** — what a yacht carries, organized on the SFI system backbone, with each item's function and the names engineers actually use for it. Plus the **method for reading a vessel's Drive folder structure** to fill that frame.

It is the curated, explicit, reviewable form of the general "what's on a yacht" knowledge a base AI model holds implicitly. Making it explicit turns unaccountable knowledge into an artifact an engineer can red-pen.

**Operating principle — categories, not specifications.** The ontology works at the level of equipment *categories*. It tells Engo what to *expect* — there will be a steering system, there will be generators, there will be a propulsion motor — so Engo can assemble the vessel's **general arrangement**: the big picture of every system and how they fit together. It deliberately does **not** pre-decide type, make, or model. Engo starts **broad** — building that general arrangement from the ontology and the folder structure — and then goes **deep**, learning each item's type, make, model and behaviour from its manuals and schematics. An entry that says "there is a steering system; it may be mechanical or hydraulic — learn which" is correct. One that says "the steering is hydraulic" is an invention. Name the category; let Engo learn the specifics.

## 2. How it is used

During onboarding, Engo reads the vessel's Drive folder structure and Owner's Manual against this ontology to produce a draft **Equipment Register** — the vessel-specific filled-in version. The ontology does three jobs:

1. **A prior for categorisation** — when Engo reads a folder `420, Propulsion Motor`, the ontology tells it what category to expect.
2. **Gap detection** — if the ontology expects a system the vessel's folders don't show, Engo flags it.
3. **A folder-reading method** — Section 3 tells Engo how to extract equipment identity from folder names.

The ontology is fleet-general and never vessel-specific. "Gelliceaux's generators are Cummins" is a Register entry; the Ontology only says "a yacht has generators." Gelliceaux is used throughout as the *worked example*, marked in italics.

**Engineer in the loop.** The Register the process produces is a **confidence-tiered draft**. Engo presents it to the vessel's engineer, who guides Engo on any missing items, confirms the list, and supplies corrections. The Register is not authoritative until the engineer has reviewed it. The confidence tiers (Confirmed / Flagged / Gap) are specified in Onboarding Protocol Step 2.

---

## 3. Reading the folder structure

A vessel's Drive encodes most of its equipment identity in folder *names* and *nesting*. Engo extracts it as follows.

### 3.1 Two parallel indices

A vessel typically keeps two views of the same equipment:

- **The systems tree** — `SWS 108-01 / 400, Propulsion and Machinery / 420, Propulsion Motor / …` — organised by SFI system. Gives system placement and the SFI code.
- **The Suppliers folder** — a flat list of vendor folders, each named `Maker (Function)`. The more complete inventory and the better source for *what exists*.

The same equipment usually appears in both. The register-build reconciles them: the **Suppliers folder for the master list**, the **systems tree for system placement and SFI code**. Equipment in one but not the other is a flag for the engineer.

### 3.2 Parsing a folder name

Equipment folder names follow a consistent pattern — `Maker (Function) [SFI]`:

> `Hundested (CPP Sterngear) [430]` → maker = Hundested, function = CPP sterngear, SFI = 430

Three fields, any of which may be absent:

- **Maker** → the Register's make field, and the contractor/support network.
- **(Function)** → matches an ontology equipment category.
- **[SFI]** → system placement; cross-links the Suppliers folder to the systems tree.

Some folders name the **product directly** — `GPM-12 drive motor`, `Modular Propulsion Control System (MPCS)`, `Akasol ESS`. Treat the product name as the model field.

### 3.3 Acronym harvesting

Folder names routinely expand acronyms — `Modular Propulsion Control System (MPCS)`, `Inverter (BEL)`, `System Control Unit (SCU3)`. Every `Full Name (ACRONYM)` pattern is a glossary entry. Harvest them all into the vessel's glossary and nickname set: the folder tree is, among other things, a glossary, and this directly attacks the cross-vocabulary retrieval gap.

### 3.4 Document-type subfolders

Within an equipment folder, expect a consistent set of subfolders: `Manuals`, `Schematics`, `Spares`, `Inventory`, `Information`. These route documents by type at ingestion — and tell the vision pipeline exactly where the schematics are.

### 3.5 Not every folder is equipment

Some folders are operational or documentary, not equipment, and must not become Register entries:

- Job/works plans — e.g. `works and plans Winter -2026`
- Service campaigns — e.g. `Generators 2000hrs service`
- Documentation groups — the `001 General Condition` group (specification, drawings, class, owner's manuals, handover notes)
- Generic containers — `Drawings`, `Inventory and consumables`

These feed the document spine and the job log, not the equipment register.

---

## 4. What folder-reading will not do — the review gate

Folder-derived equipment knowledge is a strong *draft*, never ground truth. Two kinds of issue must be caught by the engineer.

### Folder-structure realities Engo must interpret, not assume

**The same equipment — or the same word — appearing in more than one place.** Three explanations; Engo must determine which, never assume error:

1. **Genuine duplication or mis-filing** — a folder in the wrong place. Flag for the engineer.
2. **One piece of multi-function equipment**, legitimately filed under each function it serves. Example: the drive motor appears under both `420 Propulsion Motor` and `610 Power generation` — it drives the propeller *and*, in regeneration, generates power. One motor, two roles, two correct placements. Engo should register multi-function equipment as a single item with multiple functions, not as a duplicate.
3. **Genuinely distinct systems that share a word.** Example: `520 Bilge and fire`, `560 Fire suppression`, and `695 Fire system` all contain "fire" but are three different systems (see §5). A shared word is not a fragmented system.

Other realities: equipment is **indexed in both** the systems tree and the Suppliers folder — expected, deduplicate. **SFI tagging is inconsistent** — some folders carry `[430]`, some don't.

### Unverified assumptions in the ontology itself

This frame is a draft too, and its own entries can carry assumptions. Worked example, in three steps: v0.2 of this document asserted a sailing yacht's steering was "hydraulic" — an invention from general "big yacht" knowledge. v0.3 over-corrected to "most sailing yachts steer mechanically" — better, but still pre-deciding the type. v0.4 lands on the principle: the ontology names the *category* (there is a steering system) and the possible *types* (mechanical or hydraulic), and Engo *learns* which from the vessel's documents. An ontology entry is a proposal, never a vessel fact — and even a correction can overshoot.

Engo flags both kinds of issue; the engineer adjudicates.

---

## 5. The SFI system map

The structure follows the SFI major-group backbone, broadly standard across builders. The sub-codes shown are Gelliceaux's (Southern Wind) scheme as the worked example; for another builder the sub-codes get reconciled from that vessel's own folder names. Coverage is deliberately uneven. Per the operating principle, entries name categories and list possible types — Engo learns the actual type, make and model from the documents.

### 001 — General Condition *(documentation, not equipment)*

Vessel documentation: weight & stability, specification, drawings, class & compliance, acceptance trials, owner's manuals, handover notes. The register-build treats this as the **document spine** — the Owner's Manual lives here and is the equipment cross-check — not as equipment.

### 100 — Structure, Rudder and Keel

- **Hull & structure** — the hull, bulkheads and structural members. A system, mostly structural rather than serviceable equipment. *Folder:* hull and structural drawings.
- **Keel** — ballast and righting moment. May be fixed, lifting, or canting; a lifting keel raises and lowers to change draft and has its own actuation and control system. *Nicknames:* the keel, lifting keel, the bulb. *(Gelliceaux: lifting keel, maker APM — type of actuation to be learned from the documents.)*
- **Rudder & bearings** — the steering surface and its bearings. *Nicknames:* rudder, the blade.
- **Steering system** — every yacht has one; it links the helm to the rudder. The **type varies and must be learned, not assumed**: it may be **mechanical** (wheel driving the rudder quadrant via pulleys/sheaves and steering lines — modern boats using Dyneema) or **hydraulic** (common on motor yachts, found on some sailing yachts). Engo registers that a steering system exists, then learns its type from the documents. Filed under the 100-series here, not under propulsion. *Nicknames:* steering, steering gear, the quadrant. *(Gelliceaux: mechanical — quadrant, pulley system, Dyneema steering lines.)*

### 200 — Deck

- **Deck winches & deck gear** — sail-handling and utility winches. *Nicknames:* winches, primaries, grinders. *(Gelliceaux: Harken.)*
- **Hatches, windows, portlights** — *Nicknames:* hatches, ports. *(Gelliceaux: Viraver windows, Hybrid Composites deck hatches.)*
- **Anchor, windlass & ground tackle** — anchor, chain, and the windlass that hauls them. *Nicknames:* windlass, the hook, ground tackle. *(Gelliceaux: Lofrans windlass, Manson anchor, Ketten Walder chain.)*
- **Gangway / passerelle, swim ladder, transom** — boarding and transom equipment.
- **Tender launch / handling** — lazarette and tender-launch gear.

### 300 — Interiors *(lighter coverage)*

General construction, finishes, upholstery, heads, galley appliances *(Gelliceaux: Miele)*, interior lighting, general arrangement, acoustic performance. Engineering-relevant items here are mainly galley appliances and heads.

### 400 — Propulsion & Machinery spaces

- **Engine room & technical room** — the machinery space itself, including vibration control / engine mounts. *Nicknames:* ER, the engine room, tech space. *(Gelliceaux: Vulkan vibration control.)*
- **Propulsion motor** — the prime mover. May be a conventional diesel main engine or an electric traction motor (hybrid/electric). *Nicknames:* the main, mains, engine, motor, donkey, traction motor, drive motor, prop motor. **Register caution:** capture the exact model and whether it is geared or direct-drive, oil-lubricated or oil-less — this determines applicable maintenance. **Multi-function note:** on a hybrid the drive motor also generates power in regeneration — expect it to appear under both propulsion (420) and power generation (610). *(Gelliceaux: BAE GPM-12 — direct-drive, gearless, oil-less.)*
- **Gearbox / transmission** — couples a conventional engine to the shaft, providing reduction and clutching. Absent on direct-drive electric motors. *Nicknames:* gearbox, gear, the box, transmission, GB. *(Gelliceaux: none — the GPM-12 is direct-drive.)*
- **Variable pitch control / CPP** — a controllable-pitch propeller and its control system. *Nicknames:* CPP, the pitch, variable pitch, VP box; also the maker name used generically — e.g. "Hundested," a dominant variable-pitch supplier. *(Gelliceaux: Hundested CPP sterngear.)*
- **Exhaust system** — engine and generator exhaust routing. *Nicknames:* exhaust, wet exhaust.
- **Thrusters** — bow and stern manoeuvring units; electric or hydraulic — learn which. *Nicknames:* bow thruster, stern thruster. *(Gelliceaux: OMS, bow and stern.)*
- **Shaft line & seal** — the propeller shaft and its bearings. The shaft line itself usually carries little documentation; the **shaft seal** is the serviceable item and the one that gets replaced. *Nicknames:* shaft, propshaft. *(Gelliceaux: Wartsila shaft seal.)*

### 500 — Systems *(fluid, climate and services)*

- **Fresh water** — potable water storage, pumps, watermaker, purification. *Nicknames:* fresh water, the watermaker, RO. *(Gelliceaux: EcoSistems watermaker, HEM purification.)*
- **Raw water / seawater** — seawater intake, strainers, heat exchangers, seawater cooling pumps. *Nicknames:* raw water, seawater system. *(Gelliceaux: Funke and Bowman heat exchangers, Grundfos and Calpeda seawater pumps.)*
- **Cooling system** — engine/genset/hybrid cooling loops, glycol circuits and pumps, heat exchangers. *Nicknames:* the cooling loop, glycol system. *(Gelliceaux: EMP glycol pumps.)*
- **Bilge & fire system** — a firefighting and dewatering system built around pumps. The **firefighting** side draws seawater to fire hydrants for fighting a fire; the **bilge** side pumps bilge water overboard. Sometimes a single pump serves both; sometimes a dedicated pump for each. The firefighting capability is a **critical system**. *Nicknames:* bilge, fire pump, hydrants. *(Gelliceaux: a separate pump for each function; Aussie Pumps diesel fire pump on the firefighting side.)*
- **Fire suppression** — fixed fire suppression for the machinery space: a large tank of suppressant (FM200 or a similar agent) that floods the engine room if it catches fire, together with engine-room vent shutters/dampers that close to starve the fire of air. A **critical system**, distinct from the bilge & fire system and from fire detection. *Nicknames:* the suppression system, FM200, vent shutters. *(Gelliceaux: Sea-Fire.)*
- **Fuel & oil** — fuel tanks, transfer, filtration; oil transfer. *Nicknames:* fuel system, day tank. *(Gelliceaux: Racor fuel filters, Reverso oil transfer pump.)*
- **Grey & black water** — waste-water collection, treatment, discharge. *Nicknames:* grey/black water, holding tanks. *(Gelliceaux: Wave International greywater treatment, Planus waterlift.)*
- **Power hydraulic system** — hydraulic power for ship services; distinct from the sailing hydraulics (800-series). **A hydraulic system is always PLC-controlled — capture the PLC and, critically, its control logic.** The PLC hardware is commonly Wago I/O modules, but varies by vessel; the logic is vessel-specific configuration and is in no equipment manual. *Nicknames:* the hydraulics, power pack, PTO, power take-off, AC/DC hydraulic pump.
- **Pneumatic system** — compressed-air system. *Nicknames:* pneumatics, air system.
- **Refrigeration / aircon / ventilation** — *Nicknames:* the reefer, AC, vents. *(Gelliceaux: Frigomar refrigeration, Termodinamica aircon.)*
- **Tankage** — integral tanks, through-hull fittings, tank breathers, deck drains.

> **Fire is three distinct systems**, not one — two firefighting (Bilge & fire, Fire suppression, above) and one detection (Fire detection & monitoring, under 600). Engo must not collapse them just because the folders share the word "fire."

### 600 — Electric Systems

- **Power generation** — diesel gensets and chargers; on a hybrid, also charging propulsion-side batteries, and a regenerating drive motor may feed in here too. *Nicknames:* generator, gen, genny, genset. *(Gelliceaux: Cummins.)*
- **AC & DC distribution** — distributes electrical power around the vessel via AC and DC boards/panels. On a **conventional** vessel this is simply AC and DC distribution. A **hybrid** additionally has a high-voltage side (HV alongside LV). *Nicknames:* AC board, DC board, the boards, AC/DC distribution; boards are often named by location — aft AC, aft DC, fwd AC, fwd DC.
- **Power conversion (hybrid)** — converts and manages power between batteries, generators and the traction motor. *(Gelliceaux: the BAE stack — MPCS (Modular Propulsion Control System), MAPS (Modular Accessory Power System), BEL (an inverter), SCU3 (System Control Unit), EDN-S.)* **Note:** harvest these acronym expansions into the glossary.
- **Hybrid propulsion system (whole)** — the hybrid system as an integrated whole, with its own operations, mapping, schematics and investigation records. *(Gelliceaux: the BAE System folder, including the "Investigation of Errors" sub-folder.)*
- **Energy storage** — a vessel typically carries **multiple distinct battery banks**, each serving a duty, often at different voltages — commonly an engine/generator starter bank, an auxiliary/house bank, an emergency bank, and a GMDSS bank. A **hybrid** adds propulsion-capable energy storage. *Nicknames:* the batteries, the banks, the pack, ESS, traction battery. *(Gelliceaux: separate auxiliary, emergency, GMDSS and generator-starter banks, plus the Akasol ESS serving hotel and auxiliary loads; multiple banks at different voltages. Conventional banks: Mastervolt.)*
- **Monitoring & control** — vessel-wide monitoring; a vessel may run several monitoring subsystems. *Nicknames:* monitoring, the alarms. *(Gelliceaux: three — BAE monitoring, ONYX monitoring, MYT hydraulic monitoring.)*
- **Shore power converter** — dockside supply conversion. *Nicknames:* shore power, the shore lead. *(Gelliceaux: EDN-S.)*
- **Earthing, cathodic protection & anodes** — protects immersed metal from galvanic corrosion. **And, separately, lightning protection** — a distinct system, commonly filed alongside. Keep the two distinct. *Nicknames:* anodes, CP, hull protection / lightning protection. *(Gelliceaux: Tecnoseal hull protection, Dinnteco-Elna lightning.)*
- **Electrical wiring & routing** — cabling, trunking, and per-subsystem electrical design documents.
- **Lights, switches & sockets** — navigation, interior and exterior lighting. *(Gelliceaux: Barthelme LED.)*
- **Fire detection & monitoring** — vessel-wide fire and smoke detection, alarm and monitoring — the third of the three fire systems. This group may also hold dedicated suppression for battery (Li-Ion) spaces, a different hazard from the engine-room suppression. *Nicknames:* fire detection, fire monitoring, the fire panel. *(Gelliceaux: Marinelec detection; FirePro Li-Ion suppression for battery spaces.)*

### 700 — Navigation, Communication, Entertainment

- **Navigation & helm stations** — instruments, chartplotter, autopilot. *Nicknames:* nav, the plotter, the pilot. *(Gelliceaux: Furuno navigation, MARSILI autopilot.)*
- **Communication & networking** — satellite, VHF, onboard networking. *Nicknames:* comms.
- **Entertainment** — audio and AV. *(Gelliceaux: Sonance sound, Future Automation TV systems.)*

### 800 — Rigging and Sailing

- **Mast** — the spar. *Nicknames:* the rig, the mast, the stick. *(Gelliceaux: Hall Spars.)*
- **Boom** — *Nicknames:* the boom.
- **Standing rigging** — the fixed rigging supporting the mast.
- **Sailing hydraulic system** — hydraulic cylinders and manifolds driving sailing functions; distinct from the ship's power-hydraulic system. As with all hydraulic systems, **PLC-controlled — capture the PLC and its logic**. *Nicknames:* sailing hydraulics, the rams. *(Gelliceaux: Cariboni cylinders, Danfoss.)*
- **Running rigging** — the moving lines controlling the sails. *Nicknames:* running rigging, the lines.
- **Furlers** — sail furling systems. *(Gelliceaux: Bamar.)*
- **Sails** — *Nicknames:* the sails, main, jib, genoa, staysail. *(Gelliceaux: Doyle.)*

### 900 — Miscellaneous

- **Safety equipment** — life raft, EPIRB, PLB, life jackets, EEBD. *(Gelliceaux: Survitec life raft, Ocean Signal PLB.)*
- **Tender & tender handling** — the tender and its launch/haul gear. *(Gelliceaux: H+B Technics tender haul winch.)*
- **Dive** — dive compressor and equipment. *(Gelliceaux: Bauer compressor.)*
- **Tools, spare parts, medical, watersports** — lighter coverage.

---

## 6. Cross-cutting equipment classes

Some equipment recurs across many systems and is best tracked as a class as well as per-system:

- **Pumps** — seawater, freshwater, bilge, fire, fuel, oil-transfer, glycol. A vessel carries many, from many makers; the register should be able to answer "every pump aboard" as a view.
- **Heat exchangers / coolers** — across raw-water, cooling and HVAC systems.
- **Sensors** — tank level, raw-water, gas/HF detection. Often a dedicated supplier folder.
- **Hydraulic actuators** — cylinders and rams across sailing, keel and passerelle.
- **Control PLCs** — hydraulic and other automated systems are PLC-driven. The PLC hardware (often Wago I/O modules, but varies) and especially its **control logic** are part of the equipment and must be captured — the logic is vessel-specific configuration and appears in no equipment manual.
- **Multi-function equipment** — items that serve more than one system (e.g. a hybrid drive motor doing propulsion and regeneration). Register once, with all functions noted; do not duplicate.

---

## 7. Nickname index

Quick reference for resolving casual engineer vocabulary to canonical equipment. Per-vessel nicknames and acronym expansions (harvested per §3.3) are added to the Register during onboarding.

| Nickname(s) | Canonical equipment |
|---|---|
| main, the main, mains, engine, motor, donkey, traction motor, drive motor, prop motor | Propulsion motor |
| gearbox, gear, the box, transmission, GB | Gearbox / transmission |
| prop, propshaft, shaft, VP box, variable pitch, CPP, "Hundested" | Variable pitch control / CPP |
| bow thruster, stern thruster, thrusters | Thrusters |
| generator, gen, genny, genset, the gennies | Power generation / generators |
| AC board, DC board, the boards, aft AC, aft DC, fwd AC, fwd DC | AC & DC distribution |
| the batteries, the banks, the pack, ESS, traction battery | Energy storage |
| MPCS, BEL, SCU, the converters | Power conversion (hybrid) |
| the keel, lifting keel, the bulb | Keel |
| steering, steering gear, the quadrant | Steering system |
| the rig, the mast, the stick | Mast |
| the hydraulics, power pack, PTO, power take-off, AC/DC hydraulic pump | Power hydraulic system |
| the watermaker, RO, desal | Fresh water / watermaker |
| anodes, CP, hull protection | Cathodic protection |
| AC, air con, HVAC | Aircon |
| the windlass, the hook, ground tackle | Anchor & windlass |
| fire pump, hydrants | Bilge & fire system |
| FM200, vent shutters, the suppression system | Fire suppression |
| fire detection, fire monitoring, the fire panel | Fire detection & monitoring |

---

## 8. How this document grows

- **Coverage is deliberately uneven.** Engineering-critical groups (100 keel/steering, 400, 500, 600, 800) are detailed; interiors and miscellaneous are lighter. Grow the light sections as vessels need them.
- **The SFI sub-codes are one builder's scheme.** The major groups are broadly standard; the 3-digit sub-codes get reconciled from each vessel's own folder names.
- **Every onboarding extends this.** When a vessel has an equipment class not in the ontology, add it.
- This is a draft and needs an engineer's red pen. Per the operating principle: every entry is a *category proposal*, never a vessel fact. Engo learns the type, make and model from the documents.

## 9. Changes from v0.3

- **Added the operating principle** (§1): the ontology names equipment *categories*, not specifications; Engo starts broad (general arrangement) then goes deep (learns type/make/model from documents). It must not bias toward a type.
- **Steering** re-neutralised: no longer "mechanically steered" — the entry names the category and both possible types (mechanical / hydraulic) and instructs Engo to learn which.
- **§4 reworked** — "same equipment in two places" now has three explanations: duplication, multi-function equipment (drive motor = propulsion + regen), and distinct systems sharing a word (fire). The ontology-assumption worked example now shows the full v0.2→v0.3→v0.4 arc, including that a correction can overshoot.
- **Fire** corrected from "one system fragmented across codes" to **three distinct systems**: Bilge & fire (520, firefighting seawater pump + bilge), Fire suppression (560, FM200-type engine-room flooding + vent shutters), Fire detection & monitoring (695). Two are critical firefighting systems; one is detection.
- **Multi-function equipment** added as a cross-cutting class; the propulsion-motor entry notes its regeneration role.
