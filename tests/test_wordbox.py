"""Vector word-box extraction — deterministic, free text+geometry from vector PDFs."""
import unittest
from pathlib import Path
from pipeline import wordbox

# a real vector hydraulic sheet with a rich text layer
VECTOR_PDF = Path("/Users/captain/Downloads/108-01-AFT_block_A-rev10.pdf")
GM_PDF = Path("data/documents/gm_book_cache.pdf")


class TestWordbox(unittest.TestCase):
    @unittest.skipUnless(VECTOR_PDF.exists(), "vector sample not present")
    def test_vector_sheet_extracts_words(self):
        pdf = VECTOR_PDF.read_bytes()
        self.assertTrue(wordbox.has_text_layer(pdf, 0))
        wbs = wordbox.word_boxes(pdf, 0)
        self.assertGreater(len(wbs), 50)
        # every word carries a normalized bbox
        for w in wbs:
            self.assertEqual(len(w["bbox"]), 4)
            for c in w["bbox"]:
                self.assertGreaterEqual(c, 0.0)

    @unittest.skipUnless(VECTOR_PDF.exists(), "vector sample not present")
    def test_lines_reconstruct(self):
        pdf = VECTOR_PDF.read_bytes()
        lines = wordbox.group_lines(wordbox.word_boxes(pdf, 0))
        self.assertTrue(any("WINCH" in l["text"].upper() for l in lines))

    @unittest.skipUnless(VECTOR_PDF.exists(), "vector sample not present")
    def test_text_in_bbox(self):
        pdf = VECTOR_PDF.read_bytes()
        # whole page -> non-empty
        self.assertTrue(wordbox.text_in_bbox(pdf, 0, [0.0, 0.0, 1.0, 1.0]).strip())
        # empty corner -> empty
        self.assertEqual(wordbox.text_in_bbox(pdf, 0, [0.0, 0.0, 0.01, 0.01]).strip(), "")

    def test_missing_page_safe(self):
        if GM_PDF.exists():
            self.assertEqual(wordbox.word_boxes(GM_PDF.read_bytes(), 9999), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
