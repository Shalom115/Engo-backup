"""
General nautical/technical abbreviation expansion for control-map matching.

This is a CAPABILITY, not an equipment-specific lookup: it expands common marine
abbreviations BEFORE matching so that any sheet using "S.T.", "STBD THR", "HYD",
etc. resolves against the same control-map function names, regardless of which
drafter or sheet produced the label. It is vessel-agnostic vocabulary and lives in
the routing layer (node_write), NOT in the gold-blind extractor.

Keep entries GENERAL and low-ambiguity. When expansion does not resolve a label,
node_write falls back to fuzzy token matching with a confidence floor, then to the
§9e semantic matcher, then create_flagged — so an over-expansion can never
wrong-attach (worst case: no match -> flagged).
"""
from __future__ import annotations

import re

# normalized-key -> expansion. Keys are matched as contiguous token subsequences.
# Multi-token keys (e.g. "s t" from "S.T.") are supported.
ABBREV = {
    "s t": "stern thruster",
    "b t": "bow thruster",
    "thr": "thruster",
    "thrust": "thruster",
    "stbd": "starboard",
    "stb": "starboard",
    "prt": "port",
    "fwd": "forward",
    "hyd": "hydraulic",
    "gen": "generator",
    "genset": "generator",
    "wm": "watermaker",
    "fw": "fresh water",
    "sw": "sea water",
    "bw": "black water",
    "gw": "grey water",
    "eng": "engine",
    "cyl": "cylinder",
    "sol": "solenoid",
    "mtr": "motor",
    "pmp": "pump",
    "pp": "pump",
    "press": "pressure",
    "temp": "temperature",
    "wnch": "winch",
    "wch": "winch",
    "cunn": "cunningham",
    "o haul": "outhaul",
    "bkstay": "backstay",
    "wndl": "windlass",
    "cptn": "capstan",
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def expand(label: str) -> str:
    """
    Expand known abbreviations in a (raw) label. Operates on the normalized token
    stream, replacing contiguous abbreviation token-sequences with their expansion.
    Longest keys first so multi-token abbreviations win over single tokens.
    Returns a normalized, expanded string.
    """
    toks = _norm(label).split()
    keys = sorted((k.split() for k in ABBREV), key=len, reverse=True)
    out: list[str] = []
    i = 0
    while i < len(toks):
        matched = False
        for kt in keys:
            n = len(kt)
            if toks[i:i + n] == kt:
                out.extend(ABBREV[" ".join(kt)].split())
                i += n
                matched = True
                break
        if not matched:
            out.append(toks[i])
            i += 1
    return " ".join(out)
