"""
WP2 — COMPOSITION → REGISTER BRIDGE (built 2026-07-20 per TODO.md §2).

Takes a graded composition and writes its knowledge onto the Register nodes:
- per equipment-group function: a flow_scenarios fact (scenario list verbatim),
  a dry_data fact, key_components — each with full provenance incl. the
  sheet_region so Engo can point at the drawing;
- infrastructure entries → their system node;
- uncertainties → the durable engineer red-pen queue
  (open_uncertainties_<vessel>.jsonl);
- discarded_as_clutter → run ledger only.

Discipline (§0 commandments): NEVER creates a node — a missing/unknown target
is a confirmation-list finding; revision gate refuses superseded sources;
fact-hash idempotency (re-run = 0 new facts); dry_run default, real writes
need for_real=True (engineer GO recorded by the caller); backup before any
real save; integrity check after.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import config
from pipeline import revision_gate

UNCERT_PATH = config.STATE_DIR / f"open_uncertainties_{config.VESSEL_NAMESPACE}.json"


def _hash(node_id: str, kind: str, sheet: str, label: str, value: str) -> str:
    key = "|".join([node_id, kind, sheet, label,
                    " ".join(str(value).lower().split())[:400]])
    return hashlib.sha256(key.encode()).hexdigest()[:16]


class ComposeWriter:
    def __init__(self, vessel: Optional[str] = None, *, dry_run: bool = True):
        self.vessel = vessel or config.VESSEL_NAMESPACE
        self.dry_run = dry_run
        self.reg_path = config.STATE_DIR / f"register_{self.vessel}.json"
        self.reg = json.loads(self.reg_path.read_text())
        self.by_id = {e["equipment_id"]: e for e in self.reg["entries"]}
        self.superseded = revision_gate.load_superseded(self.vessel)
        self.existing_hashes = {
            f.get("fact_hash") for e in self.reg["entries"]
            for f in e.get("facts") or [] if f.get("fact_hash")}
        self.decisions: List[Dict[str, Any]] = []
        self.uncertainties: List[Dict[str, Any]] = []
        self.confirmation_flags: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    def _note(self, **kw) -> None:
        self.decisions.append(kw)

    def _attach(self, node_id: str, kind: str, value: Any, sheet_ref: Dict[str, Any],
                label: str, region: Optional[str], confidence: str = "high") -> None:
        node = self.by_id.get(node_id)
        if node is None or node.get("retired"):
            self.confirmation_flags.append(
                {"issue": "target_missing_or_retired", "node_id": node_id,
                 "label": label, "sheet": sheet_ref.get("sheet")})
            self._note(action="flagged_missing_target", node=node_id, label=label)
            return
        h = _hash(node_id, kind, sheet_ref.get("sheet", ""), label, str(value))
        if h in self.existing_hashes:
            self._note(action="skip_duplicate", node=node_id, kind=kind, label=label)
            return
        fact = {"kind": kind, "value": value, "confidence": confidence,
                "fact_hash": h,
                "provenance": {
                    "source_doc": sheet_ref.get("source_doc"),
                    "drive_file_id": sheet_ref.get("drive_file_id"),
                    "page": sheet_ref.get("page"),
                    "sheet": sheet_ref.get("sheet"),
                    "sheet_region": region,
                    "source_type": "composition",
                    "drawing_class": sheet_ref.get("drawing_class"),
                    "as_of": str(date.today())}}
        if self.dry_run:
            self._note(action="would_attach", node=node_id, kind=kind, label=label)
        else:
            node.setdefault("facts", []).append(fact)
            self.existing_hashes.add(h)
            self._note(action="attached", node=node_id, kind=kind, label=label)

    # ------------------------------------------------------------------
    def write_composition(self, comp: Dict[str, Any],
                          sheet_ref: Dict[str, Any]) -> Dict[str, int]:
        """Write one composition. Returns summary counts."""
        from pipeline.compose import PROTOCOL_VERSION
        got = comp.get("_protocol_version")
        if got != PROTOCOL_VERSION:
            self._note(action="refused_stale_protocol",
                       sheet=sheet_ref.get("sheet"),
                       composed_under=got, current=PROTOCOL_VERSION)
            return {"refused_stale_protocol": 1}
        fid = sheet_ref.get("drive_file_id")
        if fid and fid in self.superseded:
            self._note(action="refused_superseded", sheet=sheet_ref.get("sheet"))
            return {"refused_superseded": 1}

        for g in comp.get("equipment_groups", []):
            tgt = g.get("target_node_id")
            gname = g.get("equipment_name", "?")
            if not tgt:
                self.confirmation_flags.append(
                    {"issue": "no_fitting_node", "equipment_name": gname,
                     "sheet": sheet_ref.get("sheet"),
                     "reasoning": g.get("placement_reasoning", "")[:200]})
                self._note(action="flagged_no_node", label=gname)
                continue
            for f in g.get("functions", []):
                label = f.get("label", gname)
                region = f.get("sheet_region")
                scenarios = f.get("flow_scenarios") or []
                if scenarios:
                    self._attach(tgt, "flow_scenarios",
                                 {"function": label,
                                  "function_id": f.get("function_id"),
                                  "what_it_does": f.get("what_it_does"),
                                  "scenarios": scenarios},
                                 sheet_ref, label, region)
                if f.get("dry_data"):
                    self._attach(tgt, "dry_data",
                                 {"function": label, "dry_data": f["dry_data"]},
                                 sheet_ref, label, region)
                if f.get("key_components"):
                    self._attach(tgt, "key_components",
                                 {"function": label,
                                  "components": f["key_components"]},
                                 sheet_ref, label, region)

        infra = comp.get("infrastructure")
        infras = infra if isinstance(infra, list) else ([infra] if infra else [])
        for inf in infras:
            if not inf or not inf.get("facts"):
                continue
            tgt = inf.get("target_node_id")
            sysname = inf.get("system_name", "infrastructure")
            if not tgt or tgt == "<UNKNOWN>":
                self.confirmation_flags.append(
                    {"issue": "infrastructure_no_node", "system_name": sysname,
                     "sheet": sheet_ref.get("sheet"),
                     "facts_preview": inf["facts"][:2]})
                self._note(action="flagged_infra_no_node", label=sysname)
                continue
            self._attach(tgt, "infrastructure_facts",
                         {"system": sysname, "facts": inf["facts"]},
                         sheet_ref, sysname, None, confidence="high")

        uncs = comp.get("uncertainties") or []
        if isinstance(uncs, str):          # string-vs-list trap (GM-111 case):
            uncs = [uncs]                  # never iterate a string as chars
        for u in uncs:
            self.uncertainties.append({
                "sheet": sheet_ref.get("sheet"),
                "drawing_class": sheet_ref.get("drawing_class"),
                "text": u, "status": "open",
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")})

        counts: Dict[str, int] = {}
        for d in self.decisions:
            counts[d["action"]] = counts.get(d["action"], 0) + 1
        return counts

    # ------------------------------------------------------------------
    def save(self, *, for_real: bool = False) -> None:
        """Persist. Refuses unless constructed dry_run=False AND for_real."""
        if self.dry_run or not for_real:
            raise ValueError("save() refused: writer is dry-run or for_real "
                             "not set — real writes need the engineer's GO.")
        shutil.copy(self.reg_path, str(self.reg_path).replace(
            ".json", f".backup_composewrite_{date.today():%Y%m%d}.json"))
        ids = {e["equipment_id"] for e in self.reg["entries"]}
        bad = [c["target"] for e in self.reg["entries"]
               for c in e.get("cross_links") or [] if c["target"] not in ids]
        if bad:
            raise ValueError(f"integrity check FAILED before save: {bad[:5]}")
        self.reg_path.write_text(json.dumps(self.reg, indent=1))
        # durable uncertainty queue (append, dedupe by text+sheet)
        q = []
        if UNCERT_PATH.exists():
            q = json.loads(UNCERT_PATH.read_text())
        seen = {(u.get("sheet"), u.get("text")) for u in q}
        for u in self.uncertainties:
            if (u["sheet"], u["text"]) not in seen:
                q.append(u)
        UNCERT_PATH.write_text(json.dumps(q, indent=1))
