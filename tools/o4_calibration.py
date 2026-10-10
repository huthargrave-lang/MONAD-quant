"""
o4_calibration — the frozen beta-exposure method on synthetic books with known answers, for
the board that resolves objection O4 on H404702 (docs/research/O4_RESOLUTION_PROTOCOL.md,
frozen before this ran).

  venv/bin/python tools/o4_calibration.py [--seeds 100] [--json docs/research/data/o4_calibration.json]

Three books, 100 seeds each, in a world sized like H404702's sample (1,092 blocks, four
categories of ten assets):
  S  pure selection (expected active 2.2%/yr)          pass: SURVIVES in >= 90% of seeds
  T  linear timed beta, true kept share 0.26           pass: never SURVIVES/UNDERPOWERED in
                                                       >= 95%, median |s - s*| <= 0.10
  C  convex payoff (gains in up blocks only)           pass: R2 convexity detected in >= 90%
No market data, no trial: the method's own statistics() from tools/beta_timing_control.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import beta_timing_control as btc  # noqa: E402

from src.research import beta_control as bc  # noqa: E402

PROTOCOL = "docs/research/O4_RESOLUTION_PROTOCOL.md"
OUT = REPO / "docs/research/data/o4_calibration.json"
SESSIONS = 5460
CATEGORIES = 4
PER_CATEGORY = 10
HELD = 5
F_MEAN, F_SD, F_CORR = 0.0003, 0.008, 0.5
BETA_LO, BETA_HI = 0.6, 1.4
IDIO_SD = 0.006
PERIOD = 21
TARGET_ACTIVE = 0.022 / 252          # daily
TRUE_SHARE = 0.26
BOOKS = ("S", "T", "C")
PASS = {"S": "SURVIVES in >= 90% of seeds",
        "T": "neither SURVIVES nor UNDERPOWERED in >= 95% of seeds, and median |s - s*| <= 0.10",
        "C": "R2 convexity detected in >= 90% of seeds"}


def _top_half_gap() -> float:
    """E[mean of the top 5 of 10 standard normals - mean of all 10], by a fixed-seed draw."""
    z = np.sort(np.random.default_rng(20261009).standard_normal((400_000, PER_CATEGORY)), axis=1)
    return float((z[:, PER_CATEGORY - HELD:].mean(axis=1) - z.mean(axis=1)).mean())


def _timing_moment() -> float:
    """E[F_t sign(F_block)] for iid normal daily factors, t inside the 5-session block."""
    f = np.random.default_rng(20261010).normal(F_MEAN, F_SD, (400_000, bc.BLOCK))
    return float((f[:, 0] * np.sign(f.sum(axis=1))).mean())


def _convex_moment() -> float:
    """E[max(F_block, 0)] for the 5-session block sum of iid normal daily factors."""
    m, s = bc.BLOCK * F_MEAN, F_SD * math.sqrt(bc.BLOCK)
    phi = math.exp(-0.5 * (m / s) ** 2) / math.sqrt(2 * math.pi)
    Phi = 0.5 * (1 + math.erf(m / s / math.sqrt(2)))
    return s * phi + m * Phi


GAP, TIMING, CONVEX = _top_half_gap(), _timing_moment(), _convex_moment()


def world(rng):
    dates = pd.bdate_range("2004-01-02", periods=SESSIONS)
    cov = F_SD ** 2 * (F_CORR * np.ones((CATEGORIES, CATEGORIES)) + (1 - F_CORR) * np.eye(CATEGORIES))
    F = rng.multivariate_normal(np.full(CATEGORIES, F_MEAN), cov, SESSIONS)
    cat = np.repeat(np.arange(CATEGORIES), PER_CATEGORY)
    beta = rng.uniform(BETA_LO, BETA_HI, CATEGORIES * PER_CATEGORY)
    idio = rng.normal(0.0, IDIO_SD, (SESSIONS, CATEGORIES * PER_CATEGORY))
    grid = bc.block_grid(dates, dates[0])
    return dates, F, cat, beta, idio, grid


def _block_of(dates, grid):
    """Block number per session (the incomplete tail block, if any, takes -1)."""
    out = np.full(len(dates), -1)
    out[: len(grid)] = grid.to_numpy()
    return out


def _within_category(cat, scores) -> np.ndarray:
    """Weights: equal across categories, equal across the HELD highest scores within each."""
    w = np.zeros_like(scores)
    for c in range(CATEGORIES):
        idx = np.flatnonzero(cat == c)
        top = idx[np.argsort(scores[idx])[-HELD:]]
        w[top] = 1.0 / CATEGORIES / HELD
    return w


def book(name: str, rng) -> dict:
    """One synthetic book: its daily active, held weight differences, asset returns, the
    per-asset factor (category equal weight without the asset), the benchmark return, and
    the realised true kept share where it is defined."""
    dates, F, cat, beta, idio, grid = world(rng)
    n = len(beta)
    blk = _block_of(dates, grid)
    r = beta[None, :] * F[:, cat] + idio
    bench_w = np.full(n, 1.0 / n)
    delta = np.zeros((SESSIONS, n))
    true_share = None
    if name in ("S", "T"):
        sigma_a = TARGET_ACTIVE / GAP
        alpha = np.zeros((SESSIONS, n))
        for start in range(0, SESSIONS, PERIOD):
            a = rng.normal(0.0, sigma_a, n)
            alpha[start:start + PERIOD] = a
            delta[start:start + PERIOD] = _within_category(cat, a) - bench_w
        r = r + alpha
        if name == "T":
            sel = TRUE_SHARE * delta
            dev = np.zeros(n)
            for c in range(CATEGORIES):
                idx = cat == c
                dev[idx] = beta[idx] - beta[idx].mean()
            k = (1 - TRUE_SHARE) * TARGET_ACTIVE / (float((dev * beta).sum()) / CATEGORIES * TIMING) / CATEGORIES
            Fb = pd.DataFrame(F).groupby(blk).transform("sum").to_numpy()      # this block's factor sum
            tim = k * dev[None, :] * np.sign(Fb[:, cat])
            tim[blk < 0] = 0.0
            delta = sel + tim
            a_sel, a_tim = (sel * r).sum(axis=1), (tim * r).sum(axis=1)
            true_share = (a_sel, a_tim)
    elif name == "C":
        g = TARGET_ACTIVE / (0.5 * CONVEX / bc.BLOCK)
        Fb = pd.DataFrame(F).groupby(blk).transform("sum").to_numpy()
        convex = np.zeros(n, dtype=bool)
        for c in range(CATEGORIES):
            convex[np.flatnonzero(cat == c)[:HELD]] = True
        extra = g * np.maximum(Fb[:, cat], 0.0) / bc.BLOCK * convex[None, :]
        extra[blk < 0] = 0.0
        r = r + extra
        w = np.where(convex, 1.0 / CATEGORIES / HELD, 0.0)
        delta[:] = w - bench_w
    cols = [f"a{i}" for i in range(n)]
    R = pd.DataFrame(r, index=dates, columns=cols)
    D = pd.DataFrame(delta, index=dates, columns=cols)
    active = (D * R).sum(axis=1)
    bench = R.mean(axis=1)
    fcat = {}
    for c in range(CATEGORIES):
        members = [cols[i] for i in np.flatnonzero(cat == c)]
        tot = R[members].sum(axis=1)
        for m in members:
            fcat[m] = (tot - R[m]) / (len(members) - 1)
    return {"dates": dates, "grid": grid, "active": active, "delta": D, "assets": R,
            "factor": pd.DataFrame(fcat)[cols], "bench": bench, "true_share": true_share}


def control(b: dict) -> dict:
    """The frozen method on one book: the variants the synthetic world supports."""
    cols = list(b["assets"].columns)
    variants = {"primary": ([b["factor"]], btc.PRIMARY_WINDOW, btc.PRIMARY_MIN, frozenset()),
                "R1a": ([btc.frame_of(b["bench"], cols)], btc.PRIMARY_WINDOW, btc.PRIMARY_MIN, frozenset()),
                "R4": ([b["factor"]], btc.SHORT_WINDOW, btc.SHORT_MIN, frozenset())}
    out = btc.statistics(b["active"], b["delta"], b["assets"], b["grid"], btc.PRIMARY_MIN, variants, b["bench"])
    res = {"verdict": out["verdict"], "s": out["primary"]["s"], "t_alpha": min(out["primary"]["t_alpha"]),
           "t_E": min(out["primary"]["t_E"]), "convexity_detected": out["R2"]["convexity_detected"],
           "t_c": out["R2"]["t_c"], "s_R2": out["R2"]["s"]}
    if b["true_share"] is not None:
        sample = b["grid"][b["grid"] >= btc.PRIMARY_MIN]
        a_sel, a_tim = b["true_share"]
        idx = sample.index
        pos = b["dates"].get_indexer(idx)
        sel, tim = float(a_sel[pos].mean()), float(a_tim[pos].mean())
        res["true_s"] = sel / (sel + tim)
    return res


def run(seeds: int) -> dict:
    results = {}
    for i, name in enumerate(BOOKS):
        rows = [control(book(name, np.random.default_rng(seed * len(BOOKS) + i))) for seed in range(seeds)]
        verdicts = pd.Series([r["verdict"] for r in rows]).value_counts().to_dict()
        summary = {"seeds": seeds, "verdicts": verdicts,
                   "mean_s": float(np.mean([r["s"] for r in rows])),
                   "mean_t_alpha": float(np.mean([r["t_alpha"] for r in rows])),
                   "convexity_rate": float(np.mean([r["convexity_detected"] for r in rows]))}
        if name == "S":
            rate = verdicts.get(bc.SURVIVES, 0) / seeds
            summary.update({"survives_rate": rate, "passed": rate >= 0.90})
        elif name == "T":
            bad = (verdicts.get(bc.SURVIVES, 0) + verdicts.get(bc.UNDERPOWERED, 0)) / seeds
            gap = float(np.median([abs(r["s"] - r["true_s"]) for r in rows]))
            summary.update({"survives_or_underpowered_rate": bad, "median_abs_s_error": gap,
                            "mean_true_s": float(np.mean([r["true_s"] for r in rows])),
                            "passed": (1 - bad) >= 0.95 and gap <= 0.10})
        else:
            rate = summary["convexity_rate"]
            summary.update({"passed": rate >= 0.90})
        summary["pass_rule"] = PASS[name]
        results[name] = summary
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--json", default=str(OUT))
    args = ap.parse_args(argv)
    out = {"schema_version": 1, "vintage": pd.Timestamp.today().date().isoformat(), "protocol": PROTOCOL,
           "world": {"sessions": SESSIONS, "categories": CATEGORIES, "per_category": PER_CATEGORY,
                     "factor": [F_MEAN, F_SD, F_CORR], "beta": [BETA_LO, BETA_HI], "idio_sd": IDIO_SD,
                     "target_active_ann": TARGET_ACTIVE * 252, "true_share_T": TRUE_SHARE},
           "moments": {"top_half_gap": GAP, "timing": TIMING, "convex": CONVEX},
           "results": run(args.seeds)}
    text = json.dumps(out, indent=1, sort_keys=True, default=float) + "\n"
    Path(args.json).write_text(text, encoding="utf-8")
    print(f"wrote {args.json} (sha256 {hashlib.sha256(text.encode()).hexdigest()})")
    for name, s in out["results"].items():
        print(name, "PASS" if s["passed"] else "FAIL", json.dumps({k: v for k, v in s.items() if k != "pass_rule"},
                                                                  default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
