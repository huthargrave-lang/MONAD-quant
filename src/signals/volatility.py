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


def compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Wilder's Average Directional Index — trend strength (0-100), direction-agnostic.
    <20 = choppy/no trend, 20-35 = moderate, >35 = strong trend.

    Steps:
      1. True Range (same numerator as ATR)
      2. +DM / -DM directional movement
      3. Wilder smoothing via EWM(com=period-1) for TR, +DM, -DM
      4. +DI, -DI, DX, then ADX = EWM(DX)
    """
    high  = df["high"]
    low   = df["low"]
    close = df["close"]

    high_low   = high - low
    high_close = (high - close.shift(1)).abs()
    low_close  = (low  - close.shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

    up_move   =  high.diff()
    down_move = -low.diff()

    plus_dm  = pd.Series(
        np.where((up_move > down_move) & (up_move > 0),   up_move,   0.0),
        index=df.index
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=df.index
    )

    smoothed_tr  = tr.ewm(com=period - 1, adjust=False).mean()
    s_plus_dm    = plus_dm.ewm(com=period - 1,  adjust=False).mean()
    s_minus_dm   = minus_dm.ewm(com=period - 1, adjust=False).mean()

    plus_di  = 100 * s_plus_dm  / smoothed_tr
    minus_di = 100 * s_minus_dm / smoothed_tr

    dx_denom = plus_di + minus_di
    dx = pd.Series(
        np.where(dx_denom > 0, 100 * (plus_di - minus_di).abs() / dx_denom, 0.0),
        index=df.index
    )
    return dx.ewm(com=period - 1, adjust=False).mean()


def adx_kelly_mult(adx_series: pd.Series,
                   weak_thresh: float = 20,
                   strong_thresh: float = 35) -> pd.Series:
    """
    Map ADX values to a Kelly position-size multiplier.
    ADX < weak_thresh   → 0.8  (choppy — reduce size)
    ADX weak–strong     → 1.0  (moderate trend — neutral)
    ADX > strong_thresh → 1.2  (strong trend — increase size)
    """
    mult = pd.Series(1.0, index=adx_series.index)
    mult[adx_series < weak_thresh]   = 0.8
    mult[adx_series > strong_thresh] = 1.2
    return mult


def add_volatility_features(df: pd.DataFrame,
                             window: int = 20,
                             adx_period: int = 14,
                             adx_weak_thresh: float = 20,
                             adx_strong_thresh: float = 35) -> pd.DataFrame:
    """Add volatility and trend-strength columns.

    New columns: adx, adx_kelly_mult
    """
    df = df.copy()
    df["atr"]        = compute_atr(df)
    df["atr_pct"]    = df["atr"] / df["close"]
    upper, mid, lower = compute_bollinger_bands(df["close"], window)
    df["bb_upper"]   = upper
    df["bb_mid"]     = mid
    df["bb_lower"]   = lower
    df["bb_width"]   = compute_bb_width(df["close"], window)
    df["bb_position"] = compute_bb_position(df["close"], window)
    df["vol_regime"] = volatility_regime(df, window)
    df["adx"]        = compute_adx(df, period=adx_period)
    df["adx_kelly_mult"] = adx_kelly_mult(df["adx"],
                                           weak_thresh=adx_weak_thresh,
                                           strong_thresh=adx_strong_thresh)
    return df
