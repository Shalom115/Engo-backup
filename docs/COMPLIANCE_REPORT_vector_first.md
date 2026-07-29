# COMPLIANCE REPORT — vector-first protocol vs the rules of record

Audit date 2026-07-28 · branch `vector-protocol-compliance` · **$0, no vision API calls, no Register writes.**
Checklist audited: `docs/COMPLIANCE_CHECKLIST_vector_first.md` (82 rules).
Subjects: `docs/AUDIT_vector_first_protocol_20260726.md`, `docs/PROTOCOL_vector_first_classes.md`,
and `tools/{vector_probe, vector_extract_poc, run_book_extract, glyph_font_decode, electrical_lint, routing_preview, symbol_bank_build, probe_corpus}.py`.

---

## SUMMARY

| | count |
|---|---:|
| Rules checked | **82** |
| PASS | **40** |
| FLAG | **15 rows → 11 distinct findings** |
| N/A | **27** |

Counts are machine-counted from the verdict table at the foot of this document, not estimated.
15 rule-rows carry a FLAG because several findings bind more than one rule — F7 covers MS-3-b and
REV-GATE; F8 covers RP-2, RP-14, RP-15 and (related) EP-B3, EP-B8; F10 covers EP-D6 and RP-12.

**The three historically-violated rules all PASS.**
- **GOLD-BLIND (MS-0.5-b / P2-2): PASS.** Grep of all 8 extraction-path tools for
  `157B7122|157B6203|157B5111|11166832|LAZARETTE|FWD BILGE|PVG ?32|Danfoss|XA40|T/S B`
  → **grep exit 1, zero matches**. Word-bounded `\bQ13\b|\bRe1\b|\bXA[0-9]{2}\b` → **exit 1, zero matches**.
  The only ID patterns present are grammar shapes, which the rule explicitly permits:
  `routing_preview.py:34` `^(Q\d+|QE\d+|F\d+|CB\d+\.?\d*|SW\s?\d+)\s+(\d+\s?A)\b` and
  `electrical_lint.py:41` `\b(Q\d+|QE\d+|F\d+|CB\d+|Re\s?\d+|SW\s?\d+|CT\s?\d+|T/S\s?[A-Z])\b`.
- **NO-FABRICATION (EP-B1 / MS-6): PASS.** `glyph_font_decode.py:195` emits `"?"` for an unknown
  glyph signature; docstring l.21-22 "unknown signature -> '?' (never guessed)"; l.170 `continue  # never force-align`;
  l.211 "(count mismatch, never forced)". `symbol_bank_build.py` classify prompt: "If genuinely unclear,
  return 'unknown' — never guess." `electrical_lint.py` L6 surfaces device ids below conf 70 as untrusted.
- **WRITE-HOLD: PASS.** No tool imports `node_write`, constructs a writer, or passes `dry_run=False`
  (grep for `register_gelliceaux|node_write|NodeWriter|dry_run|ComposeWriter` returns only
  `routing_preview.py:42`, which is `.read_text()` — read-only). All writes are confined to the
  caller-supplied out-dir or `data/state/`. `routing_preview.py:119` prints
  `"-> …/routing_preview.md (red-pen) — NO WRITES PERFORMED"`, **confirmed in the live run below**.

### The 11 FLAGs

**F1 — LEGENDS-FIRST is absent from the vector path, while the audit claims it survives. (EP-A2)**
Audit §4 asserts: *"**What survives untouched:** legends-first (now read via the $0 label path)"*.
Grep for `legend` across all 8 tools returns exactly one hit — a comment in `electrical_lint.py:15`
("or a legend/table cell"). No tool calls `legend_first`, and no tool orders legend reading before
symbol interpretation. PROTOCOL §A.2 requires: *"`legend_first.from_pdf` reads the sheet's OWN
legends/tables before any symbol. The sheet's legend OVERRIDES the general glossary."*
This is the same failure shape as the fused-tiles arm, where legends-first lived in the caller and
was silently dropped — recorded in this repo two days ago.

**F2 — Switches are routed as if they were supplies. (ROUTE-2 CONTROL≠INDICATOR≠SUPPLY)**
`routing_preview.py:33-35` matches `SW\s?\d+` in the same device-row regex as `Q/QE/F/CB`, then
line 89 takes the remaining text as the load: `load_txt = m.group(3).strip() if m and m.group(3).strip() else txt`.
A switch is a CONTROL element, not a protective device feeding a load. CLAUDE.md: *"every panel element
is one of {control, indicator/status, supply} … ingesting indication as control is a wrong relationship."*
Nothing in the preview distinguishes the three roles.

**F3 — The preview claims writer-fidelity it does not have. (MS-9e / ID-GATE)**
`routing_preview.py:8` docstring: *"using EXACTLY the resolution order the real writer uses"*.
The real order (PROTOCOL §C) is **load map → §9e semantic matcher → create_flagged**. The preview's
actual order (`propose()`, l.47-70) is load-map-exact → non-node-disposition → load-map-containment →
**register-name whole-word containment** → UNRESOLVED. The §9e matcher is never invoked; a substring
match on a Register name is a weaker and differently-behaved test. Preview proposals may therefore
differ from what the writer would do — which defeats the stated purpose of diffing the real write
pass against the approved preview.

**F4 — Docstring order ≠ code order in the same function.** `routing_preview.py:48-50` says
*"map exact -> map containment -> non-node disposition -> register-name"*; the code checks non-node
(l.59) **before** containment (l.62). Documentation defect only; behaviour is the code's.

**F5 — Audit §5c label numbers are not reproducible from the shipped runner. (STD-2)**
Audit §5c claims for p13: *"344 label boxes (incl. 14 vertical) … 330/344 OCR non-empty; 163 word-confidence ≥70 …
**325/344 labels attached**"*. Re-running the shipped `tools/run_book_extract.py` on the same page today:
`"labels": 235, "ocr_nonempty": 200, "ocr_conf70": 100, "attached": 225`.
The **geometry** numbers in the same paragraph reproduce **exactly** (`wires 810, nets 355, sym_boxes 309, dots 1486`),
so this is specific to the label stage — the POC's `__main__` and the runner evidently cluster labels
differently. Under STD-2 the published numbers must be the ones the shipped path produces.

**F6 — `tools/symbol_bank_worksheet.py` does not exist.** It is named in the audit scope; `ls` of
`tools/` returns 11 files and this is not among them. Nothing to audit; flagged as a scope/inventory gap.

**F7 — No revision/supersession check anywhere in the vector chain. (REV-GATE)**
PROTOCOL §C: *"Revision gate: facts from a superseded drawing id are refused outright."* Neither
`probe_corpus.py`, `run_book_extract.py` nor `routing_preview.py` consults `revision_index_<vessel>.json`.
Today this is contained because nothing writes — but the preview will happily propose routings from a
superseded sheet, and the preview is intended to become the fixture the real write pass is diffed against.

**F8 — Three engineer symbol conventions are absent from the symbol-bank vocabulary. (RP-2, RP-14, RP-15)**
`symbol_bank_build.py` `iec_vocab` (l.~218-231) does include `wire_gauge_diamond`, `junction_dot`,
`plug_pin`, `connector`, `meter_gauge`, `not_a_device_annotation` — covering RP-1, RP-7, RP-16. It has
no member for: the **dotted-line rectangle = confined box/enclosure** (RP-2), the **multi-core cable**
(RP-14, which the engineer explicitly asked to be made a general rule: *"[ENGINEER: make a general rule,
pass for approval]"*), or the **terminal with a built-in fuse** (RP-15, *"a rectangle containing another
rectangle with a line across it"*). A symbol the vocabulary cannot name will be classified `unknown` at best.

**F9 — Both reference sheets HARD-FAIL the protocol's own lint gate.** Real output below:
p13 `L1_net_isolated=40 (frac 0.408)`, p19 `L1_net_isolated=60 (frac 0.571)` against the
`HARD_ISOLATED_FRAC = 0.15` ceiling; `hard_fail=True` on both; **real process exit code 1**.
Per the lint's own docstring these are *"EXTRACTION defects (or genuine drawing anomalies)"*. The
protocol's Phase-2 gate (audit §7: *"GATE: engineer eyeballs the overlays"*) has not been passed by
the two sheets the audit nominates for it.

**F10 — Three distinct Register nodes for navigation lighting, all live. (EP-D6 / RP-12)**
Not a tool defect — a data finding surfaced by auditing the router. `load_map_gelliceaux_001.json`
maps `NAVIGATION LTS → 690-lts-navigation`, `NAV. LIGHTS → 690-lts-nav-em`, and
`PORT/STBD/STERN/AUX NAV. LT.` + `STEAMING LT. 1/2` → `690-navigation-lights`. All three ids exist
and are un-retired in the Register. The engineer's rule is singular: *"NAV LIGHTS must be SEPARATED
from the rest of the lights — nav lights are a NODE OF THEIR OWN"*. Which of the three is the node
is an engineer decision; the preview will route by whichever string matches first.

**F11 — Device TYPE is never assigned in the tested path, so §6 discipline is not yet exercised. (MS-6)**
`run_book_extract.py` emits `sym_boxes` as bare `[x0,y0,x1,y1]` rectangles with no type. Typing is
deferred to `symbol_bank_build.py --classify`, which is opt-in and was not run (it is the only tool in
the set that calls a vision provider — `symbol_bank_build.py:234`). Consequence, measured in Part D:
`Q13 10A` and `F3 60A` are read as *text* but nothing in the output asserts breaker-vs-fuse. The
device-discipline rule is therefore neither honoured nor violated by the current chain — it is
**unimplemented downstream of the tested stages**, and the audit's cost model books symbol typing at
"~$1-3 once per book" without that stage having been run on these sheets.

---

## PART C — 2-SHEET TEST RUN (real dispatch path)

Sheets located in `data/state/gm_book_manifest.json`: **p13 = GMMS 108'-111a EMERGENCY SUPPLY RADIO/NAV./LTS**,
**p19 = GMMS 108'-114a BILGE SYSTEM**. Book downloaded from Drive id `1YAmYWTTes5AD7NGLCGXRG86OENBH22Pl`
(read-only SA connector, 3× retry): `downloaded 6,666,273 bytes -> /tmp/GM_book.pdf`.
Dependency: `tesseract 5.5.3 / leptonica-1.87.0` installed via `brew install tesseract`; `python3.12`
already carried `fitz` + `PIL` (system `python3` is 3.9.6 and does not — the project interpreter was used).

**1. `run_book_extract.py` — verbatim output**
```
{"page": 13, "ok": true, "secs": 3.2, "wires": 810, "nets": 355, "sym_boxes": 309, "dots": 1486, "labels": 235, "ocr_nonempty": 200, "ocr_conf70": 100, "attached": 225}
{"page": 19, "ok": true, "secs": 1.6, "wires": 712, "nets": 362, "sym_boxes": 269, "dots": 780, "labels": 86, "ocr_nonempty": 80, "ocr_conf70": 37, "attached": 84}
```

**2. `glyph_font_decode.py` — verbatim output**
```
TRAIN (even pages): 0 labels aligned, 0 skipped (count mismatch, never forced) -> font table 0 signatures
OUT-OF-SAMPLE (odd pages, vs tesseract conf>=85): 0/0 exact agreement (0.0%)
decode coverage all pages: {'partial_decode': 279, 'vertical_skipped': 36, 'no_glyphs': 6}
```
Both test pages are **odd** (13, 19) and the decoder trains on even pages, so the font table is empty
and every label is `partial_decode`. Reported as printed; nothing tuned. The 0.0% is a consequence of
the 2-page selection, not a measurement of the decoder.

**3. `electrical_lint.py` — verbatim output, real exit code 1**
```
{
 "pages": 2,
 "hard_fail_pages": [13, 19],
 "total_L1_isolated_nets": 100,
 "total_L2_symbol_orphans": 85,
 "total_L3_unattached_labels": 12,
 "total_L4_low_conf_labels": 143,
 "total_L6_untrusted_ids": 8
}
```
Per page: p13 `L1=40 (frac 0.408) L2=44 L3=10 (frac 0.05) L4=100 hard_fail=True`;
p19 `L1=60 (frac 0.571) L2=41 L3=2 (frac 0.025) L4=43 hard_fail=True`. See F9.

**4. `routing_preview.py` — verbatim output**
```
rows 61: proposed 24, unresolved 37; via {'load_map_exact': 10, 'register_name': 2, 'load_map_contain': 12}
-> /tmp/test2_dec/routing_preview.md (red-pen) — NO WRITES PERFORMED
```
**"NO WRITES PERFORMED" confirmed present in the output.**

---

## PART D — POST-HOC GOLD CHECK (fixture opened only after Part C)

Source: `tests/gold_fixtures_gelliceaux.json` → `gold_2_bilge_node.device_typing`, compared against
`/tmp/test2_dec/p19.json`. No tool was edited.

| Fixture claim | Verdict | Actual extracted element |
|---|---|---|
| `Q13`: breaker (10A, BILGE VALVES feed) | **PARTIAL** | `'Q13 10A'` conf 82.0, `attach=['symbol', 263]`; `'BILGE VALVES'` conf 96.5 read separately. Id + rating exact; **type "breaker" never asserted** (see F11). |
| `T/S B`: terminal strip | **PARTIAL** | `'T/S B'` conf 91.8, `attach=['net', 251]`. String exact; type not asserted. |
| `Re1-Re6`: relay | **PARTIAL (4/6 clean)** | `'Re2'` 91.5, `'Re3'` 91.1, `'Re4'` 89.2, `'Re6'` 89.7 — all net-attached. `'Rel'` 83.3 (Re1, l/1 confusion) and `'Red'` 84.4 (Re5) are misreads. Re5 never appears correctly. |
| `XA10[04]`, `XA40[12/14/16]`: ONYX status signal — NOT power | **MISS (as a typing claim)** | Ids partially read: `'XA10 <'` 76.2, `'XA11'` 90.0, `'XA1'` ×2, `'XA4('` ×3, plus orphan `'14]'` 77.2 / `'16]'` 74.0 — the bracketed index is split into a separate label. **Nothing in the output classifies them as status-vs-power**; that determination does not exist in this chain. |
| (bonus) `F3`: fuse 60A | **PARTIAL** | `'F3 60A'` conf 73.6. Id + rating exact; type not asserted. |

Also read cleanly on p19 and worth noting as real signal: `'MAIN BILGE PUMP'` 93.7, `'+24V SERVICE BAT.'` 93.9,
`'F2 200A'` 92.1, `'SO 6'` 95.5, `'not used'` 96.6.

**Honest reading:** the deterministic stages recover the *identifiers* on this sheet well — every fixture
device id except Re5 is present, most above conf 80, and 84/86 labels attached to a net or symbol. What is
absent is the *typing* layer: not one fixture claim about **what a device IS** can be confirmed from this
output, because the symbol bank was never run. That is a gap in what has been built, not a failure of what was run.

---

## FULL VERDICT TABLE

### Master Spec v2
| ID | Verdict | Basis |
|---|---|---|
| MS-0.5-a | PASS | Probe/extract report discovered counts; no target values anywhere in the tools. |
| MS-0.5-b | PASS | Gold-token grep exit 1 across all 8 tools (see Summary). |
| MS-0.5-c | PASS | `tests/gold_fixtures_gelliceaux.json` read only in Part D, after extraction; no tool references it. |
| MS-0.5-d | PASS | `probe_corpus.classify_pdf_bytes` counts pages/classes from the file; `run_book_extract` reports measured counts. |
| MS-0.5-e | PASS | No zone or function name is hardcoded in any tool. |
| MS-0.5-f | N/A | This audit is the structure-discovery report; no pass/fail claim is made on discovery reasoning here. |
| MS-2-a | N/A | Multi-source cross-reference is a routing-layer behaviour; the vector chain produces one source. |
| MS-2-b | N/A | Authority priors apply at fact-write time; nothing is written. |
| MS-3-a | PASS | `probe_corpus.classify_pdf_bytes` records `text_layer_chars` per page and classes A1_vector/A1_hybrid/A2_raster; `PROTOCOL_vector_first_classes.md` §0 routes on it. |
| MS-3-b | FLAG (**F7**) | No supersede check in the chain. |
| MS-3b | N/A | No part-number search is performed by any tool. |
| MS-4 | PASS | Crops are rendered *from vector* at `OCR_ZOOM` (`vector_extract_poc.py`), so the §4 raster ceiling does not bind; `get_pixmap(clip=)` deliberately avoided (l.24, l.351). |
| MS-5 | N/A | Cross-drawing assembly is out of scope of the per-sheet extractor (audit §6 states this limit explicitly). |
| MS-6 | FLAG (**F11**) | Typing stage not implemented in the tested chain. Where typing *does* exist (`symbol_bank_build` classify prompt) the discipline text is present and correct. |
| MS-9d | PASS (partial scope) | Every label carries `bbox`; nets carry `bbox`; page + rotation recorded per page. No fact is emitted, so authority/confidence/as_of are not yet applicable. |
| MS-9e | FLAG (**F3**) | §9e matcher bypassed in the preview. |
| MS-9g | N/A | No manual linking in this layer. |
| MS-9i | N/A | Corrections log belongs to the vision/describe path. |
| MS-10 | PASS | Gold fixtures used post-hoc only (Part D), diff-and-report, no tuning. |
| MS-12 | PASS | All tools are single-shot CLI runs; `run_book_extract`/`probe_corpus` are ledgered and resumable. |

### Standing rules
| ID | Verdict | Basis |
|---|---|---|
| STD-1 | PASS | `PROTOCOL_vector_first_classes.md` §0 is a table of *measured* probe verdicts on five real files; audit §5b/§5c document renders before design. |
| STD-2 | FLAG (**F5**) | Audit §5c label numbers not reproducible from the shipped runner. |
| STD-3 | PASS | This audit ran the shipped CLIs end-to-end, not a shortcut; the lint exit code was captured from the process, not from a pipe. |
| STD-4 | PASS | `probe_corpus._download_with_retry` re-raises after 4 attempts; `run_book_extract` records `ok:false` per page rather than silently skipping. |
| STD-5 | N/A | No vision-output arrays consumed in the tested chain (`symbol_bank_build --classify` not run). |
| STD-6 | PASS | `electrical_lint` is the machine gate and it *failed* the two sheets rather than passing them quietly; `vector_probe.ink_hit_rate` prints `"FAILED — DO NOT TRUST THIS OVERLAY"` below 0.90 (l.191). |
| STD-7 | PASS | `run_book_extract` ledger l.188; `probe_corpus` ledger l.127 with resume-skip l.105-111. |

### Identity / routing / node rules
| ID | Verdict | Basis |
|---|---|---|
| ID-GATE | PASS (by abstention) | No node writer exists in this chain; the preview proposes only. But see F3 — the preview's stand-in for §9e is weaker than the writer's. |
| REV-GATE | FLAG (**F7**) | — |
| ROUTE-1 | PASS | `routing_preview.propose` checks `non_node_dispositions` (l.59-60) and emits `"NON-NODE (feeder/distribution)"`. 22 dispositions loaded. |
| ROUTE-2 | FLAG (**F2**) | — |
| ROUTE-3 | N/A | No hydraulic control map is consulted anywhere in the vector chain. |
| ROUTE-4 | PASS (by abstention) | Structural elements are not routed; unmatched labels become `UNRESOLVED` (37 of 61 rows in the live run) rather than being forced. |
| CASE-AB | N/A | No identity resolution or node splitting occurs. |
| EQ-ACT | N/A | No node creation. |
| PER-INST | N/A | No node creation. |
| SFI-OCC | N/A | No SFI allocation. |
| FLAG-NG | PASS | `UNRESOLVED` is emitted rather than a guess (l.100-102); `propose` returns `None` for furniture and short fragments (l.53-56). 37/61 rows unresolved in the live run — the tool declines rather than reaches. |
| PROV | PASS (partial scope) | `bbox` on every label and net; `page` + `rotation` per record. Full fact provenance N/A until facts exist. |
| CONF-LIST | N/A | No confirmation-list interaction in this layer. |

### Electrical protocol A–F
| ID | Verdict | Basis |
|---|---|---|
| EP-A2 | FLAG (**F1**) | — |
| EP-A3 | N/A | Sub-type classification is a vision-reader concern; the vector chain reads the whole page uniformly. |
| EP-A4 | PASS | Coverage is inherent: `extract_primitives` walks every path on the page, so there is no tiling blind spot to guarantee against — the RC1 defect the audit set out to remove. |
| EP-A5 | N/A | No crop-then-enrich merge in this chain. |
| EP-B1 | PASS | Decoder `'?'` path; `unknown` in the classify vocabulary. |
| EP-B2 | PASS (vocabulary) | `wire_gauge_diamond` and `not_a_device_annotation` are members of `iec_vocab`. Not yet exercised (F11). |
| EP-B3 | FLAG (**F8**, related) | No `harness_connector` distinct from `connector`/`plug_pin` in the vocabulary; the plug-vs-switch trap is not explicitly encoded. |
| EP-B4 | PASS (vocabulary) | `breaker` present; "ISOLATOR = breaker" is a naming rule for the LLM stage, not the geometry stage. |
| EP-B5 | PASS (vocabulary) | `current_transformer` present. |
| EP-B6 | PASS (vocabulary) | `breaker` present; earth-leak routing is a router rule (EP-D5). |
| EP-B7 | N/A | "The wire is the test" requires wire↔element association at typing time; not reached. |
| EP-B8 | FLAG (**F8**, related) | Sheet-scoped vocabulary (CBx = retractable fuse on 110b/d/e) is nowhere in the chain; `routing_preview`'s `CB\d+\.?\d*` treats every CBx as a device row identically on every sheet. |
| EP-D1 | N/A | Node hierarchy is a writer concern. |
| EP-D2 | N/A | Pin→plug-owner resolution not implemented in this chain. |
| EP-D3 | N/A | Handled by load-map content, not by these tools. |
| EP-D4 | N/A | Cross-links not produced. |
| EP-D5 | N/A | Not reached. |
| EP-D6 | FLAG (**F10**) | Three live nav-lighting nodes; rule is singular. |
| EP-D7 | PASS | `non_node_dispositions` is consulted and reported as its own `via` category — "disregard" is a first-class outcome, not a dropped row. |

### Red-pen rules
| ID | Verdict | Basis |
|---|---|---|
| RP-1 | PASS (vocabulary) | `wire_gauge_diamond` in `iec_vocab`. |
| RP-2 | FLAG (**F8**) | No enclosure/confined-box member. |
| RP-3 | N/A | CAN-bus typing requires signal semantics; not reached. |
| RP-4 | FLAG (**F8**, related) | See EP-B3. |
| RP-5 | PASS (vocabulary) | `breaker` present. |
| RP-6 | PASS (vocabulary) | `fuse` present. |
| RP-7 | PASS (vocabulary) | `plug_pin` and `connector` present. |
| RP-8 | N/A | Load-map content, not tool behaviour. |
| RP-9 | PASS | Sub-panels resolve via `non_node_dispositions`. |
| RP-10 | N/A | Earth-leak attachment is a writer rule. |
| RP-11 | PASS (vocabulary) | `current_transformer` present. |
| RP-12 | FLAG (**F10**) | — |
| RP-13 | PASS | See EP-D7. |
| RP-14 | FLAG (**F8**) | Multi-core cable absent from the vocabulary despite the engineer's explicit "make a general rule". |
| RP-15 | FLAG (**F8**) | Terminal-with-built-in-fuse absent. |
| RP-16 | PASS (vocabulary) | `meter_gauge` present; gauges are nameable as non-nodes. |
| RP-17 | N/A | Per-installation node creation not in this layer. |
| RP-18 | PASS (capability) | Relay loops are exactly what the netlist makes walkable; audit §5d shows the intended `power_path` graph walk. Not exercised on these sheets. |

### Phase-2 invariants
| ID | Verdict | Basis |
|---|---|---|
| P2-1 | PASS | The single vision import is `symbol_bank_build.py:234` `from providers.vision import get_vision_provider` — through the provider layer, no vendor SDK. |
| P2-2 | PASS | See gold-blind result. |
| P2-3 | PASS | Vessel facts read from `data/state/*_gelliceaux_001.json`; only `probe_corpus.py:43` pins `VESSEL = "gelliceaux_001"` as a module constant (configuration, not a fact). |
| P2-4 | PASS | Fixtures live in `tests/`, referenced by no tool. |
| P2-5 | N/A | No manual acquisition here. |

---

## STATUS

**Awaiting engineer review of 11 flags.** Nothing was repaired: per the task's terms this audit flags
and stops. F1 (legends-first), F2 (switch-as-supply) and F3 (§9e bypass) are the three I would put in
front of you first — each one changes what the routing preview proposes, and the preview is the artifact
the real write pass is meant to be diffed against.
