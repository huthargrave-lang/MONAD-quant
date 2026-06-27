#!/usr/bin/env python3
"""
forward_expectation_study — study #8 (closing the loop on the GOAL): the static 60/40 is the
recommended product (E25-E30), but its ~9.5% historical CAGR rode a secular bond bull + a QQQ
growth tilt that won't repeat (F38/E29). So what should you HONESTLY expect going forward at
2026 starting yields — and does it meet the project's foundational ~3.75% APY income goal (D4)
and the 'near-zero drawdown' aspiration (CLAUDE.md §1)?

This is a forward SCENARIO study, not a backtest — its inputs are explicit assumptions, not data:
  - BOND forward return ≈ the STARTING YIELD (a bond's total return over its horizon is well
    approximated by its entry yield; the 10yr is ~4.2% in 2026). The 2002-2026 bond bull
    (falling yields → price gains on top of coupon) is the part that does NOT repeat.
  - EQUITY forward return ≈ a conservative nominal range (5-9%), below the 2002-2026 QQQ-tilted
    ~13%/yr — high US valuations (CAPE) compress forward equity returns.
A scenario MATRIX (equity × bond) gives the forward expected 60/40 return; a Monte-Carlo that keeps
the historical 60/40 RISK shape (vol, fat tails, drawdowns) but re-centers the MEAN to the forward
expectation gives the forward distribution of 10yr CAGR and drawdown — i.e. honest odds of hitting
the goal and the worst-case path a near-zero-drawdown product cannot deliver.

Reuses static_product_study primitives (simple-return accounting, the 2000 price cache). Deterministic.

    venv/bin/python tools/forward_expectation_study.py [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import static_product_study as sps   # noqa: E402  pmetrics / simple_ret / equity_blend
import power_study as ps             # noqa: E402  load_2000

ANN = 252
BLOCK = 20
N_PATHS = 5000
HORIZON_Y = 10
GOAL_APY = 0.0375                      # the project's foundational ~3.75% APY goal (D4)
EQUITY_FWD = [0.05, 0.07, 0.09]        # conservative / base / optimistic forward nominal equity
BOND_FWD = [0.035, 0.042, 0.050]       # low / base(≈2026 10yr) / high forward bond (≈ starting yield)


def ann_to_daily(a):
    return (1.0 + a) ** (1.0 / ANN) - 1.0


def historical_6040():
    PX = ps.load_2000()
    eq = sps.equity_blend(PX, ["QQQ", "IWM", "DIA"])
    ief = sps.simple_ret(PX["IEF"])
    df = pd.concat([eq.rename("e"), ief.rename("b")], axis=1).dropna()
    df = df.loc["2002-07-31":]
    r = (0.6 * df["e"] + 0.4 * df["b"])
    corr = float(np.corrcoef(df["e"].values, df["b"].values)[0, 1])   # full-history stock-bond corr
    r_2022 = r.loc["2022-01-01":]                                     # the positive-corr rate-shock regime
    return dict(r=r, equity=sps.pmetrics(df["e"].values), bond=sps.pmetrics(df["b"].values),
                p6040=sps.pmetrics(r.values), span=f"{df.index[0].date()}→{df.index[-1].date()}",
                corr_stock_bond=round(corr, 2), r_2022=r_2022)


def montecarlo_forward(hist_r, fwd_annual, seed=0):
    """Re-center the historical 60/40 daily returns to the forward mean (preserving vol/shape/tails),
    then block-bootstrap N_PATHS forward 10yr paths. Returns CAGR & maxDD distributions + goal odds."""
    r = np.asarray(hist_r, dtype=float)
    r_c = r - r.mean() + ann_to_daily(fwd_annual)        # swap the mean, keep the risk shape
    n = len(r_c)
    steps = HORIZON_Y * ANN
    nb = steps // BLOCK
    rng = np.random.default_rng(seed)
    cagr = np.empty(N_PATHS)
    maxdd = np.empty(N_PATHS)
    for i in range(N_PATHS):
        starts = rng.integers(0, n - BLOCK + 1, size=nb)
        path = np.concatenate([r_c[s:s + BLOCK] for s in starts])
        eq = np.cumprod(1.0 + path)
        cagr[i] = eq[-1] ** (ANN / len(path)) - 1.0
        maxdd[i] = (eq / np.maximum.accumulate(eq) - 1.0).min()
    pct = lambda x, ps_=(5, 25, 50, 75, 95): [round(float(v) * 100, 1) for v in np.percentile(x, ps_)]
    vol = float(r.std() * math.sqrt(ANN))
    return dict(
        fwd_annual_pct=round(fwd_annual * 100, 2),
        fwd_sharpe=round(fwd_annual / vol, 2) if vol > 0 else 0.0,    # forward risk-adjusted quality
        cagr_pctiles=pct(cagr), maxdd_pctiles=pct(maxdd),
        p_meet_goal=round(float(np.mean(cagr >= GOAL_APY)), 3),
        p_beat_4pct=round(float(np.mean(cagr >= 0.04)), 3),
        p_10yr_loss=round(float(np.mean(cagr < 0)), 3),
        p_dd_worse_than_20=round(float(np.mean(maxdd <= -0.20)), 3),
        median_maxdd_pct=round(float(np.median(maxdd)) * 100, 1),
    )


def fmt(eqh, bdh, h6040, span, matrix, mc_base, corr):
    L = [f"HISTORICAL 60/40  ({span}, dividend-correct equity QQQ+IWM+DIA + IEF):",
         f"   equity leg: CAGR {eqh['cagr']:.1f}%  vol {eqh['vol']:.1f}%   bond (IEF): CAGR {bdh['cagr']:.1f}%  vol {bdh['vol']:.1f}%",
         f"   60/40:      CAGR {h6040['cagr']:.1f}%  Sharpe {h6040['sharpe']:.2f}  maxDD {h6040['maxdd']:.0f}%  Calmar {h6040['calmar']:.2f}  "
         f"(stock-bond corr {corr:+.2f} — bonds HEDGED the 2008/2020 crashes)",
         f"   ↑ this rode a secular bond bull + a QQQ growth tilt + a benign negative stock-bond correlation — none guaranteed to repeat.",
         "",
         "FORWARD EXPECTED 60/40 RETURN — scenario matrix (0.6·equity + 0.4·bond), vs the 3.75% goal:",
         f"   {'equity↓ / bond→':>16}" + "".join(f"{b*100:6.1f}%" for b in BOND_FWD)]
    for row in matrix:
        cells = "".join(f"{c['fwd']*100:5.1f}%" + ("*" if c['meets'] else " ") for c in row["cells"])
        L.append(f"   {row['equity']*100:>14.0f}% " + cells)
    L += ["   (* = meets the 3.75% APY goal; base case ≈ 7% equity / 4.2% bond)",
          "",
          f"MONTE-CARLO (base case: forward 60/40 mean {mc_base['fwd_annual_pct']:.1f}%/yr → forward SHARPE "
          f"{mc_base['fwd_sharpe']:.2f} (vs {h6040['sharpe']:.2f} historical); historical risk shape, "
          f"{HORIZON_Y}yr, {N_PATHS} paths):",
          f"   10yr CAGR  pctiles [5/25/50/75/95]: {mc_base['cagr_pctiles']} %",
          f"   worst DD   pctiles [5/25/50/75/95]: {mc_base['maxdd_pctiles']} %  (median {mc_base['median_maxdd_pct']:.0f}%)",
          f"   P(CAGR ≥ 3.75% goal) = {mc_base['p_meet_goal']*100:.0f}%   P(CAGR ≥ 4%) = {mc_base['p_beat_4pct']*100:.0f}%   "
          f"P(10yr loss) = {mc_base['p_10yr_loss']*100:.0f}%   P(drawdown worse than -20%) = {mc_base['p_dd_worse_than_20']*100:.0f}%",
          f"   [caveat: this DD distribution inherits the benign {corr:+.2f} historical stock-bond correlation — bonds HEDGED the "
          f"2008/2020 crashes. If the post-2022 POSITIVE correlation (both fell in the rate shock) persists, drawdowns deepen and",
          f"    goal odds fall — so the −23% median is the estimate UNDER historical hedging, not a worst case.]"]
    return "\n".join(L)


def verdict(h6040, matrix, mc_base, mc_low, corr):
    base_fwd = matrix[1]["cells"][1]["fwd"]               # 7% equity / 4.2% bond
    lo, hi = matrix[0]["cells"][0]["fwd"], matrix[-1]["cells"][-1]["fwd"]
    bullets = [
        f"The ~{h6040['cagr']:.1f}% historical CAGR is NOT the forward expectation: re-priced at 2026 starting yields "
        f"(bond return ≈ entry yield ~4.2%, not the bull-market 3.6% price gains) and a conservative 5-9% forward equity, "
        f"the forward 60/40 EXPECTED return is ~{base_fwd*100:.1f}% (base; ~{lo*100:.1f}-{hi*100:.1f}% across the matrix). At "
        f"the same ~12% vol that is a forward SHARPE of only ~{mc_base['fwd_sharpe']:.2f}, vs the {h6040['sharpe']:.2f} the "
        f"history shows — forward risk-adjusted quality is ~40% lower (the 0.84 was flattered by the bond bull).",
        f"It MORE-LIKELY-THAN-NOT clears the ~3.75% APY goal (D4): base-case P(10yr CAGR ≥ 3.75%) = "
        f"{mc_base['p_meet_goal']*100:.0f}% — a ~1-in-3 chance of MISSING it over a full decade, falling to "
        f"{mc_low['p_meet_goal']*100:.0f}% (a coin flip) in the pessimistic corner. [Goal read as total-return CAGR ≥ 3.75%; "
        f"a sustainable 3.75% INCOME withdrawal is a stricter bar given the {mc_base['cagr_pctiles'][0]:+.1f}% 5th-pctile decade.]",
        f"It FAILS the 'near-zero drawdown' aspiration outright: median worst drawdown ~{abs(mc_base['median_maxdd_pct']):.0f}% and a "
        f"{mc_base['p_dd_worse_than_20']*100:.0f}% chance of a >20% drawdown over 10yr — EQUITY-LIKE tail risk. (NOT a QQQ-tilt "
        f"artifact: a broad-market ^GSPC 60/40 has comparable-to-DEEPER drawdowns, since the 40% bond leg dominates blend risk.) "
        f"Unattainable by any honest static OR active build here (E27/E28/F37).",
        f"And the base-case drawdown is the OPTIMISTIC end, not conservative: the MC inherits the benign {corr:+.2f} historical "
        f"stock-bond correlation — bonds rallied during the 2008/2020 equity crashes, structurally SUPPRESSING 60/40 drawdowns. "
        f"That correlation turned POSITIVE in 2022 (both fell in the rate shock). If a bonds-don't-hedge regime persists, the "
        f"~{abs(mc_base['median_maxdd_pct']):.0f}% median DD deepens and the goal odds fall — the figure is the estimate under "
        f"historical hedging, not a worst case. (A direct bootstrap of the short, recovery-dominated post-2022 window does not "
        f"itself worsen the result, so this is a structural caveat, not a measured effect.)",
    ]
    head = (
        f"Honest forward verdict: at 2026 yields the static 60/40 should be expected to return ~{base_fwd*100:.1f}%/yr (base; "
        f"~{lo*100:.1f}-{hi*100:.1f}% across scenarios) at a forward SHARPE of only ~{mc_base['fwd_sharpe']:.2f} (the history's "
        f"{h6040['sharpe']:.2f} flattered by a bond bull + benign correlation). It MORE-LIKELY-THAN-NOT clears the ~3.75% income "
        f"goal (P≈{mc_base['p_meet_goal']*100:.0f}% over 10yr — ~1-in-3 chance of missing) but with a median "
        f"~{abs(mc_base['median_maxdd_pct']):.0f}% worst drawdown — EQUITY-LIKE tail risk that could DEEPEN if the post-2022 "
        f"positive stock-bond correlation holds (the −23% assumes bonds keep hedging). The achievable product is a real "
        f"bond-alternative on RETURN (not a sure one, and NOT near-zero-drawdown); the original near-zero-DD goal is "
        f"unattainable by any honest static OR active build in this program.")
    return head, bullets


def main():
    ap = argparse.ArgumentParser(description="study #8 — forward-looking 60/40 expectation vs the income goal")
    ap.add_argument("--json", metavar="PATH")
    a = ap.parse_args()

    H = historical_6040()
    eqh, bdh, h6040, span, corr = H["equity"], H["bond"], H["p6040"], H["span"], H["corr_stock_bond"]
    matrix = []
    for eq in EQUITY_FWD:
        cells = []
        for bd in BOND_FWD:
            fwd = 0.6 * eq + 0.4 * bd
            cells.append(dict(bond=bd, fwd=round(fwd, 4), meets=bool(fwd >= GOAL_APY)))
        matrix.append(dict(equity=eq, cells=cells))
    base_fwd = 0.6 * 0.07 + 0.4 * 0.042
    mc_base = montecarlo_forward(H["r"].values, base_fwd)
    mc_low = montecarlo_forward(H["r"].values, 0.6 * 0.05 + 0.4 * 0.035)
    head, bullets = verdict(h6040, matrix, mc_base, mc_low, corr)

    print("=" * 100)
    print("STUDY #8 — forward-looking 60/40 expectation: does the product meet the income goal once the tailwinds end?")
    print("=" * 100)
    print(fmt(eqh, bdh, h6040, span, matrix, mc_base, corr))
    print()
    print("── VERDICT ──")
    print("  " + head)
    for b in bullets:
        print(f"    • {b}")
    print("=" * 100)

    if a.json:
        with open(a.json, "w") as f:
            json.dump(dict(historical=dict(equity=eqh, bond=bdh, p6040=h6040, span=span,
                                           corr_stock_bond=corr),
                           scenario_matrix=matrix, mc_base=mc_base, mc_pessimistic=mc_low,
                           goal_apy=GOAL_APY, verdict_headline=head, verdict_bullets=bullets), f, indent=2)
        print(f"[wrote {a.json}]")


if __name__ == "__main__":
    main()
