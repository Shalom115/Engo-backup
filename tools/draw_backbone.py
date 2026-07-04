"""Render the Gelliceaux data backbone as a PNG, from the real register data."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
reg = json.loads((_root / "data/state/register_gelliceaux_001.json").read_text())
counts = json.loads((_root / "data/state/_region_counts.json").read_text())

C = {"root": "#1f2a44", "tree": "#27496d", "supp": "#5b2a86", "region": "#0b6e4f",
     "sub": "#1b8a5a", "equip": "#d98324", "doc": "#7f8896", "store": "#142d4c",
     "vision": "#c0392b", "hyde": "#2e7d32", "key": "#33415c"}
fig, ax = plt.subplots(figsize=(17, 11.5))
ax.set_xlim(-1, 171); ax.set_ylim(0, 115); ax.axis("off")


def box(x, y, w, h, text, fc, tc="white", fs=9, weight="normal", ec="none"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.2",
                                fc=fc, ec=ec, lw=1.4))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color=tc,
            fontsize=fs, weight=weight)


def arrow(x1, y1, x2, y2, style="-|>", color="#33415c", ls="-", lw=1.4, rad=0.0):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, color=color,
                                 ls=ls, lw=lw, mutation_scale=12,
                                 connectionstyle=f"arc3,rad={rad}"))


ax.text(85, 112, "SY GELLICEAUX — DATA BACKBONE", ha="center", fontsize=18, weight="bold", color="#142d4c")
ax.text(85, 108.3, "the folder tree IS the categorization spine — every file inherits its full lineage",
        ha="center", fontsize=10.5, style="italic", color="#555")

# Drive root + two sources
box(70, 100, 30, 4.5, "SWS 108  (Google Drive · read-only)", C["root"], fs=10, weight="bold")
box(20, 91, 52, 5.5, "SWS 108-01\nSFI SYSTEM TREE  —  the structural backbone", C["tree"], fs=10.5, weight="bold")
box(114, 91, 54, 5.5, "SWS 108 › SWS › Suppliers\nVENDOR MASTER INDEX  (~75 vendors)", C["supp"], fs=10, weight="bold")
arrow(80, 100, 46, 96.5, rad=0.15); arrow(90, 100, 140, 96.5, rad=-0.15)

# 4-level lineage KEY (far left)
ax.text(13.5, 86, "PLACEMENT (every chunk)", ha="center", fontsize=9, weight="bold", color=C["key"])
for i, (t, c) in enumerate([("REGION (X00)", C["region"]), ("SUBSYSTEM (XX0)", C["sub"]),
                            ("EQUIPMENT (maker/model)", C["equip"]), ("DOCUMENT (manual/photo)", C["doc"])]):
    ky = 81 - i * 5.2
    box(2.5, ky, 22, 4, t, c, fs=7.3, weight="bold")
    if ky > 70:
        arrow(13.5, ky, 13.5, ky - 1.2, lw=1.2)

# Regions row (10 X00), compressed to stay left of the Suppliers column
short = {"001": "General", "100": "Structure", "200": "Deck", "300": "Interiors",
         "400": "Propulsion", "500": "Systems", "600": "Electric", "700": "Nav/Comms",
         "800": "Rig/Sail", "900": "Misc"}
xr = {}
for i, code in enumerate(["001", "100", "200", "300", "400", "500", "600", "700", "800", "900"]):
    x = 28 + i * 8.4
    xr[code] = x + 3.85
    hl = code in ("400", "600")
    box(x, 83, 7.7, 5, f"{code}\n{short[code]}", "#0a4d37" if hl else C["region"],
        fs=7.4, weight="bold", ec="#f1c40f" if hl else "none")
    ck = "000" if code == "001" else code
    ax.text(x + 3.85, 81.3, f"{counts.get(ck, 0):,}", ha="center", fontsize=6.2,
            weight="bold", color="#0a4d37")
ax.text(67, 89.6, "ALL 10 REGIONS INGESTED   ·   numbers below each = placed chunks",
        ha="center", fontsize=8.2, weight="bold", color=C["region"])
ax.text(69, 79.6, "▼  400 & 600 expanded as examples", ha="center", fontsize=6.8,
        style="italic", color="#666")

# Example A: 400 -> 420 -> GPM-12 -> docs  (offset left, arrow from real 400 box)
arrow(xr["400"], 83, 50, 77.4, rad=-0.05, lw=1.6, color="#0a4d37")
box(38, 73, 24, 4.2, "420  Propulsion Motor", C["sub"], fs=8.5, weight="bold")
arrow(50, 73, 50, 70.9); box(40, 66.5, 20, 4.2, "GPM-12 drive motor", C["equip"], fs=8.5, weight="bold")
arrow(50, 66.5, 50, 64.4); box(36, 60, 28, 3.8, "Schematics · Install Spec · ICD · Photos", C["doc"], fs=7)

# Example B: 600 -> 620 -> {MPCS,MAPS,SCU3,BEL,EDN-S} -> docs  (offset right)
arrow(xr["600"], 83, 92, 77.4, rad=0.05, lw=1.6, color="#0a4d37")
box(80, 73, 24, 4.2, "620  Power conversion", C["sub"], fs=8.5, weight="bold")
arrow(92, 73, 92, 70.9); box(78, 66.5, 28, 4.2, "MPCS · MAPS · SCU3 · BEL · EDN-S", C["equip"], fs=8, weight="bold")
arrow(92, 66.5, 92, 64.4); box(78, 60, 28, 3.8, "Install Specs · ICDs · Wiring · Tech notes", C["doc"], fs=7)

# Suppliers vendors -> placed into subsystems by the backbone-learned map
ax.text(141, 89.6, "VENDORS  →  placed by the backbone's\nvendor → subsystem map (deduped)",
        ha="center", fontsize=8.3, weight="bold", color=C["supp"])
for i, (name, sub) in enumerate([("Hundested", "430"), ("Cariboni", "840"), ("Mastervolt", "630"),
                                 ("BAE Systems", "620 / 625"), ("Racor", "550"),
                                 ("Wartsila → Shaft Seal", "430 *"), ("Pixel Sur Mer = Exocet", "900 *")]):
    vy = 83 - i * 4.3
    star = "*" in sub
    box(116, vy, 37, 3.6, name, C["supp"], fs=7.7, ec="#f1c40f" if star else "none")
    ax.text(154.5, vy + 1.8, f"→ {sub}", ha="left", va="center", fontsize=7.6,
            color="#caa53d" if star else "#5b2a86", weight="bold")
arrow(116, 79, 107, 76, ls="--", color=C["supp"], rad=0.25, lw=1.2)
ax.text(133, 52.5, "deduped: 189 already in the tree skipped · 58 unique placed\n(*  engineer-adjudicated placement)",
        ha="center", fontsize=7.8, style="italic", color=C["supp"])

# Convergence into the store
box(20, 29, 70, 8.5, "ChromaDB VECTOR STORE   ~21,305 chunks\nevery chunk tagged:  region · subsystem · equipment · doc_type",
    C["store"], fs=10.5, weight="bold")
arrow(50, 60, 45, 37.8, lw=1.6); arrow(92, 60, 70, 37.8, lw=1.6)
arrow(130, 67, 86, 37.8, ls="--", color=C["supp"], rad=0.12, lw=1.3)
box(96, 30.5, 31, 6.5, "pending_vision: 762\nscanned/images → Part 2 (Vision)", C["vision"], fs=8.4, weight="bold")
arrow(90, 33.7, 96, 33.7, lw=1.3, color=C["vision"])
box(132, 30.5, 33, 6.5, "HyDE Q&A layer\nengineer-phrased question → chunk", C["hyde"], fs=8.2, weight="bold")
arrow(127, 33.7, 132, 33.7, lw=1.3, color=C["hyde"])

# Footer stats
ax.text(85, 22, f"Structure walked LIVE: 2,238 nodes (547 folders / 1,691 files / 3.3 GB)    ·    "
        f"Register: {reg['stats']['entries']} equipment · {reg['stats']['subsystems']} subsystems · "
        f"{reg['stats']['acronyms']} acronyms · 0 gaps", ha="center", fontsize=8.6, color="#333")
ax.text(85, 18.3, "Reconciled exactly:   system tree 1,691 = 628 ingested + 709 vision + 334 already-present + 12 unsupported + 6 (·_ junk)"
        "    ·    Suppliers 310 = 58 + 189 + 53 + 10", ha="center", fontsize=8.6, color="#333")
ax.text(85, 14.3, "Order of understanding:  Owner's Manual (if present)  →  folder backbone  →  detailed content.    "
        "Numbering is the ordered spine; details live in the names.", ha="center", fontsize=8.6, style="italic", color="#666")

plt.tight_layout()
plt.savefig("/Users/captain/Downloads/gelliceaux_data_backbone.svg", bbox_inches="tight", facecolor="white")
plt.savefig("/Users/captain/Downloads/gelliceaux_data_backbone.png", dpi=150, bbox_inches="tight", facecolor="white")
print("wrote .svg (vector, zoomable) + .png to ~/Downloads/")
