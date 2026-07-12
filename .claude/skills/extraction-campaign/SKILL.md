---
name: extraction-campaign
description: Run a document-class extraction campaign for Engo/Gelliceaux the disciplined way — render-before-designing, pilot-then-stop, kill-safe ledger under Monitor, per-page verification, cost gate. Use when extracting any new or repeat document class (electrical schematics, PLC, P&ID/BOM, BAE HV, building drawings, vision backlog). This is the proven scaffold that made the 39-page GM book run survive crashes and stay honest.
---

# Extraction campaign

The repeatable shape for turning a class of drawings into Register knowledge without
burning money on a bad protocol or reporting a run that didn't happen. Read
`engo-orient` first.

## Hard sequence (do not skip steps)

### 0. Check the ledger FIRST — never re-extract what you have
Search `data/ledgers/*.jsonl` for the document. Extraction cost real money; the ledger
is the input for routing, not something to regenerate. `batch2a_v2_ledger.jsonl` (GM
wiring) and `batch3_reextract_ledger.jsonl` (GM re-read) already exist.

### 1. Render-before-designing (MANDATORY — the rule that keeps saving us)
Before writing ANY reader for a new class, render 2-3 real examples (`pipeline.
visual_extract.rasterize_pdf_page`) and LOOK at them. Designing a handler from memory
is exactly how `discover_structure` got built for hydraulic slices and silently failed
on every other class. Confirm: layout variants, rotation (BAE is 90°-rotated), text
layer (vector text? then extract word-boxes free, don't pay vision to re-read it),
legends present.

### 2. Legends-first + glossary are always on
`pipeline.legend_first.from_pdf` reads the sheet's own legends before symbols; the
symbol glossary rides in every prompt via `pipeline.symbol_glossary`. The sheet's own
legend OVERRIDES the glossary.

### 3. PILOT — one/two representative pages, then STOP for the engineer
Extract ONE page of each layout family. Report what came out. **Do not run the full
class until the engineer grades the pilot.** State the full-run cost estimate when you
ask (≈ calls/page × pages × ~$0.01-0.03/call). The BAE pilot is ~$1 vs a $15-30 full
run — the pilot is the cheap insurance.

### 4. Full run — kill-safe, under Monitor
- Append-only ledger `data/ledgers/<class>_ledger.jsonl`, one record per page, flushed
  per page. A re-run skips done pages WITHOUT re-downloading.
- Run under the **Monitor** tool (keeps the session alive; bare background tasks die at
  turn end). Filter to `^\[|COMPLETE|Traceback|Error|failed|Killed` — cover failure
  signatures, not just the happy path (silence is not success).
- Download the source once, cache to `data/documents/` or `data/ledgers/`, with 3× retry
  (a Drive/network drop mid-run is normal — the GM run hit one at page 39).
- Guard the enrich/merge path against non-dict vision output (crashed the run once).

### 5. Verify EVERY page as it lands — "clean" means reconciled
Run a second Monitor tailing the ledger through `pipeline.verify_page_live --follow N`,
emitting a verdict per page (retyped / same / multi-instance / lost). Investigate every
`CHECK (lost)`. → `verify-gate` skill for the full gate.

### 6. Route → dry-run → grade → real write
Route the extracted elements through `pipeline.node_write` (dry_run=True first). Compare
attach/flag counts vs the prior flagged list — the delta is the yield. Engineer grades
the dry-run report → real write (`dry_run=False`). → `register-write` skill.

## Cost discipline

- State a real dollar estimate before any big burn; the engineer gates it (🔴).
- Prefer FREE geometry (pdfplumber/pymupdf word boxes, OpenCV shape detection for
  diamonds/fuses/breakers) over vision calls wherever the text/symbol is deterministic.
  Reserve vision for genuine symbol/line-work reading.
- Selective tiling: per-component 600-DPI crops only on dense schematics that feed the
  node graph, not blanket.

## Traps caught before (check for each)
- Resolution: a full-height crop crushes small text to noise. Tight crop ≤~1200px long
  side BEFORE sending (the crop footprint is the binding constraint, not render DPI).
- A single two-image vision call makes the model SUMMARIZE and drop the element array —
  use the two-call enrich pattern (`read_wiring_region(cross_reference=True)`).
- Sheet-scoped vocabulary: a prefix (CBx) can mean different things on different sheets.
- The wire is the test: a cross-drawing pointer that carries a wire is an element, not
  an annotation.

## Report
Real numbers from the actual ledger only. Per-page or per-class: elements, type
distribution, enrich guard counts (invented-discarded / kept-from-crop), lost items
each individually dispositioned. Never "looks good" — quote the reconciliation.
