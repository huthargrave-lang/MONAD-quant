"""
MONAD Quant — trend-timed leverage with a live leveraged fund (domain ``levered_trend``,
family ``levered_trend.v1``), exactly as frozen in docs/research/LEVERED_TREND_PROTOCOL.md
before any price was loaded.

Gayed and Bilello (2016, "Leverage for the Long Run"): a daily-reset leveraged fund decays
most when volatility is high, and high volatility clusters below the 200-day moving
average. So holding the fund only while its index is above that average should make
leverage pay. The fund is live (ProShares Ultra S&P 500, SSO): its swap financing, fees
and decay are real, not modelled.

  * ``trend_timed`` {fund, signal, sma, schedule}: 100% ``fund`` while ``signal``'s
    total-return index closes above its ``sma``-session simple moving average, else cash
    (T-bills). ``schedule`` "daily" is the published rule: decided at each close, executed
    at the next open, one tranche, an order only when the state changes. "tranched" is
    F404704's ``sma`` schedule: checked every 21 sessions in 21 tranches.
  * ``held`` {asset}: 100% ``asset``, every 21 sessions in 21 tranches at the open: held SPY,
    the benchmark. ``fund_held`` is the same rule for the levered fund, a control; it has
    its own class because family membership recognises the benchmark by class.

``decay_interaction`` is the protocol's mechanism statistic, computed from recorded series.
"""
from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd

from src.research import significance as sig
from src.research.daily_classes import MONTH, OFFSETS, total_return_index
from src.research.daily_data import Snapshot, common_start
from src.research.daily_strategy import Tranche, static_tranches

FUND, INDEX = "SSO", "SPY"
LEVERAGE = 2
SMA = 200
WARMUP = 21
#: A night or day leg beyond this is an unadjusted split or a vendor glitch (the
#: snapshot's own check reads only the close-to-close total, in which the two cancel).
MAX_LEG = 0.40
ERAS = (("start", "2009-12-31"), ("2010-01-01", "2015-12-31"), ("2016-01-01", "end"))
REFERENCE = {"class": "held", "params": {"asset": INDEX}}
INTERACTION_BLOCK = 63
INTERACTION_BOOT = 5000


def grid() -> list[dict]:
    timed = lambda fund, schedule: {"class": "trend_timed", "params": {   # noqa: E731
        "fund": fund, "signal": INDEX, "sma": SMA, "schedule": schedule}}
    return [timed(FUND, "daily"),                 # the primary point: the published rule
            timed(FUND, "tranched"),              # F404704's schedule, at 2x
            timed(INDEX, "daily"),                # the same rule at 1x (mechanism control)
            {"class": "fund_held", "params": {"asset": FUND}}]    # levered hold (control)


GRIDS = {"v1": grid}


def _above(snap: Snapshot, signal: str, n: int) -> pd.Series:
    """True/False where the SMA is defined (data through each session only), else NaN."""
    tr = total_return_index(snap.returns())[signal]
    avg = tr.rolling(n).mean()
    return (tr > avg).astype(float).where(avg.notna())


def decide(snap: Snapshot, point: Mapping) -> list[Tranche]:
    p = point["params"]
    if point["class"] in ("held", "fund_held"):
        return static_tranches({p["asset"]: 1.0}, snap.dates, every=MONTH, offsets=OFFSETS)
    if point["class"] != "trend_timed":
        raise ValueError(f"unknown levered class {point['class']!r}")
    fund = p["fund"]
    on = _above(snap, p["signal"], int(p["sma"]))
    on = on.where(snap.close[fund].notna())               # the fund must be listed to decide
    w = pd.DataFrame({fund: on}).dropna()
    if p["schedule"] == "daily":
        changed = w[fund].ne(w[fund].shift(1))
        return [Tranche(open_orders=w.loc[changed], close_orders=pd.DataFrame())]
    if p["schedule"] == "tranched":
        return [Tranche(open_orders=w.reindex(snap.dates[off::MONTH]).dropna(),
                        close_orders=pd.DataFrame()) for off in OFFSETS]
    raise ValueError(f"unknown schedule {p['schedule']!r}")


def leg_errors(snap: Snapshot, assets=(FUND, INDEX)) -> list[str]:
    """Night or day legs beyond ``MAX_LEG``: the protocol rejects such a snapshot."""
    rets = snap.returns()
    out = []
    for leg in ("night", "day"):
        frame = getattr(rets, leg)[list(assets)]
        bad = frame.abs().gt(MAX_LEG) & frame.notna()
        for day, row in bad[bad.any(axis=1)].iterrows():
            for a in row.index[row]:
                out.append(f"{a} {leg} leg {frame.at[day, a]:+.1%} on {day.date()}")
    return out


def scoring_start(snap: Snapshot) -> pd.Timestamp:
    """The first session the fund has WARMUP sessions and the signal's SMA is defined."""
    ready = _above(snap, INDEX, SMA).first_valid_index()
    if ready is None:
        raise ValueError(f"{INDEX} never has {SMA} sessions")
    return max(common_start(snap, [FUND, INDEX], WARMUP), ready)


def truncation_violations(snap: Snapshot, point: Mapping, cuts) -> list[str]:
    from src.research import allocation_stats as stats
    full = decide(snap, point)
    out = []
    for cut in cuts:
        cut = pd.Timestamp(cut)
        out += stats.compare_orders(full, decide(stats.masked_after(snap, cut), point), cut)
    return out


def decay_interaction(levered_trend: pd.Series, levered_hold: pd.Series, unlevered_trend: pd.Series,
                      unlevered_hold: pd.Series, *, leverage: float = LEVERAGE,
                      mean_block: float = INTERACTION_BLOCK, n_boot: int = INTERACTION_BOOT,
                      seed: int = 0) -> dict:
    """The protocol's mechanism statistic: the annualised log-growth gain from timing the
    levered fund, minus ``leverage`` times the gain from timing the index,

        g = [lg(LT) - lg(LH)] - L [lg(UT) - lg(UH)],   lg = 252 x mean log(1 + r),

    with a stationary-bootstrap 95% interval over sessions (rows resampled jointly).
    Decay avoidance predicts g > 0: at 1x the filter forgoes little compounding drag; at
    L x it forgoes L^2 times as much."""
    frame = pd.concat([levered_trend, levered_hold, unlevered_trend, unlevered_hold], axis=1)
    if frame.isna().any().any():
        raise ValueError("the four series must share sessions")
    lg = np.log1p(frame.to_numpy(dtype=float))
    w = np.array([1.0, -1.0, -leverage, leverage])
    daily = lg @ w
    g = float(daily.mean() * 252)
    idx = sig.stationary_bootstrap_indices(len(daily), mean_block, n_boot, np.random.default_rng(seed))
    boot = daily[idx].mean(axis=1) * 252
    lo, hi = np.quantile(boot, [0.025, 0.975])
    return {"g": g, "ci95": [float(lo), float(hi)], "n_obs": len(daily),
            "mean_block": mean_block, "n_boot": n_boot}
