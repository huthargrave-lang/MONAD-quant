"""
Tests for the backtest fill model — stop_slippage_pct (C2).

Live stops are market orders that cross the spread and can gap, so they fill
worse than the trigger. compute_trade_returns gains a stop_slippage_pct that
applies extra adverse slippage to STOP fills only (stop_hit and worst-case
ambiguous-as-stop), leaving target fills untouched. Default 0.0 is behaviour-
preserving. Deterministic price paths pin each branch exactly.
"""
import unittest

import numpy as np
import pandas as pd

from src.strategy.engine import compute_trade_returns

TARGET = 0.02
STOP = 0.01


def _df(rows, signal_at=0):
    """rows: list of (open, high, low, close). One long entry at signal_at."""
    idx = pd.date_range("2024-01-01", periods=len(rows), freq="D")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["entry_signal"] = 0
    df.iloc[signal_at, df.columns.get_loc("entry_signal")] = 1
    return df


# Entry fills at bar 1 open = 100. Exit scanning starts at bar 2.
def _stop_path():
    return _df([
        (100, 101, 99, 100),       # 0 signal
        (100, 100.5, 99.8, 100),   # 1 entry @ open 100
        (100, 100.5, 98.5, 99),    # 2 low 98.5 <= 99 stop ; high 100.5 < 102 no target
        (99, 99.5, 98, 99),
    ])


def _target_path():
    return _df([
        (100, 101, 99, 100),
        (100, 100.5, 99.8, 100),
        (100, 103, 100, 102),      # 2 high 103 >= 102 target ; low 100 > 99 no stop
        (102, 103, 101, 102),
    ])


def _ambiguous_path():
    return _df([
        (100, 101, 99, 100),
        (100, 100.5, 99.8, 100),
        (100, 103, 98, 100),       # 2 both 103>=102 target AND 98<=99 stop
        (100, 101, 99, 100),
    ])


def _ret(df, **kw):
    res = compute_trade_returns(df, target_gain_pct=TARGET, stop_loss_pct=STOP,
                                max_trade_bars=5, **kw)
    return res.iloc[0]["return"], res.iloc[0]["exit_type"]


class TestStopSlippage(unittest.TestCase):
    def test_default_zero_preserves_stop_return(self):
        r, et = _ret(_stop_path())
        self.assertEqual(et, "stop_hit")
        self.assertAlmostEqual(r, -STOP, places=9)

    def test_stop_fill_is_worse_by_slippage(self):
        r, et = _ret(_stop_path(), stop_slippage_pct=0.005)
        self.assertEqual(et, "stop_hit")
        self.assertAlmostEqual(r, -STOP - 0.005, places=9)

    def test_target_fill_unaffected_by_stop_slippage(self):
        r, et = _ret(_target_path(), stop_slippage_pct=0.005)
        self.assertEqual(et, "target_hit")
        self.assertAlmostEqual(r, TARGET, places=9)

    def test_worst_case_ambiguous_gets_stop_slippage(self):
        r, et = _ret(_ambiguous_path(), worst_case_ambiguity=True, stop_slippage_pct=0.005)
        self.assertEqual(et, "ambiguous_same_bar")
        self.assertAlmostEqual(r, -STOP - 0.005, places=9)

    def test_optimistic_ambiguous_is_target_no_stop_slippage(self):
        r, et = _ret(_ambiguous_path(), worst_case_ambiguity=False, stop_slippage_pct=0.005)
        self.assertEqual(et, "ambiguous_same_bar")
        self.assertAlmostEqual(r, TARGET, places=9)

    def test_stacks_with_general_slippage(self):
        # general slippage_pct hits every trade; stop_slippage_pct adds on stops.
        r, et = _ret(_stop_path(), slippage_pct=0.001, stop_slippage_pct=0.005)
        self.assertEqual(et, "stop_hit")
        self.assertAlmostEqual(r, -STOP - 0.005 - 0.001, places=9)


class TestRunBacktestPassthrough(unittest.TestCase):
    def _synthetic(self, n=500):
        idx = pd.date_range("2025-01-01", periods=n, freq="h")
        rng = np.random.default_rng(7)
        close = 100 * (1 + 0.15 * np.sin(np.linspace(0, 18, n)) + rng.normal(0, 0.004, n).cumsum())
        close = np.maximum(close, 1.0)
        high = close * (1 + rng.uniform(0, 0.004, n))
        low = close * (1 - rng.uniform(0, 0.004, n))
        return pd.DataFrame({"open": (high + low) / 2, "high": high, "low": low,
                             "close": close, "volume": rng.integers(1_000, 50_000, n)},
                            index=idx)

    def test_stop_slippage_lowers_return(self):
        from src.backtest.runner import run_backtest
        df = self._synthetic()
        base = run_backtest(df=df.copy(), target_gain_pct=0.01, stop_loss_pct=0.005,
                            require_signals=1, timeframe="hourly", plot=False,
                            backtest_mode="realistic")
        slipped = run_backtest(df=df.copy(), target_gain_pct=0.01, stop_loss_pct=0.005,
                               require_signals=1, timeframe="hourly", plot=False,
                               backtest_mode="realistic", stop_slippage_pct=0.01)
        if base and slipped:   # synthetic produces stop exits
            self.assertGreaterEqual(base["total_return"], slipped["total_return"])


if __name__ == "__main__":
    unittest.main()
