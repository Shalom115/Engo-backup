# COMPLIANCE CHECKLIST — binding rules of record

Built 2026-07-28 for the vector-first protocol audit. Every line is a rule the
engineer established, extracted from the project's own record. Each cites its
source. No rule here is new; nothing is paraphrased beyond compression.

Rule IDs are stable — the audit report (`COMPLIANCE_REPORT_vector_first.md`)
verdicts against these IDs.

---

## 1. Master Spec v2 — SCHEMATIC INGESTION (source: CLAUDE.md, "★ SCHEMATIC INGESTION PROTOCOL — MASTER SPEC v2")

| ID | Rule | Source / quote |
|---|---|---|
| MS-0.5-a | DISCOVER structure, don't memorize examples. Gold values are evidence a general rule applied, never targets. | CLAUDE.md §0.5 (v3): "The §10 gold values … are EVIDENCE a GENERAL rule applied correctly to ONE sheet — NOT targets." |
| MS-0.5-b | The extractor is GOLD-BLIND: no Gelliceaux-specific token in extraction code/prompts/config. | §0.5(1): "no Gelliceaux-specific token from §10 in extraction code/prompts/config" |
| MS-0.5-c | Gold values live ONLY in a separate `tests/` harness, used post-hoc. A gold value inside the extraction path = design failure, stop and fix the leak. | §0.5(2) |
| MS-0.5-d | Counts (slices/components) are DISCOVERED, never asserted. N≠gold-N is a result to examine, not a target to force. | §0.5(3) |
| MS-0.5-e | Level-separation and semantic cross-link are RULES, not lookups — never hardcode a zone name. | §0.5(4) |
| MS-0.5-f | PASS = primary structure-discovery report graded on reasoning, THEN secondary gold match. Passing only the secondary by tuning to numbers = overall FAIL. | §0.5 "PASS = two parts in order" |
| MS-2-a | Accept-all → cross-reference → surface anomalies → multi-source vote. Never "schematics lose". | CLAUDE.md §2 |
| MS-2-b | Authority priors: installed→inventory/PMS, wired/plumbed→schematic, location→GA, manual-match→installed model. | §2 |
| MS-3-a | Three text-layer classes (A title-block-only / B BOM-rich / C encoding-corrupted) routed differently; filename ≠ content. | §3 |
| MS-3-b | Revision-supersede to newest; superseded revisions flagged. | §3 |
| MS-3b | Part search CORROBORATES, never ORIGINATES a part number; a hit on a confabulated string launders a hallucination. | CLAUDE.md §3b (GATED) |
| MS-4 | Resolution/crop footprint is the binding constraint; tight crops at high DPI, not full-height slices. | CLAUDE.md §4 RESOLUTION FINDING |
| MS-5 | Cross-drawing key is SEMANTIC (zone/function name), NOT tag numbers. | §5 |
| MS-6 | Device discipline: breaker ≠ fuse ≠ relay ≠ contactor ≠ terminal ≠ switch; signal ≠ power; mark ambiguous, NEVER guess. | §6 "mandatory in vision prompt" |
| MS-9d | Node writer: every fact carries `{value, source_doc, page/sheet, bbox, source_type, authority, confidence, as_of}` — nothing unsourced. | §9d / "Every fact carries" |
| MS-9e | Semantic matcher resolve-first: attach-on-match, create-flagged-on-no-match. Never a silent create. | §9e |
| MS-9g | Manual-coverage check: link a manual only at 100% match, else "MANUAL MISSING". | §9 deliverable (g) |
| MS-9i | Durable corrections log with full provenance for every correction. | §9i (built) |
| MS-10 | Two gold standards validate post-hoc (mast block, bilge node); diff-and-report; do not scale until clean. | §10 |
| MS-12 | Kill dynamic: a USER MESSAGE preempts in-flight runs → short inline batches, engineer HOLDS. | §12 |

## 2. Standing rules (source: CLAUDE.md standing rules + working principles)

| ID | Rule | Source / quote |
|---|---|---|
| STD-1 | RENDER BEFORE DESIGNING — render and visually inspect ≥1 real example (2-3 across layouts) before designing any handler for a document class. | CLAUDE.md "STANDING RULE — RENDER BEFORE DESIGNING (2026-07-01)" |
| STD-2 | Never write "run completed"/"PASSED"/"engineer graded X" without re-reading the actual output and quoting real numbers. | CLAUDE.md "STANDING RULE ADDED" (the fabricated Gold-#2 entry) |
| STD-3 | A validation gate must exercise the REAL dispatcher path, not a shortcut around it. | CLAUDE.md working principles: "does this test the real dispatch path, or a convenient shortcut?" |
| STD-4 | Errors fail loud and clear; no silent fallbacks. | CLAUDE.md working principles |
| STD-5 | Guard every vision-output consumer against non-dict array entries (schema is a request, not a guarantee). | PROTOCOL_electrical_extraction.md §F |
| STD-6 | "Clean" means verified, not "didn't crash"; a lost item is dispositioned by RENDERING the region, never from labels. | PROTOCOL §F |
| STD-7 | Long runs are kill-safe: append-only ledger, resumable. | CLAUDE.md ingest lesson (2026-06-09) |

## 3. Identity, routing and node rules

| ID | Rule | Source / quote |
|---|---|---|
| ID-GATE | HARD BLOCK: no node writer ships without resolve-first identity resolution against the existing Register. | CLAUDE.md "★ IDENTITY-RESOLUTION GATE (§1/§5a) — HARD BLOCK on node-writing" |
| REV-GATE | Facts from a superseded drawing id are refused outright. | PROTOCOL §C "Revision gate"; CLAUDE.md revision-gate entry |
| ROUTE-1 | FEEDER ≠ LOAD: a schedule row may feed a sub-distribution box, not an equipment. Validate breaker-by-breaker; feeder rows → panel card + cross-links. | CLAUDE.md "TWO GENERAL ROUTING RULES (engineer 2026-07-04)" (1) |
| ROUTE-2 | CONTROL ≠ INDICATOR ≠ SUPPLY: every panel element is one of the three; ingesting indication as control is a wrong relationship. | Same entry (2) |
| ROUTE-3 | Source-type gate: the hydraulic control map applies ONLY to `source_type ∈ {schematic, hydraulic_schematic}`. | PROTOCOL §C |
| ROUTE-4 | Structural elements (terminal/relay/controller/plug pin) are NOT routed as loads; `not_routed` is surfaced, never silently dropped. | PROTOCOL §C |
| CASE-AB | Case A (identity conflict) → always defer to the confirmation list. Case B (equipment-pattern inference) → may act only if the convention is already recorded, each piece has its own model+function reference, and acting only SPLITS an under-differentiated node. | CLAUDE.md "CASE A vs CASE B" |
| EQ-ACT | Equipment ≠ actuator: the actuator is not the equipment it moves; separate nodes joined by `actuates →`. | CLAUDE.md Decision 6 "EQUIPMENT-NOT-ACTUATOR" |
| PER-INST | Per-installation nodes where a section holds multiple physical instances (fault isolation). | CLAUDE.md Decision 3; PROTOCOL §E |
| SFI-OCC | Check yard-tree + Register occupancy BEFORE assigning a logical SFI; yard has priority. | CLAUDE.md item (6) "651 mistake"; PROTOCOL §E R1 |
| FLAG-NG | Flag, never guess: no/weak/ambiguous match → create_flagged, a SURFACED finding. | CLAUDE.md §9e; PROTOCOL §E R3 |
| PROV | Provenance mandatory on every fact, incl. exact bbox — the jump-to-and-mark enabler. | CLAUDE.md §9d "PROVENANCE MANDATORY on every attached fact" |
| CONF-LIST | Multi-model / identity conflict → engineer confirmation list; node mirrors state in on-node `identity_status`, never log-only. | CLAUDE.md "END-OF-SWEEP ENGINEER CONFIRMATION LIST" |

## 4. Electrical protocol A–F (source: docs/PROTOCOL_electrical_extraction.md)

| ID | Rule | Source |
|---|---|---|
| EP-A2 | LEGENDS FIRST: the sheet's own legends/tables are read before any symbol; the sheet's legend OVERRIDES the general glossary. | §A.2 |
| EP-A3 | Classify sub-type before reading; the read strategy differs per sub-type. | §A.3 |
| EP-A4 | Coverage-guaranteed detail read (survey regions ∪ fixed grid) — region detection is stochastic. | §A.4 |
| EP-A5 | Cross-reference enrich merge enforces never-invent / never-drop IN CODE. | §A.5 |
| EP-B1 | `<UNKNOWN>` for illegible, never fabricate. | §B |
| EP-B2 | Diamond + number on a wire = wire-gauge callout (annotation), not a signal. | §B (engineer red-pen) |
| EP-B3 | A multi-pin block labelled "SWITCH" on an HV/motor feed = harness connector/plug, not a mechanical switch. | §B |
| EP-B4 | "ISOLATOR" + ampere rating = breaker. | §B |
| EP-B5 | CT = current transformer (monitor) → routes to the monitoring system. | §B |
| EP-B6 | EARTH LEAKAGE n = earth-leak breaker (protection). | §B |
| EP-B7 | THE WIRE IS THE TEST — a wired element with a "see DWG n" reference stays an element; a pointer with no wire is annotation. | §B |
| EP-B8 | [VESSEL] Sheet-scoped vocabulary: a device prefix can mean different things on different sheets (CBx = retractable fuse on 110b/d/e). | §B |
| EP-D1 | Full-path hierarchy: node lives at the end of region→subsystem→equipment. | §D |
| EP-D2 | Pins attach to their plug's OWNER — follow the line to the labelled header box. | §D |
| EP-D3 | Equipment belongs to its SYSTEM, not its power source. | §D |
| EP-D4 | Cooling topology and control chains are first-class cross-links. | §D |
| EP-D5 | Earth-leak breakers are protection FOR something — attach to the protectee when it names an equipment. | §D |
| EP-D6 | [VESSEL, safety] Navigation/steaming lights are ALWAYS their own node. | §D |
| EP-D7 | "Disregard"/"skip" are real dispositions — record them, don't force-route. | §D |

## 5. Engineer red-pen rules (source: data/state/redpen_*.txt)

| ID | Rule | Source / quote |
|---|---|---|
| RP-1 | The number inside a diamond on a wire = wire gauge in mm², not a status signal. | redpen_electrical_batch1_raw_20260710.txt p3: "this is not a status signal this is a wire gauge indications , the number inside the diamond says the wire gauge in mm2" |
| RP-2 | A dotted-line rectangle = a confined box (an enclosure), e.g. the HVPDU. | redpen_electrical_batch2_CONDENSED p3: "dotted rectangle = confined box, here the HVPDU" |
| RP-3 | 1 pin hi + 1 pin lo + shield = CAN bus (twisted shielded pair) — a signal, not power. | batch2_CONDENSED p8 |
| RP-4 | "SWITCH PORT/STBD" with HVIL = multi-pin harness connectors, NOT mechanical toggles or network switches. | batch2_CONDENSED p8 |
| RP-5 | S1/S2/S3 "25A ISOLATOR" → Breaker. | batch1_raw p4 |
| RP-6 | Rectangle with a line in it, in a line = fuse. | batch2_CONDENSED p8 (F3…F10) |
| RP-7 | Pins that are part of a plug belong on the node of the equipment the plug connects to. | redpen_load_map_batch2 p12: "pins that are part of the plug that connects to the PORT MPCS" |
| RP-8 | Equipment belongs to its system, not its power source (BAE cooling pumps → 595 cooling). | load_map_batch1 p5 #6: "wrong! BAE cooling pumps are part of 595 cooling system" |
| RP-9 | Sub-panels / distribution boxes are NOT nodes ("#1 SERVICES → is a subpanel. no node"; GALLEY 1/2 = distribution box). | load_map_batch1 p5 #9/#10/#8/#9 |
| RP-10 | Each earth-leak breaker states what it protects; if it protects an equipment it goes on that equipment's node. | load_map_batch1 p5 EARTH LEAKAGE 1-12 |
| RP-11 | CT = current transmitter → Onyx monitoring node, cross-linked to what it measures. | load_map_batch1 p5 CT11/CT12 |
| RP-12 | NAV LIGHTS must be SEPARATED from the rest of the lights — a node of their own. | load_map_batch3 p14: "NAV LIGHTS must be SEPARATED from the rest of the lights — nav lights are a NODE OF THEIR OWN" |
| RP-13 | "disregard" / "skip" is a real answer and must be recorded as such. | load_map_batch1 p6 Q8 "Wrong disregard"; Q14 "disregard"; batch3 "skip" |
| RP-14 | Multi-core cable rule: thick line + equal numbered legs both sides = a multi-wire cable between two terminal strips; "MUx-N" = label + wire count; a numbered leg is a wire+terminal, NOT equipment. | load_map_batch4 p17: "[ENGINEER: make a general rule, pass for approval]" |
| RP-15 | A rectangle containing another rectangle with a line across it = a TERMINAL WITH A BUILT-IN FUSE. | load_map_batch4 p18 |
| RP-16 | Gauges/meters (Ph1/Ph2/Ph3/60Hz, voltage, load current) = indicators, NO node. | load_map_batch4 p18: "NO node, just an indicator" |
| RP-17 | Each BEL gets its own node (per-installation). | load_map_batch2 p12: "Each BEL should have its own node" |
| RP-18 | Relay/contactor loops are to be FOLLOWED ("very important, follow its loop"). | batch2_CONDENSED p4 (K4/Relay 5) |

## 6. Phase-2 invariants that bind Phase-1 code (source: ENGO_2.0_BACKLOG.md)

| ID | Rule | Source |
|---|---|---|
| P2-1 | All vendor SDKs behind `providers/` — no vendor import outside it. | BACKLOG "Architecture invariants already honored" |
| P2-2 | Gold-blind extractors: no vessel token in extraction prompts/code (audited + hash-recorded). | same |
| P2-3 | Vessel facts live in per-vessel artifacts, not in code. | same |
| P2-4 | Gold-values `tests/` harness stays OUTSIDE the extraction path. | BACKLOG "Must build BEFORE vessel #2" item 8 |
| P2-5 | Manual acquisition may SETTLE only at 100% certainty; below that, flag. | BACKLOG "Engineer-mandated 2.0 rules" |

---

**Total binding rules in this checklist: 82.** (counted from the tables above)
