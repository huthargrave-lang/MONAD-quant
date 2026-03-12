"""
MONAD Quant - Backtest Runner
Full backtest loop with equity curve and performance metrics.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from collections import deque
from src.strategy.engine import build_features, generate_trades, compute_trade_returns
from src.strategy.sizing import estimate_stats_from_backtest, compute_position_size


def run_backtest(df: pd.DataFrame,
                 initial_capital: float = 100_000,
                 target_gain_pct: float = 0.030,
                 stop_loss_pct: float = 0.015,
                 require_signals: int = 2,
                 kelly_multiplier: float = 0.5,
                 bull_kelly_multiplier: float = 0.75,
                 trade_hours: tuple = (8, 22),
                 plot: bool = True) -> dict:
    """
    Run a full backtest on historical OHLCV data.

    Returns a dict with performance metrics and equity curve.
    """
    print("=" * 50)
    print("  MONAD QUANT - BACKTEST ENGINE")
    print("=" * 50)

    # Build signals
    print("[1/4] Building features and signals...")
    import config
    df_feat = build_features(df, timeframe=timeframe)
    use_regime = config.USE_REGIME_FILTER_HOURLY if timeframe == "hourly" else config.USE_REGIME_FILTER
    # Slope regime uses 252-bar windows designed for daily bars (≈1 trading year).
    # On hourly bars, 252 bars ≈ 10 trading days — wrong calibration, blocks valid signals.
    # Disable for all hourly timeframes; signal quality is managed by RSI+VWAP alone.
    use_slope_regime = False if timeframe == "hourly" else getattr(config, "USE_SLOPE_REGIME", False)
    if getattr(config, "VERBOSE_SIGNALS", False):
        _print_signal_diagnostics(df_feat, require_signals, use_regime,
                                  getattr(config, "USE_MA_REGIME_FILTER", False),
                                  use_slope_regime=use_slope_regime)
    df_trades = generate_trades(df_feat,
                                require_signals=require_signals,
                                target_gain_pct=target_gain_pct,
                                stop_loss_pct=stop_loss_pct,
                                trade_hours=trade_hours)

    # Compute individual trade returns (indexed by entry timestamp)
    print("[2/4] Simulating trades...")
    trades_df = compute_trade_returns(df_trades, target_gain_pct, stop_loss_pct)

    if len(trades_df) == 0:
        print("No trades generated. Try loosening signal requirements.")
        return {}

    trade_returns = trades_df["return"]

    # Stats from backtest
    stats = estimate_stats_from_backtest(trade_returns)
    bull_trades = (trades_df["trend_regime"] == 1).sum()
    bear_trades = (trades_df["trend_regime"] == -1).sum()
    print(f"       {stats['total_trades']} trades | Win rate: {stats['win_rate']*100:.1f}% | Bull: {bull_trades} Bear: {bear_trades}")

    # Position sizing (base — bear/neutral regime)
    sizing = compute_position_size(
        capital=initial_capital,
        win_rate=stats["win_rate"],
        avg_win_pct=stats["avg_win_pct"],
        avg_loss_pct=stats["avg_loss_pct"],
        kelly_multiplier=kelly_multiplier,
        min_position_pct=getattr(config, "MIN_POSITION_PCT", 0.0),
    )
    bull_sizing = compute_position_size(
        capital=initial_capital,
        win_rate=stats["win_rate"],
        avg_win_pct=stats["avg_win_pct"],
        avg_loss_pct=stats["avg_loss_pct"],
        kelly_multiplier=bull_kelly_multiplier,
    )

    # Build equity curve with per-trade Kelly scaling
    print("[3/4] Computing equity curve...")
    capital = initial_capital
    equity_curve = [capital]
    for _, trade in trades_df.iterrows():
        r = trade["return"]
        kelly_capped = bull_sizing["kelly_capped"] if trade["trend_regime"] == 1 else sizing["kelly_capped"]
        position = capital * kelly_capped
        capital += position * r
        equity_curve.append(capital)
        trade_capital_returns[idx] = pct_change        # actual % capital move this trade
        recent_outcomes.append(1 if r > 0 else 0)     # update rolling window after trade

    equity = pd.Series(equity_curve)

    # Buy-and-hold benchmark
    bh_return = (df["close"].iloc[-1] - df["close"].iloc[0]) / df["close"].iloc[0]
    bh_final = initial_capital * (1 + bh_return)

    # Performance metrics
    total_return = (equity.iloc[-1] - initial_capital) / initial_capital
    trade_pnl = equity.pct_change().dropna()

    # Annualize Sharpe based on timeframe
    periods_per_year = 252 * 24 if timeframe == "hourly" else 252
    sharpe = (trade_pnl.mean() / trade_pnl.std()) * np.sqrt(periods_per_year) if trade_pnl.std() > 0 else 0

    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max
    max_drawdown = drawdown.min()

    # Annualized return
    n_days = (df.index[-1] - df.index[0]).days
    years = n_days / 365.25
    ann_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else total_return
    bh_ann_return = (1 + bh_return) ** (1 / years) - 1 if years > 0 else bh_return

    # Monthly "dividend" breakdown — use actual per-trade capital returns from equity loop
    # (trade_capital_returns reflects actual kelly sizing including adaptive adjustments)
    capital_ret_series = pd.Series(trade_capital_returns, dtype=float)
    capital_ret_series.index = pd.to_datetime(capital_ret_series.index)
    monthly_returns = capital_ret_series.resample("ME").apply(
        lambda x: (1 + x).prod() - 1 if len(x) > 0 else 0.0
    )
    monthly_counts = trade_returns.resample("ME").count()
    monthly_wr = trade_returns.resample("ME").apply(
        lambda x: (x > 0).sum() / len(x) if len(x) > 0 else 0.0
    )

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
        "kelly_position":  sizing,
        "bull_kelly_position": bull_sizing,
        "equity_curve":    equity,
        "trade_returns":   trade_returns,
        "trades_df":       trades_df,
    }

    # Print summary
    print("[4/4] Results:")
    print(f"       Total Return:   {total_return*100:.2f}%")
    print(f"       Annualized:     {ann_return*100:.2f}%")
    print(f"       Sharpe Ratio:   {sharpe:.3f}")
    print(f"       Max Drawdown:   {max_drawdown*100:.2f}%")
    print(f"       Final Capital:  ${equity.iloc[-1]:,.2f}")
    print(f"       Kelly (bear):   {sizing['position_pct']}% (${sizing['position_dollars']:,.2f})")
    print(f"       Kelly (bull):   {bull_sizing['position_pct']}% (${bull_sizing['position_dollars']:,.2f})")
    print("=" * 50)

    # Monthly dividend table
    print("\n  Monthly 'Dividend' Schedule:")
    print("  " + "-" * 44)
    print(f"  {'Month':<12} {'Return':>8}  {'Trades':>7}  {'Win Rate':>9}")
    print("  " + "-" * 44)
    for month in monthly_returns.index:
        ret = monthly_returns[month]
        count = monthly_counts[month]
        wr = monthly_wr[month]
        if count > 0:
            tag = " ✓" if ret >= 0.05 else ""
            print(f"  {month.strftime('%Y-%m'):<12} {ret*100:>+7.2f}%  {count:>7}  {wr*100:>8.1f}%{tag}")
    avg_monthly = monthly_returns[monthly_returns != 0].mean()
    print("  " + "-" * 44)
    print(f"  {'Avg Monthly':<12} {avg_monthly*100:>+7.2f}%")
    print()

    if plot:
        _plot_results(equity, drawdown, trade_returns, trades_df, df_trades, initial_capital)

    return results


def _plot_results(equity, drawdown, trade_returns, trades_df, df_price, initial_capital):
    BG      = "#0d0d1a"
    GRID    = "#1e1e3a"
    MODEL   = "#00d4ff"
    BH      = "#f0a500"
    RED     = "#ff4444"
    GREEN   = "#44ff88"
    WHITE   = "#e0e0e0"

    fig = plt.figure(figsize=(14, 11), facecolor=BG)
    fig.suptitle("MONAD Quant — BTC Backtest", fontsize=15, fontweight="bold", color=WHITE, y=0.98)

    gs = fig.add_gridspec(3, 2, hspace=0.45, wspace=0.35,
                          left=0.07, right=0.97, top=0.93, bottom=0.07)
    ax_main   = fig.add_subplot(gs[0, :])   # full-width top: equity comparison
    ax_dd     = fig.add_subplot(gs[1, :])   # full-width mid: drawdown comparison
    ax_monthly = fig.add_subplot(gs[2, 0])  # bottom-left: monthly P&L
    ax_dist   = fig.add_subplot(gs[2, 1])   # bottom-right: win/loss distribution

    for ax in [ax_main, ax_dd, ax_monthly, ax_dist]:
        ax.set_facecolor(BG)
        ax.tick_params(colors=WHITE, labelsize=8)
        ax.grid(True, color=GRID, linewidth=0.6)
        for spine in ax.spines.values():
            spine.set_edgecolor(GRID)

    # ── Buy & Hold equity curve (time-indexed) ────────────────────────────────
    first_price = df_price["close"].iloc[0]
    bh_equity = initial_capital * (df_price["close"] / first_price)

    # ── Model equity curve (time-indexed via trade timestamps) ────────────────
    if "timestamp" in trades_df.columns:
        model_ts = pd.Series(equity.values[1:], index=pd.to_datetime(trades_df["timestamp"]))
        model_ts = pd.concat([pd.Series([initial_capital], index=[df_price.index[0]]), model_ts])
        model_ts = model_ts[~model_ts.index.duplicated(keep="last")].sort_index()
        model_full = model_ts.reindex(df_price.index, method="ffill")
    else:
        model_full = pd.Series(equity.values, index=df_price.index[:len(equity)])

    # Panel 1: equity comparison
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

    # Panel 2: drawdown comparison
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

    # Panel 3: monthly P&L bar chart
    if "timestamp" in trades_df.columns:
        monthly = (trades_df.set_index(pd.to_datetime(trades_df["timestamp"]))["return"]
                   .resample("ME").sum() * 100)
        bar_colors = [GREEN if v >= 0 else RED for v in monthly.values]
        ax_monthly.bar(monthly.index, monthly.values, color=bar_colors, width=20, alpha=0.85)
        ax_monthly.axhline(0, color=WHITE, linewidth=0.7, linestyle="--")
    ax_monthly.set_title("Monthly P&L (%)", color=WHITE, fontsize=10)
    ax_monthly.set_ylabel("Return (%)", color=WHITE, fontsize=8)
    ax_monthly.tick_params(axis="x", rotation=45)

    # Panel 4: win/loss distribution
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
    print("       Chart saved → backtest_results.png")
    plt.show()
