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

    def test_the_event_grid_is_frozen_at_4_points(self):
        self.assertEqual([p["class"] for p in dc.event_grid()],
                         ["fomc_tilt", "fomc_tilt", "halloween", "halloween"])

    def test_warmup_covers_the_longest_lookback(self):
        self.assertEqual(dc.WARMUP_SESSIONS, 13 * dc.MONTH + dc.VOL_WINDOW)


class TruncationInvariance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = synthetic()
        cls.cuts = [cls.snap.dates[i] for i in (400, 523, 650, 777, 898)]

    def test_every_grid_point_is_truncation_invariant(self):
        for point in dc.grid() + dc.event_grid() + dc.auction_grid() + dc.liquidity_grid() + dc.cosmic_grid() + [dc.REFERENCE]:
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


class EventTilts(unittest.TestCase):
    def test_fomc_tilt_holds_spy_exactly_over_announcement_sessions(self):
        from src.research.fomc_calendar import announcements
        snap = synthetic(n=900)
        trs = dc.fomc_tilt(snap, {"window": "day"})
        days = pd.DatetimeIndex([pd.Timestamp(d) for d in announcements()]).intersection(snap.dates)
        self.assertGreater(len(days), 20)
        orders = trs[0].close_orders
        dates = snap.dates
        execs = {dates[dates.get_loc(d) + 1]: row["SPY"] for d, row in orders.iterrows()}
        for a in days:
            p = dates.get_loc(a)
            if p < 2:
                continue
            self.assertEqual(execs.get(dates[p - 1]), 1.0, f"enter at the close before {a.date()}")
            self.assertEqual(execs.get(a), 0.6, f"leave at the close of {a.date()}")

    def test_a_base_rebalance_inside_a_tilt_executes_to_the_tilt(self):
        from src.research.fomc_calendar import announcements
        snap = synthetic(n=900)
        days = set(pd.DatetimeIndex([pd.Timestamp(d) for d in announcements()]))
        for tr in dc.fomc_tilt(snap, {"window": "day"}):
            for d, row in tr.open_orders.iterrows():
                p = snap.dates.get_loc(d) + 1
                if p < len(snap.dates) and snap.dates[p] in days:
                    self.assertEqual((row["SPY"], row["IEF"]), (1.0, 0.0))

    def test_halloween_targets_the_execution_sessions_season(self):
        snap = synthetic(n=900)
        for tr in dc.halloween(snap, {"tilt": 0.2}):
            for d, row in tr.open_orders.iterrows():
                p = snap.dates.get_loc(d) + 1
                winter = snap.dates[p].month in (11, 12, 1, 2, 3, 4)
                self.assertAlmostEqual(row["SPY"], 0.8 if winter else 0.4)


class AuctionTilt(unittest.TestCase):
    def test_pre_auction_sessions_hold_shy_and_never_before_the_announcement(self):
        from src.research.treasury_auctions import auctions
        snap = synthetic(n=900)
        trs = dc.auction_tilt(snap, {"pre": 5, "tenors": "long"})
        orders = trs[0].close_orders
        dates = snap.dates
        enters = [dates[dates.get_loc(d) + 1] for d, row in orders.iterrows() if row.get("SHY", 0) == 0.4]
        long_auctions = [a for a in auctions() if a["term"] in dc.LONG_TENORS
                         and pd.Timestamp(a["auction"]) in set(dates)]
        self.assertTrue(long_auctions and enters)
        for a in long_auctions:
            ann = int(dates.searchsorted(pd.Timestamp(a["announced"])))
            for e in enters:
                p = dates.get_loc(e)
                ap = dates.get_loc(pd.Timestamp(a["auction"]))
                if ap - 6 <= p < ap:                   # an entry serving this auction
                    self.assertGreaterEqual(p - 1, ann, "entry decided before the announcement")


class LiquidityTilt(unittest.TestCase):
    def test_walcl_is_used_only_after_its_release(self):
        from src.research.fred_series import known_by
        days = pd.bdate_range("2020-01-06", "2020-01-17")
        known = known_by("WALCL", days)
        # The observation dated Wednesday 2020-01-08 is released Thursday evening: first
        # known at Friday 2020-01-10's close, not Wednesday's or Thursday's.
        import json
        rec = json.loads((REPO / "docs/research/data/fred_WALCL.json").read_text())
        v = dict(rec["observations"])["2020-01-08"]
        self.assertNotEqual(known.loc["2020-01-09"], v)
        self.assertEqual(known.loc["2020-01-10"], v)
