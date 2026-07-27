"""F176's source facts reproduce; four of its Sharpe figures are unverifiable, by anyone.

Study: `docs/research/F176_vol_target_provenance.md`.

F176 was flagged as quoting ten figures with no reachable document. They split in two.

**The source facts reproduce exactly.** `position_fraction` still offers only
`fixed`/`kelly`/`kelly_clamped` and never computes realized volatility; `vol_target` is
defined only under `tools/`, twice, with different caps, different warm-up handling and
only one of them able to charge financing; `mr_daily_lab` calls it exactly twice, on the
trailing-Sharpe-weighted series and on a single QQQ sleeve — never on the equal-weight
portfolio F21's headline is about.

**Two magnitudes reproduce offline**, on a seeded heteroskedastic series:

* The inter-lab discrepancy is **warm-up handling, not the leverage cap**. With both caps
  set to 2.0 the difference is unchanged to five decimals, the cap never binds, and
  prepending 60 zeros to one lab's output reproduces the other's Sharpe *exactly* — so the
  gap is entirely `fillna(0.0)` injecting zero-return bars that `perf()`'s `dropna()`
  cannot remove.
* **Constant leverage leaves Sharpe unchanged to floating point** (×1.0/1.5/2.0/3.0 all
  give the same value to 12 decimal places), so any lift is timing or cap-clipping.

**Four figures are not recoverable and this file says so.** F21's 0.66/0.42 and F20's
0.56→0.67 come from `mr_daily_lab` run against real daily prices — network-blocked here,
no panel committed — and the lab writes **no artifact**, only stdout. There is nothing to
reconcile against. The guard below pins that absence: if the lab ever gains an artifact
writer, it fails and asks for the figures to be reconciled instead of caveated.
"""
import ast
import math
import re
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import mr_daily_lab as LAB  # noqa: E402
import vol_target_study as STUDY  # noqa: E402

SIZING = (ROOT / "src" / "strategy" / "sizing.py").read_text(encoding="utf-8")
LAB_SRC = (ROOT / "tools" / "mr_daily_lab.py").read_text(encoding="utf-8")
DOC = ROOT / "docs" / "research" / "F176_vol_target_provenance.md"


def series(seed=11, n=3000):
    """Heteroskedastic by construction, so vol-targeting has something to act on."""
    rng = np.random.default_rng(seed)
    vol = np.where(np.arange(n) % 500 < 250, 0.006, 0.018)
    return pd.Series(rng.normal(0.0003, vol, n))


def sharpe(x):
    x = pd.Series(x).dropna()
    return float(x.mean() / x.std() * math.sqrt(252))


class TheSizingLayerStillCannotVolTargetTests(unittest.TestCase):
    def test_the_bridged_function_offers_three_modes_and_none_of_them_size_by_vol(self):
        tree = ast.parse(SIZING)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "position_fraction")
        modes = set(re.findall(r'mode == "(\w+)"', ast.unparse(fn)))
        self.assertTrue(modes <= {"fixed", "kelly", "kelly_clamped"},
                        "position_fraction gained a mode: {}".format(modes))
        self.assertNotIn(
            "vol_target", ast.unparse(fn),
            "position_fraction can vol-target now — F21's recommendation became "
            "implementable; supersede F176 and re-measure")

    def test_the_sizing_module_never_computes_realized_volatility(self):
        for token in ("realized_vol", "rolling(", ".std()"):
            self.assertNotIn(
                token, SIZING,
                "src/strategy/sizing.py now computes {} — check whether vol-targeting "
                "arrived without a mode".format(token))

    def test_vol_target_lives_only_in_tools(self):
        hits = sorted(p.relative_to(ROOT).as_posix()
                      for p in (ROOT / "src").rglob("*.py")
                      if "def vol_target" in p.read_text(encoding="utf-8"))
        self.assertEqual(
            hits, [],
            "vol_target is defined under src/ now ({}) — the F21 bridge may finally "
            "point at running code".format(hits))


class TheTwoLabsStillDisagreeTests(unittest.TestCase):
    def test_the_caps_differ(self):
        self.assertEqual(STUDY.MAXLEV, 2.0)
        self.assertIn("maxlev=3.0", LAB_SRC,
                      "mr_daily_lab's leverage cap moved off 3.0 — the two labs may "
                      "have been reconciled; re-measure the discrepancy")

    def test_only_one_lab_can_charge_financing(self):
        self.assertIn("financing", STUDY.vol_target.__code__.co_varnames)
        self.assertNotIn(
            "financing", LAB.vol_target.__code__.co_varnames,
            "mr_daily_lab.vol_target gained a financing parameter — the lab behind F21 "
            "can now price the cost F40 found decisive; supersede F176's point 3")

    def test_the_warm_up_handling_differs(self):
        self.assertIn("fillna(0.0)", LAB_SRC.split("def vol_target")[1][:400])
        import inspect
        self.assertIn("dropna()", inspect.getsource(STUDY.vol_target))

    def test_the_lookback_is_the_same_so_the_gap_is_not_the_window(self):
        self.assertEqual(STUDY.LB, 60)
        self.assertIn("lb=60", LAB_SRC.split("def vol_target")[1][:120])


class TheEqualWeightArmWasNeverVolTargetedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(LAB_SRC)
        cls.portfolio = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                             and n.name == "cmd_portfolio")
        cls.body = ast.unparse(cls.portfolio)

    def test_the_equal_weight_series_exists(self):
        self.assertIn("ew = R.mean(axis=1)", self.body)

    def test_vol_target_is_applied_to_the_sharpe_weighted_series_instead(self):
        calls = [ast.unparse(n) for n in ast.walk(self.portfolio)
                 if isinstance(n, ast.Call)
                 and getattr(n.func, "id", None) == "vol_target"]
        self.assertEqual(len(calls), 1, "cmd_portfolio's vol_target call count changed")
        self.assertIn("swp", calls[0])
        self.assertNotIn(
            "ew", calls[0],
            "the equal-weight portfolio is vol-targeted now — F21's recommended "
            "combination has been RUN; publish the result and supersede F176")

    def test_the_lab_calls_vol_target_exactly_twice_overall(self):
        n = len([c for c in ast.walk(ast.parse(LAB_SRC))
                 if isinstance(c, ast.Call) and getattr(c.func, "id", None) == "vol_target"])
        self.assertEqual(
            n, 2,
            "mr_daily_lab now makes {} vol_target calls (was 2: swp and a QQQ "
            "sleeve) — re-derive which arms were measured".format(n))


class TheOfflineMagnitudesReproduceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = series()
        cls.lab_out, _ = LAB.vol_target(cls.r, 0.10, maxlev=2.0)
        cls.study_out, _ = STUDY.vol_target(cls.r, 0.10)

    def test_constant_leverage_leaves_sharpe_untouched(self):
        base = sharpe(self.r)
        for k in (1.0, 1.5, 2.0, 3.0):
            self.assertAlmostEqual(
                sharpe(self.r * k), base, places=12,
                msg="constant leverage x{} changed Sharpe — the invariance F40 rests "
                    "on has broken".format(k))

    def test_the_gap_is_warm_up_not_the_cap(self):
        """Both caps at 2.0, and the cap does not bind: the gap must be elsewhere."""
        rv = self.r.rolling(60).std().shift(1) * math.sqrt(252)
        self.assertEqual(
            float(((0.10 / rv) > 2.0).mean()), 0.0,
            "the leverage cap now binds on this series — the isolation below no "
            "longer holds")
        self.assertNotAlmostEqual(
            sharpe(self.lab_out), sharpe(self.study_out), places=4,
            msg="the two labs now agree at the same cap — they were reconciled; "
                "supersede F176's warm-up point")

    def test_prepending_the_warm_up_zeros_reproduces_the_other_lab_exactly(self):
        recon = pd.concat([pd.Series([0.0] * 60), self.study_out]).reset_index(drop=True)
        self.assertAlmostEqual(
            sharpe(recon), sharpe(self.lab_out), places=9,
            msg="injecting 60 zeros no longer reproduces mr_daily_lab's result — the "
                "discrepancy has another component now")

    def test_financing_can_only_reduce_a_levered_arms_sharpe(self):
        charged, _ = STUDY.vol_target(self.r, 0.10, financing=0.02)
        self.assertLess(
            sharpe(charged), sharpe(self.study_out),
            "financing improved the levered arm — it is a one-sided cost and should "
            "not be able to")


class TheQuotedSharpesAreNotRecoverableTests(unittest.TestCase):
    """A guard on an absence: it fails when the absence is filled."""

    def test_the_lab_commits_no_artifact(self):
        self.assertNotIn(
            "json.dump", LAB_SRC,
            "mr_daily_lab now writes an artifact — F20's and F21's Sharpe figures can "
            "be RECONCILED instead of caveated. Do that and update the study.")

    def test_there_is_no_committed_panel_behind_it(self):
        data = ROOT / "docs" / "research" / "data"
        panels = [p.name for p in data.glob("*mr_daily*")] if data.exists() else []
        self.assertEqual(
            panels, [],
            "a daily-MR artifact appeared ({}) — reconcile F21's 0.66/0.42 against "
            "it".format(panels))

    def test_the_document_states_which_figures_cannot_be_checked(self):
        text = DOC.read_text(encoding="utf-8")
        for figure in ("0.66", "0.42", "0.56", "0.67"):
            self.assertIn(figure, text,
                          "the study stopped naming the unrecoverable figure {} — the "
                          "point of Part 3 is that they are named".format(figure))
        self.assertIn("not recoverable", text.lower())


if __name__ == "__main__":
    unittest.main()
