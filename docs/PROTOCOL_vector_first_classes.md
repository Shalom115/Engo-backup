# VECTOR-FIRST PROTOCOLS BY DOCUMENT CLASS
2026-07-27 · Grounded on live probes + renders of the engineer's five reference
files (render-before-designing). Extends the electrical protocol to P&ID, GA,
nav-layout, BAE, ONYX and manuals-with-figures. WRITE TO NODES: HELD everywhere
until the engineer approves the routing preview (his V1 rule: red-pen the
protocol → then full autonomous ingest → diff → repair protocol).

## 0. The probe verdicts (measured, not assumed)

| File | Probe | Consequence |
|---|---|---|
| GM book 43pp | A1_vector 43/43, no text layer | geometry-first (running) |
| BAE Wiring Diagrams 47pp | **40 A1_vector / 7 A2_raster**, 0 text | geometry-first on 40pp; vision tiles on 7 |
| Bilge & Fire System Schematic | A1_hybrid: **14,239 vector wire segs**, 3 images, 90 text chars | full geometry path incl. PIPES |
| Electrical System GA 001b | A1_hybrid: 21,137 wire segs, 17 images, 84 chars | geometry callouts + image inventory |
| Steering System GA | A1_hybrid + **real text layer (2,575 chars)** | labels FREE via get_text — no OCR |
| Nav layout schematic | hybrid + **text layer (2,188 chars)** + 32 equipment PHOTOS | text-layer harvest + photo bank |

Classifier v2 (`probe_corpus.classify_pdf_bytes`): A1_vector / A1_hybrid /
A2_raster + text-layer chars. "Has images" is NOT raster — the GA proved it.

## 1. P&ID / plumbed systems (sample: Bilge & Fire — the Gold-#2 family)

The sheet is vector and **pipe service is encoded in STROKE COLOR** (fire
line red, main bilge cyan, aux PVC/flex magenta — the sheet's own PIPE LEGEND
maps color→service). So:
1. Pipe netlist = the electrical netlist with `stroke color` carried per
   segment: nets become pipe RUNS per service, junctions = fittings/manifolds.
2. Tables (PIPING DETAILS, BILL OF MATERIALS, PUMP DATA) are glyph-plotted →
   same label pipeline; BOM row join key = the item number that also appears
   as `NNN-NN` callouts along the runs (e.g. 006-01 strumbox) — the tag join
   is DETERMINISTIC text matching, not vision.
3. SYMBOLS LEGEND on-sheet → the P&ID symbol bank seeds itself from the
   legend (legends-first, now $0).
4. Flow scenarios = graph walks per service color (suction → pump → overboard)
   with valve states from symbols; NO/NC printed at each valve.
Deliverable shape: per-service pipe graph + BOM-joined component records with
bbox provenance. Same lint (isolated runs, orphan symbols, unattached tags).

## 2. Building/GA drawings (samples: Electrical System GA, Steering GA)

Two sub-kinds, one protocol:
- **Positioned-callout GA** (Electrical GA): vector hull outline + equipment
  blocks + callout text. Extraction = label clusters with positions (glyph
  path; no text layer here) + leader-line tracing (short segments from label
  to equipment block). Facts routed as POSITION facts ('X sits in ER aft
  port') — Decision-2 positioned-callout router, now with exact coordinates.
- **Engineering GA with BOM** (Steering GA): REAL TEXT LAYER → `get_text
  ('words')` gives every string + bbox free. Extract: BOM table rows (part
  numbers, suppliers, materials), numbered callout circles joined to BOM item
  numbers (circle symbol + number → position of that part), dimension chains,
  and NOTES blocks (safety/system notes = operational knowledge → authority-
  tagged text chunks: '3 independent steering systems, no emergency tiller
  needed' is handover-grade knowledge printed on a drawing).
Embedded images (hull renders, logos) inventoried; content-bearing ones only
go to vision.

## 3. Nav/instrument layouts + ONYX-style panels (sample: Nav layout)

Text layer + equipment PHOTOS + color-coded cable classes (legend printed:
power red / N2K drop / N2K backbone magenta / video yellow / LAN blue / coax
green). Protocol:
1. Text harvest free (labels, EL/N_xx cable numbers, the cable-labeling
   legend, analog-channel lists 'Ch1 Backstay press Port from MYT plc' —
   that's a control-map cross-link printed on a nav drawing).
2. Cable netlist per color class → interconnection graph (who talks to whom
   on which bus) — exactly Engo's 'what leads to what'.
3. The 32 embedded images are the DEVICES (chart plotters, radar, hubs):
   image fingerprint (hash of bytes) clusters repeats; ONE vision call per
   unique photo → equipment identity; instances inherit. Photos of a TZT3
   repeat across yard drawings — a fleet-reusable photo bank.
4. ONYX drawings (sample pending from engineer): expected same family —
   panel layouts with tag blocks; the XA-tag vocabulary from GM sheets is the
   join key to the monitoring node. Protocol confirmed when sample arrives.

## 4. BAE book (47pp; 40 vector + 7 raster)

- Vector pages: geometry-first as-is; pages are ROTATED (rotation matrix
  discipline already enforced). Pinout tables (SWITCH→MPCS pin/wire/signal)
  are glyph-plotted tables → label pipeline reads them; **cross-validate
  against the text-ingested HV/LV Wiring xlsx** — the first dual-channel
  agreement case with two independent sources already in the corpus.
- The 7 raster pages route to the existing vision-tiling path (fused tiles).
- Two byte-variants of the book exist (hash-scan 2026-07-03: one doc, one
  rev, orientation variants) — revision gate already handles; extract from
  the landscape variant.

## 5. Manuals with embedded drawings (OEM manuals, investigation reports)

These are text-ingested already; the DRAWINGS inside them are the gap:
1. `page.get_images()` inventories every embedded figure with bbox — free.
2. Figure↔caption binding: nearest text line matching Fig/Figure/Table
   patterns in the text layer → figure gets a caption + section context.
3. Route: photos → vision describe (existing path); embedded SCHEMATIC
   figures → probe the figure itself (some are vector overlays, most raster)
   → tiling vision read with the symbol-bank vocabulary.
4. Provenance: {file, page, figure bbox} — jump-to-figure works like
   jump-to-cartridge.
5. Priority targets stay: CM-24-1732's 25 figures, CM-26 Fig 2, Akasol certs.

## 6. Hydraulic + PLC review (engineer: 'ok, flag glitches')

- **Hydraulic (discover_structure)**: sound and validated; ONE improvement —
  the rev10 sheets are Class-C text (garbled) but likely VECTOR linework:
  probe them; if A1, the cartridge callouts that cost locate_and_read vision
  calls become $0 label clusters, and the §4 crop-resolution ceiling
  disappears entirely. Worth one probe before the next hydraulic pass.
- **PLC (image-only exports)**: stays on the vision path (genuine A2), BUT
  probe each set first — 'image-only text layer' sometimes coexists with
  vector linework (the GM lesson). If truly raster, the electrical extractor
  design stands; fold rack-layout pages into the schedule reader family.

## 7. The machine loop (applies to every class above)

extract (deterministic) → lint (invariants) → **routing PREVIEW (red-pen
artifact, no writes)** → engineer approves → real write pass → full-drive
autonomous ingest → diff against approved previews → protocol repair.
Phase-1 red-pens calibrate; Phase-2 customers inherit calibrated graders,
symbol/photo banks, and font tables. Residue per book shrinks per vessel.
