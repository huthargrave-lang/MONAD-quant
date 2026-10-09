"""
MONAD Quant — the convexity-robust control (docs/research/CONVEXITY_CONTROL_PROTOCOL.md):
the F366205 beta-exposure control with a call-like payoff term on the asset's own factor
(K = max(F_w, 0)) and on a global factor (G = max(B_w, 0)), loadings estimated ex ante and
state-conditionally (the sign of the asset's weight difference at the block's start), the
loading-estimation error in the variance (a moving-block residual bootstrap), and one
downgrade regression.

Everything is computed at the block level: each term's exposure enters as the block sum of
Delta x term (``aggregates``), so the bootstrap re-estimates loadings without touching daily
arrays again.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.research import beta_control as bc
from src.research import hac

TERMS = ("F", "F_lag", "K", "G")
BOOT_BLOCK = 13
SEED = 20261009
MARKET = "MARKET EXPOSURE"
MARKET_LIKE = "EXPOSURE-LIKE (underpowered)"


# ── inputs at the block level ────────────────────────────────────────────────
@dataclass
class Blocks:
    """Everything the control reads, per block (rows) and asset (columns).

    ``y``: each asset's block return. ``terms``: name -> the asset's block-level regressor
    (F_w, F_{w-1}, max(F_w, 0), max(B_w, 0)). ``agg``: name -> the block sum of the weight
    difference times the term's daily series (the exposure a unit loading would carry).
    ``state``: sign of the weight difference at the block's first session. ``a``: the
    candidate's active block return. ``d_start``: the weight difference at each block's
    first session (the convex terms' weight). ``B``: the global factor's block sums (None
    for the products). ``D``: the |Delta|-weighted fund factor's block sums.
    """
    y: np.ndarray
    terms: dict
    agg: dict
    state: np.ndarray
    a: np.ndarray
    d_start: np.ndarray
    B: np.ndarray | None
    D: np.ndarray
    #: blocks where a held asset has no factor value (the first block's lag): allowed in
    #: the warm-up, refused inside the regression sample
    missing: np.ndarray = None


def build_blocks(active: pd.Series, delta: pd.DataFrame, asset_r: pd.DataFrame, factor: pd.DataFrame,
                 global_factor: pd.Series | None, grid: pd.Series) -> Blocks:
    """The block-level inputs on ``grid`` (every block from the sample's anchor; the
    regression sample is chosen later). ``factor``: each asset's own daily factor;
    ``global_factor``: B's daily series, or None (the products)."""
    sessions = grid.index
    blk = grid.to_numpy()
    nb = int(blk.max()) + 1
    cols = list(asset_r.columns)
    D = delta.reindex(index=sessions, columns=cols).fillna(0.0).to_numpy()
    first = np.r_[True, blk[1:] != blk[:-1]]
    start_rows = np.flatnonzero(first)
    D_start = D[start_rows][blk]                       # block-start weight difference, per session
    F = factor.reindex(columns=cols)
    Fd = F.reindex(sessions).to_numpy(dtype=float)
    Flag = F.shift(bc.BLOCK).reindex(sessions).to_numpy(dtype=float)
    Kd = bc.call_payoff_daily(F, grid).reindex(sessions).to_numpy(dtype=float)
    F_blocks = bc.block_sums(F.reindex(sessions), grid).to_numpy(dtype=float)
    y = bc.block_sums(asset_r.reindex(sessions), grid).to_numpy(dtype=float)

    missing = np.zeros(nb, dtype=bool)

    def agg(weights, daily):
        held = weights != 0
        gap = held & ~np.isfinite(daily)
        if gap.any():
            missing[np.unique(blk[gap.any(axis=1)])] = True
        return pd.DataFrame(np.where(held, weights * np.nan_to_num(daily), 0.0)).groupby(blk).sum().to_numpy()

    terms = {"F": F_blocks, "F_lag": np.vstack([np.full((1, len(cols)), np.nan), F_blocks[:-1]]),
             "K": np.clip(F_blocks, 0.0, None)}
    aggs = {"F": agg(D, Fd), "F_lag": agg(D, Flag), "K": agg(D_start, Kd)}
    B = None
    if global_factor is not None:
        Bd = global_factor.reindex(sessions)
        B = bc.block_sums(Bd, grid).to_numpy(dtype=float)
        Gd = bc.call_payoff_daily(Bd, grid).to_numpy(dtype=float)
        terms["G"] = np.repeat(np.clip(B, 0.0, None)[:, None], len(cols), axis=1)
        aggs["G"] = agg(D_start, np.repeat(Gd[:, None], len(cols), axis=1))
    absD = np.abs(D)
    wsum = absD.sum(axis=1)
    Dfac = np.where(wsum > 0, (absD * np.nan_to_num(Fd)).sum(axis=1) / np.where(wsum > 0, wsum, 1.0), 0.0)
    return Blocks(y=y, terms=terms, agg=aggs, state=np.sign(D[start_rows]).astype(int),
                  a=bc.block_sums(active.reindex(sessions), grid).to_numpy(dtype=float),
                  d_start=D[start_rows], B=B, D=pd.Series(Dfac).groupby(blk).sum().to_numpy(),
                  missing=missing)


# ── loadings ─────────────────────────────────────────────────────────────────
def _design(b: Blocks, j: int, y=None) -> tuple[np.ndarray, np.ndarray]:
    names = [n for n in TERMS if n in b.terms]
    Z = np.column_stack([np.ones(len(b.y))] + [b.terms[n][:, j] for n in names])
    yy = b.y[:, j] if y is None else y
    return Z, yy


def _rolling_solve(Z, y, rows: np.ndarray, targets: np.ndarray, window: int, minimum: int):
    """Loadings for each target block from the last ``window`` of ``rows`` (valid past
    blocks) before it; NaN where fewer than ``minimum``."""
    p = Z.shape[1]
    out = np.full((len(targets), p), np.nan)
    if len(rows) < minimum or not len(targets):
        return out
    Zv, yv = Z[rows], y[rows]
    czz = np.concatenate([np.zeros((1, p, p)), np.cumsum(Zv[:, :, None] * Zv[:, None, :], axis=0)])
    czy = np.concatenate([np.zeros((1, p)), np.cumsum(Zv * yv[:, None], axis=0)])
    n = np.searchsorted(rows, targets, side="left")
    lo = np.maximum(0, n - window)
    ok = (n - lo) >= minimum
    if ok.any():
        A = czz[n[ok]] - czz[lo[ok]]
        rhs = czy[n[ok]] - czy[lo[ok]]
        out[ok] = np.einsum("kij,kj->ki", np.linalg.pinv(A), rhs)
    return out


def loadings(b: Blocks, *, window: int, minimum: int, y: np.ndarray | None = None) -> np.ndarray:
    """``coef[w, i, term]`` (no intercept): state-conditional where at least ``minimum``
    same-state past blocks exist, else state-free, else 1 on F_w and 0 elsewhere."""
    nb, na = b.y.shape
    names = [n for n in TERMS if n in b.terms]
    coef = np.zeros((nb, na, len(names)))
    coef[:, :, 0] = 1.0
    every = np.arange(nb)
    for j in range(na):
        Z, yy = _design(b, j, None if y is None else y[:, j])
        valid = np.isfinite(yy) & np.isfinite(Z).all(axis=1)
        free = _rolling_solve(Z, yy, np.flatnonzero(valid), every, window, minimum)
        chosen = free.copy()
        for s in (-1, 0, 1):
            here = np.flatnonzero(b.state[:, j] == s)
            if not len(here):
                continue
            st = _rolling_solve(Z, yy, np.flatnonzero(valid & (b.state[:, j] == s)), here, window, minimum)
            have = np.isfinite(st).all(axis=1)
            chosen[here[have]] = st[have]
        ok = np.isfinite(chosen).all(axis=1)
        coef[ok, j, :] = chosen[ok, 1:]
    return coef


def exposure(b: Blocks, coef: np.ndarray) -> np.ndarray:
    """X_w = sum_i sum_term loading x (block sum of Delta x term)."""
    names = [n for n in TERMS if n in b.terms]
    return sum((coef[:, :, k] * b.agg[n]).sum(axis=1) for k, n in enumerate(names))


def convex_part(b: Blocks, coef: np.ndarray) -> np.ndarray:
    """The convex part of X_w, frozen as the |.|/2 components (max(F, 0) = F/2 + |F|/2):
    sum_i Delta_start (loading_K |F_w|/2 + loading_G |B_w|/2)."""
    names = [n for n in TERMS if n in b.terms]
    part = coef[:, :, names.index("K")] * np.nan_to_num(np.abs(b.terms["F"])) / 2.0
    if "G" in names:
        part = part + coef[:, :, names.index("G")] * (np.abs(b.B)[:, None] / 2.0)
    return (part * b.d_start).sum(axis=1)


# ── statistics ───────────────────────────────────────────────────────────────
def bootstrap_mean_var(b: Blocks, sample: slice, *, window: int, minimum: int, reps: int,
                       seed: int = SEED) -> float:
    """The variance of mean(X) over the sample from re-estimating the loadings on
    residual-bootstrapped asset returns (moving blocks of 13, the same indices for every
    asset; weights and factors fixed). Residuals are from each asset's state-free full-sample
    fit; an asset with no residual at a resampled block contributes 0 there."""
    nb, na = b.y.shape
    fitted = np.full_like(b.y, np.nan)
    resid = np.zeros_like(b.y)
    for j in range(na):
        Z, yy = _design(b, j)
        valid = np.isfinite(yy) & np.isfinite(Z).all(axis=1)
        if valid.sum() <= Z.shape[1]:
            continue
        beta, *_ = np.linalg.lstsq(Z[valid], yy[valid], rcond=None)
        fitted[valid, j] = Z[valid] @ beta
        resid[valid, j] = yy[valid] - fitted[valid, j]
    rng = np.random.default_rng(seed)
    means = np.empty(reps)
    for r in range(reps):
        starts = rng.integers(0, max(nb - BOOT_BLOCK, 1), size=nb // BOOT_BLOCK + 1)
        idx = (starts[:, None] + np.arange(BOOT_BLOCK)[None, :]).ravel()[:nb]
        ystar = fitted + resid[idx]
        coef = loadings(b, window=window, minimum=minimum, y=ystar)
        means[r] = exposure(b, coef)[sample].mean()
    return float(means.var(ddof=1))


def _mean_t(x: np.ndarray, extra_var: float, lag: int) -> float:
    m, se, _t = hac.mean_t(x, lag)
    var = se ** 2 + extra_var
    return float(m / np.sqrt(var)) if var > 0 else float("nan")


def downgrade(b: Blocks, u: np.ndarray, sample: slice) -> dict:
    """u on B, max(B,0), D, max(D,0) and their one-block lags (D only without B); a positive
    convexity coefficient at t >= 2 or a kept share < 0.25 downgrades."""
    cols, names = [], []
    series = ([("B", b.B)] if b.B is not None else []) + [("D", b.D)]
    for nm, x in series:
        for tag, v in ((nm, x), (f"max({nm},0)", np.clip(x, 0.0, None))):
            cols.append(v)
            names.append(tag)
            cols.append(np.r_[np.nan, v[:-1]])
            names.append(tag + "_lag")
    X = np.column_stack(cols)[sample]
    uu = u
    ok = np.isfinite(X).all(axis=1) & np.isfinite(uu)
    lag = hac.auto_lag(int(ok.sum()))
    coef, se = hac.ols(uu[ok], X[ok], lag)
    t = coef / np.where(se > 0, se, np.nan)
    conv = {names[k]: float(t[k + 1]) for k in range(len(names)) if names[k].startswith("max") and
            not names[k].endswith("_lag")}
    convex_hit = any(coef[k + 1] > 0 and t[k + 1] >= 2.0 for k in range(len(names))
                     if names[k].startswith("max"))
    return {"alpha_block": float(coef[0]), "convexity_t": conv, "convex_hit": bool(convex_hit)}


def control(b: Blocks, *, min_blocks: int, window: int, minimum: int, reps: int, seed: int = SEED) -> dict:
    """The frozen statistic and verdict on one book (the regression sample is the blocks
    from ``min_blocks`` on)."""
    sample = slice(min_blocks, None)
    if b.missing is not None and b.missing[sample].any():
        raise ValueError("a held asset has no factor value inside the regression sample")
    coef = loadings(b, window=window, minimum=minimum)
    X = exposure(b, coef)
    a = b.a[sample]
    x = X[sample]
    u = a - x
    raw = float(a.mean())
    boot = bootstrap_mean_var(b, sample, window=window, minimum=minimum, reps=reps, seed=seed) if reps else 0.0
    lags = bc.lags(len(a))
    t_alpha = tuple(_mean_t(u, boot, L) for L in lags)
    t_E = tuple(_mean_t(x, boot, L) for L in lags)
    s = float(u.mean()) / raw if raw > 0 else float("nan")
    conv = convex_part(b, coef)[sample]
    dg = downgrade(b, u, sample)
    s_dg = dg["alpha_block"] / raw if raw > 0 else float("nan")
    if not raw > 0:
        verdict = bc.INCONCLUSIVE
    elif s >= 0.5:
        verdict = (bc.SURVIVES if min(t_alpha) >= 2.0 else bc.UNDERPOWERED)
    elif s < 0.25:
        verdict = MARKET if min(t_E) >= 2.0 else MARKET_LIKE
    else:
        verdict = bc.INCONCLUSIVE
    downgraded = dg["convex_hit"] or (s_dg < 0.25)
    if downgraded and verdict in (bc.SURVIVES, bc.UNDERPOWERED):
        verdict = bc.INCONCLUSIVE
    return {"verdict": verdict, "s": s, "raw_ann": raw * bc.ANN, "alpha_ann": float(u.mean()) * bc.ANN,
            "explained_ann": float(x.mean()) * bc.ANN, "convex_ann": float(conv.mean()) * bc.ANN,
            "t_alpha": t_alpha, "t_E": t_E, "bootstrap_var_mean_X": boot, "blocks": int(len(a)),
            "downgrade": {**dg, "s": s_dg, "applied": bool(downgraded)}}
