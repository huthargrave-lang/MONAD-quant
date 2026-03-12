"""
MONAD Quant - Strategy Engine
Aggregates momentum, volume, and volatility signals into trade decisions.
Prioritizes small, consistent gains with tight risk management.
"""

import pandas as pd
import numpy as np
from src.signals.momentum import add_momentum_features
from src.signals.volume import add_volume_features
from src.signals.volatility import add_volatility_features


def build_features(df: pd.DataFrame, timeframe: str = "daily",
                   signal_overrides: dict = None) -> pd.DataFrame:
    """Run all signal modules and combine into a single feature DataFrame.

    Args:
        df: OHLCV DataFrame
        timeframe: "daily" uses standard params; "hourly" uses faster intraday params
        signal_overrides: Optional dict to override specific signal params for this run.
                          Supported keys: "rsi_oversold". Used by walk-forward optimizer
                          to test different parameter combinations without mutating config.
    """
    import config
    overrides = signal_overrides or {}
    if timeframe == "hourly":
        df = add_momentum_features(
            df,
            rsi_period=config.RSI_PERIOD_HOURLY,
            macd_fast=config.MACD_FAST_HOURLY,
            macd_slow=config.MACD_SLOW_HOURLY,
            macd_signal_period=config.MACD_SIGNAL_HOURLY,
            rsi_oversold=config.RSI_OVERSOLD_HOURLY,
            rsi_overbought=config.RSI_OVERBOUGHT_HOURLY,
        )
        df = add_volume_features(df, window=config.VWAP_WINDOW_HOURLY,
                                  zscore_threshold=config.VWAP_ZSCORE_THRESH_HOURLY)
        df = add_volatility_features(df, window=config.BB_WINDOW_HOURLY)
    else:
        kelly_mult_map = {
            "STRONG_BULL": config.KELLY_MULT_STRONG_BULL,
            "BULL":        config.KELLY_MULT_BULL,
            "STALLING":    config.KELLY_MULT_STALLING,
            "RECOVERING":  config.KELLY_MULT_RECOVERING,
            "BEAR":        config.KELLY_MULT_BEAR,
            "STRONG_BEAR": config.KELLY_MULT_STRONG_BEAR,
        }
        df = add_momentum_features(
            df,
            rsi_oversold=overrides.get("rsi_oversold", config.RSI_OVERSOLD),
            rsi_overbought=config.RSI_OVERBOUGHT,
            ma_regime_window=config.MA_REGIME_WINDOW,
            ma_short_window=getattr(config, "MA_SHORT_WINDOW", 50),
            slope_window=config.MA_SLOPE_WINDOW,
            strong_bull_thresh=config.MA_STRONG_BULL_SLOPE,
            strong_bear_thresh=config.MA_STRONG_BEAR_SLOPE,
            kelly_mult_map=kelly_mult_map,
        )
        df = add_volume_features(df, zscore_threshold=config.VWAP_ZSCORE_THRESH)
        df = add_volatility_features(
            df,
            adx_period=config.ADX_PERIOD,
            adx_weak_thresh=config.ADX_WEAK_THRESH,
            adx_strong_thresh=config.ADX_STRONG_THRESH,
        )
        # Bull breakout signal: requires ADX (from volatility) so computed here,
        # after all feature modules have run. Fires on STRONG_BULL breakouts above
        # the prior N-day high with ADX trend confirmation and MACD momentum.
        # .shift(1) on the rolling high prevents look-ahead bias on the entry bar.
        if getattr(config, "BULL_BREAKOUT_ENABLED", False) and "adx" in df.columns:
            bw       = getattr(config, "BREAKOUT_WINDOW", 20)
            adx_min  = getattr(config, "ADX_BREAKOUT_MIN", 25)
            high_n   = df["close"].rolling(bw).max().shift(1)
            macd_pos = (df["macd_hist"] > 0) & (df["macd_hist"] > df["macd_hist"].shift(1))
            df["bull_breakout_signal"] = 0
            df.loc[
                (df["regime"] == "STRONG_BULL") &
                (df["close"] > high_n) &
                macd_pos &
                (df["adx"] > adx_min),
                "bull_breakout_signal"
            ] = 1
    return df


def generate_trades(df: pd.DataFrame,
                    require_signals: int = 2,
                    target_gain_pct: float = 0.015,   # 1.5% target
                    stop_loss_pct: float = 0.01,       # 1.0% stop
                    use_regime_filter: bool = True,
                    trade_hours: tuple = None) -> pd.DataFrame:
    """
    Generate trade entry signals from aggregated features.

    Entry: N signals must agree (require_signals out of available signals)
    Exit:  Handled by compute_trade_returns() with target/stop params

    Args:
        df: Feature DataFrame from build_features()
        require_signals: Minimum agreeing signals to enter (1-3)
        use_regime_filter: Only trade in ranging vol regime if True
        use_ma_regime_filter: Legacy binary 52w MA gate (ignored when use_slope_regime=True)
        use_slope_regime: 6-state slope regime — constrains direction per regime.
        longs_only: When True, never enter shorts. In BEAR/STRONG_BEAR regimes, sit flat
                    rather than fighting a downtrend with shorts. Mean-reversion on the
                    long side only — buy dips in uptrends, wait in downtrends.

    Returns:
        DataFrame with entry_signal column added (-1, 0, 1)
    """
    df = df.copy()

    # Composite signal vote (each is -1, 0, or 1)
    df["signal_vote"] = (
        df["momentum_signal"] +
        df["volume_signal"]
    )

    long_entry  = df["signal_vote"] >= require_signals
    short_entry = df["signal_vote"] <= -require_signals

    if use_regime_filter:
        long_entry  = long_entry  & (df["vol_regime"] == 1) & (df["trend_direction"] == 1)
        short_entry = short_entry & (df["vol_regime"] == 1) & (df["trend_direction"] == -1)

    if trade_hours is not None:
        hour = df.index.hour
        in_hours = (hour >= trade_hours[0]) & (hour < trade_hours[1])
        long_entry  = long_entry  & in_hours
        short_entry = short_entry & in_hours

    df["entry_signal"] = 0
    df.loc[long_entry,  "entry_signal"] = 1
    df.loc[short_entry, "entry_signal"] = -1

    import config as _cfg

    # Override regime_kelly_mult for BEAR defensive longs to quarter-Kelly
    if (use_slope_regime and longs_only
            and "regime_kelly_mult" in df.columns
            and "regime" in df.columns):
        if getattr(_cfg, "BEAR_DEFENSIVE_LONGS", False):
            bear_long_mask = (df["entry_signal"] == 1) & (df["regime"] == "BEAR")
            df.loc[bear_long_mask, "regime_kelly_mult"] = getattr(_cfg, "KELLY_MULT_BEAR_LONG", 0.25)

    # Override regime_kelly_mult for bear shorts — size per conviction level:
    #   BEAR       → half-Kelly (volatile regime, downtrend not accelerating)
    #   STRONG_BEAR → more conviction (accelerating downtrend), slightly larger
    if (use_slope_regime and not longs_only
            and "regime_kelly_mult" in df.columns
            and "regime" in df.columns):
        bear_short_mask  = (df["entry_signal"] == -1) & (df["regime"] == "BEAR")
        sbear_short_mask = (df["entry_signal"] == -1) & (df["regime"] == "STRONG_BEAR")
        df.loc[bear_short_mask,  "regime_kelly_mult"] = getattr(_cfg, "KELLY_MULT_BEAR_SHORT",       0.5)
        df.loc[sbear_short_mask, "regime_kelly_mult"] = getattr(_cfg, "KELLY_MULT_STRONG_BEAR_SHORT", 0.75)

    return df


def compute_trade_returns(df: pd.DataFrame,
                           target_gain_pct: float = 0.015,
                           stop_loss_pct: float = 0.01) -> pd.DataFrame:
    """
    Simulate next-bar trade outcomes for backtesting.
    Returns a DataFrame with columns: timestamp, return, trend_regime (1=bull, -1=bear).
    """
    trade_returns = []
    trade_regimes = []
    trade_timestamps = []
    entries = df[df["entry_signal"] != 0]

    for i, (idx, row) in enumerate(entries.iterrows()):
        loc = df.index.get_loc(idx)
        direction = row["entry_signal"]
        entry_price = row["close"]
        regime = row.get("trend_direction", 0)

        n_bars = (bar_limit_overrides.get(idx, max_trade_bars)
                  if bar_limit_overrides else max_trade_bars)
        target = (target_overrides.get(idx, target_gain_pct)
                  if target_overrides else target_gain_pct)
        stop = (stop_overrides.get(idx, stop_loss_pct)
                if stop_overrides else stop_loss_pct)

        # Look ahead up to n_bars for target/stop
        future = df.iloc[loc + 1: loc + 1 + n_bars]
        exit_return = None
        exit_type   = None

        for _, bar in future.iterrows():
            if direction == 1:
                if bar["high"] >= entry_price * (1 + target):
                    exit_return = target
                    exit_type   = "target_hit"
                    break
                elif bar["low"] <= entry_price * (1 - stop):
                    exit_return = -stop
                    exit_type   = "stop_hit"
                    break
            elif direction == -1:
                if bar["low"] <= entry_price * (1 - target):
                    exit_return = target
                    exit_type   = "target_hit"
                    break
                elif bar["high"] >= entry_price * (1 + stop):
                    exit_return = -stop
                    exit_type   = "stop_hit"
                    break

        # If no target/stop hit, use close of last future bar
        if exit_return is None and len(future) > 0:
            last_close  = future.iloc[-1]["close"]
            exit_return = direction * (last_close - entry_price) / entry_price
            exit_type   = "time_exit"

        if exit_return is not None:
            trade_returns.append(exit_return)
            trade_regimes.append(regime)
            trade_timestamps.append(idx)

    return pd.DataFrame({"timestamp": trade_timestamps, "return": trade_returns, "trend_regime": trade_regimes})
