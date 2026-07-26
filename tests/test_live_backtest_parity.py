"""Not one of seven decision inputs agrees between the backtest and the live bot.

Study: `docs/research/LIVE_backtest_parity_census.md`. Tool:
`tools/live_backtest_parity.py`, frozen at
`docs/research/data/live_backtest_parity.json`.

The project's central unexplained fact is that the backtest shows an edge and the live bot
is flat. Individual divergences are recorded — F141 (entry gate), F148 (UTC time gate),
F26 (slope flags) — but nobody had enumerated the decision inputs in one place.

    0 agree · 2 coincident · 2 dormant · 3 divergent

**Three behavioural divergences.** Two were already known: the entry regime gate (backtest
runs it at the signature default `True`, live passes `False`) and the intraday time gate
(backtest slices UTC hours, live checks ET market hours). The third was not:

* **max hold** — `MAX_TRADE_BARS = 8` in the backtest, `MAX_TRADE_BARS_LIVE = 10` live.
  A 25% difference in the time exit, which for a mean-reversion strategy whose target and
  stop are both narrow is a first-order driver of the trade population.

**Two coincident.** Same value today, read from different places, with nothing keeping
them in step:

* **position size** — the backtest reads `config.FIXED_POSITION_PCT` (0.10);
  `live/state.py::get_position_plan` assigns the literal `0.10`. Change the config and the
  backtest moves while the bot does not. This is the most consequential parameter after
  the entry gate, and it is duplicated rather than shared.
* **slope flags** — the backtest omits them (defaulting False), live passes False
  explicitly. Same result, different mechanism.

**Two dormant.** The backtest supports an opposing-signal exit and ATR dynamic stops; the
live path has neither. Both flags are off, so there is no behavioural difference today —
but a sweep that turns either on silently models something the bot cannot do. Counted
separately rather than folded into the divergences, which would inflate the headline.

Every row is extracted from source at run time, so the table cannot rot as the code moves.
Guards below fail in both directions: if a divergence is fixed (good — supersede and
re-baseline), and if a new one appears.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import config  # noqa: E402
import live_backtest_parity as parity  # noqa: E402

FROZEN = ROOT / "docs" / "research" / "data" / "live_backtest_parity.json"


class TheCensusIsCompleteAndStableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = parity.census()
        cls.by_dim = {r["dimension"]: r for r in cls.report["rows"]}

    def test_every_dimension_produces_a_verdict(self):
        self.assertEqual(len(self.report["rows"]), len(parity.DIMENSIONS))
        for row in self.report["rows"]:
            self.assertIn(row["verdict"],
                          (parity.AGREE, parity.COINCIDENT,
                           parity.DORMANT, parity.DIVERGE))
            self.assertTrue(row["backtest"] and row["live"])

    def test_nothing_agrees_outright(self):
        self.assertEqual(
            self.report["counts"][parity.AGREE], 0,
            "a decision input now agrees by construction — good news; record which one "
            "and update docs/research/LIVE_backtest_parity_census.md")

    def test_the_divergence_count_has_not_grown(self):
        self.assertLessEqual(
            self.report["counts"][parity.DIVERGE], 3,
            "backtest/live divergences rose to {} — a new one appeared; the two paths "
            "were already not comparable".format(
                self.report["counts"][parity.DIVERGE]))

    def test_it_matches_the_frozen_artifact(self):
        frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
        self.assertEqual(
            frozen["counts"], self.report["counts"],
            "the committed parity census no longer matches a fresh run — regenerate "
            "with `python3 tools/live_backtest_parity.py --json {}`".format(
                FROZEN.relative_to(ROOT)))


class TheThreeBehaviouralDivergencesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_dim = {r["dimension"]: r for r in parity.census()["rows"]}

    def test_the_entry_gate_still_diverges(self):
        row = self.by_dim["entry regime gate"]
        self.assertEqual(
            row["verdict"], parity.DIVERGE,
            "the entry gate now matches — H27/F141 are FIXED. Supersede them, and note "
            "that every backtest number was produced under the other gate.")
        self.assertIn("True", row["backtest"])
        self.assertIn("False", row["live"])

    def test_the_time_gate_still_diverges(self):
        self.assertEqual(self.by_dim["intraday time gate"]["verdict"], parity.DIVERGE)

    def test_the_max_hold_differs_by_two_bars(self):
        """The one this census found."""
        self.assertEqual(self.by_dim["max hold (time exit)"]["verdict"], parity.DIVERGE)
        self.assertEqual(getattr(config, "MAX_TRADE_BARS", None), 8)
        self.assertEqual(getattr(config, "MAX_TRADE_BARS_LIVE", None), 10)

    def test_the_gap_is_material_relative_to_the_hold(self):
        """25% is not a rounding difference on an 8-bar horizon."""
        backtest = getattr(config, "MAX_TRADE_BARS")
        live = getattr(config, "MAX_TRADE_BARS_LIVE")
        self.assertGreater(
            abs(live - backtest) / backtest, 0.1,
            "the two max-hold settings converged to within 10% — re-measure before "
            "citing the 25% figure")


class ThePositionSizeIsDuplicatedNotSharedTests(unittest.TestCase):
    """The most consequential parameter after the entry gate, held in two places."""

    def test_the_verdict_is_coincident(self):
        row = {r["dimension"]: r for r in parity.census()["rows"]}["position size"]
        self.assertEqual(
            row["verdict"], parity.COINCIDENT,
            "position sizing is no longer coincident — if live now reads "
            "config.FIXED_POSITION_PCT, that is a real fix worth recording")

    def test_the_live_path_hardcodes_the_literal(self):
        source = (ROOT / "live" / "state.py").read_text(encoding="utf-8")
        self.assertIn(
            "position_pct = 0.10", source,
            "live/state.py no longer hardcodes the position percentage — check whether "
            "it now reads the config value")

    def test_the_backtest_reads_the_config_value(self):
        source = (ROOT / "src" / "backtest" / "runner.py").read_text(encoding="utf-8")
        self.assertIn("FIXED_POSITION_PCT", source)

    def test_they_hold_the_same_value_today(self):
        self.assertAlmostEqual(getattr(config, "FIXED_POSITION_PCT"), 0.10, places=6,
                               msg="config moved off 0.10 while live/state.py still "
                                   "hardcodes it — the two paths now size differently")


class TheDormantCapabilitiesAreNotCountedAsDivergencesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_dim = {r["dimension"]: r for r in parity.census()["rows"]}

    def test_both_capability_rows_are_dormant(self):
        for dim in ("opposing-signal exit", "ATR dynamic stops"):
            self.assertEqual(
                self.by_dim[dim]["verdict"], parity.DORMANT,
                "{} is no longer dormant — its flag was turned on, so the backtest is "
                "now modelling something the live bot cannot do".format(dim))

    def test_the_flags_are_off(self):
        self.assertFalse(getattr(config, "USE_OPPOSING_SIGNAL_EXIT", False))
        self.assertFalse(getattr(config, "USE_ATR_DYNAMIC_STOPS", False))

    def test_the_distinction_is_not_vacuous(self):
        """If nothing were dormant, the class would have no worked example."""
        self.assertGreater(parity.census()["counts"][parity.DORMANT], 0)


if __name__ == "__main__":
    unittest.main()
