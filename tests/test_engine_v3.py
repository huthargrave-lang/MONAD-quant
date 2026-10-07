"""
ENGINE_VERSION 3 (docs/research/ENGINE_V3_QUESTION.md, decision-debate consensus
2026-10-06): each execution rule pinned on hand-built bars whose answer is worked out by
hand. compute_trade_returns is the canonical execution model for every engine caller.
"""
import sys
import unittest
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.backtest.runner import BACKTEST_MODES, ENGINE_VERSION  # noqa: E402
from src.strategy.engine import compute_trade_returns  # noqa: E402
from tests._engine_uncounted import uncounted_module  # noqa: E402

setUpModule, tearDownModule = uncounted_module("engine v3 execution rules on hand-built bars")

FLAT = (100.0, 100.1, 99.9, 100.0)


def bars(rows, signals=()):
    idx = pd.date_range("2026-03-02 14:30", periods=len(rows), freq="h")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 1e6
    df["entry_signal"] = 0
    for i in signals:
        df.iloc[i, df.columns.get_loc("entry_signal")] = 1
    return df


def run(df, **kw):
    kw.setdefault("target_gain_pct", 0.02)
    kw.setdefault("stop_loss_pct", 0.01)
    kw.setdefault("max_trade_bars", 3)
    return compute_trade_returns(df, **kw)


class Version(unittest.TestCase):
    def test_the_engine_is_v3_and_stop_first_by_default(self):
        self.assertEqual(ENGINE_VERSION, 3)
        self.assertNotIn("optimistic", BACKTEST_MODES)
        self.assertTrue(BACKTEST_MODES["upper_bound"]["upper_bound"])
        import inspect
        self.assertIs(inspect.signature(compute_trade_returns).parameters["worst_case_ambiguity"].default, True)


class Rules(unittest.TestCase):
    def test_a_the_bracket_is_live_in_the_entry_bar(self):
        r = run(bars([FLAT, (100, 100.2, 98.9, 99.5), FLAT, FLAT, FLAT], signals=[0]))
        self.assertEqual(r["exit_type"].iloc[0], "stop_hit")
        self.assertEqual(r["exit_time"].iloc[0], r["entry_time"].iloc[0])

    def test_a_both_levels_in_one_bar_resolve_stop_first(self):
        r = run(bars([FLAT, (100, 102.5, 98.5, 100), FLAT, FLAT, FLAT], signals=[0]))
        self.assertEqual(r["exit_type"].iloc[0], "ambiguous_same_bar")
        self.assertAlmostEqual(r["return"].iloc[0], -0.01, places=12)
        r2 = run(bars([FLAT, (100, 102.5, 98.5, 100), FLAT, FLAT, FLAT], signals=[0]),
                 worst_case_ambiguity=False)
        self.assertAlmostEqual(r2["return"].iloc[0], 0.02, places=12)

    def test_b_an_open_through_the_stop_fills_at_the_open_plus_stop_slippage(self):
        r = run(bars([FLAT, FLAT, (97, 97.5, 96.5, 97), FLAT, FLAT], signals=[0]),
                stop_slippage_pct=0.001)
        self.assertEqual(r["exit_type"].iloc[0], "gap_stop")
        self.assertAlmostEqual(r["return"].iloc[0], -0.03 - 0.001, places=12)

    def test_b_an_open_through_the_target_fills_at_the_open_with_no_extra_charge(self):
        r = run(bars([FLAT, FLAT, (103, 103.5, 102.5, 103), FLAT, FLAT], signals=[0]),
                slippage_pct=0.0002)
        self.assertEqual(r["exit_type"].iloc[0], "gap_target")
        self.assertAlmostEqual(r["return"].iloc[0], 0.03 - 0.0002, places=12)

    def test_c_the_time_exit_fills_at_the_open_of_bar_n_plus_1_plus_max(self):
        rows = [FLAT] * 7
        rows[4] = (100.5, 100.6, 100.4, 100.5)            # N=0, MAX=3: bar 4's open
        r = run(bars(rows, signals=[0]))
        self.assertEqual(r["exit_type"].iloc[0], "time_exit")
        self.assertAlmostEqual(r["return"].iloc[0], 0.005, places=12)

    def test_c_at_the_end_of_the_data_the_time_exit_is_truncated(self):
        r = run(bars([FLAT, FLAT, (100, 100.1, 99.9, 100.3)], signals=[0]))
        self.assertEqual(r["exit_type"].iloc[0], "time_exit_truncated")
        self.assertAlmostEqual(r["return"].iloc[0], 0.003, places=12)

    def test_d_one_position_at_a_time(self):
        r = run(bars([FLAT] * 9, signals=[0, 1, 2]), max_trade_bars=4)
        self.assertEqual(len(r), 1)

    def test_d_re_entry_on_the_cycle_that_closes_the_previous_trade(self):
        # entry at bar 1, MAX=2: time exit at the open of bar 3; a signal on bar 2 enters
        # at bar 3's open (live's same-cycle *_then_entry), a signal on bar 1 does not.
        df = bars([FLAT] * 9, signals=[0, 1, 2])
        r = run(df, max_trade_bars=2)
        self.assertEqual(list(r["timestamp"]), list(df.index[[0, 2]]))

    def test_d_an_exit_inside_a_bar_frees_a_signal_on_that_same_bar(self):
        # stop inside bar 1 (the entry bar): a signal ON bar 1 may enter at bar 2's open
        r = run(bars([FLAT, (100, 100.2, 98.9, 99.5), FLAT, FLAT, FLAT, FLAT], signals=[0, 1]))
        self.assertEqual(len(r), 2)

    def test_d_a_dropped_trade_keeps_its_slot(self):
        rows = [FLAT] * 8
        rows[1] = (float("nan"), 100.1, 99.9, 100)        # unusable entry price at bar 1
        r = run(bars(rows, signals=[0, 1, 3]), max_trade_bars=3)
        # dropped trade's scheduled exit is the open of bar 4: signals on bars < 3 blocked
        self.assertEqual(len(r), 1)
        self.assertEqual(r["timestamp"].iloc[0], bars(rows).index[3])


if __name__ == "__main__":
    unittest.main()
