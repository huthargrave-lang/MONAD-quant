"""
spa_price_size_study — the measured trigger for the PRICE profile under gate rules v2
(decision debate 2026-10-06, docs/research/DEFLATION_RULE_QUESTION.md (iii), (vi)): size
and power of the v2 familywise gate (allocation_stats.familywise_gate) on the sparse daily
mark-to-market active basis that ENGINE_VERSION 3 price trials record
(src/research/mark_to_market.py), at production settings: worst of mean blocks 20/63/126,
n_boot >= 1000, alpha 0.05, about two years of sessions.

Why a second study. The dense study (tools/spa_size_study.py) drew Gaussian daily active
series with no zeros. A price trial's active series is different in exactly the ways that
threaten a bootstrap's size: most sessions are flat, the rest are heavy-tailed leveraged
moves, exposure is serially correlated (a trade held over several closes), and the
benchmark leg (f x the instrument's return) is common to every member.

Design. Each session has an overnight and an intraday instrument move, Student-t (5 df),
scaled like a 3x-levered index (about 1.5% and 2.5%). An *idea* is a stream of entry
signals; its 4 *variants* share the signals and differ in how long they hold (0 to 3
closes), one position at a time. A trade that enters at a session's open earns that
session's intraday move, the full move of each session it is held through, and the
overnight move plus a random share of the intraday move on its exit session. Daily PnL and
close exposure follow mark_to_market's definitions, and active = PnL - f x return.

* Under the null the signals are independent of every future move and the moves have zero
  mean, so every member's active mean is exactly 0 (the boundary of the null). The
  candidate is the best visible variant of the idea; null ideas use other signal rates.
* ``m`` withheld members (points searched off this window) are charged by the union
  bound, as the gate charges them.
* Power: the idea's trades earn an extra ``delta`` on their exit session, sized so the
  best variant's active Sharpe is about the stated value.

The trigger for switching the price profile: the Wilson 95% upper bound on size is
<= 0.075 at alpha 0.05 over >= 1000 replications in every cell. It evaluates no strategy
and records no trial.

  venv/bin/python tools/spa_price_size_study.py --reps 1000 --workers 16 \\
      --json docs/research/spa_price_size_study.json
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

from spa_size_study import ALPHA, N_BOOT, TRIGGER_UPPER, wilson_upper  # noqa: E402

SESSIONS = 504
OVERNIGHT_VOL, INTRADAY_VOL = 0.015, 0.025
HOLDS = (0, 1, 2, 3)                 # closes held by the idea's variants
IDEA_RATE = 0.20                     # entry-signal probability per session
NULL_RATES = (0.05, 0.20, 0.40)      # null ideas cycle through these


GARCH_ALPHA, GARCH_BETA = 0.08, 0.90  # typical daily equity-index persistence


def _moves(rng, n, garch=False):
    """Overnight and intraday moves: Student-t(5), unit variance, scaled. With ``garch``,
    both share a GARCH(1,1) volatility multiplier (unconditional variance 1), so calm and
    turbulent stretches cluster as they do in a leveraged index."""
    import numpy as np

    def t5():
        return rng.standard_t(5, n) / math.sqrt(5 / 3)
    zo, zi = t5(), t5()
    mult = np.ones(n)
    if garch:
        omega = 1.0 - GARCH_ALPHA - GARCH_BETA
        var, prev = 1.0, 0.0
        for t in range(n):
            var = omega + GARCH_ALPHA * prev + GARCH_BETA * var
            mult[t] = math.sqrt(var)
            prev = var * (zo[t] ** 2 + zi[t] ** 2) / 2.0
    return OVERNIGHT_VOL * mult * zo, INTRADAY_VOL * mult * zi


def variant(rng, signals, hold, o, i, delta=0.0):
    """(pnl, exposure) of one variant: enter at the open after each signal session while
    flat, hold ``hold`` closes, exit inside the next session."""
    import numpy as np
    n = len(o)
    pnl, expo = np.zeros(n), np.zeros(n)
    t = 0
    while t < n - 1:
        if not signals[t]:
            t += 1
            continue
        e = t + 1                                    # enter at this session's open
        u = rng.uniform(0.2, 1.0)
        if hold == 0:
            pnl[e] += u * i[e] + delta
            t = e
            continue
        pnl[e] += i[e]
        expo[e] = 1.0
        for k in range(1, hold):
            if e + k >= n:
                break
            pnl[e + k] += o[e + k] + i[e + k]
            expo[e + k] = 1.0
        x = e + hold
        if x < n:
            pnl[x] += o[x] + u * i[x] + delta
        t = x
    return pnl, expo


def family(rng, true_sharpe: float, n_null_ideas: int, sessions: int = SESSIONS,
           garch: bool = False):
    """{label: active series} for one replication, and the candidate label."""
    import numpy as np
    import pandas as pd
    cal = pd.bdate_range("2024-01-02", periods=sessions)
    o, i = _moves(rng, sessions, garch)
    r = o + i
    out = {}

    def add(prefix, signals, delta=0.0):
        for h in HOLDS:
            # the variant's own exit draws come from a stream seeded by the replication
            pnl, expo = variant(np.random.default_rng(rng.integers(1 << 62)), signals, h, o, i, delta)
            out[f"{prefix}h{h}"] = pd.Series(pnl - expo.mean() * r, index=cal)

    sig_idea = rng.random(sessions) < IDEA_RATE
    if true_sharpe > 0:
        # calibrate delta from the null series so the best variant's active Sharpe is
        # about true_sharpe: delta x trades/session = Sharpe/sqrt(252) x sd(active)
        add("probe", sig_idea)
        sd = float(np.mean([out[k].std(ddof=1) for k in out]))
        out.clear()
        trades_per_session = sig_idea.mean() / (1 + np.mean(HOLDS) * sig_idea.mean())
        delta = true_sharpe / math.sqrt(252) * sd / max(trades_per_session, 1e-9)
        add("real", sig_idea, delta)
    else:
        add("real", sig_idea)
    for j in range(n_null_ideas):
        add(f"null{j}", rng.random(sessions) < NULL_RATES[j % len(NULL_RATES)])
    best = max((k for k in out if k.startswith("real")), key=lambda k: out[k].mean())
    return out, best


def one(args) -> bool:
    true_s, n_nulls, m, rep, sessions, *rest = args
    garch = bool(rest and rest[0])
    import numpy as np
    from src.research import allocation_stats as stats

    rng = np.random.default_rng(20_000_000 + 1000 * rep + int(true_s * 10) * 100 + n_nulls * 10 + m)
    fam, best = family(rng, true_s, n_nulls, sessions, garch)
    g = stats.familywise_gate(fam, best, m=m, alpha=ALPHA, n_boot=N_BOOT, seed=rep)
    return g.p_gate <= ALPHA


def run(reps: int, workers: int, configs, sessions: int = SESSIONS,
        garch: bool = False) -> list[dict]:
    rows = []
    with Pool(workers) as pool:
        for true_s, n_nulls, m in configs:
            passes = sum(pool.map(one, [(true_s, n_nulls, m, r, sessions, garch)
                                        for r in range(reps)]))
            rows.append({"true_active_sharpe": true_s, "null_ideas": n_nulls, "withheld_m": m,
                         "sessions": sessions, "garch": garch,
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
    ap.add_argument("--sessions", type=int, default=SESSIONS,
                    help=f"window length for the full grid (default {SESSIONS})")
    ap.add_argument("--garch", action="store_true",
                    help="GARCH(1,1) volatility clustering in the instrument's moves")
    ap.add_argument("--sessions-sweep", type=int, nargs="*", metavar="N",
                    help="only rerun the single-idea, m=0 size cell at these window lengths")
    args = ap.parse_args(argv)
    if args.sessions_sweep:
        rows = [r for n in args.sessions_sweep
                for r in run(args.reps, args.workers, [(0.0, 0, 0)], sessions=n, garch=args.garch)]
        if args.json:
            with open(args.json, "w", encoding="utf-8") as fh:
                json.dump({"alpha": ALPHA, "n_boot": N_BOOT, "cell": "one idea, m=0",
                           "rows": rows}, fh, indent=1)
        return 0
    size_cfg = [(0.0, n, m) for n in (0, 2, 6) for m in (0, 5, 20)]
    power_cfg = [(s, n, m) for s in (0.6, 1.0) for n in (0, 2, 6) for m in (0, 20)]
    size = run(args.reps, args.workers, size_cfg, sessions=args.sessions, garch=args.garch)
    power = run(args.power_reps, args.workers, power_cfg, sessions=args.sessions, garch=args.garch)
    worst = max(r["wilson_upper"] for r in size)
    print(f"\nworst Wilson upper bound on size: {worst:.4f} (trigger <= {TRIGGER_UPPER}) -> "
          f"{'PASS' if worst <= TRIGGER_UPPER else 'FAIL'}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"basis": "sparse daily mark-to-market active (gate rules v2 (iii))",
                       "sessions": args.sessions, "garch": args.garch, "alpha": ALPHA, "n_boot": N_BOOT, "size": size,
                       "power": power, "worst_wilson_upper": worst, "trigger": TRIGGER_UPPER},
                      fh, indent=1)
    return 0 if worst <= TRIGGER_UPPER else 1


if __name__ == "__main__":
    sys.exit(main())
