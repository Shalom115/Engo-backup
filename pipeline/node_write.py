"""
§9d NODE WRITER — resolve-first, two-path. Attaches facts discovered in a drawing
onto the equipment-register node tree. NEVER writes blind: every discovered element
is resolved against the existing Register first (attach-on-match / create-flagged-on-
no-match), so text/folder ingestion builds the initial node set and schematic/visual
ingestion resolves-and-attaches.

PATH 1 — MANIFOLD / BLOCK (is equipment): resolve via §9e node_match.resolve() →
  attach the block's facts to the matched node, or create a new FLAGGED node.

PATH 2 — FUNCTION SLICE (is a control fact, not equipment): resolve which equipment
  it CONTROLS, in this order (per the locked design):
    1. control-map lookup (function label + aliases) → attach HIGH-confidence, cite
       the doc that stated the mapping; apply the map's cross-links.
    2. not in map → §9e semantic matcher (token+zone) ≥ threshold → attach w/ caveat.
    3. still below → create_flagged for engineer review. NEVER wrong-attach.

Every attached fact carries {source_doc, page/sheet, bbox, source_type, authority,
confidence, as_of}. Conflicts (a new fact value contradicts an existing one of the
same kind) set the node's identity_status='conflict' with BOTH values+sources inline
— never log-only.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import config
from pipeline import node_match
from pipeline import abbrev
from pipeline import revision_gate

FUZZY_FLOOR = 0.5  # token-set Jaccard floor for a fuzzy control-map match; below -> flag

# source_types the hydraulic CONTROL MAP may match against. The 10-sheet sweep proved
# routing OTHER doc classes through it wrong-attaches (building-drawing callout
# 'RUNNING BACKSTAY CABLE' -> the backstay cylinder). Electrical/GA/building facts
# resolve via §9e or their own routers — never the hydraulic control map.
_CONTROL_MAP_SOURCE_TYPES = ("schematic", "hydraulic_schematic")


def _norm(s: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


class NodeWriter:
    def __init__(self, vessel: Optional[str] = None, *, dry_run: bool = True):
        self.vessel = vessel or config.VESSEL_NAMESPACE
        self.dry_run = dry_run
        self.reg_path = config.STATE_DIR / f"register_{self.vessel}.json"
        self.reg = json.loads(self.reg_path.read_text())
        self.entries = self.reg["entries"]
        self.by_id = {e["equipment_id"]: e for e in self.entries}
        cm_path = config.STATE_DIR / f"control_map_{self.vessel}.json"
        self.control_map = json.loads(cm_path.read_text())
        self._build_control_index()
        self.decisions: List[Dict[str, Any]] = []
        # END-OF-SWEEP confirmation flags: multi-model / identity-conflict nodes.
        # Engo never silently picks or splits — these surface for the engineer.
        self.confirmation_flags: List[Dict[str, Any]] = []
        # REVISION GATE: facts from superseded drawing revisions are refused.
        self.superseded_ids = revision_gate.load_superseded(self.vessel)
        # ELECTRICAL LOAD MAP (engineer-confirmed load-name -> node), if active.
        lm_path = config.STATE_DIR / f"load_map_{self.vessel}.json"
        self.load_map: Dict[str, str] = {}
        if lm_path.exists():
            lm = json.loads(lm_path.read_text())
            if lm.get("status") == "active":
                self.load_map = {k.upper(): v for k, v in lm.get("mappings", {}).items()}

    def _revision_refused(self, source_ref: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        fid = source_ref.get("drive_file_id")
        if fid and fid in self.superseded_ids:
            dec = {"action": "refused_superseded", "source_doc": source_ref.get("source_doc"),
                   "drive_file_id": fid,
                   "reason": "revision gate: this file is a SUPERSEDED revision — facts must come from the current revision"}
            self.decisions.append(dec)
            return dec
        return None

    def _build_control_index(self) -> None:
        """Normalized alias/function -> mapping, for O(1) exact lookup."""
        self._cidx: Dict[str, Dict[str, Any]] = {}
        for m in self.control_map["mappings"]:
            for key in [m["function"], *m.get("aliases", [])]:
                self._cidx.setdefault(_norm(key), m)

    # ---- control-map resolution (Path 2 step 1), abbreviation-tolerant ----
    def _containment(self, n: str) -> Optional[Dict[str, Any]]:
        """Match if a control-map key is a contiguous TOKEN subsequence of n
        (token-boundary safe — 'vang' won't match inside 'vanguard'). Longest key wins."""
        nt = n.split()
        best = None
        for key, m in self._cidx.items():
            kt = key.split()
            if not kt:
                continue
            for i in range(len(nt) - len(kt) + 1):
                if nt[i:i + len(kt)] == kt:
                    if best is None or len(kt) > len(best[0].split()):
                        best = (key, m)
                    break
        return best[1] if best else None

    def _resolve_control(self, label: str):
        """Return (mapping, mechanism, score). mechanism in
        {exact, exact_containment, abbreviation_expanded, fuzzy} or (None,None,score)."""
        n = _norm(label)
        if n in self._cidx:
            return self._cidx[n], "exact", 1.0
        m = self._containment(n)
        if m:
            return m, "exact_containment", 0.95
        # abbreviation expansion, then retry exact + containment on the expanded form
        ex = abbrev.expand(label)
        if ex != n:
            if ex in self._cidx:
                return self._cidx[ex], "abbreviation_expanded", 0.9
            m = self._containment(ex)
            if m:
                return m, "abbreviation_expanded", 0.85
        # fuzzy: max token-set Jaccard over each mapping's function+aliases (expanded tokens)
        toks = set(ex.split())
        best, bscore = None, 0.0
        for mp in self.control_map["mappings"]:
            for key in [mp["function"], *mp.get("aliases", [])]:
                kt = set(_norm(key).split())
                if not kt:
                    continue
                j = len(toks & kt) / len(toks | kt)
                if j > bscore:
                    bscore, best = j, mp
        if best and bscore >= FUZZY_FLOOR:
            return best, "fuzzy", round(bscore, 2)
        return None, None, round(bscore, 2)

    # ---- fact attachment with provenance + conflict handling ----
    def _attach_fact(self, node_id: str, kind: str, value: Any,
                     provenance: Dict[str, Any], confidence: str) -> Dict[str, Any]:
        node = self.by_id[node_id]
        node.setdefault("facts", [])
        node.setdefault("identity_status", "pending")
        fact = {"kind": kind, "value": value, "confidence": confidence,
                "as_of": datetime.now(timezone.utc).date().isoformat(),
                "provenance": provenance}
        # conflict: an existing IDENTITY fact of the same kind with a different value
        conflict = None
        if kind in ("make", "model"):
            for f in node["facts"]:
                if f["kind"] == kind and _norm(str(f["value"])) != _norm(str(value)):
                    conflict = f
                    break
        node["facts"].append(fact)
        if conflict:
            node["identity_status"] = "conflict"
            entry = {
                "kind": kind,
                "values": [{"value": conflict["value"], "provenance": conflict["provenance"]},
                           {"value": value, "provenance": provenance}],
            }
            node.setdefault("conflicts", []).append(entry)
            # surface for end-of-sweep engineer review (never auto-resolve)
            self.confirmation_flags.append({"node_id": node_id, "issue_type": "identity_conflict",
                                            "detail": f"conflicting {kind} values from different sources", **entry})
        # mark the fact-class as contributed (Decision-2 completeness checklist)
        st = provenance.get("source_type")
        if st and st not in node.get("fact_classes_present", []):
            node.setdefault("fact_classes_present", []).append(st)
        return {"attached_to": node_id, "kind": kind, "conflict": bool(conflict)}

    def _add_cross_links(self, node_id: str, cross_links: List[Dict[str, str]], source: Dict) -> None:
        node = self.by_id[node_id]
        existing = {(c["relation"], c["target"]) for c in node.get("cross_links", [])}
        for cl in cross_links:
            if (cl["relation"], cl["target"]) not in existing:
                node.setdefault("cross_links", []).append({**cl, "source": source})

    # ---- PATH 2: a hydraulic function slice ----
    def write_function_slice(self, slice_obj: Dict[str, Any], source_ref: Dict[str, Any]) -> Dict[str, Any]:
        refused = self._revision_refused(source_ref)
        if refused:
            return refused
        label = slice_obj.get("label") or slice_obj.get("function") or ""
        prov = {**source_ref, "authority": source_ref.get("authority", "schematic")}
        # SOURCE-TYPE GATE: the control map is hydraulic-function vocabulary only
        st = source_ref.get("source_type", "schematic")
        if st in _CONTROL_MAP_SOURCE_TYPES:
            m, mech, score = self._resolve_control(label)
        else:
            m, mech, score = None, None, 0.0
        if m:
            tgt = m["target_node_id"]
            conf = {"exact": "high", "exact_containment": "high",
                    "abbreviation_expanded": "medium", "fuzzy": "caveat"}.get(mech, "medium")
            match_meta = {"match_mechanism": mech, "match_score": score,
                          "control_map_function": m["myt_function"]}
            # attach the slice's discovered facts (rating/actuation/cartridges/settings)
            for kind in ("rating", "actuation", "cartridges", "settings", "spool", "flow"):
                if slice_obj.get(kind) is not None:
                    self._attach_fact(tgt, kind, slice_obj[kind], {**prov, **match_meta}, conf)
            # record the control-fact linkage itself (cites the mapping doc)
            self._attach_fact(tgt, "hydraulic_control_function", label,
                              {**prov, "mapped_via": "control_map", **match_meta, **m["source"]}, conf)
            if m.get("cross_links"):
                self._add_cross_links(tgt, m["cross_links"], m["source"])
            dec = {"slice": label, "action": "attach", "target": tgt, "via": "control_map",
                   "myt_function": m["myt_function"], "mechanism": mech, "score": score,
                   "confidence": conf}
        else:
            comp = {"name": label, "function": label,
                    "region_code": source_ref.get("region_code"),
                    "subsystem_code": source_ref.get("subsystem_code")}
            r = node_match.resolve(comp, self.entries)
            if r["action"] == "attach":
                self._attach_fact(r["match_id"], "hydraulic_control_function", label,
                                  {**prov, "mapped_via": "semantic_matcher", "score": r["confidence"]}, "caveat")
                dec = {"slice": label, "action": "attach", "target": r["match_id"],
                       "via": "semantic_matcher", "confidence": "caveat", "score": r["confidence"]}
            else:
                dec = {"slice": label, "action": "create_flagged", "target": None,
                       "via": "no_match", "confidence": r["confidence"],
                       "reason": "no control-map entry and semantic match below threshold"}
        self.decisions.append(dec)
        return dec

    # ---- ELECTRICAL: a distribution-schedule row (breaker/fuse -> load) ----
    # FEEDER ≠ LOAD (engineer rule, 2026-07-04): a schedule/wiring row can feed a
    # SUB-DISTRIBUTION BOX, not an equipment — 'GALLEY' on GM-102 is a dist box
    # holding many component breakers whose manuals live elsewhere (e.g. 360); the
    # component breakers route to equipment from the SUB-PANEL's own sheet, not here.
    _FEEDER_KEYWORDS = re.compile(
        r"\b(PANEL|DIST(RIBUTION)?|SWITCHBOARD|BOX|BOARD|ENCLOSURE|SUB-?DB)\b", re.I)

    def _is_feeder(self, load: str, resolved_node: Optional[Dict[str, Any]]) -> bool:
        if self._FEEDER_KEYWORDS.search(load or ""):
            return True
        if resolved_node and self._FEEDER_KEYWORDS.search(str(resolved_node.get("category") or "")):
            return True
        return False

    def write_electrical_row(self, row: Dict[str, Any], source_ref: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route one schedule row. The LOAD is the equipment -> resolve via §9e (NEVER the
        hydraulic control map — source-type gate). The protective device becomes an
        ELECTRICAL-SUPPLY FACT on the load's node: {device_type, id, rating, panel}.
        No/weak match -> create_flagged (never wrong-attach).
        FEEDER ≠ LOAD: if the row's "load" is itself a sub-distribution box (not an
        equipment), attach a `feeds` cross-link + a feeder fact on the PANEL card
        instead — never invent an equipment identity for a distribution box.
        """
        refused = self._revision_refused(source_ref)
        if refused:
            return refused
        load = row.get("load_name") or ""
        prov = {**source_ref, "authority": source_ref.get("authority", "electrical_schematic")}
        if not load.strip() or load.strip() in ("/", "-", "<UNKNOWN>"):
            dec = {"row": row.get("device_id"), "action": "skipped_spare",
                   "reason": "no load name (spare way)"}
            self.decisions.append(dec)
            return dec
        # 1) ENGINEER-CONFIRMED LOAD MAP first (mirrors the hydraulic control map)
        tgt = self.load_map.get(load.strip().upper())
        if tgt and tgt in self.by_id and self._is_feeder(load, self.by_id[tgt]):
            fact = {"device_type": row.get("device_type"), "device_id": row.get("device_id"),
                    "rating": row.get("rating"), "panel": source_ref.get("panel")}
            self._attach_fact(tgt, "feeder_supply", fact,
                              {**prov, "mapped_via": "load_map_engineer_confirmed",
                               "load_as_printed": load,
                               "note": "FEEDER not LOAD — this row feeds a sub-distribution box; its component breakers live on that box's own sheet"},
                              "high")
            dec = {"row": f"{row.get('device_id')} {load}", "action": "attach_feeder",
                   "target": tgt, "via": "load_map"}
            self.decisions.append(dec)
            return dec
        if tgt and tgt in self.by_id:
            fact = {"device_type": row.get("device_type"), "device_id": row.get("device_id"),
                    "rating": row.get("rating"), "panel": source_ref.get("panel")}
            # idempotency: the same supply fact (device id + load) re-read from another
            # export of the same drawing must ENRICH-or-skip, never duplicate
            for f in (self.by_id[tgt].get("facts") or []):
                if (f.get("kind") == "electrical_supply"
                        and (f.get("value") or {}).get("device_id") == fact["device_id"]
                        and (f.get("provenance") or {}).get("load_as_printed") == load):
                    dec = {"row": f"{row.get('device_id')} {load}", "action": "already_attached",
                           "target": tgt}
                    self.decisions.append(dec)
                    return dec
            self._attach_fact(tgt, "electrical_supply", fact,
                              {**prov, "mapped_via": "load_map_engineer_confirmed",
                               "load_as_printed": load}, "high")
            dec = {"row": f"{row.get('device_id')} {load}", "action": "attach",
                   "target": tgt, "via": "load_map", "confidence": "high"}
            self.decisions.append(dec)
            return dec
        # 2) abbreviation-tolerant load resolution via §9e (expand first, then match)
        expanded = abbrev.expand(load)
        comp = {"name": expanded, "function": expanded,
                "region_code": source_ref.get("region_code"),
                "subsystem_code": source_ref.get("subsystem_code")}
        r = node_match.resolve(comp, self.entries)
        if r["action"] == "attach" and self._is_feeder(load, r["match"]):
            fact = {"device_type": row.get("device_type"), "device_id": row.get("device_id"),
                    "rating": row.get("rating"), "panel": source_ref.get("panel")}
            self._attach_fact(r["match_id"], "feeder_supply", fact,
                              {**prov, "mapped_via": "semantic_matcher", "match_score": r["confidence"],
                               "load_as_printed": load,
                               "note": "FEEDER not LOAD — feeds a sub-distribution box; component breakers live on that box's own sheet"},
                              "high" if r["confidence"] >= 0.6 else "caveat")
            dec = {"row": f"{row.get('device_id')} {load}", "action": "attach_feeder",
                   "target": r["match_id"], "score": r["confidence"]}
            self.decisions.append(dec)
            return dec
        if r["action"] == "attach":
            fact = {"device_type": row.get("device_type"), "device_id": row.get("device_id"),
                    "rating": row.get("rating"), "panel": source_ref.get("panel")}
            self._attach_fact(r["match_id"], "electrical_supply", fact,
                              {**prov, "mapped_via": "semantic_matcher",
                               "match_score": r["confidence"],
                               "load_as_printed": load}, "high" if r["confidence"] >= 0.6 else "caveat")
            dec = {"row": f"{row.get('device_id')} {load}", "action": "attach",
                   "target": r["match_id"], "score": r["confidence"]}
        else:
            dec = {"row": f"{row.get('device_id')} {load}", "action": "create_flagged",
                   "target": None, "score": r["confidence"],
                   "reason": "load not resolvable to a Register node (thin-Register expected)"}
        self.decisions.append(dec)
        return dec

    # CONTROL ≠ INDICATOR ≠ SUPPLY (engineer rule, 2026-07-04; §6 extension): every
    # wiring element is exactly one of these roles. Ingesting an indicator as a control
    # is a wrong relationship (e.g. the VCP's BEL/MAPS lamps are STATUS, not control).
    _SUPPLY_TYPES = {"breaker", "fuse", "emergency_breaker", "circuit_breaker", "current_transformer"}
    _INDICATOR_TYPES = {"status_signal"}
    _CONTROL_TYPES = {"switch"}

    def write_wiring_element(self, el: Dict[str, Any], source_ref: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route one wiring-diagram element. Role is taken from element_type, never
        guessed from the label: SUPPLY (breaker/fuse/...) resolves like a schedule
        row (incl. the FEEDER check); INDICATOR (status_signal) attaches as an
        `indicates_status_of` cross-link, NEVER as a control fact; CONTROL (switch)
        attaches as a `controls`/`controlled_by` cross-link. Structural/descriptive
        types (terminal, relay, controller_module, plug_pin, device, unknown) are
        NOT written this pass — flagged honestly rather than mis-routed.
        """
        refused = self._revision_refused(source_ref)
        if refused:
            return refused
        etype = el.get("element_type")
        label = (el.get("label") or "").strip()
        prov = {**source_ref, "authority": source_ref.get("authority", "electrical_schematic"),
               "element_id": el.get("id"), "bbox": el.get("_bbox") or el.get("bbox")}
        if not label or label.upper() in ("/", "-", "<UNKNOWN>"):
            dec = {"element": el.get("id"), "action": "skipped_unlabeled"}
            self.decisions.append(dec)
            return dec

        expanded = abbrev.expand(label)
        comp = {"name": expanded, "function": expanded,
                "region_code": source_ref.get("region_code"),
                "subsystem_code": source_ref.get("subsystem_code")}
        r = node_match.resolve(comp, self.entries)

        if etype in self._SUPPLY_TYPES:
            row = {"device_type": etype, "device_id": el.get("id"), "rating": el.get("rating"),
                  "load_name": label}
            return self.write_electrical_row(row, source_ref)

        if etype in self._INDICATOR_TYPES:
            if r["action"] != "attach":
                dec = {"element": f"{el.get('id')} {label}", "action": "create_flagged",
                       "role": "indicator", "reason": "indicator target not resolvable"}
                self.decisions.append(dec)
                return dec
            tgt = r["match_id"]
            self._add_cross_links(tgt, [{"relation": "has_status_indicator_on",
                                        "target": source_ref.get("panel_node_id", "vcp")}],
                                  {**prov, "note": "INDICATOR only — status lamp/signal, NOT a control relationship"})
            self._attach_fact(tgt, "status_indicator", {"element_id": el.get("id"), "label": label},
                              {**prov, "mapped_via": "semantic_matcher", "match_score": r["confidence"]}, "caveat")
            dec = {"element": f"{el.get('id')} {label}", "action": "attach_indicator", "target": tgt}
            self.decisions.append(dec)
            return dec

        if etype in self._CONTROL_TYPES:
            if r["action"] != "attach":
                dec = {"element": f"{el.get('id')} {label}", "action": "create_flagged",
                       "role": "control", "reason": "control target not resolvable"}
                self.decisions.append(dec)
                return dec
            tgt = r["match_id"]
            self._attach_fact(tgt, "control_element", {"element_id": el.get("id"), "label": label},
                              {**prov, "mapped_via": "semantic_matcher", "match_score": r["confidence"]}, "caveat")
            dec = {"element": f"{el.get('id')} {label}", "action": "attach_control", "target": tgt}
            self.decisions.append(dec)
            return dec

        # structural/descriptive (terminal, terminal_strip, relay, controller_module,
        # plug_pin, device, unknown) — not routed this pass, surfaced not dropped
        dec = {"element": f"{el.get('id')} {label}", "action": "not_routed",
               "reason": f"element_type='{etype}' is structural/descriptive — routing not built this pass"}
        self.decisions.append(dec)
        return dec

    # ---- PATH 1: a manifold / block (is equipment) ----
    def _create_flagged_node(self, make_model: str, block: Dict[str, Any],
                             source_ref: Dict[str, Any]) -> str:
        """Really create a FLAGGED Register node for discovered-but-unmatched equipment
        (the §9e create-flagged contract). Only called on real (non-dry) runs."""
        slug = re.sub(r"[^a-z0-9]+", "-", make_model.lower()).strip("-")
        sheet = re.sub(r"[^a-z0-9]+", "-", str(source_ref.get("sheet", "")).lower()).strip("-")
        sub = source_ref.get("subsystem_code") or source_ref.get("region_code") or "000"
        eid = "-".join(x for x in (str(sub), slug, sheet) if x)
        if eid in self.by_id:
            return eid
        node = {"equipment_id": eid, "name": make_model, "make": block.get("make"),
                "model": make_model, "category": "Discovered in schematic",
                "acronyms": [], "region_code": source_ref.get("region_code"),
                "region_label": None, "subsystem_code": source_ref.get("subsystem_code"),
                "subsystem_label": None, "functions": [],
                "source_paths": [], "source_folder_ids": [], "doc_subfolders": {},
                "file_count": 0, "flags": ["created_from_schematic_discovery"],
                "confidence": "Flagged", "parent_id": None, "children": [],
                "cross_links": [], "expected_fact_classes": ["manual", "schematic", "inventory"],
                "fact_classes_present": [], "retired": False, "merged_from": [],
                "origin": "schematic discovery (resolve-first: no Register match)",
                "node_provenance": [dict(source_ref)], "identity_status": "pending",
                "facts": []}
        self.entries.append(node)
        self.by_id[eid] = node
        return eid

    def write_block(self, block: Dict[str, Any], source_ref: Dict[str, Any]) -> Dict[str, Any]:
        """
        PER-INSTALLATION RESOLUTION (hardened 2026-07-02 after the real pass piled six
        different physical manifolds onto one node via §9e model-matching, and matched
        MYT headers to a sealogs bucket on the generic word 'Systems'). A block is a
        PHYSICAL INSTALLATION: it attaches ONLY to (a) the node whose id is its own
        per-installation slug, or (b) a node whose provenance carries the SAME drawing
        (drive_file_id). Same model on a different sheet = a DIFFERENT unit (winch/
        thruster granularity rule). No generic §9e matching for blocks.
        """
        refused = self._revision_refused(source_ref)
        if refused:
            return refused
        make_model = block.get("make_model") or block.get("model") or ""
        prov = {**source_ref, "authority": source_ref.get("authority", "schematic")}
        slug = re.sub(r"[^a-z0-9]+", "-", make_model.lower()).strip("-")
        sheet = re.sub(r"[^a-z0-9]+", "-", str(source_ref.get("sheet", "")).lower()).strip("-")
        sub = source_ref.get("subsystem_code") or source_ref.get("region_code") or "000"
        install_eid = "-".join(x for x in (str(sub), slug, sheet) if x)
        target = None
        if install_eid in self.by_id:
            target = install_eid
        else:
            fid = source_ref.get("drive_file_id")
            for e in self.entries:
                if fid and any(p.get("drive_file_id") == fid
                               for p in (e.get("node_provenance") or [])):
                    target = e["equipment_id"]
                    break
        if target:
            self._attach_fact(target, "block_identity", make_model, prov, "high")
            dec = {"block": make_model, "action": "attach", "target": target,
                   "confidence": 1.0, "reason": ["per-installation id/provenance match"]}
        elif not self.dry_run:
            eid = self._create_flagged_node(make_model, block, source_ref)
            self._attach_fact(eid, "block_identity", make_model, prov, "high")
            dec = {"block": make_model, "action": "created_flagged_node", "target": eid,
                   "confidence": None,
                   "reason": "no per-installation match — flagged node created for engineer review"}
        else:
            dec = {"block": make_model, "action": "create_flagged", "target": None,
                   "confidence": None,
                   "reason": "manifold/block: no per-installation match — new equipment to surface"}
        self.decisions.append(dec)
        return dec

    # ---- process a whole discovered structure (Path 1 block + Path 2 slices) ----
    def write_structure(self, discovered: Dict[str, Any], source_ref: Dict[str, Any]) -> List[Dict[str, Any]]:
        header = discovered.get("header") or {}
        if header.get("make_model") or header.get("model"):
            self.write_block(header, source_ref)
        for sl in discovered.get("slices", []):
            self.write_function_slice(sl, source_ref)
        return self.decisions

    def flush_confirmation_flags(self) -> int:
        """
        Merge this run's confirmation_flags (identity_conflict / multi_model) into the
        persistent END-OF-SWEEP ENGINEER CONFIRMATION LIST. Engo NEVER auto-resolves —
        it only surfaces. Dedups by (node_id, issue_type). Returns number newly added.
        Refuses in dry_run (nothing persists during a logic check).
        """
        if self.dry_run:
            raise RuntimeError("dry_run=True: refusing to persist confirmation flags.")
        path = config.STATE_DIR / f"engineer_confirmation_list_{self.vessel}.json"
        doc = json.loads(path.read_text()) if path.exists() else {"vessel": self.vessel, "entries": []}
        seen = {(e.get("node_id"), e.get("issue_type")) for e in doc["entries"]}
        n = len(doc["entries"])
        added = 0
        for fl in self.confirmation_flags:
            key = (fl.get("node_id"), fl.get("issue_type"))
            if key in seen:
                continue
            seen.add(key)
            n += 1
            doc["entries"].append({"id": f"cf-{n:03d}", **fl, "engineer_comment": "", "status": "open"})
            added += 1
        path.write_text(json.dumps(doc, indent=2))
        return added

    def save(self) -> None:
        if self.dry_run:
            raise RuntimeError("dry_run=True: refusing to persist. Set dry_run=False for a real write.")
        self.reg["stats"]["entries"] = len(self.entries)
        self.reg_path.write_text(json.dumps(self.reg, indent=2))
