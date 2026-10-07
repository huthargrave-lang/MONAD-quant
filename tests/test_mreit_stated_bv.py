"""
Company-stated GAAP book value per common share (src/research/mreit_stated_bv.py), the
frozen rules of docs/research/MREIT_DISCOUNT_TEST_V2.md on hand-built documents.
"""
import datetime as dt
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import mreit_stated_bv as s  # noqa: E402


class Extract(unittest.TestCase):
    def test_table_row_first_dollar_amount_after_the_label(self):
        doc = ("<table><tr><td>Total stockholders' equity</td><td>$ 7,450</td></tr>"
               "<tr><td>Net book value per common share 1</td><td>$ 8.89</td><td>$ 10.76</td></tr>"
               "<tr><td>Tangible net book value per common share 2</td><td>$ 8.08</td></tr></table>")
        self.assertEqual(s.extract(doc), 8.89)

    def test_rejected_labels_are_skipped(self):
        doc = ("<p>Tangible net book value per common share was $8.95 and adjusted book value "
               "per share was $9.10.</p><p>Book value per common share was $9.39 as of "
               "September 30, 2023.</p>")
        self.assertEqual(s.extract(doc), 9.39)

    def test_prose_needs_a_dollar_amount_within_the_window(self):
        far = "x" * 200
        self.assertIsNone(s.extract(f"<p>book value per common share {far} $10.00</p>"))
        self.assertEqual(s.extract("<p>Our book value per common share was $16.55.</p>"), 16.55)

    def test_document_order_prose_before_a_later_table(self):
        doc = ("<p>Book value per share of $12.30 at quarter end.</p>"
               "<table><tr><td>Book value per share</td><td>$ 99.00</td></tr></table>")
        self.assertEqual(s.extract(doc), 12.30)


class Periods(unittest.TestCase):
    def test_quarter_end_before(self):
        self.assertEqual(s.quarter_end_before(dt.date(2018, 10, 24)), dt.date(2018, 9, 30))
        self.assertEqual(s.quarter_end_before(dt.date(2019, 2, 1)), dt.date(2018, 12, 31))
        self.assertEqual(s.quarter_end_before(dt.date(2019, 4, 1)), dt.date(2019, 3, 31))

    def test_first_statement_wins(self):
        obs = [{"period": "2018-09-30", "filed": "2018-11-05", "accession": "q", "bv": 19.10},
               {"period": "2018-09-30", "filed": "2018-10-24", "accession": "k", "bv": 19.08}]
        self.assertEqual(s.first_statement(obs)[0]["accession"], "k")


if __name__ == "__main__":
    unittest.main()
