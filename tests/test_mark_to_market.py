"""
The daily mark-to-market basis (src/research/mark_to_market.py; gate rules v2 (iii)),
pinned on hand-built hourly bars whose marks are worked out by hand.
"""
import sys
import unittest
from pathlib import Path

import tempfile

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import mark_to_market as mtm  # noqa: E402
from src.research import backtest_trials as bt, trials  # noqa: E402
from tests._engine_uncounted import uncounted_module  # noqa: E402

setUpModule, tearDownModule = uncounted_module("mark-to-market of hand-built and synthetic bars")


def bars(days, closes_per_day, open_=None):
    """Seven regular-session hourly bars per New York day (14:30..20:30 UTC in winter)."""
    idx, opens, closes = [], [], []
    for d, cl in zip(days, closes_per_day):
        for h, c in enumerate(cl):
            idx.append(pd.Timestamp(f"{d} 14:30", tz="UTC") + pd.Timedelta(hours=h))
            opens.append(c if open_ is None else open_)
            closes.append(c)
    return pd.DataFrame({"open": opens, "close": closes}, index=pd.DatetimeIndex(idx))


DAYS = ["2026-01-05", "2026-01-06", "2026-01-07"]


def trade(b, entry_i, exit_i, ret, direction=1):
    return pd.DataFrame({"timestamp": [b.index[entry_i - 1]], "entry_time": [b.index[entry_i]],
                         "exit_time": [b.index[exit_i]], "return": [ret],
                         "direction": [direction]})


class Marks(unittest.TestCase):
    def setUp(self):
        self.b = bars(DAYS, [[100] * 6 + [102], [101] * 6 + [99], [100] * 7])
        self.sessions = pd.DatetimeIndex(pd.to_datetime(DAYS))

    def test_a_trade_inside_one_session_books_its_return_that_day(self):
        pnl, expo = mtm.daily_series(mtm.trade_marks(trade(self.b, 1, 3, 0.01), self.b), self.sessions)
        self.assertEqual(list(pnl), [0.01, 0.0, 0.0])
        self.assertEqual(list(expo), [0.0, 0.0, 0.0])

    def test_an_overnight_trade_is_marked_at_each_close_and_sums_to_its_return(self):
        # entry at the open of bar 1 (100); day-1 close 102 -> +2%; day-2 close 99 -> -1%;
        # exits on day 3 at a booked -0.5%
        pnl, expo = mtm.daily_series(mtm.trade_marks(trade(self.b, 1, 15, -0.005), self.b),
                                     self.sessions)
        self.assertAlmostEqual(pnl.iloc[0], 0.02, places=12)
        self.assertAlmostEqual(pnl.iloc[1], -0.01 - 0.02, places=12)
        self.assertAlmostEqual(pnl.iloc[2], -0.005 + 0.01, places=12)
        self.assertAlmostEqual(pnl.sum(), -0.005, places=12)
        self.assertEqual(list(expo), [1.0, 1.0, 0.0])

    def test_a_short_is_marked_with_its_sign(self):
        pnl, _ = mtm.daily_series(mtm.trade_marks(trade(self.b, 1, 8, 0.004, -1), self.b),
                                  self.sessions)
        self.assertAlmostEqual(pnl.iloc[0], -0.02, places=12)
        self.assertAlmostEqual(pnl.sum(), 0.004, places=12)

    def test_an_exit_at_the_next_sessions_open_holds_through_one_close(self):
        pnl, expo = mtm.daily_series(mtm.trade_marks(trade(self.b, 1, 7, 0.0), self.b), self.sessions)
        self.assertEqual(list(expo), [1.0, 0.0, 0.0])
        self.assertAlmostEqual(pnl.sum(), 0.0, places=12)

    def test_no_trades_is_a_zero_series_on_the_grid(self):
        pnl, expo = mtm.daily_series(mtm.trade_marks(None, self.b), self.sessions)
        self.assertEqual(list(pnl.index), list(self.sessions))
        self.assertFalse(pnl.any() or expo.any())


class Active(unittest.TestCase):
    def test_holding_the_instrument_has_no_active_pnl(self):
        days = pd.DatetimeIndex(pd.to_datetime(DAYS))
        r = pd.Series([0.01, -0.02, 0.005], index=days)
        a = mtm.active_pnl(r.copy(), pd.Series(1.0, index=days), r)
        self.assertTrue((a.abs() < 1e-15).all())

    def test_the_benchmark_is_scaled_by_mean_exposure(self):
        days = pd.DatetimeIndex(pd.to_datetime(DAYS))
        r = pd.Series([0.01, -0.02, 0.005], index=days)
        a = mtm.active_pnl(pd.Series(0.0, index=days), pd.Series([1.0, 0.0, 0.0], index=days), r)
        self.assertAlmostEqual(a.iloc[1], 0.02 / 3, places=15)

    def test_a_missing_instrument_session_is_refused(self):
        days = pd.DatetimeIndex(pd.to_datetime(DAYS))
        with self.assertRaises(ValueError):
            mtm.active_pnl(pd.Series(0.0, index=days), pd.Series(0.0, index=days),
                           pd.Series([0.0], index=days[:1]))

    def test_bar_session_returns_are_close_to_close(self):
        b = bars(DAYS, [[100] * 7, [101] * 7, [99.99] * 7])
        r = mtm.bar_session_returns(b)
        self.assertAlmostEqual(r.iloc[1], 0.01, places=12)
        self.assertAlmostEqual(r.iloc[2], 99.99 / 101 - 1, places=12)


class ThroughTheEngine(unittest.TestCase):
    """run_backtest marks every trade; the recorder writes the marks as named series."""

    @classmethod
    def setUpClass(cls):
        from src.backtest.runner import run_backtest
        n = 700
        idx = pd.date_range("2025-01-06 14:30", periods=n, freq="h", tz="UTC")
        rng = np.random.default_rng(7)
        close = 100 * (1 + 0.15 * np.sin(np.linspace(0, 18, n)) + rng.normal(0, 0.004, n).cumsum())
        close = np.maximum(close, 1.0)
        high = close * (1 + rng.uniform(0, 0.004, n))
        low = close * (1 - rng.uniform(0, 0.004, n))
        cls.df = pd.DataFrame({"open": (high + low) / 2, "high": high, "low": low, "close": close,
                               "volume": rng.integers(1_000, 50_000, n)}, index=idx)
        cls.res = run_backtest(df=cls.df.copy(), target_gain_pct=0.01, stop_loss_pct=0.005,
                               require_signals=1, timeframe="hourly", plot=False,
                               backtest_mode="realistic")

    def test_each_trades_marks_sum_to_its_booked_return(self):
        self.assertTrue(self.res, "the synthetic tape must produce trades")
        marks = self.res["trade_marks"]
        per_trade = marks.groupby("trade")["pnl"].sum()
        booked = self.res["trade_returns"]
        self.assertEqual(len(per_trade), len(booked))
        np.testing.assert_allclose(per_trade.reindex(booked.index).to_numpy(), booked.to_numpy(),
                                   atol=1e-12)
        self.assertLessEqual(marks.groupby("session")["exposure"].sum().max(), 1.0)

    def test_the_recorder_writes_mtm_pnl_and_exposure(self):
        with tempfile.TemporaryDirectory() as d:
            with trials.open_run(producer="t", family="f", ledger_dir=Path(d)) as run:
                bt.record_backtest(run.begin(params={}), self.res)
            rec = trials.iter_trials(Path(d))[0]
            self.assertEqual(sorted(rec.series_shas), ["exposure", "instrument_return", "mtm_pnl"])
            pnl = trials.load_series([rec], "mtm_pnl", ledger_dir=Path(d))[rec.key]
            self.assertAlmostEqual(pnl.sum(), self.res["trade_returns"].sum(), places=10)
            self.assertEqual(len(pnl), len(self.res["sessions"]))

    def test_a_restricted_outcome_restricts_the_marks(self):
        cut = self.res["trade_returns"].index[len(self.res["trade_returns"]) // 2]
        scored = bt.scored_from(self.res, cut)
        pnl, _ = mtm.daily_series(scored["trade_marks"], scored["sessions"])
        self.assertAlmostEqual(pnl.sum(), scored["trade_returns"].sum(), places=10)
        self.assertGreaterEqual(pd.DatetimeIndex(scored["sessions"]).min(),
                                mtm.session_dates(pd.DatetimeIndex([cut]))[0])


if __name__ == "__main__":
    unittest.main()
