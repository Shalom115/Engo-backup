"""
RE-EXTRACTION COMPARISON GATE (v3 — Fable audit 2026-07-11).

Reconciles every flagged switch/status_signal item against the batch-3
re-extraction, with the two honesty fixes the v2 script lacked:

  UNANIMOUS  — every new reading of that id has a DIFFERENT type (real retype)
  CONFLICTED — the id was read with BOTH the old type and other types. NOT
               counted as a win: either several distinct physical elements
               legitimately share the id (L1 appears as bus-tap AND terminal),
               or overlapping grid tiles double-detected one part and typed it
               inconsistently. Id-level matching cannot tell these apart —
               these rows go to the routing layer with per-instance provenance,
               not into the success column.
  SAME       — read again with the same type. Sub-split: entries whose new
               label carries a glossary-trap keyword (isolator/gauge/DWG/…)
               are listed as SUSPECT for engineer eyes; the rest are
               correctly-typed-but-unresolvable (a Register/load-map gap, not
               an extraction miss).
  LOST       — no new reading found (exact-id first, token fallback).

Run: PYTHONPATH=. python3.12 -m pipeline.compare_reextraction
"""
from __future__ import annotations

import collections
import json
import re

_TRAPS = re.compile(
    r"diamond|wire gauge|gauge callout|see dwg|isolator|junction/tap|caption|heading", re.I)


def _toks(s):
    return set(t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if t)


def _nid(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def run() -> dict:
    flagged = json.load(open("data/state/flagged_electrical_gelliceaux_001.json"))[
        "create_flagged_entries"]
    new_pages = {}
    for l in open("data/ledgers/batch3_reextract_ledger.jsonl"):
        if l.strip():
            r = json.loads(l)
            new_pages[r["page"]] = r

    tot = collections.Counter()
    suspects = []
    per_page = []
    for pidx, new in sorted(new_pages.items()):
        els = [e for e in (new.get("wiring_elements") or []) if isinstance(e, dict)]
        by_id = collections.defaultdict(list)
        for e in els:
            by_id[_nid(e.get("id"))].append(e)
        pf = [e for e in flagged
              if e["page"] == pidx + 1 and e["element_type"] in ("switch", "status_signal")]
        c = collections.Counter()
        for f in pf:
            cands = by_id.get(_nid(f.get("element_id")), [])
            if not cands:
                ftoks = _toks(f.get("element_id")) | _toks(f.get("label"))
                best, bo = None, 0
                for e in els:
                    ov = len((_toks(str(e.get("id"))) | _toks(e.get("label"))) & ftoks)
                    if ov > bo:
                        best, bo = e, ov
                cands = [best] if best is not None and bo >= 2 else []
            types = set(x["element_type"] for x in cands)
            if not cands:
                c["lost"] += 1
            elif f["element_type"] not in types:
                c["unanimous_retype"] += 1
            elif len(types) > 1:
                c["conflicted"] += 1
            else:
                c["same"] += 1
                for x in cands:
                    if _TRAPS.search(x.get("label") or ""):
                        suspects.append({"page": pidx, "id": f.get("element_id"),
                                         "type": x["element_type"],
                                         "label": (x.get("label") or "")[:70]})
                        break
        tot.update(c)
        per_page.append((pidx, new.get("drawing_no"), len(pf), dict(c)))

    print(f"{'page':5s} {'drawing':17s} {'flagged':>7s}  breakdown")
    for pidx, dwg, n, c in per_page:
        print(f"{pidx:<5d} {str(dwg):17s} {n:7d}  {c}")
    total = sum(tot.values())
    print(f"\nTOTALS over {len(per_page)} pages ({total} flagged items):")
    for k in ("unanimous_retype", "same", "conflicted", "lost"):
        print(f"  {k:17s} {tot[k]:5d}  ({tot[k]/total*100:.0f}%)" if total else "")
    print(f"\nSUSPECT same-type rows (glossary-trap keyword in new label — engineer eyes): {len(suspects)}")
    for s in suspects[:15]:
        print(f"   p{s['page']:<3d} {str(s['id'])[:16]:16s} {s['type']:14s} {s['label']}")
    return {"totals": dict(tot), "suspects": suspects, "pages": len(per_page)}


if __name__ == "__main__":
    run()
