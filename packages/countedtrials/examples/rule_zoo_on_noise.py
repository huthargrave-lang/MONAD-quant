#!/usr/bin/env python3
"""
A strategy search on pure noise, counted.

The price series is a seeded random walk with zero drift: no rule has an edge on it, by
construction. The search below tries what a weekend of exploring would: moving-average
crossovers, momentum and reversal at several lookbacks, z-score mean reversion, and
day-of-week effects, all long/short. It finds a "winner", because the best of many
zero-edge tries always looks good. The report shows that winner three ways: as measured,
as if it were the only thing tried (PSR), and after the search the ledger recorded.

    python examples/rule_zoo_on_noise.py              # writes ./demo_trials/
    countedtrials --ledger demo_trials stats
    countedtrials --ledger demo_trials verify

Run it twice: the second run doubles the recorded attempts, but every series is
byte-identical to one already tried, so nothing about the verdict moves. Then edit one
character of a shard and run ``verify``.
"""
import sys

import numpy as np
import pandas as pd

import countedtrials as ct

SEED = 0
rng = np.random.default_rng(SEED)
dates = pd.bdate_range("2015-01-01", periods=2520)                      # ten years of sessions
prices = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0, 0.01, len(dates)))), index=dates)
market = prices.pct_change().fillna(0.0)
WARMUP = 260                                     # every rule is scored on the same window


def _held(position: pd.Series) -> pd.Series:
    """Yesterday's position earns today's return."""
    return (position.shift(1).fillna(0.0) * market).iloc[WARMUP:]


@ct.evaluator                                    # cannot be called outside a counted trial
def backtest(rule: str, a: int, b: float = 0.0) -> pd.Series:
    if rule == "ma_cross":
        if a >= b:
            raise ValueError(f"fast ({a}) must be shorter than slow ({b:g})")
        pos = np.sign(prices.rolling(a).mean() - prices.rolling(int(b)).mean())
    elif rule == "momentum":
        pos = np.sign(prices.pct_change(a))
    elif rule == "reversal":
        pos = -np.sign(prices.pct_change(a))
    elif rule == "zscore_reversion":
        z = (prices - prices.rolling(a).mean()) / prices.rolling(a).std()
        pos = pd.Series(np.where(z < -b, 1.0, np.where(z > b, -1.0, 0.0)), index=dates)
    elif rule == "weekday":
        pos = pd.Series(np.where(dates.day_of_week == (a + 1) % 5, 1.0, 0.0), index=dates)
    else:
        raise ValueError(f"unknown rule {rule!r}")
    return _held(pd.Series(pos, index=dates).fillna(0.0))


GRID = (
    [{"rule": "ma_cross", "a": f, "b": float(s)} for f in (5, 10, 20, 50) for s in (20, 50, 100, 200)]
    + [{"rule": r, "a": n} for r in ("momentum", "reversal") for n in (1, 2, 5, 10, 21, 63, 126, 252)]
    + [{"rule": "zscore_reversion", "a": w, "b": z} for w in (10, 20, 60) for z in (1.0, 1.5, 2.0)]
    + [{"rule": "weekday", "a": d} for d in range(5)]
)


def main(ledger_dir: str = "demo_trials") -> ct.FamilyReport:
    with ct.Study("rule_zoo_on_noise.v1", ledger_dir=ledger_dir,
                  data={"series": "seeded zero-drift random walk", "seed": SEED, "n": len(prices)}) as study:
        results = study.search(backtest, GRID)
        ok = [r for r in results if r.status == "ok"]
        print(f"searched {len(results)} configurations: {len(ok)} ran, "
              f"{len(results) - len(ok)} raised (and are counted)")
        best = max(ok, key=lambda r: r.sharpe)
        print(f"the search's winner: {best.params}\n")
        report = study.report()
    print(report)
    return report


if __name__ == "__main__":
    main(*sys.argv[1:2])
