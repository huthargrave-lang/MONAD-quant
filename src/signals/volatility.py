"""
MONAD Quant - Volatility Signals
ATR, Bollinger Bands, regime detection
"""

import pandas as pd
import numpy as np


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range."""
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def compute_bollinger_bands(prices: pd.Series, window: int = 20, num_std: float = 2.0):
    """Returns (upper, middle, lower) Bollinger Bands."""
    sma = prices.rolling(window).mean()
    std = prices.rolling(window).std()
    upper = sma + num_std * std
    lower = sma - num_std * std
    return upper, sma, lower


def compute_bb_width(prices: pd.Series, window: int = 20) -> pd.Series:
    """Bollinger Band width — proxy for volatility regime."""
    upper, mid, lower = compute_bollinger_bands(prices, window)
    return (upper - lower) / mid


def compute_bb_position(prices: pd.Series, window: int = 20) -> pd.Series:
    """%B — where price sits within Bollinger Bands (0=lower, 1=upper)."""
    upper, mid, lower = compute_bollinger_bands(prices, window)
    return (prices - lower) / (upper - lower)


def volatility_regime(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """
    Classify market regime by Bollinger Band width.
    Returns: 1 = trending (wide bands), 0 = ranging (tight bands)
    min_periods=20 so it works on short datasets; was rolling(100) with no min.
    """
    bb_width = compute_bb_width(df["close"], window)
    median_width = bb_width.rolling(40, min_periods=20).median()
    return (bb_width > median_width).astype(int)


def trend_direction(df: pd.DataFrame, period: int = 200) -> pd.Series:
    """
    Directional trend regime using SMA.
    Returns: 1 = bull (close above SMA), -1 = bear (close below SMA)
    """
    sma = df["close"].rolling(period).mean()
    direction = pd.Series(0, index=df.index)
    direction[df["close"] > sma] = 1
    direction[df["close"] < sma] = -1
    return direction


def add_volatility_features(df: pd.DataFrame, trend_sma_period: int = 200) -> pd.DataFrame:
    df = df.copy()
    df["atr"] = compute_atr(df)
    df["atr_pct"] = df["atr"] / df["close"]  # normalized ATR
    upper, mid, lower = compute_bollinger_bands(df["close"])
    df["bb_upper"] = upper
    df["bb_mid"] = mid
    df["bb_lower"] = lower
    df["bb_width"] = compute_bb_width(df["close"])
    df["bb_position"] = compute_bb_position(df["close"])
    df["vol_regime"] = volatility_regime(df)
    df["trend_direction"] = trend_direction(df, period=trend_sma_period)
    return df
