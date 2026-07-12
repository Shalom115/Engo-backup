---
name: verify-gate
description: Verify an Engo/Gelliceaux extraction or routing pass ACTUALLY worked — reconcile every element against the flagged list, split outcomes honestly, and disposition every "lost" item by rendering it. Use after any re-extraction or re-route, before reporting anything as done. "Clean" here means verified, not "the script didn't crash."
---

# Verify gate

The discipline that turns "it ran" into "it's correct." The engineer forced this after
catching progress updates that meant only "didn't crash." Read `engo-orient` first.

## The core split (never collapse these into one number)

Run `pipeline.compare_reextraction` (whole book) or `pipeline.verify_page_live` (one
page / `--follow N` live). Every flagged item lands in exactly one bucket:

- **unanimous_retype** — every new read of that id has a DIFFERENT type. A real fix.
- **same** — re-read with the same type. Sub-split: items whose new label carries a
  glossary-trap keyword (isolator/gauge/DWG/junction-tap/caption) are SUSPECTS for the
  engineer; the rest are correctly-typed-but-unresolvable (a Register/load-map gap, NOT
  an extraction miss).
- **multi-instance** — same id read with BOTH the old and other types. NOT a win: either
  several physical parts share the id, or grid tiles double-detected one part. Routes
  with per-instance provenance; never counted as "retyped."
- **lost** — no new reading found (exact-id match first, then token fallback).

## Rules that keep the numbers honest

1. **Exact-id match FIRST, token overlap only as fallback.** A token-overlap-only
   matcher false-negatives on bare short ids ("SW1") — it will call present items
   "lost." (This inflated an early "58% retyped" that was really 99% accounted-for.)
2. **"same-type" is NOT automatically "correct."** Scan ALL same-type items for
   glossary-trap keywords programmatically; don't eyeball 10 and extrapolate.
3. **Every "lost" item is dispositioned INDIVIDUALLY by rendering the region** —
   `rasterize_pdf_page` + view. Labels lie: CP-SW looked like a "lost switch" but the
   drawing showed the old read had typed a real PUMP as a switch (a fix), while another
   "lost" was a genuine wired element the new read dropped (a real loss → carry forward).
   Only the rendered drawing separates improvement from regression.
4. **Multi-instance is a routing concern, not a failure** — surface it, provenance it.
5. **Carry forward genuine losses** with a provenance flag (`_carried_from_batch2a`,
   `_carry_reason`), never silently drop.

## What a PASS looks like

`compare_reextraction` over the flagged set: report unanimous / same(+suspects) /
multi-instance / lost as counts AND percentages. A pass = every `lost` individually
dispositioned (improvement vs named-uncertainty), 0 wrong-attaches (guaranteed by
flag-never-guess), suspects listed for the engineer. The 39-page GM final gate:
1,134 retyped (54%) / 772 same (37%, 48 suspects) / 168 multi-instance / 9 lost (all
dispositioned). That shape is the target.

## Live monitoring during a burn
`Monitor` tailing `pipeline.verify_page_live --follow <start_line>` — pure-Python ledger
follow (NOT `tail | echo | python` — shell echo mangles JSON escape chars, learned the
hard way). Emits `p<N> <drawing>: VERIFIED|CHECK (n lost) — flagged X: retyped.../lost N`
per page. Every `CHECK` gets investigated, not glossed.

## Anti-fabrication rule (absolute)
Before writing ANY "run completed / passed / graded" claim, RE-READ the actual tool
output and quote real numbers from it. Never reconstruct a plausible result from what a
run was expected to produce. A fabricated "Gold-#2 PASSED" entry is a permanent scar in
this project — it was written from expectation, not output, and had to be retracted.
