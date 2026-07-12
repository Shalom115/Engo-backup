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
