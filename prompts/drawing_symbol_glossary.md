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
# Entries marked [STD] are standard drafting conventions already enforced as §6
# device discipline.

## electrical

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
