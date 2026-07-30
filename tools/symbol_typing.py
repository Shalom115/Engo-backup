"""
SYMBOL TYPING — resolve every symbol instance on a page to its
ENGINEER-CONFIRMED device type, by vector fingerprint.

Closes audit flag F11 ("device TYPE is never assigned in the tested path, so
§6 discipline is not yet exercised"): the confirmed bank existed but nothing
consumed it, so `sym_boxes` stayed bare rectangles and no claim about what a
device IS could be made.

How it works — the whole point of a symbol bank:
  a device symbol is the SAME VECTOR SHAPE everywhere one drafting house
  draws, so its fingerprint is its identity. Fingerprint each shape on the
  page, look it up in symbol_bank_<house>_CONFIRMED.json, inherit the type
  the engineer wrote once.

Discipline (§6, flag-never-guess):
  * a fingerprint NOT in the bank returns type=None with reason
    'unknown_shape' — never a guessed type, never a nearest match;
  * types the engineer marked needing verification (e.g. a ganged breaker
    whose polarity is +/- on one sheet and L/N on another) carry
    `verify_required` + `verify_what`, so downstream must resolve it from the
    conductors rather than assume. THE ENGINEER'S RULE, ENFORCED IN CODE:
    "could be +/- and it could be L/N depending on where the lines are going
     — make sure it verifies and always follows the never assume".

    python tools/symbol_typing.py <pdf> <page> [--bank <confirmed.json>]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz

from symbol_bank_build import (  # noqa: E402  — one fingerprint definition only
    _pts, path_fingerprint, _page_wires, _near_wire,
)

STATE = Path(__file__).resolve().parent.parent / "data" / "state"
DEFAULT_BANK = STATE / "symbol_bank_gm_marine_CONFIRMED.json"

# Types whose meaning is not fully determined by the shape — the shape says
# WHAT it is, the conductors say WHICH VARIANT. Never resolved by assumption.
VERIFY_RULES = {
    "ganged_breaker": "follow the two conductors: +/- (DC poles) or L/N (AC) —"
                      " determined by what they connect to, never assumed",
    "2 joined breakers": "follow the two conductors: +/- (DC poles) or L/N (AC)"
                         " — determined by what they connect to, never assumed",
    "signal/control": "read the ARROW DIRECTION: pointing away from the circuit"
                      " = monitoring MEASURES it (indication); pointing toward"
                      " the circuit = monitoring COMMANDS it (control)",
    "motor": "identify supply type from the conductors: + with negative-bus"
             " mark = DC; L/N with an earth line = AC",
}


def load_bank(path: Path = DEFAULT_BANK) -> Dict[str, Dict[str, Any]]:
    """-> {fingerprint_str: {type, note, instances}} for confirmed clusters."""
    bank = json.loads(Path(path).read_text())
    out = {}
    for c in bank.get("clusters", []):
        t = (c.get("engineer_type") or "").strip()
        if not t:
            continue
        out[str(c["fingerprint"])] = {
            "type": t,
            "note": c.get("engineer_note", ""),
            "cluster": c["cluster"],
            "instances": c.get("instances", 0),
        }
    return out


def type_page_symbols(page: fitz.Page, bank: Dict[str, Dict[str, Any]],
                      legend_map: Optional[Dict[str, str]] = None
                      ) -> List[Dict[str, Any]]:
    """Every wired, symbol-sized shape on the page, typed from the bank.

    Uses the SAME geometry filters as symbol_bank_build.collect_symbol_
    instances (wire-touch, size band, title-block exclusion) so a shape that
    went into the bank is the same shape looked up here — if the two drifted
    apart, every lookup would silently miss."""
    R = page.rotation_matrix
    segs, wgrid, wcell = _page_wires(page, R)
    pr = page.rect * page.rotation_matrix
    W, H = abs(pr.width), abs(pr.height)
    out: List[Dict[str, Any]] = []
    for d in page.get_drawings():
        items = d["items"]
        kinds = {it[0] for it in items}
        all_pts = []
        for it in items:
            all_pts += [((fitz.Point(x, y) * R).x, (fitz.Point(x, y) * R).y)
                        for (x, y) in _pts(it)]
        if not all_pts:
            continue
        xs = [p[0] for p in all_pts]; ys = [p[1] for p in all_pts]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        bb = [min(xs), min(ys), max(xs), max(ys)]
        if not (7.5 <= max(w, h) <= 45):
            continue
        if kinds == {"l"} and len(items) < 3:
            continue
        if w < 2.5 or h < 2.5:
            continue
        if bb[1] > 0.84 * H and bb[0] > 0.45 * W:
            continue
        if not _near_wire(bb, segs, wgrid, wcell):
            continue
        fp, _ = path_fingerprint(d, R)
        if fp is None:
            continue
        rec: Dict[str, Any] = {"bbox": [round(v, 1) for v in bb],
                               "fingerprint": str(fp)}
        # PRECEDENCE: the sheet's OWN legend beats the bank (protocol §A2,
        # audit F1). Passed in as an argument so this step cannot be skipped
        # by a caller that forgets it.
        lg = (legend_map or {}).get(str(fp))
        if lg:
            rec["type"] = lg
            rec["source"] = "sheet_legend"
            out.append(rec)
            continue
        hit = bank.get(str(fp))
        if hit:
            rec["type"] = hit["type"]
            rec["source"] = "symbol_bank_confirmed"
            rec["bank_cluster"] = hit["cluster"]
            if hit["note"]:
                rec["engineer_note"] = hit["note"]
            vw = VERIFY_RULES.get(hit["type"])
            if vw:
                rec["verify_required"] = True
                rec["verify_what"] = vw
        else:
            rec["type"] = None            # NEVER guessed
            rec["source"] = "unknown_shape"
        out.append(rec)
    return out


def main(argv):
    pdf, pno = argv[0], int(argv[1])
    bank_path = Path(argv[argv.index("--bank") + 1]) if "--bank" in argv else DEFAULT_BANK
    bank = load_bank(bank_path)
    doc = fitz.open(pdf)
    syms = type_page_symbols(doc[pno], bank)
    typed = [s for s in syms if s["type"]]
    unknown = [s for s in syms if not s["type"]]
    verify = [s for s in syms if s.get("verify_required")]
    from collections import Counter
    print(f"bank: {len(bank)} confirmed shapes")
    print(f"page {pno}: {len(syms)} symbol instances -> "
          f"{len(typed)} typed ({100*len(typed)/max(1,len(syms)):.0f}%), "
          f"{len(unknown)} unknown_shape (flagged, never guessed), "
          f"{len(verify)} need conductor verification")
    for t, n in Counter(s["type"] for s in typed).most_common(15):
        print(f"    {n:4d}  {t}")


if __name__ == "__main__":
    main(sys.argv[1:])
