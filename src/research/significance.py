"""
MONAD Quant — Significance after search: Deflated Sharpe, effective N, PBO, and
multiple-testing corrections. One canonical module.

Why this exists (the project's own history): every reversal here was a best-of-many
number read as if it were the only number (RESEARCH_WEB.md F2, F13, F18, D6). The trial
ledger (``trials.py``) now records how many things were tried; this module turns that
count into a verdict. Before it, multiple-testing control lived as two hand-rolled
Bonferroni lines (``tools/tips_sleeve_study.py``, ``tools/correlation_regime_study.py``)
and nothing deflated a Sharpe at all.

Contents (deterministic, numpy + stdlib only; no scipy):

  * ``deflated_sharpe``  — Bailey & López de Prado (2014), "The Deflated Sharpe Ratio",
                           J. Portfolio Management 40(5). Reproduces the paper's worked
                           example exactly (DSR 0.9004 at N=100, 0.9505 at N=46; pinned
                           in tests/test_significance.py).
  * ``probabilistic_sharpe`` — the PSR the DSR is built on (same paper, eq. for PSR).
  * ``effective_trials`` — how many INDEPENDENT things a family's trials amount to. A
                           9-point grid of near-identical configs is ~2-3 tries, not 9;
                           raw counts over-deflate, and a gate that admits nothing is as
                           uninformative as one that admits everything.
  * ``pbo_cscv``         — Probability of Backtest Overfitting by combinatorially
                           symmetric cross-validation (Bailey, Borwein, López de Prado &
                           Zhu 2017, "The Probability of Backtest Overfitting").
  * ``bonferroni`` / ``holm`` / ``benjamini_hochberg`` — p-value adjustment, and
    ``familywise_percentiles`` — the two-sided Bonferroni percentile band the bootstrap
    studies use, defined once.

Units: every Sharpe here is PER-PERIOD (not annualized), because the DSR's sampling
theory is per observation. Annualize for display only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import combinations
from statistics import NormalDist
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

EULER_GAMMA = 0.5772156649015329
_N = NormalDist()

#: The effective-N clustering rule, FIXED IN ADVANCE so it cannot be tuned per result.
#: Two trials whose daily-PnL correlation is at least this are treated as one idea tried
#: twice. Clusters merge by average linkage until no pair of clusters is this correlated.
#: 0.5 is the conventional "more alike than not" line; ``effective_trials`` also reports
#: the eigenvalue-based count (Li & Ji 2005) and uses the LARGER of the two, so neither
#: rule alone can talk the count down.
CLUSTER_MIN_CORRELATION = 0.5

#: Two trials are correlated only over the days BOTH were live (each one's first..last
#: trading day). Zero-filling outside a trial's window manufactures correlation between
#: any two trials whose means share a sign, which merges independent tries and
#: undercounts N (found by the admission-gate tests). Pairs overlapping fewer days than
#: this are treated as uncorrelated: unknown dependence counts as independent.
MIN_OVERLAP_DAYS = 20


# ── moments ──────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class SharpeMoments:
    sharpe: float      # per-period
    skew: float
    kurtosis: float    # NON-excess (normal = 3), as in the DSR paper
    n_obs: int


def sharpe_moments(returns: Sequence[float] | pd.Series) -> SharpeMoments:
    """Per-period Sharpe and the higher moments the PSR/DSR correct for."""
    x = np.asarray(returns, dtype=float)
    if x.size < 2:
        raise ValueError("need at least two observations")
    if not np.all(np.isfinite(x)):
        raise ValueError("returns contain non-finite values")
    mu, sd = float(x.mean()), float(x.std(ddof=1))
    if sd == 0:
        raise ValueError("returns have zero variance; the Sharpe ratio is undefined")
    z = (x - mu) / float(x.std(ddof=0))
    return SharpeMoments(sharpe=mu / sd, skew=float((z ** 3).mean()),
                         kurtosis=float((z ** 4).mean()), n_obs=int(x.size))


# ── PSR / DSR ────────────────────────────────────────────────────────────────
def probabilistic_sharpe(sharpe: float, benchmark: float, *, n_obs: int,
                         skew: float, kurtosis: float) -> float:
    """P(true Sharpe > ``benchmark``) given the observed per-period ``sharpe``.

    ``kurtosis`` is non-excess. Raises if the moment correction is non-positive, which
    happens only for moments no real return series has; silently clamping it would
    manufacture certainty.
    """
    if n_obs < 2:
        raise ValueError("need at least two observations")
    denom = 1.0 - skew * sharpe + (kurtosis - 1.0) / 4.0 * sharpe ** 2
    if denom <= 0:
        raise ValueError(f"moment correction is non-positive ({denom:.4g}); check skew/kurtosis")
    return _N.cdf((sharpe - benchmark) * math.sqrt(n_obs - 1) / math.sqrt(denom))


def expected_max_sharpe(n_trials: float, sharpe_variance: float) -> float:
    """SR0: the Sharpe the BEST of ``n_trials`` independent zero-edge trials is expected
    to reach, given the cross-trial variance of their (per-period) Sharpes.

    One trial involves no selection, so SR0 = 0 and the DSR reduces to the PSR.
    """
    if n_trials < 1:
        raise ValueError("n_trials must be at least 1")
    if sharpe_variance < 0:
        raise ValueError("sharpe_variance must be non-negative")
    if n_trials <= 1:
        return 0.0
    return math.sqrt(sharpe_variance) * (
        (1 - EULER_GAMMA) * _N.inv_cdf(1 - 1 / n_trials)
        + EULER_GAMMA * _N.inv_cdf(1 - 1 / (n_trials * math.e)))


@dataclass(frozen=True)
class DeflatedSharpe:
    dsr: float              # P(true Sharpe > SR0): the deflated verdict
    sr0: float              # per-period rejection threshold implied by the search
    sharpe: float           # observed per-period Sharpe of the candidate
    n_trials: float         # effective number of independent trials used
    sharpe_variance: float  # cross-trial variance used
    n_obs: int
    skew: float
    kurtosis: float


def deflated_sharpe(sharpe: float, *, n_trials: float, sharpe_variance: float,
                    n_obs: int, skew: float, kurtosis: float) -> DeflatedSharpe:
    """Bailey & López de Prado's DSR for a candidate chosen from ``n_trials`` tries."""
    sr0 = expected_max_sharpe(n_trials, sharpe_variance)
    dsr = probabilistic_sharpe(sharpe, sr0, n_obs=n_obs, skew=skew, kurtosis=kurtosis)
    return DeflatedSharpe(dsr=dsr, sr0=sr0, sharpe=sharpe, n_trials=n_trials,
                          sharpe_variance=sharpe_variance, n_obs=n_obs, skew=skew,
                          kurtosis=kurtosis)


# ── effective number of trials ───────────────────────────────────────────────
def daily_pnl(series_map: Mapping[str, pd.Series]) -> pd.DataFrame:
    """Per-trade return series -> one column of daily summed PnL per trial.

    Trials trade at different times, so correlation needs a common grid: business days
    spanning every trial, a day without a trade contributing 0. Timestamps are reduced to
    their calendar date (tz-naive).
    """
    cols = {}
    for key, s in series_map.items():
        if s is None or not len(s):
            cols[key] = pd.Series(dtype=float)
            continue
        idx = pd.DatetimeIndex(pd.to_datetime(s.index))
        if idx.tz is not None:
            idx = idx.tz_convert(None)
        cols[key] = pd.Series(np.asarray(s, dtype=float), index=idx.normalize()).groupby(level=0).sum()
    nonempty = [c for c in cols.values() if len(c)]
    if not nonempty:
        return pd.DataFrame(0.0, index=pd.DatetimeIndex([]), columns=list(cols))
    lo = min(c.index.min() for c in nonempty)
    hi = max(c.index.max() for c in nonempty)
    grid = pd.bdate_range(lo, hi).union(pd.DatetimeIndex(sorted({d for c in nonempty for d in c.index})))
    return pd.DataFrame({k: c.reindex(grid, fill_value=0.0) for k, c in cols.items()}, index=grid)


def active_span(pnl: pd.Series) -> pd.Series:
    """``pnl`` trimmed to its first..last trading day. The family grid zero-fills days
    outside a trial's own window; those zeros are not observations of that trial, and
    counting them would shrink its Sharpe (and inflate its T) by the width of the grid."""
    nz = np.flatnonzero(pnl.to_numpy() != 0)
    if nz.size == 0:
        return pnl.iloc[0:0]
    return pnl.iloc[nz[0]: nz[-1] + 1]


def active_span_sharpe(pnl: pd.Series) -> float:
    """Per-period Sharpe over the active span; 0.0 when undefined (<2 obs or no variance)."""
    x = active_span(pnl).to_numpy()
    if x.size < 2:
        return 0.0
    sd = float(x.std(ddof=1))
    return float(x.mean()) / sd if sd > 0 else 0.0


def _average_linkage_clusters(corr: np.ndarray, min_corr: float) -> np.ndarray:
    """Deterministic agglomerative clustering on correlation, average linkage.

    Repeatedly merges the pair of clusters with the highest mean pairwise correlation
    while that mean is >= ``min_corr``. Ties break on the lowest cluster index, so the
    result depends only on the matrix.
    """
    n = corr.shape[0]
    labels = np.arange(n)
    members = {i: [i] for i in range(n)}
    link = corr.astype(float).copy()
    np.fill_diagonal(link, -np.inf)
    active = list(range(n))
    while len(active) > 1:
        sub = link[np.ix_(active, active)]
        flat = int(np.argmax(sub))
        i, j = divmod(flat, len(active))
        if sub[i, j] < min_corr:
            break
        a, b = sorted((active[i], active[j]))
        size_a, size_b = len(members[a]), len(members[b])
        merged = (link[a] * size_a + link[b] * size_b) / (size_a + size_b)
        link[a, :] = merged
        link[:, a] = merged
        link[a, a] = -np.inf
        link[b, :] = -np.inf
        link[:, b] = -np.inf
        members[a].extend(members.pop(b))
        active.remove(b)
    for cluster, idx in enumerate(sorted(members)):
        labels[members[idx]] = cluster
    return labels


def overlap_correlation(pnl: pd.DataFrame, min_overlap: int = MIN_OVERLAP_DAYS) -> np.ndarray:
    """Pairwise correlation over each pair's shared active span (see MIN_OVERLAP_DAYS).

    Inside a trial's span a day without a trade is a genuine flat day (0); outside it the
    trial did not exist, so those days are excluded rather than zero-filled. Undefined or
    under-supported pairs become 0 (independent). The diagonal is 1.
    """
    masked = pnl.copy()
    for col in masked.columns:
        span = active_span(pnl[col])
        keep = masked.index.isin(span.index) if len(span) else np.zeros(len(masked), bool)
        masked.loc[~keep, col] = np.nan
    corr = masked.corr(min_periods=min_overlap).to_numpy(dtype=float)
    corr = np.nan_to_num(corr, nan=0.0)
    np.fill_diagonal(corr, 1.0)
    return corr


def li_ji_effective(corr: np.ndarray) -> float:
    """Li & Ji (2005) effective number of independent tests from eigenvalues:
    sum over eigenvalues of I(|l| >= 1) + (|l| - floor(|l|))."""
    if corr.shape[0] == 0:
        return 0.0
    # Rounded before floor(): an eigenvalue of exactly 5 computed as 4.9999999999999
    # would otherwise contribute 1 + 0.9999999 instead of 1 + 0.
    eig = np.round(np.abs(np.linalg.eigvalsh(corr)), 10)
    return float(np.sum((eig >= 1).astype(float) + (eig - np.floor(eig))))


@dataclass
class EffectiveTrials:
    n_raw: int                 # series supplied
    n_distinct: int            # after collapsing byte-identical series
    n_clusters: int            # average-linkage clusters at CLUSTER_MIN_CORRELATION
    n_li_ji: float             # eigenvalue-based count
    n_effective: float         # max(n_clusters, n_li_ji): the conservative count used
    labels: dict = field(default_factory=dict)       # key -> cluster id
    cluster_sharpes: list = field(default_factory=list)  # per-period Sharpe per cluster
    sharpe_variance: float = float("nan")            # variance of cluster_sharpes


def effective_trials(series_map: Mapping[str, pd.Series], *,
                     min_corr: float = CLUSTER_MIN_CORRELATION) -> EffectiveTrials:
    """Collapse a family's trials into independent ideas, and measure their spread.

    Byte-identical series are one trial. Series with no trades (or no variance) are
    grouped into a single "found nothing" cluster: they were tried, so they count once,
    but they cannot be correlated with anything. The cross-trial Sharpe variance the DSR
    needs is taken over CLUSTER representatives (each cluster's equal-weight daily PnL),
    so fifty copies of one config do not shrink it.
    """
    keys = list(series_map)
    pnl = daily_pnl(series_map)
    # Collapse identical columns (same trades on the same days).
    distinct: dict[bytes, list[str]] = {}
    for k in keys:
        distinct.setdefault(pnl[k].to_numpy().tobytes(), []).append(k)
    reps = [ks[0] for ks in distinct.values()]
    live = [k for k in reps if pnl[k].std(ddof=0) > 0]
    dead = [k for k in reps if k not in live]

    labels: dict[str, int] = {}
    cluster_cols: list[pd.Series] = []
    n_li_ji = 0.0
    if live:
        corr = overlap_correlation(pnl[live])
        lab = _average_linkage_clusters(corr, min_corr)
        n_li_ji = li_ji_effective(corr)
        for c in range(int(lab.max()) + 1):
            idx = [live[i] for i in np.flatnonzero(lab == c)]
            cluster_cols.append(pnl[idx].mean(axis=1))
            for rep in idx:
                for k in distinct[pnl[rep].to_numpy().tobytes()]:
                    labels[k] = c
    if dead:
        c = len(cluster_cols)
        for rep in dead:
            for k in distinct[pnl[rep].to_numpy().tobytes()]:
                labels[k] = c
        n_li_ji += 1.0
    n_clusters = len(cluster_cols) + (1 if dead else 0)
    sharpes = [active_span_sharpe(col) for col in cluster_cols]
    if dead:
        sharpes.append(0.0)
    variance = float(np.var(sharpes, ddof=1)) if len(sharpes) > 1 else 0.0
    return EffectiveTrials(n_raw=len(keys), n_distinct=len(reps), n_clusters=n_clusters,
                           n_li_ji=n_li_ji, n_effective=float(max(n_clusters, n_li_ji)),
                           labels=labels, cluster_sharpes=sharpes, sharpe_variance=variance)


# ── probability of backtest overfitting ──────────────────────────────────────
@dataclass(frozen=True)
class PBO:
    pbo: float                 # fraction of splits where the IS winner is below the OOS median
    logits: tuple              # per-split logit of the IS winner's OOS relative rank
    n_splits: int
    n_combinations: int


def _column_sharpe(block: np.ndarray) -> np.ndarray:
    mu = block.mean(axis=0)
    sd = block.std(axis=0, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(sd > 0, mu / sd, -np.inf)
    return out


def pbo_cscv(performance: np.ndarray | pd.DataFrame, n_splits: int = 16) -> PBO:
    """PBO by CSCV over a (T periods x N configurations) matrix of returns.

    The rows are cut into ``n_splits`` contiguous blocks; every way of choosing half of
    them as in-sample is tried. For each, the in-sample-best configuration's out-of-sample
    Sharpe is ranked among all configurations; PBO is the fraction of splits in which it
    falls at or below the OOS median (logit <= 0). All configurations must cover the same
    periods, so the matrix is exactly the trials that ran on one data slice.
    """
    m = np.asarray(performance, dtype=float)
    if m.ndim != 2 or m.shape[1] < 2:
        raise ValueError("need a 2-D matrix with at least two configurations")
    if n_splits < 2 or n_splits % 2:
        raise ValueError("n_splits must be an even number >= 2")
    if m.shape[0] < 2 * n_splits:
        raise ValueError(f"need at least {2 * n_splits} periods for {n_splits} splits")
    if not np.all(np.isfinite(m)):
        raise ValueError("performance matrix contains non-finite values")
    blocks = np.array_split(np.arange(m.shape[0]), n_splits)
    n_cfg = m.shape[1]
    logits = []
    for is_blocks in combinations(range(n_splits), n_splits // 2):
        is_rows = np.concatenate([blocks[b] for b in is_blocks])
        oos_rows = np.concatenate([blocks[b] for b in range(n_splits) if b not in is_blocks])
        is_sr = _column_sharpe(m[is_rows])
        oos_sr = _column_sharpe(m[oos_rows])
        best = int(np.argmax(is_sr))
        # Relative rank in (0, 1): average rank of the winner's OOS Sharpe, ties split.
        below = float(np.sum(oos_sr < oos_sr[best]))
        equal = float(np.sum(oos_sr == oos_sr[best]))
        omega = (below + (equal + 1) / 2) / (n_cfg + 1)
        logits.append(math.log(omega / (1 - omega)))
    arr = np.asarray(logits)
    return PBO(pbo=float(np.mean(arr <= 0)), logits=tuple(float(x) for x in arr),
               n_splits=n_splits, n_combinations=len(arr))


# ── multiple testing ─────────────────────────────────────────────────────────
def _pvalues(p: Sequence[float]) -> np.ndarray:
    arr = np.asarray(p, dtype=float)
    if arr.ndim != 1 or arr.size == 0:
        raise ValueError("need a non-empty 1-D sequence of p-values")
    if np.any((arr < 0) | (arr > 1) | ~np.isfinite(arr)):
        raise ValueError("p-values must lie in [0, 1]")
    return arr


def bonferroni(p: Sequence[float]) -> np.ndarray:
    """Family-wise error control: p * m, capped at 1."""
    arr = _pvalues(p)
    return np.minimum(arr * arr.size, 1.0)


def holm(p: Sequence[float]) -> np.ndarray:
    """Holm's step-down adjustment: uniformly more powerful than Bonferroni, same
    family-wise guarantee."""
    arr = _pvalues(p)
    m = arr.size
    order = np.argsort(arr, kind="mergesort")
    adj = np.maximum.accumulate((m - np.arange(m)) * arr[order])
    out = np.empty(m)
    out[order] = np.minimum(adj, 1.0)
    return out


def benjamini_hochberg(p: Sequence[float]) -> np.ndarray:
    """False-discovery-rate adjustment (BH 1995). Controls the expected share of false
    discoveries, NOT the chance of any: weaker than Bonferroni/Holm by design."""
    arr = _pvalues(p)
    m = arr.size
    order = np.argsort(arr, kind="mergesort")
    ranked = arr[order] * m / np.arange(1, m + 1)
    adj = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(adj, 1.0)
    return out


def familywise_percentiles(family: int, alpha: float = 0.05) -> list[float]:
    """Two-sided Bonferroni percentile band for a bootstrap CI in a family of ``family``
    comparisons: [100*alpha/(2m), 100 - 100*alpha/(2m)].

    Computed as ``alpha / family / 2 * 100`` exactly, the expression the bootstrap studies
    used before this module existed, so migrating them changes no output bit.
    """
    if family < 1:
        raise ValueError("family must be at least 1")
    afw = alpha / family / 2 * 100
    return [afw, 100 - afw]
