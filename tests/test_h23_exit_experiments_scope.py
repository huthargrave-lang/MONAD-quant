"""H23's three exit experiments, scoped against what the repo already measured.

H23 proposes trailing stops, partial profit-taking, and a vol-scaled hold time as the
successor to F17/F19 ("the exit is the dominant lever"). Two of the three are engine
changes rather than parameter experiments, and the third has already been measured on
real data — with a null result.

**Vol-scaled hold is bounded small, on observed TQQQ hourly bars.** The overnight-gap
study replayed the live path at both configured caps:

    max bars   gap events   exact total   gap-aware total   fixed-10% damage
        8          34          −5.18%         −10.15%           −5.38 pp
       10          34          −5.17%         −10.15%           −5.38 pp

Changing the cap from 8 to 10 moves total return by **0.01 pp** and leaves the gap-event
count identical. A vol-scaled hold varies exactly this parameter, so the study already
bounds the family it belongs to.

That table also settles a backtest↔live mismatch worth naming: the backtest reads
`MAX_TRADE_BARS = 8` (`runner.py:106`) while the live trader reads
`MAX_TRADE_BARS_LIVE = 10` (`trader.py:552`). The two disagree — and, uniquely among the
mismatches this repo has found, it is measurably immaterial.

**What dominates instead is the fill model.** In the same table, changing how the stop
*fills* — exact-stop versus gap-aware — moves the same path from −5.17% to −10.15%, a
4.98 pp swing, roughly 500× the hold-cap effect. F174 found the same shape from the other
direction: the `worst_case_ambiguity` flag inverts which exit rule wins. **Exit-model
assumptions dominate exit-parameter choices**, and H23 proposes only parameter changes.

**Trailing stops and partial exits do not fit the current engine.** `compute_trade_returns`
books a stop at the constant `-stop - stop_slippage_pct` with no per-bar stop state, and
neither it nor `runner.py` contains any notion of a fractional position. A trailing stop
needs the stop level to move within a trade; a partial exit needs position accounting that
does not exist. Both are engine work, not experiments — which is worth stating before
anyone schedules them as a sweep.
"""
import inspect
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from src.backtest import runner as runner_mod  # noqa: E402
from src.strategy.engine import compute_trade_returns  # noqa: E402

GAP_STUDY = ROOT / "docs" / "research" / "D6_overnight_gap_risk_study.md"


class TheHoldCapMismatchIsRealButImmaterialTests(unittest.TestCase):
    def test_the_backtest_and_the_live_trader_read_different_caps(self):
        self.assertEqual(getattr(config, "MAX_TRADE_BARS"), 8)
        self.assertEqual(getattr(config, "MAX_TRADE_BARS_LIVE"), 10)
        self.assertIn('getattr(config, "MAX_TRADE_BARS", 20)',
                      inspect.getsource(runner_mod.run_backtest))
        self.assertIn("config.MAX_TRADE_BARS_LIVE",
                      (ROOT / "live" / "trader.py").read_text(encoding="utf-8"))

    def test_the_gap_study_measured_both_caps(self):
        text = GAP_STUDY.read_text(encoding="utf-8")
        self.assertIn("| max bars | gap events | exact total | gap-aware total |", text,
                      "the gap study no longer reports the per-cap table — this "
                      "finding's evidence is gone")
        for cap in ("| 8 |", "| 10 |"):
            self.assertIn(cap, text)

    def test_the_two_caps_produce_the_same_result(self):
        """Read from the study rather than asserted from memory."""
        text = GAP_STUDY.read_text(encoding="utf-8")
        rows = re.findall(r"^\|\s*(8|10)\s*\|\s*(\d+)\s*\|\s*(−?-?[\d.]+)%\s*\|"
                          r"\s*(−?-?[\d.]+)%\s*\|", text, re.M)
        self.assertEqual(len(rows), 2, "the per-cap rows changed shape: {}".format(rows))
        by_cap = {r[0]: r for r in rows}
        self.assertEqual(by_cap["8"][1], by_cap["10"][1],
                         "the gap-event count now differs between caps")
        exact = [float(by_cap[c][2].replace("−", "-")) for c in ("8", "10")]
        gapaware = [float(by_cap[c][3].replace("−", "-")) for c in ("8", "10")]
        self.assertLess(abs(exact[0] - exact[1]), 0.1,
                        "the 8-vs-10 cap now moves the exact-model total by more than "
                        "0.1pp — vol-scaled hold may be worth testing after all")
        self.assertLess(abs(gapaware[0] - gapaware[1]), 0.1)


class TheFillModelDominatesTheHoldLengthTests(unittest.TestCase):
    """The comparison that reframes H23."""

    def test_the_gap_aware_swing_dwarfs_the_cap_swing(self):
        text = GAP_STUDY.read_text(encoding="utf-8")
        rows = re.findall(r"^\|\s*(8|10)\s*\|\s*\d+\s*\|\s*(−?-?[\d.]+)%\s*\|"
                          r"\s*(−?-?[\d.]+)%\s*\|", text, re.M)
        by_cap = {r[0]: r for r in rows}
        cap_swing = abs(float(by_cap["8"][1].replace("−", "-"))
                        - float(by_cap["10"][1].replace("−", "-")))
        model_swing = abs(float(by_cap["8"][1].replace("−", "-"))
                          - float(by_cap["8"][2].replace("−", "-")))
        self.assertGreater(
            model_swing, 1.0,
            "the exact-vs-gap-aware swing collapsed — the 'fill model dominates' "
            "reading depends on it")
        self.assertGreater(
            model_swing / max(cap_swing, 0.01), 50,
            "the fill-model swing is no longer at least 50x the hold-cap swing "
            "({:.2f} vs {:.2f})".format(model_swing, cap_swing))

    def test_the_study_still_records_the_largest_single_miss(self):
        text = GAP_STUDY.read_text(encoding="utf-8")
        self.assertIn("8.96 pp understatement", text,
                      "the largest single gap miss is no longer recorded — it is the "
                      "clearest single-event evidence that the fill model, not the "
                      "hold length, is the lever")


class TrailingAndPartialExitsAreEngineWorkTests(unittest.TestCase):
    """Stated before anyone schedules them as a parameter sweep."""

    def test_the_stop_fill_is_constant_with_no_per_bar_state(self):
        source = inspect.getsource(compute_trade_returns)
        self.assertIn("exit_return = -stop - stop_slippage_pct", source)
        self.assertNotIn(
            "trail", source.lower(),
            "a trailing mechanism appeared in compute_trade_returns — H23's first "
            "proposal may now be implementable as a parameter")

    def test_the_exit_taxonomy_is_the_known_four(self):
        source = inspect.getsource(compute_trade_returns)
        kinds = set(re.findall(r'exit_type\s*=\s*"([a-z_]+)"', source))
        self.assertEqual(
            kinds, {"ambiguous_same_bar", "target_hit", "stop_hit", "time_exit",
                    "opposing_signal"},
            "the exit taxonomy changed to {} — re-read what the engine can express"
            .format(sorted(kinds)))

    def test_nothing_in_the_engine_or_runner_models_a_partial_position(self):
        for module in (compute_trade_returns, runner_mod.run_backtest):
            source = inspect.getsource(module).lower()
            self.assertNotIn("partial", source,
                             "partial-exit accounting appeared — H23's second proposal "
                             "may now be testable")

    def test_a_bar_limit_override_hook_DOES_exist(self):
        """The one H23 proposal the engine can already express: per-trade hold length.
        Only walk_forward uses it; runner.py never passes one."""
        params = inspect.signature(compute_trade_returns).parameters
        self.assertIn("bar_limit_overrides", params)
        self.assertNotIn(
            "bar_limit_overrides", inspect.getsource(runner_mod.run_backtest),
            "runner.py now passes bar-limit overrides — a vol-scaled hold may have "
            "landed; measure it against the null result above")


if __name__ == "__main__":
    unittest.main()
