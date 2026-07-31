"""
HUB GUARD — a hub node may never absorb equipment that has its own node.

THE FAILURE THIS EXISTS FOR (engineer, 2026-07-31, GM 110a/110b):
`625-bae-system` is a HUB — a card for the BAE system's own control apparatus.
The engineer's load map deliberately routes seven loads to it (HVIL,
CONDUCTIVITY PROCESSOR, CHART TABLE HMI, BEL-SYNC, PORT/STBD THROTTLE, DATA
LOGGER). Composition followed that correctly, then GENERALISED it: having seen
"BAE-adjacent things go to the BAE hub", it also sent there

  * a 230V AC / 24V DC CHARGER, which is not part of the BAE system at all;
  * the Parker MC43 display, which has its own node `625-parker-mc43-display`;
  * SCU3 ties, which have `628-scu3`;
  * the MAPS DC slicers (600V DC -> 24V DC), which have `626-maps`,
    `626-maps-p` and `626-maps-s`.

Every one of those nodes already existed. The hub swallowed them because
nothing in the pipeline said it could not.

TWO RULES, both deterministic:

  R1 SPECIFIC BEATS HUB. If a function's own text names a device that has its
     own node in the Register, it routes THERE, not to the hub. A hub is the
     destination of last resort, never a default.

  R2 A HUB ABSORBS ONLY WHAT THE MAP GIVES IT. If the engineer's load map does
     not route this load to the hub, and no specific node matches, the item is
     UNPLACED and waits for him. It is never swallowed by analogy.

The guard REPORTS; it does not silently re-route. A retarget is a proposal the
engineer confirms, because moving a fact to the wrong specific node is no
better than leaving it on the wrong hub.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

# A node is a HUB when it stands for a whole system rather than one machine.
# Detected from the Register, not hardcoded: a node with children, or one whose
# name says hub/system, is a container others sit under.
HUB_NAME = re.compile(r"\b(hub|system)\b", re.I)

# ON A DRAWING THESE ARE DESIGNATORS, NOT MODEL NAMES. "CT1" on an electrical
# sheet is current transformer 1; it is not the Harken CT1 captive tensioner,
# which is what a bare model-string match concluded. A token in this shape can
# never be used as identity evidence.
_DESIGNATOR = re.compile(r"^(q|qe|cb|f|fu|re|sw|so|ct|k|s|t)\d{1,3}[a-z]?$", re.I)


def hubs(register: Dict[str, Any]) -> Set[str]:
    out = set()
    for n in register.get("entries", []):
        if n.get("retired"):
            continue
        if n.get("children") or HUB_NAME.search(str(n.get("name") or "")):
            out.add(n["equipment_id"])
    return out


def _tokens(s: str) -> Set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if len(t) > 2}


def specific_index(register: Dict[str, Any], hub_ids: Set[str]
                   ) -> List[Tuple[str, Set[str], Set[str]]]:
    """(node_id, distinguishing tokens) for every NON-hub active node.

    Tokens come from the node's make, model, acronyms and name — the words a
    drawing would actually print. Generic words are dropped so 'system' or
    'panel' cannot match everything.
    """
    GENERIC = {"system", "systems", "panel", "unit", "control", "power",
               "supply", "board", "box", "the", "and", "dc", "ac", "24v",
               "230v", "600v", "port", "stbd", "starboard", "main", "aux"}
    out = []
    for n in register.get("entries", []):
        if n.get("retired") or n["equipment_id"] in hub_ids:
            continue
        # STRONG = identity (make / model / acronym). WEAK = name words.
        # A match must include at least one STRONG token. Scoring on name
        # words alone sent "BAE start key switch" to 633-battery-gen-start and
        # "BAE 24V control supply and isolator relay bank" to
        # 652-onyx-monitoring — two shared generic words are not evidence that
        # a sheet is talking about a different machine.
        # AN IDENTIFIER, NOT A WORD. Token overlap on names is not evidence:
        # it sent "BAE start key switch" to 610-service-reports-and-invoices
        # because both contain "service", and "BAE 24V control supply and
        # isolator relay bank" to 420-gpm-12-drive-motor because both contain
        # "drive". This is the same weakness that sank the earlier semantic
        # matcher, and no threshold fixes it.
        #
        # A STRONG token must be a real identifier — a model designation or an
        # acronym containing a digit (MC43, SCU3, GPM-12, PVG32). Those appear
        # on a drawing only when that machine is genuinely being named. The
        # MAKE is excluded: "BAE" is the hub's own maker and matches everything
        # BAE-adjacent, which is the exact failure being guarded against.
        strong = {t for t in _tokens(n.get("model"))
                  if any(c.isdigit() for c in t) and not _DESIGNATOR.match(t)}
        for a in n.get("acronyms") or []:
            a = str(a).lower()
            if len(a) >= 3 and any(c.isdigit() for c in a) \
                    and not _DESIGNATOR.match(a):
                strong |= {a}
        weak = _tokens(n.get("name")) - GENERIC
        if strong:
            out.append((n["equipment_id"], strong, weak))
    return out


def check_group(node_id: str, functions: List[Dict[str, Any]],
                register: Dict[str, Any],
                load_map_targets: Optional[Set[str]] = None
                ) -> List[Dict[str, Any]]:
    """Findings for one composed equipment group routed to `node_id`.

    Each finding names the function, the hub it landed on, and the specific
    node whose own vocabulary appears in that function's text.
    """
    hub_ids = hubs(register)
    if node_id not in hub_ids:
        return []
    spec = specific_index(register, hub_ids)
    lm = {t.lower() for t in (load_map_targets or set())}
    findings = []
    for f in functions:
        blob = " ".join(str(f.get(k) or "") for k in
                        ("label", "what_it_does", "dry_data", "key_components"))
        for sc in f.get("flow_scenarios") or []:
            blob += " " + (str(sc.get("path")) if isinstance(sc, dict) else str(sc))
        bt = _tokens(blob)
        # R1 — does a specific node's own vocabulary appear here?
        best, score = None, 0
        for nid, strong, weak in spec:
            sh = len(strong & bt)
            if not sh:
                continue                     # no identity evidence -> no claim
            hit = sh * 2 + len(weak & bt)
            if hit > score:
                best, score = nid, hit
        # R2 — was this load given to the hub by the engineer's map?
        # THE ENGINEER'S MAP IS A PHRASE MAP, NOT A TOKEN SET. Testing
        # `any(token in lm)` compared single words against multi-word keys like
        # "CHART TABLE HMI", so it never matched and the guard flagged three
        # loads he had DELIBERATELY routed to the hub. Match the phrase.
        low = blob.lower()
        mapped = any(k and k in low for k in lm)
        if best and score >= 3 and not mapped:
            findings.append({
                "rule": "R1_specific_beats_hub",
                "function": f.get("label"),
                "routed_to": node_id,
                "should_be": best,
                "matched_terms": sorted(
                    next(st for i, st, _w in spec if i == best) & bt)[:6],
                "action": "RETARGET (engineer confirms)",
            })
        elif not mapped and not best:
            findings.append({
                "rule": "R2_hub_absorbed_unmapped_item",
                "function": f.get("label"),
                "routed_to": node_id,
                "should_be": None,
                "action": "UNPLACED — the load map does not route this here",
            })
    return findings


def check_composition(comp: Dict[str, Any], register: Dict[str, Any],
                      load_map: Optional[Dict[str, Any]] = None
                      ) -> List[Dict[str, Any]]:
    """Every hub-absorption finding in one sheet's composition."""
    lm_targets: Set[str] = set()
    if load_map:
        maps = load_map.get("mappings")
        if isinstance(maps, dict):
            lm_targets = {k for k in maps}
        elif isinstance(maps, list):
            lm_targets = {str(m.get("load") or "") for m in maps}
    out = []
    for g in comp.get("equipment_groups") or []:
        nid = (g.get("target_node_id") or "").strip()
        if nid:
            out += check_group(nid, g.get("functions") or [], register,
                               lm_targets)
    return out
