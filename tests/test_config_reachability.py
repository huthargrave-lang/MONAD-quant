"""27 of 203 config constants are unread by shipping code — a naive census says 108.

Study: `docs/research/CONFIG_reachability_census.md`. Tool:
`tools/config_reachability.py`, output frozen at
`docs/research/data/config_reachability.json`.

Three findings said the same thing about single knobs — `USE_ADX_SIZING` has no reader
(F145), `BULL_BREAKOUT_ENABLED` gates only its own computation (F224), the backlog's
supersession filter read a key nobody emits (F225). Nobody had counted.

    static         95  (47%)   a first-party module names it literally
    dynamic        81  (40%)   reached only through a `getattr(config, f"P_{mode}")` template
    tests-only      6  ( 3%)   named only under tests/
    unreferenced   21  (10%)   named nowhere outside config itself
    DEAD to src    27  (13%)   unreferenced + tests-only — the stable headline

**The dynamic class is what makes the number honest.** A literal-name grep calls **108**
constants dead; **27** actually are.

**And the headline had to be the union**, because `unreferenced` is not stable under
observation: naming a dead constant in a guard moves it to `tests-only`, so pinning the
dead set changes it. Writing this file moved three constants across that line. The
question worth asking is "does SHIPPING code read this?", and the union answers it.

The 81 dynamic constants are reached by per-mode dispatch — `build_features` alone
resolves nine parameters that way. Any audit that does not model the dispatch
over-reports dead knobs by 4×.

The dead set is not a uniform pile. Fourteen are the per-mode `BACKTEST_START_*`/`BACKTEST_END_*`
windows — every mode declares a backtest date range and nothing reads any of them. Two are
`BEAR_SHORT_*`, parameters of an experiment CLAUDE.md §7 records as reverted. Two are
`LIVE_*`. The rest are indicator periods, including `ROC_PERIOD`, whose own comment already
says *"Legacy param — computed but unused"* — the one knob in the set that is honestly
labelled.

Guards are bidirectional: the counts must not drift silently in either direction, the
dispatch prefixes must stay modelled, and the specific families above must stay put or be
re-measured.
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import config_reachability as census_mod  # noqa: E402

FROZEN = ROOT / "docs" / "research" / "data" / "config_reachability.json"


class TheCensusIsStableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = census_mod.census()
        cls.counts = cls.report["counts"]
        cls.total = len(cls.report["constants"])

    def test_the_config_layer_is_large_enough_to_be_worth_auditing(self):
        self.assertGreater(self.total, 150,
                           "the config layer shrank to {} constants — re-derive the "
                           "percentages in the study".format(self.total))

    def test_every_constant_lands_in_exactly_one_class(self):
        kinds = {v["kind"] for v in self.report["constants"].values()}
        self.assertTrue(kinds <= set(census_mod.CLASSES), "unknown class: {}".format(kinds))
        self.assertEqual(
            sum(self.counts.get(k, 0) for k in census_mod.CLASSES), self.total,
            "the four classes no longer partition the constants (dead_to_shipping is a "
            "derived union and must not be summed with them)")

    def test_the_dead_count_has_not_grown(self):
        self.assertLessEqual(
            self.counts["dead_to_shipping"], 27,
            "config constants unread by shipping code rose to {} — a knob was added "
            "with no reader, or one lost its last reader".format(
                self.counts["dead_to_shipping"]))

    def test_it_has_not_silently_shrunk_either(self):
        """A ratchet: if the debt was paid down, update the study rather than the test."""
        self.assertGreaterEqual(
            self.counts["dead_to_shipping"], 24,
            "dead config fell to {} — good news; re-run the tool, update "
            "docs/research/CONFIG_reachability_census.md and lower this floor".format(
                self.counts["dead_to_shipping"]))

    def test_the_headline_is_stable_under_observation(self):
        """`unreferenced` alone moves when a guard names a constant; the union does not."""
        counts = self.counts
        self.assertEqual(
            counts["dead_to_shipping"],
            counts.get("unreferenced", 0) + counts.get("tests-only", 0))
        self.assertGreater(
            counts.get("tests-only", 0), 0,
            "no constant is tests-only — then the distinction this metric exists to "
            "absorb has no worked example")

    def test_it_matches_the_frozen_artifact(self):
        frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
        self.assertEqual(
            frozen["counts"], self.counts,
            "the committed census no longer matches a fresh run — regenerate it with "
            "`python3 tools/config_reachability.py --json {}`".format(
                FROZEN.relative_to(ROOT)))


class TheDynamicDispatchIsModelledTests(unittest.TestCase):
    """Without this the census over-reports dead knobs by 4.5x."""

    @classmethod
    def setUpClass(cls):
        cls.report = census_mod.census()

    def test_the_per_mode_prefixes_are_detected(self):
        for prefix in ("RSI_PERIOD", "RSI_OVERSOLD", "MACD_FAST", "VWAP_WINDOW",
                       "TARGET_GAIN_PCT", "STOP_LOSS_PCT"):
            self.assertIn(
                prefix, self.report["prefixes"],
                "{} is no longer detected as a dispatch prefix — every per-mode "
                "constant under it would be miscounted as dead".format(prefix))

    def test_dynamic_is_a_large_share(self):
        dynamic = self.report["counts"].get("dynamic", 0)
        self.assertGreater(
            dynamic, 50,
            "only {} constants are dynamically reached — if the dispatch was replaced "
            "by literal reads that is an improvement; re-measure".format(dynamic))

    def test_a_naive_census_would_be_several_times_worse(self):
        counts = self.report["counts"]
        naive = counts.get("dynamic", 0) + counts["dead_to_shipping"]
        real = counts["dead_to_shipping"]
        self.assertGreater(
            naive / max(real, 1), 3.0,
            "a literal-name census would now report {} dead against a real {} — the "
            "gap that justifies modelling the dispatch has closed".format(naive, real))

    def test_the_engine_still_dispatches_by_mode(self):
        engine = (ROOT / "src" / "strategy" / "engine.py").read_text(encoding="utf-8")
        hits = re.findall(r'getattr\(config, f"([A-Z_]+)_\{', engine)
        self.assertGreaterEqual(
            len(hits), 8,
            "build_features resolves only {} parameters by dispatch now".format(
                len(hits)))

    def test_the_tool_excludes_itself(self):
        """Its docstring shows a `PREFIX_{..}` example; scanning itself invented two."""
        self.assertNotIn("PREFIX", self.report["prefixes"])
        self.assertNotIn("P", self.report["prefixes"])


class TheDeadSetIsWhatTheStudySaysTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        report = census_mod.census()
        # Union, not `unreferenced` — this file names several of them, which would
        # otherwise reclassify the very constants it is asserting about.
        cls.dead = {n for n, v in report["constants"].items()
                    if v["kind"] in ("unreferenced", "tests-only")}

    def test_every_mode_declares_an_unread_backtest_window(self):
        windows = {n for n in self.dead if n.startswith(("BACKTEST_START_",
                                                         "BACKTEST_END_"))}
        self.assertGreaterEqual(
            len(windows), 12,
            "only {} backtest-window constants are unread — if they gained a reader, "
            "the date ranges became configurable and the study needs updating".format(
                len(windows)))

    def test_the_reverted_bear_short_parameters_are_still_there(self):
        for name in ("BEAR_SHORT_MAX_BARS", "BEAR_SHORT_STOP_PCT"):
            self.assertIn(
                name, self.dead,
                "{} gained a reader — bear shorts were reverted per CLAUDE.md §7; if "
                "they are back, that is a strategy change needing its own record".format(
                    name))

    def test_the_one_honestly_labelled_knob_is_labelled(self):
        self.assertIn("ROC_PERIOD", self.dead)
        config_text = (ROOT / "config.py").read_text(encoding="utf-8")
        line = next(l for l in config_text.splitlines() if l.startswith("ROC_PERIOD "))
        self.assertIn(
            "unused", line,
            "ROC_PERIOD lost the comment saying it is unused — it was the only knob in "
            "the dead set that admitted it")

    def test_nothing_in_the_dead_set_is_read_by_the_shipping_path(self):
        """The claim itself, re-checked independently of the tool's own classification."""
        blob = "\n".join(open(p, encoding="utf-8").read()
                         for p in census_mod._py_files(*census_mod.SHIPPING))
        for name in sorted(self.dead):
            self.assertIsNone(
                re.search(r"\b" + re.escape(name) + r"\b", blob),
                "{} IS referenced in the shipping path — the census misclassified "
                "it".format(name))


if __name__ == "__main__":
    unittest.main()
