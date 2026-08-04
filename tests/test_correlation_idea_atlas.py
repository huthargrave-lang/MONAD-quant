import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ATLAS = ROOT / "docs/research/CORRELATION_IDEA_ATLAS_100_2026.md"


class CorrelationIdeaAtlasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = ATLAS.read_text(encoding="utf-8")
        cls.ids = re.findall(r"^\| (C\d{3}) \|", cls.text, flags=re.MULTILINE)

    def test_exactly_one_hundred_unique_ideas(self):
        self.assertEqual(len(self.ids), 100)
        self.assertEqual(len(set(self.ids)), 100)
        self.assertEqual(self.ids, [f"C{i:03d}" for i in range(1, 101)])

    def test_every_idea_is_a_testable_table_row(self):
        rows = [line for line in self.text.splitlines() if re.match(r"^\| C\d{3} \|", line)]
        self.assertTrue(all(line.count("|") == 5 for line in rows))
        self.assertTrue(all(";" in line for line in rows))

    def test_atlas_is_explicitly_unranked(self):
        self.assertIn("deliberately unranked", self.text)
        self.assertIn("Novelty or strangeness is not a rejection criterion", self.text)
        self.assertIn("hypothesis seed, not an edge claim", self.text)

    def test_source_palette_covers_multiple_independent_domains(self):
        for source in (
            "SEC EDGAR APIs",
            "FRED and ALFRED",
            "Treasury FiscalData",
            "CFTC Commitments of Traders",
            "EIA Open Data",
            "NOAA Climate Data Online",
            "BLS Public Data API",
            "USAspending's public API",
            "USPTO Open Data",
            "openFDA",
        ):
            self.assertIn(source, self.text)


if __name__ == "__main__":
    unittest.main()
