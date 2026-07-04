"""
Part-number FORMAT validation (Master Spec §3a) — the safe verification layer.

Validates a vision-read part number against the MANUFACTURER's part-number
SCHEME, never against a specific part. This catches glyph-confusion (B↔8, O↔0,
S↔5, I↔1) that survives even high resolution: e.g. a read of "15786203" does not
match the Danfoss cartridge scheme "157B####", so it is FLAGGED for re-read — and
a single glyph substitution (8→B) would make it valid, which is reported as a
re-read HINT, not an authoritative correction.

GOLD-BLIND / NO-INJECTION (§0.5, §3b):
  - This module validates SHAPE only. It contains manufacturer FORMAT patterns
    (e.g. Danfoss "157B####"), keyed off the DISCOVERED manifold family — these
    are the maker's published scheme, transferable to any vessel using that maker,
    NOT vessel-specific gold values. No specific part number from any gold fixture
    appears here.
  - It NEVER originates a value. On a format miss it flags + offers a re-read
    hint; the corrected value must come from an actual re-read of the drawing,
    never from this layer. (Laundering a confabulation into a "valid" part by
    substitution is exactly the §3b failure mode this avoids.)

The format registry is per-manufacturer and extensible (Phase 2: add a maker's
scheme once, it applies to every vessel using that maker).
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

# Manufacturer part-number SCHEMES (shape only). Source: the maker's published
# numbering scheme / part-manual, keyed off the discovered manifold family — NOT
# any gold fixture. Add a maker here once; do not hardcode specific parts.
_SCHEMES: Dict[str, List[tuple]] = {
    "danfoss": [
        (re.compile(r"^157B\d{4}$"), "Danfoss PVG slip-in cartridge"),
        (re.compile(r"^11\d{6}$"),   "Danfoss PVG module/component"),
    ],
    # "parker": [...], "bosch_rexroth": [...]  # extend per Phase-2 vessel
}

# Glyph pairs that are genuinely ambiguous in small/degraded print. Used ONLY to
# generate a re-read hint when a format miss is one substitution from valid.
_GLYPH_CONFUSIONS = {
    "8": "B", "B": "8", "0": "O", "O": "0",
    "5": "S", "S": "5", "1": "I", "I": "1",
}


def _matches(value: str, family: str) -> Optional[str]:
    for pat, label in _SCHEMES.get(family, []):
        if pat.match(value):
            return label
    return None


def _near_valid_hint(value: str, family: str) -> Optional[str]:
    """If a single glyph substitution would make `value` scheme-valid, return that
    candidate as a RE-READ HINT (not a correction)."""
    for i, ch in enumerate(value):
        alt = _GLYPH_CONFUSIONS.get(ch.upper())
        if not alt:
            continue
        cand = value[:i] + alt + value[i + 1:]
        if _matches(cand, family):
            return cand
    return None


def validate_partnum(value: str, family: str) -> Dict[str, object]:
    """
    Validate a read part number against `family`'s scheme.

    Returns:
      {value, family, valid, scheme_label?, flag?, reread_hint?}
    - valid=True  → shape matches the maker scheme (says nothing about whether the
                    specific part exists — that's §3b's job, separately gated).
    - valid=False → flagged. If one glyph substitution would make it valid, a
                    reread_hint is given (a SUGGESTION to re-read the crop, never an
                    authoritative value). Unknown family → cannot validate, flagged.
    """
    v = (value or "").strip().upper().replace(" ", "")
    out: Dict[str, object] = {"value": value, "family": family}
    if family not in _SCHEMES:
        out.update(valid=False, flag=f"no scheme on file for family '{family}' — cannot format-validate")
        return out
    label = _matches(v, family)
    if label:
        out.update(valid=True, scheme_label=label)
        return out
    out.update(valid=False, flag=f"does not match {family} scheme — re-read")
    hint = _near_valid_hint(v, family)
    if hint:
        out["reread_hint"] = hint  # a glyph substitution would make it valid → re-read to confirm
    return out


def family_for_manifold(make_model: str) -> Optional[str]:
    """Map a discovered manifold make/model string to a scheme family key. General
    token match — no specific gold model hardcoded as a target."""
    s = (make_model or "").lower()
    for fam in _SCHEMES:
        if fam in s:
            return fam
    return None
