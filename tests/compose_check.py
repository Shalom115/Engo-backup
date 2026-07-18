"""
Composition-pass check runner: reuse existing bench extractions (no new
extraction cost), render the sheet, run pipeline.compose, save the result.

Usage:
  python3.12 -m tests.compose_check --plumbing          # AFT_blockB only
  python3.12 -m tests.compose_check --all               # 1 sheet per category
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import config
from pipeline.compose import compose

BENCH_DIR = config.STATE_DIR / "vision_bench"
OUT_DIR = BENCH_DIR / "composition"

# category -> (drawing_class, sheet name, extraction json path relative to BENCH_DIR)
PICKS = {
    "1-hydraulic-manifold": ("hydraulic", "AFT_blockB",
                             "disposition/AFT_blockB/anthropic.json"),
    "2-electrical-distribution-schedule": ("electrical", "GM-111_24V-DC-distribution",
                             "2-electrical-distribution-schedule/GM-111_24V-DC-distribution/anthropic.json"),
    "3-electrical-one-line": ("electrical", "GM-110a_24V-service-supply",
                             "3-electrical-one-line/GM-110a_24V-service-supply/anthropic.json"),
    "4-electrical-relay-terminal-wiring": ("electrical", "GM-114a_bilge-system",
                             "4-electrical-relay-terminal-wiring/GM-114a_bilge-system/anthropic.json"),
    "5-pid-plumbed": ("pid", "bilge-and-fire-schematic",
                             "5-pid-plumbed/bilge-and-fire-schematic/anthropic.json"),
    "6-plc-io": ("plc", "AFT-PLC-rev4-p21",
                             "6-plc-io/AFT-PLC-rev4-p21/anthropic.json"),
    "7-building-ga": ("building_ga", "steering-system-ga",
                             "7-building-ga/steering-system-ga/anthropic.json"),
    "8-bae-interconnect-pinout": ("interconnect", "bae-block-interconnect-p12",
                             "8-bae-interconnect-pinout/bae-block-interconnect-p12/anthropic.json"),
    "9-class-c-garbled-font": ("electrical", "termodinamica-wiring-rev0",
                             "9-class-c-garbled-font/termodinamica-wiring-rev0/anthropic.json"),
    "10-photos-figures": ("photos", "harken-spares-photo-3325",
                             "10-photos-figures/harken-spares-photo-3325/anthropic.json"),
}


def _sheet_png(name: str) -> bytes:
    """Whole-sheet PNG at 200 DPI from cache or the bench manifest source."""
    import io
    manifest = json.loads((Path(__file__).parent / "vision_bench_manifest.json").read_text())
    page = 0
    entry: Optional[Dict[str, Any]] = None
    for cat in manifest["categories"]:
        for sh in cat["sheets"]:
            if sh["name"] == name:
                entry = sh
                page = sh.get("page", 0)
    from tests.vision_bench import _load_sheet_bytes
    if entry is None:
        entry = {"name": name}
    data = _load_sheet_bytes(entry)
    if data[:4] != b"%PDF":       # already an image (photos category)
        return data
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(data)
    pil = doc[page].render(scale=200 / 72).to_pil()
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue()


def run_one(category: str) -> None:
    drawing_class, sheet, ext_rel = PICKS[category]
    ext_path = BENCH_DIR / ext_rel
    payload = json.loads(ext_path.read_text())
    extraction = payload.get("extraction", payload)   # disposition files nest it
    out_path = OUT_DIR / category / f"{sheet}.json"
    if out_path.exists():
        print(f"done already: {category}/{sheet}", file=sys.stderr)
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    png = _sheet_png(sheet)
    result = compose(png, extraction, drawing_class)
    out_path.write_text(json.dumps({
        "category": category, "sheet": sheet, "drawing_class": drawing_class,
        "composition": result, "elapsed_s": round(time.time() - t0, 1),
    }, indent=1))
    n_groups = len((result or {}).get("equipment_groups", []))
    print(f"ok    {category}/{sheet} [{drawing_class}] "
          f"{time.time()-t0:.1f}s — {n_groups} equipment groups")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--plumbing", action="store_true",
                   help="AFT_blockB only (the engineer's worked example)")
    p.add_argument("--all", action="store_true")
    a = p.parse_args()
    if a.plumbing:
        run_one("1-hydraulic-manifold")
        return
    if a.all:
        for cat in PICKS:
            try:
                run_one(cat)
            except Exception as e:
                print(f"ERROR {cat}: {type(e).__name__}: {e}")
        return
    p.error("pass --plumbing or --all")


if __name__ == "__main__":
    main()
