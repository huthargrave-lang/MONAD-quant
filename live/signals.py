"""
live/signals.py — Live signal generation for any hourly ETF instrument.

Wraps the existing build_features() + generate_trades() pipeline.
Fetches the last N hourly bars for config.LIVE_SYMBOL, computes all signals,
and returns the entry_signal for the most recently completed bar.

No modifications to engine.py or any signal module — this is purely
a thin adapter that feeds live OHLCV data into the existing pipeline.
"""

import logging
from datetime import datetime, timedelta, timezone

import pandas as pd

import config
from src.data.fetcher import fetch_etf_hourly
from src.strategy.engine import build_features, generate_trades

log = logging.getLogger(__name__)

# How many historical bars to fetch for rolling-window warmup.
# Largest window in hourly signals: BB=14, VWAP=10, MACD slow=13, RSI=7.
# 100 bars (~16 trading days) gives comfortable padding.
_WARMUP_BARS = 100


def _get_mode_name() -> str:
    """Returns the hourly mode name for the current LIVE_SYMBOL (e.g., 'TQQQ_HOURLY')."""
    return f"{config.LIVE_SYMBOL}_HOURLY"


def get_current_signal() -> int:
    """
    Returns the entry_signal for the most recently completed hourly bar.

    Returns:
        1  — long entry signal
        0  — no signal
        -1 — short signal (not used in long-only config, included for completeness)

    Raises:
        RuntimeError if insufficient bars are available to compute signals.
    """
    symbol = config.LIVE_SYMBOL
    mode = _get_mode_name()

    df = _fetch_recent_bars(symbol)
    if df is None or len(df) < 20:
        raise RuntimeError(
            f"Insufficient bar data for {symbol} signal computation "
            f"(got {0 if df is None else len(df)} bars, need 20+)"
        )

    df = build_features(df, timeframe="hourly")
    df = generate_trades(
        df,
        require_signals=config.ASSETS[mode]["require_signals"],
        use_slope_regime=False,
        longs_only=False,
    )

    signal = int(df["entry_signal"].iloc[-1])
    last_bar_time = df.index[-1]

    log.info(
        f"Signal check | {symbol} | bar={last_bar_time} | "
        f"rsi={df['rsi'].iloc[-1]:.1f} | "
        f"vwap_z={df['vwap_zscore'].iloc[-1]:.3f} | "
        f"mom_sig={int(df['momentum_signal'].iloc[-1])} | "
        f"vol_sig={int(df['volume_signal'].iloc[-1])} | "
        f"entry_signal={signal}"
    )
    return signal


def _fetch_recent_bars(symbol: str) -> pd.DataFrame | None:
    """
    Fetches the last ~_WARMUP_BARS hourly bars for the given symbol via yfinance.
    Returns a DataFrame trimmed to completed bars only.
    """
    # Fetch a window large enough: trading days needed = ceil(bars / 6.5 hours/day)
    # Add buffer for weekends and holidays.
    trading_days_needed = (_WARMUP_BARS // 6) + 10
    start = (datetime.now(timezone.utc) - timedelta(days=trading_days_needed * 2)).strftime("%Y-%m-%d")
    end   = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        df = fetch_etf_hourly(symbol, start=start, end=end)
    except Exception as exc:
        log.error(f"Failed to fetch {symbol} hourly data: {exc}")
        return None

    if df is None or df.empty:
        log.error(f"fetch_etf_hourly({symbol}) returned empty DataFrame")
        return None

    # Drop the current (possibly incomplete) bar.
    # A bar is "current" if its timestamp is within the last 60 minutes.
    now_utc = pd.Timestamp.now(tz="UTC")
    if df.index.tz is None:
        now_utc = pd.Timestamp.now()
    last_bar_age = now_utc - df.index[-1]
    if last_bar_age < pd.Timedelta(minutes=60):
        log.debug(f"Dropping current incomplete bar at {df.index[-1]} (age {last_bar_age})")
        df = df.iloc[:-1]

    return df.tail(_WARMUP_BARS)
