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
        # Generic hourly dispatch: reads config params using mode suffix.
        # e.g., ACTIVE_MODE="TQQQ_HOURLY" → reads RSI_PERIOD_TQQQ_HOURLY, etc.
        # BTC_HOURLY uses bare "_HOURLY" suffix (legacy naming).
        active_mode = getattr(config, "ACTIVE_MODE", "BTC_HOURLY")
        suffix = active_mode if active_mode != "BTC_HOURLY" else "HOURLY"
        df = add_momentum_features(
            df,
            rsi_period=getattr(config, f"RSI_PERIOD_{suffix}", 7),
            macd_fast=getattr(config, f"MACD_FAST_{suffix}", 6),
            macd_slow=getattr(config, f"MACD_SLOW_{suffix}", 13),
            macd_signal_period=getattr(config, f"MACD_SIGNAL_{suffix}", 4),
            rsi_oversold=getattr(config, f"RSI_OVERSOLD_{suffix}", 40),
            rsi_overbought=getattr(config, f"RSI_OVERBOUGHT_{suffix}", 62),
        )
        df = add_volume_features(
            df,
            window=getattr(config, f"VWAP_WINDOW_{suffix}", 10),
            zscore_threshold=getattr(config, f"VWAP_ZSCORE_THRESH_{suffix}", 1.0),
        )
        df = add_volatility_features(
            df, window=getattr(config, f"BB_WINDOW_{suffix}", 14),
        )
        # Compute 50-period MA for hourly soft gate (if enabled).
        # For hourly bars, 50 periods ≈ ~2.5 trading days (vs 50 days for daily).
        soft_50ma_pct = getattr(config, "STRONG_BULL_SOFT_50MA_PCT", 0.0)
        if soft_50ma_pct > 0 and "ma_50d" not in df.columns:
            ma_short = getattr(config, "MA_SHORT_WINDOW", 50)
            df["ma_50d"] = df["close"].rolling(ma_short, min_periods=1).mean()
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
                    use_slope_regime: bool = False,
                    longs_only: bool = False,
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

    # Soft 50-MA gate: block longs when price is deeply below the 50-period MA.
    # For daily mode: only blocks STRONG_BULL longs (regime-aware).
    # For hourly mode: blocks all longs (no regime classifier on hourly bars).
    # Toggled via STRONG_BULL_SOFT_50MA_PCT (0=off, 0.05=block when >5% below MA).
    soft_50ma_pct = getattr(_cfg, "STRONG_BULL_SOFT_50MA_PCT", 0.0)
    if soft_50ma_pct > 0 and "ma_50d" in df.columns:
        pct_below_50ma = (df["ma_50d"] - df["close"]) / df["close"]
        deep_below = pct_below_50ma > soft_50ma_pct
        long_mask = df["entry_signal"] == 1
        if "regime" in df.columns:
            # Daily mode: only gate STRONG_BULL entries
            gate_mask = long_mask & (df["regime"] == "STRONG_BULL") & deep_below
        else:
            # Hourly mode: gate all long entries (no regime column)
            gate_mask = long_mask & deep_below
        n_candidates = long_mask.sum()
        n_gated = gate_mask.sum()
        if n_gated > 0:
            import logging
            _log = logging.getLogger(__name__)
            gated_dates = df.index[gate_mask]
            _log.info(
                f"Soft 50-MA gate: blocked {n_gated}/{n_candidates} longs "
                f"(>{soft_50ma_pct*100:.0f}% below 50-period MA)"
            )
            for ts in gated_dates[:20]:  # cap at 20 to avoid log flood
                pct = pct_below_50ma.loc[ts]
                _log.info(f"  gated: {ts}  ({pct*100:.1f}% below MA)")
            if len(gated_dates) > 20:
                _log.info(f"  ... and {len(gated_dates) - 20} more")
            df.loc[gate_mask, "entry_signal"] = 0

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
                           stop_loss_pct: float = 0.01,
                           max_trade_bars: int = 20,
                           slippage_pct: float = 0.0,
                           worst_case_ambiguity: bool = False,
                           target_overrides: dict = None,
                           stop_overrides: dict = None,
                           bar_limit_overrides: dict = None,
                           use_opposing_signal_exit: bool = False,
                           opposing_signal_threshold: int = 1) -> pd.DataFrame:
    """
    Simulate next-bar trade outcomes for backtesting.

    Execution model (unified with live trading):
        1. Signal fires on bar N based on bar N's completed OHLCV features.
        2. Entry fills at bar N+1's open — the first tradeable price after the signal.
        3. TP/SL levels are computed relative to the entry price (bar N+1 open).
        4. Exit scanning starts at bar N+2 and runs up to max_trade_bars.
    The live equivalent: signal on completed bar → fill at current market price
    → TP/SL relative to that market price. See live/broker.py place_bracket_order().

    Args:
        df: Feature DataFrame with entry_signal column
        target_gain_pct: Default target gain percentage
        stop_loss_pct: Default stop loss percentage
        max_trade_bars: Maximum bars to hold before time exit
        slippage_pct: Round-trip slippage as decimal (e.g. 0.0004 = 4bps).
                      Deducted from every trade return (wins shrink, losses grow).
        worst_case_ambiguity: When True, if both stop and target are inside the
                              same bar's range, assume the stop was hit (pessimistic).
                              When False, assume target was hit (optimistic/legacy).
        target_overrides: Dict of {timestamp: target_pct} for per-trade targets
        stop_overrides: Dict of {timestamp: stop_pct} for per-trade stops
        bar_limit_overrides: Dict of {timestamp: max_bars} for per-trade bar limits
        use_opposing_signal_exit: When True, a future bar whose raw signal_vote
                              crosses the opposing_signal_threshold in the
                              opposite direction closes the trade at the NEXT
                              bar's open (matching entry convention). TP/SL
                              still win on the same bar. Produces
                              exit_type="opposing_signal".
                              Reads the pre-gate `signal_vote` column (raw
                              momentum+volume composite) rather than the
                              post-gate `entry_signal`, so regime filters
                              (trend_direction, vol_regime, longs_only) that
                              suppress entries in one direction do NOT also
                              suppress the exit. Falls back to `entry_signal`
                              if `signal_vote` is absent (supports test
                              fixtures that don't run generate_trades).
        opposing_signal_threshold: Absolute threshold for the raw composite
                              vote to count as an opposing signal. Should
                              match the `require_signals` used at entry so
                              the exit fires when the strategy would now
                              enter in the opposite direction. Default 1.

    Returns:
        DataFrame with columns: timestamp, return, trend_regime, exit_type
    """
    trade_returns = []
    trade_regimes = []
    trade_timestamps = []
    trade_exit_types = []
    entries = df[df["entry_signal"] != 0]

    # Precompute the raw composite vote column for opposing-signal lookups.
    # IMPORTANT: we read the pre-gate `signal_vote` (raw momentum+volume sum),
    # NOT the post-gate `entry_signal`. The regime filter in generate_trades()
    # (trend_direction + vol_regime) + longs_only gating zero out the opposite
    # direction in entry_signal, so the exit would never fire if we read
    # entry_signal. Fall back to entry_signal for legacy test fixtures that
    # construct a df without running generate_trades (they set entry_signal
    # directly and never populate signal_vote).
    if use_opposing_signal_exit:
        if "signal_vote" in df.columns:
            signal_arr = df["signal_vote"].to_numpy()
        else:
            signal_arr = df["entry_signal"].to_numpy()
        open_arr = df["open"].to_numpy()
    else:
        signal_arr = None
        open_arr   = None
    df_len     = len(df)
    # Normalize the threshold — use absolute value and ensure int-compatible.
    opp_thresh = abs(int(opposing_signal_threshold)) if opposing_signal_threshold else 1

    for i, (idx, row) in enumerate(entries.iterrows()):
        loc = df.index.get_loc(idx)
        direction = row["entry_signal"]
        regime = row.get("trend_direction", 0)

        n_bars = (bar_limit_overrides.get(idx, max_trade_bars)
                  if bar_limit_overrides else max_trade_bars)
        target = (target_overrides.get(idx, target_gain_pct)
                  if target_overrides else target_gain_pct)
        stop = (stop_overrides.get(idx, stop_loss_pct)
                if stop_overrides else stop_loss_pct)

        # Entry convention: signal fires on bar N's close, fill at bar N+1's open.
        # This matches live trading where the signal fires after bar close and the
        # order fills at the next available price (market open of next bar).
        next_bar_loc = loc + 1
        if next_bar_loc >= len(df):
            continue  # no next bar available for entry
        entry_price = df.iloc[next_bar_loc]["open"]

        # Look ahead from bar N+2 onward (N+1 is the entry bar)
        future_start = next_bar_loc + 1
        future = df.iloc[future_start: future_start + n_bars]
        exit_return = None
        exit_type   = None

        for fut_offset, (_, bar) in enumerate(future.iterrows()):
            if direction == 1:
                target_hit = bar["high"] >= entry_price * (1 + target)
                stop_hit   = bar["low"]  <= entry_price * (1 - stop)
            elif direction == -1:
                target_hit = bar["low"]  <= entry_price * (1 - target)
                stop_hit   = bar["high"] >= entry_price * (1 + stop)
            else:
                continue

            if target_hit and stop_hit:
                # Same-bar ambiguity: both TP and SL inside this bar's range.
                # We can't know which was hit first from OHLC alone.
                if worst_case_ambiguity:
                    exit_return = -stop
                    exit_type   = "ambiguous_same_bar"
                else:
                    exit_return = target
                    exit_type   = "ambiguous_same_bar"
                break
            elif target_hit:
                exit_return = target
                exit_type   = "target_hit"
                break
            elif stop_hit:
                exit_return = -stop
                exit_type   = "stop_hit"
                break

            # Opposing-signal exit — only reached when neither TP nor SL fired
            # on this bar. The signal on bar K is actionable at bar K+1 open
            # (same rule as entries), so we exit at the *next* bar's open.
            # Reads raw signal_vote, so an opposing composite fires even when
            # regime/longs_only would block an actual short entry.
            if use_opposing_signal_exit:
                bar_loc = future_start + fut_offset
                bar_signal = signal_arr[bar_loc]
                if ((direction == 1 and bar_signal <= -opp_thresh) or
                    (direction == -1 and bar_signal >= opp_thresh)):
                    opp_fill_loc = bar_loc + 1
                    if opp_fill_loc < df_len:
                        opp_price = open_arr[opp_fill_loc]
                        exit_return = direction * (opp_price - entry_price) / entry_price
                        exit_type   = "opposing_signal"
                        break
                    # Opposing signal fires on the last bar — no next bar to
                    # fill at. Fall through and let the time-exit path below
                    # handle it (consistent with entry-drop-on-last-bar rule).

        # If no target/stop/opposing-signal hit, use close of last future bar
        if exit_return is None and len(future) > 0:
            last_close  = future.iloc[-1]["close"]
            exit_return = direction * (last_close - entry_price) / entry_price
            exit_type   = "time_exit"

        if exit_return is not None:
            # Apply slippage: deduct from return (shrinks wins, enlarges losses)
            exit_return -= slippage_pct
            trade_returns.append(exit_return)
            trade_regimes.append(regime)
            trade_timestamps.append(idx)
            trade_exit_types.append(exit_type)

    return pd.DataFrame({
        "timestamp": trade_timestamps,
        "return": trade_returns,
        "trend_regime": trade_regimes,
        "exit_type": trade_exit_types,
    })
