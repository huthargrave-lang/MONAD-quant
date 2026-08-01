"""E19's reverted 5% target left a knob CLAUDE.md still advertises — and it is unreachable.

Study: `docs/research/E19_reverted_attempts_residue.md`.

E19 is the consolidated "tried and abandoned" ledger: strict 50-MA gate, 5% STRONG_BULL
target, RSI 38-42 extra entries, opposing-signal exit. Its win-rate figures need BTC daily
history and are not recoverable here (same as E18/F176). What *is* checkable is what each
reversal left behind, and the four attempts left four different kinds of residue:

* **strict 50-MA gate** — `STRONG_BULL_REQUIRE_50MA` survives as a tests-only constant,
  but a *successor* shipped: `STRONG_BULL_SOFT_50MA_PCT`, which is live and which F211
  showed is near-inert on the hourly path. Reverted-and-replaced, not simply reverted.
* **RSI 38-42 extras** — no constant at all. Removed cleanly; the model to copy.
* **opposing-signal exit** — `USE_OPPOSING_SIGNAL_EXIT` is genuinely read
  (`runner.py:145`), alongside `OPPOSING_SIGNAL_EXIT_MODES`. Off, but wired.
* **5% STRONG_BULL target** — `TARGET_GAIN_PCT_STRONG_BULL` is **unreachable**, and
  CLAUDE.md §11's config quick-reference still lists it as an active tuned parameter with
  its story attached (*"3% (not 5% — 5% killed win rate)"*).

**Why it is unreachable, and why the census first missed it.** Its suffix is a *regime*,
not a *mode*. The only dynamic dispatch in this codebase is mode-keyed —
`getattr(config, f"TARGET_GAIN_PCT_{mode}")` where mode ranges over `config.ASSETS` — so
no code path can ever build the name `TARGET_GAIN_PCT_STRONG_BULL`. F226's census matched
on the prefix alone and therefore credited it as reachable. `RSI_OVERSOLD_BEAR` (the
BEAR_DEFENSIVE_LONGS threshold) has the same shape. Validating the suffix against
`config.ASSETS` moves both into the dead set: **27 → 29**.

The bear-defensive-longs feature is the sharper case: `BEAR_DEFENSIVE_LONGS` is read only
inside a block guarded by `use_slope_regime and longs_only` — flags F26 showed no backtest
ever passes — and the threshold it would use is a constant nothing reads. A feature gated
by dead flags, parameterised by a dead constant.

Guards are bidirectional and name the fix in each message.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import config  # noqa: E402
import config_reachability as census_mod  # noqa: E402

REGIME_KEYED = ("TARGET_GAIN_PCT_STRONG_BULL", "RSI_OVERSOLD_BEAR")


class RegimeKeyedConstantsCannotBeReachedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = census_mod.census()

    def test_the_dispatch_is_keyed_on_modes_not_regimes(self):
        suffixes = set(self.report["suffixes"])
        self.assertEqual(
            suffixes - {"HOURLY"}, set(config.ASSETS),
            "the resolvable-suffix set drifted from config.ASSETS — re-derive which "
            "names a template can actually build")
        for regime in ("STRONG_BULL", "BEAR", "STRONG_BEAR", "RECOVERING", "STALLING"):
            self.assertNotIn(
                regime, suffixes,
                "{} became a configured mode — then regime-keyed constants ARE "
                "reachable and this whole finding needs re-deriving".format(regime))

    def test_both_regime_keyed_constants_are_classed_dead(self):
        for name in REGIME_KEYED:
            self.assertIn(name, self.report["constants"], "{} left config".format(name))
            self.assertIn(
                self.report["constants"][name]["kind"], ("unreferenced", "tests-only"),
                "{} is reachable again — if a regime-keyed lookup was added, that is a "
                "strategy change needing its own record".format(name))

    def test_neither_is_named_outside_config(self):
        """Checked independently of the census's own classification."""
        blob = "\n".join(open(p, encoding="utf-8").read()
                         for p in census_mod._py_files(*census_mod.SHIPPING))
        for name in REGIME_KEYED:
            self.assertIsNone(
                re.search(r"\b" + re.escape(name) + r"\b", blob),
                "{} IS referenced in the shipping path".format(name))

    def test_the_prefix_alone_would_have_credited_them(self):
        """Non-vacuity: the suffix check must be doing work, not decoration."""
        prefixes = self.report["prefixes"]
        for name in REGIME_KEYED:
            self.assertTrue(
                any(name.startswith(p + "_") for p in prefixes),
                "{} no longer matches any dispatch prefix — the false-negative this "
                "test documents can no longer occur".format(name))


class TheDocumentationStillAdvertisesADeadKnobTests(unittest.TestCase):
    def test_claude_md_lists_the_target_as_an_active_parameter(self):
        text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn(
            "TARGET_GAIN_PCT_STRONG_BULL = 0.03", text,
            "CLAUDE.md stopped advertising the dead target — if it was annotated or "
            "removed, drop this assertion and update the study")
        self.assertIn("5% killed win rate", text)

    def test_the_config_value_is_still_the_reverted_one(self):
        self.assertAlmostEqual(
            getattr(config, "TARGET_GAIN_PCT_STRONG_BULL", None), 0.03, places=6,
            msg="the dead target's value changed — someone tuned a knob that governs "
                "nothing, which is the cost this finding is about")

    def test_the_bear_threshold_is_still_thirty(self):
        self.assertEqual(getattr(config, "RSI_OVERSOLD_BEAR", None), 30)


class TheBearDefensiveFeatureIsGatedByDeadFlagsTests(unittest.TestCase):
    """A feature gated by flags nothing passes, parameterised by a constant nothing reads."""

    @classmethod
    def setUpClass(cls):
        cls.engine = (ROOT / "src" / "strategy" / "engine.py").read_text(encoding="utf-8")

    def test_the_flag_is_read_only_inside_the_slope_guarded_block(self):
        self.assertIn("BEAR_DEFENSIVE_LONGS", self.engine)
        block = self.engine[self.engine.index("BEAR_DEFENSIVE_LONGS") - 400:
                            self.engine.index("BEAR_DEFENSIVE_LONGS")]
        self.assertIn(
            "use_slope_regime and longs_only", block,
            "BEAR_DEFENSIVE_LONGS is no longer read inside the slope-guarded block — "
            "check whether it became live and supersede F26's scope")

    def test_the_runner_still_does_not_pass_those_flags(self):
        import entry_gate_probe as probe
        keywords = probe.runner_call_report()["keywords"]
        for flag in ("use_slope_regime", "longs_only"):
            self.assertNotIn(flag, keywords)

    def test_the_flag_is_still_on_in_config(self):
        """Which is what makes it look live in the docs."""
        self.assertTrue(
            getattr(config, "BEAR_DEFENSIVE_LONGS", False),
            "BEAR_DEFENSIVE_LONGS was turned off — the 'enabled but unreachable' "
            "framing no longer applies")


class TheOtherThreeReversalsLeftDifferentResidueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = census_mod.census()

    def test_the_strict_gate_survives_only_in_tests_but_its_successor_is_live(self):
        kinds = self.report["constants"]
        self.assertIn(kinds["STRONG_BULL_REQUIRE_50MA"]["kind"],
                      ("tests-only", "unreferenced"))
        self.assertEqual(kinds["STRONG_BULL_SOFT_50MA_PCT"]["kind"], "static",
                         "the soft 50-MA successor lost its reader — F211's measurement "
                         "of its near-inertness would need redoing")

    def test_the_rsi_extras_left_no_constant_at_all(self):
        """The clean case, and the model for the others."""
        names = set(self.report["constants"])
        for ghost in ("RSI_OVERSOLD_BULL_EXTRA", "BULL_RSI_EXTRA", "RSI_EXTRA_MIN"):
            self.assertNotIn(ghost, names)

    def test_the_opposing_signal_exit_is_genuinely_wired(self):
        runner = (ROOT / "src" / "backtest" / "runner.py").read_text(encoding="utf-8")
        self.assertIn("USE_OPPOSING_SIGNAL_EXIT", runner)
        self.assertIn("OPPOSING_SIGNAL_EXIT_MODES", runner)
        self.assertFalse(getattr(config, "USE_OPPOSING_SIGNAL_EXIT", True))

    def test_config_still_records_that_the_live_flag_never_existed(self):
        """The doc-cites-a-nonexistent-flag note added earlier in this project."""
        text = (ROOT / "config.py").read_text(encoding="utf-8")
        self.assertIn("no such flag or behaviour exists", text)


if __name__ == "__main__":
    unittest.main()
