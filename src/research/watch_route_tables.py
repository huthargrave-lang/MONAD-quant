"""
MONAD Quant — the forward-evidence route's error-rate table and admission-probability
figures, published with the ``admit_watch`` chain (``route.2.json`` ``build.published_with_it``;
docs/research/FORWARD_ROUTE_TABLES.md), by seeded simulation.

The model is the one the 2026-10-09 consensus simulated and the route's arithmetic implies.
A record whose true annual active Sharpe is SR gives, in window year y, an annual Sharpe
estimate Z_y ~ N(SR, 1) (volatility known), so anniversary k reads

    LLR_k = theta * sum_{y <= k} Z_y - k * theta^2 / 2,

a Gaussian random walk, checked once a year from the spec's first decisive anniversary. The
close boundary ln(beta/(1-alpha)) absorbs; the route boundary ln((1-beta)/alpha_i) admits. In
this model the cost-stressed Sharpe is positive at any crossing; H366201's long-leg and
episode conditions can only lower its figures, so its admission column is an upper bound.
After an admission the CUSUM runs on year k's own increment, W_k = max(0, W_{k-1} -
(theta Z_k - theta^2/2)) from W = 0, alarming at W >= h = 2.0 (``route.2.json``
``de_admission``).

The cross-check runs the same design on DAILY data through forward_watch's own statistic
(sample mean and standard deviation with ddof 1, T = n/252), which the yearly model
approximates by treating volatility as known.

Everything is deterministic: each table cell draws from ``numpy.random.default_rng([SEED,
cell])``. The figures are Monte Carlo estimates; each is printed with its standard error.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

SEED = 20261114
THETA, ALPHA, BETA = 0.3, 0.05, 0.2          # both founders' frozen specs (pinned by the test)
PATHS = 200_000
HORIZONS = (20, 40, 100)
LONG = 400                                     # "eventually": the unabsorbed share is reported
CUSUM_H = 2.0
DAILY_PATHS = 10_000
DAILY_YEARS = 40
LOWER = math.log(BETA / (1 - ALPHA))


def boundary(ordinal: int | None = None, *, gamma: float | None = None) -> float:
    """ln((1-beta)/alpha_i): the founders (gamma 1/3) or ordinal i >= 3 (gamma 1/(i(i+1)))."""
    g = gamma if gamma is not None else 1.0 / (ordinal * (ordinal + 1))
    return math.log((1 - BETA) / (ALPHA * g))


FOUNDERS = boundary(gamma=1 / 3)               # ln 48


def wald(upper: float, lower: float = LOWER) -> tuple[float, float]:
    """Wald's approximations to the test's error rates at boundaries A = e^upper,
    B = e^lower: alpha' = (1 - B)/(A - B), beta' = B (A - 1)/(A - B)."""
    a, b = math.exp(upper), math.exp(lower)
    return (1 - b) / (a - b), b * (a - 1) / (a - b)


@dataclass(frozen=True)
class Rate:
    p: float
    n: int

    @property
    def se(self) -> float:
        return math.sqrt(max(self.p * (1 - self.p), 0.0) / self.n)


def _rng(cell: int) -> np.random.Generator:
    return np.random.default_rng([SEED, cell])


def route_rates(upper: float, *, sharpe: float, first: int, cell: int, paths: int = PATHS,
                years: int = LONG, horizons=HORIZONS) -> dict:
    """P(admitted by h) and P(closed by h) for each horizon and at ``years``, before any
    admission, under the yearly model."""
    rng = _rng(cell)
    llr = np.zeros(paths)
    alive = np.ones(paths, dtype=bool)
    admit_at = np.zeros(paths, dtype=np.int32)
    close_at = np.zeros(paths, dtype=np.int32)
    for k in range(1, years + 1):
        llr += THETA * (sharpe + rng.standard_normal(paths)) - THETA ** 2 / 2
        if k < first:
            continue
        up = alive & (llr >= upper)
        down = alive & (llr <= LOWER)
        admit_at[up] = k
        close_at[down] = k
        alive &= ~(up | down)
    out = {"admit": {}, "close": {}}
    for h in tuple(horizons) + (years,):
        out["admit"][h] = Rate(float(np.mean((admit_at > 0) & (admit_at <= h))), paths)
        out["close"][h] = Rate(float(np.mean((close_at > 0) & (close_at <= h))), paths)
    out["open_at_end"] = Rate(float(np.mean(alive)), paths)
    return out


def cusum_rates(*, sharpe: float, cell: int, paths: int = PATHS, years: int = LONG,
                start_llr: float = FOUNDERS, within=(5, 10, 20)) -> dict:
    """From an admission (W = 0, the full-record LLR at ``start_llr``): P(CUSUM alarm within
    w years), the median years to the alarm, and P(the close boundary alone de-admits within
    w years) for comparison."""
    rng = _rng(cell)
    w = np.zeros(paths)
    llr = np.full(paths, start_llr)
    alarm_at = np.zeros(paths, dtype=np.int32)
    close_at = np.zeros(paths, dtype=np.int32)
    for k in range(1, years + 1):
        d = THETA * (sharpe + rng.standard_normal(paths)) - THETA ** 2 / 2
        w = np.maximum(0.0, w - d)
        llr += d
        alarm_at[(alarm_at == 0) & (w >= CUSUM_H)] = k
        close_at[(close_at == 0) & (llr <= LOWER)] = k
    at = np.where(alarm_at > 0, alarm_at, years + 1)
    median = float(np.median(at))
    return {"alarm": {y: Rate(float(np.mean((alarm_at > 0) & (alarm_at <= y))), paths) for y in within},
            "median_years": None if median > years else median,
            "close": {y: Rate(float(np.mean((close_at > 0) & (close_at <= y))), paths) for y in within}}


def daily_llr(x: np.ndarray, theta: float = THETA, per_year: int = 252) -> np.ndarray:
    """(paths, years) LLR at each anniversary from daily actives ``x`` (paths, years * 252),
    exactly as ``forward_watch._reading`` computes it: the full record's sample mean and
    standard deviation (ddof 1), annualised by sqrt(252), T = n/252."""
    paths, n = x.shape
    years = n // per_year
    s1 = np.cumsum(x.reshape(paths, years, per_year).sum(axis=2), axis=1)
    s2 = np.cumsum((x * x).reshape(paths, years, per_year).sum(axis=2), axis=1)
    m = (np.arange(1, years + 1) * per_year).astype(float)
    mean = s1 / m
    var = (s2 - m * mean ** 2) / (m - 1)
    sh = np.where(var > 0, mean / np.sqrt(np.maximum(var, 1e-300)) * math.sqrt(252), 0.0)
    return (m / 252) * (theta * sh - theta ** 2 / 2)


def daily_rates(upper: float, *, sharpe: float, first: int, cell: int, paths: int = DAILY_PATHS,
                years: int = DAILY_YEARS, chunk: int = 500) -> dict:
    """The same design on daily data through the engine's own statistic: P(admit by
    ``years``), P(close by ``years``)."""
    rng = _rng(cell)
    sd = 0.004                                                # any scale: the Sharpe is scale-free
    mu = sharpe * sd / math.sqrt(252)
    admit = close = 0
    for start in range(0, paths, chunk):
        n = min(chunk, paths - start)
        llr = daily_llr(rng.normal(mu, sd, (n, years * 252)))
        alive = np.ones(n, dtype=bool)
        for k in range(1, years + 1):
            if k < first:
                continue
            up = alive & (llr[:, k - 1] >= upper)
            down = alive & (llr[:, k - 1] <= LOWER)
            admit += int(up.sum())
            close += int(down.sum())
            alive &= ~(up | down)
    return {"admit": Rate(admit / paths, paths), "close": Rate(close / paths, paths)}


#: The founders and their first decisive anniversaries (route.2.json test).
WATCHES = (("H366200", 2), ("H366201", 4))
SHARPES = (0.0, 0.15, 0.3)
LATER_ORDINALS = (3, 4, 5)
CUSUM_SHARPES = (0.3, 0.15, 0.0, -0.3)


#: Each published cell's random stream, by a fixed id: adding a cell never moves another.
CELLS = {**{("founders", w, s): 1 + 3 * i + j for i, (w, _f) in enumerate(WATCHES) for j, s in enumerate(SHARPES)},
         **{("later", o): 7 + j for j, o in enumerate(LATER_ORDINALS)},
         **{("cusum", s): 10 + j for j, s in enumerate(CUSUM_SHARPES)},
         ("daily", 0.0): 14, ("daily", 0.3): 15, ("yearly", 0.0): 114, ("yearly", 0.3): 115,
         ("round2",): 16}


def compute(*, paths: int = PATHS, daily_paths: int = DAILY_PATHS) -> dict:
    """Every published table."""
    founders = {(w, s): route_rates(FOUNDERS, sharpe=s, first=f, cell=CELLS[("founders", w, s)], paths=paths)
                for w, f in WATCHES for s in SHARPES}
    later = {i: route_rates(boundary(i), sharpe=0.3, first=1, cell=CELLS[("later", i)], paths=paths)
             for i in LATER_ORDINALS}
    cusum = {s: cusum_rates(sharpe=s, cell=CELLS[("cusum", s)], paths=paths) for s in CUSUM_SHARPES}
    # The debate's close-boundary-alone figure (4.7%) started from round 2's boundary, ln 32.
    round2 = cusum_rates(sharpe=-0.3, cell=CELLS[("round2",)], paths=paths, start_llr=math.log(32))
    daily = {s: {"daily": daily_rates(FOUNDERS, sharpe=s, first=2, cell=CELLS[("daily", s)], paths=daily_paths),
                 "yearly": route_rates(FOUNDERS, sharpe=s, first=2, cell=CELLS[("yearly", s)], paths=paths,
                                       years=DAILY_YEARS, horizons=())}
             for s in (0.0, 0.3)}
    return {"founders": founders, "later": later, "cusum": cusum, "round2": round2, "daily": daily,
            "paths": paths, "daily_paths": daily_paths}


def _pct(r: Rate) -> str:
    return f"{100 * r.p:.2f}%"


def _pct_se(r: Rate) -> str:
    return f"{100 * r.p:.2f}% ± {100 * r.se:.2f}"


def render(t: dict) -> str:
    """The generated block of docs/research/FORWARD_ROUTE_TABLES.md (between its markers)."""
    a_w, b_w = wald(FOUNDERS)
    lines = [f"Seed {SEED}; {t['paths']:,} paths a cell (yearly model), {t['daily_paths']:,} (daily "
             f"cross-check); θ1 {THETA}, α {ALPHA}, β {BETA}; close boundary {LOWER:.4f} nats.", ""]
    lines += ["### 1. The founders' route test (boundary ln 48 = 3.8712 nats)", "",
              "| Watch (first decisive) | True Sharpe | Admitted by 20 y | 40 y | 100 y | "
              f"{LONG} y | Closed by 20 y | 40 y | 100 y | {LONG} y |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for w, f in WATCHES:
        for s in SHARPES:
            r = t["founders"][(w, s)]
            lines.append(f"| {w} ({f}) | {s:g} | " + " | ".join(_pct(r["admit"][h]) for h in HORIZONS + (LONG,))
                         + " | " + " | ".join(_pct(r["close"][h]) for h in HORIZONS + (LONG,)) + " |")
    worst = max(t["founders"][(w, 0.0)]["admit"][LONG].se for w, _f in WATCHES)
    lines += ["", f"Standard errors: at most {100 * worst:.2f} pp for a sub-5% cell and "
              f"{100 * math.sqrt(0.25 / t['paths']):.2f} pp for any cell. Still open after {LONG} years: "
              + ", ".join(f"{w} at Sharpe {s:g}: {_pct(t['founders'][(w, s)]['open_at_end'])}"
                          for w, _f in WATCHES for s in SHARPES) + ".", ""]
    lines += ["### 2. Error rates against the theory", "",
              "| Quantity | Value |", "|---|---|",
              f"| Ville's bound on P(admit) at a true Sharpe of 0 (any horizon): e^(−3.8712) = α_i/(1−β) | "
              f"{100 * math.exp(-FOUNDERS):.2f}% |",
              f"| Wald's approximation α′ = (1−B)/(A−B), A = 48 | {100 * a_w:.2f}% |",
              f"| Wald's approximation β′ = B(A−1)/(A−B), A = 48 | {100 * b_w:.2f}% |"]
    for w, _f in WATCHES:
        lines.append(f"| Simulated P(admit), true Sharpe 0, {w}, by {LONG} y | "
                     f"{_pct_se(t['founders'][(w, 0.0)]['admit'][LONG])} |")
        lines.append(f"| Simulated P(close), true Sharpe 0.3 (β′), {w}, by {LONG} y | "
                     f"{_pct_se(t['founders'][(w, 0.3)]['close'][LONG])} |")
    lines += ["", "### 3. Later watches (true Sharpe 0.3, first decisive anniversary 1)", "",
              "| Ordinal | γ_i | Boundary (nats) | Admitted by 20 y | 40 y | 100 y |", "|---|---|---|---|---|---|"]
    for i in LATER_ORDINALS:
        r = t["later"][i]
        lines.append(f"| {i} | 1/{i * (i + 1)} | {boundary(i):.3f} | "
                     + " | ".join(_pct(r["admit"][h]) for h in HORIZONS) + " |")
    lines += ["", "### 4. After an admission: the CUSUM (h = 2.0, W = 0 at the ADMIT) and the close boundary alone",
              "", "| True Sharpe | CUSUM alarm within 5 y | 10 y | 20 y | Median years to alarm | "
              "Close boundary alone within 20 y (from LLR = ln 48) |", "|---|---|---|---|---|---|"]
    for s in CUSUM_SHARPES:
        c = t["cusum"][s]
        med = f"{c['median_years']:.0f}" if c["median_years"] is not None else f"> {LONG}"
        lines.append(f"| {s:g} | " + " | ".join(_pct(c["alarm"][y]) for y in (5, 10, 20))
                     + f" | {med} | {_pct(c['close'][20])} |")
    lines += ["", f"From round 2's boundary ln 32 = 3.4657 instead, the close boundary alone catches a −0.3 "
              f"watch within 20 years {_pct_se(t['round2']['close'][20])} of the time."]
    lines += ["", f"### 5. Cross-check: the daily statistic vs the yearly model (H366200's design, by "
              f"{DAILY_YEARS} y)", "", "| True Sharpe | | Daily (engine statistic) | Yearly model | "
              "Difference / its standard error |", "|---|---|---|---|---|"]
    for s in (0.0, 0.3):
        d, y = t["daily"][s]["daily"], t["daily"][s]["yearly"]
        for what in ("admit", "close"):
            dr, yr = d[what], y[what][DAILY_YEARS]
            z = (dr.p - yr.p) / math.sqrt(dr.se ** 2 + yr.se ** 2) if (dr.se or yr.se) else 0.0
            lines.append(f"| {s:g} | P({what}) | {_pct_se(dr)} | {_pct_se(yr)} | {z:+.2f} |")
    return "\n".join(lines)
