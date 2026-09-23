"""
Tests for src/research/significance.py — the significance kernel.

The DSR is pinned to the published worked example in Bailey & López de Prado (2014),
"The Deflated Sharpe Ratio", J. Portfolio Management 40(5), section "A Numerical
Example": annualized SR 2.5, N = 100 trials, V[SR_n] = 1/2 (annualized), T = 1250
daily observations, skew -3, kurtosis 10, 250 obs/yr -> DSR 0.9004 ("only a 90%
chance"), and 0.9505 had the discovery come after N = 46 trials. A kernel that
disagrees with its own source paper is not a kernel.

PBO is checked on its defining property: on pure noise the in-sample winner is no
better than a coin flip out of sample (PBO ~ 0.5); with one configuration that truly
dominates, it is ~ 0.
"""
import ast
import math
import os
import unittest

import numpy as np
import pandas as pd

from src.research import significance as sig

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _paper(n_trials):
    ppy = 250
    return sig.deflated_sharpe(2.5 / math.sqrt(ppy), n_trials=n_trials, sharpe_variance=0.5 / ppy,
                               n_obs=1250, skew=-3.0, kurtosis=10.0)


class DeflatedSharpeMatchesThePaper(unittest.TestCase):
    def test_worked_example_n100(self):
        r = _paper(100)
        self.assertAlmostEqual(r.dsr, 0.9004, places=4)
        self.assertAlmostEqual(r.sr0, 0.1132, places=4)

    def test_worked_example_n46(self):
        self.assertAlmostEqual(_paper(46).dsr, 0.9505, places=4)

    def test_more_trials_always_deflate_more(self):
        dsrs = [_paper(n).dsr for n in (1, 2, 10, 46, 100, 1000)]
        self.assertEqual(dsrs, sorted(dsrs, reverse=True))

    def test_one_trial_is_the_psr_against_zero(self):
        r = _paper(1)
        self.assertEqual(r.sr0, 0.0)
        psr = sig.probabilistic_sharpe(2.5 / math.sqrt(250), 0.0, n_obs=1250, skew=-3, kurtosis=10)
        self.assertAlmostEqual(r.dsr, psr, places=12)

    def test_psr_is_one_half_at_the_benchmark(self):
        self.assertAlmostEqual(sig.probabilistic_sharpe(0.1, 0.1, n_obs=500, skew=0, kurtosis=3), 0.5)

    def test_impossible_moments_raise_rather_than_clamp(self):
        with self.assertRaises(ValueError):
            sig.probabilistic_sharpe(1.0, 0.0, n_obs=100, skew=10.0, kurtosis=1.0)

    def test_moments_of_a_normal_sample(self):
        x = np.random.default_rng(0).normal(0.001, 0.01, 200_000)
        m = sig.sharpe_moments(x)
        self.assertAlmostEqual(m.skew, 0.0, delta=0.03)
        self.assertAlmostEqual(m.kurtosis, 3.0, delta=0.05)
        self.assertAlmostEqual(m.sharpe, 0.1, delta=0.01)

    def test_degenerate_returns_raise(self):
        with self.assertRaises(ValueError):
            sig.sharpe_moments([0.01, 0.01, 0.01])
        with self.assertRaises(ValueError):
            sig.sharpe_moments([0.01, float("nan")])


def _trades(values, start="2024-01-02", step="1D", hour=10):
    idx = pd.date_range(start, periods=len(values), freq=step) + pd.Timedelta(hours=hour)
    return pd.Series(values, index=idx)


class EffectiveTrials(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(7)
        self.base = self.rng.normal(0, 0.01, 300)

    def test_near_identical_grid_is_one_idea(self):
        grid = {f"g{i}": _trades(self.base + self.rng.normal(0, 0.001, 300)) for i in range(9)}
        e = sig.effective_trials(grid)
        self.assertEqual(e.n_raw, 9)
        self.assertEqual(e.n_clusters, 1)
        # Li & Ji add each small eigenvalue's fractional part, so nine near-copies read
        # as ~2 independent tries: far from 9, and the conservative max keeps that ~2.
        self.assertLess(e.n_effective, 2.5)

    def test_independent_trials_stay_independent(self):
        ind = {f"i{i}": _trades(self.rng.normal(0, 0.01, 300)) for i in range(6)}
        e = sig.effective_trials(ind)
        self.assertEqual(e.n_clusters, 6)
        self.assertEqual(e.n_effective, max(6, e.n_li_ji))

    def test_byte_identical_series_collapse_before_anything_else(self):
        s = _trades(self.base)
        e = sig.effective_trials({"a": s, "b": s.copy(), "c": _trades(self.rng.normal(0, 0.01, 300))})
        self.assertEqual((e.n_raw, e.n_distinct), (3, 2))
        self.assertEqual(e.labels["a"], e.labels["b"])

    def test_empty_trials_count_once_as_found_nothing(self):
        e = sig.effective_trials({"x": _trades(self.base), "e1": pd.Series(dtype=float),
                                  "e2": pd.Series(dtype=float)})
        self.assertEqual(e.n_clusters, 2)
        self.assertEqual(e.labels["e1"], e.labels["e2"])
        self.assertIn(0.0, e.cluster_sharpes)

    def test_effective_count_is_the_conservative_max(self):
        grid = {f"g{i}": _trades(self.base + self.rng.normal(0, 0.004, 300)) for i in range(5)}
        e = sig.effective_trials(grid)
        self.assertEqual(e.n_effective, max(e.n_clusters, e.n_li_ji))

    def test_trades_on_different_days_align_on_a_common_grid(self):
        a = _trades([0.01, -0.01, 0.02], start="2024-01-02")
        b = _trades([0.02, 0.01], start="2024-01-10")
        pnl = sig.daily_pnl({"a": a, "b": b})
        self.assertEqual(pnl.loc["2024-01-10", "a"], 0.0)
        self.assertEqual(pnl.loc["2024-01-10", "b"], 0.02)

    def test_two_trades_on_one_day_sum(self):
        s = pd.Series([0.01, 0.02], index=pd.to_datetime(["2024-01-02 10:00", "2024-01-02 14:00"]))
        self.assertAlmostEqual(sig.daily_pnl({"s": s}).loc["2024-01-02", "s"], 0.03)

    def test_disjoint_windows_do_not_manufacture_correlation(self):
        """Independent trials with same-sign means and different windows must stay
        independent: zero-filling outside each window used to merge them."""
        rng = np.random.default_rng(5)
        trials = {}
        for i in range(12):
            start = pd.Timestamp("2021-01-04") + pd.Timedelta(days=30 * (i % 3))
            trials[f"t{i}"] = _trades(rng.normal(0.02, 0.01, 120), start=str(start.date()))
        self.assertEqual(sig.effective_trials(trials).n_clusters, 12)

    def test_li_ji_bounds(self):
        self.assertAlmostEqual(sig.li_ji_effective(np.eye(5)), 5.0)
        self.assertAlmostEqual(sig.li_ji_effective(np.ones((5, 5))), 1.0)


class ProbabilityOfBacktestOverfitting(unittest.TestCase):
    def test_pure_noise_is_a_coin_flip(self):
        m = np.random.default_rng(1).normal(0, 0.01, (640, 20))
        r = sig.pbo_cscv(m, n_splits=8)
        self.assertEqual(r.n_combinations, math.comb(8, 4))
        self.assertAlmostEqual(r.pbo, 0.5, delta=0.2)

    def test_a_dominant_configuration_is_not_overfit(self):
        rng = np.random.default_rng(2)
        m = rng.normal(0, 0.01, (640, 20))
        m[:, 3] += 0.01
        self.assertLess(sig.pbo_cscv(m, n_splits=8).pbo, 0.05)

    def test_bad_inputs_raise(self):
        with self.assertRaises(ValueError):
            sig.pbo_cscv(np.zeros((100, 1)))
        with self.assertRaises(ValueError):
            sig.pbo_cscv(np.zeros((100, 3)), n_splits=7)
        with self.assertRaises(ValueError):
            sig.pbo_cscv(np.zeros((10, 3)), n_splits=16)


class MultipleTesting(unittest.TestCase):
    P = [0.01, 0.04, 0.03, 0.005]

    def test_bonferroni(self):
        np.testing.assert_allclose(sig.bonferroni(self.P), [0.04, 0.16, 0.12, 0.02])

    def test_holm(self):
        np.testing.assert_allclose(sig.holm(self.P), [0.03, 0.06, 0.06, 0.02])

    def test_benjamini_hochberg(self):
        np.testing.assert_allclose(sig.benjamini_hochberg(self.P), [0.02, 0.04, 0.04, 0.02])

    def test_ordering_of_strictness(self):
        p = np.random.default_rng(3).uniform(0, 0.2, 30)
        self.assertTrue(np.all(sig.benjamini_hochberg(p) <= sig.holm(p) + 1e-15))
        self.assertTrue(np.all(sig.holm(p) <= sig.bonferroni(p) + 1e-15))

    def test_invalid_p_values_raise(self):
        for bad in ([], [1.5], [-0.1], [float("nan")]):
            with self.assertRaises(ValueError):
                sig.holm(bad)


class TheBootstrapStudiesUseTheKernel(unittest.TestCase):
    """The two studies that hand-rolled a Bonferroni band now call the kernel, and the
    kernel reproduces their old arithmetic bit-for-bit, so their verdicts cannot move."""

    def test_band_is_bit_identical_to_the_old_inline_expression(self):
        for family in (1, 3, 12, 40):
            afw = 0.05 / family / 2 * 100
            self.assertEqual(sig.familywise_percentiles(family), [afw, 100 - afw])

    def test_no_study_recomputes_the_band_inline(self):
        for rel in ("tools/tips_sleeve_study.py", "tools/correlation_regime_study.py"):
            with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
            self.assertNotIn("afw", names, f"{rel} rebuilt the family-wise band by hand")
            self.assertIn("familywise_percentiles", names, rel)


if __name__ == "__main__":
    unittest.main()
