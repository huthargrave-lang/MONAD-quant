"""
Tests for the walk-forward parameter optimizer (src/optimization/walk_forward.py).

Focus: the Sharpe annualization used to *select* parameters (walk_forward.py:174).
The historical bug annualized a per-trade returns series by a fixed `sqrt(252)`
regardless of how frequently the strategy actually traded. That biases parameter
selection — it inflates Sharpe for sparse daily trades (~17/yr) and is wrong in
the other direction for hourly modes (~1500/yr). The correct annualization,
matching `src/backtest/runner.py:269-273`, scales by the actual trade frequency
(trades per year) derived from the returns' datetime index.

Layers:
  * TestSharpeGuards            — degenerate inputs return -inf (unchanged)
  * TestSharpeTradeFrequency    — annualizes by trade frequency, not a fixed 252
  * TestMakeWindows             — rolling train/test window geometry
"""
import unittest

import numpy as np
import pandas as pd

from src.optimization.walk_forward import _sharpe, _make_windows


def _returns_over_span(values, start, periods=None, freq=None, end=None):
    """Build a trade-returns Series indexed by a datetime span.

    Pass either (periods, freq) or an explicit `end` to control the calendar
    span the trades are spread across — that span is what sets trade frequency.
    """
    if end is not None:
        idx = pd.date_range(start=start, end=end, periods=len(values))
    else:
        idx = pd.date_range(start=start, periods=len(values), freq=freq)
    return pd.Series(values, index=idx, dtype=float)


def _expected_sharpe(returns):
    """Reference: frequency-annualized Sharpe, mirroring runner.py."""
    idx = returns.index
    n_days = (idx[-1] - idx[0]).days
    years = n_days / 365.25 if n_days > 0 else 1
    trades_per_year = len(returns) / years if years > 0 else len(returns)
    return (returns.mean() / returns.std()) * np.sqrt(trades_per_year)


class TestSharpeGuards(unittest.TestCase):
    def test_fewer_than_three_trades_returns_neg_inf(self):
        r = _returns_over_span([0.01, -0.005], "2020-01-01", freq="D")
        self.assertEqual(_sharpe(r), -np.inf)

    def test_zero_std_returns_neg_inf(self):
        r = _returns_over_span([0.01, 0.01, 0.01, 0.01], "2020-01-01", freq="D")
        self.assertEqual(_sharpe(r), -np.inf)

    def test_empty_series_returns_neg_inf(self):
        r = pd.Series([], index=pd.to_datetime([]), dtype=float)
        self.assertEqual(_sharpe(r), -np.inf)


class TestSharpeTradeFrequency(unittest.TestCase):
    """The core correctness contract: scale by trade frequency, not a fixed 252."""

    def test_matches_runner_frequency_formula(self):
        # 12 trades spread across ~1 calendar year.
        vals = [0.01, -0.005, 0.012, -0.004, 0.009, -0.006,
                0.011, -0.005, 0.008, -0.003, 0.010, -0.004]
        r = _returns_over_span(vals, "2020-01-01", end="2021-01-01")
        self.assertAlmostEqual(_sharpe(r), _expected_sharpe(r), places=6)

    def test_higher_trade_frequency_gives_higher_sharpe(self):
        # Identical per-trade stats; only the calendar span (hence frequency) differs.
        vals = [0.01, -0.005, 0.012, -0.004, 0.009, -0.006]
        sparse = _returns_over_span(vals, "2020-01-01", end="2025-01-01")  # ~6 trades / 5yr
        dense = _returns_over_span(vals, "2020-01-01", end="2020-02-01")   # ~6 trades / month
        # Same Sharpe-per-trade, but dense trades far more often -> higher annualized Sharpe.
        self.assertGreater(_sharpe(dense), _sharpe(sparse))

    def test_span_changes_result_not_just_values(self):
        # The bug: a fixed sqrt(252) makes these two IDENTICAL despite different spans.
        # The fix: different spans -> different annualized Sharpe.
        vals = [0.01, -0.005, 0.012, -0.004, 0.009]
        one_year = _returns_over_span(vals, "2020-01-01", end="2021-01-01")
        one_month = _returns_over_span(vals, "2020-01-01", end="2020-02-01")
        self.assertNotAlmostEqual(_sharpe(one_year), _sharpe(one_month), places=3)

    def test_sparse_daily_not_inflated_to_252_assumption(self):
        # ~17 trades/yr (daily strategy reality) must annualize well below the
        # old sqrt(252)=~15.9 multiplier implied scale.
        vals = [0.01, -0.005, 0.012, -0.004, 0.009, -0.006, 0.011, -0.005]
        r = _returns_over_span(vals, "2020-01-01", end="2020-07-01")  # 8 trades / 0.5yr -> 16/yr
        # Expected multiplier ~sqrt(16) = 4, far from sqrt(252).
        implied_mult = _sharpe(r) / (r.mean() / r.std())
        self.assertLess(implied_mult, np.sqrt(252) * 0.6)
        self.assertAlmostEqual(_sharpe(r), _expected_sharpe(r), places=6)


class TestMakeWindows(unittest.TestCase):
    def _daily_df(self, months):
        idx = pd.date_range("2020-01-01", periods=months * 30, freq="D")
        return pd.DataFrame({"close": np.arange(len(idx), dtype=float)}, index=idx)

    def test_returns_empty_when_too_short(self):
        df = self._daily_df(months=6)  # < train(18)+test(6)
        self.assertEqual(_make_windows(df, train_months=18, test_months=6), [])

    def test_rolls_forward_by_test_months(self):
        df = self._daily_df(months=36)
        windows = _make_windows(df, train_months=18, test_months=6)
        self.assertGreater(len(windows), 0)
        # Test windows are contiguous and non-overlapping: each test_start equals
        # the previous test_end.
        for prev, cur in zip(windows, windows[1:]):
            _, _, _, prev_test_end = prev
            _, _, cur_test_start, _ = cur
            self.assertEqual(prev_test_end, cur_test_start)

    def test_train_precedes_test(self):
        df = self._daily_df(months=36)
        for train_start, train_end, test_start, test_end in _make_windows(
            df, train_months=18, test_months=6
        ):
            self.assertLessEqual(train_start, train_end)
            self.assertEqual(train_end, test_start)
            self.assertLess(test_start, test_end)


if __name__ == "__main__":
    unittest.main()
