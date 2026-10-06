"""
The daily strategy classes (src/research/daily_classes.py): the frozen grid, the
turn-of-month calendar arithmetic, and truncation invariance for every grid point on a
synthetic snapshot, plus a planted look-ahead rule that the check must catch.
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import allocation_stats as stats  # noqa: E402
from src.research import daily_classes as dc  # noqa: E402
from src.research.daily_data import Snapshot  # noqa: E402
from src.research.daily_strategy import Tranche  # noqa: E402

ASSETS = sorted({a for p in dc.grid() for a in dc.assets_used(p)} | {"SPY", "IEF"})


def synthetic(n=900, seed=7):
    """A random-walk panel over every asset the grid uses; no data defects."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2010-01-04", periods=n)
    close = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, (n, len(ASSETS))), axis=0)),
                         index=dates, columns=ASSETS)
    gap = np.exp(rng.normal(0, 0.003, (n, len(ASSETS))))
    opens = close.shift(1).fillna(close.iloc[0]) * gap
    dist = pd.DataFrame(0.0, index=dates, columns=ASSETS)
    dtb3 = pd.Series(1.5, index=dates)
    return Snapshot(sha="synthetic", dates=dates, assets=tuple(ASSETS), open=opens, close=close,
                    dist=dist, dtb3=dtb3, manifest={})


class TheGrid(unittest.TestCase):
    def test_it_is_frozen_at_27_distinct_points(self):
        g = dc.grid()
        self.assertEqual(len(g), 27)
        self.assertEqual(len({repr(sorted(p["params"].items())) + p["class"] for p in g}), 27)
        counts = {}
        for p in g:
            counts[p["class"]] = counts.get(p["class"], 0) + 1
        self.assertEqual(counts, {"tsmom": 12, "dualmom": 4, "tom": 4, "overnight": 3, "sma": 4})

    def test_warmup_covers_the_longest_lookback(self):
        self.assertEqual(dc.WARMUP_SESSIONS, 13 * dc.MONTH + dc.VOL_WINDOW)


class TruncationInvariance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = synthetic()
        cls.cuts = [cls.snap.dates[i] for i in (400, 523, 650, 777, 898)]

    def test_every_grid_point_is_truncation_invariant(self):
        for point in dc.grid() + [dc.REFERENCE]:
            with self.subTest(point=point):
                self.assertEqual(stats.truncation_violations(self.snap, point, self.cuts), [])

    def test_a_rule_that_peeks_one_session_ahead_is_caught(self):
        """Size SPY by TOMORROW's close: a one-session look-ahead whose output at the cut
        always depends on the erased price, so every cut must catch it. (A rule that only
        reads the future's SIGN is caught at a cut only when the sign flips the decision,
        about half the time per cut; the gate uses 12 cuts for that reason.)"""
        def peek(snap, params, rets=None):
            c = snap.close["SPY"]
            w = pd.DataFrame({"SPY": (c.shift(-1) / c / 2.0).clip(upper=1.0)})
            return [Tranche(open_orders=w.dropna(), close_orders=pd.DataFrame())]

        dc.CLASSES["_peek"] = peek
        try:
            problems = stats.truncation_violations(self.snap, {"class": "_peek", "params": {}},
                                                   self.cuts)
        finally:
            del dc.CLASSES["_peek"]
        self.assertEqual(len(problems), len(self.cuts))


class TurnOfMonth(unittest.TestCase):
    def test_window_minus1_plus3_holds_exactly_those_sessions(self):
        snap = synthetic(n=120)
        (tr,) = dc.tom(snap, {"first": -1, "last": 3, "off": "cash"})
        orders = tr.close_orders
        dates = snap.dates
        month = dates.to_period("M")
        # Executions are one session after each decision.
        exec_days = [dates[dates.get_loc(d) + 1] for d in orders.index]
        for d, (_, row) in zip(exec_days, orders.iterrows()):
            same = dates[month == d.to_period("M")]
            if row["SPY"] == 1.0:
                self.assertEqual(d, same[-2], "buy at the close of the 2nd-to-last session")
            else:
                self.assertEqual(d, same[2], "sell at the close of the 3rd session")

    def test_a_window_that_does_not_straddle_the_month_end_is_refused(self):
        with self.assertRaises(ValueError):
            dc.tom(synthetic(n=60), {"first": 1, "last": 3, "off": "cash"})


class TotalReturnIndex(unittest.TestCase):
    def test_distributions_are_returns_not_price_drops(self):
        dates = pd.bdate_range("2012-01-02", periods=4)
        snap = Snapshot(sha="t", dates=dates, assets=("A",),
                        open=pd.DataFrame({"A": [100.0, 100, 98, 98]}, index=dates),
                        close=pd.DataFrame({"A": [100.0, 100, 98, 98]}, index=dates),
                        dist=pd.DataFrame({"A": [0.0, 0, 2.0, 0]}, index=dates),
                        dtb3=pd.Series(0.0, index=dates), manifest={})
        tr = dc.total_return_index(snap.returns())["A"]
        self.assertTrue(np.allclose(tr.to_numpy(), 1.0))


if __name__ == "__main__":
    unittest.main()
