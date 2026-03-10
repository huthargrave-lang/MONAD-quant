"""
MONAD Quant — Walk-Forward Parameter Optimizer

Rolls a train/test window across the full price history and selects the best
parameter combination on each training window. The selected parameters are then
applied to the out-of-sample (OOS) test window and the OOS trade returns are
collected. Final stats are computed from the concatenated OOS returns only —
no look-ahead bias.

Why walk-forward instead of ML?
  An ML model trained on 5 years of daily BTC (1,827 bars) will overfit.
  Walk-forward optimization achieves the same adaptive goal ("what params work
  best right now?") using only recent history, is fully interpretable, and
  produces out-of-sample validation automatically.

Usage:
  python main.py --mode=walk-forward
"""

import itertools
import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

from src.strategy.engine import build_features, generate_trades, compute_trade_returns
from src.strategy.sizing import estimate_stats_from_backtest, compute_position_size
import config as _cfg


# Default search grid — small enough to finish in < 5 seconds
DEFAULT_PARAM_GRID = {
    "rsi_oversold":    [30, 33, 35, 38, 40],
    "target_gain_pct": [0.010, 0.015, 0.020],
    "stop_loss_pct":   [0.010, 0.015],
}


def _sharpe(returns: pd.Series) -> float:
    """Annualised Sharpe (daily assumption) from a series of trade returns."""
    if len(returns) < 3 or returns.std() == 0:
        return -np.inf
    return (returns.mean() / returns.std()) * np.sqrt(252)


def _run_slice(df_slice: pd.DataFrame, rsi_oversold: int,
               target_gain_pct: float, stop_loss_pct: float) -> pd.Series:
    """
    Run one backtest slice with specific params.
    Returns trade_returns Series (empty on failure).
    """
    require_signals = _cfg.REQUIRE_SIGNALS
    longs_only = getattr(_cfg, "LONGS_ONLY", True)
    use_slope  = getattr(_cfg, "USE_SLOPE_REGIME", True)

    df_feat = build_features(
        df_slice,
        timeframe="daily",
        signal_overrides={"rsi_oversold": rsi_oversold},
    )
    df_trades = generate_trades(
        df_feat,
        require_signals=require_signals,
        use_regime_filter=_cfg.USE_REGIME_FILTER,
        use_ma_regime_filter=_cfg.USE_MA_REGIME_FILTER,
        use_slope_regime=use_slope,
        longs_only=longs_only,
    )

    # Per-trade bar limits for bear defensive longs
    bear_limit_overrides = None
    if use_slope and getattr(_cfg, "BEAR_DEFENSIVE_LONGS", False) and "regime" in df_trades.columns:
        bear_bars = getattr(_cfg, "BEAR_MAX_TRADE_BARS", 10)
        bear_entries = df_trades[
            (df_trades["entry_signal"] == 1) & (df_trades["regime"] == "BEAR")
        ].index
        if len(bear_entries):
            bear_limit_overrides = {idx: bear_bars for idx in bear_entries}

    returns, _exit_types = compute_trade_returns(
        df_trades, target_gain_pct, stop_loss_pct,
        max_trade_bars=_cfg.MAX_TRADE_BARS,
        bar_limit_overrides=bear_limit_overrides,
    )
    return returns


def _make_windows(df: pd.DataFrame, train_months: int, test_months: int):
    """
    Generate (train_df, test_df) window pairs by rolling forward test_months at a time.
    Returns list of (train_start, train_end, test_start, test_end) tuples (datetime).
    """
    start = df.index[0]
    end   = df.index[-1]
    windows = []
    test_start = start + relativedelta(months=train_months)
    while test_start + relativedelta(months=test_months) <= end + relativedelta(days=1):
        train_start = test_start - relativedelta(months=train_months)
        test_end    = test_start + relativedelta(months=test_months)
        windows.append((train_start, test_start, test_start, test_end))
        test_start += relativedelta(months=test_months)
    return windows


def walk_forward_optimize(df: pd.DataFrame,
                           param_grid: dict = None,
                           train_months: int = 18,
                           test_months: int = 6) -> dict:
    """
    Walk-forward parameter optimization over a full price history.

    For each rolling window:
      1. Enumerate all parameter combinations in param_grid
      2. Run each on the training slice; select the combination with highest Sharpe
      3. Apply the winning combination to the out-of-sample test slice
      4. Collect OOS trade returns

    Args:
        df: Full OHLCV DataFrame (indexed by date)
        param_grid: Dict of param_name → list of values to try.
                    Defaults to DEFAULT_PARAM_GRID.
        train_months: Months of history used to select parameters.
        test_months: Months of OOS data the winning params are applied to.

    Returns:
        Dict with keys: oos_trade_returns, per_window_params, summary_stats, window_table.
    """
    if param_grid is None:
        # Use asset-specific grid from config if defined, else fall back to default
        param_grid = getattr(_cfg, "WALK_FORWARD_PARAM_GRID", DEFAULT_PARAM_GRID)

    windows = _make_windows(df, train_months, test_months)
    if not windows:
        raise ValueError(
            f"Not enough data for walk-forward. Need at least "
            f"{train_months + test_months} months, got "
            f"{(df.index[-1] - df.index[0]).days // 30} months."
        )

    # All combinations as list of dicts
    keys   = list(param_grid.keys())
    combos = [dict(zip(keys, vals)) for vals in itertools.product(*param_grid.values())]
    n_combos = len(combos)

    print("\n" + "=" * 56)
    print("  MONAD QUANT — WALK-FORWARD OPTIMIZER")
    print("=" * 56)
    print(f"  Train window : {train_months} months")
    print(f"  Test window  : {test_months} months")
    print(f"  Windows      : {len(windows)}")
    print(f"  Combinations : {n_combos} per window  ({n_combos * len(windows)} total backtests)")
    print(f"  Grid         : {param_grid}")
    print()

    all_oos_returns = []
    per_window_params = []
    window_rows = []

    for w_idx, (train_start, train_end, test_start, test_end) in enumerate(windows):
        train_df = df.loc[train_start:train_end].iloc[:-1]  # exclude test_start row
        test_df  = df.loc[test_start:test_end]

        if len(train_df) < 30 or len(test_df) < 5:
            continue

        # ── Optimize on training window ──────────────────────────────────────
        best_sharpe = -np.inf
        best_combo  = combos[0]
        for combo in combos:
            train_returns = _run_slice(
                train_df,
                rsi_oversold=combo["rsi_oversold"],
                target_gain_pct=combo["target_gain_pct"],
                stop_loss_pct=combo["stop_loss_pct"],
            )
            s = _sharpe(train_returns)
            if s > best_sharpe:
                best_sharpe = s
                best_combo  = combo

        # ── Apply best params to OOS test window ─────────────────────────────
        oos_returns = _run_slice(
            test_df,
            rsi_oversold=best_combo["rsi_oversold"],
            target_gain_pct=best_combo["target_gain_pct"],
            stop_loss_pct=best_combo["stop_loss_pct"],
        )

        oos_sharpe = _sharpe(oos_returns)
        oos_wr     = (oos_returns > 0).mean() if len(oos_returns) else float("nan")

        per_window_params.append(best_combo)
        all_oos_returns.append(oos_returns)

        window_rows.append({
            "window":         f"{test_start.strftime('%Y-%m')} → {test_end.strftime('%Y-%m')}",
            "best_rsi":       best_combo["rsi_oversold"],
            "best_target":    f"{best_combo['target_gain_pct']*100:.1f}%",
            "best_stop":      f"{best_combo['stop_loss_pct']*100:.1f}%",
            "train_sharpe":   round(best_sharpe, 2),
            "oos_trades":     len(oos_returns),
            "oos_win_rate":   f"{oos_wr*100:.0f}%" if not np.isnan(oos_wr) else "—",
            "oos_sharpe":     round(oos_sharpe, 2) if oos_sharpe != -np.inf else "—",
        })

        print(f"  [{w_idx+1}/{len(windows)}] OOS {test_start.strftime('%Y-%m')}→{test_end.strftime('%Y-%m')}"
              f"  best: RSI<{best_combo['rsi_oversold']}"
              f"  tgt={best_combo['target_gain_pct']*100:.1f}%"
              f"  stp={best_combo['stop_loss_pct']*100:.1f}%"
              f"  → OOS trades={len(oos_returns)}"
              f"  OOS Sharpe={oos_sharpe:.2f}")

    # ── Aggregate OOS results ─────────────────────────────────────────────────
    if not all_oos_returns or all(len(r) == 0 for r in all_oos_returns):
        print("\n  No OOS trades generated — try broadening the param grid or reducing train_months.")
        return {}

    combined_oos = pd.concat([r for r in all_oos_returns if len(r) > 0]).sort_index()
    stats = estimate_stats_from_backtest(combined_oos)
    oos_sharpe_total = _sharpe(combined_oos)

    # Equity curve from OOS returns (equal-weight for display)
    sizing = compute_position_size(
        capital=_cfg.INITIAL_CAPITAL,
        win_rate=stats["win_rate"],
        avg_win_pct=stats["avg_win_pct"],
        avg_loss_pct=stats["avg_loss_pct"],
        kelly_multiplier=_cfg.KELLY_MULTIPLIER,
    )
    capital = _cfg.INITIAL_CAPITAL
    for r in combined_oos:
        capital += capital * sizing["kelly_capped"] * r
    oos_total_return = (capital - _cfg.INITIAL_CAPITAL) / _cfg.INITIAL_CAPITAL

    # Print summary
    print()
    print("  " + "─" * 54)
    print("  OUT-OF-SAMPLE SUMMARY (no look-ahead bias)")
    print("  " + "─" * 54)
    print(f"  OOS Trades      : {stats['total_trades']}")
    print(f"  OOS Win Rate    : {stats['win_rate']*100:.1f}%")
    print(f"  OOS Sharpe      : {oos_sharpe_total:.3f}")
    print(f"  OOS Total Return: {oos_total_return*100:.2f}%")
    print(f"  OOS Final Cap   : ${capital:,.2f}")
    print()

    # Per-window parameter table
    print("  " + "─" * 80)
    print(f"  {'OOS Window':<24} {'RSI':>5} {'Target':>8} {'Stop':>6} "
          f"{'Train Sh':>9} {'Trades':>7} {'WR':>6} {'OOS Sh':>8}")
    print("  " + "─" * 80)
    for row in window_rows:
        print(f"  {row['window']:<24} {row['best_rsi']:>5} {row['best_target']:>8} "
              f"{row['best_stop']:>6} {row['train_sharpe']:>9} {row['oos_trades']:>7} "
              f"{row['oos_win_rate']:>6} {str(row['oos_sharpe']):>8}")
    print("  " + "─" * 80)
    print()

    return {
        "oos_trade_returns": combined_oos,
        "per_window_params": per_window_params,
        "oos_sharpe":        oos_sharpe_total,
        "oos_total_return":  oos_total_return,
        "final_capital":     capital,
        "window_table":      window_rows,
    }
