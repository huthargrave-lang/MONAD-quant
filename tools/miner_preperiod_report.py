#!/usr/bin/env python3
"""
MONAD Quant — the verdict, gates and diagnostics of the 1984-2005 miner/metal tilt test,
exactly as frozen in docs/research/MINER_TILT_PREPERIOD.md.

Run after ``tools/domain_search.py`` has recorded the four domains (miner_preperiod_a,
miner_preperiod_b, placebo_preperiod, miner_preperiod_lags). This tool:

  * screens both segments' data (NOT RUN on any failure);
  * records the counted 2x and 0.5x cost runs (``domain_search.stress``) and a counted
    diagnostic re-run of the A and placebo points for their per-asset weights;
  * computes the VERDICT on the concatenation of the A and B active series (one SPA,
    gate rules v2 with m = 5), and every pre-stated gate: 2x costs, the lag ladder, the
    noise bound, the noise-only placebo (synthetic panels through the exact evaluator,
    the one uncounted step, sanctioned in src/strategy/counted.py), the placebo's timing
    part, drop-one-era;
  * reports the diagnostics (static vs timing split, mean tilt and dividend bounds,
    1984-1995, top-5-day share, a Stouffer combination labelled "includes seen data"
    with weight 0).

    venv/bin/python tools/miner_preperiod_report.py --snapshot-a <sha> --snapshot-b <sha> \\
        --world-bank <path to the Pink Sheet xlsx> --json <out>
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import domain_search  # noqa: E402
from src.research import allocation_stats as stats  # noqa: E402
from src.research import commodity_classes as cc  # noqa: E402
from src.research import daily_data  # noqa: E402
from src.research import miner_preperiod as mp  # noqa: E402
from src.research import trials  # noqa: E402
from src.research.backtest_trials import family_members  # noqa: E402
from src.research.daily_domains import DOMAINS, Context  # noqa: E402
from src.research.daily_strategy import evaluate_daily  # noqa: E402
from src.research.daily_trials import daily_spec, family_name, record_daily, stored_returns  # noqa: E402

PRODUCER = "tools/miner_preperiod_report.py"
A, B, PLACEBO, LAGS = "miner_preperiod_a", "miner_preperiod_b", "placebo_preperiod", "miner_preperiod_lags"
M, ALPHA = 5, 0.05
NOISE_RHOS = (0.5, 0.86, 0.95)
NOISE_SIMS = 1000
NOISE_SEED = 20261009
NW_LAG = 20
DIVIDEND_YIELD = {mp.MINER: 0.03, mp.PLACEBO: 0.035}
#: The rule's three 2016-2026 tests (seen data), for the weight-0 Stouffer diagnostic.
SEEN = (("miner_metal_ratio", "6f18a1b701ffd141cc54f9413c822b8f7698a0ce597be63f5fb7fd6e1506ae5b"),
        ("silver_miner_ratio", "33bafcfd05e348e11eb5a1e9c719c1365d87530670348e34211cad7e116fd035"),
        ("junior_miner_ratio", "33bafcfd05e348e11eb5a1e9c719c1365d87530670348e34211cad7e116fd035"))


# ── ledger reads ─────────────────────────────────────────────────────────────
def recorded_active(domain_name: str, snapshot: str, *, multiple: float = 1.0) -> dict:
    """{label: active series} of a domain's latest recorded points at a cost multiple,
    against its benchmark at the same multiple."""
    d = DOMAINS[domain_name]
    ctx = d.load({"snapshot": snapshot})
    start, end = d.window(ctx)
    data = ctx.data_spec(start, end)
    recs = list(trials.iter_trials())
    fam = domain_search.latest(family_members(recs, family_name(d.name)), data, start, end,
                               cost_multiple=multiple)
    ref = domain_search.latest(family_members(recs, family_name(d.name, reference=True)), data, start, end,
                               cost_multiple=multiple)
    if not fam or len(ref) != 1:
        raise SystemExit(f"{domain_name}: nothing recorded at cost x{multiple:g} on {snapshot[:8]}")
    (ref_rec,) = ref.values()
    series = trials.load_returns(list(fam.values()) + [ref_rec])
    ref_r = stored_returns(series[ref_rec.key])
    return {lab: stats.active_series(stored_returns(series[r.key]), ref_r) for lab, r in fam.items()}


def only(d: dict) -> pd.Series:
    (s,) = d.values()
    return s


def sharpe_t(x: pd.Series) -> tuple[float, float]:
    sh = stats.annualized_sharpe(x)
    return sh, sh * math.sqrt(len(x) / 252)


def nw_mean_t(x: np.ndarray, lag: int = NW_LAG) -> float:
    u = x - x.mean()
    lrv = u @ u / len(u)
    for k in range(1, lag + 1):
        lrv += 2 * (1 - k / (lag + 1)) * (u[k:] @ u[:-k]) / len(u)
    return float(x.mean() / math.sqrt(lrv / len(u))) if lrv > 0 else float("nan")


# ── the counted diagnostic re-run: per-asset weights ─────────────────────────
def weights_run(domain_name: str, snapshot: str):
    d = DOMAINS[domain_name]
    ctx = d.load({"snapshot": snapshot})
    start, end = d.window(ctx)
    data = ctx.data_spec(start, end)
    (point,) = d.grid()
    with trials.open_run(producer=PRODUCER, family=family_name(d.name),
                         context={**data, "role": "diagnostic: per-asset weights"}) as run:
        t = run.begin(params=daily_spec(point, domain=d.name), data=data)
        res = evaluate_daily(d.decide(ctx, point), ctx.snap, start=start, end=end, tiers=d.tiers(ctx))
        record_daily(t, res)
    return ctx.snap, point, res


def timing_split(snap, point, res) -> dict:
    """active_t ~ (w_{t-1} - 0.5)(rA - rB) = static (w_bar - 0.5)(rA - rB) + timing
    (w_{t-1} - w_bar)(rA - rB), w the first leg's share of the invested book."""
    p = point["params"]
    a, b = p["miner"], p["metal"]
    rets = snap.returns()
    tot = ((1 + rets.night) * (1 + rets.day) - 1)[[a, b]].reindex(res.weights.index)
    w = res.weights[a] / res.weights[[a, b]].sum(axis=1)
    held = w.shift(1).dropna()
    spread = (tot[a] - tot[b]).reindex(held.index)
    wbar = float(held.mean())
    static = (wbar - 0.5) * spread
    timing = (held - wbar) * spread
    return {"mean_first_leg_weight": wbar, "mean_tilt": wbar - 0.5,
            "static_ann": float(static.mean() * 252), "timing_ann": float(timing.mean() * 252),
            "timing_nw_t": nw_mean_t(timing.to_numpy()),
            "dividend_bias_bound_ann": abs(wbar - 0.5) * DIVIDEND_YIELD.get(a, 0.03)}


# ── noise ────────────────────────────────────────────────────────────────────
def noise_variance(log_price: pd.Series) -> float:
    """Variance of iid-like measurement noise in a log price, from the variance ratio:
    [Var(d1) - Var(d21)/21] x 21/40 (zero for a pure random walk); floored at 0."""
    x = log_price.dropna()
    v1 = x.diff().var()
    v21 = x.diff(21).var()
    return max(0.0, float((v1 - v21 / 21) * 21 / 40))


_SIM = {}


def _init_sim(payload):
    _SIM.update(payload)


def _one_sim(args) -> float:
    """One synthetic panel: real gold, real stale-print calendar, a random-walk ratio at
    the realised volatility plus AR(1) noise; the exact evaluator, uncounted (it measures
    no instrument). Returns the tilt's active Sharpe."""
    from src.strategy.counted import uncounted
    seed, rho = args
    s = _SIM
    rng = np.random.default_rng(seed)
    n = len(s["gold"])
    rw = np.cumsum(rng.normal(0.0, s["rw_sd"], n))
    eps = rng.normal(0.0, s["noise_sd"] * math.sqrt(1 - rho ** 2), n)
    noise = np.empty(n)
    noise[0] = rng.normal(0.0, s["noise_sd"])
    for i in range(1, n):
        noise[i] = rho * noise[i - 1] + eps[i]
    miner = s["gold"] * np.exp(rw + noise)
    stale = s["miner_stale"]
    for i in np.flatnonzero(stale):
        if i > 0:
            miner[i] = miner[i - 1]
    close = pd.DataFrame({s["calendar"]: s["calendar_close"], s["miner"]: miner, s["metal"]: s["gold"]},
                         index=s["dates"])
    snap = daily_data.Snapshot(sha=f"noise-{seed}", dates=s["dates"], assets=tuple(close.columns),
                               open=close.shift(1).fillna(close.iloc[0]), close=close, dist=close * 0.0,
                               dtb3=s["dtb3"], manifest=s["manifest"])
    with uncounted("noise-only placebo: synthetic ratio panels, no instrument measured"):
        a = evaluate_daily(cc.decide_ratio(snap, s["point"]), snap, start=s["start"], end=s["end"],
                           tiers=s["tiers"]).returns
        b = evaluate_daily(cc.decide_ratio(snap, s["reference"]), snap, start=s["start"], end=s["end"],
                           tiers=s["tiers"]).returns
    return stats.annualized_sharpe(a - b)


def noise_placebo(snap, domain_name: str, noise_sd: float, *, sims: int = NOISE_SIMS,
                  rhos=NOISE_RHOS, workers: int | None = None) -> dict:
    d = DOMAINS[domain_name]
    (point,) = d.grid()
    p = point["params"]
    ctx = Context(snap=snap)
    start, end = d.window(ctx)
    gold = snap.close[p["metal"]].to_numpy()
    lr = np.log(snap.close[p["miner"]] / snap.close[p["metal"]])
    payload = {"gold": gold, "rw_sd": float(lr.diff().std()), "noise_sd": noise_sd,
               "miner_stale": snap.close[p["miner"]].eq(snap.close[p["miner"]].shift(1)).to_numpy(),
               "calendar": mp.CALENDAR, "calendar_close": snap.close[mp.CALENDAR].to_numpy(),
               "miner": p["miner"], "metal": p["metal"], "dates": snap.dates, "dtb3": snap.dtb3,
               "manifest": snap.manifest, "point": point, "reference": d.reference,
               "tiers": d.tiers(ctx), "start": start, "end": end}
    out = {}
    with ProcessPoolExecutor(max_workers=workers or max(1, (os.cpu_count() or 2) - 1),
                             initializer=_init_sim, initargs=(payload,)) as pool:
        for rho in rhos:
            seeds = [(NOISE_SEED + int(rho * 1000) * 100000 + k, rho) for k in range(sims)]
            sh = np.array(list(pool.map(_one_sim, seeds, chunksize=8)))
            out[str(rho)] = {"p95": float(np.quantile(sh, 0.95)), "mean": float(sh.mean()), "sims": sims}
    return out


# ── the verdict ──────────────────────────────────────────────────────────────
def eras_of(series: pd.Series, eras) -> list:
    return [e["active_sharpe"] for e in stats.era_sharpes(series, eras)]


def verdict(combined: pd.Series, *, stress2: pd.Series, lag1: float, lag6: float, noise_ok: bool,
            noise_bound_ok: bool, drop_one: list, placebo_blocks: bool) -> dict:
    sh, t = sharpe_t(combined)
    gate = stats.familywise_gate({"tilt": combined}, "tilt", m=M, alpha=ALPHA)
    worst = gate.worst_p
    sh2 = stats.annualized_sharpe(stress2)
    lag_ok = lag6 > 0 and lag6 >= 0.5 * lag1
    base = sh > 0 and t > 1.0 and worst < ALPHA
    corroborates = base and sh2 > 0 and lag_ok and noise_bound_ok and noise_ok
    contradicts = sh <= 0
    promoted = corroborates and gate.p_gate <= ALPHA and all(x > 0 for x in drop_one) and not placebo_blocks
    clean_fail = contradicts or lag6 <= 0 or not noise_ok
    return {"sharpe": sh, "t": t, "worst_block_p": worst, "p_gate": gate.p_gate, "m": M,
            "blocks": gate.blocks, "sharpe_2x": sh2, "lag_ladder_ok": lag_ok, "noise_bound_ok": noise_bound_ok,
            "noise_placebo_ok": noise_ok, "drop_one_era": drop_one, "placebo_blocks": placebo_blocks,
            "verdict": "corroborates" if corroborates else "contradicts" if contradicts else "uninformative",
            "promoted": promoted, "clean_fail_closes_lead": clean_fail}


def stouffer(z_and_years) -> float:
    w = np.array([math.sqrt(y) for _, y in z_and_years])
    z = np.array([z for z, _ in z_and_years])
    return float((w * z).sum() / math.sqrt((w ** 2).sum()))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot-a", required=True)
    ap.add_argument("--snapshot-b", required=True)
    ap.add_argument("--world-bank", required=True, help="the Pink Sheet monthly xlsx (validation only)")
    ap.add_argument("--json", required=True)
    ap.add_argument("--sims", type=int, default=NOISE_SIMS)
    args = ap.parse_args(argv)
    out = {"schema_version": 1, "vintage": mp.today(), "protocol": "docs/research/MINER_TILT_PREPERIOD.md"}

    # Screens.
    wb_bytes = Path(args.world_bank).read_bytes()
    wb = mp.world_bank_gold(wb_bytes)
    out["world_bank_payload_sha256"] = mp.payload_sha256(wb_bytes)
    reasons = []
    for seg_name, sha, dom in (("A", args.snapshot_a, A), ("B", args.snapshot_b, B)):
        d = DOMAINS[dom]
        ctx = d.load({"snapshot": sha})
        window = d.window(ctx)
        funds = mp.fetch_funds(str(window[0].date()), str((window[1] + pd.Timedelta(days=1)).date()))
        scr = mp.screens(ctx.snap, mp.SEGMENTS[seg_name], funds=funds, wb=wb, window=window)
        scr["fund_panel"] = sorted(funds.columns)
        out[f"screens_{seg_name}"] = scr
        reasons += [f"{seg_name}: {r}" for r in scr["reasons"]]
    if reasons:
        out["verdict"] = {"verdict": "NOT RUN", "reasons": reasons}
        Path(args.json).write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
        print(json.dumps(out["verdict"], indent=1))
        return 0

    # Recorded series and the counted cost runs.
    act_a, act_b = only(recorded_active(A, args.snapshot_a)), only(recorded_active(B, args.snapshot_b))
    for dom, sha in ((A, args.snapshot_a), (B, args.snapshot_b)):
        d = DOMAINS[dom]
        ctx = d.load({"snapshot": sha})
        for mult in (2.0, 0.5):
            domain_search.stress(d, ctx, "v1", multiple=mult, producer=PRODUCER)
    s2 = pd.concat([only(recorded_active(A, args.snapshot_a, multiple=2.0)),
                    only(recorded_active(B, args.snapshot_b, multiple=2.0))])
    s05 = pd.concat([only(recorded_active(A, args.snapshot_a, multiple=0.5)),
                     only(recorded_active(B, args.snapshot_b, multiple=0.5))])
    combined = pd.concat([act_a, act_b])
    if combined.index.has_duplicates:
        raise SystemExit("segments overlap")

    # Lag ladder (segment A).
    lags = recorded_active(LAGS, args.snapshot_a)
    lag_sh = {int(json.loads(k.split(" ", 1)[1])["lag"]): stats.annualized_sharpe(v) for k, v in lags.items()}
    lag1 = stats.annualized_sharpe(act_a)

    # Noise (segment A).
    ctx_a = DOMAINS[A].load({"snapshot": args.snapshot_a})
    snap_a = ctx_a.snap
    win_a = DOMAINS[A].window(ctx_a)
    lx = np.log(snap_a.close[mp.MINER]).loc[win_a[0]:win_a[1]]
    lg = np.log(snap_a.close[mp.GOLD_FFM]).loc[win_a[0]:win_a[1]]
    lr = lx - lg
    s_bar = float(lr.rolling(cc.Z_WINDOW).std().mean())
    var_ratio = noise_variance(lr)
    bound = 3 * 2.5 * var_ratio / s_bar
    active_ann_a = float(act_a.mean() * 252)
    noise = noise_placebo(snap_a, A, math.sqrt(var_ratio), sims=args.sims)
    worst_p95 = max(v["p95"] for v in noise.values())
    noise_ok = lag1 > worst_p95

    # Weights: timing split for the tilt and the placebo.
    split_a = timing_split(*weights_run(A, args.snapshot_a))
    split_p = timing_split(*weights_run(PLACEBO, args.snapshot_a))
    split_b = timing_split(*weights_run(B, args.snapshot_b))
    placebo_blocks = split_p["timing_nw_t"] > 1 and split_p["timing_nw_t"] >= split_a["timing_nw_t"]

    eras = eras_of(act_a, DOMAINS[A].eras) + [stats.annualized_sharpe(act_b)]
    drop_one = []
    era_masks = [((act_a.index >= (act_a.index[0] if lo == "start" else pd.Timestamp(lo))) &
                  (act_a.index <= (act_a.index[-1] if hi == "end" else pd.Timestamp(hi))))
                 for lo, hi in DOMAINS[A].eras]
    for mask in era_masks:
        drop_one.append(stats.annualized_sharpe(pd.concat([act_a[~mask], act_b])))
    drop_one.append(stats.annualized_sharpe(act_a))

    out["verdict"] = verdict(combined, stress2=s2, lag1=lag1, lag6=lag_sh.get(6, float("nan")),
                             noise_ok=noise_ok, noise_bound_ok=active_ann_a >= bound,
                             drop_one=drop_one, placebo_blocks=placebo_blocks)
    top5 = combined.sort_values(ascending=False).iloc[:5].sum() / combined.sum() if combined.sum() > 0 else None
    seen = []
    for dom, sha in SEEN:
        s = only(recorded_active(dom, sha))
        seen.append((sharpe_t(s)[1], len(s) / 252))
    out["diagnostics"] = {
        "segment_a": dict(zip(("sharpe", "t"), sharpe_t(act_a))), "segment_b": dict(zip(("sharpe", "t"), sharpe_t(act_b))),
        "eras_a1_a2_a3_b": eras, "active_ann_combined": float(combined.mean() * 252),
        "sharpe_cost_0_5x": stats.annualized_sharpe(s05), "lag_sharpes": {1: lag1, **lag_sh},
        "noise": {"ratio_noise_variance": var_ratio, "s_bar": s_bar, "bound_ann": bound,
                  "active_ann_a": active_ann_a, "gold_noise_variance": noise_variance(lg),
                  "xau_noise_variance": noise_variance(lx), "placebo": noise, "worst_p95": worst_p95},
        "timing_split": {"A": split_a, "placebo": split_p, "B": split_b},
        "sharpe_1984_1995": stats.annualized_sharpe(act_a.loc[:"1995-12-31"]),
        "top5_day_share": top5,
        "stouffer_includes_seen_data_weight_0": stouffer([(out["verdict"]["t"], len(combined) / 252)] + seen),
    }
    Path(args.json).write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(json.dumps({"verdict": out["verdict"], "diagnostics": out["diagnostics"]}, indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
