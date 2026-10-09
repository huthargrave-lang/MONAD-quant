"""
convexity_control — the convexity-robust control (docs/research/CONVEXITY_CONTROL_PROTOCOL.md,
frozen first). Calibration on synthetic books with known answers comes first; market data
runs only for what the calibration passes.

  venv/bin/python tools/convexity_control.py calibrate [--workers 16]
      books S, T, C, Cglob, Cday, Cmon, Cdyn on fresh seeds 1000-1099 (bootstrap B 199), and
      the CEFS-scale pure-alpha and pure-convex books on seeds 2000-2199; writes
      docs/research/data/convexity_calibration.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import o4_calibration as o4  # noqa: E402

from src.research import beta_control as bc  # noqa: E402
from src.research import convexity_control as cx  # noqa: E402

PROTOCOL = "docs/research/CONVEXITY_CONTROL_PROTOCOL.md"
CAL_OUT = REPO / "docs/research/data/convexity_calibration.json"
SEEDS = range(1000, 1100)
PRODUCT_SEEDS = range(2000, 2200)
CAL_REPS = 199
BOOKS = ("S", "T", "C", "Cglob", "Cday", "Cmon", "Cdyn")
CONVEX_BOOKS = ("C", "Cglob", "Cday", "Cmon", "Cdyn")
WINDOW, MINIMUM, MIN_BLOCKS = 156, 48, 48
PRODUCT = {"blocks": 423, "window": 104, "minimum": 52, "min_blocks": 52, "q_mean": 0.0003, "q_sd": 0.010,
           "tracking_error": 0.09, "active": 0.054}


# ── synthetic books ──────────────────────────────────────────────────────────
def _assemble(dates, grid, cat, r, delta, true_share=None) -> dict:
    """Active, weights, returns, each asset's leave-one-out category factor, and the global
    factor (equal weight of all assets), as tools/o4_calibration.py builds them."""
    cols = [f"a{i}" for i in range(r.shape[1])]
    R = pd.DataFrame(r, index=dates, columns=cols)
    D = pd.DataFrame(delta, index=dates, columns=cols)
    fcat = {}
    for c in range(o4.CATEGORIES):
        members = [cols[i] for i in np.flatnonzero(cat == c)]
        tot = R[members].sum(axis=1)
        for m in members:
            fcat[m] = (tot - R[m]) / (len(members) - 1)
    return {"active": (D * R).sum(axis=1), "delta": D, "assets": R, "factor": pd.DataFrame(fcat)[cols],
            "bench": R.mean(axis=1), "grid": grid, "true_share": true_share, "dates": dates}


def _convex_set(cat) -> np.ndarray:
    s = np.zeros(len(cat), dtype=bool)
    for c in range(o4.CATEGORIES):
        s[np.flatnonzero(cat == c)[:o4.HELD]] = True
    return s


def book(name: str, seed: int) -> dict:
    if name in ("S", "T", "C"):
        b = o4.book(name, np.random.default_rng(seed))
        return {**b, "dates": b["dates"]}
    rng = np.random.default_rng(seed)
    dates, F, cat, beta, idio, grid = o4.world(rng)
    n = len(beta)
    blk = o4._block_of(dates, grid)
    base = beta[None, :] * F[:, cat] + idio
    bench_w = np.full(n, 1.0 / n)
    target = o4.TARGET_ACTIVE
    convex = _convex_set(cat)
    hold_w = np.where(convex, 1.0 / o4.CATEGORIES / o4.HELD, 0.0)
    if name == "Cglob":
        Bb = pd.Series(base.mean(axis=1)).groupby(blk).transform("sum").to_numpy()
        drive = np.clip(Bb, 0, None) / bc.BLOCK
        drive[blk < 0] = 0.0
        g = target / (0.5 * drive[blk >= 0].mean())
        extra = g * drive[:, None] * convex[None, :]
        delta = np.repeat((hold_w - bench_w)[None, :], len(dates), axis=0)
    elif name == "Cday":
        drive = np.clip(F, 0, None)[:, cat]
        g = target / (0.5 * drive.mean())
        extra = g * drive * convex[None, :]
        delta = np.repeat((hold_w - bench_w)[None, :], len(dates), axis=0)
    elif name == "Cmon":
        win = np.arange(len(dates)) // (4 * bc.BLOCK)
        M = pd.DataFrame(F).groupby(win).transform("sum").to_numpy()
        drive = np.clip(M, 0, None)[:, cat] / (4 * bc.BLOCK)
        g = target / (0.5 * drive.mean())
        extra = g * drive * convex[None, :]
        delta = np.repeat((hold_w - bench_w)[None, :], len(dates), axis=0)
    elif name == "Cdyn":
        Fb = pd.DataFrame(F).groupby(blk).transform("sum").to_numpy()
        drive = np.clip(Fb, 0, None)[:, cat] / bc.BLOCK
        drive[blk < 0] = 0.0
        held = np.zeros((len(dates), n), dtype=bool)
        for start in range(0, len(dates), o4.PERIOD):
            pick = np.zeros(n, dtype=bool)
            for c in range(o4.CATEGORIES):
                pick[rng.choice(np.flatnonzero(cat == c), o4.HELD, replace=False)] = True
            held[start:start + o4.PERIOD] = pick
        g = target / (0.5 * drive[blk >= 0].mean())
        extra = g * drive * held
        delta = np.where(held, 1.0 / o4.CATEGORIES / o4.HELD, 0.0) - bench_w[None, :]
    else:
        raise ValueError(name)
    return _assemble(dates, grid, cat, base + extra, delta)


def product_book(kind: str, seed: int) -> dict:
    """CEFS scale: a product P against its benchmark Q (PCEF-like), pure alpha or pure
    convex, 423 blocks, tracking error 9%/yr, active 5.4%/yr."""
    rng = np.random.default_rng(seed)
    n = PRODUCT["blocks"] * bc.BLOCK
    dates = pd.bdate_range("2014-01-02", periods=n)
    grid = bc.block_grid(dates, dates[0])
    q = rng.normal(PRODUCT["q_mean"], PRODUCT["q_sd"], n)
    noise = rng.normal(0.0, PRODUCT["tracking_error"] / np.sqrt(252), n)
    if kind == "alpha":
        p = q + PRODUCT["active"] / 252 + noise
    elif kind == "convex":
        qb = pd.Series(q).groupby(np.arange(n) // bc.BLOCK).transform("sum").to_numpy()
        drive = np.clip(qb, 0, None) / bc.BLOCK
        g = PRODUCT["active"] / 252 / drive.mean()
        p = q + g * drive + noise
    else:
        raise ValueError(kind)
    R = pd.DataFrame({"P": p, "Q": q}, index=dates)
    D = pd.DataFrame({"P": 1.0, "Q": -1.0}, index=dates)
    fac = pd.DataFrame({"P": R["Q"], "Q": R["Q"]})
    return {"active": R["P"] - R["Q"], "delta": D, "assets": R, "factor": fac, "bench": None, "grid": grid}


def run_one(task) -> dict:
    kind, name, seed = task
    if kind == "book":
        b = book(name, seed)
        blocks = cx.build_blocks(b["active"], b["delta"], b["assets"], b["factor"], b["bench"], b["grid"])
        out = cx.control(blocks, min_blocks=MIN_BLOCKS, window=WINDOW, minimum=MINIMUM, reps=CAL_REPS, seed=seed)
        if b.get("true_share") is not None:
            sample = b["grid"][b["grid"] >= MIN_BLOCKS]
            pos = b["dates"].get_indexer(sample.index)
            a_sel, a_tim = b["true_share"]
            sel, tim = float(a_sel[pos].mean()), float(a_tim[pos].mean())
            out["true_s"] = sel / (sel + tim)
    else:
        b = product_book(name, seed)
        blocks = cx.build_blocks(b["active"], b["delta"], b["assets"], b["factor"], None, b["grid"])
        out = cx.control(blocks, min_blocks=PRODUCT["min_blocks"], window=PRODUCT["window"],
                         minimum=PRODUCT["minimum"], reps=CAL_REPS, seed=seed)
    return {"kind": kind, "name": name, "seed": seed, "verdict": out["verdict"], "s": out["s"],
            "t_alpha": min(out["t_alpha"]), "t_E": min(out["t_E"]), "true_s": out.get("true_s"),
            "downgraded": out["downgrade"]["applied"]}


def summarise(rows: list[dict]) -> dict:
    def rate(rs, labels):
        return sum(r["verdict"] in labels for r in rs) / len(rs)
    by = {}
    for r in rows:
        by.setdefault((r["kind"], r["name"]), []).append(r)
    out, passed = {}, {}
    for (kind, name), rs in sorted(by.items()):
        v = pd.Series([r["verdict"] for r in rs]).value_counts().to_dict()
        summ = {"seeds": len(rs), "verdicts": v, "median_s": float(np.median([r["s"] for r in rs])),
                "downgraded_rate": float(np.mean([r["downgraded"] for r in rs]))}
        certify = rate(rs, (bc.SURVIVES, bc.UNDERPOWERED))
        exposure = rate(rs, (cx.MARKET, cx.MARKET_LIKE))
        summ.update({"certify_rate": certify, "exposure_rate": exposure})
        if kind == "book" and name == "S":
            ok = rate(rs, (bc.SURVIVES,)) >= 0.90 and exposure <= 0.05
        elif kind == "book" and name == "T":
            err = float(np.median([abs(r["s"] - r["true_s"]) for r in rs]))
            summ["median_abs_s_error"] = err
            ok = (1 - certify) >= 0.95 and err <= 0.10
        elif kind == "book":
            ok = certify <= 0.10
            if name == "C":
                summ["median_abs_s"] = float(np.median([abs(r["s"]) for r in rs]))
                summ["may_establish_exposure"] = summ["median_abs_s"] <= 0.10
        elif name == "alpha":
            ok = exposure <= 0.05
        else:
            ok = certify <= 0.10
        summ["passed"] = bool(ok)
        out[f"{kind}:{name}"] = summ
        passed[f"{kind}:{name}"] = bool(ok)
    core = all(passed[f"book:{b}"] for b in ("S", "T", "C"))
    product = passed["product:alpha"] and passed["product:convex"]
    failed_shapes = [b for b in CONVEX_BOOKS if not passed[f"book:{b}"]]
    return {"books": out, "core_passed": core, "product_passed": product,
            "held_out_shapes_failed": [b for b in failed_shapes if b != "C"],
            "may_establish_exposure": out["book:C"].get("may_establish_exposure", False)}


def cmd_calibrate(args) -> int:
    tasks = [("book", b, s) for b in BOOKS for s in SEEDS] + \
            [("product", k, s) for k in ("alpha", "convex") for s in PRODUCT_SEEDS]
    with Pool(args.workers) as pool:
        rows = pool.map(run_one, tasks, chunksize=4)
    out = {"schema_version": 1, "vintage": pd.Timestamp.today().date().isoformat(), "protocol": PROTOCOL,
           "seeds": [SEEDS.start, SEEDS.stop - 1], "product_seeds": [PRODUCT_SEEDS.start, PRODUCT_SEEDS.stop - 1],
           "bootstrap_reps": CAL_REPS, "summary": summarise(rows), "rows": rows}
    text = json.dumps(out, indent=1, sort_keys=True, default=float) + "\n"
    Path(args.json).write_text(text, encoding="utf-8")
    print(f"wrote {args.json} (sha256 {hashlib.sha256(text.encode()).hexdigest()})")
    s = out["summary"]
    for k, v in s["books"].items():
        print(f"{k:16} {'PASS' if v['passed'] else 'FAIL'}  certify {v['certify_rate']:.2f}  exposure "
              f"{v['exposure_rate']:.2f}  median s {v['median_s']:+.2f}  {v['verdicts']}")
    print({k: v for k, v in s.items() if k != "books"})
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("calibrate")
    c.add_argument("--workers", type=int, default=16)
    c.add_argument("--json", default=str(CAL_OUT))
    c.set_defaults(fn=cmd_calibrate)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
