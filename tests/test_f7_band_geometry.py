"""F7's bridge, guarded: the R:R search was seeded at 2:1 and could never look at it evenly.

Tool: `tools/band_geometry.py`, frozen at `docs/research/data/band_geometry.json`.

F7 — "the stop-vs-intrabar-noise ratio drives win rate" — carries a bridge in
`context_map.json` naming `config.STOP_LOSS_PCT_TQQQ_HOURLY` and
`config.STOP_LOSS_PCT_GDXU_HOURLY`, and it had **no `guarded_by`**. This is that guard.

F7's empirical half (P(bar range > stop) of 94–100% for 3x ETFs against 37% QQQ / 17%
SPY, corr(stop_frac, WR) = −0.97) needs market data, which no provider reachable from
here will serve. Its OTHER half is checkable right now: *"win/loss magnitudes and R:R are
~identical across instruments"*. Five of ten configured modes do sit at exactly 2.00:1.

**But that agreement is close to worthless as evidence, because 2:1 is where the search
starts and most of what it can see.** From `sweep.py`'s own source:

* **Phase 1a** walks a 12-point target grid with `stop = target / 2` hardcoded. Every
  point it evaluates is exactly 2:1, so 1a cannot express a preference about R:R at all
  — it picks a target *under a fixed ratio* and hands it on as the incumbent.
* **Phase 1b** then varies the stop at that one best target, on a grid fixed in
  ABSOLUTE percent (0.15–0.60). So the R:R range 1b can explore is a function of the
  target 1a chose: at a 0.3% target nothing above 2:1 is reachable; at a 2.0% target
  nothing below 3.33:1 is, and 2:1 itself is unreachable. **The freedom to search R:R
  is inversely coupled to the target** — three of twelve targets cannot reach the seed
  ratio at all.
* At four of twelve targets the incumbent's own stop is not in 1b's grid, so that
  incumbent is never re-scored against its neighbours; it survives on its 1a score.

The search is a cross, not a grid, and its centre is 2:1 by construction. This is F2's
selection-bias family one level down: there the WINNER was picked by a biased score,
here the CANDIDATES were never symmetric to begin with.

It does NOT show 2:1 is wrong. It shows the configured agreement at 2:1 is not evidence
that 2:1 was chosen over alternatives, because for most targets the alternatives on one
side were never run.

What this deliberately does not claim: F7's uniform-stop premise describes E6's
experimental setup — one stop applied across seven instruments to isolate the mechanism
— not `config.py`, which spans 12.5x and never pretended otherwise. And E6's timescale
is not stated in the web (it ran on the morning-only cache), so nothing here rests on
whether F7's figures are daily or hourly.

Guards are bidirectional. They fail if the search stops being seeded at 2:1 (a real fix
— record it and supersede), if the coupling disappears, and if the count of modes
sitting at the seed drifts either way.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import band_geometry as bg  # noqa: E402

FROZEN = ROOT / "docs" / "research" / "data" / "band_geometry.json"


class ThePhase1aSearchIsPinnedToOneRatioTests(unittest.TestCase):
    """It cannot express a preference about R:R, because it only ever evaluates one."""

    def test_the_seed_ratio_is_read_from_source_and_is_two(self):
        self.assertEqual(
            bg.seed_ratio(), 2.0,
            "sweep.py no longer hardcodes `s = t / 2` in phase 1a. If the search became "
            "symmetric in R:R that is a REAL FIX — re-run tools/band_geometry.py, and "
            "supersede the finding rather than editing this number")

    def test_the_target_grid_is_big_enough_for_the_claim_to_mean_something(self):
        targets = bg.grid(bg.PHASE_1A_GRID)
        self.assertGreaterEqual(
            len(targets), 8,
            "phase 1a's target grid shrank to {} points — 'it explores 12 targets at one "
            "ratio' stops being the right description".format(len(targets)))
        self.assertGreater(max(targets) / min(targets), 5)

    def test_every_phase_1a_point_is_the_seed_ratio(self):
        """The structural claim, stated as arithmetic rather than as prose."""
        seed = bg.seed_ratio()
        for target in bg.grid(bg.PHASE_1A_GRID):
            self.assertAlmostEqual(target / (target / seed), seed, places=9)


class ThePhase1bReachIsCoupledToTheTargetTests(unittest.TestCase):
    """An absolute stop grid means the R:R range depends on the target 1a picked."""

    @classmethod
    def setUpClass(cls):
        cls.reach = bg.sweep_reach()
        cls.seed = bg.seed_ratio()

    def test_the_smallest_target_cannot_look_above_the_seed(self):
        smallest = min(self.reach, key=lambda r: r["target_pct"])
        self.assertLessEqual(
            smallest["rr_max"], self.seed,
            "at the smallest target ({}%) phase 1b can now reach R:R {} — the low end of "
            "the coupling is gone".format(smallest["target_pct"], smallest["rr_max"]))

    def test_the_largest_target_cannot_look_at_the_seed_at_all(self):
        largest = max(self.reach, key=lambda r: r["target_pct"])
        self.assertGreater(
            largest["rr_min"], self.seed,
            "at the largest target ({}%) phase 1b can now reach down to R:R {}, which "
            "includes the seed — the high end of the coupling is gone".format(
                largest["target_pct"], largest["rr_min"]))

    def test_the_two_ends_really_are_different(self):
        """Non-vacuity: if every target had the same reach there would be no coupling."""
        smallest = min(self.reach, key=lambda r: r["target_pct"])
        largest = max(self.reach, key=lambda r: r["target_pct"])
        self.assertGreater(
            largest["rr_max"] / smallest["rr_max"], 3.0,
            "the reachable R:R ceiling barely moves across the target grid, so 'the "
            "search range is decided by the target' is not the right description")

    def test_some_targets_cannot_reach_the_seed_ratio(self):
        counts = bg.census()["counts"]
        self.assertEqual(
            counts["targets_that_cannot_reach_seed"], 3,
            "the number of 1a targets from which 2:1 is unreachable moved to {} (was 3) "
            "— the grids changed; re-measure".format(
                counts["targets_that_cannot_reach_seed"]))

    def test_some_incumbents_are_never_re_scored(self):
        counts = bg.census()["counts"]
        self.assertEqual(
            counts["targets_whose_incumbent_is_untested"], 4,
            "the number of 1a incumbents whose own stop is absent from 1b's grid moved "
            "to {} (was 4)".format(counts["targets_whose_incumbent_is_untested"]))


class TheConfiguredBandsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = bg.census()
        cls.by_mode = {b["mode"]: b for b in cls.report["bands"]}

    def test_half_the_modes_sit_exactly_at_the_seed(self):
        counts = self.report["counts"]
        self.assertEqual(
            (counts["modes_at_seed_ratio"], counts["modes"]), (5, 10),
            "modes at the seed ratio moved to {} of {} — that is the observation the "
            "search-geometry finding is about, so re-measure before citing it".format(
                counts["modes_at_seed_ratio"], counts["modes"]))

    def test_the_seed_agreement_is_not_universal(self):
        """Non-vacuity in the other direction: if every mode sat at 2:1, the config
        would tell us nothing about whether 1b ever moves off the incumbent."""
        off_seed = [b["mode"] for b in self.report["bands"]
                    if abs(b["reward_risk"] - self.report["seed_ratio"]) > 1e-6]
        self.assertGreaterEqual(
            len(off_seed), 3,
            "almost every mode is at the seed ratio now ({} off it) — phase 1b has "
            "stopped displacing its incumbent anywhere, which is a stronger finding "
            "than the one recorded".format(len(off_seed)))

    def test_gdxu_is_the_one_extreme_band(self):
        seed = self.report["seed_ratio"]
        extreme = [b["mode"] for b in self.report["bands"]
                   if b["reward_risk"] > 2 * seed]
        self.assertEqual(
            extreme, ["GDXU_HOURLY"],
            "the set of modes with a reward:risk above {}:1 changed to {} — GDXU is the "
            "mode CLAUDE.md already flags as needing a re-sweep, and it is the one band "
            "whose geometry is nothing like the rest".format(2 * seed, extreme))
        self.assertLess(
            self.by_mode["GDXU_HOURLY"]["breakeven_wr_pct"], 20.0,
            "GDXU's break-even win rate rose above 20% — its band was re-cut")

    def test_the_stops_are_not_uniform(self):
        """Context for F7, not a contradiction of it.

        F7's "same fixed ~0.7% stop" describes E6's setup — one stop across seven
        instruments, to isolate the mechanism. `config.py` never matched that and does
        not claim to. Recorded here so nobody later reads the finding as a description
        of the configuration it is bridged to.
        """
        spread = self.report["counts"]["stop_spread_x"]
        self.assertGreater(
            spread, 5.0,
            "configured stops converged to within {}x — if they were deliberately "
            "unified, F7's premise now DOES describe the config and the bridge note "
            "should say so".format(spread))
        self.assertNotIn(
            0.7, [b["stop_pct"] for b in self.report["bands"]],
            "a mode is configured at exactly the 0.7% stop F7 cites; check whether the "
            "finding is now being read as a config claim")

    def test_break_even_win_rates_follow_from_the_ratio(self):
        """The arithmetic the band geometry implies, so a wrong R:R cannot hide."""
        for band in self.report["bands"]:
            self.assertAlmostEqual(
                band["breakeven_wr_pct"], 100.0 / (1.0 + band["reward_risk"]),
                places=1)


class TheEvObjectiveBakesInTheSameRatioTests(unittest.TestCase):
    """H22 proposed an EV-per-trade objective. It was built — with 2:1 hardcoded in it.

    `sweep.py --objective ev` routes to `sweep_scoring.ev_score`, which HARD-REJECTS any
    candidate whose win rate is below `min_wr_pct`, defaulting to **34.0** and documented
    as "the 2:1 R:R breakeven (~33.3%)". No caller ever passes it.

    A break-even win rate is `100/(1+R:R)`. A fixed floor is therefore correct at exactly
    one ratio and wrong in BOTH directions elsewhere:

        R:R 1.20 -> breakeven 45.5%  ->  floor PASSES unprofitable configs
        R:R 2.80 -> breakeven 26.3%  ->  floor REJECTS profitable ones
        R:R 6.09 -> breakeven 14.1%  ->  floor REJECTS profitable ones

    6.09 is not hypothetical: it is GDXU_HOURLY's configured band. Under this objective
    its own configuration is scored -1000 for any win rate between 14.1% and 34%.

    Read with the search geometry above, the ratio 2:1 is assumed in TWO independent
    places — the phase 1a grid that proposes candidates, and the objective that scores
    them. A sweep run with `--objective ev` therefore cannot discover a good wide band:
    1a will not propose one, and if 1b stumbles on one the objective may reject it.

    NOT FIXED HERE. The one-line change is to derive the floor from the candidate's own
    R:R, but that changes which parameters every future sweep selects, which is a
    research decision rather than a cleanup.
    """

    @classmethod
    def setUpClass(cls):
        import inspect
        from src.optimization import sweep_scoring
        cls.scoring = sweep_scoring
        cls.default = inspect.signature(sweep_scoring.ev_score).parameters[
            "min_wr_pct"].default

    def test_the_floor_is_a_fixed_number(self):
        self.assertEqual(
            self.default, 34.0,
            "ev_score's min_wr_pct default moved to {} — if it became a function of the "
            "candidate's reward:risk that is the FIX; record it and supersede".format(
                self.default))

    def test_no_caller_ever_overrides_it(self):
        """A defaulted knob nobody passes is the value in force everywhere."""
        hits = []
        for area in ("src", "tools", "."):
            root = ROOT / area if area != "." else ROOT
            for path in (root.glob("*.py") if area == "." else root.rglob("*.py")):
                if path.name == "sweep_scoring.py" or "test" in path.name:
                    continue
                if "min_wr_pct" in path.read_text(encoding="utf-8"):
                    hits.append(path.name)
        self.assertEqual(
            sorted(set(hits)), [],
            "something now passes min_wr_pct ({}) — the floor is no longer a single "
            "fixed value and this finding needs re-measuring".format(sorted(set(hits))))

    def test_the_floor_matches_the_seed_ratio_and_nothing_else(self):
        seed_breakeven = 100.0 / (1.0 + bg.seed_ratio())
        self.assertAlmostEqual(
            self.default, seed_breakeven, delta=1.0,
            msg="the fixed floor {} is no longer ~the seed ratio's breakeven {:.1f}% — "
                "the coincidence tying the objective to the search grid has "
                "changed".format(self.default, seed_breakeven))

    def test_it_misjudges_the_configured_bands_in_both_directions(self):
        """Non-vacuity, and the reason this is a defect rather than a quirk."""
        rejected, passed = [], []
        for band in bg.census()["bands"]:
            be = band["breakeven_wr_pct"]
            if be < self.default - 0.5:
                rejected.append(band["mode"])      # profitable below the floor
            elif be > self.default + 0.5:
                passed.append(band["mode"])        # unprofitable above it
        self.assertTrue(
            rejected,
            "no configured band has a breakeven below the floor, so the objective "
            "cannot currently reject a profitable config — the defect is dormant")
        self.assertIn(
            "GDXU_HOURLY", rejected,
            "GDXU is no longer among the bands the EV floor would misjudge: {}".format(
                rejected))
        self.assertTrue(
            passed,
            "no configured band has a breakeven above the floor, so the objective "
            "cannot currently accept an unprofitable config — half the claim is dormant")

    def test_the_breakeven_formula_is_what_the_floor_should_be(self):
        for rr, expected in ((2.0, 33.3), (2.8, 26.3), (6.09, 14.1)):
            self.assertAlmostEqual(100.0 / (1.0 + rr), expected, delta=0.1)


class TheCensusIsFrozenAndBridgedTests(unittest.TestCase):
    def test_it_matches_the_frozen_artifact(self):
        frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
        self.assertEqual(
            frozen["counts"], bg.census()["counts"],
            "the committed band census no longer matches a fresh run — regenerate with "
            "`python3 tools/band_geometry.py --json docs/research/data/"
            "band_geometry.json`")
        self.assertEqual(frozen["subject"], "repository")

    def test_f7s_bridge_now_names_this_guard(self):
        """The backlog item this file exists to close."""
        manifest = json.loads((ROOT / "context_map.json").read_text(encoding="utf-8"))
        bridges = [b for b in manifest["graph_bridges"]["bridges"]
                   if b.get("node") == "F7"]
        self.assertTrue(bridges, "F7's bridge is gone from context_map.json")
        guarded = [g for b in bridges for g in b.get("guarded_by", [])]
        self.assertTrue(
            any("test_f7_band_geometry" in g for g in guarded),
            "F7's bridge no longer names this guard, so `research_backlog.py` will "
            "report it as unguarded again: {}".format(guarded))

    def test_the_bridge_still_names_the_constants_the_census_reads(self):
        manifest = json.loads((ROOT / "context_map.json").read_text(encoding="utf-8"))
        code = [c for b in manifest["graph_bridges"]["bridges"]
                if b.get("node") == "F7" for c in b.get("code", [])]
        self.assertIn("config.STOP_LOSS_PCT_TQQQ_HOURLY", code)
        self.assertIn("config.STOP_LOSS_PCT_GDXU_HOURLY", code)


if __name__ == "__main__":
    unittest.main()
