"""
BDC NAV per share read from original filings (src/research/bdc_text_nav.py): the
extractor takes the first table row labelled NAV (or net assets) per share and its first
number, the filing's own period; filings() keeps originals only, oldest first.
"""
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import bdc_text_nav as t  # noqa: E402

BALANCE = """<table>
<tr><td>Total net assets</td><td>$</td><td>10,254</td><td>$</td><td>9,880</td></tr>
<tr><td><b>Net&nbsp;asset value per share</b></td><td>$</td><td>19.46</td><td>$</td><td>18.96</td></tr>
</table>
<table><tr><td>Net asset value per share, end of period</td><td>20.11</td></tr></table>"""


class Extract(unittest.TestCase):
    def test_first_labelled_row_first_number(self):
        self.assertEqual(t.extract_nav(BALANCE), 19.46)

    def test_net_assets_per_common_share_label(self):
        doc = "<tr><td>Net assets per common share</td><td>$ 8.07</td><td>$ 8.30</td></tr>"
        self.assertEqual(t.extract_nav(doc), 8.07)

    def test_a_prose_sentence_is_not_a_table_row(self):
        doc = ("<tr><td>Our net asset value per share decreased during the quarter as a result "
               "of unrealized losses across the portfolio and other factors described below "
               "in detail</td><td>3.14</td></tr>")
        self.assertIsNone(t.extract_nav(doc))

    def test_no_row_is_none(self):
        self.assertIsNone(t.extract_nav("<tr><td>Total assets</td><td>1,000.00</td></tr>"))


class Filings(unittest.TestCase):
    def test_originals_only_oldest_first_with_paged_history(self):
        recent = {"accessionNumber": ["a3", "a2", "a1"], "form": ["10-Q", "10-Q/A", "8-K"],
                  "filingDate": ["2020-05-01", "2020-04-01", "2020-03-01"],
                  "reportDate": ["2020-03-31", "2019-12-31", ""],
                  "primaryDocument": ["q.htm", "qa.htm", "k.htm"]}
        older = {"accessionNumber": ["a0"], "form": ["10-K"], "filingDate": ["2019-03-01"],
                 "reportDate": ["2018-12-31"], "primaryDocument": ["k10.htm"]}

        def get(url, **_):
            if url.endswith("CIK0000000001.json"):
                return json.dumps({"filings": {"recent": recent,
                                               "files": [{"name": "page1.json"}]}}).encode()
            return json.dumps(older).encode()
        got = t.filings(1, get=get)
        self.assertEqual([f["accession"] for f in got], ["a0", "a3"])


class UserAgent(unittest.TestCase):
    def test_a_contact_is_required(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"SEC_USER_AGENT": "no contact"}):
            with self.assertRaises(RuntimeError):
                t.user_agent()


if __name__ == "__main__":
    unittest.main()
