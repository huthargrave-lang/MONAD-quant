"""
Insider purchase clusters (src/research/insider_classes.py) on synthetic data: price
corroboration (and that it never reads after the decision), position caps and full
investment, and truncation invariance over prices and events together.
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import insider_classes as ic  # noqa: E402
from src.research.daily_data import Snapshot  # noqa: E402

DATES = pd.bdate_range("2021-01-04", periods=400)
TICKERS = ["IWM"] + [f"S{i:02d}" for i in range(15)]


def world():
    rng = np.random.default_rng(3)
    close = pd.DataFrame(20 * np.exp(np.cumsum(rng.normal(0, 0.01, (len(DATES), len(TICKERS))), axis=0)),
                         index=DATES, columns=TICKERS)
    snap = Snapshot(sha="s", dates=DATES, assets=tuple(TICKERS), open=close.copy(), close=close,
                    dist=pd.DataFrame(0.0, index=DATES, columns=TICKERS),
                    dtb3=pd.Series(1.0, index=DATES), manifest={})
    rows = []
    for i in range(15):
        d = DATES[30 + 20 * i]
        rows.append({"ticker": f"S{i:02d}", "issuer_cik": i, "known": d, "insiders": 3 + i % 2,
                     "value": 1e5, "price": float(close.loc[d, f"S{i:02d}"])})
    ev = ic.InsiderEvents(sha="e", events=pd.DataFrame(rows))
    return snap, ev


class Rules(unittest.TestCase):
    def test_a_remapped_ticker_fails_corroboration(self):
        snap, ev = world()
        ev.events.loc[0, "price"] *= 3.0                        # the filing's price is far off
        c = ic.corroborated_events(snap, ev)
        self.assertNotIn("S00", set(c["ticker"]))
        self.assertEqual(len(c), 14)

    def test_corroboration_never_reads_after_the_decision(self):
        snap, ev = world()
        d0 = DATES.searchsorted(ev.events.loc[1, "known"])
        snap.close.iloc[d0 + 1:, snap.close.columns.get_loc("S01")] = 999.0   # future prices
        self.assertIn("S01", set(ic.corroborated_events(snap, ev)["ticker"]))

    def test_weights_cap_each_event_and_stay_fully_invested(self):
        snap, ev = world()
        (tr,) = ic.decide(snap, ev, {"class": "insider_cluster", "params": {"hold": 63, "min_insiders": 3}})
        o = tr.close_orders
        self.assertTrue(np.allclose(o.sum(axis=1), 1.0))
        stocks = o.drop(columns=["IWM"])
        self.assertLessEqual(float(stocks.max().max()), 1 / ic.MIN_SLOTS + 1e-12)

    def test_min_insiders_filters(self):
        snap, ev = world()
        self.assertEqual(len(ic.corroborated_events(snap, ev, 4)), 7)

    def test_truncation_invariant(self):
        snap, ev = world()
        cuts = [DATES[i] for i in (100, 200, 300, 390)]
        for p in ic.grid() + [ic.REFERENCE]:
            with self.subTest(point=p):
                self.assertEqual(ic.truncation_violations(snap, ev, p, cuts), [])


if __name__ == "__main__":
    unittest.main()
