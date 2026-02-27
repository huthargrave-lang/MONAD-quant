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


def build_features(df: pd.DataFrame, timeframe: str = "daily") -> pd.DataFrame:
    """Run all signal modules and combine into a single feature DataFrame.

    Args:
        df: OHLCV DataFrame
        timeframe: "daily" uses standard params; "hourly" uses faster intraday params
    """
    if timeframe == "hourly":
        import config
        df = add_momentum_features(
            df,
            rsi_period=config.RSI_PERIOD_HOURLY,
            macd_fast=config.MACD_FAST_HOURLY,
            macd_slow=config.MACD_SLOW_HOURLY,
            macd_signal_period=config.MACD_SIGNAL_HOURLY,
            roc_period=config.ROC_PERIOD_HOURLY,
        )
        df = add_volume_features(df, window=config.VWAP_WINDOW_HOURLY)
        df = add_volatility_features(df, window=config.BB_WINDOW_HOURLY)
    else:
        df = add_momentum_features(df)
        df = add_volume_features(df)
        df = add_volatility_features(df)
    return df


def generate_trades(df: pd.DataFrame,
                    require_signals: int = 2,
                    target_gain_pct: float = 0.015,   # 1.5% target
                    stop_loss_pct: float = 0.01,       # 1.0% stop
                    use_regime_filter: bool = True) -> pd.DataFrame:
    """
    Generate trade signals from aggregated features.

    Entry: N signals must agree (default 2 out of 3)
    Exit:  Take profit at target OR stop loss hit

    Args:
        df: Feature DataFrame from build_features()
        require_signals: Minimum agreeing signals to enter (1-3)
        target_gain_pct: Take profit level as decimal
        stop_loss_pct:   Stop loss level as decimal
        use_regime_filter: Only trade in trending regime if True

    Returns:
        DataFrame with trade signals added
    """
    df = df.copy()

    # Composite signal vote (each is -1, 0, or 1)
    df["signal_vote"] = (
        df["momentum_signal"] +
        df["volume_signal"]
    )

    # Long entry: enough signals agree AND (optionally) trending regime
    long_entry = df["signal_vote"] >= require_signals
    short_entry = df["signal_vote"] <= -require_signals

    if use_regime_filter:
        long_entry = long_entry & (df["vol_regime"] == 1)
        short_entry = short_entry & (df["vol_regime"] == 1)

    df["entry_signal"] = 0
    df.loc[long_entry, "entry_signal"] = 1
    df.loc[short_entry, "entry_signal"] = -1

    # Target and stop prices
    df["target_price"] = df["close"] * (1 + df["entry_signal"] * target_gain_pct)
    df["stop_price"] = df["close"] * (1 - df["entry_signal"] * stop_loss_pct)

    return df


def compute_trade_returns(df: pd.DataFrame,
                           target_gain_pct: float = 0.015,
                           stop_loss_pct: float = 0.01) -> pd.Series:
    """
    Simulate next-bar trade outcomes for backtesting.
    Returns a Series of individual trade P&L percentages.
    """
    trade_returns = []
    trade_indices = []
    entries = df[df["entry_signal"] != 0]

    for i, (idx, row) in enumerate(entries.iterrows()):
        loc = df.index.get_loc(idx)
        direction = row["entry_signal"]
        entry_price = row["close"]

        # Look ahead up to 5 bars for exit
        future = df.iloc[loc + 1: loc + 6]
        exit_return = None

        for _, bar in future.iterrows():
            if direction == 1:
                if bar["high"] >= entry_price * (1 + target_gain_pct):
                    exit_return = target_gain_pct
                    break
                elif bar["low"] <= entry_price * (1 - stop_loss_pct):
                    exit_return = -stop_loss_pct
                    break
            elif direction == -1:
                if bar["low"] <= entry_price * (1 - target_gain_pct):
                    exit_return = target_gain_pct
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
