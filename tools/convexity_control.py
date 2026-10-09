"""
convexity_control — the convexity-robust control (docs/research/CONVEXITY_CONTROL_PROTOCOL.md,
frozen first). Calibration on synthetic books with known answers comes first; market data
runs only for what the calibration passes.

  venv/bin/python tools/convexity_control.py calibrate [--workers 16]
      books S, T, C, Cglob, Cday, Cmon, Cdyn on fresh seeds 1000-1099 (bootstrap B 199), and
      the CEFS-scale pure-alpha and pure-convex books on seeds 2000-2199; writes
      docs/research/data/convexity_calibration.json.
  venv/bin/python tools/convexity_control.py run --acknowledge-live H404701 H404702
      only if the calibration's core books passed: H404702 (exact replay, every check),
      its two planted positive controls, and the F366204 tilt (reported); the products only
      if the product-scale calibration passed. Writes docs/research/data/convexity_control.json.
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


# ── market data (only what the calibration passed) ───────────────────────────
RUN_OUT = REPO / "docs/research/data/convexity_control.json"
MARKET_REPS = 999
PLANT_SHARE = 0.75


def _planted(blocks_in: dict, form: str) -> dict:
    """The candidate's own data with a convex payoff injected into its overweights, scaled
    to its raw active: 'static' (every asset ever overweighted carries it always) or
    'conditional' (only while overweighted at the block's start)."""
    grid, delta, R, cat_of, elig = (blocks_in[k] for k in ("grid", "delta", "assets", "category", "elig"))
    sessions = grid.index
    blk = grid.to_numpy()
    Fcat = blocks_in["factor"]
    Kd = bc.call_payoff_daily(Fcat, grid).reindex(sessions).fillna(0.0)
    D = delta.reindex(index=sessions, columns=R.columns).fillna(0.0)
    first = np.r_[True, blk[1:] != blk[:-1]]
    d_start = pd.DataFrame(D.to_numpy()[np.flatnonzero(first)][blk], index=sessions, columns=R.columns)
    sample = grid >= MIN_BLOCKS
    if form == "static":
        carriers = pd.DataFrame(np.repeat(((D[sample] > 0).any(axis=0)).to_numpy()[None, :], len(sessions), axis=0),
                                index=sessions, columns=R.columns)
    else:
        carriers = d_start > 0
    unit = Kd.where(carriers, 0.0)
    unit_active = (D * unit).sum(axis=1)
    g = float(blocks_in["active"].reindex(sessions)[sample].mean()) / float(unit_active[sample].mean())
    extra = g * unit
    R2 = R.copy()
    R2.loc[sessions] = R.loc[sessions] + extra
    bench_w = blocks_in["bench_weights"].reindex(index=sessions, columns=R.columns).fillna(0.0)
    B2 = blocks_in["bench"].copy()
    B2.loc[sessions] = blocks_in["bench"].reindex(sessions) + (bench_w * extra).sum(axis=1)
    from beta_timing_control import category_factor
    F2 = category_factor(R2, list(R.columns), elig, cat_of)
    active2 = blocks_in["active"].copy()
    active2.loc[sessions] = blocks_in["active"].reindex(sessions) + (D * extra).sum(axis=1)
    # a mean of DAILY values annualises by 252 (bc.ANN is per 5-session block)
    planted_mean = float((D * extra).sum(axis=1)[sample].mean()) * 252.0
    return {"active": active2, "assets": R2, "factor": F2, "bench": B2, "planted_ann": planted_mean}


def _h404702(recs, acknowledged) -> dict:
    import beta_timing_control as btc
    pair = btc.replay_pair("H404702", recs, acknowledged=acknowledged)
    ctx, tot, recorded = pair["ctx"], pair["tot"], pair["recorded"]
    cand, bench = pair["cand"], pair["bench"]
    funds = [a for a in ctx.snap.assets if a in ctx.panel.category]
    start = btc.exposure_start(cand, bench)
    grid = bc.block_grid(cand.returns.index, start)
    delta = (cand.weights[funds] - bench.weights[funds]).shift(1).fillna(0.0)
    bench_prev = bench.weights[funds].shift(1).fillna(0.0)
    elig = bench_prev > 0
    Fcat = btc.category_factor(tot, funds, elig, ctx.panel.category)
    b_rec = recorded[btc.PAIRS["H404702"]["bench"]]
    active = recorded[btc.PAIRS["H404702"]["cand"]] - b_rec
    blocks = cx.build_blocks(active, delta, tot[funds], Fcat, b_rec, grid)
    out = {"checks": pair["checks"], "exposure_start": str(start.date()),
           "control": cx.control(blocks, min_blocks=MIN_BLOCKS, window=WINDOW, minimum=MINIMUM, reps=MARKET_REPS)}
    base_E = cx.control(blocks, min_blocks=MIN_BLOCKS, window=WINDOW, minimum=MINIMUM, reps=0)["explained_ann"]
    inputs = {"grid": grid, "delta": delta, "assets": tot[funds], "category": ctx.panel.category, "elig": elig,
              "factor": Fcat, "active": active, "bench": b_rec, "bench_weights": bench_prev}
    planted = {}
    for form in ("static", "conditional"):
        pl = _planted(inputs, form)
        pb = cx.build_blocks(pl["active"], delta, pl["assets"], pl["factor"], pl["bench"], grid)
        pc = cx.control(pb, min_blocks=MIN_BLOCKS, window=WINDOW, minimum=MINIMUM, reps=0)
        share = (pc["explained_ann"] - base_E) / pl["planted_ann"] if pl["planted_ann"] else float("nan")
        planted[form] = {"planted_ann": pl["planted_ann"], "explained_ann": pc["explained_ann"],
                         "base_explained_ann": base_E, "attributed_share": share, "passed": share >= PLANT_SHARE,
                         "verdict_with_plant": pc["verdict"]}
    out["planted"] = planted
    return out


def _f366204(recs) -> dict:
    """The F366204 tilt, reported only (it has no known answer)."""
    import beta_timing_control as btc
    name = "positive_control_F366204"
    pair = btc.replay_pair(name, recs, acknowledged=[])
    ctx, tot, recorded = pair["ctx"], pair["tot"], pair["recorded"]
    cand, bench = pair["cand"], pair["bench"]
    etf_of = {f: m["etf"] for f, m in ctx.panel.matched.items()}
    universe = set(etf_of) | set(etf_of.values())
    held = [a for a in cand.weights.columns
            if a in universe or cand.weights[a].abs().sum() > 0 or bench.weights[a].abs().sum() > 0]
    start = btc.exposure_start(cand, bench)
    grid = bc.block_grid(cand.returns.index, start)
    delta = (cand.weights[held] - bench.weights[held]).shift(1).fillna(0.0)
    b_rec = recorded[btc.PAIRS[name]["bench"]]
    active = recorded[btc.PAIRS[name]["cand"]] - b_rec
    fac = pd.DataFrame({a: tot[etf_of.get(a, a)] for a in held})
    blocks = cx.build_blocks(active, delta, tot[held], fac, b_rec, grid)
    return {"checks": pair["checks"],
            "control": cx.control(blocks, min_blocks=MIN_BLOCKS, window=WINDOW, minimum=MINIMUM, reps=MARKET_REPS)}


def cmd_run(args) -> int:
    import beta_timing_control as btc
    from src.research import trials
    from src.research.daily_domains import DOMAINS
    from src.research.daily_trials import family_name, live_registrations
    if trials.code_state().get("dirty"):
        raise SystemExit("the protocol requires a clean tree: commit first")
    cal = json.loads(Path(args.calibration).read_text(encoding="utf-8"))["summary"]
    out = {"schema_version": 1, "vintage": pd.Timestamp.today().date().isoformat(), "protocol": PROTOCOL,
           "calibration": {k: v for k, v in cal.items() if k != "books"}}
    if not cal["core_passed"]:
        out["verdict"] = "NOT RUN"
        out["reason"] = "the calibration's core books (S, T, C) did not all pass"
    else:
        recs = btc.records()
        dom = DOMAINS["cef_discount"]
        ctx = dom.load(recs[btc.PAIRS["H404702"]["cand"]].spec["data"])
        live = live_registrations(family_name(dom.name))
        before = {h: btc.gate_inputs(h, ctx, dom) for h in live}
        h = _h404702(recs, args.acknowledge_live)
        recs = btc.records()
        f = _f366204(recs)
        after = {hh: btc.gate_inputs(hh, ctx, dom) for hh in live}
        out["gate_invariance"] = {"identical": before == after, "hypotheses": live}
        if before != after:
            raise SystemExit("gate inputs changed across the replays: NOT RUN")
        planted_ok = all(p["passed"] for p in h["planted"].values())
        verdict = h["control"]["verdict"]
        if not planted_ok:
            verdict = bc.INCONCLUSIVE
        if verdict in (cx.MARKET, cx.MARKET_LIKE) and not cal["may_establish_exposure"]:
            verdict = bc.INCONCLUSIVE
        out["H404702"] = {**h, "verdict": verdict,
                          "scope_excludes": cal["held_out_shapes_failed"]}
        out["F366204_tilt_reported"] = f
        out["products"] = ("NOT RUN: the product-scale calibration failed" if not cal["product_passed"]
                           else "run separately")
    text = json.dumps(out, indent=1, sort_keys=True, default=float) + "\n"
    Path(args.json).write_text(text, encoding="utf-8")
    print(f"wrote {args.json} (sha256 {hashlib.sha256(text.encode()).hexdigest()})")
    print(json.dumps({k: (v if k not in ("H404702", "F366204_tilt_reported") else
                          {kk: vv for kk, vv in v.items() if kk != "checks"}) for k, v in out.items()},
                     indent=1, default=float)[:4000])
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("calibrate")
    c.add_argument("--workers", type=int, default=16)
    c.add_argument("--json", default=str(CAL_OUT))
    c.set_defaults(fn=cmd_calibrate)
    r = sub.add_parser("run")
    r.add_argument("--calibration", default=str(CAL_OUT))
    r.add_argument("--acknowledge-live", nargs="*", default=[])
    r.add_argument("--json", default=str(RUN_OUT))
    r.set_defaults(fn=cmd_run)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
