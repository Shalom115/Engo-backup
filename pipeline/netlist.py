"""
NETLIST — geometry + labels fused into a walkable circuit (2026-07-22).

The three-layer electrical protocol, each layer using the tool that can
actually do the job:

  LAYER 1  GEOMETRY  (pipeline.net_trace)   what is connected to what.
           Deterministic: real vector segments unioned into nets. No model.
  LAYER 2  LABELS    (pipeline.label_ocr)   what each thing is called.
           OCR with coordinates, bound to the net whose ink it sits on.
  LAYER 3  MEANING   (vision + glossary, downstream)   what it IS and DOES.

Why the old pipeline failed: it asked ONE vision call to do all three at once,
so connectivity was inferred from label proximity — "a number near a switch"
became "a pin on that switch". Connectivity is now measured, not guessed; the
model is left to do only naming and typing.

Output shape (per sheet):
  {"nets": [{net_id, kind, bbox, labels[]}],
   "terminals": [{label, net_id, point}],
   "devices":  [{label, net_id, kind}],
   "unbound_labels": [...]}
"""

from __future__ import annotations

import math
import re
import config  # loads .env (API keys) on import
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pipeline import net_trace

# A terminal/wire number is a bare 1-3 digit token; device ids carry letters.
_NUMERIC = re.compile(r"^\d{1,3}$")
_DEVICE_ID = re.compile(r"^[A-Za-z]{1,4}[-_ ]?\d{1,3}(\.\d+)?$")


def build(pdf_bytes: bytes, page_index: int = 0, *,
          labels: Optional[List[Dict[str, Any]]] = None,
          located: Optional[List[Dict[str, Any]]] = None,
          locate: bool = True,
          tol: float = 0.75, bind_dist: float = 10.0) -> Dict[str, Any]:
    """Full netlist for one sheet: geometry + labels + located device symbols."""
    from pipeline import label_ocr
    segs = net_trace.extract_segments(pdf_bytes, page_index)
    nets = net_trace.classify_nets(net_trace.build_nets(segs, tol=tol))
    if labels is None:
        labels = label_ocr.get_labels(pdf_bytes, page_index)
    net_trace.bind_labels(nets, labels, max_dist=bind_dist)

    bound = {id(n): n for n in nets if n["labels"]}
    terminals, devices = [], []
    for n in nets:
        for lb in n["labels"]:
            t = lb["text"].strip()
            rec = {"label": t, "net_id": n["net_id"], "net_kind": n["kind"]}
            if _NUMERIC.match(t):
                terminals.append(rec)
            elif _DEVICE_ID.match(t):
                devices.append(rec)
    bound_texts = {l["text"] for n in nets for l in n["labels"]}
    unbound = [l for l in labels if l["text"] not in bound_texts]

    # LAYER 3: locate device symbols and bind them to the nets they touch, so
    # terminal->device is answerable by geometry (the piece missing at 50%).
    result_stub = {"_nets_full": nets}
    if located is None and locate:
        from pipeline import device_locate
        try:
            located = device_locate.locate_devices(pdf_bytes, page_index)
        except Exception:
            located = []
    placed_devices = []
    if located:
        # located boxes are already page-points (device_locate emits points)
        bind_devices(result_stub, located, page_size=None)
        placed_devices = result_stub.get("placed_devices", [])

    return {"nets": [{"net_id": n["net_id"], "kind": n["kind"],
                      "devices": n.get("devices", []),
                      "bbox": [round(v, 1) for v in n["bbox"]],
                      "n_segments": n["n_segments"],
                      "labels": [l["text"] for l in n["labels"]]}
                     for n in nets],
            "_nets_full": nets,
            "terminals": terminals,
            "devices": devices,
            "placed_devices": placed_devices,
            "unbound_labels": [l["text"] for l in unbound],
            "stats": {"segments": len(segs), "nets": len(nets),
                      "conductors": sum(1 for n in nets if n["kind"] == "conductor"),
                      "labels": len(labels),
                      "bound": len(bound_texts),
                      "unbound": len(unbound),
                      "devices_located": len(located or []),
                      "devices_placed": len(placed_devices)}}


def bind_devices(netlist: Dict[str, Any],
                 devices: Sequence[Dict[str, Any]],
                 *, page_size: Optional[Tuple[float, float]] = None,
                 max_dist: float = 14.0) -> Dict[str, Any]:
    """
    LAYER 3 BINDING: attach vision-identified DEVICES (relay, valve motor,
    fuse, switch, terminal strip...) to the nets their symbol touches.

    This is what makes "which valve does this terminal drive?" answerable:
    once a valve-motor symbol owns a set of nets, any terminal on those nets
    is wired to that valve. Without it the netlist knows the wires but not
    what sits on their ends.

    `devices`: [{"label":..., "kind":..., "bbox":[x0,y0,x1,y1]}]; bbox may be
    normalized (pass page_size) or already in points.
    """
    nets = netlist["_nets_full"]
    placed: List[Dict[str, Any]] = []
    for dv in devices:
        if not isinstance(dv, dict):    # same guard: non-dict device entry
            continue
        bx = dv.get("bbox")
        if not bx or len(bx) != 4:
            continue
        if page_size and max(bx) <= 1.0:
            W, H = page_size
            bx = [bx[0] * W, bx[1] * H, bx[2] * W, bx[3] * H]
        touching = []
        for n in nets:
            if n.get("kind") == "glyph":
                continue
            x0, y0, x1, y1 = n["bbox"]
            # symbol box overlapping (or nearly touching) the net's ink
            if (x0 - max_dist <= bx[2] and x1 + max_dist >= bx[0] and
                    y0 - max_dist <= bx[3] and y1 + max_dist >= bx[1]):
                d = min((math.dist(((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2), p)
                         for p in n["points"]), default=float("inf"))
                if d <= max(max_dist, (bx[2] - bx[0] + bx[3] - bx[1]) / 2):
                    touching.append(n["net_id"])
        rec = {"label": dv.get("label", ""), "kind": dv.get("kind", ""),
               "bbox": [round(v, 1) for v in bx], "nets": touching[:12]}
        placed.append(rec)
        for nid in touching:
            for n in nets:
                if n["net_id"] == nid:
                    n.setdefault("devices", []).append(rec["label"] or rec["kind"])
    netlist["placed_devices"] = placed
    return netlist


def what_drives(netlist: Dict[str, Any], terminal_label: str,
                near_point: Optional[Point] = None) -> List[str]:
    """
    Devices reachable from a terminal, by geometry. When a label is ambiguous
    (many '9's on a sheet) pass `near_point` to pick the right instance —
    ambiguity is resolved by POSITION, never by guessing.
    """
    nets = netlist["_nets_full"]
    cands = [n for n in nets
             if any(l["text"].strip() == terminal_label.strip() for l in n["labels"])]
    if near_point and cands:
        cands = [min(cands,
                     key=lambda n: min(math.dist(near_point, p) for p in n["points"]))]
    out: List[str] = []
    for n in cands:
        out.extend(n.get("devices", []))
    return sorted(set(out))


def connected(netlist: Dict[str, Any], a: str, b: str) -> Dict[str, Any]:
    """THE finger test, by name: are two labelled points on the same conductor?"""
    nets = netlist["_nets_full"]
    na = net_trace.net_of_label(nets, a)
    nb = net_trace.net_of_label(nets, b)
    return {"a": a, "b": b,
            "a_net": na["net_id"] if na else None,
            "b_net": nb["net_id"] if nb else None,
            "connected": bool(na and nb and na["net_id"] == nb["net_id"])}


def neighbours(netlist: Dict[str, Any], label: str) -> List[str]:
    """Everything else sitting on the same net as `label` — its wire-mates."""
    nets = netlist["_nets_full"]
    n = net_trace.net_of_label(nets, label)
    if not n:
        return []
    return [l["text"] for l in n["labels"] if l["text"].strip().lower()
            != label.strip().lower()]


def digest(netlist: Dict[str, Any], max_nets: int = 40) -> str:
    """
    Prompt block for composition: MEASURED connectivity. Composition must build
    loops from THIS, not from what looks near what on the raster.
    """
    s = netlist["stats"]
    out = [f"MEASURED NETLIST (geometry, not inference) — {s['segments']} drawn "
           f"segments resolved into {s['nets']} nets ({s['conductors']} "
           f"conductors); {s['bound']}/{s['labels']} labels bound to ink.",
           "Each line below is ONE electrical node and everything physically "
           "wired to it. Two labels on the SAME net are connected; labels on "
           "different nets are NOT — do not join them because they sit near "
           "each other on the sheet."]
    shown = 0
    for n in netlist["nets"]:
        if n["kind"] != "conductor":
            continue
        devs = n.get("devices", [])
        if len(n["labels"]) < 2 and not devs:
            continue
        line = f"  {n['net_id']}: " + " = ".join(n["labels"][:12])
        if devs:
            line += "   [devices on this net: " + ", ".join(sorted(set(devs))[:6]) + "]"
        out.append(line)
        shown += 1
        if shown >= max_nets:
            break
    if netlist["unbound_labels"]:
        out.append("  (labels not bound to any conductor — treat as annotation "
                   "or off-net text: " +
                   ", ".join(netlist["unbound_labels"][:20]) + ")")
    return "\n".join(out)
