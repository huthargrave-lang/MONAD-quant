"""
Tests for the unified execution model across backtest and live trading.

Execution rule (backtest and live):
    1. Signal fires on completed bar N (features from bar N's OHLCV).
    2. Entry at the next tradeable price: bar N+1 open (backtest) / market price (live).
    3. TP/SL computed relative to the entry price, NOT bar N's close.
    4. Exit via target hit, stop hit, or time limit.

These tests verify this rule is implemented correctly in compute_trade_returns()
and that the old failure mode (TP/SL anchored to bar N close) is not reintroduced.
"""

import unittest
import pandas as pd
import numpy as np


def _make_ohlcv(rows: list[dict]) -> pd.DataFrame:
    """Helper: build a minimal OHLCV DataFrame from a list of bar dicts.

    Each dict must have: open, high, low, close.
    Optional: entry_signal (default 0), trend_direction (default 0).
    Index is integer-based (simulates bar positions).
    """
    df = pd.DataFrame(rows)
    if "entry_signal" not in df.columns:
        df["entry_signal"] = 0
    if "trend_direction" not in df.columns:
        df["trend_direction"] = 0
    df.index = pd.RangeIndex(len(df))
    return df


class TestBacktestEntryBasis(unittest.TestCase):
    """Verify compute_trade_returns uses bar N+1 open as entry, not bar N close."""

    def test_entry_at_next_bar_open_not_signal_bar_close(self):
        """Signal on bar 0 (close=100). Bar 1 opens at 101.
        Entry should be at 101, not 100."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            # Bar 0: signal bar — close=100, but next bar opens higher
            {"open": 99.0, "high": 101.0, "low": 98.0, "close": 100.0, "entry_signal": 1},
            # Bar 1: entry bar — open=101 (gap up overnight)
            {"open": 101.0, "high": 103.0, "low": 100.5, "close": 102.0, "entry_signal": 0},
            # Bar 2: first exit-scan bar — target hit based on entry=101
            {"open": 102.0, "high": 105.0, "low": 101.5, "close": 104.0, "entry_signal": 0},
        ])

        result = compute_trade_returns(df, target_gain_pct=0.03, stop_loss_pct=0.015, max_trade_bars=5)

        self.assertEqual(len(result), 1, "Should produce exactly one trade")
        trade = result.iloc[0]

        # Entry at 101. Target = 101 * 1.03 = 104.03. Bar 2 high = 105 → target hit.
        self.assertEqual(trade["exit_type"], "target_hit")
        self.assertAlmostEqual(trade["return"], 0.03, places=4)

    def test_tp_sl_relative_to_entry_not_close(self):
        """Signal bar close=80, next bar open=80.50.
        With 0.42% target: TP should be 80.50*1.0042=80.838, NOT 80*1.0042=80.336.
        With 0.20% stop: SL should be 80.50*0.998=80.339."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            # Bar 0: signal fires — close=80.00
            {"open": 79.5, "high": 80.5, "low": 79.0, "close": 80.0, "entry_signal": 1},
            # Bar 1: entry bar — open=80.50 (gap up from close)
            {"open": 80.50, "high": 80.60, "low": 80.40, "close": 80.45, "entry_signal": 0},
            # Bar 2: high=80.80, low=80.40 — does NOT breach TP (80.838) or SL (80.339)
            {"open": 80.45, "high": 80.80, "low": 80.40, "close": 80.70, "entry_signal": 0},
            # Bar 3: high=81.00 — now hits TP at 80.838
            {"open": 80.70, "high": 81.00, "low": 80.50, "close": 80.90, "entry_signal": 0},
        ])

        result = compute_trade_returns(df, target_gain_pct=0.0042, stop_loss_pct=0.002, max_trade_bars=5)

        self.assertEqual(len(result), 1)
        trade = result.iloc[0]
        self.assertEqual(trade["exit_type"], "target_hit")
        # If TP were at bar-close-based 80.336, it would have hit on bar 2.
        # Since entry is 80.50, TP is 80.838 — only hit on bar 3.
        # Return = 0.0042 (the target pct)
        self.assertAlmostEqual(trade["return"], 0.0042, places=4)

    def test_stop_loss_relative_to_entry_not_close(self):
        """Signal bar close=80, next bar open=79.50 (gap down).
        Stop at 0.2% = 79.50*0.998=79.341. NOT 80*0.998=79.84."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            # Bar 0: signal fires
            {"open": 80.5, "high": 81.0, "low": 79.8, "close": 80.0, "entry_signal": 1},
            # Bar 1: entry bar — open=79.50 (gap down)
            {"open": 79.50, "high": 79.80, "low": 79.40, "close": 79.60, "entry_signal": 0},
            # Bar 2: low=79.30 — breaches stop at 79.341 (entry-based)
            {"open": 79.55, "high": 79.70, "low": 79.30, "close": 79.50, "entry_signal": 0},
        ])

        result = compute_trade_returns(df, target_gain_pct=0.01, stop_loss_pct=0.002, max_trade_bars=5)

        self.assertEqual(len(result), 1)
        trade = result.iloc[0]
        # Entry=79.50, SL=79.50*0.998=79.341. Bar 2 low=79.30 < 79.341 → stop_hit.
        self.assertEqual(trade["exit_type"], "stop_hit")
        self.assertAlmostEqual(trade["return"], -0.002, places=4)

    def test_exit_scanning_starts_at_bar_n_plus_2(self):
        """Exit scanning must start at bar N+2 (bar after entry bar).
        Bar N+1 is the entry bar — its OHLC should NOT trigger TP/SL."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            # Bar 0: signal
            {"open": 100, "high": 101, "low": 99, "close": 100, "entry_signal": 1},
            # Bar 1: entry bar — high=110 would hit any target, but should be skipped
            {"open": 100, "high": 110, "low": 90, "close": 100, "entry_signal": 0},
            # Bar 2: first scan bar — narrow range, no exit
            {"open": 100, "high": 100.1, "low": 99.9, "close": 100, "entry_signal": 0},
        ])

        result = compute_trade_returns(df, target_gain_pct=0.05, stop_loss_pct=0.05, max_trade_bars=5)

        self.assertEqual(len(result), 1)
        trade = result.iloc[0]
        # Bar 1 has range 90-110 but is the entry bar → not scanned.
        # Bar 2 has range 99.9-100.1 → neither 5% target nor 5% stop → time exit.
        self.assertEqual(trade["exit_type"], "time_exit")

    def test_time_exit_uses_last_future_bar_close(self):
        """When neither TP nor SL hits, return is based on last bar's close."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            # Bar 0: signal
            {"open": 100, "high": 101, "low": 99, "close": 100, "entry_signal": 1},
            # Bar 1: entry bar — open=100 is entry price
            {"open": 100, "high": 100.5, "low": 99.5, "close": 100.2, "entry_signal": 0},
            # Bar 2: no exit
            {"open": 100.2, "high": 100.3, "low": 100.0, "close": 100.1, "entry_signal": 0},
            # Bar 3: no exit — last bar before time limit
            {"open": 100.1, "high": 100.4, "low": 99.8, "close": 100.5, "entry_signal": 0},
        ])

        result = compute_trade_returns(df, target_gain_pct=0.05, stop_loss_pct=0.05, max_trade_bars=2)

        self.assertEqual(len(result), 1)
        trade = result.iloc[0]
        self.assertEqual(trade["exit_type"], "time_exit")
        # Entry=100 (bar 1 open). Last future bar close=100.5. Return=(100.5-100)/100=0.005
        self.assertAlmostEqual(trade["return"], 0.005, places=4)

    def test_signal_on_last_bar_skipped(self):
        """Signal on the very last bar has no bar N+1 → trade should be dropped."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            {"open": 100, "high": 101, "low": 99, "close": 100, "entry_signal": 0},
            {"open": 100, "high": 101, "low": 99, "close": 100, "entry_signal": 1},
        ])

        result = compute_trade_returns(df, target_gain_pct=0.03, stop_loss_pct=0.015, max_trade_bars=5)
        self.assertEqual(len(result), 0, "Signal on last bar should produce no trade")


class TestRegressionBarCloseAnchor(unittest.TestCase):
    """Regression tests for the old bug: TP/SL anchored to bar N close.

    The old code used entry_price = row["close"] (bar N close) instead of
    df.iloc[next_bar_loc]["open"] (bar N+1 open). When these differ (gaps),
    the bracket levels are wrong.
    """

    def test_gap_up_makes_tp_unreachable_under_old_model(self):
        """Old bug scenario: bar close=80.00, market opens at 80.50.
        With 0.42% target, old TP = 80.00*1.0042 = 80.336.
        But entry is at 80.50, so TP is BELOW entry → guaranteed loss.
        New model: TP = 80.50*1.0042 = 80.838 → correct."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            # Bar 0: signal — close far below next bar's open
            {"open": 79.0, "high": 80.5, "low": 78.5, "close": 80.0, "entry_signal": 1},
            # Bar 1: entry — opens 0.625% higher than bar 0 close
            {"open": 80.50, "high": 80.55, "low": 80.40, "close": 80.48, "entry_signal": 0},
            # Bar 2: price reaches 80.85 — hits new TP (80.838) but NOT old TP (80.336)
            {"open": 80.48, "high": 80.85, "low": 80.30, "close": 80.70, "entry_signal": 0},
        ])

        result = compute_trade_returns(df, target_gain_pct=0.0042, stop_loss_pct=0.002, max_trade_bars=5)

        self.assertEqual(len(result), 1)
        trade = result.iloc[0]
        # Correct model: entry=80.50, TP=80.838, bar 2 high=80.85 → target_hit
        self.assertEqual(trade["exit_type"], "target_hit")
        self.assertAlmostEqual(trade["return"], 0.0042, places=4)

    def test_gap_down_widens_effective_stop(self):
        """Bar close=80.00, market opens at 79.00 (gap down).
        Old SL = 80.00*0.998 = 79.84 → already below entry at 79.00 → instant stop.
        New SL = 79.00*0.998 = 78.842 → reasonable stop below entry."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            # Bar 0: signal
            {"open": 80.5, "high": 81.0, "low": 79.5, "close": 80.0, "entry_signal": 1},
            # Bar 1: entry — opens at 79.00 (1.25% gap down)
            {"open": 79.0, "high": 79.5, "low": 78.9, "close": 79.2, "entry_signal": 0},
            # Bar 2: low=79.0 — does NOT hit new stop at 78.842
            {"open": 79.2, "high": 79.8, "low": 79.0, "close": 79.5, "entry_signal": 0},
            # Bar 3: recovery — hits target at 79.0*1.0042 = 79.332
            {"open": 79.5, "high": 79.9, "low": 79.3, "close": 79.7, "entry_signal": 0},
        ])

        result = compute_trade_returns(df, target_gain_pct=0.0042, stop_loss_pct=0.002, max_trade_bars=5)

        self.assertEqual(len(result), 1)
        trade = result.iloc[0]
        # Under old model: entry=80.0, stop=79.84. Bar 1 low=78.9 → stop hit on entry bar.
        # But entry bar is NOT scanned, so even old model wouldn't stop on bar 1.
        # Bar 2 low=79.0 < 79.84 → old model would stop_hit here.
        # Under new model: entry=79.0, stop=78.842. Bar 2 low=79.0 > 78.842 → survives.
        # Bar 3 high=79.9 > 79.332 (target) → target_hit.
        self.assertEqual(trade["exit_type"], "target_hit")


class TestStateFillBasisConsistency(unittest.TestCase):
    """Verify that fill_basis (not bar_close) is recorded in state and used for PnL."""

    def setUp(self):
        import sqlite3
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        import live.state as state_mod
        self._state = state_mod
        self._state._DB_PATH = self._tmp.name
        self._state.init_db()

    def tearDown(self):
        import os
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass

    def test_entry_price_is_fill_basis_not_bar_close(self):
        """Simulate the live flow: bar_close=80.0, fill_basis=80.50.
        State should record 80.50 as entry_price."""
        bar_close = 80.0
        fill_basis = 80.50  # live market price at order time

        # This is what trader.py now does — records fill_basis, not bar_close
        self._state.open_position("TQQQ", fill_basis, 10, "999")
        pos = self._state.get_position()

        self.assertAlmostEqual(pos.entry_price, 80.50,
                               msg="entry_price should be fill_basis (80.50), not bar_close (80.0)")
        self.assertNotAlmostEqual(pos.entry_price, bar_close,
                                  msg="entry_price must NOT be bar_close")

    def test_pnl_computed_against_fill_basis(self):
        """PnL should be (exit_fill - fill_basis) / fill_basis."""
        fill_basis = 80.50
        exit_fill = 80.84  # target hit

        self._state.open_position("TQQQ", fill_basis, 10, "999")

        # This is what trader.py does on bracket fill
        ret = (exit_fill - fill_basis) / fill_basis
        self._state.close_position(return_pct=ret, exit_type="target_hit", exit_price=exit_fill)

        summary = self._state.get_trade_summary()
        self.assertEqual(summary["total"], 1)
        # Expected: (80.84 - 80.50) / 80.50 = 0.004224...
        self.assertAlmostEqual(summary["total_ret"], 0.004224, places=4)
        self.assertAlmostEqual(summary["win_rate"], 1.0)

    def test_pending_close_records_zero_pnl(self):
        """When fill data is unavailable, return_pct=0.0 is recorded."""
        self._state.open_position("TQQQ", 80.50, 10, "999")
        self._state.close_position(return_pct=0.0, exit_type="pending_close", exit_price=None)

        summary = self._state.get_trade_summary()
        self.assertEqual(summary["total"], 1)
        self.assertAlmostEqual(summary["total_ret"], 0.0)
        self.assertEqual(summary["exit_types"], {"pending_close": 1})

    def test_time_exit_pnl_uses_entry_price_from_state(self):
        """Time-exit PnL = (ref_price - entry_price) / entry_price.
        entry_price in state is fill_basis, so PnL is correct."""
        fill_basis = 80.50
        ref_price = 80.30  # reference price at time-exit

        self._state.open_position("TQQQ", fill_basis, 10, "999")
        ret = (ref_price - fill_basis) / fill_basis
        self._state.close_position(return_pct=ret, exit_type="time_exit", exit_price=ref_price)

        summary = self._state.get_trade_summary()
        # (80.30 - 80.50) / 80.50 = -0.002484...
        self.assertAlmostEqual(summary["total_ret"], -0.002484, places=4)
        self.assertEqual(summary["exit_types"], {"time_exit": 1})


if __name__ == "__main__":
    unittest.main()
