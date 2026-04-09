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


class TestExitTypeTracking(unittest.TestCase):
    """Verify exit_type values including ambiguous_same_bar."""

    def test_ambiguous_same_bar_pessimistic(self):
        """When both TP and SL are inside the same bar, exit_type = ambiguous_same_bar."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            {"open": 100, "high": 101, "low": 99, "close": 100, "entry_signal": 1},
            # Bar 1: entry at open=100
            {"open": 100, "high": 100.5, "low": 99.8, "close": 100.2, "entry_signal": 0},
            # Bar 2: huge range — both 1% target (101) and 1% stop (99) inside
            {"open": 100, "high": 102, "low": 98, "close": 100, "entry_signal": 0},
        ])

        result = compute_trade_returns(df, target_gain_pct=0.01, stop_loss_pct=0.01,
                                       max_trade_bars=5, worst_case_ambiguity=True)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["exit_type"], "ambiguous_same_bar")
        # Pessimistic: return = -stop
        self.assertAlmostEqual(result.iloc[0]["return"], -0.01, places=4)

    def test_ambiguous_same_bar_optimistic(self):
        """Optimistic mode: same-bar ambiguity still labeled ambiguous_same_bar, but return = +target."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            {"open": 100, "high": 101, "low": 99, "close": 100, "entry_signal": 1},
            {"open": 100, "high": 100.5, "low": 99.8, "close": 100.2, "entry_signal": 0},
            {"open": 100, "high": 102, "low": 98, "close": 100, "entry_signal": 0},
        ])

        result = compute_trade_returns(df, target_gain_pct=0.01, stop_loss_pct=0.01,
                                       max_trade_bars=5, worst_case_ambiguity=False)
        self.assertEqual(result.iloc[0]["exit_type"], "ambiguous_same_bar")
        self.assertAlmostEqual(result.iloc[0]["return"], 0.01, places=4)

    def test_exit_type_values_complete(self):
        """All three normal exit types are produced by a multi-trade scenario."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            # Trade 1: target hit
            {"open": 100, "high": 101, "low": 99, "close": 100, "entry_signal": 1},
            {"open": 100, "high": 100.5, "low": 99.8, "close": 100.2, "entry_signal": 0},
            {"open": 100.2, "high": 103, "low": 100, "close": 102, "entry_signal": 0},
            # Trade 2: stop hit
            {"open": 102, "high": 103, "low": 101, "close": 102, "entry_signal": 1},
            {"open": 102, "high": 102.5, "low": 101.8, "close": 102, "entry_signal": 0},
            {"open": 102, "high": 102.1, "low": 98, "close": 99, "entry_signal": 0},
            # Trade 3: time exit (narrow bars)
            {"open": 99, "high": 100, "low": 98, "close": 99, "entry_signal": 1},
            {"open": 99, "high": 99.1, "low": 98.9, "close": 99, "entry_signal": 0},
            {"open": 99, "high": 99.1, "low": 98.9, "close": 99.05, "entry_signal": 0},
        ])

        result = compute_trade_returns(df, target_gain_pct=0.02, stop_loss_pct=0.02, max_trade_bars=1)
        exit_types = set(result["exit_type"].values)
        self.assertIn("target_hit", exit_types)
        self.assertIn("stop_hit", exit_types)
        self.assertIn("time_exit", exit_types)


class TestSoft50MAGate(unittest.TestCase):
    """Verify the soft 50-MA gate blocks STRONG_BULL longs when price is deeply below 50-MA."""

    def test_gate_blocks_deep_below_50ma(self):
        """When price is >5% below 50-MA in STRONG_BULL, entry should be blocked."""
        from src.strategy.engine import generate_trades
        import config

        df = pd.DataFrame({
            "open": [100, 100, 100],
            "high": [101, 101, 101],
            "low": [99, 99, 99],
            "close": [100, 100, 100],
            "momentum_signal": [1, 1, 0],
            "volume_signal": [0, 0, 0],
            "vol_regime": [0, 0, 0],
            "trend_direction": [0, 0, 0],
            "regime": ["STRONG_BULL", "STRONG_BULL", "STRONG_BULL"],
            "regime_kelly_mult": [1.5, 1.5, 1.5],
            "ma_50d": [106, 104, 106],  # bar 0: 6% above close; bar 1: 4% above
        })
        df.index = pd.RangeIndex(3)

        old_val = getattr(config, "STRONG_BULL_SOFT_50MA_PCT", 0.0)
        try:
            config.STRONG_BULL_SOFT_50MA_PCT = 0.05
            result = generate_trades(df, require_signals=1, use_regime_filter=False,
                                     use_slope_regime=True, longs_only=True)
            # Bar 0: close=100, ma_50d=106 → 6% below → blocked
            self.assertEqual(result.iloc[0]["entry_signal"], 0)
            # Bar 1: close=100, ma_50d=104 → 4% below → NOT blocked
            self.assertEqual(result.iloc[1]["entry_signal"], 1)
        finally:
            config.STRONG_BULL_SOFT_50MA_PCT = old_val

    def test_gate_off_when_zero(self):
        """Gate should be inactive when STRONG_BULL_SOFT_50MA_PCT = 0."""
        from src.strategy.engine import generate_trades
        import config

        df = pd.DataFrame({
            "open": [100], "high": [101], "low": [99], "close": [100],
            "momentum_signal": [1], "volume_signal": [0],
            "vol_regime": [0], "trend_direction": [0],
            "regime": ["STRONG_BULL"], "regime_kelly_mult": [1.5],
            "ma_50d": [110],  # 10% above close — would be blocked if gate on
        })
        df.index = pd.RangeIndex(1)

        old_val = getattr(config, "STRONG_BULL_SOFT_50MA_PCT", 0.0)
        try:
            config.STRONG_BULL_SOFT_50MA_PCT = 0.0
            result = generate_trades(df, require_signals=1, use_regime_filter=False,
                                     use_slope_regime=True, longs_only=True)
            self.assertEqual(result.iloc[0]["entry_signal"], 1)
        finally:
            config.STRONG_BULL_SOFT_50MA_PCT = old_val


    def test_gate_works_without_regime_column_hourly(self):
        """Hourly mode has no regime column — gate should apply to all longs."""
        from src.strategy.engine import generate_trades
        import config

        df = pd.DataFrame({
            "open": [100, 100, 100],
            "high": [101, 101, 101],
            "low": [99, 99, 99],
            "close": [100, 100, 100],
            "momentum_signal": [1, 1, 0],
            "volume_signal": [0, 0, 0],
            "vol_regime": [0, 0, 0],
            "trend_direction": [0, 0, 0],
            # No "regime" column — simulates hourly mode
            "ma_50d": [106, 104, 106],
        })
        df.index = pd.RangeIndex(3)

        old_val = getattr(config, "STRONG_BULL_SOFT_50MA_PCT", 0.0)
        try:
            config.STRONG_BULL_SOFT_50MA_PCT = 0.05
            result = generate_trades(df, require_signals=1, use_regime_filter=False,
                                     use_slope_regime=False, longs_only=True)
            # Bar 0: 6% below → blocked
            self.assertEqual(result.iloc[0]["entry_signal"], 0)
            # Bar 1: 4% below → NOT blocked
            self.assertEqual(result.iloc[1]["entry_signal"], 1)
        finally:
            config.STRONG_BULL_SOFT_50MA_PCT = old_val


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
            # Low=80.35 stays above SL (80.339) so only TP is hit, not ambiguous
            {"open": 80.48, "high": 80.85, "low": 80.35, "close": 80.70, "entry_signal": 0},
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


class TestATRDynamicStops(unittest.TestCase):
    """Verify ATR dynamic stops widen the stop via stop_overrides."""

    def test_stop_override_widens_stop(self):
        """With stop_overrides, a wider stop prevents a stop_hit that would occur
        with the default stop."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            # Signal bar
            {"open": 100, "high": 101, "low": 99, "close": 100, "entry_signal": 1},
            # Entry bar — open=100
            {"open": 100, "high": 100.5, "low": 99.8, "close": 100.2, "entry_signal": 0},
            # Bar 2: low=99.0 — hits default 1.5% stop (98.5) NO, but hits 0.5% stop (99.5) YES
            {"open": 100, "high": 100.3, "low": 99.0, "close": 99.5, "entry_signal": 0},
            # Bar 3: recovery
            {"open": 99.5, "high": 103, "low": 99.4, "close": 102, "entry_signal": 0},
        ])

        # Default stop=0.5%: entry=100, SL=99.50. Bar 2 low=99.0 → stop_hit
        result_default = compute_trade_returns(df, target_gain_pct=0.02, stop_loss_pct=0.005,
                                               max_trade_bars=5)
        self.assertEqual(result_default.iloc[0]["exit_type"], "stop_hit")

        # With widened stop via override: SL=100*(1-0.015)=98.5. Bar 2 low=99.0 → survives
        # Bar 3 high=103 → target at 102 hit
        stop_overrides = {0: 0.015}  # override for signal at index 0
        result_widened = compute_trade_returns(df, target_gain_pct=0.02, stop_loss_pct=0.005,
                                              max_trade_bars=5, stop_overrides=stop_overrides)
        self.assertEqual(result_widened.iloc[0]["exit_type"], "target_hit")

    def test_stop_override_only_affects_specified_trade(self):
        """Override for one trade doesn't affect other trades."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            # Trade 1 (overridden)
            {"open": 100, "high": 101, "low": 99, "close": 100, "entry_signal": 1},
            {"open": 100, "high": 100.5, "low": 99.8, "close": 100, "entry_signal": 0},
            {"open": 100, "high": 100.1, "low": 98, "close": 99, "entry_signal": 0},
            # Trade 2 (not overridden)
            {"open": 99, "high": 100, "low": 98, "close": 99, "entry_signal": 1},
            {"open": 99, "high": 99.5, "low": 98.8, "close": 99, "entry_signal": 0},
            {"open": 99, "high": 99.1, "low": 97, "close": 98, "entry_signal": 0},
        ])

        # Override trade 1 to wide stop; trade 2 keeps default 1%
        stop_overrides = {0: 0.05}
        result = compute_trade_returns(df, target_gain_pct=0.05, stop_loss_pct=0.01,
                                       max_trade_bars=3, stop_overrides=stop_overrides)
        self.assertEqual(len(result), 2)
        # Trade 1: entry=100, override stop=5%, so SL=95. Low=98 → survives → time_exit
        self.assertEqual(result.iloc[0]["exit_type"], "time_exit")
        # Trade 2: entry=99, default stop=1%, SL=98.01. Low=97 → stop_hit
        self.assertEqual(result.iloc[1]["exit_type"], "stop_hit")


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

    def test_pending_close_blocks_then_reconciles(self):
        """Pending close keeps position in DB; finalize records actual PnL."""
        self._state.open_position("TQQQ", 80.50, 10, "999")

        # Mark pending_close — position stays in DB
        self._state.mark_pending_close(estimated_exit_price=80.70)
        pos = self._state.get_position()
        self.assertIsNotNone(pos, "Position must remain in DB while pending_close")
        self.assertEqual(pos.status, "pending_close")
        self.assertAlmostEqual(pos.estimated_exit_price, 80.70)

        # Finalize with actual fill data
        actual_ret = (80.60 - 80.50) / 80.50
        self._state.finalize_pending_close(
            return_pct=actual_ret, exit_type="target_hit", exit_price=80.60,
        )
        pos = self._state.get_position()
        self.assertIsNone(pos, "Position must be removed after finalization")

        summary = self._state.get_trade_summary()
        self.assertEqual(summary["total"], 1)
        self.assertAlmostEqual(summary["total_ret"], actual_ret, places=4)
        self.assertEqual(summary["exit_types"], {"target_hit": 1})

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


class TestOpposingSignalExit(unittest.TestCase):
    """Verify the opposing-signal exit path in compute_trade_returns().

    When use_opposing_signal_exit=True, an open long closes at the NEXT bar's
    open if a future bar's entry_signal is -1 (and vice versa for shorts).
    TP/SL checks still win on the same bar.
    """

    def test_flag_off_is_unchanged(self):
        """With flag OFF, an opposing signal in a future bar has no effect."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            # Bar 0: long signal
            {"open": 99.0, "high": 100.5, "low": 98.5, "close": 100.0, "entry_signal": 1},
            # Bar 1: entry at open=100
            {"open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0, "entry_signal": 0},
            # Bar 2: opposing signal fires here; narrow range (no TP/SL)
            {"open": 100.0, "high": 100.1, "low": 99.9, "close": 100.0, "entry_signal": -1},
            # Bar 3: narrow
            {"open": 100.0, "high": 100.1, "low": 99.9, "close": 100.05, "entry_signal": 0},
        ])

        result = compute_trade_returns(
            df, target_gain_pct=0.05, stop_loss_pct=0.05, max_trade_bars=5,
            use_opposing_signal_exit=False,
        )
        self.assertEqual(len(result), 1)
        # Neither TP nor SL hit, flag off → time_exit
        self.assertEqual(result.iloc[0]["exit_type"], "time_exit")

    def test_long_closes_on_short_signal(self):
        """Long position: opposing signal on bar K → exit at bar K+1 open."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            # Bar 0: long signal
            {"open": 99.0, "high": 100.5, "low": 98.5, "close": 100.0, "entry_signal": 1},
            # Bar 1: entry at open=100
            {"open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0, "entry_signal": 0},
            # Bar 2: opposing short signal (narrow bar, no TP/SL breach)
            {"open": 100.0, "high": 100.3, "low": 99.7, "close": 100.1, "entry_signal": -1},
            # Bar 3: this bar's open is where opposing-signal exit fills
            {"open": 101.0, "high": 101.5, "low": 100.5, "close": 101.0, "entry_signal": 0},
        ])

        result = compute_trade_returns(
            df, target_gain_pct=0.05, stop_loss_pct=0.05, max_trade_bars=5,
            use_opposing_signal_exit=True,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["exit_type"], "opposing_signal")
        # Entry=100, exit=101 → return = +0.01 (long, signed)
        self.assertAlmostEqual(result.iloc[0]["return"], 0.01, places=6)

    def test_short_closes_on_long_signal(self):
        """Short position: opposing (long) signal on bar K → exit at bar K+1 open.
        Requires LONGS_ONLY=False so direction=-1 entries make it through."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            # Bar 0: short signal
            {"open": 101.0, "high": 101.5, "low": 99.5, "close": 100.0, "entry_signal": -1},
            # Bar 1: entry at open=100 (short)
            {"open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0, "entry_signal": 0},
            # Bar 2: opposing long signal (narrow bar)
            {"open": 100.0, "high": 100.3, "low": 99.7, "close": 99.9, "entry_signal": 1},
            # Bar 3: fill here at open=99 → short profits
            {"open": 99.0, "high": 99.5, "low": 98.5, "close": 99.0, "entry_signal": 0},
        ])

        result = compute_trade_returns(
            df, target_gain_pct=0.05, stop_loss_pct=0.05, max_trade_bars=5,
            use_opposing_signal_exit=True,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["exit_type"], "opposing_signal")
        # Short entry=100, exit=99 → signed return = -1 * (99-100)/100 = +0.01
        self.assertAlmostEqual(result.iloc[0]["return"], 0.01, places=6)

    def test_target_hit_beats_opposing_signal_same_bar(self):
        """Hard TP/SL wins over opposing signal on the same bar."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            # Bar 0: long signal
            {"open": 99.0, "high": 100.5, "low": 98.5, "close": 100.0, "entry_signal": 1},
            # Bar 1: entry at open=100
            {"open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0, "entry_signal": 0},
            # Bar 2: TP hit (high=103 >> 100*1.02=102) AND opposing signal present
            {"open": 100.0, "high": 103.0, "low": 99.9, "close": 102.5, "entry_signal": -1},
            {"open": 102.5, "high": 103.0, "low": 102.0, "close": 102.5, "entry_signal": 0},
        ])

        result = compute_trade_returns(
            df, target_gain_pct=0.02, stop_loss_pct=0.02, max_trade_bars=5,
            use_opposing_signal_exit=True,
        )
        self.assertEqual(len(result), 1)
        # TP wins even though opposing signal is on the same bar
        self.assertEqual(result.iloc[0]["exit_type"], "target_hit")
        self.assertAlmostEqual(result.iloc[0]["return"], 0.02, places=6)

    def test_stop_hit_beats_opposing_signal_same_bar(self):
        """Hard SL wins over opposing signal on the same bar (symmetric to TP)."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            # Bar 0: long signal
            {"open": 99.0, "high": 100.5, "low": 98.5, "close": 100.0, "entry_signal": 1},
            # Bar 1: entry at open=100
            {"open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0, "entry_signal": 0},
            # Bar 2: SL hit (low=97 << 100*0.98=98) AND opposing signal
            {"open": 100.0, "high": 100.1, "low": 97.0, "close": 98.0, "entry_signal": -1},
            {"open": 98.0, "high": 98.5, "low": 97.5, "close": 98.0, "entry_signal": 0},
        ])

        result = compute_trade_returns(
            df, target_gain_pct=0.02, stop_loss_pct=0.02, max_trade_bars=5,
            use_opposing_signal_exit=True,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["exit_type"], "stop_hit")
        self.assertAlmostEqual(result.iloc[0]["return"], -0.02, places=6)

    def test_opposing_signal_on_last_bar_falls_through_to_time_exit(self):
        """If the opposing signal fires on the final future bar, there's no
        next bar to fill at → the code falls through to time_exit."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            # Bar 0: long signal
            {"open": 99.0, "high": 100.5, "low": 98.5, "close": 100.0, "entry_signal": 1},
            # Bar 1: entry at open=100
            {"open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0, "entry_signal": 0},
            # Bar 2: opposing signal on the LAST bar of the dataframe — no bar 3.
            {"open": 100.0, "high": 100.3, "low": 99.7, "close": 100.2, "entry_signal": -1},
        ])

        result = compute_trade_returns(
            df, target_gain_pct=0.05, stop_loss_pct=0.05, max_trade_bars=5,
            use_opposing_signal_exit=True,
        )
        self.assertEqual(len(result), 1)
        # No next bar for the opposing-signal fill → fell through to time_exit
        self.assertEqual(result.iloc[0]["exit_type"], "time_exit")
        # Time exit uses last close = 100.2 → return = (100.2-100)/100 = 0.002
        self.assertAlmostEqual(result.iloc[0]["return"], 0.002, places=6)

    def test_only_triggers_on_directional_mismatch(self):
        """A same-direction signal (long while long) must NOT trigger exit."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            # Bar 0: long signal
            {"open": 99.0, "high": 100.5, "low": 98.5, "close": 100.0, "entry_signal": 1},
            # Bar 1: entry at open=100
            {"open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0, "entry_signal": 0},
            # Bar 2: ANOTHER long signal (same direction — should NOT exit)
            {"open": 100.0, "high": 100.3, "low": 99.7, "close": 100.1, "entry_signal": 1},
            # Bar 3: final bar
            {"open": 100.1, "high": 100.2, "low": 100.0, "close": 100.15, "entry_signal": 0},
        ])

        result = compute_trade_returns(
            df, target_gain_pct=0.05, stop_loss_pct=0.05, max_trade_bars=5,
            use_opposing_signal_exit=True,
        )
        # Same-direction bars don't trigger exit; time_exit fires at last close.
        # Note: two entry signals → two trades; we only check that NEITHER is labeled
        # "opposing_signal".
        self.assertNotIn("opposing_signal", set(result["exit_type"].values))

    def test_reads_signal_vote_when_present_not_entry_signal(self):
        """Production path: generate_trades() writes both signal_vote (raw
        composite) and entry_signal (post-regime-gate). When signal_vote is
        present, compute_trade_returns must read from it, not entry_signal.

        This is the bug that made opposing_signal_exit never fire for TQQQ:
        use_regime_filter=True forces longs and shorts to never coexist in
        entry_signal (different trend_direction), but signal_vote keeps the
        raw direction. The exit must fire on the raw vote flip."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            # Bar 0: long entry — entry_signal=+1, signal_vote=+1
            {"open": 99.0, "high": 100.5, "low": 98.5, "close": 100.0, "entry_signal": 1},
            # Bar 1: entry at open=100
            {"open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0, "entry_signal": 0},
            # Bar 2: regime filter ZEROED entry_signal, but signal_vote shows -1
            # (momentum+volume still voted opposite). Flag should still fire here.
            {"open": 100.0, "high": 100.3, "low": 99.7, "close": 100.1, "entry_signal": 0},
            # Bar 3: opposing-signal fills at this open
            {"open": 101.0, "high": 101.5, "low": 100.5, "close": 101.0, "entry_signal": 0},
        ])
        # Populate signal_vote with the pre-gate truth: long, neutral, short, neutral.
        df["signal_vote"] = [1, 0, -1, 0]

        result = compute_trade_returns(
            df, target_gain_pct=0.05, stop_loss_pct=0.05, max_trade_bars=5,
            use_opposing_signal_exit=True,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["exit_type"], "opposing_signal")
        # Entry=100, exit=101 → +0.01 (signal_vote drove the exit, not entry_signal)
        self.assertAlmostEqual(result.iloc[0]["return"], 0.01, places=6)

    def test_threshold_respects_require_signals(self):
        """Opposing-signal exit should only fire when |signal_vote| >= threshold,
        matching the require_signals used at entry. A threshold=2 run must NOT
        exit on a single-signal vote of -1."""
        from src.strategy.engine import compute_trade_returns

        df = _make_ohlcv([
            {"open": 99.0, "high": 100.5, "low": 98.5, "close": 100.0, "entry_signal": 1},
            {"open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0, "entry_signal": 0},
            # Bar 2: signal_vote=-1 (only one signal fired). threshold=2 should IGNORE.
            {"open": 100.0, "high": 100.3, "low": 99.7, "close": 100.1, "entry_signal": 0},
            {"open": 101.0, "high": 101.5, "low": 100.5, "close": 101.0, "entry_signal": 0},
        ])
        df["signal_vote"] = [1, 0, -1, 0]

        result = compute_trade_returns(
            df, target_gain_pct=0.05, stop_loss_pct=0.05, max_trade_bars=5,
            use_opposing_signal_exit=True,
            opposing_signal_threshold=2,
        )
        self.assertEqual(len(result), 1)
        # Vote=-1 < threshold=2 → no opposing exit → falls through to time_exit
        self.assertEqual(result.iloc[0]["exit_type"], "time_exit")


if __name__ == "__main__":
    unittest.main()
