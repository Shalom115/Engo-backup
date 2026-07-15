"""Deterministic diamond detection + wire-gauge confirmation."""
import unittest
from pathlib import Path
from pipeline import symbol_detect

GM = Path("data/documents/gm_book_cache.pdf")


class TestDiamondDetect(unittest.TestCase):
    @unittest.skipUnless(GM.exists(), "GM book not cached")
    def test_finds_wire_gauge_diamonds(self):
        gm = GM.read_bytes()
        # GMMS-101 (page index 2) carries the 4mm2/16mm2 wire-gauge diamonds
        dets = symbol_detect.detect_diamonds(gm, 2, dpi=200)
        self.assertGreater(len(dets), 5, "should find the row of wire-gauge diamonds")
        for d in dets:
            self.assertEqual(d["shape"], "diamond")
            self.assertEqual(len(d["bbox"]), 4)
            # diamond bbox is small (a glyph), not a panel
            w = d["bbox"][2] - d["bbox"][0]
            self.assertLess(w, 0.1)

    @unittest.skipUnless(GM.exists(), "GM book not cached")
    def test_confirm_image_only_routes_no_text(self):
        gm = GM.read_bytes()
        dets = symbol_detect.detect_diamonds(gm, 2, dpi=200)
        res = symbol_detect.confirm_wire_gauge_diamonds(dets, gm, 2)
        # image-only sheet: no free text, so all candidates await a vision read
        self.assertEqual(len(res["confirmed"]) + len(res["rejected_nonnumeric"]), 0)
        self.assertEqual(len(res["no_text"]), len(dets))

    def test_numeric_matcher(self):
        self.assertTrue(symbol_detect._NUMERIC.match("16"))
        self.assertTrue(symbol_detect._NUMERIC.match("120"))
        self.assertTrue(symbol_detect._NUMERIC.match("2.5"))
        self.assertFalse(symbol_detect._NUMERIC.match("V"))
        self.assertFalse(symbol_detect._NUMERIC.match("Hz"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
