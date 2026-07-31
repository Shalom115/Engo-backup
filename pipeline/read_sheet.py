"""
READ SHEET — one entry point that reads a drawing the way the protocol says,
whatever discipline it turns out to be.

WHY THIS EXISTS. Every piece needed to read a sheet correctly already existed
and none of them were joined:

  * the vector sweep measures connectivity exactly, for free, better than any
    model ever derived it — but it read text crop-by-crop with tesseract, and a
    clipped one-line crop has no context to recover from (measured: 20 of 43 GM
    pages, 38 of 47 BAE and 23 of 25 PLC pages could not even be identified by
    discipline from their own text);
  * the fused tile pass reads text WITH its surroundings and names the
    label-to-symbol association directly — but it lived on a branch;
  * `schematic_extract.discover_structure` (hydraulic) and
    `pid_extract.fluid_loops` (flow scenarios) are engineer-approved and
    already the source of 183 hydraulic facts in the Register — but the
    dispatcher routed on FILE FORMAT and never asked what discipline a sheet
    was, so neither was ever called;
  * `compose` carries the engineer's rules for all seven classes — relay NO/NC,
    arrows-as-flow-authority, PLC channel and side — reachable from nothing.

The division of labour is the point:

    CONNECTIVITY comes from the vector tracer. It is measured, not a model,
    and it does not guess.
    NAMING AND TYPING come from one fused vision read, which sees context.
    REASONING (loops, flow scenarios, command chains) comes from `compose`,
    working from the measured netlist rather than from a picture.

No layer is asked to do another layer's job, which is the failure mode that
produced reversed polarity and invented part numbers.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# Which composition class each detected discipline composes under. `compose`
# raises on an unknown class rather than silently composing under the wrong
# rules, so this table is the only place the mapping lives.
COMPOSE_CLASS = {
    "hydraulic": "hydraulic",
    "pid": "pid",
    "plc": "plc",
    "electrical": "electrical",
    "interconnect": "interconnect",
    "building_ga": "building_ga",
}


def geometry(pdf_bytes: bytes, page_index: int,
             sweep_rec: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Measured connectivity. Free.

    Prefers a sweep page record — that geometry is already computed and paid
    for in wall-clock; recomputing it would be pure waste. Falls back to
    tracing the page directly when no sweep has run.
    """
    from pipeline import netlist
    # TRACE FROM THE PDF even when a sweep record exists. Measured on GM p20:
    # the sweep record carries net MEMBERSHIP but not the raw segment graph
    # (`_nets_full`), and without that graph the fused read's labels cannot be
    # bound to the nets — the read is paid for and then thrown away. Tracing is
    # vector geometry: $0 and a few seconds. The sweep record is still used,
    # for the engineer-confirmed symbol TYPES it carries, which tracing alone
    # does not produce.
    #
    # locate=False: device symbols come from the fused read below, not from a
    # separate paid locate pass. Asking twice was two thirds of the old bill.
    nl = netlist.build(pdf_bytes, page_index, locate=False)
    if sweep_rec:
        from pipeline import sweep_adapter
        swept = sweep_adapter.netlist_from_page(sweep_rec)
        nl["typed_symbols"] = [p for p in swept["placed_devices"]
                               if p.get("kind") != "<UNKNOWN_SHAPE>"]
        nl["stats"]["devices_typed"] = len(nl["typed_symbols"])
        nl["stats"]["source"] = "traced+sweep_types"
    return nl


def classify(sweep_rec: Optional[Dict[str, Any]],
             fused: Optional[Dict[str, Any]] = None,
             filename: str = "") -> Dict[str, Any]:
    """Discipline of this sheet, from whatever text is already available.

    Free. Runs on the sweep's own labels first; if a fused read has happened,
    its labels are better and are used instead — the same detector, better
    input.
    """
    from pipeline import drawing_class
    text = ""
    if fused:
        text = " ".join((l.get("text") or "") for l in fused.get("labels", []))
    if len(text) < 80 and sweep_rec:
        text = drawing_class.text_from_page_record(sweep_rec)
    return drawing_class.detect(text, filename=filename)


def read(pdf_bytes: bytes, page_index: int = 0, *,
         sweep_rec: Optional[Dict[str, Any]] = None,
         filename: str = "",
         drawing_class_override: Optional[str] = None,
         compose_sheet: bool = True,
         sheet_name: str = "") -> Dict[str, Any]:
    """Read one sheet end to end and return what would be written.

    WRITES NOTHING. The caller decides whether to persist, and the write path
    stays out of this module so the read chain is provably write-free.

    Returns {drawing_class, class_evidence, geometry_stats, extraction,
             composition, would_write, layers_run, notes}.
    """
    notes: List[str] = []
    layers: List[str] = []

    # ---- 1. CONNECTIVITY (free, measured) --------------------------------
    nl = geometry(pdf_bytes, page_index, sweep_rec)
    layers.append("geometry:" + nl["stats"].get("source", "traced"))

    # ---- 2. ORIENTATION: ROLE + HEADER, then DISCIPLINE (all free) -------
    # The engineer's own reading order (2026-07-31): decide what KIND of page
    # this is, read its header for scope, and only then start following lines.
    # An index page is a ROUTER to other sheets and a title page has no
    # circuit — sending either to a circuit reader spends money to invent
    # structure that was never drawn.
    from pipeline import drawing_class as _dcmod
    role, header = "schematic", ""
    if sweep_rec:
        _txt = _dcmod.text_from_page_record(sweep_rec)
        _cond = sum(1 for n in sweep_rec.get("nets", []) if n.get("n_segs", 0) > 2)
        _labs = len([l for l in sweep_rec.get("labels", [])
                     if (l.get("text") or "").strip()])
        role = _dcmod.sheet_role(_txt, n_conductors=_cond, n_labels=_labs)
        header = _dcmod.header_block(sweep_rec)
    layers.append(f"role:{role}")
    if role in ("index", "title"):
        notes.append(f"page role '{role}' — no circuit is drawn here, so no "
                     f"circuit was read. An index is a router to other sheets; "
                     f"its value is the sheet list, not a traced loop.")
        return {"drawing_class": role, "class_evidence": {"confidence": "geometry"},
                "sheet_role": role, "header": header,
                "geometry_stats": nl["stats"], "extraction": None,
                "composition": None, "would_write": None,
                "layers_run": layers, "notes": notes}

    cls = classify(sweep_rec, None, filename)
    if drawing_class_override:
        cls = {"drawing_class": drawing_class_override,
               "confidence": "engineer_override", "score": None,
               "evidence": [], "runner_up": None, "all_scores": {}}
    layers.append(f"class:{cls['drawing_class']}({cls['confidence']})")

    # ---- 3. READING (one paid pass) --------------------------------------
    # Hydraulic and P&ID have their OWN engineer-approved extractors whose
    # output shape the generic tiled reader cannot produce — a hydraulic
    # function slice and a fluid lineup are not "labels and symbols". Route to
    # them; use the fused reader for the electrical family.
    dc = cls["drawing_class"]
    extraction: Dict[str, Any]
    if dc == "hydraulic":
        from pipeline import schematic_extract
        extraction = schematic_extract.discover_structure(pdf_bytes, page_index)
        extraction.setdefault("drawing_class", "hydraulic")
        layers.append("read:discover_structure")
    elif dc == "pid":
        from pipeline import pid_extract
        extraction = pid_extract.extract_pid(pdf_bytes, page_index)
        extraction.setdefault("drawing_class", "pid")
        layers.append("read:pid_extract")
    else:
        from pipeline import fused_tiles
        sub = {"plc": "plc_io", "interconnect": "connector_pinout"}.get(
            dc, "relay_terminal_wiring")
        extraction = fused_tiles.extract_sheet_fused(pdf_bytes, page_index,
                                                     sub_type=sub)
        layers.append("read:fused_tiles")
        # ---- 4. REBIND on the better labels ------------------------------
        # The fused read names things the local OCR could not. Rebinding the
        # measured nets to THOSE labels is what turns "net 278 carries three
        # unreadable strings" into "net 278 ties F3 to BILGE PUMP".
        tiles = extraction.get("_fused_tiles") or {}
        if tiles.get("labels"):
            from pipeline import netlist, net_trace
            labels, devices = fused_tiles.as_netlist_inputs(tiles)
            full = nl.get("_nets_full")
            if full is not None:
                net_trace.bind_labels(full, labels, max_dist=10.0)
                # THE ENGINEER-CONFIRMED SYMBOL TYPES GO IN TOO. `typed_symbols`
                # was set on the netlist and read by NOTHING: the 136 red-penned
                # shapes were loaded, counted in the stats, and dropped before
                # composition ever saw them. They matter beyond naming —
                # circuit.classify_sources decides polarity from the DEVICE
                # KINDS on a net, so an engineer-confirmed fuse or breaker is
                # direct evidence that its net is a supply. Bank types are
                # bound FIRST so the vision read's guess cannot displace them.
                bank = nl.get("typed_symbols") or []
                if bank:
                    netlist.bind_devices(
                        nl, [{"label": b.get("label") or "", "kind": b["kind"],
                              "bbox": b["bbox"]} for b in bank if b.get("bbox")],
                        page_size=None)
                    banked = list(nl.get("placed_devices") or [])
                    layers.append(f"bank:{len(bank)} confirmed types bound")
                else:
                    banked = []
                netlist.bind_devices(nl, devices, page_size=None)
                # bind_devices REPLACES placed_devices; keep both sources.
                nl["placed_devices"] = banked + list(nl.get("placed_devices") or [])
                nl = _refresh(nl, full)
                layers.append("rebind:fused_labels")
            else:
                notes.append("no raw segment graph — fused labels not bound "
                             "to nets; connectivity claims will be weak.")
        # ---- RE-CLASSIFY on the labels we just paid for -------------------
        # Measured on GM p20: classifying from the local OCR returned
        # 'unknown', so composition never ran and a paid read was discarded.
        # The fused labels are the good ones — the discipline verdict must be
        # taken from them, not from the text that was too poor to route on.
        if not drawing_class_override:
            better = classify(sweep_rec, tiles, filename)
            if better["drawing_class"] != "unknown":
                if better["drawing_class"] != dc:
                    notes.append(f"discipline revised {dc} -> "
                                 f"{better['drawing_class']} once the fused "
                                 f"labels were readable")
                cls, dc = better, better["drawing_class"]
                layers.append(f"reclass:{dc}({better['confidence']})")

    # ---- 5. MEASURED BLOCKS INTO THE EXTRACTION --------------------------
    from pipeline import netlist as _nlmod, circuit as _cir
    # Re-read the header off the labels we paid for — the free OCR header is
    # often unreadable on exactly the dense sheets where the header matters.
    tiles = (extraction.get("_fused_tiles") or {}) if extraction else {}
    if tiles.get("labels"):
        better_hdr = _dcmod.header_block({"labels": tiles["labels"]})
        if len(better_hdr) > len(header):
            header = better_hdr
    if header:
        extraction["_header"] = header
        extraction["_sheet_role"] = role
        layers.append("header:read")
    extraction["_netlist_digest"] = _nlmod.digest(nl, max_nets=60)
    extraction["_circuit_digest"] = _cir.digest(nl)
    extraction["_loop_completeness"] = _cir.loop_completeness(nl)
    layers.append("digests:netlist+circuit+loops")

    # ---- 6. REASONING ----------------------------------------------------
    # NEVER DISCARD A PAID READ BECAUSE THE CLASS IS UNSURE. The BAE
    # connector page was read for $0.74, classified `unknown`, and then
    # dropped without a single fact — the same waste as truncating the
    # extraction, just at the other end of the chain. If the sheet has real
    # drawn conductors and real labels it can be composed; compose it under
    # the best-scoring electrical-family class and SAY the class was a
    # fallback, so the engineer knows to check the routing rather than the
    # reading.
    if dc not in COMPOSE_CLASS and compose_sheet:
        n_cond = nl["stats"].get("conductors", 0)
        n_lab = nl["stats"].get("labels", 0)
        if n_cond >= 50 and n_lab >= 30:
            ranked = sorted((cls.get("all_scores") or {}).items(),
                            key=lambda kv: -kv[1])
            best = next((k for k, v in ranked if k in COMPOSE_CLASS and v > 0),
                        "electrical")
            notes.append(
                f"CLASS UNCERTAIN ('{dc}', best guess '{best}'): the sheet has "
                f"{n_cond} drawn conductors and {n_lab} labels, so it was "
                f"composed under '{best}' rather than discarding a paid read. "
                f"CHECK THE ROUTING on this sheet — the reading is sound, the "
                f"discipline is a fallback.")
            dc = best
            layers.append(f"fallback_class:{best}")

    composition = None
    if compose_sheet and dc in COMPOSE_CLASS:
        from pipeline.compose import compose
        png = _png(pdf_bytes, page_index)
        # OUTPUT ROOM SCALED TO THE SHEET. The default 16,384 was never
        # overridden, and GM-111 — 485 labels, ~80 loads — could not state its
        # systems inside it: the reply truncated mid-tool-call and the sheet
        # returned nothing, twice, for $2.29. A sheet's answer is roughly
        # proportional to how many devices it carries, so give it room in
        # proportion rather than discovering the ceiling by hitting it.
        n_labels = len((extraction.get("_fused_tiles") or {}).get("labels") or [])
        mt = 16384 if n_labels < 250 else 24000 if n_labels < 420 else 32000
        composition = compose(png, extraction, COMPOSE_CLASS[dc],
                              max_tokens=mt,
                              sheet_name=sheet_name or filename)
        layers.append(f"compose:{COMPOSE_CLASS[dc]}")
        # A COMPOSITION THAT CAME BACK EMPTY IS A FAILURE, NOT A RESULT.
        # GM-111 cost $2.29, read 43,117 segments and 485 labels cleanly, and
        # returned zero systems because the reply truncated — and the batch
        # ledger booked it `ok: True`. That is the same defect as counting a
        # failed download as done: the run looks complete and the sheet is
        # silently missing. Callers must be able to tell the two apart.
        if isinstance(composition, dict) and (
                composition.get("_malformed_response")
                or not (composition.get("equipment_groups")
                        or composition.get("infrastructure"))):
            notes.append(
                "COMPOSITION FAILED (malformed/truncated response) — the read "
                "succeeded and is cached, but nothing was composed. This sheet "
                "must be RE-RUN; it is not an empty sheet.")
            composition = None
    elif dc not in COMPOSE_CLASS:
        notes.append(f"discipline '{dc}' has no composition rules — the "
                     f"generic geometry path ran and nothing was reasoned "
                     f"over. This is a REPORTED gap, not a silent skip.")

    # ---- 7. WHAT WOULD BE WRITTEN (dry run) ------------------------------
    would_write = None
    if composition:
        from pipeline.compose_write import ComposeWriter
        w = ComposeWriter(dry_run=True)
        counts = w.write_composition(composition, {
            "sheet": sheet_name or filename, "page": page_index,
            "drawing_class": COMPOSE_CLASS[dc]})
        would_write = {"counts": counts, "decisions": w.decisions,
                       "uncertainties": w.uncertainties,
                       "flags": w.confirmation_flags,
                       "cross_refs": w.cross_refs}

    return {"drawing_class": dc, "class_evidence": cls,
            "sheet_role": role, "header": header,
            "geometry_stats": nl["stats"], "extraction": extraction,
            "loop_completeness": extraction.get("_loop_completeness"),
            "composition": composition, "would_write": would_write,
            "layers_run": layers, "notes": notes}


def _refresh(nl: Dict[str, Any], full: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Re-project the net list after rebinding, so the digests see the new
    labels. The full graph stays attached for any later pass."""
    nl["nets"] = [{"net_id": n["net_id"], "kind": n.get("kind", "conductor"),
                   "devices": n.get("devices", []),
                   "bbox": [round(v, 1) for v in n["bbox"]],
                   "n_segments": n["n_segments"],
                   "labels": [l["text"] for l in n.get("labels", [])]}
                  for n in full]
    bound = {t for n in nl["nets"] for t in n["labels"]}
    nl["stats"]["bound"] = len(bound)
    return nl


def _png(pdf_bytes: bytes, page_index: int, dpi: int = 200) -> bytes:
    import io
    import pypdfium2 as pdfium
    pil = pdfium.PdfDocument(pdf_bytes)[page_index].render(scale=dpi / 72).to_pil()
    b = io.BytesIO()
    pil.save(b, format="PNG")
    return b.getvalue()
