"""
Unit tests for the PURE decision core of the strategy promotion funnel
(``src/optimization/funnel.py``).

Everything here is pure arithmetic over pre-computed metrics — no backtests, no
network, no config, no filesystem. That is the whole point of keeping the decision
logic separate from ``tools/strategy_funnel.py``: the gates that actually decide
PASS / SHADOW / REJECT can be exhaustively tested without running the engine.
"""
import json
import math
import unittest

from src.optimization import funnel as F


def passing_metrics(**overrides) -> F.CandidateMetrics:
    """A CandidateMetrics that clears every default gate. Tests mutate one field
    at a time to drive a single gate to failure and assert the resulting verdict."""
    base = dict(
        total_trades=100,
        trades_per_window=[10, 12, 8, 9],
        oos_sharpe=1.2, oos_total_return=0.05, oos_max_drawdown=-0.03, oos_win_rate=0.55,
        realistic_sharpe=1.0, realistic_total_return=0.06,
        harsh_sharpe=0.5, harsh_total_return=0.03,
        cost_stress_return={1: 0.05, 2: 0.04, 3: 0.03},
        cost_stress_sharpe={1: 1.0, 2: 0.8, 3: 0.6},
        stability={
            "target_gain_pct": {"center": 1.0, "neighbors": [0.9, 0.8, 1.1, 1.0]},
            "rsi_oversold": {"center": 1.0, "neighbors": [0.7, 0.8, 0.9, 1.0]},
        },
        benchmark_metric="calmar",
        benchmark_score=1.0, strategy_benchmark_score=2.0,
        benchmark_total_return=0.04, strategy_return_vs_benchmark=0.06,
        benchmark_max_drawdown=-0.20, strategy_maxdd_vs_benchmark=-0.03,
        uncertainty_sharpe_point=1.2, uncertainty_sharpe_lo=0.3,
        uncertainty_sharpe_hi=2.1, prob_below_initial=0.2,
    )
    base.update(overrides)
    return F.CandidateMetrics(**base)


class TestIsNum(unittest.TestCase):
    def test_rejects_non_numbers(self):
        for bad in (None, float("nan"), float("inf"), -float("inf"), True, False, "1"):
            self.assertFalse(F._is_num(bad), bad)

    def test_accepts_real_numbers(self):
        for good in (0, 1, -1, 0.5, -3.2, 1e9):
            self.assertTrue(F._is_num(good), good)


class TestClassifyCostStress(unittest.TestCase):
    def test_robust(self):
        self.assertEqual(F.classify_cost_stress({1: 0.05, 2: 0.04, 3: 0.03}), "robust")

    def test_fragile_flips_by_3x(self):
        self.assertEqual(F.classify_cost_stress({1: 0.05, 2: 0.01, 3: -0.02}), "fragile")

    def test_dead_negative_at_1x(self):
        self.assertEqual(F.classify_cost_stress({1: -0.01, 2: -0.02, 3: -0.03}), "dead")

    def test_unknown_when_empty(self):
        self.assertEqual(F.classify_cost_stress(None), "unknown")
        self.assertEqual(F.classify_cost_stress({}), "unknown")

    def test_min_return_threshold(self):
        # 0.005 at 3x fails a 1% floor -> fragile, but passes a 0% floor -> robust.
        curve = {1: 0.05, 2: 0.02, 3: 0.005}
        self.assertEqual(F.classify_cost_stress(curve, min_return=0.01), "fragile")
        self.assertEqual(F.classify_cost_stress(curve, min_return=0.0), "robust")


class TestClassifyStability(unittest.TestCase):
    def test_plateau_broad(self):
        # all 4 neighbours retain >= 50% of centre and positive -> plateau
        self.assertEqual(F.classify_stability(1.0, [0.9, 0.8, 1.1, 1.0]), "plateau")

    def test_magic_single_lucky_param(self):
        # neighbours collapse (<=34% retain) -> magic
        self.assertEqual(F.classify_stability(1.0, [0.0, -0.2, 0.1, 0.05]), "magic")

    def test_dead_when_centre_nonpositive(self):
        self.assertEqual(F.classify_stability(-0.5, [1.0, 1.0]), "dead")
        self.assertEqual(F.classify_stability(0.0, [1.0, 1.0]), "dead")

    def test_ridge_in_between(self):
        # exactly half retain (2 of 4) -> between magic(<=.34) and plateau(>=.6)
        self.assertEqual(F.classify_stability(1.0, [0.9, 0.8, 0.1, 0.0]), "ridge")

    def test_unknown_no_neighbors(self):
        self.assertEqual(F.classify_stability(1.0, []), "unknown")
        self.assertEqual(F.classify_stability(1.0, None), "unknown")


class TestMinTradeGates(unittest.TestCase):
    def test_min_trades_pass_and_fail(self):
        self.assertTrue(F.gate_min_trades(50, min_total=30).passed)
        self.assertTrue(F.gate_min_trades(30, min_total=30).passed)   # boundary inclusive
        self.assertFalse(F.gate_min_trades(29, min_total=30).passed)

    def test_min_trades_none_fails(self):
        g = F.gate_min_trades(None, min_total=30)
        self.assertFalse(g.passed)
        self.assertEqual(g.severity, F.HARD)

    def test_trades_per_window_uses_worst(self):
        self.assertTrue(F.gate_trades_per_window([6, 7, 8], min_per_window=5).passed)
        self.assertFalse(F.gate_trades_per_window([6, 2, 8], min_per_window=5).passed)

    def test_trades_per_window_empty_fails(self):
        self.assertFalse(F.gate_trades_per_window([], min_per_window=5).passed)
        self.assertFalse(F.gate_trades_per_window(None, min_per_window=5).passed)


class TestWalkforwardGate(unittest.TestCase):
    def test_pass_requires_sharpe_and_positive_return(self):
        self.assertTrue(F.gate_walkforward(0.8, 0.02, min_sharpe=0.5).passed)

    def test_fail_negative_return_even_if_sharpe_ok(self):
        self.assertFalse(F.gate_walkforward(0.8, -0.01, min_sharpe=0.5).passed)

    def test_fail_low_sharpe(self):
        self.assertFalse(F.gate_walkforward(0.3, 0.05, min_sharpe=0.5).passed)

    def test_none_fails(self):
        self.assertFalse(F.gate_walkforward(None, 0.05, min_sharpe=0.5).passed)
        self.assertFalse(F.gate_walkforward(0.8, None, min_sharpe=0.5).passed)


class TestCostStressGate(unittest.TestCase):
    def test_robust_passes(self):
        self.assertTrue(F.gate_cost_stress({1: 0.05, 2: 0.04, 3: 0.03}, min_return=0.0).passed)

    def test_fragile_fails(self):
        self.assertFalse(F.gate_cost_stress({1: 0.05, 2: 0.01, 3: -0.01}, min_return=0.0).passed)

    def test_severity_is_soft(self):
        self.assertEqual(F.gate_cost_stress({1: 0.05}, min_return=0.0).severity, F.SOFT)


class TestStabilityGate(unittest.TestCase):
    def test_all_plateau_passes(self):
        stab = {"a": {"center": 1.0, "neighbors": [0.9, 0.8, 1.1, 1.0]}}
        self.assertTrue(F.gate_stability(stab, retain_frac=0.5, plateau_frac=0.6,
                                         magic_frac=0.34).passed)

    def test_any_magic_fails(self):
        stab = {
            "a": {"center": 1.0, "neighbors": [0.9, 0.8, 1.1, 1.0]},
            "b": {"center": 1.0, "neighbors": [0.0, -0.1, 0.05, 0.0]},  # magic
        }
        g = F.gate_stability(stab, retain_frac=0.5, plateau_frac=0.6, magic_frac=0.34)
        self.assertFalse(g.passed)
        self.assertIn("b=magic", g.detail)

    def test_not_computed_fails_soft(self):
        g = F.gate_stability(None, retain_frac=0.5, plateau_frac=0.6, magic_frac=0.34)
        self.assertFalse(g.passed)
        self.assertEqual(g.severity, F.SOFT)


class TestBenchmarkGate(unittest.TestCase):
    def test_beats_benchmark_passes(self):
        self.assertTrue(F.gate_benchmark(2.0, 1.0, margin=0.0).passed)

    def test_loses_to_benchmark_fails(self):
        self.assertFalse(F.gate_benchmark(0.5, 1.0, margin=0.0).passed)

    def test_margin_enforced(self):
        self.assertFalse(F.gate_benchmark(1.05, 1.0, margin=0.1).passed)
        self.assertTrue(F.gate_benchmark(1.2, 1.0, margin=0.1).passed)

    def test_none_fails_hard(self):
        g = F.gate_benchmark(None, 1.0, margin=0.0)
        self.assertFalse(g.passed)
        self.assertEqual(g.severity, F.HARD)


class TestUncertaintyGate(unittest.TestCase):
    def test_lower_band_positive_and_low_loss_prob_passes(self):
        self.assertTrue(F.gate_uncertainty(0.3, 0.2, min_sharpe_lo=0.0,
                                           max_prob_below=0.5).passed)

    def test_negative_lower_band_fails(self):
        self.assertFalse(F.gate_uncertainty(-0.1, 0.2, min_sharpe_lo=0.0,
                                            max_prob_below=0.5).passed)

    def test_high_loss_probability_fails(self):
        self.assertFalse(F.gate_uncertainty(0.3, 0.6, min_sharpe_lo=0.0,
                                            max_prob_below=0.5).passed)

    def test_none_fails(self):
        self.assertFalse(F.gate_uncertainty(None, 0.2, min_sharpe_lo=0.0,
                                            max_prob_below=0.5).passed)


class TestDecide(unittest.TestCase):
    def _g(self, name, passed, severity):
        return F.GateResult(name, passed, severity, None, None, "")

    def test_all_pass_is_pass(self):
        gates = [self._g("a", True, F.HARD), self._g("b", True, F.SOFT)]
        self.assertEqual(F.decide(gates).verdict, F.PASS)

    def test_soft_fail_is_shadow(self):
        gates = [self._g("a", True, F.HARD), self._g("b", False, F.SOFT)]
        self.assertEqual(F.decide(gates).verdict, F.SHADOW)

    def test_hard_fail_is_reject(self):
        gates = [self._g("a", False, F.HARD), self._g("b", False, F.SOFT)]
        self.assertEqual(F.decide(gates).verdict, F.REJECT)

    def test_hard_fail_dominates_soft(self):
        # a hard failure outranks any number of soft failures
        gates = [self._g("a", False, F.HARD), self._g("b", True, F.SOFT)]
        v = F.decide(gates)
        self.assertEqual(v.verdict, F.REJECT)
        self.assertTrue(any("a" in r for r in v.reasons))


class TestEvaluateCandidate(unittest.TestCase):
    def test_clean_candidate_passes(self):
        v = F.evaluate_candidate(passing_metrics())
        self.assertEqual(v.verdict, F.PASS, v.reasons)
        self.assertEqual(len(v.gates), 9)

    def test_too_few_trades_rejects(self):
        v = F.evaluate_candidate(passing_metrics(total_trades=5))
        self.assertEqual(v.verdict, F.REJECT)

    def test_negative_oos_rejects(self):
        v = F.evaluate_candidate(passing_metrics(oos_sharpe=-0.5, oos_total_return=-0.02))
        self.assertEqual(v.verdict, F.REJECT)

    def test_loses_to_benchmark_rejects(self):
        v = F.evaluate_candidate(passing_metrics(strategy_benchmark_score=0.5))
        self.assertEqual(v.verdict, F.REJECT)

    def test_uncertainty_band_straddling_zero_rejects(self):
        v = F.evaluate_candidate(passing_metrics(uncertainty_sharpe_lo=-0.4))
        self.assertEqual(v.verdict, F.REJECT)

    def test_harsh_cost_failure_is_shadow_only(self):
        # hard gates all pass; harsh (soft) fails -> SHADOW, not REJECT
        v = F.evaluate_candidate(passing_metrics(harsh_sharpe=-0.3))
        self.assertEqual(v.verdict, F.SHADOW)

    def test_fragile_cost_stress_is_shadow(self):
        v = F.evaluate_candidate(
            passing_metrics(cost_stress_return={1: 0.05, 2: 0.01, 3: -0.02}))
        self.assertEqual(v.verdict, F.SHADOW)

    def test_magic_parameter_is_shadow(self):
        v = F.evaluate_candidate(passing_metrics(stability={
            "rsi": {"center": 1.0, "neighbors": [0.0, -0.1, 0.05, 0.0]}}))
        self.assertEqual(v.verdict, F.SHADOW)

    def test_empty_metrics_rejects(self):
        # the skeptical default: no evidence at all -> REJECT
        v = F.evaluate_candidate(F.CandidateMetrics())
        self.assertEqual(v.verdict, F.REJECT)


class TestSurvivorCard(unittest.TestCase):
    def _card(self, metrics=None, verdict=None):
        m = metrics or passing_metrics()
        v = verdict or F.evaluate_candidate(m)
        return F.build_survivor_card(
            strategy_id="QQQ_TEST", ticker="QQQ",
            strategy_family="long_only_rsi_vwap_mr_hourly",
            params={"rsi_oversold": 70, "target_gain_pct": 0.01},
            train_period="2024 → 2026", oos_period="4 folds",
            cost_assumptions={"sizing": "fixed_10pct", "base_round_trip_cost_pct": 0.0001},
            metrics=m, verdict=v, generated_at="2026-06-29T00:00:00",
            extra={"trades_per_year": 120.0})

    def test_card_has_all_required_fields(self):
        card = self._card()
        for key in ("strategy_id", "ticker", "strategy_family", "params", "train_period",
                    "oos_period", "metrics", "cost_assumptions", "cost_stress",
                    "uncertainty", "parameter_stability", "benchmark", "verdict",
                    "reasons", "gates"):
            self.assertIn(key, card, key)
        # spec'd metric fields
        for key in ("total_trades", "trades_per_year", "oos_sharpe", "oos_max_drawdown",
                    "oos_total_return", "oos_win_rate"):
            self.assertIn(key, card["metrics"], key)
        self.assertEqual(card["metrics"]["trades_per_year"], 120.0)

    def test_card_json_round_trips(self):
        card = self._card()
        s = F.card_to_json(card)
        restored = json.loads(s)
        self.assertEqual(restored["verdict"], card["verdict"])
        self.assertEqual(restored["ticker"], "QQQ")
        self.assertEqual(len(restored["gates"]), 9)

    def test_card_markdown_is_str_with_verdict(self):
        card = self._card()
        md = F.card_to_markdown(card)
        self.assertIsInstance(md, str)
        self.assertIn(card["verdict"], md)
        self.assertIn("Gate trail", md)

    def test_reject_card_carries_reasons(self):
        m = passing_metrics(total_trades=2)
        card = self._card(metrics=m)
        self.assertEqual(card["verdict"], F.REJECT)
        self.assertTrue(card["reasons"])
        self.assertTrue(any("min_total_trades" in r for r in card["reasons"]))

    def test_cost_stress_class_in_card(self):
        card = self._card()
        self.assertEqual(card["cost_stress"]["class"], "robust")


if __name__ == "__main__":
    unittest.main()
