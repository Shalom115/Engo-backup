"""
VERIFY LOCAL SETUP — prove the machine Engo actually runs on is on the CURRENT
protocol, before any sweep or agent query.

"The repo is updated" is not the same as "this machine is updated". Git does
not touch: gitignored data (.env, data/chroma), stale __pycache__ that can
shadow a new module, missing system dependencies, or a dirty working tree that
silently blocked the merge. This script checks the things that actually break,
and prints PASS/FAIL per check with the real value it found.

    python3.12 tools/verify_local_setup.py

Exit 0 = this machine is current and safe to sweep.
Exit 1 = at least one BLOCKER. Fix it before running anything else; the
         failure text says exactly what to do.

Nothing here writes, downloads, or calls an API.
"""
from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "state"

results = []  # (level, name, ok, detail)   level: BLOCKER | WARN


def check(level, name, ok, detail=""):
    results.append((level, name, bool(ok), detail))


def sh(cmd):
    try:
        return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                              shell=True).stdout.strip()
    except Exception as e:
        return f"<error {e}>"


# ---------------------------------------------------------------- 1. git
head = sh("git rev-parse --short HEAD")
branch = sh("git rev-parse --abbrev-ref HEAD")
dirty = sh("git status --porcelain")
check("WARN", "git branch", True, f"{branch} @ {head}")
check("WARN", "working tree clean", not dirty,
      "clean" if not dirty else f"{len(dirty.splitlines())} modified/untracked "
      f"file(s) — a dirty tree can block a merge; commit or stash them")

# ---------------------------------------------------------------- 2. tools
REQUIRED_TOOLS = [
    "extract_document.py", "sweep_drive.py", "symbol_typing.py",
    "sheet_legend.py", "symbol_bank_build.py", "symbol_bank_apply.py",
    "symbol_bank_worksheet.py", "glyph_font_decode.py", "electrical_lint.py",
    "routing_preview.py", "probe_corpus.py", "run_book_extract.py",
    "vector_extract_poc.py", "vector_probe.py", "label_vision_verify.py",
]
missing = [t for t in REQUIRED_TOOLS if not (ROOT / "tools" / t).exists()]
check("BLOCKER", "vector-first tools present", not missing,
      "all 15 present" if not missing else f"MISSING: {missing} — "
      f"the merge did not land; re-run the fetch/merge")

# ---------------------------------------------------------------- 3. deps
for mod, hint in (("fitz", "pip install pymupdf"), ("PIL", "pip install pillow")):
    try:
        importlib.import_module(mod)
        check("BLOCKER", f"python module {mod}", True, "importable")
    except Exception:
        check("BLOCKER", f"python module {mod}", False,
              f"NOT importable on {sys.executable} — {hint}")
tess = shutil.which("tesseract")
check("BLOCKER", "tesseract on PATH", bool(tess),
      tess or "NOT FOUND — brew install tesseract (needed for OCR on "
              "vector sheets with no text layer)")
check("WARN", "python version", sys.version_info[:2] >= (3, 10),
      f"{sys.version.split()[0]} at {sys.executable}")

# ---------------------------------------------------------------- 4. stale bytecode
pyc = list((ROOT / "tools").rglob("__pycache__")) + \
      list((ROOT / "pipeline").rglob("__pycache__"))
check("WARN", "no stale bytecode caches", not pyc,
      "none" if not pyc else f"{len(pyc)} __pycache__ dir(s) — delete them so "
      f"a new module cannot be shadowed: find . -name __pycache__ -prune "
      f"-exec rm -rf {{}} +")

# ---------------------------------------------------------------- 5. state assets
bank_p = STATE / "symbol_bank_gm_marine_CONFIRMED.json"
if bank_p.exists():
    bank = json.loads(bank_p.read_text())
    cl = bank.get("clusters", [])
    typed = [c for c in cl if (c.get("engineer_type") or "").strip()]
    # fingerprints must be the STABLE hex form, not old python hash ints
    hexish = sum(1 for c in cl
                 if isinstance(c.get("fingerprint"), str)
                 and all(ch in "0123456789abcdef" for ch in c["fingerprint"])
                 and len(c["fingerprint"]) >= 16)
    check("BLOCKER", "symbol bank confirmed", len(typed) >= 130,
          f"{len(typed)}/{len(cl)} shapes typed by the engineer")
    check("BLOCKER", "symbol bank uses STABLE fingerprints", hexish == len(cl),
          f"{hexish}/{len(cl)} stable-hex — if this fails the bank is the OLD "
          f"python-hash build and will type 0%: rebuild with "
          f"tools/symbol_bank_build.py then re-apply the red-pen")
else:
    check("BLOCKER", "symbol bank confirmed", False, f"MISSING {bank_p.name}")

for f, blocker in (("load_map_gelliceaux_001.json", True),
                   ("register_gelliceaux_001.json", True),
                   ("revision_index_gelliceaux_001.json", True),
                   ("structure_gelliceaux_001.json", False)):
    p = STATE / f
    check("BLOCKER" if blocker else "WARN", f"state: {f}", p.exists(),
          f"{p.stat().st_size//1024} KB" if p.exists() else "MISSING")

# ---------------------------------------------------------------- 6. prompts current
gl = ROOT / "prompts" / "drawing_symbol_glossary.md"
if gl.exists():
    g = gl.read_text()
    need = {
        "XA arrow-direction rule": "ARROW DIRECTION",
        "power-conversion block rule": "POWER-CONVERSION BLOCK",
        "the dot rule": "THE DOT RULE",
        "fused terminal": "FUSED TERMINAL",
        "symbol-bank precedence": "SYMBOL BANK",
    }
    for label, token in need.items():
        check("BLOCKER", f"glossary has {label}", token in g,
              "present" if token in g else
              "ABSENT — this machine is on the OLD glossary; the merge did "
              "not land prompts/")
else:
    check("BLOCKER", "drawing_symbol_glossary.md", False, "MISSING")

# ---------------------------------------------------------------- 7. live import
sys.path.insert(0, str(ROOT / "tools"))
try:
    from symbol_typing import load_bank  # noqa: E402
    b = load_bank()
    check("BLOCKER", "symbol typing loads the bank", len(b) >= 130,
          f"{len(b)} shapes resolvable by fingerprint")
except Exception as e:
    check("BLOCKER", "symbol typing loads the bank", False, f"{type(e).__name__}: {e}")
try:
    import extract_document, sweep_drive, sheet_legend  # noqa: E402,F401
    check("BLOCKER", "dispatcher + sweep import cleanly", True, "ok")
except Exception as e:
    check("BLOCKER", "dispatcher + sweep import cleanly", False,
          f"{type(e).__name__}: {e}")

# ---------------------------------------------------------------- 8. write-hold
# Test for a real WRITE PATH, not a mention. A substring search matched this
# script's own check and sweep_drive's docstring line "no node_write import
# anywhere in this chain" — i.e. the documentation asserting safety tripped
# the safety test. Parse the AST for actual imports/calls instead.
import ast as _ast
offenders = []
for t in (ROOT / "tools").glob("*.py"):
    try:
        tree = _ast.parse(t.read_text())
    except SyntaxError:
        continue
    for node in _ast.walk(tree):
        if isinstance(node, (_ast.Import, _ast.ImportFrom)):
            mods = ([a.name for a in node.names]
                    + ([node.module] if isinstance(node, _ast.ImportFrom)
                       and node.module else []))
            if any("node_write" in (m or "") for m in mods):
                offenders.append(f"{t.name}: imports node_write")
        if isinstance(node, _ast.keyword) and node.arg == "dry_run":
            v = node.value
            if isinstance(v, _ast.Constant) and v.value is False:
                offenders.append(f"{t.name}: dry_run=False")
check("BLOCKER", "no Register writes in the sweep chain", not offenders,
      "none of the 15 tools import node_write or set dry_run=False"
      if not offenders else f"WRITE PATH PRESENT in {offenders}")

# ---------------------------------------------------------------- report
print("\n=== LOCAL SETUP VERIFICATION ===")
blockers = 0
for level, name, ok, detail in results:
    mark = "PASS" if ok else ("FAIL" if level == "BLOCKER" else "warn")
    if not ok and level == "BLOCKER":
        blockers += 1
    print(f"[{mark:4}] {name:42} {detail}")
print(f"\n{len(results)} checks, {blockers} blocker(s).")
if blockers:
    print("NOT READY — fix the FAIL lines above, then re-run this script.")
    sys.exit(1)
print("READY — this machine is on the current protocol.")
sys.exit(0)
