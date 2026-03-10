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
                 target_gain_pct: float = 0.030,
                 stop_loss_pct: float = 0.015,
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
    use_slope_regime = getattr(config, "USE_SLOPE_REGIME", False)
    if getattr(config, "VERBOSE_SIGNALS", False):
        _print_signal_diagnostics(df_feat, require_signals, use_regime,
                                  getattr(config, "USE_MA_REGIME_FILTER", False),
                                  use_slope_regime=use_slope_regime)
    df_trades = generate_trades(df_feat,
                                require_signals=require_signals,
                                use_regime_filter=use_regime,
                                use_ma_regime_filter=config.USE_MA_REGIME_FILTER,
                                use_slope_regime=use_slope_regime,
                                longs_only=getattr(config, "LONGS_ONLY", False))

    # Compute individual trade returns (indexed by entry timestamp)
    print("[2/4] Simulating trades...")
    bar_limit_overrides = {}
    target_overrides    = {}
    stop_overrides      = {}

    if use_slope_regime and "regime" in df_trades.columns:
        # Bear defensive longs: exit faster — don't hold into deepening downtrend
        if getattr(config, "BEAR_DEFENSIVE_LONGS", False):
            bear_bars = getattr(config, "BEAR_MAX_TRADE_BARS", 10)
            for idx in df_trades[(df_trades["entry_signal"] == 1) & (df_trades["regime"] == "BEAR")].index:
                bar_limit_overrides[idx] = bear_bars

        # Bull longs: wider target and longer hold — let winners run in confirmed uptrend
        bull_target = getattr(config, "TARGET_GAIN_PCT_STRONG_BULL", target_gain_pct)
        bull_bars   = getattr(config, "MAX_TRADE_BARS_STRONG_BULL",  config.MAX_TRADE_BARS)
        for idx in df_trades[(df_trades["entry_signal"] == 1) & (df_trades["regime"] == "STRONG_BULL")].index:
            target_overrides[idx]    = bull_target
            bar_limit_overrides[idx] = bull_bars

        # Bear shorts: quick exit + wider stop (crypto swings 3-5% intraday, 1.5% is noise)
        # ONLY ACTIVE WHEN LONGS_ONLY=False
        if not getattr(config, "LONGS_ONLY", True):
            bear_short_bars = getattr(config, "BEAR_SHORT_MAX_BARS", 10)
            bear_short_stop = getattr(config, "BEAR_SHORT_STOP_PCT",  0.025)
            short_in_bear   = (df_trades["entry_signal"] == -1) & df_trades["regime"].isin({"BEAR", "STRONG_BEAR"})
            for idx in df_trades[short_in_bear].index:
                bar_limit_overrides[idx] = bear_short_bars
                stop_overrides[idx]      = bear_short_stop

        # ATR-based dynamic stops: widen stop when volatility spikes above 2× normal.
        # Prevents noise-triggered exits during intra-bull corrections (June/Aug 2024).
        # Disabled by default (USE_ATR_DYNAMIC_STOPS=False).
        if getattr(config, "USE_ATR_DYNAMIC_STOPS", False) and "atr_pct" in df_trades.columns:
            atr_stop_mult = getattr(config, "ATR_STOP_MULT", 2.0)
            atr_stop_cap  = getattr(config, "ATR_STOP_CAP_PCT", 0.04)
            atr_baseline  = df_trades["atr_pct"].rolling(20, min_periods=5).median()
            high_vol_entries = df_trades[
                (df_trades["entry_signal"] != 0) &
                (df_trades["atr_pct"] > atr_baseline * atr_stop_mult)
            ].index
            for idx in high_vol_entries:
                new_stop = min(df_trades.at[idx, "atr_pct"] * 1.0, atr_stop_cap)
                if new_stop > stop_loss_pct:   # only override if it's wider than default
                    stop_overrides[idx] = new_stop

    trade_returns, trade_exit_types = compute_trade_returns(
        df_trades, target_gain_pct, stop_loss_pct,
        max_trade_bars=config.MAX_TRADE_BARS,
        bar_limit_overrides=bar_limit_overrides or None,
        target_overrides=target_overrides or None,
        stop_overrides=stop_overrides or None,
    )

    if len(trade_returns) == 0:
        print("No trades generated. Try loosening signal requirements.")
        return {}

    # Stats from backtest
    stats = estimate_stats_from_backtest(trade_returns)
    vc = trade_exit_types.value_counts()
    print(f"       {stats['total_trades']} trades | Win rate: {stats['win_rate']*100:.1f}%"
          f"  (target={vc.get('target_hit', 0)}  stop={vc.get('stop_hit', 0)}"
          f"  time={vc.get('time_exit', 0)})")

    # Position sizing
    sizing = compute_position_size(
        capital=initial_capital,
        win_rate=stats["win_rate"],
        avg_win_pct=stats["avg_win_pct"],
        avg_loss_pct=stats["avg_loss_pct"],
        kelly_multiplier=kelly_multiplier,
        min_position_pct=getattr(config, "MIN_POSITION_PCT", 0.0),
    )

    # Build equity curve with per-trade Kelly scaling
    print("[3/4] Computing equity curve...")
    capital = initial_capital
    equity_curve = [capital]

    # Regime → Kelly multiplier map from config (with fallback defaults)
    regime_mult_map = {
        "STRONG_BULL": getattr(config, "KELLY_MULT_STRONG_BULL", 1.5),
        "BULL":        getattr(config, "KELLY_MULT_BULL",        1.0),
        "STALLING":    getattr(config, "KELLY_MULT_STALLING",   0.75),
        "RECOVERING":  getattr(config, "KELLY_MULT_RECOVERING", 0.75),
        "BEAR":        getattr(config, "KELLY_MULT_BEAR",        0.75),
        "STRONG_BEAR": getattr(config, "KELLY_MULT_STRONG_BEAR", 0.5),
    }

    for idx, r in trade_returns.items():
        base_kelly = sizing["kelly_capped"]

        # Regime-based Kelly scaling (per-trade, not one global fraction)
        if (use_slope_regime
                and "regime_kelly_mult" in df_trades.columns
                and idx in df_trades.index):
            regime_mult = df_trades.at[idx, "regime_kelly_mult"]
        else:
            regime_mult = 1.0

        # ADX-based Kelly scaling
        if (getattr(config, "USE_ADX_SIZING", False)
                and "adx_kelly_mult" in df_trades.columns
                and idx in df_trades.index):
            adx_mult = df_trades.at[idx, "adx_kelly_mult"]
        else:
            adx_mult = 1.0

        # STRONG_BULL gets a higher position cap so Kelly ×1.5 isn't truncated at the base 20%
        if (use_slope_regime
                and idx in df_trades.index
                and df_trades.at[idx, "regime"] == "STRONG_BULL"):
            pos_cap = getattr(config, "MAX_POSITION_PCT_STRONG_BULL", config.MAX_POSITION_PCT)
        else:
            pos_cap = config.MAX_POSITION_PCT
        kelly_trade = min(base_kelly * regime_mult * adx_mult, pos_cap)
        capital += capital * kelly_trade * r
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
        "exit_types":       trade_exit_types,
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
                               use_regime: bool, use_ma_regime: bool,
                               use_slope_regime: bool = False) -> None:
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

    if use_slope_regime and "regime" in df.columns:
        no_long_regimes  = {"STRONG_BEAR", "BEAR"}
        no_short_regimes = {"STRONG_BULL", "BULL", "RECOVERING"}
        long_mask  = long_mask  & (~df["regime"].isin(no_long_regimes))
        short_mask = short_mask & (~df["regime"].isin(no_short_regimes))
        after_regime = (long_mask | short_mask).sum()
    elif use_ma_regime and "ma_regime" in df.columns:
        long_mask  = long_mask  & (df["ma_regime"] == 1)
        short_mask = short_mask & (df["ma_regime"] == -1)
        after_regime = (long_mask | short_mask).sum()
    else:
        after_regime = None

    print(f"\n  Signal diagnostics ({n} bars total):")
    print(f"    momentum_signal != 0  : {mom:>4} bars")
    print(f"    volume_signal   != 0  : {vol:>4} bars")
    print(f"    signal_vote >= {require_signals}      : {vote:>4} bars")
    if use_regime:
        print(f"    + vol_regime filter   : {after_vol:>4} bars")
    if after_regime is not None:
        label = "slope regime" if use_slope_regime else "ma_regime   "
        print(f"    + {label} filter : {after_regime:>4} bars  <- final candidates")

    # Regime distribution
    if "regime" in df.columns:
        print(f"\n  Regime distribution ({n} bars):")
        mult_lookup = {
            "STRONG_BULL": 1.5, "BULL": 1.0,
            "STALLING": 0.75,   "RECOVERING": 0.75,
            "BEAR": 0.75,       "STRONG_BEAR": 0.5,
        }
        import config as _cfg
        bear_defensive = getattr(_cfg, "BEAR_DEFENSIVE_LONGS", False)
        longs_only     = getattr(_cfg, "LONGS_ONLY", True)
        direction_lookup = {
            "STRONG_BULL": "longs only",
            "BULL":        "longs only",
            "STALLING":    "shorts (standard RSI gate)" if not longs_only else "flat",
            "RECOVERING":  "longs only",
            "BEAR":        ("defensive longs (RSI<30, ×0.25K) + shorts (RSI>60, ×0.5K)"
                            if (bear_defensive and not longs_only)
                            else ("defensive longs (RSI<30, ×0.25K)" if bear_defensive else
                                  ("shorts (RSI>60, ×0.5K)" if not longs_only else "flat"))),
            "STRONG_BEAR": "shorts (RSI>58, ×0.75K)" if not longs_only else "flat",
        }
        for state in ["STRONG_BULL", "BULL", "STALLING", "RECOVERING", "BEAR", "STRONG_BEAR"]:
            count = (df["regime"] == state).sum()
            mult  = mult_lookup.get(state, 1.0)
            direction = direction_lookup.get(state, "both")
            print(f"    {state:<14}: {count:>4} bars  (Kelly ×{mult}, {direction})")
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
