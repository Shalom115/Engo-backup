"""
Glossary-correction layer for vision (and any generated) acronym expansions.

The vision model reads vessel acronyms off a drawing correctly (it sees "MPCS-S")
but FREE-INVENTS the expansion — e.g. "MPCS (Multi-Point Control System)" when the
vessel's authoritative expansion is "Modular Propulsion Control System". A confident
wrong expansion in a stored description is exactly the kind of plausible-but-false
detail that makes an engineer distrust the agent, so it must be corrected against the
authoritative vessel glossary (glossary_<vessel>.json, sourced from the handover +
Owner's Manual acronym tables) BEFORE the description is stored.

What it does (high precision, low recall by design — never invents):
  - Finds inline expansions in either order:
        ACRONYM (Expansion words)        e.g. "MPCS-S (Multi-Point Control System)"
        Expansion words (ACRONYM)        e.g. "Multi-Point Control System (MPCS)"
  - If the acronym is in the glossary AND the written expansion doesn't match the
    authoritative one (normalised: case/punctuation/whitespace-insensitive), it
    replaces the expansion with the authoritative form and records the correction.
  - Acronyms NOT in the glossary are left untouched (can't verify ⇒ don't touch).
  - A bare acronym with no expansion is left alone (nothing to get wrong).
  - A -P/-S/-PORT/-STBD side suffix on the acronym is preserved.

Deliberately does NOT rewrite free-floating expansions with no adjacent acronym —
that needs context we don't have and risks corrupting correct prose. Parenthetical
pairing is the unambiguous, safe signal.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import config

# ACRONYM core (2-7 upper alnum) + optional side suffix (-S, -P, -PORT, -STBD, -1…).
_ACR = r"[A-Z][A-Z0-9]{1,6}"
_SUFFIX = r"(?:[-_/](?:[A-Z]{1,4}|\d{1,2}))?"
# "ACRONYM (expansion)" — expansion is 4-70 chars, must contain a letter, no nested parens.
_FORM_A = re.compile(rf"\b({_ACR})({_SUFFIX})\s*\(\s*([^()]*[A-Za-z][^()]*?)\s*\)")
# "Expansion (ACRONYM)" — the expansion must be a run of 1-6 Capitalised words right
# before the paren, so lowercase lead-in prose ("power flows from the …") can't be
# swallowed into the captured expansion.
_CAPWORD = r"[A-Z][A-Za-z0-9'&/-]*"
_FORM_B = re.compile(rf"((?:{_CAPWORD}\s+){{0,5}}{_CAPWORD})\s*\(\s*({_ACR})({_SUFFIX})\s*\)")


def load_glossary(vessel: Optional[str] = None) -> Dict[str, str]:
    """ACRONYM (upper) -> authoritative expansion (upper). Empty if no glossary."""
    vessel = vessel or config.VESSEL_NAMESPACE
    path = config.STATE_DIR / f"glossary_{vessel}.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[str, str] = {}
    for acr, rec in (data.get("acronyms") or {}).items():
        exp = (rec or {}).get("expansion")
        if exp:
            out[acr.upper()] = str(exp).upper()
    return out


def _norm(s: str) -> str:
    """Normalise an expansion for comparison: upper, drop non-alnum, collapse."""
    return re.sub(r"[^A-Z0-9]+", " ", s.upper()).strip()


def _expansion_like(s: str) -> bool:
    """A plausible expansion: >=2 words OR one long word, mostly alphabetic."""
    words = s.split()
    return len(words) >= 2 or (len(words) == 1 and len(words[0]) >= 6)


def correct_text(
    text: str,
    glossary: Optional[Dict[str, str]] = None,
) -> Tuple[str, List[Dict[str, str]]]:
    """
    Correct inline acronym expansions in `text` against the glossary.

    Returns (corrected_text, corrections) where each correction is
    {acronym, written, authoritative}. No glossary or no text ⇒ unchanged.
    """
    if not text:
        return text, []
    glossary = load_glossary() if glossary is None else glossary
    if not glossary:
        return text, []

    corrections: List[Dict[str, str]] = []

    def fix_a(m: re.Match) -> str:
        acr, suffix, written = m.group(1), m.group(2) or "", m.group(3).strip()
        auth = glossary.get(acr.upper())
        if not auth or not _expansion_like(written) or _norm(written) == _norm(auth):
            return m.group(0)
        corrections.append({"acronym": acr + suffix, "written": written, "authoritative": auth.title()})
        return f"{acr}{suffix} ({auth.title()})"

    def fix_b(m: re.Match) -> str:
        written, acr, suffix = m.group(1).strip(), m.group(2), m.group(3) or ""
        auth = glossary.get(acr.upper())
        if not auth or not _expansion_like(written) or _norm(written) == _norm(auth):
            return m.group(0)
        corrections.append({"acronym": acr + suffix, "written": written, "authoritative": auth.title()})
        return f"{auth.title()} ({acr}{suffix})"

    corrected = _FORM_A.sub(fix_a, text)
    corrected = _FORM_B.sub(fix_b, corrected)
    return corrected, corrections


def correct_components(
    components: List[Dict[str, Any]],
    glossary: Optional[Dict[str, str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """Apply correction to each component's label + note. Returns (components, all_corrections)."""
    glossary = load_glossary() if glossary is None else glossary
    all_corr: List[Dict[str, str]] = []
    for c in components:
        for field in ("label", "note"):
            if c.get(field):
                fixed, corr = correct_text(str(c[field]), glossary)
                c[field] = fixed
                all_corr.extend(corr)
    return components, all_corr


class CorrectionsLog:
    """
    Durable append-only audit trail of glossary corrections (before -> after).

    The per-run vision checkpoint is overwritten every batch, so the raw
    `written` (model's invented expansion) for corrections in earlier batches
    was being lost — only the count survived. This persists each fix the moment
    it is applied, with full provenance, so the trail survives across every run
    and chunk. One JSON line per correction. Flushed per record (kill-safe).

    Record shape:
      {ts, file_name, drive_file_id, page, figure, acronym, written, authoritative}
      written = what the model invented; authoritative = the glossary truth.
    """

    def __init__(self, vessel: Optional[str] = None):
        vessel = vessel or config.VESSEL_NAMESPACE
        self.path = config.STATE_DIR / f"glossary_corrections_{vessel}.jsonl"
        self._fh = open(self.path, "a", encoding="utf-8")
        self.count = 0

    def record(self, fixes: List[Dict[str, str]], *, context: Dict[str, Any]) -> int:
        """Append each fix in `fixes` with the given provenance context. Returns n written."""
        if not fixes:
            return 0
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        ctx = {k: v for k, v in context.items() if v is not None}
        for f in fixes:
            self._fh.write(json.dumps({"ts": ts, **ctx, **f}, ensure_ascii=False) + "\n")
            self.count += 1
        self._fh.flush()
        return len(fixes)

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass
