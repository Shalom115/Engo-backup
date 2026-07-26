"""
CIRCUIT SEMANTICS over the measured netlist (2026-07-26).

THE POLARITY REVERSAL — root causes, found by diagnosing p20/p15 rather than
patching the examples:

  CAUSE 1  NO POLARITY MODEL. The netlist knew which wires connect, but no net
           carried "+" or "-". Composition therefore INFERRED polarity from
           words and position — and inferred it backwards (it reported the
           breaker feed as the negative). Nothing could apply the engineer's
           rule "in LV DC, breakers are almost always on the + side" because
           there was no polarity to apply it to.
  CAUSE 2  NO WALK-BACK-TO-SOURCE. "Follow Q14 all the way back" was not an
           operation the pipeline could perform: the digest was a FLAT list of
           nets, never a path from a load to its origin.
  CAUSE 3  COMMON RAILS INVISIBLE. One net feeding many devices (a shared
           positive rail, e.g. a terminal feeding four relay coils) looked
           like any other net, so a common feed was simply never mentioned.
  CAUSE 4  NO RELAY STRUCTURE. A relay is a coil (two power sides) plus
           contacts that are NO or NC. Nothing captured that, so "is the load
           on NO or NC?" and "what energises this coil?" were unanswerable.

This module fixes 1-3 deterministically over the geometry (4 is captured in
device_locate). Polarity and source come from the DRAWN topology, never from
wording.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

# device-kind vocabulary (general, no vessel tokens)
_PROTECTIVE = ("breaker", "fuse", "mcb", "circuit breaker")
_POS_WORDS = ("+", "positive", "pos bus", "+24", "+ 24", "supply", "vcc", "l1", "line")
_NEG_WORDS = ("-", "negative", "neg bus", "0v", "gnd", "ground", "rtn", "return", "n ")
_PROT_ID = re.compile(r"^(Q|QE|CB|F|FU)\s?\d{1,3}$", re.I)


def _txt(*parts: Any) -> str:
    return " ".join(str(p or "") for p in parts).lower()


def classify_sources(netlist: Dict[str, Any]) -> Dict[str, str]:
    """
    Mark nets as 'positive' / 'negative' where the DRAWING says so:

      * a net carrying a protective device (breaker/fuse) or a protective id
        (Q15, QE6, F3, CB7) is a SUPPLY net -> POSITIVE.
        Engineer rule: in low-voltage DC, breakers/fuses sit on the + side
        almost always. Recorded as an assumption, overridable by an explicit
        negative marking on the same net.
      * a net carrying an explicit negative/ground marking is NEGATIVE.

    An explicit negative marking always wins over the breaker heuristic.
    """
    pol: Dict[str, str] = {}
    for n in netlist.get("nets", []):
        blob = _txt(" ".join(n.get("labels", [])), " ".join(n.get("devices", [])))
        explicit_neg = any(w in blob for w in _NEG_WORDS[1:])  # skip bare "-"
        has_prot = any(w in blob for w in _PROTECTIVE) or \
            any(_PROT_ID.match(l.strip()) for l in n.get("labels", []))
        explicit_pos = any(w in blob for w in _POS_WORDS[1:])
        if explicit_neg:
            pol[n["net_id"]] = "negative"
        elif has_prot or explicit_pos:
            pol[n["net_id"]] = "positive"
    return pol


def common_rails(netlist: Dict[str, Any], min_devices: int = 3
                 ) -> List[Dict[str, Any]]:
    """
    A net touching MANY devices is a COMMON RAIL — a shared feed or a shared
    return. These are exactly what a per-device reading misses (the engineer's
    'their positive is COMMON from T/S E terminal 21 which it completely
    ignored').
    """
    out = []
    for n in netlist.get("nets", []):
        devs = n.get("devices") or []
        if len(set(devs)) >= min_devices and n.get("kind") == "conductor":
            out.append({"net_id": n["net_id"],
                        "labels": n.get("labels", [])[:8],
                        "devices": sorted(set(devs))[:12],
                        "n_devices": len(set(devs))})
    out.sort(key=lambda r: -r["n_devices"])
    return out


def _device_nets(netlist: Dict[str, Any]) -> Dict[str, Set[str]]:
    """device label -> the nets it touches (from placed_devices)."""
    d: Dict[str, Set[str]] = {}
    for pd in netlist.get("placed_devices", []):
        key = (pd.get("label") or pd.get("kind") or "").strip()
        if not key:
            continue
        d.setdefault(key, set()).update(pd.get("nets", []))
    return d


def trace_to_source(netlist: Dict[str, Any], start_net: str,
                    max_hops: int = 6) -> Dict[str, Any]:
    """
    WALK BACK TO THE ORIGIN — the operation that was missing.

    From a net, hop through the devices that touch it to the nets they also
    touch, until reaching a net classified as a supply (positive) or a
    negative/return. Returns the chain, so a composition can say
    "fed from Q14 via T/S B 17" instead of "not traced".
    """
    pol = classify_sources(netlist)
    dev_nets = _device_nets(netlist)
    net_devs: Dict[str, List[str]] = {}
    for dev, nets in dev_nets.items():
        for nid in nets:
            net_devs.setdefault(nid, []).append(dev)

    seen = {start_net}
    frontier = [(start_net, [start_net])]
    for _ in range(max_hops):
        nxt = []
        for nid, path in frontier:
            if pol.get(nid):
                return {"source_net": nid, "polarity": pol[nid],
                        "path": path, "via_devices":
                        [d for p in path for d in net_devs.get(p, [])][:12]}
            for dev in net_devs.get(nid, []):
                for other in dev_nets.get(dev, ()):
                    if other not in seen:
                        seen.add(other)
                        nxt.append((other, path + [other]))
        frontier = nxt
        if not frontier:
            break
    return {"source_net": None, "polarity": None, "path": [], "via_devices": []}


def annotate(netlist: Dict[str, Any]) -> Dict[str, Any]:
    """Attach polarity + common-rail findings to the netlist in place."""
    pol = classify_sources(netlist)
    for n in netlist.get("nets", []):
        if pol.get(n["net_id"]):
            n["polarity"] = pol[n["net_id"]]
    netlist["polarity"] = pol
    netlist["common_rails"] = common_rails(netlist)
    return netlist


def digest(netlist: Dict[str, Any], max_rails: int = 12) -> str:
    """Prompt block: measured polarity + common rails + the walk-back rule."""
    annotate(netlist)
    pol = netlist.get("polarity", {})
    rails = netlist.get("common_rails", [])
    npos = sum(1 for v in pol.values() if v == "positive")
    nneg = sum(1 for v in pol.values() if v == "negative")
    out = [f"MEASURED POLARITY — {npos} supply(+) nets and {nneg} return(-) nets "
           f"identified from the drawing itself.",
           "POLARITY RULES (engineer): in low-voltage DC a breaker/fuse sits on "
           "the POSITIVE side almost always — a net carrying a breaker or fuse "
           "is a SUPPLY (+) net, never the return. NEVER call a breaker feed "
           "the negative. A device's return goes to the negative bus/rail.",
           "WALK BACK BEFORE YOU NAME A SIDE: for every feed, follow the "
           "conductor back through its devices to the breaker/bus it comes "
           "from, and say so ('fed from <breaker> via <terminal>'). Do not "
           "write 'not traced' for a side that the netlist below can reach."]
    if rails:
        out.append("COMMON RAILS — one net feeding/returning MANY devices. A "
                   "device on a common rail shares that side with every other "
                   "device on it; say the shared source explicitly instead of "
                   "treating each device as isolated:")
        for r in rails[:max_rails]:
            labs = ", ".join(r["labels"][:5]) or "(unlabelled)"
            out.append(f"  {r['net_id']} [{labs}] feeds/returns {r['n_devices']} "
                       f"devices: {', '.join(r['devices'][:8])}")
    pos_nets = [nid for nid, v in pol.items() if v == "positive"][:12]
    neg_nets = [nid for nid, v in pol.items() if v == "negative"][:12]
    if pos_nets:
        out.append(f"  supply(+) nets: {', '.join(pos_nets)}")
    if neg_nets:
        out.append(f"  return(-) nets: {', '.join(neg_nets)}")
    return "\n".join(out)
