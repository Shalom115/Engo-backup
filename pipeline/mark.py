"""
Mark the component an engineer asks about, ON the drawing.

query → best vision chunk → load its kept original image → highlight the matching
component's bounding box. The whole point of the locate layer: Engo doesn't just
answer, it points.

Confidence is visible, per the engineer mandate (a confidently-wrong marker mid-
repair is worse than none):
  - high / medium  → solid translucent highlight
  - low            → DASHED outline + "(low confidence)" tag
  - no bbox        → not drawn; the component's position note is reported instead

Highlight (rectangle) over circle: cheaper to draw, reads clearer on dense sheets.

CLI:
    python -m pipeline.mark "BEL sync reference wiring"
    python -m pipeline.mark "where is fuse F3P on the HVPDU" --out /tmp/m.png
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import config
from pipeline.retrieve import search

_CONF_COLOR = {"high": (40, 170, 90), "medium": (217, 131, 36), "low": (192, 57, 43)}


def _match_component(query: str, components: List[Dict[str, Any]]):
    """Best component by overlap of query terms with the component label + note."""
    qterms = {w for w in query.lower().replace("?", " ").split() if len(w) >= 2}
    best, best_score = None, 0
    for c in components:
        hay = (str(c.get("label", "")) + " " + str(c.get("note", ""))).lower()
        score = sum(1 for t in qterms if t in hay)
        if score > best_score:
            best, best_score = c, score
    return best, best_score


def _dashed_rect(draw, box, color, width=4, dash=16, gap=10):
    x0, y0, x1, y1 = box
    x = x0
    while x < x1:
        draw.line([(x, y0), (min(x + dash, x1), y0)], fill=color, width=width)
        draw.line([(x, y1), (min(x + dash, x1), y1)], fill=color, width=width)
        x += dash + gap
    y = y0
    while y < y1:
        draw.line([(x0, y), (x0, min(y + dash, y1))], fill=color, width=width)
        draw.line([(x1, y), (x1, min(y + dash, y1))], fill=color, width=width)
        y += dash + gap


def _font(size=20):
    from PIL import ImageFont
    for path in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                 "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def mark(query: str, out: Optional[str] = None, k: int = 8) -> Optional[Dict[str, Any]]:
    results = search(query, k=k, filters={"source_kind": "vision"})
    if not results:
        print(f"No vision chunk found for: {query!r}")
        return None
    top = results[0]
    m = top["metadata"]
    img_path = m.get("image_path")
    if not img_path or not Path(img_path).exists():
        print(f"Top vision chunk has no stored image ({m.get('file_name')}).")
        return None

    components = json.loads(m.get("vision_components") or "[]")
    target, score = _match_component(query, components)
    to_draw = [target] if (target and score > 0) else components

    from PIL import Image, ImageDraw
    img = Image.open(img_path).convert("RGBA")
    W, H = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _font()

    drew, unplaced = 0, []
    for c in to_draw:
        if not c:
            continue
        bbox, conf = c.get("bbox"), c.get("confidence", "low")
        color = _CONF_COLOR.get(conf, _CONF_COLOR["low"])
        if not bbox:
            unplaced.append(c)
            continue
        box = [bbox[0] * W, bbox[1] * H, bbox[2] * W, bbox[3] * H]
        tag = c["label"] + (" (low confidence)" if conf == "low" else "")
        if conf == "low":
            _dashed_rect(draw, box, color + (255,), width=4)
        else:
            draw.rectangle(box, fill=color + (55,), outline=color + (255,), width=4)
        ty = max(0, box[1] - 22)
        draw.rectangle([box[0], ty, box[0] + 11 * len(tag), ty + 20], fill=(255, 255, 255, 210))
        draw.text((box[0] + 2, ty), tag, fill=color + (255,), font=font)
        drew += 1

    composite = Image.alpha_composite(img, overlay).convert("RGB")
    out_path = Path(out) if out else (
        config.DATA_DIR / "images" / "marked" / f"mark_{Path(img_path).stem}.png")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    composite.save(out_path)

    loc = m.get("page_number") or m.get("figure_index")
    loc_s = f"p.{m['page_number']}" if m.get("page_number") else \
        (f"figure {m['figure_index']}" if m.get("figure_index") else "")
    print(f"Source : {m.get('file_name')}  {loc_s}  [{m.get('content_type')}]")
    print(f"Marked : {drew} component(s)  (target: "
          f"{target['label'] if target and score > 0 else 'all components'})")
    for c in unplaced:
        print(f"  ~ '{c['label']}' found but not placeable — {c.get('note','no position')}")
    print(f"Saved  : {out_path}")
    return {"image": str(out_path), "source": m.get("file_name"), "loc": loc_s,
            "marked": drew, "unplaced": [c["label"] for c in unplaced]}


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.mark")
    ap.add_argument("query")
    ap.add_argument("--out", default=None)
    ap.add_argument("-k", type=int, default=8)
    args = ap.parse_args(argv)
    return 0 if mark(args.query, out=args.out, k=args.k) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
