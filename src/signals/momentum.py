"""
MONAD Quant - Momentum Signals
RSI divergence, MACD crossovers, Rate of Change
"""

import pandas as pd
import numpy as np


def compute_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_roc(prices: pd.Series, period: int = 10) -> pd.Series:
    """Rate of Change - % price change over N periods."""
    return prices.pct_change(periods=period) * 100


def momentum_signal(df: pd.DataFrame, 
                    rsi_oversold: float = 35, 
                    rsi_overbought: float = 65) -> pd.Series:
    """
    Composite momentum signal.
    Returns: 1 (long), -1 (short), 0 (neutral)
    """
    close = df["close"]

    rsi = compute_rsi(close)
    macd_line, signal_line, hist = compute_macd(close)
    roc = compute_roc(close)

    signal = pd.Series(0, index=df.index)

    # Long: RSI oversold + MACD histogram turning up (reversal detection)
    # Using hist > hist.shift(1) instead of roc > 0 so the signal fires at
    # the turning point from oversold — not after price is already recovering,
    # which contradicts an oversold RSI reading in bear conditions.
    long_cond = (
        (rsi < rsi_oversold) &
        (hist > hist.shift(1))
    )

    # Short: RSI overbought + MACD histogram turning down
    short_cond = (
        (rsi > rsi_overbought) &
        (hist < hist.shift(1))
    )

    signal[long_cond] = 1
    signal[short_cond] = -1

    return signal


def compute_ma_regime(prices: pd.Series, window: int = 252) -> pd.Series:
    """
    52-week (252-bar) moving average regime.
    Returns +1 when price is above the MA (bull), -1 when below (bear).
    Uses min_periods=1 so it degrades gracefully on short datasets.
    """
    ma = prices.rolling(window, min_periods=1).mean()
    return np.where(prices >= ma, 1, -1)


def compute_ma_slope(prices: pd.Series,
                     ma_window: int = 252,
                     slope_window: int = 20) -> pd.Series:
    """
    Rate of change of the rolling MA over slope_window bars.
    e.g. 0.02 = MA rose 2% over the last 20 bars.
    NaN for the first slope_window rows — those default to NEUTRAL in classify_regime.
    """
    ma = prices.rolling(ma_window, min_periods=1).mean()
    return ma.pct_change(periods=slope_window)


def classify_regime(prices: pd.Series,
                    ma_window: int = 252,
                    slope_window: int = 20,
                    strong_bull_thresh: float = 0.02,
                    strong_bear_thresh: float = -0.02) -> pd.Series:
    """
    6-state slope-based MA regime classifier.
    Returns pd.Series of str.

    STRONG_BULL : price > MA  AND slope >  +thresh   (trend accelerating up)
    BULL        : price > MA  AND slope >= 0          (trend steady upward)
    STALLING    : price > MA  AND slope <  0          (overextended; MA rolling over)
                  → both long & short allowed (fade the stall)
    RECOVERING  : price < MA  AND slope >= 0          (price rising back toward MA)
                  → LONGS ONLY; shorts fight recovery momentum and lose
    BEAR        : price < MA  AND slope <  0          (declining)
    STRONG_BEAR : price < MA  AND slope < -thresh     (trend accelerating down)

    NaN slope rows (first slope_window bars) → STALLING (both directions, sized 0.75×).
    """
    ma = prices.rolling(ma_window, min_periods=1).mean()
    slope = ma.pct_change(periods=slope_window)
    above_ma = prices >= ma

    regime = pd.Series("STALLING", index=prices.index, dtype=object)
    regime[above_ma & (slope >= 0) & (slope <= strong_bull_thresh)] = "BULL"
    regime[above_ma & (slope > strong_bull_thresh)]                  = "STRONG_BULL"
    # above_ma & slope < 0  → stays "STALLING"

    regime[~above_ma & (slope >= 0)]                                 = "RECOVERING"
    regime[~above_ma & (slope < 0) & (slope >= strong_bear_thresh)]  = "BEAR"
    regime[~above_ma & (slope < strong_bear_thresh)]                 = "STRONG_BEAR"
    return regime


_DEFAULT_REGIME_KELLY_MAP = {
    "STRONG_BULL": 1.5,
    "BULL":        1.0,
    "STALLING":    0.75,   # above MA but losing momentum — fade both ways, cautious
    "RECOVERING":  0.75,   # below MA but rising — longs only, cautious
    "BEAR":        0.75,
    "STRONG_BEAR": 0.5,
}


def add_momentum_features(df: pd.DataFrame,
                           rsi_period: int = 14,
                           macd_fast: int = 12,
                           macd_slow: int = 26,
                           macd_signal_period: int = 9,
                           roc_period: int = 10,
                           rsi_oversold: float = 35,
                           rsi_overbought: float = 65,
                           ma_regime_window: int = 252,
                           slope_window: int = 20,
                           strong_bull_thresh: float = 0.02,
                           strong_bear_thresh: float = -0.02,
                           kelly_mult_map: dict = None) -> pd.DataFrame:
    """Add all momentum columns to a DataFrame.

    New columns: ma_slope, regime, regime_kelly_mult
    """
    if kelly_mult_map is None:
        kelly_mult_map = _DEFAULT_REGIME_KELLY_MAP

    df = df.copy()
    df["rsi"] = compute_rsi(df["close"], period=rsi_period)
    df["macd"], df["macd_signal"], df["macd_hist"] = compute_macd(
        df["close"], fast=macd_fast, slow=macd_slow, signal=macd_signal_period
    )
    df["roc_10"] = compute_roc(df["close"], roc_period)
    df["roc_20"] = compute_roc(df["close"], roc_period * 2)
    df["momentum_signal"] = momentum_signal(df, rsi_oversold=rsi_oversold,
                                             rsi_overbought=rsi_overbought)
    df["ma_52w"]    = df["close"].rolling(ma_regime_window, min_periods=1).mean()
    df["ma_regime"] = compute_ma_regime(df["close"], window=ma_regime_window)

    # Slope-based regime classifier
    df["ma_slope"] = compute_ma_slope(df["close"],
                                      ma_window=ma_regime_window,
                                      slope_window=slope_window)
    df["regime"]   = classify_regime(df["close"],
                                     ma_window=ma_regime_window,
                                     slope_window=slope_window,
                                     strong_bull_thresh=strong_bull_thresh,
                                     strong_bear_thresh=strong_bear_thresh)
    df["regime_kelly_mult"] = df["regime"].map(kelly_mult_map).fillna(1.0)
    return df
