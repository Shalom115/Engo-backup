"""
RED-PEN TRACEABILITY — standing gate (2026-07-22).

Every engineer red-pen rule from every session must remain present in
code/register. If this test fails, a rule was silently dropped — the exact
failure class that wasted the engineer's review time on stale results. Run in
CI and before any composition/write run.

Each check maps: (red-pen source, rule, verification pattern, where).
"""
import json
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _load():
    code_files = ['pipeline/compose.py', 'pipeline/compose_write.py',
                  'pipeline/vessel_context.py', 'pipeline/pid_extract.py',
                  'pipeline/electrical_extract.py', 'pipeline/loop_prepass.py',
                  'pipeline/power_path.py', 'prompts/drawing_symbol_glossary.md',
                  # three-layer electrical stack: geometry, fusion, semantics
                  'pipeline/net_trace.py', 'pipeline/netlist.py',
                  'pipeline/circuit.py', 'pipeline/device_locate.py',
                  'pipeline/open_questions.py', 'pipeline/vcache.py']
    allcode = "\n".join((_ROOT / f).read_text() for f in code_files)
    reg = json.loads((_ROOT / 'data/state/register_gelliceaux_001.json').read_text())
    return allcode, reg


CHECKS = [
    ("gm-b1-all", "engineer answers durable + outrank later passes", r"def answer_by_engineer", "code"),
    ("gm-b1-all", "engineer answer match is token-bounded + scoped", r"identifier too short to be unique", "code"),
    ("gm-b1-all", "settled answers never re-raised as uncertainties", r"SETTLED BY THE ENGINEER", "code"),
    ("gm-b1-corpus", "corpus context has a relevance floor (no filler)", r"CORPUS_MAX_DISTANCE", "code"),
    ("gm-b1-corpus", "duplicate corpus rows collapsed, not read as corroboration", r"READS AS CORROBORATION", "code"),
    ("gm-b1-p36", "relay gap declared when contact state unmeasured", r"RELAYS PRESENT BUT CONTACT STATE NOT MEASURED", "code"),
    ("gm-b1-latent", "polarity words matched on token boundaries, not substrings", r"NEVER AS SUBSTRINGS", "code"),
    ("gm-b1-latent", "device TYPE kept alongside label for circuit logic", r"device_kinds", "code"),
    ("gm-b1-fix1", "engineer answers VERIFIED as applied, not just offered", r"def verify_settled", "code"),
    ("gm-b1-fix1", "answer scope travels with the answer", r"SCOPE TRAVELS WITH THE ANSWER", "code"),
    ("gm-b1-fix2", "NO/NC measured from net topology, reconciled with symbol", r"def contact_states", "code"),
    ("gm-b1-fix3", "label never binds to its own glyph", r"NEVER BINDS TO ITS OWN INK", "code"),
    ("gm-b1-fix3", "binding counted per instance, not per distinct string", r"COUNT LABEL INSTANCES", "code"),
    ("gm-b1-cost", "deterministic vision layers cached by content", r"VISION-LAYER CACHE", "code"),
    # --- GM batch-1 red-pen, 2026-07-26 (polarity reversal + relay/rail/pairing)
    ("gm-b1-p20", "LV DC: breaker/fuse sits on the POSITIVE side", r"POLARITY - NEVER INVERT IT", "code"),
    ("gm-b1-p20", "walk the conductor back to its breaker/bus", r"FOLLOW THE CONDUCTOR ALL THE WAY BACK", "code"),
    ("gm-b1-p20", "measured polarity from geometry, not wording", r"def classify_sources", "code"),
    ("gm-b1-p20", "trace-to-source operation exists", r"def trace_to_source", "code"),
    ("gm-b1-p20", "tag direction decided by whether the net reaches a coil", r"def tag_direction", "code"),
    ("gm-b1-p15", "common rail named for every device on it", r"COMMON RAILS", "code"),
    ("gm-b1-p15", "common-rail detection over the netlist", r"def common_rails", "code"),
    ("gm-b1-p15", "never interpolate a correspondence (ALL classes)", r"NEVER INTERPOLATE A CORRESPONDENCE", "code"),
    ("gm-b1-p15", "unbound labels declared as measurement gaps", r"MEASUREMENT COMPLETENESS", "code"),
    ("gm-b1-p15", "reach-binding only when decisively nearest", r"decisive_ratio", "code"),
    ("gm-b1-p26", "relay: load on NO or NC + what energises the coil", r"RELAY READING - ANSWER BOTH QUESTIONS", "code"),
    ("gm-b1-p26", "contact state captured at locate time", r"contact_state", "code"),
    ("gm-b1-p26", "a contact reaching a coil is control, not status", r"REACHES A COIL IS A CONTROL", "code"),
    ("gm-b1-p26", "manuals reachable during composition (inflatable seal)", r"def corpus_context", "code"),
    ("elec-batch1", "wire-gauge diamond = annotation not status", r"diamond.*mm.{0,6}2|wire.gauge.*diamond|conductor mm", "code"),
    ("elec-batch2", "pin-7 = 24V negative", r"negative", "code"),
    ("elec-batch2", "dotted rectangle = confined box (HVPDU)", r"confined box|dotted.*rectangle|dotted-line rectangle", "code"),
    ("elec-batch2", "each BEL gets its own node", r"629-bel", "node"),
    ("loadmap-b1", "24V supply = distribution not a node", r"640-dc-distribution", "node"),
    ("loadmap-b2", "BEL per-installation nodes", r"629-bel1-p|629-bel-1-p|bel1-p", "reg"),
    ("loadmap-b3", "fused terminal separate from load", r"FUSED TERMINAL|has_builtin_fuse", "code"),
    ("loadmap-b4", "multi-core cable rule (MUx-N)", r"MULTI-CORE CABLE|multi-core|MUx", "code"),
    ("hyd-blockC", "distinct spool per function", r"different spool for every|per.function.*spool|slice", "code"),
    ("hyd-blockC", "A/B port pressure reliefs to tank", r"PRESSURE-RELIEF SYMBOL|pressure relief", "code"),
    ("hyd-blockC", "full-command-chain 2 PLC hops + A/B", r"FULL-COMMAND-CHAIN|input channel.*output channel|two PLC", "tracker"),
    ("comp-0719", "bar convention", r"in BAR", "code"),
    ("comp-0719", "A/B port -> equipment actuator port", r"work port goes to the actuator", "code"),
    ("comp-0719", "red triangle = revision marker", r"REVISION MARKER", "code"),
    ("comp-0719", "PVEO/PVEU = pilot module", r"pilot module, not a valve block", "code"),
    ("comp-0719", "fused terminal symbol", r"FUSED TERMINAL", "code"),
    ("comp-0719", "XA direction status vs activation", r"SIGNAL DIRECTION|ACTIVATION", "code"),
    ("comp-0719", "loop-walk multi-switch = one scenario", r"LOOP-WALK|alternative activation", "code"),
    ("comp-0719", "uncertainty discipline", r"UNCERTAINTY DISCIPLINE", "code"),
    ("comp-0719", "function over part number", r"FUNCTION OVER PART NUMBER", "code"),
    ("comp-0719", "system identity", r"SYSTEM IDENTITY", "code"),
    ("comp-0719", "drawn-line law", r"DRAWN-LINE LAW", "code"),
    ("comp-0719", "glossary injected", r"glossary_block|VESSEL ACRONYM GLOSSARY", "code"),
    ("comp-0719", "steering hierarchy card", r"150-steering-system", "node"),
    ("wp3", "P&ID arrows = flow authority", r"ARROWS ARE THE FLOW AUTHORITY|FLOW ARROWS", "code"),
    ("wp3", "NO/NC valve states", r"NO/NC VALVE STATES|valve_state", "code"),
    ("wp3", "pump sides fixed", r"PUMP SIDES", "code"),
    ("wp3", "parallel pump sets", r"PARALLEL PUMP SETS", "code"),
    ("wp3", "drawn-pipe law", r"DRAWN-PIPE LAW", "code"),
    ("wp3", "pipe-size not valve type", r"PIPE SIZES", "code"),
    ("wp3", "PLC rack index page", r"RACK/INDEX PAGE", "code"),
    ("wp3", "PLC commons per output module", r"COMMONS", "code"),
    ("wp3", "540 blackwater system card", r"540-blackwater-system", "node"),
    ("wp3", "PLC rack cards per location", r"570-plc-rack-mast", "node"),
    ("wp3", "694 AC panel += GM-112/112a", r"112a", "reg"),
    ("wp3", "content-level fabrication audit rule", r"RENDER.*verify|content-level", "todo"),
    ("q10", "WP1 relationship-triggered fact exchange", r"relationship_context|RELATIONSHIP is the trigger", "code"),
    ("q10", "cf-002 Gianneschi ACB 431 B", r"ACB 431", "reg"),
    ("q10", "living docs channel", r"living_docs", "file"),
    ("q10", "620-hvpdu = 600V bus", r"620-hvpdu", "node"),
    ("wp2", "pressure-relief symbol rule", r"PRESSURE-RELIEF SYMBOL|PRESSURE RELIEF VALVE SETTING", "code"),
    ("wp2", "spool control pressure", r"SPOOL CONTROL", "code"),
    ("wp2", "photos = identity no scenario", r"leave flow_scenarios EMPTY", "code"),
    ("wp2", "protocol version gate", r"PROTOCOL_VERSION|refused_stale_protocol", "code"),
    ("wp2", "engineer-facts-first within node", r"engineer facts first WITHIN node|engineer-authority-first", "code"),
    ("wp2v3", "cross-class fact scoping (no weave)", r"never generate a new scenario, control path", "code"),
    ("wp2v3", "coil dual-line read (+/-)", r"READ ELECTRICITY SIDE-TO-SIDE|TWO POWER SIDES", "code"),
    ("wp2v3", "indicator lamp mapping", r"INDICATOR LAMPS", "code"),
    ("wp2v3", "converter/charger symbol read", r"CONVERTER/CHARGER/INVERTER SYMBOL", "code"),
    ("wp2v3", "spare way rule", r"SPARE WAYS", "code"),
    ("wp2v3", "valve-lineup enumeration", r"ENUMERATE VALVE-LINEUP SCENARIOS|LINEUP \(one scenario\)|def _enumerate", "code"),
    ("wp2v3", "scenarios from topology only", r"SCENARIOS COME ONLY FROM THE WALKED TOPOLOGY", "code"),
    ("wp2v3", "no invented controls / pull-start", r"NO INVENTED CONTROLS|pull-start / manual-start", "code"),
    ("wp2v3", "operating-modes cross-ref", r"OPERATING-MODES DOC", "code"),
    ("wp2v3", "uncertainty vs good-to-have tiering", r"UNCERTAINTY vs GOOD-TO-HAVE|good_to_have", "code"),
    ("wp2v3", "cross-reference channel", r"CROSS-REFERENCE, DO NOT IMPORT|cross_references", "code"),
    ("wp2v3", "resolved-not-flagged", r"DO NOT FLAG WHAT YOU RESOLVED", "code"),
]


def _run_checks():
    allcode, reg = _load()
    regblob = json.dumps(reg)
    ids = {e['equipment_id'] for e in reg['entries'] if not e.get('retired')}
    tracker = (_ROOT / 'ENGO_1.0_TRACKER.md').read_text()
    todo = (_ROOT / 'TODO.md').read_text()
    living = (_ROOT / 'data/state/living_docs_gelliceaux_001.json').exists()
    rows = []
    for src, rule, pat, kind in CHECKS:
        if kind == "code":
            ok = bool(re.search(pat, allcode, re.I))
        elif kind == "node":
            ok = pat in ids
        elif kind == "reg":
            ok = bool(re.search(pat, regblob, re.I))
        elif kind == "tracker":
            ok = bool(re.search(pat, tracker, re.I))
        elif kind == "todo":
            ok = bool(re.search(pat, todo, re.I))
        elif kind == "file":
            ok = living
        else:
            ok = False
        rows.append((src, rule, kind, ok))
    return rows


def test_all_redpen_rules_present():
    rows = _run_checks()
    missing = [f"[{s}] {r}" for s, r, k, ok in rows if not ok]
    assert not missing, "DROPPED RED-PEN RULES:\n" + "\n".join(missing)


if __name__ == "__main__":
    rows = _run_checks()
    npass = sum(1 for r in rows if r[3])
    print(f"RED-PEN TRACEABILITY: {npass}/{len(rows)} verified\n")
    cur = None
    for s, rule, k, ok in rows:
        if s != cur:
            print(f"\n[{s}]")
            cur = s
        print(f"  {'OK     ' if ok else 'MISSING'} ({k}) {rule}")
