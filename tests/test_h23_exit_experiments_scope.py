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

**Scoped under engine v2; ENGINE_VERSION 3 (docs/research/ENGINE_V3_QUESTION.md) moves
one premise.** v3 adopts the gap-aware fill the table above measured: an open at or
through the stop fills at the open less ``stop_slippage_pct`` (``gap_stop``), so the
-5.17% vs -10.15% fill-model swing is now a v2-vs-v3 difference, not an open choice. The
constant ``-stop - stop_slippage_pct`` survives only for a stop touched inside a bar. The
scoping verdict stands: the stop LEVEL is still fixed once per trade (no per-bar stop
state, no trailing), there is still no fractional position, and the exit taxonomy grew
to eight labels (gap_stop, gap_target, time_exit_truncated added), none of them a
trailing or partial exit.
"""
import ast
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
    def test_the_backtest_now_holds_the_live_mode_for_the_live_cap(self):
        """The two config caps still differ (8 and 10), but since ENGINE_VERSION 2 the
        backtest resolves the LIVE mode's hold to the live cap (runner.resolve_hold,
        F404701); other modes keep MAX_TRADE_BARS."""
        self.assertEqual(getattr(config, "MAX_TRADE_BARS"), 8)
        self.assertEqual(getattr(config, "MAX_TRADE_BARS_LIVE"), 10)
        self.assertIn("resolve_hold(mode, timeframe, max_trade_bars)",
                      inspect.getsource(runner_mod.run_backtest))
        self.assertEqual(runner_mod.resolve_hold(f"{config.LIVE_SYMBOL}_HOURLY", "hourly"), 10)
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

    def test_the_stop_level_is_fixed_per_trade_with_no_per_bar_state(self):
        """A trailing stop needs the stop level to move within a trade; it does not.

        Re-pinned for ENGINE_VERSION 3 (docs/research/ENGINE_V3_QUESTION.md): v2 booked
        every stop at the constant ``-stop - stop_slippage_pct``; v3 keeps that only for
        a stop touched inside a bar and fills a gapped open at the open (gap_stop). The
        guard's real subject, per-bar stop state, is now checked directly: ``stop_lvl``
        is assigned before the bar loop and never inside it. Renamed from
        test_the_stop_fill_is_constant_with_no_per_bar_state.
        """
        source = inspect.getsource(compute_trade_returns)
        self.assertIn("-stop - stop_slippage_pct", source,
                      "the in-bar stop is no longer the fixed band")
        fn = ast.parse(inspect.getsource(inspect.getmodule(compute_trade_returns)))
        fn = next(n for n in ast.walk(fn)
                  if isinstance(n, ast.FunctionDef) and n.name == "compute_trade_returns")
        bar_loops = [n for n in ast.walk(fn) if isinstance(n, ast.For)
                     and isinstance(n.target, ast.Name) and n.target.id == "k"]
        self.assertEqual(len(bar_loops), 1, "the per-bar scan loop changed shape")
        assigned_in_loop = {t.id for n in ast.walk(bar_loops[0])
                            if isinstance(n, (ast.Assign, ast.AugAssign))
                            for tgt in (n.targets if isinstance(n, ast.Assign) else [n.target])
                            for t in ast.walk(tgt) if isinstance(t, ast.Name)}
        self.assertFalse(
            assigned_in_loop & {"stop_lvl", "stop", "tgt_lvl", "target"},
            "a bracket level is re-assigned inside the bar loop ({}) — the stop may now "
            "trail; H23's first proposal may be implementable as a parameter".format(
                sorted(assigned_in_loop & {"stop_lvl", "stop", "tgt_lvl", "target"})))
        self.assertNotIn(
            "trail", source.lower(),
            "a trailing mechanism appeared in compute_trade_returns — H23's first "
            "proposal may now be implementable as a parameter")

    def test_the_exit_taxonomy_is_the_known_eight(self):
        """Every label the engine can book, read from its assignments.

        Re-pinned for ENGINE_VERSION 3 (docs/research/ENGINE_V3_QUESTION.md): v3 adds
        gap_stop, gap_target and time_exit_truncated, and assigns labels in tuple
        assignments that the v2 regex (``exit_type = "..."``) cannot see, so the labels
        are now read from the AST. Renamed from test_the_exit_taxonomy_is_the_known_four
        (which listed five).
        """
        fn = ast.parse(inspect.getsource(inspect.getmodule(compute_trade_returns)))
        fn = next(n for n in ast.walk(fn)
                  if isinstance(n, ast.FunctionDef) and n.name == "compute_trade_returns")
        kinds = set()
        for n in ast.walk(fn):
            if not isinstance(n, ast.Assign):
                continue
            for tgt in n.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "exit_type":
                    pairs = [(tgt, n.value)]
                elif isinstance(tgt, ast.Tuple) and isinstance(n.value, ast.Tuple):
                    pairs = list(zip(tgt.elts, n.value.elts))
                else:
                    continue
                for t, v in pairs:
                    if (isinstance(t, ast.Name) and t.id == "exit_type"
                            and isinstance(v, ast.Constant) and isinstance(v.value, str)):
                        kinds.add(v.value)
        self.assertEqual(
            kinds, {"ambiguous_same_bar", "target_hit", "stop_hit", "time_exit",
                    "opposing_signal", "gap_stop", "gap_target", "time_exit_truncated"},
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
