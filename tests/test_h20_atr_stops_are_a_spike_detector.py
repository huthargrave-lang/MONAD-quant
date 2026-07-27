"""H20's premise is wrong, and the feature that exists is not the one it wants.

H20 says *"`USE_ATR_DYNAMIC_STOPS` exists but `compute_trade_returns()` has no
implementation"*, and asks for stops and targets scaled by recent ATR so they sit outside
intraday noise (F7: for 3× ETFs the fixed stop is inside the bar's own range 94–100% of
the time).

**The premise is false.** The feature is wired end to end. `runner.py` builds a
`stop_overrides` dict from `atr_pct` and passes it to `compute_trade_returns`, which
consumes it at `engine.py:311` (`stop = stop_overrides.get(idx, stop_loss_pct)`). It is
simply **off by default** — `config.USE_ATR_DYNAMIC_STOPS = False`.

**But what is implemented is not what H20 asks for.** Three structural properties, all
exact from source:

1. It is a **spike detector, not a scaling rule**. The override applies only when
   `atr_pct > ATR_STOP_MULT × median(atr_pct, 20)`. On every other bar the stop stays at
   its configured value — so on the ordinary bars where F7's complaint actually lives,
   nothing changes.
2. It **only widens**, never narrows: `if widened_stop > stop_loss_pct`.
3. It **never touches the target**. `compute_trade_returns` accepts `target_overrides`,
   and `runner.py` never builds one.

Together (2) and (3) mean the reward:risk ratio can only get worse when the feature fires.
On synthetic ATR series the trigger fires on ~2% of bars (lognormal) to ~5% (with
volatility clustering), and when it does the stop widens from 0.50% to a median 2.1–2.5%
against an unchanged 1.00% target — **R:R 2.00 → ~0.40–0.47**, so breakeven win rate goes
from 33% to about 70%.

So enabling the flag as-is would convert the rare high-volatility trades from 2:1 into
roughly 0.4:1 while leaving the systematic problem untouched. A rule that addressed F7
would scale **both** barriers on **every** trade, not widen one on a spike.

The trigger rate and the R:R medians come from synthetic ATR distributions and are
illustrative. The three structural properties are exact.
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
from src.backtest import runner as runner_mod  # noqa: E402
from src.strategy.engine import compute_trade_returns  # noqa: E402


def atr_series(n=6000, seed=4, bursty=False):
    rng = np.random.default_rng(seed)
    base = rng.normal(-4.6, 0.35, n)
    if bursty:
        base = base + 0.9 * (rng.random(n) < 0.05)
    return pd.Series(np.exp(base))


class TheFeatureIsWiredEndToEndTests(unittest.TestCase):
    """H20's premise, checked."""

    def test_the_engine_consumes_stop_overrides(self):
        params = inspect.signature(compute_trade_returns).parameters
        self.assertIn("stop_overrides", params)
        source = inspect.getsource(compute_trade_returns)
        self.assertIn("stop_overrides.get(idx, stop_loss_pct)", source,
                      "compute_trade_returns no longer applies per-trade stop "
                      "overrides — H20's 'no implementation' claim would become true")

    def test_the_runner_builds_and_passes_them(self):
        source = inspect.getsource(runner_mod.run_backtest)
        self.assertIn("stop_overrides[idx] = widened_stop", source)
        self.assertIn("stop_overrides=stop_overrides", source)

    def test_it_is_off_by_default(self):
        self.assertFalse(
            getattr(config, "USE_ATR_DYNAMIC_STOPS", False),
            "ATR dynamic stops are now ON. Read this file first: as implemented the "
            "feature degrades R:R when it fires, because it widens the stop and never "
            "adjusts the target.")


class ItIsASpikeDetectorNotAScalingRuleTests(unittest.TestCase):
    """The three structural properties, exact from source."""

    @classmethod
    def setUpClass(cls):
        cls.source = inspect.getsource(runner_mod.run_backtest)

    def test_the_override_is_gated_on_a_relative_ATR_threshold(self):
        self.assertIn("if current_atr > atr_mult * baseline:", self.source,
                      "the ATR override is no longer threshold-gated — if it became an "
                      "unconditional scaling rule, this whole finding changes")
        self.assertGreaterEqual(getattr(config, "ATR_STOP_MULT", 2.0), 1.5,
                                "the multiplier dropped low enough that the override "
                                "stops being a spike detector")

    def test_it_only_widens_never_narrows(self):
        self.assertIn("if widened_stop > stop_loss_pct:", self.source,
                      "the override may now narrow stops too — re-derive the R:R effect")

    def test_the_target_is_never_overridden(self):
        self.assertIn("target_overrides",
                      inspect.getsource(compute_trade_returns),
                      "the engine no longer supports target overrides")
        self.assertNotIn(
            "target_overrides", self.source,
            "runner.py now builds target overrides — if both barriers scale together, "
            "the R:R degradation documented here is fixed; update H20 and this file")


class TheEffectOnRewardToRiskTests(unittest.TestCase):
    """Illustrative magnitudes on synthetic ATR. The direction is structural."""

    def _fire_rate(self, atr):
        med = atr.rolling(20, min_periods=5).median()
        mult = getattr(config, "ATR_STOP_MULT", 2.0)
        return (atr > mult * med)

    def test_the_trigger_is_rare(self):
        for bursty in (False, True):
            rate = self._fire_rate(atr_series(bursty=bursty)).mean()
            self.assertLess(
                rate, 0.15,
                "the ATR trigger now fires on {:.0%} of bars — it would be behaving as "
                "a scaling rule rather than a spike detector".format(rate))
            self.assertGreater(rate, 0.001, "the trigger never fires at all")

    def test_the_stop_stays_INSIDE_typical_noise_on_untriggered_bars(self):
        """F7's actual complaint, untouched by this feature."""
        atr = atr_series()
        quiet = atr[~self._fire_rate(atr)]
        stop = config.STOP_LOSS_PCT_TQQQ_HOURLY
        self.assertGreater(
            (quiet > stop).mean(), 0.8,
            "typical ATR no longer exceeds the configured stop on most untriggered "
            "bars — F7's premise would have changed")

    def test_reward_to_risk_COLLAPSES_when_it_fires(self):
        atr = atr_series(bursty=True)
        fired = atr[self._fire_rate(atr)]
        cap = getattr(config, "ATR_STOP_CAP_PCT", 0.04)
        widened = np.minimum(fired, cap)
        target = config.TARGET_GAIN_PCT_TQQQ_HOURLY
        base_rr = target / config.STOP_LOSS_PCT_TQQQ_HOURLY
        fired_rr = float((target / widened).median())
        self.assertGreater(base_rr, 1.5)
        self.assertLess(
            fired_rr, 1.0,
            "R:R no longer collapses below 1:1 when the override fires ({:.2f}) — the "
            "asymmetry this finding rests on has changed".format(fired_rr))
        self.assertGreater(
            base_rr / fired_rr, 2.5,
            "the R:R degradation shrank below 2.5x; re-measure before citing it")

    def test_the_breakeven_win_rate_moves_a_long_way(self):
        """Stated in the units the project already reasons in (see F179)."""
        target = config.TARGET_GAIN_PCT_TQQQ_HOURLY
        stop = config.STOP_LOSS_PCT_TQQQ_HOURLY
        base_be = stop / (target + stop)
        widened_be = 0.025 / (target + 0.025)      # a fired stop near the synthetic median
        self.assertLess(base_be, 0.35)
        self.assertGreater(
            widened_be, 0.6,
            "widening the stop to ~2.5% against an unchanged target no longer pushes "
            "breakeven above 60%")


if __name__ == "__main__":
    unittest.main()
