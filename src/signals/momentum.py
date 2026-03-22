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
                    ma_short_window: int = 50,
                    slope_window: int = 20,
                    strong_bull_thresh: float = 0.02,
                    strong_bear_thresh: float = -0.02) -> pd.Series:
    """
    6-state dual-MA regime classifier.
    Returns pd.Series of str.

    Uses two moving averages:
      ma_long  (252-day) — broad trend direction
      ma_short (50-day)  — medium-term recovery confirmation

    STRONG_BULL : price > 252-MA  AND slope > +thresh
    BULL        : price > 252-MA  AND slope >= 0
    STALLING    : price > 252-MA  AND slope < 0          → both directions
    RECOVERING  : price < 252-MA  AND price >= 50-MA     → LONGS ONLY
                  Triggers within weeks of recovery (50-MA), NOT after 12 months
                  (the old slope >= 0 condition lagged by ~1 year after crashes)
    BEAR        : price < 252-MA  AND price < 50-MA  AND slope >= -thresh
    STRONG_BEAR : price < 252-MA  AND price < 50-MA  AND slope < -thresh

    NaN slope rows (first slope_window bars) → STALLING.
    """
    ma_long  = prices.rolling(ma_window, min_periods=1).mean()
    ma_short = prices.rolling(ma_short_window, min_periods=1).mean()
    slope    = ma_long.pct_change(periods=slope_window)

    above_long  = prices >= ma_long
    above_short = prices >= ma_short

    regime = pd.Series("STALLING", index=prices.index, dtype=object)
    regime[above_long & (slope >= 0) & (slope <= strong_bull_thresh)] = "BULL"
    regime[above_long & (slope > strong_bull_thresh)]                  = "STRONG_BULL"
    # above_long & slope < 0 → stays STALLING

    # RECOVERING: below the long-term MA but already back above the 50-day.
    # This fires 2-4 weeks into recovery vs ~12 months for slope-based detection.
    regime[~above_long & above_short]                                           = "RECOVERING"
    regime[~above_long & ~above_short & (slope >= strong_bear_thresh)]          = "BEAR"
    regime[~above_long & ~above_short & (slope < strong_bear_thresh)]           = "STRONG_BEAR"
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
                           rsi_oversold: float = 35,
                           rsi_overbought: float = 65,
                           ma_regime_window: int = 252,
                           ma_short_window: int = 50,
                           slope_window: int = 20,
                           strong_bull_thresh: float = 0.02,
                           strong_bear_thresh: float = -0.02,
                           kelly_mult_map: dict = None) -> pd.DataFrame:
    """Add all momentum columns to a DataFrame.

    New columns: rsi, macd, macd_signal, macd_hist, momentum_signal,
                 ma_52w, ma_50d, ma_regime, ma_slope, regime, regime_kelly_mult,
                 bear_short_signal (only when LONGS_ONLY=False)
    """
    if kelly_mult_map is None:
        kelly_mult_map = _DEFAULT_REGIME_KELLY_MAP

    df = df.copy()
    df["rsi"] = compute_rsi(df["close"], period=rsi_period)
    df["macd"], df["macd_signal"], df["macd_hist"] = compute_macd(
        df["close"], fast=macd_fast, slow=macd_slow, signal=macd_signal_period
    )
    df["momentum_signal"] = momentum_signal(df, rsi_oversold=rsi_oversold,
                                             rsi_overbought=rsi_overbought)
    df["ma_52w"]  = df["close"].rolling(ma_regime_window, min_periods=1).mean()
    df["ma_50d"]  = df["close"].rolling(ma_short_window,  min_periods=1).mean()
    df["ma_regime"] = compute_ma_regime(df["close"], window=ma_regime_window)

    df["ma_slope"] = compute_ma_slope(df["close"],
                                      ma_window=ma_regime_window,
                                      slope_window=slope_window)
    df["regime"] = classify_regime(df["close"],
                                   ma_window=ma_regime_window,
                                   ma_short_window=ma_short_window,
                                   slope_window=slope_window,
                                   strong_bull_thresh=strong_bull_thresh,
                                   strong_bear_thresh=strong_bear_thresh)
    df["regime_kelly_mult"] = df["regime"].map(kelly_mult_map).fillna(1.0)

    # Bear short signal: fade dead-cat bounces in confirmed downtrends.
    # Uses a lower RSI overbought threshold than the standard signal (60/58 vs 62)
    # because bear markets suppress RSI peaks — bounces rarely reach 65+.
    # ONLY COMPUTED WHEN LONGS_ONLY=False — inert column (all zeros) when longs-only.
    try:
        import config as _cfg
        _longs_only = getattr(_cfg, "LONGS_ONLY", True)
    except ImportError:
        _longs_only = True
    df["bear_short_signal"] = 0  # always create so downstream checks never KeyError
    if not _longs_only:
        try:
            bear_rsi_ob = getattr(_cfg, "RSI_OVERBOUGHT_BEAR", 60)
            sb_rsi_ob   = getattr(_cfg, "RSI_OVERBOUGHT_STRONG_BEAR", 58)
        except ImportError:
            bear_rsi_ob, sb_rsi_ob = 60, 58
        macd_turning_dn = df["macd_hist"] < df["macd_hist"].shift(1)
        df.loc[(df["regime"] == "BEAR")        & (df["rsi"] > bear_rsi_ob) & macd_turning_dn, "bear_short_signal"] = -1
        df.loc[(df["regime"] == "STRONG_BEAR") & (df["rsi"] > sb_rsi_ob)   & macd_turning_dn, "bear_short_signal"] = -1

    return df
