"""
Multi-provider vision benchmark — Claude vs Gemini vs GPT on Engo's own sheets,
through Engo's own protocols. The routing decision mechanism: VISION_ROUTES is
set from THIS benchmark's engineer-graded results, never from leaderboard vibes.

Design (engineer-specified 2026-07-12):
  - 2 sample drawings per drawing CATEGORY (engineer picks; manifest below).
  - Each sheet runs the FULL existing loop per provider — same prompts, same
    tiling, same skeleton→detail→cross-reference protocol; only the model swaps.
  - Scoring: gold-fixture auto-diff where fixtures exist (tests/gold_fixtures_*),
    side-by-side engineer-grading report for everything else. Fabrication
    (invented values) is the heavy penalty; <UNKNOWN> honesty is credited.

Manifest: tests/vision_bench_manifest.json
  {"categories": [{"category": "...", "protocol": "...", "sheets":
      [{"name": "...", "path": "local.pdf"  OR  "drive_file_id": "...", "page": 0}]}]}

Protocols (per category):
  hydraulic   -> pipeline.schematic_extract.discover_structure (skeleton+detail tiling)
  electrical  -> pipeline.electrical_extract.extract_sheet (survey + region readers)
  describe    -> provider.describe() whole-sheet (classes with no dedicated extractor
                 yet: PLC, GA/building, photos, Class-C render test) — an honest
                 like-for-like read, not a fake extractor.

Run:
    python3 -m tests.vision_bench --providers anthropic,gemini,openai
    python3 -m tests.vision_bench --only hydraulic --providers anthropic,gemini
    python3 -m tests.vision_bench --report            # rebuild report only

Kill-safe: append-only ledger data/state/vision_bench/ledger.jsonl; finished
(category, sheet, provider) runs are skipped on resume.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402

BENCH_DIR = config.STATE_DIR / "vision_bench"
LEDGER = BENCH_DIR / "ledger.jsonl"
MANIFEST = Path(__file__).parent / "vision_bench_manifest.json"
REPORT = BENCH_DIR / "vision_bench_report.md"

PROVIDERS_DEFAULT = ["anthropic", "gemini", "openai"]


# ---------------------------------------------------------------- sheet loading

SHEET_CACHE = BENCH_DIR / "sheets"


def _load_sheet_bytes(sheet: Dict[str, Any]) -> bytes:
    """Resolution order: explicit path -> local cache (pre-downloaded) ->
    drive_file_id via the read-only SA connector."""
    if sheet.get("path"):
        return Path(sheet["path"]).expanduser().read_bytes()
    for ext in (".pdf", ".PDF", ".jpg", ".jpeg", ".png"):
        cached = SHEET_CACHE / f"{sheet['name']}{ext}"
        if cached.exists():
            return cached.read_bytes()
    if sheet.get("drive_file_id"):
        from providers.structure import GoogleDriveStructureProvider
        prov = GoogleDriveStructureProvider(root_id="bench", root_name="bench")
        meta = prov.file_meta(sheet["drive_file_id"])
        data, _sfx = prov.download_bytes(meta["id"], meta["mimeType"])
        return data
    raise ValueError(f"Sheet {sheet.get('name')} has neither 'path' nor 'drive_file_id'.")


# ---------------------------------------------------------------- provider forcing

def _force_provider(vendor: str) -> None:
    """Route EVERYTHING to one vendor for this run (bench-only override)."""
    import os
    from providers import vision
    os.environ["VISION_PROVIDER"] = vendor
    os.environ["VISION_ROUTES"] = ""  # no per-class routing during the bench
    vision._PROVIDER_CACHE.clear()


# ---------------------------------------------------------------- protocols

def _run_hydraulic(pdf: bytes, page: int) -> Dict[str, Any]:
    from pipeline.schematic_extract import discover_structure
    return discover_structure(pdf, page_index=page, do_detail=True)


def _run_electrical(pdf: bytes, page: int) -> Dict[str, Any]:
    from pipeline.electrical_extract import extract_sheet
    return extract_sheet(pdf, page_index=page)


def _run_describe(pdf: bytes, page: int, kind: str) -> Dict[str, Any]:
    from providers.vision import get_vision_provider
    from pipeline import visual_extract as vx
    vp = get_vision_provider()
    if pdf[:5] == b"%PDF-":
        img = vx.rasterize_pdf_page(pdf, page, dpi=300)
    else:
        img = pdf  # already an image (photos)
    return vp.describe(img, "image/png", kind)


def _run_protocol(protocol: str, pdf: bytes, page: int) -> Dict[str, Any]:
    if protocol == "hydraulic":
        return _run_hydraulic(pdf, page)
    if protocol == "electrical":
        return _run_electrical(pdf, page)
    if protocol.startswith("describe"):
        kind = protocol.split(":", 1)[1] if ":" in protocol else "schematic"
        return _run_describe(pdf, page, kind)
    raise ValueError(f"Unknown protocol '{protocol}'.")


def _route_hydraulic(result: Dict[str, Any], sheet: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """
    FAIRNESS BY CONSTRUCTION (engineer requirement 2026-07-12): every provider's
    extraction goes through the IDENTICAL backbone — the same Register, control
    map, and §9d node-writer rules (dry-run) — and we record which node each
    provider's read routes to. No model sees the repo/Register during
    EXTRACTION (including Claude — the gold-blind prompts are identical);
    node-location happens downstream in this shared step, so the comparison is
    provider-vs-provider on reads, with routing as the common yardstick.
    """
    try:
        from pipeline.node_write import NodeWriter
        # bypass_revision_gate: bench-only (dry-run) — superseded sheets route
        # anyway so each provider's INTENDED node placement is visible side by
        # side (engineer request 2026-07-17). Real writes keep the gate.
        w = NodeWriter(dry_run=True, bypass_revision_gate=True)
        src = {"source_doc": sheet["name"], "sheet": sheet["name"],
               "source_type": "hydraulic_schematic",
               "drive_file_id": sheet.get("drive_file_id")}
        w.write_structure(result, src)
        return [{k: d.get(k) for k in ("slice", "block", "action", "target",
                                       "via", "mechanism", "confidence")
                 if d.get(k) is not None} for d in w.decisions]
    except Exception as e:  # routing is a bonus layer — never kills a bench run
        return [{"routing_error": f"{type(e).__name__}: {e}"}]


# ---------------------------------------------------------------- ledger

def _ledger_done() -> set:
    done = set()
    if LEDGER.exists():
        for line in LEDGER.read_text().splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("status") == "ok":
                done.add((r["category"], r["sheet"], r["provider"]))
    return done


def _ledger_append(rec: Dict[str, Any]) -> None:
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as f:
        f.write(json.dumps(rec, default=str) + "\n")
        f.flush()


# ---------------------------------------------------------------- run

def run_bench(providers: List[str], only: Optional[str] = None,
              sheet_filter: Optional[str] = None) -> None:
    manifest = json.loads(MANIFEST.read_text())
    done = _ledger_done()
    for cat in manifest["categories"]:
        if only and only not in cat["category"]:
            continue
        for sheet in cat["sheets"]:
            if sheet_filter and sheet_filter not in sheet.get("name", ""):
                continue
            if not (sheet.get("path") or sheet.get("drive_file_id")):
                print(f"SKIP {cat['category']}/{sheet.get('name')}: no source set "
                      f"(engineer fills the manifest)", file=sys.stderr)
                continue
            pdf = None
            for vendor in providers:
                key = (cat["category"], sheet["name"], vendor)
                if key in done:
                    print(f"done already: {key}", file=sys.stderr)
                    continue
                if pdf is None:
                    pdf = _load_sheet_bytes(sheet)
                _force_provider(vendor)
                out_dir = BENCH_DIR / cat["category"] / sheet["name"]
                out_dir.mkdir(parents=True, exist_ok=True)
                t0 = time.time()
                rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "category": cat["category"], "sheet": sheet["name"],
                       "provider": vendor, "protocol": cat["protocol"]}
                try:
                    result = _run_protocol(cat["protocol"], pdf, int(sheet.get("page", 0)))
                    if cat["protocol"] == "hydraulic":
                        result["_node_routing"] = _route_hydraulic(result, sheet)
                    rec.update(status="ok", seconds=round(time.time() - t0, 1))
                    (out_dir / f"{vendor}.json").write_text(
                        json.dumps(result, indent=2, default=str))
                except Exception as e:
                    rec.update(status="error", seconds=round(time.time() - t0, 1),
                               error=f"{type(e).__name__}: {e}",
                               trace=traceback.format_exc()[-800:])
                    print(f"ERROR {key}: {e}", file=sys.stderr)
                _ledger_append(rec)
                print(f"{rec['status']:5s} {cat['category']}/{sheet['name']} "
                      f"[{vendor}] {rec['seconds']}s", file=sys.stderr)


# ---------------------------------------------------------------- report

def _labels_of(result: Any) -> List[str]:
    """Flatten a protocol result into comparable element labels (best-effort)."""
    labels: List[str] = []
    def walk(node):
        if isinstance(node, dict):
            for k in ("label", "function", "id", "load_name", "make_model", "read"):
                v = node.get(k)
                if isinstance(v, str) and v.strip():
                    labels.append(v.strip())
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(result)
    seen, out = set(), []
    for l in labels:
        if l.lower() not in seen:
            seen.add(l.lower())
            out.append(l)
    return out


def _routing_matrix(runs: Dict[str, Any]) -> List[str]:
    """
    Side-by-side routing alignment (engineer request 2026-07-17): one row per
    element, matched across providers by intended TARGET NODE (the judgment
    that matters), cells show the label as each provider read it. Rows where
    providers disagree on target — or where a provider missed the element —
    are exactly what the engineer grades.
    """
    per_vendor: Dict[str, List[Dict[str, Any]]] = {}
    for vendor, result in runs.items():
        rows = []
        for d in result.get("_node_routing") or []:
            if "routing_error" in d or d.get("action") == "refused_superseded":
                continue
            rows.append({"label": d.get("slice") or d.get("block") or "?",
                         "target": d.get("target") or "(flagged — no node)",
                         "action": d.get("action")})
        per_vendor[vendor] = rows
    if not any(per_vendor.values()):
        return []
    # group rows by target node; within a target, list each vendor's labels
    targets: List[str] = []
    for rows in per_vendor.values():
        for r in rows:
            if r["target"] not in targets:
                targets.append(r["target"])
    vendors = sorted(per_vendor)
    lines = ["- ROUTING MATRIX (rows = intended node; cells = the label each "
             "provider read; ✗ = provider never routed anything here):",
             "", "| intended node | " + " | ".join(vendors) + " |",
             "|" + "---|" * (len(vendors) + 1)]
    for tgt in targets:
        cells = []
        for v in vendors:
            labels = [r["label"] for r in per_vendor[v] if r["target"] == tgt]
            cells.append("; ".join(labels) if labels else "✗")
        lines.append(f"| `{tgt}` | " + " | ".join(cells) + " |")
    lines.append("")
    return lines


def build_report() -> None:
    manifest = json.loads(MANIFEST.read_text())
    lines = ["# Vision benchmark — side-by-side (engineer grades)",
             f"\nGenerated {datetime.now(timezone.utc).isoformat(timespec='seconds')}.",
             "\nPer sheet: what each provider extracted, agreement/disagreement in "
             "element labels, runtime. Grade on: correctness vs the actual sheet, "
             "fabrication (worst failure), <UNKNOWN> honesty (credit), completeness.\n"]
    for cat in manifest["categories"]:
        for sheet in cat["sheets"]:
            out_dir = BENCH_DIR / cat["category"] / sheet["name"]
            if not out_dir.exists():
                continue
            runs = {p.stem: json.loads(p.read_text()) for p in out_dir.glob("*.json")}
            if not runs:
                continue
            lines.append(f"\n## {cat['category']} — {sheet['name']}\n")
            lines.extend(_routing_matrix(runs))
            label_sets = {v: set(l.lower() for l in _labels_of(r))
                          for v, r in runs.items()}
            common = set.intersection(*label_sets.values()) if label_sets else set()
            for vendor, result in sorted(runs.items()):
                labels = _labels_of(result)
                uniq = [l for l in labels if l.lower() not in common]
                lines.append(f"### {vendor} — {len(labels)} elements")
                lines.append(f"- agreed with all: {len(labels) - len(uniq)}"
                             f" · unique to {vendor}: {len(uniq)}")
                if uniq:
                    lines.append(f"- unique reads (VERIFY THESE — disagreement or "
                                 f"fabrication): {', '.join(uniq[:40])}")
                routing = result.get("_node_routing")
                if routing:
                    lines.append("- node routing (same backbone for every provider):")
                    for d in routing:
                        if "routing_error" in d:
                            lines.append(f"    - ROUTING ERROR: {d['routing_error']}")
                            continue
                        what = d.get("slice") or d.get("block") or "?"
                        tgt = d.get("target") or "—"
                        lines.append(f"    - {what} → {d.get('action')} "
                                     f"[{tgt}] via {d.get('via') or d.get('mechanism') or '-'}")
            lines.append("")
    REPORT.write_text("\n".join(lines))
    print(f"report -> {REPORT}", file=sys.stderr)


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(prog="tests.vision_bench")
    ap.add_argument("--providers", default=",".join(PROVIDERS_DEFAULT))
    ap.add_argument("--only", default=None, help="substring filter on category")
    ap.add_argument("--sheet", default=None, help="substring filter on sheet name")
    ap.add_argument("--report", action="store_true", help="rebuild report only")
    args = ap.parse_args(argv)
    if args.report:
        build_report()
        return 0
    run_bench([p.strip() for p in args.providers.split(",") if p.strip()],
              only=args.only, sheet_filter=args.sheet)
    build_report()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
