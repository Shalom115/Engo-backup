# ENGO 2.0 — PHASE-2 BACKLOG
Everything tagged "vessel #2 / fleet / generalize later". One codebase — these are the
items that must be TRUE before the same engine onboards another boat. Updated on the spot.

Last full audit: 2026-07-02

## Architecture invariants already honored (nothing to do, keep honoring)
- All vendor SDKs behind providers/ (LLM, embeddings, vectorstore, Drive, vision)
- Gold-blind extractors: no vessel token in extraction prompts/code (audited + hash-recorded)
- Vessel facts live in per-vessel artifacts (register/control_map/load_map/glossary/vocab_<vessel>)
- SHARED vs VESSEL prompt layers (system prompt v7 header) — split at Phase 2

## Must build BEFORE vessel #2 onboards
1. **Pre-classification protocol** (design locked 2026-06-18): find vessel root (SFI pattern,
   3-deep) → classify by folder/filename/text/thumbnail → CLASSIFIED MANIFEST → engineer
   reviews → then extraction. Promote route_kind to a first-class pass with artifact + gate.
2. **Logical-SFI auto-numbering in the autonomous node-creation path** (the 650/651 rule —
   applied by hand on Gelliceaux; must be code in Decision-5 auto-create).
3. **§9a text-layer classifier as a pipeline module** (A / B / C1 / C2 via chars + garble
   score + font-embedding; with the repeated-title-block guard that fooled the survey).
4. **Class-C decode integrated into text ingestion** (C2 = decode is the only read).
5. **Revision gate wired into ingest** (today: enforced at node-writer; ingest should
   mark/deprioritize superseded at chunk level too).
6. **Building-drawing positioned-callout router** (Decision 2) — one drawing fans to many
   nodes; unbuilt; blocks GA/structural class on any vessel.
7. **Equipment-alias / ontology DB** — per equipment class: names, common makers — makes
   backbone-building faster on vessel #2 (recorded 2026-06-10).
8. **Gold-values tests/ harness** (§0.5) — per-vessel gold fixtures OUTSIDE extraction path.
9. **Onboarding confirmation page** (§9j) for the engineer-facing review loop.

## Engineer-mandated 2.0 rules (2026-07-03)
- **GATED MANUAL ACQUISITION:** when an equipment identity is LOCKED (no-doubt, or doubt resolved
  by engineer red-pen) AND its manual is missing from the corpus → external search for the manual
  is allowed, but it may SETTLE (ingest+link) ONLY at 100% certainty it is the right manual for the
  exact installed model. Below 100% → flag for engineer, never link. (Extends the §3b hard rule:
  search corroborates, never originates.) In 1.0: manual missing → flag only, no search.
- **OPERATIONAL/LIVE LISTS channel:** running log / inventory / tools are living documents refreshed
  daily-to-bi-daily on Gelliceaux — in 2.0 this becomes either a PMS API feed or the same
  refresh-ingest setup; placement/refresh cadence is per-vessel configuration, not folder-walk.

## Fleet-learning artifacts (grow as conventions confirm)
- fleet_first_principles_candidates.json — fp-cand-001 (captive winch + tensioner pair,
  hard-gated detection rule) AWAITING engineer confirmation
- Functional-equipment list per vessel class (Register-first pre-seed, Decision 4)
- Drawing-symbol glossary (electrical/hydraulic/P&ID symbol → device type) + equipment-class
  glossary (§6 future build)
- Vessel identity capture (naval architect / builder) for fleet cross-referencing
- Hull_number = primary key; same-hull-model ≠ same-vessel

## Phase-2 pivots noted
- Exocet / Pixel Sur Mer may pivot the v2 monitoring architecture
- Suppliers per-file routing for multi-subsystem vendors (Farr, SENSORS)
- Meta Business API replaces Twilio sandbox (MessagingProvider seam exists)
- Multi-tenant: one namespace per vessel (collection naming already vessel-scoped)
