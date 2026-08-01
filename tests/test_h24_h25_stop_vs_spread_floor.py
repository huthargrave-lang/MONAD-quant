"""H24/H25 answered without a sweep: whether a stop is "inside the spread" is arithmetic.

H24 worries that SOXL/LABU/TNA's tight stops "may collapse like GDXU", whose optimistic
0.075% stop sat inside the bid-ask spread (Sharpe 96.5 → 1.8 realistic). H25 asks for a
GDXU realistic re-sweep. Both prescribe running `sweep.py`, which needs market data — and
Yahoo is network-blocked here, so neither can be *executed*. Both can be *answered*.

**The sweep already contains the safety model.** `sweep.py` derives a per-instrument cost
from `estimate_spread(median_price, broker)` and injects it as `slippage_pct`, overriding
the backtest mode's flat 2 bps. It also computes a floor:

    auto_min_stop_pct = max(0.15, (5 * est_spread / median_price) * 100)

— "safe stop = 5× spread", with a hard 0.15% minimum whose stated reason is that tighter
stops "create same-bar ambiguity on hourly bars (both stop and target fit inside one bar's
range, making the result random)". That is precisely F174's mechanism: at a high ambiguous
share, `worst_case_ambiguity` chooses the result.

**So the question reduces to a minimum price per mode.** Solving `stop% ≥ floor%` against
the repo's own spread tiers:

    mode           stop     needs price ≥ (ibkr)   needs price ≥ (retail)
    TQQQ_HOURLY    0.50%          $10.0                  $30.0
    SOXL_HOURLY    0.45%          $11.2                  $33.4
    GDXU_HOURLY    0.46%          $10.9                  $32.7
    LABU_HOURLY    0.25%          $20.0                  $80.0
    TNA_HOURLY     0.15%          $33.4                 $133.4

**H24's concern is confirmed for two of the three, and quantified.** TNA's stop equals the
hard 0.15% floor exactly — a parameter sitting on its own safety boundary means the
unconstrained optimum was *below* it and the constraint bound. At retail spreads TNA would
need to trade above $133 for its stop to clear the 5×-spread floor; at IBKR spreads, above
$33.4. LABU needs $80 retail / $20 IBKR. SOXL clears comfortably and belongs with TQQQ and
GDXU, not with TNA and LABU.

The live path trades through IBKR, so the IBKR column is the operative one — which turns
a vague worry into a checkable precondition: **TNA is only sweep-safe above ~$33.4.**

**H25 appears already done.** GDXU's configured stop is 0.46%, annotated "realistic sweep",
not the 0.075% H25 complains about — and 0.075% is *half* the hard 0.15% floor, so it could
only have come from `--min-stop 0` or from before the floor existed.

Prices are the one thing not available offline. This file asserts the thresholds, not the
verdict; the verdict needs one median price per instrument.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from src.optimization.sweep_costs import (  # noqa: E402
    BROKER_SPREADS, estimate_spread, round_trip_cost_pct,
)

MODES = ("TQQQ_HOURLY", "SOXL_HOURLY", "LABU_HOURLY", "TNA_HOURLY", "GDXU_HOURLY")
HARD_FLOOR_PCT = 0.15


def stop_pct(mode):
    return config.ASSETS[mode]["stop_loss_pct"] * 100


def floor_pct(price, broker):
    return max(HARD_FLOOR_PCT, (5 * estimate_spread(price, broker) / price) * 100)


def min_safe_price(mode, broker):
    """Lowest price at which the configured stop clears the 5x-spread floor."""
    stop = stop_pct(mode)
    for tenths in range(50, 3000):
        price = tenths / 10
        if stop >= floor_pct(price, broker):
            return price
    return None


class TheSweepAlreadyModelsTheSpreadTests(unittest.TestCase):
    """H24/H25 prescribe a sweep; the sweep's own guard is the answer."""

    def test_the_safe_stop_floor_exists_and_is_five_times_the_spread(self):
        source = (ROOT / "sweep.py").read_text(encoding="utf-8")
        self.assertIn("auto_min_stop_pct = max(0.15, (5 * est_spread / median_price) * 100)",
                      source,
                      "sweep.py's safe-stop floor changed — the thresholds below are "
                      "derived from it")

    def test_the_floors_reason_is_the_same_bar_ambiguity_F174_quantified(self):
        source = (ROOT / "sweep.py").read_text(encoding="utf-8")
        self.assertIn("same-bar ambiguity", source,
                      "the floor lost its stated reason; it is the link to F174")

    def test_the_sweep_overrides_the_flat_mode_slippage(self):
        """Otherwise 'realistic mode' would charge a flat 2bps regardless of instrument."""
        source = (ROOT / "sweep.py").read_text(encoding="utf-8")
        self.assertIn("slippage_pct=SLIPPAGE_PCT", source)
        self.assertIn("SLIPPAGE_PCT = round_trip_cost_pct(est_spread, median_price)",
                      source)

    def test_a_flat_realistic_mode_alone_would_not_answer_H24(self):
        """The mode default is instrument-blind and far smaller than any of these stops."""
        from src.backtest.runner import BACKTEST_MODES
        flat = BACKTEST_MODES["realistic"]["slippage_pct"] * 100
        for mode in MODES:
            self.assertGreater(
                stop_pct(mode) / flat, 5.0,
                "{}'s stop is now within 5x the flat realistic slippage, so running "
                "realistic mode alone might actually probe it".format(mode))


class TheAnswerIsAMinimumPricePerModeTests(unittest.TestCase):
    def test_every_mode_has_a_computable_threshold(self):
        for mode in MODES:
            for broker in ("ibkr", "retail"):
                self.assertIsNotNone(min_safe_price(mode, broker),
                                     "{}/{} has no safe price".format(mode, broker))

    def test_tna_needs_the_highest_price_by_a_wide_margin(self):
        """H24 named LABU 0.25% and TNA 0.15% as the risks. TNA is the extreme."""
        thresholds = {m: min_safe_price(m, "retail") for m in MODES}
        self.assertEqual(max(thresholds, key=thresholds.get), "TNA_HOURLY")
        others = [v for m, v in thresholds.items() if m != "TNA_HOURLY"]
        self.assertGreater(
            thresholds["TNA_HOURLY"] / max(others), 1.5,
            "TNA's required price is no longer well above every other mode's — the "
            "ranking H24 depends on has changed")

    def test_tna_sits_exactly_on_the_hard_floor(self):
        """A parameter on its own safety boundary means the constraint bound."""
        self.assertAlmostEqual(stop_pct("TNA_HOURLY"), HARD_FLOOR_PCT, places=6,
                               msg="TNA's stop moved off the hard floor — re-read "
                                   "whether the sweep constraint still binds")

    def test_soxl_belongs_with_the_safe_modes_not_with_tna(self):
        """H24 groups SOXL with LABU and TNA; the arithmetic separates it."""
        for broker in ("ibkr", "retail"):
            self.assertLess(
                min_safe_price("SOXL_HOURLY", broker),
                min_safe_price("LABU_HOURLY", broker),
                "SOXL no longer clears its floor more easily than LABU on {}".format(
                    broker))

    def test_ibkr_thresholds_are_lower_than_retail(self):
        """The live path trades through IBKR, so the tier matters to the verdict."""
        for mode in MODES:
            self.assertLessEqual(min_safe_price(mode, "ibkr"),
                                 min_safe_price(mode, "retail"))
        self.assertLess(BROKER_SPREADS["ibkr"]["<50"], BROKER_SPREADS["retail"]["<50"])


class H25LooksAlreadyDoneTests(unittest.TestCase):
    def test_gdxus_configured_stop_is_the_realistic_one_not_the_optimistic_one(self):
        self.assertAlmostEqual(config.STOP_LOSS_PCT_GDXU_HOURLY, 0.0046, places=6)
        self.assertGreater(
            stop_pct("GDXU_HOURLY"), HARD_FLOOR_PCT,
            "GDXU's stop fell to or below the hard floor again")

    def test_the_config_annotates_it_as_a_realistic_sweep_result(self):
        source = (ROOT / "config.py").read_text(encoding="utf-8")
        line = next(l for l in source.splitlines()
                    if l.startswith("STOP_LOSS_PCT_GDXU_HOURLY"))
        self.assertIn("realistic", line.lower(),
                      "GDXU's stop is no longer annotated as a realistic-sweep result — "
                      "H25 may be open again")

    def test_the_optimistic_value_H25_complains_about_is_below_the_hard_floor(self):
        """Which is why it could not be produced by a sweep with the floor in place."""
        self.assertLess(0.075, HARD_FLOOR_PCT)


class WhatIsNotAnsweredHereTests(unittest.TestCase):
    """The honest boundary: no price data, so no verdict — only thresholds."""

    def test_no_price_series_is_available_in_this_checkout(self):
        cache = ROOT / "data" / "cache"
        self.assertEqual(
            list(cache.glob("*")) if cache.exists() else [], [],
            "price data appeared — compute each instrument's median price and turn "
            "the thresholds in this file into an actual verdict")

    def test_the_round_trip_cost_helper_is_the_one_the_sweep_uses(self):
        self.assertAlmostEqual(round_trip_cost_pct(0.03, 30.0), 0.001, places=9)


if __name__ == "__main__":
    unittest.main()
