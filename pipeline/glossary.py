"""
Vessel glossary builder — extract the acronym/abbreviation table from the source
documents and reconcile it with the folder-harvested vocab.

The lesson behind this: ingesting a document is not the same as extracting its
knowledge. The Owner's Manual (p.7) and the Engineering Handover (p.4) both carry
the authoritative acronym chart, but blind token-chunking flattened the table into
prose, so it was never usable. This pass reads those tables structurally and emits
an authoritative glossary_<vessel>.json — the source of truth for acronym
expansion, feeding the HyDE vocab layer and the agent's nickname resolution.

Conflicts (where the manual disagrees with the folder-harvest, e.g. EDN) are kept
and flagged with both readings + source — never silently overwritten.

CLI:
    python -m pipeline.glossary --dry-run
    python -m pipeline.glossary            # writes glossary_<vessel>.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import config

# Documents known to carry an acronym/abbreviation table, in priority order.
ACRONYM_SOURCES: List[Tuple[str, str]] = [
    ("handover", "/Users/captain/Downloads/SY Gelliceaux Hand Over.pdf"),
    ("owners_manual", str(config.DOCUMENTS_DIR / "108-01 Owner's Manual Rev1 2023-08-08.pdf")),
]

# Section start/end markers (scope parsing to the acronym table only).
_SECTION_START = re.compile(r"ABBREVIATION|ACRONYM", re.I)
_SECTION_END = re.compile(r"^\s*2[\.\-\s]|DISPLAYS AND PLC", re.I)
# A table row: an acronym token (mostly upper, 2–9 chars) then a description.
_ROW = re.compile(r"^([A-Za-z][A-Za-z0-9\-]{1,8})\s+([A-Za-z][A-Za-z0-9 &/().\-]{3,60})$")


# Common words that look acronym-ish in a TOC/prose but aren't equipment acronyms.
_STOP = {"AND", "THE", "FOR", "SEE", "ALL", "NOT", "DECK", "NEW", "WITH", "FROM",
         "THIS", "PAGE", "NOTE", "SY"}


def _is_acronymish(tok: str) -> bool:
    letters = [c for c in tok if c.isalpha()]
    if not letters:
        return False
    upper = sum(1 for c in letters if c.isupper())
    return upper / len(letters) >= 0.6  # mostly uppercase (allows Li-ION)


def _is_toc_artifact(desc: str) -> bool:
    d = desc.upper().strip()
    return "CHAPTER" in d or d in ("DESCRIPTION", "ABBREVIATION", "PAGE")


def extract_acronym_table(pdf_path: str) -> Dict[str, str]:
    """Pull {ACRONYM: description} from the acronym section of a PDF."""
    from pypdf import PdfReader
    if not Path(pdf_path).exists():
        return {}
    reader = PdfReader(pdf_path)
    out: Dict[str, str] = {}
    in_section = False
    for page in reader.pages:
        text = page.extract_text() or ""
        for line in text.splitlines():
            line = line.strip()
            if not in_section:
                if _SECTION_START.search(line):
                    in_section = True
                continue
            if _SECTION_END.match(line):
                in_section = False
                continue
            m = _ROW.match(line)
            if m and _is_acronymish(m.group(1)):
                acr = m.group(1).upper()
                desc = m.group(2).strip()
                if acr not in _STOP and not _is_toc_artifact(desc):
                    out.setdefault(acr, desc)
    return out


def build(dry_run: bool = False) -> Dict[str, Any]:
    state, vessel = config.STATE_DIR, config.VESSEL_NAMESPACE

    # 1. Extract acronym tables from each source doc.
    by_source: Dict[str, Dict[str, str]] = {}
    for name, path in ACRONYM_SOURCES:
        tbl = extract_acronym_table(path)
        if tbl:
            by_source[name] = tbl

    # 2. Folder-harvested vocab (the per-vessel layer we built from folder names).
    vocab_path = state / f"vocab_{vessel}.json"
    folder_vocab = json.loads(vocab_path.read_text()).get("acronyms", {}) if vocab_path.exists() else {}

    # 3. Reconcile. Manuals are authoritative for expansion; folder-harvest is a
    #    secondary source. Disagreements are flagged, not overwritten.
    acronyms: Dict[str, Dict[str, Any]] = {}
    all_keys = set().union(*[set(t) for t in by_source.values()], set(folder_vocab))
    conflicts: List[Dict[str, Any]] = []
    for k in sorted(all_keys):
        readings: Dict[str, str] = {}
        for src, tbl in by_source.items():
            if k in tbl:
                readings[src] = tbl[k]
        if folder_vocab.get(k):
            readings["folder_harvest"] = folder_vocab[k]
        # authoritative = first manual source that has it, else folder
        primary = next((readings[s] for s, _ in ACRONYM_SOURCES if s in readings),
                       folder_vocab.get(k, ""))
        distinct = {v.lower().strip() for v in readings.values() if v}
        is_conflict = len(distinct) > 1
        acronyms[k] = {"expansion": primary, "sources": readings,
                       "conflict": is_conflict}
        if is_conflict:
            conflicts.append({"acronym": k, "readings": readings})

    glossary = {
        "vessel_namespace": vessel,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_docs": {n: len(t) for n, t in by_source.items()},
        "count": len(acronyms),
        "conflicts": conflicts,
        "acronyms": acronyms,
    }

    print(f"glossary: {len(acronyms)} acronyms | sources: "
          f"{ {n: len(t) for n, t in by_source.items()} } | conflicts: {len(conflicts)}")
    for c in conflicts:
        print(f"  CONFLICT {c['acronym']}: {c['readings']}")
    if dry_run:
        sample = list(acronyms.items())[:12]
        for k, v in sample:
            print(f"  {k:8} = {v['expansion']!r}  ({'/'.join(v['sources'])})")
        return glossary

    (state / f"glossary_{vessel}.json").write_text(
        json.dumps(glossary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote glossary_{vessel}.json")
    return glossary


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.glossary")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    build(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
