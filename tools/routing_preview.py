"""
ROUTING PREVIEW — what WOULD be written to which Register node, for the
engineer's red-pen. WRITES NOTHING (engineer hold, 2026-07-27: 'please hold
writing anything to nodes we will do it once i approve the nodes').

Consumes a run_book_extract output dir, proposes a destination for every
readable load-like label using EXACTLY the resolution order the real writer
uses (engineer-confirmed load map first -> non-node dispositions -> register
name match -> UNRESOLVED), and emits:
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


DEVICE_ROW_RE = re.compile(
    r"^(Q\d+|QE\d+|F\d+|CB\d+\.?\d*|SW\s?\d+)\s+(\d+\s?A)\b(.*)$",
    re.IGNORECASE)


def load_maps():
    lm = json.loads((STATE / "load_map_gelliceaux_001.json").read_text())
    mappings = { _norm(k): v for k, v in lm["mappings"].items() }
    non_node = { _norm(k) for k in lm["non_node_dispositions"] }
    reg = json.loads((STATE / "register_gelliceaux_001.json").read_text())
    entries = [e for e in reg["entries"] if not e.get("retired")]
    return mappings, non_node, entries


def propose(text: str, mappings, non_node, entries):
    """Resolution order mirrors write_electrical_row: map exact -> map
    containment -> non-node disposition -> register-name whole-word match ->
    UNRESOLVED. Returns (node_or_disposition, via)."""
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
    pages = sorted(run_dir.glob("p*.json"), key=lambda p: int(p.stem[1:]))
    out_rows = []
    for pf in pages:
        rec = json.loads(pf.read_text())
        for lab in rec.get("labels", []):
            # prefer the glyph-decoded read when it fully decoded (conf 99);
            # fall back to tesseract otherwise
            txt = lab.get("text_final", lab.get("text", ""))
            conf = lab.get("conf_final", lab.get("conf", 0))
            if not txt or conf < min_conf:
                continue
            m = DEVICE_ROW_RE.match(txt.strip())
            load_txt = m.group(3).strip() if m and m.group(3).strip() else txt
            node, via = propose(load_txt, mappings, non_node, entries)
            row = {"page": rec["page"], "label": txt, "conf": conf,
                   "bbox": lab.get("bbox")}
            if m:
                row["device_id"] = m.group(1)
                row["rating"] = m.group(2)
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
    print(f"rows {len(out_rows)}: proposed {by[False]}, unresolved {by[True]}; via {dict(via)}")
    print(f"-> {run_dir}/routing_preview.md (red-pen) — NO WRITES PERFORMED")


if __name__ == "__main__":
    main(sys.argv[1:])
