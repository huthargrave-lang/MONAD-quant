"""
MONAD Quant — Judging a daily strategy against the static 60/40: every statistic relative.

D6 settled the question this module asks: the decision-relevant bar is the static 60/40,
not zero and not buy & hold. A long equity/bond portfolio earns a positive Sharpe from
beta alone (about 0.8 over twenty years, t near 3.6), so a Deflated Sharpe tested against
"true Sharpe = 0" admits almost anything; H404700 passed exactly that test with DSR 0.9999
while being an execution artifact (F404703). Here the unit of evidence is the ACTIVE series:

    active[t] = strategy[t] - reference[t]     (same sessions, same costs, same cash)

which equals the difference of excess-over-cash returns, so the cash leg cancels and a
cash-heavy rule gains nothing from a near-zero-volatility T-bill yield.

  * ``deflate_active``         DSR of the candidate's active series, with N built from the
                               family's active series (``significance.effective_trials``
                               on the snapshot calendar) plus the declared prior search;
  * ``familywise``             Hansen's SPA over every family member's active series at
                               several mean block lengths (trend and regime returns persist
                               for months, so one short block understates the variance);
  * ``era_sharpes``            the active Sharpe within each pre-declared era;
  * ``truncation_violations``  look-ahead check: orders computed on a snapshot whose
                               prices after a cut are erased must equal the full-data
                               orders up to that cut.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from src.research import significance as sig
from src.research.daily_data import Snapshot

PERIODS_PER_YEAR = 252
#: Mean block lengths (sessions) for the familywise test: a month, a quarter, half a year.
#: The candidate must clear the bar at EVERY one.
SPA_BLOCKS = (20, 63, 126)
SPA_BOOT = 5000


def active_series(strategy: pd.Series, reference: pd.Series) -> pd.Series:
    """strategy - reference on identical sessions. Refuses misaligned inputs rather than
    silently intersecting them: two series on different windows are not comparable."""
    if not strategy.index.equals(reference.index):
        raise ValueError("strategy and reference were scored on different sessions")
    return (strategy - reference).rename("active")


def annualized_sharpe(x: pd.Series) -> float:
    x = np.asarray(x, dtype=float)
    sd = x.std(ddof=1)
    return float(x.mean() / sd * math.sqrt(PERIODS_PER_YEAR)) if sd > 0 else 0.0


def era_sharpes(active: pd.Series, eras: Sequence[Sequence[str]]) -> list[dict]:
    """Annualized active Sharpe per era. An era bound of "start"/"end" is the series' own."""
    out = []
    for lo, hi in eras:
        lo_t = active.index[0] if lo == "start" else pd.Timestamp(lo)
        hi_t = active.index[-1] if hi == "end" else pd.Timestamp(hi)
        part = active[(active.index >= lo_t) & (active.index <= hi_t)]
        out.append({"era": [lo, hi], "sessions": int(len(part)),
                    "active_sharpe": annualized_sharpe(part) if len(part) > 1 else None,
                    "active_return_ann": float(part.mean() * PERIODS_PER_YEAR) if len(part) else None})
    return out


@dataclass(frozen=True)
class ActiveDeflation:
    dsr: float
    sr0_ann: float
    sharpe_ann: float
    n_trials: float
    n_effective: float
    prior_trials: int
    unknown_specs: int
    members: int
    n_obs: int


def deflate_active(active: Mapping[str, pd.Series], candidate: str, *, calendar: pd.DatetimeIndex,
                   prior_trials: int = 0, unknown_specs: int = 0) -> ActiveDeflation:
    """DSR of ``active[candidate]`` against the family's search: N is the effective number
    of independent active series, plus each distinct spec whose result is unknown, plus
    the declared prior search (``prior_trials``) the ledger could not have seen."""
    if candidate not in active:
        raise ValueError(f"{candidate} has no active series")
    if prior_trials < 0 or unknown_specs < 0:
        raise ValueError("trial counts cannot be negative")
    eff = sig.effective_trials(active, calendar=calendar)
    n_trials = eff.n_effective + unknown_specs + prior_trials
    pnl = sig.daily_pnl({candidate: active[candidate]}, calendar)[candidate]
    m = sig.sharpe_moments(sig.active_span(pnl))
    res = sig.deflated_sharpe(m.sharpe, n_trials=n_trials, sharpe_variance=eff.sharpe_variance,
                              n_obs=m.n_obs, skew=m.skew, kurtosis=m.kurtosis)
    root = math.sqrt(PERIODS_PER_YEAR)
    return ActiveDeflation(dsr=res.dsr, sr0_ann=res.sr0 * root, sharpe_ann=m.sharpe * root,
                           n_trials=n_trials, n_effective=eff.n_effective,
                           prior_trials=prior_trials, unknown_specs=unknown_specs,
                           members=len(active), n_obs=m.n_obs)


def familywise(active: Mapping[str, pd.Series], candidate: str, *,
               blocks: Sequence[int] = SPA_BLOCKS, n_boot: int = SPA_BOOT,
               seed: int = 0) -> list[dict]:
    """Hansen's SPA over every family member, once per mean block length. Every series
    must cover the same sessions (``active_series`` guarantees it within one snapshot and
    window). Returns, per block: the family's SPA p-value and the candidate's adjusted one."""
    keys = list(active)
    if candidate not in keys:
        raise ValueError(f"{candidate} is not a family member")
    frame = pd.DataFrame({k: active[k] for k in keys})
    if frame.isna().any().any():
        raise ValueError("family active series do not share one set of sessions")
    d = frame.to_numpy(dtype=float)
    j = keys.index(candidate)
    out = []
    for b in blocks:
        r = sig.superior_predictive_ability(d, mean_block=b, n_boot=n_boot, seed=seed)
        out.append({"mean_block": b, "spa_pvalue": r.spa_pvalue,
                    "candidate_pvalue": r.adjusted_pvalues[j], "candidate_t": r.t_stats[j],
                    "family_size": len(keys), "n_obs": r.n_obs})
    return out


def masked_after(snap: Snapshot, cut: pd.Timestamp) -> Snapshot:
    """``snap`` with every price, distribution and cash rate AFTER ``cut`` erased, and the
    calendar kept (scheduled sessions are known in advance; their prices are not)."""
    later = snap.dates > pd.Timestamp(cut)

    def erase(frame):
        out = frame.copy()
        out.loc[later] = np.nan
        return out

    return Snapshot(sha=f"{snap.sha}@{pd.Timestamp(cut).date()}", dates=snap.dates,
                    assets=snap.assets, open=erase(snap.open), close=erase(snap.close),
                    dist=erase(snap.dist), dtb3=erase(snap.dtb3), manifest=snap.manifest)


def _orders_until(tranches, cut: pd.Timestamp) -> list:
    out = []
    for tr in tranches:
        for frame in (tr.open_orders, tr.close_orders):
            if frame is None or not len(frame):
                out.append(pd.DataFrame())
                continue
            out.append(frame[frame.index <= cut].sort_index())
    return out


def truncation_violations(snap: Snapshot, point: Mapping, cuts: Sequence[pd.Timestamp]) -> list[str]:
    """Every cut at which the strategy's orders up to the cut change when the prices after
    it are erased. Empty means no detected look-ahead at these cuts.

    Detection power: a rule whose order on the cut date depends on an erased value in
    magnitude is caught at every cut. One that reads only the future's SIGN (buy if
    tomorrow is up) is caught at a cut only when that sign flips the cut-date decision,
    roughly half the time; over ``default_cuts``' 12 cuts it escapes with probability
    about 1/4096. Rules that read the future through some source other than the
    snapshot they are handed are not covered: the classes take only the snapshot."""
    from src.research.daily_classes import decide

    full = decide(snap, point)
    problems = []
    for cut in cuts:
        cut = pd.Timestamp(cut)
        problems += compare_orders(full, decide(masked_after(snap, cut), point), cut)
    return problems


def compare_orders(full, truncated, cut: pd.Timestamp) -> list[str]:
    """Problems if ``truncated``'s orders up to ``cut`` differ from ``full``'s."""
    a = _orders_until(full, cut)
    b = _orders_until(truncated, cut)
    if len(a) != len(b):
        return [f"{cut.date()}: the number of tranches changed"]
    for i, (fa, fb) in enumerate(zip(a, b)):
        if fa.empty and fb.empty:
            continue
        cols = sorted(set(fa.columns) | set(fb.columns))
        fa = fa.reindex(columns=cols).fillna(0.0)
        fb = fb.reindex(columns=cols).fillna(0.0)
        if not fa.index.equals(fb.index) or not np.allclose(fa.to_numpy(), fb.to_numpy(),
                                                            rtol=0, atol=1e-12):
            return [f"{cut.date()}: tranche {i // 2} {('open', 'close')[i % 2]} orders differ "
                    f"before the cut"]
    return []


def default_cuts(snap: Snapshot, start: pd.Timestamp, n: int = 12) -> list[pd.Timestamp]:
    """``n`` cut dates spread evenly over the scored window (deterministic)."""
    scored = snap.dates[snap.dates >= pd.Timestamp(start)]
    pos = np.linspace(0, len(scored) - 2, n).round().astype(int)
    return [scored[p] for p in pos]


def duplicate_points(orders_by_label: Mapping[str, list]) -> list[tuple[str, str]]:
    """Pairs of grid points whose orders are identical: the same idea counted twice, and
    usually a sign that a parameter does not do what its grid assumed (2026-10-06: an
    announcement gate made the auction tilt's pre=5 identical to pre=3). A search should
    refuse to run such a grid before any trial is recorded."""
    def fingerprint(tranches) -> bytes:
        parts = []
        for tr in tranches:
            for frame in (tr.open_orders, tr.close_orders):
                if frame is None or frame.empty:
                    parts.append(b"-")
                    continue
                f = frame.reindex(columns=sorted(frame.columns)).fillna(0.0).sort_index()
                parts.append(repr(list(f.columns)).encode() + f.index.asi8.tobytes()
                             + np.round(f.to_numpy(dtype=float), 12).tobytes())
        return b"|".join(parts)

    seen: dict[bytes, str] = {}
    dupes = []
    for label, tranches in orders_by_label.items():
        fp = fingerprint(tranches)
        if fp in seen:
            dupes.append((seen[fp], label))
        else:
            seen[fp] = label
    return dupes
