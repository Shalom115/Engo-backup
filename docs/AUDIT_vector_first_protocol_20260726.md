# AUDIT — Why the electrical-schematic protocol keeps failing, and the vector-first fix

2026-07-26 · Fresh-eyes audit requested by the engineer. Grounded on: the live
pipeline code (`electrical_extract.py`, `legend_first.py`, `node_write.py`,
`power_path.py`), the red-pen session records, the fused-tiles trial results,
and — decisively — a direct structural probe of the GM book PDF itself.

**Verdict up front: the pipeline has been paying a vision model ~$2/page to
reconstruct, stochastically and imperfectly, information that sits in the PDF
losslessly and is extractable for $0.** The GM book is not a scan. It is a pure
vector CAD plot. Every wire is an exact line segment with coordinates. Every
label is a cluster of glyph strokes with coordinates. The protocol's failures —
line-tracing, element identity, activation loops, cost, the red-pen correction
spiral — all trace to one architectural decision: rasterizing vector data and
asking an LLM to be a geometer. The fix is not a better prompt. It is to stop
rasterizing.

---

## 1. The measured finding (this changes the whole cost/quality frame)

Probe of `SW108-01-600 Electrical schematics - GM Marine 06 Oct 2023` (43pp):

| Measurement | Result |
|---|---|
| Embedded raster images | **0 on all 43 pages** — pure vector everywhere |
| Vector paths, whole book | 215,816 instances |
| Text layer | 23 chars/page ("G M MARINE SERVICES") — text is *plotted as strokes* (CAD SHX font), which is why it was classed "Class A / vision mandatory" |
| p10 line segments | 26,533 total → 23,545 tiny glyph strokes, ~600 wire/frame segments. **The wire/text separation is a one-line length filter.** |
| Shape reuse | 20,493 unique shapes; **89% of all path instances are shapes repeating ≥5×** (10.5× mean reuse) |

Prototyped in this session, zero API calls, no tuning:

- **Netlist from geometry:** endpoint-snap + point-on-segment union-find on p13
  (GMMS 111a) produced 119 multi-segment nets; the overlay render shows nets
  correctly traced *through the drawn twisted-pair crossings* and across the
  full sheet width. This is exactly the "run over the lines" capability the
  vision pipeline has never delivered. Deterministic, reproducible, exact
  coordinates. (`tools/vector_probe.py` regenerates the overlay.)
- **Labels for free:** glyph strokes cluster into ~238 label boxes on p10;
  tesseract at 576-DPI-equivalent on untuned crops read `CB2_50A`, `-G3-D1P1-`,
  `PORT`, `STBD`, `BATTERY`, `SHUNT`… (11/15 clean in the first blind sample,
  zero configuration, PSM 7, no whitelist).
- **Symbols classify once, not per instance:** identical vector shapes
  fingerprint identically. A breaker symbol is the same path sequence all 43
  pages. Classify each *unique* shape once per drafting house — not each
  instance per tile per page.

## 2. Why the current protocol keeps failing (root causes, not symptoms)

**RC1 — Tiling destroys topology by construction.** The §4 resolution finding
correctly forced tight crops for legibility. But a wire is the one object that
never fits in a tile. The 3×3 coverage grid guarantees every *symbol* is seen
while guaranteeing every *long wire* is fragmented across 3-6 tiles, read as
disconnected stubs, and reassembled downstream by token-matching free-text
`connections` strings. "Runs over the lines" is precisely the capability that
tiling amputates. No prompt fixes this; it is geometric.

**RC2 — Stochastic enumeration under deterministic dedupe.** Every documented
scar is the same scar: survey region detection stochastic; locate-recall
stochastic; 106 vs 177 elements on the *same sheet* across runs; 7→2 "systems"
swing in the fused trial. The element's identity key is `(type, normalized id,
label prefix)` — text the model produces slightly differently each pass — so
the same physical device becomes two elements, or two devices merge. The graph
downstream is built on sand. Vector coordinates give every element a *spatial*
identity that cannot drift.

**RC3 — Connectivity crosses two lossy hops.** Geometry → vision free-text
("from → to" strings) → `power_path` token-matching. The PDF holds the exact
adjacency; the pipeline reconstructs an approximation of an approximation of
it. The activation loops the engineer keeps asking for (breaker → fuse → relay
→ device, with negatives and signal returns) are *graph paths* — they fall out
of a real netlist for free and can only be partially, expensively recovered
from tile text.

**RC4 — The red-pen correction spiral is a role-confusion symptom.** Wire-gauge
diamonds, plug-vs-switch, CP-SW, XA-signal-vs-power, CBx=retractable-fuse…
every correction became another paragraph in an ever-heavier prompt applied to
every tile of every page — cost up, rule interactions up, and the same class
of error recurring because each tile read re-rolls the dice. In a symbol-bank
architecture each of those red-pens is **one durable row keyed to one vector
fingerprint** ("this shape = wire-gauge callout, annotation"). Corrected once,
correct on all 43 pages and every future GM drawing, forever. The engineer's
red-pen effort moves from per-instance to per-type — that is a ~100× leverage
change on the scarcest resource in this project.

**RC5 — The model is asked to be four things per tile.** OCR engine + geometer
+ symbol classifier + marine electrician, simultaneously, per crop. The first
two are solved deterministic problems for vector input. The LLM earns its money
only on the last two — and those it can do at book level (symbol bank) and
netlist level (circuit interpretation), not tile level.

## 3. The fused-tiles trial, judged honestly

The fused run (3 OCR passes → 1, geometry pass kept) is a competent *linear*
optimization of the wrong layer: $2.00 → ~$0.93/page at parity quality. Its own
numbers show the ceiling: variance did not shrink (7→2 systems on identical
input), because fusing reads doesn't touch RC1-RC3. At the honest rate the full
Class-A set is ~$400/pass *and still stochastic*. Do not scale it over vector
sheets. Keep it — it is the right tool for the genuinely raster classes (PLC
image-only exports, scans, investigation-report photos), which is where it
should live.

## 4. The vector-first architecture (GEOMETRY-FIRST protocol)

Class split, decided by a $0 probe (`get_images()`/`get_drawings()` counts):
**A1 vector-plot** (GM book: confirmed 43/43; expect BAE, yard 600-series,
trunking, Hall Spars to probe likewise — verify, don't assume) and
**A2 raster** (PLC exports, scans, photos) which keeps the existing
fused-tiles vision path.

For A1, five deterministic stages ($0 API) + two narrow LLM stages:

1. **`vector_netlist`** — extract segments; length-filter wires from glyph
   strokes; merge collinear/dashed runs; junction discipline (endpoint-touch
   and T-joint join; plain crossings do NOT join — union-find on endpoints
   gets this right by construction; junction dots confirm); output nets with
   exact coordinates.
2. **`vector_labels`** — cluster glyph strokes into label boxes (+ orientation
   for vertical text); render each crop at high DPI *from vector* (no quality
   ceiling); local OCR (tesseract, char whitelist, confidence-gated).
   Low-confidence residue → batched montage vision calls (50 crops/call).
   Optional deterministic upgrade if residue is high: glyph-fingerprint
   decode — learn the ~80 unique glyph shapes once per book, then every label
   decodes exactly (same win as the C2 +29 decode).
3. **`symbol_bank`** — spatially group non-wire paths at net endpoints;
   fingerprint groups; **one vision call per unique symbol** (rendered with
   2-3 in-context examples), §6 discipline in that one prompt; engineer
   red-pens the *bank* once (~50-80 rows for the whole GM house), not pages.
   The bank is a durable per-drafting-house asset — vessel #2 with a GM-drawn
   boat inherits it.
4. **`assemble`** — attach labels to nets/symbols by geometric proximity
   (deterministic rules; ambiguous cases flagged, never guessed); emit
   per-sheet netlist JSON: `{nets, devices{type,id,rating,bbox}, labels,
   enclosures, cross-refs}` — every element with exact vector bboxes, so the
   jump-to-and-mark end-game becomes exact instead of fuzzy.
5. **`power_path` (existing)** — now walks real adjacency instead of token
   soup. Activation loops = shortest paths from supply anchors. The engineer's
   "breaker→fuse→relay→function" chains are queries, not extractions.
6. **LLM stage A — circuit interpretation (text-only, cheap):** Haiku/Sonnet
   reads the *structured netlist* (no images) and does the electrician's part:
   name the circuit, spot the load, classify feeder-vs-load, control-vs-
   indicator-vs-supply. Feeds the existing `node_write` machinery — load map,
   §9e, revision gate, provenance, confirmation list — **unchanged**.
7. **LLM stage B — QA sampling:** render overlay (nets colored, devices
   boxed) → one vision call verifies a sample; plus the existing verify-gate
   discipline. Vision becomes the *auditor*, not the *reader*.

**What survives untouched:** legends-first (now read via the $0 label path),
§6 device discipline (lives in the symbol bank), load map + control map +
source-type gate, revision gate, Register/node writer/provenance/confirmation
list, verify-gate, render-before-designing. The routing half of the protocol
was never the problem — it was being fed noise.

## 5. Cost model (honest estimates, to be validated at the Phase-1 gate)

| | current | fused trial | vector-first (A1 sheets) |
|---|---|---|---|
| geometry/topology | ~$1.20 of the $2, stochastic | in the $0.93, stochastic | **$0, exact** |
| labels/OCR | in tile reads | in tile reads | $0 local + ~$0.03-0.10 residue calls |
| symbol typing | every tile, every page | every tile | **one-time/book ~$1-3, amortized <$0.05/page** |
| circuit interpretation | implicit, unreliable | implicit | ~$0.02-0.05/page text-only |
| QA | — | — | ~$0.03/page (sampled) |
| **per page** | **~$2.00** | **~$0.93** | **~$0.10-0.20** |
| GM book (43pp) | ~$86 | ~$40 | **~$5-9 + one-time bank** |
| variance across runs | high (measured) | high (measured) | **zero on stages 1-5** |

Re-runs after a rule fix: free (deterministic stages recompute locally).

## 5b. CORRECTION — the first overlay was misaligned; the engineer caught it (2026-07-26)

The first net-overlay PNG sent with this audit had its colored lines ~90° off
the actual wires. Root cause: PDF pages carry a `/Rotate` attribute (p13 of the
GM book = Rotate 270); `get_drawings()` returns coordinates in the UNROTATED
space while `get_pixmap()` renders the rotated view. Measured ink-hit rate of
the bad overlay: **6.4%**. After mapping segments through `page.rotation_matrix`:
**96.2%** (p13) / 93.3% (p10, rotation 0 — baseline; residue = dash gaps).

Two lessons recorded, same family as the fabricated-Gold-#2 scar:
1. **I graded my own overlay by eyeball and reported tracing success over a
   6% alignment.** The engineer, who knows the sheet, caught it in one look.
2. **Fix in kind, not in apology: the overlay tool now computes its own
   ink-hit rate and prints it ON the image** (`ink_hit_rate()` in
   `tools/vector_probe.py`, threshold 0.90, "DO NOT TRUST" verdict below it).
   An overlay without its self-check number is not a deliverable.

The rotation trap generalizes: ANY consumer of `get_drawings()` coordinates
(netlist, label crops for OCR, symbol grouping, bbox provenance) MUST transform
through `rotation_matrix` when comparing against or cropping from renders.
The BAE set is drawn rotated 90° (known from the corpus survey) — this fix is
a precondition for probing it, not an afterthought.

## 5c. FULL ACCOUNTING — nothing on the page is left unread (2026-07-26, engineer push-back #2)

The engineer's second grade: "everything you left in black won't be read" — the
first overlays colored only the top-60 nets and drew nothing for symbols/labels.
Fixed in `tools/vector_extract_poc.py`, proven on p13 (GMMS 111a):

- **100% of ink pixels accounted** into four primitive classes: 810 wire
  conductors (dash-joined) → 355 nets; 309 closed-loop symbol boxes (terminal
  boxes, fuse elements, relay outlines, diamonds); 1,486 filled marks (junction
  dots — used as net connectors — and arrowheads); 344 label boxes (incl. 14
  vertical). Every class drawn in the overlay; nothing black.
- **Labels read and attached, locally, $0.** ⚠ CORRECTED 2026-07-28 (audit
  flag F5): the numbers first published here — 344 boxes / 330 non-empty /
  163 conf≥70 / 325 attached — came from the v1 box-merge segmentation and
  are NOT reproducible from the shipped runner. `cluster_labels` was replaced
  by the char-chain line builder on 2026-07-27 (v1 cut the first/last
  character off ~35% of labels), which produces FEWER, WHOLER labels. The
  reproducible figures on p13 today are **235 labels / 208 non-empty /
  103 conf≥70 / 225 attached**. The geometry numbers below (810 wires, 355
  nets, 309 symbol boxes, 1486 dots) DO reproduce exactly. Lesson recorded:
  a published measurement must name the code version that produced it.
- Known gaps, named: lamp/circle symbols (curve loops) not yet promoted to
  symbol boxes; ~half the labels below conf-70 await the residue channel;
  `get_pixmap(clip=)` is rotation-treacherous — the POC crops from one
  full-page render instead (two mis-crop bugs burned before this was learned).

**The deterministic OCR endgame — glyph-fingerprint FONT DECODE:** the plotted
SHX text means each character is an identical vector shape everywhere (89%
shape-reuse measured). Build the font table once per drafting house (one vision
read of the ~80 unique glyph shapes, or self-derived by aligning high-confidence
tesseract reads with their glyph sequences), and every label on every sheet of
every GM-drawn vessel decodes EXACTLY, forever — zero OCR noise, zero API. Same
family as the decode_c +29 win, at glyph level. This is the planned kill for the
OCR-residue channel, not a nice-to-have.

## 5d. HOW EXTRACTED OBJECTS BECOME NODE FACTS (the engineer's "how will all of
this be added to the nodes?")

The assembly emits one structured record per device: `{device_type (from the
symbol bank), id + rating (from attached labels), net memberships (from the
netlist), bbox}`. From there the EXISTING machinery routes it — nothing new:
- supply devices → `write_electrical_row` (load-map first, §9e fallback,
  flag-never-guess) → `electrical_supply` fact on the load's node;
- switches/relays/indicators → control/indicator facts per the two routing
  rules (FEEDER≠LOAD, CONTROL≠INDICATOR≠SUPPLY);
- **activation loops become graph queries, not extractions**: walk the netlist
  from a supply anchor through fuse→terminal→relay-coil→device; store as the
  existing `power_path` fact. Example assembled from real p13 output: +24V
  SERVICE BUS → F6 200A → SW7 → Q36 6A 'NAVIGATION LTS' → T/S E 22 → F 0.1A →
  PORT NAV. LT. — every hop with exact bbox provenance (jump-to-and-mark exact).
The difference from today: `power_path` walks REAL adjacency instead of
free-text 'connections' strings, and every element has a spatial identity that
cannot drift between runs.

## 5e. AUTONOMY ARCHITECTURE — the machine grades itself; red-pen is calibration,
not operation (the engineer's "step the game up" mandate)

Phase-1 red-pens are the TRAINING SET for automatic graders — their purpose is
to make themselves unnecessary. Customers never red-pen. Four self-grading
channels, all engineer-free at run time:

1. **Drafting invariants (electrical lint, $0):** a valid extraction obeys
   checkable physics/drafting rules — every net touches ≥2 objects; every
   device symbol sits on ≥1 net; every label attaches within radius; a
   fuse/breaker bridges exactly 2 nets; every load reachable from a supply
   rail; terminal strips number monotonically; cross-refs resolve to sheets
   that exist in the book index. Violations = machine-detected extraction
   defects. This replaces "engineer eyeballs the overlay."
2. **Dual-channel agreement:** the same fact derived two independent ways must
   match — geometry-netlist vs a sampled vision audit; tesseract vs glyph-
   decode vs vision on labels; the schedule sheet vs the wiring sheet vs the
   HV/LV wiring xlsx for the same device (the §2 multi-source vote, now cheap
   enough to run on everything). Agreement → auto-accept; disagreement →
   auto-flag.
3. **Self-derived ID grammars:** the corpus teaches its own tag formats
   (Q\d+, F\d+, Re\d+, CB\d+, XA\d+[nn]) from high-confidence reads; a read
   that breaks the sheet's own grammar triggers an automatic re-read
   (partnum_format generalized, self-deriving — never hardcoded).
4. **Confidence routing:** every fact carries confidence from channels 1-3;
   only sub-threshold residue queues on the existing confirmation-list
   machinery. Phase-1 red-pens calibrate the thresholds ONCE; the symbol bank
   red-pen is once per drafting HOUSE and accumulates as a fleet asset.

**End-state flow (customer experience):** share the Drive → walk → A1/A2 probe
runs INSIDE ingest (the `route_kind` classifier gains the get_drawings probe —
code, not a session) → per-class pipelines → netlists + labels + symbol
instances → invariants lint → cross-doc reconciliation → nodes, facts and
activation loops written with provenance → ONE residue page per book for a
human, shrinking per vessel as banks and grammars accumulate. The engineer's
role in Phase 1 — answering everything — is precisely what gets encoded so
vessel #2's engineer answers almost nothing.

## 6. Risks and limits, stated plainly

- **Only A1 sheets benefit.** Probe every set before promising; PLC stays on
  the vision path. (Probe is one command, $0.)
- **Dashed lines & symbol-interrupted wires** fragment nets → needs collinear
  gap-joining with tolerances; this is real engineering, not magic. Expect
  1-2 sessions of tuning against overlay renders graded by eye.
- **SHX OCR residue.** Tesseract will misread some plotted glyphs; the
  confidence gate + batched vision verification bounds the damage; the glyph-
  fingerprint decoder is the deterministic escape hatch if residue is high.
- **False joins** where an unrelated endpoint lands exactly on another wire
  within tolerance — rare, and junction-dot detection (filled circles are
  distinct vector objects) disambiguates.
- **The netlist is per-sheet truth, not system truth.** Cross-sheet assembly
  still runs through the semantic/zone key and cross-ref machinery — that part
  of the Master Spec stands.

## 7. Recommended sequence (gates in the house style)

1. **Phase 0 — probe the corpus** (one session, $0): classify every Class-A
   candidate A1/A2 with `tools/vector_probe.py`. Deliverable: the real
   population split. GATE: engineer sees the split.
2. **Phase 1 — netlist + overlay on 2 sheets** (111a + 114a, $0): colored-net
   overlays. GATE: engineer eyeballs the overlays — "are the lines run
   correctly?" is now a picture, not a claim.
3. **Phase 2 — labels** ($0 + residue): OCR against the red-penned sheets'
   known labels as ground truth (they exist — use them as the fixture, gold-
   blind rules unchanged: fixtures validate post-hoc, never enter prompts).
4. **Phase 3 — symbol bank** (~$1-3 once): unique-symbol sheet → engineer
   red-pens the bank in one sitting.
5. **Phase 4 — assemble + route** GM-114a end-to-end; diff the activation
   loops against the engineer's known chain (Q13 → T/S B 8 → Re1 → XA40).
   GATE: engineer grades. Then scale the book at ~$0.15/page.

## 8. Open questions for the engineer

1. May a session probe the BAE 47pp + yard 600-series + trunking + Hall Spars
   PDFs from Drive ($0, minutes) so the A1/A2 split is fact, not hope?
2. One symbol-bank red-pen sitting (~50-80 rows, once per drafting house)
   replaces per-page red-pens — acceptable format?
3. Local OCR adds `pymupdf` + `tesseract` to the MacBook toolchain (both free,
   offline — consistent with the boat-laptop constraint). OK?
