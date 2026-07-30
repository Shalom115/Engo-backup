"""
ROUTING PREVIEW — what WOULD be written to which Register node, for the
engineer's red-pen. WRITES NOTHING (engineer hold, 2026-07-27: 'please hold
writing anything to nodes we will do it once i approve the nodes').

Consumes a run_book_extract output dir and proposes a destination for every
readable load-like label.

RESOLUTION ORDER, STATED HONESTLY (audit F3/F4 — the previous docstring
claimed "EXACTLY the resolution order the real writer uses", which was not
true: the real writer's §9e semantic matcher is NOT invoked here, and the
stated order did not even match this function's own code):
    1. engineer-confirmed load map, exact
    2. non-node disposition (feeder / distribution box)
    3. load-map containment (>= 8 chars, both directions)
    4. Register name containment (>= 8 chars)   <-- STANDS IN for §9e
    5. UNRESOLVED
Step 4 is a SUBSTITUTE for the real writer's §9e semantic matcher, not the
same thing: it has no scoring, no threshold, no identity-signal guard. A row
proposed via `register_name` is therefore weaker evidence than one via
`load_map_exact`, and the `via` column says which. Rows are the engineer's to
red-pen; the approved file becomes the fixture the real write pass is diffed
against.

DEVICE ROLE (audit F2 — switches were being routed as supplies): only
PROTECTIVE devices (breaker/fuse/CB/QE) may take the trailing text as the
LOAD they feed. A switch is a CONTROL element; it gets role=control and is
never proposed as a supply for a load.

REVISION GATE (audit F7): if the source drawing id is superseded per
revision_index_<vessel>.json, every row from it is refused — the same rule
the real writer enforces.

Emits:
    routing_preview.json   (machine record)
    routing_preview.md     (the red-pen artifact, grouped by page)

Once red-penned, the same preview file becomes the fixture the real write
pass is diffed against — protocol correct first, THEN autonomous ingest.

    python tools/routing_preview.py <bookrun_dir> [--min-conf 70]
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

STATE = Path(__file__).resolve().parent.parent / "data" / "state"


def _norm(s: str) -> str:
    return re.sub(r"[^A-Z0-9 ]+", "", (s or "").upper()).strip()


# PROTECTIVE devices only — these feed a load, so the trailing text is that
# load. SW (switch) is deliberately NOT here: a switch is a control element
# (audit F2 / the engineer's CONTROL != INDICATOR != SUPPLY rule).
SUPPLY_ROW_RE = re.compile(
    r"^(Q\d+|QE\d+|F\d+|CB\d+\.?\d*)\s+(\d+\s?A)\b(.*)$", re.IGNORECASE)
# Control elements: recognised so they are typed correctly and NOT routed as
# supplies. What a switch controls is resolved from the circuit, not the label.
CONTROL_ROW_RE = re.compile(r"^(SW\s?\d+)\s*(\d+\s?A)?\b(.*)$", re.IGNORECASE)


def load_superseded() -> set:
    """Drawing ids refused outright (audit F7 — the revision gate was absent
    from the vector chain). Same source of truth as the real writer."""
    p = STATE / "revision_index_gelliceaux_001.json"
    if not p.exists():
        return set()
    idx = json.loads(p.read_text())
    out = set()
    # Real shape (inspected, not assumed): families is a LIST of
    # {family, members, rule, current, superseded}; plus a flat superseded_ids.
    for fam in (idx.get("families") or []):
        if not isinstance(fam, dict):
            continue
        for sid in (fam.get("superseded") or []):
            out.add(str(sid.get("id") if isinstance(sid, dict) else sid))
    for sid in (idx.get("superseded_ids") or []):
        out.add(str(sid))
    return out


def load_maps():
    lm = json.loads((STATE / "load_map_gelliceaux_001.json").read_text())
    mappings = { _norm(k): v for k, v in lm["mappings"].items() }
    non_node = { _norm(k) for k in lm["non_node_dispositions"] }
    reg = json.loads((STATE / "register_gelliceaux_001.json").read_text())
    entries = [e for e in reg["entries"] if not e.get("retired")]
    return mappings, non_node, entries


def propose(text: str, mappings, non_node, entries):
    """Order AS IMPLEMENTED BELOW (F4: the old docstring listed a different
    order than the code ran): load-map exact -> non-node disposition ->
    load-map containment -> Register-name containment -> UNRESOLVED.
    Returns (node_or_disposition, via)."""
    t = _norm(text)
    # title-block furniture and OCR fragments never route
    FURNITURE = {"DATE", "TITLE", "PROJECT", "CUSTOMER", "SCALE", "DRAWN",
                 "DWG NO", "SHIPYARD", "REV", "MODIFICATION", "SIGNATURE"}
    if not t or len(t) < 3 or t in FURNITURE:
        return None, None
    if t in mappings:
        return mappings[t], "load_map_exact"
    if t in non_node:
        return "NON-NODE (feeder/distribution)", "disposition"
    # containment only for real phrases: fragment 'DRA'/'THE' must not match.
    if len(t) >= 8:
        for k, v in mappings.items():
            if len(k) >= 8 and (k in t or t in k):
                return v, "load_map_contain"
        for e in entries:
            nm = _norm(e.get("name", ""))
            if nm and len(nm) >= 8 and (nm in t or t in nm):
                return e["equipment_id"], "register_name"
    return None, None


def main(argv):
    run_dir = Path(argv[0])
    min_conf = float(argv[argv.index("--min-conf") + 1]) if "--min-conf" in argv else 70.0
    mappings, non_node, entries = load_maps()
    superseded = load_superseded()
    drawing_id = None
    if "--drawing-id" in argv:
        drawing_id = argv[argv.index("--drawing-id") + 1]
    if drawing_id and str(drawing_id) in superseded:
        print(f"REFUSED: drawing id {drawing_id} is SUPERSEDED per the "
              f"revision index — no rows proposed (revision gate, F7).")
        return
    # only p<digits>.json — plan.json also matches "p*.json" and crashed the
    # sort key (caught running the real dispatcher path, not a shortcut)
    pages = sorted((q for q in run_dir.glob("p*.json") if q.stem[1:].isdigit()),
                   key=lambda q: int(q.stem[1:]))
    out_rows = []
    sym_summary = Counter()
    for pf in pages:
        rec = json.loads(pf.read_text())
        for s_ in rec.get("typed_symbols", []):
            sym_summary[s_.get("type") or "UNKNOWN_SHAPE"] += 1
        for lab in rec.get("labels", []):
            # prefer the glyph-decoded read when it fully decoded (conf 99);
            # fall back to tesseract otherwise
            txt = lab.get("text_final", lab.get("text", ""))
            conf = lab.get("conf_final", lab.get("conf", 0))
            if not txt or conf < min_conf:
                continue
            m = SUPPLY_ROW_RE.match(txt.strip())
            c = None if m else CONTROL_ROW_RE.match(txt.strip())
            row = {"page": rec["page"], "label": txt, "conf": conf,
                   "bbox": lab.get("bbox")}
            if c:
                # CONTROL element (F2): typed, never routed as a supply.
                row.update({"device_id": c.group(1), "role": "control",
                            "proposed": "CONTROL — not a supply; what it "
                                        "controls is resolved from the circuit",
                            "via": "role_rule"})
                if c.group(2):
                    row["rating"] = c.group(2)
                out_rows.append(row)
                continue
            load_txt = m.group(3).strip() if m and m.group(3).strip() else txt
            node, via = propose(load_txt, mappings, non_node, entries)
            if m:
                row["device_id"] = m.group(1)
                row["rating"] = m.group(2)
                row["role"] = "supply"
            if node:
                row["proposed"] = node
                row["via"] = via
                out_rows.append(row)
            elif m or len(_norm(load_txt)) >= 6:
                row["proposed"] = "UNRESOLVED"
                out_rows.append(row)
    (run_dir / "routing_preview.json").write_text(json.dumps(out_rows, indent=1))
    by = Counter(r["proposed"] == "UNRESOLVED" for r in out_rows)
    via = Counter(r.get("via") for r in out_rows if r.get("via"))
    md = ["# ROUTING PREVIEW — NOTHING WRITTEN (red-pen artifact)",
          "",
          f"Labels considered (conf>={min_conf:.0f}): {len(out_rows)} | "
          f"proposed {by[False]} | UNRESOLVED {by[True]}",
          f"Via: {dict(via)}", "",
          "| pg | label (as OCR'd) | device | rating | proposed node | via |",
          "|---|---|---|---|---|---|"]
    for r in out_rows:
        md.append(f"| {r['page']} | {r['label'][:44]} | "
                  f"{r.get('device_id','')} | {r.get('rating','')} | "
                  f"**{r['proposed']}** | {r.get('via','')} |")
    (run_dir / "routing_preview.md").write_text("\n".join(md))
    if sym_summary:
        top = ", ".join(f"{t}:{n}" for t, n in sym_summary.most_common(8))
        print(f"typed symbols on these pages: {sum(sym_summary.values())} "
              f"({top})")
    ctrl = sum(1 for r in out_rows if r.get("role") == "control")
    print(f"rows {len(out_rows)}: proposed {by[False]}, unresolved {by[True]}, "
          f"control-not-supply {ctrl}; via {dict(via)}")
    print(f"-> {run_dir}/routing_preview.md (red-pen) — NO WRITES PERFORMED")


if __name__ == "__main__":
    main(sys.argv[1:])
