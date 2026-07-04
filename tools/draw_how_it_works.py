"""A plain-English picture of how Engo works: Claude fills the box, Engo searches it."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

C = {"claude": "#27496d", "box": "#142d4c", "engo": "#2e7d32",
     "you": "#d98324", "arrow": "#5b6472"}
fig, ax = plt.subplots(figsize=(14.5, 9))
ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")


def box(cx, cy, w, h, text, fc, fs=10.5, weight="bold", tc="white"):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                 boxstyle="round,pad=0.4,rounding_size=1.6", fc=fc, ec="none"))
    ax.text(cx, cy, text, ha="center", va="center", color=tc, fontsize=fs, weight=weight)


def arr(x1, y1, x2, y2, color=C["arrow"], lw=2.2, rad=0.0, ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", color=color,
                 lw=lw, ls=ls, mutation_scale=20, connectionstyle=f"arc3,rad={rad}"))


ax.text(50, 96, "HOW ENGO WORKS", ha="center", fontsize=23, weight="bold", color=C["box"])
ax.text(50, 91, "Claude builds & fills the box  ·  Engo searches it and answers you",
        ha="center", fontsize=12.5, style="italic", color="#555")

# ---- TOP LANE: SETUP (Claude) ----
ax.text(4, 84.5, "SETUP — done once  ·  built by Claude (me)", fontsize=12.5,
        weight="bold", color=C["claude"], ha="left")
box(13, 74, 19, 12, "Boat documents\non Google Drive", "#6b7a99", fs=10.5)
box(38, 74, 22, 12, "1.  Read the folder map\nwhat's aboard, and\nwhich system each is in", C["claude"])
box(64, 74, 24, 12, "2.  Read every document\ncut into bite-size pieces,\nstamp each with its system", C["claude"])
box(89, 74, 18, 12, "3.  File them all\nin the search box", C["claude"])
arr(22.5, 74, 26.8, 74); arr(49.2, 74, 52, 74); arr(76.2, 74, 80, 74)

# ---- THE BOX (center) ----
box(50, 50, 54, 12, "THE SEARCH BOX\n21,305 stamped pieces of real document text\nfinds things by MEANING, not exact words",
    C["box"], fs=12)
arr(89, 68, 60, 56.5, color=C["claude"], rad=-0.25, lw=2.4)
ax.text(83, 62.5, "Claude fills it", color=C["claude"], fontsize=10, style="italic", ha="center")
arr(40, 44, 30, 33.5, color=C["engo"], rad=-0.25, lw=2.4)
ax.text(24, 39, "Engo reads it", color=C["engo"], fontsize=10, style="italic", ha="center")

# ---- BOTTOM LANE: USE (Engo) ----
ax.text(4, 36, "EVERY QUESTION — every time  ·  by Engo", fontsize=12.5,
        weight="bold", color=C["engo"], ha="left")
box(13, 24, 19, 12, "You ask:\n\"bow thruster\nfault?\"", C["you"])
box(38, 24, 22, 12, "4.  Engo searches\nthe box by meaning", C["engo"])
box(64, 24, 24, 12, "5.  Pulls the few\nmost-relevant pieces", C["engo"])
box(89, 24, 18, 12, "6.  Reads them +\nkey boat-facts →\nanswers, names source", C["engo"])
arr(22.5, 24, 26.8, 24); arr(49.2, 24, 52, 24); arr(76.2, 24, 80, 24)
# loop the answer back to you
arr(89, 18, 13, 18, color=C["you"], rad=0.18, lw=2.0)
ax.text(51, 11.5, "answer comes back to you, with its source", color=C["you"],
        fontsize=10, style="italic", ha="center")

# ---- footer ----
ax.text(50, 5, "Today: 680 documents readable as text.   Next build = \"vision\", "
        "so Engo can also read the 762 scanned drawings, schematics & photos.",
        ha="center", fontsize=10, color="#666")

plt.tight_layout()
plt.savefig("/Users/captain/Downloads/engo_how_it_works.svg", bbox_inches="tight", facecolor="white")
plt.savefig("/Users/captain/Downloads/engo_how_it_works.png", dpi=150, bbox_inches="tight", facecolor="white")
print("wrote engo_how_it_works.svg + .png to ~/Downloads/")
