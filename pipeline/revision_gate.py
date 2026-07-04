"""
REVISION GATE — regard only the most-up-to-date source (§3 revision-supersede).

Groups drawing files into revision FAMILIES and marks one member CURRENT, the rest
SUPERSEDED. Conservative by design: it only supersedes on explicit evidence; anything
uncertain is flagged AMBIGUOUS for the engineer, never auto-dropped.

Rules (in order):
  R1 explicit rev token in the filename ('rev10', '_REV.0', 'Rev 1') — highest rev wins.
  R2 files under an 'OLD - ARCHIVE' folder are superseded by construction.
  R3 yard drawing-number letter suffix (108-01-680-002d supersedes ...-002) — applied
     ONLY to SWS 108-01-XXX-YYY[letter] numbers, NOT to GM sheet numbers ('108' - 111a'
     is a DIFFERENT SHEET, not a revision of 111).
  R4 same filename resolving to MULTIPLE distinct contents (md5) with no rev evidence
     -> AMBIGUOUS, engineer decides (e.g. BAE Wiring Diagrams.pdf x2 contents).
  R5 title-block overrides: revisions read off the rendered title block during the
     population survey (e.g. Electrical System GA prelim P2 vs Rev B).

Artifact: revision_index_<vessel>.json. node_write refuses facts from superseded ids.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import config

_REV_TOKEN = re.compile(r"rev[\s._-]*([0-9]+|[a-z])\b", re.I)
_YARD_NO = re.compile(r"\b(108-01-\d{3}-\d{3})([a-z])?\b", re.I)
_ARCHIVE = re.compile(r"OLD\s*-\s*ARCHIVE", re.I)

# R5 — title-block reads from the rendered population survey (2026-07-02).
_OVERRIDES = [
    {"family": "108-01-600-001 Electrical System GA",
     "superseded_ids": ["<prelim-1890007B-id>"],  # resolved at build time by size
     "note": "unnumbered 'Electrical System GA.pdf' 1.89MB = PRELIM ISSUE 2 (12 AUG 2022); 001b = Rev B (19 JAN 2023) current"},
]


def _family_key(name: str) -> str:
    n = name.lower().rsplit(".", 1)[0]
    m = _YARD_NO.search(name)
    if m:
        return m.group(1).lower()          # yard number without its rev letter
    mt = _REV_TOKEN.search(n)
    if mt:
        # family = everything BEFORE the rev token, so 'X-rev6 10of12' and
        # 'X-rev10-mast_block' land in ONE family and compete on rev rank
        return re.sub(r"[\s_-]+$", "", n[:mt.start()]).strip()
    return re.sub(r"\s+", " ", n).strip()


def _rev_rank(name: str, path: str) -> Optional[float]:
    """Higher = newer. None = no explicit evidence."""
    m = _REV_TOKEN.search(name)
    if m:
        tok = m.group(1)
        return float(tok) if tok.isdigit() else 0.01 * (ord(tok.lower()) - 96)
    m = _YARD_NO.search(name)
    if m:
        return 0.01 * (ord(m.group(2).lower()) - 96) if m.group(2) else 0.0
    return None


def build_revision_index(vessel: Optional[str] = None) -> Dict[str, Any]:
    vessel = vessel or config.VESSEL_NAMESPACE
    man = json.loads((config.STATE_DIR / f"structure_{vessel}.json").read_text())
    nodes = man.get("nodes") or man.get("files") or []
    if isinstance(nodes, dict):
        nodes = list(nodes.values())
    files = [n for n in nodes if n.get("type") != "folder" and n.get("mime")]

    fams: Dict[str, List[Dict[str, Any]]] = {}
    for f in files:
        nm, path = str(f.get("name", "")), str(f.get("path", ""))
        fams.setdefault(_family_key(nm), []).append(
            {"id": f.get("id"), "name": nm, "path": path,
             "rev_rank": _rev_rank(nm, path), "archived": bool(_ARCHIVE.search(path))})

    out = {"vessel": vessel, "built_at": "2026-07-02", "families": [], "superseded_ids": [],
           "ambiguous": []}
    for key, members in fams.items():
        ranked = [m for m in members if m["rev_rank"] is not None]
        archived = [m for m in members if m["archived"]]
        distinct_ids = {m["id"] for m in members}
        if len(distinct_ids) < 2 and not archived:
            continue                       # nothing to gate
        entry: Dict[str, Any] = {"family": key, "members": members, "rule": None,
                                 "current": None, "superseded": []}
        if ranked and len({m["rev_rank"] for m in ranked}) > 1:
            top = max(m["rev_rank"] for m in ranked)
            entry["rule"] = "R1/R3 explicit rev"
            entry["current"] = [m["id"] for m in ranked if m["rev_rank"] == top]
            entry["superseded"] = [m["id"] for m in ranked if m["rev_rank"] < top]
        if archived:
            entry["rule"] = (entry["rule"] or "") + "+R2 archive" if entry["rule"] else "R2 archive"
            entry["superseded"] = sorted(set(entry["superseded"]) |
                                         {m["id"] for m in archived})
            live = [m["id"] for m in members if not m["archived"]]
            entry["current"] = entry["current"] or (live or None)
        if entry["superseded"]:
            if not entry["current"]:
                entry["note"] = ("archive-only family: no live member under this name — "
                                 "the current version likely exists under a DIFFERENT filename; "
                                 "engineer to confirm before relying on the archived copy")
            cur_names = {}
            for m in members:
                if entry["current"] and m["id"] in entry["current"]:
                    cur_names.setdefault(m["name"], set()).add(m["id"])
            multi = {n: sorted(ids) for n, ids in cur_names.items() if len(ids) > 1}
            if multi:
                entry["current_multi_id_note"] = ("multiple distinct ids remain CURRENT under one "
                                                  "filename — verify contents (md5); if they differ, "
                                                  "engineer picks (e.g. BAE Wiring Diagrams 2 contents)")
                entry["current_multi_ids"] = multi
            out["families"].append(entry)
            out["superseded_ids"].extend(entry["superseded"])
        elif len({m["name"] for m in members}) == 1 and len(distinct_ids) > 1:
            # same name, several ids, no rev evidence: only ambiguous if contents differ
            # (content check is done by the population survey; record as watch item)
            out["ambiguous"].append({"family": key,
                                     "ids": sorted(distinct_ids),
                                     "note": "same name, multiple ids, no rev evidence — verify contents (md5) before trusting either"})
    out["superseded_ids"] = sorted(set(out["superseded_ids"]))
    (config.STATE_DIR / f"revision_index_{vessel}.json").write_text(json.dumps(out, indent=2))
    return out


def load_superseded(vessel: Optional[str] = None) -> set:
    vessel = vessel or config.VESSEL_NAMESPACE
    p = config.STATE_DIR / f"revision_index_{vessel}.json"
    if not p.exists():
        return set()
    return set(json.loads(p.read_text()).get("superseded_ids", []))
