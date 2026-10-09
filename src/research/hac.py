"""
MONAD Quant — heteroskedasticity- and autocorrelation-consistent (Newey-West, Bartlett
kernel) inference for means, ratios of means and OLS coefficients.

Older report tools carry their own copies of these few lines; their recorded results are
left untouched. New statistics should use this module.
"""
from __future__ import annotations

import math

import numpy as np


def auto_lag(n: int) -> int:
    """The Newey-West (1994) rule of thumb, floor(4 (n/100)^(2/9))."""
    return int(math.floor(4 * (n / 100.0) ** (2.0 / 9.0)))


def long_run_cov(u: np.ndarray, lag: int) -> np.ndarray:
    """Bartlett long-run covariance of the columns of ``u`` (rows are time; each column is
    demeaned here). A 1-d input gives a 1x1 matrix."""
    u = np.asarray(u, dtype=float)
    if u.ndim == 1:
        u = u[:, None]
    u = u - u.mean(axis=0)
    n = len(u)
    S = u.T @ u / n
    for k in range(1, min(lag, n - 1) + 1):
        G = u[k:].T @ u[:-k] / n
        S = S + (1.0 - k / (lag + 1.0)) * (G + G.T)
    return S


def mean_t(x: np.ndarray, lag: int) -> tuple[float, float, float]:
    """(mean, standard error of the mean, t)."""
    x = np.asarray(x, dtype=float)
    m = float(x.mean())
    var = float(long_run_cov(x, lag)[0, 0]) / len(x)
    se = math.sqrt(var) if var > 0 else float("nan")
    return m, se, (m / se if se > 0 else float("nan"))


def ols(y: np.ndarray, X: np.ndarray, lag: int) -> tuple[np.ndarray, np.ndarray]:
    """OLS of ``y`` on a constant and the columns of ``X``: (coefficients, NW standard
    errors), the constant first."""
    y = np.asarray(y, dtype=float)
    A = np.column_stack([np.ones(len(y)), np.asarray(X, dtype=float).reshape(len(y), -1)])
    b, *_ = np.linalg.lstsq(A, y, rcond=None)
    scores = (y - A @ b)[:, None] * A
    n = len(y)
    S = scores.T @ scores
    for k in range(1, min(lag, n - 1) + 1):
        G = scores[k:].T @ scores[:-k]
        S = S + (1.0 - k / (lag + 1.0)) * (G + G.T)
    inv = np.linalg.pinv(A.T @ A)
    V = inv @ S @ inv
    return b, np.sqrt(np.maximum(np.diag(V), 0.0))


def fieller(num: np.ndarray, den: np.ndarray, lag: int, z: float = 1.959963984540054
            ) -> tuple[float, float] | None:
    """The Fieller confidence set for mean(num) / mean(den) with NW covariance of the two
    means: (lower, upper) when it is a bounded interval, None when it is unbounded (the
    denominator is not distinguishable from zero at this level)."""
    num = np.asarray(num, dtype=float)
    den = np.asarray(den, dtype=float)
    n = len(num)
    V = long_run_cov(np.column_stack([num, den]), lag) / n
    a_, d_ = float(num.mean()), float(den.mean())
    A = d_ * d_ - z * z * V[1, 1]
    B = a_ * d_ - z * z * V[0, 1]
    C = a_ * a_ - z * z * V[0, 0]
    if A <= 0:
        return None
    disc = B * B - A * C
    if disc < 0:
        return None
    r = math.sqrt(disc)
    return (B - r) / A, (B + r) / A
