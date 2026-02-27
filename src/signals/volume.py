"""
MONAD Quant - Volume Signals
VWAP deviation, OBV, volume confirmation
"""

import pandas as pd
import numpy as np


def compute_vwap(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Rolling VWAP over N periods."""
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    vwap = (typical_price * df["volume"]).rolling(window).sum() / df["volume"].rolling(window).sum()
    return vwap


def compute_vwap_zscore(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Z-score of price vs rolling VWAP — key mean reversion signal."""
    vwap = compute_vwap(df, window)
    deviation = df["close"] - vwap
    rolling_std = deviation.rolling(window).std()
    return deviation / rolling_std


def compute_obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume."""
    direction = np.sign(df["close"].diff())
    obv = (df["volume"] * direction).cumsum()
    return obv


def compute_volume_sma_ratio(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Current volume vs rolling average — confirms signal strength."""
    return df["volume"] / df["volume"].rolling(window).mean()


def volume_signal(df: pd.DataFrame, zscore_threshold: float = 1.5) -> pd.Series:
    """
    Volume-based signal using VWAP z-score.
    Returns: 1 (long - price below VWAP), -1 (short - price above VWAP), 0 (neutral)
    """
    zscore = compute_vwap_zscore(df)
    vol_ratio = compute_volume_sma_ratio(df)

    signal = pd.Series(0, index=df.index)

    # Price significantly below VWAP with above-avg volume = buy
    signal[(zscore < -zscore_threshold) & (vol_ratio > 1.0)] = 1
    # Price significantly above VWAP with above-avg volume = sell
    signal[(zscore > zscore_threshold) & (vol_ratio > 1.0)] = -1

    return signal


def add_volume_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["vwap"] = compute_vwap(df)
    df["vwap_zscore"] = compute_vwap_zscore(df)
    df["obv"] = compute_obv(df)
    df["vol_ratio"] = compute_volume_sma_ratio(df)
    df["volume_signal"] = volume_signal(df)
    return df
