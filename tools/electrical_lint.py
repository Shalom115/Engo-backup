"""
ELECTRICAL LINT v0 — machine-checkable drafting invariants over a page's
extracted structure. This is the self-grading gate that replaces "engineer
eyeballs the overlay" (autonomy channel #1 in the audit §5e).

A valid extraction of a valid sheet satisfies rules a schematic must obey by
construction. Violations are EXTRACTION defects (or genuine drawing anomalies)
— either way, machine-detected findings, no human in the loop:

  L1 net_isolated        a multi-segment net with total length > threshold that
                         touches no symbol box and no attached label — a traced
                         conductor connected to nothing nameable (broken join
                         or missed symbol).
  L2 symbol_orphan       a symbol box touching no net — a device wired to
                         nothing (missed conductor or a legend/table cell).
  L3 label_unattached    a non-empty label that attached to nothing within
                         radius (missed symbol/net or a notes block).
  L4 ocr_low_conf        non-empty label below confidence 70 — residue queue
                         for the vision-verify / glyph-decode channel.
  L5 net_fragment        1-segment nets below fragment length — usually dash
                         debris; counted, not itemized.
  L6 id_grammar          label matching a device-ID shape (Q/F/QE/CB/Re/SW/
                         CT/T\\/S + number) whose OCR conf < 70 — a device id
                         we cannot yet trust; must be resolved before routing.

Per-page defect counts + a book-level summary; exit 1 if any page exceeds
hard ceilings (isolated nets > 15% of nets, unattached labels > 15%).

    python tools/electrical_lint.py <out_dir_of_run_book_extract>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ISOLATED_NET_MIN_LEN = 60.0   # pt — ignore short debris in L1
FRAG_LEN = 30.0
DEVICE_ID_RE = re.compile(
    r"\b(Q\d+|QE\d+|F\d+|CB\d+|Re\s?\d+|SW\s?\d+|CT\s?\d+|T/S\s?[A-Z])\b",
    re.IGNORECASE)
HARD_ISOLATED_FRAC = 0.15
HARD_UNATTACHED_FRAC = 0.15


def _touch(bb, nb, pad=3.0):
    return not (bb[2] + pad < nb[0] or nb[2] + pad < bb[0]
                or bb[3] + pad < nb[1] or nb[3] + pad < bb[1])


def lint_page(rec: dict) -> dict:
    nets = rec.get("nets", [])
    syms = rec.get("sym_boxes", [])
    labels = rec.get("labels", [])
    big_nets = [n for n in nets
                if n["total_len"] >= ISOLATED_NET_MIN_LEN or n["n_segs"] >= 3]
    # net -> touching symbols / attached labels
    attached_netids = {tuple(l["attach"])[1] for l in labels
                       if l.get("attach") and l["attach"][0] == "net"}
    touched = set()
    for n in big_nets:
        nb = n["bbox"]
        if n["net_id"] in attached_netids:
            touched.add(n["net_id"])
            continue
        if any(_touch(sb, nb) for sb in syms):
            touched.add(n["net_id"])
    l1 = [n["net_id"] for n in big_nets if n["net_id"] not in touched]
    # symbol orphans: no net bbox touches the symbol
    l2 = 0
    for sb in syms:
        if not any(_touch(sb, n["bbox"]) for n in nets):
            l2 += 1
    ne_labels = [l for l in labels if l.get("text")]
    l3 = [l["text"] for l in ne_labels if not l.get("attach")]
    l4 = [l["text"] for l in ne_labels if l.get("conf", 0) < 70]
    l5 = sum(1 for n in nets if n["n_segs"] == 1 and n["total_len"] < FRAG_LEN)
    l6 = [l["text"] for l in ne_labels
          if DEVICE_ID_RE.search(l["text"]) and l.get("conf", 0) < 70]
    nn = max(1, len(big_nets))
    nl = max(1, len(ne_labels))
    return {
        "page": rec["page"],
        "L1_net_isolated": len(l1), "L1_frac": round(len(l1) / nn, 3),
        "L2_symbol_orphan": l2,
        "L3_label_unattached": len(l3), "L3_frac": round(len(l3) / nl, 3),
        "L4_ocr_low_conf": len(l4),
        "L5_net_fragments": l5,
        "L6_untrusted_device_ids": l6[:20],
        "hard_fail": (len(l1) / nn > HARD_ISOLATED_FRAC
                      or len(l3) / nl > HARD_UNATTACHED_FRAC),
    }


def main(argv):
    out_dir = Path(argv[0])
    pages = sorted(out_dir.glob("p*.json"),
                   key=lambda p: int(p.stem[1:]))
    rows = []
    for pf in pages:
        rec = json.loads(pf.read_text())
        rows.append(lint_page(rec))
    fails = [r["page"] for r in rows if r["hard_fail"]]
    summary = {
        "pages": len(rows),
        "hard_fail_pages": fails,
        "total_L1_isolated_nets": sum(r["L1_net_isolated"] for r in rows),
        "total_L2_symbol_orphans": sum(r["L2_symbol_orphan"] for r in rows),
        "total_L3_unattached_labels": sum(r["L3_label_unattached"] for r in rows),
        "total_L4_low_conf_labels": sum(r["L4_ocr_low_conf"] for r in rows),
        "total_L6_untrusted_ids": sum(len(r["L6_untrusted_device_ids"]) for r in rows),
        "per_page": rows,
    }
    (out_dir / "lint_report.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: v for k, v in summary.items() if k != "per_page"},
                     indent=1))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
