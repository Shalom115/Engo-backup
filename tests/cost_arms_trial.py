"""
SIDE-BY-SIDE COST-IDEA TEST (2026-07-26, engineer-requested).

Four arms on the SAME three sheets — none of them previously composed — each
metered, each taken all the way through a Register DRY-RUN so the comparison is
"what would this actually have written", not "what did it say".

  A0 BASELINE  protocol v9 as it stands: label OCR + device locate + wiring
               coverage + compose, all on the strong model, no prompt cache.
  A1 FUSED     idea 1 — ONE tiled pass returning labels + symbols + elements,
               replacing three separate looks at the same ink.
  A2 CACHED    idea 2 — same reads as baseline, but deterministic layers served
               from the content cache and the invariant composition prefix
               sent as a cached block.
  A3 CHEAP     idea 3 — tiled transcription layers on the small model, the
               reasoning (composition) still on the strong one.

Geometry (net_trace) is free and identical for every arm, so the netlist is
built once per sheet and shared — the arms differ only in what they PAY a model
to do.
"""
import io, json, os, sys, time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from pipeline import netlist, circuit, meter, vcache, net_trace
from pipeline.compose import compose, PROTOCOL_VERSION
from pipeline.compose_write import ComposeWriter
from pipeline.electrical_extract import extract_sheet
from tests.vision_bench import _load_sheet_bytes
import pypdfium2 as pdfium

GM = "1YAmYWTTes5AD7NGLCGXRG86OENBH22Pl"
OUT = config.STATE_DIR / "vision_bench/arms"
OUT.mkdir(parents=True, exist_ok=True)
LED = OUT / "ledger.jsonl"

SHEETS = [(19, "BILGE SYSTEM"),
          (21, "AFT SERVICE PUMPS"),
          (5,  "230V AFT DISTRIBUTION PANEL")]

done = set()
if LED.exists():
    for ln in open(LED):
        try:
            r = json.loads(ln)
            if r.get("ok"):
                done.add((r["arm"], r["page"]))
        except Exception:
            pass

pdf = _load_sheet_bytes({"name": "GM_book", "drive_file_id": GM})


def png(page, dpi=200):
    pil = pdfium.PdfDocument(pdf)[page].render(scale=dpi / 72).to_pil()
    b = io.BytesIO(); pil.save(b, format="PNG"); return b.getvalue()


def spend_since(mark):
    r = meter.report()
    return round(r["usd"] - mark, 4), r["calls"]


def build_ext_baseline(page, nl):
    ext = extract_sheet(pdf, page)
    ext["_netlist_digest"] = netlist.digest(nl, max_nets=60)
    ext["_circuit_digest"] = circuit.digest(nl)
    return ext


def build_ext_fused(page, tiles, nl):
    """The fused pass already read every element; shape it the way compose
    consumes an extraction, without a second look at the sheet."""
    return {"legends": [], "legend_context": "",
            "survey": {"sub_type": "relay_terminal_wiring",
                       "source": "fused tile pass"},
            "sub_type": "relay_terminal_wiring",
            "regions_read": [{"region": "ALL (fused tiles)",
                              "region_type": "relay_terminal_wiring",
                              "bbox": [0, 0, 1, 1], "reader": "fused",
                              "elements": tiles.get("elements", [])}],
            "_netlist_digest": netlist.digest(nl, max_nets=60),
            "_circuit_digest": circuit.digest(nl)}


def run_arm(arm, page, title):
    if (arm, page) in done:
        print(f"  skip {arm} p{page} (done)", flush=True)
        return
    t0 = time.time()
    mark = meter.report()["usd"]
    os.environ.pop("VISION_MODEL_LABELS", None)
    os.environ.pop("VISION_MODEL_DEVICES", None)
    os.environ.pop("VISION_MODEL_TILES", None)
    prompt_cache = False
    try:
        if arm == "A1_FUSED":
            from pipeline import fused_tiles
            tiles = fused_tiles.read_tiles(pdf, page)
            labels, devices = fused_tiles.as_netlist_inputs(tiles)
            nl = netlist.build(pdf, page, labels=labels, located=devices)
            ext = build_ext_fused(page, tiles, nl)
        elif arm == "A3_CHEAP":
            os.environ["VISION_MODEL_LABELS"] = "claude-haiku-4-5-20251001"
            os.environ["VISION_MODEL_DEVICES"] = "claude-haiku-4-5-20251001"
            # cheap arm must NOT read the strong arm's cache — separate params
            from pipeline import label_ocr, device_locate
            labels = label_ocr.labels_from_vision(pdf, page, dpi=401)
            devices = device_locate.locate_devices(pdf, page, dpi=401)
            nl = netlist.build(pdf, page, labels=labels, located=devices)
            ext = build_ext_baseline(page, nl)
        else:                                  # A0_BASELINE, A2_CACHED
            prompt_cache = (arm == "A2_CACHED")
            nl = netlist.build(pdf, page)
            ext = build_ext_baseline(page, nl)

        comp = compose(png(page), ext, "electrical", max_tokens=20000,
                       sheet_name=title, prompt_cache=prompt_cache)
        usd, calls = spend_since(mark)
        c = comp or {}

        # WHAT WOULD IT WRITE? — Register dry-run
        w = ComposeWriter(dry_run=True)
        counts = w.write_composition(c, {"sheet": f"GM_p{page}_{arm}",
                                         "drawing_class": "electrical",
                                         "page": page, "drive_file_id": GM})
        key = f"{arm}_p{page}"
        json.dump({"arm": arm, "page": page, "title": title,
                   "usd": usd, "seconds": round(time.time() - t0),
                   "composition": comp, "netlist_stats": nl["stats"],
                   "write_counts": counts,
                   "would_write": w.decisions,
                   "uncertainties": w.uncertainties,
                   "flags": w.confirmation_flags,
                   "cross_refs": w.cross_refs},
                  open(OUT / f"{key}.json", "w"), indent=1, default=str)
        att = counts.get("would_attach", 0) if isinstance(counts, dict) else 0
        print(f"  ok {arm:12s} p{page:<3} ${usd:<6} {calls:3d} calls "
              f"{time.time()-t0:5.0f}s | groups {len(c.get('equipment_groups') or [])} "
              f"| would-attach {att} | bound→cond {nl['stats'].get('bound_to_conductor')}",
              flush=True)
        with open(LED, 'a') as f:
            f.write(json.dumps({"arm": arm, "page": page, "ok": True,
                                "usd": usd}) + "\n")
    except Exception as e:
        print(f"  ERROR {arm} p{page}: {type(e).__name__}: {str(e)[:160]}", flush=True)
        with open(LED, 'a') as f:
            f.write(json.dumps({"arm": arm, "page": page, "ok": False,
                                "err": str(e)[:200]}) + "\n")


ARMS = ["A0_BASELINE", "A1_FUSED", "A2_CACHED", "A3_CHEAP"]
print(f"protocol v{PROTOCOL_VERSION} | {len(ARMS)} arms x {len(SHEETS)} sheets",
      flush=True)
for page, title in SHEETS:
    print(f"\n=== p{page} {title} ===", flush=True)
    for arm in ARMS:
        run_arm(arm, page, title)
print("\nARMS_DONE", flush=True)
print(json.dumps(meter.report(), indent=1), flush=True)
