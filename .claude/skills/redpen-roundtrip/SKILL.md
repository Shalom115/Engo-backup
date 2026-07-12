---
name: redpen-roundtrip
description: Run the engineer red-pen round trip for Engo/Gelliceaux — turn a queue of decisions into a review artifact, capture his answers verbatim, apply them to the Register/load-map, and propagate his logic to close more rows. Use whenever the engineer needs to review/confirm proposed nodes, load mappings, symbol types, or identity conflicts. His time is the scarcest resource — this skill maximizes rows-closed per minute of his review.
---

# Red-pen round trip

The engineer's corrections are the most valuable data in the project. This is the
proven loop for collecting and applying them without wasting his time or losing his
words. Read `engo-orient` first if you haven't.

## The loop (five steps)

### 1. Build the review queue — confidence-sorted, not page-order
Surface the rows that unlock the MOST downstream closure first (a breaker/feeder that
anchors many indicators; a node that many rows map to), not sheet order. Each row
carries: what it IS (auto-classified), what SYSTEM/sheet it's on, the proposed node
(decoded to a human label + raw id + new-vs-existing), and — critically — a
**cross-check against the live Register** for what already exists at that SFI code
(catches stale "create NEW" proposals). See `pipeline/streamline_load_maps.py` for the
load-map version.

### 2. Publish the review page (the Artifact)
Generate an HTML review page (see prior `scratch_out/*_review.html` generators for the
pattern). MUST HAVE, learned from failures:
- **Autosave to localStorage** — a refresh must never lose typed answers.
- **A working export**: a pre-selected textarea + `document.execCommand('copy')` AND a
  Download-.txt button. Do NOT rely on the clipboard API alone (it's blocked in the
  sandboxed artifact frame — this broke once and cost the engineer an hour).
- **Full-width answer boxes** (textareas, not narrow inputs — truncation confused him).
- Filter box, jump-to-page, per-row badges (kind / new / existing / ⚠ stale).
Publish with the Artifact tool; keep the same file path to redeploy to the same URL.

### 3. Capture his answers VERBATIM
When he pastes answers, save them EXACTLY as written to
`data/state/redpen_<topic>_batch<N>_raw_<date>.txt` and commit before doing anything
else. His phrasing is the provenance. NEVER paraphrase the raw file (a prior session
saved a condensed version — it had to be redone). If the artifact's export failed, the
rescue is a devtools console script reading `input.einput`/`textarea.einput` values —
but prefer fixing the export.

### 4. Apply — backup first, integrity-gate, provenance on everything
- **Back up the Register first**: `cp register_<vessel>.json register_<vessel>.backup_<what>_<ts>.json`.
- Apply his decisions VERBATIM. Where he says "allocate a free SFI between X-Y", use
  `pipeline.sfi_allocate.allocate_in_range` (occupancy-checked) — never assign N+1.
- Every new node/fact/cross-link carries `{source_doc: "engineer red-pen ...", file:
  <raw txt>, authority: "engineer", as_of: <date>}`.
- **Integrity check before saving**: no dangling cross_links/parent/child; count active.
  Only write the file if 0 issues. → `register-write` skill for the write mechanics.
- Update the active `load_map_<vessel>.json` mappings + `non_node_dispositions` +
  `rules` (a new general rule he states goes in `rules`).

### 5. Propagate his logic — this is the multiplier
He teaches RULES, not just rows. After applying, sweep the still-open rows and close
any his new logic reaches (e.g. "nav lights are their own node" closes every nav-light
row; "pins attach to their plug's owner" closes wiring-tag rows; existing zone/system
maps close matching names). Write the propagation to
`data/state/*_propagation_<date>.json` split into `auto_answered` + `still_open`; fold
`auto_answered` back into the review page as PRE-FILLED (confirm, don't re-decide).
Report: N direct + M propagated closed, K genuinely open.

## Rules for reading his answers (he writes fast, in shorthand)

- "wrong! X goes to Y" → a correction; apply Y, note the correction on the node.
- "skip" / "disregard" → a real disposition (`non_node_dispositions`), not a gap.
- "make a new node ... logic is A→B→C" → full-path hierarchy; create at the end of the
  chain, occupancy-check the SFI.
- "link to X" / "cross link to Y" → bidirectional cross_link.
- "each X should have its own node" → per-installation parent/child.
- Answers often teach a GENERAL rule mid-row ("CT stands for... always goes to Onyx") —
  capture it as a rule AND apply it everywhere it fits.

## Report back
Lead with the number: "N of M rows closed (X direct, Y from your logic); Register now
Z entries, integrity clean." Then any new rule learned, any conflict surfaced (never
auto-resolved), and the next-highest-leverage queue.
