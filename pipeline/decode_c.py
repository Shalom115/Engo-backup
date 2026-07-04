"""
Class-C text-layer decoder (§3) — the decode pass that was specified but never built.

Class C = encoding-corrupted text layers from CAD PDF exports. Two variants found by
the corpus survey (2026-07-02):
  C1 — text garbled, RENDER CLEAN (broken ToUnicode map; glyphs fine). Vision can
       read the sheet; decoding the text layer is a bonus for text ingestion.
  C2 — text garbled AND RENDER GARBLED (font not embedded; the substituted font draws
       raw shifted char-codes). Vision CANNOT read the affected callouts — the decoded
       text layer is the ONLY reliable read. Decode is MANDATORY here.

The observed corruption is a FIXED ASCII SHIFT (e.g. +29: '0$67(592/7' -> 'MASTERVOLT').
decode_text() searches candidate shifts and keeps the one that maximizes real-word
density; it never applies a shift that does not clearly improve the text (fail-honest:
returns the original with decoded=False rather than laundering garbage).
"""
from __future__ import annotations

import io
import re
from typing import Any, Dict, Optional

_WORD = re.compile(r"[A-Za-z]{4,}")
# generic engineering-drawing vocabulary for scoring (vessel-agnostic)
_VOCAB = {"PANEL", "ELECTRIC", "ELECTRICAL", "SECTION", "DETAIL", "SCALE", "TRUNKING",
          "CABLE", "SYSTEM", "PUMP", "VALVE", "TANK", "LOOKING", "VIEW", "PLAN",
          "PROFILE", "DECK", "HULL", "FRAME", "GALLEY", "SALOON", "CABIN", "AFT",
          "FWD", "PORT", "STBD", "STARBOARD", "LIGHTS", "BREAKER", "BOARD", "POWER"}


def _score(text: str) -> float:
    toks = text.split()
    if not toks:
        return 0.0
    alpha = sum(1 for t in toks if _WORD.fullmatch(t.strip(".,:;()[]")))
    vocab = sum(1 for w in _VOCAB if w in text.upper())
    return alpha / len(toks) + 0.05 * vocab


def _shift(text: str, k: int) -> str:
    return "".join(chr(ord(c) + k) if 33 <= ord(c) <= 126 - k else c for c in text)


def decode_text(text: str, *, shifts=range(1, 48)) -> Dict[str, Any]:
    """
    Try fixed-shift decodes; keep the best only if clearly better than the original.
    Returns {decoded: bool, shift, text, score_before, score_after}.
    """
    base = _score(text)
    best_k, best_s, best_t = None, base, text
    for k in shifts:
        cand = _shift(text, k)
        s = _score(cand)
        if s > best_s:
            best_k, best_s, best_t = k, s, cand
    ok = best_k is not None and best_s >= max(2 * base, base + 0.08)
    return {"decoded": ok, "shift": best_k if ok else None,
            "text": best_t if ok else text,
            "score_before": round(base, 3), "score_after": round(best_s, 3)}


def fonts_embedded(pdf_bytes: bytes, page_index: int = 0) -> Dict[str, bool]:
    """
    Per-font embedding check (the C1/C2 discriminator): a garbled-text font that is
    NOT embedded renders garbled too (C2 — vision unreliable); an embedded one
    renders fine (C1 — vision OK).
    """
    from pypdf import PdfReader
    out: Dict[str, bool] = {}
    page = PdfReader(io.BytesIO(pdf_bytes)).pages[page_index]
    res = page.get("/Resources") or {}
    fonts = res.get("/Font") or {}
    for name, ref in fonts.items():
        f = ref.get_object()
        desc = f.get("/FontDescriptor")
        emb = False
        if desc is not None:
            desc = desc.get_object()
            emb = any(k in desc for k in ("/FontFile", "/FontFile2", "/FontFile3"))
        # Type0 composite fonts keep the descriptor on the descendant
        if not emb and f.get("/Subtype") == "/Type0":
            for dsc in (f.get("/DescendantFonts") or []):
                d = dsc.get_object().get("/FontDescriptor")
                if d is not None and any(k in d.get_object()
                                         for k in ("/FontFile", "/FontFile2", "/FontFile3")):
                    emb = True
        out[str(name)] = emb
    return out


def classify_c_variant(pdf_bytes: bytes, page_index: int = 0) -> str:
    """'C1' (all fonts embedded -> render clean) | 'C2' (unembedded font present ->
    render garbled, decode mandatory) | 'unknown' (no fonts found)."""
    emb = fonts_embedded(pdf_bytes, page_index)
    if not emb:
        return "unknown"
    return "C1" if all(emb.values()) else "C2"
