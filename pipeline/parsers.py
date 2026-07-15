"""
PDF and XLSX parsing.

PDF: page-by-page streaming, light whitespace normalization, single open.
XLSX: one chunk per non-empty data row, "Header: value" lines.

Both return a dict with a total count and a list of usable units:
  parse_pdf  → {"total_pages": int,
                "pages": [{"page_number": int, "text": str}]}
  parse_xlsx → {"total_rows": int, "total_sheets": int,
                "rows": [{"row_number": int, "sheet_name": str,
                          "text": str, "token_count": int}]}

PDF: image-only PDFs return {"total_pages": N, "pages": []}. Per-page
extraction errors log a warning and skip; the parser keeps going. PDF is
opened exactly once. Light whitespace normalization — do not over-clean.

XLSX: row 1 of each sheet is the header. Cells with None or empty/whitespace
values are skipped (no "Header: " lines emitted). Rows where every value
is empty are skipped entirely. Multi-sheet workbooks: each sheet processed
independently; row numbers reset per sheet (1-indexed; data starts at row 2).
Date/datetime/float coercion is sensible: dates as ISO, integer-valued
floats as ints.

New parser types can register themselves in PARSER_REGISTRY at the bottom
of this module — ingest dispatches through that, not hardcoded if/else.

DOCX: walks the document body XML directly so paragraphs and tables stay
interleaved as they appear in the file. Sections are formed by Heading or
Title style breaks. Tables are rendered inline ("cell | cell" rows joined
by newlines) within their section. Inline images are dropped and counted;
content inside text boxes and footnotes is NOT captured (v1 gap, flagged
for later).
"""
from __future__ import annotations

import datetime as _dt
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

from openpyxl import load_workbook
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.table import Table

from pipeline.tokens import get_encoder


def count_tokens_raw(text):
    """Encode via the shared lazy cl100k_base encoder (offline-safe load)."""
    return get_encoder().encode(text)

logger = logging.getLogger(__name__)

# ----- PDF parsing -----

# Collapse runs of horizontal whitespace (spaces, tabs) — not newlines.
_HSPACE_RUN = re.compile(r"[ \t\f\v]+")
# Collapse 3+ consecutive newlines down to a paragraph break (2 newlines).
_VSPACE_RUN = re.compile(r"\n{3,}")


def _normalize(text: str) -> str:
    """Light cleanup. Preserves single newlines and double-newline paragraph breaks."""
    if not text:
        return ""
    # Normalize line endings.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse horizontal whitespace runs to a single space, line-by-line.
    lines = [_HSPACE_RUN.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    # Collapse 3+ newlines to 2 (paragraph break).
    text = _VSPACE_RUN.sub("\n\n", text)
    return text.strip()


def parse_pdf(path: Path) -> Dict[str, Any]:
    """
    Parse a PDF page-by-page. Opens the file exactly once.

    Returns:
        {"total_pages": int, "pages": [{"page_number": int, "text": str}, ...]}.
        `pages` contains only pages that yielded extractable text, in order.
        `total_pages` is the PDF's full page count regardless of extraction.

    Raises:
        FileNotFoundError: file does not exist.
        PdfReadError: file exists but is not a readable PDF.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    try:
        reader = PdfReader(str(path))
    except PdfReadError:
        logger.error("pypdf could not open %s", path)
        raise

    total_pages = len(reader.pages)
    pages: List[Dict[str, Any]] = []

    for idx in range(total_pages):
        page_no = idx + 1
        try:
            raw = reader.pages[idx].extract_text() or ""
        except Exception as e:  # pypdf raises various subclasses; keep going on per-page failures
            logger.warning("Page %d/%d of %s failed to extract: %s",
                           page_no, total_pages, path.name, e)
            continue

        cleaned = _normalize(raw)
        if not cleaned:
            logger.warning("Page %d/%d of %s yielded no text (image-only or empty)",
                           page_no, total_pages, path.name)
            continue

        pages.append({"page_number": page_no, "text": cleaned})

    return {"total_pages": total_pages, "pages": pages}


# ----- XLSX parsing -----

def _format_cell(value: Any) -> str:
    """Coerce a cell value to a string suitable for inline text.
    Returns "" for None or whitespace-only strings."""
    if value is None:
        return ""
    if isinstance(value, bool):  # must come before int/float — bool is an int subclass
        return "True" if value else "False"
    if isinstance(value, _dt.datetime):
        # Date-only datetime: drop "00:00:00" noise.
        if value.hour == 0 and value.minute == 0 and value.second == 0 and value.microsecond == 0:
            return value.date().isoformat()
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, _dt.date):
        return value.isoformat()
    if isinstance(value, float):
        # Avoid "3.0" for integer-valued floats.
        if value.is_integer():
            return str(int(value))
        return str(value)
    return str(value).strip()


def parse_xlsx(path: Path) -> Dict[str, Any]:
    """
    Parse an .xlsx workbook into one chunk per non-empty data row.

    Strategy:
      - Open with data_only=True (formulas resolved to cached values).
      - Open with read_only=True (memory-efficient streaming).
      - Header row = first row with >=2 non-empty cells (leading blank/title
        rows are skipped). Empty header cells within it are skipped.
      - For each data row below the header:
        - Skip if all values empty/None.
        - Build text as "Header: value" per non-empty cell, one line each.

    Returns:
        {
          "total_rows": int,    # data rows scanned across all sheets (header excluded)
          "total_sheets": int,  # workbook sheet count
          "rows": [
            {"row_number": int, "sheet_name": str,
             "text": str, "token_count": int},
          ],
        }

    Raises:
        FileNotFoundError: file does not exist.
        Exception: openpyxl raises if file is not a valid xlsx.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"XLSX not found: {path}")

    wb = load_workbook(filename=str(path), data_only=True, read_only=True)
    rows_out: List[Dict[str, Any]] = []
    total_rows = 0
    total_sheets = len(wb.sheetnames)

    try:
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows_iter = ws.iter_rows(values_only=True)

            # Find the header row: the first row with >=2 non-empty cells within
            # the first HEADER_SCAN_LIMIT rows. This skips leading blank rows and
            # single-cell title rows (a real header is multi-column). Files whose
            # header sits on row 1 are unaffected.
            HEADER_SCAN_LIMIT = 10
            headers: list[tuple[int, str]] = []
            header_row_num = 0
            for idx, row in enumerate(rows_iter, start=1):
                candidate: list[tuple[int, str]] = []
                for col_idx, h in enumerate(row):
                    if h is None:
                        continue
                    h_str = str(h).strip()
                    if h_str:
                        candidate.append((col_idx, h_str))
                if len(candidate) >= 2:
                    headers = candidate
                    header_row_num = idx
                    break
                if idx >= HEADER_SCAN_LIMIT:
                    break

            if not headers:
                logger.warning("Sheet %r in %s: no header row (>=2 cells) found "
                               "in first %d rows.", sheet_name, path.name, HEADER_SCAN_LIMIT)
                continue

            for row_idx, row in enumerate(rows_iter, start=header_row_num + 1):
                total_rows += 1
                lines: List[str] = []
                for col_idx, header in headers:
                    if col_idx >= len(row):
                        continue
                    cell_str = _format_cell(row[col_idx])
                    if not cell_str:
                        continue
                    lines.append(f"{header}: {cell_str}")
                if not lines:
                    continue
                text = "\n".join(lines)
                rows_out.append({
                    "row_number": row_idx,
                    "sheet_name": sheet_name,
                    "text": text,
                    "token_count": len(count_tokens_raw(text)),
                })
    finally:
        wb.close()

    return {
        "total_rows": total_rows,
        "total_sheets": total_sheets,
        "rows": rows_out,
    }


# ----- DOCX parsing -----

def parse_docx(path: Path) -> Dict[str, Any]:
    """
    Parse a .docx into ordered sections by walking the body XML directly
    (doc.paragraphs and doc.tables are separate lists that lose
    interleaving — must walk body and dispatch on tag).

    Section logic:
      - A paragraph whose style name starts with "Heading" or equals
        "Title" starts a new section. Heading text becomes section_title;
        the heading paragraph itself is NOT included in the body text.
      - Content before the first heading lands in an untitled preamble
        (section_title="").
      - Documents with no headings collapse to a single preamble section.

    Tables: rendered inside the current section. Cells joined by " | ",
    rows by "\n". Merged cells are de-duplicated (python-docx returns
    the same cell once per grid position). Multi-paragraph cells joined
    by space inside the cell.

    Images: dropped. Total inline image count (drawing + pict elements)
    is logged and returned so the ingestion summary can report what the
    future vision pipeline will eventually pick up.

    Known v1 limitations (graceful — do not crash):
      - Heading detection is style-name based ("Heading*" / "Title").
        Custom or localized style names collapse the doc to a single
        preamble section. Diagnose by reading total_sections post-ingest.
      - Text boxes and footnotes are NOT captured (they live outside
        the paragraph stream).

    Returns:
        {
          "total_sections": int,
          "total_images_skipped": int,
          "sections": [
            {"section_index": int, "section_title": str, "text": str},
          ],
        }

    Raises:
        FileNotFoundError: file does not exist.
        Exception: python-docx raises on invalid docx.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"DOCX not found: {path}")

    doc = Document(str(path))

    P_TAG = qn("w:p")
    TBL_TAG = qn("w:tbl")
    DRAWING_TAG = qn("w:drawing")
    PICT_TAG = qn("w:pict")

    sections: List[Dict[str, Any]] = []
    current_title = ""
    current_parts: List[str] = []
    image_count = 0

    def flush() -> None:
        nonlocal current_parts
        text = "\n\n".join(p for p in current_parts if p.strip())
        if text.strip():
            sections.append({
                "section_index": len(sections),
                "section_title": current_title,
                "text": text,
            })
        current_parts = []

    for child in doc.element.body.iterchildren():
        tag = child.tag
        if tag == P_TAG:
            # Count images regardless of whether the paragraph has text.
            image_count += sum(1 for _ in child.iter(DRAWING_TAG))
            image_count += sum(1 for _ in child.iter(PICT_TAG))

            para = Paragraph(child, doc)
            style_name = ""
            if para.style is not None and para.style.name:
                style_name = para.style.name
            text = (para.text or "").strip()

            if style_name.startswith("Heading") or style_name == "Title":
                flush()
                current_title = text  # may be "" if heading paragraph is empty
            elif text:
                current_parts.append(text)
        elif tag == TBL_TAG:
            table = Table(child, doc)
            row_lines: List[str] = []
            for row in table.rows:
                cell_texts: List[str] = []
                seen_cells: set = set()
                for cell in row.cells:
                    # Merged cells repeat in row.cells — dedup by underlying tc element.
                    cell_id = id(cell._tc)
                    if cell_id in seen_cells:
                        continue
                    seen_cells.add(cell_id)
                    cell_paras = [
                        p.text.strip()
                        for p in cell.paragraphs
                        if p.text and p.text.strip()
                    ]
                    cell_texts.append(" ".join(cell_paras))
                row_lines.append(" | ".join(cell_texts))
            table_text = "\n".join(row_lines).strip()
            if table_text:
                current_parts.append(table_text)
        # Other elements (sectPr, sdt, etc.) silently skipped.

    flush()

    logger.info(
        "Parsed %s: %d sections, dropped %d inline images "
        "(vision pipeline picks these up later).",
        path.name, len(sections), image_count,
    )

    return {
        "total_sections": len(sections),
        "total_images_skipped": image_count,
        "sections": sections,
    }


# ----- Parser registry -----
# Dispatch table for pipeline/ingest.py. Add new file types here, not via
# more if/else branches in ingest.py.
#
# "needs_chunking" semantics:
#   True  → parser yields a chunkable unit list (pages or sections) that
#           must run through the appropriate chunker before embedding.
#           ingest.py maps suffix → chunker via its CHUNKERS table.
#   False → parser yields a "rows" list where each row IS already a chunk
#           (one row → one embedding). Used for tabular sources.
#
# Keep ingest.py's branching tight — extend this dict and the CHUNKERS
# table over there, not the dispatcher logic.
def parse_pptx(path: Path) -> Dict[str, Any]:
    """
    Parse a .pptx into ordered sections — ONE SLIDE = ONE SECTION, so slide
    identity is preserved for citations ([file, section='Slide N: title']).

    Captured per slide: all text frames (in shape order), tables (cells
    joined ' | ', rows by newline), and speaker notes (prefixed NOTES:).
    Pictures are counted and dropped (same v1 treatment as parse_docx —
    the vision pipeline picks them up later).

    Returns the same shape as parse_docx:
        {"total_sections": int, "total_images_skipped": int,
         "sections": [{"section_index", "section_title", "text"}]}
    """
    from pptx import Presentation

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PPTX not found: {path}")

    prs = Presentation(str(path))
    sections: List[Dict[str, Any]] = []
    images = 0
    for i, slide in enumerate(prs.slides):
        parts: List[str] = []
        title = ""
        title_shape = None
        try:
            title_shape = slide.shapes.title
        except Exception:
            pass
        for shape in slide.shapes:
            if shape.shape_type == 13:  # PICTURE
                images += 1
            if getattr(shape, "has_text_frame", False) and shape.text_frame.text.strip():
                txt = shape.text_frame.text.strip()
                if not title and title_shape is not None and shape is title_shape:
                    title = txt.splitlines()[0]
                else:
                    parts.append(txt)
            if getattr(shape, "has_table", False):
                rows = []
                for row in shape.table.rows:
                    rows.append(" | ".join(c.text.strip() for c in row.cells))
                parts.append("\n".join(rows))
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                parts.append(f"NOTES: {notes}")
        text = "\n".join(p for p in parts if p).strip()
        label = f"Slide {i + 1}" + (f": {title}" if title else "")
        if text or title:
            sections.append({"section_index": i, "section_title": label,
                             "text": text or title})
    return {"total_sections": len(sections), "total_images_skipped": images,
            "sections": sections}


def parse_csv(path: Path) -> Dict[str, Any]:
    """
    Parse a .csv into one chunk per non-empty data row — the tabular treatment
    parse_xlsx already gives workbooks, so CSV sealogs cite as [file, row=N].

    Same header rule as parse_xlsx: header = first row with >=2 non-empty
    cells within the first 10 rows (skips title/blank lead-ins). Delimiter is
    sniffed (comma/semicolon/tab); encoding tried utf-8-sig then latin-1
    (sealog exports are frequently latin-1).

    Returns the parse_xlsx shape: {"total_rows", "total_sheets": 1,
    "rows": [{"row_number", "sheet_name": "csv", "text", "token_count"}]}.
    """
    import csv as _csv

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    raw = path.read_bytes()
    for enc in ("utf-8-sig", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"CSV not decodable as utf-8 or latin-1: {path}")

    # Delimiter: the candidate most frequent across the first 20 lines. The
    # stdlib Sniffer fails on files with a delimiter-free title line; counting
    # is robust to that.
    head = text.splitlines()[:20]
    delim = max(",;\t", key=lambda d: sum(ln.count(d) for ln in head))

    reader = _csv.reader(text.splitlines(), delimiter=delim)
    HEADER_SCAN_LIMIT = 10
    headers: List[tuple] = []
    header_row_num = 0
    rows_out: List[Dict[str, Any]] = []
    total_rows = 0
    for idx, row in enumerate(reader, start=1):
        if not headers:
            candidate = [(ci, c.strip()) for ci, c in enumerate(row) if c and c.strip()]
            if len(candidate) >= 2:
                headers = candidate
                header_row_num = idx
            elif idx >= HEADER_SCAN_LIMIT:
                break
            continue
        total_rows += 1
        lines = []
        for col_idx, header in headers:
            if col_idx >= len(row):
                continue
            cell = (row[col_idx] or "").strip()
            if cell:
                lines.append(f"{header}: {cell}")
        if not lines:
            continue
        body = "\n".join(lines)
        rows_out.append({
            "row_number": idx,
            "sheet_name": "csv",
            "text": body,
            "token_count": len(count_tokens_raw(body)),
        })
    if not headers:
        logger.warning("CSV %s: no header row (>=2 cells) found in first %d rows.",
                       path.name, HEADER_SCAN_LIMIT)
    return {"total_rows": total_rows, "total_sheets": 1, "rows": rows_out}


PARSER_REGISTRY = {
    ".pdf":  {"parser": parse_pdf,  "needs_chunking": True},
    ".xlsx": {"parser": parse_xlsx, "needs_chunking": False},
    ".docx": {"parser": parse_docx, "needs_chunking": True},
    ".pptx": {"parser": parse_pptx, "needs_chunking": True},
    ".csv":  {"parser": parse_csv,  "needs_chunking": False},
}
