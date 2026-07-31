"""
DRAWING-CLASS DETECTION — the missing question in the dispatcher.

`tools/extract_document.plan()` routes on PDF FILE FORMAT: has it vector
content, has it a text layer, how many images. Those are the right questions
for "how do I READ this file". They are not the question "what KIND of drawing
is this", and because nothing asked it, every approved class extractor was
orphaned:

  * a hydraulic block sheet went down the generic label path and produced 0
    rows, while `schematic_extract.discover_structure` — validated, engineer-
    approved, already the source of 183 facts in the Register — was never
    called;
  * a PLC set produced 2 rows out of 25 pages;
  * a P&ID printed "pid: per-service split NOT BUILT" while
    `pid_extract.fluid_loops()` sat unused in the same repo.

This module answers the missing question at $0, from text the file already
carries (its text layer, or the labels the geometry pass already OCR'd — never
a new render, never an API call).

GOLD-BLIND BY CONSTRUCTION. Every token below is GENERAL drafting-discipline
vocabulary — the words any hydraulic sheet, any P&ID, any PLC rack page uses,
in any yard. There is no maker name, no vessel tag, no Gelliceaux value here;
a detector tuned on this vessel's brands would learn the boat instead of the
discipline and route vessel #2 into the wrong extractor.

EVIDENCE IS RETURNED, NOT JUST A VERDICT. `detect()` reports which terms fired
and the runner-up, so a misroute is diagnosable from the ledger instead of
being an unexplained wrong answer. Below `MIN_SCORE` it returns `unknown` and
the generic path runs — flag-never-guess applies to routing too.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# Each class: (weight, regex). Weights encode how DIAGNOSTIC a term is, not how
# common — "spool" or "cartridge" names a hydraulic part and nothing else, while
# "valve" appears on hydraulic sheets, P&IDs and GAs alike.
SIGNALS: Dict[str, List[Tuple[float, str]]] = {
    "hydraulic": [
        (3.0, r"\bmanifold\b"), (3.0, r"\bspool\b"), (3.0, r"\bcartridge\b"),
        (2.5, r"\bproportional\s+valve\b"), (2.5, r"\brelief\b"),
        (2.0, r"\bl\s*/\s*min\b|\blt\s*/\s*min\b|\blpm\b"),
        (2.0, r"\b\d{2,4}\s*bar\b"), (2.0, r"\bhydraulic\b"),
        (1.5, r"\baccumulator\b"), (1.5, r"\bload\s*sens"),
        (1.5, r"\bsolenoid\b"), (1.0, r"\bcylinder\b"),
        (2.0, r"\b\d+\s+functions?\b"),
    ],
    "pid": [
        (3.0, r"\bsuction\b"), (3.0, r"\bdischarge\b"), (3.0, r"\boverboard\b"),
        (3.0, r"\bstrainer\b|\bstrum\s*box\b"), (2.5, r"\bsea\s*(cock|chest|water)\b"),
        (2.5, r"\bnon[- ]?return\b|\bnrv\b|\bcheck\s+valve\b"),
        (2.0, r"\bmanifold\s+box\b|\bbill\s+of\s+materials\b"),
        (2.0, r"\bbilge\b|\bblack\s*water\b|\bgrey\s*water\b|\bfuel\s+(line|system)\b"),
        (1.5, r"\bDN\s?\d{2,3}\b"), (1.5, r"\bpipe\b|\bpiping\b"),
        (1.5, r"\bheader\b|\bhydrant\b"),
    ],
    "plc": [
        (3.5, r"\bplc\b"), (3.0, r"\b(digital|analog(ue)?)\s+(in|out)put\b"),
        (3.0, r"\b(DI|DO|AI|AO)\s*\d"), (2.5, r"\brack\b|\bslot\b"),
        (2.5, r"\bfieldbus\b|\bbus\s+coupler\b"), (2.0, r"\bchannel\s*\d"),
        (2.0, r"\bi\s*/\s*o\b"), (1.5, r"\bmodule\b"),
        (1.5, r"\bcommon\b.{0,12}\boutput\b"),
    ],
    "electrical": [
        # breaker/fuse ID grammar + a rating is what a DISTRIBUTION SCHEDULE is
        (3.0, r"\b(Q|QE|CB|F)\s?\d{1,3}\b.{0,10}\b\d{1,3}\s*A(mp)?\b"),
        (2.5, r"\bdistribution\b"), (2.5, r"\bbreaker\b"),
        (2.0, r"\bbus\s*bar\b|\bbusbar\b"), (2.0, r"\bpanel\b"),
        (2.0, r"\b(24\s*V|230\s*V|400\s*V|600\s*V)\b"),
        (1.5, r"\bfuse\b"), (1.5, r"\brelay\b"), (1.5, r"\bterminal\s+strip\b"),
        (1.5, r"\bshore\s+power\b"), (1.0, r"\bearth\b|\bground\b"),
    ],
    "interconnect": [
        (3.0, r"\bpin\s*out\b|\bpinout\b"), (2.5, r"\bconnector\b"),
        (2.5, r"\bharness\b"), (2.5, r"\binterlock\b"),
        (2.0, r"\bpin\s*\d{1,2}\b"), (2.0, r"\bwire\s+(no|number|list)\b"),
        (1.5, r"\bshield\b"), (1.5, r"\bcan\s*(bus|hi|lo|h\b|l\b)"),
    ],
    "building_ga": [
        (3.0, r"\bgeneral\s+arrangement\b"), (2.5, r"\bscale\s*1\s*[:/]\s*\d"),
        # DRAWINGS ABBREVIATE. A saddle-layout GA labels its stations "STN
        # 5.0", not "station 5" - so a spelled-out-only pattern scored it 5.0
        # against a floor of 6 and the sheet did not route. STN and FR are
        # standard drafting shorthand on any yard's structural sheets.
        # (Dimension DENSITY was tested as a structural alternative and
        # rejected: GA 12%, BAE 11%, a GM wiring sheet 11%, PLC 10% - it
        # separates nothing.)
        (2.5, r"\b(frame|station|stn|fr)\.?\s*\d{1,3}(\.\d)?\b"),
        (2.0, r"\bsaddle\b|\bbulkhead\b|\bdeck\s*plan\b|\bkeel\b"),
        (2.0, r"\bprofile\b|\belevation\b|\bplan\s+view\b"),
        (2.0, r"\bwaterline\b|\bdatum\b"), (1.5, r"\bsection\s+[A-Z]\s*-\s*[A-Z]\b"),
    ],
}

COMPILED = {k: [(w, re.compile(p, re.I)) for w, p in v] for k, v in SIGNALS.items()}

# The grammar of a sheet that is DRAWN as wiring: a protective-device id with a
# rating, a named terminal strip with numbered terminals, or relay/contactor
# designators. Any one of these means conductors are being drawn, whatever the
# loads are called. Used only to break a tie — never to create a verdict.
_DRAWN_AS_WIRING = re.compile(
    r"\b(?:Q|QE|CB|F)\s?\d{1,3}\b\s*\d{1,3}\s*A"      # Q14 10A
    r"|\bT\s*/\s*S\s*[A-Z]\b"                          # T/S B
    r"|\bRe\s?\d{1,2}\b"                               # Re7
    r"|\bterminal\s+strip\b",
    re.I)

# Below this, the evidence is too thin to override the generic path. Chosen so
# a single weak term (one "panel", one "valve") can never route a whole file.
MIN_SCORE = 6.0
# A win this narrow is not a win: two disciplines are both present (a compound
# sheet — a P&ID carrying its own electrical control block is the common case),
# and forcing one extractor would silently drop the other half.
AMBIGUOUS_MARGIN = 0.25


def score_text(text: str) -> Dict[str, float]:
    """Weighted discipline score for a block of drawing text. Each term counts
    at most 3 times: a schedule that prints 'breaker' 90 times is not 30x more
    electrical than one printing it 3 times, and uncapped counts let one
    repeated word drown every other signal."""
    out: Dict[str, float] = {}
    for cls, pats in COMPILED.items():
        s = 0.0
        for w, rx in pats:
            hits = len(rx.findall(text))
            if hits:
                s += w * min(hits, 3)
        out[cls] = round(s, 2)
    return out


def evidence(text: str, cls: str, limit: int = 6) -> List[str]:
    """The terms that actually fired for `cls` — so a misroute is diagnosable."""
    found = []
    for w, rx in COMPILED.get(cls, []):
        m = rx.search(text)
        if m:
            found.append(m.group(0).strip().lower())
        if len(found) >= limit:
            break
    return found


def detect(text: str, *, page_count: int = 1,
           filename: str = "") -> Dict[str, Any]:
    """Classify one drawing by discipline.

    `text` is whatever the file already gives up for free: its PDF text layer,
    or the labels the geometry pass has already OCR'd. Never a fresh render.

    Returns {drawing_class, confidence, score, runner_up, evidence, basis}.
    `drawing_class` is 'unknown' when the evidence is thin or two disciplines
    tie — the generic path then runs, which is the honest outcome rather than a
    coin-flip into the wrong extractor.
    """
    text = text or ""
    scores = score_text(text)
    # The filename is a WEAK corroborator, never a decider: yards misname files,
    # and 'Electrical System GA' is a GA whichever way the name leans. It can
    # break a tie; it cannot create one.
    # UNDERSCORES DEFEAT WORD BOUNDARIES. The sweep stores the file as
    # "BAE_Wiring_Diagrams.pdf"; `_` is a word character, so `\bwiring\b` never
    # matched and the wiring-book hint did not fire — the sheet fell back to
    # 'electrical' instead of 'interconnect'. Separators are normalised to
    # spaces before any filename test.
    fname = re.sub(r"[_\-.]+", " ", (filename or "").lower())
    for cls in scores:
        if cls != "building_ga" and re.search(rf"\b{cls[:5]}", fname):
            scores[cls] += 1.0
    if "ga" in re.split(r"[^a-z]+", fname) or "arrangement" in fname:
        scores["building_ga"] += 1.0
    # THE DOCUMENT'S OWN TITLE IS EVIDENCE ABOUT ITS PAGES. A connector-pinout
    # page inside "BAE Wiring Diagrams.pdf" carries almost no discipline
    # vocabulary — its labels are a title block and bare pin ids (SIZE, DRAWING
    # NO., 196D5023, DC1, I1, -A) — and scored 4.5 against a floor of 6, so a
    # whole 47-page wiring book failed to route. Pin DENSITY was tested as a
    # structural signal and rejected: BAE 22%, a GM wiring sheet 37%, a PLC
    # rack page 48%, so it separates nothing. The book's title does: a page in
    # a wiring book is a wiring page. General drafting words only, no vessel
    # or maker token, so this transfers to any yard's file naming.
    for pat, cls, w in (
            (r"\bwiring\b|\bwire\s+list\b|\bpinout\b|\bharness\b", "interconnect", 3.0),
            (r"\bp\s*&\s*i\s*d\b|\bpiping\b|\bplumbing\b", "pid", 3.0),
            (r"\bhydraulic\b", "hydraulic", 3.0),
            (r"\bplc\b|\bi/o\b", "plc", 3.0),
            (r"\bschematic\b|\bdistribution\b|\bpanel\b", "electrical", 2.0)):
        if re.search(pat, fname):
            scores[cls] += w

    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    top, top_s = ranked[0]
    second, second_s = ranked[1] if len(ranked) > 1 else (None, 0.0)

    if top_s < MIN_SCORE:
        verdict, conf = "unknown", "insufficient_evidence"
    elif second_s and (top_s - second_s) / top_s < AMBIGUOUS_MARGIN:
        # A SHEET'S DISCIPLINE IS WHAT IT DRAWS, NOT WHAT ITS LOADS ARE CALLED.
        #
        # Measured on a real GM sheet: "WATER TRANSFER VALVES Q14 10A / T/S B
        # 14 15 16 / Re7 Re8 Re9 / OPEN / CLOSE / FRESH WATER PORT BUNKER"
        # scored pid 8.0 and electrical 8.0 and was called ambiguous — so
        # nothing was composed and a paid read was thrown away. But that sheet
        # is not half a P&ID: it is a wiring diagram whose LOADS happen to be
        # water valves. It draws conductors, terminals and relay contacts.
        #
        # Conversely a bilge P&ID drawn as pipework stays a P&ID even though it
        # names electric pumps. So the tie-break is STRUCTURAL: if the sheet
        # carries the grammar of wiring — a device id with a rating, numbered
        # terminals, relay/contact designators — it is drawn as an electrical
        # schematic whatever its loads are named.
        if "electrical" in (top, second) and _DRAWN_AS_WIRING.search(text):
            verdict, conf = "electrical", "tie_broken_by_wiring_grammar"
        else:
            # Genuinely compound and not settled by structure — say so rather
            # than pick. Naming both is the honest outcome.
            verdict, conf = "unknown", f"ambiguous_{top}_vs_{second}"
    else:
        verdict = top
        conf = "high" if top_s >= MIN_SCORE * 2 else "medium"

    return {
        "drawing_class": verdict,
        "confidence": conf,
        "score": top_s,
        "runner_up": second,
        "runner_up_score": second_s,
        "all_scores": scores,
        "evidence": evidence(text, top),
        "basis": "text_layer_or_ocr_labels",
        "text_chars": len(text),
    }


# ------------------------------------------------------- sheet role + header
# A drawing set is not all schematics. The engineer's first question is what
# KIND of page this is — index, title/header page, schedule, or a schematic —
# because an index is a ROUTER to other sheets and a title page carries no
# circuit at all. Reading either as a schematic wastes a paid pass and invents
# structure that is not drawn.
_INDEX_RE = re.compile(r"\b(index|drawing\s+list|sheet\s+list|contents)\b", re.I)
_TITLE_RE = re.compile(r"\b(cover|title\s+page|electrical\s+systems?\s+manual)\b", re.I)


def sheet_role(text: str, *, n_conductors: int = 0, n_labels: int = 0) -> str:
    """index | title | schedule | schematic — the page's ROLE, not its
    discipline. Geometry decides more than words here: an index is a page of
    text with almost no drawn conductor."""
    # GEOMETRY DECIDES FIRST, because it survives bad OCR. A schematic is a
    # page of DRAWN CONDUCTORS; a page with almost none is not one, however
    # many words it carries. Measured on the GM book's index page: 2 conductors
    # and 62 labels, which the word-based rules called a schematic because its
    # OCR text was too poor to match "index" — a page of pure text routed to a
    # circuit reader.
    if n_conductors < 10:
        return "index" if n_labels >= 25 else "title"
    if _INDEX_RE.search(text) and n_conductors < 40:
        return "index"
    if _TITLE_RE.search(text) and n_labels < 40:
        return "title"
    # A schedule is repeated [device][rating]->[load] rows rather than a traced
    # circuit: many device ids, few conductors relative to them.
    ids = len(re.findall(r"\b(?:Q|QE|CB|F)\s?\d{1,3}\b", text))
    if ids >= 12 and n_conductors < ids * 6:
        return "schedule"
    return "schematic"


def header_block(rec: Dict[str, Any], top_frac: float = 0.16) -> str:
    """The sheet's own header — the text band across the TOP of the page.

    "read the page's header if existing… that is a good orientation to start
    with" (engineer, 2026-07-31). On these drawings the header is exactly what
    the sheet IS: SHORE POWER INPUT, 230V AC SERVICE SUPPLY / PORT / BEL-1
    6KW, AC DB PANEL, 230V AC AFT DISTRIBUTION PANEL. It states the scope and
    the supply before a single conductor is followed, and it is free.

    Ordered left-to-right so a multi-part header reads as printed.
    """
    labels = [l for l in (rec.get("labels") or [])
              if (l.get("text") or "").strip() and l.get("bbox")]
    if not labels:
        return ""
    ys = [l["bbox"][1] for l in labels]
    y_min, y_max = min(ys), max(ys)
    cut = y_min + (y_max - y_min) * top_frac
    top = [l for l in labels if l["bbox"][1] <= cut]
    top.sort(key=lambda l: (round(l["bbox"][1] / 6), l["bbox"][0]))
    seen, parts = set(), []
    for l in top:
        t = l["text"].strip()
        if len(t) > 1 and t.upper() not in seen:
            seen.add(t.upper())
            parts.append(t)
    return "  ".join(parts[:24])


def text_from_page_record(rec: Dict[str, Any], min_conf: float = 60.0) -> str:
    """Drawing text from a sweep page record — the labels the geometry pass
    already read. Free: no render, no OCR re-run, no API call."""
    parts = []
    for l in rec.get("labels") or []:
        t = (l.get("text") or "").strip()
        if t and l.get("conf", 0) >= min_conf:
            parts.append(t)
    for t in rec.get("text_layer_labels") or []:
        s = t.get("text") if isinstance(t, dict) else t
        if s:
            parts.append(str(s))
    return " ".join(parts)


def detect_per_page(recs: List[Dict[str, Any]], *,
                    filename: str = "") -> Dict[str, Any]:
    """Class per PAGE, then the book's dominant class.

    A file is not one discipline. Measured on a real PLC set: pages 1-6 are
    connector pinouts and pages 3+ are I/O rack pages — classifying the whole
    file from its first pages called the book 'interconnect' and would have
    sent every rack page to the wrong reader. The dispatcher already treats
    raster pages inside a vector book individually; discipline deserves the
    same treatment.

    `dominant` is reported for the ledger, but the per-page verdict is what
    dispatch should use.
    """
    pages = []
    for rec in recs:
        txt = text_from_page_record(rec)
        r = detect(txt, filename=filename)
        r["page"] = rec.get("page")
        pages.append(r)
    tally: Dict[str, float] = {}
    for p in pages:
        if p["drawing_class"] != "unknown":
            tally[p["drawing_class"]] = tally.get(p["drawing_class"], 0) + 1
    dominant = max(tally, key=tally.get) if tally else "unknown"
    return {"dominant": dominant, "page_classes": tally,
            "pages": pages,
            "unknown_pages": sum(1 for p in pages
                                 if p["drawing_class"] == "unknown")}


# Which extractor each class belongs to. The names are the modules that ALREADY
# EXIST and were already engineer-approved — this table is the wiring that was
# missing, not new capability.
EXTRACTOR = {
    "hydraulic":    "pipeline.schematic_extract.discover_structure",
    "pid":          "pipeline.pid_extract.extract_pid + fluid_loops",
    "plc":          "pipeline.electrical_extract + compose(class=plc)",
    "electrical":   "pipeline.electrical_extract + compose(class=electrical)",
    "interconnect": "pipeline.electrical_extract + compose(class=interconnect)",
    "building_ga":  "positioned-callout router (NOT BUILT)",
    "unknown":      "generic geometry path",
}
