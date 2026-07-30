"""
SWEEP ADAPTER — feed the vector sweep's measured geometry into the composition
layer that already knows how to reason about it.

WHY THIS EXISTS (found 2026-07-30 by auditing the new chain against the format
the engineer has been building since May):

The vector-first sweep (`tools/sweep_drive.py` -> `extract_document` ->
`run_book_extract`) is a strictly better FRONT END than the vision extractor it
replaced: exact segment geometry, deterministic, $0, no run-to-run variance.
Since c62e8c9 each net also persists what it TOUCHES, so the conductor topology
survives the run.

The reasoning that turns that topology into the artifacts the engineer asked
for — full electrical loops (L to N / - to +, through every terminal, breaker
and relay), flow scenarios per lineup for liquids and gases, PLC channel/side
command chains, hydraulic function slices — lives in `pipeline/compose.py`
(7 drawing classes) and lands on nodes via `pipeline/compose_write.py`.

Neither half imported the other. `compose()` was already written to consume
`_netlist_digest` and `_circuit_digest`, and `netlist.build()` is the only
thing that produced them — by re-deriving the geometry from the PDF AND paying
for a vision OCR pass (`label_ocr.get_labels`). So using the composition layer
meant paying again for work the sweep had already done exactly, and better.

This module converts a sweep PAGE RECORD into the netlist shape
`pipeline.netlist.digest` and `pipeline.circuit.digest` consume. No re-render,
no re-trace, no API call: the sweep's own measurements, reshaped. $0.

    rec  = json.load(open("data/state/sweep/<doc>/p14.json"))
    nl   = netlist_from_page(rec)          # $0
    ext  = extraction_from_page(rec, nl)   # $0 — ready for compose()

WHAT IT DOES NOT DO: decide anything. Every value here is measured or carried
through. Unknown symbol type stays unknown, low-confidence OCR stays flagged,
and a net that touches nothing is reported as touching nothing.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# Same rule as pipeline.net_trace.classify_nets. The sweep runs its own
# union-find in tools/run_book_extract.py and never classifies, so the
# conductor/glyph/symbol split is applied here from the persisted geometry.
# It is COPIED DELIBERATELY rather than re-derived: two different rules for
# "is this a wire" would let the same sheet answer differently depending on
# which path read it.
def classify(bbox: List[float], n_segs: int) -> str:
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    span, thin = max(w, h), min(w, h)
    density = n_segs / max(span, 1.0)
    if span <= 14 and n_segs >= 20:
        return "glyph"
    if span >= 25 and thin <= 6:
        return "conductor"
    if density >= 4 and span < 60:
        return "symbol"
    return "conductor"


def _sym_kind(sym: Dict[str, Any]) -> str:
    """A symbol's device kind, or the honest unknown. `type` is the
    engineer-confirmed type from the symbol bank; `source` records how it was
    resolved (sheet legend > confirmed bank > fleet glossary > unknown)."""
    return sym.get("type") or "<UNKNOWN_SHAPE>"


def netlist_from_page(rec: Dict[str, Any],
                      min_conf: float = 0.0) -> Dict[str, Any]:
    """Reshape one sweep page record into the netlist dict that
    netlist.digest() and circuit.digest() consume.

    `min_conf` drops labels below an OCR confidence before they enter the
    digest. Default 0 keeps everything and lets the digest carry the
    confidence, which is the protocol's preference (flag, do not silently
    discard); raise it when a sheet's OCR is known bad.
    """
    labels: List[Dict[str, Any]] = rec.get("labels") or []
    symbols: List[Dict[str, Any]] = rec.get("typed_symbols") or []
    nets_in: List[Dict[str, Any]] = rec.get("nets") or []

    nets_out: List[Dict[str, Any]] = []
    # symbol index -> the nets it sits on, so a device knows its own
    # connectivity and not just its position.
    sym_nets: Dict[int, List[str]] = {}

    for n in nets_in:
        kind = classify(n["bbox"], n["n_segs"])
        texts, devs = [], []
        for li in n.get("labels", []):
            if li >= len(labels):
                continue
            lb = labels[li]
            t = (lb.get("text") or "").strip()
            if t and lb.get("conf", 0) >= min_conf:
                texts.append(t)
        for si in n.get("symbols", []):
            if si >= len(symbols):
                continue
            devs.append(_sym_kind(symbols[si]))
            sym_nets.setdefault(si, []).append(f"net{n['net_id']}")
        nets_out.append({
            # NET ID TYPE — net_trace emits f"net{i}" (a STRING); the sweep's
            # own union-find persists a bare int. circuit.digest joins net ids
            # into text, so an int id raises TypeError there. The canonical
            # contract is the string, so the adapter converts rather than
            # asking every consumer to accept both. `sweep_net_id` keeps the
            # numeric id so a claim can still be traced to the page record.
            "net_id": f"net{n['net_id']}",
            "sweep_net_id": n["net_id"],
            "kind": kind,
            "labels": texts,
            "devices": sorted(set(devs)),
            "bbox": n["bbox"],
            "n_segments": n["n_segs"],
            "total_len": n.get("total_len"),
        })

    # placed_devices — what circuit.py walks for polarity, common rails and
    # the relay table. A symbol carries its measured net membership, its
    # engineer-confirmed type, and its verify flag; nothing is inferred.
    placed: List[Dict[str, Any]] = []
    for si, s in enumerate(symbols):
        placed.append({
            "index": si,
            "kind": _sym_kind(s),
            "label": s.get("label"),
            "bbox": s.get("bbox"),
            "nets": sym_nets.get(si, []),
            "contact_state": s.get("contact_state"),
            "coil_id": s.get("coil_id"),
            "verify_required": bool(s.get("verify_required")),
            "source": s.get("source"),
        })

    ne = [l for l in labels if (l.get("text") or "").strip()]
    bound = {t for n in nets_out for t in n["labels"]}
    conductors = [n for n in nets_out if n["kind"] == "conductor"]
    return {
        "nets": nets_out,
        "placed_devices": placed,
        "terminals": [], "devices": [],
        "unbound_labels": [l["text"] for l in ne
                           if (l.get("text") or "").strip() not in bound][:200],
        "stats": {
            "segments": rec.get("counts", {}).get("wires", 0),
            "nets": len(nets_out),
            "conductors": len(conductors),
            "labels": len(ne),
            "bound": len(bound),
            "unbound": max(0, len(ne) - len(bound)),
            "devices_located": len(symbols),
            "devices_placed": sum(1 for p in placed if p["nets"]),
            "devices_typed": sum(1 for s in symbols if s.get("type")),
            "source": "vector_sweep",     # never a vision re-read
        },
    }


def extraction_from_page(rec: Dict[str, Any],
                         nl: Optional[Dict[str, Any]] = None,
                         *, sub_type: str = "relay_terminal_wiring",
                         drawing_class: str = "electrical") -> Dict[str, Any]:
    """Shape a sweep page record the way compose() consumes an extraction.

    The elements handed to composition are the TYPED symbols with their
    measured net membership and their nearest labels — not a re-read of the
    sheet. `_netlist_digest` / `_circuit_digest` are the measured-geometry
    blocks compose() already looks for.
    """
    from pipeline import netlist as _netlist
    from pipeline import circuit as _circuit

    nl = nl or netlist_from_page(rec)
    labels = rec.get("labels") or []
    by_net = {n["net_id"]: n for n in nl["nets"]}

    elements = []
    for p in nl["placed_devices"]:
        near = []
        for nid in p["nets"]:
            n = by_net.get(int(nid))
            if n:
                near += n["labels"][:6]
        elements.append({
            "element_type": p["kind"],
            "id": p.get("label"),
            "label": p.get("label") or p["kind"],
            "bbox": p["bbox"],
            "connections": near[:12],   # measured, not proximity-guessed
            "nets": p["nets"],
            "contact_state": p.get("contact_state"),
            "verify_required": p["verify_required"],
        })

    legend = rec.get("legend") or {}
    return {
        "legends": legend.get("entries") or [],
        "legend_context": legend.get("context", ""),
        "survey": {"sub_type": sub_type, "source": "vector sweep page record"},
        "sub_type": sub_type,
        "drawing_class": drawing_class,
        "regions_read": [{
            "region": "ALL (vector geometry)",
            "region_type": sub_type,
            "bbox": [0, 0, 1, 1],
            "reader": "run_book_extract",
            "elements": elements,
        }],
        "labels_read": [{"text": l.get("text"), "conf": l.get("conf"),
                         "bbox": l.get("bbox")}
                        for l in labels if (l.get("text") or "").strip()][:400],
        "_netlist_digest": _netlist.digest(nl, max_nets=60),
        "_circuit_digest": _circuit.digest(nl),
        "_page": rec.get("page"),
    }
