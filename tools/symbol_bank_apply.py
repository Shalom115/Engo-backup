"""
SYMBOL BANK APPLY — write the engineer's red-pen answers into the bank.

Consumes the export format the worksheet produces (Copy answers /
Download .txt): one line per answered symbol,

    #<id> <TAB> <type> [<TAB> # <note>]

('#'-prefixed comment lines and blank lines are ignored; separators may be
tabs or 2+ spaces — engineers paste from anywhere.)

Applies them to a symbol_bank_DRAFT.json:
  - engineer_type / engineer_note filled per cluster,
  - confidence: engineer answers are AUTHORITATIVE (they overwrite any
    auto_type; the auto_type is kept alongside for the record),
  - unanswered clusters stay untouched (blank engineer_type = genuinely
    unreviewed, never defaulted),
  - unknown ids in the answers -> reported, never silently dropped.

Writes the CONFIRMED bank to the output path (never mutates the draft
in place — the draft is the record of what was asked). Reports real counts.

    python tools/symbol_bank_apply.py <answers.txt> <symbol_bank_DRAFT.json> \
        <symbol_bank_CONFIRMED.json>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LINE_RE = re.compile(r"^#?(\d+)(?:\t+| {2,})(\S[^\t#]*?)(?:(?:\t+| {2,})#?\s*(.*))?$")


def parse_answers(text: str):
    """-> {id: {"type": str, "note": str}}, [unparseable lines]"""
    answers, bad = {}, []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("# "):
            continue
        m = LINE_RE.match(line)
        if not m:
            bad.append(raw)
            continue
        cid = int(m.group(1))
        answers[cid] = {"type": m.group(2).strip(),
                        "note": (m.group(3) or "").strip()}
    return answers, bad


def main(argv):
    ans_path, draft_path, out_path = argv[0], argv[1], argv[2]
    answers, bad = parse_answers(Path(ans_path).read_text())
    bank = json.loads(Path(draft_path).read_text())
    known_ids = {c["cluster"] for c in bank["clusters"]}
    unknown = sorted(set(answers) - known_ids)

    applied = 0
    for c in bank["clusters"]:
        a = answers.get(c["cluster"])
        if not a:
            continue
        c["engineer_type"] = a["type"]
        if a["note"]:
            c["engineer_note"] = a["note"]
        applied += 1

    total = len(bank["clusters"])
    instances_typed = sum(c["instances"] for c in bank["clusters"]
                          if c.get("engineer_type"))
    instances_total = sum(c["instances"] for c in bank["clusters"])
    bank["engineer_confirmed"] = True
    bank["answers_applied"] = applied
    Path(out_path).write_text(json.dumps(bank, indent=1))

    print(f"answers parsed: {len(answers)}  (unparseable lines: {len(bad)})")
    for l in bad[:10]:
        print(f"  UNPARSEABLE: {l!r}")
    if unknown:
        print(f"  UNKNOWN symbol ids (not in draft, NOT applied): {unknown}")
    print(f"applied: {applied}/{total} clusters -> "
          f"{instances_typed}/{instances_total} symbol instances now typed "
          f"({100*instances_typed/max(1,instances_total):.0f}% of the book's "
          f"symbol population)")
    print(f"-> {out_path}")
    unanswered = [c["cluster"] for c in bank["clusters"]
                  if not c.get("engineer_type")]
    if unanswered:
        print(f"still unanswered ({len(unanswered)}): "
              f"{unanswered[:30]}{'...' if len(unanswered) > 30 else ''}")


if __name__ == "__main__":
    main(sys.argv[1:])
