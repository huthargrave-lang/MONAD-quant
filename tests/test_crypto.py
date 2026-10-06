"""
Crypto trend-following (src/research/crypto_classes.py) and the continuous-calendar
snapshot mode it needs (daily_data.build_frames(continuous=True)).
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import allocation_stats as stats  # noqa: E402
from src.research import crypto_classes as cc  # noqa: E402
from src.research import daily_data as dd  # noqa: E402

DAYS = pd.date_range("2015-01-01", periods=dd.MIN_SESSIONS + 200, freq="D")


def btc(seed=0):
    rng = np.random.default_rng(seed)
    close = 300 * np.exp(np.cumsum(rng.normal(0.001, 0.035, len(DAYS))))
    return pd.DataFrame({"Open": np.r_[close[0], close[:-1]], "Close": close, "Dividends": 0.0,
                         "Capital Gains": 0.0, "Stock Splits": 0.0}, index=DAYS)


def snapshot():
    frames, report = dd.build_frames(["BTC-USD"], "2015-01-01", "2020-01-01", continuous=True,
                                     fetch_asset=lambda s, a, b: btc(),
                                     fetch_cash=lambda a, b: pd.Series(1.0, index=DAYS),
                                     fetch_check=None)
    return dd.Snapshot(sha="c", dates=frames["open"].index, assets=("BTC-USD",), open=frames["open"],
                       close=frames["close"], dist=frames["dist"], dtb3=frames["dtb3"],
                       manifest={"validation": report})


class Calendar(unittest.TestCase):
    def test_weekends_are_refused_unless_the_market_is_continuous(self):
        kw = dict(fetch_asset=lambda s, a, b: btc(), fetch_cash=lambda a, b: pd.Series(1.0, index=DAYS),
                  fetch_check=None)
        with self.assertRaises(dd.SnapshotError):
            dd.build_frames(["BTC-USD"], "2015-01-01", "2020-01-01", **kw)
        snap = snapshot()
        self.assertIn("BTC-USD", snap.unreliable_opens, "a 24/7 market has no real open")

    def test_utc_dates_are_kept(self):
        """A bar stamped 2020-03-01 00:00 UTC is 2020-03-01, not New York's 29 February."""
        idx = pd.DatetimeIndex(["2020-03-01 00:00"], tz="UTC")
        self.assertEqual(idx.tz_convert("UTC").tz_localize(None).normalize()[0], pd.Timestamp("2020-03-01"))
        self.assertEqual(idx.tz_convert("America/New_York").tz_localize(None).normalize()[0],
                         pd.Timestamp("2020-02-29"))


class Trend(unittest.TestCase):
    def test_orders_are_state_changes_at_the_close(self):
        snap = snapshot()
        (tr,) = cc.trend(snap, {"ma_days": 50})
        self.assertTrue(tr.open_orders.empty)
        vals = tr.close_orders["BTC-USD"].to_numpy()
        self.assertTrue(set(np.unique(vals)) <= {0.0, 1.0})
        self.assertTrue((np.diff(vals) != 0).all(), "only changes are ordered")

    def test_every_point_is_truncation_invariant(self):
        snap = snapshot()
        cuts = [snap.dates[i] for i in (500, 700, 900, 1100)]
        for point in cc.grid() + [cc.REFERENCE]:
            with self.subTest(point=point):
                self.assertEqual(cc.truncation_violations(snap, point, cuts), [])

    def test_the_reference_holds_half_at_the_close(self):
        snap = snapshot()
        trs = cc.reference(snap)
        self.assertEqual(len(trs), cc.REBALANCE_DAYS)
        self.assertTrue(all(t.open_orders.empty for t in trs))
        self.assertTrue((trs[0].close_orders["BTC-USD"] == 0.5).all())

    def test_the_grid_has_no_duplicates(self):
        snap = snapshot()
        orders = {repr(p): cc.decide(snap, p) for p in cc.grid()}
        self.assertEqual(stats.duplicate_points(orders), [])


if __name__ == "__main__":
    unittest.main()
