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
    df_feat = build_features(df)
    df_trades = generate_trades(df_feat,
                                require_signals=require_signals,
                                target_gain_pct=target_gain_pct,
                                stop_loss_pct=stop_loss_pct)

    # Compute individual trade returns
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

    # Performance metrics
    total_return = (equity.iloc[-1] - initial_capital) / initial_capital
    daily_returns = equity.pct_change().dropna()
    sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if daily_returns.std() > 0 else 0
    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max
    max_drawdown = drawdown.min()

    results = {
        "total_trades":    stats["total_trades"],
        "win_rate":        stats["win_rate"],
        "avg_win_pct":     stats["avg_win_pct"],
        "avg_loss_pct":    stats["avg_loss_pct"],
        "total_return":    round(total_return, 4),
        "sharpe_ratio":    round(sharpe, 3),
        "max_drawdown":    round(max_drawdown, 4),
        "final_capital":   round(equity.iloc[-1], 2),
        "kelly_position":  sizing,
        "equity_curve":    equity,
        "trade_returns":   trade_returns,
    }

    # Print summary
    print("[4/4] Results:")
    print(f"       Total Return:   {total_return*100:.2f}%")
    print(f"       Sharpe Ratio:   {sharpe:.3f}")
    print(f"       Max Drawdown:   {max_drawdown*100:.2f}%")
    print(f"       Final Capital:  ${equity.iloc[-1]:,.2f}")
    print(f"       Kelly Pos Size: {sizing['position_pct']}% (${sizing['position_dollars']:,.2f})")
    print("=" * 50)

    if plot:
        _plot_results(equity, drawdown, trade_returns, df_trades)

    return results


def _plot_results(equity, drawdown, trade_returns, df_trades):
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    fig.suptitle("MONAD Quant — Backtest Results", fontsize=14, fontweight="bold")

    # Equity curve
    axes[0].plot(equity.values, color="#00d4ff", linewidth=1.5)
    axes[0].set_title("Equity Curve")
    axes[0].set_ylabel("Capital ($)")
    axes[0].grid(True, alpha=0.3)
    axes[0].fill_between(range(len(equity)), equity.values, equity.values[0],
                          alpha=0.1, color="#00d4ff")

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

    plt.tight_layout()
    plt.savefig("backtest_results.png", dpi=150, bbox_inches="tight",
                facecolor="#1a1a2e")
    print("       Chart saved → backtest_results.png")
    plt.show()
