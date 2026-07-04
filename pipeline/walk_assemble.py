"""
Structure walk assembler + completeness reconciliation.

Two sources feed the same finalizer, producing the canonical
``data/state/structure_<vessel>.json`` (every node: folders AND files, full path,
id, mime, parent, size, ext, modifiedTime, region, walked_at):

  - LIVE (``--gdrive``): walks the Drive tree via GoogleDriveStructureProvider in
    one pass. Complete by construction (BFS of everything reachable). This is the
    authoritative path once a read-only credential is configured.

  - WAVES (default): reconstructs the tree from agent-mediated wave files under
    ``data/state/raw_listings/wave_*.json`` and PROVES completeness — every folder
    discovered as a node must itself have been walked, else it is reported as
    ``unwalked`` and the walk is incomplete. Used before the connector exists.

CLI:
    python -m pipeline.walk_assemble --root <id> --root-name "SWS 108-01" --gdrive --emit
    python -m pipeline.walk_assemble --root <id> --root-name "SWS 108-01"          # waves, reconcile-only
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import config

FOLDER_MIME = "application/vnd.google-apps.folder"
RAW_DIR = config.STATE_DIR / "raw_listings"


def _load_waves() -> Dict[str, List[Dict[str, Any]]]:
    """Merge all wave files into {parentId: [child nodes]} (later waves win)."""
    listings: Dict[str, List[Dict[str, Any]]] = {}
    for wf in sorted(glob.glob(str(RAW_DIR / "wave_*.json"))):
        data = json.loads(Path(wf).read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"Wave file {wf} must be a JSON array of records.")
        for rec in data:
            listings[rec["parentId"]] = rec.get("files", [])
    return listings


def _nodes_from_waves(root_id: str, root_name: str):
    """Build node table + unwalked list from wave files."""
    listings = _load_waves()
    nodes: Dict[str, Dict[str, Any]] = {
        root_id: {"id": root_id, "name": root_name, "type": "folder",
                  "mime": FOLDER_MIME, "parentId": None}
    }
    for parent_id, children in listings.items():
        for c in children:
            mime = c.get("mimeType", "")
            is_folder = mime == FOLDER_MIME
            nodes[c["id"]] = {
                "id": c["id"], "name": c.get("title", ""),
                "type": "folder" if is_folder else "file",
                "mime": mime, "parentId": c.get("parentId", parent_id),
                "fileSize": int(c["fileSize"]) if c.get("fileSize") else None,
                "ext": c.get("fileExtension"), "modifiedTime": c.get("modifiedTime"),
            }
    walked = set(listings.keys())
    folder_ids = {nid for nid, n in nodes.items() if n["type"] == "folder"}
    unwalked = sorted((nid for nid in folder_ids if nid not in walked),
                      key=lambda i: nodes[i]["name"])
    return nodes, unwalked


def _nodes_from_gdrive(root_id: str, root_name: str):
    """Walk the live Drive tree via the connector. Complete by construction."""
    from providers.structure import GoogleDriveStructureProvider
    prov = GoogleDriveStructureProvider(root_id, root_name)
    node_list = prov.walk()
    nodes = {n["id"]: n for n in node_list}
    nodes.setdefault(root_id, {"id": root_id, "name": root_name, "type": "folder",
                               "mime": FOLDER_MIME, "parentId": None})
    return nodes, []


def finalize_structure(nodes: Dict[str, Dict[str, Any]], root_id: str,
                       root_name: str, unwalked: List[str]) -> Dict[str, Any]:
    """Compute paths, regions, stats; assemble the canonical structure dict."""
    def path_of(nid: str) -> str:
        parts: List[str] = []
        seen: set = set()
        cur: Optional[str] = nid
        while cur and cur in nodes and cur not in seen:
            seen.add(cur)
            parts.append(nodes[cur]["name"])
            cur = nodes[cur]["parentId"]
        return "/".join(reversed(parts))

    def region_of(nid: str) -> Optional[str]:
        seen: set = set()
        cur: Optional[str] = nid
        while cur and cur in nodes and cur not in seen:
            seen.add(cur)
            parent = nodes[cur]["parentId"]
            if parent == root_id:
                return nodes[cur]["name"]
            cur = parent
        return None

    for nid, n in nodes.items():
        n["path"] = path_of(nid)
        n["region"] = region_of(nid)

    files = [n for n in nodes.values() if n["type"] == "file"]
    folders = [n for n in nodes.values() if n["type"] == "folder"]
    per_region: Dict[str, Dict[str, int]] = {}
    for n in nodes.values():
        reg = n.get("region")
        if reg is None:
            continue
        b = per_region.setdefault(reg, {"folders": 0, "files": 0})
        b["folders" if n["type"] == "folder" else "files"] += 1
    by_mime: Dict[str, int] = {}
    for n in files:
        by_mime[n["mime"]] = by_mime.get(n["mime"], 0) + 1
    total_bytes = sum(n.get("fileSize") or 0 for n in files)

    return {
        "vessel_namespace": config.VESSEL_NAMESPACE,
        "root_id": root_id, "root_name": root_name,
        "walked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stats": {
            "total_nodes": len(nodes), "folders": len(folders), "files": len(files),
            "folders_unwalked": len(unwalked), "total_file_bytes": total_bytes,
            "files_by_mime": dict(sorted(by_mime.items(), key=lambda kv: -kv[1])),
            "per_region": dict(sorted(per_region.items())),
        },
        "unwalked": [{"id": i, "name": nodes[i]["name"], "path": nodes[i]["path"]}
                     for i in unwalked],
        "nodes": sorted(nodes.values(), key=lambda n: n["path"]),
    }


def assemble(root_id: str, root_name: str, source: str = "waves") -> Dict[str, Any]:
    if source == "gdrive":
        nodes, unwalked = _nodes_from_gdrive(root_id, root_name)
    else:
        nodes, unwalked = _nodes_from_waves(root_id, root_name)
    return finalize_structure(nodes, root_id, root_name, unwalked)


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.walk_assemble")
    ap.add_argument("--root", required=True)
    ap.add_argument("--root-name", required=True)
    ap.add_argument("--gdrive", action="store_true",
                    help="Walk the live Drive tree via the connector (complete).")
    ap.add_argument("--emit", action="store_true",
                    help="Write structure_<vessel>.json.")
    args = ap.parse_args(argv)

    structure = assemble(args.root, args.root_name,
                         source="gdrive" if args.gdrive else "waves")
    s = structure["stats"]
    src = "LIVE gdrive" if args.gdrive else "wave files"
    print(f"=== WALK RECONCILIATION ({structure['vessel_namespace']}) — {src} ===")
    print(f"  nodes={s['total_nodes']}  folders={s['folders']}  files={s['files']}")
    print(f"  UNWALKED={s['folders_unwalked']}  bytes={s['total_file_bytes']:,}")
    print("  per-region (folders/files):")
    for reg, c in s["per_region"].items():
        print(f"    {reg:<48} {c['folders']:>4} / {c['files']:>4}")
    print("  files by mime:")
    for mime, n in s["files_by_mime"].items():
        print(f"    {n:>4}  {mime}")

    if structure["unwalked"]:
        print(f"\n  !!! {len(structure['unwalked'])} UNWALKED folder(s) remain.")
    else:
        print("\n  ✓ COMPLETE: every folder walked.")

    if args.emit:
        out = config.STATE_DIR / f"structure_{config.VESSEL_NAMESPACE}.json"
        out.write_text(json.dumps(structure, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        print(f"  wrote {out}")
    return 0 if not structure["unwalked"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
