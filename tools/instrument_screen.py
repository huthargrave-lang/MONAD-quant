#!/usr/bin/env python3
"""
Noise-ratio instrument screener (research idea-web node E8; rule from F7).

This project's mean-reversion engine uses a fixed % stop. Whether it has an edge
on a given instrument is predicted by ONE number: how often a single bar's own
intrabar range can trigger the stop on noise alone, `P(bar range > stop)`.

  - 3x leveraged ETFs: ~94–100%  → stop is always inside the noise → coin-flip
    stop-outs → no edge (corr(stop_frac, win_rate) = -0.97 across 7 instruments).
  - QQQ ~37%, SPY ~17%           → stop sits OUTSIDE noise → fires only on genuine
    adverse moves → the mean-reversion edge survives (Sharpe ~3–4).

RULE (F7 / D3): only deploy this signal where `noise_ratio = stop_pct / median
intraday range > 1`, i.e. `P(bar range > stop)` is well below 0.5. Use this to
screen candidates BEFORE spending sweep/leak-free-validation time on them.

Usage:
    venv/bin/python tools/instrument_screen.py QQQ SPY TQQQ SOXL [--stop 0.005]
    # uncached tickers are fetched via yfinance (730d hourly); cached ones are reused.
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "cache")


def _load(ticker):
    path = os.path.join(CACHE, f"{ticker}_1h.csv")
    if os.path.exists(path):
        return pd.read_csv(path, index_col=0, parse_dates=True), "cache"
    from datetime import datetime, timedelta
    from src.data.fetcher import fetch_yfinance
    start = (datetime.now() - timedelta(days=710)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    return fetch_yfinance(ticker, start, end, interval="1h"), "fetch"


def screen(ticker, stop_pct):
    df, src = _load(ticker)
    rng = (df["high"] - df["low"]) / df["close"]      # intrabar range as % of close
    med_range = float(rng.median())
    p_bar_gt_stop = float((rng > stop_pct).mean())     # P(single bar can hit the stop)
    noise_ratio = stop_pct / med_range if med_range else float("inf")
    # Verdict: signal-friendly when the stop is usually OUTSIDE one bar's noise.
    if p_bar_gt_stop < 0.40:
        verdict = "SIGNAL-FRIENDLY"
    elif p_bar_gt_stop < 0.70:
        verdict = "marginal"
    else:
        verdict = "NOISE-DOMINATED (avoid)"
    return {
        "ticker": ticker, "src": src, "bars": len(df),
        "med_range_pct": round(med_range * 100, 3),
        "noise_ratio": round(noise_ratio, 2),
        "p_bar_gt_stop": round(p_bar_gt_stop, 3),
        "verdict": verdict,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--stop", type=float, default=0.005,
                    help="Stop-loss fraction to screen against (default 0.005 = 0.5%%, the 2:1 R:R stop).")
    args = ap.parse_args()

    print(f"\nNOISE-RATIO SCREEN  (stop={args.stop*100:.2f}%)  — rule: deploy only where "
          f"P(bar range > stop) is low (stop sits OUTSIDE intrabar noise)")
    hdr = f"{'TKR':<6}{'src':>6}{'bars':>6}{'medRange%':>10}{'noiseRatio':>11}{'P(bar>stop)':>12}  verdict"
    print(hdr); print("-" * len(hdr))
    rows = []
    for tk in args.tickers:
        try:
            rows.append(screen(tk, args.stop))
        except Exception as e:
            print(f"{tk:<6} (error: {e})")
    # Best (lowest noise) first.
    for r in sorted(rows, key=lambda x: x["p_bar_gt_stop"]):
        print(f"{r['ticker']:<6}{r['src']:>6}{r['bars']:>6}{r['med_range_pct']:>10}"
              f"{r['noise_ratio']:>11}{r['p_bar_gt_stop']:>12}  {r['verdict']}")
    print("\n(noise_ratio = stop / median intrabar range; want > 1. "
          "P(bar>stop) = fraction of bars whose own range can trigger the stop on noise.)\n")


if __name__ == "__main__":
    main()
