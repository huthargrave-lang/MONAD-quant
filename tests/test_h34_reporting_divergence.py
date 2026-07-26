"""H34 understates it: seven views of one 65-trade run give SIX different answers.

H34 records "dashboard (compounded, 62 PROD trades) != alert path (simple-sum, 65 all
trades)" and proposes extracting one shared `src/analysis/performance.py`. That file still
does not exist (it is a roadmap proposal in `IMPROVEMENT_PLAN.md`), and the divergence is
not a two-way mismatch. Computed on the committed 65-trade archive:

    view                                                          value      n
    live/state.py get_trade_summary   simple sum, ALL           +31.086%    65
    ops/archive   alert_simple_sum    simple sum, ALL           +31.086%    65
    ops/archive   dashboard_compounded compounded, PROD, notional +35.203%  62
    ctx perf      ALL notional        compounded, ALL           +35.411%    65
    ctx perf      ALL account         compounded, ALL, x10%      +3.149%    65
    ops/analyze_run CONFIRMED         compounded, ACTUAL, notional +0.205%  47
    ctx perf      CONFIRMED account   compounded, ACTUAL, x10%   +0.045%    47

**Six distinct values, three trade populations (47 / 62 / 65), two unit conventions.**
The spread is 35.37 percentage points.

Comparing like with like, which is the honest way to state the gap:

* notional, compounded: ALL `+35.411%` vs CONFIRMED `+0.205%` — a factor of ~173.
* account, compounded: ALL `+3.149%` vs CONFIRMED `+0.045%` — a factor of ~70.

(Quoting `+35.411%` against `+0.045%` would be a ~787× headline that crosses both the
population *and* the unit boundary at once. It is the same arithmetic error the repo
already recorded as F160, so it is not repeated here.)

**What actually reaches a human is the inflated end.** `ops/archive_and_start_new_run.py`
writes `dashboard_compounded_pct` into each archived run headline — `+35.203%`. And
`live/state.py::get_trade_summary` returns `total_ret` as a **simple sum over every
trade**, which is what `alerts.alert_exit` puts in Slack — `+31.086%`. The honest
confirmed-fill account figure, `+0.045%`, appears in exactly one place: `ctx perf`.

**Nothing here is fixed.** The consolidation H34 asks for touches `live/state.py` (fenced)
and the archive/dashboard writers, and picking the one true population is precisely the
decision F202/F203 showed cannot be made correctly until fills carry provenance. This
measures the divergence so the argument for H28's column has a number attached.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ctx  # noqa: E402

ARCHIVE = (ROOT / "data" / "live_runs" / "archive_2026-06-18_pre_clean_run"
           / "trades.jsonl")
PROD = {"target_hit", "stop_hit", "time_exit", "bracket_exit", "pending_close"}
ACTUAL = {"bracket_exit", "stop_hit"}
FRACTION = 0.10


def trades():
    return [json.loads(l) for l in ARCHIVE.read_text(encoding="utf-8").splitlines()
            if l.strip()]


def compound(returns, fraction=1.0):
    equity = 1.0
    for r in returns:
        equity *= (1 + r * fraction)
    return (equity - 1) * 100


def select(rows, kinds):
    return [t["return_pct"] for t in rows if t["exit_type"] in kinds]


def all_views(rows):
    every = [t["return_pct"] for t in rows]
    return {
        "state_simple_sum_all": sum(every) * 100,
        "archive_dashboard_compounded_prod": compound(select(rows, PROD)),
        "archive_alert_simple_sum_all": sum(every) * 100,
        "analyze_run_confirmed_notional": compound(select(rows, ACTUAL)),
        "ctx_confirmed_account": compound(select(rows, ACTUAL), FRACTION),
        "ctx_all_account": compound(every, FRACTION),
        "ctx_all_notional": compound(every),
    }


class TheViewsDivergeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = trades()
        cls.views = all_views(cls.rows)

    def test_the_archive_still_has_the_expected_shape(self):
        self.assertEqual(len(self.rows), 65)
        self.assertEqual(len(select(self.rows, PROD)), 62)
        self.assertEqual(len(select(self.rows, ACTUAL)), 47)

    def test_three_different_trade_populations_are_in_use(self):
        sizes = {len(self.rows), len(select(self.rows, PROD)),
                 len(select(self.rows, ACTUAL))}
        self.assertEqual(
            sizes, {47, 62, 65},
            "the set of trade populations changed — H34's divergence has a different "
            "shape; re-measure before citing it")

    def test_seven_views_give_six_distinct_answers(self):
        distinct = {round(v, 3) for v in self.views.values()}
        self.assertEqual(len(self.views), 7)
        self.assertEqual(
            len(distinct), 6,
            "the number of distinct reported values changed from 6 — either a "
            "consolidation landed (good) or a new view appeared: {}".format(
                sorted(distinct)))

    def test_the_spread_is_over_thirty_points(self):
        spread = max(self.views.values()) - min(self.views.values())
        self.assertGreater(
            spread, 30.0,
            "the spread across reporting views fell below 30pp ({:.2f}) — if a "
            "consolidation landed, update this file".format(spread))

    def test_the_two_simple_sum_paths_at_least_agree_with_each_other(self):
        """Non-vacuity: not every pair diverges, so the divergence is specific."""
        self.assertAlmostEqual(self.views["state_simple_sum_all"],
                               self.views["archive_alert_simple_sum_all"], places=9)


class LikeForLikeGapsTests(unittest.TestCase):
    """Stated within one unit convention, to avoid F160's cross-boundary error."""

    @classmethod
    def setUpClass(cls):
        cls.views = all_views(trades())

    def test_notional_all_vs_confirmed_is_about_170x(self):
        ratio = (self.views["ctx_all_notional"]
                 / self.views["analyze_run_confirmed_notional"])
        self.assertGreater(ratio, 100, "the notional ALL/CONFIRMED ratio fell below 100")
        self.assertLess(ratio, 300)

    def test_account_all_vs_confirmed_is_about_70x(self):
        ratio = self.views["ctx_all_account"] / self.views["ctx_confirmed_account"]
        self.assertGreater(ratio, 40, "the account ALL/CONFIRMED ratio fell below 40")
        self.assertLess(ratio, 120)

    def test_the_units_differ_by_the_position_fraction(self):
        """Which is why quoting across both boundaries at once is the F160 error."""
        self.assertAlmostEqual(
            self.views["ctx_confirmed_account"],
            compound(select(trades(), ACTUAL), FRACTION), places=9)
        self.assertGreater(self.views["ctx_all_notional"],
                           self.views["ctx_all_account"])


class TheInflatedEndIsWhatReachesAHumanTests(unittest.TestCase):
    def test_the_archive_headline_uses_the_compounded_prod_number(self):
        source = (ROOT / "ops" / "archive_and_start_new_run.py").read_text(
            encoding="utf-8")
        self.assertIn('"dashboard_compounded_pct": round(_compounded(prodr), 4)', source,
                      "the archived run headline changed — re-check which number is "
                      "written into the durable record")

    def test_the_slack_path_uses_a_simple_sum_over_every_trade(self):
        state = (ROOT / "live" / "state.py").read_text(encoding="utf-8")
        idx = state.index("def get_trade_summary")
        body = state[idx:state.index("\ndef ", idx + 5)]
        self.assertIn("total_ret = sum(returns)", body,
                      "get_trade_summary no longer simple-sums — the alert path may "
                      "have been corrected")
        self.assertNotIn("exit_type in", body,
                         "get_trade_summary now filters by exit type — it used to "
                         "include every trade")

    def test_only_ctx_perf_reports_the_confirmed_account_figure(self):
        import inspect
        self.assertIn("THE HONEST EDGE", inspect.getsource(ctx.cmd_perf))
        for other in (ROOT / "ops" / "archive_and_start_new_run.py",
                      ROOT / "live" / "state.py"):
            self.assertNotIn(
                "LIVE_POSITION_FRACTION", other.read_text(encoding="utf-8"),
                "{} now reports in account units — the divergence may be closing"
                .format(other.name))


class TheSharedModuleH34AsksForDoesNotExistTests(unittest.TestCase):
    def test_there_is_no_src_analysis_performance(self):
        self.assertFalse(
            (ROOT / "src" / "analysis" / "performance.py").exists(),
            "src/analysis/performance.py now exists — H34's consolidation may have "
            "landed; re-measure the divergence and retire this file")

    def test_it_is_still_only_a_roadmap_proposal(self):
        plan = (ROOT / "IMPROVEMENT_PLAN.md").read_text(encoding="utf-8")
        self.assertIn("src/analysis/performance.py", plan,
                      "the roadmap no longer proposes the shared module, so H34 has "
                      "no recorded plan behind it")

    def test_choosing_the_population_needs_the_provenance_column_first(self):
        """Why this is recorded rather than fixed: F202/F203."""
        self.assertEqual(set(ctx.CONFIRMED), ACTUAL)
        rows = trades()
        self.assertGreater(
            len(select(rows, {"target_hit"})), 0,
            "no target_hit trades remain — the population question would be simpler")


if __name__ == "__main__":
    unittest.main()
