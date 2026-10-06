"""
Relative statistics for daily strategies (src/research/allocation_stats.py) and the SPA
test underneath them (significance.superior_predictive_ability): calibration under the
null, power against a real winner, the recentering that keeps losers from diluting the
test, and the refusals.
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import allocation_stats as stats  # noqa: E402
from src.research import significance as sig  # noqa: E402

CAL = pd.bdate_range("2010-01-04", periods=1500)


class StationaryBootstrap(unittest.TestCase):
    def test_indices_are_in_range_and_mostly_consecutive(self):
        rng = np.random.default_rng(0)
        idx = sig.stationary_bootstrap_indices(500, 20, 50, rng)
        self.assertEqual(idx.shape, (50, 500))
        self.assertTrue(((idx >= 0) & (idx < 500)).all())
        steps = (np.diff(idx, axis=1) % 500) == 1
        self.assertAlmostEqual(float(steps.mean()), 1 - 1 / 20, delta=0.01)


class SPA(unittest.TestCase):
    def test_null_family_rejects_at_about_the_nominal_rate(self):
        """Ten zero-mean strategies, 60 independent families: the SPA p-value is roughly
        uniform, so it falls below 0.10 in about 10% of families (allowing sampling noise)."""
        rejections = 0
        families = 60
        for f in range(families):
            rng = np.random.default_rng(1000 + f)
            d = rng.normal(0, 0.01, (400, 10))
            r = sig.superior_predictive_ability(d, mean_block=10, n_boot=400, seed=f)
            rejections += r.spa_pvalue < 0.10
        self.assertLessEqual(rejections, 13, "the test rejects far too often under the null")

    def test_a_real_winner_is_found_and_named(self):
        rng = np.random.default_rng(5)
        d = rng.normal(0, 0.01, (1500, 8))
        d[:, 3] += 0.0012                      # annualized Sharpe ~ 1.9 over the benchmark
        r = sig.superior_predictive_ability(d, mean_block=20, n_boot=1000, seed=0)
        self.assertLess(r.spa_pvalue, 0.01)
        self.assertLess(r.adjusted_pvalues[3], 0.01)
        self.assertGreater(min(p for i, p in enumerate(r.adjusted_pvalues) if i != 3), 0.2)

    def test_terrible_strategies_do_not_dilute_the_test(self):
        """Hansen's recentering: adding strategies that lose badly must not make a modest
        winner look less significant, which White's Reality Check would."""
        rng = np.random.default_rng(9)
        base = rng.normal(0, 0.01, (1500, 1)) + 0.0006
        losers = rng.normal(0, 0.01, (1500, 20)) - 0.004
        alone = sig.superior_predictive_ability(base, mean_block=20, n_boot=1000, seed=0)
        diluted = sig.superior_predictive_ability(np.hstack([base, losers]), mean_block=20,
                                                  n_boot=1000, seed=0)
        self.assertAlmostEqual(diluted.adjusted_pvalues[0], alone.adjusted_pvalues[0], delta=0.02)

    def test_more_lookalike_competitors_raise_the_bar(self):
        rng = np.random.default_rng(11)
        winner = rng.normal(0, 0.01, (1500, 1)) + 0.0007
        rivals = rng.normal(0, 0.01, (1500, 25))
        one = sig.superior_predictive_ability(np.hstack([winner, rivals[:, :1]]), mean_block=20,
                                              n_boot=1000, seed=0)
        many = sig.superior_predictive_ability(np.hstack([winner, rivals]), mean_block=20,
                                               n_boot=1000, seed=0)
        self.assertGreater(many.adjusted_pvalues[0], one.adjusted_pvalues[0])

    def test_deterministic_under_a_seed(self):
        d = np.random.default_rng(2).normal(0, 0.01, (300, 4))
        a = sig.superior_predictive_ability(d, mean_block=10, n_boot=300, seed=7)
        b = sig.superior_predictive_ability(d, mean_block=10, n_boot=300, seed=7)
        self.assertEqual(a, b)

    def test_refusals(self):
        with self.assertRaises(ValueError):
            sig.superior_predictive_ability(np.zeros((10, 2)), mean_block=5)
        with self.assertRaises(ValueError):
            sig.superior_predictive_ability(np.full((100, 2), np.nan), mean_block=5)


class DuplicatePoints(unittest.TestCase):
    def test_identical_orders_are_flagged_and_distinct_ones_are_not(self):
        from src.research.daily_strategy import Tranche
        idx = pd.bdate_range("2012-01-02", periods=3)
        a = [Tranche(open_orders=pd.DataFrame({"X": [1.0, 0.0, 1.0]}, index=idx), close_orders=pd.DataFrame())]
        b = [Tranche(open_orders=pd.DataFrame({"X": [1.0, 0.0, 1.0]}, index=idx), close_orders=pd.DataFrame())]
        c = [Tranche(open_orders=pd.DataFrame({"X": [1.0, 0.5, 1.0]}, index=idx), close_orders=pd.DataFrame())]
        self.assertEqual(stats.duplicate_points({"a": a, "b": b, "c": c}), [("a", "b")])

    def test_the_frozen_grids_have_no_duplicates_except_the_recorded_auction_pair(self):
        """The auction grid ran before this check existed and its pre=5 points equal pre=3
        (F404707); every other grid is distinct on a synthetic panel."""
        sys.path.insert(0, str(REPO / "tests"))
        from test_daily_classes import synthetic
        from src.research import daily_classes as dc
        snap = synthetic(n=900)
        for name, g in dc.GRIDS.items():
            if name == "auctions":
                continue
            with self.subTest(grid=name):
                orders = {repr(p): dc.decide(snap, p) for p in g()}
                self.assertEqual(stats.duplicate_points(orders), [])


class VolMatched(unittest.TestCase):
    def test_leverage_alone_has_zero_vol_matched_active_return(self):
        rng = np.random.default_rng(4)
        cash = pd.Series(0.0001, index=CAL)
        ref = cash + pd.Series(rng.normal(0.0004, 0.01, len(CAL)), index=CAL)
        levered = cash + 1.5 * (ref - cash)              # same Sharpe, more exposure
        self.assertGreater(stats.active_series(levered, ref).mean(), 0)
        self.assertAlmostEqual(float(stats.vol_matched_active(levered, ref, cash).mean()), 0.0, places=12)


class ActiveStatistics(unittest.TestCase):
    def test_active_series_refuses_misaligned_windows(self):
        a = pd.Series(0.0, index=CAL[:100])
        b = pd.Series(0.0, index=CAL[1:101])
        with self.assertRaises(ValueError):
            stats.active_series(a, b)

    def test_beta_alone_does_not_deflate_well_on_the_active_series(self):
        """A strategy that is just the reference plus noise has an active Sharpe near 0, so
        its active DSR is low, however high its raw Sharpe (the H404700 failure mode)."""
        rng = np.random.default_rng(3)
        ref = pd.Series(rng.normal(0.0004, 0.008, len(CAL)), index=CAL)
        fam = {f"s{i}": stats.active_series(ref + rng.normal(0, 0.002, len(CAL)), ref)
               for i in range(10)}
        best = max(fam, key=lambda k: fam[k].mean())
        d = stats.deflate_active(fam, best, calendar=CAL, prior_trials=30)
        self.assertLess(d.dsr, 0.95)
        self.assertEqual(d.n_trials, d.n_effective + 30)

    def test_era_sharpes_split_on_the_declared_bounds(self):
        a = pd.Series(np.r_[np.full(500, 0.001), np.full(1000, -0.001)]
                      + np.random.default_rng(0).normal(0, 0.001, 1500), index=CAL)
        eras = stats.era_sharpes(a, [("start", str(CAL[499].date())), (str(CAL[500].date()), "end")])
        self.assertGreater(eras[0]["active_sharpe"], 0)
        self.assertLess(eras[1]["active_sharpe"], 0)
        self.assertEqual([e["sessions"] for e in eras], [500, 1000])


if __name__ == "__main__":
    unittest.main()
