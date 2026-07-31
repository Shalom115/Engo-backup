"""
TROUBLESHOOT INDEX — the machine-readable elimination list per node.

THE POINT (engineer, 2026-07-31): a loop often does not close on one sheet, and
sometimes the return is never drawn at all. Waiting for a closed loop throws
away the half that IS shown — and that half is the half you can actually TEST.
What matters for fault-finding is the ordered list of things that can be
checked, replaced, or eliminated:

    breaker            has it tripped?
    earth-leak breaker has it tripped? does the test button work?
    fuse               is there continuity, or has it blown?
    relay NO contact   is the coil energised? (load is OFF until it is)
    relay NC contact   is the coil energised? is there continuity? (load is ON
                       until it is)
    selector           is it on the right setting? what changes per position?
    isolator           open or closed?
    terminal           is the voltage present at this way?
    shunt              what does it read?
    status tag         what does it report, and to what?

So the ingestion phase EXTRACTS these and puts them on the node in SOURCE->LOAD
order, whether or not the loop closes. Engo then answers a fault without
re-reading the drawing: it already knows what to ask and in what sequence.

This is written for ENGO to read, not the engineer. Terse, typed, ordered.
Nothing here is generated — every entry comes from an element the extraction
actually found, and carries the sheet and provenance it came from, so a check
Engo proposes can always be traced back to the drawing that justifies it.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# id grammar -> device class. Generic drafting convention, no vessel token.
ID_CLASS = [
    (re.compile(r"^QE\s?\d", re.I), "emergency_breaker"),
    (re.compile(r"^(Q|CB)\s?\d", re.I), "breaker"),
    (re.compile(r"^(F|FU)\s?\d", re.I), "fuse"),
    (re.compile(r"^Re\s?\d", re.I), "relay"),
    (re.compile(r"^(SO|K)\s?\d", re.I), "contactor"),
    (re.compile(r"^(SW|S)\s?\d", re.I), "switch"),
    (re.compile(r"^CT\s?\d", re.I), "current_transformer"),
    (re.compile(r"^T/S\s?[A-Z]", re.I), "terminal_strip"),
    (re.compile(r"^XA\s?\d", re.I), "status_tag"),
]

# What an engineer can DO to each class, and what the answer eliminates. The
# `check` is the question Engo asks; `if_fails` is what that result rules in.
CHECKS: Dict[str, Dict[str, str]] = {
    "breaker": {
        "check": "tripped?",
        "method": "look at the lever / continuity across the poles",
        "if_fails": "supply to everything downstream is dead; reset and see if "
                    "it holds — an immediate re-trip means a downstream fault",
        "replaceable": "yes"},
    "emergency_breaker": {
        "check": "tripped?",
        "method": "look at the lever; note it is fed from the EMERGENCY side",
        "if_fails": "emergency supply to downstream is dead; the normal-side "
                    "breaker for the same load may still be live",
        "replaceable": "yes"},
    "earth_leak_breaker": {
        "check": "tripped? does the test button trip it?",
        "method": "test button, then insulation-test the downstream circuit",
        "if_fails": "an earth fault downstream; isolate loads one at a time to "
                    "find which one drags it out",
        "replaceable": "yes"},
    "fuse": {
        "check": "continuity — has it blown?",
        "method": "meter across it with the circuit isolated",
        "if_fails": "open circuit downstream; a blown fuse is a SYMPTOM — find "
                    "what drew the current before refitting",
        "replaceable": "yes"},
    "relay": {
        "check": "is the coil energised, and is the load on the NO or the NC "
                 "contact?",
        "method": "measure the coil supply and its return separately, then "
                  "continuity across the contact in both coil states",
        "if_fails": "on NO the load stays OFF until the coil energises; on NC "
                    "the load stays ON until it does — an inverted reading "
                    "inverts the whole function",
        "replaceable": "yes"},
    "contactor": {
        "check": "is the coil energised? do the main contacts close?",
        "method": "coil voltage, then continuity across the main poles",
        "if_fails": "the load it switches has no supply even though its "
                    "breaker is healthy",
        "replaceable": "yes"},
    "switch": {
        "check": "position, and continuity in each position",
        "method": "operate it and meter through",
        "if_fails": "the circuit is selected away from the path you are "
                    "testing",
        "replaceable": "yes"},
    "isolator": {
        "check": "open or closed?",
        "method": "handle position + continuity across it",
        "if_fails": "the bus it ties is split; downstream is fed from the "
                    "other side or not at all",
        "replaceable": "no — operate it"},
    "terminal_strip": {
        "check": "voltage present at the numbered way?",
        "method": "meter to the return rail at that terminal",
        "if_fails": "narrows the fault to before or after this terminal — the "
                    "cheapest single measurement to bisect a run",
        "replaceable": "no — a test point"},
    "current_transformer": {
        "check": "what does it read?",
        "method": "read at the meter it feeds",
        "if_fails": "measurement only; it does not break the supply",
        "replaceable": "no"},
    "shunt": {
        "check": "what current does it read?",
        "method": "read at the monitor it feeds",
        "if_fails": "measurement only",
        "replaceable": "no"},
    # ---- HYDRAULIC. A hydraulic sheet has its own testable items, and an
    # electrical-only index returned ZERO checks for a hydraulic block whose
    # composition named pilot modules, spools, work-port reliefs and LS
    # limiters with their bar settings. The engineer's ask was troubleshooting,
    # not troubleshooting-if-electrical.
    "pilot_module": {
        "check": "is the pilot energised, and does the spool actually shift?",
        "method": "check the coil supply and its return, then feel/observe the "
                  "spool or watch the function respond",
        "if_fails": "the function will not move at all; an energised pilot with "
                    "no movement points at the spool or a blocked pilot supply, "
                    "not at the actuator",
        "replaceable": "yes"},
    "spool": {
        "check": "does it return to neutral, and shift fully both ways?",
        "method": "operate both directions and observe; open-centre neutral "
                  "should bypass P to T freely",
        "if_fails": "a spool stuck off-centre creeps the function; one that "
                    "will not shift fully gives reduced or no flow one way",
        "replaceable": "yes"},
    "relief_valve": {
        "check": "is it set to the printed value, and is it passing?",
        "method": "gauge the port and compare with the setting printed on the "
                  "sheet; a relief passing at rest is hot and the function is "
                  "weak",
        "if_fails": "the function is weak or will not hold load; a relief set "
                    "too low is the commonest cause of 'it lifts but not "
                    "fully'",
        "replaceable": "yes"},
    "pressure_limiter": {
        "check": "is the LS limiter at its printed setting?",
        "method": "gauge the LS line for that branch",
        "if_fails": "caps the pressure that branch can command, so the "
                    "function is weak while the rest of the block is normal",
        "replaceable": "yes"},
    "cartridge": {
        "check": "is it passing / blocked?",
        "method": "isolate and compare behaviour with the mirrored branch when "
                  "one exists",
        "if_fails": "a blocked cartridge stops that branch only; a passing one "
                    "bleeds it to tank and the function creeps",
        "replaceable": "yes"},
    "check_valve": {
        "check": "does it hold in the blocking direction?",
        "method": "load the line and watch for drift",
        "if_fails": "the function will not hold position under load",
        "replaceable": "yes"},
    "accumulator": {
        "check": "is the pre-charge correct?",
        "method": "gauge with the system depressurised",
        "if_fails": "lost pre-charge gives a soft or pulsing function",
        "replaceable": "yes"},
    # ---- FLUID / P&ID
    "isolation_valve": {
        "check": "open or closed, and does it match the lineup?",
        "method": "handle position; compare with the normal lineup for the "
                  "scenario being run",
        "if_fails": "a valve in the wrong state silently selects a different "
                    "lineup — check this BEFORE suspecting the pump",
        "replaceable": "no — operate it"},
    "strainer": {
        "check": "is it blocked?",
        "method": "differential across it, or open and inspect the basket",
        "if_fails": "starves the pump: loud running, poor or no discharge, "
                    "and it will damage the pump if left",
        "replaceable": "no — clean it"},
    "pump": {
        "check": "is it running, and is it making pressure?",
        "method": "gauge suction and discharge; a pump that runs without "
                  "discharge is losing prime or starved",
        "if_fails": "no flow in every scenario that uses it — check its supply "
                    "breaker and its suction lineup before condemning it",
        "replaceable": "yes"},
    "non_return_valve": {
        "check": "is it holding, or passing backwards?",
        "method": "pressurise downstream and watch for reverse flow",
        "if_fails": "back-flow between branches; two pumps on a common header "
                    "will fight each other",
        "replaceable": "yes"},
    "level_switch": {
        "check": "does it change state at the right level?",
        "method": "lift/lower the float or simulate, and watch the alarm or "
                  "the pump start",
        "if_fails": "the automatic start never fires, or runs continuously",
        "replaceable": "yes"},
    "status_tag": {
        "check": "what does it report, and to which system?",
        "method": "compare the monitoring system's indication against the "
                  "physical state",
        "if_fails": "a disagreement means the SIGNAL is wrong, not necessarily "
                    "the equipment — do not chase the equipment first",
        "replaceable": "no — indication"},
}


def classify_element(label: str, kind: str = "") -> Optional[str]:
    """Device class from its printed id, falling back to a typed symbol kind.
    Returns None when neither says anything — never a guess."""
    lab = (label or "").strip()
    for rx, cls in ID_CLASS:
        if rx.match(lab):
            # An earth-leak breaker is a breaker whose LABEL says so; the id
            # grammar alone cannot distinguish it.
            if cls == "breaker" and re.search(r"earth|leak|elcb|rcd", lab, re.I):
                return "earth_leak_breaker"
            return cls
    k = (kind or "").lower()
    for cls in CHECKS:
        if cls.replace("_", " ") in k or cls in k:
            return cls
    if "earth" in k and "leak" in k:
        return "earth_leak_breaker"
    if "shunt" in k:
        return "shunt"
    if "isolat" in k:
        return "isolator"
    return None


# Elimination order: you check the supply side before the thing it feeds.
# Position in this list is the ORDER Engo should propose checks in, not an
# importance ranking.
ORDER = ["isolator", "breaker", "emergency_breaker", "earth_leak_breaker",
         "fuse", "switch", "contactor", "relay", "terminal_strip",
         "current_transformer", "shunt", "status_tag",
         # hydraulic: pilot commands the spool, spool directs the oil, the
         # reliefs limit it, the cartridges/checks hold it
         "pilot_module", "spool", "pressure_limiter", "relief_valve",
         "cartridge", "check_valve", "accumulator",
         # fluid: the lineup first, then what moves the fluid, then what it
         # passes through, then what reports on it
         "isolation_valve", "strainer", "pump", "non_return_valve",
         "level_switch"]

# PHRASES a composition uses for a testable item that has NO id of its own.
# A hydraulic sheet names "PVEO pilot module", "work-port relief valve on the A
# branch", "LS_A pressure limiter (240 bar)" — real, checkable, and invisible
# to a scan that only looks for Q14-shaped identifiers.
PHRASE_CLASS = [
    (re.compile(r"\bPVE[OU]\b|\bpilot module\b|\bpilot valve\b", re.I), "pilot_module"),
    (re.compile(r"\bpressure limiter\b|\bLS[_ ]?[AB] limiter\b", re.I), "pressure_limiter"),
    (re.compile(r"\b(work[- ]port )?relief valve\b|\binlet relief\b", re.I), "relief_valve"),
    (re.compile(r"\bdirectional spool\b|\bmain spool\b|\bspool\b", re.I), "spool"),
    (re.compile(r"\bcartridge\b", re.I), "cartridge"),
    (re.compile(r"\bcheck valve\b|\bshuttle\b", re.I), "check_valve"),
    (re.compile(r"\baccumulator\b", re.I), "accumulator"),
    (re.compile(r"\bstrainer\b|\bstrum ?box\b", re.I), "strainer"),
    (re.compile(r"\bnon[- ]?return valve\b|\bNRV\b", re.I), "non_return_valve"),
    (re.compile(r"\b(isolation|sea ?cock|3-way|three-way) valve\b|\bNC valve\b", re.I), "isolation_valve"),
    (re.compile(r"\b(float|level) switch\b", re.I), "level_switch"),
    (re.compile(r"\bpump\b", re.I), "pump"),
]


def _rating(after: str) -> Optional[str]:
    """A rating belongs to a device only when it is printed IMMEDIATELY after
    its id ("Q14 10A"). Scanning a wide context window instead put F3's 60A
    onto the SW8 next to it in the same sentence — a switch given a fuse's
    rating, which would send someone looking for a 60A switch that does not
    exist. Adjacent only, or nothing."""
    m = re.match(r"[\s:,-]{0,3}(\d{1,4}\s?A(?:mp)?)\b", after or "", re.I)
    return m.group(1).replace(" ", "") if m else None


def _device_id(label: str) -> Optional[str]:
    m = re.match(r"^([A-Za-z/]{1,3}\s?\d{1,3}[a-z]?)", (label or "").strip())
    return m.group(1).strip() if m else None


def from_composition(comp: Dict[str, Any], sheet: str,
                     provenance: Optional[Dict[str, Any]] = None
                     ) -> Dict[str, List[Dict[str, Any]]]:
    """Build {node_id: [check, ...]} from one sheet's composition.

    Reads the traced scenario paths and the key_components list — i.e. the
    things the sheet was actually found to contain — and keeps every element
    that a person can test. Elements that cannot be tested are dropped, not
    invented into something that can.
    """
    out: Dict[str, List[Dict[str, Any]]] = {}
    for g in comp.get("equipment_groups") or []:
        node = (g.get("target_node_id") or "").strip()
        if not node or node.upper().strip("<>") in {"UNKNOWN", "CLARIFY", "TBC"}:
            continue
        seen = set()
        entries: List[Dict[str, Any]] = []
        for f in g.get("functions") or []:
            texts: List[str] = []
            kc = f.get("key_components")
            if isinstance(kc, list):
                texts += [str(x) for x in kc]
            elif isinstance(kc, str):
                texts.append(kc)
            for sc in f.get("flow_scenarios") or []:
                texts.append(str(sc.get("path")) if isinstance(sc, dict) else str(sc))
            blob = " ; ".join(texts)
            # Every device-id-shaped token in this function's own text. The
            # path IS the evidence: an id only appears here because the
            # extraction put it on this function.
            # ORDER MATTERS IN THIS ALTERNATION. "T/S S 13" is terminal strip S,
            # way 13 — but a bare `S\d` alternative matched the "S 13" inside
            # it and filed a terminal as a switch. The terminal-strip form is
            # tried FIRST so it consumes the whole token.
            # BARE `S<n>` IS A SWITCH AND MUST BE MATCHED. Removing it to fix
            # the "T/S S 13" misparse threw out every panel switch: GM-112
            # named "switch S8 (NO)" and "S8 is closed" in its own text and
            # yielded 3 checks from 18 functions, GM-116 6 from 15. The
            # terminal-strip alternative is tried FIRST and consumes the whole
            # "T/S S 13" token, so the two can coexist — which is what the
            # ordering was for in the first place.
            for m in re.finditer(
                    r"\b(T/S\s?[A-Z](?:\s?\d{1,3})?"
                    r"|(?:QE|CB|SO|XA|Re|SW|CT|Q|F|K|S)\s?\d{1,3}[a-z]?"
                    r"(?:\s*/\s*\d{1,3})?)\b", blob):
                lab = m.group(1).strip()
                cls = classify_element(lab)
                if not cls:
                    continue
                key = (cls, lab.upper().replace(" ", ""))
                if key in seen:
                    continue
                seen.add(key)
                ctx = blob[max(0, m.start() - 90):m.start() + 110]
                spec = CHECKS[cls]
                entries.append({
                    "device_class": cls,
                    "device_id": _device_id(lab) or lab,
                    "rating": _rating(blob[m.end():m.end() + 10]),
                    "check": spec["check"],
                    "method": spec["method"],
                    "if_fails": spec["if_fails"],
                    "replaceable": spec["replaceable"],
                    "function": f.get("label"),
                    "context": ctx.strip(),
                    "sheet": sheet,
                    "provenance": provenance or {"source_doc": sheet},
                })
        # PHRASE-NAMED ITEMS, for classes whose devices carry no id. Recorded
        # once per (class, function) — "the relief valve on this function",
        # not one entry per mention.
        for f in g.get("functions") or []:
            texts = []
            kc = f.get("key_components")
            if isinstance(kc, list):
                texts += [str(x) for x in kc]
            elif isinstance(kc, str):
                texts.append(kc)
            for sc in f.get("flow_scenarios") or []:
                texts.append(str(sc.get("path")) if isinstance(sc, dict) else str(sc))
            texts.append(str(f.get("what_it_does") or ""))
            blob = " ; ".join(texts)
            for rx, cls in PHRASE_CLASS:
                m = rx.search(blob)
                if not m:
                    continue
                key = (cls, (f.get("label") or "")[:40])
                if key in seen:
                    continue
                seen.add(key)
                spec = CHECKS[cls]
                entries.append({
                    "device_class": cls,
                    "device_id": m.group(0).strip(),
                    "rating": None,
                    "check": spec["check"], "method": spec["method"],
                    "if_fails": spec["if_fails"],
                    "replaceable": spec["replaceable"],
                    "function": f.get("label"),
                    "context": blob[max(0, m.start() - 70):m.start() + 120].strip(),
                    "sheet": sheet, "provenance": provenance or {"source_doc": sheet},
                })
        if entries:
            # ACCUMULATE, never overwrite. Two equipment groups on one sheet
            # can legitimately target the SAME node (five valve branches under
            # one water-transfer node); assigning out[node] replaced the first
            # group's checks with the second's and silently lost them.
            entries = out.get(node, []) + entries
            entries.sort(key=lambda x: (ORDER.index(x["device_class"])
                                        if x["device_class"] in ORDER else 99,
                                        x["device_id"]))
            out[node] = entries
    return out


def merge(a: Dict[str, List[Dict[str, Any]]],
          b: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    """Fold one sheet's index into the running one, de-duplicating on
    (class, id, sheet) — the SAME device on a DIFFERENT sheet is kept, because
    a breaker appearing on both the distribution sheet and the equipment sheet
    is two pieces of evidence about one device, not a duplicate."""
    for node, rows in b.items():
        have = {(r["device_class"], r["device_id"], r["sheet"])
                for r in a.get(node, [])}
        a.setdefault(node, [])
        for r in rows:
            if (r["device_class"], r["device_id"], r["sheet"]) not in have:
                a[node].append(r)
        a[node].sort(key=lambda x: (ORDER.index(x["device_class"])
                                    if x["device_class"] in ORDER else 99,
                                    x["device_id"]))
    return a
