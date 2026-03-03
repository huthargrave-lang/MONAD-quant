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
                    use_regime_filter: bool = True,
                    use_ma_regime_filter: bool = True,
                    use_slope_regime: bool = False,
                    longs_only: bool = False) -> pd.DataFrame:
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
        long_entry  = long_entry  & (df["vol_regime"] == 0)
        short_entry = short_entry & (df["vol_regime"] == 0)

    if use_slope_regime and "regime" in df.columns:
        if longs_only:
            # Long entries only in confirmed uptrend or recovery:
            #   STRONG_BULL, BULL : clear uptrend
            #   RECOVERING        : below 252-MA but above 50-MA — momentum is upward
            # Sit flat in STALLING (252-MA rolling over — Dec 2021 proved buying dips here
            # is catching a falling knife) and STRONG_BEAR (accelerating downtrend).
            # BEAR (mild downtrend) may allow defensive longs — see BEAR_DEFENSIVE_LONGS below.
            import config as _cfg
            bear_defensive = getattr(_cfg, "BEAR_DEFENSIVE_LONGS", False)
            if bear_defensive:
                flat_regimes = {"STRONG_BEAR", "STALLING"}
            else:
                flat_regimes = {"BEAR", "STRONG_BEAR", "STALLING"}
            long_entry  = long_entry  & (~df["regime"].isin(flat_regimes))

            # Bear defensive gate: BEAR longs require RSI deeply oversold (< RSI_OVERSOLD_BEAR)
            # AND both signals must agree (signal_vote >= 2). Overrides regime_kelly_mult to
            # KELLY_MULT_BEAR_LONG (quarter-Kelly) for these entries.
            if bear_defensive and "rsi" in df.columns:
                bear_mask    = df["regime"] == "BEAR"
                deep_oversold = df["rsi"] < getattr(_cfg, "RSI_OVERSOLD_BEAR", 30)
                # Veto any BEAR long that doesn't meet the tighter criteria
                long_entry = long_entry & (~bear_mask | (deep_oversold & (df["signal_vote"] >= 2)))

            # Softer 50-MA gate for STRONG_BULL: only block when price is >X% below the 50-MA.
            # Healthy bull dips (Aug 2023): 1-3% below 50-MA → NOT blocked.
            # Extended corrections (June 2024): 7-15% below 50-MA → BLOCKED.
            # Disabled by default (0.0). Set STRONG_BULL_SOFT_50MA_PCT=0.05 to activate.
            _soft_50ma_pct = getattr(_cfg, "STRONG_BULL_SOFT_50MA_PCT", 0.0)
            if _soft_50ma_pct > 0 and "ma_50d" in df.columns:
                sb_mask      = df["regime"] == "STRONG_BULL"
                pct_below_ma = (df["ma_50d"] - df["close"]) / df["close"]
                deep_corr    = sb_mask & (pct_below_ma > _soft_50ma_pct)
                long_entry   = long_entry & ~deep_corr

            short_entry = pd.Series(False, index=df.index)
        else:
            # Bidirectional: constrain direction per regime
            # Longs blocked in BEAR/STRONG_BEAR — don't fight a confirmed downtrend
            # Shorts blocked in STRONG_BULL/BULL/RECOVERING — don't fade an uptrend
            no_long_regimes  = {"STRONG_BEAR", "BEAR"}
            no_short_regimes = {"STRONG_BULL", "BULL", "RECOVERING"}
            long_entry  = long_entry  & (~df["regime"].isin(no_long_regimes))
            short_entry = short_entry & (~df["regime"].isin(no_short_regimes))

            # Bear short override: in BEAR/STRONG_BEAR, use bear_short_signal instead
            # of standard signal_vote shorts. bear_short_signal uses a lower RSI
            # overbought threshold (60/58 vs 62) since bear markets suppress RSI peaks.
            if "bear_short_signal" in df.columns:
                bear_regimes      = df["regime"].isin({"BEAR", "STRONG_BEAR"})
                bear_short_entry  = bear_regimes & (df["bear_short_signal"] == -1)
                other_short_entry = ~bear_regimes & short_entry
                short_entry = bear_short_entry | other_short_entry

            # Bull breakout: in STRONG_BULL, OR the breakout signal with mean-reversion
            # longs so both entry types are active simultaneously.
            if "bull_breakout_signal" in df.columns:
                bull_breakout = df["bull_breakout_signal"] == 1
                long_entry = long_entry | bull_breakout
    elif use_ma_regime_filter and "ma_regime" in df.columns:
        long_entry  = long_entry  & (df["ma_regime"] == 1)
        short_entry = short_entry & (df["ma_regime"] == -1)

    if longs_only:
        short_entry = pd.Series(False, index=df.index)

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
                           target_gain_pct: float = 0.030,
                           stop_loss_pct: float = 0.015,
                           max_trade_bars: int = 10,
                           bar_limit_overrides: dict = None,
                           target_overrides: dict = None,
                           stop_overrides: dict = None):
    """
    Simulate next-bar trade outcomes for backtesting.

    Returns a tuple: (returns, exit_types)
      - returns:    pd.Series of individual trade P&L percentages
      - exit_types: pd.Series of exit type strings ("target_hit", "stop_hit", "time_exit")

    Args:
        bar_limit_overrides: Optional dict of {timestamp: n_bars} — different hold window.
        target_overrides:    Optional dict of {timestamp: target_pct} — different take-profit.
        stop_overrides:      Optional dict of {timestamp: stop_pct} — different stop-loss.
    """
    trade_returns = []
    trade_exit_types = []
    trade_indices = []
    entries = df[df["entry_signal"] != 0]

    for i, (idx, row) in enumerate(entries.iterrows()):
        loc = df.index.get_loc(idx)
        direction = row["entry_signal"]
        entry_price = row["close"]

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
            trade_exit_types.append(exit_type)
            trade_indices.append(idx)

    idx_dt = pd.DatetimeIndex(trade_indices)
    return (
        pd.Series(trade_returns,    index=idx_dt),
        pd.Series(trade_exit_types, index=idx_dt),
    )
