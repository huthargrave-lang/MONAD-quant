"""H19's "#1 unsolved problem" describes a gate that does not run.

H19 records regime lag as the primary unsolved active-engine problem: the 252-MA **slope**
stays positive through a −20–30% intra-bull correction, so the regime reads STRONG_BULL
and the engine buys RSI dips into a falling knife. CLAUDE.md §4 calls the 6-state slope
classifier "the core innovation" and §12 called it "the entire foundation".

**Verified from source: it gates nothing.** `runner.py` calls `generate_trades()` with
`require_signals`, `target_gain_pct`, `stop_loss_pct` and `trade_hours` — and never passes
`use_slope_regime` or `longs_only`, both of which default to `False`. Every remaining
regime reference in `generate_trades` is gated on `use_slope_regime and longs_only`, so
none of it fires. F26 said this; it is still true.

**What DOES gate entries is a different indicator, and it is undocumented as such.**
`use_regime_filter` defaults to **True** and `runner.py` never overrides it, so every
backtest runs:

    long_entry &= (vol_regime == 1) & (trend_direction == 1)

where `trend_direction` is `close > SMA(200)` — a **level** test — and `vol_regime` is
Bollinger width **above** its rolling median. Two things follow, and both contradict the
project's own documentation:

* CLAUDE.md §3 says `vol_regime` is *"currently disabled (USE_REGIME_FILTER=False) — too
  blunt, blocks good entries"*. It is not disabled; `config.USE_REGIME_FILTER` has no
  reader on this path, and the engine default wins. Entries are restricted to the
  **more volatile** half of bars.
* The active trend gate is a level test, not a slope test — so **H19's lag mechanism
  cannot fire through it.** On a synthetic −25% intra-bull correction the level test
  starts blocking longs 59 bars in and blocks 80% of the drop, while the 252-MA slope
  stays positive for 227 bars and would permit longs through 76% of it. Same correction,
  3.8× the lag, and the laggy one is the one that is disconnected.

So H19 is **retired as stated**: it is a real design risk *for an engine that would exist
if the slope gate were restored*, not a live defect. Its own body already says "MOOT while
the active engine stays retired (D6)"; this file establishes the stronger claim that it
would be moot even if the engine were running, because the mechanism is unwired.

The synthetic series is a shape demonstration of two indicator definitions. It is not a
market claim and no performance conclusion is drawn from it.
"""
import inspect
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.backtest import runner as runner_mod  # noqa: E402
from src.strategy.engine import generate_trades  # noqa: E402
from src.signals.volatility import trend_direction  # noqa: E402


def correction_series(n=1200, drop_at=900, drop=0.29):
    """A long bull run followed by a deep intra-bull correction."""
    x = np.concatenate([np.linspace(0, 0.9, drop_at),
                        np.linspace(0.9, 0.9 - drop, n - drop_at)])
    return pd.DataFrame({"close": 100 * np.exp(x)})


class TheSlopeRegimeIsNotWiredTests(unittest.TestCase):
    """H19's subject."""

    def test_generate_trades_defaults_the_slope_flags_off(self):
        params = inspect.signature(generate_trades).parameters
        self.assertFalse(params["use_slope_regime"].default)
        self.assertFalse(params["longs_only"].default)

    def test_the_runner_never_passes_them(self):
        source = inspect.getsource(runner_mod.run_backtest)
        call = source[source.index("generate_trades("):]
        call = call[:call.index(")\n") + 1]
        for flag in ("use_slope_regime", "longs_only"):
            self.assertNotIn(
                flag, call,
                "runner.py now passes {} to generate_trades — the slope regime may be "
                "live again, which would make H19 a real problem rather than a "
                "hypothetical one. Re-open it.".format(flag))

    def test_every_slope_regime_branch_is_behind_the_dead_flag(self):
        source = inspect.getsource(generate_trades)
        for marker in ("use_slope_regime and longs_only",):
            self.assertIn(
                marker, source,
                "the slope-regime branches are no longer guarded by the flag pair — "
                "re-check what runs")


class TheGateThatACTUALLYRunsTests(unittest.TestCase):
    """And the two places the docs disagree with it."""

    def test_use_regime_filter_defaults_ON_and_the_runner_does_not_override(self):
        self.assertTrue(inspect.signature(generate_trades)
                        .parameters["use_regime_filter"].default)
        source = inspect.getsource(runner_mod.run_backtest)
        call = source[source.index("generate_trades("):]
        call = call[:call.index(")\n") + 1]
        self.assertNotIn(
            "use_regime_filter", call,
            "runner.py now sets use_regime_filter explicitly — good; check whether it "
            "matches config.USE_REGIME_FILTER and update this file")

    def test_the_config_flag_the_docs_cite_has_no_effect_here(self):
        import config
        self.assertFalse(
            getattr(config, "USE_REGIME_FILTER", True),
            "config.USE_REGIME_FILTER is no longer False, so the doc/code contradiction "
            "documented here has changed shape")

    def test_the_active_filter_is_vol_regime_AND_trend_direction(self):
        source = inspect.getsource(generate_trades)
        self.assertIn('(df["vol_regime"] == 1) & (df["trend_direction"] == 1)', source,
                      "the active entry gate changed — re-derive what runs")

    def test_trend_direction_is_a_LEVEL_test_not_a_slope_test(self):
        source = inspect.getsource(trend_direction)
        self.assertIn("rolling(period).mean()", source)
        self.assertIn('df["close"] > sma', source)
        self.assertNotIn("shift", source,
                         "trend_direction now looks at a change over time — if it "
                         "became a slope test, H19's lag mechanism could fire through "
                         "the ACTIVE gate and H19 must be re-opened")


class TheLevelTestDoesNotHaveH19sLagTests(unittest.TestCase):
    """The quantitative half. Two indicator definitions, one correction."""

    @classmethod
    def setUpClass(cls):
        cls.df = correction_series()
        cls.level = trend_direction(cls.df, 200)
        sma = cls.df["close"].rolling(200).mean()
        cls.slope = (sma - sma.shift(252)) / sma.shift(252)
        cls.window = slice(900, 1200)

    def test_the_level_test_blocks_most_of_the_correction(self):
        allowed = (self.level[self.window] == 1).mean()
        self.assertLess(
            allowed, 0.35,
            "the level gate now permits longs through {:.0%} of a -25% correction — it "
            "has acquired the lag H19 describes".format(allowed))

    def test_the_SLOPE_test_stays_bullish_through_most_of_it(self):
        allowed = (self.slope[self.window] > 0).mean()
        self.assertGreater(
            allowed, 0.6,
            "the 252-MA slope no longer stays positive through the correction, so H19's "
            "premise would not hold even for the unwired gate")

    def test_the_slope_lags_the_level_by_several_times(self):
        first_block = next(i for i in range(900, 1200) if self.level.iloc[i] != 1)
        first_neg = next(i for i in range(900, 1200) if self.slope.iloc[i] <= 0)
        self.assertGreater(
            (first_neg - 900) / (first_block - 900), 2.5,
            "the slope test no longer lags the level test by a wide margin ({} vs {} "
            "bars) — the distinction this finding rests on has narrowed".format(
                first_neg - 900, first_block - 900))

    def test_the_fixture_really_contains_a_deep_correction(self):
        """Non-vacuity: without an actual drawdown neither test means anything."""
        peak = self.df["close"].iloc[:900].max()
        trough = self.df["close"].iloc[900:].min()
        self.assertLess(trough / peak, 0.8, "the synthetic correction is not deep enough")


if __name__ == "__main__":
    unittest.main()
