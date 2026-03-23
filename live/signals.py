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
from src.data.fetcher import fetch_yfinance
from src.strategy.engine import build_features, generate_trades

log = logging.getLogger(__name__)

# How many historical bars to fetch for rolling-window warmup.
# Largest window in hourly signals: BB=14, VWAP=10, MACD slow=13, RSI=7.
# 300 bars (~46 trading days) stabilizes feature distributions across weekends,
# holidays, and yfinance session gaps. Cheap to fetch since we only check once/bar.
_WARMUP_BARS = 300


def _get_mode_name() -> str:
    """Returns the hourly mode name for the current LIVE_SYMBOL (e.g., 'TQQQ_HOURLY')."""
    return f"{config.LIVE_SYMBOL}_HOURLY"


def get_current_signal() -> dict:
    """
    Returns signal info for the most recently completed hourly bar.

    Returns dict with:
        signal:    1 (long), 0 (no signal), or -1 (short)
        bar_close: float — the completed bar's close price (use for bracket pricing)
        bar_time:  the bar's timestamp

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
        use_regime_filter=False,
        use_slope_regime=False,
        longs_only=False,
    )

    signal = int(df["entry_signal"].iloc[-1])
    bar_close = float(df["close"].iloc[-1])
    last_bar_time = df.index[-1]

    log.info(
        f"Signal check | {symbol} | bar={last_bar_time} | "
        f"close={bar_close:.2f} | "
        f"rsi={df['rsi'].iloc[-1]:.1f} | "
        f"vwap_z={df['vwap_zscore'].iloc[-1]:.3f} | "
        f"mom_sig={int(df['momentum_signal'].iloc[-1])} | "
        f"vol_sig={int(df['volume_signal'].iloc[-1])} | "
        f"entry_signal={signal}"
    )
    return {"signal": signal, "bar_close": bar_close, "bar_time": last_bar_time}


def _fetch_recent_bars(symbol: str) -> pd.DataFrame | None:
    """
    Fetches the last ~_WARMUP_BARS hourly bars for the given symbol via yfinance.
    Returns a DataFrame trimmed to completed bars only.
    """
    # Fetch a window large enough: trading days needed = ceil(bars / 6.5 hours/day)
    # Add buffer for weekends and holidays.
    trading_days_needed = (_WARMUP_BARS // 6) + 10
    start = (datetime.now(timezone.utc) - timedelta(days=trading_days_needed * 2)).strftime("%Y-%m-%d")
    # yfinance 'end' is exclusive — add 1 day so today's bars are included
    end   = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        df = fetch_yfinance(symbol, start=start, end=end, interval="1h")
    except Exception as exc:
        log.error(f"Failed to fetch {symbol} hourly data: {exc}")
        return None

    if df is None or df.empty:
        log.error(f"fetch_yfinance({symbol}, 1h) returned empty DataFrame")
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

    result = df.tail(_WARMUP_BARS)
    log.info(
        f"Warmup bars: {len(result)} | "
        f"first={result.index[0]} | last={result.index[-1]} | "
        f"dropped_incomplete={'yes' if last_bar_age < pd.Timedelta(minutes=60) else 'no'}"
    )
    return result
