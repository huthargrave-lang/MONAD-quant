#!/usr/bin/env python3
"""
MONAD Quant — the pre-stated diagnostics and registration trigger of the miner/metal tilt
replication (docs/research/MINER_TILT_REPLICATION.md), computed from RECORDED series only.

Reads, from the trial ledger, the latest active series (member minus its 50/50 benchmark)
of the frozen ratio tilt in five domains on one snapshot and window:

  miner_metal_ratio (GDX/GLD, seen), silver_miner_ratio (SIL/SLV, the verdict),
  junior_miner_ratio (GDXJ/GLD), gold_silver_ratio (GLD/SLV), placebo_ratio (IWM/SPY)

and reports the protocol's diagnostics plus whether the registration trigger fires. It
records no trial.

    venv/bin/python tools/miner_tilt_replication.py --snapshot <sha> [--gdx-snapshot <sha>]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import commodity_atlas as ca  # noqa: E402
from src.research import allocation_stats as stats  # noqa: E402
from src.research import significance as sig  # noqa: E402
from src.research import trials  # noqa: E402
from src.research.backtest_trials import family_members  # noqa: E402
from src.research.daily_domains import DOMAINS  # noqa: E402
from src.research.daily_trials import family_name, stored_returns  # noqa: E402

VERDICT = "silver_miner_ratio"
SEEN = "miner_metal_ratio"
OTHERS = ("junior_miner_ratio", "gold_silver_ratio", "placebo_ratio")
BLOCK, BOOT, SEED = 63, 5000, 0
PRIOR = 2
ALPHA = 0.05


def active_series(domain_name: str, snapshot: str, *, records=None) -> pd.Series:
    """The latest ok search trial's active series against the latest benchmark run."""
    import domain_search as ds
    d = DOMAINS[domain_name]
    ctx = d.load({"snapshot": snapshot})
    start, end = d.window(ctx)
    data = ctx.data_spec(start, end)
    records = list(trials.iter_trials()) if records is None else records
    fam = ds.latest(family_members(records, family_name(d.name)), data, start, end)
    ref = ds.latest(family_members(records, family_name(d.name, reference=True)), data, start, end)
    if len(fam) != 1 or len(ref) != 1:
        raise SystemExit(f"{domain_name}: need one search point and one benchmark on {snapshot[:8]}")
    (rec,), (ref_rec,) = fam.values(), ref.values()
    s = trials.load_returns([rec, ref_rec])
    return stats.active_series(stored_returns(s[rec.key]), stored_returns(s[ref_rec.key]))


def sharpe_t(x: pd.Series) -> tuple[float, float]:
    sh = stats.annualized_sharpe(x)
    return sh, sh * math.sqrt(len(x) / 252)


def nw_mean_t(x: np.ndarray, lag: int) -> float:
    """t of the mean of ``x`` with a Newey-West (Bartlett) long-run variance."""
    u = x - x.mean()
    lrv = u @ u / len(u)
    for k in range(1, lag + 1):
        lrv += 2 * (1 - k / (lag + 1)) * (u[k:] @ u[:-k]) / len(u)
    return float(x.mean() / math.sqrt(lrv / len(u)))


def joint_ci(frame: pd.DataFrame, weights: dict) -> dict:
    """Sharpe of a weighted average of active series with a stationary-bootstrap 95% CI,
    the same resampled sessions for every series."""
    w = np.array([weights[c] for c in frame.columns])
    x = frame.to_numpy() @ w
    idx = sig.stationary_bootstrap_indices(len(x), BLOCK, BOOT, np.random.default_rng(SEED))
    boot = x[idx]
    sh = boot.mean(axis=1) / boot.std(axis=1, ddof=1) * math.sqrt(252)
    lo, hi = np.quantile(sh, [0.025, 0.975])
    point = x.mean() / x.std(ddof=1) * math.sqrt(252)
    return {"sharpe": float(point), "ci95": [float(lo), float(hi)]}


def evaluate(series: dict, eras, spa_worst_p: float) -> dict:
    v = series[VERDICT]
    frame = pd.concat(series, axis=1).dropna()
    sh, t = sharpe_t(v)
    era_sh = [e["active_sharpe"] for e in stats.era_sharpes(v, eras)]
    drop_one = []
    for i, (a, b) in enumerate(eras):
        keep = pd.Series(True, index=v.index)
        lo = v.index[0] if a == "start" else pd.Timestamp(a)
        hi = v.index[-1] if b == "end" else pd.Timestamp(b)
        keep[(v.index >= lo) & (v.index <= hi)] = False
        drop_one.append(stats.annualized_sharpe(v[keep]))
    # Contamination: SIL/SLV active on GDX/GLD active, and on the gold/silver tilt.
    regs = {}
    for other in (SEEN, "gold_silver_ratio"):
        y, x = frame[VERDICT].to_numpy(), frame[other].to_numpy()
        slope, t_slope = ca.newey_west_t(y, x, 20)
        A = np.column_stack([np.ones(len(y)), x])
        b, *_ = np.linalg.lstsq(A, y, rcond=None)
        resid = y - A @ b
        r2 = 1 - resid.var() / y.var()
        alpha = y - slope * x
        regs[other] = {"beta": slope, "beta_nw_t": t_slope, "r2": float(r2),
                       "alpha_ann": float(alpha.mean() * 252), "alpha_nw_t": nw_mean_t(alpha, 20)}
    pools = {"pool_unseen": joint_ci(frame[[VERDICT, "junior_miner_ratio"]],
                                     {VERDICT: 0.5, "junior_miner_ratio": 0.5}),
             "pool_all (includes seen data)": joint_ci(frame[[VERDICT, SEEN, "junior_miner_ratio"]],
                                                       {VERDICT: 0.5, SEEN: 0.25, "junior_miner_ratio": 0.25})}
    others = {k: dict(zip(("sharpe", "t"), sharpe_t(series[k]))) for k in (SEEN, *OTHERS)}
    corr = frame.corr()[VERDICT].to_dict()
    trigger = {"sharpe_positive": sh > 0, "t_above_1": t > 1.0, "spa_below_5pct": spa_worst_p < ALPHA,
               "p_times_3_below_5pct": spa_worst_p * (1 + PRIOR) <= ALPHA,
               "alpha_vs_gdx_positive": regs[SEEN]["alpha_ann"] > 0,
               "drop_any_era_positive": all(x > 0 for x in drop_one)}
    return {"verdict_pair": {"sharpe": sh, "t": t, "eras": era_sh, "drop_one_era": drop_one,
                             "spa_worst_p": spa_worst_p},
            "contamination": regs, "pools": pools, "others": others, "corr_with_verdict": corr,
            "trigger": trigger, "register": all(trigger.values())}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot", required=True, help="the replication snapshot")
    ap.add_argument("--gdx-snapshot", required=True, help="the snapshot GDX/GLD was recorded on")
    ap.add_argument("--spa-worst-p", type=float, required=True,
                    help="silver_miner_ratio's worst-block SPA p from its domain report")
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    records = list(trials.iter_trials())
    series = {SEEN: active_series(SEEN, args.gdx_snapshot, records=records)}
    for name in (VERDICT, *OTHERS):
        series[name] = active_series(name, args.snapshot, records=records)
    out = evaluate(series, DOMAINS[VERDICT].eras, args.spa_worst_p)
    text = json.dumps(out, indent=1, default=float)
    if args.json:
        Path(args.json).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
