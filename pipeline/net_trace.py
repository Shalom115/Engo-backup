"""
GEOMETRIC NET TRACER (2026-07-22) — the answer to "why can I follow the line
with my finger and Engo can't".

THE DIAGNOSIS. Until now every "connection" came from a vision model looking at
a raster crop. A vision model does not traverse a conductor; it reads nearby
labels and associates them. That is why it reported "pins 1/2" (a caption next
to the switch) instead of cables 1&2 running to T/S C terminals 48/49, and why
it named the plug-D signal terminals instead of the plug-C motor terminals —
both are plausible numbers sitting near the right place. No prompt fixes this,
and a stronger model only makes the guess more convincing: the model is not
doing geometry.

THE FIX. These drawings are VECTOR. GM-114a alone carries ~23,000 line
segments with exact endpoints. A conductor is therefore an object we can
follow deterministically:

  1. pull every line segment from the PDF (exact coordinates);
  2. union segments that share an endpoint  ->  a NET (one electrical node);
  3. bind OCR'd labels to the net whose geometry they sit on;
  4. "follow the line" becomes a graph walk over real ink — exact, repeatable,
     no inference.

The vision model is then used for what it is good at (reading text, naming
device types), never for deciding what connects to what.

Text note: on these sheets the labels are drawn as vector outlines, so the PDF
text layer is empty — label STRINGS still come from vision OCR with boxes;
only CONNECTIVITY moves to geometry.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

Point = Tuple[float, float]
Segment = Tuple[Point, Point]


# --------------------------------------------------------------- extraction
def extract_segments(pdf_bytes: bytes, page_index: int = 0,
                     *, include_rects: bool = True) -> List[Segment]:
    """
    Every drawn line segment on the page, in PDF points.

    ROTATION (found on BAE 2026-07-22): pages in one file can carry different
    /Rotate values (BAE p0 = 90, the rest 0). `page.get_drawings()` returns
    coordinates in UNROTATED space, while renders/OCR boxes follow the
    displayed rotation — mixing the two silently misaligns every label bind.
    Normalizing here keeps geometry and labels in ONE space.
    """
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_index]
    # use PyMuPDF's own rotation matrix — exact, no hand-derived trig
    rot = page.rotation or 0
    _m = page.rotation_matrix if rot else None
    def _fix(pt):
        if _m is None:
            return pt
        p = fitz.Point(pt[0], pt[1]) * _m
        return (p.x, p.y)
    segs: List[Segment] = []
    for path in page.get_drawings():
        for item in path["items"]:
            kind = item[0]
            if kind == "l":
                a, b = item[1], item[2]
                segs.append((_fix((a.x, a.y)), _fix((b.x, b.y))))
            elif kind == "re" and include_rects:
                r = item[1]
                c = [_fix(p) for p in ((r.x0, r.y0), (r.x1, r.y0),
                                       (r.x1, r.y1), (r.x0, r.y1))]
                for i in range(4):
                    segs.append((c[i], c[(i + 1) % 4]))
            elif kind == "qu" and include_rects:
                q = item[1]
                pts = [_fix(p) for p in ((q.ul.x, q.ul.y), (q.ur.x, q.ur.y),
                                         (q.lr.x, q.lr.y), (q.ll.x, q.ll.y))]
                for i in range(4):
                    segs.append((pts[i], pts[(i + 1) % 4]))
    return segs


# ------------------------------------------------------------------- nets
class _DSU:
    def __init__(self) -> None:
        self.p: Dict[int, int] = {}

    def find(self, x: int) -> int:
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def _snap(p: Point, tol: float) -> Tuple[int, int]:
    return (int(round(p[0] / tol)), int(round(p[1] / tol)))


def build_nets(segments: Sequence[Segment], *, tol: float = 0.75,
               drop_frame: bool = True) -> List[Dict[str, Any]]:
    """
    Union segments that share an endpoint (within `tol` points) into NETS.
    A net is one electrical node: everything galvanically joined by drawn ink.

    `drop_frame` removes the page border/title-block rectangles, which would
    otherwise bridge unrelated circuits into one giant net.
    """
    if not segments:
        return []
    xs = [c for s in segments for c in (s[0][0], s[1][0])]
    ys = [c for s in segments for c in (s[0][1], s[1][1])]
    W, H = max(xs) - min(xs), max(ys) - min(ys)

    dsu = _DSU()
    node_of: Dict[Tuple[int, int], int] = {}
    seg_nodes: List[Tuple[int, int]] = []
    kept: List[Segment] = []
    for (a, b) in segments:
        if drop_frame:
            length = math.dist(a, b)
            # a single segment spanning most of the sheet is frame/rule, not wire
            if length > 0.85 * max(W, H):
                continue
        ka, kb = _snap(a, tol), _snap(b, tol)
        for k in (ka, kb):
            if k not in node_of:
                node_of[k] = len(node_of)
        ia, ib = node_of[ka], node_of[kb]
        dsu.union(ia, ib)
        seg_nodes.append((ia, ib))
        kept.append((a, b))

    groups: Dict[int, List[int]] = defaultdict(list)
    for idx, (ia, _ib) in enumerate(seg_nodes):
        groups[dsu.find(ia)].append(idx)

    nets: List[Dict[str, Any]] = []
    for gid, seg_idxs in groups.items():
        pts = [p for i in seg_idxs for p in kept[i]]
        x0 = min(p[0] for p in pts); x1 = max(p[0] for p in pts)
        y0 = min(p[1] for p in pts); y1 = max(p[1] for p in pts)
        nets.append({
            "net_id": f"net{len(nets)}",
            "segments": [kept[i] for i in seg_idxs],
            "n_segments": len(seg_idxs),
            "bbox": (x0, y0, x1, y1),
            "points": pts,
            "labels": [],
        })
    nets.sort(key=lambda n: -n["n_segments"])
    for i, n in enumerate(nets):
        n["net_id"] = f"net{i}"
    return nets


# ------------------------------------------------------- label binding
def bind_labels(nets: List[Dict[str, Any]],
                labels: Sequence[Dict[str, Any]],
                *, page_size: Optional[Tuple[float, float]] = None,
                max_dist: float = 12.0) -> List[Dict[str, Any]]:
    """
    Attach OCR labels to the net they physically sit on.

    `labels`: [{"text": str, "bbox": [x0,y0,x1,y1]}] in the SAME coordinate
    space as the segments (pass page_size to convert normalized boxes).
    A label binds to the net with the nearest ink within `max_dist` points.
    """
    for lb in labels:
        if not isinstance(lb, dict):    # provider returned a bare string —
            continue                    # skip, never crash the page
        bx = lb.get("bbox")
        if not bx or len(bx) != 4:
            continue
        if page_size and max(bx) <= 1.0:      # normalized -> points
            W, H = page_size
            bx = [bx[0] * W, bx[1] * H, bx[2] * W, bx[3] * H]
        cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
        best, best_d = None, float("inf")
        for n in nets:
            x0, y0, x1, y1 = n["bbox"]
            if cx < x0 - max_dist or cx > x1 + max_dist:
                continue
            if cy < y0 - max_dist or cy > y1 + max_dist:
                continue
            d = min(math.dist((cx, cy), p) for p in n["points"])
            if d < best_d:
                best, best_d = n, d
        if best is not None and best_d <= max_dist:
            best["labels"].append({"text": lb.get("text", ""),
                                   "dist": round(best_d, 2)})
    return nets


def net_of_label(nets: Sequence[Dict[str, Any]], text: str) -> Optional[Dict[str, Any]]:
    """The net carrying a given label (exact-ish match)."""
    t = (text or "").strip().lower()
    for n in nets:
        for lb in n["labels"]:
            if lb["text"].strip().lower() == t:
                return n
    return None


def trace_between(nets: Sequence[Dict[str, Any]], a: str, b: str) -> Optional[Dict[str, Any]]:
    """Are two labels on the SAME net (i.e. actually wired together)?"""
    na, nb = net_of_label(nets, a), net_of_label(nets, b)
    if not na or not nb:
        return {"connected": False, "reason": "label not bound to any net",
                "a_net": na["net_id"] if na else None,
                "b_net": nb["net_id"] if nb else None}
    return {"connected": na["net_id"] == nb["net_id"],
            "a_net": na["net_id"], "b_net": nb["net_id"]}


def classify_nets(nets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Separate CONDUCTORS from glyphs and symbols.

    On these sheets the label text is drawn as vector outlines, so a block of
    lettering becomes a dense net inside a tiny box — that is a GLYPH, not a
    wire. A conductor is long and thin; a device symbol is compact but not
    letter-sized. Classifying keeps the trace honest: only conductors carry
    connectivity.
    """
    for n in nets:
        x0, y0, x1, y1 = n["bbox"]
        w, h = x1 - x0, y1 - y0
        span = max(w, h)
        thin = min(w, h)
        segs = n["n_segments"]
        density = segs / max(span, 1.0)
        if span <= 14 and segs >= 20:
            kind = "glyph"          # lettering drawn as outlines
        elif span >= 25 and thin <= 6:
            kind = "conductor"      # long thin run = a wire/bus
        elif density >= 4 and span < 60:
            kind = "symbol"         # compact dense device symbol
        else:
            kind = "conductor"
        n["kind"] = kind
    return nets


def conductors(nets: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [n for n in nets if n.get("kind") == "conductor"]


def net_at_point(nets: Sequence[Dict[str, Any]], pt: Point,
                 *, max_dist: float = 6.0,
                 kinds: Sequence[str] = ("conductor",)) -> Optional[Dict[str, Any]]:
    """Which net's ink passes through/near this coordinate."""
    best, best_d = None, float("inf")
    for n in nets:
        if kinds and n.get("kind") not in kinds:
            continue
        x0, y0, x1, y1 = n["bbox"]
        if not (x0 - max_dist <= pt[0] <= x1 + max_dist and
                y0 - max_dist <= pt[1] <= y1 + max_dist):
            continue
        d = min(math.dist(pt, p) for p in n["points"])
        if d < best_d:
            best, best_d = n, d
    return best if best_d <= max_dist else None


def same_net(nets: Sequence[Dict[str, Any]], a: Point, b: Point,
             **kw) -> Dict[str, Any]:
    """THE finger-follow test: are two points galvanically joined by drawn ink?"""
    na, nb = net_at_point(nets, a, **kw), net_at_point(nets, b, **kw)
    return {"connected": bool(na and nb and na["net_id"] == nb["net_id"]),
            "a_net": na["net_id"] if na else None,
            "b_net": nb["net_id"] if nb else None}


def summarize(nets: Sequence[Dict[str, Any]], top: int = 10) -> str:
    out = [f"NETS: {len(nets)}"]
    for n in nets[:top]:
        labs = ", ".join(l["text"] for l in n["labels"][:8]) or "(no labels bound)"
        out.append(f"  {n['net_id']}: {n['n_segments']} segs · {labs}")
    return "\n".join(out)
