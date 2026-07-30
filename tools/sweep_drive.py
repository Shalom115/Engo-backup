"""
SWEEP DRIVE — the full-corpus extraction runner. ONE command, kill-safe,
resumable, cost-capped. This is the tool the engineer's "GO for the full
drive" actually runs.

    python3.12 tools/sweep_drive.py                    # full Drive sweep (Mac)
    python3.12 tools/sweep_drive.py --limit 20         # first 20 (smoke)
    python3.12 tools/sweep_drive.py --local <dir>      # local PDFs (testing)

Per file: probe -> route (extract_document) -> lint -> routing preview.
Everything lands under data/state/sweep/<safe-name>/ with a global append-only
ledger (data/state/sweep/ledger.jsonl) — a killed run resumes by skipping
completed ids; re-running the same command is always safe.

WHAT IT NEVER DOES: write to the Register (no node_write import anywhere in
this chain; routing_preview prints "NO WRITES PERFORMED" per file), call any
vision API (this sweep is the $0 deterministic pass — the vision-verify queue
it produces is priced and run SEPARATELY with an explicit cap), or fabricate a
summary (the final report is computed from the ledger, never typed).

Output report: data/state/sweep/sweep_report.json —
  route split, per-route file counts, lint pass/fail, total preview rows
  proposed/unresolved/control, symbols typed/unknown, raster pages queued,
  vision-verify queue size + its ESTIMATED cost (so the engineer approves a
  number, not a surprise).
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

STATE = Path(__file__).resolve().parent.parent / "data" / "state"
SWEEP = STATE / "sweep"
VESSEL = "gelliceaux_001"


def safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:80]


def drive_downloader():
    """Build the connector that can actually FETCH BYTES, and prove it can
    before the sweep starts.

    Bug found on the Mac 2026-07-30, 20/20 files failed: this used the
    `get_structure_provider()` factory, which defaults to STRUCTURE_PROVIDER=
    "snapshot" — a provider that reads the materialised structure JSON and has
    no download_bytes at all. The manifest is exactly what we already have;
    what the sweep needs is the LIVE connector, constructed the way the proven
    path (pipeline/ingest_drive.py) constructs it. Never ask a factory for a
    capability when you know which implementation provides it.
    """
    from providers.structure import GoogleDriveStructureProvider
    manifest = json.loads((STATE / f"structure_{VESSEL}.json").read_text())
    provider = GoogleDriveStructureProvider(manifest["root_id"],
                                            manifest.get("root_name", ""))
    if not hasattr(provider, "download_bytes"):
        raise RuntimeError(
            f"{type(provider).__name__} cannot download bytes — the sweep "
            f"cannot run against Drive with it.")
    return provider, manifest


def iter_drive_pdfs():
    """Yield (id, name, download_fn) from the structure manifest via the
    read-only Drive connector."""
    provider, manifest = drive_downloader()
    nodes = manifest.get("nodes") or manifest
    import time as _t

    def dl(fid, mime):
        delay = 2.0
        for attempt in range(4):
            try:
                # download_bytes returns (data, suffix) — the suffix is only
                # set for exported Google-native files, which a PDF never is.
                data, _suffix = provider.download_bytes(fid, mime)
                return data
            except (AttributeError, TypeError, KeyError):
                # A programming error is not transient. Retrying it four times
                # with backoff burned 14s per file on the Mac and produced 20
                # identical failures that looked like a network problem.
                raise
            except Exception:
                if attempt == 3:
                    raise
                _t.sleep(delay)
                delay *= 2

    for n in nodes:
        if isinstance(n, dict) and n.get("mime") == "application/pdf":
            yield (n["id"], n.get("name", n["id"]),
                   (lambda fid=n["id"], mime=n["mime"]: dl(fid, mime)))


def iter_local_pdfs(root: Path):
    for f in sorted(root.glob("**/*.pdf")) + sorted(root.glob("**/*.PDF")):
        yield str(f), f.name, (lambda f=f: f.read_bytes())


def superseded_ids() -> set:
    from routing_preview import load_superseded
    return load_superseded()


def process_one(fid: str, name: str, data: bytes, out_dir: Path) -> dict:
    import extract_document as xd
    import electrical_lint as el
    import routing_preview as rp

    out_dir.mkdir(parents=True, exist_ok=True)
    # Name the temp file after the REAL document: extract_document derives
    # the font-table name from the file stem, so writing every book as
    # "src.pdf" merged EVERY drafting house into one font_table_src.json —
    # cross-house glyph contamination. Caught pre-flight, 2026-07-28.
    pdf_tmp = out_dir / f"{safe_name(Path(name).stem)}.pdf"
    pdf_tmp.write_bytes(data)
    line: dict = {"id": fid, "name": name}

    p = xd.plan(data, name)
    line["route"] = p["route"]
    line["pages"] = p["pages"]
    line["specialisations_pending"] = p["specialisations_pending"]

    if p["route"] == "raster":
        (out_dir / "queue_vision.json").write_text(json.dumps(
            {"id": fid, "name": name, "queued_for": "vision_tiling_path"},
            indent=1))
        line["handled"] = "queued_vision"
        return line

    xd.main([str(pdf_tmp), str(out_dir)])

    page_files = [q for q in out_dir.glob("p*.json") if q.stem[1:].isdigit()]
    line["pages_extracted"] = len(page_files)
    counts = Counter()
    for q in page_files:
        rec = json.loads(q.read_text())
        for k in ("labels", "ocr_conf70", "attached", "symbols",
                  "symbols_typed", "symbols_unknown", "symbols_need_verify",
                  "legend_entries"):
            counts[k] += rec["counts"].get(k, 0)
        counts["text_layer_labels"] += rec["counts"].get("text_layer_labels", 0)
    line["counts"] = dict(counts)

    # lint (in-process; exit code captured, not allowed to kill the sweep)
    rows = [el.lint_page(json.loads(q.read_text()))
            for q in sorted(page_files, key=lambda q: int(q.stem[1:]))]
    fails = [r["page"] for r in rows if r["hard_fail"]]
    (out_dir / "lint_report.json").write_text(json.dumps(
        {"pages": len(rows), "hard_fail_pages": fails, "per_page": rows},
        indent=1))
    line["lint_hard_fail_pages"] = fails

    # routing preview (writes nothing) — refuse superseded drawings outright
    if fid in superseded_ids():
        line["preview"] = "REFUSED_SUPERSEDED"
    else:
        rp.main([str(out_dir)])
        pv = json.loads((out_dir / "routing_preview.json").read_text())
        line["preview_rows"] = len(pv)
        line["preview_proposed"] = sum(
            1 for r in pv if r["proposed"] not in ("UNRESOLVED",)
            and r.get("role") != "control")
        line["preview_unresolved"] = sum(
            1 for r in pv if r["proposed"] == "UNRESOLVED")

    # vision-verify queue: low-conf, non-decoded labels (priced, not run)
    vq: list = []
    for q in page_files:
        rec = json.loads(q.read_text())
        for lab in rec.get("labels", []):
            if lab.get("text") and lab.get("conf_final",
                                           lab.get("conf", 0)) < 70:
                vq.append({"page": rec["page"], "bbox": lab["bbox"],
                           "tesseract": lab["text"]})
    if vq:
        (out_dir / "queue_label_verify.json").write_text(
            json.dumps(vq, indent=1))
    line["label_verify_queue"] = len(vq)
    # KEEP the PDF when there is a verify queue. label_vision_verify needs
    # --pdf to re-crop the labels; deleting it here forced a re-download from
    # Drive mid-verify (a network dependency in the middle of a PAID step).
    # Caught 2026-07-30 by walking the runbook end to end instead of per tool.
    if vq:
        line["pdf_kept"] = str(pdf_tmp)
    else:
        pdf_tmp.unlink(missing_ok=True)
    return line


def main(argv):
    SWEEP.mkdir(parents=True, exist_ok=True)
    ledger = SWEEP / "ledger.jsonl"
    done = set()
    if ledger.exists():
        for l in ledger.read_text().splitlines():
            try:
                r = json.loads(l)
            except Exception:
                continue
            # ONLY successful ids are "done". Treating a failed row as done
            # meant a transient error retired a file permanently — the 20
            # provider failures on the Mac would never have been retried, and
            # the final report would have quietly shown 20 fewer files with
            # nothing marked missing. Resume must retry failures, not bury
            # them.
            if r.get("ok"):
                done.add(r["id"])
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
    if "--local" in argv:
        src = iter_local_pdfs(Path(argv[argv.index("--local") + 1]))
    else:
        # PREFLIGHT: prove the connector can fetch bytes BEFORE processing a
        # single file. Without this the failure arrives once per file, with a
        # retry/backoff delay each time, and reads as a Drive outage.
        try:
            provider, _m = drive_downloader()
            print(f"connector: {type(provider).__name__} — download_bytes OK")
        except Exception as e:
            print(f"REFUSED: cannot reach Drive — {type(e).__name__}: {e}\n"
                  f"  * credentials: GDRIVE_SERVICE_ACCOUNT_JSON must point at "
                  f"the service-account key file (see .env)\n"
                  f"  * or sweep local files instead: --local <dir>")
            sys.exit(2)
        src = iter_drive_pdfs()
    n = 0
    # Superseded drawings are refused BEFORE download, not after extraction.
    # Extracting them was not just wasted time: the glyph decoder trains the
    # per-house font table on whatever it extracts, so an obsolete revision
    # was contributing glyphs to the house font that the current revisions
    # are then decoded against. Refusal is ledgered, so the count is visible.
    sup = superseded_ids()
    with ledger.open("a") as led:
        for fid, name, get in src:
            if fid in done:
                continue
            if limit and n >= limit:
                break
            if fid in sup:
                led.write(json.dumps({"id": fid, "name": name, "ok": True,
                                      "route": "refused_superseded",
                                      "handled": "refused_superseded"}) + "\n")
                led.flush()
                continue
            n += 1
            t0 = time.time()
            out_dir = SWEEP / safe_name(name)
            try:
                line = process_one(fid, name, get(), out_dir)
                line["ok"] = True
            except Exception as e:
                line = {"id": fid, "name": name, "ok": False,
                        "error": f"{type(e).__name__}: {e}",
                        "trace": traceback.format_exc()[-800:]}
            line["secs"] = round(time.time() - t0, 1)
            led.write(json.dumps(line) + "\n")
            led.flush()
            print(json.dumps({k: line[k] for k in line
                              if k not in ("trace", "counts")}), flush=True)
    report(ledger)


def report(ledger: Path):
    """Computed from the ledger — never typed from memory."""
    raw = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
    # Retries append a second row for the same id. Keep the LAST outcome per
    # id, otherwise a file that failed then succeeded is counted twice and the
    # file total exceeds the corpus.
    latest = {}
    for r in raw:
        latest[r.get("id")] = r
    rows = list(latest.values())
    ok = [r for r in rows if r.get("ok")]
    routes = Counter(r.get("route", "error") for r in rows)
    agg = Counter()
    for r in ok:
        for k, v in (r.get("counts") or {}).items():
            agg[k] += v
        agg["preview_proposed"] += r.get("preview_proposed", 0)
        agg["preview_unresolved"] += r.get("preview_unresolved", 0)
        agg["label_verify_queue"] += r.get("label_verify_queue", 0)
    lint_fail_files = [r["name"] for r in ok if r.get("lint_hard_fail_pages")]
    # vision-verify cost estimate: ~40 crops/montage call, Sonnet-class call
    # ~ $0.02 in + out at these crop sizes -> price BEFORE anyone runs it
    calls = (agg["label_verify_queue"] + 39) // 40
    est_cost = round(calls * 0.02, 2)
    rep = {
        "files": len(rows), "ok": len(ok),
        "errors": [{"name": r["name"], "error": r["error"]}
                   for r in rows if not r.get("ok")][:50],
        "routes": dict(routes),
        "totals": dict(agg),
        "lint_hard_fail_files": lint_fail_files[:100],
        "vision_verify_queue": agg["label_verify_queue"],
        "vision_verify_est_calls": calls,
        "vision_verify_est_cost_usd": est_cost,
    }
    (SWEEP / "sweep_report.json").write_text(json.dumps(rep, indent=1))
    print("\n=== SWEEP REPORT (computed from ledger) ===")
    print(json.dumps({k: v for k, v in rep.items() if k != "errors"}, indent=1))
    if rep["errors"]:
        print(f"errors ({len(rep['errors'])} shown up to 50):")
        for e in rep["errors"][:10]:
            print(f"  {e['name']}: {e['error']}")


if __name__ == "__main__":
    main(sys.argv[1:])
