# DRAWING SYMBOL GLOSSARY — fleet-general, cross-vessel
#
# Purpose: the §6 cross-discipline symbol→device-type glossary. Injected into
# extraction prompts so the reader starts from marine-drafting conventions instead
# of guessing. FLEET-GENERAL ONLY — no vessel-specific equipment, names, or system
# routing in this file (vessel facts live in the vessel layer). A sheet's OWN
# legend, read by the legends-first pass, always OVERRIDES this glossary.
#
# Provenance: entries marked [ENG] were confirmed by the engineer during the GM
# electrical red-pen review (batch 1, 2026-07-10, recorded in
# data/state/redpen_electrical_batch1_raw_20260710.txt + flagged_propagation_20260710.json).
# Entries marked [ENG-SB] come from the SYMBOL-BANK red-pen (2026-07-28,
# data/state/redpen_symbol_bank_gm_20260728.txt): 133 of 136 unique repeated
# shapes in the GM book typed by the engineer, covering 96% of the book's
# symbol instances. Entries marked [STD] are standard drafting conventions
# already enforced as §6 device discipline.
#
# ─────────────────────────────────────────────────────────────────────────────
# HOW A SYMBOL IS TYPED — read in this order, first match wins:
#   1. the sheet's OWN legend (legends-first pass)      — always overrides
#   2. the confirmed SYMBOL BANK for this drafting house — shape fingerprint
#      → engineer-confirmed type (data/state/symbol_bank_<house>_CONFIRMED.json)
#   3. this glossary's shape and id-prefix rules
#   4. <UNKNOWN> — never guess
# ─────────────────────────────────────────────────────────────────────────────

## electrical — SHAPE rules (what the drawing looks like)

- [ENG-SB] **POWER-CONVERSION BLOCK — a rectangle with a DIAGONAL line through
  it and a VOLTAGE printed on EACH side is a power-conversion unit.** Read the
  two voltages to name the class:
    DC in → AC out  = INVERTER          (e.g. 600V DC / 230V AC)
    DC in → DC out  = CONVERTER / DC-DC slicer (e.g. 600V DC / 24V DC)
    AC in → DC out  = BATTERY CHARGER   (e.g. 230V AC / 24V DC)
  It is never a terminal, never a plain load, never annotation. Type it as the
  conversion class and route it to power conversion.
  ⚠ THIS RULE WAS MISSING FROM THE GLOSSARY UNTIL 2026-07-28 AND THE ENGINEER
  HAD TO STATE IT TWICE. Root cause recorded in
  docs/PROTOCOL_electrical_extraction.md §G: his earlier instruction was
  captured only as INSTANCE routing (BEL→629, MAPS→626, chargers→621 in the
  load-map red-pen) and never generalised into a SHAPE rule — the exact
  per-instance-instead-of-per-type failure this whole symbol-bank effort
  exists to end.
- [ENG-SB] **FUSED TERMINAL — a rectangle-with-a-line-inside drawn INSIDE
  another rectangle is a terminal with a built-in fuse.** Distinct from a plain
  terminal (empty rectangle) and from an inline fuse (rectangle on a
  conductor). Terminal strips routinely mix fused and unfused terminals in one
  strip — type each terminal individually, never by strip.
- [ENG-SB] **TERMINAL STRIP — "T/S <letter>" names the strip; each numbered
  rectangle is one terminal and the number inside is that terminal's label.**
  Record strip and terminal separately (T/S E terminal 84), never as one blob.
- [ENG-SB] **GANGED BREAKERS — two breaker symbols joined by a mechanical link
  are ganged: if one trips the other trips with it** (2 phases, or + and −).
  They may carry two labels (Q12 16A + Q13 16A) or one label for the pair
  (Q1 32A). Record the gang relationship — it is a protection fact.
- [ENG-SB] **THE DOT RULE (topology-critical) — a solid dot where a line meets
  a terminal, a component or another line is a REAL ELECTRICAL CONNECTION at
  that point. No dot = the line passes by/through WITHOUT connecting.** Two
  terminals crossed by one line, with a dot in only the lower one, means the
  line connects to the lower terminal only. This governs net building: an
  extractor that ignores dots will invent connections that do not exist.
- [ENG-SB] **CABLE-CORE NUMBERING — a number INSIDE a terminal rectangle is the
  terminal's own label; a number OUTSIDE it is the CORE NUMBER within a
  multi-core cable.** Both must be captured; they answer different questions
  (which terminal vs which wire in which cable).
- [ENG-SB] **TWISTED SHIELDED PAIR / CABLE GROUP — crossed lines (an X) between
  two conductors mark them as a TWISTED PAIR; a vertical line carrying solid
  dots across several conductors is the common SHIELD / DRAIN wire; a heavy bar
  terminating those lines is a SHIELD GROUND / chassis-earth termination.**
  Naming convention: `<cable>P<n>` = Pair n, `<cable>R<n>` = its Return. These
  are CABLE STRUCTURE, not devices — but they are facts about the conductor
  (shielded, twisted, which cable group) and belong on the wire, not discarded.
- [ENG-SB] **PLUG / CONNECTOR — a large rectangle is the PLUG; the bold text
  names what the plug serves (e.g. MPCS-S, ECP1); each small rectangle with a
  triangle beside it inside that plug is ONE PIN, and the text inside the
  rectangle is the cable core landing on that pin.** Pins attach to their
  plug's owner — a pin is never an equipment node of its own.
- [ENG-SB] **NEGATIVE-BUS MARK — the bus symbol on a terminal's side means that
  terminal connects to the NEGATIVE BUS BAR.** Negative/return paths are part
  of the circuit loop and must be traced, not dropped as "not power".
- [ENG-SB] **OVERCURRENT/UNDERCURRENT RELAY — a rectangle enclosing an `I > <`
  symbol is a current-monitoring / over- and under-current protection relay.**
- [ENG-SB] **HV CONTACTOR — carries BOTH NO and NC contact sets on one device**
  (typically NO group above, NC group below). Record which side a circuit uses.
- [ENG-SB] **RELAY POSITIVE-SIDE RULE — the positive side of a relay can feed
  BOTH the coil (activation) and the switched function.** A power-path trace
  that assumes coil and load supplies are separate will mis-read the circuit.
- [ENG-SB] **PIGGY-BACKED TERMINALS — a terminal may take its supply from its
  neighbour and pass it onward to a different cable core** (e.g. 58 shares 57's
  source and feeds core 7; 60 piggybacks 59 and feeds core 8). Supply lineage
  is per-terminal, not per-strip.

## electrical — MONITORING / CONTROL INTERFACE

- [ENG-SB] **THE XA ARROW-DIRECTION RULE — an arrow-shaped tag block labelled
  `XA<strip> <terminal>` is the interface to the monitoring & control system
  (on this vessel, ONYX). `XA50` is the terminal strip; the arrow-shaped
  rectangle is the terminal. THE ARROW DIRECTION CARRIES THE SEMANTICS:**
    arrow pointing AWAY from the electrical system  →  the monitoring system
        MEASURES a signal FROM the circuit  =  STATUS / INDICATION
    arrow pointing TOWARD the electrical system     →  the monitoring system
        SENDS a signal INTO the circuit     =  CONTROL / COMMAND
  This is the CONTROL ≠ INDICATOR ≠ SUPPLY distinction drawn geometrically.
  Read the arrow before typing: an indication tap routed as a control is a
  wrong relationship, not a wrong label. Never type these as annotation and
  never drop them because "the wire goes elsewhere".
- [ENG-SB] **CURRENT TRANSMITTER — measures the current in a line and TRANSMITS
  the measurement to the monitoring/control system.** (The engineer's term;
  "CT / current transformer" appears on some sheets for the same function —
  the FUNCTION is what routes: a measurement device reporting to monitoring,
  cross-linked to the line it measures. Not a load, not a power tap.)
- [ENG-SB] **AMP GAUGE — sits IN LINE with the supply/consumer and displays the
  current flowing through it.** A gauge is an instrument, not a load.
- [ENG-SB] **PHASE-INDICATOR LAMP — lit = live between that phase and neutral**
  (shore-power phase indication). Indicator, never a control.

## electrical — DEVICE CLASSES seen in the GM book

- [ENG-SB] BILGE LEVEL SENSOR / bilge switch — water contact closes the circuit
  or sends a signal, raising the bilge alarm.
- [ENG-SB] TANK LEVEL SENDER — level sender fitted in every tank.
- [ENG-SB] ALARM BUZZER — audible annunciator driven when an alarm is raised.
- [ENG-SB] SOLENOID VALVE — incl. pneumatic solenoid valves.
- [ENG-SB] MOTORISED VALVE — a motor that opens and closes a valve. The motor
  is the actuator; the VALVE is the equipment (equipment ≠ actuator).
- [ENG-SB] MOTOR variants: a DC motor is fed by a positive line with the
  negative-bus mark on its return; an AC motor shows L and N plus a grounding
  line to the earth bar. Record which — it identifies the supply system.
- [ENG-SB] EMERGENCY STOP BUTTON — e.g. the hybrid-system emergency stop.
- [ENG-SB] THROTTLE — propulsion control input.
- [ENG-SB] RELAY WITH LIGHT INDICATION — relay carrying an integral indicator.
- [ENG-SB] GREY-WATER TRANSFER BOX — a box containing a level switch and a
  pump: when the box fills, the level switch starts the pump and transfers to
  the grey-water tank. (An assembly: box + switch + pump, one equipment node
  with its internal devices as facts.)
- [ENG-SB] LIGHTING-MODULE TERMINALS — terminals of a lighting PLC module: the
  − side goes to the negative bus, the + side feeds the terminals that switch
  individual light circuits.

## drawing furniture — MUST BE READ, NOT DISCARDED

- [ENG-SB] **TITLE BLOCK / SHEET DESCRIPTION — the table at the bottom of every
  sheet carrying drawing number, title, drafting company, project and customer
  IS PAGE IDENTIFICATION AND MUST BE READ AND RECORDED PER PAGE.** It is not a
  device and not noise: it tells the sweep which sheet it is looking at and how
  to read it. (Note: the symbol-bank builder deliberately EXCLUDES title-block
  shapes from the device bank — that exclusion is about not typing furniture as
  equipment, and does not license skipping the block's TEXT.)
- [ENG-SB] **INDEX PAGE — identify it as the index and treat it as the
  drawing→system ROUTER** (§9b), not as a schematic to extract devices from.

## electrical — ID-PREFIX and legacy rules

- [ENG] A DIAMOND enclosing a number, sitting ON a wire, is a WIRE-GAUGE CALLOUT —
  the number is the conductor cross-section in mm². It is an ANNOTATION, not a
  device, not a terminal, and NOT a status signal. This holds however the callout
  is labelled: a bare number, or a "junction/tap N", or "N — to <somewhere>",
  drawn in a diamond on a conductor, is the same wire-gauge annotation.
- [ENG] A group of conductors — one HI, one LO, and a SHIELD — twisted together is
  a CAN BUS (twisted shielded pair). Any conductor labelled …HI / …LO with an
  associated shield tap is a CAN-bus conductor: a signal bus, not a power line.
  Type the shield tap and the HI/LO lines as status_signal (CAN), never power.
- [ENG] HVIL = HIGH-VOLTAGE INTERLOCK LOOP — a safety signal on high-voltage
  connectors: if a plug is not fully mated the loop opens and the HV system shuts
  down. "HVIL", "HVIL IN", "HVIL OUT" are interlock signals (status_signal), not
  power and not a manual switch.
- [ENG] A block labelled "SWITCH" (e.g. SWITCH PORT / SWITCH STBD) on a
  high-voltage or motor feed that carries MANY PINS and mates to external wiring
  is a multi-pin HARNESS CONNECTOR / plug interface — the physical junction
  between an external control system and internal motor/sensor wiring. It is NOT a
  mechanical toggle and NOT a network switch. Type it as a connector/plug, not a
  switch. (This is the plug-mistaken-for-a-switch trap.)
- [ENG] A FUSE is drawn as a rectangle with a single line through it, placed inline
  in a conductor; id prefix F (F3, F4…). Distinguish from a breaker; never type a
  fuse as a status signal just because a monitoring tap sits near it.
- [ENG] A label naming a power unit or bus (a battery/energy-storage bank, a
  power-conversion/control unit, a HV/LV distribution bus) sitting on a HEAVY
  conductor is a POWER connection to that unit — trace the loop supply→return,
  don't type it status_signal just because the label is short. "follow that loop."
- [ENG] A block that routes between alternative SUPPLIES (shore / auxiliary /
  emergency, or which of two controllers drives a load) is a SOURCE SELECTOR — a
  control, not a status signal.
- [ENG] ID prefix "Re" (Re1, Re aux2, Re6…) = RELAY, always.
- [ENG] The relay SYMBOL: a small rectangle with a dash through the middle and a
  dotted line above it. Dotted linkage lines tie a relay coil to the contacts it
  drives elsewhere on the sheet.
- [ENG] ID prefix "K" (K1…K5) with a multi-pole contact group = CONTACTOR — a
  coil-driven power-switching device connecting/disconnecting a source to a bus.
  Not a manual switch.
- [ENG] A device labelled "ISOLATOR" with an ampere rating (e.g. "S1 25A ISOLATOR")
  = BREAKER (isolator breaker), even when its ID prefix is S.
- [STD/ENG] ID prefix "Q" = breaker; "QE" = emergency breaker [ENG-confirmed];
  "F" = fuse; "CB" = circuit breaker; "SW" = switch.
- [ENG] "CT" (CT1, CT2…) = CURRENT TRANSFORMER — a monitoring device clamped
  around a power line that transmits the measured current to a monitoring/control
  system. Its output line is a signal; the CT itself is a measurement device, not
  a load and not a power tap.
- [ENG] "EARTH LEAKAGE n" = EARTH-LEAK (residual-current) BREAKER — the protective
  device the ground conductors of consumers connect to; trips on leakage current.
  A protective device, not a switch and not a monitor-only element.
- [ENG] "PRESSURE SW" / pressostat = an AUTOMATIC pressure-controlled switch
  (cuts a pump in below a set pressure, out above it). A control device, not a
  manual switch.
- [ENG] A reference like "see DWG 410a" / "→ DWG 102" on a terminal or wire is a
  CROSS-DRAWING POINTER — the circuit continues on that drawing. It is not a
  device; record it as a cross-reference and follow the loop there. ONLY an
  explicit drawing/sheet reference qualifies — a letters+digits tag block on a
  stub wire tapping a circuit toward a monitoring/alarm loom is a STATUS SIGNAL,
  not a pointer, even though its wire leaves the local circuit. AND: when the
  cross-drawing reference sits on an element that CARRIES A WIRE into this
  sheet's circuit (a source/target flag wired to a terminal, a terminal block
  continuing on another sheet), that element STAYS an element — typed by its
  electrical function, with the drawing reference recorded on it — never
  demoted to annotation-only and never dropped. The wire is the test.
- [ENG] A DOTTED/DASHED RECTANGLE enclosing a group of components marks an
  ENCLOSURE BOUNDARY — everything inside lives in one physical box/panel/unit.
  A dotted rectangle is NOT automatically a signal path.
- [ENG] Bus bars labelled L1 / L2 / L3 / N (with a voltage) = POWER SUPPLY BUSES —
  power distribution, not signals.
- [ENG] A text label directly ABOVE a device row describes the device BELOW it
  (e.g. a function caption over a terminal/contact group) — attach the caption to
  that device, don't read it as a separate element.
- [ENG] A selector switch feeding an instrument (e.g. a voltmeter phase selector
  L1-L2 / L2-L3 / L3-L1) is a GAUGE SELECTOR — a display-selection control, not a
  power switch.
- [STD] Numbered junction/tap blocks whose wires collect per-circuit taps and route
  to a central monitoring/alarm system are STATUS SIGNALS, even when drawn as
  terminal blocks.
- [ENG] MULTI-CORE CABLE: a THICK line with multiple thinner NUMBERED legs
  branching on BOTH sides (equal leg count each side) is a multi-core cable
  connecting two Terminal Strips — NOT equipment, NOT a load. The top-middle
  label "MUx-N": MUx = cable id, N = wire count; each leg 1..N lands on a
  terminal; the T/S each side belongs to is named at the TOP of that side's
  terminal column. Variant: a 4-wire cable with no top label where one side
  lands on GAUGES (voltage/current meter) instead of a second T/S. A bare
  wire+terminal reference ("12/69", "119") is a wire number + terminal, not
  equipment; "not used" = spare → skip. (Cable itself = wiring_detail: record
  cable id + the two T/S endpoints, never a node.)
- [ENG] FUSED TERMINAL: a terminal drawn as a rectangle containing an inner
  rectangle with a line across it = a terminal with a BUILT-IN FUSE. Type =
  terminal, but note the inline protection.
- [STD] breaker ≠ fuse ≠ relay ≠ contactor ≠ terminal ≠ switch; signal ≠ power;
  mark ambiguous rather than guess.

## REVISION MARKER (hydraulic/mechanical sheets) — engineer-taught 2026-07-19
A RED WARNING TRIANGLE containing a number is a REVISION MARKER: the element it
sits next to was added or changed in that numbered row of the sheet's revision
table. It is never a component. Cross-read the revision table row to learn what
changed and when — this ties drawn elements to design history.

## FLOW REDUCTOR (hydraulic sheets) — engineer-taught 2026-07-20
The ")(" symbol in a hydraulic line is a FLOW REDUCTOR (restrictor). When it
carries NO number, it needs no fact and no flag — disregard it. Only a numbered
reductor (a set value) is worth recording, inline in the scenario it affects.

## PRESSURE RELIEF VALVE SETTING (hydraulic sheets) — engineer-taught 2026-07-22
A NUMBER inside a SQUARE with an ARROW under the number and a SPRING drawn next
to it = a PRESSURE RELIEF VALVE set to that number, in BAR. Always read it as a
relief setting — never an unknown marking, orifice value, or coil parameter.

## ELECTRICAL SYMBOL TRUTHS — distilled from the engineer's GM-book red-pens
## (general symbol→device rules; no sheet-specific data)

- **FUSE**: a rectangle with a line through it, sitting IN a conductor run. Any
  `F<n>` label on such a symbol is Fuse n.
- **FUSED TERMINAL**: an outer rectangle containing a smaller rectangle crossed
  by a line = a terminal with a built-in replaceable fuse. Type stays terminal;
  the inline protection is what matters for troubleshooting.
- **RELAY**: a rectangle with a dash through the middle and a dotted line above
  it. The dotted line associates the coil with its contacts. The label above the
  coil names the function it activates.
- **WIRE-GAUGE CALLOUT**: a diamond containing a number = conductor size in mm².
  This is an ANNOTATION, never a signal, never a device.
- **ENCLOSURE**: a dotted-line rectangle drawn around a group = those parts live
  in one physical box/unit; the box's name applies to everything inside it.
- **GANGED BREAKER PAIR**: two breaker symbols joined by a dotted line = one
  breaker on the positive and one on the negative of the same circuit,
  mechanically linked — if one trips the other trips.
- **MULTI-CORE CABLE**: a thick line with several thinner NUMBERED legs on BOTH
  sides (equal count each side) = a multi-wire cable joining two terminal
  strips. A top-centre `MUx-N` label gives cable id and wire count; each
  numbered leg is one wire. Read the strip name at the TOP of each side's
  column to know which strips it joins. A variant carries no top label (e.g. a
  4-wire run from a terminal strip to gauges) — same reading.
- **HARNESS CONNECTOR**: a block labelled "SWITCH <side>" (or similar) on an
  interconnect sheet is often a MULTI-PIN WIRE HARNESS CONNECTOR / plug
  interface, not an operator switch — decide from its pin rows, not its word.
- **PLUG PINS**: pins of a plug belong to the equipment the plug mates with —
  follow the conductor to the block whose header names that equipment.
- **HVIL**: high-voltage interlock loop — if a HV plug is not fully mated the
  interlock opens and the system shuts down for safety.
- **CT (current transformer/transmitter)**: measures current in a power line for
  load monitoring/control. It is INSTRUMENTATION on the line it clamps — not an
  equipment node of its own.
- **EARTH-LEAK BREAKER**: the common return/protective point that component
  ground cables land on. Treat as protective infrastructure of its panel.
- **MEASUREMENT INDICATORS** (phase voltage/current, frequency meters, sync
  lamps, run lamps): these INDICATE state; they are facts on the equipment they
  monitor, never equipment nodes themselves.
- **CROSS-DRAWING POINTER**: text naming another drawing ("see dwg <n>") means
  the loop CONTINUES there — record a cross-reference and resolve it when that
  sheet is ingested; never invent the far end.
