"""
REGISTRY PROPOSAL — turn a whole sweep into ONE registry-shaped document the
engineer red-pens, node by node. WRITES NOTHING TO THE REGISTER.

The per-file routing_preview.json artifacts answer "what would this SHEET
write?". That is the wrong unit for review: the engineer thinks in equipment,
not in sheets, and the same node collects facts from a dozen drawings. This
tool inverts the sweep — every proposed row across every file, grouped by
DESTINATION NODE, with each proposed fact carrying its provenance
(source_doc, page, bbox) so a claim can be checked against the drawing it came
from.

    python3.12 tools/registry_proposal.py                    # whole sweep
    python3.12 tools/registry_proposal.py --sweep <dir> --min-conf 70

Emits (data/state/):
    registry_proposal_<vessel>.json   machine record; the fixture the real
                                      write pass is later diffed against
    registry_proposal_<vessel>.md     the red-pen artifact, grouped by node,
                                      with an empty decision line per node

THE FOUR BUCKETS (the review is triage, not proofreading):
  1. ATTACH-TO-EXISTING  node exists in the Register; facts would be added.
     Engineer confirms the ROUTING, not every character.
  2. NEW NODE REQUIRED   destination named by the load map but absent from the
     Register — a node creation, which is a bigger decision than a fact.
  3. UNRESOLVED          read cleanly, routed to nothing. This is the honest
     residue: flag-never-guess means these WAIT for the engineer.
  4. CONTROL / NON-NODE  typed correctly and deliberately not routed as a
     supply (switches, feeders, distribution boxes).

CONFIDENCE IS CARRIED, NOT AVERAGED. Every row keeps the `via` that produced
it (load_map_exact > load_map_contain > register_name) and the OCR
`conf_source` (glyph_decode 99 > dual_channel_agree 95 > tesseract). A node
whose facts all arrived via `register_name` containment is weaker evidence
than one routed by the engineer's own load map, and the artifact says so per
row instead of blending them into one number.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "state"
SWEEP = STATE / "sweep"
VESSEL = "gelliceaux_001"

VIA_RANK = {"load_map_exact": 3, "load_map_contain": 2, "register_name": 1}
# Values the engineer writes in the load map that are NOT node ids.
NON_NODE_MARKERS = {"CLARIFY", "UNKNOWN", "TBC", ""}


def load_register() -> dict:
    p = STATE / f"register_{VESSEL}.json"
    reg = json.loads(p.read_text())
    return {e["equipment_id"]: e for e in reg.get("entries", [])
            if not e.get("retired")}


def ledger_index(sweep: Path) -> dict:
    """dir-name -> {id, name, route} from the sweep ledger (the ledger is the
    source of truth for what ran; directory names are derived from it)."""
    out = {}
    led = sweep / "ledger.jsonl"
    if not led.exists():
        return out
    for line in led.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        safe = "".join(c if c.isalnum() or c in "-_" else "_"
                       for c in r.get("name", ""))[:80]
        out[safe] = r
    return out


def collect(sweep: Path, min_conf: float):
    reg = load_register()
    lidx = ledger_index(sweep)
    by_node = defaultdict(list)
    unresolved, control = [], []
    stats = Counter()

    for pv in sorted(sweep.glob("*/routing_preview.json")):
        d = pv.parent
        meta = lidx.get(d.name, {})
        src_doc = meta.get("name", d.name)
        src_id = meta.get("id")
        try:
            rows = json.loads(pv.read_text())
        except Exception:
            stats["preview_unreadable"] += 1
            continue
        for r in rows:
            if float(r.get("conf", 0)) < min_conf:
                stats["below_min_conf"] += 1
                continue
            prov = {"source_doc": src_doc, "drive_file_id": src_id,
                    "page": r.get("page"), "bbox": r.get("bbox"),
                    "source_type": "electrical_schematic",
                    "conf": r.get("conf")}
            if r.get("role") == "control":
                control.append({"label": r.get("label"),
                                "device_id": r.get("device_id"),
                                "provenance": prov})
                stats["control"] += 1
                continue
            node = r.get("proposed")
            # The engineer's own load map carries MARKER values, not just node
            # ids ("CLARIFY" = he wanted to look at it again). Found by running
            # this tool and reading its output: a node literally named CLARIFY
            # was proposed for creation. A marker is an open question, so it
            # goes to UNRESOLVED where open questions belong.
            if node in NON_NODE_MARKERS:
                unresolved.append({"label": r.get("label"),
                                   "device_id": r.get("device_id"),
                                   "rating": r.get("rating"),
                                   "note": f"load map says {node}",
                                   "provenance": prov})
                stats["load_map_marker"] += 1
                continue
            if not node or node == "UNRESOLVED":
                unresolved.append({"label": r.get("label"),
                                   "device_id": r.get("device_id"),
                                   "rating": r.get("rating"),
                                   "provenance": prov})
                stats["unresolved"] += 1
                continue
            if str(node).startswith("NON-NODE"):
                stats["non_node"] += 1
                continue
            # FACT KIND IS EARNED, NOT ASSUMED (found by reading this tool's
            # own first output: most rows showed device_id '?', i.e. the label
            # never matched the protective-device pattern, yet every fact was
            # being stamped `electrical_supply`. A load NAME on a sheet is
            # evidence the equipment APPEARS there — it is not evidence of
            # which breaker feeds it. Two different claims, two different
            # kinds, and only one of them is a supply fact.)
            dev = (r.get("device_id") or "").strip()
            if dev:
                kind = "electrical_supply"
                dtype = ("breaker" if dev.upper().startswith(("Q", "CB"))
                         else "fuse" if dev.upper().startswith("F") else None)
                value = {"device_type": dtype, "device_id": dev,
                         "rating": r.get("rating"),
                         "load_as_printed": r.get("label")}
            else:
                kind = "appears_on_drawing"
                value = {"label_as_printed": r.get("label")}
            by_node[node].append({"kind": kind, "value": value,
                                  "via": r.get("via"), "provenance": prov})
            stats[f"kind_{kind}"] += 1
            stats["proposed_facts"] += 1

    nodes = []
    for nid, facts in sorted(by_node.items()):
        exists = nid in reg
        best = max((VIA_RANK.get(f.get("via"), 0) for f in facts), default=0)
        nodes.append({
            "node_id": nid,
            "node_name": reg.get(nid, {}).get("name"),
            "bucket": "attach_existing" if exists else "new_node_required",
            "strongest_via": next((k for k, v in VIA_RANK.items()
                                   if v == best), None),
            "fact_count": len(facts),
            "source_docs": sorted({f["provenance"]["source_doc"]
                                   for f in facts}),
            "facts": facts,
            "engineer_decision": "",       # CONFIRM / REJECT / RETARGET <id>
            "engineer_comment": "",
        })
        stats["attach_existing" if exists else "new_node_required"] += 1
    return nodes, unresolved, control, dict(stats)


def write_md(path: Path, nodes, unresolved, control, stats, min_conf):
    L = ["# REGISTRY PROPOSAL — engineer red-pen",
         "", "NOTHING HAS BEEN WRITTEN TO THE REGISTER. Every node below is a "
         "proposal.", "",
         f"min-conf {min_conf:.0f} · {stats.get('proposed_facts', 0)} proposed "
         f"facts · {stats.get('attach_existing', 0)} existing nodes · "
         f"{stats.get('new_node_required', 0)} new nodes · "
         f"{stats.get('unresolved', 0)} unresolved", "",
         "Per node write one of: `CONFIRM` · `REJECT` · `RETARGET <node-id>`. "
         "Anything left blank stays UNWRITTEN — silence is never taken as "
         "approval.", ""]
    for b, title in (("attach_existing", "## 1. ATTACH TO EXISTING NODES"),
                     ("new_node_required", "## 2. NEW NODES REQUIRED")):
        sel = [n for n in nodes if n["bucket"] == b]
        L += [title, f"({len(sel)} nodes)", ""]
        for n in sel:
            nm = n["node_name"] or "(not in Register)"
            L += [f"### {n['node_id']}  —  {nm}",
                  f"routed via **{n['strongest_via']}** · {n['fact_count']} "
                  f"fact(s) · sources: {', '.join(n['source_docs'][:4])}", ""]
            for f in n["facts"][:12]:
                v = f["value"]
                head = (f"`{v['device_id']}` {v.get('rating') or ''} feeds"
                        if f["kind"] == "electrical_supply"
                        else "appears on drawing:")
                txt = v.get("load_as_printed") or v.get("label_as_printed")
                L.append(f"- {head} {txt}  "
                         f"_[{f['provenance']['source_doc']}, "
                         f"p.{f['provenance']['page']}]_")
            if n["fact_count"] > 12:
                L.append(f"- … {n['fact_count'] - 12} more")
            L += ["", "**DECISION:** ______   **NOTE:** ______", ""]
    L += ["## 3. UNRESOLVED — read cleanly, routed to nothing",
          f"({len(unresolved)}) These wait for you; Engo does not guess a "
          "destination.", ""]
    for u in unresolved[:400]:
        L.append(f"- `{u.get('device_id') or ''}` {u.get('rating') or ''} "
                 f"{u['label']}  _[{u['provenance']['source_doc']}, "
                 f"p.{u['provenance']['page']}]_  → **NODE:** ______")
    if len(unresolved) > 400:
        L.append(f"- … {len(unresolved) - 400} more in the JSON")
    L += ["", "## 4. CONTROL / NON-NODE — typed, deliberately not routed",
          f"({len(control)} control elements) A switch is not a supply; what "
          "it controls comes from the circuit, not the label.", ""]
    path.write_text("\n".join(L))


def main(argv):
    sweep = Path(argv[argv.index("--sweep") + 1]) if "--sweep" in argv else SWEEP
    min_conf = float(argv[argv.index("--min-conf") + 1]) \
        if "--min-conf" in argv else 70.0
    if not sweep.exists():
        print(f"no sweep at {sweep} — run tools/sweep_drive.py first")
        sys.exit(2)
    nodes, unresolved, control, stats = collect(sweep, min_conf)
    doc = {"vessel": VESSEL, "min_conf": min_conf,
           "written_to_register": False,
           "stats": stats, "nodes": nodes,
           "unresolved": unresolved, "control": control}
    jp = STATE / f"registry_proposal_{VESSEL}.json"
    mp = STATE / f"registry_proposal_{VESSEL}.md"
    jp.write_text(json.dumps(doc, indent=1))
    write_md(mp, nodes, unresolved, control, stats, min_conf)
    print(json.dumps(stats, indent=1))
    print(f"-> {jp}\n-> {mp}   (NO WRITES PERFORMED)")


if __name__ == "__main__":
    main(sys.argv[1:])
