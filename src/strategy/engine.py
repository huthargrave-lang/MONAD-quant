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
            roc_period=config.ROC_PERIOD_HOURLY,
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

            # Bull participation: add entries where RSI is between the neutral threshold
            # and the looser bull threshold. momentum_signal was built with RSI_OVERSOLD (38)
            # so these bars were excluded from signal_vote — add them back for bull regimes.
            # Volume signal must still agree for confirmation.
            if "rsi" in df.columns:
                base_rsi = getattr(_cfg, "RSI_OVERSOLD", 38)
                bull_rsi  = getattr(_cfg, "RSI_OVERSOLD_BULL", base_rsi)
                sbull_rsi = getattr(_cfg, "RSI_OVERSOLD_STRONG_BULL", base_rsi)
                if sbull_rsi > base_rsi:
                    sb_extra = (
                        (df["regime"] == "STRONG_BULL") &
                        (df["rsi"] < sbull_rsi) &
                        (df["volume_signal"] >= 1)
                    )
                    long_entry = long_entry | sb_extra
                if bull_rsi > base_rsi:
                    b_extra = (
                        (df["regime"] == "BULL") &
                        (df["rsi"] < bull_rsi) &
                        (df["volume_signal"] >= 1)
                    )
                    long_entry = long_entry | b_extra

            short_entry = pd.Series(False, index=df.index)
        else:
            # Bidirectional: constrain direction per regime
            no_long_regimes  = {"STRONG_BEAR", "BEAR"}
            no_short_regimes = {"STRONG_BULL", "BULL", "RECOVERING"}
            long_entry  = long_entry  & (~df["regime"].isin(no_long_regimes))
            short_entry = short_entry & (~df["regime"].isin(no_short_regimes))
    elif use_ma_regime_filter and "ma_regime" in df.columns:
        long_entry  = long_entry  & (df["ma_regime"] == 1)
        short_entry = short_entry & (df["ma_regime"] == -1)

    if longs_only:
        short_entry = pd.Series(False, index=df.index)

    df["entry_signal"] = 0
    df.loc[long_entry,  "entry_signal"] = 1
    df.loc[short_entry, "entry_signal"] = -1

    # Override regime_kelly_mult for BEAR defensive longs to quarter-Kelly
    if (use_slope_regime and longs_only
            and "regime_kelly_mult" in df.columns
            and "regime" in df.columns):
        import config as _cfg
        if getattr(_cfg, "BEAR_DEFENSIVE_LONGS", False):
            bear_long_mask = (df["entry_signal"] == 1) & (df["regime"] == "BEAR")
            df.loc[bear_long_mask, "regime_kelly_mult"] = getattr(_cfg, "KELLY_MULT_BEAR_LONG", 0.25)

    return df


def compute_trade_returns(df: pd.DataFrame,
                           target_gain_pct: float = 0.030,
                           stop_loss_pct: float = 0.015,
                           max_trade_bars: int = 10,
                           bar_limit_overrides: dict = None,
                           target_overrides: dict = None) -> pd.Series:
    """
    Simulate next-bar trade outcomes for backtesting.
    Returns a Series of individual trade P&L percentages.

    Args:
        bar_limit_overrides: Optional dict of {timestamp: n_bars} to use a different
                             hold window for specific trades. Used for bear defensive
                             longs (BEAR_MAX_TRADE_BARS) and bull longs (MAX_TRADE_BARS_STRONG_BULL).
        target_overrides: Optional dict of {timestamp: target_pct} to use a different
                         take-profit for specific trades. Used for STRONG_BULL entries
                         to let winners run further (TARGET_GAIN_PCT_STRONG_BULL).
    """
    trade_returns = []
    trade_indices = []
    entries = df[df["entry_signal"] != 0]

    for i, (idx, row) in enumerate(entries.iterrows()):
        loc = df.index.get_loc(idx)
        direction = row["entry_signal"]
        entry_price = row["close"]

        # Per-trade overrides — bear defensive longs use shorter window; bull longs use wider target
        n_bars = (bar_limit_overrides.get(idx, max_trade_bars)
                  if bar_limit_overrides else max_trade_bars)
        target = (target_overrides.get(idx, target_gain_pct)
                  if target_overrides else target_gain_pct)

        # Look ahead up to n_bars for target/stop
        future = df.iloc[loc + 1: loc + 1 + n_bars]
        exit_return = None

        for _, bar in future.iterrows():
            if direction == 1:
                if bar["high"] >= entry_price * (1 + target):
                    exit_return = target
                    break
                elif bar["low"] <= entry_price * (1 - stop_loss_pct):
                    exit_return = -stop_loss_pct
                    break
            elif direction == -1:
                if bar["low"] <= entry_price * (1 - target):
                    exit_return = target
                    break
                elif bar["high"] >= entry_price * (1 + stop_loss_pct):
                    exit_return = -stop_loss_pct
                    break

        # If no target/stop hit, use close of last future bar
        if exit_return is None and len(future) > 0:
            last_close = future.iloc[-1]["close"]
            exit_return = direction * (last_close - entry_price) / entry_price

        if exit_return is not None:
            trade_returns.append(exit_return)
            trade_indices.append(idx)

    return pd.Series(trade_returns, index=pd.DatetimeIndex(trade_indices))
