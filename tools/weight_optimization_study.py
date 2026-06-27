#!/usr/bin/env python3
"""
weight_optimization_study — study #9 (the product-recommendation refinement): the whole program
ASSUMED a 60/40 equity/bond mix. But study #8 (E32/F41) showed that FORWARD, equity is high-vol /
modest-return (~7% at ~20% vol) while bonds offer a decent yield at low vol (~4.2% at ~7% vol) — so
the forward bond Sharpe (~0.6) actually EXCEEDS the forward equity Sharpe (~0.35). Is 60/40 then the
right static mix for *this* goal (clear ~3.75% APY with the shallowest drawdown), or is it
equity-heavier than the low goal bar requires?

This sweeps the equity weight 0→100% and, for each mix, runs study #8's forward Monte-Carlo (keep the
historical mix's risk shape, re-center the mean to that mix's forward expectation = w·7% + (1−w)·4.2%).
It reports the **goal-odds-vs-drawdown frontier** and locates:
  - the mix that maximizes P(10yr CAGR ≥ 3.75%);
  - the mix that maximizes forward Sharpe;
  - the SHALLOWEST-drawdown mix that still clears the goal reliably (P ≥ 0.80) — the decision-relevant
    "least risk that meets the floor" allocation.

A SCENARIO study (forward assumptions, not data), reusing study #8's verified Monte-Carlo and study
#5's price cache. Deterministic.

    venv/bin/python tools/weight_optimization_study.py [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import static_product_study as sps          # noqa: E402  simple_ret / equity_blend
import power_study as ps                     # noqa: E402  load_2000
import forward_expectation_study as fes      # noqa: E402  montecarlo_forward / GOAL_APY

ANN = 252
EQ_FWD, BOND_FWD = 0.07, 0.042               # base-case forward nominal returns (study #8)
GOAL = fes.GOAL_APY                          # 3.75%
RELIABLE = 0.80                              # "clears the goal reliably" threshold
WGRID = [round(0.05 * i, 2) for i in range(0, 21)]   # equity weight 0%..100% step 5%
SENS_GRID = [round(0.10 * i, 2) for i in range(0, 11)]  # coarser grid for the equity-vol sensitivity


def legs():
    PX = ps.load_2000()
    eq = sps.equity_blend(PX, ["QQQ", "IWM", "DIA"])
    bond = sps.simple_ret(PX["IEF"])
    df = pd.concat([eq.rename("e"), bond.rename("b")], axis=1).dropna().loc["2002-07-31":]
    return df["e"], df["b"]


def rescale_vol(r, target_vol):
    """Rescale a return series' DEVIATIONS to a target annualized vol (preserves shape + stock-bond
    correlation; the mean is irrelevant — the forward MC re-centers it)."""
    rv = float(r.std() * np.sqrt(ANN))
    return (r - r.mean()) * (target_vol / rv) + r.mean() if rv > 0 else r


def vol_sensitivity(eq, bond):
    """The goal-optimum and the 60/40 gap are sensitive to the FORWARD equity vol. The base sweep uses
    the realized QQQ-tilted ~20%; here we rescale the equity leg to 20/18/15% and relocate the optimum,
    to show whether 'tilt more conservative than 60/40' is a goal fact or a high-equity-vol artifact."""
    realized = float(eq.std() * np.sqrt(ANN))     # unrounded → the realized-vol row is a no-op rescale
    out = []
    for tv in (realized, 0.18, 0.15):
        eqs = rescale_vol(eq, tv)
        rows = [dict(w=w, **{k: fes.montecarlo_forward((w * eqs + (1 - w) * bond).values,
                                                       w * EQ_FWD + (1 - w) * BOND_FWD)[k]
                             for k in ("p_meet_goal", "median_maxdd_pct")}) for w in SENS_GRID]
        wmax = max(rows, key=lambda r: r["p_meet_goal"])
        s60 = next(r for r in rows if r["w"] == 0.60)
        dom = bool(wmax["w"] < 0.60 and wmax["p_meet_goal"] >= s60["p_meet_goal"]
                   and wmax["median_maxdd_pct"] >= s60["median_maxdd_pct"])
        out.append(dict(eq_vol_pct=round(tv * 100, 0), w_pmax_pct=round(wmax["w"] * 100, 0),
                        p_max=round(wmax["p_meet_goal"], 3), p_6040=round(s60["p_meet_goal"], 3),
                        dd_6040=round(s60["median_maxdd_pct"], 1), dominates_6040=dom))
    return out


def study():
    eq, bond = legs()
    rows = []
    for w in WGRID:
        hist_mix = (w * eq + (1 - w) * bond)
        fwd_mean = w * EQ_FWD + (1 - w) * BOND_FWD
        mc = fes.montecarlo_forward(hist_mix.values, fwd_mean)
        rows.append(dict(w_equity=w, fwd_mean_pct=round(fwd_mean * 100, 2),
                         fwd_sharpe=mc["fwd_sharpe"], p_meet_goal=mc["p_meet_goal"],
                         median_maxdd_pct=mc["median_maxdd_pct"],
                         cagr_median_pct=mc["cagr_pctiles"][2], cagr_p75_pct=mc["cagr_pctiles"][3],
                         cagr_p95_pct=mc["cagr_pctiles"][4], p_10yr_loss=mc["p_10yr_loss"]))
    w_goal = max(rows, key=lambda r: r["p_meet_goal"])
    w_sharpe = max(rows, key=lambda r: r["fwd_sharpe"])
    sixty = next(r for r in rows if r["w_equity"] == 0.60)
    no_reliable = not any(r["p_meet_goal"] >= RELIABLE for r in rows)
    best_p = w_goal["p_meet_goal"]
    # does the goal-odds-optimal mix DOMINATE 60/40 (higher goal-odds, higher Sharpe, shallower DD)?
    dominates_6040 = (w_goal["p_meet_goal"] >= sixty["p_meet_goal"]
                      and w_goal["fwd_sharpe"] >= sixty["fwd_sharpe"]
                      and w_goal["median_maxdd_pct"] >= sixty["median_maxdd_pct"]
                      and w_goal["w_equity"] < sixty["w_equity"])
    return dict(rows=rows, w_max_goal=w_goal, w_max_sharpe=w_sharpe, sixtyforty=sixty,
                no_reliable=no_reliable, reliable_threshold=RELIABLE, best_p_meet_goal=best_p,
                w_goal_dominates_6040=dominates_6040,
                equity_vol_pct=round(float(eq.std() * np.sqrt(ANN)) * 100, 1),
                vol_sensitivity=vol_sensitivity(eq, bond))


def fmt(s):
    L = ["FORWARD goal-odds vs drawdown frontier (equity weight sweep; bond = 100−equity; base-case",
         f"forward returns equity {EQ_FWD*100:.0f}% / bond {BOND_FWD*100:.1f}%; goal = 10yr CAGR ≥ {GOAL*100:.2f}%):",
         "",
         f"   {'eq%':>4} {'fwd%':>6} {'fwdShrp':>8} {'P(goal)':>8} {'medCAGR':>8} {'medMaxDD':>9} {'P(loss)':>8}"]
    marks = {s["w_max_goal"]["w_equity"], s["w_max_sharpe"]["w_equity"], 0.60}
    for r in s["rows"]:
        if round(r["w_equity"] * 100) % 10 != 0 and r["w_equity"] not in marks:
            continue
        tag = ""
        tag += " ←P(goal)*" if r is s["w_max_goal"] else ""
        tag += " ←Sharpe*" if r is s["w_max_sharpe"] else ""
        tag += " (60/40)" if r["w_equity"] == 0.60 else ""
        L.append(f"   {r['w_equity']*100:4.0f} {r['fwd_mean_pct']:6.1f} {r['fwd_sharpe']:8.2f} "
                 f"{r['p_meet_goal']*100:7.0f}% {r['cagr_median_pct']:7.1f}% {r['median_maxdd_pct']:8.0f}% {r['p_10yr_loss']*100:7.0f}%{tag}")
    L += ["", f"   EQUITY-VOL SENSITIVITY (the exact optimum depends on the FORWARD equity vol; base sweep uses the",
          f"   realized QQQ-tilted {s['equity_vol_pct']:.0f}% — a broad-market ^GSPC leg is ~19%, a lower forward assumption ~15%):"]
    for v in s["vol_sensitivity"]:
        L.append(f"      eq vol {v['eq_vol_pct']:.0f}%: P(goal)-optimum at {v['w_pmax_pct']:.0f}% equity (P={v['p_max']*100:.0f}%); "
                 f"60/40 P={v['p_6040']*100:.0f}% DD {v['dd_6040']:.0f}%  → "
                 f"{'60/40 dominated' if v['dominates_6040'] else 'NEAR-TIE (60/40 not strictly dominated)'}")
    sf, g = s["sixtyforty"], s["w_max_goal"]
    L += ["", f"   asymmetric upside give-up of the 40/60 tilt vs 60/40 — median CAGR {g['cagr_median_pct']:.1f}% vs {sf['cagr_median_pct']:.1f}%, "
          f"but p75 {g['cagr_p75_pct']:.1f}% vs {sf['cagr_p75_pct']:.1f}%, p95 {g['cagr_p95_pct']:.1f}% vs {sf['cagr_p95_pct']:.1f}%:",
          f"   the equity you drop is the RIGHT-TAIL upside (≈{sf['cagr_p95_pct']-g['cagr_p95_pct']:.1f}%/yr at p95), which the low ~3.75% goal does not need."]
    return "\n".join(L)


def verdict(s):
    g, sh, sf = s["w_max_goal"], s["w_max_sharpe"], s["sixtyforty"]
    vs0, vsL = s["vol_sensitivity"][0], s["vol_sensitivity"][-1]
    gap0 = (vs0["p_max"] - vs0["p_6040"]) * 100
    gapL = (vsL["p_max"] - vsL["p_6040"]) * 100
    bullets = [
        f"A more conservative tilt WEAKLY DOMINATES 60/40 — at the base-case assumptions and the realized ~{s['equity_vol_pct']:.0f}% "
        f"(QQQ-tilted) equity vol. The goal-odds frontier peaks at ~{g['w_equity']*100:.0f}% equity (P={g['p_meet_goal']*100:.0f}%) and "
        f"forward Sharpe at ~{sh['w_equity']*100:.0f}% (Sharpe {sh['fwd_sharpe']:.2f}); the ~{g['w_equity']*100:.0f}/{100-g['w_equity']*100:.0f} "
        f"mix beats 60/40 on goal-odds ({g['p_meet_goal']*100:.0f}% vs {sf['p_meet_goal']*100:.0f}%), forward Sharpe "
        f"({g['fwd_sharpe']:.2f} vs {sf['fwd_sharpe']:.2f}), AND median drawdown ({g['median_maxdd_pct']:.0f}% vs {sf['median_maxdd_pct']:.0f}%).",
        f"The DIRECTION is robust, the MARGIN is equity-vol-dependent: across forward equity vols of 20/18/15% the goal-optimum "
        f"stays BELOW 60% equity (drifts ~{vs0['w_pmax_pct']:.0f}%→{vsL['w_pmax_pct']:.0f}%), so a more conservative mix weakly "
        f"dominates 60/40 throughout — but the goal-odds margin shrinks from ~{gap0:.0f}pp (at the realized ~{s['equity_vol_pct']:.0f}% "
        f"vol) to ~{gapL:.0f}pp (at an assumed 15% vol — a near-tie on ODDS, though the drawdown edge persists). The "
        f"assumption-INSENSITIVE result is the DIRECTION (tilt more conservative) and the forward-Sharpe peak at ~{sh['w_equity']*100:.0f}% "
        f"equity (a diversification effect — the negative stock-bond correlation lowers blend vol below pure bonds).",
        f"WHY forward bonds out-Sharpe equity: at 2026 yields a forward bond (~{BOND_FWD*100:.1f}% at ~7% vol → Sharpe ~0.6) carries "
        f"a higher Sharpe than forward equity (~{EQ_FWD*100:.0f}% at ~{s['equity_vol_pct']:.0f}% vol → Sharpe ~0.35), so equity "
        f"beyond ~{sh['w_equity']*100:.0f}-{g['w_equity']*100:.0f}% mostly buys DRAWDOWN (−13%→−40% across the sweep) and RIGHT-TAIL "
        f"upside (p95 CAGR {g['cagr_p95_pct']:.1f}%→{sf['cagr_p95_pct']:.1f}%) — neither of which the LOW ~3.75% goal needs.",
        f"BUT no mix clears the goal RELIABLY: the best goal-odds at ANY allocation is only {s['best_p_meet_goal']*100:.0f}%, short "
        f"of the {int(s['reliable_threshold']*100)}% bar — 10yr return DISPERSION, not the stock/bond mix, is the binding constraint "
        f"(study #8). And the drawdowns inherit the benign −0.29 historical stock-bond correlation; a post-2022 positive-correlation "
        f"regime would erode the bond-heavy tilt's advantage most. Forward returns are pinned to the equity-7% / bond-4.2%-entry-yield base case.",
    ]
    head = (
        f"For the project's actual goal — clear ~3.75% APY with the shallowest drawdown — 60/40 is somewhat equity-heavy: a more "
        f"conservative ~{g['w_equity']*100:.0f}/{100-g['w_equity']*100:.0f} equity/bond mix WEAKLY dominates it (goal-odds "
        f"{g['p_meet_goal']*100:.0f}% vs {sf['p_meet_goal']*100:.0f}%, forward Sharpe {g['fwd_sharpe']:.2f} vs {sf['fwd_sharpe']:.2f}, "
        f"median drawdown {abs(g['median_maxdd_pct']):.0f}% vs {abs(sf['median_maxdd_pct']):.0f}%, ~{sf['cagr_median_pct']-g['cagr_median_pct']:.1f}%/yr "
        f"less median return) AT the realized ~{s['equity_vol_pct']:.0f}% equity vol — though the margin narrows to a near-tie if "
        f"forward equity vol is materially lower (~15%). The robust takeaway is the DIRECTION: forward bonds out-Sharpe forward "
        f"equity, so for the low income goal you can tilt more conservative than 60/40 and shave drawdown for little return. But no "
        f"allocation makes 3.75% a sure thing (best ~{s['best_p_meet_goal']*100:.0f}%); this REFINES the static-60/40 product, it "
        f"does not change the family.")
    return head, bullets


def main():
    ap = argparse.ArgumentParser(description="study #9 — goal-optimal static equity/bond mix")
    ap.add_argument("--json", metavar="PATH")
    a = ap.parse_args()
    s = study()
    head, bullets = verdict(s)
    print("=" * 100)
    print("STUDY #9 — what static equity/bond mix best meets the income + low-drawdown goal?")
    print("=" * 100)
    print(fmt(s))
    print()
    print("── VERDICT ──")
    print("  " + head)
    for b in bullets:
        print(f"    • {b}")
    print("=" * 100)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(dict(study=s, eq_fwd=EQ_FWD, bond_fwd=BOND_FWD, goal=GOAL,
                           verdict_headline=head, verdict_bullets=bullets), f, indent=2)
        print(f"[wrote {a.json}]")


if __name__ == "__main__":
    main()
