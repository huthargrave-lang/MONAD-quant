"""
MONAD Quant — Insider purchase clusters against the small-cap index (domain
``insider_cluster``, family ``insider_cluster.v1``), exactly as frozen in
docs/research/INSIDER_CLUSTERS_PROTOCOL.md before any event-stock price was fetched.

  * an event (src/research/insider_data.py) counts if its ticker is priced in the snapshot
    and, on its decision session or one of the 5 before it, the close is within 30% of the
    insiders' purchase price (a reused ticker's prices will not match; nothing after the
    decision is read);
  * decided at the close of the first session on or after the known date, bought at the
    next close, sold ``hold`` sessions after that, at the close;
  * each open event weighs 1/max(open, 10); the remainder is IWM (always fully invested);
  * benchmark: IWM 100%; costs: tier ``smallcap`` for the stocks, tier1 for IWM.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd

from src.research.daily_data import Snapshot
from src.research.daily_strategy import Tranche

INDEX = "IWM"
MIN_SLOTS = 10
CORROBORATION_TOLERANCE = 0.30
CORROBORATION_LOOKBACK = 5
MIN_EVENTS_FOR_WINDOW = 10
ERAS = (("start", "2022-12-31"), ("2023-01-01", "2024-12-31"), ("2025-01-01", "end"))
REFERENCE = {"class": "insider_index", "params": {}}


@dataclass(frozen=True)
class InsiderEvents:
    sha: str
    events: pd.DataFrame          # ticker, issuer_cik, known, insiders, value, price


def grid() -> list[dict]:
    return [{"class": "insider_cluster", "params": {"hold": h, "min_insiders": m}}
            for h in (21, 63) for m in (3, 4)]


GRIDS = {"v1": grid}


def corroborated_events(snap: Snapshot, ev: InsiderEvents, min_insiders: int = 3) -> pd.DataFrame:
    """Events that pass the protocol's corroboration, with their decision session index."""
    dates = snap.dates
    rows = []
    for e in ev.events.itertuples(index=False):
        if e.insiders < min_insiders or e.ticker not in snap.assets:
            continue
        d0 = int(dates.searchsorted(pd.Timestamp(e.known)))
        if d0 >= len(dates):
            continue
        window = snap.close[e.ticker].iloc[max(0, d0 - CORROBORATION_LOOKBACK):d0 + 1].dropna()
        if not len(window) or not (np.abs(window / e.price - 1.0) <= CORROBORATION_TOLERANCE).any():
            continue
        rows.append({"ticker": e.ticker, "d0": d0, "insiders": e.insiders})
    return pd.DataFrame(rows, columns=["ticker", "d0", "insiders"])


def scoring_start(snap: Snapshot, ev: InsiderEvents) -> pd.Timestamp:
    c = corroborated_events(snap, ev)
    counts = pd.Series(0, index=range(len(snap.dates)))
    for d0 in c["d0"]:
        counts.iloc[d0] += 1
    trailing = counts.rolling(252, min_periods=1).sum()
    ok = trailing[trailing >= MIN_EVENTS_FOR_WINDOW]
    if not len(ok):
        raise ValueError("never 10 corroborated events in a trailing year")
    return snap.dates[int(ok.index[0])]


def decide(snap: Snapshot, ev: InsiderEvents, point: Mapping) -> list[Tranche]:
    dates = snap.dates
    n = len(dates)
    if point["class"] == "insider_index":
        orders = pd.DataFrame({INDEX: [1.0]}, index=[dates[0]])
        return [Tranche(open_orders=pd.DataFrame(), close_orders=orders)]
    if point["class"] != "insider_cluster":
        raise ValueError(f"unknown insider class {point['class']!r}")
    hold = int(point["params"]["hold"])
    c = corroborated_events(snap, ev, int(point["params"]["min_insiders"]))
    # positions[c] = tickers held after the close of session c
    held: list[dict] = [dict() for _ in range(n)]
    for e in c.itertuples(index=False):
        entry, exit_ = e.d0 + 1, e.d0 + 1 + hold          # executed at these closes
        for k in range(entry, min(exit_, n)):
            held[k][e.ticker] = held[k].get(e.ticker, 0) + 1
    rows, idx = [], []
    prev = None
    for k in range(1, n):
        names = held[k]
        slots = sum(names.values())
        w = {t: cnt / max(slots, MIN_SLOTS) for t, cnt in names.items()}
        w[INDEX] = 1.0 - sum(w.values())
        key = tuple(sorted((t, round(v, 12)) for t, v in w.items()))
        if key != prev:
            rows.append(w)
            idx.append(dates[k - 1])                      # decided one session before
            prev = key
    orders = pd.DataFrame(rows, index=pd.DatetimeIndex(idx)).fillna(0.0)
    return [Tranche(open_orders=pd.DataFrame(), close_orders=orders)]


def tiers(snap: Snapshot, ev: InsiderEvents) -> dict:
    return {t: "smallcap" for t in snap.assets if t != INDEX}


def masked_events(ev: InsiderEvents, cut: pd.Timestamp) -> InsiderEvents:
    keep = pd.to_datetime(ev.events["known"]) <= pd.Timestamp(cut)
    return InsiderEvents(sha=f"{ev.sha}@{pd.Timestamp(cut).date()}", events=ev.events.loc[keep])


def truncation_violations(snap: Snapshot, ev: InsiderEvents, point: Mapping, cuts) -> list[str]:
    from src.research import allocation_stats as stats
    full = decide(snap, ev, point)
    out = []
    for cut in cuts:
        cut = pd.Timestamp(cut)
        out += stats.compare_orders(full, decide(stats.masked_after(snap, cut),
                                                 masked_events(ev, cut), point), cut)
    return out
