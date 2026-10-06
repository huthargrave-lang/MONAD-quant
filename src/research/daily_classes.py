"""
MONAD Quant — Daily strategy classes and their frozen search grid (family ``daily_alloc.v1``).

Four classic daily rules the research web had never tested (the 2026-10-05 search), plus
the trend filter they are usually compared with. Every choice that could be tuned is
fixed HERE, before any trial runs, so the grid below is the whole search and the trial
ledger can count it: lookbacks, skip-month, volatility windows, rebalance cadence,
tranche offsets, universes, and window edges.

Conventions shared by every class:

  * signals read the TOTAL-RETURN index built from the snapshot's night and day legs, so
    a distribution is a return, not a price drop;
  * a "month" is ``MONTH = 21`` sessions; monthly rules rebalance every 21 sessions and run
    as 21 tranches, one per offset 0..20 (``OFFSETS``), so no single rebalance day's luck
    decides the result (the staggered-tranche treatment of rebalance timing);
  * decisions are made at a session's close from data through that close, and execute at
    the next session (``daily_strategy``). ``decide(snap, params)`` must be TRUNCATION
    INVARIANT: computing on the snapshot cut at any date gives the same orders up to that
    date. ``allocation_stats.truncation_violations`` checks this, and the admission gate
    requires it of every registered candidate;
  * the trading calendar (the snapshot's sessions) is treated as known in advance, which
    scheduled NYSE holidays are. Turn-of-month needs it to know which session ends a month.

The reference portfolio (``REFERENCE``) is the bar D6 set, built under the SAME execution
model: 60% SPY / 40% IEF, rebalanced every 21 sessions in 21 tranches, same costs, same
cash. It deliberately differs from the D6-arc labs' 60/40 (``tools/mr_daily_lab.py``: an
equal-weight four-equity blend, re-weighted daily for free, log returns, zero cash), whose
flaws the 2026-10-05 skeptic review listed; the two are not interchangeable numbers.
"""
from __future__ import annotations

import itertools
from typing import Callable, Mapping

import numpy as np
import pandas as pd

from src.research.daily_data import SessionReturns, Snapshot
from src.research.daily_strategy import Tranche, static_tranches

MONTH = 21
OFFSETS = tuple(range(MONTH))
VOL_WINDOW = 63                      # sessions of daily total returns for inverse-vol weights

UNIVERSE_4 = ("SPY", "EFA", "IEF", "GLD")
UNIVERSE_8 = ("SPY", "IWM", "EFA", "EEM", "IEF", "TLT", "GLD", "DBC")
UNIVERSES = {"u4": UNIVERSE_4, "u8": UNIVERSE_8}

#: The longest history any rule needs before its first decision: 12-month momentum with a
#: one-month skip (13 months), plus the inverse-vol window.
WARMUP_SESSIONS = 13 * MONTH + VOL_WINDOW

#: Pre-declared eras for the regime split: the post-GFC bond bull with zero rates, the
#: 2014-2021 low-rate expansion, and the post-2022 positive stock-bond correlation regime
#: (F46/F49: the 60/40 itself is conditional on that correlation).
ERAS = (("start", "2013-12-31"), ("2014-01-01", "2021-12-31"), ("2022-01-01", "end"))


def total_return_index(rets: SessionReturns) -> pd.DataFrame:
    """Cumulative total return per asset (night then day legs), NaN before the asset's
    first session. The first session's own return is not counted: it has no prior close."""
    gross = ((1.0 + rets.night) * (1.0 + rets.day)).fillna(1.0)
    return gross.cumprod().where(rets.day.notna(), np.nan)


def cash_index(rets: SessionReturns) -> pd.Series:
    return (1.0 + rets.cash.fillna(0.0)).cumprod()


def _monthly_decisions(dates: pd.DatetimeIndex, offset: int) -> pd.DatetimeIndex:
    return dates[offset::MONTH]


def _tranches_from(weights_on: Callable[[pd.DatetimeIndex], pd.DataFrame],
                   dates: pd.DatetimeIndex) -> list[Tranche]:
    out = []
    for off in OFFSETS:
        days = _monthly_decisions(dates, off)
        out.append(Tranche(open_orders=weights_on(days), close_orders=pd.DataFrame()))
    return out


def _trailing(tr: pd.DataFrame, lookback: int, skip: int) -> pd.DataFrame:
    """Total return over (t - skip - lookback, t - skip]: data through t only."""
    return tr.shift(skip) / tr.shift(skip + lookback) - 1.0


# ── classes ──────────────────────────────────────────────────────────────────
def tsmom(snap: Snapshot, params: Mapping, rets: SessionReturns | None = None) -> list[Tranche]:
    """Time-series momentum: hold each asset whose trailing L-month total return (skipping
    the latest month) beats cash over the same span; equal or inverse-vol weights over the
    universe, unselected weight in cash."""
    rets = rets or snap.returns()
    universe = list(UNIVERSES[params["universe"]])
    L = int(params["lookback_months"]) * MONTH
    tr = total_return_index(rets)[universe]
    mom = _trailing(tr, L, MONTH)
    cash = cash_index(rets)
    cash_mom = cash.shift(MONTH) / cash.shift(MONTH + L) - 1.0
    selected = mom.gt(cash_mom, axis=0) & mom.notna()
    if params["weighting"] == "equal":
        base = pd.DataFrame(1.0 / len(universe), index=tr.index, columns=universe)
    elif params["weighting"] == "invvol":
        vol = (tr / tr.shift(1) - 1.0).rolling(VOL_WINDOW).std()
        inv = 1.0 / vol
        base = inv.div(inv.sum(axis=1, skipna=False), axis=0)
    else:
        raise ValueError(f"unknown weighting {params['weighting']!r}")
    ready = mom.notna().all(axis=1) & base.notna().all(axis=1)
    w = (base * selected).where(ready, np.nan)
    return _tranches_from(lambda days: w.loc[days].dropna(how="all"), snap.dates)


def dualmom(snap: Snapshot, params: Mapping, rets: SessionReturns | None = None) -> list[Tranche]:
    """Dual momentum (Antonacci's GEM shape): the better of SPY and EFA by trailing L-month
    total return if it beats cash over the span, else the safe asset."""
    rets = rets or snap.returns()
    L = int(params["lookback_months"]) * MONTH
    safe = params["safe"]
    tr = total_return_index(rets)[["SPY", "EFA", safe]]
    mom = _trailing(tr[["SPY", "EFA"]], L, 0)
    cash = cash_index(rets)
    cash_mom = cash / cash.shift(L) - 1.0
    complete = mom.notna().all(axis=1)
    # The better of the two where both have a lookback; SPY on an exact tie.
    best = pd.Series(np.where(mom["EFA"] > mom["SPY"], "EFA", "SPY"), index=mom.index).where(complete)
    best_ret = mom.max(axis=1).where(complete)
    cols = ["SPY", "EFA", safe]
    w = pd.DataFrame(0.0, index=tr.index, columns=cols)
    risk_on = best_ret > cash_mom
    for a in ("SPY", "EFA"):
        w.loc[risk_on & (best == a), a] = 1.0
    w.loc[~risk_on & best.notna(), safe] = 1.0
    w = w.where(best.notna() & tr[safe].notna(), np.nan)
    return _tranches_from(lambda days: w.loc[days].dropna(how="all"), snap.dates)


def tom(snap: Snapshot, params: Mapping, rets: SessionReturns | None = None) -> list[Tranche]:
    """Turn of the month: hold SPY over the sessions from ``first`` (negative: before the
    month ends; -1 is the month's last session) through ``last`` (the new month's
    ``last``-th session), close to close; otherwise cash or IEF.

    Holding a session's close-to-close return means buying at the PREVIOUS session's close,
    so the buy executes at the close of session ``first - 1`` and the sale at the close of
    session ``last``; both are decided one session earlier from the calendar alone.
    """
    first, last = int(params["first"]), int(params["last"])
    if not (first < 0 < last):
        raise ValueError("turn-of-month window must straddle the month end")
    off = params["off"]
    dates = snap.dates
    month = pd.Series(dates.to_period("M"), index=dates)
    pos_from_end = month.groupby(month).cumcount(ascending=False) + 1      # 1 = last session
    pos_from_start = month.groupby(month).cumcount() + 1                    # 1 = first session
    buy_at = pos_from_end == (-first + 1)          # e.g. first=-1: buy at the close of the 2nd-to-last
    sell_at = pos_from_start == last
    on = {"SPY": 1.0}
    off_w = {} if off == "cash" else {off: 1.0}
    cols = sorted({"SPY", *off_w})
    rows, idx = [], []
    exec_pos = np.flatnonzero(buy_at.to_numpy() | sell_at.to_numpy())
    for p in exec_pos:
        if p == 0:
            continue                                # decided before the snapshot begins
        target = on if buy_at.iloc[p] else off_w
        rows.append({c: target.get(c, 0.0) for c in cols})
        idx.append(dates[p - 1])                    # decided one session before execution
    orders = pd.DataFrame(rows, index=pd.DatetimeIndex(idx), columns=cols)
    return [Tranche(open_orders=pd.DataFrame(), close_orders=orders)]


def overnight(snap: Snapshot, params: Mapping, rets: SessionReturns | None = None) -> list[Tranche]:
    """Overnight drift: own the asset from each close to the next open; cash in the day.
    Executes at both auctions every session (decided a session earlier, from the
    calendar), so it pays two one-way costs per session."""
    a = params["asset"]
    dates = snap.dates
    # Listed and priced as of the decision date (not the next session: reading the next
    # session's price to decide would be look-ahead, which truncation_violations catches).
    listed = snap.close[a].notna().cummax().to_numpy()
    days = dates[:-1][listed[:-1]]
    buy = pd.DataFrame({a: 1.0}, index=days)        # executes at the next session's close
    sell = pd.DataFrame({a: 0.0}, index=days)       # executes at the next session's open
    return [Tranche(open_orders=sell, close_orders=buy)]


def sma(snap: Snapshot, params: Mapping, rets: SessionReturns | None = None) -> list[Tranche]:
    """Trend filter on SPY (Faber's shape): 60/40 SPY/IEF while SPY's total-return index is
    above its N-session simple moving average, otherwise cash or IEF. Checked every 21
    sessions in 21 tranches, whatever N is."""
    rets = rets or snap.returns()
    n = int(params["sma_sessions"])
    off = params["off"]
    tr = total_return_index(rets)
    spy = tr["SPY"]
    above = spy > spy.rolling(n).mean()
    ready = spy.rolling(n).mean().notna() & tr["IEF"].notna()
    w = pd.DataFrame(0.0, index=tr.index, columns=["SPY", "IEF"])
    w.loc[above, "SPY"] = 0.6
    w.loc[above, "IEF"] = 0.4
    if off == "IEF":
        w.loc[~above, "IEF"] = 1.0
    elif off != "cash":
        raise ValueError(f"unknown off state {off!r}")
    w = w.where(ready, np.nan)
    return _tranches_from(lambda days: w.loc[days].dropna(how="all"), snap.dates)


def reference_6040(snap: Snapshot, params: Mapping | None = None,
                   rets: SessionReturns | None = None) -> list[Tranche]:
    """The static 60/40 bar: SPY/IEF, every 21 sessions, 21 tranches."""
    return static_tranches({"SPY": 0.6, "IEF": 0.4}, snap.dates, every=MONTH, offsets=OFFSETS)


CLASSES: dict[str, Callable] = {"tsmom": tsmom, "dualmom": dualmom, "tom": tom,
                                "overnight": overnight, "sma": sma}
REFERENCE = {"class": "static_6040", "params": {"weights": {"SPY": 0.6, "IEF": 0.4},
                                                "every": MONTH, "tranches": len(OFFSETS)}}


def grid() -> list[dict]:
    """The whole search, frozen: 27 (class, params) points."""
    points = []
    for L, wt, u in itertools.product((3, 6, 12), ("equal", "invvol"), ("u4", "u8")):
        points.append({"class": "tsmom", "params": {"lookback_months": L, "weighting": wt,
                                                    "universe": u}})
    for L, safe in itertools.product((6, 12), ("AGG", "IEF")):
        points.append({"class": "dualmom", "params": {"lookback_months": L, "safe": safe}})
    for (first, last), off in itertools.product(((-1, 3), (-2, 3)), ("cash", "IEF")):
        points.append({"class": "tom", "params": {"first": first, "last": last, "off": off}})
    for a in ("SPY", "QQQ", "IWM"):
        points.append({"class": "overnight", "params": {"asset": a}})
    for n, off in itertools.product((210, 200), ("cash", "IEF")):
        points.append({"class": "sma", "params": {"sma_sessions": n, "off": off}})
    return points


def assets_used(point: Mapping) -> tuple:
    cls, p = point["class"], point["params"]
    if cls == "tsmom":
        return UNIVERSES[p["universe"]]
    if cls == "dualmom":
        return ("SPY", "EFA", p["safe"])
    if cls == "tom":
        return ("SPY",) if p["off"] == "cash" else ("SPY", p["off"])
    if cls == "overnight":
        return (p["asset"],)
    if cls == "sma":
        return ("SPY", "IEF")
    if cls == "static_6040":
        return ("SPY", "IEF")
    raise ValueError(f"unknown class {cls!r}")


def decide(snap: Snapshot, point: Mapping, rets: SessionReturns | None = None) -> list[Tranche]:
    if point["class"] == "static_6040":
        return reference_6040(snap, point["params"], rets)
    return CLASSES[point["class"]](snap, point["params"], rets)
