#!/usr/bin/env python3
"""
MONAD Quant — the pre-stated diagnostics and the extra corroboration conditions of the
physical-metal trust discount tilt (docs/research/METAL_TRUST_DISCOUNT_PROTOCOL.md).

  * the 2x cost stress: a COUNTED run of the candidate and benchmark at cost_multiple 2
    (it must also have active Sharpe > 0);
  * per pair: episodes (departures from neutral), share of sessions not neutral, and the
    pair's active contribution split by leg (trust held long, z <= -1 state; trust
    underweight, z >= +1 state), from snapshot returns and the rule's session states;
  * leave-one-pair-out Sharpe of the contributions;
  * the break-even discount swing per round trip at the frozen cost tiers.

    venv/bin/python tools/metal_trust_report.py --snapshot <sha> --panel <CEFNAV sha>
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

from src.research import allocation_stats as stats  # noqa: E402
from src.research import metal_trust_classes as mt  # noqa: E402
from src.research import trials  # noqa: E402
from src.research.daily_classes import MONTH  # noqa: E402
from src.research.daily_domains import DOMAINS  # noqa: E402
from src.research.daily_strategy import COST_BPS, evaluate_daily  # noqa: E402
from src.research.daily_trials import daily_spec, family_name, record_daily  # noqa: E402

PRODUCER = "tools/metal_trust_report.py"
MIN_EPISODES = 20


def held_state(states: pd.Series) -> pd.Series:
    """The pair's effective trust weight: decided at a session, traded at the next close,
    and each of 21 tranches re-decides every 21 sessions, so the book holds the mean of
    the last 21 lagged decisions."""
    return states.shift(1).rolling(MONTH, min_periods=1).mean()


def pair_contributions(snap, panel, point) -> dict:
    rets = snap.returns()
    total = (1 + rets.night) * (1 + rets.day) - 1
    p = point["params"]
    share = 1.0 / len(p["pairs"])
    out = {}
    for trust, etf in (tuple(x) for x in p["pairs"]):
        st = mt.session_states(panel, trust, snap.dates, p)
        h = held_state(st)
        spread = total[trust] - total[etf]
        contrib = share * (h - mt.NEUTRAL) * spread
        out[trust] = {"states": st, "contrib": contrib, "held": h}
    return out


def summarise(contribs: dict, start, end) -> dict:
    res = {}
    window = lambda s: s.loc[start:end].dropna()          # noqa: E731
    for trust, c in contribs.items():
        st, x, h = window(c["states"]), window(c["contrib"]), window(c["held"])
        long_days = x[h.reindex(x.index) > mt.NEUTRAL]
        short_days = x[h.reindex(x.index) < mt.NEUTRAL]
        res[trust] = {"episodes": mt.episodes(st), "share_not_neutral": float((st != mt.NEUTRAL).mean()),
                      "contrib_ann": float(x.mean() * 252),
                      "long_leg_mean_bp_per_day": float(long_days.mean() * 1e4) if len(long_days) else None,
                      "short_leg_mean_bp_per_day": float(short_days.mean() * 1e4) if len(short_days) else None,
                      "long_leg_ann_contrib": float(long_days.sum() / (len(x) / 252)) if len(x) else None,
                      "short_leg_ann_contrib": float(short_days.sum() / (len(x) / 252)) if len(x) else None}
    frame = pd.concat({k: window(v["contrib"]) for k, v in contribs.items()}, axis=1).fillna(0.0)
    res["leave_one_pair_out_sharpe"] = {k: stats.annualized_sharpe(frame.drop(columns=k).sum(axis=1))
                                        for k in frame.columns}
    long_all = sum(r["long_leg_ann_contrib"] or 0.0 for k, r in res.items() if k in contribs)
    res["long_leg_total_ann"] = long_all
    res["episodes_total"] = sum(res[k]["episodes"] for k in contribs)
    return res


def break_even_bp() -> float:
    """One round trip of half a pair's capital between trust and ETF, in bp of the pair:
    0.5 x 2 legs x (trust cef + ETF tier1) one-way, twice (in and out)."""
    one_way = COST_BPS["cef"]["post"] + COST_BPS["tier1"]["post"]
    return 0.5 * one_way * 2


def stress(domain, ctx, point, start, end) -> dict:
    """The counted 2x cost run of the candidate and the benchmark."""
    data = ctx.data_spec(start, end)
    out = {}
    with trials.open_run(producer=PRODUCER, family=family_name(domain.name, reference=True),
                         context={**data, "role": "cost_stress"}) as run:
        t = run.begin(params=daily_spec(domain.reference, cost_multiple=2.0, domain=domain.name), data=data)
        ref = evaluate_daily(domain.decide(ctx, domain.reference), ctx.snap, start=start, end=end,
                             cost_multiple=2.0, tiers=domain.tiers(ctx))
        record_daily(t, ref)
    with trials.open_run(producer=PRODUCER, family=family_name(domain.name),
                         context={**data, "role": "cost_stress"}) as run:
        t = run.begin(params=daily_spec(point, cost_multiple=2.0, domain=domain.name), data=data)
        cand = evaluate_daily(domain.decide(ctx, point), ctx.snap, start=start, end=end,
                              cost_multiple=2.0, tiers=domain.tiers(ctx))
        record_daily(t, cand)
    a = stats.active_series(cand.returns, ref.returns)
    out["active_sharpe_2x"] = stats.annualized_sharpe(a)
    out["active_ann_2x"] = float(a.mean() * 252)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--panel", required=True)
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    domain = DOMAINS["metal_trust_discount"]
    ctx = domain.load({"snapshot": args.snapshot, "nav_panel": args.panel})
    start, end = domain.window(ctx)
    (point,) = domain.grid()
    contribs = pair_contributions(ctx.snap, ctx.panel, point)
    out = {"window": [str(start.date()), str(end.date())], "pairs": summarise(contribs, start, end),
           "break_even_bp_per_round_trip": break_even_bp(), "min_episodes": MIN_EPISODES,
           "cost_stress": stress(domain, ctx, point, start, end)}
    text = json.dumps(out, indent=1, default=float)
    if args.json:
        Path(args.json).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
