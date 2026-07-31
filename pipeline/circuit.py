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

# POLARITY VOCABULARY IS MATCHED ON WORD BOUNDARIES, NEVER AS SUBSTRINGS
# (2026-07-26). The first version tested membership with `in`, and one of the
# negative tokens was the AC-neutral "n " — which matches inside "MAIN FEED",
# "STERN LIGHT", "FAN", "GEN". Since an explicit negative marking overrides the
# breaker rule, any net labelled with such a word was flipped to negative: a
# silent polarity REVERSAL produced by a substring test. Same failure shape as
# the loose answer-matcher; the cure is the same — token boundaries only.
# A signed rail marking ("+24V", "+ 24 V", "-24V") is the clearest polarity
# statement a drawing makes, so it is matched explicitly rather than left to
# the word list.
_POS_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:\+\s?\d{1,3}\s?v?|\+|positive|pos\s+bus|supply|vcc"
    r"|l1|line)(?![A-Za-z0-9])", re.I)
_NEG_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:-\s?\d{1,3}\s?v(?:dc)?|negative|neg\s+bus|0v|gnd"
    r"|ground|rtn|return|n)(?![A-Za-z0-9])", re.I)
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
        blob = _txt(" ".join(n.get("labels", [])), " ".join(n.get("devices", [])),
                    " ".join(n.get("device_kinds", [])))
        explicit_neg = bool(_NEG_RE.search(blob))
        has_prot = any(w in blob for w in _PROTECTIVE) or \
            any(_PROT_ID.match(l.strip()) for l in n.get("labels", []))
        explicit_pos = bool(_POS_RE.search(blob))
        if explicit_neg:
            pol[n["net_id"]] = "negative"
        elif has_prot or explicit_pos:
            pol[n["net_id"]] = "positive"
    return pol


# A named SUPPLY RAIL as a drawing prints one. These are the points the
# engineer starts a trace FROM: "start at the source — either a bus (+24
# service / +24 emergency / negative bus / 230VAC L bus / 230VAC N bus) or just
# a label" (2026-07-31). Both forms appear: an on-sheet bus column (a labelled
# L1 / N pair with tick-offs down it) and an off-sheet source ARROW carrying
# the rail name rotated alongside it.
RAIL_PATTERNS = [
    ("dc_positive_service",   r"\+?\s*24\s*v?\s*(dc\s*)?service|service\s+bat"),
    ("dc_positive_emergency", r"\+?\s*24\s*v?\s*(dc\s*)?emergency|emergency\s+bat"),
    ("dc_positive",           r"\+\s*24\s*v|\+\s*12\s*v|\+\s*24\b"),
    ("dc_negative",           r"negative\s+bus|neg\s+bus|0\s*v\s+bus|\bgnd\s+bus"),
    ("hv_dc",                 r"\b600\s*v\s*dc|\bhv\s+dc\s+bus"),
    ("ac_line",               r"\b230\s*v.{0,12}\bbus|\bL1\b|\bL2\b|\bL3\b|ac\s+bus"),
    ("ac_neutral",            r"\bneutral\b|(?<![A-Za-z0-9])N(?![A-Za-z0-9])"),
    ("bus_named",             r"\bbus\s*[-–]?\s*[A-Z]\b"),
]
_RAIL_C = [(k, re.compile(p, re.I)) for k, p in RAIL_PATTERNS]


def rails(netlist: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The SOURCES on this sheet — where a trace starts and where it must end.

    A loop is only closed when it leaves one rail and arrives at the opposite
    one. Naming the rails first is what makes 'complete' checkable instead of
    a matter of how confidently the composition narrates.
    """
    out = []
    for n in netlist.get("nets", []):
        if n.get("kind") != "conductor":
            continue
        labels = n.get("labels", [])
        blob = " ".join(labels)
        if not blob.strip():
            continue
        for kind, rx in _RAIL_C:
            if rx.search(blob):
                out.append({"net_id": n["net_id"], "rail": kind,
                            "labels": labels[:6],
                            "n_devices": len(set(n.get("devices") or [])),
                            "side": ("return" if kind in
                                     ("dc_negative", "ac_neutral") else "supply")})
                break
    # A rail feeding many devices is more certainly a rail than one feeding
    # none; report the busiest first so composition anchors on real buses.
    out.sort(key=lambda r: -r["n_devices"])
    return out


def loop_completeness(netlist: Dict[str, Any], max_hops: int = 14
                      ) -> Dict[str, Any]:
    """Can every device be reached from a SUPPLY rail AND from a RETURN rail?

    The engineer's completeness test, made machine-checkable: a circuit that
    leaves the +24V bus through a breaker, a terminal and a relay contact to a
    motor is only HALF a loop until the motor's return is traced back to the
    negative bus. Composition used to narrate the half it could see; this
    reports the half it cannot, per device, so an incomplete trace is stated
    rather than presented as a finished loop.

    Adjacency is shared DEVICES between nets — the same join the netlist
    already records. No new measurement, no model.
    """
    nets = [n for n in netlist.get("nets", []) if n.get("kind") == "conductor"]
    by_id = {n["net_id"]: n for n in nets}
    dev_nets: Dict[str, List[str]] = {}
    for n in nets:
        for d in set(n.get("devices") or []):
            dev_nets.setdefault(d, []).append(n["net_id"])

    def reach(seeds: List[str]) -> set:
        seen, frontier, hops = set(seeds), list(seeds), 0
        while frontier and hops < max_hops:
            nxt = []
            for nid in frontier:
                for d in set((by_id.get(nid) or {}).get("devices") or []):
                    for other in dev_nets.get(d, []):
                        if other not in seen:
                            seen.add(other)
                            nxt.append(other)
            frontier, hops = nxt, hops + 1
        return seen

    rl = rails(netlist)
    sup_seeds = [r["net_id"] for r in rl if r["side"] == "supply"]
    ret_seeds = [r["net_id"] for r in rl if r["side"] == "return"]
    # Fall back to measured polarity when no rail is NAMED on the sheet — a
    # breaker-bearing net is a supply even if its bus is drawn off-sheet.
    pol = netlist.get("polarity") or classify_sources(netlist)
    if not sup_seeds:
        sup_seeds = [k for k, v in pol.items() if v == "positive"]
    if not ret_seeds:
        ret_seeds = [k for k, v in pol.items() if v == "negative"]

    from_sup, from_ret = reach(sup_seeds), reach(ret_seeds)
    complete, half, orphan = [], [], []
    for d, nids in dev_nets.items():
        s = any(x in from_sup for x in nids)
        r = any(x in from_ret for x in nids)
        (complete if (s and r) else half if (s or r) else orphan).append(
            {"device": d, "reaches_supply": s, "reaches_return": r})
    return {"rails": rl,
            "supply_seeds": len(sup_seeds), "return_seeds": len(ret_seeds),
            "complete": complete, "half_traced": half, "unreached": orphan,
            "n_complete": len(complete), "n_half": len(half),
            "n_unreached": len(orphan)}


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
    # SOURCE INVENTORY + COMPLETENESS (engineer's reading order, 2026-07-31):
    # name the buses FIRST, then every trace starts at one and must arrive at
    # the opposite one. Stating which devices are only half-traced stops a
    # half-loop from being narrated as a finished one.
    lc = loop_completeness(netlist)
    if lc["rails"]:
        out.append("")
        out.append("SOURCES ON THIS SHEET — start every trace at one of these "
                   "and finish at the OPPOSITE one. A loop is not complete "
                   "until it returns to the other rail:")
        for r in lc["rails"][:10]:
            out.append(f"  [{r['side']}/{r['rail']}] net {r['net_id']}: "
                       f"{', '.join(r['labels'][:4])} "
                       f"({r['n_devices']} devices on it)")
    if lc["n_complete"] or lc["n_half"]:
        out.append(f"LOOP COMPLETENESS (measured): {lc['n_complete']} devices "
                   f"reach BOTH a supply and a return rail; {lc['n_half']} "
                   f"reach only ONE; {lc['n_unreached']} reach neither.")
        if lc["half_traced"]:
            out.append("  HALF-TRACED — name the missing side explicitly, or "
                       "say it leaves the sheet and to which drawing. Do NOT "
                       "present these as closed loops:")
            for h in lc["half_traced"][:10]:
                miss = "return" if h["reaches_supply"] else "supply"
                out.append(f"    {h['device']}: {miss} side not traced")
    td = tag_digest(netlist)
    if td:
        out.append("")
        out.append(td)
    cs = contact_digest(netlist)
    if cs:
        out.append("")
        out.append(cs)
    return "\n".join(out)


# --------------------------------------------------------------- tag direction
_COIL_WORDS = ("coil", "relay", "contactor", "solenoid")
# a relay drawn as "Re7"/"K12"/"CR3" — label shape as a backup signal
# when the symbol was typed but not named (general, no vessel token)
_RELAY_LABEL = re.compile(r"^(RE|K|CR|R)\s?\d{1,3}$", re.I)


def tag_direction(netlist: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    SIGNAL vs CONTROL, decided by GEOMETRY not by name (the XA60/XA41 swap).

    A monitoring-system tag block is a COMMAND when its conductor reaches a
    relay/contactor COIL (the monitor energises the coil, typically by
    supplying its negative). It is a STATUS when its conductor is taken off a
    contact, a load or an instrument instead.

    Prompt rules could not settle this because two tag families look alike;
    the drawn net decides. Tag families are discovered from the sheet's own
    labels — no vessel-specific token.
    """
    fam = re.compile(r"^[A-Z]{2}\d{2,3}$")      # e.g. a two-letter + digits tag block
    out: List[Dict[str, Any]] = []
    for n in netlist.get("nets", []):
        tags = [l for l in n.get("labels", []) if fam.match(l.strip())]
        if not tags:
            continue
        devs = [d for d in (n.get("devices") or [])]
        kinds = [k for k in (n.get("device_kinds") or [])]
        # KIND first: bind_devices stores the LABEL ("Re7") as the device name,
        # so searching names for the word "relay" found nothing and every tag
        # came back STATUS. The device's TYPE is the thing that decides this.
        blob = _txt(" ".join(kinds), " ".join(devs))
        reaches_coil = (any(w in blob for w in _COIL_WORDS)
                        or any(_RELAY_LABEL.match(str(d).strip()) for d in devs))
        for t in tags:
            out.append({"tag": t.strip(), "net_id": n["net_id"],
                        "direction": "COMMAND (reaches a coil)" if reaches_coil
                                     else "STATUS (no coil on this net)",
                        "devices_on_net": sorted(set(devs))[:8]})
    # one verdict per tag family prefix, majority wins, so families don't mix
    return out


def tag_digest(netlist: Dict[str, Any]) -> str:
    tags = tag_direction(netlist)
    if not tags:
        return ""
    out = ["TAG DIRECTION (measured from the drawn net, NOT from the tag name — "
           "a tag whose conductor reaches a relay coil is a COMMAND INTO the "
           "circuit; a tag with no coil on its net is a STATUS OUT to the "
           "monitor). Use these verdicts; do not swap tag families:"]
    seen = set()
    for t in tags[:30]:
        key = (t["tag"], t["direction"])
        if key in seen:
            continue
        seen.add(key)
        devs = ", ".join(t["devices_on_net"][:5]) or "(no devices bound)"
        out.append(f"  {t['tag']} ({t['net_id']}): {t['direction']} — on net with: {devs}")
    return "\n".join(out)

# --------------------------------------------------------- contact state (geometry)
_CONTACT_KINDS = ("contact", "relay", "switch", "changeover")


def contact_states(netlist: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    NO vs NC READ FROM THE DRAWING'S TOPOLOGY, not from the symbol picture
    (2026-07-26).

    The insight that makes this free: a contact drawn OPEN is a physical BREAK
    in the conductor, so the two stubs either side land on DIFFERENT nets. A
    contact drawn CLOSED is continuous, so the conductor through it is ONE net.
    The union-find tracer already knows this — nobody had asked it.

      2+ distinct conductor nets under the symbol -> drawn OPEN  -> NO
      exactly 1                                   -> drawn CLOSED -> NC

    This is EVIDENCE, not a verdict: a tracer can split a continuous conductor
    at a junction, and a symbol box can overlap a neighbouring wire. So it is
    reconciled against whatever the vision pass read:

      agree                  -> confirmed (state it plainly)
      vision unknown         -> use the geometry, labelled as measured
      disagree               -> FLAG, never silently pick one

    That reconciliation is the point — two independent readings of the same
    fact is exactly what the multi-source rule asks for, and it turns the
    commonest "contact=unknown" dead end into an answer.
    """
    out: List[Dict[str, Any]] = []
    conductor = {n["net_id"] for n in netlist.get("nets", [])
                 if n.get("kind") == "conductor"}
    for pd in netlist.get("placed_devices", []):
        kind = (pd.get("kind") or "").lower()
        if not any(k in kind for k in _CONTACT_KINDS):
            continue
        nets = [n for n in (pd.get("nets") or []) if n in conductor]
        if not nets:
            continue
        distinct = len(set(nets))
        geo = "NO" if distinct >= 2 else "NC"
        read = (pd.get("contact_state") or "").upper()
        if read in ("NO", "NC"):
            verdict = geo if read == geo else "CONFLICT"
            basis = "confirmed by both the drawn symbol and the wiring" \
                if read == geo else \
                f"symbol read as {read} but the wiring shows {geo}"
        else:
            verdict, basis = geo, "measured from the wiring (symbol not legible)"
        out.append({"device": pd.get("label") or pd.get("kind"),
                    "kind": pd.get("kind", ""),
                    "coil_id": pd.get("coil_id", ""),
                    "state": verdict, "basis": basis,
                    "nets": sorted(set(nets))[:6],
                    "n_distinct_nets": distinct})
    return out


def contact_digest(netlist: Dict[str, Any], limit: int = 24) -> str:
    cs = contact_states(netlist)
    if not cs:
        return ""
    out = ["CONTACT STATE (NO/NC) — a contact drawn OPEN breaks the conductor, "
           "so its two sides sit on DIFFERENT nets; drawn CLOSED it is one "
           "continuous net. Read from the wiring below and cross-checked "
           "against the symbol. Use these verdicts: a load on NO is OFF until "
           "the coil energises; a load on NC is ON until the coil energises "
           "and energising REMOVES it:"]
    for c in cs[:limit]:
        coil = f", coil {c['coil_id']}" if c.get("coil_id") else ""
        out.append(f"  {c['device']} ({c['kind']}{coil}): {c['state']} "
                   f"— {c['basis']} [{c['n_distinct_nets']} net(s): "
                   f"{', '.join(c['nets'][:4])}]")
    conflicts = [c for c in cs if c["state"] == "CONFLICT"]
    if conflicts:
        out.append("  A CONFLICT above means the symbol and the wiring "
                   "disagree — say so explicitly and record it as an "
                   "uncertainty; do NOT pick one silently.")
    return "\n".join(out)
