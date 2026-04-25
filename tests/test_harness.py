"""
Tests for src/research/harness.py — shared research infrastructure.

Tests pure functions that don't require data fetching or full backtests:
  - CandidateParams construction and serialization
  - live_score penalty logic
  - compute_confidence verdict logic
  - equity_max_drawdown calculation
  - compare_candidates delta computation
"""

import unittest
from dataclasses import dataclass

import pandas as pd
from src.research.harness import (
    CandidateParams,
    CandidateResult,
    ValidationResult,
    AutoSweepConfig,
    extract_metrics,
    live_score,
    compute_confidence,
    equity_max_drawdown,
    compare_candidates,
)
import numpy as np


class TestCandidateParams(unittest.TestCase):

    def test_defaults(self):
        p = CandidateParams(ticker="TQQQ", target=0.01, stop=0.005)
        self.assertEqual(p.rsi, 80)
        self.assertEqual(p.vwap, 0.3)
        self.assertEqual(p.max_trade_bars, 20)
        self.assertEqual(p.backtest_mode, "realistic")

    def test_trade_hours_property(self):
        p = CandidateParams(ticker="X", target=0.01, stop=0.005,
                            entry_start_hour=10, entry_end_hour=15)
        self.assertEqual(p.trade_hours, (10, 15))

    def test_round_trip_serialization(self):
        p = CandidateParams(ticker="SOXL", target=0.009, stop=0.0045, rsi=75, vwap=1.2)
        d = p.to_dict()
        p2 = CandidateParams.from_dict(d)
        self.assertEqual(p.ticker, p2.ticker)
        self.assertAlmostEqual(p.target, p2.target)
        self.assertAlmostEqual(p.stop, p2.stop)
        self.assertEqual(p.rsi, p2.rsi)

    def test_from_dict_ignores_extra_keys(self):
        d = {"ticker": "QQQ", "target": 0.01, "stop": 0.005, "unknown_key": 99}
        p = CandidateParams.from_dict(d)
        self.assertEqual(p.ticker, "QQQ")
        self.assertFalse(hasattr(p, "unknown_key"))


class TestCandidateResult(unittest.TestCase):

    def test_to_dict_excludes_raw_result(self):
        p = CandidateParams(ticker="T", target=0.01, stop=0.005)
        m = CandidateResult(params=p, total_return_pct=5.0, raw_result={"big": "data"})
        d = m.to_dict()
        self.assertNotIn("raw_result", d)
        self.assertIn("params", d)
        self.assertEqual(d["total_return_pct"], 5.0)


class TestAutoSweepConfig(unittest.TestCase):

    def test_defaults(self):
        cfg = AutoSweepConfig()
        self.assertEqual(cfg.validate_top, 10)
        self.assertEqual(cfg.mc_samples, 500)
        self.assertFalse(cfg.skip_mc)


class TestExtractMetrics(unittest.TestCase):

    def _fake_result(self, **overrides) -> dict:
        """Build a minimal backtest result dict matching runner.py output."""
        mo = pd.Series([0.01, 0.005, -0.002, 0.008, 0.0, 0.003])
        mo.index = pd.date_range("2025-01-01", periods=6, freq="MS")
        defaults = {
            "total_return": 0.15,
            "sharpe_ratio": 25.0,
            "max_drawdown": -0.008,
            "win_rate": 0.58,
            "total_trades": 60,
            "monthly_returns": mo,
            "exit_breakdown": {
                "target_hit": 30,
                "stop_hit": 25,
                "time_exit": 3,
                "ambiguous_same_bar": 2,
            },
        }
        defaults.update(overrides)
        return defaults

    def test_preserves_params(self):
        p = CandidateParams(ticker="TQQQ", target=0.01, stop=0.005,
                            rsi=80, entry_start_hour=10)
        m = extract_metrics(self._fake_result(), p)
        self.assertIsNotNone(m)
        self.assertEqual(m.params.ticker, "TQQQ")
        self.assertAlmostEqual(m.params.target, 0.01)
        self.assertAlmostEqual(m.params.stop, 0.005)
        self.assertEqual(m.params.entry_start_hour, 10)

    def test_return_values(self):
        p = CandidateParams(ticker="X", target=0.01, stop=0.005)
        m = extract_metrics(self._fake_result(), p)
        self.assertAlmostEqual(m.total_return_pct, 15.0, places=1)
        self.assertAlmostEqual(m.sharpe_ratio, 25.0)
        self.assertEqual(m.total_trades, 60)
        self.assertAlmostEqual(m.win_rate_pct, 58.0)

    def test_exit_breakdown_counts(self):
        p = CandidateParams(ticker="X", target=0.01, stop=0.005)
        m = extract_metrics(self._fake_result(), p)
        self.assertEqual(m.target_hit_count, 30)
        self.assertEqual(m.stop_hit_count, 25)
        self.assertEqual(m.time_exit_count, 3)
        self.assertEqual(m.ambiguous_count, 2)

    def test_negative_months_counted(self):
        p = CandidateParams(ticker="X", target=0.01, stop=0.005)
        m = extract_metrics(self._fake_result(), p)
        self.assertEqual(m.neg_months, 1)

    def test_none_result_returns_none(self):
        p = CandidateParams(ticker="X", target=0.01, stop=0.005)
        self.assertIsNone(extract_metrics(None, p))

    def test_error_result_returns_none(self):
        p = CandidateParams(ticker="X", target=0.01, stop=0.005)
        self.assertIsNone(extract_metrics({"error": "boom"}, p))

    def test_stop_hit_ratio(self):
        p = CandidateParams(ticker="X", target=0.01, stop=0.005)
        m = extract_metrics(self._fake_result(), p)
        self.assertAlmostEqual(m.stop_hit_ratio, 25 / 60, places=2)


class TestLiveScore(unittest.TestCase):

    def _base_metrics(self, **overrides) -> CandidateResult:
        p = CandidateParams(ticker="T", target=0.01, stop=0.005)
        defaults = dict(
            params=p,
            total_return_pct=10.0,
            sharpe_ratio=30.0,
            max_drawdown_pct=-0.5,
            avg_monthly_pct=0.5,
            total_trades=100,
            win_rate_pct=55.0,
            neg_months=1,
            total_months=20,
            stop_hit_ratio=0.40,
            ambiguous_ratio=0.05,
            trades_per_month=5.0,
        )
        defaults.update(overrides)
        return CandidateResult(**defaults)

    def test_positive_score_for_good_candidate(self):
        m = self._base_metrics()
        s = live_score(m, median_price=50.0, est_spread=0.03)
        self.assertGreater(s, 0)

    def test_none_returns_negative(self):
        s = live_score(None, 50.0, 0.03)
        self.assertEqual(s, -9999)

    def test_zero_trades_returns_negative(self):
        m = self._base_metrics(total_trades=0)
        s = live_score(m, 50.0, 0.03)
        self.assertEqual(s, -9999)

    def test_high_stop_hit_penalty(self):
        good = self._base_metrics(stop_hit_ratio=0.40)
        bad = self._base_metrics(stop_hit_ratio=0.60)
        s_good = live_score(good, 50.0, 0.03)
        s_bad = live_score(bad, 50.0, 0.03)
        self.assertGreater(s_good, s_bad)

    def test_many_neg_months_penalty(self):
        good = self._base_metrics(neg_months=1, total_months=20)
        bad = self._base_metrics(neg_months=8, total_months=20)
        s_good = live_score(good, 50.0, 0.03)
        s_bad = live_score(bad, 50.0, 0.03)
        self.assertGreater(s_good, s_bad)

    def test_high_ambiguous_penalty(self):
        good = self._base_metrics(ambiguous_ratio=0.05)
        bad = self._base_metrics(ambiguous_ratio=0.25)
        s_good = live_score(good, 50.0, 0.03)
        s_bad = live_score(bad, 50.0, 0.03)
        self.assertGreater(s_good, s_bad)

    def test_low_trades_per_month_penalty(self):
        good = self._base_metrics(total_trades=100, total_months=20)
        bad = self._base_metrics(total_trades=30, total_months=20)
        s_good = live_score(good, 50.0, 0.03)
        s_bad = live_score(bad, 50.0, 0.03)
        self.assertGreater(s_good, s_bad)

    def test_spread_penalty_tight_stop(self):
        p_wide = CandidateParams(ticker="T", target=0.01, stop=0.005)
        p_tight = CandidateParams(ticker="T", target=0.01, stop=0.0003)
        m_wide = self._base_metrics(params=p_wide)
        m_tight = self._base_metrics(params=p_tight)
        s_wide = live_score(m_wide, median_price=50.0, est_spread=0.03)
        s_tight = live_score(m_tight, median_price=50.0, est_spread=0.03)
        self.assertGreater(s_wide, s_tight)

    def test_holdout_degradation_penalty(self):
        train = self._base_metrics(avg_monthly_pct=1.0)
        holdout_good = self._base_metrics(avg_monthly_pct=0.8)
        holdout_bad = self._base_metrics(avg_monthly_pct=-0.5)
        s_good = live_score(holdout_good, 50.0, 0.03, train_metrics=train)
        s_bad = live_score(holdout_bad, 50.0, 0.03, train_metrics=train)
        self.assertGreater(s_good, s_bad)


class TestComputeConfidence(unittest.TestCase):

    def test_perfect_score(self):
        vr = ValidationResult()
        result = compute_confidence(vr)
        self.assertEqual(result["confidence"], "HIGH")
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["warnings"], [])

    def test_unstable_rolling_deducts(self):
        vr = ValidationResult(
            rolling={"stable": False, "positive_windows": "2/4"}
        )
        result = compute_confidence(vr)
        self.assertLess(result["score"], 100)
        self.assertTrue(any("Unstable" in w for w in result["warnings"]))

    def test_unlucky_mc_deducts(self):
        vr = ValidationResult(
            monte_carlo={"unlucky_sequencing": True, "dd_percentile_rank": 0.1}
        )
        result = compute_confidence(vr)
        self.assertLess(result["score"], 100)

    def test_bad_drawdown_deducts(self):
        vr = ValidationResult(
            drawdown_profile={
                "max_consecutive_losses": 12,
                "worst_month_pct": -8,
                "negative_months": 10,
                "total_active_months": 20,
            }
        )
        result = compute_confidence(vr)
        self.assertLess(result["score"], 70)

    def test_fragile_slippage_deducts(self):
        vr = ValidationResult(
            slippage_sensitivity={"fragile": True, "degradation_per_bps": 1.5}
        )
        result = compute_confidence(vr)
        self.assertLess(result["score"], 100)

    def test_everything_bad_is_rejected(self):
        vr = ValidationResult(
            rolling={"stable": False, "positive_windows": "1/4"},
            monte_carlo={"unlucky_sequencing": True},
            drawdown_profile={
                "max_consecutive_losses": 15,
                "worst_month_pct": -10,
                "negative_months": 15,
                "total_active_months": 20,
            },
            slippage_sensitivity={"fragile": True, "degradation_per_bps": 2.0},
        )
        result = compute_confidence(vr)
        self.assertIn(result["confidence"], ("LOW", "REJECTED"))

    def test_score_clamped_to_0_100(self):
        vr = ValidationResult(
            rolling={"stable": False, "positive_windows": "0/4"},
            monte_carlo={"unlucky_sequencing": True},
            regime_split={"warnings": ["a", "b", "c", "d", "e"]},
            drawdown_profile={
                "max_consecutive_losses": 15,
                "worst_month_pct": -10,
                "negative_months": 15,
                "total_active_months": 20,
            },
            slippage_sensitivity={"fragile": True, "degradation_per_bps": 2.0},
        )
        result = compute_confidence(vr)
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)


class TestEquityMaxDrawdown(unittest.TestCase):

    def test_no_drawdown(self):
        returns = np.array([0.01, 0.01, 0.01])
        dd = equity_max_drawdown(returns)
        self.assertAlmostEqual(dd, 0.0)

    def test_simple_drawdown(self):
        returns = np.array([0.10, -0.20, 0.05])
        dd = equity_max_drawdown(returns)
        self.assertLess(dd, 0)

    def test_full_loss(self):
        returns = np.array([-0.5, -0.5])
        dd = equity_max_drawdown(returns)
        # equity = [50k, 25k], peak = [50k, 50k], dd from peak = -50%
        self.assertAlmostEqual(dd, -0.50, places=2)


class TestCompareCandidates(unittest.TestCase):

    def test_delta_computation(self):
        p = CandidateParams(ticker="T", target=0.01, stop=0.005)
        a = CandidateResult(params=p, total_return_pct=10.0, sharpe_ratio=20.0)
        b = CandidateResult(params=p, total_return_pct=15.0, sharpe_ratio=25.0)
        delta = compare_candidates(a, b)
        self.assertAlmostEqual(delta["total_return_pct"], 5.0)
        self.assertAlmostEqual(delta["sharpe_ratio"], 5.0)

    def test_identical_returns_zero_delta(self):
        p = CandidateParams(ticker="T", target=0.01, stop=0.005)
        a = CandidateResult(params=p, total_return_pct=10.0)
        delta = compare_candidates(a, a)
        self.assertAlmostEqual(delta["total_return_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
