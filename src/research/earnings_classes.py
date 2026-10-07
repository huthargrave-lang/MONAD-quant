"""
MONAD Quant — the earnings-announcement premium in small caps (domain
``earnings_premium``, family ``earnings_premium.v1``), exactly as frozen in
docs/research/EARNINGS_PREMIUM_PROTOCOL.md before any announcement-window return was
computed.

Stocks earn more in the window in which they are expected to announce earnings (Frazzini
and Lamont 2007; Barber et al. 2013). "Expected" uses only the past: a stock is an
expected announcer at session t if it filed an earnings 8-K (Item 2.02) in the same
calendar window one year earlier, (t - 365, t - 365 + h] in calendar days. Nothing about
the coming announcement is read.

  * eligible at t: priced at t, 252 sessions listed, and 4 or more earnings 8-Ks filed
    before t;
  * candidate (``earn_window``, h days): equal weight over eligible expected announcers,
    decided at t's close and traded at the next close (daily), if at least 20 qualify;
    otherwise equal weight over all eligible stocks;
  * benchmark (``earn_universe``): equal weight over all eligible stocks, every 21
    sessions in 21 tranches;
  * costs: tier ``smallcap``; window: from the first session with 200 eligible stocks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd

from src.research.daily_classes import MONTH, OFFSETS
from src.research.daily_data import Snapshot
from src.research.daily_strategy import Tranche

INDEX = "IWM"
LISTED_SESSIONS = 252
MIN_HISTORY = 4
MIN_NAMES = 20
MIN_ELIGIBLE = 200
LOOKBACK_DAYS = 365
ERAS = (("start", "2022-12-31"), ("2023-01-01", "2024-12-31"), ("2025-01-01", "end"))
REFERENCE = {"class": "earn_universe", "params": {}}


@dataclass(frozen=True)
class Announcements:
    sha: str
    dates: pd.DataFrame          # ticker, filed (earnings 8-K filing date)


def grid() -> list[dict]:
    return [{"class": "earn_window", "params": {"days": h}} for h in (7, 30)]


GRIDS = {"v1": grid}


def _matrices(snap: Snapshot, ann: Announcements, days: int):
    """(names, eligible[t, name], expected[t, name]) as boolean frames on the snapshot."""
    names = sorted(set(ann.dates["ticker"]) & set(snap.assets) - {INDEX})
    sess = snap.dates.values.astype("datetime64[D]")
    lo = sess - np.timedelta64(LOOKBACK_DAYS, "D")
    hi = lo + np.timedelta64(days, "D")
    hist, expd = {}, {}
    by = ann.dates.groupby("ticker")["filed"]
    for n in names:
        d = np.sort(pd.to_datetime(by.get_group(n)).values.astype("datetime64[D]"))
        hist[n] = np.searchsorted(d, sess, side="left")                     # filed before t
        expd[n] = np.searchsorted(d, hi, side="right") - np.searchsorted(d, lo, side="right")
    close = snap.close[names]
    priced = close.notna()
    eligible = priced & (priced.cumsum() >= LISTED_SESSIONS) & \
        (pd.DataFrame(hist, index=snap.dates)[names] >= MIN_HISTORY)
    expected = eligible & (pd.DataFrame(expd, index=snap.dates)[names] > 0)
    return names, eligible, expected


def scoring_start(snap: Snapshot, ann: Announcements) -> pd.Timestamp:
    c = _matrices(snap, ann, 7)[1].sum(axis=1)
    ok = c[c >= MIN_ELIGIBLE]
    if not len(ok):
        raise ValueError(f"never {MIN_ELIGIBLE} eligible stocks")
    return ok.index[0]


def _equal(row: pd.Series) -> dict:
    members = list(row.index[row])
    return {m: 1.0 / len(members) for m in members} if members else {}


def decide(snap: Snapshot, ann: Announcements, point: Mapping) -> list[Tranche]:
    if point["class"] == "earn_universe":
        names, elig, _ = _matrices(snap, ann, 7)
        out = []
        for off in OFFSETS:
            rows = {d: _equal(elig.loc[d]) for d in snap.dates[off::MONTH]}
            w = pd.DataFrame.from_dict(rows, orient="index").reindex(columns=names).fillna(0.0)
            w.index = pd.DatetimeIndex(w.index)
            out.append(Tranche(open_orders=pd.DataFrame(), close_orders=w.sort_index()))
        return out
    if point["class"] != "earn_window":
        raise ValueError(f"unknown earnings class {point['class']!r}")
    names, elig, expd = _matrices(snap, ann, int(point["params"]["days"]))
    rows, idx, prev = [], [], None
    for d in snap.dates:
        e = expd.loc[d]
        w = _equal(e) if int(e.sum()) >= MIN_NAMES else _equal(elig.loc[d])
        key = tuple(sorted(w))
        if key != prev:
            rows.append(w)
            idx.append(d)
            prev = key
    orders = pd.DataFrame(rows, index=pd.DatetimeIndex(idx)).reindex(columns=names).fillna(0.0)
    return [Tranche(open_orders=pd.DataFrame(), close_orders=orders)]


def tiers(snap: Snapshot, ann: Announcements) -> dict:
    return {t: "smallcap" for t in snap.assets if t != INDEX}


def masked_announcements(ann: Announcements, cut: pd.Timestamp) -> Announcements:
    keep = pd.to_datetime(ann.dates["filed"]) <= pd.Timestamp(cut)
    return Announcements(sha=f"{ann.sha}@{pd.Timestamp(cut).date()}", dates=ann.dates.loc[keep])


def truncation_violations(snap: Snapshot, ann: Announcements, point: Mapping, cuts) -> list[str]:
    from src.research import allocation_stats as stats
    full = decide(snap, ann, point)
    out = []
    for cut in cuts:
        cut = pd.Timestamp(cut)
        out += stats.compare_orders(full, decide(stats.masked_after(snap, cut),
                                                 masked_announcements(ann, cut), point), cut)
    return out
