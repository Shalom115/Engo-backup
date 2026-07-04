"""
System prompt loader and context formatter.

Loads prompts/engo_system.md once at module import. Failing here fails fast
(import error) — that's the right behaviour: no prompt = no agent.

format_context() builds the <context> XML block we inject into the user
message. Location attributes adapt to the source type:
  - PDF chunks emit pages="X-Y"
  - XLSX chunks emit sheet="..." row="N"
  - DOCX chunks emit section="Section Title"
  - Sources lacking all of these emit none (no fallback).
Attributes that depend on optional metadata (sfi, category) are omitted
entirely when absent. Chunk text is XML-escaped.
"""
from __future__ import annotations

from typing import Any, Dict, List
from xml.sax.saxutils import escape, quoteattr

import config

_PROMPT_PATH = config.PROJECT_ROOT / "prompts" / "engo_system.md"

if not _PROMPT_PATH.exists():
    raise FileNotFoundError(
        f"System prompt missing: {_PROMPT_PATH}. Agent cannot start without it."
    )

SYSTEM_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8").strip()


def _attr(name: str, value: Any) -> str:
    """Render a single XML attribute, properly quoted."""
    return f"{name}={quoteattr(str(value))}"


def format_context(chunks: List[Dict[str, Any]]) -> str:
    """
    Format retrieved chunks as a <context> XML block.

    Each chunk becomes:
        <chunk source="..." pages="X-Y" distance="0.5450"
               [sfi="600 Electrical"] [category="Manual"]>
        <escaped chunk text>
        </chunk>

    Optional attributes (sfi, category) are emitted only when the chunk's
    metadata carries them.

    Empty input returns the explicit "no documents matched" block so the
    LLM can detect retrieval emptiness deterministically.
    """
    if not chunks:
        return (
            "<context>\n"
            "(No documents in the library matched this query.)\n"
            "</context>"
        )

    lines: List[str] = ["<context>"]
    for c in chunks:
        meta = c.get("metadata", {}) or {}
        attrs: List[str] = [
            _attr("source", meta.get("file_name", "unknown")),
        ]
        # Location attributes: branch on which fields the metadata carries.
        # PDF → pages="X-Y"; xlsx → sheet="..." row="N"; docx → section="..."; otherwise omit.
        page_start = meta.get("page_start")
        page_end = meta.get("page_end")
        sheet_name = meta.get("sheet_name")
        row_number = meta.get("row_number")
        section_title = meta.get("section_title")
        # vision chunks: page (PDF) or figure_index+section (DOCX), + a marker flag
        is_vision = meta.get("source_kind") == "vision"
        v_page = meta.get("page_number")
        v_fig = meta.get("figure_index")
        if is_vision and v_page is not None:
            attrs.append(_attr("page", v_page))
        elif is_vision and v_fig is not None:
            attrs.append(_attr("figure", v_fig))
            if meta.get("section_title"):
                attrs.append(_attr("section", meta["section_title"]))
        else:
            # Non-vision: a chunk may carry several locators at once — a
            # procedure-aware handover chunk has BOTH pages and a section
            # (the ONYX tab / procedure it belongs to). Emit each that exists.
            if page_start is not None and page_end is not None:
                attrs.append(_attr("pages", f"{page_start}-{page_end}"))
            if sheet_name and row_number is not None:
                attrs.append(_attr("sheet", sheet_name))
                attrs.append(_attr("row", row_number))
            if section_title:
                attrs.append(_attr("section", section_title))
        if is_vision:
            attrs.append(_attr("content", meta.get("content_type", "figure")))
            if meta.get("figure_label"):
                attrs.append(_attr("figure_label", meta["figure_label"]))
            if meta.get("image_path"):
                attrs.append(_attr("markable", "yes"))

        attrs.append(_attr("distance", f"{float(c.get('distance', 0.0)):.4f}"))

        sfi_label = meta.get("sfi_label")
        if sfi_label:
            attrs.append(_attr("sfi", sfi_label))
        category = meta.get("category")
        if category:
            attrs.append(_attr("category", category))
        # Authority tier (handover docs) — lets the agent apply the HANDOVER
        # NOTES AUTHORITY hierarchy in the system prompt to what it retrieves.
        authority = meta.get("authority")
        if authority:
            attrs.append(_attr("authority", authority))

        text = escape(str(c.get("text", "")))
        lines.append(f"<chunk {' '.join(attrs)}>")
        lines.append(text)
        lines.append("</chunk>")
    lines.append("</context>")
    return "\n".join(lines)
