"""v2: exact-id match first (fixes the bare-short-id false-negative), token
overlap as fallback only. Reports genuine retype/same/lost, with 'same' split
into a spot-checkable list rather than assumed correct."""
import json, re, collections

flagged = json.load(open('/Users/captain/projects/gelliceaux/data/state/flagged_electrical_gelliceaux_001.json'))['create_flagged_entries']
new_pages = {}
for l in open('/Users/captain/projects/gelliceaux/data/ledgers/batch3_reextract_ledger.jsonl'):
    r = json.loads(l); new_pages[r['page']] = r

def toks(s): return set(t for t in re.split(r'[^a-z0-9]+', (s or '').lower()) if t)
def norm_id(s): return re.sub(r'[^a-z0-9]', '', str(s or '').lower())

totals = collections.Counter()
for pidx, new in sorted(new_pages.items()):
    new_els = [e for e in (new.get('wiring_elements') or []) if isinstance(e, dict)]
    by_exact_id = collections.defaultdict(list)
    for e in new_els:
        by_exact_id[norm_id(e.get('id'))].append(e)
    pf = [e for e in flagged if e['page'] == pidx + 1 and e['element_type'] in ('switch','status_signal')]
    retyped = same = lost = 0
    for f in pf:
        candidates = by_exact_id.get(norm_id(f.get('element_id')), [])
        if not candidates:
            ftoks = toks(f.get('element_id')) | toks(f.get('label'))
            best, best_ov = None, 0
            for e in new_els:
                ov = len((toks(str(e.get('id'))) | toks(e.get('label'))) & ftoks)
                if ov > best_ov: best, best_ov = e, ov
            candidates = [best] if best is not None and best_ov >= 2 else []
        if not candidates:
            lost += 1
        elif any(c['element_type'] != f['element_type'] for c in candidates):
            retyped += 1
        else:
            same += 1
    totals['retyped'] += retyped; totals['same'] += same; totals['lost'] += lost; totals['total'] += len(pf)
    print(f"page {pidx:3d} {str(new.get('drawing_no')):16s} flagged={len(pf):3d} retyped={retyped:3d} same={same:3d} lost={lost:3d}")

print()
print("TOTALS:", dict(totals))
print(f"genuinely accounted-for (retyped+verified-same): {totals['retyped']+totals['same']}/{totals['total']}")
print(f"genuinely lost/unmatched: {totals['lost']}/{totals['total']}")
