"""
Regression tests for the 2026-07-12 sanity-pass fixes.

All offline — no API keys, no network. Each test pins one fixed behaviour:
  1. retry helpers retry transient errors and re-raise permanent ones
  2. node_write saves the Register atomically (tmp + os.replace pattern)
  3. node_match never matches retired nodes
  4. _attach_fact is idempotent for exact re-run duplicates
  5. tokens.get_encoder is lazy (importing pipeline.chunk needs no network)
  6. poller quarantines a corrupt state file and prunes old daily logs
  7. ingest._expand_paths covers every PARSER_REGISTRY type
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---- 1. retry helpers -------------------------------------------------------

def test_drive_retry_transient_then_success(monkeypatch):
    from providers import structure

    monkeypatch.setattr(structure, "_RETRY_BACKOFF", (0.0, 0.0, 0.0))
    calls = {"n": 0}

    class FakeRequest:
        def execute(self):
            calls["n"] += 1
            if calls["n"] < 3:
                raise TimeoutError("transient blip")
            return {"ok": True}

    assert structure._execute_with_retry(FakeRequest()) == {"ok": True}
    assert calls["n"] == 3


def test_drive_retry_permanent_not_retried():
    from providers import structure

    calls = {"n": 0}

    class FakeRequest:
        def execute(self):
            calls["n"] += 1
            raise ValueError("permanent: bad request")

    with pytest.raises(ValueError):
        structure._execute_with_retry(FakeRequest())
    assert calls["n"] == 1  # no retry on non-transient


def test_vision_retry_transient_then_success(monkeypatch):
    import anthropic
    import httpx
    from providers import vision

    monkeypatch.setattr(vision, "_RETRY_BACKOFF", (0.0, 0.0, 0.0))
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise anthropic.APIConnectionError(request=httpx.Request("POST", "http://x"))
        return "done"

    assert vision._call_with_retry(flaky) == "done"
    assert calls["n"] == 2


# ---- 2. atomic register save ------------------------------------------------

def test_atomic_write_json_replaces_not_truncates(tmp_path):
    from pipeline.node_write import _atomic_write_json

    target = tmp_path / "register_test.json"
    target.write_text(json.dumps({"old": True}))
    _atomic_write_json(target, {"new": True})
    assert json.loads(target.read_text()) == {"new": True}
    assert not target.with_suffix(".json.tmp").exists()  # tmp cleaned up


# ---- 3. retired nodes never match -------------------------------------------

def _entry(eid, **kw):
    base = {"equipment_id": eid, "name": eid, "make": None, "model": None,
            "acronyms": [], "functions": [], "category": None,
            "region_code": None, "subsystem_code": None, "subsystem_label": None}
    base.update(kw)
    return base


def test_resolve_skips_retired_nodes():
    from pipeline.node_match import resolve

    register = [
        _entry("220-winches", name="Winches", model="B1235", retired=True),
        _entry("220-primary-winch", name="Primary Winch Harken", model="B1235"),
    ]
    r = resolve({"name": "primary winch", "model": "B1235"}, register)
    assert r["action"] == "attach"
    assert r["match_id"] == "220-primary-winch"  # retired twin never wins

    # even when ONLY a retired node would match, it must not attach
    r2 = resolve({"name": "winches", "model": "B9999"},
                 [_entry("220-winches", name="Winches", model="B9999", retired=True),
                  _entry("999-unrelated", name="Bow Thruster")])
    assert r2["match_id"] != "220-winches"


def test_exact_make_boost_skips_retired():
    from pipeline.node_match import resolve

    register = [
        _entry("510-watermaker", name="Watermaker", make="Ecosistems", retired=True),
        _entry("510-ecosistems-watermaker", name="Watermaker A-300", make="Ecosistems"),
    ]
    r = resolve({"name": "some system", "make": "Ecosistems"}, register)
    if r["action"] == "attach":
        assert r["match_id"] == "510-ecosistems-watermaker"


# ---- 4. fact idempotency on re-runs ------------------------------------------

def test_fact_dedupe_key_ignores_bbox():
    from pipeline.node_write import NodeWriter

    prov_a = {"source_doc": "sheet.pdf", "sheet": "5", "page": 1, "bbox": [0.1, 0.2]}
    prov_b = {"source_doc": "sheet.pdf", "sheet": "5", "page": 1, "bbox": [0.11, 0.19]}
    k1 = NodeWriter._fact_dedupe_key("rating", "40 l/min", prov_a)
    k2 = NodeWriter._fact_dedupe_key("rating", "40 l/min", prov_b)
    assert k1 == k2  # stochastic bbox drift must not defeat the dedupe
    k3 = NodeWriter._fact_dedupe_key("rating", "65 l/min", prov_a)
    assert k1 != k3  # a different value is NOT a duplicate


def test_attach_fact_skips_exact_rerun_duplicate():
    from pipeline.node_write import NodeWriter

    w = NodeWriter.__new__(NodeWriter)  # bypass __init__ (no state files needed)
    node = {"equipment_id": "130-apm-lifting-keel", "facts": []}
    w.by_id = {"130-apm-lifting-keel": node}
    w.confirmation_flags = []
    prov = {"source_doc": "mast_block.pdf", "sheet": "1", "page": 1}
    r1 = w._attach_fact("130-apm-lifting-keel", "rating", "40 l/min", dict(prov), "high")
    r2 = w._attach_fact("130-apm-lifting-keel", "rating", "40 l/min", dict(prov), "high")
    assert not r1.get("duplicate") and r2.get("duplicate")
    assert len(node["facts"]) == 1  # re-run attached nothing new


# ---- 5. lazy tokenizer -------------------------------------------------------

def test_chunk_imports_without_encoder_load():
    # the import itself must never trigger a download; only first USE loads
    import importlib
    import pipeline.chunk  # noqa: F401  (would raise offline pre-fix)
    importlib.reload(pipeline.chunk)


# ---- 6. poller: corrupt-state quarantine + log retention ----------------------

def test_corrupt_state_quarantined(tmp_path):
    from sensors.poller import load_state

    state = tmp_path / "exocet_rolling.json"
    state.write_text("{ this is not json")
    assert load_state(state) is None
    assert not state.exists()  # moved aside, not deleted silently in place
    quarantined = list(tmp_path.glob("exocet_rolling.json.corrupt-*"))
    assert len(quarantined) == 1  # original bytes kept for inspection


def test_prune_daily_logs(tmp_path):
    from sensors.poller import prune_daily_logs

    old = tmp_path / "exocet_20250101.jsonl"
    new = tmp_path / "exocet_20260712.jsonl"
    other = tmp_path / "keep_me.jsonl"
    for f in (old, new, other):
        f.write_text("{}\n")
    now = datetime(2026, 7, 12, tzinfo=timezone.utc)
    removed = prune_daily_logs(tmp_path, now, retention_days=90)
    assert removed == 1
    assert not old.exists() and new.exists() and other.exists()
    # retention 0 disables pruning entirely
    assert prune_daily_logs(tmp_path, now, retention_days=0) == 0


# ---- 7. directory ingest covers all registry types ----------------------------

def test_expand_paths_covers_registry(tmp_path):
    from pipeline.ingest import _expand_paths
    from pipeline.parsers import PARSER_REGISTRY

    for suffix in PARSER_REGISTRY:
        (tmp_path / f"doc{suffix}").write_text("x")
    found = {p.suffix for p in _expand_paths([str(tmp_path)])}
    assert found == set(PARSER_REGISTRY)


# ---------------------------------------------------------------------------
# REAL-SHAPE regression (2026-07-26). tag_direction was first "verified" on a
# hand-built netlist whose device entries contained the word "relay". The real
# pipeline stores the LABEL ("Re7") — so on real data every tag came back
# STATUS and the XA41/XA60 swap would have survived the fix meant to cure it.
# This test builds the netlist THROUGH bind_devices, the way production does.
# ---------------------------------------------------------------------------

def test_tag_direction_on_real_bind_devices_shape():
    from pipeline import netlist, circuit
    nets = [{"net_id": "n1", "kind": "conductor", "bbox": [0, 0, 10, 10],
             "points": [(1, 1)], "labels": [{"text": "XA41"}],
             "n_segments": 3, "devices": []},
            {"net_id": "n2", "kind": "conductor", "bbox": [20, 0, 30, 10],
             "points": [(21, 1)], "labels": [{"text": "XA60"}],
             "n_segments": 3, "devices": []}]
    nl = {"_nets_full": nets}
    netlist.bind_devices(nl, [
        {"label": "Re7", "kind": "relay", "contact_state": "NO",
         "bbox": [0, 0, 10, 10]},
        {"label": "M1", "kind": "valve motor", "bbox": [20, 0, 30, 10]}])
    nl["nets"] = [{"net_id": n["net_id"], "kind": n["kind"],
                   "devices": n.get("devices", []),
                   "device_kinds": n.get("device_kinds", []),
                   "labels": [l["text"] for l in n["labels"]]} for n in nets]
    verdict = {t["tag"]: t["direction"] for t in circuit.tag_direction(nl)}
    assert verdict["XA41"].startswith("COMMAND"), verdict
    assert verdict["XA60"].startswith("STATUS"), verdict


def test_breaker_net_is_positive_by_device_kind():
    """Polarity must also work when the breaker is typed but oddly named."""
    from pipeline import netlist, circuit
    nets = [{"net_id": "n1", "kind": "conductor", "bbox": [0, 0, 10, 10],
             "points": [(1, 1)], "labels": [{"text": "MAIN FEED"}],
             "n_segments": 3, "devices": []}]
    nl = {"_nets_full": nets}
    netlist.bind_devices(nl, [{"label": "MAIN FEED", "kind": "breaker",
                               "bbox": [0, 0, 10, 10]}])
    nl["nets"] = [{"net_id": n["net_id"], "kind": n["kind"],
                   "devices": n.get("devices", []),
                   "device_kinds": n.get("device_kinds", []),
                   "labels": [l["text"] for l in n["labels"]]} for n in nets]
    assert circuit.classify_sources(nl)["n1"] == "positive"


def test_label_never_binds_to_its_own_glyph():
    """A label sits on top of its own drawn letters; binding there teaches
    nothing and steals the label from the conductor it names."""
    from pipeline import net_trace
    nets = [{"net_id": "g1", "kind": "glyph", "bbox": [0, 0, 6, 6],
             "points": [(3, 3)], "labels": []},
            {"net_id": "c1", "kind": "conductor", "bbox": [0, 8, 40, 9],
             "points": [(3, 8.5)], "labels": []}]
    net_trace.bind_labels(nets, [{"text": "21", "bbox": [2, 2, 4, 4]}],
                          max_dist=12.0)
    assert nets[0]["labels"] == [], "bound to its own glyph"
    assert [l["text"] for l in nets[1]["labels"]] == ["21"]


def test_binding_stats_count_instances_not_distinct_texts():
    """Seven terminals printed '9' are seven measurements, not one."""
    from pipeline import net_trace
    nets = [{"net_id": f"c{i}", "kind": "conductor",
             "bbox": [i * 50, 0, i * 50 + 40, 1], "points": [(i * 50 + 5, 0.5)],
             "labels": []} for i in range(3)]
    labels = [{"text": "9", "bbox": [i * 50 + 4, 0, i * 50 + 6, 2]}
              for i in range(3)]
    net_trace.bind_labels(nets, labels, max_dist=12.0)
    instances = sum(len(n["labels"]) for n in nets)
    assert instances == 3, f"expected 3 bound instances, got {instances}"
