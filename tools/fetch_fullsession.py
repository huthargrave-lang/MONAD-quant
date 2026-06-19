#!/usr/bin/env python3
"""
Full-session hourly data fetcher (fixes research-web F10: morning-only data).

yfinance returns only ~3 bars/day (the volatile open, 13–15 UTC) when 1h data is
requested over a long (~710-day) range, but returns FULL 7-bar sessions (13–19/20
UTC) for shorter ranges — even 250-day chunks. So this rebuilds ~720 days of
full-session 1h bars by concatenating a few wide chunks, deduping the overlaps,
validating OHLC, and overwriting the morning-only cache at data/cache/{T}_1h.csv.

The result roughly TRIPLES bars/day (3 -> 7), tripling trade counts (better
statistics) and covering the full trading day rather than just the open.

Usage:
    venv/bin/python tools/fetch_fullsession.py QQQ SPY TQQQ AGG ...
    venv/bin/python tools/fetch_fullsession.py --universe conservative
"""
import argparse
import os
import sys
import time
from datetime import datetime, timedelta

import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.data.fetcher import fetch_yfinance  # noqa: E402

CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "cache")

UNIVERSES = {
    # Conservative bond-ETF-alternative candidates + leveraged ones for contrast.
    "conservative": [
        "SPY", "QQQ", "IWM", "DIA",          # broad indices (un-leveraged)
        "USMV", "SPLV", "SCHD", "VIG",       # low-vol / dividend
        "AGG", "BND", "LQD", "TLT", "IEF", "SHY", "TIP", "HYG",  # bond ETFs
        "TQQQ", "SOXL",                      # leveraged (contrast; expected noise-dominated)
    ],
}


def fetch_full(ticker, total_days=720, chunk_days=240, pause=2.0):
    """Fetch full-session 1h bars over `total_days` via wide chunks; dedupe + sort."""
    import pandas as pd
    frames = []
    end = datetime.now()
    earliest = end - timedelta(days=total_days)
    cur_end = end
    while cur_end > earliest:
        cur_start = max(cur_end - timedelta(days=chunk_days), earliest)
        try:
            df = fetch_yfinance(ticker, cur_start.strftime("%Y-%m-%d"),
                                cur_end.strftime("%Y-%m-%d"), interval="1h")
            if len(df):
                frames.append(df)
        except Exception as exc:
            print(f"    chunk {cur_start.date()}..{cur_end.date()} failed: {exc}")
        cur_end = cur_start
        time.sleep(pause)  # be kind to yfinance
    if not frames:
        return None
    out = pd.concat(frames)
    out = out[~out.index.duplicated(keep="first")].sort_index()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="*")
    ap.add_argument("--universe", choices=list(UNIVERSES))
    ap.add_argument("--days", type=int, default=720)
    args = ap.parse_args()

    tickers = list(args.tickers)
    if args.universe:
        tickers += [t for t in UNIVERSES[args.universe] if t not in tickers]
    if not tickers:
        ap.error("give tickers or --universe")

    os.makedirs(CACHE, exist_ok=True)
    print(f"Full-session fetch: {len(tickers)} tickers, ~{args.days}d each\n")
    for tk in tickers:
        df = fetch_full(tk, total_days=args.days)
        if df is None or not len(df):
            print(f"{tk:<6} FAILED (no data)")
            continue
        bpd = int(df.groupby(df.index.date).size().median())
        path = os.path.join(CACHE, f"{tk}_1h.csv")
        df.to_csv(path)
        print(f"{tk:<6} {len(df):5d} bars | {bpd} bars/day | {df.index[0].date()}..{df.index[-1].date()} -> {os.path.basename(path)}")
    print("\nDone. Re-run: tools/instrument_screen.py / tools/walkforward_eval.py")


if __name__ == "__main__":
    main()
