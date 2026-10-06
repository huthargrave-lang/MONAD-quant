"""
MONAD Quant — Crypto trend-following against a static crypto/cash blend (domain
``crypto_trend``, family ``crypto_trend.v1``). Correlation atlas idea C091.

Question: does holding Bitcoin only while its total-return index is above a long moving
average beat a STATIC blend that holds half Bitcoin, half T-bills? Buy and hold is the
wrong bar: a trend filter carries less risk on average, and a static blend at a comparable
exposure is the fair comparison (the D6 logic, applied to crypto). The blend's 50% is
fixed here, before any trial, not fitted to the filters' realised exposure.

Frozen 2026-10-06, before any return on the snapshot was examined:
  * trend: BTC 100% while TR > SMA(n) of TR, else cash; checked at every daily close,
    traded at the next close (crypto has no opening print: snapshots flag every open);
    n in {50, 100, 200, 365} days;
  * reference: 50% BTC / 50% cash, rebalanced every 30 days in 30 staggered tranches;
  * costs: tier ``crypto``, 25 bps one-way;
  * eras: through 2017 (the early market), 2018-2021, 2022 on.
"""
from __future__ import annotations

from typing import Mapping

import pandas as pd

from src.research.daily_classes import total_return_index
from src.research.daily_data import SessionReturns, Snapshot
from src.research.daily_strategy import Tranche, static_tranches

ASSET = "BTC-USD"
MA_DAYS = (50, 100, 200, 365)
WARMUP_DAYS = max(MA_DAYS)
REBALANCE_DAYS = 30
ERAS = (("start", "2017-12-31"), ("2018-01-01", "2021-12-31"), ("2022-01-01", "end"))
REFERENCE = {"class": "crypto_static_half", "params": {"weight": 0.5, "every": REBALANCE_DAYS}}


def grid() -> list[dict]:
    return [{"class": "crypto_trend", "params": {"ma_days": n}} for n in MA_DAYS]


GRIDS = {"v1": grid}


def trend(snap: Snapshot, params: Mapping, rets: SessionReturns | None = None) -> list[Tranche]:
    n = int(params["ma_days"])
    rets = rets or snap.returns()
    tr = total_return_index(rets)[ASSET]
    sma = tr.rolling(n, min_periods=n).mean()
    on = (tr > sma).astype(float).where(sma.notna())
    orders = pd.DataFrame({ASSET: on}).dropna()
    # Only state CHANGES need an order; repeating the target every day is equivalent but
    # makes the tranche's order book needlessly long.
    changed = orders[ASSET].ne(orders[ASSET].shift(1))
    return [Tranche(open_orders=pd.DataFrame(), close_orders=orders[changed])]


def reference(snap: Snapshot, params: Mapping | None = None,
              rets: SessionReturns | None = None) -> list[Tranche]:
    tranches = static_tranches({ASSET: 0.5}, snap.dates, every=REBALANCE_DAYS,
                               offsets=range(REBALANCE_DAYS))
    # Crypto trades at the close: move the static orders from open to close.
    return [Tranche(open_orders=pd.DataFrame(), close_orders=t.open_orders) for t in tranches]


def decide(snap: Snapshot, point: Mapping, rets: SessionReturns | None = None) -> list[Tranche]:
    if point["class"] == "crypto_trend":
        return trend(snap, point["params"], rets)
    if point["class"] == "crypto_static_half":
        return reference(snap, point["params"], rets)
    raise ValueError(f"unknown crypto class {point['class']!r}")


def scoring_start(snap: Snapshot) -> pd.Timestamp:
    first = snap.close[ASSET].first_valid_index()
    return snap.dates[snap.dates.get_loc(first) + WARMUP_DAYS + 1]


def tiers(snap: Snapshot) -> dict:
    return {ASSET: "crypto"}


def truncation_violations(snap: Snapshot, point: Mapping, cuts) -> list[str]:
    from src.research import allocation_stats as stats
    full = decide(snap, point)
    out = []
    for cut in cuts:
        cut = pd.Timestamp(cut)
        out += stats.compare_orders(full, decide(stats.masked_after(snap, cut), point), cut)
    return out

