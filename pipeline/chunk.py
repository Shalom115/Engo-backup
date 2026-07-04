"""
Token-aware chunking for page-based and section-based sources.

Two public entry points share the same low-level helpers:

  chunk_pages(pages, ...)         → for PDF-shaped input (page_number / text)
  chunk_sections(sections, ...)   → for DOCX-shaped input (section_index / section_title / text)

Strategy (shared):
  - Walk units in order, accumulating tokens.
  - Prefer breaking at unit boundaries: when adding the next unit would
    exceed chunk_size, emit the current accumulator as a chunk.
  - When a single unit exceeds chunk_size on its own, fall back to
    token-level splits via _split_long_text.
  - Overlap is applied between consecutive chunks (token-level) via
    _apply_overlap, copying source-specific position keys through.

Pages are typically small (100–500 tokens) and almost always fit a chunk
whole. Sections can be much larger (5,000+ tokens for a long heading
block) and frequently need mid-section splitting. Both cases go through
the same primitives — only the wrapper differs.

Token counting: tiktoken cl100k_base. Used as a sizing proxy — Voyage's
exact tokenization differs slightly but the gap is well inside our safety
margins.

Output per chunk (PDF):
    {text, page_start, page_end, chunk_index, token_count}

Output per chunk (DOCX):
    {text, section_index, section_title, chunk_index, token_count}
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

import tiktoken

logger = logging.getLogger(__name__)

_ENCODER = tiktoken.get_encoding("cl100k_base")


# ----- Shared low-level helpers -----

def _count_tokens(text: str) -> int:
    return len(_ENCODER.encode(text))


def _split_long_text(
    text: str,
    chunk_size: int,
    overlap: int,
) -> List[Dict[str, Any]]:
    """Split a single oversize text into chunk-sized pieces on token boundaries.

    Returns pieces of shape {"text": str, "token_count": int}. The caller
    attaches its own position metadata (page_start/page_end for PDF;
    section_index/section_title for DOCX) to each piece.

    Operates on token IDs to make sizing exact, decodes back for storage.
    """
    token_ids = _ENCODER.encode(text)
    pieces: List[Dict[str, Any]] = []
    step = max(1, chunk_size - overlap)
    start = 0
    while start < len(token_ids):
        end = min(start + chunk_size, len(token_ids))
        slice_ids = token_ids[start:end]
        piece_text = _ENCODER.decode(slice_ids)
        pieces.append({
            "text": piece_text,
            "token_count": len(slice_ids),
        })
        if end == len(token_ids):
            break
        start += step
    return pieces


def _apply_overlap(
    raw_chunks: List[Dict[str, Any]],
    overlap_tokens: int,
    position_keys: List[str],
) -> List[Dict[str, Any]]:
    """Apply token-level overlap between consecutive chunks.

    Overlap is taken from the tail of chunk N and prepended to chunk N+1.
    `position_keys` is the list of source-specific metadata keys to copy
    from each raw chunk through to the final chunk (e.g. ["page_start",
    "page_end"] for PDF, ["section_index", "section_title"] for DOCX).

    When overlap is zero or there are fewer than two chunks, no merging
    occurs — chunk_index is assigned in place and raw_chunks is returned
    as-is (same behaviour as the pre-refactor inline path).
    """
    if overlap_tokens == 0 or len(raw_chunks) < 2:
        for i, c in enumerate(raw_chunks):
            c["chunk_index"] = i
        return raw_chunks

    final: List[Dict[str, Any]] = []
    for i, c in enumerate(raw_chunks):
        if i == 0:
            text = str(c["text"])
            entry: Dict[str, Any] = {"text": text}
            for k in position_keys:
                entry[k] = c[k]
            entry["chunk_index"] = 0
            entry["token_count"] = _count_tokens(text)
            final.append(entry)
            continue
        prev_text = str(raw_chunks[i - 1]["text"])
        prev_ids = _ENCODER.encode(prev_text)
        tail_ids = prev_ids[-overlap_tokens:] if len(prev_ids) > overlap_tokens else prev_ids
        tail_text = _ENCODER.decode(tail_ids)
        merged_text = tail_text + "\n\n" + str(c["text"])
        entry = {"text": merged_text}
        for k in position_keys:
            entry[k] = c[k]
        entry["chunk_index"] = i
        entry["token_count"] = _count_tokens(merged_text)
        final.append(entry)
    return final


def _validate_sizes(chunk_size_tokens: int, overlap_tokens: int) -> None:
    if chunk_size_tokens <= 0:
        raise ValueError(f"chunk_size_tokens must be > 0, got {chunk_size_tokens}")
    if overlap_tokens < 0 or overlap_tokens >= chunk_size_tokens:
        raise ValueError(
            f"overlap_tokens must be in [0, chunk_size_tokens), "
            f"got overlap={overlap_tokens} chunk_size={chunk_size_tokens}"
        )


# ----- PDF page chunker -----

def chunk_pages(
    pages: List[Dict[str, Any]],
    chunk_size_tokens: int,
    overlap_tokens: int,
) -> List[Dict[str, Any]]:
    """
    Chunk a parsed PDF (list of page dicts) into token-bounded pieces.

    Args:
        pages: list of {"page_number": int, "text": str}, in order.
        chunk_size_tokens: max tokens per chunk.
        overlap_tokens: tokens of overlap between consecutive chunks.

    Returns:
        List of chunk dicts. Empty list if `pages` is empty.
    """
    if not pages:
        return []
    _validate_sizes(chunk_size_tokens, overlap_tokens)

    # First pass: page-aware accumulation.
    raw_chunks: List[Dict[str, Any]] = []
    buf_text_parts: List[str] = []
    buf_tokens = 0
    buf_page_start: int | None = None
    buf_page_end: int | None = None

    def flush() -> None:
        nonlocal buf_text_parts, buf_tokens, buf_page_start, buf_page_end
        if not buf_text_parts:
            return
        raw_chunks.append({
            "text": "\n\n".join(buf_text_parts),
            "page_start": buf_page_start,
            "page_end": buf_page_end,
            "token_count": buf_tokens,
        })
        buf_text_parts = []
        buf_tokens = 0
        buf_page_start = None
        buf_page_end = None

    for page in pages:
        page_no = int(page["page_number"])
        text = str(page["text"])
        page_tokens = _count_tokens(text)

        # Single page exceeds budget: flush, then split it standalone.
        if page_tokens > chunk_size_tokens:
            flush()
            for piece in _split_long_text(text, chunk_size_tokens, overlap_tokens):
                piece["page_start"] = page_no
                piece["page_end"] = page_no
                raw_chunks.append(piece)
            continue

        if buf_tokens + page_tokens > chunk_size_tokens and buf_text_parts:
            flush()

        buf_text_parts.append(text)
        buf_tokens += page_tokens
        if buf_page_start is None:
            buf_page_start = page_no
        buf_page_end = page_no

    flush()

    return _apply_overlap(raw_chunks, overlap_tokens, ["page_start", "page_end"])


# ----- DOCX section chunker -----

def chunk_sections(
    sections: List[Dict[str, Any]],
    chunk_size_tokens: int,
    overlap_tokens: int,
) -> List[Dict[str, Any]]:
    """
    Chunk a parsed DOCX (list of section dicts) into token-bounded pieces.

    Args:
        sections: list of {"section_index": int, "section_title": str, "text": str}.
        chunk_size_tokens: max tokens per chunk.
        overlap_tokens: tokens of overlap between consecutive chunks.

    Returns:
        List of chunk dicts: {text, section_index, section_title,
        chunk_index, token_count}. Empty list if `sections` is empty.

    Section-boundary preference: a section that fits inside the budget
    is emitted as one chunk. If it exceeds the budget, it is split via
    _split_long_text; every resulting piece carries the same
    section_index and section_title. Sections are NOT merged across
    boundaries — section identity is preserved per chunk so citations
    remain accurate.
    """
    if not sections:
        return []
    _validate_sizes(chunk_size_tokens, overlap_tokens)

    raw_chunks: List[Dict[str, Any]] = []
    for s in sections:
        idx = int(s["section_index"])
        title = str(s.get("section_title", ""))
        text = str(s["text"])
        if not text.strip():
            continue
        tokens = _count_tokens(text)
        if tokens > chunk_size_tokens:
            for piece in _split_long_text(text, chunk_size_tokens, overlap_tokens):
                piece["section_index"] = idx
                piece["section_title"] = title
                raw_chunks.append(piece)
        else:
            raw_chunks.append({
                "text": text,
                "section_index": idx,
                "section_title": title,
                "token_count": tokens,
            })

    return _apply_overlap(raw_chunks, overlap_tokens, ["section_index", "section_title"])


# ----- Procedure-aware PDF chunker -----

# A heading line is a numbered section header, NOT a procedure step.
#   "1.- ABBREVIATIONS"      top-level   (digits + ".-")
#   "2.1. ONYX DISPLAY"      sub-section (two+ numeric groups)
#   "• 2.1.1. FUEL"          ONYX tab    (bullet optional, three groups)
# A step like "1. Turn pumps OFF" is single-level with no ".-" → deliberately
# NOT matched, so numbered procedures stay inside their section, intact.
_PROC_HEADER = re.compile(r"^\s*(?:•\s*)?(?:\d+\.\-|\d+(?:\.\d+)+\.?)\s+[A-Za-z]")

# Recurring page furniture to drop so it doesn't pollute section text or get
# mistaken for content. Bare page numbers and the running title/doc-id band.
_NOISE = re.compile(r"^\s*(?:\d{1,4}|SWS\d+H-\d+|SY\s+Gelliceaux\b.*)\s*$", re.I)

# A header-shaped line that ends in "Page N" is a table-of-contents entry
# (dot-leader nav), NOT a real section — real headers never end that way.
_TOC_LINE = re.compile(r"Page\s+\d+\s*\.*\s*$", re.I)


def segment_numbered_sections(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Re-cut page-based PDF text into numbered sections, tracking page spans.

    Walks every line in page order. A line matching _PROC_HEADER opens a new
    section; everything until the next header is that section's body. Page
    furniture (_NOISE) is dropped. Content before the first header becomes an
    untitled preamble section so nothing is lost.

    Returns: [{section_index, section_title, text, page_start, page_end}].
    """
    sections: List[Dict[str, Any]] = []
    cur: Dict[str, Any] | None = None

    def open_section(title: str, page_no: int) -> Dict[str, Any]:
        return {"section_index": len(sections), "section_title": title.strip(),
                "_parts": [], "page_start": page_no, "page_end": page_no}

    for page in pages:
        page_no = int(page["page_number"])
        for raw_line in str(page["text"]).splitlines():
            line = raw_line.rstrip()
            if _NOISE.match(line) or _TOC_LINE.search(line):
                continue
            if _PROC_HEADER.match(line):
                if cur is not None:
                    sections.append(cur)
                cur = open_section(line, page_no)
            else:
                if cur is None:
                    cur = open_section("", page_no)
                if line.strip():
                    cur["_parts"].append(line)
                cur["page_end"] = page_no
    if cur is not None:
        sections.append(cur)

    out: List[Dict[str, Any]] = []
    for s in sections:
        body = "\n".join(s.pop("_parts"))
        # Prepend the header line itself so the section is self-describing.
        text = (s["section_title"] + "\n" + body).strip() if s["section_title"] else body.strip()
        if not text:
            continue
        s["text"] = text
        out.append(s)
    return out


def chunk_procedures(
    pages: List[Dict[str, Any]],
    chunk_size_tokens: int,
    overlap_tokens: int,
) -> List[Dict[str, Any]]:
    """
    Procedure-aware chunker for numbered-section PDFs (handover notes, SOPs).

    Segments on numbered headers, then emits ONE chunk per section so numbered
    procedures and reference tables stay intact. A section larger than
    chunk_size_tokens is split as a last resort (token-level, with overlap);
    sections are never merged across boundaries.

    Each chunk carries page_start/page_end (for [filename, p.X] citation) AND
    section_title (the procedure/tab it belongs to). Falls back to whole-doc
    page chunking only if no numbered headers are found at all.
    """
    if not pages:
        return []
    _validate_sizes(chunk_size_tokens, overlap_tokens)

    sections = segment_numbered_sections(pages)
    if not sections:
        return chunk_pages(pages, chunk_size_tokens, overlap_tokens)

    raw_chunks: List[Dict[str, Any]] = []
    for s in sections:
        text = s["text"]
        tokens = _count_tokens(text)
        if tokens > chunk_size_tokens:
            for piece in _split_long_text(text, chunk_size_tokens, overlap_tokens):
                piece["page_start"] = s["page_start"]
                piece["page_end"] = s["page_end"]
                piece["section_title"] = s["section_title"]
                raw_chunks.append(piece)
        else:
            raw_chunks.append({
                "text": text,
                "page_start": s["page_start"],
                "page_end": s["page_end"],
                "section_title": s["section_title"],
                "token_count": tokens,
            })

    # Keep procedures intact: no cross-section overlap. chunk_index assigned in place.
    return _apply_overlap(raw_chunks, 0, ["page_start", "page_end", "section_title"])
