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


EXECUTIONS = ("open", "close")


def ratio_point(miner: str = MINER, metal: str = METAL, *, execution: str = "open", lag: int = 1,
                fresh: bool = False, fixings: bool = False) -> dict:
    """The frozen rule on one pair, with the execution options a historical test needs
    (docs/research/MINER_TILT_PREPERIOD.md). Defaults are left out of the params so the
    specs recorded before an option existed keep their hashes.

    * ``execution`` "close": trade at a close, for data with no opening print;
    * ``lag`` k: an order decided at session t's close executes at session t+k (k = 1 is
      the rule; larger k is a robustness ladder against measurement noise);
    * ``fresh``: decide only on a session at which both legs printed a NEW close (a
      carried fixing or an unchanged index close is stale): a scheduled decision on a
      stale session moves to the next fresh one, so no decision reads a stale leg;
    * ``fixings``: execute only on a session at which the metal leg FIXED (the snapshot
      manifest's ``calendars[metal]``, a scheduled exchange calendar known in advance like
      the NYSE's): an execution falling on a session that carries an older fixing moves to
      the next fixing session, so no trade is booked at a price the miner leg has already
      moved past.
    """
    if execution not in EXECUTIONS:
        raise ValueError(f"unknown execution {execution!r}")
    if int(lag) != lag or lag < 1:
        raise ValueError("lag must be a whole number of sessions >= 1")
    params = {"miner": miner, "metal": metal, "window": Z_WINDOW, "slope": SLOPE}
    if execution != "open":
        params["execution"] = execution
    if lag != 1:
        params["lag"] = int(lag)
    if fresh:
        params["fresh"] = True
    if fixings:
        params["fixings"] = True
    return {"class": "ratio_tilt", "params": params}


def ratio_grid(miner: str = MINER, metal: str = METAL, *, execution: str = "open") -> list[dict]:
    """The frozen rule on one pair (docs/research/MINER_TILT_REPLICATION.md replicates it
    unchanged on other pairs)."""
    return [ratio_point(miner, metal, execution=execution)]


def ratio_reference(miner: str = MINER, metal: str = METAL, *, execution: str = "open",
                    fixings: bool = False) -> dict:
    """The 50/50 benchmark; with ``fixings`` it trades only on the metal's fixing
    sessions, as the candidate does (``fixings`` names that asset)."""
    params = {"weights": {miner: 0.5, metal: 0.5}}
    if execution != "open":
        params["execution"] = execution
    if fixings:
        params["fixings"] = metal
    return {"class": "pair_static", "params": params}


def trend_grid() -> list[dict]:
    return [{"class": "commodity_trend", "params": {"fund": FUND, "anchor": ANCHOR, "sma": SMA}}]


def ratio_weights(snap: Snapshot, p: Mapping) -> pd.DataFrame:
    tr = total_return_index(snap.returns())
    lr = np.log(tr[p["miner"]] / tr[p["metal"]])
    n = int(p["window"])
    z = (lr - lr.rolling(n).mean()) / lr.rolling(n).std()
    w = (0.5 - float(p["slope"]) * z).clip(0.0, 1.0)
    return pd.DataFrame({p["miner"]: w, p["metal"]: 1.0 - w}).dropna()


def fresh_sessions(snap: Snapshot, legs) -> pd.Series:
    """True where every leg is priced and its close differs from the previous session's
    (an unchanged close is a carried fixing or a stale print). Known at that close."""
    c = snap.close[list(legs)]
    changed = c.ne(c.shift(1)) & c.notna() & c.shift(1).notna()
    return changed.all(axis=1)


def _on_schedule(w: pd.DataFrame, dates: pd.DatetimeIndex, execution: str, *, lag: int = 1,
                 fresh: pd.Series | None = None,
                 execute_on: pd.DatetimeIndex | None = None) -> list[Tranche]:
    """Every 21 sessions in 21 tranches. A scheduled decision session (moved forward to
    the next ``fresh`` session when given) takes that session's weights; the order
    executes ``lag`` sessions later (moved forward to the next session in ``execute_on``
    when given) at the open ("open") or close ("close"). The engine executes an order at
    the session after its index, so it is indexed one session before its execution; that
    placement reads no prices (``execute_on`` is a scheduled calendar)."""
    if execution not in EXECUTIONS:
        raise ValueError(f"unknown execution {execution!r}")
    pos = {d: i for i, d in enumerate(dates)}
    fresh_pos = None if fresh is None else np.flatnonzero(fresh.reindex(dates).fillna(False).to_numpy())
    exec_pos = None if execute_on is None else np.flatnonzero(dates.isin(execute_on))
    out = []
    for off in OFFSETS:
        rows, idx = [], []
        for d in dates[off::MONTH]:
            i = pos[d]
            if fresh_pos is not None:
                k = np.searchsorted(fresh_pos, i)
                if k == len(fresh_pos):
                    continue
                i = int(fresh_pos[k])
            if dates[i] not in w.index or w.loc[dates[i]].isna().any():
                continue
            e = i + lag
            if exec_pos is not None:
                k = np.searchsorted(exec_pos, e)
                if k == len(exec_pos):
                    continue
                e = int(exec_pos[k])
            j = e - 1
            if j >= len(dates) - 1:
                continue
            if idx and dates[j] <= idx[-1]:
                continue                        # two decisions moved onto one session: keep the first
            rows.append(w.loc[dates[i]])
            idx.append(dates[j])
        orders = pd.DataFrame(rows, index=pd.DatetimeIndex(idx), columns=w.columns)
        out.append(Tranche(open_orders=orders, close_orders=pd.DataFrame()) if execution == "open"
                   else Tranche(open_orders=pd.DataFrame(), close_orders=orders))
    return out


def decide_ratio(snap: Snapshot, point: Mapping) -> list[Tranche]:
    p = point["params"]
    execution = p.get("execution", "open")
    if point["class"] == "pair_static":
        if execution == "open" and not p.get("fixings"):
            return static_tranches(p["weights"], snap.dates, every=MONTH, offsets=OFFSETS)
        w = pd.DataFrame([p["weights"]] * len(snap.dates), index=snap.dates)
        w = w.loc[snap.close[list(p["weights"])].notna().all(axis=1)]
        execute_on = fixing_calendar(snap, p["fixings"]) if p.get("fixings") else None
        return _on_schedule(w, snap.dates, execution, execute_on=execute_on)
    if point["class"] != "ratio_tilt":
        raise ValueError(f"unknown ratio class {point['class']!r}")
    fresh = fresh_sessions(snap, [p["miner"], p["metal"]]) if p.get("fresh") else None
    execute_on = fixing_calendar(snap, p["metal"]) if p.get("fixings") else None
    return _on_schedule(ratio_weights(snap, p), snap.dates, execution, lag=int(p.get("lag", 1)),
                        fresh=fresh, execute_on=execute_on)


def fixing_calendar(snap: Snapshot, asset: str) -> pd.DatetimeIndex:
    """The sessions at which ``asset`` printed its own fixing (snapshot manifest
    ``calendars``). Refuses a snapshot without one: executing on carried prices silently
    would be the look-ahead the option exists to prevent."""
    cal = (snap.manifest or {}).get("calendars", {}).get(asset)
    if not cal:
        raise ValueError(f"snapshot {snap.sha[:12]} has no fixing calendar for {asset}")
    return pd.DatetimeIndex(pd.to_datetime(cal))


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


def ratio_start(snap: Snapshot, miner: str = MINER, metal: str = METAL, *,
                floor: pd.Timestamp = CONFIRMATION_START) -> pd.Timestamp:
    """The first session on or after ``floor`` at which both legs have 21 sessions and
    the z-score is defined (data before ``floor`` is warm-up only)."""
    ready = ratio_weights(snap, ratio_grid(miner, metal)[0]["params"]).index[0]
    first = snap.dates[snap.dates >= pd.Timestamp(floor)][0]
    return max(common_start(snap, [miner, metal], MONTH), ready, first)


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
