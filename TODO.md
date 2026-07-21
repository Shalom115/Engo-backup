# ENGO v1 — EXECUTION PLAN TO FULL-DRIVE INGESTION
**Rewritten 2026-07-20 (engineer directive). This file is the single execution truth for
any session (Sonnet/Opus/Fable) working toward Engo v1. Goal: the ENTIRE drive ingested
end-to-end, clean, in ONE run, within days. No guesses — every unknown goes to the
engineer as a numbered question. Companion ledgers: `ENGO_1.0_TRACKER.md` (statuses),
`CLAUDE.md` (detailed log), `EXECUTION_SPECS.md` (older per-task specs — this file wins
where they disagree).**

---

## §0 SESSION BOOTSTRAP — read before touching anything

1. Load the `engo-orient` skill FIRST. Then read this file fully. Do not read all of
   CLAUDE.md (150KB) — use it as a lookup.
2. Repo = `/Users/captain/projects/gelliceaux`. Bash cwd RESETS between calls — `cd` in
   every command or use absolute paths. Python = `python3.12`, run with
   `PYTHONPATH=/Users/captain/projects/gelliceaux` for scripts outside the repo root.
3. **Long runs die when the turn ends.** Anything > ~2 min runs under the Monitor tool
   with a kill-safe append-only ledger (`.jsonl`, one line per unit, flushed per line).
   Resume = skip ledger-done units. NEVER a bare background task.
4. **The ten commandments (violating any = stop and re-read):**
   a. NEVER self-certify. Every "PASSED" claim quotes real numbers from real output
      re-read AFTER the run. (A fabricated pass was caught once; the rule is blood-law.)
   b. NEVER write to the real Register without the engineer's explicit GO for that
      specific pass. Default `dry_run=True` everywhere.
   c. NEVER guess. Unknown → numbered question to the engineer (batch them, see §3).
   d. NEVER create a Register node from a composition "no fitting node" flag without
      first checking the corpus/glossary/established facts (the 620-hv-dc-backbone
      lesson: the "unknown bus" WAS the HVPDU; the glossary said so).
   e. Extraction prompts stay GOLD-BLIND and VESSEL-BLIND (no Gelliceaux tokens, no
      gold values). Vessel knowledge enters ONLY via `pipeline/vessel_context.py` in
      the composition/knowledge passes. Class prompts with vessel examples = §0.5
      violation (happened once with sea chests; was ripped out).
   f. Engineer red-pen answers are saved VERBATIM to `data/state/redpen_*.txt` BEFORE
      acting on them, and mapped to the CORRECT sheet's uncertainty list — read the
      list you are answering against, never pattern-match numbers (the block A/B
      mix-up lesson: two sheets both had a "100"; answers went to the wrong one).
   g. Every Register write: backup first, provenance on every fact, integrity check
      after (no dangling links), idempotent on re-run.
   h. Revision gate on every write path; superseded drive_file_ids are refused
      (bench dry-runs may bypass with `bypass_revision_gate=True` — dry-run only).
   i. Conflicts/multi-model identities surface on the confirmation list + on-node
      `identity_status` — Engo never silently picks.
   j. Update `ENGO_1.0_TRACKER.md` ON THE SPOT with every status change.
5. **Cost discipline:** state the estimated $ before any vision run > ~$3 and get GO if
   it exceeds what the engineer already approved for that work package.

---

## §1 CURRENT STATE — what already works (2026-07-20)

**The pipeline is: EXTRACT (gold-blind, per drawing class) → COMPOSE (equipment-centric,
vessel-aware) → NODE-WRITE (resolve-first, dry-run default).**

| Module | Role |
|---|---|
| `pipeline/schematic_extract.py` | Hydraulic 2-pass extractor (skeleton+detail, block-level channel) — PROVEN |
| `pipeline/electrical_extract.py` | Electrical 3-sub-type extractor (schedule/one-line/wiring) + coverage-grid + per-terminal `has_builtin_fuse` (NEW — extractions before 2026-07-20 lack the flag) |
| `pipeline/pid_extract.py` | P&ID topology extractor (survey → BOM verbatim → component/connection graph) + `fluid_loops()` walker — BUILT 2026-07-20, validated once on raw-water-515 |
| `pipeline/loop_prepass.py` | Wiring graph walk BEFORE composition (multi-switch loops discovered, not fragmented) — validated on GM-114a |
| `pipeline/compose.py` | Composition v2: serve-who → flow scenarios on EQUIPMENT nodes → per-system infrastructure → relevance filter → uncertainties. Class rules for hydraulic/electrical/pid/plc/building_ga/interconnect/photos. Consumes loop digests + vessel_context |
| `pipeline/vessel_context.py` | The intrinsic-truth substrate: glossary + register index + established-facts (multi-fact/node, engineer-authority first) |
| `pipeline/node_write.py` | Resolve-first writer: control-map/load-map first, §9e fallback, flag-never-guess, revision gate, conflicts on-node |
| `pipeline/power_path.py` | Electrical circuit tracer (breaker→terminal→relay→device, cross-sheet capable) |
| `pipeline/revision_gate.py` | Supersede index; writers refuse old revisions |
| `tests/compose_check.py` | Composition runner over bench sheets |
| `data/state/vision_bench/**` | All bench extractions + compositions (engineer grading in progress) |

**Class readiness (honest):**
- Hydraulic: READY (template class; 10 sheets real-written pre-composition; composition validated on 3 fresh sheets).
- Electrical: READY for compose+route. 10,196 wiring elements already extracted (batch2a ledger `data/ledgers/batch2a_v2_ledger.jsonl` — do NOT re-extract). CAVEAT: those extractions predate `has_builtin_fuse` → §3 Q2.
- P&ID: extractor built; ONE validation (raw-water-515). Needs 1-2 more sheets + engineer grade before scale.
- PLC: composition validated on 2 pages (bench); dedicated rack/IO extraction = electrical-reader reuse per Ch2.3 plan; MYT program still with MYT (🔴 external).
- Building GA / schematic GA: composition-from-image validated (steering + electrical GA); positioned-callout ROUTER for many-node building drawings still unbuilt (Decision-2).
- Photos/certs/figures: describe-protocol works (bench cat 10); 762-file pending_vision queue waits on it.
- BAE interconnect: describe-level works; pinout cross-validation vs HV/LV xlsx designed, not run.
- Class-C: decode-first (`pipeline/decode_c.py`) then underlying class.
- KNOWN RECURRENCE: composition guessed "Cathelco" on 515 despite the Tecnoseal fact on the node — fact-pull is identifier-triggered; WP1 closes this. Until WP1 lands, treat make/brand names in compositions as UNVERIFIED unless the BOM printed them.

---

## §2 WORK PACKAGES — in execution order

### WP1 — Relationship-triggered fact exchange 🔴 BLOCKED on engineer wording confirm
**Why:** the Cathelco recurrence. Identifier-triggered fact-pull misses relationships
stated in words.
**The wording awaiting his confirm (build EXACTLY this once confirmed):**
> Whenever a pass establishes ANY relationship between a drawn element and an equipment
> or system (controls, actuates, feeds, cools, monitors, part-of), it must at that
> moment: (a) resolve the related node(s); (b) pull their established facts into the
> reasoning BEFORE composing — never re-derive or downgrade what a node already knows;
> (c) attach what was newly learned to the correct side of the relationship. Identifier
> codes are merely one trigger; the RELATIONSHIP is the trigger.
**Build:** in `compose()` — after the model's first-draft equipment_groups resolve, do a
SECOND pass: fetch each target node's facts via `vessel_context`, re-inject, let the
model self-correct (or simpler: pre-resolve candidate nodes from control/load maps +
serve-who keywords BEFORE the call and inject their facts up front — prefer this,
single-call). Validate: 515 re-run must say Tecnoseal.
**Files:** `pipeline/compose.py`, `pipeline/vessel_context.py`.
**Gate:** engineer confirms wording → build → show 515 diff.

### WP2 — Composition → real node-write bridge (THE missing link)
**Why:** composition output is currently a dry-run artifact. Ingestion needs it to become
facts on nodes.
**Build `pipeline/compose_write.py`:**
1. Input: one composition JSON + its sheet ref {source_doc, drive_file_id, page}.
2. For each equipment_group: verify `target_node_id` exists + active (NEVER create from
   a group — a missing node is a flagged finding per §0.4d); attach per function: one
   `flow_scenarios` fact (the scenario list verbatim), one `dry_data` fact, one
   `sheet_region` in provenance; key_components as a component fact.
3. Infrastructure entries → their system node the same way. `<UNKNOWN>`/missing target →
   confirmation-list entry, never a guess.
4. Uncertainties → append to a durable `open_uncertainties_<vessel>.jsonl` with sheet ref
   (the engineer's red-pen queue — THIS is what he grades between chunks).
5. Discarded_as_clutter → logged in the run ledger only.
6. Idempotency: fact-hash guard (sheet+kind+value) — re-run = 0 new facts.
7. Revision gate: refuse superseded drive_file_ids. Dry-run default; `--for-real` flag
   requires the engineer GO recorded in the session.
**Validate:** dry-run on ALL existing compositions (12 sheets), show the engineer the
would-be fact counts per node, get GO, real-write those 12, integrity check, spot-check
3 nodes by hand.

### WP3 — Per-class GO-gates (small, before the big run)
For each class NOT yet engineer-graded at composition level, run ONE more fresh sheet
end-to-end (extract→compose→dry-run write) and put it in front of the engineer:
- P&ID: one more sheet (suggest fuel 108-01-550-001 — the known compound BOM sheet).
- PLC: one rack page + one IO page through electrical-reader + compose plc.
- Building GA: one Hall Spars structural sheet (tests positioned-callout needs; if the
  composition can't route many-node callouts, STOP and design the Decision-2 router
  with the engineer — do not improvise).
- Photos: one cert + one investigation figure (CM-24-1732).
Each gate = engineer grades the composition page. His graded verdicts on the main bench
(10 categories) may arrive during this — apply red-pen fixes before the big run.

### WP4 — THE FULL-DRIVE RUN (the centerpiece — one clean run)
**Precondition: WP1..WP3 done + engineer GO on the batch plan below.**
**Inputs:** `structure_gelliceaux_001.json` (walk LIVE first — never trust cache),
`revision_index_gelliceaux_001.json` (rebuild after the walk), the batch2a ledger
(existing extractions — reuse, don't re-extract), `pending_vision_gelliceaux_001.json`.
**Order & batching (50-file chunks, engineer checkpoint after chunk 1 of each class):**
1. Hydraulic remainder (any sheet not among the 10 real-written; incl. rev10 `General`
   via P&ID/BOM protocol).
2. Electrical: compose+route the EXISTING batch2a extractions (41 wiring pages,
   one-line topo) + GM book pages; NO re-extraction of what the ledger holds.
3. PLC sets (MAST 25pp / ER 12pp / AFT + Rev4) via WP3-validated path.
4. P&ID population (~all 5xx system schematics).
5. GA/building drawings (post WP3 gate).
6. BAE 47pp (landscape variant, id per CLAUDE.md; pinouts cross-checked vs
   `HV Wiring.xlsx`/`LV Wiring list.xlsx` — mismatches to confirmation list).
7. pending_vision 762 (photos/certs/figures) — describe+compose photos class.
8. Class-C: decode (C2) then route to underlying class; C1 straight to class.
**Per chunk:** Monitor + ledger; after chunk: reconcile counts EXACTLY
(processed = attached + flagged + refused + errors, itemized); update tracker; dry-run
diff → engineer GO → real write; uncertainties file to the engineer.
**Cost:** estimate per class before starting (hydraulic ≈ $1-2/sheet composed;
electrical compose ≈ $0.5-1/page; P&ID ≈ $2-3/sheet; photos ≈ $0.1-0.3 each). State
totals up front; the engineer already signalled days-scale budget but SHOW THE NUMBER.
**Definition of a clean run:** every file in the live walk carries a disposition
(ingested-text / composed-to-nodes / queued-with-reason / excluded-with-reason /
superseded), counts reconcile exactly, zero unexplained errors, all uncertainties in
the engineer queue, Register integrity 0 issues.

### WP5 — Retrieval refresh (makes v1 answer from the new knowledge)
1. HyDE rebuild, component-level, SYMPTOM-PHRASED (from flow scenarios: "stern thruster
   weak to port" → EV-9.1 scenario facts). Vocabulary via `hyde_vessel_context.md` +
   lexicon; 5q/chunk docs, 3q/row, scenario-facts get symptom questions.
2. Node-facts → retrieval: embed each node's composed facts as retrievable chunks
   (doc_type="node_fact", metadata: node_id, sheet, bbox) so the chat agent cites
   nodes and can point at drawings (describe-AND-LOCATE end feature).
3. Re-run validation cases #1 (BEL) + #2 (GPM-12) + the engineer's live chat questions
   ("which relay alarms the onyx when the 230V is off?" MUST now answer from GM-114a
   facts — that was his first-ever webchat question and it failed on the old corpus).

### WP6 — v1 close-out
1. Validation Case #3 (engineer picks: MAPS contactors / BEL overloading / GPM-12
   alignment) — 🔴 graded.
2. M2 exit audit (every file dispositioned; gold fixtures diff clean; hash-audit
   extractor gold-blindness).
3. Webchat + conversation memory already live; sensors (Exocet endpoint) needs ONE
   aboard session with the engineer — schedule with him, not blocking ingestion.
4. Tracker + CLAUDE.md brought current; blind-run rehearsal (M3) scheduled with the
   engineer as the 2.0 gate — NOT part of v1.

---

## §3 QUESTIONS FOR THE ENGINEER (numbered — ask in batches, record answers verbatim)

1. **WP1 wording:** confirm the relationship-triggered fact-exchange wording (§2 WP1) —
   or edit it. Build follows your text exactly.
2. **batch2a fused terminals:** the 10,196 wiring elements were extracted BEFORE the
   per-terminal fuse flag existed. Options: (a) live with label-fallback now, add flags
   opportunistically when sheets are re-touched; (b) re-extract the 41 wiring pages
   (~$15-25, half a day). Which?
3. **Vision bench grading:** your per-category winner picks → we set `VISION_ROUTES`.
   (You said "tomorrow" — the run plan can start on anthropic-default and re-route later
   if you prefer not to block.)
4. **P&ID second gate sheet:** fuel 550-001 OK, or another?
5. **10 pointer files (.gsheet/.gdoc):** which matter? (List in CLAUDE.md Ch1.3.)
6. **Operational/live lists** (Running log / tools / inventory, ~1,700 un-placed
   chunks): placement decision is yours (living docs channel).
7. **cf-002 close-out:** what make IS the installed MAIN bilge pump (BOM printed FEIT =
   error; Gianneschi ACB 431 B turned out to be the FIRE pump)?
8. **Load-map v2 red-pen** (230V book extension draft) — still open from batch 1.
9. **MYT PLC program ETA** — chase MYT?
10. **Main AC Panel schematics:** which drawing(s) are its authoritative source, so the
    694 hub card links land right?

---

## §4 TRAPS THAT ALREADY BURNED US (do not repeat)

- Idle-kill: turn ends → background dies. Monitor + ledger, always.
- One-fact-per-node truncation in context injection (fixed — but watch any new cap).
- Pattern-matching engineer answers to the wrong list (block A/B). Read the list back.
- Creating nodes from composition flags without corpus check (HV backbone).
- Vessel tokens leaking into class prompts (sea-chest patch). Grep before commit:
  `python3.12 -c` gold-blind check exists in CLAUDE.md/commits.
- 16K output truncation on dense sheets (GM-111) → chunk the composition or raise to
  20K (>20K needs streaming; not wired).
- Anthropic 529 storms outlast bounded retry → ledger-resume, not bigger retries.
- Shell heredocs mangle JSON/escapes — write Python to temp files and run them.
- `pdftoppm` absent — render PDFs with pypdfium2.
- Charset: always `<meta charset="utf-8">` in artifacts; always `encoding='utf-8'`.
- The Browser preview launch.json lives at the CWD claude dir, not the repo.

---

# AUDIT PLAN (unchanged, binding)
1. Real-dispatcher rule: tests exercise the path a real run uses.
2. Counts reconcile exactly or the gap is itemized. No silent gaps.
3. Zero-fabrication: values printed-on-sheet or `<UNKNOWN>`; spot-verify against renders.
4. Integrity check after every Register write; backup before.
5. Idempotency: re-run same input → 0 new facts.
6. Engineer grades every new protocol/class before scale. Gold values live only in
   `tests/`. Revision gate always. Conflicts always surface. Both ledgers current.
