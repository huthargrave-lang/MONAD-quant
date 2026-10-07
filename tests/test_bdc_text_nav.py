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

    def test_rows_that_only_mention_nav_are_other_tables(self):
        """Seen in the tagged-era validation: OCSL's dilution table, RAND's change row and
        OFS's highlights, whose first NAV row is the prior year's."""
        doc = ("<tr><td>10% premium to net asset value per common share</td><td>$ 10.00</td></tr>"
               "<tr><td>(Decrease) increase in net assets per share</td><td>6.21</td></tr>"
               "<tr><td>Net asset value per share at beginning of year</td><td>13.47</td></tr>"
               "<tr><td>Net asset value per share at end of year</td><td>12.09</td><td>13.47</td></tr>")
        self.assertEqual(t.extract_nav(doc), 12.09)

    def test_the_balance_sheet_table_beats_an_example_table(self):
        doc = ("<table><tr><td>Net asset value per common share</td><td>$ 10.00</td></tr></table>"
               "<table><tr><td>Total liabilities</td><td>5,000</td></tr>"
               "<tr><td>Net asset value per common share</td><td>$ 18.09</td><td>$ 19.63</td></tr></table>")
        self.assertEqual(t.extract_nav(doc), 18.09)

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


class Panel(unittest.TestCase):
    def test_first_filing_per_period_wins(self):
        obs = [{"report_date": "2020-03-31", "filed": "2020-05-01", "accession": "b", "nav": 10.0},
               {"report_date": "2020-03-31", "filed": "2021-05-01", "accession": "c", "nav": 9.0},
               {"report_date": "2019-12-31", "filed": "2020-02-01", "accession": "a", "nav": 11.0}]
        got = t.first_per_period(obs)
        self.assertEqual([(o["report_date"], o["nav"]) for o in got],
                         [("2019-12-31", 11.0), ("2020-03-31", 10.0)])

    def test_validation_counts_agreement_to_the_cent(self):
        rep = t.validate({"A": {"2023-03-31": 10.00, "2023-06-30": 10.50, "2019-12-31": 9.0}},
                         {"A": {"2023-03-31": 10.004, "2023-06-30": 10.40}})
        self.assertEqual((rep["compared"], rep["agree"], rep["filers"]), (2, 1, 1))
        self.assertEqual(rep["disagreements"][0]["period_end"], "2023-06-30")


class CrossCheck(unittest.TestCase):
    def obs(self, form, end, filed, nav, prior):
        return {"form": form, "report_date": end, "filed": filed, "accession": filed, "nav": nav,
                "prior": prior}

    def test_a_year_end_is_checked_against_the_next_filings_prior_column(self):
        rows = [self.obs("10-K", "2015-12-31", "2016-03-01", 10.00, 9.50),
                self.obs("10-Q", "2016-03-31", "2016-05-01", 10.20, 10.00),
                self.obs("10-K", "2016-12-31", "2017-03-01", 11.00, 10.00),
                self.obs("10-Q", "2017-03-31", "2017-05-01", 11.10, 10.90),
                self.obs("10-K", "2017-12-31", "2018-03-01", 5.00, 11.00),
                self.obs("10-Q", "2018-03-31", "2018-05-01", 5.0, 2.50),
                self.obs("10-K", "2022-12-31", "2023-03-01", 7.00, 6.00)]
        rep = t.comparative_cross_check(rows, before="2022-01-01")
        self.assertEqual((rep["compared"], rep["agree"]), (2, 1))
        self.assertEqual(rep["disagreements"][0]["period_end"], "2016-12-31")
        self.assertEqual(rep["splits"][0]["period_end"], "2017-12-31")

    def test_the_balance_row_keeps_the_prior_column(self):
        self.assertEqual(t.extract_balance_row(BALANCE), [19.46, 18.96])


class UserAgent(unittest.TestCase):
    def test_a_contact_is_required(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"SEC_USER_AGENT": "no contact"}):
            with self.assertRaises(RuntimeError):
                t.user_agent()


if __name__ == "__main__":
    unittest.main()
