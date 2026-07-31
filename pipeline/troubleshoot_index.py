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
         "current_transformer", "shunt", "status_tag"]


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
            for m in re.finditer(
                    r"\b(T/S\s?[A-Z](?:\s?\d{1,3})?"
                    r"|(?:QE|CB|SO|XA|Re|SW|CT|Q|F|K)\s?\d{1,3}[a-z]?"
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
