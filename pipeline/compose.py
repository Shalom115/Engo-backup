"""
EQUIPMENT-CENTRIC COMPOSITION PASS (engineer-mandated rule, 2026-07-17).

Sits between extraction and node-write. A drawing is a VIEW ONTO EQUIPMENT,
never the destination: this pass answers "which equipment does each region of
this sheet serve?", composes each function as plain-language FLOW SCENARIOS
(oil/power/signal paths with settings inline), files shared infrastructure on
the infrastructure node, filters clutter, and carries provenance so Engo can
cite the drawing without re-reading it.

Distinct from the gold-blind EXTRACTOR seam: composition is the
equipment-knowledge channel — it legitimately sees the Register index and the
engineer-confirmed control/load maps (same scoping rule as the agent prompt
and HyDE vessel context).
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import config

# ---------------------------------------------------------------------------
# Per-class composition rules. The GENERAL RULE is shared; these add the
# class-specific reading of "function", "scenario" and "infrastructure".
# ---------------------------------------------------------------------------

CLASS_RULES: Dict[str, str] = {
    "hydraulic": (
        "Function slices serve the equipment their LABEL names (e.g. three "
        "slices labelled STERN THRUSTER / S.T. UP-DOWN / S.T. LOCK all serve "
        "the stern thruster). Flow scenarios are OIL PATHS: neutral + each "
        "command state, e.g. 'pressured oil from line P through port A to the "
        "actuator, returns via port B to line T back to tank; relief set to "
        "X bar'. Relief/limiter settings go INLINE in the scenario they "
        "protect. Load-sense rails, block inlet/relief and end sections are "
        "INFRASTRUCTURE (the manifold/block node)."),
    "electrical": (
        "Each load/row/branch serves the equipment the LOAD NAME names. The "
        "scenario is the SUPPLY or CONTROL LOOP in words: 'fed from <panel> "
        "via breaker <id> <rating>' or 'commanded from <switch/panel> via "
        "terminal <n> and relay <id>; status back to monitoring via <tap>'. "
        "Bus structure, supply topology, terminal strips and relay banks are "
        "INFRASTRUCTURE (the panel/distribution node). Status taps are "
        "signals, never power."),
    "pid": (
        "The sheet describes a fluid SYSTEM. The system node gets the flow "
        "scenarios ('suction from X via strainer to pump, discharge overboard "
        "via Y'; alternate/emergency lineups as separate scenarios) plus the "
        "roster of equipment within the system. Each pump/valve/tank also "
        "gets its own role-in-flow fact on ITS node, with BOM identity "
        "(make/model per item tag) when the sheet's table provides it."),
    "plc": (
        "Each I/O channel serves the equipment its signal name names. The "
        "scenario is the COMMAND CHAIN with the side stated: 'channel <n> of "
        "module position <p> in the <rack> energises <EV/output> = <equipment "
        "action>' — record which channel drives which direction (port A vs "
        "B / open vs close). Rack layout (coupler, module types, positions) "
        "is INFRASTRUCTURE (the PLC/rack node)."),
    "building_ga": (
        "Callouts serve the equipment they point at. Facts are POSITIONS and "
        "PHYSICAL SPECS: where aboard (frame/compartment/height), dimensions, "
        "SWL, structural details. A compartment-level fact lists what lives "
        "in the compartment. No flow scenarios — location is the fact."),
    "interconnect": (
        "Each device's facts are its LOOP MEMBERSHIPS: which bus it sits on, "
        "its neighbours and terminators, and pin/wire signal chains "
        "('<signal> from <device> pin <n> via wire <id> to <device> pin "
        "<m>'). Attach to each DEVICE node; the bus/backbone description is "
        "INFRASTRUCTURE on the system node."),
    "photos": (
        "Labels and part photos yield IDENTITY facts: part number, "
        "description, quantity, order reference — attached to the equipment "
        "the part belongs to. Investigation figures yield evidence facts on "
        "the implicated system node."),
}


_COMPOSE_TOOL = {
    "name": "record_composition",
    "description": "Record the equipment-centric composition of this drawing.",
    "input_schema": {
        "type": "object",
        "properties": {
            "serve_who": {
                "type": "string",
                "description": "One short paragraph: which equipment/system "
                               "this sheet serves and the sheet evidence for "
                               "that conclusion."},
            "equipment_groups": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "target_node_id": {"type": "string"},
                        "equipment_name": {"type": "string"},
                        "placement_reasoning": {"type": "string"},
                        "functions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "function_id": {"type": "string"},
                                    "label": {"type": "string"},
                                    "what_it_does": {"type": "string"},
                                    "flow_scenarios": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "state": {"type": "string"},
                                                "path": {"type": "string"},
                                            },
                                            "required": ["state", "path"],
                                        }},
                                    "key_components": {
                                        "type": "array",
                                        "items": {"type": "string"}},
                                    "dry_data": {"type": "string"},
                                    "sheet_region": {"type": "string"},
                                },
                                "required": ["label", "what_it_does",
                                             "flow_scenarios", "dry_data"],
                            }},
                    },
                    "required": ["equipment_name", "functions",
                                 "placement_reasoning"],
                }},
            "infrastructure": {
                "type": "object",
                "properties": {
                    "target_node_id": {"type": "string"},
                    "facts": {"type": "array", "items": {"type": "string"}},
                },
            },
            "discarded_as_clutter": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Short names of extracted items filtered out "
                               "(meta, duplicates, legend repeats) — the "
                               "audit trail of the relevance filter."},
            "uncertainties": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Anything illegible/ambiguous that limits a "
                               "scenario — never guess a value."},
        },
        "required": ["serve_who", "equipment_groups", "discarded_as_clutter"],
    },
}


_COMPOSE_PROMPT = """\
You are composing a vessel drawing into EQUIPMENT-CENTRIC knowledge. The sheet
image is attached; a prior extraction of it and the vessel's equipment
register index follow.

THE GENERAL RULE — a drawing is a view onto equipment, never the destination:
1. SERVE-WHO: decide which equipment/system this sheet — and each region of
   it — serves, from the sheet's own evidence (labels, title, zone; e.g.
   several functions all naming the same equipment means they ALL belong to
   that equipment).
2. For each served equipment, choose its node from the register index and
   compose:
   - each FUNCTION in operational language — what it does for the equipment,
     not which internal part it uses;
   - FLOW SCENARIOS per function: neutral/default plus each command state,
     told as a path (source → route → target → return), with protective
     settings INLINE in the scenario they protect;
   - KEY COMPONENTS by role (relief, lock, check, sensor) — identifiers
     secondary to role;
   - a compact DRY DATA line (module/actuation/rating) — always AFTER the
     scenarios;
   - sheet_region: where on the sheet this lives (so the drawing can be
     cited without re-reading).
3. Shared infrastructure (rails, supply/inlet sections, bus structure, rack
   layout) goes to the infrastructure node, NOT the equipment nodes.
4. RELEVANCE FILTER: extraction meta, duplicate repeats, legend rows that
   restate function data — discard, but list what you discarded.
5. Values you cannot read cleanly are UNCERTAINTIES — state them; never guess.
6. Use ONLY node ids from the register index. If no node fits, name the
   equipment and say no node fits — do not force a wrong attach.

CLASS-SPECIFIC RULES for this sheet:
{class_rules}

ENGINEER-CONFIRMED MAPPINGS (authoritative vocabulary → node; use when a
label matches):
{maps}

PRIOR EXTRACTION:
{extraction}

REGISTER INDEX:
{index}
"""


def _register_index() -> str:
    reg = json.loads((config.STATE_DIR / f"register_{config.VESSEL_NAMESPACE}.json").read_text())
    lines = []
    for e in reg["entries"]:
        if e.get("retired"):
            continue
        bits = [e.get("name") or ""]
        if e.get("make"):
            bits.append(e["make"])
        if e.get("model"):
            bits.append(e["model"])
        if e.get("subsystem_label"):
            bits.append(f"({e['subsystem_label']})")
        lines.append(f"{e['equipment_id']} — {' '.join(b for b in bits if b)}")
    return "\n".join(lines)


def _maps_digest(drawing_class: str) -> str:
    """Control map (hydraulic) / load map (electrical) as vocabulary lines."""
    out = []
    if drawing_class in ("hydraulic", "plc"):
        cm = json.loads((config.STATE_DIR / f"control_map_{config.VESSEL_NAMESPACE}.json").read_text())
        for m in cm["mappings"]:
            aliases = f" (aliases: {', '.join(m['aliases'])})" if m.get("aliases") else ""
            out.append(f"{m['function']}{aliases} -> {m['target_node_id']}")
    if drawing_class == "electrical":
        lm_path = config.STATE_DIR / f"load_map_{config.VESSEL_NAMESPACE}.json"
        if lm_path.exists():
            lm = json.loads(lm_path.read_text())
            if lm.get("status") == "active":
                for k, v in lm.get("mappings", {}).items():
                    out.append(f"{k} -> {v}")
    return "\n".join(out) if out else "(none for this class)"


def compose(image_png: bytes, extraction: Dict[str, Any],
            drawing_class: str,
            vision_kind: str = "hydraulic_schematic",
            max_tokens: int = 16384) -> Optional[Dict[str, Any]]:
    """Run the composition pass on one sheet. Returns the composition dict."""
    from providers.vision import get_vision_provider
    rules = CLASS_RULES.get(drawing_class)
    if rules is None:
        raise ValueError(f"No composition rules for class '{drawing_class}'. "
                         f"Known: {sorted(CLASS_RULES)}")
    ext = {k: v for k, v in extraction.items()
           if k not in ("_node_routing", "model", "passes")}
    prompt = _COMPOSE_PROMPT.format(
        class_rules=rules,
        maps=_maps_digest(drawing_class),
        extraction=json.dumps(ext, indent=1)[:55000],
        index=_register_index())
    vp = get_vision_provider(vision_kind)
    return vp.extract(image_png, "image/png", prompt, _COMPOSE_TOOL,
                      max_tokens=max_tokens)
