"""H22's "~50% of bars" has a mechanism: every hourly mode's RSI filter is neutralised.

H22 observes that the entry signal fires on roughly half of all bars and asks for entry
quality — require both signals, a deeper RSI, an EV-per-trade objective. The frequency
claim is correct, and the cause is more specific than "the threshold is loose".

**Every hourly ETF mode has `oversold` set ABOVE `overbought`.**

    mode            oversold   overbought
    TQQQ_HOURLY        80          62      <- the live mode
    GDXU_HOURLY        85          62
    QQQ_HOURLY         70          62
    BTC_DAILY          38          62      <- the only correctly ordered pair

`momentum_signal` fires long on `(rsi < oversold) & (hist > hist.shift(1))`. With
`oversold = 80`, the RSI term is true on **94.9%** of bars on a synthetic hourly series
(98.0% at GDXU's 85). The long signal therefore reduces to *"the MACD histogram ticked
up"*, which fires about half the time by construction — measured **46.2%**, which is
H22's "~50%".

For contrast, the daily mode's correctly-ordered 38 gives `rsi < 38` on 23.3% of bars and
a long signal on **6.6%** — seven times more selective.

**The zones also overlap.** With oversold 80 above overbought 62, RSI sits in *both* named
zones on **24.6%** of bars. No contradictory signal is produced — `hist` rising and
falling are mutually exclusive, so the tie is always broken — but that is the point: the
RSI term contributes nothing, and the labels "oversold"/"overbought" no longer describe
what they select.

**This looks like an optimizer outcome, not a typo.** CLAUDE.md records GDXU's 85 as
"RSI saturated; 85 optimal" — a sweep result. A sweep free to raise `oversold` will keep
raising it while the constraint hurts, until it stops binding at all. The feature was not
tuned; it was switched off from the outside, and nothing in the repo flags the inversion.

So H22's "deeper RSI" is not a refinement of a working filter — it would be **restoring
one that is currently inert on every hourly mode, including the one that trades**.

Percentages are from a synthetic hourly series (σ ≈ 1.1%/bar) run through the repo's own
`compute_rsi`/`compute_macd`. The threshold orderings are exact config values.
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from src.signals.momentum import compute_macd, compute_rsi  # noqa: E402

HOURLY_MODES = ("TQQQ_HOURLY", "GDXU_HOURLY", "QQQ_HOURLY")


def thresholds(mode):
    return (getattr(config, "RSI_OVERSOLD_{}".format(mode)),
            getattr(config, "RSI_OVERBOUGHT_{}".format(mode)))


def synthetic(n=12000, sigma=0.011, seed=12):
    rng = np.random.default_rng(seed)
    return pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0002, sigma, n))))


class TheThresholdsAreInvertedTests(unittest.TestCase):
    def test_every_hourly_mode_has_oversold_above_overbought(self):
        for mode in HOURLY_MODES:
            oversold, overbought = thresholds(mode)
            self.assertGreater(
                oversold, overbought,
                "{} no longer has oversold above overbought ({} vs {}) — the inversion "
                "documented here was fixed. Re-measure the entry rate and update H22 "
                "rather than editing this test.".format(mode, oversold, overbought))

    def test_the_daily_mode_is_ordered_correctly(self):
        """Non-vacuity: if every mode were inverted this would be a convention, not a
        defect."""
        self.assertLess(
            config.RSI_OVERSOLD, config.RSI_OVERBOUGHT,
            "the daily mode is now inverted too — the contrast this finding rests on "
            "is gone")

    def test_the_live_mode_is_one_of_the_inverted_ones(self):
        self.assertIn(config.ACTIVE_MODE, HOURLY_MODES,
                      "the active mode is no longer one of the inverted hourly modes")


class TheRSITermIsInertTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.close = synthetic()
        cls.rsi = compute_rsi(cls.close)
        _macd, _sig, hist = compute_macd(cls.close)
        cls.turn_up = hist > hist.shift(1)

    def _long_rate(self, oversold):
        return float(((self.rsi < oversold) & self.turn_up).mean())

    def test_the_live_oversold_threshold_binds_almost_never(self):
        oversold, _ = thresholds(config.ACTIVE_MODE)
        rate = float((self.rsi < oversold).mean())
        self.assertGreater(
            rate, 0.9,
            "`rsi < {}` now excludes more than 10% of bars ({:.1%}) — the RSI term has "
            "regained some selectivity".format(oversold, rate))

    def test_the_long_signal_fires_on_about_half_the_bars(self):
        """H22's observation, reproduced."""
        oversold, _ = thresholds(config.ACTIVE_MODE)
        rate = self._long_rate(oversold)
        self.assertGreater(rate, 0.35)
        self.assertLess(rate, 0.6,
                        "the long signal rate moved outside the ~50% H22 reports")

    def test_it_is_SEVEN_TIMES_less_selective_than_the_daily_setting(self):
        """The comparison that shows the filter is switched off, not merely loose."""
        live_rate = self._long_rate(thresholds(config.ACTIVE_MODE)[0])
        daily_rate = self._long_rate(config.RSI_OVERSOLD)
        self.assertGreater(
            live_rate / daily_rate, 4.0,
            "the live threshold is now within 4x the daily one's selectivity "
            "({:.1%} vs {:.1%}) — the 'inert' characterisation weakens".format(
                live_rate, daily_rate))

    def test_the_signal_is_effectively_the_MACD_TICK_ALONE(self):
        """With the RSI term inert, what remains is one boolean."""
        oversold, _ = thresholds(config.ACTIVE_MODE)
        with_rsi = self._long_rate(oversold)
        macd_only = float(self.turn_up.mean())
        self.assertLess(
            abs(with_rsi - macd_only) / macd_only, 0.15,
            "the RSI term now changes the long rate by more than 15% ({:.1%} vs a bare "
            "{:.1%}) — it is contributing again".format(with_rsi, macd_only))

    def test_the_two_zones_OVERLAP(self):
        oversold, overbought = thresholds(config.ACTIVE_MODE)
        overlap = float(((self.rsi < oversold) & (self.rsi > overbought)).mean())
        self.assertGreater(
            overlap, 0.15,
            "RSI now sits in both named zones on under 15% of bars ({:.1%}) — the "
            "labels are becoming meaningful again".format(overlap))

    def test_no_bar_produces_BOTH_signals_despite_the_overlap(self):
        """The overlap is a naming failure, not a correctness bug — hist rising and
        falling are mutually exclusive, so the tie is always broken."""
        _m, _s, hist = compute_macd(self.close)
        oversold, overbought = thresholds(config.ACTIVE_MODE)
        long_cond = (self.rsi < oversold) & (hist > hist.shift(1))
        short_cond = (self.rsi > overbought) & (hist < hist.shift(1))
        self.assertEqual(int((long_cond & short_cond).sum()), 0,
                         "a bar now satisfies both entry conditions — the overlap has "
                         "become a correctness problem, not just a naming one")


class ItLooksLikeAnOptimizerOutcomeTests(unittest.TestCase):
    def test_the_repo_records_the_saturated_threshold_as_a_sweep_RESULT(self):
        import json
        claims = json.loads((ROOT / "context_map.json").read_text(
            encoding="utf-8"))["param_claims"]["claims"]
        gdxu = next(c for c in claims if c["key"] == "gdxu_hourly_rsi_oversold")
        self.assertEqual(gdxu["value"], 85)
        self.assertIn(
            "saturated", gdxu["note"].lower(),
            "the manifest no longer records GDXU's RSI as saturated — that note is the "
            "evidence this was an optimizer outcome rather than a typo")

    def test_the_bound_claim_still_matches_config(self):
        self.assertEqual(config.RSI_OVERSOLD_GDXU_HOURLY, 85)


if __name__ == "__main__":
    unittest.main()
