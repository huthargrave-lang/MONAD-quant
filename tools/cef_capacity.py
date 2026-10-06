"""
cef_capacity — how much capital a registered CEF hypothesis could run before its own
trading becomes a large share of the funds' volume.

H404702's edge lives in closed-end funds that institutions cannot trade at size. That is
the mechanism's explanation, and also its limit. This tool measures the limit. It replays
the registered candidate's orders (``cef_classes.decide``, the same code the gate uses;
no returns are computed and no trial is recorded), sizes each tranche's trades at a given
portfolio value, and compares them with each fund's traded dollar volume.

For each portfolio value it reports, over every (session, fund) trade:
* the trade's participation (dollars traded / 20-session median dollar volume);
* the share of trades above 10% and 20% participation;
* the days needed to exit the largest holding at 10% participation.

Volume is daily share volume from Yahoo (``yfinance``), times the snapshot's raw close.
It is a research record of feasibility, not a recommendation.

  venv/bin/python tools/cef_capacity.py H404702 --since 2016-01-01 --json out.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.research import cef_classes as cc  # noqa: E402
from src.research import prereg  # noqa: E402
from src.research.daily_domains import CEF  # noqa: E402

AUM_GRID = (1e6, 5e6, 10e6, 25e6, 50e6, 100e6)
ADV_WINDOW = 20


def trade_weights(tranches, sessions: pd.DatetimeIndex) -> pd.DataFrame:
    """Portfolio-weight traded per (session, fund): each tranche holds 1/len(tranches) of
    the portfolio, and an order trades the change from that tranche's previous targets."""
    n = len(tranches)
    out = None
    for tr in tranches:
        orders = tr.close_orders.dropna(how="all").fillna(0.0)
        if orders.empty:
            continue
        delta = orders.diff().abs()
        delta.iloc[0] = orders.iloc[0].abs()
        part = delta / n
        out = part if out is None else out.add(part, fill_value=0.0)
    return out.reindex(sessions).fillna(0.0) if out is not None else pd.DataFrame(index=sessions)


def holdings(tranches) -> pd.DataFrame:
    """Portfolio weight held per (decision session, fund), averaged across tranches."""
    n = len(tranches)
    frames = [tr.close_orders.dropna(how="all").fillna(0.0) for tr in tranches]
    idx = sorted(set().union(*[f.index for f in frames]))
    cols = sorted(set().union(*[f.columns for f in frames]))
    total = sum(f.reindex(index=idx, columns=cols).ffill().fillna(0.0) for f in frames)
    return total / n


def dollar_volume(tickers, closes: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    import yfinance as yf
    vol = yf.download(list(tickers), start=start, end=end, auto_adjust=False, progress=False,
                      threads=True)["Volume"]
    vol = vol.reindex(index=closes.index, columns=closes.columns)
    return (vol * closes).rolling(ADV_WINDOW, min_periods=10).median().shift(1)


def capacity(trades: pd.DataFrame, held: pd.DataFrame, adv: pd.DataFrame) -> list[dict]:
    rows = []
    stacked_t = trades.stack()
    stacked_t = stacked_t[stacked_t > 0]
    adv_t = adv.stack().reindex(stacked_t.index)
    ok = adv_t.notna() & (adv_t > 0)
    stacked_t, adv_t = stacked_t[ok], adv_t[ok]
    held_last = held.reindex(adv.index, method="ffill")
    for aum in AUM_GRID:
        part = stacked_t * aum / adv_t
        pos = (held_last * aum).stack()
        adv_h = adv.stack().reindex(pos.index)
        days = (pos / (0.10 * adv_h)).replace([np.inf, -np.inf], np.nan).dropna()
        rows.append({
            "aum": aum, "trades": int(len(part)),
            "median_participation": float(part.median()),
            "p90_participation": float(part.quantile(0.9)),
            "share_above_10pct": float((part > 0.10).mean()),
            "share_above_20pct": float((part > 0.20).mean()),
            "median_days_to_exit_largest": float(
                days.groupby(level=0).max().median()) if len(days) else None,
        })
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hypothesis")
    ap.add_argument("--since", default="2016-01-01")
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    spec, _ = prereg.load(args.hypothesis)
    p = spec["params"]
    ctx = CEF.load(p["data"])
    tranches = cc.decide(ctx.snap, ctx.panel, p["candidate"])
    sessions = ctx.snap.dates[ctx.snap.dates >= pd.Timestamp(args.since)]
    trades = trade_weights(tranches, sessions)
    held = holdings(tranches)
    held = held[held.index >= pd.Timestamp(args.since)]
    traded = [c for c in trades.columns if trades[c].sum() > 0]
    closes = ctx.snap.close.reindex(index=sessions, columns=traded)
    adv = dollar_volume(traded, closes, args.since,
                        (ctx.snap.dates[-1] + pd.Timedelta(days=1)).date().isoformat())
    rows = capacity(trades[traded], held.reindex(columns=traded).fillna(0.0), adv)
    weight_thin = float((held.iloc[-1][adv.iloc[-1].reindex(held.columns) < 1e6]).sum()) \
        if len(held) else None
    out = {"hypothesis": args.hypothesis, "since": args.since, "funds_traded": len(traded),
           "adv_window": ADV_WINDOW, "latest_weight_in_funds_under_1m_adv": weight_thin,
           "median_fund_adv_latest": float(adv.iloc[-1].median()), "capacity": rows}
    for r in rows:
        print(f"AUM ${r['aum'] / 1e6:>5.0f}M  median part {r['median_participation']:6.2%}  "
              f"p90 {r['p90_participation']:6.2%}  >10% {r['share_above_10pct']:6.2%}  "
              f">20% {r['share_above_20pct']:6.2%}  exit-largest {r['median_days_to_exit_largest']:.1f}d")
    print(f"funds traded {len(traded)}; median fund ADV ${out['median_fund_adv_latest'] / 1e6:.2f}M; "
          f"latest weight in funds under $1M ADV {weight_thin:.1%}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"schema_version": 1, **out}, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
