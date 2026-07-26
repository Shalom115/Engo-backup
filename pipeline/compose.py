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

# PROTOCOL VERSION — bump on EVERY rule/schema/red-pen change. Compositions are
# stamped with this; pipeline/compose_write.py REFUSES compositions stamped
# with an older version (the stale-composition failure of 2026-07-22: a write
# set built from pre-red-pen compositions re-presented every answered
# uncertainty to the engineer). Airtight by construction, not by memory.
PROTOCOL_VERSION = 7

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
        "— call it the pilot module, not a valve block. "
        "PRESSURE-RELIEF SYMBOL (engineer rule): a NUMBER IN A SQUARE with "
        "an ARROW under the number and a SPRING drawn next to it is a "
        "PRESSURE RELIEF VALVE set to that number, in bar — state it as "
        "such, never as an unknown setting or orifice. "
        "SPOOL CONTROL PRESSURE: the standalone reduced-pressure valve in "
        "the block inlet section supplies the SPOOL CONTROL (pilot) "
        "pressure for the slices — that is its role."),
    "electrical": (
        "Each load/row/branch serves the equipment the LOAD NAME names. The "
        "scenario is the SUPPLY or CONTROL LOOP in words: 'fed from <panel> "
        "via breaker <id> <rating>' or 'commanded from <switch/panel> via "
        "terminal <n> and relay <id>; status back to monitoring via <tap>'. "
        "Bus structure, supply topology, terminal strips and relay banks are "
        "INFRASTRUCTURE (the panel/distribution node). "
        "FUSED TERMINALS (engineer rule): outer rectangle = the terminal; "
        "INSIDE it a smaller rectangle crossed by a line = a BUILT-IN "
        "REPLACEABLE FUSE. Always name it in the loop ('via fused terminal "
        "8') and point to the EXACT terminal number on each path; these are "
        "known troubleshooting culprits. "
        "BUS OWNERSHIP: a bus bar belongs to the distribution unit/system "
        "that owns it — a bus is never its own system unless the sheet "
        "titles it as one; check the glossary and established facts for "
        "which unit the bus IS before flagging it unplaced. "
        "SIGNAL DIRECTION: monitoring-system taps (XA-style) can be STATUS "
        "taps out of the circuit OR ACTIVATION commands into it — derive "
        "the direction from the drawn wiring (what the line reaches), never "
        "assume all taps are status. "
        "MEASURED NETLIST OUTRANKS APPEARANCE: when a MEASURED NETLIST block is "
        "supplied, it is derived from the drawing's real vector geometry and "
        "is the AUTHORITY on connectivity. Two labels on the same net ARE "
        "wired together; labels on different nets are NOT, however close they "
        "look. Never contradict the netlist from raster appearance, and never "
        "attach a number to a device just because it is printed nearby — check "
        "the net. "
        "READ ELECTRICITY SIDE-TO-SIDE (engineer rule): a relay/contactor "
        "coil is energised only when BOTH its power sides are made — the "
        "positive/L feed AND the negative/N return. Compose each coil's loop "
        "with BOTH: where the + comes from (e.g. a fused terminal on a "
        "terminal strip) and how the - returns (e.g. terminal strip -> "
        "multi-core wire -> plug pin, closed by a switch). A relay whose + "
        "feed OR - return you cannot trace is INCOMPLETE — say which side is "
        "missing, do not present it as fully understood. The function the coil "
        "activates is labelled on top of the coil; the relay energises that "
        "function (valve/pump/lamp). "
        "INDICATOR LAMPS: a bank of lamps on a supply line each indicates one "
        "equipment engaged by closing its circuit — map each lamp to the "
        "equipment it monitors (e.g. one lamp per BEL/MAPS/charger), do not "
        "leave them as an undifferentiated bank. "
        "CONVERTER/CHARGER/INVERTER SYMBOL (engineer rule): a rectangle with a "
        "sideways cross. BOTH voltages are written INSIDE the rectangle, one on "
        "each side of the cross (each marked AC or DC) — that is the device's "
        "input and output. CONFIRM EACH SIDE BY ITS CONNECTIONS: every side has "
        "TWO lines, and they identify it — an AC side runs one line to L and one "
        "to N; a DC side runs one line to the positive bus and one to the "
        "negative bus. Trace those four lines to name the input and output "
        "correctly. The RATING is always printed in CLOSE PROXIMITY to the "
        "rectangle, either directly ABOVE or BELOW it — read it from there, and "
        "do not attach a number found elsewhere on the sheet to this device. If "
        "the rating digits are genuinely illegible, record it as good-to-have "
        "with low confidence; never present a doubtful rating as fact, and never "
        "let a stray number become a device rating. "
        "NEGATIVE-BUS SYMBOL (engineer rule): a short line terminating in a bar/tick (a ground-style stub) at the end of a conductor means that conductor RETURNS TO THE NEGATIVE BUS. It is a complete, known return path — record the coil/device negative as 'to negative bus' and do NOT flag it as an untraced side. A cross-sheet note ('+ from DWG n') likewise means the feed is established on that sheet — record it as a cross-reference, not an uncertainty. "
        "SPARE WAYS: an empty/unlabelled breaker way (e.g. 'QE5' with no load) "
        "is a SPARE for future installation — record it as spare, not as an "
        "uncertainty."),
    "pid": (
        "The sheet describes a fluid SYSTEM. The system node gets the flow "
        "scenarios ('suction from X via strainer to pump, discharge overboard "
        "via Y'; alternate/emergency lineups as separate scenarios) plus the "
        "roster of equipment within the system. Each pump/valve/tank also "
        "gets its own role-in-flow fact on ITS node, with BOM identity "
        "(make/model per item tag) when the sheet's table provides it. The "
        "infrastructure/system target must be a real SYSTEM node — never a "
        "documentation/folder node. "
        "READ THE SHEET'S OWN KEYS FIRST: title block, BOM/item table, "
        "legends and notes — the BOM is the identity authority (item tag -> "
        "make/model); legends define the sheet's own symbols and override "
        "generic convention. "
        "WALK EACH FLUID LOOP END TO END (the same discipline as wiring "
        "loop-walks): start at each intake/source and follow the drawn pipe "
        "to its discharge; one continuous line = one loop; where a line "
        "branches, each branch is walked to its own end. PARALLEL LOOPS STAY "
        "SEPARATE: multiple intakes or circuits that carry the same medium "
        "are still DIFFERENT loops serving different systems — merging two "
        "loops because the fluid is the same is the cardinal P&ID error. "
        "SUPPLY-TO vs JOIN: a line drawn INTO a component is a supply to "
        "that component (e.g. a cooling feed); it joins the component's "
        "outlet only if the drawing shows the lines actually meeting. "
        "ARROWS ARE THE FLOW AUTHORITY: every scenario's direction must "
        "follow the printed arrowheads — never your reading order; a path "
        "narrated against an arrow is a wrong read. No arrow = say the "
        "direction is unconfirmed. "
        "NO/NC VALVE STATES DEFINE THE LINEUP: a normally-closed (NC) valve "
        "means that path carries NO flow in the normal scenario; opening it "
        "is a SEPARATE scenario, stated as such. Never narrate flow through "
        "a closed valve. "
        "PUMP SIDES ARE FIXED: identify each pump's suction side and "
        "discharge side from the arrows and check valves; fittings and "
        "manifolds belong to the side they are drawn on and NEVER move "
        "across the pump. "
        "PARALLEL PUMP SETS: two identical pumps with isolation valves on "
        "both sides of each = a parallel, individually-isolatable set — "
        "either pump can serve either source when crossovers are open; say "
        "it that way, do not assume a single duty pump. "
        "THE DRAWN-PIPE LAW: a fixture or tank connects to a manifold ONLY "
        "via a pipe that is actually drawn. Inventing a connection that is "
        "not on the sheet is the worst possible failure of this pass. "
        "SCENARIOS COME ONLY FROM THE WALKED TOPOLOGY: every flow scenario "
        "must correspond to a path in the WALKED FLUID LOOPS block below (or "
        "a path you can point to on the drawing). If the walk did not reach "
        "a destination, do NOT narrate a flow to it. Never invent a pump-out, "
        "a suction source, or a discharge route that is not drawn (the "
        "'sail-locker auxiliary pump-out' and 'operating-modes' inventions). "
        "ENUMERATE VALVE-LINEUP SCENARIOS: a pump with multiple valved "
        "sources or destinations has ONE scenario PER lineup — e.g. a fire "
        "pump that can reach fire hydrants, a tender/laz sprinkler, AND (via "
        "a 3-way valve) bilge suction-to-overboard = THREE separate scenarios; "
        "a pump fed by a normally-open sea-chest valve and a normally-closed "
        "emergency-suction valve = a normal lineup AND an emergency lineup "
        "(reverse the valves). Walk every valve branch to its end and list "
        "each reachable lineup. "
        "NO INVENTED CONTROLS: do NOT add a 'remote start' or any electrical "
        "control to a pump unless it is DRAWN on THIS fluid sheet. A "
        "pull-start / manual-start pump has no remote start — never give it "
        "one. Electrical control of a pump lives on the electrical sheets; if "
        "this P&ID does not draw the control, note 'control on electrical "
        "sheet — cross-ref' and move on. Distinguish separate remote inputs "
        "(a fire-pump remote vs a bilge-pump remote are different devices in "
        "different places) — never merge them. "
        "OPERATING-MODES DOC: if the vessel has an operating-modes companion "
        "document for this system, its lineups are the authority for the "
        "scenario set — cross-reference it; on Gelliceaux most P&IDs have one. "
        "SANITY: a tank empties only through a pump or gravity line the "
        "sheet shows — a 'direct discharge with no pump' claim demands a "
        "drawn gravity path, otherwise re-read. "
        "NUMBERS ON LINES ARE PIPE SIZES: a diameter marking (2\", DN50) "
        "next to a line is the pipe size, never a valve type (a '3-way "
        "valve' is a drawn symbol, not a number). "
        "DO NOT GUESS MAKES: name a component's make only if the sheet's "
        "BOM/table gives it; otherwise record the function and leave make "
        "unstated."),
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
        "never downgrade it to a bare 'solenoid'. "
        "RACK/INDEX PAGE (engineer rule): a PLC set's rack-layout page is "
        "the set's INDEX — it shows the whole rack as a GA, and the "
        "following pages detail one module each. Read it as the rack "
        "inventory + page router. Module positions come from the PRINTED "
        "position labels, counted carefully — never inferred from module "
        "count; the first position is often a bus coupler/CAN gateway, not "
        "an I/O module. Power-supply modules within the rack (feeding a "
        "group of output modules) are part of the inventory — do not skip "
        "them. COMMONS: common/reference terminals exist per OUTPUT module "
        "(WAGO marks them 'M'); when a vendor has no on-module common, the "
        "reference is the vessel's 24V negative — say which applies."),
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
        "the part belongs to, as dry_data + key_components. A photo has NO "
        "flow scenarios — leave flow_scenarios EMPTY, never invent one. "
        "Investigation figures yield evidence facts on the implicated "
        "system node."),
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
                                "required": ["label", "what_it_does"],
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
                "description": "Only MUST-level items: an ambiguous "
                               "FUNCTION/IDENTITY/CONNECTION that changes the "
                               "meaning and needs the engineer. NOT exact "
                               "pressure-relief values, part numbers, or fuse "
                               "ratings — those are good_to_have (below), not "
                               "uncertainties. Never guess a value.",
                "items": {"type": "string"}},
            "good_to_have": {
                "type": "array",
                "description": "Present-but-unread detail that does NOT block "
                               "understanding: an exact relief bar value, a "
                               "part number, a fuse rating. Record the item "
                               "and that its value is available on the drawing "
                               "/ at inspection — the function is understood "
                               "without it. These are notes, not red-pen "
                               "musts.",
                "items": {"type": "string"}},
            "cross_references": {
                "type": "array",
                "description": "Things this sheet points to another sheet for: "
                               "an EV-x.y that lives on a hydraulic block, a "
                               "CT/CB/wire continuing on another drawing, a "
                               "'see DWG N', a control/remote whose wiring is "
                               "on an electrical sheet, an operating-modes doc. "
                               "Each = {what, referenced_sheet_hint} so it is "
                               "resolved when that sheet is ingested.",
                "items": {"type": "object", "properties": {
                    "what": {"type": "string"},
                    "referenced_sheet_hint": {"type": "string"}},
                    "required": ["what"]}},
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
   the corrected reading noted. DO NOT FLAG WHAT YOU RESOLVED: if an item
   was placed on a node (via the load/control map, a name match, or the
   drawn wiring), it is NOT an uncertainty — a resolved item and an
   uncertainty are mutually exclusive. A short downstream link you can
   follow (a switch/fuse feeding the panel drawn right next to it) must be
   TRACED, not flagged as 'no downstream label'.
11. FUNCTION OVER PART NUMBER: the presence and FUNCTION of a device is the
   critical fact. An unreadable part number on an identified device is NOT
   an uncertainty — record the function, note 'part number: capture at
   inspection if ever needed'. Data that changes routinely (dates of
   record-keeping, live values) is irrelevant.
12. UNCERTAINTY vs GOOD-TO-HAVE (severity discipline): an UNCERTAINTY is a
   MUST — an ambiguous function / identity / connection that changes meaning
   and needs the engineer. An exact pressure-relief bar value, a part number
   or a fuse rating that is simply not legible is NOT an uncertainty — it is
   good_to_have: record the ITEM (there is a relief here / there is a fuse
   here) so a troubleshooter knows to look, and note the value is on the
   drawing or read at inspection. The function being understood is what
   matters; do not flag a good-to-have as a red-pen must.
13. CROSS-REFERENCE, DO NOT IMPORT: when this sheet points to another (an
   EV-x.y detailed on a hydraulic block, a wire/CT/CB continuing elsewhere,
   a control whose wiring is on an electrical sheet, an operating-modes doc),
   record it under cross_references — do NOT pull the other sheet's content
   in and narrate it here as if drawn. Resolution happens when that sheet is
   ingested.

CLASS-SPECIFIC RULES for this sheet:
{class_rules}

VESSEL ACRONYM GLOSSARY (authoritative — never call one of these unknown):
{glossary}

ESTABLISHED FACTS (already on the vessel's nodes from previously ingested
sheets). USE AS REFERENCE ONLY — to stay consistent with what is already
known and to NOT re-derive or downgrade an established identity/type. HARD
RULE: never generate a new scenario, control path, or connection FROM these
facts. A fact carries its own drawing class in [brackets]; a fact from a
DIFFERENT class than THIS sheet is background only — e.g. an [electrical]
control_loop fact must NEVER become a fluid flow line on a P&ID, and a
[hydraulic] fact must never become an electrical scenario. If a control or
remote input is not DRAWN on THIS sheet, it does not exist on this sheet —
do not import it from another node's fact:
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
            max_tokens: int = 16384,
            sheet_name: str = "") -> Optional[Dict[str, Any]]:
    """Run the composition pass on one sheet. Returns the composition dict."""
    from providers.vision import get_vision_provider
    rules = CLASS_RULES.get(drawing_class)
    if rules is None:
        raise ValueError(f"No composition rules for class '{drawing_class}'. "
                         f"Known: {sorted(CLASS_RULES)}")
    ext = {k: v for k, v in extraction.items()
           if k not in ("_node_routing", "model", "passes")}
    ext_json = json.dumps(ext, indent=1)[:55000]
    # Wiring sheets: walk the graph FIRST so composition discovers the control
    # loop (multi-switch activation) instead of fragmenting it (114a lesson).
    loop_block = ""
    if drawing_class == "electrical":
        from pipeline import loop_prepass
        digest = loop_prepass.loops_digest(extraction)
        if digest and "no wiring graph" not in digest:
            loop_block = "\n\n" + digest
        # MEASURED NETLIST (geometry) — the authority on what connects to what.
        nl = extraction.get("_netlist_digest")
        if nl:
            loop_block += "\n\n" + nl
    elif drawing_class == "pid":
        from pipeline import pid_extract, operating_modes
        digest = pid_extract.loops_digest(extraction)
        if digest and "no fluid topology" not in digest:
            loop_block = "\n\n" + digest
        if sheet_name:      # authoritative lineup set, when the vessel ships one
            loop_block += "\n\n" + operating_modes.modes_digest(sheet_name)
    try:
        from pipeline import open_questions
        oq = open_questions.open_digest()
    except Exception:
        oq = ""
    if oq:
        loop_block += "\n\n" + oq
    prompt = _COMPOSE_PROMPT.format(
        class_rules=rules + loop_block,
        glossary=vessel_context.glossary_block(),
        established=vessel_context.relationship_context(ext_json),
        maps=_maps_digest(drawing_class),
        extraction=ext_json,
        index=vessel_context.register_index())
    vp = get_vision_provider(vision_kind)
    result = vp.extract(image_png, "image/png", prompt, _COMPOSE_TOOL,
                        max_tokens=max_tokens)
    result = _repair_stringified(result)
    # MALFORMED-RESPONSE RETRY (2026-07-26): a tool call can come back with
    # placeholder keys (e.g. {"parameter_name": ...}) instead of the schema's
    # fields — seen once on a 31k-segment sheet whose geometry was perfect.
    # Silently writing that as "0 groups" would look like a real empty result.
    if isinstance(result, dict) and not result.get("serve_who") \
            and not result.get("equipment_groups"):
        retry = vp.extract(image_png, "image/png", prompt, _COMPOSE_TOOL,
                           max_tokens=max_tokens)
        retry = _repair_stringified(retry)
        if isinstance(retry, dict) and (retry.get("serve_who")
                                        or retry.get("equipment_groups")):
            result = retry
        elif isinstance(result, dict):
            result["_malformed_response"] = True
    if isinstance(result, dict):
        result["_protocol_version"] = PROTOCOL_VERSION
    return result


def _repair_stringified(result: Any) -> Any:
    """Some vision providers return an array/object tool-arg as a JSON STRING
    (seen 2026-07-22: equipment_groups came back as a 1836-char string, which
    len()'d to a fake '1836 groups'). Parse any list/dict field that arrived
    as a string so downstream never iterates characters."""
    if not isinstance(result, dict):
        return result
    for key in ("equipment_groups", "infrastructure", "uncertainties",
                "discarded_as_clutter", "good_to_have", "cross_references"):
        v = result.get(key)
        if isinstance(v, str) and v.strip().startswith(("[", "{")):
            try:
                result[key] = json.loads(v)
            except (ValueError, TypeError):
                pass  # leave as-is; the writer's guards still catch it
    return result
