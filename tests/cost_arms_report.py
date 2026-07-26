"""Side-by-side: what each arm cost, read, and WOULD HAVE WRITTEN."""
import json, sys, glob, collections
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

D = config.STATE_DIR / "vision_bench/arms"
ARMS = ["A0_BASELINE", "A1_FUSED", "A2_CACHED", "A3_CHEAP"]
SHEETS = [(19, "BILGE SYSTEM"), (21, "AFT SERVICE PUMPS"),
          (5, "230V AFT DISTRIBUTION PANEL")]


def load(arm, page):
    p = D / f"{arm}_p{page}.json"
    return json.loads(p.read_text()) if p.exists() else None


def facts_of(d):
    """The would-attach decisions, as (node, kind, label) — the Register delta."""
    out = []
    for n in (d.get("would_write") or []):
        if n.get("action") in ("would_attach", "attached"):
            out.append((n.get("node"), n.get("kind"), (n.get("label") or "")[:60]))
    return out


print("=" * 100)
print("COST + OUTPUT BY ARM")
print("=" * 100)
print(f"{'sheet':<30}{'arm':<14}{'usd':>7}{'sec':>6}{'grp':>5}{'facts':>7}"
      f"{'nodes':>7}{'unc':>5}{'flags':>7}{'bound':>7}")
tot = collections.defaultdict(lambda: {"usd": 0.0, "facts": 0, "grp": 0,
                                       "nodes": set(), "unc": 0, "flags": 0})
for page, title in SHEETS:
    for arm in ARMS:
        d = load(arm, page)
        if not d:
            print(f"{title[:28]:<30}{arm:<14}{'-':>7}")
            continue
        c = d.get("composition") or {}
        f = facts_of(d)
        nodes = {x[0] for x in f if x[0]}
        t = tot[arm]
        t["usd"] += d.get("usd", 0)
        t["facts"] += len(f)
        t["grp"] += len(c.get("equipment_groups") or [])
        t["nodes"] |= nodes
        t["unc"] += len(c.get("uncertainties") or [])
        t["flags"] += len(d.get("flags") or [])
        print(f"{title[:28]:<30}{arm:<14}{d.get('usd',0):>7.3f}{d.get('seconds',0):>6}"
              f"{len(c.get('equipment_groups') or []):>5}{len(f):>7}{len(nodes):>7}"
              f"{len(c.get('uncertainties') or []):>5}{len(d.get('flags') or []):>7}"
              f"{d.get('netlist_stats',{}).get('bound_to_conductor',0):>7}")
    print()

print("=" * 100)
print("TOTALS (3 sheets)")
print("=" * 100)
print(f"{'arm':<14}{'usd':>8}{'$/sheet':>10}{'groups':>8}{'facts':>8}"
      f"{'nodes':>8}{'unc':>6}{'flags':>7}")
base = tot["A0_BASELINE"]["usd"] or 1
for arm in ARMS:
    t = tot[arm]
    print(f"{arm:<14}{t['usd']:>8.3f}{t['usd']/3:>10.3f}{t['grp']:>8}"
          f"{t['facts']:>8}{len(t['nodes']):>8}{t['unc']:>6}{t['flags']:>7}"
          f"   ({100*t['usd']/base:.0f}% of baseline)")

print()
print("=" * 100)
print("WHAT EACH ARM WOULD WRITE — node coverage vs baseline")
print("=" * 100)
for page, title in SHEETS:
    print(f"\n--- p{page} {title}")
    per = {}
    for arm in ARMS:
        d = load(arm, page)
        per[arm] = {x[0] for x in facts_of(d)} if d else set()
    allnodes = sorted(set().union(*per.values()))
    if not allnodes:
        print("   (no nodes resolved by any arm)")
        continue
    print(f"   {'node':<44}" + "".join(f"{a.split('_')[0]:>6}" for a in ARMS))
    for n in allnodes:
        print(f"   {str(n)[:42]:<44}" +
              "".join(("   yes" if n in per[a] else "    - ") for a in ARMS))
    only = {a: per[a] - set().union(*[per[b] for b in ARMS if b != a])
            for a in ARMS}
    for a in ARMS:
        if only[a]:
            print(f"   ONLY {a}: {sorted(only[a])}")

print()
print("=" * 100)
print("FACT-LEVEL DIFF on the densest sheet (what actually lands on each node)")
print("=" * 100)
best = max(SHEETS, key=lambda s: len(facts_of(load("A0_BASELINE", s[0]) or {})))
page, title = best
print(f"sheet: p{page} {title}\n")
for arm in ARMS:
    d = load(arm, page)
    if not d:
        continue
    f = facts_of(d)
    print(f"--- {arm}  ({len(f)} facts)")
    by_node = {}
    for node, kind, label in f:
        by_node.setdefault(node, []).append(f"{kind}: {label}")
    for node, items in sorted(by_node.items(), key=lambda kv: str(kv[0])):
        print(f"    {node}")
        for it in items[:6]:
            print(f"        {it[:96]}")
    print()
