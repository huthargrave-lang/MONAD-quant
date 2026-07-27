"""F21's sizing bridge: the recommended build was never run, and the code cannot run it.

`context_map.json` bridges F21 to `src/strategy/sizing.py::position_fraction` with the
note *"vol-targeted sizing beat both fixed-Kelly and adaptive-Kelly on Sharpe;
equal-weight beat 'smart' weighting."* F21 itself recommends **"EQUAL-WEIGHT diversified
daily-MR sleeves ... + VOL-TARGETED (not Kelly) sizing → ~Sharpe 0.66"**. The bridge had
no guard. Three things are checkable from source, and all three matter.

**1. The bridged function cannot do vol-targeting.** `position_fraction`'s modes are
`fixed` / `kelly` / `kelly_clamped`. There is no vol-target branch, no config knob, and
no reference to realized volatility anywhere in `src/strategy/sizing.py`. Vol-targeting
exists only in `tools/` — twice, in two labs, with different parameters. So the bridge
points a recommendation at a function that has never implemented it: F26's pattern
(aspirational design recorded as if it were running code), in the sizing layer.

**2. The recommended COMBINATION was never run.** `mr_daily_lab.py` calls `vol_target`
exactly twice: on `swp`, the **trailing-Sharpe-weighted** portfolio (line 179), and on a
single **QQQ** sleeve (line 211). The equal-weight portfolio `ew` is never vol-targeted.
So F21's headline build composes two rows of one table that were never combined: the
0.66 belongs to equal-weight *without* vol-targeting, and the vol-target arm was applied
to the weighting scheme that **lost** (0.42). Whether equal-weight plus vol-targeting is
better than either has not been measured.

(F20's separate "vol-targeting helps, 0.56→0.67" is the line-211 single-sleeve QQQ
result — a third scope again, not the portfolio claim F21 makes.)

**3. The lab that produced F21 cannot charge financing.** `mr_daily_lab.vol_target` has
no financing parameter and caps leverage at 3.0; `tools/vol_target_study.vol_target` —
the study behind **F40** — has one and caps at 2.0. F40 found that charge decisive on a
60/40: leverage is Sharpe-invariant, so its measured +0.06 lift was timing, and a
realistic 2%/yr financing cost pushed the levered form *below* the unlevered baseline.
F21 and F40 therefore reach opposite conclusions about vol-targeting with no edge between
them in the web.

**Honest magnitudes.** The two labs also differ in warm-up handling — `mr_daily_lab`
zero-fills the first 60 bars (`lev.fillna(0.0)`, and `perf()`'s `dropna` cannot remove
injected *zeros*), while `vol_target_study` drops them. On a synthetic heteroskedastic
series that difference is worth ~0.003 Sharpe, and the leverage cap does not bind. Those
are recorded as *structural* discrepancies, not as large ones. The one exact result is
the invariance: constant leverage leaves Sharpe unchanged to floating-point.

Nothing here re-tests F21's or F40's Sharpe numbers — both rest on real daily data that
is not reachable offline.
"""
import ast
import inspect
import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.strategy import sizing  # noqa: E402

MR_LAB = ROOT / "tools" / "mr_daily_lab.py"
VT_STUDY = ROOT / "tools" / "vol_target_study.py"


def sharpe(r, ann=252):
    r = pd.Series(r).dropna()
    return float((r.mean() * ann) / (r.std() * math.sqrt(ann)))


def heteroskedastic(n=3000, seed=5):
    """A series whose volatility actually moves, so vol-targeting has something to time."""
    rng = np.random.default_rng(seed)
    vol = 0.008 * np.exp(0.5 * np.sin(np.arange(n) / 180)
                         + rng.normal(0, 0.15, n).cumsum() * 0.01)
    return pd.Series(rng.normal(0.0002, 1, n) * vol)


def _calls_to(path, func_name):
    """Every call to `func_name` in a module, with the first positional arg unparsed."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == func_name):
            out.append(ast.unparse(node.args[0]) if node.args else "")
    return out


class TheBridgedFunctionCannotVolTargetTests(unittest.TestCase):
    """Claim 1 — the recommendation points at code that does not implement it."""

    def test_position_fraction_has_only_the_three_known_modes(self):
        source = inspect.getsource(sizing.position_fraction)
        tree = ast.parse(source)
        compared = {c.value for node in ast.walk(tree)
                    if isinstance(node, ast.Compare)
                    for c in node.comparators if isinstance(c, ast.Constant)}
        self.assertEqual(
            compared & {"fixed", "kelly", "kelly_clamped", "rolling"},
            {"fixed", "kelly_clamped", "rolling"},
            "position_fraction's mode set changed — if a vol-target branch was added, "
            "F21's bridge is finally implemented and this class should be replaced by "
            "a test of the new behaviour")
        self.assertNotIn("vol_target", source)

    def test_the_sizing_module_never_computes_realized_volatility(self):
        source = (ROOT / "src" / "strategy" / "sizing.py").read_text(encoding="utf-8")
        for token in ("vol_target", "realized_vol", "rolling(", "std()"):
            self.assertNotIn(
                token, source,
                "src/strategy/sizing.py now references {!r} — vol-aware sizing may "
                "have landed in the strategy layer; re-read F21's bridge".format(token))

    def test_vol_targeting_lives_only_in_the_labs(self):
        strategy_and_live = [p for d in ("src", "live") for p in (ROOT / d).rglob("*.py")]
        offenders = [str(p.relative_to(ROOT)) for p in strategy_and_live
                     if "def vol_target" in p.read_text(encoding="utf-8")]
        self.assertEqual(
            offenders, [],
            "vol-targeting is now defined outside tools/ ({}) — the F21 gap may be "
            "closed; verify and update the bridge".format(offenders))
        self.assertIn("def vol_target", MR_LAB.read_text(encoding="utf-8"))
        self.assertIn("def vol_target", VT_STUDY.read_text(encoding="utf-8"))


class TheRecommendedCombinationWasNeverRunTests(unittest.TestCase):
    """Claim 2 — the load-bearing one. F21 composes two rows that never met."""

    def test_vol_target_is_applied_to_the_SHARPE_WEIGHTED_portfolio_not_equal_weight(self):
        targets = _calls_to(MR_LAB, "vol_target")
        self.assertEqual(
            len(targets), 2,
            "mr_daily_lab now calls vol_target {} times instead of 2 — re-read which "
            "arms are targeted before citing F21".format(len(targets)))
        self.assertIn("swp", targets,
                      "the Sharpe-weighted portfolio is no longer the vol-targeted arm")
        self.assertNotIn(
            "ew", targets,
            "the EQUAL-WEIGHT portfolio is now vol-targeted — F21's recommended build "
            "has finally been measured. Read the new number and supersede F21 rather "
            "than editing this test.")

    def test_the_other_call_site_is_a_single_sleeve_not_a_portfolio(self):
        targets = _calls_to(MR_LAB, "vol_target")
        single = [t for t in targets if "QQQ" in t]
        self.assertEqual(
            len(single), 1,
            "the single-sleeve vol-target call changed — F20's 0.56->0.67 lift is that "
            "line, and its scope claim depends on it staying single-instrument")

    def test_the_equal_weight_arm_exists_and_is_measured_unlevered(self):
        """Otherwise 'the 0.66 is the un-vol-targeted arm' has nothing to point at."""
        source = MR_LAB.read_text(encoding="utf-8")
        self.assertIn("ew = R.mean(axis=1)", source)
        self.assertIn('("equal-weight", ew)', source)


class TheTwoLabsDisagreeOnMethodTests(unittest.TestCase):
    """Claim 3 — F21's lab cannot price the cost F40 found decisive."""

    def test_the_f21_lab_has_no_financing_parameter(self):
        tree = ast.parse(MR_LAB.read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "vol_target")
        names = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.kwonlyargs}
        self.assertNotIn(
            "financing", names,
            "mr_daily_lab.vol_target can now charge financing — re-run F21's portfolio "
            "comparison with it priced and supersede the node")

    def test_the_f40_lab_does_have_one(self):
        """The asymmetry is the point; without this the comparison is vacuous."""
        tree = ast.parse(VT_STUDY.read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "vol_target")
        names = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.kwonlyargs}
        self.assertIn("financing", names)

    def test_the_leverage_caps_differ(self):
        self.assertIn("maxlev=3.0", MR_LAB.read_text(encoding="utf-8"))
        self.assertIn("MAXLEV = 2.0", VT_STUDY.read_text(encoding="utf-8"))

    def test_the_warmup_handling_differs(self):
        self.assertIn("fillna(0.0)", MR_LAB.read_text(encoding="utf-8"))
        self.assertIn("return out.dropna()", VT_STUDY.read_text(encoding="utf-8"))

    def test_the_warmup_difference_is_SMALL_and_that_is_stated(self):
        """Recorded honestly: a structural discrepancy, not a large one. If it ever
        becomes large this fails and the claim above must be strengthened."""
        r = heteroskedastic()
        rv = r.rolling(60).std().shift(1) * math.sqrt(252)
        zeroed = r * (0.10 / rv).clip(upper=3.0).fillna(0.0)
        dropped = (r * (0.10 / rv).clip(upper=3.0)).dropna()
        self.assertEqual((zeroed == 0).sum(), 60, "the warm-up length changed")
        self.assertLess(
            abs(sharpe(zeroed) - sharpe(dropped)), 0.02,
            "zero-filling the vol-target warm-up now moves Sharpe materially ({:.3f} "
            "vs {:.3f}) — this is no longer a cosmetic discrepancy and F21's arm needs "
            "recomputing".format(sharpe(zeroed), sharpe(dropped)))


class LeverageIsSharpeInvariantTests(unittest.TestCase):
    """The one exact result, and the reason a Sharpe lift must be timing, not leverage."""

    def test_constant_leverage_leaves_sharpe_unchanged(self):
        r = heteroskedastic()
        for mult in (0.5, 1.5, 3.0):
            self.assertAlmostEqual(
                sharpe(r * mult), sharpe(r), places=10,
                msg="constant leverage now changes Sharpe, which would break the "
                    "argument both F40 and mr_daily_lab's own comment rest on")

    def test_the_lab_states_the_invariance_itself(self):
        self.assertIn(
            "Sharpe-invariant", MR_LAB.read_text(encoding="utf-8"),
            "mr_daily_lab no longer states the scale-invariance it relies on")

    def test_financing_can_only_reduce_a_LEVERED_arms_sharpe(self):
        """So omitting it is a one-sided error, never a conservative one."""
        r = heteroskedastic()
        rv = r.rolling(60).std().shift(1) * math.sqrt(252)
        lev = (0.30 / rv).clip(upper=2.0)          # target chosen so leverage exceeds 1
        self.assertGreater(float(lev.mean()), 1.0, "the fixture is no longer levered")
        free = (lev * r).dropna()
        charged = (lev * r - (lev - 1).clip(lower=0) * 0.02 / 252).dropna()
        self.assertLess(
            sharpe(charged), sharpe(free),
            "charging financing no longer lowers a levered arm's Sharpe — the "
            "one-sidedness of the omission would no longer hold")


if __name__ == "__main__":
    unittest.main()
