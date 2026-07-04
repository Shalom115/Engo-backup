"""
Equipment Register builder — the vessel's categorization backbone.

Consumes a StructureProvider tree and reasons TOP-DOWN, carrying lineage down so
every node inherits its full placement:

    region (X00)  ->  subsystem (XX0)  ->  equipment  ->  document

The chain IS the product. A document's meaning is its position in the tree, so
every file emerges with region+subsystem+equipment+doc_type attached (or an
explicit "unplaced" flag for engineer review — never silently dropped).

Outputs (data/state/):
  register_<vessel>.json  — regions/subsystems/equipment with make/model/SFI,
                            functions, doc routes, source paths, confidence tier.
  vocab_<vessel>.json     — harvested acronym/nickname glossary (per-vessel layer
                            that sits on top of the base lexicon in HyDE).
  placements_<vessel>.json — every file with its full lineage (the manifest the
                            ingestion reconciliation checks against).

Confidence tiers: Confirmed (clean parse + numbered placement) / Flagged
(ambiguity, multi-placement, operational, possible-superseded) / Gap (numbered
subsystem with no equipment and no files).

CLI:
    python -m pipeline.register --emit                 # build + write all outputs
    python -m pipeline.register --region 400 --region 600   # print a tree summary
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import config
from providers.structure import SnapshotStructureProvider
from pipeline.folder_parse import (
    REGION_LABELS, region_for_code, strip_leading_code,
    is_doc_type_folder, is_non_equipment_group, parse_equipment_name,
    harvest_acronyms,
)

IMAGE_MIMES = ("image/",)
# A strong model token: letters then digits, optionally hyphenated (GPM-12, SCU3,
# QSB4.5). Used to detect the same physical unit placed in two systems.
_STRONG_TOKEN_RE = re.compile(r"[A-Z]{2,}-?\d[\w.\-]*")


def _slug(*parts: str) -> str:
    s = "-".join(p for p in parts if p)
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s or "x"


def _strong_tokens(name: str) -> set:
    return set(_STRONG_TOKEN_RE.findall(name.upper()))


class _Ctx:
    """Lineage carried down the recursion."""
    __slots__ = ("region_code", "region_label", "subsystem_code",
                 "subsystem_label", "equipment_id", "equipment_name",
                 "doc_type", "operational")

    def __init__(self, region_code=None, region_label=None, subsystem_code=None,
                 subsystem_label=None, equipment_id=None, equipment_name=None,
                 doc_type=None, operational=False):
        self.region_code = region_code
        self.region_label = region_label
        self.subsystem_code = subsystem_code
        self.subsystem_label = subsystem_label
        self.equipment_id = equipment_id
        self.equipment_name = equipment_name
        self.doc_type = doc_type
        self.operational = operational

    def copy(self, **kw):
        c = _Ctx(self.region_code, self.region_label, self.subsystem_code,
                 self.subsystem_label, self.equipment_id, self.equipment_name,
                 self.doc_type, self.operational)
        for k, v in kw.items():
            setattr(c, k, v)
        return c


def build_register(provider: SnapshotStructureProvider) -> Dict[str, Any]:
    """Walk the tree top-down and assemble the Register, glossary, placements."""
    nodes = provider.walk()
    root_id = provider.root_id
    idmap = {n["id"]: n for n in nodes}
    childmap: Dict[Optional[str], List[Dict[str, Any]]] = defaultdict(list)
    for n in nodes:
        childmap[n.get("parentId")].append(n)

    entries: Dict[str, Dict[str, Any]] = {}     # equipment_id -> entry
    placements: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    acronyms: Dict[str, str] = {}
    subsystems_seen: Dict[str, Dict[str, Any]] = {}   # code -> {label, region, has_content}

    def add_acronyms(name: str) -> None:
        for k, v in harvest_acronyms(name).items():
            # Keep the richest expansion we ever see for a token.
            if k not in acronyms or (not acronyms[k] and v):
                acronyms[k] = v

    def make_equipment_entry(node: Dict[str, Any], ctx: _Ctx) -> Dict[str, Any]:
        parsed = parse_equipment_name(node["name"])
        eid = _slug(ctx.subsystem_code or ctx.region_code or "x", node["name"])
        # Merge multi-placement: same strong model token already registered.
        tokens = _strong_tokens(node["name"])
        if tokens:
            for ex in entries.values():
                if tokens & ex["_tokens"]:
                    ex["source_paths"].append(node["path"])
                    ex["source_folder_ids"].append(node["id"])
                    fn = _function_of(ctx, node["name"])
                    if fn and fn not in ex["functions"]:
                        ex["functions"].append(fn)
                    ex["flags"].append(
                        f"multi-placement: also at {node['path']}")
                    ex["confidence"] = "Flagged"
                    return ex
        entry = {
            "equipment_id": eid,
            "name": parsed["name"],
            "make": parsed["make"],
            "model": parsed["model"],
            "category": parsed["category"],
            "acronyms": parsed["acronyms"],
            "region_code": ctx.region_code,
            "region_label": ctx.region_label,
            "subsystem_code": ctx.subsystem_code,
            "subsystem_label": ctx.subsystem_label,
            "functions": [f for f in [_function_of(ctx, node["name"])] if f],
            "source_paths": [node["path"]],
            "source_folder_ids": [node["id"]],
            "doc_subfolders": defaultdict(list),
            "file_count": 0,
            "flags": [],
            "_tokens": tokens,
        }
        entries[eid] = entry
        return entry

    def _function_of(ctx: _Ctx, name: str) -> Optional[str]:
        # Function from a "(Function)" in the equipment name, else the subsystem.
        p = parse_equipment_name(name)
        if p["category"]:
            return str(p["category"]).lower()
        if ctx.subsystem_label:
            return ctx.subsystem_label.lower()
        return None

    def place_file(node: Dict[str, Any], ctx: _Ctx) -> None:
        is_image = node.get("mime", "").startswith(IMAGE_MIMES)
        rec = {
            "file_id": node["id"], "name": node["name"], "path": node["path"],
            "mime": node.get("mime"), "ext": node.get("ext"),
            "size": node.get("fileSize"),
            "region_code": ctx.region_code, "region_label": ctx.region_label,
            "subsystem_code": ctx.subsystem_code,
            "subsystem_label": ctx.subsystem_label,
            "equipment_id": ctx.equipment_id, "equipment_name": ctx.equipment_name,
            "doc_type": ctx.doc_type, "operational": ctx.operational,
            "pending_vision": is_image,
            "unplaced": ctx.region_code is None and not ctx.operational,
        }
        placements.append(rec)
        if ctx.subsystem_code:
            subsystems_seen.setdefault(
                ctx.subsystem_code,
                {"label": ctx.subsystem_label, "region": ctx.region_code,
                 "has_content": False})
            subsystems_seen[ctx.subsystem_code]["has_content"] = True
        if ctx.equipment_id and ctx.equipment_id in entries:
            e = entries[ctx.equipment_id]
            e["file_count"] += 1
            if ctx.doc_type:
                e["doc_subfolders"][ctx.doc_type].append(node["name"])

    def recurse(node: Dict[str, Any], ctx: _Ctx) -> None:
        for child in sorted(childmap.get(node["id"], []), key=lambda c: c["name"]):
            add_acronyms(child["name"])
            if child["type"] != "folder":
                # Skip Office lock/temp files and zero-byte files (counted, with reason).
                if child["name"].startswith("~$") or child.get("fileSize") == 0:
                    skipped.append({
                        "file_id": child["id"], "name": child["name"],
                        "path": child["path"],
                        "reason": "office lock/temp" if child["name"].startswith("~$")
                                  else "zero-byte",
                    })
                    continue
                # Loose files directly under the vessel root are placed at root level.
                if node["id"] == root_id:
                    place_file(child, ctx.copy(region_label="(vessel root)",
                                               operational=True))
                else:
                    place_file(child, ctx)
                continue

            name = child["name"]
            code, rest = strip_leading_code(name)

            # Region: a coded or named group directly under the vessel root.
            if node["id"] == root_id:
                if code:
                    rc = region_for_code(code)
                    op = (rc == "000") or is_non_equipment_group(name)
                    recurse(child, ctx.copy(
                        region_code=rc, region_label=REGION_LABELS.get(rc, rest),
                        subsystem_code=None, subsystem_label=None,
                        equipment_id=None, equipment_name=None,
                        doc_type=None, operational=op))
                elif is_non_equipment_group(name):
                    recurse(child, ctx.copy(
                        region_code=None, region_label=name, operational=True,
                        subsystem_code=None, equipment_id=None, doc_type=None))
                else:
                    recurse(child, ctx.copy(region_label=name, operational=True))
                continue

            # Subsystem: a coded folder whose region matches the current region.
            if code and ctx.region_code and region_for_code(code) == ctx.region_code \
                    and not ctx.subsystem_code:
                subsystems_seen.setdefault(
                    code, {"label": rest, "region": ctx.region_code,
                           "has_content": False})
                recurse(child, ctx.copy(subsystem_code=code, subsystem_label=rest,
                                        equipment_id=None, equipment_name=None,
                                        doc_type=None))
                continue

            # Document-type routing folder: keep equipment context, tag doc_type.
            if is_doc_type_folder(name):
                recurse(child, ctx.copy(doc_type=rest))
                continue

            # Otherwise: equipment (or sub-equipment). Operational groups don't
            # register equipment, but their files still get placed.
            if ctx.operational:
                recurse(child, ctx.copy(doc_type=rest))
                continue
            entry = make_equipment_entry(child, ctx)
            if ctx.subsystem_code:
                subsystems_seen[ctx.subsystem_code]["has_content"] = True
            recurse(child, ctx.copy(equipment_id=entry["equipment_id"],
                                    equipment_name=entry["name"]))

    recurse(idmap[root_id], _Ctx())

    # --- Confidence tiers + Gaps ---
    for e in entries.values():
        del e["_tokens"]
        e["doc_subfolders"] = dict(e["doc_subfolders"])
        identified = bool(e["make"] or e["model"] or e["acronyms"])
        if e["flags"]:
            e["confidence"] = "Flagged"
        elif identified and e["region_code"] and e["subsystem_code"]:
            e["confidence"] = "Confirmed"
        else:
            e["confidence"] = "Flagged"
            if not e["subsystem_code"]:
                e["flags"].append("no subsystem placement")
            if not identified:
                e["flags"].append("name did not parse to make/model")

    gaps = [
        {"subsystem_code": code, "label": info["label"], "region": info["region"]}
        for code, info in sorted(subsystems_seen.items())
        if not info["has_content"]
    ]

    entry_list = sorted(entries.values(),
                        key=lambda e: (e["region_code"] or "zzz",
                                       e["subsystem_code"] or "zzz", e["name"]))
    tiers = {"Confirmed": 0, "Flagged": 0}
    for e in entry_list:
        tiers[e["confidence"]] = tiers.get(e["confidence"], 0) + 1

    unplaced = [p for p in placements if p["unplaced"]]
    pending_vision = [p for p in placements if p["pending_vision"]]

    return {
        "vessel_namespace": config.VESSEL_NAMESPACE,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_walked_at": provider.walked_at,
        "source_incomplete": bool(provider.unwalked),
        "stats": {
            "entries": len(entry_list),
            "tiers": tiers,
            "subsystems": len(subsystems_seen),
            "gaps": len(gaps),
            "files_placed": len(placements),
            "files_unplaced": len(unplaced),
            "files_pending_vision": len(pending_vision),
            "files_skipped": len(skipped),
            "acronyms": len(acronyms),
        },
        "entries": entry_list,
        "acronyms": dict(sorted(acronyms.items())),
        "gaps": gaps,
        "skipped": skipped,
        "placements": placements,
    }


def _print_region(reg: Dict[str, Any], region_code: str) -> None:
    ents = [e for e in reg["entries"] if e["region_code"] == region_code]
    label = REGION_LABELS.get(region_code, region_code)
    print(f"\n=== {region_code} {label} — {len(ents)} equipment entries ===")
    by_sub: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in ents:
        by_sub[f"{e['subsystem_code']} {e['subsystem_label']}"].append(e)
    for sub in sorted(by_sub):
        print(f"  {sub}")
        for e in by_sub[sub]:
            tag = {"Confirmed": "✓", "Flagged": "⚑"}.get(e["confidence"], "?")
            ident = e["make"] or e["model"] or e["name"]
            acr = f" [{','.join(e['acronyms'])}]" if e["acronyms"] else ""
            fns = f" fn={'/'.join(e['functions'])}" if e["functions"] else ""
            docs = (" docs=" + ",".join(sorted(e["doc_subfolders"]))
                    if e["doc_subfolders"] else "")
            print(f"    {tag} {ident}{acr}{fns}  files={e['file_count']}{docs}")
            for fl in e["flags"]:
                print(f"        ⚑ {fl}")


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.register")
    ap.add_argument("--emit", action="store_true",
                    help="Write register/vocab/placements JSON to data/state/.")
    ap.add_argument("--region", action="append", default=[],
                    help="Print a tree summary for this region code (repeatable).")
    args = ap.parse_args(argv)

    provider = SnapshotStructureProvider()
    reg = build_register(provider)
    s = reg["stats"]

    print(f"=== EQUIPMENT REGISTER ({reg['vessel_namespace']}) ===")
    if reg["source_incomplete"]:
        print("  NOTE: source structure walk is INCOMPLETE — register is partial.")
    print(f"  entries={s['entries']}  Confirmed={s['tiers'].get('Confirmed',0)}  "
          f"Flagged={s['tiers'].get('Flagged',0)}")
    print(f"  subsystems={s['subsystems']}  gaps={s['gaps']}")
    print(f"  files placed={s['files_placed']}  unplaced={s['files_unplaced']}  "
          f"pending_vision={s['files_pending_vision']}  skipped={s['files_skipped']}")
    print(f"  acronyms harvested={s['acronyms']}")

    for rc in args.region:
        _print_region(reg, rc)

    if args.emit:
        base = config.STATE_DIR
        vessel = config.VESSEL_NAMESPACE
        (base / f"register_{vessel}.json").write_text(
            json.dumps({k: v for k, v in reg.items() if k != "placements"},
                       indent=2, ensure_ascii=False), encoding="utf-8")
        (base / f"vocab_{vessel}.json").write_text(
            json.dumps({"vessel_namespace": vessel,
                        "generated_at": reg["built_at"],
                        "acronyms": reg["acronyms"]},
                       indent=2, ensure_ascii=False), encoding="utf-8")
        (base / f"placements_{vessel}.json").write_text(
            json.dumps({"vessel_namespace": vessel,
                        "built_at": reg["built_at"],
                        "placements": reg["placements"]},
                       indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  wrote register_{vessel}.json, vocab_{vessel}.json, "
              f"placements_{vessel}.json")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
