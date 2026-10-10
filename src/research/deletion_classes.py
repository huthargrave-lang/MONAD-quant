"""
MONAD Quant — S&P 500 deletion rebound (domain ``index_deletion``, family
``index_deletion.v1``), exactly as frozen in docs/research/INDEX_DELETION_PROTOCOL.md
before any deleted stock's price was loaded.

  * events: S&P 500 removals for market-capitalization changes since 2010 (Wikipedia's
    dated changes table; acquisitions, mergers and spin-offs excluded), each with its
    effective date;
  * event session: the first session on or after the effective date, if the stock is
    priced on it (a ticker later reused by another company has no price there);
  * buy at the close of event session + k, hold 252 sessions; each open position weighs
    1/max(open, 10), the remainder IJH; benchmark IJH 100%;
  * costs: tier ``tier2`` (mid caps, 5 bps after 2010) for deleted stocks, tier1 for IJH.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pandas as pd

from src.research import data_store
from src.research.daily_data import Snapshot
from src.research.daily_strategy import Tranche

INDEX = "IJH"
HOLD = 252
MIN_SLOTS = 10
MIN_EVENTS_FOR_WINDOW = 5
ERAS = (("start", "2016-12-31"), ("2017-01-01", "2021-12-31"), ("2022-01-01", "end"))
REFERENCE = {"class": "deletion_index", "params": {}}
PREFIX = "IDXDEL"


@dataclass(frozen=True)
class Deletions:
    sha: str
    events: pd.DataFrame          # ticker, effective


def grid() -> list[dict]:
    return [{"class": "deletion_hold", "params": {"entry": k}} for k in (1, 21)]


GRIDS = {"v1": grid}


def encode(rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["ticker", "effective"])
    for r in sorted(set(rows)):
        w.writerow(r)
    return buf.getvalue().encode("utf-8")


def load_events(sha: str, *, data_dir: Path | None = None,
                private_dir: Path | None = None) -> Deletions:
    """The deletions named ``sha``, verified (committed store, then private). The panel
    is derived from Wikipedia's changes table and carries its CC BY-SA 4.0 licence
    (docs/research/data/README.md)."""
    data = data_store.read(PREFIX, sha, data_dir=data_dir, private_dir=private_dir)
    return Deletions(sha=sha, events=pd.read_csv(io.BytesIO(data), parse_dates=["effective"]))


def event_sessions(snap: Snapshot, ev: Deletions) -> pd.DataFrame:
    rows = []
    for e in ev.events.itertuples(index=False):
        if e.ticker not in snap.assets:
            continue
        i = int(snap.dates.searchsorted(e.effective))
        if i >= len(snap.dates) or pd.isna(snap.close[e.ticker].iloc[i]):
            continue
        rows.append({"ticker": e.ticker, "d0": i})
    return pd.DataFrame(rows, columns=["ticker", "d0"])


def scoring_start(snap: Snapshot, ev: Deletions) -> pd.Timestamp:
    counts = pd.Series(0, index=range(len(snap.dates)))
    for d0 in event_sessions(snap, ev)["d0"]:
        counts.iloc[d0] += 1
    ok = counts.rolling(252, min_periods=1).sum()
    ok = ok[ok >= MIN_EVENTS_FOR_WINDOW]
    if not len(ok):
        raise ValueError(f"never {MIN_EVENTS_FOR_WINDOW} events in a trailing year")
    return snap.dates[int(ok.index[0])]


def decide(snap: Snapshot, ev: Deletions, point: Mapping) -> list[Tranche]:
    dates = snap.dates
    n = len(dates)
    if point["class"] == "deletion_index":
        return [Tranche(open_orders=pd.DataFrame(),
                        close_orders=pd.DataFrame({INDEX: [1.0]}, index=[dates[0]]))]
    if point["class"] != "deletion_hold":
        raise ValueError(f"unknown deletion class {point['class']!r}")
    k = int(point["params"]["entry"])
    held: list[set] = [set() for _ in range(n)]
    for e in event_sessions(snap, ev).itertuples(index=False):
        entry = e.d0 + k
        for j in range(entry, min(entry + HOLD, n)):
            held[j].add(e.ticker)
    rows, idx, prev = [], [], None
    for j in range(1, n):
        names = held[j]
        w = {t: 1.0 / max(len(names), MIN_SLOTS) for t in names}
        w[INDEX] = 1.0 - sum(w.values())
        key = tuple(sorted(names))
        if key != prev:
            rows.append(w)
            idx.append(dates[j - 1])
            prev = key
    orders = pd.DataFrame(rows, index=pd.DatetimeIndex(idx)).fillna(0.0)
    return [Tranche(open_orders=pd.DataFrame(), close_orders=orders)]


def tiers(snap: Snapshot, ev: Deletions) -> dict:
    return {t: "tier2" for t in snap.assets if t != INDEX}


def masked_events(ev: Deletions, cut: pd.Timestamp) -> Deletions:
    keep = pd.to_datetime(ev.events["effective"]) <= pd.Timestamp(cut)
    return Deletions(sha=f"{ev.sha}@{pd.Timestamp(cut).date()}", events=ev.events.loc[keep])


def truncation_violations(snap: Snapshot, ev: Deletions, point: Mapping, cuts) -> list[str]:
    from src.research import allocation_stats as stats
    full = decide(snap, ev, point)
    out = []
    for cut in cuts:
        cut = pd.Timestamp(cut)
        out += stats.compare_orders(full, decide(stats.masked_after(snap, cut),
                                                 masked_events(ev, cut), point), cut)
    return out
