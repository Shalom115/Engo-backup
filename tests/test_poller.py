"""
Unit tests for sensors/poller.py (Ch 4.1 S1) and the GNSS clock cross-check
in agent/clock.py (Ch 4.1 S2). Exercises the REAL code paths: the summarizer
windows, state persistence round-trip, the full poll_once() cycle against a
local HTTP server, and clock_status() with the GNSS layer in both drift
directions — never shortcuts around the dispatchers.

FIXTURE PROVENANCE: channel names and values below marked "real" are quoted
verbatim from row 1 of the recorded PSM export
/Users/captain/Downloads/psm4-20260217-000000.csv (254 columns, 17/02/2026) —
including the stuck SBG date 2015-05-03 (locked vessel fact). The JSON
*envelope* (flat object of channel: value-string) is ASSUMED — the live
/data endpoint's JSON shape is not yet verified (it served the web-app HTML
shell when probed 2026-07-10). The nested/array channels are synthetic,
present only to exercise flatten_payload's defenses.

Run:  PYTHONPATH=/Users/captain/projects/gelliceaux python3.12 -m unittest tests.test_poller -v
"""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

import config
from agent import clock
from sensors.poller import (
    ExocetPayloadError,
    RollingSummarizer,
    build_gnss_block,
    flatten_payload,
    load_state,
    parse_gnss_utc,
    poll_once,
    write_state,
)

# Values marked real are verbatim from the recorded PSM CSV (see module docstring).
FIXTURE_PAYLOAD = {
    "BAE_Motor_LoadPower_pt": "0.00000",       # real
    "BAE_Motor_LoadPower_stbd": "0.00000",     # real
    "BAE_EMRAX1_Power": "0.00000",             # real
    "BAE_EMRAX2_Power": "0.00000",             # real
    "BAE_EMRAX1_CoolingTemp": "16.00000",      # real
    "BAE_Motor_CoolingTemp": "-6.00000",       # real
    "BAE_ESS_StateOfCharge": "98.40000",       # real
    "GNSS_SOG": "0.00000",                     # real
    "GNSS_UTCdate": "2026-02-16",              # real
    "GNSS_UTCtime": "23:59:59.897",            # real
    "SBG_UTC_Date": "2015-05-03",              # real — the stuck SBG clock
    "SBG_UTC_Time": "16:22:42.000",            # real
    "BAE_SystemModeStr": "LV",                 # real (text channel)
    # Synthetic, exercising flatten defenses only (envelope shape unverified):
    "LOADS": {"Backstay_port": "12.5"},        # nested object -> dotted key
    "TREND_array": [1.0, 2.0, 3.5],            # raw array -> last scalar only
}

UTC = timezone.utc


def _assert_no_lists(node, path=""):
    """Recursively assert no list values (raw arrays must never pass through)."""
    if isinstance(node, list):
        raise AssertionError(f"list found at {path!r}")
    if isinstance(node, dict):
        for k, v in node.items():
            _assert_no_lists(v, f"{path}.{k}")


class TestFlatten(unittest.TestCase):
    def test_arrays_reduced_nests_flattened(self):
        flat = flatten_payload(FIXTURE_PAYLOAD)
        self.assertEqual(flat["TREND_array"], 3.5)          # last scalar, not the array
        self.assertEqual(flat["LOADS.Backstay_port"], "12.5")
        self.assertEqual(flat["GNSS_UTCdate"], "2026-02-16")
        _assert_no_lists(flat)


class TestSummarizerWindows(unittest.TestCase):
    def test_window_membership_and_stats(self):
        rs = RollingSummarizer()
        now = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)
        # 25h old: outside both windows AND retention; 2h old: 24h window only;
        # 10min + 1min old: both windows.
        for age_min, val in [(25 * 60, 100.0), (120, 40.0), (10, 10.0), (1, 20.0)]:
            rs.add_poll({"BAE_EMRAX1_Power": val}, now - timedelta(minutes=age_min))
        summary = rs.summary(now)
        ch = summary["BAE_EMRAX1_Power"]
        w15 = ch["windows"]["15m"]
        self.assertEqual(w15["n"], 2)
        self.assertEqual(w15["min"], 10.0)
        self.assertEqual(w15["max"], 20.0)
        self.assertAlmostEqual(w15["mean"], 15.0)
        w24 = ch["windows"]["24h"]
        self.assertEqual(w24["n"], 3)                       # 25h sample trimmed/excluded
        self.assertEqual(w24["max"], 40.0)
        self.assertAlmostEqual(w24["mean"], (40.0 + 10.0 + 20.0) / 3)
        self.assertEqual(ch["last"], 20.0)

    def test_numeric_strings_coerced(self):
        rs = RollingSummarizer()
        now = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)
        rs.add_poll(flatten_payload(FIXTURE_PAYLOAD), now)
        summary = rs.summary(now)
        self.assertEqual(summary["BAE_ESS_StateOfCharge"]["last"], 98.4)
        self.assertEqual(summary["BAE_Motor_CoolingTemp"]["last"], -6.0)
        # Text channel: last-value only, no windows stats
        self.assertEqual(summary["BAE_SystemModeStr"]["last"], "LV")
        self.assertEqual(summary["BAE_SystemModeStr"]["windows"], {})

    def test_sbg_timestamp_channels_never_summarized(self):
        rs = RollingSummarizer()
        now = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)
        rs.add_poll(flatten_payload(FIXTURE_PAYLOAD), now)
        summary = rs.summary(now)
        self.assertNotIn("SBG_UTC_Date", summary)
        self.assertNotIn("SBG_UTC_Time", summary)
        state = rs.to_state(now)
        self.assertEqual(
            state["sbg_timestamps_ignored"],
            {"SBG_UTC_Date": "2015-05-03", "SBG_UTC_Time": "16:22:42.000"},
        )

    def test_raw_array_reaching_summarizer_raises(self):
        rs = RollingSummarizer()
        now = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)
        with self.assertRaises(TypeError):
            rs.add_poll({"TREND_array": [1.0, 2.0]}, now)


class TestStatePersistence(unittest.TestCase):
    def test_roundtrip_preserves_summaries(self):
        rs = RollingSummarizer()
        now = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)
        rs.add_poll(flatten_payload(FIXTURE_PAYLOAD), now - timedelta(minutes=5))
        rs.add_poll(flatten_payload(FIXTURE_PAYLOAD), now)
        state = rs.to_state(now)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "exocet_rolling.json"
            write_state(state, path)
            restored = RollingSummarizer.from_state(load_state(path))
        self.assertEqual(restored.summary(now), rs.summary(now))

    def test_retention_trims_beyond_24h(self):
        rs = RollingSummarizer()
        now = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)
        rs.add_poll({"GNSS_SOG": 5.0}, now - timedelta(hours=25))
        rs.add_poll({"GNSS_SOG": 7.0}, now)
        state = rs.to_state(now)
        self.assertEqual(len(state["samples"]["GNSS_SOG"]), 1)  # 25h sample gone

    def test_bad_version_fails_loud(self):
        with self.assertRaises(ValueError):
            RollingSummarizer.from_state({"version": 99})


class TestGnssBlock(unittest.TestCase):
    def test_parse_and_drift_both_signs(self):
        sample = flatten_payload(FIXTURE_PAYLOAD)
        gnss_utc = parse_gnss_utc(sample)
        self.assertEqual(
            gnss_utc, datetime(2026, 2, 16, 23, 59, 59, 897000, tzinfo=UTC)
        )
        ahead = build_gnss_block(sample, gnss_utc + timedelta(seconds=600))
        self.assertAlmostEqual(ahead["drift_seconds"], 600.0)
        behind = build_gnss_block(sample, gnss_utc - timedelta(seconds=600))
        self.assertAlmostEqual(behind["drift_seconds"], -600.0)

    def test_implausible_gnss_date_ignored(self):
        # A GNSS receiver with an unset clock (the SBG failure mode) must not
        # feed the drift check.
        sample = {"GNSS_UTCdate": "2015-05-03", "GNSS_UTCtime": "16:22:42.000"}
        self.assertIsNone(parse_gnss_utc(sample))
        self.assertIsNone(build_gnss_block(sample, datetime.now(UTC)))


class _FixtureHandler(BaseHTTPRequestHandler):
    body: bytes = b"{}"
    content_type: str = "application/json"

    def do_GET(self):  # noqa: N802 — BaseHTTPRequestHandler API
        self.send_response(200)
        self.send_header("Content-Type", self.content_type)
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *args):  # silence test output
        pass


class TestPollOnceEndToEnd(unittest.TestCase):
    """Full poll cycle through the REAL dispatch path: HTTP GET -> flatten ->
    summarize -> state file -> daily log. Local server only — never the vessel."""

    def _serve(self, body: bytes, content_type: str) -> HTTPServer:
        _FixtureHandler.body = body
        _FixtureHandler.content_type = content_type
        server = HTTPServer(("127.0.0.1", 0), _FixtureHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server

    def test_poll_once_writes_state_and_daily_log(self):
        server = self._serve(json.dumps(FIXTURE_PAYLOAD).encode(), "application/json")
        try:
            with tempfile.TemporaryDirectory() as td:
                td = Path(td)
                state_path = td / "exocet_rolling.json"
                logs_dir = td / "logs"
                now = datetime(2026, 2, 17, 0, 5, 0, tzinfo=UTC)
                url = f"http://127.0.0.1:{server.server_port}/data"
                state = poll_once(url=url, state_path=state_path, logs_dir=logs_dir, now=now)

                # State persisted and re-loadable
                on_disk = load_state(state_path)
                self.assertEqual(on_disk["updated_at"], now.isoformat())
                self.assertIn("BAE_Motor_LoadPower_pt", on_disk["summary"])
                # GNSS block present, drift = host(00:05:00 17th) - gnss(23:59:59.897 16th)
                self.assertAlmostEqual(on_disk["gnss"]["drift_seconds"], 300.103, places=3)
                # Summary (the LLM-facing form) carries no raw arrays
                _assert_no_lists(on_disk["summary"], "summary")
                self.assertEqual(state["summary"], on_disk["summary"])

                # Daily log: append-only, one line, scalars only
                log_path = logs_dir / "exocet_20260217.jsonl"
                lines = log_path.read_text().splitlines()
                self.assertEqual(len(lines), 1)
                record = json.loads(lines[0])
                self.assertTrue(record["ok"])
                _assert_no_lists(record["sample"], "sample")
                self.assertNotIn("TREND_array_raw", record["sample"])
                self.assertEqual(record["sample"]["TREND_array"], 3.5)

                # Second poll appends (never truncates) and resumes state from disk
                poll_once(url=url, state_path=state_path, logs_dir=logs_dir,
                          now=now + timedelta(minutes=1))
                self.assertEqual(len(log_path.read_text().splitlines()), 2)
                resumed = load_state(state_path)
                self.assertEqual(
                    resumed["summary"]["BAE_ESS_StateOfCharge"]["windows"]["15m"]["n"], 2
                )
        finally:
            server.shutdown()
            server.server_close()

    def test_html_shell_fails_loud(self):
        # The live endpoint served the Angular shell on 2026-07-10 — that must
        # be a hard, explanatory error, never a silent empty poll.
        server = self._serve(b"<!DOCTYPE html><html><head><title>Exocet</title>", "text/html")
        try:
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaises(ExocetPayloadError):
                    poll_once(
                        url=f"http://127.0.0.1:{server.server_port}/data",
                        state_path=Path(td) / "s.json", logs_dir=Path(td) / "logs",
                    )
        finally:
            server.shutdown()
            server.server_close()


class TestClockGnssCrossCheck(unittest.TestCase):
    """agent/clock.py S2: GNSS layer flags drift in BOTH directions and never
    weakens the existing floor / forward-jump checks. STATE_DIR and LOGS_DIR
    are patched to a temp dir so the real data/state is never touched."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        tmp = Path(self._td.name)
        self.state_dir = tmp / "state"
        self.logs_dir = tmp / "logs"
        self.state_dir.mkdir()
        self.logs_dir.mkdir()
        self._patches = [
            mock.patch.object(config, "STATE_DIR", self.state_dir),
            mock.patch.object(config, "LOGS_DIR", self.logs_dir),
        ]
        for p in self._patches:
            p.start()
        self.now = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._td.cleanup()

    def _write_gnss_state(self, drift_seconds: float, host_at_read: datetime | None = None):
        host = host_at_read or (self.now - timedelta(minutes=2))
        gnss_utc = host - timedelta(seconds=drift_seconds)
        (self.state_dir / "exocet_rolling.json").write_text(json.dumps({
            "version": 1,
            "updated_at": host.isoformat(),
            "gnss": {
                "utc": gnss_utc.isoformat(),
                "host_at_read": host.isoformat(),
                "drift_seconds": drift_seconds,
            },
        }))

    def test_healthy_drift_not_suspect(self):
        self._write_gnss_state(60.0)  # 1 min: within tolerance
        _, suspect, _ = clock.clock_status(now=self.now)
        self.assertFalse(suspect)

    def test_host_ahead_of_gnss_suspect(self):
        self._write_gnss_state(900.0)  # host 15 min ahead
        _, suspect, _ = clock.clock_status(now=self.now)
        self.assertTrue(suspect)

    def test_host_behind_gnss_suspect(self):
        self._write_gnss_state(-900.0)  # host 15 min behind
        _, suspect, _ = clock.clock_status(now=self.now)
        self.assertTrue(suspect)

    def test_no_poller_state_falls_through(self):
        self.assertIsNone(clock.gnss_drift())
        _, suspect, _ = clock.clock_status(now=self.now)
        self.assertFalse(suspect)

    def test_floor_check_not_weakened_by_healthy_gnss(self):
        # Existing behind-floor check must still trip even when GNSS looks fine.
        self._write_gnss_state(0.0)
        (self.state_dir / "audit_report_corpus.json").write_text(json.dumps({
            "ran_at": (self.now + timedelta(days=3)).isoformat(),
        }))
        _, suspect, floor = clock.clock_status(now=self.now)
        self.assertTrue(suspect)
        self.assertIsNotNone(floor)

    def test_forward_jump_check_not_weakened(self):
        # No GNSS state; clock 100 days past all recorded activity still flags.
        (self.state_dir / "audit_report_corpus.json").write_text(json.dumps({
            "ran_at": (self.now - timedelta(days=100)).isoformat(),
        }))
        _, suspect, _ = clock.clock_status(now=self.now)
        self.assertTrue(suspect)

    def test_poller_state_extends_the_floor(self):
        # updated_at from the poller is a floor source: now before the last
        # poll write is provably wrong.
        self._write_gnss_state(0.0, host_at_read=self.now + timedelta(days=1))
        _, suspect, floor = clock.clock_status(now=self.now)
        self.assertTrue(suspect)
        self.assertEqual(floor, self.now + timedelta(days=1))

    def test_gnss_drift_recomputed_from_timestamps(self):
        # The stored float is not trusted; drift comes from the two timestamps.
        host = self.now - timedelta(minutes=2)
        (self.state_dir / "exocet_rolling.json").write_text(json.dumps({
            "version": 1,
            "updated_at": host.isoformat(),
            "gnss": {
                "utc": (host - timedelta(seconds=750)).isoformat(),
                "host_at_read": host.isoformat(),
                "drift_seconds": 0.0,  # lying float
            },
        }))
        drift, measured_at = clock.gnss_drift()
        self.assertAlmostEqual(drift, 750.0)
        self.assertEqual(measured_at, host)
        _, suspect, _ = clock.clock_status(now=self.now)
        self.assertTrue(suspect)


if __name__ == "__main__":
    unittest.main()
