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

CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "cache")

# Floors for a usable full-session hourly panel. A US session is 7 hourly bars;
# the F12 artifact was a panel averaging ~3, so 5 rejects it while allowing
# half-days and holidays to pull the median down slightly.
MIN_BARS = 500
MIN_BARS_PER_DAY = 5

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
    """Full-session 1h bars over ``total_days``, via the canonical loader
    (fetcher.load_session_bars). This tool used to carry its own chunked fetch, which
    swallowed a failed chunk and wrote a silently shortened panel; the loader refuses
    instead, and applies the New York session. Returns None when the loader refuses."""
    from src.data.fetcher import MAX_HOURLY_LOOKBACK_DAYS, SessionDataError, load_session_bars
    end = datetime.now()
    start = end - timedelta(days=min(total_days, MAX_HOURLY_LOOKBACK_DAYS))
    try:
        return load_session_bars(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"),
                                 pause=pause)
    except SessionDataError as exc:
        print(f"    {ticker}: refused: {exc}")
        return None


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
        # A PARTIAL fetch is the dangerous case here, not an empty one. This tool's
        # 710-day fetch returning morning-only bars is the documented root cause of
        # the backtest-vs-live mismatch (F12/F13), and an empty-only check would
        # write that panel happily. Refuse anything too short to be a real session
        # panel, or too few bars per day to be full-session.
        if len(df) < MIN_BARS or bpd < MIN_BARS_PER_DAY:
            print(f"{tk:<6} REFUSED ({len(df)} bars, {bpd}/day) — need >={MIN_BARS} "
                  f"bars and >={MIN_BARS_PER_DAY}/day. A partial or morning-only "
                  f"panel is exactly the F12 artifact; not written.")
            continue
        path = os.path.join(CACHE, f"{tk}_1h.csv")
        df.to_csv(path)
        print(f"{tk:<6} {len(df):5d} bars | {bpd} bars/day | {df.index[0].date()}..{df.index[-1].date()} -> {os.path.basename(path)}")
    print("\nDone. Re-run: tools/instrument_screen.py / tools/walkforward_eval.py")


if __name__ == "__main__":
    main()
