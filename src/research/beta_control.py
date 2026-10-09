"""
MONAD Quant — the beta-exposure control (docs/research/BETA_TIMING_CONTROL_PROTOCOL.md):
does a candidate's active return survive hedging its ex-ante beta exposure, static or
timed?

Pure functions on daily series. The tool (``tools/beta_timing_control.py``) supplies the
recorded series and the replayed weights.

  * Blocks: consecutive 5-session sums anchored at the sample start; an incomplete final
    block is dropped. One grid serves the betas and the regressions.
  * Ex-ante Dimson betas: for each asset and factor, slopes on the factor's block return
    and its previous block's, estimated on the asset's complete blocks that END BEFORE
    the block where the beta is used (the last ``window`` of them, at least ``min_blocks``;
    with fewer, the fallback b0 = 1, b1 = 0 on the first factor).
  * Exposure X_t = sum_i Delta_i,t sum_f (b0_i,f F_f,i,t + b1_i,f F_f,i,t-5), where Delta is
    the candidate's minus the benchmark's weight at the previous close. An asset can be
    its own factor (an ETF in a fund-vs-ETF book): b0 = 1, b1 = 0, not estimated.
  * Primary statistic, g fixed at 1: alpha = mean(a - X) per block, E = mean(X), and the
    kept share s = alpha / mean(a).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.research import hac

BLOCK = 5
ANN = 252.0 / BLOCK
BASE_LAG = 4

SURVIVES = "SURVIVES"
UNDERPOWERED = "UNDERPOWERED"
BETA = "BETA EXPOSURE"
BETA_LIKE = "BETA-LIKE (underpowered)"
INCONCLUSIVE = "INCONCLUSIVE"


# ── blocks ───────────────────────────────────────────────────────────────────
def block_grid(dates: pd.DatetimeIndex, start: pd.Timestamp) -> pd.Series:
    """Session -> block number for the sessions from ``start``, consecutive groups of 5;
    the sessions of an incomplete final block are not in the grid."""
    sessions = dates[dates >= start]
    n_full = len(sessions) // BLOCK
    sessions = sessions[: n_full * BLOCK]
    return pd.Series(np.arange(len(sessions)) // BLOCK, index=sessions)


def block_sums(daily: pd.Series | pd.DataFrame, grid: pd.Series):
    """Per-block sums; a block with any missing session is NaN."""
    d = daily.reindex(grid.index)
    return d.groupby(grid.to_numpy()).sum(min_count=BLOCK)


# ── replay checks ────────────────────────────────────────────────────────────
REPRODUCTION_TOLERANCE = 1e-12
IDENTITY_FLOOR = -1e-12
IDENTITY_SUM_TOLERANCE = 1e-9


def reproduction_problems(replayed: pd.Series, recorded: pd.Series,
                          tol: float = REPRODUCTION_TOLERANCE) -> list[str]:
    """A replay reproduces a recorded series: the identical session index and every return
    within ``tol``."""
    if not replayed.index.equals(recorded.index):
        return [f"the replay covers {len(replayed)} sessions, the record {len(recorded)}, "
                f"or their dates differ"]
    diff = float(np.max(np.abs(replayed.to_numpy() - recorded.to_numpy()))) if len(replayed) else 0.0
    return [] if diff <= tol else [f"the replay differs from the record by up to {diff:.3e}"]


def weight_identity_problems(returns: pd.Series, weights: pd.DataFrame, asset_returns: pd.DataFrame,
                             cash: pd.Series, cost_paid: float, *, carry_in: bool,
                             first_session_fee_bound: float = 0.0) -> list[str]:
    """The evaluator's book identity for close-executed orders: each session's return is
    the previous close's weights times the assets' close-to-close returns, plus cash on the
    rest, less that session's fee: f_t = sum_i w_i,t-1 r_i,t + (1 - sum_i w_i,t-1) c_t - R_t
    must be >= 0 (to rounding), and the f_t sum to ``cost_paid``. It proves
    ``weights.shift(1)`` is what each session held.

    The book starts in cash. Without a ``carry_in`` (no order dated before the window),
    the identity holds from the first session (weight 0 before it). With one, the
    evaluator builds the carried-in targets at the first session's OPEN, which the closing
    weights cannot express. Then the identity is checked from the second session, and the
    first session's fee, cost_paid - sum_{t>=2} f_t, must lie in
    [0, ``first_session_fee_bound``] (protocol clarification 2)."""
    w_prev = weights.shift(1).fillna(0.0)
    r = asset_returns.reindex(index=weights.index, columns=weights.columns)
    held = w_prev != 0
    missing = held & ~np.isfinite(r)
    if missing.to_numpy().any():
        d, a = np.argwhere(missing.to_numpy())[0]
        return [f"{weights.columns[a]} is held with no return on {weights.index[d].date()}"]
    gross = (w_prev * r.where(held, 0.0)).sum(axis=1) + (1.0 - w_prev.sum(axis=1)) * cash.reindex(weights.index)
    f = gross - returns.reindex(weights.index)
    if carry_in:
        f = f.iloc[1:]
    problems = []
    if len(f) and float(f.min()) < IDENTITY_FLOOR:
        problems.append(f"a session earned more than its weights allow (f = {float(f.min()):.3e} "
                        f"on {f.idxmin().date()})")
    if carry_in:
        first = cost_paid - float(f.sum())
        if not (-IDENTITY_SUM_TOLERANCE <= first <= first_session_fee_bound + IDENTITY_SUM_TOLERANCE):
            problems.append(f"the first session's fee would be {first:.12f}, outside "
                            f"[0, {first_session_fee_bound:.6f}]")
    elif abs(float(f.sum()) - cost_paid) > IDENTITY_SUM_TOLERANCE:
        problems.append(f"the residuals sum to {float(f.sum()):.12f}, the fees to {cost_paid:.12f}")
    return problems


# ── ex-ante Dimson betas ─────────────────────────────────────────────────────
@dataclass
class Betas:
    """``coef[k, i, 2f + j]``: asset i's slope on factor f at lag j (0: same block, 1: the
    previous block) used in block k. ``fallback[k, i]``: no estimate, the fallback applied."""
    assets: list
    coef: np.ndarray
    fallback: np.ndarray


def dimson_betas(asset_blocks: pd.DataFrame, factor_blocks: list[pd.DataFrame], *,
                 window: int, min_blocks: int, self_factor: frozenset = frozenset()) -> Betas:
    """``asset_blocks``: blocks x assets. ``factor_blocks``: one blocks x assets frame per
    factor (each asset's own factor series). ``self_factor``: assets that are their own
    first factor (b0 = 1, b1 = 0, never estimated)."""
    assets = list(asset_blocks.columns)
    nb, na, nf = len(asset_blocks), len(assets), len(factor_blocks)
    coef = np.zeros((nb, na, 2 * nf))
    coef[:, :, 0] = 1.0
    fallback = np.ones((nb, na), dtype=bool)
    for j, a in enumerate(assets):
        if a in self_factor:
            fallback[:, j] = False
            continue
        y = asset_blocks[a].to_numpy(dtype=float)
        cols = [np.ones(nb)]
        for F in factor_blocks:
            f = F[a].to_numpy(dtype=float)
            lagged = np.r_[np.nan, f[:-1]]
            cols += [f, lagged]
        Z = np.column_stack(cols)
        valid = np.isfinite(y) & np.isfinite(Z).all(axis=1)
        idx = np.flatnonzero(valid)
        if len(idx) < min_blocks:
            continue
        Zv, yv = Z[idx], y[idx]
        p = Z.shape[1]
        czz = np.concatenate([np.zeros((1, p, p)), np.cumsum(Zv[:, :, None] * Zv[:, None, :], axis=0)])
        czy = np.concatenate([np.zeros((1, p)), np.cumsum(Zv * yv[:, None], axis=0)])
        k = np.arange(nb)
        n_before = np.searchsorted(idx, k, side="left")      # complete blocks strictly before k
        lo = np.maximum(0, n_before - window)
        ok = (n_before - lo) >= min_blocks
        if not ok.any():
            continue
        A = czz[n_before[ok]] - czz[lo[ok]]
        b = czy[n_before[ok]] - czy[lo[ok]]
        sol = np.einsum("kij,kj->ki", np.linalg.pinv(A), b)
        coef[ok, j, :] = sol[:, 1:]
        fallback[ok, j] = False
    return Betas(assets=assets, coef=coef, fallback=fallback)


# ── exposure ─────────────────────────────────────────────────────────────────
@dataclass
class Exposure:
    daily: pd.Series                     # X_t on the grid's sessions
    static_daily: float                  # sum over assets and terms of mean(Delta b) mean(F)
    fallback_share: float                # |Delta|-weighted share of exposure on the fallback
    terms: dict = field(default_factory=dict)


def exposure(delta: pd.DataFrame, factors: list[pd.DataFrame], betas: Betas, grid: pd.Series) -> Exposure:
    """X_t for the sessions of ``grid``. ``delta``: sessions x assets, the weight difference
    held during each session (the previous close's). ``factors``: one sessions x assets
    frame of DAILY factor returns per factor, on the full calendar (the lag is 5 sessions
    of that calendar)."""
    sessions = grid.index
    blk = grid.to_numpy()
    assets = betas.assets
    D = delta.reindex(index=sessions, columns=assets).fillna(0.0).to_numpy()
    X = np.zeros(len(sessions))
    static = 0.0
    for f, F in enumerate(factors):
        cur = F.reindex(columns=assets)
        lag = cur.shift(BLOCK)
        for j, frame in enumerate((cur, lag)):
            vals = frame.reindex(sessions).to_numpy(dtype=float)
            bad = (D != 0) & ~np.isfinite(vals)
            if bad.any():
                r, c = np.argwhere(bad)[0]
                raise ValueError(f"{assets[c]} is held with no factor return on {sessions[r].date()}")
            vals = np.where(D != 0, vals, 0.0)
            e = D * betas.coef[blk, :, 2 * f + j]
            X += (e * vals).sum(axis=1)
            static += float((e.mean(axis=0) * vals.mean(axis=0)).sum())
    absd = np.abs(D)
    fb = betas.fallback[blk]
    share = float((absd * fb).sum() / absd.sum()) if absd.sum() > 0 else 0.0
    return Exposure(daily=pd.Series(X, index=sessions), static_daily=static, fallback_share=share)


def within_category_part(dw: pd.DataFrame, x: pd.DataFrame, families: dict,
                         live: pd.DataFrame | None = None) -> pd.Series:
    """The within-family part of sum_i Delta_i x_i (F366204's decomposition): per family,
    sum over the funds live that day of (Delta_i - mean Delta)(x_i - mean x). ``live``
    defaults to Delta or x nonzero; pass the realised series' mask to split another x
    (an exposure) over the same funds."""
    within = pd.Series(0.0, index=dw.index)
    for fam in sorted({families[f] for f in dw.columns}):
        fs = [f for f in dw.columns if families[f] == fam]
        d, xx = dw[fs], x[fs].reindex(dw.index).fillna(0.0)
        live_f = ((d != 0) | (xx != 0)) if live is None else live[fs].reindex(dw.index).fillna(False)
        live_f = live_f.astype(bool)
        dbar = d.where(live_f).mean(axis=1)
        xbar = xx.where(live_f).mean(axis=1)
        within += (d.sub(dbar, axis=0) * xx.sub(xbar, axis=0)).where(live_f).sum(axis=1).fillna(0.0)
    return within


# ── statistics ───────────────────────────────────────────────────────────────
def lags(n: int) -> tuple[int, int]:
    return BASE_LAG, hac.auto_lag(n)


def _t_both(x: np.ndarray, n: int) -> tuple[float, float]:
    """The t of mean(x) at both pre-stated lags; the condition must hold at both, so the
    smaller absolute value is the binding one."""
    return tuple(hac.mean_t(x, L)[2] for L in lags(n))


def primary(a_w: np.ndarray, X_w: np.ndarray) -> dict:
    """g = 1: alpha = mean(a - X), E = mean(X), s = alpha / mean(a)."""
    n = len(a_w)
    u = a_w - X_w
    raw = float(a_w.mean())
    t_alpha = _t_both(u, n)
    t_E = _t_both(X_w, n)
    t_raw = _t_both(a_w, n)
    fl = hac.fieller(u, a_w, lags(n)[1])
    return {"blocks": n, "raw_ann": raw * ANN, "alpha_ann": float(u.mean()) * ANN,
            "explained_ann": float(X_w.mean()) * ANN,
            "s": float(u.mean()) / raw if raw > 0 else float("nan"),
            "t_alpha": t_alpha, "t_E": t_E, "t_raw": t_raw,
            "fieller_s": list(fl) if fl is not None else None, "lags": list(lags(n))}


def free_g(a_w: np.ndarray, X_w: np.ndarray) -> dict:
    """R0: a = alpha + g X; g with its CI and the t of g - 1 (at the automatic lag)."""
    n = len(a_w)
    L = lags(n)[1]
    b, se = hac.ols(a_w, X_w, L)
    raw = float(a_w.mean())
    return {"alpha_ann": float(b[0]) * ANN, "g": float(b[1]),
            "g_ci": [float(b[1] - 1.96 * se[1]), float(b[1] + 1.96 * se[1])],
            "t_g_minus_1": float((b[1] - 1.0) / se[1]) if se[1] > 0 else float("nan"),
            "s": float(b[0]) / raw if raw > 0 else float("nan")}


def treynor_mazuy(a_w: np.ndarray, F_w: np.ndarray) -> dict:
    """R2: a = alpha + b F + c F^2 + d F_{w-1}; the first block (no lag) is dropped."""
    n = len(a_w)
    L = lags(n - 1)[1]
    Xr = np.column_stack([F_w[1:], F_w[1:] ** 2, F_w[:-1]])
    b, se = hac.ols(a_w[1:], Xr, L)
    raw = float(a_w.mean())
    t_c = float(b[2] / se[2]) if se[2] > 0 else float("nan")
    return {"alpha_ann": float(b[0]) * ANN, "c": float(b[2]), "t_c": t_c,
            "convexity_detected": bool(b[2] > 0 and t_c >= 2.0),
            "s": float(b[0]) / raw if raw > 0 else float("nan")}


def conditional_beta(a_w: np.ndarray, F_w: np.ndarray, S_prev: np.ndarray) -> dict:
    """R2b: a = alpha + b F + c S_{w-1} F + d F_{w-1}; S_{w-1} is the factor's trailing
    13-block return ending at the previous block (rows without it are dropped)."""
    ok = np.isfinite(S_prev)
    ok[0] = False
    idx = np.flatnonzero(ok)
    Xr = np.column_stack([F_w[idx], S_prev[idx] * F_w[idx], F_w[idx - 1]])
    L = lags(len(idx))[1]
    b, se = hac.ols(a_w[idx], Xr, L)
    raw = float(a_w.mean())
    return {"alpha_ann": float(b[0]) * ANN, "c": float(b[2]),
            "t_c": float(b[2] / se[2]) if se[2] > 0 else float("nan"),
            "s": float(b[0]) / raw if raw > 0 else float("nan"), "blocks": int(len(idx))}


def trailing(F_w: np.ndarray, n: int = 13) -> np.ndarray:
    """S_{w-1}: the sum of the n blocks ending at w - 1 (NaN until n blocks exist)."""
    c = np.r_[0.0, np.cumsum(F_w)]
    out = np.full(len(F_w), np.nan)
    for w in range(n, len(F_w)):
        out[w] = c[w] - c[w - n]
    return out


# ── verdict ──────────────────────────────────────────────────────────────────
def verdict(p: dict, robust: dict, *, establishing=("R1a", "R1b", "R3", "R4")) -> tuple[str, list]:
    """The pre-stated rule. ``robust``: name -> {"s": ..., and for an exposure check
    "t_E": (t at lag 4, t at the automatic lag)}. Returns (verdict, reasons)."""
    reasons = []
    if not (p["raw_ann"] > 0):
        return INCONCLUSIVE, ["the raw active mean is not positive on the sample"]
    s = p["s"]
    t_alpha = min(p["t_alpha"])
    t_E = min(p["t_E"])
    failing = sorted(k for k, r in robust.items() if not r["s"] >= 0.25)
    primary_survives = s >= 0.5 and t_alpha >= 2.0
    if s >= 0.5:
        if failing:
            v = INCONCLUSIVE
            reasons.append(f"robustness shares below 0.25: {', '.join(failing)}")
        else:
            v = SURVIVES if t_alpha >= 2.0 else UNDERPOWERED
    elif s < 0.25:
        v = BETA if t_E >= 2.0 else BETA_LIKE
    else:
        v = INCONCLUSIVE
    # A robustness factor may establish beta exposure, unless the primary statistic itself
    # meets SURVIVES' bar (then the conflict reads INCONCLUSIVE, as set above).
    if v != BETA and not primary_survives:
        for k in establishing:
            r = robust.get(k)
            if r is not None and r["s"] < 0.25 and min(r["t_E"]) >= 2.5:
                reasons.append(f"{k} establishes beta exposure (s {r['s']:.2f}, t_E {min(r['t_E']):.2f})")
                v = BETA
                break
    return v, reasons
