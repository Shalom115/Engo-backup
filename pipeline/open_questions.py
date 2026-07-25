"""
OPEN-QUESTION LEDGER — cross-sheet uncertainty resolution (engineer-mandated
2026-07-22).

The engineer's observation: "there will be a lot of time when things are not
necessarily understood in the current sheet but it will come clear as the
entire drive gets ingested." A sheet legitimately cannot answer everything —
GM-116 says "the + comes from DWG 118", the ONYX taps only resolve once the
ONYX drawings land.

So an uncertainty is not a dead end; it is an OPEN QUESTION with a key. This
module keeps that ledger across the whole ingestion:

  * every composition's uncertainties + cross_references are filed as OPEN
    questions, each with search keys (device ids, terminal numbers, drawing
    references, equipment words);
  * when a LATER sheet is ingested, its facts are matched against every open
    question — anything it answers is CLOSED, with the answering sheet
    recorded as provenance;
  * whatever is still open at the end of the run is the engineer's real
    red-pen list — small, and genuinely unanswerable from the corpus.

This turns "unknown on this sheet" from noise into a resolvable queue.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Set

import config

LEDGER = config.STATE_DIR / f"open_questions_{config.VESSEL_NAMESPACE}.json"

# identifiers worth keying on: device ids (Q15, Re24, F3, XA50, QE5),
# terminal numbers, drawing references (DWG 118, GMMS 108'-116)
_ID = re.compile(r"\b(?:[A-Z]{1,3}E?\d{1,3}(?:\.\d+)?|XA\d{2,3}|MU\d{1,2}-\d{1,2})\b")
_DWG = re.compile(r"\b(?:DWG|DRAWING|SHEET|GMMS)[\s.:'-]*([\w\d\-']{2,12})", re.I)
_TERM = re.compile(r"\bterminals?\s+(\d{1,3})\b", re.I)


def _keys(text: str) -> Set[str]:
    t = text or ""
    keys = set(m.group(0).upper() for m in _ID.finditer(t))
    keys |= {f"DWG:{m.group(1).upper()}" for m in _DWG.finditer(t)}
    keys |= {f"TERM:{m.group(1)}" for m in _TERM.finditer(t)}
    return keys


def _load() -> Dict[str, Any]:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text())
    return {"vessel": config.VESSEL_NAMESPACE, "questions": []}


def _save(data: Dict[str, Any]) -> None:
    tmp = LEDGER.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(LEDGER)


def file_questions(sheet: str, composition: Dict[str, Any],
                   drawing_class: str = "") -> int:
    """File this sheet's uncertainties + cross-references as OPEN questions."""
    data = _load()
    have = {(q["sheet"], q["text"]) for q in data["questions"]}
    added = 0
    for u in composition.get("uncertainties") or []:
        text = u if isinstance(u, str) else json.dumps(u)
        if (sheet, text) in have:
            continue
        data["questions"].append({
            "id": f"q{len(data['questions']) + 1}",
            "sheet": sheet, "drawing_class": drawing_class,
            "kind": "uncertainty", "text": text,
            "keys": sorted(_keys(text)), "status": "open",
            "opened": str(date.today())})
        added += 1
    for x in composition.get("cross_references") or []:
        if not isinstance(x, dict):
            continue
        text = x.get("what", "")
        hint = x.get("referenced_sheet_hint", "")
        if (sheet, text) in have or not text:
            continue
        data["questions"].append({
            "id": f"q{len(data['questions']) + 1}",
            "sheet": sheet, "drawing_class": drawing_class,
            "kind": "cross_reference", "text": text,
            "hint": hint,
            "keys": sorted(_keys(f"{text} {hint}")), "status": "open",
            "opened": str(date.today())})
        added += 1
    _save(data)
    return added


def _composition_text(composition: Dict[str, Any]) -> str:
    return json.dumps(composition, ensure_ascii=False)


def resolve_with(sheet: str, composition: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check this sheet's content against every OPEN question from earlier sheets.
    A question is CLOSED when this sheet carries its key AND is a different
    sheet (a sheet cannot answer itself).
    """
    data = _load()
    blob = _composition_text(composition).upper()
    closed: List[Dict[str, Any]] = []
    for q in data["questions"]:
        if q["status"] != "open" or q["sheet"] == sheet:
            continue
        keys = q.get("keys") or []
        if not keys:
            continue
        hits = [k for k in keys if k.split(":")[-1] in blob]
        # require a real identifier hit, not a bare 1-2 digit coincidence
        strong = [k for k in hits if len(k.split(":")[-1]) >= 2]
        if strong:
            q["status"] = "answered"
            q["answered_by"] = sheet
            q["answered_on"] = str(date.today())
            q["matched_keys"] = strong
            closed.append(q)
    if closed:
        _save(data)
    return closed


def open_digest(limit: int = 30) -> str:
    """Prompt block: what earlier sheets could not answer — if THIS sheet
    resolves one, say so explicitly in the composition."""
    data = _load()
    openq = [q for q in data["questions"] if q["status"] == "open"]
    if not openq:
        return ""
    out = ["OPEN QUESTIONS FROM EARLIER SHEETS — if anything on THIS sheet "
           "answers one of these, state the answer explicitly in the relevant "
           "fact or note (do not invent; only answer what this sheet shows):"]
    for q in openq[:limit]:
        keys = ", ".join(q["keys"][:6])
        out.append(f"  [{q['id']}] ({q['sheet']}) {q['text'][:160]}"
                   + (f"   keys: {keys}" if keys else ""))
    return "\n".join(out)


def stats() -> Dict[str, int]:
    data = _load()
    qs = data["questions"]
    return {"total": len(qs),
            "open": sum(1 for q in qs if q["status"] == "open"),
            "answered": sum(1 for q in qs if q["status"] == "answered")}
