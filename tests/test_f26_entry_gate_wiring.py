"""F26's figures reproduce, and the same probe shows F194's fact 2 is wrong.

Study: `docs/research/F26_entry_gate_wiring.md`. Probe: `tools/entry_gate_probe.py`.

Three claims, guarded bidirectionally — each fails if the claim stops being true, with a
message telling the maintainer to supersede the web node rather than edit the test.

1. **The slope flags cannot reach `entry_signal`** (F26 claim c). Not "did not on the
   panels tried": every read of `use_slope_regime`/`longs_only` inside `generate_trades`
   sits after the last write to `entry_signal`, and every statement they guard assigns to
   `regime_kelly_mult`. The empirical 4-combo hash equality is kept as a check on that
   source reading, not as the evidence for it.

2. **`use_regime_filter` runs at its undeclared default and that is large.** 4.0%–20.9% of
   the configured entries survive, across 8 panels. F140 measured 12.5% on one; the spread
   is why it should be cited as a range.

3. **The soft 50-MA gate's `else` branch is unreachable** — and this corrects
   `tests/test_h21_soft_50ma_gate_timeframe.py` and F194, both mine.
   `add_momentum_features` writes `regime` unconditionally, so `build_features` output
   always has it, on hourly too. F194 said "there is no `regime` column on the hourly path,
   so the code takes the else-branch" and derived a ~28%-of-bars / 42%-of-dip-bars block
   rate from it. The branch actually taken is STRONG_BULL-conditional and blocks 1.9%–9.0%
   of candidates at F194's own volatility — an overstatement of 2.7×–7.9×.

   The old guard asserted the *source text* of both branches and the fraction of bars
   below the MA. Both were true; neither touched reachability, so it passed while the
   claim it defended was false. Distance-below-the-MA is an upper bound on the block rate
   and I cited the bound as the rate. This guard runs a real frame through
   `build_features` and asserts **which branch fires**.

Panels are seeded synthetic — no market data is reachable here. That is adequate for
reachability (a property of the code) and is why every magnitude is asserted as a loose
range over several generated regimes.
"""
import ast
import inspect
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import config  # noqa: E402
import entry_gate_probe as probe  # noqa: E402
from src.signals import momentum as momentum_mod  # noqa: E402
from src.strategy import engine as engine_mod  # noqa: E402
from src.strategy.engine import build_features, generate_trades  # noqa: E402

COMMON = dict(require_signals=1, target_gain_pct=0.01, stop_loss_pct=0.006)


def written_columns(target):
    """The column names an assignment target actually writes.

    `df["x"] = …` and `df.loc[mask, "x"] = …` write `x`; a `mask` that mentions other
    columns reads them, it does not write them.
    """
    if not isinstance(target, ast.Subscript):
        return set()
    key = target.slice
    if isinstance(key, ast.Tuple):
        key = key.elts[-1] if key.elts else None
    return {key.value} if isinstance(key, ast.Constant) and isinstance(
        key.value, str) else set()


def hourly_frame(seed=17, drift=0.00008, bars=1500, sigma=0.006):
    return build_features(
        probe.synth_panel(seed, drift, bars, "1h", sigma), timeframe="hourly")


class TheSlopeFlagsCannotReachEntriesTests(unittest.TestCase):
    """F26 claim (c), as a property of the source rather than of a sample."""

    @classmethod
    def setUpClass(cls):
        cls.report = probe.structural_report()

    def test_every_slope_flag_read_is_after_the_last_entry_signal_write(self):
        self.assertTrue(
            self.report["all_slope_reads_after_last_entry_write"],
            "a slope flag is now read at line {} while entry_signal is still written at "
            "line {} — the flags may have become live. Re-run "
            "tools/entry_gate_probe.py and supersede F26.".format(
                self.report["first_slope_flag_read"],
                self.report["last_entry_signal_write"]))

    def test_the_flags_are_actually_present_so_the_check_is_not_vacuous(self):
        self.assertTrue(self.report["slope_flag_read_lines"],
                        "neither slope flag is read at all — the guard has nothing to "
                        "assert about; F26 needs restating, not this test relaxing")
        self.assertTrue(self.report["entry_signal_write_lines"])

    def test_the_blocks_they_guard_write_only_the_kelly_column(self):
        kelly = self.report["regime_kelly_mult_write_lines"]
        first_read = self.report["first_slope_flag_read"]
        self.assertTrue(any(line > first_read for line in kelly),
                        "the slope-guarded region no longer writes regime_kelly_mult — "
                        "what does it write now?")

    def test_runner_does_not_pass_them(self):
        keywords = probe.runner_call_report()["keywords"]
        for flag in ("use_slope_regime", "longs_only"):
            self.assertNotIn(
                flag, keywords,
                "runner.py now passes {} to generate_trades — F26's claim (b) is "
                "resolved; supersede it and re-baseline every backtest number".format(
                    flag))

    def test_all_four_combinations_give_one_entry_vector(self):
        """The empirical confirmation of the structural claim above."""
        feat = hourly_frame()
        hashes = set()
        for slope, longs in probe.FLAG_MATRIX:
            out = generate_trades(feat, use_slope_regime=slope, longs_only=longs,
                                  **COMMON)
            hashes.add(probe.entry_hash(out))
        self.assertEqual(
            len(hashes), 1,
            "the four slope-flag combinations now produce {} distinct entry vectors — "
            "the source read above must be wrong, or the flags were wired in".format(
                len(hashes)))

    def test_the_frame_has_entries_at_all(self):
        """Non-vacuity: all-zero entry vectors would be identical for a trivial reason."""
        out = generate_trades(hourly_frame(), **COMMON)
        self.assertGreater(int((out["entry_signal"] != 0).sum()), 50,
                           "the synthetic panel stopped producing entries — the "
                           "equality above would be vacuous")

    def test_the_flags_do_move_the_column_nobody_reads(self):
        """They are live code, not no-ops — which is the point of F145."""
        feat = hourly_frame()
        seen = set()
        for slope, longs in probe.FLAG_MATRIX:
            out = generate_trades(feat, use_slope_regime=slope, longs_only=longs,
                                  **COMMON)
            seen.add(tuple(out["regime_kelly_mult"].round(6)))
        self.assertGreater(
            len(seen), 1,
            "the slope flags no longer change regime_kelly_mult either — they are now "
            "fully inert, which is a different (simpler) finding than F26 records")


class TheGateThatDoesRunIsLargeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rates = []
        for name, seed, drift in probe.PANELS:
            feat = build_features(probe.synth_panel(seed, drift, 1500, "1h"),
                                  timeframe="hourly")
            on = int((generate_trades(feat, use_regime_filter=True,
                                      **COMMON)["entry_signal"] != 0).sum())
            off = int((generate_trades(feat, use_regime_filter=False,
                                       **COMMON)["entry_signal"] != 0).sum())
            cls.rates.append((name, on / off if off else 1.0))

    def test_the_runner_still_takes_the_signature_default(self):
        sig = inspect.signature(generate_trades)
        self.assertIs(
            sig.parameters["use_regime_filter"].default, True,
            "the signature default flipped — the divergence F26/H27 describe is gone; "
            "supersede them and re-baseline every backtest number")
        self.assertNotIn(
            "use_regime_filter", probe.runner_call_report()["keywords"],
            "runner.py now passes use_regime_filter — H27 is FIXED. Supersede it, and "
            "note every prior backtest number was produced under the other gate.")

    def test_config_still_says_the_gate_is_off(self):
        self.assertFalse(
            getattr(config, "USE_REGIME_FILTER", True),
            "config.USE_REGIME_FILTER is now True, so config and the running default "
            "agree — the contradiction F26 records has dissolved")

    def test_the_gate_suppresses_the_large_majority_of_entries(self):
        for name, retained in self.rates:
            self.assertLess(
                retained, 0.35,
                "panel {} now retains {:.1%} of configured entries — the gate has "
                "become mild and the 4.0%-20.9% range in the study is stale".format(
                    name, retained))
            self.assertGreater(
                retained, 0.0,
                "panel {} retains nothing at all — the gate now blocks every entry, "
                "which is a stronger claim than the study makes".format(name))


class TheSoftFiftyMaElseBranchIsUnreachableTests(unittest.TestCase):
    """The correction to F194 and to my own H21 guard."""

    def test_build_features_always_writes_a_regime_column(self):
        for timeframe, freq in (("hourly", "1h"), ("daily", "1D")):
            feat = build_features(probe.synth_panel(7, 0.0003, 600, freq),
                                  timeframe=timeframe)
            self.assertIn(
                "regime", feat.columns,
                "{} frames no longer carry a regime column — the else-branch became "
                "reachable and F194's fact 2 is true again for {}".format(
                    timeframe, timeframe))

    def test_the_regime_write_is_unconditional_in_the_source(self):
        """Why it is always there, so the guard survives a refactor of build_features.

        `written_columns` looks at the *subscript key*, not at the unparsed target text.
        Matching on text counted `df.loc[(df["regime"] == "BEAR") & …,
        "bear_short_signal"] = …` as a write to `regime`, because the mask mentions it —
        the same read-as-write confusion the probe's `structural_report` had.
        """
        fn = ast.parse(inspect.getsource(momentum_mod.add_momentum_features)).body[0]
        writes = [
            node for node in ast.walk(fn)
            if isinstance(node, ast.Assign)
            and any("regime" in written_columns(t) for t in node.targets)]
        self.assertEqual(
            len(writes), 1,
            "add_momentum_features no longer writes regime exactly once — check whether "
            "it became conditional, which would make the else-branch reachable")
        guarded = [n for n in ast.walk(fn) if isinstance(n, (ast.If, ast.Try))
                   and any(w in ast.walk(n) for w in writes)]
        self.assertFalse(
            guarded,
            "the regime write is now inside a conditional — the else-branch may be "
            "reachable after all; re-run tools/entry_gate_probe.py")

    def test_the_conditional_detector_would_notice_a_guarded_write(self):
        """Negative control — a detector that cannot fire is not a detector."""
        rewired = ast.parse(
            "def f(df, timeframe):\n"
            "    if timeframe == 'daily':\n"
            "        df['regime'] = classify(df)\n"
            "    return df\n").body[0]
        writes = [n for n in ast.walk(rewired) if isinstance(n, ast.Assign)
                  and any("regime" in written_columns(t) for t in n.targets)]
        self.assertEqual(len(writes), 1)
        guarded = [n for n in ast.walk(rewired) if isinstance(n, (ast.If, ast.Try))
                   and any(w in ast.walk(n) for w in writes)]
        self.assertTrue(guarded, "the conditional detector missed a guarded write")

    def test_both_branches_still_exist_in_the_source(self):
        source = inspect.getsource(engine_mod.generate_trades)
        self.assertIn('gate_mask = long_mask & (df["regime"] == "STRONG_BULL") & deep_below',
                      source, "the branch that DOES run was changed")
        self.assertIn(
            "gate_mask = long_mask & deep_below", source,
            "the unreachable else-branch was removed — good; retire this class and "
            "supersede F194's fact 2 rather than keeping a guard for dead code")

    def test_no_production_caller_can_reach_the_else_branch(self):
        """Every caller hands generate_trades a frame straight out of build_features."""
        callers = {
            "src/backtest/runner.py": "df_feat",
            "src/optimization/walk_forward.py": "df_feat",
            "live/signals.py": "df",
            "tools/overnight_gap_risk_study.py": None,
        }
        for path in callers:
            source = (ROOT / path).read_text(encoding="utf-8")
            self.assertIn(
                "build_features", source,
                "{} calls generate_trades without build_features — it could be feeding "
                "a frame with no regime column, which would reach the else-branch"
                .format(path))
            self.assertNotIn(
                'drop(columns=["regime"]', source,
                "{} now drops the regime column — the else-branch is reachable from "
                "production and F194's fact 2 needs re-examining".format(path))

    def test_the_branch_taken_blocks_far_less_than_the_branch_f194_assumed(self):
        feat = hourly_frame(seed=3, drift=0.0002, bars=6000, sigma=0.011)
        prior = config.STRONG_BULL_SOFT_50MA_PCT
        try:
            config.STRONG_BULL_SOFT_50MA_PCT = 0.0
            candidates = int((generate_trades(feat, **COMMON)["entry_signal"] == 1).sum())
        finally:
            config.STRONG_BULL_SOFT_50MA_PCT = prior
        taken = int((generate_trades(feat, **COMMON)["entry_signal"] == 1).sum())
        else_branch = int((generate_trades(feat.drop(columns=["regime"]),
                                           **COMMON)["entry_signal"] == 1).sum())
        self.assertGreater(candidates, 300, "too few candidates to measure a rate")
        blocked_taken = (candidates - taken) / candidates
        blocked_else = (candidates - else_branch) / candidates
        self.assertGreater(
            blocked_else, blocked_taken * 2,
            "the two branches now block comparably ({:.1%} vs {:.1%}) — the correction "
            "to F194 no longer has a magnitude, only a direction".format(
                blocked_taken, blocked_else))
        self.assertLess(
            blocked_taken, 0.15,
            "the running gate now blocks {:.1%} of candidates — F194's ~28%/42% figures "
            "are approaching correct for the wrong reason; re-measure".format(
                blocked_taken))
        self.assertGreater(
            blocked_taken, 0.0,
            "the running gate now blocks nothing at all — the gate is fully inert, a "
            "stronger claim than the study makes; supersede it")

    def test_the_threshold_is_still_the_one_that_was_measured(self):
        self.assertAlmostEqual(
            getattr(config, "STRONG_BULL_SOFT_50MA_PCT", 0.0), 0.02, places=6,
            msg="the soft 50-MA threshold moved — every block rate in "
                "docs/research/F26_entry_gate_wiring.md was measured at 0.02")


class TheStudyAndTheNodeStayInSyncTests(unittest.TestCase):
    def test_the_study_document_exists_and_names_its_probe(self):
        doc = (ROOT / "docs/research/F26_entry_gate_wiring.md").read_text(
            encoding="utf-8")
        self.assertIn("tools/entry_gate_probe.py", doc)
        self.assertIn("docs/research/data/f26_entry_gate_probe.json", doc)

    def test_f194_still_carries_the_claim_this_corrects(self):
        web = (ROOT / "RESEARCH_WEB.md").read_text(encoding="utf-8")
        start = web.index("### F194 ")
        body = web[start:web.index("\n### ", start + 5)]
        self.assertIn(
            "There is no `regime` column on the hourly path", body,
            "F194's fact 2 was edited or removed — if it was corrected in place, this "
            "guard and the study's §3 should be retired together")


if __name__ == "__main__":
    unittest.main()
