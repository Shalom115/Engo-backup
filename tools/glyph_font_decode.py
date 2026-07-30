"""
GLYPH FONT DECODER — deterministic label reading for CAD-plotted (SHX) text.

The kill for the OCR-residue channel: in a vector plot every character is the
IDENTICAL vector shape wherever it appears (89% shape reuse measured on the GM
book). So the drafting house's font is LEARNABLE: align high-confidence
tesseract reads with their glyph shapes once, and from then on every label on
every sheet of every vessel drawn by that house decodes EXACTLY — no OCR, no
API, no per-page cost. Same family as decode_c's +29 shift, at glyph level.

SELF-LEARNING (no engineer, no gold values):
  TRAIN on even pages only: for each horizontal label whose tesseract
  confidence >= TRAIN_CONF and whose glyph-derived character-cluster count
  equals its text length (strict 1:1 alignment — anything else is skipped,
  never force-aligned), each character cluster votes its shape-signature ->
  character. Table keeps signatures with >= MIN_VOTES and >= MAJORITY
  agreement.
  TEST on odd pages (never trained on): decoded text vs high-conf tesseract.
  The agreement number reported is OUT-OF-SAMPLE — the honest one.

DECODE: every label re-read from its glyph signatures; unknown signature ->
'?' (never guessed). A label with zero '?' is a FULL decode (conf 99 for the
routing preview); labels made of signatures the font never saw (dotted
enclosure runs, symbol fragments) decode to nothing and are auto-flagged
non-text — which also fixes the 'eee eee' dotted-boundary lint findings.

    python tools/glyph_font_decode.py <book.pdf> <bookrun_dir> <out_dir>

FINGERPRINTS ARE CROSS-PROCESS STABLE (stable_hash/blake2b — the builtin
hash() is randomised per process; with it the persisted font table could never
match a later run, so the per-house font asset was dead weight. Same bug
caught live in the symbol bank: 0/159 typed.) A persisted font table can now
be RELOADED for later books from the same drafting house via --font-table.

Outputs: font_table_<house>.json, decode_report.json,
         <out_dir>/p<N>.json (bookrun copies with decoded text merged).
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz

from symbol_bank_build import stable_hash  # cross-process-stable fingerprints

TRAIN_CONF = 85.0
MIN_VOTES = 3
MAJORITY = 0.9
SPACE_FACTOR = 1.9   # gap > SPACE_FACTOR * median char gap -> insert a space
# Char-splitting gap SCALES with font size (title-block text is 2-3x the
# schematic text; a fixed 0.55pt merged whole words there): any positive gap
# > 0.16 x glyph-line height separates characters, floor 0.3pt.


def _pts(it):
    out = []
    for q in it[1:]:
        if hasattr(q, "x"):
            out.append((q.x, q.y))
        elif hasattr(q, "x0"):
            out += [(q.x0, q.y0), (q.x1, q.y1)]
        elif hasattr(q, "ul"):
            out += [(q.ul.x, q.ul.y), (q.lr.x, q.lr.y)]
    return out


def page_glyphs(page):
    """Small drawing paths (glyph strokes) in render space:
    [(fingerprint, x0,y0,x1,y1)]. Fingerprint is SCALE-INVARIANT shape:
    coordinates are normalized by the path's own size before quantizing, so
    the same letter at schematic size and title-block size shares one
    signature (v1 kept absolute pt -> 265 fragmented signatures for a ~40
    char font; jitter + font sizes split the vote pools)."""
    R = page.rotation_matrix
    out = []
    for d in page.get_drawings():
        raw = []
        xs, ys = [], []
        for it in d["items"]:
            pts = [((fitz.Point(x, y) * R).x, (fitz.Point(x, y) * R).y)
                   for (x, y) in _pts(it)]
            if not pts:
                continue
            raw.append((it[0], pts))
            xs += [p[0] for p in pts]
            ys += [p[1] for p in pts]
        if not raw or not xs:
            continue
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        if max(w, h) >= 7.5 or max(w, h) < 0.05:    # glyph-sized only
            continue
        scale = max(w, h, 0.15)
        ox, oy = min(xs), min(ys)
        sig = tuple((op,) + tuple((round((x - ox) / scale, 1) + 0.0,
                                   round((y - oy) / scale, 1) + 0.0)
                                  for (x, y) in pts)
                    for op, pts in raw)
        # aspect bucket keeps '-' distinct from '|' after scale-norm
        aspect = round(min(w, h) / scale, 1)
        out.append((stable_hash((sig, aspect)), min(xs), min(ys), max(xs), max(ys)))
    return out


def chars_of_label(glyphs, bbox, pad=1.2):
    """Group the glyph paths inside a label bbox into CHARACTER clusters
    (left->right). A char may be several paths ('i', '=', '%'); paths whose
    x-ranges overlap or nearly touch belong to one char. EDGE-JUNK FILTER:
    wire stubs / terminal-box edges crossing the label bbox are not text —
    tesseract reads them as '-', ']', '}' (its hallucinated punctuation);
    a glyph much taller than the text line is dropped."""
    x0, y0, x1, y1 = bbox
    line_h = max(0.8, y1 - y0)
    # membership by CENTER inside the padded box: full-containment dropped
    # any char whose stroke poked past the bbox ('MPCS'->'PCS', 'T/S'->'TS',
    # 'STBD'->'STB' — chars silently vanishing at the edges)
    inside = []
    for g in glyphs:
        cx, cy = (g[1] + g[3]) / 2, (g[2] + g[4]) / 2
        # 1.9x: '/' legitimately overshoots the line (measured 1.53x on
        # 'T/S'); real wire stubs are >=4pt lines and never enter the glyph
        # pool in the first place, so this filter only guards box edges.
        if (x0 - pad <= cx <= x1 + pad and y0 - pad <= cy <= y1 + pad
                and (g[4] - g[2]) <= 1.9 * line_h):
            inside.append(g)
    if not inside:
        return []
    gap_thr = max(0.3, 0.16 * line_h)
    inside.sort(key=lambda g: g[1])
    chars = []
    cur = [inside[0]]
    cur_max = inside[0][3]
    for g in inside[1:]:
        if g[1] > cur_max + gap_thr:
            chars.append(cur)
            cur = [g]
            cur_max = g[3]
        else:
            cur.append(g)
            cur_max = max(cur_max, g[3])
    chars.append(cur)
    out = []
    for c in chars:
        cx0 = min(g[1] for g in c); cx1 = max(g[3] for g in c)
        cy0 = min(g[2] for g in c); cy1 = max(g[4] for g in c)
        ch = max(cy1 - cy0, cx1 - cx0, 0.3)
        # signature includes each path's RELATIVE OFFSET inside the char —
        # without it 'T' and '+' (both {h-bar, v-stem}) hash identically
        fps = tuple(sorted((g[0], round((g[1] - cx0) / ch, 1) + 0.0,
                            round((g[2] - cy0) / ch, 1) + 0.0) for g in c))
        out.append({"sig": stable_hash(fps), "x0": cx0, "x1": cx1, "n_paths": len(c)})
    return out


def learn(doc, run_dir, train_pages):
    votes = defaultdict(Counter)
    aligned = skipped = 0
    for pno in train_pages:
        pf = run_dir / f"p{pno}.json"
        if not pf.exists():
            continue
        rec = json.loads(pf.read_text())
        glyphs = page_glyphs(doc[pno])
        for lab in rec["labels"]:
            if lab.get("vertical") or lab.get("conf", 0) < TRAIN_CONF:
                continue
            text = (lab.get("text") or "").replace(" ", "")
            if not text:
                continue
            chars = chars_of_label(glyphs, lab["bbox"])
            if len(chars) != len(text):
                skipped += 1
                continue                       # never force-align
            aligned += 1
            for ch, t in zip(chars, text):
                votes[ch["sig"]][t] += 1
    table = {}
    for sig, cnt in votes.items():
        ch, n = cnt.most_common(1)[0]
        if n >= MIN_VOTES and n / sum(cnt.values()) >= MAJORITY:
            table[sig] = ch
    return table, aligned, skipped


def decode_label(glyphs, lab, table):
    chars = chars_of_label(glyphs, lab["bbox"])
    if not chars:
        return None, 0, 0
    gaps = [b["x0"] - a["x1"] for a, b in zip(chars, chars[1:])]
    med = sorted(gaps)[len(gaps) // 2] if gaps else 0.0
    out = []
    unknown = 0
    for i, c in enumerate(chars):
        if i and med > 0 and (c["x0"] - chars[i - 1]["x1"]) > SPACE_FACTOR * max(med, 0.3):
            out.append(" ")
        ch = table.get(c["sig"])
        if ch is None:
            out.append("?")
            unknown += 1
        else:
            out.append(ch)
    return "".join(out), len(chars), unknown


def main(argv):
    pdf_path, run_dir, out_dir = argv[0], Path(argv[1]), Path(argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    all_pages = sorted(int(q.stem[1:]) for q in run_dir.glob("p*.json")
                       if q.stem[1:].isdigit())
    train_pages = [p for p in all_pages if p % 2 == 0]
    test_pages = [p for p in all_pages if p % 2 == 1]
    table, aligned, skipped = learn(doc, run_dir, train_pages)
    print(f"TRAIN (even pages): {aligned} labels aligned, {skipped} skipped "
          f"(count mismatch, never forced) -> font table {len(table)} signatures")
    # PER-HOUSE FONT REUSE: a previously learned table for this drafting house
    # extends today's (today's votes win on conflict). This is what makes the
    # font a durable asset instead of a per-run throwaway — and it is only
    # possible now that fingerprints are cross-process stable.
    if "--font-table" in argv:
        ft = Path(argv[argv.index("--font-table") + 1])
        if ft.exists():
            prior = json.loads(ft.read_text())
            merged = dict(prior)
            merged.update(table)
            print(f"  merged prior house font {ft.name}: {len(prior)} + "
                  f"{len(table)} -> {len(merged)} signatures")
            table = merged

    # OUT-OF-SAMPLE test: odd pages, high-conf tesseract as reference
    agree = differ = 0
    diffs = []
    stats = Counter()
    for pno in all_pages:
        pf = run_dir / f"p{pno}.json"
        rec = json.loads(pf.read_text())
        glyphs = page_glyphs(doc[pno])
        for lab in rec["labels"]:
            if lab.get("vertical"):
                stats["vertical_skipped"] += 1
                continue
            decoded, n_chars, unknown = decode_label(glyphs, lab, table)
            if decoded is None:
                stats["no_glyphs"] += 1
                continue
            full = unknown == 0 and n_chars > 0
            stats["full_decode" if full else "partial_decode"] += 1
            lab["decoded"] = decoded
            lab["decode_full"] = full
            if full:
                lab["text_final"] = decoded
                lab["conf_final"] = 99.0
            else:
                lab["text_final"] = lab.get("text", "")
                lab["conf_final"] = lab.get("conf", 0)
            if (pno in test_pages and full
                    and lab.get("conf", 0) >= TRAIN_CONF
                    and not lab.get("vertical")):
                a = (lab.get("text") or "").replace(" ", "")
                b = decoded.replace(" ", "")
                if a == b:
                    agree += 1
                else:
                    differ += 1
                    if len(diffs) < 40:
                        diffs.append({"page": pno, "tesseract": lab.get("text"),
                                      "decoded": decoded})
        (out_dir / f"p{pno}.json").write_text(json.dumps(rec))
    total_ht = agree + differ
    print(f"OUT-OF-SAMPLE (odd pages, vs tesseract conf>={TRAIN_CONF:.0f}): "
          f"{agree}/{total_ht} exact agreement "
          f"({100 * agree / max(1, total_ht):.1f}%)")
    print(f"decode coverage all pages: {dict(stats)}")
    report = {"font_signatures": len(table), "train_aligned": aligned,
              "train_skipped": skipped,
              "oos_agree": agree, "oos_differ": differ,
              "oos_agreement_pct": round(100 * agree / max(1, total_ht), 1),
              "coverage": dict(stats), "sample_disagreements": diffs}
    (out_dir / "decode_report.json").write_text(json.dumps(report, indent=1))
    (out_dir / "font_table.json").write_text(json.dumps(
        {str(k): v for k, v in table.items()}, indent=0))
    print(f"-> {out_dir}/decode_report.json, font_table.json")


if __name__ == "__main__":
    main(sys.argv[1:])
