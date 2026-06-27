"""
MONAD Quant — Uncertainty bands for backtest results.

The companion to ``metrics.py``. Where ``metrics`` returns a single point
estimate — one Sharpe, one win rate, one return — this module returns the
*distribution around it*, so a result can be reported as a range you calibrate
your trust to, not a number you over-trust.

Why this exists (the project's own history): every major reversal here was a
point estimate that looked great until uncertainty analysis deflated it —
holdout-selection bias inflating the sweep (RESEARCH_WEB.md F2), the morning-only
data-sampling artifact (F13), naive t-stats that were ~3x too confident (F18),
and the no-edge-vs-static verdict (D6). The robust machinery that produced those
corrections lived only in the research lab (``tools/mr_daily_lab.py``); this
promotes it to a shared, unit-tested module the backtest/sweep reporting can call.

Methods (all deterministic given ``seed``; no scipy dependency):
  * ``block_bootstrap``    — moving-block resample that PRESERVES short-range
                             autocorrelation. Essential: the daily mean-reversion
                             "edge" under test (F16) literally *is* lag-1
                             autocorrelation, so an i.i.d. bootstrap would shuffle
                             it away and overstate confidence. Mirrors the 20-day
                             block bootstrap in ``tools/mr_daily_lab.py``.
  * ``sharpe_band``        — block-bootstrap CI around ``metrics.annualized_sharpe``.
  * ``total_return_band``  — block-bootstrap CI around the compounded total return.
  * ``winrate_posterior``  — Beta-Binomial credible interval on the win rate, so a
                             60% WR over 10 trades reports a far wider band than
                             over 500 (same point estimate, different evidence).
  * ``montecarlo_equity``  — resample the closed-trade sequence into many equity
                             paths; percentile bands on final equity and max
                             drawdown, plus P(end below start).

Everything reuses ``metrics.py`` (one Sharpe / one drawdown definition across the
codebase — the historical walk-forward bug came from a *second* divergent Sharpe).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.backtest import metrics

# A series shorter than this can't be block-bootstrapped into a stable CI; the
# band functions report a point-only (degenerate) band rather than a false range.
_MIN_BOOTSTRAP_N = 8


@dataclass(frozen=True)
class Band:
    """A point estimate plus the uncertainty interval around it.

    point  — the statistic on the observed sample (what ``metrics`` reports today)
    lo, hi — lower/upper bounds of the interval (NaN when the sample is too small)
    level  — interval coverage, e.g. 0.95
    method — how the band was produced (block-bootstrap / Beta-posterior /
             monte-carlo), carried so a report stays honest about WHERE it came from
    n      — sample size behind the estimate (the evidence, not just the estimate)
    """

    point: float
    lo: float
    hi: float
    level: float
    method: str
    n: int

    @property
    def width(self) -> float:
        """Interval width (NaN if degenerate)."""
        return self.hi - self.lo

    @property
    def degenerate(self) -> bool:
        """True when no interval could be computed (sample too small)."""
        return not np.isfinite(self.lo) or not np.isfinite(self.hi)

    def __str__(self) -> str:
        if self.degenerate:
            return f"{self.point:.4f}  [n/a] (n={self.n})"
        return (
            f"{self.point:.4f}  [{self.lo:.4f}, {self.hi:.4f}] "
            f"({self.level:.0%} {self.method}, n={self.n})"
        )


@dataclass(frozen=True)
class EquityBands:
    """Monte-Carlo bands on an equity path's endpoint and worst drawdown."""

    final_equity: Band          # percentile band on ending capital
    max_drawdown: Band          # percentile band on worst peak-to-trough (<= 0)
    prob_below_initial: float   # fraction of resampled paths ending below the start
    n_paths: int


# ── Primitives ──────────────────────────────────────────────────────────────


def _effective_block(n: int, requested: int) -> int:
    """Block length that fits the series: never longer than ``n//4`` (so there are
    at least ~4 resampled blocks for variety) nor longer than the series itself."""
    return max(1, min(int(requested), n // 4))


def _band_from_samples(point, samples, level, method, n) -> Band:
    a = (1.0 - level) / 2.0
    lo, hi = np.percentile(samples, [100.0 * a, 100.0 * (1.0 - a)])
    return Band(float(point), float(lo), float(hi), float(level), method, int(n))


def block_bootstrap(x, stat_fn, *, block, n_boot=2000, seed=0):
    """Moving-block bootstrap of ``stat_fn`` over a return series.

    Resamples ``n // block`` blocks of consecutive observations (with replacement)
    and re-evaluates ``stat_fn`` on each synthetic series. Returns the array of
    ``n_boot`` resampled statistics. Block resampling preserves short-range
    autocorrelation — the whole point here, since the mean-reversion signal under
    test *is* autocorrelation.

    O(n_boot * n); this is offline reporting, not a hot path.
    """
    x = np.asarray(x, dtype=float)
    n = x.size
    block = max(1, min(int(block), n))
    n_blocks = max(1, n // block)
    last_start = n - block
    rng = np.random.default_rng(seed)
    out = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        starts = rng.integers(0, last_start + 1, size=n_blocks)
        out[b] = stat_fn(np.concatenate([x[s:s + block] for s in starts]))
    return out


# ── Bands on the headline metrics ───────────────────────────────────────────


def sharpe_band(period_returns, trades_per_year, *, block=20, n_boot=2000,
                level=0.95, seed=0) -> Band:
    """Block-bootstrap CI around ``metrics.annualized_sharpe``.

    The annualization frequency (``trades_per_year``) is a property of the
    strategy's cadence, not of the resample, so it is held fixed across bootstrap
    samples — only the mean/std of returns vary.
    """
    r = np.asarray(period_returns, dtype=float)
    n = r.size
    point = metrics.annualized_sharpe(r, trades_per_year)
    if n < _MIN_BOOTSTRAP_N:
        return Band(point, float("nan"), float("nan"), level,
                    f"block-bootstrap(n<{_MIN_BOOTSTRAP_N})", n)
    eb = _effective_block(n, block)
    samples = block_bootstrap(
        r, lambda s: metrics.annualized_sharpe(s, trades_per_year),
        block=eb, n_boot=n_boot, seed=seed,
    )
    return _band_from_samples(point, samples, level, f"block-bootstrap(b={eb},B={n_boot})", n)


def total_return_band(period_returns, *, block=20, n_boot=2000, level=0.95,
                      seed=0) -> Band:
    """Block-bootstrap CI around the compounded total return of the trade sequence."""
    r = np.asarray(period_returns, dtype=float)
    n = r.size
    point = float(np.prod(1.0 + r) - 1.0) if n else float("nan")
    if n < _MIN_BOOTSTRAP_N:
        return Band(point, float("nan"), float("nan"), level,
                    f"block-bootstrap(n<{_MIN_BOOTSTRAP_N})", n)
    eb = _effective_block(n, block)
    samples = block_bootstrap(
        r, lambda s: np.prod(1.0 + s) - 1.0, block=eb, n_boot=n_boot, seed=seed,
    )
    return _band_from_samples(point, samples, level, f"block-bootstrap(b={eb},B={n_boot})", n)


def winrate_posterior(wins, n_trades, *, level=0.95, prior=(0.5, 0.5),
                      n_draws=40000, seed=0) -> Band:
    """Beta-Binomial credible interval on the win rate.

    A 60% win rate over 10 trades and over 500 trades are the same point estimate
    but very different evidence — this reports the second as a much tighter band.
    Default prior is Jeffreys ``Beta(0.5, 0.5)``. ``point`` is the *observed* win
    rate (for continuity with existing reports); the interval is the equal-tailed
    posterior credible interval, sampled so there is no scipy dependency.
    """
    wins = int(wins)
    n_trades = int(n_trades)
    if n_trades <= 0:
        return Band(float("nan"), float("nan"), float("nan"), level, "beta-posterior", 0)
    observed = wins / n_trades
    a = prior[0] + wins
    b = prior[1] + (n_trades - wins)
    rng = np.random.default_rng(seed)
    draws = rng.beta(a, b, size=n_draws)
    alpha = (1.0 - level) / 2.0
    lo, hi = np.percentile(draws, [100.0 * alpha, 100.0 * (1.0 - alpha)])
    return Band(float(observed), float(lo), float(hi), float(level),
                f"beta-posterior{tuple(prior)}", n_trades)


def _row_max_drawdowns(equity_paths):
    """Per-row max drawdown for an ``(n_paths, n_steps)`` equity matrix.

    Vectorized equivalent of ``metrics.max_drawdown`` applied to each row (the two
    are pinned equal in the tests, so they can't silently diverge)."""
    running_max = np.maximum.accumulate(equity_paths, axis=1)
    drawdown = (equity_paths - running_max) / running_max
    return drawdown.min(axis=1)


def montecarlo_equity(per_trade_returns, *, initial_capital=100_000.0, n_paths=2000,
                      level=0.95, seed=0) -> EquityBands:
    """Resample the closed-trade P&L sequence into many equity paths.

    Each path draws ``n`` trades with replacement from the observed per-trade
    returns and compounds them, answering "given these trades, how lucky or unlucky
    was the realized ordering?". Trades are treated as exchangeable (i.i.d.
    resample), which is appropriate for CLOSED-position returns; do NOT use this on
    bar returns where autocorrelation matters (use ``block_bootstrap`` there).
    """
    r = np.asarray(per_trade_returns, dtype=float)
    n = r.size
    if n == 0:
        nan_band = Band(float("nan"), float("nan"), float("nan"), level, "monte-carlo", 0)
        return EquityBands(nan_band, nan_band, float("nan"), 0)

    obs_equity = initial_capital * np.cumprod(1.0 + r)
    obs_final = float(obs_equity[-1])
    obs_dd = metrics.max_drawdown(obs_equity)

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_paths, n))
    paths = initial_capital * np.cumprod(1.0 + r[idx], axis=1)
    finals = paths[:, -1]
    dds = _row_max_drawdowns(paths)

    final_band = _band_from_samples(obs_final, finals, level, "monte-carlo", n)
    dd_band = _band_from_samples(obs_dd, dds, level, "monte-carlo", n)
    prob_below = float(np.mean(finals < initial_capital))
    return EquityBands(final_band, dd_band, prob_below, int(n_paths))


# ── Convenience: one call per backtest result ───────────────────────────────


def summarize(period_returns, *, wins=None, trades_per_year=None,
              initial_capital=100_000.0, level=0.95, block=20, n_boot=2000,
              n_paths=2000, seed=0) -> dict:
    """Bundle every band for a single backtest's per-trade return series.

    ``wins`` and ``trades_per_year`` default to values derived from the returns
    (wins = count of positive trades; frequency = trade count, i.e. unannualized)
    but should be passed explicitly when the caller knows the true calendar span.
    """
    r = np.asarray(period_returns, dtype=float)
    n = r.size
    wins = int((r > 0).sum()) if wins is None else int(wins)
    tpy = float(n) if trades_per_year is None else float(trades_per_year)
    return {
        "n_trades": n,
        "level": level,
        "sharpe": sharpe_band(r, tpy, block=block, n_boot=n_boot, level=level, seed=seed),
        "total_return": total_return_band(r, block=block, n_boot=n_boot, level=level, seed=seed),
        "win_rate": winrate_posterior(wins, n, level=level, seed=seed),
        "equity": montecarlo_equity(r, initial_capital=initial_capital, n_paths=n_paths,
                                    level=level, seed=seed),
    }


def _fmt_ratio(b: Band) -> str:
    if b.degenerate:
        return f"{b.point:.3f}  [n/a]"
    return f"{b.point:.3f}  [{b.lo:.3f}, {b.hi:.3f}]"


def _fmt_pct(b: Band) -> str:
    if b.degenerate:
        return f"{b.point:+.2%}  [n/a]"
    return f"{b.point:+.2%}  [{b.lo:+.2%}, {b.hi:+.2%}]"


def format_report(summary: dict) -> str:
    """Render a ``summarize()`` dict into aligned, human-readable lines (pure)."""
    s = summary
    eq = s["equity"]
    lines = [
        f"Uncertainty bands ({s['level']:.0%} CI, n={s['n_trades']} trades):",
        f"  Sharpe ............ {_fmt_ratio(s['sharpe'])}",
        f"  Total return ...... {_fmt_pct(s['total_return'])}",
        f"  Win rate .......... {s['win_rate'].point:.1%}"
        + ("" if s['win_rate'].degenerate
           else f"  [{s['win_rate'].lo:.1%}, {s['win_rate'].hi:.1%}]"),
        f"  Final equity ...... ${eq.final_equity.point:,.0f}"
        + ("" if eq.final_equity.degenerate
           else f"  [${eq.final_equity.lo:,.0f}, ${eq.final_equity.hi:,.0f}]"),
        f"  Max drawdown ...... {_fmt_pct(eq.max_drawdown)}",
        f"  P(end below start)  {eq.prob_below_initial:.1%}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover - runnable smoke demo, no network/data
    # Synthetic 49%-win, slight-positive-edge trade stream — shape of BTC_DAILY.
    _rng = np.random.default_rng(7)
    _wins = _rng.normal(0.03, 0.01, size=41)     # ~41 winners near +3% target
    _losses = -_rng.normal(0.015, 0.005, size=42)  # ~42 losers near -1.5% stop
    _returns = np.concatenate([_wins, _losses])
    _rng.shuffle(_returns)
    print(format_report(summarize(_returns, trades_per_year=16, seed=0)))
