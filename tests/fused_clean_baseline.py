"""
CLEAN FUSED BASELINE — the three trial sheets re-run with:
  * the fused tile pass as a first-class path (legends-first inside it), and
  * the REPAIRED composition prompt (the established-facts rule was split
    mid-sentence during a reorder, so every composition in the cost trial —
    all four arms — ran with a truncated instruction).

The trial's arm-vs-arm comparison stays valid (every arm carried the same
defect), but its absolute numbers are a floor. This run establishes the real
one. Kill-safe ledger; metered; each sheet ends in a Register dry-run so the
output is the delta that would actually be written.
"""
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from pipeline import circuit, fused_tiles, meter, netlist
from pipeline.compose import PROTOCOL_VERSION, compose
from pipeline.compose_write import ComposeWriter
from tests.vision_bench import _load_sheet_bytes
import pypdfium2 as pdfium

GM = "1YAmYWTTes5AD7NGLCGXRG86OENBH22Pl"
OUT = config.STATE_DIR / "vision_bench/fused_clean"
OUT.mkdir(parents=True, exist_ok=True)
LED = OUT / "ledger.jsonl"

SHEETS = [(19, "BILGE SYSTEM"),
          (21, "AFT SERVICE PUMPS"),
          (5, "230V AFT DISTRIBUTION PANEL")]

done = set()
if LED.exists():
    for ln in open(LED):
        try:
            r = json.loads(ln)
            if r.get("ok"):
                done.add(r["page"])
        except Exception:
            pass

pdf = _load_sheet_bytes({"name": "GM_book", "drive_file_id": GM})


def png(page, dpi=200):
    pil = pdfium.PdfDocument(pdf)[page].render(scale=dpi / 72).to_pil()
    b = io.BytesIO()
    pil.save(b, format="PNG")
    return b.getvalue()


print(f"protocol v{PROTOCOL_VERSION} — fused + legends-first + repaired prompt",
      flush=True)

for page, title in SHEETS:
    if page in done:
        print(f"  skip p{page} (done)", flush=True)
        continue
    t0 = time.time()
    mark = meter.report()["usd"]
    try:
        ext = fused_tiles.extract_sheet_fused(pdf, page)
        tiles = ext["_fused_tiles"]
        labels, devices = fused_tiles.as_netlist_inputs(tiles)
        nl = netlist.build(pdf, page, labels=labels, located=devices)
        ext["_netlist_digest"] = netlist.digest(nl, max_nets=60)
        ext["_circuit_digest"] = circuit.digest(nl)
        ext.pop("_fused_tiles", None)

        comp = compose(png(page), ext, "electrical", max_tokens=20000,
                       sheet_name=title, prompt_cache=True)
        c = comp or {}
        usd = round(meter.report()["usd"] - mark, 4)

        w = ComposeWriter(dry_run=True)
        counts = w.write_composition(c, {"sheet": f"GM_p{page}_FUSED_CLEAN",
                                         "drawing_class": "electrical",
                                         "page": page, "drive_file_id": GM})
        attach = sum(1 for n in w.decisions
                     if n.get("action") in ("would_attach", "attached"))
        json.dump({"page": page, "title": title, "usd": usd,
                   "seconds": round(time.time() - t0),
                   "legend_tables": len(ext.get("legends") or []),
                   "composition": comp, "netlist_stats": nl["stats"],
                   "write_counts": counts, "would_write": w.decisions,
                   "uncertainties": w.uncertainties,
                   "flags": w.confirmation_flags, "cross_refs": w.cross_refs},
                  open(OUT / f"FUSED_CLEAN_p{page}.json", "w"),
                  indent=1, default=str)
        print(f"  ok p{page:<3} ${usd:<7} {time.time()-t0:5.0f}s | "
              f"legends {len(ext.get('legends') or [])} | "
              f"grp {len(c.get('equipment_groups') or [])} | "
              f"attach {attach} | unc {len(c.get('uncertainties') or [])} | "
              f"bound->cond {nl['stats'].get('bound_to_conductor')}", flush=True)
        with open(LED, "a") as f:
            f.write(json.dumps({"page": page, "ok": True, "usd": usd}) + "\n")
    except Exception as e:
        print(f"  ERROR p{page}: {type(e).__name__}: {str(e)[:160]}", flush=True)
        with open(LED, "a") as f:
            f.write(json.dumps({"page": page, "ok": False,
                                "err": str(e)[:200]}) + "\n")

print("FUSED_CLEAN_DONE", flush=True)
print(json.dumps(meter.report(), indent=1), flush=True)
