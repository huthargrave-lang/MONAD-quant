"""
The earnings-announcement premium domain (src/research/earnings_classes.py;
docs/research/EARNINGS_PREMIUM_PROTOCOL.md): expected announcers come only from the
same window a year earlier, eligibility needs history, and the candidate falls back to
the universe when too few qualify.
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import earnings_classes as ec  # noqa: E402
from src.research.daily_data import Snapshot  # noqa: E402


def setup(n_names=30, sessions=800):
    names = [f"S{i}" for i in range(n_names)]
    dates = pd.bdate_range("2019-01-02", periods=sessions)
    close = pd.DataFrame(10.0, index=dates, columns=names + ["IWM"])
    snap = Snapshot(sha="s", dates=dates, assets=tuple(names + ["IWM"]), open=close, close=close,
                    dist=close * 0, dtb3=pd.Series(1.0, index=dates), manifest={})
    rows = []
    for i, n in enumerate(names):
        # quarterly announcements; the first 20 names announce on the 10th of Feb/May/Aug/Nov,
        # the rest on the 25th of Mar/Jun/Sep/Dec
        months, day = ((2, 5, 8, 11), 10) if i < 20 else ((3, 6, 9, 12), 25)
        for y in (2018, 2019, 2020, 2021, 2022):
            for m in months:
                rows.append((n, pd.Timestamp(y, m, day)))
    ann = ec.Announcements(sha="a", dates=pd.DataFrame(rows, columns=["ticker", "filed"]))
    return snap, ann


class Expected(unittest.TestCase):
    def test_expected_announcers_come_from_the_same_window_a_year_earlier(self):
        snap, ann = setup()
        _, elig, expd = ec._matrices(snap, ann, 7)
        d = snap.dates[snap.dates.get_indexer([pd.Timestamp("2021-02-05")], method="bfill")[0]]
        on = expd.loc[d]
        self.assertTrue(on[[f"S{i}" for i in range(20)]].all())     # 2020-02-10 is within (t-365, t-358]
        self.assertFalse(on[[f"S{i}" for i in range(20, 30)]].any())

    def test_no_future_filing_is_read(self):
        snap, ann = setup()
        cut = pd.Timestamp("2020-06-30")
        masked = ec.masked_announcements(ann, cut)
        a = ec._matrices(snap, ann, 30)[2].loc[:cut]
        b = ec._matrices(snap, masked, 30)[2].loc[:cut]
        pd.testing.assert_frame_equal(a, b)


class Orders(unittest.TestCase):
    def test_candidate_holds_expected_announcers_else_the_universe(self):
        snap, ann = setup()
        orders = ec.decide(snap, ann, {"class": "earn_window", "params": {"days": 7}})[0].close_orders
        d = orders.index[orders.index.get_indexer([pd.Timestamp("2021-02-05")], method="pad")[0]]
        held = orders.loc[d]
        self.assertEqual(int((held > 0).sum()), 20)
        np.testing.assert_allclose(held[held > 0].values, 1 / 20)
        quiet = orders.loc[orders.index[orders.index.get_indexer([pd.Timestamp("2021-04-15")], method="pad")[0]]]
        self.assertEqual(int((quiet > 0).sum()), 30)                 # too few expected: the universe


if __name__ == "__main__":
    unittest.main()
