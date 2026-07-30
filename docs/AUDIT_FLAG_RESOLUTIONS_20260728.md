# AUDIT FLAG RESOLUTIONS — vector-first protocol
2026-07-28. Against `docs/COMPLIANCE_REPORT_vector_first.md` (82 rules,
40 PASS / 15 FLAG rows = 11 findings / 27 N/A, branch
`vector-protocol-compliance`). Every claim below was verified by running the
tool and reading its real output.

| # | Finding | Resolution |
|---|---|---|
| F1 | legends-first absent from the vector path | **FIXED IN THE PATH.** New `tools/sheet_legend.py`; `run_book_extract.process_page` reads the sheet's own legend BEFORE typing, and passes it into `type_page_symbols(legend_map=…)` as an argument the caller cannot forget. Precedence: sheet legend > confirmed bank > glossary > UNKNOWN. Live on the bilge P&ID: heading found, 50 usable symbol→meaning pairs. Heading regex made truncation-tolerant after the real heading OCR'd as `'SYMBOLS LEGE'`. Junk pairs (OCR crumbs) are rejected, never promoted — a bad legend entry would override the engineer's bank. |
| F2 | switches routed as supplies | **FIXED.** `SW\d+` removed from the supply regex; new `CONTROL_ROW_RE` types switches `role=control` and never proposes them as a supply for a load. |
| F3 | preview claimed writer-fidelity it lacked | **FIXED (honesty).** Docstring now states plainly that Register-name containment STANDS IN for §9e, has no scoring/threshold/identity guard, and that `via=register_name` is weaker evidence than `via=load_map_exact`. |
| F4 | docstring order ≠ code order | **FIXED.** `propose()` docstring now lists the order the code actually runs. |
| F5 | audit §5c label numbers not reproducible | **CORRECTED IN THE AUDIT DOC.** Cause identified: those numbers came from the v1 box-merge segmentation; `cluster_labels` was replaced by the char-chain line builder on 2026-07-27. Reproducible p13 figures now stated: 235/208/103/225. Geometry numbers reproduce exactly. Lesson recorded: a published measurement must name the code version that produced it. |
| F6 | `symbol_bank_worksheet.py` does not exist | **STALE — it exists** (built 2026-07-28, after the audit's scope was fixed). Not a defect; the audit was right about the state it saw. |
| F7 | no revision/supersession check in the vector chain | **FIXED.** `routing_preview.load_superseded()` reads `revision_index_gelliceaux_001.json` (shape inspected, not assumed) and `--drawing-id` refuses a superseded drawing outright. Verified live against a real superseded id. |
| F8 | engineer conventions absent from the bank vocabulary | **FIXED.** Worksheet vocabulary rewritten to the engineer's own terms; ~25 general rules added to `prompts/drawing_symbol_glossary.md` from the symbol-bank red-pen (dot rule, XA arrow direction, conversion block, fused terminal, ganged breakers, cable structure, plug/pin anatomy, title block, index page…). |
| F9 | both reference sheets hard-fail the lint | **TEST CORRECTED, THRESHOLD UNCHANGED.** Measured first: of 40 "isolated" nets on p13, 21 touch a TYPED symbol and 10 more touch a nearby label — the L1 test predated symbol typing and only knew raw closed-loop boxes. With typed symbols as evidence: 9 genuinely floating (9.2%), p13 exits 0. The 0.15 ceiling is unchanged and the floating nets are still reported with bboxes. |
| F10 | three live Register nodes for navigation lighting | **SURFACED, NOT RESOLVED.** Added to the engineer confirmation list as `cf-003`. Engo does not merge or pick unilaterally (Case A). |
| F11 | device TYPE never assigned in the tested path | **FIXED — the big one.** New `tools/symbol_typing.py` resolves each symbol instance against the confirmed bank by fingerprint, wired INTO `process_page`. p13: 159 symbols → **134 typed (84%)**, 25 flagged `unknown_shape` (never guessed). |

## Bug found while wiring F11 (not in the audit — found by running it)

**The symbol bank was unusable across processes.** `path_fingerprint` used
Python's built-in `hash()`, which is randomised per process for strings, so a
fingerprint written to the bank in one run could never match the same shape in
the next run. First live test: **0 of 159 symbols typed.** In the full-drive
run this would have silently produced zero typing on every sheet.
Fixed with `stable_hash` (blake2b over a canonical repr) + `-0.0` normalisation
(`repr(-0.0) != repr(0.0)` while their hashes are equal, which split 136
clusters into 137). Rebuild verified **identical**: 136 clusters, same instance
counts, same example bboxes — so the engineer's red-pen maps 1:1 onto the new
fingerprints and was re-applied without re-asking him anything.

**Also found by running the real dispatcher:** `plan.json` matches the
`p*.json` glob and crashed the lint's sort key. Fixed at every consumer.

## The engineer's never-assume rule, enforced in code

`symbol_typing.VERIFY_RULES` marks types whose meaning the SHAPE alone cannot
settle. A ganged breaker carries `verify_required` + what to verify: *"follow
the two conductors: +/- (DC poles) or L/N (AC) — determined by what they
connect to, never assumed"*. Live on GM p2: 27 ganged breakers flagged for
conductor verification rather than assumed. Same mechanism carries the XA
arrow-direction rule (measure vs command) and DC-vs-AC motor supply.
