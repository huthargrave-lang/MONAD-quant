"""
Tests for the sweep scoring decision layer (src/optimization/sweep_scoring.py).

This is the function that *selects production parameters* from a sweep — the
plan's "test the decision layer, not just the mechanics." Each ``live_score``
penalty is isolated by starting from a no-penalty baseline and toggling exactly
one hostile trait, asserting the resulting multiplicative shrink.

Layers:
  * TestExtractMetrics  — flattening a backtest result into scoring inputs
  * TestLiveScoreBase   — the base objective with no penalties active
  * TestLiveScorePenalties — each penalty tier in isolation
  * TestSpreadPenalty   — stop-inside-spread penalty (explicit spread/price args)
"""
import unittest

import pandas as pd

from src.optimization.sweep_scoring import extract_metrics, live_score, ev_score


def _result(total_return=0.10, sharpe=4.0, max_dd=-0.01, win_rate=0.55,
            monthly=None, total_trades=120,
            target_hit=80, stop_hit=30, ambiguous=5, time_exit=5,
            error=False):
    """A backtest-result dict with no-penalty defaults (base score = 4.8)."""
    if error:
        return {"error": "boom"}
    if monthly is None:
        monthly = pd.Series(
            [0.01] * 12, index=pd.date_range("2024-01-31", periods=12, freq="ME")
        )
    return {
        "monthly_returns": monthly,
        "exit_breakdown": {
            "target_hit": target_hit, "stop_hit": stop_hit,
            "ambiguous_same_bar": ambiguous, "time_exit": time_exit,
        },
        "total_trades": total_trades,
        "total_return": total_return,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_dd,
        "win_rate": win_rate,
    }


# base = sharpe*0.5 + return_pct*0.3 + dd_pct*0.2 = 4*0.5 + 10*0.3 + (-1)*0.2
BASE = 4.8


class TestExtractMetrics(unittest.TestCase):
    def test_none_and_error_return_none(self):
        self.assertIsNone(extract_metrics(None))
        self.assertIsNone(extract_metrics({"error": "x"}))

    def test_basic_extraction(self):
        m = extract_metrics(_result())
        self.assertEqual(m["total_return_pct"], 10.0)
        self.assertEqual(m["max_drawdown_pct"], -1.0)
        self.assertEqual(m["win_rate_pct"], 55.0)
        self.assertEqual(m["total_trades"], 120)
        self.assertEqual(m["stop_hit_ratio"], round(30 / 120, 3))
        self.assertEqual(m["ambiguous_ratio"], round(5 / 120, 3))
        self.assertEqual(m["target_hit_count"], 80)
        self.assertEqual(m["time_exit_count"], 5)

    def test_active_months_exclude_zeros(self):
        monthly = pd.Series(
            [0.02, 0.0, -0.01, 0.0, 0.03],
            index=pd.date_range("2024-01-31", periods=5, freq="ME"),
        )
        m = extract_metrics(_result(monthly=monthly))
        self.assertEqual(m["total_months"], 3)   # the two zeros excluded
        self.assertEqual(m["neg_months"], 1)

    def test_zero_trades_no_division_error(self):
        m = extract_metrics(_result(total_trades=0, stop_hit=0, ambiguous=0,
                                    target_hit=0, time_exit=0))
        self.assertEqual(m["stop_hit_ratio"], 0)
        self.assertEqual(m["ambiguous_ratio"], 0)


class TestLiveScoreBase(unittest.TestCase):
    def test_errored_result_is_floored(self):
        self.assertEqual(live_score(None), -9999)
        self.assertEqual(live_score({"error": "x"}), -9999)

    def test_no_penalties_equals_base(self):
        self.assertAlmostEqual(live_score(_result()), BASE, places=6)

    def test_base_formula_components(self):
        # Different sharpe/return/dd -> base recomputes; no penalties active.
        r = _result(sharpe=2.0, total_return=0.05, max_dd=-0.02)
        expected = 2.0 * 0.5 + 5.0 * 0.3 + (-2.0) * 0.2
        self.assertAlmostEqual(live_score(r), expected, places=6)


class TestLiveScorePenalties(unittest.TestCase):
    def test_stop_hit_ratio_tiers(self):
        # >0.55 -> 0.6 ;  >0.50 -> 0.8
        self.assertAlmostEqual(
            live_score(_result(stop_hit=70, target_hit=45, ambiguous=0, time_exit=5)),
            BASE * 0.6, places=6)
        self.assertAlmostEqual(
            live_score(_result(stop_hit=63, target_hit=52, ambiguous=0, time_exit=5)),
            BASE * 0.8, places=6)

    def test_negative_months_tiers(self):
        idx = pd.date_range("2024-01-31", periods=12, freq="ME")
        # 4/12 negative -> >0.25 -> 0.5
        many_neg = pd.Series([0.01] * 8 + [-0.01] * 4, index=idx)
        self.assertAlmostEqual(live_score(_result(monthly=many_neg)), BASE * 0.5, places=6)
        # 2/12 negative -> >0.10 -> 0.75
        some_neg = pd.Series([0.01] * 10 + [-0.01] * 2, index=idx)
        self.assertAlmostEqual(live_score(_result(monthly=some_neg)), BASE * 0.75, places=6)

    def test_ambiguous_tiers(self):
        # >0.20 -> 0.5 ;  >0.10 -> 0.75  (keep stop low, plenty of trades)
        self.assertAlmostEqual(
            live_score(_result(total_trades=120, ambiguous=30, stop_hit=10, target_hit=75, time_exit=5)),
            BASE * 0.5, places=6)
        self.assertAlmostEqual(
            live_score(_result(total_trades=120, ambiguous=18, stop_hit=10, target_hit=87, time_exit=5)),
            BASE * 0.75, places=6)

    def test_too_few_trades_tiers(self):
        # <3/mo -> 0.5 ;  <5/mo -> 0.75  (12 active months)
        self.assertAlmostEqual(
            live_score(_result(total_trades=30, stop_hit=5, ambiguous=1, target_hit=20, time_exit=4)),
            BASE * 0.5, places=6)
        self.assertAlmostEqual(
            live_score(_result(total_trades=48, stop_hit=5, ambiguous=1, target_hit=38, time_exit=4)),
            BASE * 0.75, places=6)

    def test_holdout_degradation_tiers(self):
        base_r = _result()  # holdout avg_monthly_pct = 1.0
        # retention 0.5 (1.0/2.0) -> in [0.4,0.6) -> 0.7
        self.assertAlmostEqual(
            live_score(base_r, train_metrics={"avg_monthly_pct": 2.0}), BASE * 0.7, places=6)
        # retention 0.25 (1.0/4.0) -> <0.4 -> 0.5
        self.assertAlmostEqual(
            live_score(base_r, train_metrics={"avg_monthly_pct": 4.0}), BASE * 0.5, places=6)
        # retention >=0.6 -> no penalty
        self.assertAlmostEqual(
            live_score(base_r, train_metrics={"avg_monthly_pct": 1.0}), BASE, places=6)

    def test_holdout_penalty_skipped_when_train_avg_not_positive(self):
        # train_avg <= 0 -> retention block guarded off -> no penalty
        self.assertAlmostEqual(
            live_score(_result(), train_metrics={"avg_monthly_pct": 0.0}), BASE, places=6)

    def test_holdout_negative_retention_compounds_with_neg_months(self):
        # Negative holdout avg necessarily implies negative months, so both
        # penalties fire: 0.3 (retention<0) × 0.5 (neg_frac>0.25).
        idx = pd.date_range("2024-01-31", periods=2, freq="ME")
        neg_avg = pd.Series([0.05, -0.07], index=idx)  # mean < 0
        r = _result(monthly=neg_avg, total_trades=20, stop_hit=2, ambiguous=1,
                    target_hit=15, time_exit=2)
        self.assertAlmostEqual(
            live_score(r, train_metrics={"avg_monthly_pct": 1.0}), BASE * 0.5 * 0.3, places=6)


class TestSpreadPenalty(unittest.TestCase):
    def test_spread_mult_below_3(self):
        # stop_dollars = 100*0.005 = 0.5 ; spread 0.25 -> mult 2.0 (<3) -> 0.3
        self.assertAlmostEqual(
            live_score(_result(), stop=0.005, est_spread=0.25, median_price=100),
            BASE * 0.3, places=6)

    def test_spread_mult_between_3_and_5(self):
        # spread 0.125 -> mult 4.0 -> 0.7
        self.assertAlmostEqual(
            live_score(_result(), stop=0.005, est_spread=0.125, median_price=100),
            BASE * 0.7, places=6)

    def test_spread_mult_above_5_no_penalty(self):
        # spread 0.05 -> mult 10 -> no penalty
        self.assertAlmostEqual(
            live_score(_result(), stop=0.005, est_spread=0.05, median_price=100),
            BASE, places=6)

    def test_zero_spread_disables_penalty(self):
        self.assertAlmostEqual(
            live_score(_result(), stop=0.005, est_spread=0.0, median_price=100), BASE, places=6)

    def test_stop_none_disables_penalty(self):
        self.assertAlmostEqual(
            live_score(_result(), stop=None, est_spread=0.25, median_price=100), BASE, places=6)


class TestEvScore(unittest.TestCase):
    """The opt-in net-of-cost EV objective (C4)."""

    def test_errored_result_floored(self):
        self.assertEqual(ev_score(None), -9999)
        self.assertEqual(ev_score({"error": "x"}), -9999)

    def test_base_is_total_return_no_penalties(self):
        # No penalties active -> score == total_return_pct (not the Sharpe blend).
        self.assertAlmostEqual(ev_score(_result()), 10.0, places=6)

    def test_hard_rejects_sub_breakeven_win_rate(self):
        # WR below 34% (2:1 breakeven) -> heavy fixed penalty regardless of return.
        r = _result(win_rate=0.30)
        self.assertAlmostEqual(ev_score(r), 10.0 - 1000.0, places=6)

    def test_win_rate_at_floor_not_rejected(self):
        self.assertAlmostEqual(ev_score(_result(win_rate=0.34)), 10.0, places=6)

    def test_custom_min_wr(self):
        self.assertLess(ev_score(_result(win_rate=0.40), min_wr_pct=45.0), 0)

    def test_penalties_still_apply(self):
        # >25% negative months halves the base (10.0 * 0.5 = 5.0).
        idx = pd.date_range("2024-01-31", periods=12, freq="ME")
        many_neg = pd.Series([0.01] * 8 + [-0.01] * 4, index=idx)
        self.assertAlmostEqual(ev_score(_result(monthly=many_neg)), 5.0, places=6)

    def test_differs_from_live_score(self):
        # EV ignores Sharpe; a high-Sharpe/low-return config scores differently.
        r = _result(sharpe=12.0, total_return=0.04)
        self.assertNotAlmostEqual(ev_score(r), live_score(r), places=3)


if __name__ == "__main__":
    unittest.main()
