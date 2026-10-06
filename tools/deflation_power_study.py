"""
deflation_power_study — how the admission gate's two multiple-testing stages behave on
synthetic families: the active-series Deflated Sharpe (allocation_stats.deflate_active)
and Hansen's SPA (significance.superior_predictive_ability).

Evidence for the open deflation-scope question (docs/research/DEFLATION_RULE_QUESTION.md).
Each family is one idea (4 correlated variants, correlation ~0.64, at a chosen true active
Sharpe) plus some UNRELATED null ideas, over 20 years of daily active returns. The best
variant of the real idea is the candidate. The table reports how often each stage passes it
(DSR >= 0.95; SPA adjusted p <= 0.05). It evaluates no strategy and records no trial.

  venv/bin/python tools/deflation_power_study.py [--reps 60]
"""
from __future__ import annotations

import argparse
import math
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.research import allocation_stats as stats  # noqa: E402
from src.research import significance as sig  # noqa: E402

CALENDAR = pd.bdate_range("2004-01-02", periods=252 * 20)
VARIANTS = 4
PRIOR = 4


def family(rng: np.random.Generator, true_sharpe: float, n_nulls: int) -> dict:
    t = len(CALENDAR)
    base = rng.normal(0, 1, t)
    out = {}
    for v in range(VARIANTS):
        e = 0.8 * base + 0.6 * rng.normal(0, 1, t)
        out[f"real{v}"] = pd.Series((e / e.std() + true_sharpe / math.sqrt(252)) * 0.01, index=CALENDAR)
    for j in range(n_nulls):
        out[f"null{j}"] = pd.Series(rng.normal(0, 0.01, t), index=CALENDAR)
    return out


def study(reps: int) -> list[dict]:
    rows = []
    for true_s in (0.0, 0.6, 1.0):
        for n_nulls in (0, 2, 6):
            dsr = spa = 0
            for r in range(reps):
                rng = np.random.default_rng(1000 * r + int(true_s * 10) + n_nulls)
                fam = family(rng, true_s, n_nulls)
                best = max((k for k in fam if k.startswith("real")), key=lambda k: fam[k].mean())
                dsr += stats.deflate_active(fam, best, calendar=CALENDAR, prior_trials=PRIOR).dsr >= 0.95
                res = sig.superior_predictive_ability(pd.DataFrame(fam).to_numpy(), mean_block=20,
                                                      n_boot=300, seed=r)
                spa += res.adjusted_pvalues[list(fam).index(best)] <= 0.05
            rows.append({"true_active_sharpe": true_s, "null_ideas": n_nulls,
                         "dsr_pass": dsr / reps, "spa_pass": spa / reps})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=60)
    args = ap.parse_args(argv)
    print(f"{'true active Sharpe':>18} {'null ideas':>10} {'DSR>=0.95':>10} {'SPA p<=0.05':>12}")
    for r in study(args.reps):
        print(f"{r['true_active_sharpe']:>18.1f} {r['null_ideas']:>10} {r['dsr_pass']:>10.0%} {r['spa_pass']:>12.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
