"""
OPERATING-MODES CHANNEL (engineer-mandated 2026-07-22).

Why: the bilge/fire P&ID composition scored 40-50% because it narrated only
the paths it happened to walk and invented the rest. The vessel ships an
OPERATING-MODES companion document per fluid system ("<System> Operating
Modes"), filed alongside the system schematics, which states the real lineups
(fire mode / bilge mode / sprinkler / emergency suction ...). That document is
the AUTHORITY for the scenario set.

General rule (transfers to any vessel): for a fluid-system sheet, look for a
sibling document whose name matches "<system words> operating modes"; if one
exists, read it and hand its modes to composition as the authoritative
scenario list. If none exists (many vessels), composition falls back to the
walked topology alone — no invention either way.

The docs are image-only on this vessel, so they are read with vision.
"""

from __future__ import annotations

import io
import json
import re
from typing import Any, Dict, List, Optional

import config

_MODES_PROMPT = (
    "This is a vessel OPERATING MODES document for a fluid system. List EVERY "
    "operating mode / lineup it describes, verbatim in substance: the mode "
    "name, which pump(s) run, the suction source, the discharge destination, "
    "and any valve positions the mode requires. Read only what the document "
    "states; '<UNKNOWN>' for illegible. Do not invent modes."
)
_MODES_TOOL = {
    "name": "record_operating_modes",
    "description": "Operating modes / lineups stated by the document.",
    "input_schema": {
        "type": "object",
        "properties": {
            "system": {"type": "string"},
            "modes": {"type": "array", "items": {"type": "object", "properties": {
                "mode_name": {"type": "string"},
                "pumps": {"type": "string"},
                "suction_from": {"type": "string"},
                "discharge_to": {"type": "string"},
                "valve_positions": {"type": "string"},
                "notes": {"type": "string"}},
                "required": ["mode_name"]}},
        },
        "required": ["modes"],
    },
}

_CACHE = config.STATE_DIR / "operating_modes_cache.json"


def _norm(s: str) -> set:
    return {w for w in re.split(r"[^a-z0-9]+", (s or "").lower())
            if len(w) > 2 and w not in {"system", "schematic", "and", "the", "pdf"}}


def find_modes_doc(sheet_name: str,
                   structure: Optional[List[Dict[str, Any]]] = None
                   ) -> Optional[Dict[str, str]]:
    """Find the '<system> Operating Modes' doc matching a P&ID sheet name.
    Matches on shared system words — general, not a hardcoded table."""
    if structure is None:
        s = json.loads((config.STATE_DIR /
                        f"structure_{config.VESSEL_NAMESPACE}.json").read_text())
        structure = s.get("nodes", s if isinstance(s, list) else [])
    want = _norm(sheet_name)
    best, best_score = None, 0
    for n in structure:
        name = n.get("name") or ""
        if "operating mode" not in name.lower():
            continue
        score = len(want & _norm(name))
        if score > best_score:
            best, best_score = n, score
    if best and best_score >= 1:
        return {"id": best["id"], "name": best["name"]}
    return None


def read_modes(doc_id: str, doc_name: str = "") -> Optional[Dict[str, Any]]:
    """Vision-read an operating-modes doc (they are image-only here). Cached."""
    cache = json.loads(_CACHE.read_text()) if _CACHE.exists() else {}
    if doc_id in cache:
        return cache[doc_id]
    from tests.vision_bench import _load_sheet_bytes
    from providers.vision import get_vision_provider
    import pypdfium2 as pdfium
    pdf = _load_sheet_bytes({"name": doc_name or doc_id, "drive_file_id": doc_id})
    pil = pdfium.PdfDocument(pdf)[0].render(scale=200 / 72).to_pil()
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    vp = get_vision_provider("plumbed_diagram")
    res = vp.extract(buf.getvalue(), "image/png", _MODES_PROMPT, _MODES_TOOL,
                     max_tokens=8192)
    if res:
        res["_doc_name"] = doc_name
        cache[doc_id] = res
        _CACHE.write_text(json.dumps(cache, indent=1))
    return res


def modes_digest(sheet_name: str) -> str:
    """Prompt block: the authoritative lineup set for this system, or a clear
    'none exists' so composition does not invent one."""
    doc = find_modes_doc(sheet_name)
    if not doc:
        return ("(no operating-modes document found for this system — compose "
                "scenarios from the walked topology ONLY; do not invent modes)")
    try:
        res = read_modes(doc["id"], doc["name"])
    except Exception as e:  # never kill a composition over the companion doc
        return f"(operating-modes doc '{doc['name']}' found but unreadable: {e})"
    modes = (res or {}).get("modes") or []
    if not modes:
        return f"(operating-modes doc '{doc['name']}' found but no modes read)"
    out = [f"AUTHORITATIVE OPERATING MODES — from '{doc['name']}'. These are the "
           f"real lineups of this system: compose ONE flow scenario per mode, "
           f"and reconcile them with the walked topology (a mode the drawing "
           f"cannot support = flag it, never drop it silently):"]
    for m in modes:
        bits = [f"MODE: {m.get('mode_name','?')}"]
        for k, lbl in (("pumps", "pump(s)"), ("suction_from", "suction from"),
                       ("discharge_to", "discharge to"),
                       ("valve_positions", "valves"), ("notes", "notes")):
            if m.get(k):
                bits.append(f"{lbl}: {m[k]}")
        out.append("  " + " · ".join(bits))
    return "\n".join(out)
