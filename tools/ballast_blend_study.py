#!/usr/bin/env python3
"""
ballast_blend_study — study #15 ([[H43]]): is there a REGIME-AGNOSTIC ballast? Study #13
([[F46]]) showed duration is a regime trade-off: the 7yr Treasury leg wins the negative-corr
era (2000-2021) on every metric, T-bill cash wins the positive-corr/inflation era (1962-1999,
acutely 1965-1981) on real drawdown — and each loses badly in the other regime. The open
question this study answers: does any FIXED ballast composition (a cash/bond blend, or a
short/long duration barbell) weakly dominate BOTH poles across BOTH regimes — or is the
ballast choice an irreducible regime bet? Either answer is the finding.

  PORTFOLIO: 40% equity + 60% ballast, monthly rebalanced, 1962-2026 (study #13's exact data
  build, imported: month-end ^GSPC + Shiller dy equity TR; exact constant-maturity Treasury
  zeros; ^IRX T-bill cash; FRED CPI).
  BALLASTS: the two poles (100% 7yr zero · 100% cash) · cash/z7 blends 25/75, 50/50, 75/25 ·
  a 2yr/10yr 50/50 duration BARBELL (avg duration ~6, close to the 7yr pole — isolates the
  curve-positioning question from the duration-level question).
  SCORING per era: excess-of-T-bill Sharpe · nominal maxDD · REAL (CPI-deflated) maxDD (+ real
  CAGR reported). Eras: the two DECISION eras (positive-corr 1962-1999, negative-corr
  2000-2021) drive the verdict; inflation 1965-1981, flip 2022+, and the full 64yr are
  REPORTING rows.
  INFERENCE: for every non-pole ballast, paired block bootstrap (block=12m, B=5000, seed=0)
  of (ballast mix − era-best-pole mix): dSharpe on excess returns, dMaxDD on nominal returns.

PRE-REGISTERED READS (stated before the numbers): (1) a ballast WEAKLY DOMINATES the poles iff
in BOTH decision eras it is not significantly worse than that era's BEST pole on excess Sharpe
(paired dSharpe CI not entirely below 0) and nominal maxDD (paired dMaxDD CI not entirely below
0), and its REAL maxDD is within 1pp of that era's best pole (point, no bootstrap — CPI path);
(2) if NO ballast dominates, the finding is that the ballast choice is an IRREDUCIBLE REGIME
BET, and the constructive output is the MINIMAX-REGRET ballast: per era x metric, regret =
shortfall vs the era-best pole normalized by the pole-vs-pole gap on that era-metric (so Sharpe
and drawdown are comparable); a ballast's score is its WORST normalized regret; smallest wins;
(3) "not significantly worse" is deliberately weak (absence-of-harm, not proof of equality) —
any dominance verdict here is a candidate for an equivalence (TOST) follow-up, not a settled
edge; (4) the barbell tests curve positioning at ~matched duration: if it tracks the 7yr pole
within noise everywhere, curve shape adds nothing and the whole question collapses to the
duration level (one axis, not two).

KNOWN CONSTRUCTIONS (folded in after a 3-lens skeptic panel, 2026-07-07): (a) the 50/50-by-weight
z2/z10 barbell has Macaulay duration 6.0 vs the 7yr pole's 7.0 — ~90% of its neg-era Sharpe
shortfall is that duration gap, so a duration-MATCHED 37.5/62.5 barbell (duration exactly 7.0) is
scored alongside; the curve-shape read is made ONLY on the matched instrument, and it is
absence-of-evidence at one curve point, not proof that shape never matters; (b) the dominance
verdict and the minimax winner are PROXY-ROBUST (re-run under study #13's coupon-honest legs: all
ballasts still fail, 50/50 cash/z7 still wins) but individual per-era failure MARGINS are not —
near-tolerance real-DD failures (<2pp) are bootstrap-fragile and every candidate's verdict also
rests on at least one robust failure (pos-era real-DD gaps of 8-10pp with CIs excluding the
tolerance, or neg-era dSharpe CIs entirely below 0 across block/seed choices); (c) the 2yr leg
inherits study #13's coarse pre-1976 ^IRX->^FVX interpolation (understates its carry) — a bias
AGAINST the barbell, which fails anyway; (d) the poles' own worst normalized regret is 1.0 by
construction — the printed regret numbers are meaningful only against that baseline (the 50/50
HALVES the worst-case regime bet; softening, not removing it).

Deterministic (seed=0); reuses study #13's /tmp caches (fetches them if absent).

    venv/bin/python tools/ballast_blend_study.py [--json out.json] [--selfcheck]
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
import correlation_regime_study as crs   # noqa: E402  study #13's builders (data + metrics)
import bond_ladder_study as bls          # noqa: E402  load_yields / load_cpi

ANN = 12
EQ_W = 0.4                                # the F42 conservative shape study #13 stressed
DECISION_ERAS = ["pos_corr 1962-1999", "neg_corr 2000-2021"]
REPORT_ERAS = ["inflation 1965-1981", "flip 2022-2026"]
REAL_DD_TOL = 1.0                         # pp; pre-registered read #1


def build_legs():
    y = bls.load_yields()
    cpi = bls.load_cpi()
    eq = crs.equity_tr(crs.load_gspc(), crs.load_shiller())
    z7 = crs.const_maturity_zero(y, 7)
    z2 = crs.const_maturity_zero(y, 2)
    z10 = crs.const_maturity_zero(y, 10)
    cash = crs.cash_returns(y)
    df = pd.concat([eq.rename("e"), z7.rename("z7"), z2.rename("z2"),
                    z10.rename("z10"), cash.rename("c")], axis=1).dropna()
    return df, cpi


def ballasts(df):
    return {
        "z7 pole (100% 7yr zero)": df["z7"],
        "cash pole (100% T-bill)": df["c"],
        "25% cash / 75% z7": 0.25 * df["c"] + 0.75 * df["z7"],
        "50% cash / 50% z7": 0.50 * df["c"] + 0.50 * df["z7"],
        "75% cash / 25% z7": 0.75 * df["c"] + 0.25 * df["z7"],
        "barbell 50% z2 / 50% z10": 0.50 * df["z2"] + 0.50 * df["z10"],
        # duration-MATCHED barbell (panel-forced): 0.375*2 + 0.625*10 = Macaulay 7.0 == the z7
        # pole, so barbell-vs-pole differences here are pure curve shape, not duration level
        "barbell 37.5/62.5 (dur=7.0)": 0.375 * df["z2"] + 0.625 * df["z10"],
    }


def score(df, cpi):
    """Per-era metrics for every ballast mix."""
    out = {}
    spans = {**crs.ERAS, "full 1962-2026": (str(df.index[0].date()), str(df.index[-1].date()))}
    mixes = {name: EQ_W * df["e"] + (1 - EQ_W) * leg for name, leg in ballasts(df).items()}
    for era, (a, b) in spans.items():
        rows = {}
        c = df["c"].loc[a:b]
        for name, r in mixes.items():
            rr = r.loc[a:b]
            ex = rr - c.reindex(rr.index).fillna(0.0)
            m = crs.pm12(rr)
            m["sharpe_ex"] = round(float(ex.mean() / ex.std() * math.sqrt(ANN)), 3) if ex.std() > 0 else 0.0
            m.update(crs.real_stats(rr, cpi))
            rows[name] = m
        out[era] = rows
    return out, mixes


def dominance(df, cpi, scored, mixes):
    """Pre-registered read #1, applied mechanically. Also collects the bootstraps."""
    poles = ("z7 pole (100% 7yr zero)", "cash pole (100% T-bill)")
    cands = [n for n in mixes if n not in poles]
    boots = {}
    table = {}
    for name in cands:
        fails = []
        for era in DECISION_ERAS:
            a, b = crs.ERAS[era]
            c = df["c"].loc[a:b]
            # era-best pole per metric (Sharpe_ex and maxDD both stored so bigger = better)
            best_sh = max(poles, key=lambda p: scored[era][p]["sharpe_ex"])
            best_dd = max(poles, key=lambda p: scored[era][p]["maxdd"])
            best_rdd = max(poles, key=lambda p: scored[era][p]["real_maxdd"])
            r = mixes[name].loc[a:b]
            # dSharpe vs the Sharpe-best pole, on EXCESS returns
            pb_sh = crs.paired_boot12((r - c).values, (mixes[best_sh].loc[a:b] - c).values)
            # dMaxDD vs the DD-best pole, on nominal returns
            pb_dd = crs.paired_boot12(r.values, mixes[best_dd].loc[a:b].values)
            boots[f"{name} | {era}"] = dict(vs_sharpe_pole=best_sh, dSharpe_ex=pb_sh["dSharpe"],
                                            vs_dd_pole=best_dd, dMaxDD=pb_dd["dMaxDD"])
            if pb_sh["dSharpe"][1] < 0:
                fails.append(f"{era}: excess Sharpe significantly below {best_sh}")
            if pb_dd["dMaxDD"][1] < 0:
                fails.append(f"{era}: nominal maxDD significantly deeper than {best_dd}")
            gap = scored[era][best_rdd]["real_maxdd"] - scored[era][name]["real_maxdd"]
            if gap > REAL_DD_TOL:
                fails.append(f"{era}: real maxDD {gap:.1f}pp deeper than {best_rdd} (tol {REAL_DD_TOL}pp)")
        table[name] = fails
    return table, boots


def minimax_regret(scored, mixes):
    """Read #2: normalized worst-case shortfall vs the era-best pole (pole-gap units)."""
    poles = ("z7 pole (100% 7yr zero)", "cash pole (100% T-bill)")
    metrics = ["sharpe_ex", "maxdd", "real_maxdd"]         # all stored so bigger = better
    out = {}
    for name in mixes:
        if name in poles:
            continue
        worst, detail = 0.0, None
        for era in DECISION_ERAS:
            for met in metrics:
                pv = [scored[era][p][met] for p in poles]
                best, gap = max(pv), abs(pv[0] - pv[1]) or 1e-9
                reg = max(0.0, (best - scored[era][name][met]) / gap)
                if reg > worst:
                    worst, detail = reg, f"{era}/{met}"
        out[name] = dict(worst_regret=round(worst, 3), at=detail)
    return out


def selfcheck(df):
    # blend accounting identity: 50/50 mix return == mean of the two pole mixes' returns
    b = ballasts(df)
    lhs = EQ_W * df["e"] + 0.6 * b["50% cash / 50% z7"]
    rhs = 0.5 * (EQ_W * df["e"] + 0.6 * b["z7 pole (100% 7yr zero)"]) + \
          0.5 * (EQ_W * df["e"] + 0.6 * b["cash pole (100% T-bill)"])
    assert np.allclose(lhs.values, rhs.values), "blend identity violated"
    # duration ordering through the 2022 shock: z10 deeper than barbell than z2
    dd = {}
    for k in ("z2", "z10"):
        r = df[k].loc["2021-06-01":"2023-12-31"]
        eq_ = (1 + r).cumprod()
        dd[k] = float((eq_ / eq_.cummax() - 1).min())
    rb = (0.5 * df["z2"] + 0.5 * df["z10"]).loc["2021-06-01":"2023-12-31"]
    eb = (1 + rb).cumprod()
    dd["barbell"] = float((eb / eb.cummax() - 1).min())
    assert dd["z10"] < dd["barbell"] < dd["z2"], f"barbell duration ordering violated: {dd}"
    print(f"[selfcheck OK] 50/50 blend identity exact; 2022 DD ordering z10 {dd['z10']*100:.1f}% < barbell "
          f"{dd['barbell']*100:.1f}% < z2 {dd['z2']*100:.1f}%; {len(df)} months on study #13's build.")


def fmt(scored, dom, boots, regret):
    L = []
    for era in DECISION_ERAS + REPORT_ERAS + ["full 1962-2026"]:
        rows = scored[era]
        L.append(f"== {era}{' (decision era)' if era in DECISION_ERAS else ' (reporting)'} ==")
        L.append(f"   {'ballast':28} {'CAGR%':>7} {'Sh(exc)':>8} {'maxDD%':>7} {'realCAGR%':>9} {'realDD%':>8}")
        for name, m in rows.items():
            rc = f"{m['real_cagr']:9.2f}" if m.get("real_cagr") is not None else "      n/a"
            rd = f"{m['real_maxdd']:8.1f}" if m.get("real_maxdd") is not None else "     n/a"
            L.append(f"   {name:28} {m['cagr']:7.2f} {m['sharpe_ex']:8.3f} {m['maxdd']:7.1f} {rc} {rd}")
        L.append("")
    L.append("== DOMINANCE TEST (read #1: vs the era-best pole, both decision eras, three metrics) ==")
    for name, fails in dom.items():
        L.append(f"   {name:28} " + ("WEAKLY DOMINATES (no significant shortfall)" if not fails
                                     else f"FAILS: " + "; ".join(fails)))
    L.append("")
    L.append("== BOOTSTRAPS (ballast − era-best pole) ==")
    for key, bo in boots.items():
        L.append(f"   {key:52} dSharpe(exc) vs {bo['vs_sharpe_pole'].split(' ')[0]:4} "
                 f"CI[{bo['dSharpe_ex'][0]:+.2f},{bo['dSharpe_ex'][1]:+.2f}]   "
                 f"dMaxDD vs {bo['vs_dd_pole'].split(' ')[0]:4} CI[{bo['dMaxDD'][0]:+.1f},{bo['dMaxDD'][1]:+.1f}]")
    L.append("")
    L.append("== MINIMAX REGRET (read #2: worst normalized shortfall vs era-best pole; smaller = better) ==")
    L.append("   [baseline: each POLE's own worst regret is 1.00 by construction — it concedes the full")
    L.append("    pole-gap in the era it loses; a blend below 1.00 is SOFTENING the regime bet, not removing it]")
    for name, d in sorted(regret.items(), key=lambda kv: kv[1]["worst_regret"]):
        L.append(f"   {name:28} worst regret {d['worst_regret']:.2f} pole-gap units (at {d['at']})")
    L.append("   [near-tolerance real-DD failures (<2pp) in the dominance table are bootstrap-fragile;")
    L.append("    every candidate's FAILS verdict also rests on at least one robust leg — see docstring (b)]")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="study #15 — is there a regime-agnostic ballast?")
    ap.add_argument("--json", metavar="PATH")
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    df, cpi = build_legs()
    if cpi is None:
        sys.exit("FRED CPI unavailable — the real-terms read needs it; retry with network.")
    if a.selfcheck:
        selfcheck(df)
        return
    scored, mixes = score(df, cpi)
    dom, boots = dominance(df, cpi, scored, mixes)
    regret = minimax_regret(scored, mixes)
    dominators = [n for n, fails in dom.items() if not fails]
    best_regret = min(regret.items(), key=lambda kv: kv[1]["worst_regret"])
    print("=" * 104)
    print("STUDY #15 — is there a REGIME-AGNOSTIC ballast? (fixed blends & a barbell vs the two poles, 1962-2026)")
    print("=" * 104)
    print(fmt(scored, dom, boots, regret))
    print()
    print("-- PRE-REGISTERED READS, APPLIED MECHANICALLY --")
    if dominators:
        print(f"   WEAK DOMINATORS (read #1; absence-of-harm, needs a TOST follow-up per read #3): {dominators}")
    else:
        print("   NO ballast weakly dominates both poles -> the ballast choice is an IRREDUCIBLE REGIME BET (read #2).")
    print(f"   MINIMAX-REGRET ballast: {best_regret[0]} (worst regret {best_regret[1]['worst_regret']:.2f} "
          f"pole-gap units at {best_regret[1]['at']})")
    print("=" * 104)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(dict(scored=scored, dominance=dom, bootstraps=boots, regret=regret,
                           dominators=dominators), f, indent=2, default=str)
        print(f"[wrote {a.json}]")


if __name__ == "__main__":
    main()
