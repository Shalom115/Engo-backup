"""
DRAWING SYMBOL GLOSSARY loader — the §6 cross-discipline symbol→device-type
glossary, as prompt context.

Fleet-general conventions live in prompts/drawing_symbol_glossary.md (per
discipline section, '## electrical' etc.). Extraction prompts get the relevant
section prepended so the reader starts from marine-drafting conventions rather
than guessing — while the sheet's OWN legend (legends-first pass) explicitly
overrides these generics.

Gold-blind by construction: the glossary file carries symbol conventions only,
no vessel-specific equipment names or values.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

_GLOSSARY_PATH = Path(__file__).resolve().parent.parent / "prompts" / "drawing_symbol_glossary.md"

_HEADER = (
    "GENERAL DRAWING-SYMBOL CONVENTIONS (marine electrical drafting; the sheet's "
    "OWN legend, if present above, OVERRIDES these where they disagree):\n"
)


@lru_cache(maxsize=8)
def block(discipline: str = "electrical") -> str:
    """The glossary section for one discipline, formatted for prompt injection.
    Returns "" (and stays silent) if the file or section is missing — extraction
    must degrade to bare §6 discipline, never crash on a missing glossary."""
    try:
        text = _GLOSSARY_PATH.read_text()
    except OSError:
        return ""
    m = re.search(rf"^## {re.escape(discipline)}\s*$(.*?)(?=^## |\Z)",
                  text, re.M | re.S)
    if not m:
        return ""
    # keep only the bullet lines; drop provenance tags — they are for humans,
    # not the model
    lines = []
    for ln in m.group(1).splitlines():
        ln = ln.strip()
        if ln.startswith("- "):
            lines.append(re.sub(r"\[(?:ENG|STD|STD/ENG)\]\s*", "", ln))
        elif lines and ln and not ln.startswith("#"):
            lines[-1] += " " + ln  # continuation of a wrapped bullet
    if not lines:
        return ""
    return _HEADER + "\n".join(lines) + "\n\n"


def with_glossary(prompt: str, discipline: str = "electrical") -> str:
    """Prepend the discipline glossary to a prompt (no-op if unavailable)."""
    g = block(discipline)
    return (g + prompt) if g else prompt
