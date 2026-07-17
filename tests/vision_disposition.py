"""
Disposition bench (engineer-designed test, 2026-07-17): reading vs UNDERSTANDING.

For one sheet, each provider (a) extracts via the normal gold-blind hydraulic
protocol, then (b) receives the whole-sheet image + ITS OWN extraction + the
vessel's Register node index, and must disposition EVERY piece of information:
relevant / irrelevant / uncertain — and for relevant items, WHICH register node
it belongs on and as what kind of fact. No placement rules are taught: the
point is to reveal each model's own placement judgment. All three get byte-
identical instructions and the same node index — fair by construction.

The backbone's dry-run routing runs alongside as the reference yardstick.

Usage:  python3.12 -m tests.vision_disposition --sheet AFT_blockB \
            --drive-id 1_5jkC_q8DzgLGMEUBe2Qi90kzWQLoR1H \
            --providers anthropic,gemini,openai
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import config

BENCH_DIR = config.STATE_DIR / "vision_bench"
SHEETS_DIR = BENCH_DIR / "sheets"

_DISPOSITION_PROMPT = """\
You previously extracted the JSON below from the attached hydraulic schematic
(whole sheet shown). The vessel's equipment register index follows — each line
is `node_id — name/description`.

For EVERY piece of information in your extraction — every function slice, every
cartridge and setting, every table row, the header, every note — output one
disposition item:
- relevance: "relevant" (belongs in the vessel's equipment knowledge base),
  "irrelevant" (say why in a few words), or "uncertain".
- For relevant items: target_node_id — the ONE register node this information
  should be stored on, chosen from the index. If no node fits, OMIT
  target_node_id and say "no fitting node — new equipment" in reason.
  Also give fact_kind — a short name for what kind of fact this is on that node.
- Never invent node ids. Do not skip items.

YOUR EXTRACTION:
{extraction}

REGISTER INDEX:
{index}
"""

_DISPOSITION_SCHEMA = {
    "name": "record_dispositions",
    "description": "Record the relevance and intended storage node for every "
                   "piece of extracted information.",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "information": {"type": "string"},
                        "relevance": {"type": "string",
                                      "enum": ["relevant", "irrelevant", "uncertain"]},
                        "reason": {"type": "string"},
                        "target_node_id": {"type": "string"},
                        "fact_kind": {"type": "string"},
                    },
                    "required": ["information", "relevance", "reason"],
                },
            }
        },
        "required": ["items"],
    },
}


def _register_index() -> str:
    reg = json.loads((config.STATE_DIR / "register_gelliceaux_001.json").read_text())
    lines = []
    for e in reg["entries"]:
        if e.get("retired"):
            continue
        bits = [e.get("name") or ""]
        if e.get("make"):
            bits.append(e["make"])
        if e.get("model"):
            bits.append(e["model"])
        if e.get("subsystem_label"):
            bits.append(f"({e['subsystem_label']})")
        lines.append(f"{e['equipment_id']} — {' '.join(b for b in bits if b)}")
    return "\n".join(lines)


def _whole_sheet_png(pdf: bytes, page: int, dpi: int = 200) -> bytes:
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf)
    pil = doc[page].render(scale=dpi / 72).to_pil()
    import io
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue()


def run(sheet_name: str, drive_id: str, page: int, providers: List[str]) -> None:
    from tests.vision_bench import _force_provider, _run_hydraulic, _route_hydraulic
    from providers.vision import get_vision_provider

    SHEETS_DIR.mkdir(parents=True, exist_ok=True)
    cache = SHEETS_DIR / f"{sheet_name}.pdf"
    if cache.exists():
        pdf = cache.read_bytes()
        print(f"sheet from cache: {cache}", file=sys.stderr)
    else:
        from tests.vision_bench import _load_sheet_bytes
        pdf = _load_sheet_bytes({"name": sheet_name, "drive_file_id": drive_id})
        cache.write_bytes(pdf)
        print(f"downloaded {len(pdf)} bytes -> {cache}", file=sys.stderr)

    png = _whole_sheet_png(pdf, page)
    index = _register_index()
    out_dir = BENCH_DIR / "disposition" / sheet_name
    out_dir.mkdir(parents=True, exist_ok=True)
    sheet_ref = {"name": sheet_name, "drive_file_id": drive_id}

    for vendor in providers:
        out_path = out_dir / f"{vendor}.json"
        if out_path.exists():
            print(f"done already: {vendor}", file=sys.stderr)
            continue
        t0 = time.time()
        _force_provider(vendor)
        print(f"[{vendor}] extraction…", file=sys.stderr)
        extraction = _run_hydraulic(pdf, page)
        extraction["_node_routing"] = _route_hydraulic(extraction, sheet_ref)

        print(f"[{vendor}] disposition pass…", file=sys.stderr)
        # strip routing from what the model sees — placement must be ITS judgment
        ext_for_model = {k: v for k, v in extraction.items()
                         if k not in ("_node_routing", "model", "passes")}
        prompt = _DISPOSITION_PROMPT.format(
            extraction=json.dumps(ext_for_model, indent=1)[:60000],
            index=index)
        vp = get_vision_provider("hydraulic_schematic")
        dispo = vp.extract(png, "image/png", prompt, _DISPOSITION_SCHEMA,
                           max_tokens=16384)

        out_path.write_text(json.dumps({
            "sheet": sheet_name, "provider": vendor,
            "extraction": extraction,
            "disposition": dispo,
            "elapsed_s": round(time.time() - t0, 1),
        }, indent=1))
        n = len((dispo or {}).get("items", []))
        print(f"ok    {sheet_name} [{vendor}] {time.time()-t0:.1f}s — "
              f"{n} disposition items")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sheet", required=True)
    p.add_argument("--drive-id", required=True)
    p.add_argument("--page", type=int, default=0)
    p.add_argument("--providers", default="anthropic,gemini,openai")
    a = p.parse_args()
    run(a.sheet, a.drive_id, a.page, [v.strip() for v in a.providers.split(",")])


if __name__ == "__main__":
    main()
