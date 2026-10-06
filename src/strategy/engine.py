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
from src.strategy.counted import evaluator as _counted_evaluator


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


@_counted_evaluator  # refuses to run without a begun trial (src/strategy/counted.py)
def compute_trade_returns(df: pd.DataFrame,
                           target_gain_pct: float = 0.015,
                           stop_loss_pct: float = 0.01,
                           max_trade_bars: int = 20,
                           slippage_pct: float = 0.0,
                           stop_slippage_pct: float = 0.0,
                           worst_case_ambiguity: bool = True,
                           target_overrides: dict = None,
                           stop_overrides: dict = None,
                           bar_limit_overrides: dict = None,
                           use_opposing_signal_exit: bool = False,
                           opposing_signal_threshold: int = 1) -> pd.DataFrame:
    """
    Simulate trade outcomes with the live bot's execution (ENGINE_VERSION 3).

    The rules are the decision-debate consensus of 2026-10-06
    (docs/research/ENGINE_V3_QUESTION.md), where every divergence from live that hourly
    OHLC cannot resolve is taken at its conservative bound and declared:

      (a) A signal on bar N's close fills at bar N+1's OPEN, and the TP/SL bracket is live
          from that fill: bars N+1 .. N+MAX are scanned. Live fills ~2-3 min after the
          open at a quote, so an N+1 touch is an approximation.
      (b) In each bar after N+1 the OPEN is checked first: an open at or through the stop
          fills at the open less ``stop_slippage_pct`` ("gap_stop"); at or through the
          target, at the open ("gap_target"). Otherwise, both levels inside one bar resolve
          STOP-FIRST unless ``worst_case_ambiguity`` is False (the upper-bound mode only).
      (c) With no exit, the time exit fills at the OPEN of bar N+1+MAX (the live cycle that
          closes it runs at :32 of that bar; overnight when N+MAX ends a session). A gap
          there is labelled gap_stop / gap_target. At the end of the data only, the last
          close is used ("time_exit_truncated").
      (d) ONE position, as live holds: a signal on bar S may enter (at S+1's open) only if
          the previous trade exited at or before that open. An exit inside bar E allows
          S >= E; an exit at the open of bar X allows S >= X-1 (live re-enters on the same
          cycle). A trade dropped for an unusable entry price keeps its slot until its
          scheduled time exit.
      (e) ``slippage_pct`` is round-trip and comes off every trade once;
          ``stop_slippage_pct`` is the stop's trigger-to-fill slippage beyond the spread,
          on stop and gap-stop exits only.

    Args:
        df: Feature DataFrame with entry_signal column
        target_gain_pct / stop_loss_pct: default bracket, as fractions of the entry price
        max_trade_bars: MAX, the bars held before the time exit
        slippage_pct: round-trip slippage, deducted from every trade return once
        stop_slippage_pct: extra adverse fill on stop exits (see (e))
        worst_case_ambiguity: stop-first on a bar containing both levels (default True)
        target_overrides / stop_overrides / bar_limit_overrides: per-signal overrides
        use_opposing_signal_exit: a later raw ``signal_vote`` crossing
            ``opposing_signal_threshold`` against the trade closes it at the NEXT bar's
            open (TP/SL still win on the same bar); falls back to ``entry_signal``.

    Returns:
        DataFrame with columns: timestamp (the signal bar), return, trend_regime,
        exit_type, entry_time, exit_time.
    """
    trade_returns, trade_regimes, trade_timestamps, trade_exit_types = [], [], [], []
    trade_entry_times, trade_exit_times = [], []
    entries = df[df["entry_signal"] != 0]
    if use_opposing_signal_exit:
        signal_arr = (df["signal_vote"] if "signal_vote" in df.columns else df["entry_signal"]).to_numpy()
    else:
        signal_arr = None
    opp_thresh = abs(int(opposing_signal_threshold)) if opposing_signal_threshold else 1
    open_arr = df["open"].to_numpy(dtype=float)
    high_arr = df["high"].to_numpy(dtype=float)
    low_arr = df["low"].to_numpy(dtype=float)
    close_arr = df["close"].to_numpy(dtype=float)
    index = df.index
    df_len = len(df)
    next_free_signal = -1            # the earliest signal bar a new trade may use (rule d)

    for idx, row in entries.iterrows():
        loc = index.get_loc(idx)
        if loc < next_free_signal:
            continue                 # a position is open: live holds one at a time
        direction = row["entry_signal"]
        if direction not in (1, -1):
            continue
        regime = row.get("trend_direction", 0)
        n_bars = (bar_limit_overrides.get(idx, max_trade_bars)
                  if bar_limit_overrides else max_trade_bars)
        target = (target_overrides.get(idx, target_gain_pct)
                  if target_overrides else target_gain_pct)
        stop = (stop_overrides.get(idx, stop_loss_pct)
                if stop_overrides else stop_loss_pct)
        entry_loc = loc + 1
        if entry_loc >= df_len:
            continue                 # no bar to fill in
        entry_price = open_arr[entry_loc]
        time_exit_loc = entry_loc + n_bars           # bar N+1+MAX, whose open closes it
        if not np.isfinite(entry_price) or entry_price <= 0:
            next_free_signal = time_exit_loc - 1     # the slot stays taken (rule d)
            continue
        if direction == 1:
            stop_lvl, tgt_lvl = entry_price * (1 - stop), entry_price * (1 + target)
        else:
            stop_lvl, tgt_lvl = entry_price * (1 + stop), entry_price * (1 - target)

        def through_stop(price):
            return price <= stop_lvl if direction == 1 else price >= stop_lvl

        def through_target(price):
            return price >= tgt_lvl if direction == 1 else price <= tgt_lvl

        def ret_at(price):
            return direction * (price - entry_price) / entry_price

        exit_return = exit_type = None
        exit_loc = None              # bar of the exit
        exit_at_open = False         # True: the exit fills at that bar's open
        for k in range(entry_loc, min(time_exit_loc, df_len)):
            if k > entry_loc and np.isfinite(open_arr[k]):
                if through_stop(open_arr[k]):
                    exit_return = ret_at(open_arr[k]) - stop_slippage_pct
                    exit_type, exit_loc, exit_at_open = "gap_stop", k, True
                    break
                if through_target(open_arr[k]):
                    exit_return = ret_at(open_arr[k])
                    exit_type, exit_loc, exit_at_open = "gap_target", k, True
                    break
            if direction == 1:
                target_hit, stop_hit = high_arr[k] >= tgt_lvl, low_arr[k] <= stop_lvl
            else:
                target_hit, stop_hit = low_arr[k] <= tgt_lvl, high_arr[k] >= stop_lvl
            if target_hit and stop_hit:
                exit_return = (-stop - stop_slippage_pct) if worst_case_ambiguity else target
                exit_type, exit_loc = "ambiguous_same_bar", k
                break
            if stop_hit:
                exit_return, exit_type, exit_loc = -stop - stop_slippage_pct, "stop_hit", k
                break
            if target_hit:
                exit_return, exit_type, exit_loc = target, "target_hit", k
                break
            if signal_arr is not None and k > entry_loc:
                v = signal_arr[k]
                if (direction == 1 and v <= -opp_thresh) or (direction == -1 and v >= opp_thresh):
                    if k + 1 < df_len and np.isfinite(open_arr[k + 1]):
                        exit_return = ret_at(open_arr[k + 1])
                        exit_type, exit_loc, exit_at_open = "opposing_signal", k + 1, True
                        break
        if exit_return is None:
            if time_exit_loc < df_len and np.isfinite(open_arr[time_exit_loc]):
                px = open_arr[time_exit_loc]
                if through_stop(px):
                    exit_return, exit_type = ret_at(px) - stop_slippage_pct, "gap_stop"
                elif through_target(px):
                    exit_return, exit_type = ret_at(px), "gap_target"
                else:
                    exit_return, exit_type = ret_at(px), "time_exit"
                exit_loc, exit_at_open = time_exit_loc, True
            else:
                last = df_len - 1
                if last < entry_loc or not np.isfinite(close_arr[last]):
                    next_free_signal = df_len
                    continue
                exit_return, exit_type = ret_at(close_arr[last]), "time_exit_truncated"
                exit_loc, exit_at_open = last, False
        next_free_signal = exit_loc - 1 if exit_at_open else exit_loc
        exit_return -= slippage_pct
        trade_returns.append(exit_return)
        trade_regimes.append(regime)
        trade_timestamps.append(idx)
        trade_exit_types.append(exit_type)
        trade_entry_times.append(index[entry_loc])
        trade_exit_times.append(index[exit_loc])

    return pd.DataFrame({
        "timestamp": trade_timestamps,
        "return": trade_returns,
        "trend_regime": trade_regimes,
        "exit_type": trade_exit_types,
        "entry_time": trade_entry_times,
        "exit_time": trade_exit_times,
    })
