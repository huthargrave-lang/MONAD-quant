"""H21's soft 50-MA gate is live, gates everything, and its threshold is off by a timeframe.

H21 proposes raising `STRONG_BULL_SOFT_50MA_PCT` from 0.02 to 0.05 — "block STRONG_BULL
entries only when price is >5% below the 50-MA" — citing daily observations: bad June-2024
entries sat 7–15% below, good August-2023 ones 1–3% below.

Three things are true of the running code, and together they mean the threshold is not
measuring what H21 thinks it measures.

**It is active, on the live mode.** `STRONG_BULL_SOFT_50MA_PCT = 0.02` and
`generate_trades` applies it whenever the column exists.

**On hourly it gates ALL longs, not just STRONG_BULL.** There is no `regime` column on
the hourly path, so the code takes the else-branch and blocks every long entry deep below
the MA — the regime-awareness H21 assumes is daily-only.

**And `ma_50d` on hourly is a 50-HOUR mean.** `engine.py:50` says so in its own comment:
*"For hourly bars, 50 periods ≈ ~2.5 trading days (vs 50 days for daily)."* So a threshold
calibrated from distance-below-a-50-**day** MA is applied to distance-below-a-2.5-**day**
MA, on a 3× ETF.

**What that costs.** On a synthetic 3× hourly series (σ ≈ 1.1%/bar, TQQQ-like), 2% below
the 50-bar MA covers **28% of all bars — and 42% of dip bars**, dip bars being exactly the
mean-reversion entry candidates the strategy exists to take. CLAUDE.md §7 records that the
*strict* any-touch version was reverted for filtering 71 of 83 trades; the current setting
is far from that, but it is also nothing like the gentle filter H21 describes.

**So H21's direction is right and its reasoning does not transfer.** Raising 0.02 → 0.05
would cut the hourly block rate from ~28% to ~11%, which is probably an improvement on the
live path — but not because June-2024 dips sat 7–15% below a 50-day MA. Any recalibration
has to be done in the timeframe the gate actually runs in.

Percentages are from synthetic series with the stated volatilities; they illustrate the
scale mismatch and are not measurements of TQQQ. The three structural facts are exact.
"""
import inspect
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from src.strategy import engine as engine_mod  # noqa: E402


def below_ma(n, sigma, seed=9, window=50):
    rng = np.random.default_rng(seed)
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0002, sigma, n))))
    ma = close.rolling(window, min_periods=1).mean()
    return close, (ma - close) / close


class TheGateIsLiveAndUngatedByRegimeOnHourlyTests(unittest.TestCase):
    def test_the_threshold_is_set_and_nonzero(self):
        self.assertAlmostEqual(
            getattr(config, "STRONG_BULL_SOFT_50MA_PCT", 0.0), 0.02, places=6,
            msg="the soft 50-MA threshold moved — H21 and the measurements below are "
                "calibrated against 0.02; re-derive them")

    def test_hourly_takes_the_else_branch_and_gates_ALL_longs(self):
        source = inspect.getsource(engine_mod.generate_trades)
        self.assertIn('gate_mask = long_mask & (df["regime"] == "STRONG_BULL") & deep_below',
                      source, "the daily branch changed")
        self.assertIn("# Hourly mode: gate all long entries (no regime column)", source)
        self.assertIn("gate_mask = long_mask & deep_below", source,
                      "the hourly branch no longer gates every long — H21's "
                      "'STRONG_BULL entries only' framing may now be accurate")

    def test_the_active_mode_is_one_without_a_regime_column(self):
        self.assertTrue(
            config.ACTIVE_MODE.endswith("_HOURLY"),
            "the active mode is no longer hourly, so the else-branch analysis may not "
            "apply to it")

    def test_the_hourly_ma_is_50_BARS_and_the_code_says_so(self):
        source = inspect.getsource(engine_mod.build_features)
        self.assertIn('df["ma_50d"] = df["close"].rolling(ma_short, min_periods=1).mean()',
                      source)
        self.assertIn("For hourly bars, 50 periods ≈ ~2.5 trading days", source,
                      "the comment recording the timeframe mismatch was removed — it is "
                      "the clearest in-code evidence for this finding")
        self.assertEqual(getattr(config, "MA_SHORT_WINDOW", 50), 50)


class TheThresholdMeansSomethingDifferentPerTimeframeTests(unittest.TestCase):
    """Synthetic, and labelled as such. The point is the ratio, not the level."""

    @classmethod
    def setUpClass(cls):
        cls.hourly_close, cls.hourly_below = below_ma(12000, 0.011)
        cls.daily_close, cls.daily_below = below_ma(3000, 0.010)

    def test_two_percent_is_common_on_an_hourly_3x_series(self):
        rate = (self.hourly_below > 0.02).mean()
        self.assertGreater(
            rate, 0.15,
            "2% below a 50-bar MA is no longer a common condition on an hourly 3x "
            "series ({:.0%}) — the scale-mismatch claim weakens".format(rate))

    def test_it_is_MORE_common_among_dip_bars_the_strategy_targets(self):
        """The sharpest form: the gate conditions on the thing that defines an entry."""
        ret = self.hourly_close.pct_change()
        dip = ret < -0.011
        rate_all = (self.hourly_below > 0.02).mean()
        rate_dip = (self.hourly_below[dip] > 0.02).mean()
        self.assertGreater(dip.sum(), 500, "too few dip bars to measure")
        self.assertGreater(
            rate_dip, rate_all,
            "dip bars are no longer over-represented below the MA — the gate would no "
            "longer be selecting against the strategy's own entries")
        self.assertGreater(
            rate_dip, 0.3,
            "the gate now blocks under 30% of dip bars ({:.0%}); re-measure before "
            "citing the 42% figure".format(rate_dip))

    def test_raising_it_to_five_percent_materially_loosens_the_hourly_gate(self):
        """H21's proposal, evaluated in the timeframe the gate actually runs in."""
        at_two = (self.hourly_below > 0.02).mean()
        at_five = (self.hourly_below > 0.05).mean()
        self.assertLess(
            at_five, at_two / 2,
            "raising the threshold to 5% no longer at least halves the hourly block "
            "rate ({:.0%} -> {:.0%}) — H21's direction would need re-checking".format(
                at_two, at_five))

    def test_the_daily_series_behaves_differently_at_the_same_threshold(self):
        """Non-vacuity: if both timeframes gave the same rate there is no mismatch."""
        self.assertNotAlmostEqual(
            (self.hourly_below > 0.02).mean(), (self.daily_below > 0.02).mean(),
            places=2,
            msg="the same threshold now means the same thing on both timeframes, so "
                "there is no scale mismatch to report")


class TheStrictVersionsHistoryStillStandsTests(unittest.TestCase):
    """Context for why the threshold matters: the strict form was catastrophic."""

    def test_claude_md_still_records_the_reverted_strict_gate(self):
        text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("STRONG_BULL_REQUIRE_50MA = False", text)
        self.assertIn("filtered 71/83", text,
                      "CLAUDE.md no longer records that the strict any-touch gate "
                      "filtered 71 of 83 trades — that history is why the soft "
                      "threshold's value is load-bearing")

    def test_the_strict_flag_is_still_off(self):
        self.assertFalse(getattr(config, "STRONG_BULL_REQUIRE_50MA", False))


if __name__ == "__main__":
    unittest.main()
