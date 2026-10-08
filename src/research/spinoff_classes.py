"""
MONAD Quant — spin-off drift (domain ``spinoff_drift``, family ``spinoff_drift.v1``),
exactly as frozen in docs/research/SPINOFF_PROTOCOL.md before any spin-off price was
loaded.

  * events: surviving spin-offs (SEC Form 10-12B registrants whose information statement,
    an EX-99.1 over 200 kB, was filed; listed today), each with its first 10-12B date;
  * event session: the ticker's first priced session in the snapshot, if within 30 days
    before to 540 days after the first 10-12B (else it was already listed, or abandoned);
  * buy at the close of event session + k, hold 252 sessions; each open position weighs
    1/max(open, 10), the remainder IWM; benchmark IWM 100%;
  * costs: tier ``smallcap`` for spin-offs, tier1 for IWM.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pandas as pd

from src.research.daily_data import DATA_DIR, Snapshot, SnapshotError
from src.research.daily_strategy import Tranche

INDEX = "IWM"
HOLD = 252
MIN_SLOTS = 10
BEFORE_DAYS, AFTER_DAYS = 30, 540
MIN_EVENTS_FOR_WINDOW = 10
ERAS = (("start", "2016-12-31"), ("2017-01-01", "2021-12-31"), ("2022-01-01", "end"))
REFERENCE = {"class": "spinoff_index", "params": {}}
PREFIX = "SPINEVENTS"


@dataclass(frozen=True)
class SpinEvents:
    sha: str
    events: pd.DataFrame          # ticker, cik, first_10_12b


def grid() -> list[dict]:
    return [{"class": "spinoff_hold", "params": {"entry": k}} for k in (1, 21)]


GRIDS = {"v1": grid}


def encode(rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["ticker", "cik", "first_10_12b"])
    for r in sorted(set(rows)):
        w.writerow(r)
    return buf.getvalue().encode("utf-8")


def load_events(sha: str, *, data_dir: Path | None = None) -> SpinEvents:
    base = Path(data_dir) if data_dir is not None else DATA_DIR
    data = gzip.decompress((base / f"{PREFIX}-{sha}.csv.gz").read_bytes())
    if hashlib.sha256(data).hexdigest() != sha:
        raise SnapshotError(f"{PREFIX}-{sha[:12]} does not hash to its name")
    return SpinEvents(sha=sha, events=pd.read_csv(io.BytesIO(data), parse_dates=["first_10_12b"]))


def event_sessions(snap: Snapshot, ev: SpinEvents) -> pd.DataFrame:
    """(ticker, d0) for events whose first priced session passes the protocol window."""
    rows = []
    for e in ev.events.itertuples(index=False):
        if e.ticker not in snap.assets:
            continue
        priced = snap.close[e.ticker].dropna()
        if not len(priced):
            continue
        first = priced.index[0]
        lo = e.first_10_12b - pd.Timedelta(days=BEFORE_DAYS)
        hi = e.first_10_12b + pd.Timedelta(days=AFTER_DAYS)
        if lo <= first <= hi:
            rows.append({"ticker": e.ticker, "d0": int(snap.dates.get_loc(first))})
    return pd.DataFrame(rows, columns=["ticker", "d0"])


def scoring_start(snap: Snapshot, ev: SpinEvents) -> pd.Timestamp:
    c = event_sessions(snap, ev)
    counts = pd.Series(0, index=range(len(snap.dates)))
    for d0 in c["d0"]:
        counts.iloc[d0] += 1
    ok = counts.rolling(252, min_periods=1).sum()
    ok = ok[ok >= MIN_EVENTS_FOR_WINDOW]
    if not len(ok):
        raise ValueError(f"never {MIN_EVENTS_FOR_WINDOW} events in a trailing year")
    return snap.dates[int(ok.index[0])]


def decide(snap: Snapshot, ev: SpinEvents, point: Mapping) -> list[Tranche]:
    dates = snap.dates
    n = len(dates)
    if point["class"] == "spinoff_index":
        return [Tranche(open_orders=pd.DataFrame(),
                        close_orders=pd.DataFrame({INDEX: [1.0]}, index=[dates[0]]))]
    if point["class"] != "spinoff_hold":
        raise ValueError(f"unknown spin-off class {point['class']!r}")
    k = int(point["params"]["entry"])
    held: list[set] = [set() for _ in range(n)]
    for e in event_sessions(snap, ev).itertuples(index=False):
        entry = e.d0 + k                                   # bought at this close
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
            idx.append(dates[j - 1])                       # decided one session before
            prev = key
    orders = pd.DataFrame(rows, index=pd.DatetimeIndex(idx)).fillna(0.0)
    return [Tranche(open_orders=pd.DataFrame(), close_orders=orders)]


def tiers(snap: Snapshot, ev: SpinEvents) -> dict:
    return {t: "smallcap" for t in snap.assets if t != INDEX}


def masked_events(ev: SpinEvents, cut: pd.Timestamp) -> SpinEvents:
    keep = pd.to_datetime(ev.events["first_10_12b"]) <= pd.Timestamp(cut)
    return SpinEvents(sha=f"{ev.sha}@{pd.Timestamp(cut).date()}", events=ev.events.loc[keep])


def truncation_violations(snap: Snapshot, ev: SpinEvents, point: Mapping, cuts) -> list[str]:
    from src.research import allocation_stats as stats
    full = decide(snap, ev, point)
    out = []
    for cut in cuts:
        cut = pd.Timestamp(cut)
        out += stats.compare_orders(full, decide(stats.masked_after(snap, cut),
                                                 masked_events(ev, cut), point), cut)
    return out
