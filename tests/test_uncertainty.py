"""
Tests for the uncertainty bands (src/backtest/uncertainty.py).

This pins the *confidence* layer that wraps the point-estimate metrics: block
bootstrap CIs (Sharpe, total return), the Beta-Binomial win-rate posterior, and
the Monte-Carlo equity bands. The properties tested are the ones that make the
bands trustworthy:

  * determinism      — same seed -> identical band (reproducible reports)
  * point continuity — the band's point estimate equals what metrics.py reports
  * bracketing       — the observed point lies inside its own CI
  * evidence scaling — more data -> tighter interval (the whole reason to report a
                       band instead of a number)
  * no divergence    — the vectorized Monte-Carlo drawdown equals metrics.max_drawdown
"""
import unittest

import numpy as np

from src.backtest import metrics, uncertainty


def _edge_returns(n_win, n_loss, seed=1):
    """A shuffled win/loss trade stream with a small positive edge."""
    rng = np.random.default_rng(seed)
    wins = rng.normal(0.03, 0.008, size=n_win)
    losses = -rng.normal(0.015, 0.004, size=n_loss)
    r = np.concatenate([wins, losses])
    rng.shuffle(r)
    return r


class TestBand(unittest.TestCase):
    def test_width_and_degenerate(self):
        b = uncertainty.Band(1.0, 0.5, 1.5, 0.95, "x", 10)
        self.assertAlmostEqual(b.width, 1.0)
        self.assertFalse(b.degenerate)

    def test_degenerate_when_bounds_nan(self):
        b = uncertainty.Band(1.0, float("nan"), float("nan"), 0.95, "x", 3)
        self.assertTrue(b.degenerate)
        self.assertIn("n/a", str(b))


class TestBlockBootstrap(unittest.TestCase):
    def test_shape_and_determinism(self):
        x = _edge_returns(40, 40)
        a = uncertainty.block_bootstrap(x, np.mean, block=10, n_boot=500, seed=0)
        b = uncertainty.block_bootstrap(x, np.mean, block=10, n_boot=500, seed=0)
        self.assertEqual(a.shape, (500,))
        np.testing.assert_array_equal(a, b)  # same seed -> identical

    def test_different_seed_differs(self):
        x = _edge_returns(40, 40)
        a = uncertainty.block_bootstrap(x, np.mean, block=10, n_boot=500, seed=0)
        b = uncertainty.block_bootstrap(x, np.mean, block=10, n_boot=500, seed=1)
        self.assertFalse(np.array_equal(a, b))

    def test_block_capped_to_series_length(self):
        x = np.array([0.01, -0.01, 0.02])
        # block longer than the series must not raise; it is capped to len(x)
        out = uncertainty.block_bootstrap(x, np.mean, block=99, n_boot=20, seed=0)
        self.assertEqual(out.shape, (20,))


class TestSharpeBand(unittest.TestCase):
    def test_point_matches_metrics(self):
        r = _edge_returns(45, 45)
        band = uncertainty.sharpe_band(r, 16, n_boot=400, seed=0)
        self.assertAlmostEqual(band.point, metrics.annualized_sharpe(r, 16), places=12)

    def test_point_inside_interval(self):
        r = _edge_returns(45, 45)
        band = uncertainty.sharpe_band(r, 16, n_boot=600, seed=0)
        self.assertLessEqual(band.lo, band.point)
        self.assertLessEqual(band.point, band.hi)

    def test_determinism(self):
        r = _edge_returns(45, 45)
        a = uncertainty.sharpe_band(r, 16, n_boot=400, seed=3)
        b = uncertainty.sharpe_band(r, 16, n_boot=400, seed=3)
        self.assertEqual((a.lo, a.hi), (b.lo, b.hi))

    def test_too_short_is_degenerate_but_keeps_point(self):
        r = np.array([0.01, -0.02, 0.03])  # n < _MIN_BOOTSTRAP_N
        band = uncertainty.sharpe_band(r, 16, n_boot=400, seed=0)
        self.assertTrue(band.degenerate)
        self.assertAlmostEqual(band.point, metrics.annualized_sharpe(r, 16), places=12)


class TestTotalReturnBand(unittest.TestCase):
    def test_point_is_compounded_return(self):
        r = _edge_returns(40, 40)
        band = uncertainty.total_return_band(r, n_boot=400, seed=0)
        self.assertAlmostEqual(band.point, float(np.prod(1.0 + r) - 1.0), places=12)

    def test_point_inside_interval(self):
        r = _edge_returns(40, 40)
        band = uncertainty.total_return_band(r, n_boot=600, seed=0)
        self.assertLessEqual(band.lo, band.point)
        self.assertLessEqual(band.point, band.hi)


class TestWinratePosterior(unittest.TestCase):
    def test_point_is_observed_rate(self):
        band = uncertainty.winrate_posterior(30, 50)
        self.assertAlmostEqual(band.point, 0.6, places=12)

    def test_interval_within_unit_and_brackets_truth(self):
        band = uncertainty.winrate_posterior(30, 50, seed=0)
        self.assertGreaterEqual(band.lo, 0.0)
        self.assertLessEqual(band.hi, 1.0)
        self.assertLess(band.lo, 0.6)
        self.assertGreater(band.hi, 0.6)

    def test_more_evidence_tightens_band(self):
        # Same 60% win rate, 10x the trades -> the credible interval must shrink.
        small = uncertainty.winrate_posterior(6, 10, seed=0)
        large = uncertainty.winrate_posterior(300, 500, seed=0)
        self.assertLess(large.width, small.width)

    def test_zero_trades_is_degenerate(self):
        band = uncertainty.winrate_posterior(0, 0)
        self.assertTrue(band.degenerate)
        self.assertEqual(band.n, 0)

    def test_determinism(self):
        a = uncertainty.winrate_posterior(30, 50, seed=5)
        b = uncertainty.winrate_posterior(30, 50, seed=5)
        self.assertEqual((a.lo, a.hi), (b.lo, b.hi))


class TestMonteCarloEquity(unittest.TestCase):
    def test_observed_final_equity_is_exact(self):
        r = _edge_returns(40, 40)
        bands = uncertainty.montecarlo_equity(r, initial_capital=100_000.0, n_paths=500, seed=0)
        expected_final = 100_000.0 * float(np.prod(1.0 + r))
        self.assertAlmostEqual(bands.final_equity.point, expected_final, places=6)

    def test_all_winners_never_lose(self):
        # Every trade positive -> no resampled path can end below start, and the
        # max drawdown of a monotonically rising path is 0.
        r = np.full(30, 0.01)
        bands = uncertainty.montecarlo_equity(r, n_paths=300, seed=0)
        self.assertEqual(bands.prob_below_initial, 0.0)
        self.assertAlmostEqual(bands.max_drawdown.point, 0.0, places=12)
        self.assertAlmostEqual(bands.max_drawdown.hi, 0.0, places=12)

    def test_prob_below_initial_in_unit_interval(self):
        r = _edge_returns(40, 45)
        bands = uncertainty.montecarlo_equity(r, n_paths=400, seed=0)
        self.assertGreaterEqual(bands.prob_below_initial, 0.0)
        self.assertLessEqual(bands.prob_below_initial, 1.0)

    def test_empty_is_degenerate(self):
        bands = uncertainty.montecarlo_equity([], n_paths=100, seed=0)
        self.assertTrue(bands.final_equity.degenerate)
        self.assertEqual(bands.n_paths, 0)

    def test_vectorized_drawdown_matches_metrics(self):
        # The vectorized per-row drawdown must equal metrics.max_drawdown row-by-row,
        # so the two implementations cannot silently diverge.
        rng = np.random.default_rng(0)
        paths = 100_000.0 * np.cumprod(1.0 + rng.normal(0.0, 0.02, size=(7, 60)), axis=1)
        vec = uncertainty._row_max_drawdowns(paths)
        for i in range(paths.shape[0]):
            self.assertAlmostEqual(vec[i], metrics.max_drawdown(paths[i]), places=12)


class TestSummarizeAndReport(unittest.TestCase):
    def test_summary_keys_and_winrate(self):
        r = _edge_returns(41, 42)
        s = uncertainty.summarize(r, trades_per_year=16, seed=0)
        self.assertEqual(set(s), {"n_trades", "level", "sharpe", "total_return", "win_rate", "equity"})
        self.assertEqual(s["n_trades"], 83)
        # default wins = count of positive trades
        self.assertAlmostEqual(s["win_rate"].point, float((r > 0).sum()) / r.size, places=12)

    def test_format_report_is_string_with_labels(self):
        r = _edge_returns(41, 42)
        text = uncertainty.format_report(uncertainty.summarize(r, trades_per_year=16, seed=0))
        self.assertIsInstance(text, str)
        for label in ("Sharpe", "Total return", "Win rate", "Final equity", "Max drawdown"):
            self.assertIn(label, text)


if __name__ == "__main__":
    unittest.main()
