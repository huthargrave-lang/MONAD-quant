"""
live/signals.py — Live signal generation for any hourly ETF instrument.

Wraps the existing build_features() + generate_trades() pipeline.
Fetches the last N hourly bars for config.LIVE_SYMBOL, computes all signals,
and returns the entry_signal for the most recently completed bar.

No modifications to engine.py or any signal module — this is purely
a thin adapter that feeds live OHLCV data into the existing pipeline.

Safety: every failure path (yfinance down, stale data, insufficient bars,
NaN features) raises RuntimeError. The caller (trader.py) MUST block new
entries when this module raises. Never trade on stale or partial signals.

Resilience: on yfinance transient failures, falls back to the last
successful OHLCV fetch (in-memory cache). Cached data still goes through
all Phase 6.3 validation — staleness, min-bars, NaN checks — so stale
cache can't sneak through. Cache clears on process restart (clean slate).
"""

import logging
import math
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

# Minimum bar count before we trust feature values. The widest rolling window
# is 14 bars (BB), so ~50 bars would be mathematically sufficient, but we want
# comfortable headroom so distributions (vwap_zscore, ADX) are stable.
_MIN_BARS_DEFAULT = 200

# Maximum allowed age of the latest completed bar, in hours. Covers the longest
# realistic US-market holiday weekend (Thanksgiving Wed-early-close → following
# Monday 9:30 ET ≈ 115 hours). Beyond this, yfinance or the data source is broken.
_MAX_STALENESS_HOURS_DEFAULT = 120

# ── In-memory cache of last successful OHLCV fetch ──────────────────────────
# Populated after every successful fetch_yfinance call. Used as fallback when
# yfinance has a transient failure. Cached data still passes through ALL
# Phase 6.3 validation (staleness, min_bars, NaN). Clears on process restart.
_cached_bars: pd.DataFrame | None = None
_cached_bars_time: datetime | None = None


def _get_mode_name() -> str:
    """Returns the hourly mode name for the current LIVE_SYMBOL (e.g., 'TQQQ_HOURLY')."""
    return f"{config.LIVE_SYMBOL}_HOURLY"


def get_current_signal() -> dict:
    """
    Returns signal info for the most recently completed hourly bar.

    Execution model: signal fires on bar N's completed features. The caller
    (trader.py) then places a bracket order at the current market price via
    broker.py — that market price is the live equivalent of bar N+1's open
    in the backtest. bar_close is returned for qty estimation and logging only;
    it is NOT used as the TP/SL basis (broker.py uses live market price).

    Returns dict with:
        signal:    1 (long), 0 (no signal), or -1 (short)
        bar_close: float — the completed bar's close price (for qty estimation)
        bar_time:  the bar's timestamp
        rsi / vwap_zscore / momentum_signal / volume_signal: latest feature values

    Raises:
        RuntimeError on any failure mode — caller must block new entries:
          * yfinance fetch exception
          * empty DataFrame returned
          * fewer than LIVE_MIN_WARMUP_BARS completed bars
          * latest completed bar older than LIVE_MAX_BAR_STALENESS_HOURS
          * NaN on any critical feature for the latest bar
    """
    symbol = config.LIVE_SYMBOL
    mode = _get_mode_name()

    min_bars = getattr(config, "LIVE_MIN_WARMUP_BARS", _MIN_BARS_DEFAULT)
    df = _fetch_recent_bars(symbol, min_bars=min_bars)
    # _fetch_recent_bars raises RuntimeError on every failure mode, so if we
    # reach here we have a clean DataFrame with >= min_bars rows and a fresh
    # latest bar.

    df = build_features(df, timeframe="hourly")
    df = generate_trades(
        df,
        require_signals=config.ASSETS[mode]["require_signals"],
        use_regime_filter=False,
        use_slope_regime=False,
        longs_only=False,
    )

    # ── Feature sanity checks — block entry on any NaN in the critical
    # signal columns for the latest completed bar. Computed features can be
    # NaN if the input data has gaps (bad fetch), flat close (zero variance),
    # or insufficient warmup. entry_signal should ALWAYS be an integer.
    last_row = df.iloc[-1]
    for col in ("rsi", "momentum_signal", "volume_signal", "entry_signal", "close"):
        val = last_row.get(col)
        if val is None or (isinstance(val, float) and math.isnan(val)):
            raise RuntimeError(
                f"Feature '{col}' is NaN/None on latest bar for {symbol} "
                f"(bar_time={df.index[-1]}). Refusing to trade on bad data."
            )

    signal = int(last_row["entry_signal"])
    bar_close = float(last_row["close"])
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
    return {
        "signal": signal,
        "bar_close": bar_close,
        "bar_time": last_bar_time,
        "rsi": float(df["rsi"].iloc[-1]),
        "vwap_zscore": float(df["vwap_zscore"].iloc[-1]),
        "momentum_signal": int(df["momentum_signal"].iloc[-1]),
        "volume_signal": int(df["volume_signal"].iloc[-1]),
    }


def _fetch_recent_bars(symbol: str, min_bars: int = _MIN_BARS_DEFAULT) -> pd.DataFrame:
    """
    Fetches the last ~_WARMUP_BARS hourly bars for the given symbol via yfinance.
    Returns a DataFrame trimmed to completed bars only.

    On a successful yfinance fetch, caches the raw OHLCV in memory. On a
    transient fetch failure (exception or empty DataFrame), falls back to the
    in-memory cache from the last successful cycle. Cached data still goes
    through ALL validation (min_bars, staleness) — stale cache can't sneak past.

    Raises RuntimeError when no usable data is available:
      * yfinance exception AND no cached fallback (or cache also invalid)
      * fewer than min_bars completed bars (fresh or cached)
      * latest completed bar older than LIVE_MAX_BAR_STALENESS_HOURS
    """
    global _cached_bars, _cached_bars_time

    # Fetch a window large enough: trading days needed = ceil(bars / 6.5 hours/day)
    # Add buffer for weekends and holidays.
    trading_days_needed = (_WARMUP_BARS // 6) + 10
    start = (datetime.now(timezone.utc) - timedelta(days=trading_days_needed * 2)).strftime("%Y-%m-%d")
    # yfinance 'end' is exclusive — add 1 day so today's bars are included
    end   = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

    df = None
    fetch_source = "live"
    fetch_error = None

    try:
        df = fetch_yfinance(symbol, start=start, end=end, interval="1h")
    except Exception as exc:
        fetch_error = exc

    if df is None or (hasattr(df, "empty") and df.empty):
        # ── Fallback to cached data ───────────────────────────────────────
        if _cached_bars is not None and not _cached_bars.empty:
            log.warning(
                f"yfinance fetch failed ({fetch_error or 'empty DataFrame'}). "
                f"Falling back to cached data from {_cached_bars_time}."
            )
            df = _cached_bars.copy()
            fetch_source = "cache"
        else:
            # No cache available — raise with the original error
            if fetch_error is not None:
                raise RuntimeError(
                    f"fetch_yfinance({symbol}, 1h) raised: {fetch_error}"
                ) from fetch_error
            raise RuntimeError(
                f"fetch_yfinance({symbol}, 1h) returned empty DataFrame "
                f"and no cached data is available"
            )

    # Drop the current (possibly incomplete) bar.
    # A bar is "current" if its timestamp is within the last 60 minutes.
    now_utc = pd.Timestamp.now(tz="UTC")
    if df.index.tz is None:
        now_utc = pd.Timestamp.now()
    last_bar_age = now_utc - df.index[-1]
    dropped_incomplete = last_bar_age < pd.Timedelta(minutes=60)
    if dropped_incomplete:
        log.debug(f"Dropping current incomplete bar at {df.index[-1]} (age {last_bar_age})")
        df = df.iloc[:-1]

    if df.empty:
        raise RuntimeError(
            f"{symbol} fetch returned only an incomplete bar — nothing to compute features on"
        )

    result = df.tail(_WARMUP_BARS)

    # ── Hardening: minimum bar count ───────────────────────────────────────
    if len(result) < min_bars:
        raise RuntimeError(
            f"Insufficient bar data for {symbol}: got {len(result)} completed bars, "
            f"need >= {min_bars} for stable feature computation"
        )

    # ── Hardening: staleness check on the latest completed bar ─────────────
    # Rebuild now_utc (may have been stripped to naive above to match df.index)
    now_for_check = pd.Timestamp.now(tz="UTC") if result.index.tz is not None else pd.Timestamp.now()
    latest_age = now_for_check - result.index[-1]
    max_staleness = pd.Timedelta(hours=getattr(
        config, "LIVE_MAX_BAR_STALENESS_HOURS", _MAX_STALENESS_HOURS_DEFAULT
    ))
    if latest_age > max_staleness:
        raise RuntimeError(
            f"{symbol} latest completed bar is stale: "
            f"bar_time={result.index[-1]}, age={latest_age}, "
            f"max_allowed={max_staleness}. "
            f"{'Cached data too old.' if fetch_source == 'cache' else 'yfinance likely down or returning stale data.'}"
        )

    # ── Update cache on successful validation ─────────────────────────────
    # Only update cache from a live fetch (not from a cache fallback that
    # passed validation — that would just re-cache the same stale data).
    if fetch_source == "live":
        _cached_bars = df.copy()
        _cached_bars_time = datetime.now(timezone.utc)

    log.info(
        f"Warmup bars: {len(result)} (source={fetch_source}) | "
        f"first={result.index[0]} | last={result.index[-1]} | "
        f"latest_age={latest_age} | "
        f"dropped_incomplete={'yes' if dropped_incomplete else 'no'}"
    )
    return result
