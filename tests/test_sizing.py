"""
Extensive tests for position sizing — Kelly, adaptive Kelly, and the sizing
workflow used by the backtest/sweep. This is the previously-untested core that
decides how much capital each trade deploys, including "run with adaptive Kelly".

Layers:
  * TestKellyMath          — kelly_fraction / half_kelly / compute_position_size
  * TestAdaptiveKelly      — recent_win_rate + the rolling-WR tier multiplier
  * TestPositionFraction   — the single mode-parameterized entry point
  * TestSizingWorkflow     — a simulated equity loop (adaptive ON vs OFF, fixed,
                             no-lookahead) — the deterministic workflow proof
  * TestBacktestSmoke      — run_backtest end-to-end with each sizing mode
"""
import math
import unittest

import pandas as pd

from src.strategy import sizing
from src.strategy.sizing import (
    kelly_fraction, half_kelly, compute_position_size, estimate_stats_from_backtest,
    recent_win_rate, adaptive_kelly_multiplier, position_fraction,
)


class TestKellyMath(unittest.TestCase):
    def test_known_value(self):
        # WR=0.6, win=0.01, loss=0.005 -> b=2, f=(0.6*2-0.4)/2 = 0.4
        self.assertAlmostEqual(kelly_fraction(0.6, 0.01, 0.005), 0.4, places=6)

    def test_half_kelly(self):
        self.assertAlmostEqual(half_kelly(0.6, 0.01, 0.005), 0.2, places=6)

    def test_negative_edge_clamped_to_zero(self):
        # 40% WR at 1:1 R:R -> negative edge -> 0
        self.assertEqual(kelly_fraction(0.4, 0.01, 0.01), 0.0)

    def test_zero_avg_loss_guard(self):
        self.assertEqual(kelly_fraction(0.6, 0.01, 0.0), 0.0)

    def test_compute_position_size_caps(self):
        out = compute_position_size(10_000, win_rate=0.9, avg_win_pct=0.02,
                                    avg_loss_pct=0.005, kelly_multiplier=1.0,
                                    max_position_pct=0.20)
        self.assertLessEqual(out["kelly_capped"], 0.20)
        self.assertEqual(out["position_dollars"], round(10_000 * out["kelly_capped"], 2))

    def test_compute_position_size_floor_only_with_edge(self):
        # Positive edge but thin -> floored to min_position_pct
        out = compute_position_size(1.0, 0.55, 0.011, 0.01, kelly_multiplier=0.01,
                                    min_position_pct=0.05, max_position_pct=0.20)
        self.assertGreaterEqual(out["kelly_capped"], 0.05)
        # Negative edge -> NOT floored (stays 0)
        neg = compute_position_size(1.0, 0.40, 0.01, 0.01, kelly_multiplier=0.5,
                                    min_position_pct=0.05)
        self.assertEqual(neg["kelly_capped"], 0.0)


class TestAdaptiveKelly(unittest.TestCase):
    AK = dict(lookback=10, high_wr=0.60, low_wr=0.45, pause_wr=0.35,
              high_mult=2.0, low_mult=0.5, pause_mult=0.2, high_cap=0.30)

    def test_recent_win_rate(self):
        self.assertEqual(recent_win_rate([1, -1, 1, 1], 10), 0.75)
        self.assertEqual(recent_win_rate([], 10), 0.0)
        # only the last `lookback` count
        self.assertEqual(recent_win_rate([-1] * 10 + [1, 1], 2), 1.0)

    def test_warmup_unchanged(self):
        # fewer than lookback recent trades -> base unchanged
        self.assertEqual(adaptive_kelly_multiplier(0.10, [0.01] * 5, **self.AK), 0.10)

    def test_high_tier_sizes_up_and_caps(self):
        # all wins -> WR=1.0 >= high_wr -> *2.0, capped at 0.30
        self.assertEqual(adaptive_kelly_multiplier(0.10, [0.01] * 10, **self.AK), 0.20)
        self.assertEqual(adaptive_kelly_multiplier(0.20, [0.01] * 10, **self.AK), 0.30)  # capped

    def test_pause_tier(self):
        rets = [0.01] * 3 + [-0.01] * 7      # WR=0.30 < pause_wr -> *0.2
        self.assertAlmostEqual(adaptive_kelly_multiplier(0.10, rets, **self.AK), 0.02)

    def test_low_tier(self):
        rets = [0.01] * 4 + [-0.01] * 6      # WR=0.40: >=pause, <low -> *0.5
        self.assertAlmostEqual(adaptive_kelly_multiplier(0.10, rets, **self.AK), 0.05)

    def test_normal_tier_unchanged(self):
        rets = [0.01] * 5 + [-0.01] * 5      # WR=0.50: >=low, <high -> unchanged
        self.assertEqual(adaptive_kelly_multiplier(0.10, rets, **self.AK), 0.10)

    def test_tier_boundaries(self):
        # WR exactly high_wr -> HIGH (>=)
        rets = [0.01] * 6 + [-0.01] * 4      # WR=0.60 == high_wr
        self.assertEqual(adaptive_kelly_multiplier(0.10, rets, **self.AK), 0.20)


class TestPositionFraction(unittest.TestCase):
    def test_fixed_mode(self):
        f = position_fraction(mode="fixed", fixed_pct=0.10, rolling_returns=[0.01] * 30)
        self.assertEqual(f, 0.10)

    def test_kelly_rolling_warmup_uses_min(self):
        f = position_fraction(mode="kelly", kelly_mode="rolling",
                              rolling_returns=[0.01] * 3, min_pct=0.02, min_trades_for_kelly=10)
        self.assertEqual(f, 0.02)

    def test_kelly_rolling_sizes_from_history(self):
        f = position_fraction(mode="kelly", kelly_mode="rolling",
                              rolling_returns=[0.01, -0.005] * 10, kelly_multiplier=0.5,
                              min_pct=0.0, max_pct=0.20, min_trades_for_kelly=10)
        self.assertGreater(f, 0.0)
        self.assertLessEqual(f, 0.20)

    def test_adaptive_on_vs_off(self):
        # High (not 100%) recent win rate -> base Kelly > 0 AND HIGH tier fires.
        # (All-wins would make Kelly undefined: no losses -> 0.)
        hist = ([0.01] * 7 + [-0.005] * 3) * 2   # 20 trades, WR=0.70
        off = position_fraction(mode="kelly", kelly_mode="rolling", rolling_returns=hist,
                                kelly_multiplier=0.5, min_pct=0.02, max_pct=0.20, adaptive=None)
        on = position_fraction(mode="kelly", kelly_mode="rolling", rolling_returns=hist,
                               kelly_multiplier=0.5, min_pct=0.02, max_pct=0.20,
                               adaptive=dict(lookback=20, high_wr=0.46, low_wr=0.42,
                                             pause_wr=0.35, high_mult=2.0, low_mult=0.5,
                                             pause_mult=0.2, high_cap=0.35))
        self.assertGreater(on, off)  # adaptive HIGH tier deploys more

    def test_kelly_clamped(self):
        f = position_fraction(mode="kelly_clamped", kelly_mode="rolling",
                              rolling_returns=[0.05] * 20, kelly_multiplier=1.0,
                              max_pct=0.50, clamp_min=0.02, clamp_max=0.10)
        self.assertLessEqual(f, 0.10)
        self.assertGreaterEqual(f, 0.02)


class TestSizingWorkflow(unittest.TestCase):
    """Simulate the runner's equity loop deterministically over a trade sequence."""

    def _run(self, returns, *, mode="kelly", adaptive=None, fixed_pct=0.10):
        capital = 100_000.0
        rolling, sizes = [], []
        for r in returns:
            frac = position_fraction(
                mode=mode, kelly_mode="rolling", rolling_returns=list(rolling),
                kelly_multiplier=0.5, min_pct=0.02, max_pct=0.20,
                fixed_pct=fixed_pct, min_trades_for_kelly=10, adaptive=adaptive)
            sizes.append(frac)
            capital += capital * frac * r
            rolling.append(r)   # AFTER sizing — no lookahead
        return capital, sizes

    def test_fixed_is_constant(self):
        _, sizes = self._run([0.01, -0.01, 0.02] * 10, mode="fixed", fixed_pct=0.10)
        self.assertTrue(all(s == 0.10 for s in sizes))

    def test_adaptive_changes_trajectory(self):
        seq = ([0.008] * 4 + [-0.004]) * 5   # 25 trades, WR=0.80 (real losses -> Kelly>0)
        ak = dict(lookback=20, high_wr=0.46, low_wr=0.42, pause_wr=0.35,
                  high_mult=2.0, low_mult=0.5, pause_mult=0.2, high_cap=0.35)
        cap_off, _ = self._run(seq, adaptive=None)
        cap_on, sizes_on = self._run(seq, adaptive=ak)
        # Adaptive sizes up after the streak -> ends with more capital.
        self.assertGreater(cap_on, cap_off)
        # And later trades (post-lookback, high WR) deploy more than early ones.
        self.assertGreater(max(sizes_on), sizes_on[0])

    def test_pause_after_losses(self):
        seq = [-0.01] * 25
        ak = dict(lookback=20, high_wr=0.46, low_wr=0.42, pause_wr=0.35,
                  high_mult=2.0, low_mult=0.5, pause_mult=0.2, high_cap=0.35)
        _, sizes = self._run(seq, adaptive=ak)
        # After 20 losses, WR=0 < pause_wr -> heavily de-risked (pause_mult).
        self.assertLess(sizes[-1], sizes[0] + 1e-9)

    def test_no_lookahead(self):
        # The fraction for trade i must not depend on trade i's own return:
        # flipping the last return's sign must not change the sizes computed so far.
        base = [0.01] * 12
        _, s1 = self._run(base + [0.01])
        _, s2 = self._run(base + [-0.01])
        self.assertEqual(s1[:-1], s2[:-1])


class TestEstimateStats(unittest.TestCase):
    def test_basic(self):
        st = estimate_stats_from_backtest(pd.Series([0.02, -0.01, 0.02, -0.01]))
        self.assertEqual(st["win_rate"], 0.5)
        self.assertAlmostEqual(st["avg_win_pct"], 0.02, places=4)
        self.assertAlmostEqual(st["avg_loss_pct"], 0.01, places=4)
        self.assertEqual(st["total_trades"], 4)

    def test_empty(self):
        st = estimate_stats_from_backtest(pd.Series([], dtype=float))
        self.assertEqual(st["total_trades"], 0)
        self.assertEqual(st["win_rate"], 0)


class TestBacktestSmoke(unittest.TestCase):
    """run_backtest end-to-end with each sizing mode on synthetic hourly data.

    Verifies the workflow plumbs each sizing mode through without crashing.
    Lenient on trade count (synthetic data may produce few/none) — the point is
    that 'run with adaptive Kelly' (and fixed/kelly) executes the full pipeline.
    """

    def _synthetic(self, n=500):
        import numpy as np
        idx = pd.date_range("2025-01-01", periods=n, freq="h")
        rng = np.random.default_rng(7)
        # mean-reverting-ish price with intraday swings
        steps = rng.normal(0, 0.004, n).cumsum()
        close = 100 * (1 + 0.15 * np.sin(np.linspace(0, 18, n)) + steps)
        close = np.maximum(close, 1.0)
        high = close * (1 + rng.uniform(0, 0.004, n))
        low = close * (1 - rng.uniform(0, 0.004, n))
        open_ = (high + low) / 2
        vol = rng.integers(1_000, 50_000, n)
        return pd.DataFrame({"open": open_, "high": high, "low": low,
                             "close": close, "volume": vol}, index=idx)

    def test_runs_with_each_sizing_mode(self):
        from unittest import mock
        from src.backtest.runner import run_backtest
        import config
        df = self._synthetic()
        scenarios = [("fixed", False), ("kelly", True), ("kelly", False)]
        for sizing_mode, adaptive in scenarios:
            with self.subTest(sizing_mode=sizing_mode, adaptive=adaptive), \
                 mock.patch.object(config, "POSITION_SIZING_MODE", sizing_mode, create=True), \
                 mock.patch.object(config, "USE_ADAPTIVE_KELLY", adaptive, create=True):
                result = run_backtest(
                    df=df.copy(), initial_capital=100_000,
                    target_gain_pct=0.01, stop_loss_pct=0.005, require_signals=1,
                    kelly_multiplier=0.5, timeframe="hourly", plot=False,
                    backtest_mode="realistic",
                )
                # Either None (no trades) or a valid result dict — never an exception.
                if result is not None:
                    self.assertIn("sharpe_ratio", result)
                    self.assertIn("total_return", result)
                    self.assertTrue(math.isfinite(result["sharpe_ratio"]))


if __name__ == "__main__":
    unittest.main()
