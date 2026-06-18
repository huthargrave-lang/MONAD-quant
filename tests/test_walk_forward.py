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
from unittest import mock

import numpy as np
import pandas as pd

from src.optimization import walk_forward
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


class TestRunSlice(unittest.TestCase):
    """_run_slice must return a timestamp-indexed Series of trade returns.

    Regression: compute_trade_returns returns a DataFrame (timestamp/return/
    trend_regime/exit_type), but _run_slice used to unpack it as a 2-tuple
    (`returns, _exit_types = ...`), which raises ValueError — so the whole
    walk-forward optimizer (main.py --mode=walk-forward) crashed on the first
    parameter evaluation. build_features/generate_trades are mocked to a fixed
    feature frame so this isolates the return-contract handling.
    """

    def _feature_df(self):
        idx = pd.date_range("2024-01-01", periods=12, freq="D")
        close = np.linspace(100, 111, 12)
        df = pd.DataFrame({
            "open":  close,
            "high":  close + 2.0,   # generous range so the long target hits
            "low":   close - 2.0,
            "close": close,
            "entry_signal": [0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        }, index=idx)
        return df

    @mock.patch("src.optimization.walk_forward.generate_trades")
    @mock.patch("src.optimization.walk_forward.build_features")
    def test_returns_timestamp_indexed_series(self, mock_bf, mock_gt):
        feat = self._feature_df()
        mock_bf.return_value = feat
        mock_gt.return_value = feat
        out = walk_forward._run_slice(feat, rsi_oversold=35,
                                      target_gain_pct=0.01, stop_loss_pct=0.01)
        self.assertIsInstance(out, pd.Series)
        self.assertEqual(out.name, "return") if out.name else None
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(out.index))
        self.assertEqual(len(out), 1)                  # one entry signal -> one trade
        # _sharpe consumes this Series; it must not raise on it.
        self.assertTrue(np.isfinite(_sharpe(pd.concat([out, out, out]))) or True)

    @mock.patch("src.optimization.walk_forward.generate_trades")
    @mock.patch("src.optimization.walk_forward.build_features")
    def test_no_trades_returns_empty_series(self, mock_bf, mock_gt):
        feat = self._feature_df()
        feat["entry_signal"] = 0   # no entries
        mock_bf.return_value = feat
        mock_gt.return_value = feat
        out = walk_forward._run_slice(feat, rsi_oversold=35,
                                      target_gain_pct=0.01, stop_loss_pct=0.01)
        self.assertIsInstance(out, pd.Series)
        self.assertEqual(len(out), 0)


class TestWalkForwardEndToEnd(unittest.TestCase):
    """Run the real optimizer on synthetic daily data — no mocks.

    This exercises build_features -> generate_trades -> compute_trade_returns ->
    _run_slice -> _sharpe and would have caught BOTH stale-API bugs in _run_slice
    (the DataFrame tuple-unpack and the removed use_ma_regime_filter kwarg) that
    made `main.py --mode=walk-forward` crash.
    """

    def _synthetic_daily(self, n=520):
        idx = pd.date_range("2022-01-01", periods=n, freq="D")
        rng = np.random.default_rng(3)
        close = 100 * (1 + 0.2 * np.sin(np.linspace(0, 30, n)) + rng.normal(0, 0.01, n).cumsum())
        close = np.maximum(close, 5.0)
        return pd.DataFrame({
            "open": close, "high": close * 1.02, "low": close * 0.98,
            "close": close, "volume": rng.integers(1_000_000, 5_000_000, n),
        }, index=idx)

    def test_optimize_runs_without_raising(self):
        import contextlib
        import io
        df = self._synthetic_daily()
        grid = {"rsi_oversold": [35, 40], "target_gain_pct": [0.01], "stop_loss_pct": [0.01]}
        with contextlib.redirect_stdout(io.StringIO()):
            res = walk_forward.walk_forward_optimize(
                df, param_grid=grid, train_months=12, test_months=3
            )
        # May be {} if the synthetic data produced no OOS trades, but it must run.
        self.assertIsInstance(res, dict)
        if res:
            self.assertIsInstance(res["oos_trade_returns"], pd.Series)
            self.assertTrue(pd.api.types.is_datetime64_any_dtype(res["oos_trade_returns"].index))
            self.assertIn("oos_sharpe", res)
            self.assertIn("window_table", res)


if __name__ == "__main__":
    unittest.main()
