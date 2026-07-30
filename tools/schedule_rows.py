"""
SCHEDULE ROW ASSEMBLY — rebuild `[device][rating] -> [LOAD]` rows from the
individual labels the geometry pass produces.

WHY THIS EXISTS (found 2026-07-30 by running registry_proposal on a real
sweep and reading its output: 225 of 225 proposed facts came back as
`appears_on_drawing` and ZERO as `electrical_supply`). The vision-era
extractor read a schedule REGION and returned assembled rows. The vector
extractor is more accurate but lower-level: it returns `Q45__ 10A` and
`RADAR SYSTEM` as two separate labels, because that is what they physically
are on the sheet. Nothing put them back together, so the breaker->load
pairing — the entire point of reading a distribution schedule — never
reached the Register. The reads were fine; the assembly step was missing.

THE PAIRING IS DISCOVERED PER PAGE, NOT ASSUMED. A drafting house may print
the load under the device or to its right. This module measures BOTH on the
page it is given, counts which relation actually occurs, and uses the
dominant one — reporting the count so the decision is auditable. Nothing here
knows any vessel, house or load name (gold-blind).

AMBIGUITY IS FLAGGED, NEVER RESOLVED BY PREFERENCE. If a device has two
equally-plausible load candidates, the row is emitted with ambiguous=True and
no load; the engineer sees it in the unresolved bucket rather than a coin
flip landing on a node.

    from schedule_rows import assemble_rows
    rows, meta = assemble_rows(page_record)
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# Protective/identified device tokens. Deliberately NOT switches: a switch is
# a control element and must never take a trailing load as "what it feeds"
# (the engineer's CONTROL != INDICATOR != SUPPLY rule).
DEV_INLINE = re.compile(r"^(Q\d{1,3}|QE\d{1,3}|F\d{1,3}|CB\d{1,3}(?:\.\d)?)"
                        r"[\W_]*\s+(\d{1,3}\s?A)\s*$", re.IGNORECASE)
DEV_ALONE = re.compile(r"^(Q\d{1,3}|QE\d{1,3}|F\d{1,3}|CB\d{1,3}(?:\.\d)?)"
                       r"[\W_]*$", re.IGNORECASE)
RATING = re.compile(r"^(\d{1,3}\s?A)$", re.IGNORECASE)

BELOW_MAX_DY = 14.0     # points from device bottom to load top
BELOW_MAX_DX = 60.0     # column drift allowed between device and its load
RIGHT_MAX_DX = 80.0
MIN_LOAD_CHARS = 3


def _txt(lab: Dict[str, Any]) -> str:
    return (lab.get("text_final") or lab.get("text") or "").strip()


def _conf(lab: Dict[str, Any]) -> float:
    return float(lab.get("conf_final", lab.get("conf", 0)) or 0)


def _below(dev, cand) -> bool:
    db, cb = dev["bbox"], cand["bbox"]
    return (0 < cb[1] - db[3] <= BELOW_MAX_DY
            and abs(cb[0] - db[0]) <= BELOW_MAX_DX)


def _right(dev, cand) -> bool:
    db, cb = dev["bbox"], cand["bbox"]
    v_overlap = min(db[3], cb[3]) - max(db[1], cb[1])
    return 0 < cb[0] - db[2] <= RIGHT_MAX_DX and v_overlap > 0


def assemble_rows(page: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict]:
    """Return (rows, meta). Each row carries `text` in the canonical
    '<id> <rating> <LOAD>' form so existing row parsers consume it unchanged,
    plus the separate parts and both bboxes for provenance."""
    labels = [l for l in page.get("labels", []) if _txt(l) and l.get("bbox")]
    devices, ratings, others = [], [], []
    for l in labels:
        t = _txt(l)
        if DEV_INLINE.match(t):
            m = DEV_INLINE.match(t)
            devices.append({**l, "_id": m.group(1).upper(),
                            "_rating": m.group(2).upper().replace(" ", "")})
        elif DEV_ALONE.match(t):
            devices.append({**l, "_id": DEV_ALONE.match(t).group(1).upper(),
                            "_rating": None})
        elif RATING.match(t):
            ratings.append(l)
        elif len(t) >= MIN_LOAD_CHARS:
            others.append(l)

    # --- discover the page's device->load relation instead of assuming it
    n_below = sum(1 for d in devices if any(_below(d, o) for o in others))
    n_right = sum(1 for d in devices if any(_right(d, o) for o in others))
    direction = "below" if n_below >= n_right else "right"
    meta = {"devices": len(devices), "candidates_below": n_below,
            "candidates_right": n_right, "direction_used": direction,
            "direction_confident": abs(n_below - n_right) >= max(
                2, 0.2 * max(n_below, n_right, 1))}

    test = _below if direction == "below" else _right

    def dist(d, o):
        return (abs(o["bbox"][1] - d["bbox"][3]) if direction == "below"
                else abs(o["bbox"][0] - d["bbox"][2]))

    rows = []
    for d in devices:
        rating = d["_rating"]
        if not rating:
            near = [r for r in ratings if _right(d, r) or _below(d, r)]
            if near:
                near.sort(key=lambda r: dist(d, r))
                rating = _txt(near[0]).upper().replace(" ", "")
        cands = sorted((o for o in others if test(d, o)), key=lambda o: dist(d, o))
        row = {"device_id": d["_id"], "rating": rating,
               "conf_device": _conf(d), "bbox_device": d["bbox"],
               "page": page.get("page"), "direction": direction}
        if not cands:
            row.update({"load": None, "ambiguous": False,
                        "note": "no load candidate in the discovered relation"})
        elif len(cands) > 1 and abs(dist(d, cands[0]) - dist(d, cands[1])) < 1.5:
            row.update({"load": None, "ambiguous": True,
                        "candidates": [_txt(c) for c in cands[:3]],
                        "note": "two equally-near load candidates"})
        else:
            c = cands[0]
            row.update({"load": _txt(c), "conf_load": _conf(c),
                        "bbox_load": c["bbox"], "ambiguous": False})
        parts = [row["device_id"], row["rating"] or "", row.get("load") or ""]
        row["text"] = " ".join(p for p in parts if p).strip()
        # Routing confidence is the LOAD's read — the load name is what
        # resolves to a node. A weak device token must not delete a strong
        # load read (real case: 'Q49' read at conf 28 next to 'AUTO PILOT' at
        # 96); it is carried separately and flagged so the vision-verify pass
        # targets exactly those ids.
        row["conf"] = row.get("conf_load", row["conf_device"])
        row["device_id_low_conf"] = row["conf_device"] < 70.0
        rows.append(row)
    return rows, meta
