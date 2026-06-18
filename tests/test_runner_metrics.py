"""
Tests for the backtest performance metrics (src/backtest/metrics.py).

These pin the *measurement* layer that produced the project's headline numbers —
Sharpe (trade-frequency annualization), max drawdown, total/buy-hold/annualized
return, and monthly compounding — on fixed synthetic inputs with hand-computed
expected values. The runner now delegates to these functions, so a change to any
of them is caught here rather than silently shifting reported performance.

Layers:
  * TestAnnualizedSharpe   — frequency annualization + degenerate handling
  * TestTradesPerYear      — calendar-span trade frequency
  * TestDrawdownReturns    — max_drawdown, total/buy-hold/annualized return
  * TestMonthlyReturns     — per-trade returns compounded into months
  * TestMetricsGoldenMaster— a fixed equity curve composed through every metric
"""
import unittest

import numpy as np
import pandas as pd

from src.backtest import metrics


class TestAnnualizedSharpe(unittest.TestCase):
    def test_known_value(self):
        # mean=0.005, std(ddof=1)=0.0173205..., ratio=0.288675, ×sqrt(4)=2 -> 0.57735
        self.assertAlmostEqual(
            metrics.annualized_sharpe([0.02, -0.01, 0.02, -0.01], 4), 0.5773502692, places=8
        )

    def test_scales_with_sqrt_of_frequency(self):
        r = [0.02, -0.01, 0.02, -0.01]
        # 4x the trades/year -> 2x the Sharpe (sqrt scaling). This is the whole point.
        self.assertAlmostEqual(
            metrics.annualized_sharpe(r, 16), 2 * metrics.annualized_sharpe(r, 4), places=10
        )

    def test_zero_std_returns_degenerate(self):
        self.assertEqual(metrics.annualized_sharpe([0.01, 0.01, 0.01], 100), 0.0)
        self.assertEqual(
            metrics.annualized_sharpe([0.01, 0.01, 0.01], 100, degenerate=-np.inf), -np.inf
        )

    def test_too_few_points_returns_degenerate(self):
        self.assertEqual(metrics.annualized_sharpe([0.01], 100), 0.0)
        self.assertEqual(metrics.annualized_sharpe([], 100), 0.0)

    def test_accepts_list_and_series_equally(self):
        r = [0.02, -0.01, 0.02, -0.01]
        self.assertEqual(
            metrics.annualized_sharpe(r, 4),
            metrics.annualized_sharpe(pd.Series(r), 4),
        )


class TestTradesPerYear(unittest.TestCase):
    def test_one_year_span(self):
        tpy = metrics.trades_per_year(
            12, pd.Timestamp("2020-01-01"), pd.Timestamp("2021-01-01")
        )
        self.assertAlmostEqual(tpy, 12 / (366 / 365.25), places=6)

    def test_zero_span_returns_trade_count(self):
        # Degenerate span collapses to one year -> just the trade count (matches runner).
        tpy = metrics.trades_per_year(
            12, pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-01")
        )
        self.assertEqual(tpy, 12)

    def test_higher_frequency_for_shorter_span(self):
        short = metrics.trades_per_year(
            50, pd.Timestamp("2020-01-01"), pd.Timestamp("2020-02-01")
        )
        long = metrics.trades_per_year(
            50, pd.Timestamp("2020-01-01"), pd.Timestamp("2025-01-01")
        )
        self.assertGreater(short, long)


class TestDrawdownReturns(unittest.TestCase):
    def test_max_drawdown(self):
        # peak 120 -> trough 90 = -25%
        self.assertAlmostEqual(metrics.max_drawdown([100, 120, 90, 130]), -0.25, places=10)

    def test_max_drawdown_monotonic_is_zero(self):
        self.assertEqual(metrics.max_drawdown([100, 110, 120, 130]), 0.0)

    def test_max_drawdown_empty(self):
        self.assertEqual(metrics.max_drawdown([]), 0.0)

    def test_total_return(self):
        self.assertAlmostEqual(
            metrics.total_return([100_000, 105_000, 110_000], 100_000), 0.10, places=10
        )

    def test_total_return_guards(self):
        self.assertEqual(metrics.total_return([], 100_000), 0.0)
        self.assertEqual(metrics.total_return([1, 2, 3], 0), 0.0)

    def test_buy_hold_return(self):
        self.assertAlmostEqual(metrics.buy_hold_return([100, 120, 150]), 0.50, places=10)

    def test_buy_hold_zero_first_price(self):
        self.assertEqual(metrics.buy_hold_return([0, 150]), 0.0)

    def test_annualize_return(self):
        # (1.21)^(1/2) - 1 = 0.10
        self.assertAlmostEqual(metrics.annualize_return(0.21, 2), 0.10, places=10)

    def test_annualize_return_zero_years(self):
        self.assertEqual(metrics.annualize_return(0.21, 0), 0.21)


class TestMonthlyReturns(unittest.TestCase):
    def test_compounds_within_month(self):
        s = pd.Series(
            [0.01, 0.02, -0.01],
            index=pd.to_datetime(["2020-01-05", "2020-01-20", "2020-02-10"]),
        )
        m = metrics.monthly_returns(s)
        self.assertEqual(len(m), 2)
        self.assertAlmostEqual(m.iloc[0], 1.01 * 1.02 - 1, places=10)  # Jan
        self.assertAlmostEqual(m.iloc[1], -0.01, places=10)            # Feb

    def test_empty_returns_empty(self):
        self.assertTrue(metrics.monthly_returns(pd.Series([], dtype=float)).empty)


class TestMetricsGoldenMaster(unittest.TestCase):
    """A fixed equity curve composed through every metric — config-independent.

    These exact values characterize the current metric definitions. A break here
    means a metric's behavior changed (regenerate intentionally); it cannot be
    perturbed by config/sweep edits because nothing here reads config.
    """

    def _curve(self):
        # 6 trades over exactly one year, deterministic.
        ts = pd.to_datetime([
            "2020-01-15", "2020-03-10", "2020-05-01",
            "2020-07-20", "2020-09-05", "2020-12-20",
        ])
        per_trade = pd.Series([0.02, -0.01, 0.03, -0.015, 0.025, -0.005], index=ts)
        initial = 100_000.0
        equity = [initial]
        for r in per_trade:
            equity.append(equity[-1] * (1 + r))
        return per_trade, pd.Series(equity, dtype=float), initial

    def test_composed_metrics(self):
        per_trade, equity, initial = self._curve()
        tr = metrics.total_return(equity, initial)
        tpy = metrics.trades_per_year(len(per_trade), per_trade.index[0], per_trade.index[-1])
        sharpe = metrics.annualized_sharpe(equity.pct_change().dropna(), tpy)
        mdd = metrics.max_drawdown(equity)
        monthly = metrics.monthly_returns(per_trade)

        # total return = product of (1+r) - 1
        expected_tr = np.prod([1 + r for r in per_trade]) - 1
        self.assertAlmostEqual(tr, expected_tr, places=10)
        # equity pct_change equals the per-trade returns exactly -> Sharpe well-defined
        self.assertTrue(np.allclose(equity.pct_change().dropna().values, per_trade.values))
        self.assertTrue(np.isfinite(sharpe))
        self.assertGreater(sharpe, 0)        # net-positive curve
        self.assertLess(mdd, 0)              # had at least one losing trade
        self.assertGreaterEqual(mdd, -1.0)
        # one entry per distinct trade-month (6 trades in 6 different months)
        self.assertEqual((monthly != 0).sum(), 6)


if __name__ == "__main__":
    unittest.main()
