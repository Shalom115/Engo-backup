"""
SYMBOL BANK WORKSHEET — turns a symbol_bank_build.py DRAFT + its source PDF
into a FILLABLE HTML red-pen (real crops, a text input per symbol, local
save, export to .txt) instead of a flat contact-sheet PNG the engineer can't
write on. One generator, reusable for every drafting house's bank (GM
electrical done; P&ID / hydraulic / BAE banks use the same tool unchanged).

    python tools/symbol_bank_worksheet.py <book.pdf> <symbol_bank_DRAFT.json> <out.html> \
        [--title "..."] [--eyebrow "..."] [--vocab breaker,fuse,relay_NO,...]

Self-contained output (crops embedded as base64 PNG, no external requests) —
publish directly as an HTML Artifact. Answers persist in the browser's
localStorage AND export via Copy/Download as `#id <TAB> type [<TAB> # note]`
lines — that format is what a future symbol_bank_apply.py reads back to
write engineer_type into the bank JSON.
"""
import argparse
import base64
import io
import json
import re
import sys
from pathlib import Path

_BARE_AMP = re.compile(r"&(?!(?:[a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);)")


def _esc(s: str) -> str:
    """Escape bare '&' for safe HTML text-node insertion, without double-
    escaping a caller who already wrote a real entity (&mdash; etc.) —
    v1 of this tool blindly did .replace('&','&amp;') and mangled any
    entity in a custom --title/--eyebrow into '&amp;mdash;' (visible
    literal text instead of the glyph). Caught before this tool's first
    reuse for the P&ID/hydraulic banks."""
    return _BARE_AMP.sub("&amp;", s)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fitz
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

DEFAULT_VOCAB = [
    "breaker", "emergency_breaker", "fuse", "retractable_fuse",
    "relay_NO", "relay_NC", "relay_changeover", "terminal", "terminal_strip_cell",
    "switch", "selector_switch", "pushbutton", "lamp_indicator",
    "current_transformer", "shunt", "earth_leak_breaker", "earth_ground",
    "meter_gauge", "motor", "solenoid_valve", "plug_pin", "connector",
    "wire_gauge_diamond", "junction_dot", "not_a_device", "other",
]


def render_crops(pdf_path, bank_path, ctx_pad_pt=10.0, zoom=8.0, cell=(260, 200)):
    doc = fitz.open(pdf_path)
    bank = json.load(open(bank_path))
    page_cache = {}

    def render_crop(pno, bbox):
        if pno not in page_cache:
            page = doc[pno]
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            page_cache.clear()
            page_cache[pno] = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        img = page_cache[pno]
        x0, y0, x1, y1 = bbox
        crop = img.crop((
            int((x0 - ctx_pad_pt) * zoom), int((y0 - ctx_pad_pt) * zoom),
            int((x1 + ctx_pad_pt) * zoom), int((y1 + ctx_pad_pt) * zoom),
        ))
        crop.thumbnail(cell)
        canvas = Image.new("RGB", cell, (255, 255, 255))
        ox, oy = (cell[0] - crop.width) // 2, (cell[1] - crop.height) // 2
        canvas.paste(crop, (ox, oy))
        buf = io.BytesIO()
        canvas.save(buf, "PNG", optimize=True)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    out = []
    for c in bank["clusters"]:
        ex = c["example"]
        out.append({"id": c["cluster"], "instances": c["instances"],
                    "pages": c["pages"], "page0": ex["page"],
                    "img": render_crop(ex["page"], ex["bbox"])})
    return out


def build(pdf_path, bank_path, out_path, title=None, eyebrow=None, vocab=None):
    crops = render_crops(pdf_path, bank_path)
    crops.sort(key=lambda c: c["id"])
    data_json = json.dumps(crops, separators=(",", ":"))
    VOCAB = vocab or DEFAULT_VOCAB

    html = _TEMPLATE
    html = html.replace("__DATA_JSON__", data_json)
    html = html.replace("__VOCAB_JSON__", json.dumps(VOCAB))
    html = html.replace("__TOTAL__", str(len(crops)))
    if title:
        html = html.replace(
            "Symbol Bank Red-Pen &mdash; SW108-01 GM Electrical Book",
            _esc(title))
    if eyebrow:
        html = html.replace(
            'DWG&nbsp;SW108-01-600</span><span>&middot;</span>'
            '<span>GM MARINE SERVICES &mdash; ELECTRICAL SCHEMATICS, 06 OCT 2023'
            '</span><span>&middot;</span><span>43 PAGES',
            _esc(eyebrow))

    Path(out_path).write_text(html)
    print(f"written: {out_path}  bytes={len(html)}  symbols={len(crops)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("bank_json")
    ap.add_argument("out")
    ap.add_argument("--title", default=None)
    ap.add_argument("--eyebrow", default=None)
    ap.add_argument("--vocab", default=None,
                    help="comma-separated, overrides the default IEC-ish vocabulary")
    args = ap.parse_args()
    vocab = args.vocab.split(",") if args.vocab else None
    build(args.pdf, args.bank_json, args.out,
         title=args.title, eyebrow=args.eyebrow, vocab=vocab)


_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Symbol Bank Red-Pen &mdash; SW108-01 GM Electrical Book</title>
<style>
:root {
  --navy-950: #0b1420;
  --navy-900: #101c29;
  --navy-800: #16232f;
  --navy-700: #223342;
  --steel-100: #eef1f2;
  --steel-200: #e2e8ea;
  --steel-300: #ccd6d9;
  --steel-500: #7c8b92;
  --steel-600: #5c6b73;
  --ink: #101c29;
  --paper: #ffffff;
  --ground: var(--steel-100);
  --panel: var(--paper);
  --border: var(--steel-300);
  --caption: var(--steel-600);
  --pen-red: #c23b2e;
  --pen-red-dim: #c23b2e33;
  --ok-green: #3e7a5c;
  --ok-green-dim: #3e7a5c1f;
  --focus-ring: #c23b2e66;
  --mono: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, "Roboto Mono", monospace;
  --sans: -apple-system, "Segoe UI", system-ui, "Helvetica Neue", Arial, sans-serif;
  --radius: 3px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --ink: #e7ecee;
    --paper: var(--navy-800);
    --ground: var(--navy-950);
    --panel: var(--navy-900);
    --border: var(--navy-700);
    --caption: #8ea0aa;
    --pen-red: #e35a4a;
    --pen-red-dim: #e35a4a2e;
    --ok-green: #5fae87;
    --ok-green-dim: #5fae871f;
    --focus-ring: #e35a4a66;
  }
}
:root[data-theme="dark"] {
  --ink: #e7ecee;
  --paper: var(--navy-800);
  --ground: var(--navy-950);
  --panel: var(--navy-900);
  --border: var(--navy-700);
  --caption: #8ea0aa;
  --pen-red: #e35a4a;
  --pen-red-dim: #e35a4a2e;
  --ok-green: #5fae87;
  --ok-green-dim: #5fae871f;
  --focus-ring: #e35a4a66;
}
:root[data-theme="light"] {
  --ink: #101c29;
  --paper: #ffffff;
  --ground: var(--steel-100);
  --panel: var(--paper);
  --border: var(--steel-300);
  --caption: var(--steel-600);
  --pen-red: #c23b2e;
  --pen-red-dim: #c23b2e33;
  --ok-green: #3e7a5c;
  --ok-green-dim: #3e7a5c1f;
  --focus-ring: #c23b2e66;
}
* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0;
  background: var(--ground);
  color: var(--ink);
  font-family: var(--sans);
  -webkit-font-smoothing: antialiased;
}
body { min-height: 100vh; padding-bottom: 4rem; }
::selection { background: var(--pen-red-dim); }
a { color: var(--pen-red); }

.masthead {
  padding: 2rem clamp(1rem, 4vw, 2.5rem) 1.25rem;
  border-bottom: 1px solid var(--border);
  background:
    linear-gradient(180deg, transparent 0%, transparent 100%),
    repeating-linear-gradient(0deg, transparent, transparent 27px, var(--border) 27px, var(--border) 28px);
  background-size: 100% 100%, 100% 28px;
  background-repeat: no-repeat, repeat-y;
  opacity: 1;
}
.masthead-inner { max-width: 74rem; margin: 0 auto; }
.eyebrow {
  font-family: var(--mono);
  font-size: 0.72rem;
  letter-spacing: 0.11em;
  text-transform: uppercase;
  color: var(--caption);
  display: flex;
  gap: 0.6em;
  align-items: baseline;
}
.eyebrow .dwg { color: var(--pen-red); }
h1 {
  font-size: clamp(1.5rem, 2.6vw, 2.05rem);
  line-height: 1.15;
  letter-spacing: -0.01em;
  margin: 0.35em 0 0.4em;
  text-wrap: balance;
  font-weight: 650;
}
.dek {
  max-width: 46rem;
  color: var(--caption);
  font-size: 0.98rem;
  line-height: 1.55;
  margin: 0 0 0.2em;
}
.dek strong { color: var(--ink); font-weight: 600; }

.toolbar {
  position: sticky; top: 0; z-index: 30;
  background: color-mix(in srgb, var(--ground) 88%, transparent);
  backdrop-filter: blur(8px) saturate(1.1);
  -webkit-backdrop-filter: blur(8px) saturate(1.1);
  border-bottom: 1px solid var(--border);
  padding: 0.7rem clamp(1rem, 4vw, 2.5rem);
}
.toolbar-inner {
  max-width: 74rem; margin: 0 auto;
  display: flex; flex-wrap: wrap; align-items: center; gap: 0.9rem;
}
.progress-wrap {
  display: flex; align-items: center; gap: 0.6rem;
  font-family: var(--mono); font-size: 0.82rem; color: var(--caption);
  white-space: nowrap;
}
.progress-wrap b { color: var(--ink); font-variant-numeric: tabular-nums; }
.progress-bar {
  width: 108px; height: 6px; border-radius: 3px;
  background: var(--border); overflow: hidden; flex-shrink: 0;
}
.progress-fill {
  height: 100%; width: 0%;
  background: var(--ok-green);
  transition: width 0.25s ease;
}
.search-wrap { flex: 1 1 220px; min-width: 160px; }
#search {
  width: 100%; padding: 0.5rem 0.75rem;
  border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--panel); color: var(--ink);
  font-family: var(--sans); font-size: 0.88rem;
}
#search:focus { outline: none; border-color: var(--pen-red); box-shadow: 0 0 0 3px var(--focus-ring); }
.filter-chip {
  font-family: var(--mono); font-size: 0.76rem; letter-spacing: 0.02em;
  padding: 0.4rem 0.65rem; border-radius: var(--radius);
  border: 1px solid var(--border); background: var(--panel); color: var(--caption);
  cursor: pointer; user-select: none; white-space: nowrap;
}
.filter-chip[aria-pressed="true"] { color: var(--pen-red); border-color: var(--pen-red); background: var(--pen-red-dim); }
.filter-chip:hover { border-color: var(--pen-red); }
.btn-row { display: flex; gap: 0.5rem; margin-left: auto; }
.btn {
  font-family: var(--sans); font-size: 0.84rem; font-weight: 550;
  padding: 0.5rem 0.85rem; border-radius: var(--radius);
  border: 1px solid var(--border); background: var(--panel); color: var(--ink);
  cursor: pointer; white-space: nowrap;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.btn:hover { border-color: var(--pen-red); }
.btn:focus-visible { outline: 2px solid var(--pen-red); outline-offset: 1px; }
.btn.primary { background: var(--pen-red); border-color: var(--pen-red); color: #fff; }
.btn.primary:hover { filter: brightness(1.08); }
.btn.ghost { color: var(--caption); }
.toast {
  position: fixed; bottom: 1.25rem; left: 50%; transform: translateX(-50%) translateY(8px);
  background: var(--ink); color: var(--ground);
  padding: 0.55rem 1rem; border-radius: var(--radius);
  font-size: 0.85rem; font-family: var(--sans);
  opacity: 0; pointer-events: none; transition: opacity 0.2s ease, transform 0.2s ease;
  z-index: 50;
}
.toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }

.export-panel {
  position: sticky; top: 3.6rem; z-index: 25;
  background: var(--panel);
  border-bottom: 2px solid var(--pen-red);
  box-shadow: 0 8px 24px -12px rgba(0,0,0,0.35);
}
.export-panel[hidden] { display: none; }
.export-panel-inner {
  max-width: 74rem; margin: 0 auto;
  padding: 1rem clamp(1rem, 4vw, 2.5rem) 1.2rem;
  display: flex; flex-direction: column; gap: 0.6rem;
}
.export-head {
  display: flex; align-items: baseline; justify-content: space-between;
  font-size: 0.95rem;
}
.export-help {
  margin: 0; color: var(--caption); font-size: 0.85rem; line-height: 1.5;
  max-width: 52rem;
}
#export-text {
  width: 100%; min-height: 9rem;
  font-family: var(--mono); font-size: 0.82rem; line-height: 1.5;
  padding: 0.75rem; border-radius: var(--radius);
  border: 1.5px solid var(--border); background: var(--ground); color: var(--ink);
  resize: vertical;
}
#export-text:focus { outline: none; border-color: var(--pen-red); box-shadow: 0 0 0 3px var(--focus-ring); }
.export-actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.export-status {
  margin: 0; font-size: 0.82rem; color: var(--ok-green); min-height: 1.2em;
  font-family: var(--mono);
}
.export-status.error { color: var(--pen-red); }

main { max-width: 74rem; margin: 0 auto; padding: 0 clamp(1rem, 4vw, 2.5rem); }

.sheet-nav {
  display: flex; gap: 0.4rem; flex-wrap: wrap;
  padding: 1.1rem 0 0.3rem;
  font-family: var(--mono); font-size: 0.78rem;
}
.sheet-nav a {
  text-decoration: none; color: var(--caption);
  border: 1px solid var(--border); border-radius: var(--radius);
  padding: 0.3rem 0.6rem;
}
.sheet-nav a:hover { color: var(--pen-red); border-color: var(--pen-red); }

.sheet-heading {
  display: flex; align-items: baseline; gap: 0.7rem;
  padding: 1.6rem 0 0.9rem;
  border-top: 1px solid var(--border);
  margin-top: 1.4rem;
  scroll-margin-top: 5rem;
}
.sheet-heading:first-of-type { border-top: none; margin-top: 0.4rem; }
.sheet-heading h2 {
  font-size: 1.05rem; margin: 0; font-weight: 650; letter-spacing: -0.005em;
}
.sheet-heading .range {
  font-family: var(--mono); font-size: 0.76rem; color: var(--caption);
  letter-spacing: 0.03em;
}
.sheet-count {
  margin-left: auto; font-family: var(--mono); font-size: 0.76rem; color: var(--caption);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(215px, 1fr));
  gap: 0.85rem;
  padding-bottom: 0.5rem;
}

.card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.6rem 0.6rem 0.7rem;
  display: flex; flex-direction: column; gap: 0.5rem;
  transition: border-color 0.15s ease;
  scroll-margin-top: 5rem;
}
.card.answered { border-color: var(--ok-green); }
.card.dimmed { opacity: 0.28; }

.card-meta {
  display: flex; align-items: baseline; justify-content: space-between;
  font-family: var(--mono); font-size: 0.72rem; color: var(--caption);
  letter-spacing: 0.01em;
}
.card-meta .cid { color: var(--ink); font-weight: 600; }
.card-meta .cid::before { content: "#"; color: var(--caption); font-weight: 400; }

.card-figure {
  background: var(--steel-100);
  border: 1px solid var(--border);
  border-radius: 2px;
  display: flex; align-items: center; justify-content: center;
  aspect-ratio: 260 / 200;
  overflow: hidden;
}
:root[data-theme="dark"] .card-figure,
@media (prefers-color-scheme: dark) { .card-figure { background: #eceff0; } }
.card-figure img { width: 100%; height: 100%; object-fit: contain; display: block; }

.card-src {
  font-family: var(--mono); font-size: 0.68rem; color: var(--steel-500);
}

.card-input-wrap { position: relative; }
.type-input {
  width: 100%;
  font-family: var(--mono); font-size: 0.86rem;
  padding: 0.35rem 0.1rem 0.3rem;
  background: transparent; color: var(--ink);
  border: none; border-bottom: 1.5px dashed var(--steel-500);
  border-radius: 0;
}
.type-input::placeholder { color: var(--steel-500); font-family: var(--sans); font-style: italic; }
.type-input:focus {
  outline: none; border-bottom-style: solid; border-bottom-color: var(--pen-red);
  box-shadow: 0 1px 0 0 var(--pen-red);
}
.type-input:not(:placeholder-shown) { border-bottom-style: solid; border-bottom-color: var(--ok-green); color: var(--ok-green); font-weight: 600; }
.type-input:focus:not(:placeholder-shown) { color: var(--ink); border-bottom-color: var(--pen-red); }

datalist { display: none; }

.note-toggle {
  font-family: var(--sans); font-size: 0.72rem; color: var(--steel-500);
  background: none; border: none; cursor: pointer; padding: 0; text-align: left;
  text-decoration: underline; text-decoration-style: dotted; text-underline-offset: 2px;
}
.note-toggle:hover { color: var(--pen-red); }
.note-input {
  width: 100%; font-family: var(--sans); font-size: 0.78rem;
  color: var(--caption); background: transparent;
  border: 1px dashed var(--border); border-radius: 2px;
  padding: 0.35rem 0.4rem; resize: vertical; min-height: 2.2rem;
  display: none;
}
.note-input.open { display: block; }
.note-input:focus { outline: none; border-color: var(--pen-red); color: var(--ink); }

footer {
  max-width: 74rem; margin: 2.5rem auto 0; padding: 1.2rem clamp(1rem, 4vw, 2.5rem) 0;
  border-top: 1px solid var(--border);
  font-family: var(--mono); font-size: 0.74rem; color: var(--steel-500);
  display: flex; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;
}

@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; }
}
</style>
</head>
<body>

<div class="masthead">
  <div class="masthead-inner">
    <div class="eyebrow"><span class="dwg">DWG&nbsp;SW108-01-600</span><span>&middot;</span><span>GM MARINE SERVICES &mdash; ELECTRICAL SCHEMATICS, 06 OCT 2023</span><span>&middot;</span><span>43 PAGES</span></div>
    <h1>Symbol bank red-pen</h1>
    <p class="dek">Each card below is <strong>one repeated shape</strong>, pulled once from the book &mdash; not each of its instances. A breaker symbol looks the same on every sheet, so naming it once here types <strong>every occurrence across all 43 pages</strong>. Type the device into the field under each image (breaker, fuse, relay NO/NC, terminal, switch&hellip;) &mdash; whatever's fastest. Leave anything uncertain blank.</p>
  </div>
</div>

<div class="toolbar">
  <div class="toolbar-inner">
    <div class="progress-wrap">
      <span>ANSWERED</span><b id="prog-count">0 / __TOTAL__</b>
      <div class="progress-bar"><div class="progress-fill" id="prog-fill"></div></div>
    </div>
    <div class="search-wrap"><input id="search" type="text" placeholder="Filter by symbol #, page, or your own text&hellip;" autocomplete="off"></div>
    <button class="filter-chip" id="filter-unanswered" aria-pressed="false" type="button">Unanswered only</button>
    <div class="btn-row">
      <button class="btn ghost" id="clear-all" type="button">Clear all</button>
      <button class="btn primary" id="open-export" type="button">Export answers</button>
    </div>
  </div>
</div>

<div class="export-panel" id="export-panel" hidden>
  <div class="export-panel-inner">
    <div class="export-head">
      <strong>Export &mdash; <span id="export-count">0</span> answered</strong>
      <button class="btn ghost" id="close-export" type="button">Close</button>
    </div>
    <p class="export-help">Tap inside the box below, select all (long-press &rarr; Select All, or Cmd/Ctrl+A), then copy (Cmd/Ctrl+C) and paste it back into the chat. This always works, even when the buttons below don't &mdash; some browsers block automatic copy/download inside this page.</p>
    <textarea id="export-text" readonly rows="10" spellcheck="false"></textarea>
    <div class="export-actions">
      <button class="btn" id="select-all-export" type="button">Select all text</button>
      <button class="btn" id="copy-answers" type="button">Try copy button</button>
      <button class="btn" id="download-answers" type="button">Try download</button>
    </div>
    <p class="export-status" id="export-status"></p>
  </div>
</div>

<main>
  <nav class="sheet-nav">
    <a href="#sheet-0">Sheet 1 &middot; #0&ndash;47</a>
    <a href="#sheet-1">Sheet 2 &middot; #48&ndash;95</a>
    <a href="#sheet-2">Sheet 3 &middot; #96&ndash;135</a>
  </nav>
  <div id="sheets"></div>
</main>

<footer>
  <span>SY GELLICEAUX &middot; ENGO SCHEMATIC INGESTION</span>
  <span id="footer-progress">0 of __TOTAL__ answered</span>
</footer>

<div class="toast" id="toast"></div>

<script id="crop-data" type="application/json">__DATA_JSON__</script>
<script>
(function () {
  "use strict";
  var CROPS = JSON.parse(document.getElementById("crop-data").textContent);
  var STORE_KEY = "engo-symbol-bank-redpen-v2";
  var VOCAB = __VOCAB_JSON__;

  var answers = {};
  try {
    var saved = JSON.parse(localStorage.getItem(STORE_KEY) || "{}");
    if (saved && typeof saved === "object") answers = saved;
  } catch (e) {}

  function save() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(answers)); } catch (e) {}
  }

  var SHEET_SIZE = 48;
  var sheets = [[], [], []];
  CROPS.forEach(function (c) {
    var s = Math.min(2, Math.floor(c.id / SHEET_SIZE));
    sheets[s].push(c);
  });

  var datalistHTML = '<datalist id="vocab-list">' +
    VOCAB.map(function (v) { return '<option value="' + v + '">'; }).join("") +
    "</datalist>";

  var sheetsRoot = document.getElementById("sheets");
  var html = datalistHTML;

  sheets.forEach(function (items, si) {
    if (!items.length) return;
    var lo = items[0].id, hi = items[items.length - 1].id;
    html += '<section class="sheet-heading" id="sheet-' + si + '">' +
      "<h2>Sheet " + (si + 1) + "</h2>" +
      '<span class="range">#' + lo + "&ndash;" + hi + "</span>" +
      '<span class="sheet-count">' + items.length + " symbols</span>" +
      "</section>";
    html += '<div class="grid" data-sheet="' + si + '">';
    items.forEach(function (c) {
      var pages = c.pages.slice(0, 4).map(function (p) { return "p" + p; }).join(" ");
      var more = c.pages.length > 4 ? " +" + (c.pages.length - 4) : "";
      html += '<div class="card" id="card-' + c.id + '" data-id="' + c.id + '" ' +
        'data-search="' + c.id + " p" + c.page0 + " " + c.pages.map(function(p){return "p"+p;}).join(" ") + '">' +
        '<div class="card-meta"><span class="cid">' + c.id + "</span>" +
        "<span>&times;" + c.instances + "</span></div>" +
        '<div class="card-figure"><img loading="lazy" src="data:image/png;base64,' + c.img + '" alt="symbol ' + c.id + '"></div>' +
        '<div class="card-src">' + pages + more + "</div>" +
        '<div class="card-input-wrap"><input class="type-input" list="vocab-list" data-id="' + c.id + '" placeholder="type&hellip;" autocomplete="off" spellcheck="false"></div>' +
        '<button class="note-toggle" data-id="' + c.id + '" type="button">+ note</button>' +
        '<textarea class="note-input" data-id="' + c.id + '" placeholder="optional note" rows="2"></textarea>' +
        "</div>";
    });
    html += "</div>";
  });

  sheetsRoot.innerHTML = html;

  var total = CROPS.length;
  var progCount = document.getElementById("prog-count");
  var progFill = document.getElementById("prog-fill");
  var footerProgress = document.getElementById("footer-progress");

  function answeredCount() {
    var n = 0;
    for (var k in answers) { if (answers[k] && answers[k].type) n++; }
    return n;
  }

  function updateProgress() {
    var n = answeredCount();
    progCount.innerHTML = n + " / " + total;
    progFill.style.width = (total ? (100 * n / total) : 0) + "%";
    footerProgress.textContent = n + " of " + total + " answered";
  }

  function applySavedToDOM() {
    document.querySelectorAll(".type-input").forEach(function (inp) {
      var id = inp.getAttribute("data-id");
      var a = answers[id];
      if (a && a.type) {
        inp.value = a.type;
        inp.closest(".card").classList.add("answered");
      }
    });
    document.querySelectorAll(".note-input").forEach(function (ta) {
      var id = ta.getAttribute("data-id");
      var a = answers[id];
      if (a && a.note) {
        ta.value = a.note;
        ta.classList.add("open");
        var btn = document.querySelector('.note-toggle[data-id="' + id + '"]');
        if (btn) btn.textContent = "− note";
      }
    });
  }
  applySavedToDOM();
  updateProgress();

  sheetsRoot.addEventListener("input", function (e) {
    if (e.target.classList.contains("type-input")) {
      var id = e.target.getAttribute("data-id");
      var v = e.target.value.trim();
      answers[id] = answers[id] || {};
      answers[id].type = v;
      e.target.closest(".card").classList.toggle("answered", !!v);
      save();
      updateProgress();
    } else if (e.target.classList.contains("note-input")) {
      var nid = e.target.getAttribute("data-id");
      answers[nid] = answers[nid] || {};
      answers[nid].note = e.target.value;
      save();
    }
  });

  sheetsRoot.addEventListener("click", function (e) {
    if (e.target.classList.contains("note-toggle")) {
      var id = e.target.getAttribute("data-id");
      var ta = document.querySelector('.note-input[data-id="' + id + '"]');
      var isOpen = ta.classList.toggle("open");
      e.target.textContent = (isOpen ? "−" : "+") + " note";
      if (isOpen) ta.focus();
    }
  });

  // search / filter
  var searchInput = document.getElementById("search");
  var filterBtn = document.getElementById("filter-unanswered");
  var unansweredOnly = false;

  function applyFilter() {
    var q = searchInput.value.trim().toLowerCase();
    document.querySelectorAll(".card").forEach(function (card) {
      var id = card.getAttribute("data-id");
      var hay = card.getAttribute("data-search") + " " + ((answers[id] && answers[id].type) || "");
      var matchesQ = !q || hay.toLowerCase().indexOf(q) !== -1;
      var isAnswered = !!(answers[id] && answers[id].type);
      var matchesFilter = !unansweredOnly || !isAnswered;
      card.classList.toggle("dimmed", !(matchesQ && matchesFilter));
    });
  }
  searchInput.addEventListener("input", applyFilter);
  filterBtn.addEventListener("click", function () {
    unansweredOnly = !unansweredOnly;
    filterBtn.setAttribute("aria-pressed", String(unansweredOnly));
    filterBtn.textContent = unansweredOnly ? "Showing unanswered" : "Unanswered only";
    applyFilter();
  });

  // toast
  var toastEl = document.getElementById("toast");
  var toastTimer = null;
  function toast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove("show"); }, 1800);
  }

  function buildExportText() {
    var lines = [];
    lines.push("# Symbol bank red-pen — SW108-01-600 GM Marine electrical schematics");
    lines.push("# " + answeredCount() + " / " + total + " answered");
    lines.push("# format: #id  type  [note]");
    lines.push("");
    CROPS.forEach(function (c) {
      var a = answers[c.id];
      if (!a || !a.type) return;
      var line = "#" + c.id + "\t" + a.type;
      if (a.note) line += "\t# " + a.note;
      lines.push(line);
    });
    return lines.join("\n");
  }

  // EXPORT PANEL — this environment can silently block navigator.clipboard
  // and programmatic <a download> (sandboxed iframe permissions vary by
  // browser/host and fail with no error the page can detect), so the
  // GUARANTEED path is a visible, pre-selected <textarea>: native OS
  // select-all + copy always works because it isn't going through any JS
  // API that can be sandboxed. The buttons below are best-effort extras,
  // not the primary path.
  var exportPanel = document.getElementById("export-panel");
  var exportText = document.getElementById("export-text");
  var exportCount = document.getElementById("export-count");
  var exportStatus = document.getElementById("export-status");

  function setStatus(msg, isError) {
    exportStatus.textContent = msg;
    exportStatus.classList.toggle("error", !!isError);
  }

  function openExport() {
    var text = buildExportText();
    exportText.value = text;
    exportCount.textContent = String(answeredCount());
    exportPanel.hidden = false;
    setStatus("");
    exportPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    setTimeout(function () {
      exportText.focus();
      exportText.select();
    }, 50);
  }

  document.getElementById("open-export").addEventListener("click", openExport);
  document.getElementById("close-export").addEventListener("click", function () {
    exportPanel.hidden = true;
  });

  document.getElementById("select-all-export").addEventListener("click", function () {
    exportText.focus();
    exportText.select();
    setStatus("Text selected — press Cmd/Ctrl+C to copy it.");
  });

  document.getElementById("copy-answers").addEventListener("click", function () {
    exportText.focus();
    exportText.select();
    var text = exportText.value;
    var done = false;
    try {
      done = document.execCommand && document.execCommand("copy");
    } catch (e) { done = false; }
    if (done) {
      toast("Copied " + answeredCount() + " answers");
      setStatus("Copied to clipboard.");
      return;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        toast("Copied " + answeredCount() + " answers");
        setStatus("Copied to clipboard.");
      }, function () {
        setStatus("Copy blocked by the browser — text is already selected above, press Cmd/Ctrl+C.", true);
      });
    } else {
      setStatus("Copy blocked by the browser — text is already selected above, press Cmd/Ctrl+C.", true);
    }
  });

  document.getElementById("download-answers").addEventListener("click", function () {
    var text = buildExportText();
    try {
      var blob = new Blob([text], { type: "text/plain" });
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = "symbol-bank-redpen-answers.txt";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
      setStatus("Download triggered — if you can't find the file, use the text box above instead.");
    } catch (e) {
      setStatus("Download blocked by the browser — select the text above and copy it instead.", true);
    }
  });

  document.getElementById("clear-all").addEventListener("click", function () {
    if (!confirm("Clear all " + answeredCount() + " answers on this device? This cannot be undone.")) return;
    answers = {};
    save();
    document.querySelectorAll(".type-input").forEach(function (i) { i.value = ""; i.closest(".card").classList.remove("answered"); });
    document.querySelectorAll(".note-input").forEach(function (t) { t.value = ""; t.classList.remove("open"); });
    document.querySelectorAll(".note-toggle").forEach(function (b) { b.textContent = "+ note"; });
    updateProgress();
    toast("Cleared");
  });
})();
</script>

</body>
</html>
"""

if __name__ == "__main__":
    main()
