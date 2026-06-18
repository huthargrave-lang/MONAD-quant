"""
MONAD Quant - Backtest Runner
Full backtest loop with equity curve and performance metrics.

Fairness fixes (2026-03-23):
  - Rolling Kelly: position sizing uses only past trades (no lookahead)
  - Correct Sharpe: annualized by actual trade frequency, not hourly periods
  - Same-bar ambiguity: worst-case rule (stop wins when both hit)
  - Configurable slippage: deducted from every trade return
  - Per-trade debug logging: shows entry, exit, size, slippage
  - Backtest mode: optimistic / realistic / harsh
"""

import pandas as pd
# matplotlib is optional: it is only used to render backtest_results.png. The
# minimal/live Pi venv omits it, so guard the import — the backtest still
# computes and prints all stats; only the plot is skipped when it's absent.
try:
    import matplotlib
    matplotlib.use("Agg")  # headless — no display required
    import matplotlib.pyplot as plt
    _HAS_MPL = True
except ImportError:
    _HAS_MPL = False
from collections import deque
from src.strategy.engine import build_features, generate_trades, compute_trade_returns
from src.strategy.sizing import estimate_stats_from_backtest, compute_position_size, position_fraction
from src.backtest import metrics


# ═══════════════════════════════════════════════════════════════════════════
#  BACKTEST MODES — preset fairness levels
# ═══════════════════════════════════════════════════════════════════════════
BACKTEST_MODES = {
    "optimistic": {
        "slippage_pct":          0.0,
        "worst_case_ambiguity":  False,
        "kelly_mode":            "full_sample",   # legacy: full-sample Kelly (lookahead)
        "description":           "Legacy mode — no slippage, target wins ambiguity, full-sample Kelly",
    },
    "realistic": {
        "slippage_pct":          0.0002,           # 2bps round-trip
        "worst_case_ambiguity":  True,
        "kelly_mode":            "rolling",        # rolling window Kelly (no lookahead)
        "description":           "Fair mode — 2bps slippage, stop wins ambiguity, rolling Kelly",
    },
    "harsh": {
        "slippage_pct":          0.0005,           # 5bps round-trip
        "worst_case_ambiguity":  True,
        "kelly_mode":            "rolling",
        "description":           "Pessimistic — 5bps slippage, stop wins ambiguity, rolling Kelly",
    },
}


def run_backtest(df: pd.DataFrame,
                 initial_capital: float = 100_000,
                 target_gain_pct: float = 0.030,
                 stop_loss_pct: float = 0.015,
                 require_signals: int = 2,
                 kelly_multiplier: float = 0.5,
                 bull_kelly_multiplier: float = 0.75,
                 trade_hours: tuple = (8, 22),
                 timeframe: str = "daily",
                 plot: bool = True,
                 backtest_mode: str = "realistic",
                 slippage_pct: float = None,
                 stop_slippage_pct: float = 0.0,
                 debug: bool = False) -> dict:
    """
    Run a full backtest on historical OHLCV data.

    Args:
        backtest_mode: "optimistic" | "realistic" | "harsh" — controls slippage,
                       same-bar ambiguity, and Kelly sizing method.
        debug: When True, prints per-trade detail (entry, exit, size, slippage).

    Returns a dict with performance metrics and equity curve.
    """
    import config

    mode_cfg = BACKTEST_MODES.get(backtest_mode, BACKTEST_MODES["realistic"])
    # Explicit slippage_pct overrides the mode default — lets the sweep inject a
    # realistic, instrument-derived round-trip cost (the fixed 2bps mode default
    # badly understates a low-priced ETF's bid-ask spread). None => use the mode.
    if slippage_pct is None:
        slippage_pct = mode_cfg["slippage_pct"]
    worst_case = mode_cfg["worst_case_ambiguity"]
    kelly_mode = mode_cfg["kelly_mode"]

    print("=" * 60)
    print(f"  MONAD QUANT - BACKTEST ENGINE  [{backtest_mode.upper()}]")
    print(f"  {mode_cfg['description']}")
    print("=" * 60)

    # ── 1. Build signals ──────────────────────────────────────────────────
    print("[1/4] Building features and signals...")
    df_feat = build_features(df, timeframe=timeframe)
    use_regime = config.USE_REGIME_FILTER_HOURLY if timeframe == "hourly" else config.USE_REGIME_FILTER
    use_slope_regime = False if timeframe == "hourly" else getattr(config, "USE_SLOPE_REGIME", False)
    if getattr(config, "VERBOSE_SIGNALS", False):
        _print_signal_diagnostics(df_feat, require_signals, use_regime,
                                  getattr(config, "USE_MA_REGIME_FILTER", False),
                                  use_slope_regime=use_slope_regime)

    max_trade_bars = getattr(config, "MAX_TRADE_BARS", 20)
    df_trades = generate_trades(df_feat,
                                require_signals=require_signals,
                                target_gain_pct=target_gain_pct,
                                stop_loss_pct=stop_loss_pct,
                                trade_hours=trade_hours)

    # ── ATR dynamic stops ──────────────────────────────────────────────
    # When ATR is elevated (> mult × rolling median), widen the stop to reduce
    # noise-triggered exits. Uses stop_overrides dict passed to compute_trade_returns().
    stop_overrides = None
    use_atr_stops = getattr(config, "USE_ATR_DYNAMIC_STOPS", False)
    if use_atr_stops and "atr_pct" in df_trades.columns:
        atr_mult = getattr(config, "ATR_STOP_MULT", 2.0)
        atr_cap  = getattr(config, "ATR_STOP_CAP_PCT", 0.04)
        atr_baseline = df_trades["atr_pct"].rolling(20, min_periods=5).median()
        # Only override for entry bars where ATR is elevated
        entries = df_trades[df_trades["entry_signal"] != 0]
        stop_overrides = {}
        n_widened = 0
        for idx in entries.index:
            current_atr = df_trades.loc[idx, "atr_pct"]
            baseline = atr_baseline.loc[idx] if pd.notna(atr_baseline.loc[idx]) else current_atr
            if current_atr > atr_mult * baseline:
                widened_stop = min(current_atr * 1.0, atr_cap)
                if widened_stop > stop_loss_pct:
                    stop_overrides[idx] = widened_stop
                    n_widened += 1
        if n_widened > 0:
            print(f"       ATR dynamic stops: widened {n_widened}/{len(entries)} trades "
                  f"(ATR > {atr_mult}× baseline, cap {atr_cap*100:.1f}%)")
        else:
            stop_overrides = None  # no overrides needed

    # ── Opposing-signal exit resolution ───────────────────────────────────
    # Global flag OR per-mode override set (checked against ACTIVE_MODE).
    active_mode = getattr(config, "ACTIVE_MODE", None)
    opp_modes = getattr(config, "OPPOSING_SIGNAL_EXIT_MODES", set()) or set()
    use_opposing_exit = bool(
        getattr(config, "USE_OPPOSING_SIGNAL_EXIT", False)
        or (active_mode is not None and active_mode in opp_modes)
    )
    if use_opposing_exit:
        print(f"       Opposing-signal exit: ENABLED "
              f"(reads raw signal_vote, threshold ±{require_signals})")

    # ── 2. Simulate trades ────────────────────────────────────────────────
    print("[2/4] Simulating trades...")
    trades_df = compute_trade_returns(
        df_trades,
        target_gain_pct=target_gain_pct,
        stop_loss_pct=stop_loss_pct,
        max_trade_bars=max_trade_bars,
        slippage_pct=slippage_pct,
        stop_slippage_pct=stop_slippage_pct,
        worst_case_ambiguity=worst_case,
        stop_overrides=stop_overrides,
        use_opposing_signal_exit=use_opposing_exit,
        opposing_signal_threshold=require_signals,
    )

    if len(trades_df) == 0:
        print("No trades generated. Try loosening signal requirements.")
        return {}

    trade_returns = trades_df["return"]
    trade_returns.index = pd.to_datetime(trades_df["timestamp"])

    # Exit type breakdown
    if "exit_type" in trades_df.columns:
        exit_counts = trades_df["exit_type"].value_counts()
        exit_str = "  ".join(f"{k}={v}" for k, v in exit_counts.items())
    else:
        exit_str = ""

    # Stats from all trades (for reporting only — NOT used for sizing in rolling mode)
    stats = estimate_stats_from_backtest(trade_returns)
    bull_trades = (trades_df["trend_regime"] == 1).sum()
    bear_trades = (trades_df["trend_regime"] == -1).sum()
    print(f"       {stats['total_trades']} trades | WR: {stats['win_rate']*100:.1f}% "
          f"| Bull: {bull_trades} Bear: {bear_trades}")
    if exit_str:
        print(f"       Exits: {exit_str}")
    if slippage_pct > 0:
        print(f"       Slippage: {slippage_pct*100:.2f}% per trade ({slippage_pct*10000:.0f} bps)")

    # ── 3. Build equity curve ─────────────────────────────────────────────
    print("[3/4] Computing equity curve...")
    capital = initial_capital
    equity_curve = [capital]
    trade_capital_returns = {}    # {timestamp: pct capital change}
    rolling_returns = deque()     # rolling window for adaptive Kelly
    min_trades_for_kelly = 10     # need at least N trades before Kelly kicks in

    # Position sizing mode
    sizing_mode      = getattr(config, "POSITION_SIZING_MODE", "kelly")
    fixed_pos_pct    = getattr(config, "FIXED_POSITION_PCT", 0.08)
    kelly_clamp_min  = getattr(config, "KELLY_CLAMP_MIN", 0.02)
    kelly_clamp_max  = getattr(config, "KELLY_CLAMP_MAX", 0.10)

    # Adaptive Kelly config
    use_adaptive = getattr(config, "USE_ADAPTIVE_KELLY", False) and timeframe == "hourly"
    ak_lookback  = getattr(config, "ADAPTIVE_KELLY_LOOKBACK", 20)
    ak_high_wr   = getattr(config, "ADAPTIVE_KELLY_HIGH_WR", 0.52)
    ak_low_wr    = getattr(config, "ADAPTIVE_KELLY_LOW_WR", 0.42)
    ak_pause_wr  = getattr(config, "ADAPTIVE_KELLY_PAUSE_WR", 0.35)
    ak_high_mult = getattr(config, "ADAPTIVE_KELLY_HIGH_MULT", 1.5)
    ak_low_mult  = getattr(config, "ADAPTIVE_KELLY_LOW_MULT", 0.5)
    ak_pause_mult= getattr(config, "ADAPTIVE_KELLY_PAUSE_MULT", 0.2)
    ak_high_cap  = getattr(config, "ADAPTIVE_KELLY_HIGH_CAP", 0.30)
    max_pos_pct  = getattr(config, "MAX_POSITION_PCT", 0.20)
    min_pos_pct  = getattr(config, "MIN_POSITION_PCT", 0.02)

    if debug:
        print(f"\n  {'#':>4}  {'Timestamp':<20} {'Dir':>4} {'Entry$':>9} {'Return':>8} "
              f"{'Exit':>11} {'Kelly%':>7} {'Pos$':>10} {'PnL$':>9} {'Capital$':>11}")
        print("  " + "-" * 110)

    for i, (_, trade) in enumerate(trades_df.iterrows()):
        r = trade["return"]
        ts = trade["timestamp"]
        direction = "LONG" if trade.get("trend_regime", 0) >= 0 else "SHORT"
        exit_type = trade.get("exit_type", "?")

        # ── Position sizing (delegated to src/strategy/sizing.position_fraction;
        #    behaviour-identical to the previous inline logic, now unit-tested) ──
        adaptive_params = None
        if use_adaptive:
            adaptive_params = dict(
                lookback=ak_lookback, high_wr=ak_high_wr, low_wr=ak_low_wr,
                pause_wr=ak_pause_wr, high_mult=ak_high_mult, low_mult=ak_low_mult,
                pause_mult=ak_pause_mult, high_cap=ak_high_cap,
            )
        kelly_capped = position_fraction(
            mode=sizing_mode, kelly_mode=kelly_mode,
            rolling_returns=list(rolling_returns), full_sample_stats=stats,
            kelly_multiplier=kelly_multiplier,
            min_pct=min_pos_pct, max_pct=max_pos_pct, fixed_pct=fixed_pos_pct,
            min_trades_for_kelly=min_trades_for_kelly, adaptive=adaptive_params,
            clamp_min=kelly_clamp_min, clamp_max=kelly_clamp_max,
        )

        position = capital * kelly_capped
        pnl = position * r
        capital += pnl
        equity_curve.append(capital)

        # Track capital return for this trade
        pct_change = pnl / (capital - pnl) if (capital - pnl) != 0 else 0
        trade_capital_returns[ts] = pct_change

        # Update rolling window AFTER using it (no lookahead)
        rolling_returns.append(r)

        if debug:
            entry_price = 0  # not available in trades_df, but exit_type tells the story
            print(f"  {i+1:>4}  {str(ts):<20} {direction:>4} {'':>9} {r*100:>+7.3f}% "
                  f"{exit_type:>11} {kelly_capped*100:>6.2f}% {position:>10,.0f} "
                  f"{pnl:>+9,.0f} {capital:>11,.0f}")

    equity = pd.Series(equity_curve)

    # Buy-and-hold benchmark
    bh_return = metrics.buy_hold_return(df["close"])
    bh_final = initial_capital * (1 + bh_return)

    # ── Performance metrics (pure functions in src/backtest/metrics.py) ────
    total_return = metrics.total_return(equity, initial_capital)

    # Sharpe: annualize by actual trade frequency, NOT hourly periods
    n_days = (df.index[-1] - df.index[0]).days
    years = n_days / 365.25 if n_days > 0 else 1
    trades_per_year = metrics.trades_per_year(stats["total_trades"], df.index[0], df.index[-1])
    sharpe = metrics.annualized_sharpe(equity.pct_change().dropna(), trades_per_year, degenerate=0)

    max_drawdown = metrics.max_drawdown(equity)

    # Annualized return
    ann_return = metrics.annualize_return(total_return, years)
    bh_ann_return = metrics.annualize_return(bh_return, years)

    # Monthly breakdown using actual per-trade capital returns
    monthly_returns = metrics.monthly_returns(pd.Series(trade_capital_returns, dtype=float))
    monthly_counts = trade_returns.resample("ME").count()
    monthly_wr = trade_returns.resample("ME").apply(
        lambda x: (x > 0).sum() / len(x) if len(x) > 0 else 0.0
    )

    # Exit type breakdown (for results dict and reporting)
    exit_breakdown = {}
    if "exit_type" in trades_df.columns:
        exit_breakdown = trades_df["exit_type"].value_counts().to_dict()

    results = {
        "total_trades":    stats["total_trades"],
        "bull_trades":     int(bull_trades),
        "bear_trades":     int(bear_trades),
        "win_rate":        stats["win_rate"],
        "avg_win_pct":     stats["avg_win_pct"],
        "avg_loss_pct":    stats["avg_loss_pct"],
        "total_return":    round(total_return, 4),
        "sharpe_ratio":    round(sharpe, 3),
        "max_drawdown":    round(max_drawdown, 4),
        "final_capital":   round(equity.iloc[-1], 2),
        "equity_curve":    equity,
        "trade_returns":   trade_returns,
        "trades_df":       trades_df,
        "monthly_returns": monthly_returns,
        "backtest_mode":   backtest_mode,
        "slippage_pct":    slippage_pct,
        "trades_per_year": round(trades_per_year, 1),
        "exit_breakdown":  exit_breakdown,
    }

    # Print summary
    print(f"\n[4/4] Results [{backtest_mode.upper()}]:")
    print(f"       Total Return:   {total_return*100:.2f}%")
    print(f"       Annualized:     {ann_return*100:.2f}%")
    print(f"       Sharpe Ratio:   {sharpe:.3f}  (annualized by {trades_per_year:.0f} trades/yr)")
    print(f"       Max Drawdown:   {max_drawdown*100:.2f}%")
    print(f"       Final Capital:  ${equity.iloc[-1]:,.2f}")
    if sizing_mode == "fixed":
        print(f"       Sizing:         Fixed {fixed_pos_pct*100:.0f}% per trade")
    elif sizing_mode == "kelly_clamped":
        print(f"       Sizing:         Kelly clamped [{kelly_clamp_min*100:.0f}%-{kelly_clamp_max*100:.0f}%]"
              f" ({'rolling' if kelly_mode == 'rolling' else 'full-sample'})")
    elif kelly_mode == "rolling":
        print(f"       Sizing:         Rolling Kelly (min {min_trades_for_kelly} trades warmup)")
    else:
        print(f"       Sizing:         Full-sample Kelly (LOOKAHEAD — use realistic mode)")
    print("=" * 60)

    # Monthly dividend table with exit type breakdown
    # Pre-compute per-month exit type counts
    monthly_exit_types = {}
    if "exit_type" in trades_df.columns:
        trades_ts = trades_df.copy()
        trades_ts["_ts"] = pd.to_datetime(trades_ts["timestamp"])
        trades_ts["_month"] = trades_ts["_ts"].dt.to_period("M")
        for month_period, grp in trades_ts.groupby("_month"):
            monthly_exit_types[month_period] = grp["exit_type"].value_counts().to_dict()

    print("\n  Monthly 'Dividend' Schedule:")
    print("  " + "-" * 70)
    print(f"  {'Month':<12} {'Return':>8}  {'Trades':>7}  {'Win Rate':>9}  {'Exits'}")
    print("  " + "-" * 70)
    for month in monthly_returns.index:
        ret = monthly_returns[month]
        count = monthly_counts.get(month, 0)
        wr = monthly_wr.get(month, 0)
        if count > 0:
            mp = month.to_period("M")
            exits = monthly_exit_types.get(mp, {})
            exit_parts = " ".join(f"{k[0].upper()}:{v}" for k, v in sorted(exits.items()))
            print(f"  {month.strftime('%Y-%m'):<12} {ret*100:>+7.2f}%  {count:>7}  {wr*100:>8.1f}%  {exit_parts}")
    avg_monthly = monthly_returns[monthly_returns != 0].mean()
    neg_months = (monthly_returns[monthly_returns != 0] < 0).sum()
    total_months = (monthly_returns != 0).sum()
    print("  " + "-" * 70)
    print(f"  {'Avg Monthly':<12} {avg_monthly*100:>+7.2f}%")
    print(f"  Negative months: {neg_months}/{total_months}")
    if exit_breakdown:
        print(f"  Exit breakdown: " + "  ".join(f"{k}={v}" for k, v in sorted(exit_breakdown.items())))
    print()

    if plot and _HAS_MPL:
        _plot_results(equity, drawdown, trade_returns, trades_df, df_trades, initial_capital)
    elif plot:
        print("(matplotlib not installed — skipping backtest_results.png; stats above are complete. "
              "`pip install -r requirements-dev.txt` to enable the plot.)")

    return results


def _print_signal_diagnostics(df, require_signals, use_regime,
                               use_ma_regime_filter, use_slope_regime=False):
    """Print per-filter bar counts for signal debugging."""
    total_bars = len(df)
    mom_long  = (df["momentum_signal"] == 1).sum()
    mom_short = (df["momentum_signal"] == -1).sum()
    vol_long  = (df["volume_signal"] == 1).sum()
    vol_short = (df["volume_signal"] == -1).sum()

    print(f"  Signal diagnostics ({total_bars} bars):")
    print(f"    momentum_signal: long={mom_long} short={mom_short}")
    print(f"    volume_signal:   long={vol_long} short={vol_short}")

    vote = df["momentum_signal"] + df["volume_signal"]
    vote_long  = (vote >= require_signals).sum()
    vote_short = (vote <= -require_signals).sum()
    print(f"    signal_vote >= {require_signals}: {vote_long}")
    print(f"    signal_vote <= -{require_signals}: {vote_short}")

    if "entry_signal" in df.columns:
        entries = (df["entry_signal"] != 0).sum()
        print(f"    entry_signal (after all filters): {entries}")


def _plot_results(equity, drawdown, trade_returns, trades_df, df_price, initial_capital):
    BG      = "#0d0d1a"
    GRID    = "#1e1e3a"
    MODEL   = "#00d4ff"
    BH      = "#f0a500"
    RED     = "#ff4444"
    GREEN   = "#44ff88"
    WHITE   = "#e0e0e0"

    fig = plt.figure(figsize=(14, 11), facecolor=BG)
    fig.suptitle("MONAD Quant — Backtest", fontsize=15, fontweight="bold", color=WHITE, y=0.98)

    gs = fig.add_gridspec(3, 2, hspace=0.45, wspace=0.35,
                          left=0.07, right=0.97, top=0.93, bottom=0.07)
    ax_main   = fig.add_subplot(gs[0, :])
    ax_dd     = fig.add_subplot(gs[1, :])
    ax_monthly = fig.add_subplot(gs[2, 0])
    ax_dist   = fig.add_subplot(gs[2, 1])

    for ax in [ax_main, ax_dd, ax_monthly, ax_dist]:
        ax.set_facecolor(BG)
        ax.tick_params(colors=WHITE, labelsize=8)
        ax.grid(True, color=GRID, linewidth=0.6)
        for spine in ax.spines.values():
            spine.set_edgecolor(GRID)

    # Buy & Hold equity curve
    first_price = df_price["close"].iloc[0]
    bh_equity = initial_capital * (df_price["close"] / first_price)

    # Model equity curve (time-indexed via trade timestamps)
    if "timestamp" in trades_df.columns:
        model_ts = pd.Series(equity.values[1:], index=pd.to_datetime(trades_df["timestamp"]))
        model_ts = pd.concat([pd.Series([initial_capital], index=[df_price.index[0]]), model_ts])
        model_ts = model_ts[~model_ts.index.duplicated(keep="last")].sort_index()
        model_full = model_ts.reindex(df_price.index, method="ffill")
    else:
        model_full = pd.Series(equity.values, index=df_price.index[:len(equity)])

    ax_main.plot(bh_equity.index, bh_equity.values, color=BH, linewidth=1.2,
                 label="Buy & Hold", alpha=0.85)
    ax_main.plot(model_full.index, model_full.values, color=MODEL, linewidth=1.4,
                 label="MONAD Model")
    ax_main.fill_between(model_full.index, model_full.values, initial_capital,
                         where=(model_full.values > initial_capital),
                         color=MODEL, alpha=0.07)
    ax_main.set_title("Equity: Model vs Buy & Hold", color=WHITE, fontsize=10)
    ax_main.set_ylabel("Capital ($)", color=WHITE, fontsize=8)
    ax_main.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    leg = ax_main.legend(fontsize=8, framealpha=0.2, labelcolor=WHITE)
    leg.get_frame().set_facecolor(BG)

    # Drawdown comparison
    bh_roll_max = bh_equity.cummax()
    bh_dd = (bh_equity - bh_roll_max) / bh_roll_max

    model_roll_max = model_full.cummax()
    model_dd = (model_full - model_roll_max) / model_roll_max

    ax_dd.fill_between(bh_dd.index, bh_dd.values * 100, 0, color=BH, alpha=0.35, label="B&H DD")
    ax_dd.fill_between(model_dd.index, model_dd.values * 100, 0, color=RED, alpha=0.55, label="Model DD")
    ax_dd.set_title("Drawdown Comparison", color=WHITE, fontsize=10)
    ax_dd.set_ylabel("Drawdown (%)", color=WHITE, fontsize=8)
    leg2 = ax_dd.legend(fontsize=8, framealpha=0.2, labelcolor=WHITE)
    leg2.get_frame().set_facecolor(BG)

    # Monthly P&L
    if "timestamp" in trades_df.columns:
        monthly = (trades_df.set_index(pd.to_datetime(trades_df["timestamp"]))["return"]
                   .resample("ME").sum() * 100)
        bar_colors = [GREEN if v >= 0 else RED for v in monthly.values]
        ax_monthly.bar(monthly.index, monthly.values, color=bar_colors, width=20, alpha=0.85)
        ax_monthly.axhline(0, color=WHITE, linewidth=0.7, linestyle="--")
    ax_monthly.set_title("Monthly P&L (%)", color=WHITE, fontsize=10)
    ax_monthly.set_ylabel("Return (%)", color=WHITE, fontsize=8)
    ax_monthly.tick_params(axis="x", rotation=45)

    # Win/loss distribution
    wins  = trade_returns[trade_returns > 0] * 100
    losses = trade_returns[trade_returns < 0] * 100
    ax_dist.hist(wins,   bins=20, color=GREEN, alpha=0.75, label=f"Wins ({len(wins)})",   edgecolor=BG)
    ax_dist.hist(losses, bins=20, color=RED,   alpha=0.75, label=f"Losses ({len(losses)})", edgecolor=BG)
    ax_dist.axvline(0, color=WHITE, linewidth=0.8, linestyle="--")
    ax_dist.set_title("Win / Loss Distribution", color=WHITE, fontsize=10)
    ax_dist.set_xlabel("Trade Return (%)", color=WHITE, fontsize=8)
    ax_dist.set_ylabel("Count", color=WHITE, fontsize=8)
    leg3 = ax_dist.legend(fontsize=8, framealpha=0.2, labelcolor=WHITE)
    leg3.get_frame().set_facecolor(BG)

    plt.savefig("backtest_results.png", dpi=150, bbox_inches="tight", facecolor=BG)
    print("       Chart saved -> backtest_results.png")
    plt.close(fig)
