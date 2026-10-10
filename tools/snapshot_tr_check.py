#!/usr/bin/env python3
"""
MONAD Quant — cross-check a frozen snapshot's total returns against Yahoo's adjusted close.

A snapshot builds total return from raw closes plus booked distributions (dividends and
capital gains). If yfinance leaves a fund's capital gains empty, its total return is
understated, silently. This tool compares, per asset and calendar year, the snapshot's
total return with the return of Yahoo's dividend-and-split-adjusted close, and lists every
year further apart than the tolerance (docs/research/RISKY_PICKS_PROTOCOL.md: 1%).

It reads prices only; it records no trial.

    venv/bin/python tools/snapshot_tr_check.py --snapshot <sha> [--tolerance 0.01] [ASSET ...]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import daily_data  # noqa: E402
from src.research.daily_classes import total_return_index  # noqa: E402

TOLERANCE = 0.01


def yahoo_adjusted(symbol: str, start: str, end: str) -> pd.Series:
    import yfinance as yf
    h = yf.Ticker(symbol).history(start=start, end=end, auto_adjust=True, actions=False)
    s = h["Close"]
    s.index = pd.DatetimeIndex(s.index.date)
    return s


def yearly(index: pd.Series) -> pd.Series:
    """Calendar-year return of a level series, from each year's last level to the next."""
    last = index.dropna().groupby(index.dropna().index.year).last()
    first_year = index.dropna().index[0].year
    out = last.pct_change()
    # The first (partial) year: from the first level to the year's last.
    out.loc[first_year] = last.loc[first_year] / index.dropna().iloc[0] - 1.0
    return out


def compare(snap: daily_data.Snapshot, assets, *, tolerance: float = TOLERANCE,
            fetch: Callable[[str, str, str], pd.Series] = yahoo_adjusted) -> list[dict]:
    tr = total_return_index(snap.returns())
    start = snap.dates[0].date().isoformat()
    end = (snap.dates[-1] + pd.Timedelta(days=1)).date().isoformat()
    rows = []
    for a in assets:
        ours = tr[a].dropna()
        theirs = fetch(a, start, end).reindex(ours.index).dropna()
        ours = ours.reindex(theirs.index)
        yo, yt = yearly(ours), yearly(theirs)
        for year in yo.index:
            gap = float(yo[year] - yt[year])
            rows.append({"asset": a, "year": int(year), "snapshot": float(yo[year]),
                         "yahoo_adjusted": float(yt[year]), "gap": gap,
                         "flag": abs(gap) > tolerance})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--tolerance", type=float, default=TOLERANCE)
    ap.add_argument("assets", nargs="*", help="default: every asset in the snapshot")
    args = ap.parse_args(argv)
    snap = daily_data.load_snapshot(args.snapshot)
    rows = compare(snap, args.assets or snap.assets, tolerance=args.tolerance)
    flagged = [r for r in rows if r["flag"]]
    for r in flagged:
        print(f"{r['asset']:6} {r['year']}  snapshot {r['snapshot']:+.2%}  yahoo adjusted "
              f"{r['yahoo_adjusted']:+.2%}  gap {r['gap']:+.2%}")
    print(f"{len(flagged)} of {len(rows)} asset-years beyond {args.tolerance:.1%}")
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
