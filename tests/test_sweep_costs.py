"""
Tests for the sweep cost model (src/optimization/sweep_costs.py) and the
run_backtest slippage override they feed — C3.

The sweep estimated a bid-ask spread but never charged trade returns for it, so
high-trade-count configs escaped cumulative slippage cost. These pin the spread
tiers, the round-trip cost conversion, and that run_backtest now applies an
explicit slippage_pct (overriding the mode's fixed default).
"""
import math
import unittest

import numpy as np
import pandas as pd

from src.optimization.sweep_costs import (
    estimate_spread, round_trip_cost_pct, BROKER_SPREADS,
)


class TestEstimateSpread(unittest.TestCase):
    def test_retail_tiers(self):
        self.assertEqual(estimate_spread(10), 0.02)    # <15
        self.assertEqual(estimate_spread(30), 0.03)    # <50
        self.assertEqual(estimate_spread(100), 0.04)   # <150
        self.assertEqual(estimate_spread(200), 0.05)   # else

    def test_ibkr_tiers_tighter(self):
        self.assertEqual(estimate_spread(10, "ibkr"), 0.01)
        self.assertEqual(estimate_spread(200, "ibkr"), 0.02)

    def test_unknown_broker_falls_back_to_retail(self):
        self.assertEqual(estimate_spread(30, "nonexistent"), BROKER_SPREADS["retail"]["<50"])
        self.assertEqual(estimate_spread(30, None), 0.03)

    def test_tier_boundaries(self):
        # 15 -> not <15; 50 -> not <50; 150 -> else
        self.assertEqual(estimate_spread(15), 0.03)
        self.assertEqual(estimate_spread(50), 0.04)
        self.assertEqual(estimate_spread(150), 0.05)


class TestRoundTripCost(unittest.TestCase):
    def test_full_spread_fraction(self):
        # $0.04 spread on a $13 ETF -> ~0.31%/round-trip
        self.assertAlmostEqual(round_trip_cost_pct(0.04, 13.0), 0.04 / 13.0, places=9)

    def test_low_price_means_higher_cost(self):
        self.assertGreater(round_trip_cost_pct(0.04, 13.0), round_trip_cost_pct(0.04, 130.0))

    def test_nonpositive_price_is_zero(self):
        self.assertEqual(round_trip_cost_pct(0.04, 0.0), 0.0)
        self.assertEqual(round_trip_cost_pct(0.04, -5.0), 0.0)


class TestRunBacktestSlippageOverride(unittest.TestCase):
    """run_backtest must apply an explicit slippage_pct over the mode default."""

    def _synthetic(self, n=500):
        idx = pd.date_range("2025-01-01", periods=n, freq="h")
        rng = np.random.default_rng(7)
        steps = rng.normal(0, 0.004, n).cumsum()
        close = 100 * (1 + 0.15 * np.sin(np.linspace(0, 18, n)) + steps)
        close = np.maximum(close, 1.0)
        high = close * (1 + rng.uniform(0, 0.004, n))
        low = close * (1 - rng.uniform(0, 0.004, n))
        return pd.DataFrame({"open": (high + low) / 2, "high": high, "low": low,
                             "close": close, "volume": rng.integers(1_000, 50_000, n)},
                            index=idx)

    def _run(self, **kw):
        from src.backtest.runner import run_backtest
        return run_backtest(df=self._synthetic(), initial_capital=100_000,
                            target_gain_pct=0.01, stop_loss_pct=0.005, require_signals=1,
                            timeframe="hourly", plot=False, backtest_mode="realistic", **kw)

    def test_explicit_override_reflected(self):
        res = self._run(slippage_pct=0.01)
        if res:  # synthetic should produce trades
            self.assertAlmostEqual(res["slippage_pct"], 0.01, places=9)

    def test_default_uses_mode_value(self):
        res = self._run()  # no override -> realistic mode's 2bps
        if res:
            self.assertAlmostEqual(res["slippage_pct"], 0.0002, places=9)

    def test_higher_slippage_lowers_return(self):
        lo = self._run(slippage_pct=0.0)
        hi = self._run(slippage_pct=0.02)
        if lo and hi:
            self.assertGreater(lo["total_return"], hi["total_return"])


if __name__ == "__main__":
    unittest.main()
