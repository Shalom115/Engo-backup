"""
Suppliers vendor-index ingest — folds the OEM-manual master index into the
backbone, deduped and placed under the right SFI subsystem.

The Suppliers folder (SWS 108 › SWS › Suppliers) is a flat ~75-vendor index,
each folder named "Maker (Function)". It is NOT the structural backbone (that is
SWS 108-01) — but it holds authoritative OEM manuals, some unique. This pass:

  1. Walks Suppliers live (connector).
  2. Places each vendor by looking its maker up in the vendor->subsystem map
     LEARNED from the SWS 108-01 register (the backbone teaches the placement).
     Misses fall back to function-word matching against subsystem labels; a hard
     miss is FLAGGED (region/subsystem None) for engineer adjudication — never
     guessed.
  3. Ingests each text file with the existing pipeline, hash-deduped so files
     already present from the system tree are skipped (no duplication). Images /
     scanned PDFs append to the pending_vision queue. source_kind="supplier".
  4. Reconciles into ingestion_report_suppliers.json (resumable via
     ingest_ledger_suppliers.jsonl).

CLI:
    python -m pipeline.ingest_suppliers --dry-run   # walk + show placements, no cost
    python -m pipeline.ingest_suppliers             # ingest (resumes if interrupted)
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import config
from providers.structure import GoogleDriveStructureProvider, FOLDER_MIME
from providers.embeddings import get_embedding_provider
from providers.vectorstore import get_vectorstore_provider
from pipeline.ingest import ingest_file
from pipeline.folder_parse import (parse_equipment_name, is_doc_type_folder,
                                   strip_leading_code, region_for_code, REGION_LABELS)
from pipeline.ingest_drive import TEXT_MIMES, _classify, UNSUPPORTED_REASON

logging.basicConfig(
    level="INFO",
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[logging.FileHandler(config.LOGS_DIR / "ingest_suppliers.log", encoding="utf-8"),
              logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("pipeline.ingest_suppliers")

SUPPLIERS_ROOT = "1QQqbYeFy_emrd0PTKfVjBy9c07UCIjIe"
_STOP = {"the", "and", "system", "systems", "of", "for", "control", "and"}

# Engineer-adjudicated placements (override the auto-map). keyed by normalized
# maker -> (region, subsystem|None, label, note). Subsystem None = region-level
# (spans subsystems / no clean home); flagged for per-file routing in v2.
VENDOR_OVERRIDE = {
    "wartsila":          ("400", "430", "Variable pitch control",
                          "shaft seal (430 folder renamed Bearing->Shaft Seal)"),
    "diverse":           ("800", None, "Rigging and Sailing",
                          "rigging load pin (0-5V/4-20mA); spans standing+running (per-file v2)"),
    "farr":              ("100", None, "Structure, Rudder and Keel",
                          "naval architect; files span subsystems (per-file routing = v2)"),
    "future automation": ("300", None, "Interiors",
                          "interior TV sliding system; no specific subsystem rule"),
    "pixel sur mer":     ("900", None, "Miscellaneous",
                          "Exocet — onboard CAN/network data aggregator (monitoring source)"),
    "sensors":           ("500", "570", "Power hydraulic systems",
                          "sensor suppliers; some manuals also belong in 001/70 (per-file v2)"),
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def build_vendor_map(reg: Dict[str, Any]):
    """Learn maker -> (region, subsystem, label) from the backbone register,
    and seed the subsystem lookup from EVERY SFI subsystem folder in the
    structure (so function-fallback can reach subsystems that had no equipment
    entry of their own, e.g. 580 Refrigeration)."""
    vmap: Dict[str, Tuple[str, str, str]] = {}
    subsystems: Dict[Tuple[str, str], str] = {}
    for e in reg["entries"]:
        if not e.get("subsystem_code"):
            continue
        loc = (e["region_code"], e["subsystem_code"], e.get("subsystem_label") or "")
        subsystems[(e["region_code"], e["subsystem_code"])] = loc[2]
        for field in (e.get("make"), e.get("model"), e.get("name"), *e.get("acronyms", [])):
            k = _norm(field if isinstance(field, str) else "")
            if k and len(k) >= 3:
                vmap.setdefault(k, loc)
    # Seed all subsystem folders from the structure manifest.
    try:
        st = json.loads((config.STATE_DIR / f"structure_{config.VESSEL_NAMESPACE}.json").read_text())
        for n in st["nodes"]:
            if n["type"] != "folder":
                continue
            code, rest = strip_leading_code(n["name"])
            if code and len(code) == 3 and code != region_for_code(code):  # XX0 subsystem, not X00 region
                rc = region_for_code(code)
                subsystems.setdefault((rc, code), rest)
    except Exception:
        pass
    return vmap, subsystems


def place_vendor(folder_name: str, vmap, subsystems) -> Dict[str, Any]:
    """Resolve a 'Maker (Function)' folder to a backbone placement."""
    parsed = parse_equipment_name(folder_name)
    maker = parsed.get("make") or parsed.get("model") or parsed.get("name") or folder_name
    func = parsed.get("category") or ""
    nmaker = _norm(maker)

    # 0. Engineer-adjudicated override wins.
    if nmaker in VENDOR_OVERRIDE:
        rc, sc, label, note = VENDOR_OVERRIDE[nmaker]
        return {"region_code": rc, "subsystem_code": sc, "subsystem_label": label,
                "vendor": maker, "method": "engineer", "note": note}

    # 1. Exact maker match.
    if nmaker in vmap:
        r = vmap[nmaker]
        return {"region_code": r[0], "subsystem_code": r[1], "subsystem_label": r[2],
                "vendor": maker, "method": "exact"}
    # 2. Token match — a maker token equal to, or a token within, a learned key
    #    (catches "Cummins" -> key "cummins qsb4 5").
    for tok in nmaker.split():
        if len(tok) < 4:
            continue
        for vk, r in vmap.items():
            if tok == vk or tok in vk.split():
                return {"region_code": r[0], "subsystem_code": r[1], "subsystem_label": r[2],
                        "vendor": maker, "method": "token"}
    # 3. Function-word overlap vs subsystem labels, with light stemming so
    #    thruster~thrusters / refrigeration~refrigeration match.
    def stem(w: str) -> str:
        return w[:5]
    fwords = {w for w in _norm(func + " " + maker).split() if len(w) >= 4 and w not in _STOP}
    best, best_score = None, 0
    for (rc, sc), label in subsystems.items():
        lwords = {w for w in _norm(label).split() if len(w) >= 4 and w not in _STOP}
        score = sum(1 for fw in fwords for lw in lwords if fw == lw or stem(fw) == stem(lw))
        if score > best_score:
            best, best_score = (rc, sc, label), score
    if best:
        return {"region_code": best[0], "subsystem_code": best[1], "subsystem_label": best[2],
                "vendor": maker, "method": "function"}
    # 4. Hard miss — flag, do not guess.
    return {"region_code": None, "subsystem_code": None, "subsystem_label": None,
            "vendor": maker, "method": "UNMAPPED"}


def build_placements(nodes, vmap, subsystems):
    """Assign each Suppliers file a placement inherited from its vendor folder."""
    idmap = {n["id"]: n for n in nodes}
    childmap = defaultdict(list)
    for n in nodes:
        childmap[n.get("parentId")].append(n)
    root = next((n["id"] for n in nodes if n.get("parentId") is None), SUPPLIERS_ROOT)

    placements: List[Dict[str, Any]] = []
    vendor_placements: Dict[str, Dict[str, Any]] = {}

    def descend(node_id, vendor_ctx, doc_type):
        for c in childmap.get(node_id, []):
            if c["type"] == "folder":
                if node_id == root:
                    # depth-1 = a vendor folder
                    pl = place_vendor(c["name"], vmap, subsystems)
                    vendor_placements[c["name"]] = pl
                    descend(c["id"], pl, None)
                elif is_doc_type_folder(c["name"]):
                    _, rest = strip_leading_code(c["name"])
                    descend(c["id"], vendor_ctx, rest)
                else:
                    descend(c["id"], vendor_ctx, doc_type)
            else:
                pl = vendor_ctx or {"region_code": None, "subsystem_code": None,
                                    "subsystem_label": None, "vendor": "(root)", "method": "root-file"}
                placements.append({
                    "file_id": c["id"], "name": c["name"], "path": c["path"],
                    "mime": c.get("mime"), "ext": c.get("ext"), "size": c.get("fileSize"),
                    "region_code": pl["region_code"], "subsystem_code": pl["subsystem_code"],
                    "subsystem_label": pl["subsystem_label"],
                    "equipment_name": pl["vendor"], "doc_type": doc_type,
                    "place_method": pl["method"],
                })
    descend(root, None, None)
    return placements, vendor_placements


def _placement_metadata(p: Dict[str, Any]) -> Dict[str, Any]:
    raw = {
        "sfi_section": p.get("region_code"), "region_code": p.get("region_code"),
        "subsystem_code": p.get("subsystem_code"), "subsystem_label": p.get("subsystem_label"),
        "equipment_name": p.get("equipment_name"), "doc_type": p.get("doc_type"),
        "drive_file_id": p.get("file_id"), "source_kind": "supplier",
        "supplier_vendor": p.get("equipment_name"),
    }
    return {k: v for k, v in raw.items() if v not in (None, "")}


def run(dry_run: bool = False) -> Dict[str, Any]:
    state, vessel = config.STATE_DIR, config.VESSEL_NAMESPACE
    reg = json.loads((state / f"register_{vessel}.json").read_text())
    vmap, subsystems = build_vendor_map(reg)

    prov = GoogleDriveStructureProvider(SUPPLIERS_ROOT, "Suppliers")
    logger.info("Walking Suppliers...")
    nodes = prov.walk()
    placements, vendor_placements = build_placements(nodes, vmap, subsystems)
    (state / f"placements_suppliers_{vessel}.json").write_text(
        json.dumps({"placements": placements,
                    "vendor_placements": vendor_placements}, indent=2, ensure_ascii=False),
        encoding="utf-8")

    total = len(placements)
    methods = defaultdict(int)
    for v in vendor_placements.values():
        methods[v["method"]] += 1
    kinds = defaultdict(int)
    for p in placements:
        kinds[_classify(p.get("mime", ""))] += 1

    logger.info("Suppliers: %d vendor folders, %d files. vendor placement methods: %s",
                len(vendor_placements), total, dict(methods))
    logger.info("file classification: %s", dict(kinds))
    unmapped = {k: v for k, v in vendor_placements.items() if v["method"] in ("function", "UNMAPPED")}
    print("\n=== vendors needing review (function-fallback or unmapped) ===")
    for name, v in sorted(unmapped.items()):
        print(f"  [{v['method']:8}] {name}  ->  {v['subsystem_code']} {v['subsystem_label']}")

    if dry_run:
        return {"vendors": len(vendor_placements), "files": total,
                "methods": dict(methods), "kinds": dict(kinds)}

    # --- Ingest with dedup + ledger ---
    ledger_path = state / f"ingest_ledger_suppliers_{vessel}.jsonl"
    ledger: Dict[str, str] = {}
    if ledger_path.exists():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line); ledger[r["file_id"]] = r["bucket"]
    store = get_vectorstore_provider()
    embedder = get_embedding_provider()
    lf = open(ledger_path, "a", encoding="utf-8")

    def rec(fid, bucket, **kw):
        ledger[fid] = bucket
        lf.write(json.dumps({"file_id": fid, "bucket": bucket, **kw}, ensure_ascii=False) + "\n")
        lf.flush()

    tmpdir = Path(tempfile.mkdtemp(prefix="engo_suppliers_"))
    buckets = defaultdict(int)
    pending: List[Dict[str, Any]] = []
    for i, p in enumerate(placements, 1):
        fid = p["file_id"]
        if fid in ledger:
            continue
        mime = p.get("mime", "")
        kind = _classify(mime)
        if kind == "vision":
            pending.append(p); rec(fid, "pending_vision", name=p["name"]); buckets["pending_vision"] += 1
            continue
        if kind == "unsupported":
            rec(fid, "unsupported", name=p["name"], reason=UNSUPPORTED_REASON.get(mime, "unsupported"))
            buckets["unsupported"] += 1
            continue
        _, suffix = TEXT_MIMES[mime]
        tmp = tmpdir / f"{fid}{suffix}"
        try:
            data, _ = prov.download_bytes(fid, mime)
            tmp.write_bytes(data)
            s = ingest_file(tmp, extra_metadata=_placement_metadata(p),
                            display_name=p["name"], display_path=p["path"],
                            store=store, embedder=embedder)
            if s["skipped"]:
                rec(fid, "duplicate", name=p["name"]); buckets["duplicate"] += 1
            elif s["chunks_created"] == 0:
                pending.append({**p, "reason": "scanned"})
                rec(fid, "pending_vision", name=p["name"], reason="scanned"); buckets["pending_vision"] += 1
            else:
                rec(fid, "ingested", name=p["name"], chunks=s["chunks_created"]); buckets["ingested"] += 1
        except Exception as e:
            rec(fid, "error", name=p["name"], error=str(e)); buckets["errors"] += 1
            logger.warning("fail: %s — %s", p["name"], e)
        finally:
            tmp.unlink(missing_ok=True)
        if i % 25 == 0:
            logger.info("progress %d/%d %s", i, total, dict(buckets))
    lf.close()

    accounted = sum(1 for p in placements if p["file_id"] in ledger)
    report = {
        "vessel_namespace": vessel, "source": "suppliers",
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": total, "accounted": accounted, "reconciled": accounted == total,
        "buckets": dict(buckets), "vendor_methods": dict(methods),
        "unmapped_vendors": {k: v for k, v in vendor_placements.items() if v["method"] == "UNMAPPED"},
    }
    (state / f"ingestion_report_suppliers_{vessel}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    # merge pending_vision into the main queue file
    pv_path = state / f"pending_vision_{vessel}.json"
    existing = json.loads(pv_path.read_text())["queue"] if pv_path.exists() else []
    pv_path.write_text(json.dumps({"vessel_namespace": vessel,
                                   "count": len(existing) + len(pending),
                                   "queue": existing + pending}, indent=2, ensure_ascii=False),
                       encoding="utf-8")
    logger.info("DONE suppliers. %s reconciled=%s", dict(buckets), report["reconciled"])
    return report


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.ingest_suppliers")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    rep = run(dry_run=args.dry_run)
    return 0 if args.dry_run or rep.get("reconciled") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
