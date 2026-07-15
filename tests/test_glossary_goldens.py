"""
GROUND-TRUTH REGRESSION SUITE (Fable gap #2).

Turns the engineer's approved rulings into automatic checks. Two layers:

  1. GLOSSARY PRESENCE — every rule the engineer confirmed must still be stated
     in prompts/drawing_symbol_glossary.md (a rule silently deleted = a
     regression). Cheap, offline, runs in CI.
  2. RULING CATALOGUE — tests/glossary_goldens.json is the durable, growing
     record of every label→type/disposition the engineer ruled on. New red-pen
     rulings get appended here; this file asserts the catalogue stays
     well-formed and that the load-map/Register reflect the node-level rulings.

This is the safety net that would have caught the XA-tap regression in seconds
instead of three days later on a live page. Run after ANY glossary or extractor
prompt change. It does NOT call vision (that's the separate gold_fixtures run) —
it guards the RULES, deterministically and for free.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GLOSSARY = ROOT / "prompts" / "drawing_symbol_glossary.md"
GOLDENS = Path(__file__).parent / "glossary_goldens.json"
REGISTER = ROOT / "data" / "state" / "register_gelliceaux_001.json"
LOAD_MAP = ROOT / "data" / "state" / "load_map_gelliceaux_001.json"


class TestGoldenCatalogue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads(GOLDENS.read_text())["cases"]

    def test_catalogue_well_formed(self):
        seen = set()
        for c in self.cases:
            self.assertIn("id", c)
            self.assertNotIn(c["id"], seen, f"duplicate case id {c['id']}")
            seen.add(c["id"])
            self.assertTrue(c.get("reason"), f"{c['id']} missing reason")
            self.assertTrue(c.get("ruling"), f"{c['id']} missing ruling provenance")
            self.assertTrue(any(k in c for k in
                            ("expected_type", "expected_disposition", "expected_node")),
                            f"{c['id']} has no expectation")

    def test_glossary_states_each_confirmed_rule(self):
        """Every glossary-level ruling must still be reflected in the glossary
        text — a regression check on the prompt the extractor actually sees."""
        gloss = GLOSSARY.read_text().lower()
        # (case id, a phrase that MUST appear if the rule is still stated)
        must_state = {
            "wire_gauge_diamond": "wire-gauge callout",
            "can_bus_hi": "can bus",
            "hvil": "hvil",
            "harness_connector": "harness connector",
            "isolator_breaker": "isolator",
            "cross_drawing_wired_stays_element": "the wire is the test",
        }
        for cid, phrase in must_state.items():
            self.assertIn(phrase, gloss,
                          f"glossary no longer states the rule behind '{cid}' "
                          f"(missing phrase: {phrase!r}) — a confirmed rule regressed")

    def test_node_level_rulings_reflected(self):
        """Rulings that create/route to a node must be honoured in the live
        Register + load map (catches an applied ruling being reverted)."""
        reg = json.loads(REGISTER.read_text())
        ids = {e["equipment_id"] for e in reg["entries"] if not e.get("retired")}
        lm = json.loads(LOAD_MAP.read_text())
        mappings = {k.upper(): v for k, v in lm["mappings"].items()}

        for c in self.cases:
            node = c.get("expected_node")
            if node:
                self.assertIn(node, ids, f"{c['id']}: node {node} missing from Register")
        # the nav-lights safety rule specifically
        self.assertIn("690-navigation-lights", ids,
                      "nav-lights safety node missing (a confirmed safety ruling)")
        self.assertEqual(mappings.get("PORT NAV. LT."), "690-navigation-lights",
                         "PORT NAV. LT. no longer maps to the nav-lights node")

    def test_feeder_and_disposition_rules_present(self):
        """Load-map dispositions the engineer ruled must survive in the map's rules."""
        lm = json.loads(LOAD_MAP.read_text())
        rules_blob = " ".join(lm.get("rules", [])).lower()
        self.assertIn("pin", rules_blob, "PIN RULE dropped from load map rules")
        self.assertIn("nav", rules_blob, "NAV-LIGHTS RULE dropped from load map rules")


if __name__ == "__main__":
    unittest.main(verbosity=2)
