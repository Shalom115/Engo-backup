"""Per-page live verification for the batch-3 burn: given one ledger page,
reconcile that page's flagged items and print a one-line verdict.
Used by the verification Monitor (tail ledger -> verdict per page)."""
from __future__ import annotations

import collections
import json
import re
import sys

_TRAPS = re.compile(
    r"diamond|wire gauge|gauge callout|see dwg|isolator|junction/tap|caption|heading", re.I)


def _toks(s):
    return set(t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if t)


def _nid(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def verdict(rec: dict, flagged: list) -> str:
    els = [e for e in (rec.get("wiring_elements") or []) if isinstance(e, dict)]
    by_id = collections.defaultdict(list)
    for e in els:
        by_id[_nid(e.get("id"))].append(e)
    pf = [e for e in flagged
          if e["page"] == rec["page"] + 1 and e["element_type"] in ("switch", "status_signal")]
    c = collections.Counter()
    suspects = 0
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
            c["retyped"] += 1
        elif len(types) > 1:
            c["multi"] += 1
        else:
            c["same"] += 1
            if any(_TRAPS.search(x.get("label") or "") for x in cands):
                suspects += 1
    status = "VERIFIED" if c["lost"] == 0 else f"CHECK ({c['lost']} lost)"
    return (f"p{rec['page']} {rec.get('drawing_no')}: {status} — flagged {len(pf)}: "
            f"retyped {c['retyped']}, same {c['same']} ({suspects} suspect), "
            f"multi-instance {c['multi']}, lost {c['lost']}")





def follow(start_line: int = 0, poll_s: int = 60) -> None:
    """Follow the ledger from start_line, printing one verdict per new page.
    Pure-Python file tailing — no shell line-splitting/escaping pitfalls."""
    import time
    flagged = json.load(open("data/state/flagged_electrical_gelliceaux_001.json"))[
        "create_flagged_entries"]
    seen = start_line
    while True:
        try:
            lines = open("data/ledgers/batch3_reextract_ledger.jsonl").read().splitlines()
        except FileNotFoundError:
            lines = []
        for ln in lines[seen:]:
            if not ln.strip():
                continue
            try:
                print(verdict(json.loads(ln), flagged), flush=True)
            except Exception as e:  # noqa: BLE001 — verdict failure is an event, not a crash
                print(f"VERDICT-ERROR: {e}", flush=True)
        seen = len(lines)
        time.sleep(poll_s)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--follow":
        follow(start_line=int(sys.argv[2]) if len(sys.argv) > 2 else 0)
    else:
        flagged = json.load(open("data/state/flagged_electrical_gelliceaux_001.json"))[
            "create_flagged_entries"]
        rec = json.loads(sys.stdin.read())
        print(verdict(rec, flagged))
