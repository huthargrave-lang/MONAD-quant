"""
MONAD Quant — commodity-to-equity linkage rules, exactly as frozen in
docs/research/COMMODITY_LINKAGE_CONFIRMATION.md (chosen by a board from the discovery
atlas, docs/research/data/commodity_atlas_discovery.json, before any confirmation-window
price was fetched).

Domain ``miner_metal_ratio``: gold miners overshoot gold, then partly revert.
  * ``ratio_tilt`` {miner, metal, window, slope}: z = (log(TR_miner / TR_metal) - its
    ``window``-session mean) / its ``window``-session std, data through the decision
    session; miner weight clip(0.5 - slope x z, 0, 1), the metal ETF the rest. Every 21
    sessions in 21 tranches at the open.
  * ``pair_static`` {weights}: the benchmark, 50/50 GDX/GLD, same schedule.

Domain ``oil_trend_equities``: oil equities lag crude's trend.
  * ``commodity_trend`` {fund, anchor, sma}: 100% ``fund`` while the anchor future's latest
    close on or before the session is above its ``sma``-observation simple moving average,
    else T-bills; decided at each close, executed at the next open, an order only when the
    state changes.
  * ``fund_static`` {asset}: the benchmark, 100% XLE, every 21 sessions in 21 tranches.
"""
from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd

from src.research.daily_classes import MONTH, OFFSETS, total_return_index
from src.research.daily_data import Snapshot, common_start
from src.research.daily_strategy import Tranche, static_tranches
from src.research.futures_panel import FuturesPanel

CONFIRMATION_START = pd.Timestamp("2016-01-01")
ERAS = (("start", "2019-12-31"), ("2020-01-01", "2022-12-31"), ("2023-01-01", "end"))
#: Declared prior search: every statistic of the discovery atlas (board, 2026-10-08).
ATLAS_CELLS = 1401

MINER, METAL, Z_WINDOW, SLOPE = "GDX", "GLD", 60, 0.25
RATIO_REFERENCE = {"class": "pair_static", "params": {"weights": {MINER: 0.5, METAL: 0.5}}}

FUND, ANCHOR, SMA = "XLE", "CL=F", 100
TREND_REFERENCE = {"class": "fund_static", "params": {"asset": FUND}}


def ratio_grid() -> list[dict]:
    return [{"class": "ratio_tilt", "params": {"miner": MINER, "metal": METAL,
                                               "window": Z_WINDOW, "slope": SLOPE}}]


def trend_grid() -> list[dict]:
    return [{"class": "commodity_trend", "params": {"fund": FUND, "anchor": ANCHOR, "sma": SMA}}]


def ratio_weights(snap: Snapshot, p: Mapping) -> pd.DataFrame:
    tr = total_return_index(snap.returns())
    lr = np.log(tr[p["miner"]] / tr[p["metal"]])
    n = int(p["window"])
    z = (lr - lr.rolling(n).mean()) / lr.rolling(n).std()
    w = (0.5 - float(p["slope"]) * z).clip(0.0, 1.0)
    return pd.DataFrame({p["miner"]: w, p["metal"]: 1.0 - w}).dropna()


def decide_ratio(snap: Snapshot, point: Mapping) -> list[Tranche]:
    p = point["params"]
    if point["class"] == "pair_static":
        return static_tranches(p["weights"], snap.dates, every=MONTH, offsets=OFFSETS)
    if point["class"] != "ratio_tilt":
        raise ValueError(f"unknown ratio class {point['class']!r}")
    w = ratio_weights(snap, p)
    return [Tranche(open_orders=w.reindex(snap.dates[off::MONTH]).dropna(),
                    close_orders=pd.DataFrame()) for off in OFFSETS]


def trend_state(snap: Snapshot, panel: FuturesPanel, p: Mapping) -> pd.Series:
    """1/0 per session where the SMA is defined, NaN otherwise. The SMA runs over the
    future's own observations (its calendar), then is read on each equity session."""
    fut = panel.close[p["anchor"]].dropna()
    avg = fut.rolling(int(p["sma"])).mean()
    above = (fut > avg).astype(float).where(avg.notna())
    return above.reindex(above.index.union(snap.dates)).ffill().reindex(snap.dates)


def decide_trend(snap: Snapshot, panel: FuturesPanel, point: Mapping) -> list[Tranche]:
    p = point["params"]
    if point["class"] == "fund_static":
        return static_tranches({p["asset"]: 1.0}, snap.dates, every=MONTH, offsets=OFFSETS)
    if point["class"] != "commodity_trend":
        raise ValueError(f"unknown trend class {point['class']!r}")
    on = trend_state(snap, panel, p).where(snap.close[p["fund"]].notna())
    w = pd.DataFrame({p["fund"]: on}).dropna()
    changed = w[p["fund"]].ne(w[p["fund"]].shift(1))
    return [Tranche(open_orders=w.loc[changed], close_orders=pd.DataFrame())]


def ratio_start(snap: Snapshot) -> pd.Timestamp:
    ready = ratio_weights(snap, ratio_grid()[0]["params"]).index[0]
    first = snap.dates[snap.dates >= CONFIRMATION_START][0]
    return max(common_start(snap, [MINER, METAL], MONTH), ready, first)


def trend_start(snap: Snapshot, panel: FuturesPanel) -> pd.Timestamp:
    ready = trend_state(snap, panel, trend_grid()[0]["params"]).first_valid_index()
    first = snap.dates[snap.dates >= CONFIRMATION_START][0]
    return max(common_start(snap, [FUND], MONTH), ready, first)


def ratio_truncation(snap: Snapshot, point: Mapping, cuts) -> list[str]:
    from src.research import allocation_stats as stats
    full = decide_ratio(snap, point)
    out = []
    for cut in cuts:
        cut = pd.Timestamp(cut)
        out += stats.compare_orders(full, decide_ratio(stats.masked_after(snap, cut), point), cut)
    return out


def trend_truncation(snap: Snapshot, panel: FuturesPanel, point: Mapping, cuts) -> list[str]:
    from src.research import allocation_stats as stats
    from src.research.futures_panel import masked_after
    full = decide_trend(snap, panel, point)
    out = []
    for cut in cuts:
        cut = pd.Timestamp(cut)
        out += stats.compare_orders(full, decide_trend(stats.masked_after(snap, cut),
                                                       masked_after(panel, cut), point), cut)
    return out
