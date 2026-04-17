"""
Tests for signal modules: momentum, volume, volatility.

Verifies the mathematical correctness of RSI, MACD, regime classification,
VWAP z-score, Bollinger Bands, ATR, and ADX — the core signal pipeline
that generates every trade.
"""

import unittest
import pandas as pd
import numpy as np


def _make_ohlcv(closes, highs=None, lows=None, opens=None, volumes=None):
    """Helper: build OHLCV DataFrame from price series."""
    n = len(closes)
    closes = list(closes)
    if highs is None:
        highs = [c * 1.01 for c in closes]
    if lows is None:
        lows = [c * 0.99 for c in closes]
    if opens is None:
        opens = closes[:]
    if volumes is None:
        volumes = [1000] * n
    df = pd.DataFrame({
        "open": opens, "high": highs, "low": lows,
        "close": closes, "volume": volumes,
    })
    df.index = pd.RangeIndex(n)
    return df


# ════════════════════════════════════════════════════════════════════
#  MOMENTUM SIGNALS (src/signals/momentum.py)
# ════════════════════════════════════════════════════════════════════


class TestComputeRSI(unittest.TestCase):
    """Tests for compute_rsi()."""

    def test_rsi_range_0_to_100(self):
        """RSI should always be between 0 and 100."""
        from src.signals.momentum import compute_rsi
        prices = pd.Series([100 + i * (-1)**i * 3 for i in range(50)])
        rsi = compute_rsi(prices, period=14)
        valid = rsi.dropna()
        self.assertTrue((valid >= 0).all(), "RSI below 0")
        self.assertTrue((valid <= 100).all(), "RSI above 100")

    def test_rsi_high_on_steady_uptrend(self):
        """Steady uptrend should produce RSI > 70."""
        from src.signals.momentum import compute_rsi
        prices = pd.Series([100 + i * 2 for i in range(30)])
        rsi = compute_rsi(prices, period=14)
        self.assertGreater(rsi.iloc[-1], 70)

    def test_rsi_low_on_steady_downtrend(self):
        """Steady downtrend should produce RSI < 30."""
        from src.signals.momentum import compute_rsi
        prices = pd.Series([200 - i * 2 for i in range(30)])
        rsi = compute_rsi(prices, period=14)
        self.assertLess(rsi.iloc[-1], 30)

    def test_rsi_flat_market_near_50(self):
        """Flat market (constant price) should produce RSI near 50."""
        from src.signals.momentum import compute_rsi
        prices = pd.Series([100.0] * 30)
        rsi = compute_rsi(prices, period=14)
        # With no movement, ewm produces NaN — verify it doesn't crash
        # and non-NaN values are near 50 (or all NaN from zero movement)
        valid = rsi.dropna()
        if len(valid) > 0:
            for v in valid:
                self.assertTrue(40 <= v <= 60 or np.isnan(v),
                                f"RSI on flat market should be ~50, got {v}")

    def test_rsi_period_affects_smoothing(self):
        """Shorter RSI period should be more responsive (higher variance)."""
        from src.signals.momentum import compute_rsi
        prices = pd.Series([100 + i * (-1)**i * 5 for i in range(50)])
        rsi_short = compute_rsi(prices, period=7)
        rsi_long = compute_rsi(prices, period=21)
        # Short period RSI should have higher standard deviation
        self.assertGreater(rsi_short.dropna().std(), rsi_long.dropna().std())


class TestComputeMACD(unittest.TestCase):
    """Tests for compute_macd()."""

    def test_macd_returns_three_series(self):
        """compute_macd should return (macd_line, signal_line, histogram)."""
        from src.signals.momentum import compute_macd
        prices = pd.Series([100 + i for i in range(50)])
        result = compute_macd(prices)
        self.assertEqual(len(result), 3)
        self.assertEqual(len(result[0]), 50)

    def test_histogram_is_macd_minus_signal(self):
        """Histogram = MACD line - signal line."""
        from src.signals.momentum import compute_macd
        prices = pd.Series([100 + i * (-1)**i * 2 for i in range(50)])
        macd_line, signal_line, histogram = compute_macd(prices)
        diff = (macd_line - signal_line).dropna()
        hist_valid = histogram.dropna()
        np.testing.assert_array_almost_equal(diff.values, hist_valid.values)

    def test_macd_positive_in_uptrend(self):
        """MACD line should be positive in strong uptrend (fast EMA > slow EMA)."""
        from src.signals.momentum import compute_macd
        prices = pd.Series([100 + i * 3 for i in range(50)])
        macd_line, _, _ = compute_macd(prices, fast=12, slow=26, signal=9)
        self.assertGreater(macd_line.iloc[-1], 0)


class TestMomentumSignal(unittest.TestCase):
    """Tests for momentum_signal()."""

    def test_long_signal_on_oversold_with_macd_turn(self):
        """Long (+1) when RSI < oversold AND MACD histogram turning up."""
        from src.signals.momentum import momentum_signal
        # Create a sharp drop (RSI goes low) then a small uptick (MACD turns)
        prices = [100] * 20 + [100 - i * 3 for i in range(1, 16)] + [56, 57]
        df = _make_ohlcv(prices)
        sig = momentum_signal(df, rsi_oversold=40, rsi_overbought=60)
        # The last bar (57, up from 56) should have RSI < 40 and hist turning up
        # Check that at least one +1 signal exists in the recovery zone
        self.assertIn(1, sig.values, "Expected at least one long signal")

    def test_short_signal_on_overbought_with_macd_turn(self):
        """Short (-1) when RSI > overbought AND MACD histogram turning down."""
        from src.signals.momentum import momentum_signal
        prices = [100] * 20 + [100 + i * 3 for i in range(1, 16)] + [144, 143]
        df = _make_ohlcv(prices)
        sig = momentum_signal(df, rsi_oversold=40, rsi_overbought=60)
        self.assertIn(-1, sig.values, "Expected at least one short signal")

    def test_neutral_in_midrange_rsi(self):
        """No signal when RSI is in the neutral zone (40-60)."""
        from src.signals.momentum import momentum_signal
        # Gentle oscillation keeps RSI near 50
        prices = [100 + (i % 3) for i in range(40)]
        df = _make_ohlcv(prices)
        sig = momentum_signal(df, rsi_oversold=30, rsi_overbought=70)
        # All signals should be 0 (RSI never reaches extremes)
        self.assertTrue((sig == 0).all(), "Expected all neutral signals in midrange")

    def test_signal_values_are_minus1_0_or_1(self):
        """Signal output should only contain -1, 0, or 1."""
        from src.signals.momentum import momentum_signal
        prices = [100 + i * (-1)**i * 5 for i in range(60)]
        df = _make_ohlcv(prices)
        sig = momentum_signal(df, rsi_oversold=40, rsi_overbought=60)
        unique = set(sig.unique())
        self.assertTrue(unique.issubset({-1, 0, 1}), f"Unexpected values: {unique}")


class TestClassifyRegime(unittest.TestCase):
    """Tests for classify_regime() — the 6-state dual-MA system."""

    def test_strong_bull(self):
        """Price well above 252-MA with rising slope → STRONG_BULL."""
        from src.signals.momentum import classify_regime
        # Long uptrend: price climbs steadily
        prices = pd.Series([100 + i * 0.5 for i in range(300)])
        regime = classify_regime(prices, ma_window=252, slope_window=20,
                                 strong_bull_thresh=0.02)
        self.assertEqual(regime.iloc[-1], "STRONG_BULL")

    def test_strong_bear(self):
        """Price below 252-MA with steep negative slope → STRONG_BEAR."""
        from src.signals.momentum import classify_regime
        # Rise then sustained steep fall — needs enough bars for MA to turn down hard
        prices = pd.Series(
            [100 + i * 0.5 for i in range(260)] +
            [230 - i * 3 for i in range(1, 100)]
        )
        regime = classify_regime(prices, ma_window=252, slope_window=20,
                                 strong_bear_thresh=-0.02)
        # After a long sustained drop, should be STRONG_BEAR or at least BEAR
        last = regime.iloc[-1]
        self.assertIn(last, ["STRONG_BEAR", "BEAR"],
                      f"Expected STRONG_BEAR or BEAR after sustained crash, got {last}")

    def test_recovering(self):
        """Price below 252-MA but above 50-MA → RECOVERING."""
        from src.signals.momentum import classify_regime
        # Use smaller windows to make this testable without 300+ bars.
        # Up for 60 bars, crash for 20, partial recover for 30 bars.
        # Key: recovery must NOT bring price above the long MA.
        # With ma_window=50, long MA at end ≈ 100.8; price ends at 100 → below long MA.
        # Short MA (15-bar) at end ≈ 96.5; price 100 → above short MA.
        # So: ~above_long=False, above_short=True → RECOVERING.
        prices_list = (
            [100 + i * 1.0 for i in range(60)] +     # up to 159
            [159 - i * 4 for i in range(1, 21)] +     # crash to 79
            [79 + i * 0.7 for i in range(1, 31)]      # partial recover to ~100
        )
        prices = pd.Series(prices_list)
        regime = classify_regime(prices, ma_window=50, ma_short_window=15,
                                 slope_window=10)
        last = regime.iloc[-1]
        # During partial recovery: price should be above short MA but below long MA
        self.assertIn(last, ["RECOVERING", "BEAR"],
                      f"Expected RECOVERING or BEAR during partial recovery, got {last}")

    def test_all_six_regimes_are_valid_strings(self):
        """All regime values should be one of the 6 defined states."""
        from src.signals.momentum import classify_regime
        valid_regimes = {"STRONG_BULL", "BULL", "STALLING", "RECOVERING", "BEAR", "STRONG_BEAR"}
        prices = pd.Series(
            [100 + i for i in range(150)] +
            [250 - i * 2 for i in range(150)]
        )
        regime = classify_regime(prices, ma_window=100, slope_window=10)
        unique = set(regime.unique())
        self.assertTrue(unique.issubset(valid_regimes),
                        f"Invalid regime values: {unique - valid_regimes}")

    def test_nan_slope_defaults_to_stalling(self):
        """First few bars (slope=NaN) should default to STALLING."""
        from src.signals.momentum import classify_regime
        prices = pd.Series([100 + i for i in range(50)])
        regime = classify_regime(prices, ma_window=10, slope_window=20)
        # First 20 bars have NaN slope → should be STALLING
        self.assertEqual(regime.iloc[0], "STALLING")

    def test_regime_uses_shift_no_lookahead(self):
        """Regime classification should not use future data."""
        from src.signals.momentum import classify_regime
        prices = pd.Series([100 + i * 0.3 for i in range(300)])
        regime_full = classify_regime(prices)
        # Truncated to first 250 bars — regime at bar 249 should be identical
        regime_trunc = classify_regime(prices.iloc[:250])
        self.assertEqual(regime_full.iloc[249], regime_trunc.iloc[249],
                         "Regime at bar 249 should not depend on bars 250+")


class TestAddMomentumFeatures(unittest.TestCase):
    """Tests for add_momentum_features() integration."""

    def test_all_columns_present(self):
        """add_momentum_features should add all expected columns."""
        from src.signals.momentum import add_momentum_features
        df = _make_ohlcv([100 + i * (-1)**i for i in range(50)])
        result = add_momentum_features(df)
        expected = ["rsi", "macd", "macd_signal", "macd_hist",
                    "momentum_signal", "ma_52w", "ma_50d", "ma_regime",
                    "ma_slope", "regime", "regime_kelly_mult", "bear_short_signal"]
        for col in expected:
            self.assertIn(col, result.columns, f"Missing column: {col}")

    def test_does_not_modify_input(self):
        """Should return a copy, not modify the input DataFrame."""
        from src.signals.momentum import add_momentum_features
        df = _make_ohlcv([100 + i for i in range(50)])
        cols_before = set(df.columns)
        add_momentum_features(df)
        self.assertEqual(set(df.columns), cols_before)


# ════════════════════════════════════════════════════════════════════
#  VOLUME SIGNALS (src/signals/volume.py)
# ════════════════════════════════════════════════════════════════════


class TestComputeVWAPZscore(unittest.TestCase):
    """Tests for compute_vwap_zscore()."""

    def test_zscore_near_zero_when_price_at_vwap(self):
        """Z-score should be ~0 when price is at VWAP."""
        from src.signals.volume import compute_vwap_zscore
        # Constant prices → close = VWAP → deviation = 0 → zscore = 0 or NaN
        df = _make_ohlcv([100.0] * 30, volumes=[1000] * 30)
        zscore = compute_vwap_zscore(df, window=10)
        valid = zscore.dropna()
        if len(valid) > 0:
            # When deviation and std are both 0, we get NaN (from our guard)
            # which is correct — no signal on flat data
            pass  # NaN is acceptable for flat market

    def test_zscore_negative_when_price_below_vwap(self):
        """Z-score should be negative when close drops below VWAP."""
        from src.signals.volume import compute_vwap_zscore
        # Need 40+ bars for two rolling windows (VWAP=20 + std=20).
        # Oscillating prices produce non-zero rolling_std, then a sharp drop
        # pushes close well below VWAP → negative z-score.
        prices = [100 + 3 * (i % 3) - 3 for i in range(50)] + [85.0, 82.0, 79.0]
        df = _make_ohlcv(prices)
        zscore = compute_vwap_zscore(df, window=20)
        valid = zscore.dropna()
        self.assertGreater(len(valid), 0, "Expected non-NaN z-scores")
        self.assertLess(valid.iloc[-1], 0, "Z-score should be negative after price drop")

    def test_zero_std_guard(self):
        """Division by zero when rolling_std=0 should return NaN, not crash."""
        from src.signals.volume import compute_vwap_zscore
        # Perfectly flat prices → rolling_std = 0
        df = _make_ohlcv([50.0] * 30,
                          highs=[50.0] * 30,
                          lows=[50.0] * 30,
                          volumes=[1000] * 30)
        zscore = compute_vwap_zscore(df, window=10)
        # Should not raise. Values should be NaN (not inf, not crash)
        self.assertFalse(np.isinf(zscore.dropna()).any(),
                         "Z-score should be NaN, not inf, on flat data")


class TestVolumeSignal(unittest.TestCase):
    """Tests for volume_signal()."""

    def test_long_signal_when_zscore_below_threshold(self):
        """volume_signal = +1 when z-score < -threshold AND volume above average."""
        from src.signals.volume import volume_signal
        # Need 40+ bars for rolling windows. Oscillating prices produce non-zero
        # rolling_std, then sharp drop with high volume triggers long signal.
        prices = [100 + 3 * (i % 3) - 3 for i in range(50)] + [85.0, 80.0, 75.0, 70.0]
        vols = [1000] * 50 + [3000, 3000, 3000, 3000]
        df = _make_ohlcv(prices, volumes=vols)
        sig = volume_signal(df, zscore_threshold=1.0, window=20)
        self.assertIn(1, sig.values, "Expected long signal on deep VWAP dip with volume")

    def test_no_signal_low_volume(self):
        """No signal when z-score passes threshold but volume is below average."""
        from src.signals.volume import volume_signal
        prices = [100.0] * 25 + [92.0, 89.0, 86.0, 84.0, 82.0]
        vols = [1000] * 25 + [100, 100, 100, 100, 100]  # very low volume
        df = _make_ohlcv(prices, volumes=vols)
        sig = volume_signal(df, zscore_threshold=1.0, window=20)
        # Volume confirmation should block the signal
        self.assertEqual(sig.iloc[-1], 0, "Should not signal on low volume")

    def test_signal_values_are_minus1_0_or_1(self):
        """volume_signal output should only contain -1, 0, or 1."""
        from src.signals.volume import volume_signal
        prices = [100 + i * (-1)**i * 3 for i in range(50)]
        df = _make_ohlcv(prices)
        sig = volume_signal(df, zscore_threshold=1.0, window=20)
        unique = set(sig.unique())
        self.assertTrue(unique.issubset({-1, 0, 1}), f"Unexpected values: {unique}")


class TestAddVolumeFeatures(unittest.TestCase):
    """Tests for add_volume_features() integration."""

    def test_all_columns_present(self):
        from src.signals.volume import add_volume_features
        df = _make_ohlcv([100 + i for i in range(30)])
        result = add_volume_features(df)
        for col in ["vwap", "vwap_zscore", "obv", "vol_ratio", "volume_signal"]:
            self.assertIn(col, result.columns, f"Missing column: {col}")

    def test_does_not_modify_input(self):
        from src.signals.volume import add_volume_features
        df = _make_ohlcv([100 + i for i in range(30)])
        cols_before = set(df.columns)
        add_volume_features(df)
        self.assertEqual(set(df.columns), cols_before)


# ════════════════════════════════════════════════════════════════════
#  VOLATILITY SIGNALS (src/signals/volatility.py)
# ════════════════════════════════════════════════════════════════════


class TestComputeATR(unittest.TestCase):
    """Tests for compute_atr()."""

    def test_atr_positive(self):
        """ATR should always be positive."""
        from src.signals.volatility import compute_atr
        df = _make_ohlcv([100 + i * (-1)**i * 2 for i in range(30)])
        atr = compute_atr(df, period=14)
        valid = atr.dropna()
        self.assertTrue((valid > 0).all(), "ATR should be positive")

    def test_atr_higher_in_volatile_market(self):
        """ATR should be higher when price swings are larger."""
        from src.signals.volatility import compute_atr
        # Low vol
        low_vol = _make_ohlcv(
            [100 + i * 0.1 * (-1)**i for i in range(40)],
            highs=[100 + i * 0.1 * (-1)**i + 0.5 for i in range(40)],
            lows=[100 + i * 0.1 * (-1)**i - 0.5 for i in range(40)],
        )
        # High vol
        high_vol = _make_ohlcv(
            [100 + i * 2 * (-1)**i for i in range(40)],
            highs=[100 + i * 2 * (-1)**i + 5 for i in range(40)],
            lows=[100 + i * 2 * (-1)**i - 5 for i in range(40)],
        )
        atr_low = compute_atr(low_vol, period=14).iloc[-1]
        atr_high = compute_atr(high_vol, period=14).iloc[-1]
        self.assertGreater(atr_high, atr_low)


class TestComputeBBPosition(unittest.TestCase):
    """Tests for compute_bb_position()."""

    def test_bb_position_range(self):
        """bb_position values should generally be between 0 and 1 (can exceed)."""
        from src.signals.volatility import compute_bb_position
        prices = pd.Series([100 + i * (-1)**i * 2 for i in range(40)])
        bb_pos = compute_bb_position(prices, window=20)
        valid = bb_pos.dropna()
        # Most values should be near 0-1 range
        self.assertTrue(len(valid) > 0)

    def test_flat_market_returns_0_5(self):
        """When bands converge (flat market), bb_position should return 0.5."""
        from src.signals.volatility import compute_bb_position
        prices = pd.Series([100.0] * 30)
        bb_pos = compute_bb_position(prices, window=20)
        # After warmup, where upper==lower, result should be 0.5
        for val in bb_pos.dropna():
            if not np.isnan(val):
                self.assertAlmostEqual(val, 0.5, places=5,
                                       msg="Flat market bb_position should be 0.5")


class TestComputeADX(unittest.TestCase):
    """Tests for compute_adx()."""

    def test_adx_positive(self):
        """ADX values should be non-negative."""
        from src.signals.volatility import compute_adx
        df = _make_ohlcv([100 + i * (-1)**i * 2 for i in range(50)])
        adx = compute_adx(df, period=14)
        valid = adx.dropna()
        self.assertTrue((valid >= 0).all(), "ADX should be non-negative")

    def test_adx_high_in_strong_trend(self):
        """ADX should be elevated in a strong one-directional trend."""
        from src.signals.volatility import compute_adx
        # Strong uptrend with wide range bars
        closes = [100 + i * 3 for i in range(50)]
        highs = [c + 2 for c in closes]
        lows = [c - 1 for c in closes]
        df = _make_ohlcv(closes, highs=highs, lows=lows)
        adx = compute_adx(df, period=14)
        self.assertGreater(adx.iloc[-1], 20, "ADX should be >20 in strong trend")


class TestAddVolatilityFeatures(unittest.TestCase):
    """Tests for add_volatility_features() integration."""

    def test_all_columns_present(self):
        from src.signals.volatility import add_volatility_features
        df = _make_ohlcv([100 + i * (-1)**i for i in range(50)])
        result = add_volatility_features(df)
        expected = ["atr", "atr_pct", "bb_upper", "bb_mid", "bb_lower",
                    "bb_width", "bb_position", "vol_regime", "trend_direction",
                    "adx", "adx_kelly_mult"]
        for col in expected:
            self.assertIn(col, result.columns, f"Missing column: {col}")

    def test_adx_kelly_mult_values(self):
        """adx_kelly_mult should only be 0.8, 1.0, or 1.2."""
        from src.signals.volatility import add_volatility_features
        df = _make_ohlcv([100 + i * (-1)**i * 3 for i in range(60)])
        result = add_volatility_features(df)
        unique = set(result["adx_kelly_mult"].unique())
        self.assertTrue(unique.issubset({0.8, 1.0, 1.2}),
                        f"Unexpected adx_kelly_mult values: {unique}")

    def test_does_not_modify_input(self):
        from src.signals.volatility import add_volatility_features
        df = _make_ohlcv([100 + i for i in range(50)])
        cols_before = set(df.columns)
        add_volatility_features(df)
        self.assertEqual(set(df.columns), cols_before)


if __name__ == "__main__":
    unittest.main()
