# ENGO 1.0 — PHASE-1 TRACKER
Living ledger. Updated ON THE SPOT when a decision lands, a build completes, or a status changes.
Statuses: ✅ DONE · 🔨 IN-PROCESS · ⬜ NOT STARTED · 🔴 AWAITING ENGINEER

Last full audit: 2026-07-02

---

## A. FOUNDATION (all done)
| Item | Status |
|---|---|
| Providers (LLM/embeddings/vectorstore/structure/vision abstractions) | ✅ |
| Config/.env, smoke test | ✅ |
| Parsers: PDF / XLSX (blank-header hardened) / DOCX / procedure-chunker | ✅ |
| Drive connector (read-only SA) + LIVE walk (2,238 nodes) | ✅ |
| Register from folder walk + Suppliers fold-in (deduped, reconciled exact) | ✅ |
| Full text corpus ingested (1,689 + 310 files; audit gate PASS, 0 silent gaps) | ✅ |
| HyDE v1 (original ~757 chunks) + vocab seam (lexicon/vessel-context/acronyms) | ✅ |
| Glossary + corrections log (Block D) | ✅ |
| Handover/authority ingestion (Block C) + CAN-H locked fact | ✅ |
| System prompt v7.1 (Step 0 budget, no-anchoring, recency carve-out) | ✅ |
| Clock sanity guard (floor) | ✅ |
| Validation cases #1 (BEL) + #2 (GPM-12) passed & re-passed | ✅ |

## B. NODE ARCHITECTURE (the Register-as-node-tree)
| Item | Status |
|---|---|
| §9e semantic matcher (threshold 0.45 + identity guard) | ✅ |
| §9d node writer: two-path, control-map-first, provenance, conflict-on-node | ✅ |
| Control map (39 hydraulic functions, engineer-confirmed) | ✅ |
| 6 general decisions (SFI collision, building-drawing class, parent/child, register-first, auto-create rule, equipment≠actuator) | ✅ |
| Function-equipment identity resolution (integrated vs separate-actuator) | ✅ |
| Case A/B protocol (conflict=defer vs pattern=may-act) + confirmation list | ✅ |
| Abbreviation capability (S.T./B.T. proven general) + fuzzy floor | ✅ |
| Source-type gate (control map = hydraulic only) | ✅ |
| Per-installation block resolution (hardened after real-pass wrong-attach) | ✅ |
| Revision gate (42 families, 96 superseded; enforced in node writer) | ✅ |
| Logical-SFI rule (650/651) — applied by hand in map scripts | ✅ applied / ⬜ **not yet in pipeline auto-create path** |
| Engineer confirmation list mechanism + on-node identity_status mirror | ✅ |

## C. EXTRACTION PROTOCOLS BY DOCUMENT CLASS
| Class | Protocol | Status |
|---|---|---|
| Hydraulic function blocks + sailing manifolds | discover_structure → node_write | ✅ **REAL data written** (10 sheets, 194→273 facts, Path-1 repair done) |
| Hydraulic `General` overview (parts list) | compound BOM protocol | ⬜ (shares build with P&ID) |
| Electrical schedule (GM sub-type A) | survey → schedule reader → load map | ✅ **REAL: GM-111 written** (79 attach / 0 unresolved) |
| Electrical wiring (GM sub-type C) | wiring reader | ✅ validated on 114a · ⬜ not yet node-routed |
| Electrical one-line (GM sub-type B) | one-line reader | ✅ validated on 110b · ⬜ not yet node-routed |
| Remaining GM book sheets (43pp current book) | above readers | ⬜ next |
| BAE wiring (47pp, rotated; 2 contents ambiguous) | one-line+wiring readers + HV/LV xlsx cross-val | ⬜ 🔴 (pick current content) |
| PLC sets (image-only; rack + I/O pages) | electrical extractor | ⬜ |
| Trunking C2 (garbled render) | decode_c (+29 proven) + building router | ✅ decoder / ⬜ ingestion wiring |
| System P&ID (fuel/blackwater) | BOM-table + symbol tiling | ⬜ design sketch only |
| Building/GA drawings (Hall Spars, hull, GA) | Decision-2 positioned-callout router | ⬜ **unbuilt — known gap** |
| Class-C text decode in text-ingestion path | decode_c integration | ⬜ |
| Electrical load map | engineer red-penned, ACTIVE | ✅ |

## D. VISION / SCHEMATIC BACKLOG
| Item | Status |
|---|---|
| pending_vision queue (762) reprocessing under node pipeline | ⬜ |
| 188 legacy describe-only chunks (flagged) → reprocess/purge | ⬜ |
| Legacy ~2,125 un-placed chunks purge + re-place | ⬜ (deferred to HyDE rebuild) |
| Full-corpus HyDE rebuild (component-level, §9h) | ⬜ |
| describe-AND-LOCATE end feature (mark item on drawing for engineer) | 🔨 (locate_and_read built; bboxes on nodes started; retrieval/UI integration ⬜) |
| Gold #1 mast block | ✅ effectively (discovery+tiling+locate graded) |
| Gold #2 bilge node (cross-drawing assembly) | ⬜ — wiring reader ready; assembly not run |
| Gold-values `tests/` harness (§0.5) | ⬜ **never built — flag** |
| 50-file engineer-graded ingestion cycles | ⬜ gated on protocols complete |
| CM-24-1732's 25 figures + Akasol cert set (vision targets) | ⬜ |

## E. INGEST CLEANUP (small, standing)
| Item | Status |
|---|---|
| `._` AppleDouble skip-list | ⬜ |
| 12 unsupported: .gsheet/.gdoc pointers, cutlass-bearing .pptx, 3 CSV sealogs | 🔴 engineer decides which matter |
| md5-join for 206 ambiguous same-name multi-id files | ⬜ noted refinement |

## F. AGENT / LIVE FEATURES (untouched this whole phase — by design, but on the roadmap)
| Item | Status |
|---|---|
| Exocet sensor poller + summarizer (+ GNSS clock cross-check) | ⬜ |
| Clock guard upper bound (forward jump) | ⬜ backlog |
| Twilio WhatsApp check-ins | ⬜ |
| Multi-turn conversation memory | ⬜ |
| Operational mode handling (calendar → mode) | ⬜ |
| Retrieval eval harness (gates threshold/chunk tuning) | ⬜ |
| Validation Case #3 (MAPS contactors / BEL overload / GPM-12 alignment) | ⬜ |
| MYT PLC program parse (waiting on MYT delivery) | 🔴 external, ETA days |

## G. CONFIRMATION QUEUE — answered 2026-07-02, all applied
1. cf-001 captive winch → **SPLIT** ✅ parent + `220-captive-mainsheet-9t` / `220-captive-tensioner-ct1`; control map #37/#38 retargeted
2. cf-002 bilge pump → **Gianneschi** ✅ on `520-main-bilge-pump` (both claims recorded); FEIT node kept as unresolved documentation; 2.0 rule: conflicts red-penned in onboarding
3. fp-cand-001 → **deferred**, reminder set: raise before next major ingestion / vessel #2 (not crucial — it's only the AUTO-split convention for future boats; the Gelliceaux instance is resolved)
4. BAE copies → **hash-scanned all 6: ONE document, ONE revision** (196D5023 rev –, Apr-2023); 2 byte-variants = page orientation only. Standing rule adopted: same-name copies hash-compared (≈$0 — ingest already hashes); differing hashes → title-page rev comparison
5. 260 doors + passerelle → **CONFIRMED** ✅ flags cleared
6. 651 → **BAE keeps 651** ✅ emergency-stops moved to **654** (652 ONYX / 653 MYT / 655 BAE / 656 taken); bonus: ONYX moved to its REAL yard section **652**. Rule hardened: logical-SFI assignment must check yard-tree occupancy first
7. Cutlass .pptx → **INGESTED** ✅ (pptx parser added to registry; Feb-2026 shaft clearances live under 430). Remaining: .gsheet/.gdoc pointers + 3 CSV sealogs still flagged, non-critical
8. Legacy purge → answered (see report): best practice = re-ingest placed replacements first, verify, THEN purge — decoupled from full HyDE rebuild; queued in cleanup pass
9. Extraction order → **GO**: GM book → BAE → P&ID
10. Gold standard → **GO**: build tests/ gold harness + run Gold #2 BEFORE scaling the GM book

## H. ACTIVE WORK QUEUE (in order, per engineer GO 2026-07-02/03)
1. ✅ **Legacy cleanup CORE DONE (2026-07-03):** 7 core pre-Drive docs re-placed/purged — 854 old un-placed chunks out, 184 placed chunks in, 0 un-placed remaining (Owner's Manual, M50GB3825, M50GB3822→Drive names, CM-22-702→Drive twin, CM-24-1732→purged dup, CS-21-D82→purged dup of placed 420 twin, CM-26→placed 625 🔴flag). **HyDE regen DONE: 7 files, 214 chunks, 1,070 questions, 0 errors. Retrieval spot-checks PASS: the documented Akasol pollution case is fixed (top-4 now all placed Akasol chunks); BEL query still ranks CM-24-1732 (placed twin) top-3.** **Deferred w/ reasons:** operational lists (Running log/tools/inventory + live variants, ~1,700 chunks) = placement is an engineer domain decision; describe-188 = reprocess under node pipeline, already retrieval-flagged. 🔴 Two placement flags for red-pen: BAE manuals carried 500/570 from the Suppliers vendor map (suspect — 625/420 more likely right); CM-26 assigned 600/625 by me (local-only file).
2. 🔴 **Gold #2 RE-RUN FOR REAL (2026-07-04, fixed + re-run same day the fabrication was caught).** Prior "PASSED" entry was fabricated (retracted, see CLAUDE.md). Added retry logic to the Drive download (root cause of the crash), re-ran in foreground, read the real output directly. **Result is a mixed real finding, NOT a clean pass** — `tests/gold2_diff_20260704.json`: Re2-6 found (Re1 missing), zone-merge pattern confirmed, 0-components P&ID gap confirmed. MISSES: Q13/F3 breaker/fuse not typed at all this run (non-deterministic vs the earlier partial attempt which did catch them — same sheet, 177 vs 106 elements across two live passes); T/S B not read; **XA10/XA40/XA11 mistyped as controller_module/terminal_strip, never status_signal — a real §6 device-typing miss.** **NEW OPEN QUESTION for engineer:** the schematic's primary pump reads as "MAIN BLUE PUMP: Jabsco 43400" — neither "Gianneschi" nor "FEIT" appears anywhere in this read; unclear if this is even the same pump cf-002 addressed. 🔴 Awaiting engineer grade on: (a) whether this result is acceptable to proceed on, (b) the Jabsco/Gianneschi/FEIT pump-identity question.
   **→ BATCH 2A/2B EXECUTED (2026-07-05).** Re-extracted all 41 wiring/one-line pages of the GM book with the coverage-guaranteed readers: **10,196 wiring elements total.** Two real problems surfaced mid-run, both handled honestly rather than glossed over: (1) the malformed-vision-output crash hit 5 pages (08,13,18,21,30) — but their WIRING data had already completed successfully before the topology read crashed, so no re-extraction was actually needed for those (only their one-line TOPOLOGY data is still missing); (2) **page 42 (Vessel Control Panel) failed on a genuine Anthropic API credit exhaustion ("Your credit balance is too low") — a real external blocker, not a code bug; its wiring data (116 elements) had already completed before the topology call hit the wall.** No further vision-API work is possible until the account is topped up. **Routing (batch 2b) ran on all 10,196 elements (pure local computation, no API cost, unaffected by the credit wall):** `not_routed`=7,154 (structural — terminal/plug_pin/relay/controller_module/unknown, ~6,155 of these; not routed by design, this pass only builds SUPPLY/INDICATOR/CONTROL), `create_flagged`=2,873 (label didn't resolve to a Register node — expected on a still-thin register, correct decline not failure), `already_attached`=50, `attach`=11, `attach_feeder`=1 (the FEEDER rule fired correctly in production: QE6→`640-dc-distribution` as a feeder, not a load). **Honest limitation found: status_signal (1,395) and switch (700) elements mostly declined, not because the CONTROL/INDICATOR split is broken (verified safe — zero wrong-attaches) but because their raw labels are often signal/pin tags ("OPEN","XA10-04") rather than equipment names — §9e correctly has nothing to match. Real yield on indicator/control routing is near-zero this pass; needs a smarter design (resolve via the nearby breaker/load context, not the bare signal label) — flagged for later, not rushed.** Register: 311 entries, 0 dangling cross-links. 🔴 **Blocked: top up Anthropic API credit before any further vision extraction (BAE, PLC, P&ID, remaining topology).**
   **→ FIXED SAME DAY (2026-07-04):** (1) **Coverage guarantee built** (`read_wiring_coverage`: survey regions ∪ full-sheet grid, merged) — re-validated on 114a: 264 elements, **178 found only by the grid** (proof ~2/3 of the sheet was previously unread); Q13 ✓ F3 ✓ T/S B ✓ Re1-6 ✓ XA→status_signal 18/23 ✓. (2) **P&ID brick #1: tiled verbatim table reads** — the bilge BOM read matches the engineer's ground truth row-for-row (crash pump = Aussie Pumps/Yanmar L48; electric fire pump = Gianneschi ACB 431B; FEIT VA 40B = the printed-but-incorrect main-bilge label; aux = Whale Gulper 320; Burkert valve actuators; Vega alarms). Facts written to 6 nodes; crash-pump node created; Jabsco = STBD gen pump w/ emergency bilge suction recorded from engineer. 🔴 **NEW cf item: what make IS the installed MAIN bilge pump?** (BOM's FEIT is wrong per engineer; Gianneschi turned out to be the FIRE pump — cf-002's answer needs re-confirmation.)
   **→ RESOLVED (2026-07-04, engineer):** main bilge pump and electric fire pump are TWO SEPARATE physical pumps, SAME model (Gianneschi ACB 431B) — not one unit. Register corrected, cross-linked, cf item closed.
   **→ Coverage-guarantee EXTENDED to the schedule reader** (same stochastic-region-detection risk as wiring) + **re-validated on GM-111 (already real-written in batch 1)** — found 8 genuinely-missed loads (PASSARELLE LIGHT, TENDER REFUELING PUMP, SALOON FRIDGE, SALOON LKR LT., FWD MAN. SUMP PUMP, FWD EMERGENCY LTS/HATCH SUPPLY, MAIN PANEL, AUX1/B&G) — attached as create_flagged (none in the confirmed map, correctly declined not guessed). ~30 other apparent "new" hits were grid-tile label truncation (noise, filtered, not real misses).
3. 🔨 **GM BOOK BATCH 1 DONE (2026-07-03) — AWAITING GRADE + LOAD-MAP-v2 RED-PEN.** All 43 pages surveyed → `gm_book_manifest.json` (13 one-line / 26 wiring / 1 schedule / 2 mixed / 1 cover; sheet titles + regions per page). Schedule regions REAL-written via the confirmed map: **56 attached, 47 blocked by idempotency guard, 324 spares, 546 flagged**. Flagged = loads NOT in the map (230V AC panels, BAE LVPDU CB banks, per-panel lighting circuits, cockpit control panels, vessel control panel) → **`load_map_gelliceaux_001.EXTENSION.DRAFT.json` — 29 sheets, 479 distinct loads for red-pen**. Honest wrinkle found+fixed: 54 duplicate supply facts (archived-single partial reads vs book's cleaner reads of the same rows) reconciled — kept most-complete read, enrichment note recorded. **Batch 2 (held for grade): wiring-page element routing (per-sheet system node + zone splits, Gold-#2 pattern) + one-line topology routing.**
   **BATCH 1B APPLIED (2026-07-03, engineer decisions):** LIGHTING per zone → **135 circuit rows attached** to 690-lts-* zone nodes (hatch circuits→240-hatches; 0 unresolvable); COCKPIT 124 buttons → **14 attached via the hydraulic control map** (furl jib→860-gfsi30, staysail→860-sit20, jib sheet/tack→840; PLC pb_-signal cross-validation noted for the PLC pass; LED/pin internals honestly flagged). **Draft v2 for red-pen** (`load_map_gelliceaux_001.EXTENSION.DRAFT_v2.json`): 21 sheets / 324 loads / 133 auto-proposed (MPCS→620, ACTM→420, PVED→430-hundested, chargers→630, galley→360, aircon→590 + NEW-node proposals: **BEL×4 per-installation, MAPS, SCU3, EDN, BAE-cooling-pumps group, battery banks ×4 (GMDSS/Emergency/Gen-start/Aux), 230V outlets, VCP hub node 641 w/ cross-links + operating-mode switches**) / 191 UNKNOWN (mostly LVPDU wire-tags + one-line internals = batch-2 topology, not loads). **Meta-plan confirmed with engineer: graded batches = protocol tuning → protocols locked → BLIND RUN on Gelliceaux → tweak → 2.0 red-pen minimal.**
4. ⬜ BAE 47pp (landscape variant): index-routed, one-line + pinout readers, HV/LV xlsx cross-validation
5. ⬜ P&ID protocol (fuel + blackwater + hydraulic `General` parts list)
6. ⬜ Small cleanup: `._` skip-list, CSV sealogs decision, .gsheet/.gdoc pointers
7. ⬜ Then LIVE LAYER: Exocet poller → multi-turn → Case #3 → eval harness

fp-cand-001: **CONFIRMED as captive-winch-specific convention** (2026-07-03). General parent/child machinery = existing protocol (Decisions 3/5 + Case A/B); convention list grows per-instance.
