"""
The mortgage REIT book-value test's data and classes (src/research/mreit_data.py,
mreit_classes.py; docs/research/MREIT_DISCOUNT_TEST.md): book value per common share
from one filing's equity, preferred and shares, first filing per period end; the
universe screen's rules; and the selection reusing the CEF/BDC discount logic.
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import mreit_classes as mc, mreit_data as md  # noqa: E402
from src.research.bdc_data import BdcPanel  # noqa: E402
from src.research.daily_data import Snapshot  # noqa: E402


def fact(accn, end, filed, val, form="10-Q"):
    return {"accn": accn, "end": end, "filed": filed, "val": val, "form": form}


def facts(**concepts):
    return {"facts": {"us-gaap": {k: {"units": {u: v}} for k, (u, v) in concepts.items()}}}


class BookValue(unittest.TestCase):
    def test_equity_less_liquidation_preference_over_shares_from_one_filing(self):
        f = facts(StockholdersEquity=("USD", [fact("a1", "2019-12-31", "2020-02-20", 11041e6, "10-K"),
                                              fact("a2", "2019-12-31", "2020-05-01", 11000e6)]),
                  PreferredStockLiquidationPreferenceValue=("USD", [fact("a1", "2019-12-31", "2020-02-20", 963e6, "10-K")]),
                  PreferredStockValue=("USD", [fact("a1", "2019-12-31", "2020-02-20", 932e6, "10-K")]),
                  CommonStockSharesOutstanding=("shares", [fact("a1", "2019-12-31", "2020-02-20", 540.9e6, "10-K"),
                                                           fact("a2", "2019-12-31", "2020-05-01", 541e6)]))
        h = md.bv_history(f)
        self.assertEqual(len(h), 1)
        self.assertEqual(h[0]["accession"], "a1")             # the first filing reporting it
        self.assertAlmostEqual(h[0]["bv"], (11041 - 963) / 540.9, places=9)

    def test_carrying_value_when_no_liquidation_preference_and_zero_when_no_preferred(self):
        f = facts(StockholdersEquity=("USD", [fact("a", "2015-03-31", "2015-05-01", 100.0),
                                              fact("b", "2015-06-30", "2015-08-01", 120.0)]),
                  PreferredStockValue=("USD", [fact("a", "2015-03-31", "2015-05-01", 20.0)]),
                  CommonStockSharesOutstanding=("shares", [fact("a", "2015-03-31", "2015-05-01", 10.0),
                                                           fact("b", "2015-06-30", "2015-08-01", 10.0)]))
        self.assertEqual([round(r["bv"], 9) for r in md.bv_history(f)], [8.0, 12.0])

    def test_inputs_from_different_filings_are_not_combined(self):
        f = facts(StockholdersEquity=("USD", [fact("a", "2015-03-31", "2015-05-01", 100.0)]),
                  CommonStockSharesOutstanding=("shares", [fact("z", "2015-03-31", "2015-05-01", 10.0)]))
        self.assertEqual(md.bv_history(f), [])


INSTANCE = b"""<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:us-gaap="http://fasb.org/us-gaap/2018"
 xmlns:dei="http://xbrl.sec.gov/dei/2018" xmlns:xbrldi="http://xbrl.org/2006/xbrldi">
<context id="I"><entity><identifier>1</identifier></entity><period><instant>2018-09-30</instant></period></context>
<context id="B"><entity><identifier>1</identifier><segment><xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">us-gaap:SeriesBPreferredStockMember</xbrldi:explicitMember></segment></entity><period><instant>2018-09-30</instant></period></context>
<context id="C"><entity><identifier>1</identifier><segment><xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">us-gaap:SeriesCPreferredStockMember</xbrldi:explicitMember></segment></entity><period><instant>2018-09-30</instant></period></context>
<context id="D"><entity><identifier>1</identifier></entity><period><instant>2018-10-31</instant></period></context>
<us-gaap:StockholdersEquity contextRef="I" unitRef="usd">1100</us-gaap:StockholdersEquity>
<us-gaap:PreferredStockLiquidationPreferenceValue contextRef="B" unitRef="usd">60</us-gaap:PreferredStockLiquidationPreferenceValue>
<us-gaap:PreferredStockLiquidationPreferenceValue contextRef="C" unitRef="usd">40</us-gaap:PreferredStockLiquidationPreferenceValue>
<us-gaap:CommonStockSharesOutstanding contextRef="I" unitRef="shares">100000</us-gaap:CommonStockSharesOutstanding>
<dei:EntityCommonStockSharesOutstanding contextRef="D" unitRef="shares">100</dei:EntityCommonStockSharesOutstanding>
</xbrl>"""


class InstanceCorrection(unittest.TestCase):
    """The spent correction (MREIT_DISCOUNT_TEST.md): series-level preferred summed from a
    filing's instance, and a 1000x share-scale error rescaled against the cover page."""

    def test_series_preferred_summed_and_scale_error_rescaled(self):
        p = md.parse_instance(INSTANCE, "2018-09-30")
        self.assertEqual((p["preferred"], p["preferred_concept"]),
                         (100.0, "PreferredStockLiquidationPreferenceValue"))
        bv, note = md.bv_from_instance(p)
        self.assertAlmostEqual(bv, (1100 - 100) / 100.0)
        self.assertIn("rescaled", note)

    def test_instance_name_prefers_the_inline_extract(self):
        idx = {"directory": {"item": [{"name": "a-20200930_cal.xml"}, {"name": "a-20200930_htm.xml"},
                                      {"name": "FilingSummary.xml"}]}}
        self.assertEqual(md.instance_name(idx), "a-20200930_htm.xml")


class Universe(unittest.TestCase):
    def test_repo_share_reit_sic_and_a_listed_common_ticker(self):
        frames = {"repo": {"data": [{"cik": 1, "entityName": "A", "val": 80}, {"cik": 2, "entityName": "B", "val": 80},
                                    {"cik": 3, "entityName": "C", "val": 10}, {"cik": 4, "entityName": "D", "val": 90}]},
                  "assets": {"data": [{"cik": 1, "val": 100}, {"cik": 2, "val": 100}, {"cik": 3, "val": 100},
                                      {"cik": 4, "val": 100}]}}
        subs = {1: {"tickers": ["AAA", "AAA-PA"], "exchanges": ["NYSE", "NYSE"], "sic": "6798"},
                2: {"tickers": ["BBB"], "exchanges": ["NYSE"], "sic": "6211"},      # broker-dealer
                4: {"tickers": ["DDD-PA"], "exchanges": ["NYSE"], "sic": "6798"}}   # preferred only

        def get(url):
            if "SecuritiesSoldUnderAgreementsToRepurchase" in url:
                return frames["repo"]
            if "frames/us-gaap/Assets" in url:
                return frames["assets"]
            cik = int(url.split("CIK")[1][:10])
            return subs.get(cik, {})
        md.PAUSE, pause = 0.0, md.PAUSE
        try:
            got = md.build_universe(get=get, first_year=2020, last_year=2020)
        finally:
            md.PAUSE = pause
        self.assertEqual([g["ticker"] for g in got], ["AAA"])


class Selection(unittest.TestCase):
    def test_cheapest_fifth_against_book_with_at_least_four(self):
        names = [f"M{i}" for i in range(20)]
        dates = pd.bdate_range("2015-01-02", periods=400)
        close = pd.DataFrame(np.tile(np.linspace(5, 24, 20), (400, 1)), index=dates, columns=names)
        snap = Snapshot(sha="s", dates=dates, assets=tuple(names), open=close, close=close,
                        dist=close * 0, dtb3=pd.Series(1.0, index=dates), manifest={})
        rows = pd.DataFrame([{"ticker": n, "period_end": pd.Timestamp("2014-12-31"), "nav": 20.0,
                              "filed": pd.Timestamp("2015-02-01"), "known": pd.Timestamp("2015-02-02")}
                             for n in names])
        panel = BdcPanel(sha="p", rows=rows, manifest={})
        start = mc.scoring_start(snap, panel)
        self.assertGreaterEqual(start, dates[125])
        w = mc.decide(snap, panel, {"class": "mreit_discount", "params": {"fraction": 0.2}})[0].close_orders
        held = w.loc[w.index >= start].iloc[0]
        self.assertEqual(sorted(held[held > 0].index), ["M0", "M1", "M2", "M3"])


if __name__ == "__main__":
    unittest.main()
