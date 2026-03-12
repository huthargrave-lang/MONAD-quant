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

    # Adaptive Kelly state — tracks rolling WR to detect signal quality degradation
    # Resolve per-profile params: BTC_HOURLY_AGG uses _AGG suffixed config values
    _agg = config.ACTIVE_MODE == "BTC_HOURLY_AGG"
    def _ak(name, default):
        if _agg:
            return getattr(config, name + "_AGG", getattr(config, name, default))
        return getattr(config, name, default)

    use_adaptive_kelly  = _ak("USE_ADAPTIVE_KELLY", False)
    ak_lookback         = _ak("ADAPTIVE_KELLY_LOOKBACK",  20)
    ak_high_wr          = _ak("ADAPTIVE_KELLY_HIGH_WR",  0.55)
    ak_low_wr           = _ak("ADAPTIVE_KELLY_LOW_WR",   0.42)
    ak_pause_wr         = _ak("ADAPTIVE_KELLY_PAUSE_WR", 0.35)
    ak_high_mult        = _ak("ADAPTIVE_KELLY_HIGH_MULT",  1.4)
    ak_low_mult         = _ak("ADAPTIVE_KELLY_LOW_MULT",   0.5)
    ak_pause_mult       = _ak("ADAPTIVE_KELLY_PAUSE_MULT", 0.2)
    ak_high_cap         = _ak("ADAPTIVE_KELLY_HIGH_CAP",   0.28)
    recent_outcomes: deque = deque(maxlen=ak_lookback)

    # Collect actual per-trade capital contributions for accurate monthly display
    trade_capital_returns: dict = {}

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

        # Adaptive Kelly: scale position by rolling win rate of recent trades.
        # High WR → size up; degrading WR → size down; breakdown → near-flat.
        # Only activates after warm-up period (first ak_lookback trades use baseline).
        if use_adaptive_kelly and len(recent_outcomes) == ak_lookback:
            rolling_wr = sum(recent_outcomes) / ak_lookback
            if rolling_wr >= ak_high_wr:
                adaptive_mult = ak_high_mult
                pos_cap = max(pos_cap, ak_high_cap)   # allow slightly larger cap when WR is strong
            elif rolling_wr >= ak_low_wr:
                adaptive_mult = 1.0                   # normal — no change
            elif rolling_wr >= ak_pause_wr:
                adaptive_mult = ak_low_mult           # signal degrading — half position
            else:
                adaptive_mult = ak_pause_mult         # signal breakdown — near-flat
        else:
            adaptive_mult = 1.0

        kelly_trade = min(base_kelly * regime_mult * adx_mult * adaptive_mult, pos_cap)
        pct_change  = kelly_trade * r
        capital    += capital * pct_change
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
            tag = " ✓" if ret >= 0.005 else ""
            print(f"  {month.strftime('%Y-%m'):<12} {ret*100:>+7.2f}%  {count:>7}  {wr*100:>8.1f}%{tag}")
    avg_monthly = monthly_returns[monthly_returns != 0].mean()
    print("  " + "-" * 44)
    print(f"  {'Avg Monthly':<12} {avg_monthly*100:>+7.2f}%")
    print()

    if plot:
        _plot_results(equity, drawdown, monthly_returns, monthly_wr, monthly_counts,
                      df, initial_capital,
                      total_return, ann_return, sharpe, max_drawdown,
                      stats["win_rate"], stats["total_trades"], bh_return, bh_ann_return)

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


def _plot_results(equity, drawdown, monthly_returns, monthly_wr, monthly_counts,
                  price_df, initial_capital,
                  total_return, ann_return, sharpe, max_drawdown,
                  win_rate, total_trades, bh_return, bh_ann_return):
    # ── Palette ────────────────────────────────────────────────────────────
    BG      = "#0d1117"
    PANEL   = "#161b22"
    BORDER  = "#21262d"
    GRID    = "#21262d"
    TEXT    = "#e6edf3"
    MUTED   = "#8b949e"
    CYAN    = "#58a6ff"
    GREEN   = "#3fb950"
    RED     = "#f85149"
    ORANGE  = "#e3b341"
    AMBER   = "#d29922"

    TARGET_MONTHLY = 0.005  # 0.5%

    plt.rcParams.update({
        "figure.facecolor":  BG,
        "axes.facecolor":    PANEL,
        "axes.edgecolor":    BORDER,
        "axes.labelcolor":   MUTED,
        "axes.titlecolor":   TEXT,
        "xtick.color":       MUTED,
        "ytick.color":       MUTED,
        "xtick.labelsize":   8,
        "ytick.labelsize":   8,
        "grid.color":        GRID,
        "grid.linewidth":    0.5,
        "text.color":        TEXT,
        "font.family":       "monospace",
        "axes.spines.top":   False,
        "axes.spines.right": False,
    })

    fig = plt.figure(figsize=(14, 12))
    fig.suptitle("MONAD Quant  ·  Performance Dashboard",
                 fontsize=13, fontweight="bold", color=TEXT, y=0.99)

    gs = fig.add_gridspec(3, 1, height_ratios=[2.8, 2.2, 1.0],
                          hspace=0.45, left=0.08, right=0.96,
                          top=0.95, bottom=0.07)
    ax_eq = fig.add_subplot(gs[0])
    ax_mo = fig.add_subplot(gs[1])
    ax_dd = fig.add_subplot(gs[2])

    price_dates = price_df.index
    n_price     = len(price_dates)

    # ── helpers ────────────────────────────────────────────────────────────
    def _map_to_dates(series_len):
        """Map an equity/drawdown index (0..N) onto price_df date positions."""
        idx = np.linspace(0, n_price - 1, series_len).astype(int)
        return price_dates[np.clip(idx, 0, n_price - 1)]

    # ── Panel 1 · Equity Curve ─────────────────────────────────────────────
    bh_equity  = initial_capital * (price_df["close"] / price_df["close"].iloc[0])
    eq_dates   = _map_to_dates(len(equity))

    ax_eq.plot(price_dates, bh_equity.values,
               color=ORANGE, linewidth=1.0, alpha=0.55, linestyle="--", label="Buy & Hold")
    ax_eq.plot(eq_dates, equity.values,
               color=CYAN, linewidth=1.8, label="Strategy")
    ax_eq.fill_between(eq_dates, initial_capital, equity.values,
                        where=equity.values >= initial_capital,
                        color=CYAN, alpha=0.07)

    ax_eq.set_title("Equity Curve", fontsize=10, fontweight="bold", pad=6)
    ax_eq.set_ylabel("Capital ($)", fontsize=8)
    ax_eq.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax_eq.legend(fontsize=8, framealpha=0.25, loc="upper left")
    ax_eq.grid(True, alpha=0.35)

    # Stats box — top right
    alpha_pct = (total_return - bh_return) * 100
    stats_lines = [
        f"{'Return':<9} {total_return*100:>+6.2f}%  ({ann_return*100:>+.2f}% ann.)",
        f"{'Sharpe':<9} {sharpe:>7.3f}",
        f"{'Max DD':<9} {max_drawdown*100:>+6.2f}%",
        f"{'Win Rate':<9} {win_rate*100:>5.1f}%   ({total_trades} trades)",
        f"{'vs B&H':<9} {alpha_pct:>+6.2f}%  alpha",
    ]
    ax_eq.text(0.99, 0.97, "\n".join(stats_lines),
               transform=ax_eq.transAxes,
               fontsize=7.5, va="top", ha="right", fontfamily="monospace",
               bbox=dict(boxstyle="round,pad=0.5", facecolor=BG,
                         edgecolor=BORDER, alpha=0.85))

    # ── Panel 2 · Monthly Returns ──────────────────────────────────────────
    active_mo   = monthly_returns[monthly_returns != 0]
    active_wr   = monthly_wr.reindex(active_mo.index).fillna(0)
    active_cnt  = monthly_counts.reindex(active_mo.index).fillna(0)

    bar_colors = []
    for r in active_mo.values:
        if r >= TARGET_MONTHLY:
            bar_colors.append(GREEN)
        elif r >= 0:
            bar_colors.append(AMBER)
        else:
            bar_colors.append(RED)

    xs = np.arange(len(active_mo))
    ax_mo.bar(xs, active_mo.values * 100,
              color=bar_colors, alpha=0.85, edgecolor=BG, linewidth=0.4, width=0.72)
    ax_mo.axhline(TARGET_MONTHLY * 100, color=GREEN, linewidth=1.1,
                  linestyle="--", alpha=0.75, label=f"{TARGET_MONTHLY*100:.1f}% target")
    ax_mo.axhline(0, color=BORDER, linewidth=0.8)

    # Annotate monthly return value on each bar
    for i, ret in enumerate(active_mo.values):
        y_off = 0.04 if ret >= 0 else -0.04
        ax_mo.text(i, ret * 100 + y_off, f"{ret*100:+.2f}%",
                   ha="center", va="bottom" if ret >= 0 else "top",
                   fontsize=6, color=TEXT, fontweight="bold")

    ax_mo.set_title("Monthly Returns  ·  'Dividend' Schedule", fontsize=10,
                    fontweight="bold", pad=6)
    ax_mo.set_ylabel("Return (%)", fontsize=8)
    ax_mo.set_xticks(xs)
    ax_mo.set_xticklabels([m.strftime("%b '%y") for m in active_mo.index],
                           rotation=45, ha="right", fontsize=7)
    ax_mo.legend(fontsize=8, framealpha=0.25)
    ax_mo.grid(True, alpha=0.35, axis="y")

    pos_months  = (active_mo > 0).sum()
    hit_rate    = pos_months / len(active_mo) if len(active_mo) > 0 else 0
    avg_monthly = active_mo.mean()
    beat_target = (active_mo >= TARGET_MONTHLY).sum()
    summary = (
        f"Avg   {avg_monthly*100:>+5.2f}%\n"
        f"Hit   {hit_rate*100:>4.0f}%\n"
        f"≥0.5% {beat_target}/{len(active_mo)} mo"
    )
    ax_mo.text(0.995, 0.97, summary,
               transform=ax_mo.transAxes,
               fontsize=7.5, va="top", ha="right", fontfamily="monospace",
               bbox=dict(boxstyle="round,pad=0.5", facecolor=BG,
                         edgecolor=BORDER, alpha=0.85))

    # ── Panel 3 · Drawdown (% below all-time equity high) ───────────────────
    dd_dates = _map_to_dates(len(drawdown))
    dd_pct   = drawdown.values * 100

    ax_dd.fill_between(dd_dates, dd_pct, 0, color=RED, alpha=0.55)
    ax_dd.plot(dd_dates, dd_pct, color=RED, linewidth=0.6, alpha=0.8)
    ax_dd.axhline(0, color=BORDER, linewidth=0.8)

    # Mark the max drawdown point
    worst_idx = np.argmin(dd_pct)
    worst_val = dd_pct[worst_idx]
    ax_dd.annotate(
        f"Max DD: {worst_val:.2f}%",
        xy=(dd_dates[worst_idx], worst_val),
        xytext=(0.5, 0.15), textcoords="axes fraction",
        fontsize=7.5, fontweight="bold", color=RED,
        arrowprops=dict(arrowstyle="->", color=RED, lw=1.2),
        bbox=dict(boxstyle="round,pad=0.3", facecolor=BG, edgecolor=RED, alpha=0.85),
    )

    ax_dd.set_title("Drawdown  ·  Distance from equity peak (%)",
                    fontsize=10, fontweight="bold", pad=6)
    ax_dd.set_ylabel("Below peak (%)", fontsize=8)
    ax_dd.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.2f}%"))
    ax_dd.set_ylim(min(worst_val * 1.5, -0.1), 0.15)
    ax_dd.grid(True, alpha=0.35)

    plt.savefig("backtest_results.png", dpi=150, bbox_inches="tight", facecolor=BG)
    print("       Chart saved → backtest_results.png")
    plt.show()
