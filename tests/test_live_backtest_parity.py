"""The backtest decides like the live bot: 0 divergent decision inputs (ENGINE_VERSION 2).

Study: `docs/research/LIVE_backtest_parity_census.md`. Tool:
`tools/live_backtest_parity.py`, frozen at
`docs/research/data/live_backtest_parity.json`.

History. The first census (2026-08) found not one of seven decision inputs agreeing:
three behavioural divergences (the entry regime gate, the UTC intraday time gate F148, a
10-vs-8 bar max hold), two coincident rows and two dormant capabilities. The admission
gate (tools/admit.py) blocks every price strategy while any input diverges, so the
decision-debate of 2026-09-22 (Q4) aligned the BACKTEST to the live bot (live is ground
truth) and found a fourth: the backtest simulated short trades the bot skips, which the
census could not see because `longs_only` gates no entry (F26).

Now every row that used to be read from source text is MEASURED:

* **entry regime gate** — the value run_backtest resolves (`runner.resolve_regime_filter`)
  against the literal live passes;
* **intraday time gate** — the exact set of session bars each path acts on over a
  synthetic fortnight (the backtest's session loader + trade-hours gate, against live's
  :32 cron acting on the latest bar at least an hour old);
* **max hold** — the hold run_backtest resolves for the live mode against
  MAX_TRADE_BARS_LIVE;
* **short entries** — short entries the backtest path emits, against live's policy.

    3 agree · 2 coincident · 2 dormant · 0 divergent

Each measured row has a negative control below, so an agreement cannot be vacuous. The
max-hold time-exit measurement (bands resolve before the clock at this volatility) is
kept: it still explains why the old 8-vs-10 gap was cheap, and when it would stop being.
"""
import json
import sys
import unittest
from unittest import mock
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

    def test_nothing_diverges(self):
        diverging = [r["dimension"] for r in self.report["rows"] if r["verdict"] == parity.DIVERGE]
        self.assertEqual(
            diverging, [],
            "a backtest/live divergence reappeared: {} — the admission gate will block every "
            "price strategy until it is reconciled".format(diverging))

    def test_it_matches_the_frozen_artifact(self):
        frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
        self.assertEqual(
            frozen["counts"], self.report["counts"],
            "the committed parity census no longer matches a fresh run — regenerate "
            "with `python3 tools/live_backtest_parity.py --json {}`".format(
                FROZEN.relative_to(ROOT)))


class TheDivergencesAreClosedByMeasurement(unittest.TestCase):
    """Each formerly divergent row now agrees, and each agreement has a control showing
    the probe would have seen a difference."""

    @classmethod
    def setUpClass(cls):
        cls.by_dim = {r["dimension"]: r for r in parity.census()["rows"]}

    def test_the_entry_gate_agrees(self):
        row = self.by_dim["entry regime gate"]
        self.assertEqual(row["verdict"], parity.AGREE)
        self.assertIn("False", row["backtest"])
        self.assertIn("False", row["live"])

    def test_the_time_gate_acts_on_the_same_bars(self):
        backtest, live = parity.acted_bars()
        self.assertTrue(backtest)
        self.assertEqual(backtest, live)

    def test_the_old_utc_gate_would_have_diverged(self):
        """Control: F148's UTC hour gate (9, 16) on a naive-UTC index drops most of the
        session, so the probe must report a difference for it."""
        with mock.patch.object(parity, "_signature_default", return_value="(9, 16)"):
            backtest, live = parity.acted_bars()
        self.assertLess(len(backtest), len(live))

    def test_the_max_hold_agrees_for_the_live_mode(self):
        self.assertEqual(self.by_dim["max hold (time exit)"]["verdict"], parity.AGREE)
        from src.backtest.runner import resolve_hold
        self.assertEqual(resolve_hold(f"{config.LIVE_SYMBOL}_HOURLY", "hourly"),
                         config.MAX_TRADE_BARS_LIVE)
        # other modes keep their own hold; only the live mode is tied to the bot
        self.assertEqual(resolve_hold("BTC_DAILY", "daily"), config.MAX_TRADE_BARS)

    def test_short_entries_agree(self):
        self.assertEqual(self.by_dim["short entries"]["verdict"], parity.AGREE)

    def test_the_short_probe_sees_shorts_when_they_are_allowed(self):
        """Control: with shorts allowed the backtest emits them, so a 0 count is real."""
        with mock.patch.object(config, "TRADER_ALLOW_SHORTS", True):
            backtest, _, _, _ = parity.shorts()
        self.assertNotEqual(backtest.split()[0], "0")

    def test_but_the_time_exit_almost_never_fires_at_this_volatility(self):
        """The correction: a 25% config gap with ~zero behavioural cost today."""
        result = parity.time_exit_bind_rate(sigma=0.008)
        share = result["time_exits_at_8"] / result["trades"]
        self.assertGreater(result["trades"], 500, "too few trades to measure")
        self.assertLess(
            share, 0.02,
            "the time exit now ends {:.1%} of trades at 0.8%/bar — it has become "
            "material, so the 8-vs-10 divergence needs costing properly".format(share))
        self.assertLess(
            abs(result["mean_return_delta_bp"]), 0.5,
            "8-vs-10 now moves the mean return by {:.2f} bp — re-measure and update "
            "the study".format(result["mean_return_delta_bp"]))

    def test_it_does_bind_at_low_volatility_so_the_check_is_not_vacuous(self):
        result = parity.time_exit_bind_rate(sigma=0.0015)
        share = result["time_exits_at_8"] / result["trades"]
        self.assertGreater(
            share, 0.05,
            "the time exit no longer binds even at 0.15%/bar ({:.1%}) — then the "
            "'bands resolve first' mechanism has no worked counter-example".format(
                share))


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
