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


def add_momentum_features(df: pd.DataFrame,
                           rsi_period: int = 14,
                           macd_fast: int = 12,
                           macd_slow: int = 26,
                           macd_signal_period: int = 9,
                           roc_period: int = 10,
                           rsi_oversold: float = 35,
                           rsi_overbought: float = 65,
                           ma_regime_window: int = 252) -> pd.DataFrame:
    """Add all momentum columns to a DataFrame in place."""
    df = df.copy()
    df["rsi"] = compute_rsi(df["close"], period=rsi_period)
    df["macd"], df["macd_signal"], df["macd_hist"] = compute_macd(
        df["close"], fast=macd_fast, slow=macd_slow, signal=macd_signal_period
    )
    df["roc_10"] = compute_roc(df["close"], roc_period)
    df["roc_20"] = compute_roc(df["close"], roc_period * 2)
    df["momentum_signal"] = momentum_signal(df, rsi_oversold=rsi_oversold, rsi_overbought=rsi_overbought)
    df["ma_52w"] = df["close"].rolling(ma_regime_window, min_periods=1).mean()
    df["ma_regime"] = compute_ma_regime(df["close"], window=ma_regime_window)
    return df
