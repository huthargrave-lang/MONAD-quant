"""
spa_size_study — the measured trigger for gate rules v2 (decision debate 2026-10-06):
size and power of the v2 familywise gate (allocation_stats.familywise_gate) at production
settings, worst of mean blocks 20/63/126 with n_boot >= 1000, on dense daily active
series, including WITHHELD members (the union-bound (1+m) charge at m > 0).

Design. Each family is one idea with 4 correlated variants at a true active Sharpe, plus
unrelated null ideas, plus ``m`` withheld null members the gate cannot see. The candidate
is the best VISIBLE variant. Under the null (true Sharpe 0) any pass is a familywise error
over the whole K + m search. The trigger for switching a profile: the Wilson 95% upper bound
on size <= 0.075 at alpha 0.05 over >= 1000 replications. It evaluates no strategy and
records no trial.

  venv/bin/python tools/spa_size_study.py --reps 1000 --workers 16
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from multiprocessing import Pool

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ALPHA = 0.05
N_BOOT = 1000
TRIGGER_UPPER = 0.075


def wilson_upper(k: int, n: int, z: float = 1.959964) -> float:
    if n == 0:
        return 1.0
    p = k / n
    centre = p + z * z / (2 * n)
    rad = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre + rad) / (1 + z * z / n)


def one(args) -> bool:
    true_s, n_nulls, m, rep = args
    import numpy as np
    import deflation_power_study as dps
    from src.research import allocation_stats as stats

    rng = np.random.default_rng(10_000_000 + 1000 * rep + int(true_s * 10) * 100 + n_nulls * 10 + m)
    fam = dps.family(rng, true_s, n_nulls)
    best = max((k for k in fam if k.startswith("real")), key=lambda k: fam[k].mean())
    g = stats.familywise_gate(fam, best, m=m, alpha=ALPHA, n_boot=N_BOOT, seed=rep)
    return g.p_gate <= ALPHA


def run(reps: int, workers: int, configs) -> list[dict]:
    rows = []
    with Pool(workers) as pool:
        for true_s, n_nulls, m in configs:
            passes = sum(pool.map(one, [(true_s, n_nulls, m, r) for r in range(reps)]))
            rows.append({"true_active_sharpe": true_s, "null_ideas": n_nulls, "withheld_m": m,
                         "reps": reps, "passes": passes, "rate": passes / reps,
                         "wilson_upper": wilson_upper(passes, reps)})
            print(json.dumps(rows[-1]), flush=True)
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=1000)
    ap.add_argument("--power-reps", type=int, default=300)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    size_cfg = [(0.0, n, m) for n in (0, 2, 6) for m in (0, 5, 20)]
    power_cfg = [(s, n, m) for s in (0.6, 1.0) for n in (0, 2, 6) for m in (0, 20)]
    size = run(args.reps, args.workers, size_cfg)
    power = run(args.power_reps, args.workers, power_cfg)
    worst = max(r["wilson_upper"] for r in size)
    print(f"\nworst Wilson upper bound on size: {worst:.4f} (trigger <= {TRIGGER_UPPER}) -> "
          f"{'PASS' if worst <= TRIGGER_UPPER else 'FAIL'}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"alpha": ALPHA, "n_boot": N_BOOT, "size": size, "power": power,
                       "worst_wilson_upper": worst, "trigger": TRIGGER_UPPER}, fh, indent=1)
    return 0 if worst <= TRIGGER_UPPER else 1


if __name__ == "__main__":
    sys.exit(main())
