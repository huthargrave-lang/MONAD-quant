"""F20's sizing bridge: the estimator's variance comes from its WINDOW, not its shape.

`context_map.json` bridges F20 to `src/strategy/sizing.py::adaptive_kelly_multiplier`
and `config.USE_ADAPTIVE_KELLY`, noting that *"a noisy CONTINUOUS half-Kelly hurt Sharpe
(0.72->0.48), but the project's coarse WR-TIERED adaptive_kelly_multiplier re-runs
~Sharpe-neutral"*. F20 itself frames the mechanism as **"the estimator SHAPE matters"**
— continuous chases the noisy win/loss ratio `b` (CV 0.77); the 4-tier step never
computes `b` (CV 0.23). The bridge had no guard.

**F20's conclusion holds. Its stated mechanism does not survive isolation.**

Re-running F20's own estimator (`tools/mr_daily_lab.py::cmd_kelly`: half-Kelly on a
**30-trade** window, capped at **1.0**) against the tiered multiplier reproduces the CV
ordering — continuous 0.88–1.79 vs tiered 0.27–0.49. But varying one factor at a time
shows what is actually driving it:

    estimator                       CV @ wr .45 / .50 / .55
    lab continuous, W=30, cap 1.0      1.79 / 1.10 / 0.88
    lab continuous, W=30, cap 0.20     1.79 / 1.06 / 0.82   <- cap barely matters
    lab continuous, W=200, cap 1.0     1.42 / 0.50 / 0.38   <- window halves it
    tiered 4-step                      0.49 / 0.37 / 0.27

Tightening the cap by 5x leaves the variance essentially unchanged. Widening the
estimation window from 30 to 200 cuts it by 47% at wr .50 and 72% at wr .55 (measured on
the same sample for both windows). The instability is in `b = avg_win/avg_loss` estimated
from few trades — a ratio whose denominator wanders — not in continuity as such.

The wr .45 column is the exception and it is kept, not tuned away: with no edge to find,
Kelly's `max(..., 0)` clamps the fraction to zero over half the time, and the CV of a
zero-inflated series is set by the zero share, which more data cannot shrink. A window
helps an estimator that has something to estimate.

**The decisive case is the project's own Kelly.** `position_fraction(kelly_mode=
"rolling")` passes its entire history to `estimate_stats_from_backtest` with no
truncation, and `runner.py:197` backs it with an **unbounded** `deque()` whose comment
reads *"rolling window for adaptive Kelly"*. So the project's continuous Kelly is an
**expanding**-window estimator, and it is *less* variable than the 4-tier step it is
supposedly the noisy alternative to — F20's ordering reverses for the estimator the repo
actually ships. Continuity is not the discriminating property; sample size is.

(The tier itself is unaffected: `recent_win_rate` slices `[-lookback:]` internally, so
the win-rate tier genuinely uses the last 20 trades. Only the continuous path expands.)

**And on the default path none of it runs.** `position_fraction` returns `fixed_pct`
before the adaptive block, and the shipped config sets `POSITION_SIZING_MODE = "fixed"`,
so `runner.py` assembles `adaptive_params` from nine config knobs and hands them to a
function that has already returned. F20 says this in passing ("bypassed on the active
fixed-sizing path"); it is asserted here so it stays true.

Every test below is offline arithmetic on synthetic trade sequences. F20's Sharpe
numbers came from 12yr of real daily data and are not reproducible here — nothing in
this file re-tests them.
"""
import ast
import inspect
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from src.backtest import runner as runner_mod  # noqa: E402
from src.strategy import sizing  # noqa: E402
from src.strategy.sizing import (  # noqa: E402
    adaptive_kelly_multiplier, position_fraction,
)

BASE = 0.10
WIN_RATES = (0.45, 0.50, 0.55)


def trades(win_rate, n=800, seed=3):
    rng = np.random.default_rng(seed)
    return np.array([abs(rng.normal(0.010, 0.008)) if rng.random() < win_rate
                     else -abs(rng.normal(0.008, 0.007)) for _ in range(n)])


def lab_kelly(tr, W=30, frac=0.5, cap=1.0):
    """F20's own continuous estimator, transcribed from tools/mr_daily_lab.py::cmd_kelly.

    Kept as a literal transcription rather than an import so that a change to the lab
    shows up as a disagreement here instead of silently redefining what F20 measured.
    """
    out = []
    for i, _ in enumerate(tr):
        hh = tr[max(0, i - W):i]
        wins, loss = hh[hh > 0], -hh[hh < 0]
        if len(wins) and len(loss):
            p = len(wins) / len(hh)
            b = wins.mean() / loss.mean()
            out.append(min(frac * max((p * b - (1 - p)) / b, 0), cap))
        else:
            out.append(0.5)
    return np.array(out)


def tiered(tr):
    return np.array([adaptive_kelly_multiplier(BASE, list(tr[:i])) for i in range(len(tr))])


def cv(x):
    x = np.asarray(x, dtype=float)
    return float(x.std() / x.mean()) if x.mean() else float("nan")


class TheTierCannotChaseTheWinLossRatioTests(unittest.TestCase):
    """The half of F20's mechanism that IS structural — and true."""

    def test_the_tier_never_computes_b(self):
        tree = ast.parse(inspect.getsource(adaptive_kelly_multiplier))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        for forbidden in ("avg_win", "avg_loss", "kelly_fraction", "half_kelly",
                          "compute_position_size", "avg_win_pct", "avg_loss_pct"):
            self.assertNotIn(
                forbidden, names,
                "adaptive_kelly_multiplier now consults {} — it is no longer the "
                "magnitude-free win-rate tier F20 describes; supersede F20 rather "
                "than editing this test".format(forbidden))

    def test_the_tier_takes_at_most_four_distinct_values(self):
        """A step function on a bounded quantity cannot blow up, whatever the data."""
        for wr in WIN_RATES:
            values = {round(v, 10) for v in tiered(trades(wr))}
            self.assertLessEqual(
                len(values), 4,
                "the win-rate tier is no longer a 4-step function (got {}) — F20's "
                "'coarse' characterisation is stale".format(sorted(values)))

    def test_the_tier_is_bounded_by_its_extreme_multipliers(self):
        for wr in WIN_RATES:
            t = tiered(trades(wr))
            self.assertGreaterEqual(t.min(), BASE * 0.2 - 1e-12)
            self.assertLessEqual(t.max(), BASE * 1.5 + 1e-12)


class F20sCVOrderingReproducesAgainstItsOwnEstimatorTests(unittest.TestCase):
    """F20's measurement stands when you use the estimator F20 used."""

    def test_the_lab_continuous_kelly_is_more_variable_than_the_tier(self):
        for wr in WIN_RATES:
            tr = trades(wr)
            self.assertGreater(
                cv(lab_kelly(tr)[30:]), cv(tiered(tr)[30:]),
                "at wr={} F20's own continuous estimator is no longer the more "
                "variable of the two — its CV comparison would be stale".format(wr))


class TheDriverIsTheWindowNotContinuityTests(unittest.TestCase):
    """One factor at a time. This is the correction to F20's stated mechanism."""

    def test_tightening_the_cap_barely_changes_the_variance(self):
        """If the cap were the driver, a 5x tightening would show up. It does not."""
        for wr in WIN_RATES:
            tr = trades(wr)
            wide = cv(lab_kelly(tr, cap=1.0)[30:])
            tight = cv(lab_kelly(tr, cap=0.20)[30:])
            self.assertLess(
                abs(wide - tight) / wide, 0.10,
                "capping now materially changes estimator variance at wr={} "
                "({:.3f} -> {:.3f}) — the cap has become a driver and this "
                "attribution needs redoing".format(wr, wide, tight))

    def test_widening_the_window_substantially_reduces_the_variance(self):
        """Measured on the same sample for both windows. The reduction is large where
        the estimator has an edge to estimate (47% at wr .50, 72% at .55) and small
        where it does not (9% at wr .45) — see the zero-pinning test below for why."""
        for wr in (0.50, 0.55):
            tr = trades(wr)
            short = cv(lab_kelly(tr, W=30)[200:])
            long_ = cv(lab_kelly(tr, W=200)[200:])
            self.assertLess(
                long_, short * 0.7,
                "widening the estimation window from 30 to 200 no longer materially "
                "reduces variance at wr={} ({:.3f} -> {:.3f}) — the window is no "
                "longer the driver, so F20's mechanism should be re-derived".format(
                    wr, short, long_))

    def test_a_LOSING_estimator_is_zero_pinned_and_no_window_helps(self):
        """The honest exception, kept visible rather than tuned away. At wr .45 Kelly's
        `max(..., 0)` clamps the fraction to zero over half the time; the CV of a
        zero-inflated series is set by the zero share, which more data cannot shrink
        because the edge genuinely is not there."""
        tr = trades(0.45)
        short, long_ = lab_kelly(tr, W=30)[200:], lab_kelly(tr, W=200)[200:]
        self.assertGreater(
            (long_ == 0).mean(), 0.4,
            "the losing case is no longer zero-pinned, so the exception documented "
            "here has a different cause; re-measure")
        self.assertGreater(
            cv(long_), cv(short) * 0.7,
            "the window now DOES rescue the zero-pinned case — the explanation above "
            "is wrong and should be rewritten")

    def test_a_LONG_window_continuous_kelly_beats_the_tier_on_stability(self):
        """The claim in its sharpest form: continuity is not what makes an estimator
        noisy. Same functional form, longer window, LOWER variance than the step."""
        beaten = 0
        for wr in WIN_RATES:
            tr = trades(wr)
            if cv(lab_kelly(tr, W=200)[200:]) < cv(tiered(tr)[200:]):
                beaten += 1
        self.assertGreater(
            beaten, 0,
            "a long-window continuous Kelly is no longer more stable than the 4-tier "
            "step at any tested win rate — 'shape matters' would be rehabilitated and "
            "this correction should be withdrawn")


class TheProjectsOwnKellyIsExpandingNotRollingTests(unittest.TestCase):
    """The decisive case, and a prose/code mismatch worth keeping visible."""

    def test_the_backtest_deque_is_unbounded(self):
        source = inspect.getsource(runner_mod.run_backtest)
        self.assertIn(
            "rolling_returns = deque()", source,
            "the sizing history deque changed — if it now has a maxlen, the project's "
            "Kelly really is windowed and this whole class should be re-derived")
        self.assertNotIn("deque(maxlen", source)

    def test_position_fraction_consumes_the_WHOLE_history(self):
        """Feed it a history whose distant past differs; a windowed estimator would
        return the same number, an expanding one would not."""
        recent = list(trades(0.50, n=60, seed=1))
        old_good = [0.05] * 300 + recent
        old_bad = [-0.05] * 300 + recent
        a = position_fraction(mode="kelly", kelly_mode="rolling", rolling_returns=old_good)
        b = position_fraction(mode="kelly", kelly_mode="rolling", rolling_returns=old_bad)
        self.assertNotAlmostEqual(
            a, b, places=6,
            msg="position_fraction now ignores trades far in the past — it has become "
                "a genuinely rolling estimator, which is what its name and the "
                "BACKTEST_MODES description have always claimed; update them and "
                "re-derive the stability comparison above")

    def test_the_win_rate_TIER_does_window_correctly(self):
        """Only the continuous path expands — the tier's [-lookback:] slice is real."""
        recent = [0.01] * 20
        self.assertEqual(
            adaptive_kelly_multiplier(BASE, [-0.05] * 300 + recent),
            adaptive_kelly_multiplier(BASE, recent),
            "the win-rate tier now consults trades older than its lookback — it is no "
            "longer the bounded-window step F20 describes")

    def test_the_shipped_description_still_calls_it_rolling(self):
        """Not a failure — a marker. If someone fixes the wording, this points them at
        the finding so the two do not drift apart again."""
        desc = runner_mod.BACKTEST_MODES["realistic"]["description"]
        self.assertIn(
            "rolling", desc.lower(),
            "the 'rolling Kelly' wording was corrected — good; check that the "
            "unbounded deque was corrected too, or the labels have merely swapped "
            "which one is wrong")


class NoneOfThisRunsOnTheDefaultPathTests(unittest.TestCase):
    """F20's parenthetical, asserted."""

    def test_fixed_mode_returns_before_the_adaptive_block(self):
        adaptive = dict(lookback=20, high_wr=0.0, high_mult=1.5, high_cap=0.30)
        got = position_fraction(mode="fixed", fixed_pct=0.10,
                                rolling_returns=[0.01] * 50, adaptive=adaptive)
        self.assertEqual(
            got, 0.10,
            "fixed-mode sizing now applies the adaptive multiplier. That silently "
            "changes live position sizes, since the shipped config is fixed mode.")

    def test_the_shipped_config_is_fixed_mode_so_the_knobs_are_inert(self):
        self.assertEqual(
            getattr(config, "POSITION_SIZING_MODE", None), "fixed",
            "the shipped sizing mode changed — the nine ADAPTIVE_KELLY_* knobs are no "
            "longer inert on the default path, so F20's 'bypassed' parenthetical and "
            "every fixed-10% backtest number need re-reading")
        self.assertTrue(
            getattr(config, "USE_ADAPTIVE_KELLY", False),
            "USE_ADAPTIVE_KELLY is now off, which removes the oddity F20 documents: a "
            "flag that is ON while governing nothing")

    def test_the_runner_still_builds_params_it_will_not_use(self):
        source = inspect.getsource(runner_mod.run_backtest)
        self.assertIn("adaptive_params = dict(", source)
        self.assertIn("adaptive=adaptive_params", source)


class TheseAreArithmeticNotMarketClaimsTests(unittest.TestCase):
    def test_the_lab_transcription_matches_the_labs_source(self):
        """The transcription is load-bearing: if cmd_kelly changes, what F20 measured
        changes, and the comparison above stops being about F20."""
        lab = (ROOT / "tools" / "mr_daily_lab.py").read_text(encoding="utf-8")
        for fragment in ("hh = tr[max(0, i - W):i]",
                         "b = wins.mean() / loss.mean()",
                         "f = min(frac * max((p * b - (1 - p)) / b, 0), 1.0)",
                         "def series(W=30, frac=0.5, fixed=None)"):
            self.assertIn(
                fragment, lab,
                "mr_daily_lab.cmd_kelly no longer contains {!r} — the estimator F20 "
                "measured has changed and lab_kelly() above must be re-transcribed"
                .format(fragment))


if __name__ == "__main__":
    unittest.main()
