"""
POWER-PATH / CIRCUIT-LOOP PROTOCOL (engineer-mandated 2026-07-05).

PRINCIPLE: every equipment node should carry the traceable power path — the
chain of supply device -> relay/terminal/controller -> equipment, INCLUDING
the negative/return leg — assembled from the wiring elements already
extracted off the sheet the equipment's supply fact came from. This is what
makes "this equipment is powered by relay X, activated by terminal Y, and
getting negative from connection Z" answerable, and lets Engo call it back
for elimination during a live fault.

WHY THIS IS AN ASSEMBLY STEP, NOT A NEW EXTRACTION PASS: coverage-guarantee
extraction (electrical_extract.read_wiring_coverage) already captures each
element's immediate wiring text in `connections` — verified on real ledger
data 2026-07-05: relay 91%, terminal 91%, terminal_strip 78%, plug_pin 89%,
controller_module 81% of elements carry non-empty connections. What was
missing was RESOLVING that free-text adjacency into a graph and walking it.
No new vision calls are required for the base trace.

PRINCIPLES (general, vessel-agnostic — this module carries no vessel tokens):

  P1 SCOPE TO REGION, NOT SHEET. The same id/label ('Re', '63A', 'Q1', 'F1')
     recurs across DIFFERENT physical sub-circuits on one sheet (separate
     panel groups, repeated similar circuits — confirmed on the real shore-
     power sheet: 'Re', '63A', 'Q1'-'Q3', 'F1'/'F2' each appear 2-3x in
     unrelated locations). Resolve within the tile/region an element was
     found in FIRST (electrical_extract already stamps `_bbox` = the
     tile/region rectangle); only fall back to sheet-wide search when the
     tile-scoped search finds nothing, and require every id-token be >=2
     chars at that wider scope (P2) to keep single-letter ids from drifting
     across the whole sheet.
  P2 TOKEN-BOUNDARY MATCH, NEVER SUBSTRING. Short ids ('V','N','E','1') falsely
     substring-match almost any text ('GND' contains the letter 'N'). A
     candidate resolves only if ALL of its own id-tokens appear as WHOLE
     tokens in the connection text. Validated 2026-07-05 on a real sheet:
     naive substring matching produced dozens of false hits; token-boundary
     matching on the same data did not.
  P3 MULTI-HOP IS NORMAL, NOT A FAILURE. A connections string frequently names
     BOTH neighbors of an inline element ("63A breaker R-out -> Shore/Ship
     Isolator Panel R") — that is two real edges (upstream + downstream), not
     an ambiguity. Every distinct token-matched candidate in one string gets
     its own edge.
  P4 ANCHOR AT RESOLVED EQUIPMENT, WALK OUTWARD. Don't solve the graph for
     every isolated relay in the abstract — start from an element that is
     already resolved to equipment (an electrical_supply / feeder_supply /
     control_element / status_indicator fact) and walk the sheet's graph
     outward from that anchor, hop by hop, up to a hop budget.
  P5 PRESERVE RAIL/POLARITY. Tag each traced edge's rail (positive/negative/
     ground/signal/control/unknown) from keywords in the label/connection
     text wherever determinable — this is exactly the "getting negative from
     connection Z" detail the trace exists to carry.
  P6 NEVER FABRICATE A LINK. Zero token-matched candidates -> the raw text is
     kept as an unresolved leaf, verbatim, never guessed.
  P7 STORE BOTH FORMS ON THE NODE. A structured `power_path` fact (hop list
     with provenance/bbox) AND a rolled-up plain-language string, so it reads
     at a glance during a live diagnostic and is still traceable back to a
     sheet+bbox.
  P8 GENERAL PROTOCOL, GOLD-BLIND. No vessel-specific tokens in this module —
     it operates purely on element_type/id/label/connections/bbox, generic to
     any wiring sheet on any vessel.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_RAIL_PATTERNS = [
    ("negative", re.compile(r"\b(neg(ative)?|return|rtn|-ve)\b", re.I)),
    ("positive", re.compile(r"\b(pos(itive)?|\+ve)\b", re.I)),
    ("ground", re.compile(r"\b(gnd|ground|earth)\b", re.I)),
    ("signal", re.compile(r"\b(signal|status|monitor(ing)?|sync)\b", re.I)),
    ("control", re.compile(r"\b(control|command|enable|trigger)\b", re.I)),
]

# ROLE classification (engineer-mandated 2026-07-05, session 2): a relay/
# contactor's coil needs TWO distinct things — SUPPLY (power to the coil,
# from a breaker/fuse/bus) and an ACTIVATION SOURCE (whatever completes the
# circuit to energize it: a switch, a pressure/float/level sensor, a button,
# a command signal, or another relay's contacts). Its own switched output
# then feeds an OUTPUT — validated on real data (GM-102 Re1 "Salt Water Pump
# control": terminal 18 -> PRESSURE SW (switch) + PUMP device — the pressure
# switch IS the activation source, already found by the graph walk, just not
# previously labeled as such). Never invented — only tagged when the
# connected element genuinely carries switch/sensor/coil/contact vocabulary.
_ACTIVATION_KW = re.compile(
    r"\b(switch|button|press(ure)?|float|sensor|manual|man|enable|trigger)\b", re.I)
_COIL_KW = re.compile(r"\bcoil\b", re.I)
_CONTACT_KW = re.compile(r"\bcontact\b", re.I)


def infer_role(text: Optional[str], to_type: Optional[str]) -> Optional[str]:
    """Best-effort functional role of one edge, relative to a relay/contactor:
    'activation' (what energizes the coil), 'coil_supply' (power to the coil),
    'contact_output' (what the switched contacts feed onward), or None when
    the text doesn't carry enough signal to say — never guessed."""
    t = text or ""
    if to_type == "switch" or _ACTIVATION_KW.search(t):
        return "activation"
    if _CONTACT_KW.search(t):
        return "contact_output"
    if _COIL_KW.search(t):
        return "coil_supply"
    return None


def _toks(s: Optional[str]) -> set:
    return set(t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if t)


def _id_toks(el: Dict[str, Any]) -> set:
    return _toks(str(el.get("id") or ""))


def infer_rail(*texts: Optional[str]) -> str:
    blob = " ".join(t for t in texts if t)
    for rail, pat in _RAIL_PATTERNS:
        if pat.search(blob):
            return rail
    return "unknown"


def _tile_key(el: Dict[str, Any]):
    b = el.get("_bbox")
    return tuple(round(x, 3) for x in b) if b else None


def _brief(e: Dict[str, Any]) -> Dict[str, Any]:
    b = {"id": e.get("id"), "type": e.get("element_type"), "label": e.get("label")}
    if e.get("has_builtin_fuse"):
        b["has_builtin_fuse"] = True  # engineer rule: fused terminals are
        # prime troubleshooting suspects — the flag must survive into hops
    return b


def build_edges(elements: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    """
    For every element (keyed by index — ids are NOT unique across a sheet,
    P1), resolve each of its `connections` strings to sibling element(s) on
    the same sheet. Tile-scoped first; sheet-wide fallback only for ids whose
    every token is >=2 chars (P2 risk control). Multiple candidates in one
    string all become edges (P3). Zero hits -> kept unresolved, verbatim (P6).
    """
    elements = [e for e in elements if isinstance(e, dict)]
    by_tile: Dict[Any, List[int]] = {}
    for i, e in enumerate(elements):
        by_tile.setdefault(_tile_key(e), []).append(i)

    edges: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(len(elements))}
    for i, e in enumerate(elements):
        same_tile = [j for j in by_tile.get(_tile_key(e), []) if j != i]
        for c in (e.get("connections") or []):
            if not isinstance(c, str) or not c.strip():
                continue
            ct = _toks(c)
            if not ct:
                continue
            hits = [
                j for j in same_tile
                if (idt := _id_toks(elements[j])) and idt <= ct
                # guard: same id + same tile is almost always a duplicate DETECTION
                # of the same physical part (extraction redundancy across
                # overlapping grid tiles), not a second real neighbor — an edge
                # between two identically-id'd same-tile elements carries no
                # diagnostic value either way (indistinguishable), so it's
                # dropped rather than shown as a meaningless self-loop.
                and _id_toks(elements[j]) != _id_toks(elements[i])
            ]
            tier = "tile"
            if not hits:
                hits = [
                    j for j in range(len(elements))
                    if j != i
                    and (idt := _id_toks(elements[j]))
                    and idt <= ct
                    and all(len(t) >= 2 for t in idt)  # P2: no single-letter drift sheet-wide
                    and idt != _id_toks(elements[i])   # same duplicate-detection guard as tile-scope
                ]
                tier = "sheet" if hits else "unresolved"
            rail = infer_rail(c, e.get("label"))
            if hits:
                for j in hits:
                    edges[i].append({"to": j, "raw": c, "tier": tier, "rail": rail})
            else:
                edges[i].append({"to": None, "raw": c, "tier": "unresolved", "rail": rail})
    return edges


def trace_power_path(anchor_index: int, elements: List[Dict[str, Any]],
                      edges: Dict[int, List[Dict[str, Any]]],
                      *, max_hops: int = 6) -> Dict[str, Any]:
    """
    Walk the sheet graph outward from an anchor element (an already-resolved
    equipment-supply element). Edges are walked as undirected — a wire
    connects both ways even when only one side's connections text describes
    it — but each edge still carries which element's text produced it.
    Returns {hops, unresolved_refs, rails_seen}.
    """
    adj: Dict[int, List[Dict[str, Any]]] = {i: list(v) for i, v in edges.items()}
    for i, es in edges.items():
        for ed in es:
            if ed["to"] is not None:
                adj.setdefault(ed["to"], []).append(
                    {"to": i, "raw": ed["raw"], "tier": ed["tier"], "rail": ed["rail"]})

    visited = {anchor_index}
    hops: List[Dict[str, Any]] = []
    unresolved: List[Dict[str, Any]] = []
    frontier = [anchor_index]
    depth = 0
    while frontier and depth < max_hops:
        nxt = []
        for i in frontier:
            for ed in adj.get(i, []):
                if ed["to"] is None:
                    unresolved.append({"from": _brief(elements[i]), "raw": ed["raw"], "rail": ed["rail"]})
                    continue
                if ed["to"] in visited:
                    continue
                visited.add(ed["to"])
                role = infer_role(ed["raw"], elements[ed["to"]].get("element_type"))
                hops.append({
                    "from": _brief(elements[i]), "to": _brief(elements[ed["to"]]),
                    "rail": ed["rail"], "role": role, "via_text": ed["raw"], "resolution_tier": ed["tier"],
                    "bbox": elements[ed["to"]].get("_bbox"),
                })
                nxt.append(ed["to"])
        frontier = nxt
        depth += 1
    rails_seen = sorted({h["rail"] for h in hops if h["rail"] != "unknown"})
    return {"hops": hops, "unresolved_refs": unresolved, "rails_seen": rails_seen}


_DC_RE = re.compile(r"\bdc\b", re.I)


def check_dc_fuse_completeness(anchor: Dict[str, Any], trace: Dict[str, Any],
                               *, assume_dc: bool = False) -> Optional[str]:
    """
    Engineer's rule (2026-07-05): a DC loop must have a fuse somewhere in it
    (AC circuits more commonly rely on a breaker alone). If this is a DC path
    and none of the hops involve a fuse-type element, that's worth a flag —
    either a genuinely breaker-only design (a real answer) or a sign the fuse
    sits beyond this trace's hop range / on another sheet (a coverage gap).
    Never silently completes the trace as if the question doesn't matter.

    "DC-ness" is detected two ways: (1) text — the word "DC" appears in a
    label this trace touched; (2) `assume_dc` — an explicit hint from the
    CALLER, who may know the sheet's own title says e.g. "+24V DC
    DISTRIBUTION" even though that word never recurs on every individual
    label. Text-only detection under-fires (silent, not falsely alarmed) on
    sheets like a bilge relay chain that live on a DC system but never spell
    "DC" near any individual component — `assume_dc` is how a caller with
    real document context (the sheet's own title) closes that gap without
    this gold-blind module hardcoding any vessel assumption itself.
    """
    blob = " ".join([anchor.get("label") or ""] +
                    [f"{h['from']['label'] or ''} {h['to']['label'] or ''}" for h in trace["hops"]])
    if not (assume_dc or _DC_RE.search(blob)):
        return None
    has_fuse = any(h["from"]["type"] == "fuse" or h["to"]["type"] == "fuse" for h in trace["hops"])
    if has_fuse:
        return None
    return ("DC circuit — no fuse element found in this traced path. Verify: this may be a "
            "breaker-only design, or the fuse sits beyond this trace's hop range / on another sheet.")


def render_trace(anchor_label: str, trace: Dict[str, Any]) -> str:
    lines = [f"Power path for {anchor_label}:"]
    for h in trace["hops"]:
        rail = f" [{h['rail']}]" if h["rail"] != "unknown" else ""
        role = ""
        if h.get("role") == "activation":
            role = "  <-- ACTIVATED BY"
        elif h.get("role") == "contact_output":
            role = "  <-- contact output"
        elif h.get("role") == "coil_supply":
            role = "  <-- coil supply"
        lines.append(
            f"  {h['from']['id']} ({h['from']['type']}) -> "
            f"{h['to']['id']} ({h['to']['type']}){rail} — \"{h['via_text']}\"{role}"
        )
    if trace["unresolved_refs"]:
        lines.append("  Unresolved references (kept verbatim, not guessed):")
        for u in trace["unresolved_refs"]:
            rail = f" [{u['rail']}]" if u["rail"] != "unknown" else ""
            lines.append(f"    {u['from']['id']}{rail}: \"{u['raw']}\"")
    if trace.get("dc_fuse_flag"):
        lines.append(f"  ⚠ {trace['dc_fuse_flag']}")
    return "\n".join(lines)


def build_power_path_fact(anchor_index: int, elements: List[Dict[str, Any]],
                           *, max_hops: int = 6, assume_dc: bool = False) -> Dict[str, Any]:
    """One-call entry point: build the sheet graph, trace from the anchor,
    return {hops, unresolved_refs, rails_seen, dc_fuse_flag, trace_text} ready
    to attach as a node fact. Pass assume_dc=True when the CALLER knows the
    sheet is a DC distribution sheet (e.g. its own title says so) even if
    that word doesn't recur on every individual label."""
    elements = [e for e in elements if isinstance(e, dict)]
    edges = build_edges(elements)
    trace = trace_power_path(anchor_index, elements, edges, max_hops=max_hops)
    anchor = elements[anchor_index]
    trace["dc_fuse_flag"] = check_dc_fuse_completeness(anchor, trace, assume_dc=assume_dc)
    trace["trace_text"] = render_trace(f"{anchor.get('id')} ({anchor.get('label')})", trace)
    return trace


# ===========================================================================
# CROSS-DRAWING LOOP FOLLOWING (engineer-mandated 2026-07-10).
#
# "Follow the power loop from supply to return... look at the full cycle even
# if it means moving to another drawing in the book when it indicates to move
# to another drawing." A single-sheet trace stops at the sheet edge, but the
# real supply→return cycle frequently CONTINUES on another sheet: a wire
# leaves with a "see DWG N" / "→ DWG N" reference and the rest of the loop
# lives there. This walks INTO the referenced sheet (when that drawing is in
# the book) and keeps tracing; a target NOT in the book is flagged with its
# name, never silently dropped (P6). Loop protection + a sheet budget bound it.
# Gold-blind: operates only on drawing-number tokens + element id/label/
# connection text, no vessel specifics.
# ===========================================================================

# A wire that references another drawing: "DWG 117", "DWG. 410a", "see DWG 102",
# "→ DWG 117", "Drawing 102", "ref sheet 110b". The captured token is the
# drawing number (2-3 digits + optional letter), the join key to the book index.
_XDWG_RE = re.compile(r"\b(?:dwg|drawing|sheet|ref)\.?\s*#?\s*(\d{2,3}[a-z]?)\b", re.I)


def drawing_ref(text: Optional[str]) -> Optional[str]:
    """The drawing number a text points to ('see DWG 117' -> '117'), or None."""
    m = _XDWG_RE.search(text or "")
    return m.group(1).lower() if m else None


def normalize_drawing_key(drawing_no: Optional[str]) -> Optional[str]:
    """A ledger drawing_no -> its join key: 'GMMS 108'-110b' -> '110b'."""
    m = re.search(r"(\d{2,3}[a-z]?)\s*$", (drawing_no or "").strip())
    return m.group(1).lower() if m else None


def build_book_index(pages: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Map drawing-number key -> that page record, for cross-sheet continuation.
    `pages` are ledger records carrying {drawing_no, wiring_elements}."""
    idx: Dict[str, Dict[str, Any]] = {}
    for p in pages:
        key = normalize_drawing_key(p.get("drawing_no"))
        if key:
            idx.setdefault(key, p)
    return idx


def _entry_index_on_sheet(elements: List[Dict[str, Any]], hint_text: str) -> Optional[int]:
    """Where a cross-drawing pointer lands on the TARGET sheet. The pointer
    text often carries a pin/panel hint ('to PASSAGE PANEL pin 2, see DWG 117');
    match it to a target element by shared whole tokens (P2). Returns the
    best-matched element index, or None when nothing on the sheet matches —
    then the continuation is recorded as 'entry not pinned', never guessed."""
    hint = _toks(hint_text) - {"dwg", "drawing", "sheet", "ref", "see", "to", "the"}
    hint = {t for t in hint if not (t.isdigit() and len(t) == 3)}  # drop the drawing number itself
    if not hint:
        return None
    best, best_overlap = None, 0
    for j, e in enumerate(elements):
        etoks = _toks(str(e.get("id") or "")) | _toks(str(e.get("label") or ""))
        overlap = len(hint & etoks)
        if overlap > best_overlap:
            best, best_overlap = j, overlap
    return best if best_overlap >= 1 else None


def trace_full_loop(anchor_index: int, page: Dict[str, Any],
                    all_pages: List[Dict[str, Any]], *, max_hops: int = 6,
                    max_sheets: int = 4, assume_dc: bool = False) -> Dict[str, Any]:
    """
    Trace supply→return ACROSS sheets. Start on `page` at `anchor_index`; when a
    traced edge or unresolved ref points to another drawing in the book, continue
    the trace there (entry pinned by the pointer's hint tokens when possible).

    Returns {segments:[{drawing, anchor, trace, entry_pinned}],
    external_continuations:[{target_drawing, from_text}], sheets_visited,
    cross_sheet, trace_text}. Bounded by max_sheets and a visited-drawing set
    (no infinite ping-pong between two mutually-referencing sheets).
    """
    book = build_book_index(all_pages)
    start_key = normalize_drawing_key(page.get("drawing_no")) or "?"
    segments: List[Dict[str, Any]] = []
    external: List[Dict[str, Any]] = []
    visited_drawings = {start_key}

    # queue entries: (drawing_key, page_record, anchor_index, entry_pinned, via_text)
    queue = [(start_key, page, anchor_index, True, "")]
    while queue and len(segments) < max_sheets:
        dkey, pg, aidx, pinned, via = queue.pop(0)
        els = [e for e in (pg.get("wiring_elements") or []) if isinstance(e, dict)]
        if not els:
            continue
        if not pinned or aidx is None or aidx >= len(els):
            # ENTRY NOT PINNED: the pointer named the drawing but no element on
            # the target sheet token-matched it. Tracing from an arbitrary
            # element would present NOISE as the loop's continuation (P6:
            # never fabricate) — record the un-pinned continuation honestly
            # instead, with no trace.
            segments.append({"drawing": pg.get("drawing_no"), "drawing_key": dkey,
                             "anchor": None, "entry_pinned": False,
                             "entered_via": via, "trace": None,
                             "note": "loop continues on this sheet, but the pointer "
                                     "did not name a specific terminal/element — "
                                     "entry point needs the sheet read directly"})
            continue
        trace = build_power_path_fact(aidx, els, max_hops=max_hops, assume_dc=assume_dc)
        segments.append({"drawing": pg.get("drawing_no"), "drawing_key": dkey,
                         "anchor": _brief(els[aidx]), "entry_pinned": pinned,
                         "entered_via": via, "trace": trace})
        # collect cross-drawing pointers from EVERYWHERE they appear on this
        # segment: the anchor's own label + connections (the "see DWG N" is
        # frequently on the terminal strip itself), each hop's via-text AND the
        # label of the element it reaches, and the unresolved refs.
        pointer_texts = [els[aidx].get("label") or ""]
        pointer_texts += [c for c in (els[aidx].get("connections") or []) if isinstance(c, str)]
        for h in trace["hops"]:
            pointer_texts.append(h["via_text"])
            pointer_texts.append((h["to"] or {}).get("label") or "")
        pointer_texts += [u["raw"] for u in trace["unresolved_refs"]]
        for txt in pointer_texts:
            ref = drawing_ref(txt)
            if not ref or ref in visited_drawings:
                continue
            visited_drawings.add(ref)
            if ref in book:
                tgt_pg = book[ref]
                tgt_els = [e for e in (tgt_pg.get("wiring_elements") or []) if isinstance(e, dict)]
                entry = _entry_index_on_sheet(tgt_els, txt)
                queue.append((ref, tgt_pg, entry if entry is not None else 0,
                              entry is not None, txt))
            else:
                external.append({"target_drawing": ref, "from_text": txt,
                                 "note": "referenced drawing is not in this book — "
                                         "loop continues on an external sheet"})
    return {
        "segments": segments,
        "external_continuations": external,
        "sheets_visited": [s["drawing"] for s in segments],
        "cross_sheet": len(segments) > 1 or bool(external),
        "trace_text": render_full_loop(segments, external),
    }


def render_full_loop(segments: List[Dict[str, Any]],
                     external: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for n, seg in enumerate(segments, 1):
        if seg.get("trace") is None:
            lines.append(f"── Sheet {n}: {seg['drawing']}  [loop continues here — "
                         f"entry not pinned to a terminal; read this sheet directly] "
                         f"(from: \"{seg['entered_via']}\")")
            continue
        head = f"── Sheet {n}: {seg['drawing']} (anchor {seg['anchor']['id']})"
        if n > 1:
            head += f"  [entered via: \"{seg['entered_via']}\"]"
        lines.append(head)
        lines.append(seg["trace"]["trace_text"])
    if external:
        lines.append("── Loop continues on drawings OUTSIDE this book (not traceable here):")
        for x in external:
            lines.append(f"    → DWG {x['target_drawing']}  (from: \"{x['from_text']}\")")
    return "\n".join(lines)
