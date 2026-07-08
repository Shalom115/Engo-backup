"""
LEGENDS-FIRST PROTOCOL — code enforcement (engineer-mandated 2026-07-06).

Implements steps 0-2 of the SHEET-READING SEQUENCE in
prompts/system_archetypes.md so the pipeline does them WITHOUT being told:

  0. inventory EVERY legend / reference table on the sheet
  1. read each one fully, verbatim, before any diagram symbol is classified
  2. hand the result to the extractors as a context block that is PREPENDED
     to their prompts, so component classification uses THIS sheet's own
     symbol/pipe/tag definitions instead of generic priors.

Why this exists (two real, documented failures, same root cause):
  - the bilge schematic's PIPE legend (main vs. aux bilge line colors) was
    never read -> pickups/valves were miscounted per zone;
  - the aircon schematic's PIPE legend (GAS supply/return) and BOM were
    never read together -> the system was mislabeled chilled-water and a
    phantom "engine-room AHU" was invented ("AIR HANDLER" in the BOM == the
    fancoil units, joinable only by model number).
Both were caught by the ENGINEER, not the pipeline. The old extract_sheet
survey even DETECTED legend regions and then skipped them. This module makes
skipping impossible: extractors auto-run it unless explicitly told not to.

Gold-blind and fleet-general: prompts describe legend/table STRUCTURE only —
no vessel tokens, no expected values.

Cost note (per the engineer's usage-economy rule): one inventory call plus
one tight-crop call per table found (typically 5-8 per system sheet). The
page is rasterized ONCE at table_dpi; the inventory pass reuses a downscale
of the same render, so no extra rasterization.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

from PIL import Image

# Our own trusted big-sheet renders (A0/A1 at 400 DPI) exceed PIL's default
# decompression-bomb threshold; same lift as the P&ID table reader.
Image.MAX_IMAGE_PIXELS = None

from providers.vision import get_vision_provider
from pipeline import visual_extract as vx

KINDS = [
    "symbols_legend",        # icon -> meaning
    "pipe_line_legend",      # line color/style -> service (the loop-tracing key)
    "text_tag_legend",       # tag/numbering format, abbreviations (NO/NC/LT/LS...)
    "bom_parts_table",       # bill of materials / parts list
    "equipment_data_table",  # pump data, fan data, compressor data, air handler data...
    "operating_modes_panel", # mode -> highlighted path / valve states
    "tank_connection_detail",
    "notes_block",
    "other_table",
]

_INVENTORY_PROMPT = (
    "This is a marine engineering drawing (schematic / P&ID / wiring / GA). "
    "Locate EVERY legend and reference table printed on the sheet - do not skip "
    "any. These typically include: a symbols legend, a pipe/line legend (line "
    "colors/styles and what each carries), a text/tag legend (tag formats, "
    "abbreviations like NO/NC/LT/LS), a bill of materials or parts table, "
    "equipment data tables (pump data, fan data, compressor data, etc.), "
    "operating-mode panels, tank-connection details, and notes blocks. "
    "For EACH one report: its title exactly as printed, its kind, and its "
    "bounding box in normalized coordinates [x0, y0, x1, y1] with (0,0) at the "
    "top-left of the sheet, drawn a little generously so the whole table is "
    "inside the box. Report only what is actually printed - if a kind is "
    "absent, do not invent it."
)

_INVENTORY_TOOL = {
    "name": "record_legend_inventory",
    "description": "Every legend/reference table found on the sheet.",
    "input_schema": {
        "type": "object",
        "properties": {
            "tables": {"type": "array", "items": {"type": "object", "properties": {
                "title_as_printed": {"type": "string"},
                "kind": {"type": "string", "enum": KINDS},
                "bbox": {"type": "array", "items": {"type": "number"},
                         "minItems": 4, "maxItems": 4},
            }, "required": ["kind", "bbox"]}},
            "notes": {"type": "string"},
        },
        "required": ["tables"],
    },
}

_READ_PROMPT = (
    "This is a cropped legend or reference table from a marine engineering "
    "drawing. Transcribe it VERBATIM and COMPLETELY: the title as printed, "
    "then every entry/row in order. For a symbols legend, one entry per "
    "symbol: {label: the printed meaning, symbol_description: what the icon "
    "looks like}. For a pipe/line legend, one entry per line type: {label: "
    "the printed service name, symbol_description: the line's color and "
    "style as drawn}. For a BOM/data table, one entry per row: {label: the "
    "row joined with ' | ' between cells}. Read ONLY what is printed; use "
    "'<illegible>' for anything unreadable; never guess or complete a row."
)

_READ_TOOL = {
    "name": "record_legend_content",
    "description": "Verbatim content of one legend/reference table.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "entries": {"type": "array", "items": {"type": "object", "properties": {
                "label": {"type": "string"},
                "symbol_description": {"type": "string"},
            }, "required": ["label"]}},
        },
        "required": ["entries"],
    },
}


def _crop(png_bytes: bytes, bbox: List[float], pad: float = 0.012) -> bytes:
    img = Image.open(io.BytesIO(png_bytes))
    W, H = img.size
    x0 = max(0, int((bbox[0] - pad) * W)); y0 = max(0, int((bbox[1] - pad) * H))
    x1 = min(W, int((bbox[2] + pad) * W)); y1 = min(H, int((bbox[3] + pad) * H))
    buf = io.BytesIO()
    img.crop((x0, y0, x1, y1)).save(buf, format="PNG")
    return buf.getvalue()


def read_all(page_png: bytes, *, kinds: Optional[List[str]] = None,
             vp=None) -> Dict[str, Any]:
    """
    Steps 0+1 on one full-page render: inventory every legend/table, then
    read each verbatim (tight crop from the SAME render). `kinds` narrows
    which get the content read (inventory always covers everything) - the
    default None reads ALL of them, per the protocol.
    Returns {"tables": [{title, kind, bbox, content}], "context_block": str}.
    """
    vp = vp or get_vision_provider()
    inv = vp.extract(page_png, "image/png", _INVENTORY_PROMPT, _INVENTORY_TOOL)
    tables = [t for t in inv.get("tables", []) if isinstance(t, dict) and t.get("bbox")]
    for t in tables:
        if kinds is not None and t.get("kind") not in kinds:
            t["content"] = None  # inventoried but not content-read this run
            continue
        try:
            t["content"] = vp.extract(_crop(page_png, t["bbox"]), "image/png",
                                      _READ_PROMPT, _READ_TOOL)
        except Exception as e:  # a failed table read is a finding, not a crash
            t["content"] = {"error": str(e)[:200]}
    return {"tables": tables, "inventory_notes": inv.get("notes", ""),
            "context_block": build_context_block(tables)}


def from_pdf(pdf_bytes: bytes, page_index: int = 0, *, dpi: int = 300,
             kinds: Optional[List[str]] = None, vp=None) -> Dict[str, Any]:
    """Convenience wrapper: rasterize once, then read_all."""
    page = vx.rasterize_pdf_page(pdf_bytes, page_index, dpi=dpi)
    return read_all(page, kinds=kinds, vp=vp)


_MAX_ENTRIES_PER_TABLE = 60  # keep the context block prompt-sized


def build_context_block(tables: List[Dict[str, Any]]) -> str:
    """
    Compact text block for PREPENDING to extraction prompts. The sheet's own
    definitions are stated as authoritative over any generic convention.
    """
    if not tables:
        return ""
    lines = ["THIS SHEET'S OWN LEGENDS AND TABLES (read first; these definitions are "
             "AUTHORITATIVE for this sheet and override any generic symbol/line "
             "convention):"]
    for t in tables:
        title = t.get("title_as_printed") or t.get("kind", "table")
        content = t.get("content")
        if not content or "error" in (content or {}):
            lines.append(f"- [{t.get('kind')}] {title}: (present on sheet; not read)")
            continue
        lines.append(f"- [{t.get('kind')}] {title}:")
        for e in (content.get("entries") or [])[:_MAX_ENTRIES_PER_TABLE]:
            if not isinstance(e, dict):
                continue
            lab = e.get("label", "")
            sym = e.get("symbol_description")
            lines.append(f"    * {lab}" + (f" -> {sym}" if sym else ""))
    return "\n".join(lines)


def with_context(legend_context: str, prompt: str) -> str:
    """Prepend a legend context block to an extraction prompt (no-op if empty)."""
    return f"{legend_context}\n\n{prompt}" if legend_context else prompt
