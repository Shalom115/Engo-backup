"""
LOAD-MAP STREAMLINING (engineer-requested 2026-07-11).

Merges the 3 draft load-map files into ONE current, non-redundant document,
per load answering exactly what the engineer asked for:
  - what is it (equipment / instrument-gauge / breaker-or-protective-device /
    alarm-monitor / control-relay / unclear) — classified from the load text
  - what SYSTEM (source sheet/drawing) the read found it on
  - what NODE it's proposed for, decoded into a human system label + raw id,
    and whether that node already exists or needs creating

Reconciles a real gap found in review: EXTENSION.DRAFT_v2 only covers 21 of
EXTENSION.DRAFT's 29 sheets (155 loads were silently missing proposals) —
those 8 sheets are carried forward here with proposed=NEEDS_PROPOSAL, not
dropped. DRAFT.json (v1, the GMMS-111 sheet) is fully closed (every entry
verified present in the active map) — included as history, not actionable.

Outputs:
  data/state/load_map_gelliceaux_001.STREAMLINED.json   (machine-readable)
  scratch_out/load_map_review.html                       (engineer review page)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

STATE = Path("data/state")

# ---------------------------------------------------------------- SFI decode
def build_sfi_labels() -> Dict[str, str]:
    labels: Dict[str, str] = {}
    reg = json.loads((STATE / "register_gelliceaux_001.json").read_text())
    for e in reg["entries"]:
        for code, label in ((e.get("subsystem_code"), e.get("subsystem_label")),
                            (e.get("region_code"), e.get("region_label"))):
            if code and label:
                labels.setdefault(code, label)
    # fill gaps the Register doesn't cover (from the draft files' own rationale text)
    labels.setdefault("650", "Monitoring (ONYX)")
    labels.setdefault("652", "Onyx monitoring")
    labels.setdefault("654", "Emergency stops")
    labels.setdefault("670", "Earthing / cathodic protection")
    labels.setdefault("690", "Lighting circuits")
    labels.setdefault("691", "Yachtica lighting control")
    labels.setdefault("692", "DC sockets")
    labels.setdefault("693", "Emergency lighting")
    labels.setdefault("695", "Fire alarm / fire system")
    labels.setdefault("696", "Gas alarms")
    labels.setdefault("710", "Radar")
    labels.setdefault("711", "B&G instruments")
    labels.setdefault("712", "Navigation station")
    labels.setdefault("713", "External screens")
    labels.setdefault("720", "CCTV / entertainment")
    labels.setdefault("730", "VHF / comms")
    labels.setdefault("731", "Navtex")
    labels.setdefault("732", "Network")
    labels.setdefault("733", "Fog horn")
    labels.setdefault("625", "BAE cooling pumps")
    labels.setdefault("629", "BEL converters")
    labels.setdefault("630", "Mastervolt batteries / chargers")
    labels.setdefault("640", "DC distribution")
    labels.setdefault("641", "Vessel control panel")
    return labels


SFI_LABELS = build_sfi_labels()
_CODE_RE = re.compile(r"\b(\d{3})[a-z]?\b")
_NEW_HINT = re.compile(r"\bnew\b|no node yet|no proposal|engineer assigns", re.I)
_UNKNOWN_VALUES = {"UNKNOWN", "NEEDS_PROPOSAL", ""}


def build_register_index() -> Dict[str, List[str]]:
    """SFI code (region or subsystem) -> existing Register node ids under it —
    lets the engineer see at a glance what's already there before deciding
    whether a proposal is genuinely new or should attach to something real."""
    reg = json.loads((STATE / "register_gelliceaux_001.json").read_text())
    idx: Dict[str, List[str]] = {}
    for e in reg["entries"]:
        for code in (e.get("subsystem_code"), e.get("region_code")):
            if code:
                idx.setdefault(code, []).append(e["equipment_id"])
    return idx


REGISTER_INDEX = build_register_index()


def decode_node(proposed_raw: str) -> Dict[str, Any]:
    """proposed_raw is inconsistently formatted in the source drafts — clean
    slugs ('630-mastervolt-batteries-chargers'), NEW:-prefixed slugs, and
    free-text ('590 aircon (existing subsystem — node: Termodinamica)').
    Splits into a clean node_id_display + a separate note, decodes the SFI
    code to a human label, and cross-references the Register for what
    already exists under that code."""
    raw = (proposed_raw or "").strip()
    if raw in _UNKNOWN_VALUES:
        return {"node_id": None, "note": None, "is_new": None, "needs_engineer": True,
                "system_label": None, "existing_nodes_at_code": [], "raw": raw or "UNKNOWN"}
    is_new = raw.startswith("NEW:") or bool(_NEW_HINT.search(raw))
    body = raw[4:] if raw.startswith("NEW:") else raw
    # split primary token from a trailing parenthetical / free-text note
    m = re.match(r"^([^(]+?)(?:\s*\((.+)\))?$", body)
    primary, note = (m.group(1).strip(), m.group(2)) if m else (body, None)
    m2 = _CODE_RE.search(primary)
    code = m2.group(1) if m2 else None
    system_label = SFI_LABELS.get(code)
    existing = REGISTER_INDEX.get(code, []) if code else []
    return {"node_id": primary, "note": note, "is_new": is_new, "needs_engineer": False,
            "system_label": system_label, "existing_nodes_at_code": existing, "raw": raw}


# ---------------------------------------------------------------- kind classifier
_PATTERNS: List[tuple] = [
    ("instrument_gauge", re.compile(
        r"volt\s*meter|voltage.*\(v\)|frequency meter|\(hz\)|ammeter|\(a\)$|"
        r"pressure gauge|temp(erature)? gauge|\bgauge\b", re.I)),
    ("current_transformer", re.compile(r"\bCT\s?\d+\b|current transformer", re.I)),
    ("alarm_monitor", re.compile(r"\balarm\b|\bind\.?\b|indicator|monitor(ing)?", re.I)),
    ("control_relay", re.compile(r"^Re\b|^K\d\b|\brelay\b|\bcontactor\b|\bresistor\b", re.I)),
    ("breaker_protective_device", re.compile(
        r"^(Q|QE|F)\s?\d+\b|isolator|breaker|\bfuse\b|earth leakage", re.I)),
    ("signal_status_tap", re.compile(
        r"\bsignal\b|\bstatus\b|\btap\b|^XA|hvil|can\s*(bus|hi|lo)", re.I)),
    ("power_source_unit", re.compile(r"^BEL|converter|600V\s*DC|shore power", re.I)),
    ("selector_switch", re.compile(r"selector|selection", re.I)),
]


def classify_kind(load_name: str) -> str:
    for kind, pat in _PATTERNS:
        if pat.search(load_name):
            return kind
    return "equipment"  # default: named consuming load (pump/system/light circuit)


_STRIP_PREFIX = re.compile(r"^(none|<unknown>|#\d+)\s*", re.I)


def clean_label(load_name: str) -> str:
    return _STRIP_PREFIX.sub("", load_name).strip() or load_name


# ---------------------------------------------------------------- merge
def merge() -> Dict[str, Any]:
    v1_sheets = json.loads((STATE / "load_map_gelliceaux_001.EXTENSION.DRAFT.json").read_text())["sheets"]
    v2_sheets = json.loads((STATE / "load_map_gelliceaux_001.EXTENSION.DRAFT_v2.json").read_text())["sheets"]
    v2_by_page = {s["page"]: s for s in v2_sheets}

    out_sheets = []
    total = 0
    for s1 in sorted(v1_sheets, key=lambda s: s["page"]):
        page = s1["page"]
        s2 = v2_by_page.get(page)
        proposals = {l["load"]: l["proposed"] for l in s2["loads"]} if s2 else {}
        rows = []
        for load_name in s1["unresolved"]:
            proposed_raw = proposals.get(load_name, "NEEDS_PROPOSAL")
            decoded = decode_node(proposed_raw)
            rows.append({
                "instrument": clean_label(load_name),
                "instrument_raw": load_name,
                "kind": classify_kind(load_name),
                "proposed_node_id": decoded["node_id"],
                "proposed_node_note": decoded["note"],
                "proposed_system_label": decoded["system_label"],
                "is_new_node": decoded["is_new"],
                "needs_engineer": decoded["needs_engineer"],
                "existing_nodes_at_code": decoded["existing_nodes_at_code"],
                "engineer_decision": "",
            })
            total += 1
        out_sheets.append({
            "page": page, "sheet": s1["sheet"],
            "v2_reached_this_sheet": s2 is not None,
            "loads": rows,
        })

    return {
        "vessel": "gelliceaux_001",
        "generated": "2026-07-11",
        "note": ("Streamlined merge of load_map_gelliceaux_001.DRAFT.json (v1, GMMS-111 — "
                 "verified fully CLOSED, every entry present in the active map, history only, "
                 "not included below) + EXTENSION.DRAFT.json (29 sheets/479 loads) + "
                 "EXTENSION.DRAFT_v2.json (21/29 sheets proposed — the 8 missing sheets are "
                 "carried forward here with needs_engineer=true, not dropped)."),
        "sheets_total": len(out_sheets),
        "loads_total": total,
        "sheets": out_sheets,
    }


if __name__ == "__main__":
    doc = merge()
    out_path = STATE / "load_map_gelliceaux_001.STREAMLINED.json"
    out_path.write_text(json.dumps(doc, indent=1))
    print(f"sheets: {doc['sheets_total']}  loads: {doc['loads_total']}")
    import collections
    kinds = collections.Counter(
        l["kind"] for s in doc["sheets"] for l in s["loads"])
    print("kind distribution:", dict(kinds))
    need_eng = sum(1 for s in doc["sheets"] for l in s["loads"] if l["needs_engineer"])
    print(f"needs_engineer (no proposal at all): {need_eng}")
    print(f"wrote {out_path}")
