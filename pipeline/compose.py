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
        "INFRASTRUCTURE (the manifold/block node). "
        "CONVENTIONS (engineer-confirmed): pressure settings on hydraulic "
        "sheets are in BAR — state them as bar, do not flag units as "
        "uncertain. The function's port mapping (which side is A, which is "
        "B, IN/OUT, UP/DOWN) is PRINTED in its own spec/legend block — use "
        "it to resolve where each work port's hose goes: the hose from a "
        "work port goes to the actuator of the function named above it. "
        "A red warning triangle with a number is a REVISION MARKER — the "
        "element was added/changed in that revision-table row; cross-read "
        "the revision table, never call it an unknown component. The pilot "
        "module on a slice (PVEO/PVEU) is the device that directs the spool "
        "— call it the pilot module, not a valve block."),
    "electrical": (
        "Each load/row/branch serves the equipment the LOAD NAME names. The "
        "scenario is the SUPPLY or CONTROL LOOP in words: 'fed from <panel> "
        "via breaker <id> <rating>' or 'commanded from <switch/panel> via "
        "terminal <n> and relay <id>; status back to monitoring via <tap>'. "
        "Bus structure, supply topology, terminal strips and relay banks are "
        "INFRASTRUCTURE (the panel/distribution node). "
        "FUSED TERMINALS (engineer rule): a rectangular terminal containing "
        "a small rectangle-with-a-line symbol is a terminal with a BUILT-IN "
        "REPLACEABLE FUSE — always name it in the loop ('via fused terminal "
        "8'); these are known troubleshooting culprits. "
        "SIGNAL DIRECTION: monitoring-system taps (XA-style) can be STATUS "
        "taps out of the circuit OR ACTIVATION commands into it — derive "
        "the direction from the drawn wiring (what the line reaches), never "
        "assume all taps are status."),
    "pid": (
        "The sheet describes a fluid SYSTEM. The system node gets the flow "
        "scenarios ('suction from X via strainer to pump, discharge overboard "
        "via Y'; alternate/emergency lineups as separate scenarios) plus the "
        "roster of equipment within the system. Each pump/valve/tank also "
        "gets its own role-in-flow fact on ITS node, with BOM identity "
        "(make/model per item tag) when the sheet's table provides it. The "
        "infrastructure/system target must be a real SYSTEM node — never a "
        "documentation/folder node."),
    "plc": (
        "Each I/O channel serves the equipment its signal name names. The "
        "scenario is the COMMAND CHAIN with the side stated: 'channel <n> of "
        "module position <p> in the <rack> energises <EV/output> = <equipment "
        "action>' — record which channel drives which direction (port A vs "
        "B / open vs close). State that a channel's voltage is measured "
        "RELATIVE TO THE MODULE'S COMMON channel — name the common so the "
        "engineer knows where to put the meter probes. Rack layout (coupler, "
        "module types, positions) is INFRASTRUCTURE (the PLC/rack node). "
        "CROSS-SHEET CONSISTENCY: an EV-x.y identifier referenced here is a "
        "hydraulic-manifold FUNCTION whose pilot device type (PVEO/PVEU "
        "module) is established on the hydraulic sheet — keep that type; "
        "never downgrade it to a bare 'solenoid'."),
    "building_ga": (
        "FIRST classify the GA sub-type from the sheet itself: a BUILDING/"
        "STRUCTURAL GA (positions, dimensions, structural details) or a "
        "SCHEMATIC GA (a system's connectivity drawn over the vessel outline "
        "— e.g. a navigation/network layout with cable labels). A schematic "
        "GA is composed under its system's rules (loops/backbones per "
        "equipment), not as positions. For building GAs: callouts serve the "
        "equipment they point at; facts are POSITIONS and PHYSICAL SPECS "
        "(frame/compartment, dimensions, SWL); a compartment-level fact "
        "lists what lives in the compartment; no flow scenarios. MIRRORING: "
        "when the drawing shows PORT/STBD mirrored pairs, state the mirror "
        "fact once ('stbd mirrors port') instead of treating the sides as "
        "unrelated. LINES/ROPES: identify the FUNCTION of a line first; "
        "length is secondary — flag an unknown length only when the line "
        "has a real function (e.g. steering rope), never for functionless "
        "graphics."),
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
                "type": "array",
                "description": "One entry PER DISTINCT SYSTEM on the sheet "
                               "(same commodity does not merge systems).",
                "items": {
                    "type": "object",
                    "properties": {
                        "system_name": {"type": "string"},
                        "target_node_id": {"type": "string"},
                        "facts": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["system_name", "facts"],
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
7. THE DRAWN-LINE LAW: a connection exists ONLY where a line is drawn.
   Proximity on the sheet is NEVER connectivity. Never compose a scenario,
   control relationship, or interlock across a link that is not drawn — an
   invented connection is the worst possible failure of this pass.
8. SYSTEM IDENTITY: sharing a commodity (same DC voltage, same fluid) does
   NOT make two systems one system. The sheet's own titled sections/boxes
   define distinct systems; each named system attaches to ITS OWN node — if
   no node exists for it, say so ('no fitting node'), never fold it into a
   sibling system's node.
9. LOOP-WALK (wiring sheets): compose control loops by WALKING the drawn
   lines end to end. When several switches/relays/remote commands can
   energise the same device, that is ONE loop scenario listing the
   alternative activation paths — not several disconnected fragments, and
   not several separate uncertainties. Flag only where the walk genuinely
   dead-ends off-sheet or in illegible print.
10. UNCERTAINTY DISCIPLINE: an uncertainty is about MEANING — a value, a
   role, a connection. Never flag orphan letters/fragments from the
   extraction: resolve them from context, or discard them as clutter with
   the corrected reading noted.
11. FUNCTION OVER PART NUMBER: the presence and FUNCTION of a device is the
   critical fact. An unreadable part number on an identified device is NOT
   an uncertainty — record the function, note 'part number: capture at
   inspection if ever needed'. Data that changes routinely (dates of
   record-keeping, live values) is irrelevant.

CLASS-SPECIFIC RULES for this sheet:
{class_rules}

VESSEL ACRONYM GLOSSARY (authoritative — never call one of these unknown):
{glossary}

ESTABLISHED FACTS (already on the vessel's nodes from previously ingested
sheets — identifiers on THIS sheet that these facts cover keep their
established identity/type; build on them, never re-derive or downgrade them):
{established}

ENGINEER-CONFIRMED MAPPINGS (authoritative vocabulary → node; use when a
label matches):
{maps}

PRIOR EXTRACTION:
{extraction}

REGISTER INDEX:
{index}
"""




# Vessel knowledge substrate — shared by ALL equipment-knowledge passes
# (the intrinsic-truth architecture, engineer-mandated 2026-07-20).
from pipeline import vessel_context


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
    ext_json = json.dumps(ext, indent=1)[:55000]
    prompt = _COMPOSE_PROMPT.format(
        class_rules=rules,
        glossary=vessel_context.glossary_block(),
        established=vessel_context.established_facts_for(ext_json),
        maps=_maps_digest(drawing_class),
        extraction=ext_json,
        index=vessel_context.register_index())
    vp = get_vision_provider(vision_kind)
    return vp.extract(image_png, "image/png", prompt, _COMPOSE_TOOL,
                      max_tokens=max_tokens)
