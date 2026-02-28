"""
MONAD Quant - Backtest Runner
Full backtest loop with equity curve and performance metrics.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from src.strategy.engine import build_features, generate_trades, compute_trade_returns
from src.strategy.sizing import estimate_stats_from_backtest, compute_position_size


def run_backtest(df: pd.DataFrame,
                 initial_capital: float = 100_000,
                 target_gain_pct: float = 0.015,
                 stop_loss_pct: float = 0.01,
                 require_signals: int = 2,
                 kelly_multiplier: float = 0.5,
                 timeframe: str = "daily",
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
    if getattr(config, "VERBOSE_SIGNALS", False):
        _print_signal_diagnostics(df_feat, require_signals, use_regime,
                                  getattr(config, "USE_MA_REGIME_FILTER", False))
    df_trades = generate_trades(df_feat,
                                require_signals=require_signals,
                                target_gain_pct=target_gain_pct,
                                stop_loss_pct=stop_loss_pct,
                                use_regime_filter=use_regime,
                                use_ma_regime_filter=config.USE_MA_REGIME_FILTER)

    # Compute individual trade returns (indexed by entry timestamp)
    print("[2/4] Simulating trades...")
    trade_returns = compute_trade_returns(df_trades, target_gain_pct, stop_loss_pct)

    if len(trade_returns) == 0:
        print("No trades generated. Try loosening signal requirements.")
        return {}

    # Stats from backtest
    stats = estimate_stats_from_backtest(trade_returns)
    print(f"       {stats['total_trades']} trades | Win rate: {stats['win_rate']*100:.1f}%")

    # Position sizing
    sizing = compute_position_size(
        capital=initial_capital,
        win_rate=stats["win_rate"],
        avg_win_pct=stats["avg_win_pct"],
        avg_loss_pct=stats["avg_loss_pct"],
        kelly_multiplier=kelly_multiplier,
        min_position_pct=getattr(config, "MIN_POSITION_PCT", 0.0),
    )

    # Build equity curve
    print("[3/4] Computing equity curve...")
    capital = initial_capital
    equity_curve = [capital]
    for r in trade_returns:
        position = capital * sizing["kelly_capped"]
        capital += position * r
        equity_curve.append(capital)

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

    # Monthly "dividend" breakdown — scale by kelly_capped so it matches equity curve
    kelly_scaled = trade_returns * sizing["kelly_capped"]
    monthly_returns = kelly_scaled.resample("ME").apply(
        lambda x: (1 + x).prod() - 1 if len(x) > 0 else 0.0
    )
    monthly_counts = trade_returns.resample("ME").count()
    monthly_wr = trade_returns.resample("ME").apply(
        lambda x: (x > 0).sum() / len(x) if len(x) > 0 else 0.0
    )

    results = {
        "total_trades":     stats["total_trades"],
        "win_rate":         stats["win_rate"],
        "avg_win_pct":      stats["avg_win_pct"],
        "avg_loss_pct":     stats["avg_loss_pct"],
        "total_return":     round(total_return, 4),
        "sharpe_ratio":     round(sharpe, 3),
        "max_drawdown":     round(max_drawdown, 4),
        "final_capital":    round(equity.iloc[-1], 2),
        "kelly_position":   sizing,
        "equity_curve":     equity,
        "trade_returns":    trade_returns,
        "monthly_returns":  monthly_returns,
        "bh_return":        round(bh_return, 4),
    }

    # Print summary
    print("[4/4] Results:")
    print(f"       Total Return:   {total_return*100:.2f}%")
    print(f"       Annualized:     {ann_return*100:.2f}%")
    print(f"       Sharpe Ratio:   {sharpe:.3f}")
    print(f"       Max Drawdown:   {max_drawdown*100:.2f}%")
    print(f"       Final Capital:  ${equity.iloc[-1]:,.2f}")
    print(f"       Kelly Pos Size: {sizing['position_pct']}% (${sizing['position_dollars']:,.2f})")
    print("-" * 50)
    print(f"  vs Buy & Hold:")
    print(f"       B&H Return:     {bh_return*100:.2f}%")
    print(f"       B&H Annualized: {bh_ann_return*100:.2f}%")
    print(f"       B&H Final:      ${bh_final:,.2f}")
    alpha = total_return - bh_return
    print(f"       Alpha:          {alpha*100:>+.2f}%")
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
        _plot_results(equity, drawdown, trade_returns, monthly_returns,
                      df, initial_capital)

    return results


def _print_signal_diagnostics(df: pd.DataFrame, require_signals: int,
                               use_regime: bool, use_ma_regime: bool) -> None:
    """Print how many bars survive each filter layer so dead filters are obvious."""
    n = len(df)
    mom  = (df["momentum_signal"] != 0).sum()
    vol  = (df["volume_signal"]   != 0).sum()
    vote = ((df["momentum_signal"] + df["volume_signal"]).abs() >= require_signals).sum()

    long_mask  = (df["momentum_signal"] + df["volume_signal"]) >= require_signals
    short_mask = (df["momentum_signal"] + df["volume_signal"]) <= -require_signals

    if use_regime and "vol_regime" in df.columns:
        long_mask  = long_mask  & (df["vol_regime"] == 0)
        short_mask = short_mask & (df["vol_regime"] == 0)
    after_vol = (long_mask | short_mask).sum()

    if use_ma_regime and "ma_regime" in df.columns:
        long_mask  = long_mask  & (df["ma_regime"] == 1)
        short_mask = short_mask & (df["ma_regime"] == -1)
    after_ma = (long_mask | short_mask).sum()

    print(f"\n  Signal diagnostics ({n} bars total):")
    print(f"    momentum_signal != 0  : {mom:>4} bars")
    print(f"    volume_signal   != 0  : {vol:>4} bars")
    print(f"    signal_vote >= {require_signals}      : {vote:>4} bars")
    if use_regime:
        print(f"    + vol_regime filter   : {after_vol:>4} bars")
    if use_ma_regime:
        print(f"    + ma_regime  filter   : {after_ma:>4} bars  <- final candidates")
    print()


def _plot_results(equity, drawdown, trade_returns, monthly_returns,
                  price_df, initial_capital):
    fig, axes = plt.subplots(4, 1, figsize=(12, 14))
    fig.suptitle("MONAD Quant — Backtest Results", fontsize=14, fontweight="bold")

    # Equity curve + buy-and-hold overlay
    bh_equity = initial_capital * (price_df["close"] / price_df["close"].iloc[0])
    ax0_x = np.linspace(0, len(bh_equity) - 1, len(equity))
    axes[0].plot(ax0_x, equity.values, color="#00d4ff", linewidth=1.5, label="Strategy")
    axes[0].plot(range(len(bh_equity)), bh_equity.values, color="#ff8844",
                 linewidth=1.2, alpha=0.7, linestyle="--", label="Buy & Hold")
    axes[0].set_title("Equity Curve — Strategy vs Buy & Hold")
    axes[0].set_ylabel("Capital ($)")
    axes[0].legend(fontsize=9)
    axes[0].grid(True, alpha=0.3)

    # Drawdown
    axes[1].fill_between(range(len(drawdown)), drawdown.values, 0,
                          color="#ff4444", alpha=0.6)
    axes[1].set_title("Drawdown")
    axes[1].set_ylabel("Drawdown %")
    axes[1].grid(True, alpha=0.3)

    # Trade return distribution
    axes[2].hist(trade_returns * 100, bins=30, color="#44ff88", alpha=0.7, edgecolor="white")
    axes[2].axvline(0, color="white", linewidth=1, linestyle="--")
    axes[2].set_title("Trade Return Distribution")
    axes[2].set_xlabel("Return (%)")
    axes[2].set_ylabel("Frequency")
    axes[2].grid(True, alpha=0.3)

    # Monthly returns bar chart
    colors = ["#44ff88" if r >= 0 else "#ff4444" for r in monthly_returns.values]
    axes[3].bar(range(len(monthly_returns)), monthly_returns.values * 100,
                color=colors, alpha=0.8, edgecolor="white", linewidth=0.5)
    axes[3].axhline(5, color="#ffdd44", linewidth=1, linestyle="--", label="5% target")
    axes[3].axhline(0, color="white", linewidth=0.8)
    axes[3].set_title("Monthly Returns — 'Dividend' Schedule")
    axes[3].set_ylabel("Return (%)")
    axes[3].set_xticks(range(len(monthly_returns)))
    axes[3].set_xticklabels(
        [m.strftime("%b %y") for m in monthly_returns.index],
        rotation=45, ha="right", fontsize=8
    )
    axes[3].legend(fontsize=8)
    axes[3].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("backtest_results.png", dpi=150, bbox_inches="tight",
                facecolor="#1a1a2e")
    print("       Chart saved → backtest_results.png")
    plt.show()
