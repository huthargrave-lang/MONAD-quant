#!/usr/bin/env python3
"""
Honest rolling-origin walk-forward evaluator (C5) — leak-free OOS.

The sweep selects its winner BY holdout score, so its reported "holdout" numbers
are the best-of-many on the holdout (optimistically biased). This evaluator
removes that leak: it walks an EXPANDING window across the data and, for each
out-of-sample fold, selects params using ONLY the prior data, then evaluates on
the held fold. The concatenated OOS trade returns therefore contain no selection
leakage — they are an honest read on whether an edge survives out of sample.

Uses cached hourly OHLCV, the live FIXED 10% sizing, and the C3 round-trip cost
baked into every trade. Reports per-fold selected params + aggregate OOS metrics.

Usage:
    venv/bin/python tools/walkforward_eval.py TQQQ TNA LABU [--objective ev|sharpe] [--folds 5]
"""
import argparse
import contextlib
import io
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from src.backtest.runner import run_backtest
from src.backtest import metrics
from src.optimization.sweep_scoring import ev_score, live_score
from src.optimization.sweep_costs import estimate_spread, round_trip_cost_pct

# Small, fixed candidate grid (target, stop, rsi_oversold). 2:1 R:R family.
GRID = [(t, t / 2, rsi)
        for t in (0.008, 0.010, 0.014)
        for rsi in (70, 80, 90)]


def _configure(ticker, target, stop, rsi):
    """Inject the per-ticker hourly config the engine reads (same shape sweep.py
    uses), with live fixed-10% sizing. Varies target/stop/rsi per candidate."""
    mode = f"{ticker}_HOURLY"
    base = {"RSI_PERIOD": 7, "RSI_OVERBOUGHT": 62, "MACD_FAST": 6, "MACD_SLOW": 13,
            "MACD_SIGNAL": 4, "VWAP_WINDOW": 10, "VWAP_ZSCORE_THRESH": 0.3, "BB_WINDOW": 14}
    for k, v in base.items():
        setattr(config, f"{k}_{mode}", getattr(config, f"{k}_{mode}", v))
    setattr(config, f"RSI_OVERSOLD_{mode}", rsi)
    config.ASSETS[mode] = {
        "type": f"etf_hourly_{ticker.lower()}", "target_gain_pct": target,
        "stop_loss_pct": stop, "require_signals": 1, "rsi_oversold": rsi,
        "rsi_overbought": getattr(config, f"RSI_OVERBOUGHT_{mode}"),
        "vwap_zscore_thresh": getattr(config, f"VWAP_ZSCORE_THRESH_{mode}"),
    }
    config._MODE_TO_ASSET[mode] = mode
    config.ACTIVE_MODE = mode
    config.PLOT_RESULTS = False
    config.VERBOSE_SIGNALS = False
    config.POSITION_SIZING_MODE = "fixed"
    config.FIXED_POSITION_PCT = 0.10
    config.USE_ADAPTIVE_KELLY = False


def _bt(df, ticker, target, stop, rsi, cost):
    _configure(ticker, target, stop, rsi)
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            return run_backtest(df=df.copy(), target_gain_pct=target, stop_loss_pct=stop,
                                require_signals=1, timeframe="hourly", plot=False,
                                backtest_mode="realistic", slippage_pct=cost)
        except Exception:
            return None


def walkforward(df, ticker, objective="ev", n_folds=4, min_train_frac=0.5):
    cost = round_trip_cost_pct(estimate_spread(float(df["close"].median()), None),
                               float(df["close"].median()))
    score_fn = ev_score if objective == "ev" else live_score
    n = len(df)
    start = int(n * min_train_frac)          # first selection uses >= half the data
    step = max((n - start) // n_folds, 1)
    oos_returns, picks = [], []
    for k in range(n_folds):
        tr_end = start + k * step
        te_end = n if k == n_folds - 1 else start + (k + 1) * step
        # ── Select params on prior data only (df[:tr_end]) ──
        best = (-1e9, None)
        for (t, s, rsi) in GRID:
            r = _bt(df.iloc[:tr_end], ticker, t, s, rsi, cost)
            sc = score_fn(r) if r else -9999
            if sc > best[0]:
                best = (sc, (t, s, rsi))
        t, s, rsi = best[1]
        # ── OOS with full feature warmup: run on df[:te_end] (features are causal,
        #    .shift(1)), keep only trades AFTER the train boundary. The params never
        #    saw post-tr_end data, so these trades are genuine OOS. ──
        train_end_ts = df.index[tr_end - 1]
        r_full = _bt(df.iloc[:te_end], ticker, t, s, rsi, cost)
        oos = pd.Series(dtype=float)
        if r_full and len(r_full.get("trade_returns", [])):
            tr = r_full["trade_returns"]
            oos = tr[tr.index > train_end_ts]
        picks.append({"fold": k + 1, "train_bars": tr_end, "oos_bars": te_end - tr_end,
                      "params": (t, s, rsi), "oos_trades": len(oos)})
        if len(oos):
            oos_returns.append(oos)
    if not oos_returns:
        return {"error": "no OOS trades"}, picks

    combined = pd.concat(oos_returns).sort_index()  # leak-free OOS per-trade returns
    # Fixed-10% compounding equity from the concatenated OOS trades.
    eq = [1.0]
    for r in combined:
        eq.append(eq[-1] * (1 + 0.10 * r))
    equity = pd.Series(eq)
    total_return = metrics.total_return(equity, 1.0)
    tpy = metrics.trades_per_year(len(combined), combined.index[0], combined.index[-1])
    sharpe = metrics.annualized_sharpe(equity.pct_change().dropna(), tpy)
    months = max((combined.index[-1] - combined.index[0]).days / 30.44, 1e-9)
    return {
        "oos_trades": len(combined),
        "win_rate_pct": round(float((combined > 0).mean()) * 100, 1),
        "total_return_pct": round(total_return * 100, 2),
        "avg_monthly_pct": round(((1 + total_return) ** (1 / months) - 1) * 100, 3),
        "sharpe": round(sharpe, 2),
        "max_drawdown_pct": round(metrics.max_drawdown(equity) * 100, 2),
        "round_trip_cost_pct": round(cost * 100, 3),
        "oos_span_months": round(months, 1),
    }, picks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--objective", default="ev", choices=["ev", "sharpe"])
    ap.add_argument("--folds", type=int, default=4)
    args = ap.parse_args()

    cache = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
    print(f"\nLEAK-FREE WALK-FORWARD (expanding window, {args.folds} OOS folds, "
          f"fixed 10%, realistic+cost, objective={args.objective})")
    print("Each fold's params chosen ONLY on prior data — no holdout-selection leak.\n")
    hdr = f"{'TKR':<6}{'OOS_tr':>7}{'WR%':>6}{'tot%':>7}{'avg/mo%':>8}{'Sharpe':>7}{'DD%':>7}{'span_mo':>8}"
    print(hdr); print("-" * len(hdr))
    for tk in args.tickers:
        path = os.path.join(cache, f"{tk}_1h.csv")
        if not os.path.exists(path):
            print(f"{tk:<6} (no cached data at {path})"); continue
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        res, picks = walkforward(df, tk, objective=args.objective, n_folds=args.folds)
        if "error" in res:
            print(f"{tk:<6} {res['error']}"); continue
        print(f"{tk:<6}{res['oos_trades']:>7}{res['win_rate_pct']:>6}{res['total_return_pct']:>7}"
              f"{res['avg_monthly_pct']:>8}{res['sharpe']:>7}{res['max_drawdown_pct']:>7}{res['oos_span_months']:>8}")
    print()


if __name__ == "__main__":
    main()
