"""
OPEN-QUESTION LEDGER — cross-sheet uncertainty resolution (engineer-mandated
2026-07-22).

The engineer's observation: "there will be a lot of time when things are not
necessarily understood in the current sheet but it will come clear as the
entire drive gets ingested." A sheet legitimately cannot answer everything —
GM-116 says "the + comes from DWG 118", the ONYX taps only resolve once the
ONYX drawings land.

So an uncertainty is not a dead end; it is an OPEN QUESTION with a key. This
module keeps that ledger across the whole ingestion:

  * every composition's uncertainties + cross_references are filed as OPEN
    questions, each with search keys (device ids, terminal numbers, drawing
    references, equipment words);
  * when a LATER sheet is ingested, its facts are matched against every open
    question — anything it answers is CLOSED, with the answering sheet
    recorded as provenance;
  * whatever is still open at the end of the run is the engineer's real
    red-pen list — small, and genuinely unanswerable from the corpus.

This turns "unknown on this sheet" from noise into a resolvable queue.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Set

import config

LEDGER = config.STATE_DIR / f"open_questions_{config.VESSEL_NAMESPACE}.json"

# identifiers worth keying on: device ids (Q15, Re24, F3, XA50, QE5),
# terminal numbers, drawing references (DWG 118, GMMS 108'-116)
_ID = re.compile(r"\b(?:[A-Z]{1,3}E?\d{1,3}(?:\.\d+)?|XA\d{2,3}|MU\d{1,2}-\d{1,2})\b")
_DWG = re.compile(r"\b(?:DWG|DRAWING|SHEET|GMMS)[\s.:'-]*([\w\d\-']{2,12})", re.I)
_TERM = re.compile(r"\bterminals?\s+(\d{1,3})\b", re.I)


def _keys(text: str) -> Set[str]:
    t = text or ""
    keys = set(m.group(0).upper() for m in _ID.finditer(t))
    keys |= {f"DWG:{m.group(1).upper()}" for m in _DWG.finditer(t)}
    keys |= {f"TERM:{m.group(1)}" for m in _TERM.finditer(t)}
    return keys


def _load() -> Dict[str, Any]:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text())
    return {"vessel": config.VESSEL_NAMESPACE, "questions": []}


def _save(data: Dict[str, Any]) -> None:
    tmp = LEDGER.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(LEDGER)


def file_questions(sheet: str, composition: Dict[str, Any],
                   drawing_class: str = "") -> int:
    """File this sheet's uncertainties + cross-references as OPEN questions."""
    data = _load()
    have = {(q["sheet"], q["text"]) for q in data["questions"]}
    added = 0
    for u in composition.get("uncertainties") or []:
        text = u if isinstance(u, str) else json.dumps(u)
        if (sheet, text) in have:
            continue
        data["questions"].append({
            "id": f"q{len(data['questions']) + 1}",
            "sheet": sheet, "drawing_class": drawing_class,
            "kind": "uncertainty", "text": text,
            "keys": sorted(_keys(text)), "status": "open",
            "opened": str(date.today())})
        added += 1
    for x in composition.get("cross_references") or []:
        if not isinstance(x, dict):
            continue
        text = x.get("what", "")
        hint = x.get("referenced_sheet_hint", "")
        if (sheet, text) in have or not text:
            continue
        data["questions"].append({
            "id": f"q{len(data['questions']) + 1}",
            "sheet": sheet, "drawing_class": drawing_class,
            "kind": "cross_reference", "text": text,
            "hint": hint,
            "keys": sorted(_keys(f"{text} {hint}")), "status": "open",
            "opened": str(date.today())})
        added += 1
    _save(data)
    return added


def _composition_text(composition: Dict[str, Any]) -> str:
    return json.dumps(composition, ensure_ascii=False)


def resolve_with(sheet: str, composition: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check this sheet's content against every OPEN question from earlier sheets.
    A question is CLOSED when this sheet carries its key AND is a different
    sheet (a sheet cannot answer itself).
    """
    data = _load()
    blob = _composition_text(composition).upper()
    closed: List[Dict[str, Any]] = []
    for q in data["questions"]:
        if q["status"] != "open" or q["sheet"] == sheet:
            continue
        keys = q.get("keys") or []
        if not keys:
            continue
        hits = [k for k in keys if k.split(":")[-1] in blob]
        # require a real identifier hit, not a bare 1-2 digit coincidence
        strong = [k for k in hits if len(k.split(":")[-1]) >= 2]
        if strong:
            q["status"] = "answered"
            q["answered_by"] = sheet
            q["answered_on"] = str(date.today())
            q["matched_keys"] = strong
            closed.append(q)
    if closed:
        _save(data)
    return closed


def answer_by_engineer(match: str, answer: str, *,
                       scope: str = "") -> List[Dict[str, Any]]:
    """
    Record an ENGINEER answer to open question(s) — the durable channel for
    red-pen knowledge (2026-07-26).

    Until now a red-pen answer had nowhere to live: the engineer settled a
    question in chat, the ledger still showed it open, and the next sheet
    re-asked it or re-derived it differently. An answer given once must hold
    for every later sheet — that is what "so Engo gets these results without
    me" requires.

    MATCHING IS DELIBERATELY STRICT (tightened the same day it was written,
    after a substring matcher pasted the hatch-solenoid answer onto four
    unrelated thruster/sailing questions and a black-water relay answer onto a
    fog-horn question on a different sheet). An answer written onto the wrong
    question is worse than an unanswered one — it becomes authoritative and
    outranks later evidence. Therefore:

      * matching is on TOKEN BOUNDARIES, never bare substring;
      * a short token (< 4 chars, e.g. "S1", "Q14") is ambiguous across sheets
        and REQUIRES `scope` (the sheet key) — otherwise nothing is written;
      * `scope`, when given, restricts to that sheet.
    """
    data = _load()
    m = (match or "").strip()
    if not m:
        return []
    if len(m) < 4 and not scope:
        raise ValueError(
            f"answer_by_engineer({m!r}): identifier too short to be unique "
            f"across sheets — pass scope='<sheet key>' so the answer cannot "
            f"land on another sheet's question.")
    pat = re.compile(r"(?<![A-Za-z0-9])" + re.escape(m) + r"(?![A-Za-z0-9])",
                     re.I)
    hit: List[Dict[str, Any]] = []
    for q in data["questions"]:
        if scope and scope not in (q.get("sheet") or ""):
            continue
        blob = (q.get("text", "") + " " + " ".join(q.get("keys") or []))
        if not pat.search(blob):
            continue
        q["status"] = "answered"
        q["answer"] = answer
        q["authority"] = "engineer"
        q["answered_by"] = "engineer"
        q["answered_on"] = str(date.today())
        # SCOPE TRAVELS WITH THE ANSWER. Some answers are sheet-specific ("Re19
        # on the black-water sheet gives negative to relays whose load is on
        # NC"); others are vessel-general ("XA41 terminals are the control").
        # Without recording which, a sheet-specific answer gets applied to a
        # different sheet's relay of the same number — the cross-sheet
        # contamination failure, arriving through the answer channel.
        q["answer_scope"] = scope or ""
        hit.append(q)
    if hit:
        _save(data)
    return hit


def reopen(question_ids: List[str]) -> int:
    """Undo an answer that landed on the wrong question — back to open, with
    every trace of the wrong answer removed (a stale answer left on the record
    would still be read as authoritative)."""
    data = _load()
    n = 0
    for q in data["questions"]:
        if q["id"] in question_ids:
            q["status"] = "open"
            for k in ("answer", "authority", "answered_by", "answered_on",
                      "matched_keys"):
                q.pop(k, None)
            n += 1
    if n:
        _save(data)
    return n


def settled_digest(limit: int = 25) -> str:
    """Prompt block: questions the ENGINEER has settled. These are authoritative
    — a later sheet may cite them, must not contradict them, and must never
    re-raise them as uncertainties."""
    data = _load()
    ans = [q for q in data["questions"]
           if q.get("authority") == "engineer" and q.get("answer")]
    if not ans:
        return ""
    out = ["SETTLED BY THE ENGINEER (authoritative — do NOT re-raise these as "
           "uncertainties, and do not contradict them; where this sheet shows "
           "the same thing, describe it consistently with the answer):"]
    for q in ans[:limit]:
        out.append(f"  [{q['id']}] {q['text'][:130]} -> ANSWER: {q['answer'][:260]}")
    return "\n".join(out)


def open_digest(limit: int = 30) -> str:
    """Prompt block: what earlier sheets could not answer — if THIS sheet
    resolves one, say so explicitly in the composition."""
    data = _load()
    openq = [q for q in data["questions"] if q["status"] == "open"]
    if not openq:
        return ""
    out = ["OPEN QUESTIONS FROM EARLIER SHEETS — if anything on THIS sheet "
           "answers one of these, state the answer explicitly in the relevant "
           "fact or note (do not invent; only answer what this sheet shows):"]
    for q in openq[:limit]:
        keys = ", ".join(q["keys"][:6])
        out.append(f"  [{q['id']}] ({q['sheet']}) {q['text'][:160]}"
                   + (f"   keys: {keys}" if keys else ""))
    return "\n".join(out)


def _function_texts(composition: Dict[str, Any]) -> List[tuple]:
    """(label, text) for every function/scenario block in a composition.

    Checking a settled answer against the WHOLE composition is too coarse: the
    p26 reed switch was written up as a status output while the answer's words
    ("relay", "terminals", "inflate") all appeared elsewhere on the sheet, so a
    whole-document check passed a composition that contradicted the answer on
    the very element it was about. An answer is applied or not applied AT AN
    ELEMENT, so that is the unit that gets checked.
    """
    out: List[tuple] = []
    groups = composition.get("equipment_groups")
    if not isinstance(groups, list):
        return out
    for g in groups:
        if not isinstance(g, dict):
            continue
        for f in (g.get("functions") or []):
            if not isinstance(f, dict):
                continue
            bits = [str(f.get("label", "")), str(f.get("what_it_does", "")),
                    str(f.get("dry_data", ""))]
            for kc in (f.get("key_components") or []):
                bits.append(str(kc))
            for sc in (f.get("flow_scenarios") or []):
                if isinstance(sc, dict):
                    bits.append(str(sc.get("state", "")))
                    bits.append(str(sc.get("path", "")))
                else:
                    bits.append(str(sc))
            out.append((str(f.get("label", ""))[:80], " ".join(bits).upper()))
    return out


def check_settled_applied(composition: Dict[str, Any],
                          sheet: str = "") -> List[Dict[str, Any]]:
    """
    DID THE COMPOSITION ACTUALLY USE THE ENGINEER'S ANSWERS? (2026-07-26)

    The p26 reed-switch miss: the engineer's answer ("the reed switch closes
    terminals 24/25 and supplies Re8 its NEGATIVE, which lets the inflate
    valves open") WAS in the prompt and WAS applied to a neighbouring function
    — but not to the reed switch itself, which was still written up as a status
    output. Offering an answer in a prompt does not make it land on the element
    it is about, so it is CHECKED deterministically, per element.

    Three things keep this sharp rather than noisy:
      * SCOPE — a sheet-scoped answer is only checked against that sheet, so a
        p22 relay answer is never demanded of a p20 function;
      * IDENTIFIERS decide WHICH function is judged (Re8, V1, XA41, S1) —
        never generic words like "relay" or "negative", which appear in every
        wiring function ever written and made the first version fire on
        everything;
      * RELATION decides whether the answer LANDED — the answer's own
        directional claim (negative/positive, NO/NC, opens/closes, status vs
        control). A function that names the element but states none of the
        answer's relation has not applied it.
    """
    funcs = _function_texts(composition)
    if not funcs:
        return []
    data = _load()
    missed: List[Dict[str, Any]] = []
    for q in data["questions"]:
        if q.get("authority") != "engineer" or not q.get("answer"):
            continue
        scope = q.get("answer_scope") or ""
        if scope and sheet and scope not in sheet:
            continue              # sheet-specific answer, different sheet
        cross = bool(scope) and bool(sheet) and scope not in sheet
        if not scope and sheet and q.get("sheet") and q["sheet"] != sheet:
            cross = True          # general answer being reused on another sheet
        idents = _answer_identifiers(q["answer"], cross_sheet=cross)
        concepts = _relation_concepts(q["answer"])
        if not idents or not concepts:
            continue
        for label, text in funcs:
            if not any(_token_in(i, text) for i in idents):
                continue
            unmet = [c for c in concepts if not _states_concept(c, text)]
            if len(unmet) == len(concepts):     # states NONE of the claim kinds
                missed.append({"id": q["id"], "answer": q["answer"],
                               "function": label, "idents": idents[:5],
                               "missing_relation": unmet[:5]})
            break
    return missed


# IDENTIFIER LOCALITY (2026-07-26) — the same lesson as the node matcher's
# "never key on tag numbers" and power_path's region scoping, arriving here:
# relay numbers, terminal numbers and terminal-strip letters RESTART ON EVERY
# SHEET. Re7 on the water-valve sheet and Re7 on the companionway sheet are
# different relays. Monitoring-bus tags (XA-blocks) and multi-core cable ids
# are drawn to be unique across the whole vessel, which is what makes them
# usable as cross-sheet keys. So an answer's identifiers only travel to
# another sheet if they are of the GLOBAL kind.
_ID_LOCAL = re.compile(r"(?<![A-Z0-9])(?:RE\s?\d{1,3}|T/S\s?[A-Z]|"
                       r"TERMINALS?\s+\d{1,3}|[A-Z]{1,2}\d{1,3})(?![A-Z0-9])")
_ID_GLOBAL = re.compile(r"(?<![A-Z0-9])(?:XA\d{2,3}|MU\d{1,2}-\d{1,2})(?![A-Z0-9])")

# RELATION CONCEPTS, not literal words. The first version demanded the answer's
# exact verb: an answer saying "activated by" was reported as unapplied by a
# composition that said "energised through". Same claim, different word. What
# matters is whether the function states the answer's KIND of claim.
_RELATION_CONCEPTS = {
    "polarity":  ("NEGATIVE", "POSITIVE", "+VE", "-VE", "NEG ", "POS "),
    "contact":   (" NC", " NO ", "NORMALLY CLOSED", "NORMALLY OPEN",
                  "OPENS", "CLOSES"),
    "actuation": ("ACTIVAT", "ENERGIS", "COMMAND", "DRIVE", "OPERAT",
                  "SWITCH", "TRIGGER"),
    "direction": ("STATUS", "SIGNAL", "MONITOR", "CONTROL", "FEEDBACK"),
    "supply":    ("SUPPLIES", "SUPPLY", "FEED", "SOURCE", "COMES FROM"),
}


def _answer_identifiers(answer: str, cross_sheet: bool = False,
                        limit: int = 6) -> List[str]:
    """Identifier-like tokens that decide WHICH function an answer is about.
    Cross-sheet, only globally-unique identifiers qualify (see above)."""
    up = answer.upper()
    pats = [_ID_GLOBAL] if cross_sheet else [_ID_GLOBAL, _ID_LOCAL]
    out, seen = [], set()
    for pat in pats:
        for m in pat.finditer(up):
            t = " ".join(m.group(0).split())
            if t not in seen:
                seen.add(t)
                out.append(t)
            if len(out) >= limit:
                return out
    return out


def _relation_concepts(answer: str) -> List[str]:
    """Which KINDS of claim this answer makes."""
    up = answer.upper()
    return [name for name, words in _RELATION_CONCEPTS.items()
            if any(w in up for w in words)]


def _states_concept(concept: str, text: str) -> bool:
    return any(w in text for w in _RELATION_CONCEPTS[concept])


def _token_in(token: str, text: str) -> bool:
    return re.search(r"(?<![A-Z0-9])" + re.escape(token) + r"(?![A-Z0-9])",
                     text) is not None


def candidate_pairs(composition: Dict[str, Any], sheet: str = ""
                    ) -> List[Dict[str, Any]]:
    """
    (engineer answer, function) pairs where the function is ABOUT the answer's
    subject. Cheap, deterministic, high-recall — this is only the TRIGGER; the
    judgement of whether the answer was actually applied is made in
    `verify_settled`.
    """
    funcs = _function_texts(composition)
    if not funcs:
        return []
    data = _load()
    pairs: List[Dict[str, Any]] = []
    for q in data["questions"]:
        if q.get("authority") != "engineer" or not q.get("answer"):
            continue
        scope = q.get("answer_scope") or ""
        if scope and sheet and scope not in sheet:
            continue
        cross = bool(sheet) and bool(q.get("sheet")) and q["sheet"] != sheet
        idents = _answer_identifiers(q["answer"], cross_sheet=cross)
        if not idents:
            continue
        for label, text in funcs:
            if any(_token_in(i, text) for i in idents):
                pairs.append({"id": q["id"], "answer": q["answer"],
                              "function": label, "function_text": text[:1200],
                              "idents": idents[:5]})
                break
    return pairs


_VERIFY_PROMPT = (
    "An engineer has given an authoritative answer about part of a technical "
    "drawing. Below is that answer, and below it is what a draft description "
    "says about the same element.\n\n"
    "Decide ONE thing per item: does the draft STATE the engineer's answer, or "
    "does it OMIT or CONTRADICT it?\n"
    "  applied      - the draft says the same thing, in whatever words\n"
    "  omitted      - the draft describes the element but leaves out what the "
    "answer establishes\n"
    "  contradicted - the draft says something incompatible with the answer\n"
    "Judge the SUBSTANCE, not the wording: 'activated by' and 'energised "
    "through' are the same claim. Only mark contradicted when the draft "
    "asserts something that cannot both be true with the answer. If the answer "
    "is about a different element than the draft text describes, mark "
    "'not_applicable'.\n"
)

def verify_settled(composition: Dict[str, Any], sheet: str = "",
                   model: str = "") -> List[Dict[str, Any]]:
    """
    IS THE ENGINEER'S ANSWER ACTUALLY IN THE COMPOSITION? — judged, not
    string-matched (2026-07-26).

    Three string-matching versions of this check were built and each traded one
    failure for the other: keyed on content words it passed a composition that
    contradicted the answer (generic words like "relay" and "control" appear in
    every wiring function); tightened, it demanded the engineer's exact verb
    and flagged a correct paraphrase. Whether a description AGREES with an
    English sentence is a semantic judgement, and no amount of regex makes it
    one.

    So the split is: deterministic code finds the CANDIDATES (which function is
    about which answer — reliable), and one cheap-model call judges AGREEMENT
    across all candidates for the sheet at once. Typically 0-4 pairs and a few
    hundred tokens, i.e. a fraction of a cent against a composition costing
    dollars — and it catches exactly the class of miss that used to reach the
    engineer.

    Returns only the failures ([] when everything landed). Verification failure
    never blocks a run: it degrades to "no verdict" rather than losing the work.
    """
    pairs = candidate_pairs(composition, sheet)
    if not pairs:
        return []
    from providers.llm import get_llm_provider
    import os
    body = []
    for p in pairs:
        body.append(f"ITEM {p['id']}\n  ENGINEER ANSWER: {p['answer']}\n"
                    f"  DRAFT SAYS (function '{p['function']}'): "
                    f"{p['function_text'][:900]}\n")
    system = _VERIFY_PROMPT + (
        "\nReply with ONE line per item and nothing else, in the form:\n"
        "<item id>|<applied|omitted|contradicted|not_applicable>|<short reason>")
    try:
        llm = get_llm_provider(model=os.getenv(
            "VERIFY_MODEL", "claude-haiku-4-5-20251001"))
        res = llm.complete_full(system, "\n".join(body), max_tokens=800)
        text = res.get("text", "") if isinstance(res, dict) else str(res)
    except Exception:
        return []                      # never block a run on the verifier
    verdicts = []
    for line in (text or "").splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2 and parts[1].lower() in (
                "applied", "omitted", "contradicted", "not_applicable"):
            verdicts.append({"id": parts[0].strip().strip("[]"),
                             "verdict": parts[1].lower(),
                             "why": parts[2] if len(parts) > 2 else ""})
    by_id = {p["id"]: p for p in pairs}
    out = []
    for v in verdicts:
        if not isinstance(v, dict):
            continue
        if v.get("verdict") in ("omitted", "contradicted"):
            p = by_id.get(v.get("id"), {})
            out.append({"id": v.get("id"), "verdict": v["verdict"],
                        "why": v.get("why", ""), "answer": p.get("answer", ""),
                        "function": p.get("function", "")})
    return out


def enforcement_note(missed: List[Dict[str, Any]]) -> str:
    """A targeted re-ask block naming exactly which settled answers the draft
    failed to apply, and to what."""
    if not missed:
        return ""
    out = ["YOU DID NOT APPLY THESE ENGINEER-SETTLED ANSWERS, though this "
           "sheet shows what they are about. Rewrite the affected function so "
           "the answer's substance is stated where it belongs — on the element "
           "itself, not only on a neighbouring one:"]
    for m in missed:
        where = m.get("function") or ", ".join(m.get("subject", [])[:4])
        verdict = m.get("verdict", "not applied")
        why = f"  ({m['why']})" if m.get("why") else ""
        out.append(f"  [{m['id']}] {verdict} in '{where}'{why}\n"
                   f"      ANSWER: {m['answer']}")
    return "\n".join(out)


def stats() -> Dict[str, int]:
    data = _load()
    qs = data["questions"]
    return {"total": len(qs),
            "open": sum(1 for q in qs if q["status"] == "open"),
            "answered": sum(1 for q in qs if q["status"] == "answered")}
