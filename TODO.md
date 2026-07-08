# ENGO BUILD PLAN — TODO.md
The whole plan, broken **Milestones → Chapters → Subjects → Sessions**. One SESSION = one
sitting with a named deliverable and a VERIFY step. Statuses: ✅ done · 🔨 in-process · ⬜ next · 🔴 engineer gate.
Companion ledgers: `ENGO_1.0_TRACKER.md` (live statuses) · `ENGO_2.0_BACKLOG.md` (fleet items) · `CLAUDE.md` (detailed log).
**→ EXECUTION_SPECS.md holds the full per-task spec for EVERY open item below (context,
files, procedure, verify, gates, traps, suggested model tier). Any executing session
reads its spec there — and §0 of that file — before starting a task.**

---

## M1 — KNOWLEDGE BASE (the library reads itself) — ~95% done
### Ch 1.1 Text corpus ✅
- Drive walk, Register backbone, full text ingestion (1,689+310 reconciled-exact), Suppliers fold-in,
  handover/authority docs, glossary+corrections, HyDE v1. **All done.**
### Ch 1.2 Node architecture ✅
- §9e matcher, §9d two-path writer, control map, load map, 6 general decisions, identity-resolution,
  Case A/B, abbreviation capability, source-type gate, per-installation blocks, revision gate,
  confirmation-list mechanism. **All done + engineer-graded.**
### Ch 1.3 Cleanup 🔨
- S1 ✅ legacy core re-place→purge→HyDE (854 out / 184 in / spot-checks pass)
- S2 ⬜ small residue: `._` skip-list; CSV sealogs; .gsheet/.gdoc pointers 🔴(which matter)
- S3 🔨 operational/live lists channel — YMP API now live changes the picture; reconcile + red-pen 🔴
### Ch 1.4 PMS/YMP channel (NEW) ✅ read / ⬜ write (future, hard-gated)
- Read-only YMP provider LIVE (equipment/jobs/inventory; 21 matches written as facts).
  Write side (Engo fills log/work cards) = future, explicit 🔴 gate before any build.

## M2 — EXTRACTION PROTOCOLS, ALL DOCUMENT CLASSES (the drawings feed the nodes)
### Ch 2.0 Cross-class layer (NEW) ✅
- system_archetypes.md v0.4 (sheet-reading sequence · loop-following · symbol traps ·
  15 system archetypes) + legend_first.py CODE-ENFORCED in both extractors (legends
  read before any symbol, by default) + power_path.py (circuit-loop facts on nodes) +
  node_crossref.py (doc-class completeness + corroboration/conflict on every fact write).
### Ch 2.1 Hydraulic ✅ (the template class)
- discover_structure, tiling, locate_and_read, control-map routing, REAL write pass (10 sheets),
  per-installation repair. Remaining subject: `General` sheet parts-list → Ch 2.4 (BOM protocol).
### Ch 2.2 Electrical 🔨
- S1 ✅ taxonomy grounding (5 GM renders → A/B/C sub-types)
- S2 ✅ extractor build + validation (survey/classifier 5/5; schedule 97 rows; wiring 91 el.; one-line topology)
- S3 ✅ Class-C decoder (C1/C2 split; +29 shift proven); population survey (8 groups)
- S4 ✅ load map v1 red-penned + applied (79 rows); GM book batch 1 (43pp surveyed, schedules written)
- S5 ✅ batch 1b: lighting-per-zone (135) + cockpit→control-map (14)
- S6 ✅ **batch 2a: wiring-page extraction** — 41 pages, 10,196 elements + topology (26 pages),
        0 errors; ledger preserved at `data/ledgers/batch2a_v2_ledger.jsonl` (do NOT re-extract)
- S7 🔨 **batch 2b: wiring routing** — write_sheet real pass done (62 power_path facts, GM-111
        loads via map v1); the 2,868 flagged re-route AFTER S9 lands 🔴 grade
- S8 ⬜ **batch 2c: one-line topology routing** (26 pages of topo in the ledger; ROUTER UNBUILT —
        cross-sheet bus reconciliation is the design piece) 🔴 design grade
- S9 ⬜ load map v2 red-pen applied (230V breaker-by-breaker validation; VCP hub w/ indicator semantics) 🔴
- S10 ⬜ BAE 47pp: index-routed run (landscape variant; rotation; pinouts cross-validated vs HV/LV xlsx)
### Ch 2.3 PLC (MYT Wago) ⬜
- S1 rack-layout pages via schedule-reader analogue; S2 I/O channel pages via wiring reader;
  S3 pb_ signals ↔ control map cross-validation (cockpit buttons + functions); S4 MYT program (when MYT delivers) 🔴
### Ch 2.4 P&ID / BOM-compound sheets ⬜
- S1 render-ground 2-3 examples (fuel, blackwater, hydraulic `General`) — RENDER-BEFORE-DESIGNING
- S2 build: BOM-table extractor + item-tag join to diagram symbols; S3 route via §9e + maps 🔴 grade
### Ch 2.5 Building/structural drawings ⬜
- S1 positioned-callout router design (Decision 2; one drawing → many nodes; position=fact) 🔴 design grade
- S2 build + validate on Hall Spars mast/boom + hull structure; S3 rig-package facts onto 810/830/850
### Ch 2.6 Vision queue backlog ⬜
- S1 762 pending_vision reprocess under node pipeline (photos/certs/figures classes)
- S2 describe-188 legacy reprocess; S3 CM-24-1732's 25 figures + Akasol certs (investigation-figure class)
### Ch 2.7 Retrieval layer refresh ⬜
- S1 full-corpus component-level HyDE rebuild (§9h); S2 node-tree → retrieval wiring
  (agent answers cite nodes + jump-to-bbox = describe-AND-LOCATE end feature)

## M3 — PROTOCOL LOCK + BLIND RUN (the 2.0 rehearsal)
### Ch 3.1 Protocol docs ⬜
- S1 write the final per-class protocol docs (from CLAUDE.md decisions → clean specs)
- S2 logical-SFI + occupancy-check into Decision-5 auto-create CODE; feeder/indicator rules into readers
### Ch 3.2 Blind run 🔴
- S1 re-run the FULL chain on Gelliceaux blind (no engineer input): walk → classify → extract → route
- S2 measure: red-pen list size, wrong-attaches (target 0), flags precision — vs this session's baselines
- S3 tweak protocols from the diff; re-run affected classes. **Exit = red-pen list is small + all-conflict-only.**

## M4 — LIVE AGENT LAYER (Engo becomes a crewmate)
### Ch 4.1 Sensors ⬜
- S1 Exocet poller (1/min, read-only) + summarizer; S2 GNSS clock cross-check (kills clock-guard backlog);
  S3 anomaly flags → WhatsApp
### Ch 4.2 Conversation ⬜
- S1 multi-turn memory (activates the diagnostic dialogue flow); S2 operational modes
  (calendar + VCP mode switches S3/S4/S5 tie-in)
### Ch 4.3 Comms ⬜
- S1 Twilio WhatsApp check-ins (morning/evening + follow-up loop)
### Ch 4.4 Validation ⬜
- S1 Case #3 (MAPS contactors / BEL overloading / GPM-12 alignment) 🔴 grade
- S2 retrieval eval harness (queries × docs × scored relevance) — unlocks threshold/chunk tuning

## M5 — ENGO 2.0 FOUNDATIONS (see ENGO_2.0_BACKLOG.md for the full list)
- Pre-classification manifest protocol · alias/ontology DB · onboarding red-pen page ·
  PMS/API operational channel · fleet convention list · gated manual acquisition ·
  multi-tenant namespaces. **Gate: M3 blind run passed first.**

---

# AUDIT PLAN — how we know it was done right
### Per-session verification (every session ends with its VERIFY, in the report)
1. **Real-dispatcher rule:** the test must exercise the path a real run uses (standing principle —
   two past failures came from shortcut tests).
2. **Counts reconcile exactly** or the gap is itemized (the 1,689 = … pattern). No silent gaps.
3. **Zero-fabrication check:** extracted values are printed-on-sheet or `<UNKNOWN>` — spot-verify
   a sample against the rendered sheet.
4. **Integrity check after any Register write:** no dangling cross-links/children/parents; maps'
   targets all active; backup exists before the write.
5. **Idempotency:** re-run the same input → 0 new facts (guard catches).
### Per-milestone audits
- **M2 exit audit:** every file in the structure manifest carries a class + a disposition
  (extracted / queued / excluded-with-reason); pending_vision = 0 or itemized; gold fixtures diff clean.
- **M3 exit audit (the big one):** blind-run diff vs engineer-graded baseline — wrong-attach count,
  flag precision/recall, red-pen size. Written report, engineer signs.
- **M4 exit audit:** validation cases #1-#3 re-pass on the full corpus; eval harness baseline recorded.
### Standing gates (never skipped)
- Engineer grades every new protocol/class before scale (no self-certification).
- Gold values live only in `tests/`; extractors stay gold-blind (hash-audited).
- Revision gate on every write; superseded sources refused.
- Conflicts surface on the confirmation list + on-node identity_status; Engo never silently picks.
- Both ledgers (`ENGO_1.0_TRACKER.md`, `ENGO_2.0_BACKLOG.md`) updated ON THE SPOT.
