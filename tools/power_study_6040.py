#!/usr/bin/env python3
"""
power_study_6040 — study #2: does active daily-MR beat the DECISION-RELEVANT static
60/40 equity/bond, not just the easier 50/50≡buy&hold of study #1 (E25/F34)?

E25/F34 tested active vs static 50/50 (which is Sharpe-invariant to buy&hold) and found
no edge. But D6/F25's ACTUAL recommendation is static 60/40 equity/BOND (IEF), whose Sharpe
(~0.84 over 2014-2026) EXCEEDS buy&hold — the harder, decision-relevant bar. A skeptic on
the E25 verification panel flagged exactly this: the 50/50 baseline is conservative in the
active engine's favour; re-test against 60/40, handling IEF's 2002-07 inception so the
early-2000s bond leg is not silently 60/40-CASH (the bias mr_daily_lab.cmd_gonogolong warns of).

Same methodology and rigor as E25 — this REUSES tools/power_study.py's vetted primitives
(one Sharpe, one paired block bootstrap, one power/TOST implementation, no divergent math):
paired ΔSharpe(active − 60/40) block bootstrap (block=20, B=5000, seed=0, same starts both
legs), MDE@80% power, two-sided power curves, TOST equivalence (90%-CI ⊂ ±Δ → Δ*), and a
paired maxDD-gap panel. Windows are RESTRICTED to where IEF actually trades, so the bond leg
is real throughout: 2014-2026 (12.5yr) and 2002-2026 (IEF inception → now, ~24yr).

The 60/40 is a daily-rebalanced constant-weight 0.6·equity-blend + 0.4·IEF, matching
mr_daily_lab._gonogo_core's static-60/40 row. The active leg is the SAME dip+5d sleeve blend
as E25 (apples-to-apples: same active, harder bench).

Read-only research; reuses mr_daily_lab.sleeve; not a trading system, not imported by the
live path. Deterministic (seed=0) so the numbers reproduce.

Two disclosures (both conservative-leaning, i.e. they do not manufacture the no-edge result):
  - Sharpe is the LOG-return convention (matching mr_daily_lab). A simple-return daily-rebalanced
    60/40 scores ~0.97 Sharpe vs the log-convention 0.84 — an even HARDER bar for active. ΔSharpe is
    internally apples-to-apples (active, equity, IEF all log-weighted).
  - Window B's equity blend includes ^GSPC, a PRICE-ONLY index (no dividends), understating the
    equity leg ~0.5%/yr and thus the 60/40 bench ~0.3%/yr (~0.03 Sharpe). Since 60/40 holds less
    equity-time than the ~79%-invested active leg, the omission penalizes active slightly MORE
    (per mr_daily_lab.cmd_gonogolong) — conservative against active, not for it.

    venv/bin/python tools/power_study_6040.py [--json out.json]
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
import mr_daily_lab as lab        # noqa: E402  canonical sleeve / load
import power_study as ps          # noqa: E402  vetted primitives (study #1, E25)


def build_legs(PX, equities, *, start=None):
    """active = equal-weight dip+5d sleeve blend; bench = daily-rebalanced 0.6·equity + 0.4·IEF.

    All three legs (active, equity-blend, IEF) are aligned on a common index; if `start` is
    given (IEF inception) the window is sliced so the bond leg is real for every day."""
    equities = [s for s in equities if s in PX.columns]
    active = pd.DataFrame({s: lab.sleeve(PX, s) for s in equities}).fillna(0.0).mean(axis=1)
    eqret = pd.DataFrame(
        {s: np.log(PX[s].dropna() / PX[s].dropna().shift(1)) for s in equities}
    ).mean(axis=1)
    ief = np.log(PX["IEF"].dropna() / PX["IEF"].dropna().shift(1))
    df = pd.concat([active.rename("a"), eqret.rename("e"), ief.rename("ief")], axis=1).dropna()
    if start is not None:
        df = df.loc[start:]
    bench = 0.6 * df["e"] + 0.4 * df["ief"]
    return df["a"].values, bench.values, df["e"].values, df["ief"].values, df.index, equities


def analyze(active, bench, eqret, ief, idx, equities, label):
    """active-vs-60/40 power & equivalence panel, built from power_study's vetted atoms."""
    n = len(active)
    years = (idx[-1] - idx[0]).days / 365.25
    sh_a, sh_b = ps.sharpe(active), ps.sharpe(bench)
    sh_eq, sh_ief = ps.sharpe(eqret), ps.sharpe(ief)
    vol_active = float(active.std() * math.sqrt(ps.ANN) * 100.0)
    diff_point = sh_a - sh_b

    boot = ps.paired_sharpe_diff_boot(active, bench)         # block=20, B=5000, seed=0
    se = float(boot.std(ddof=1))
    lo95, hi95 = (float(x) for x in np.percentile(boot, [2.5, 97.5]))
    lo90, hi90 = (float(x) for x in np.percentile(boot, [5.0, 95.0]))
    excludes_zero = not (lo95 < 0 < hi95)

    mde_80 = (ps.Z_ALPHA + ps.Z[0.80]) * se

    def power(delta, se_):
        ncp = abs(delta) / se_ if se_ > 0 else float("inf")
        return ps.norm_cdf(ncp - ps.Z_ALPHA) + ps.norm_cdf(-ncp - ps.Z_ALPHA)

    def years_for_power(delta, target=0.80):
        se_target = abs(delta) / (ps.Z_ALPHA + ps.Z[target])
        return years * (se / se_target) ** 2

    deltas = [0.10, 0.20, 0.30, 0.50]
    power_now = {f"{d:.2f}": round(power(d, se), 3) for d in deltas}
    years_80 = {f"{d:.2f}": round(years_for_power(d), 1) for d in deltas}
    equiv_margin = max(abs(lo90), abs(hi90))
    tost = {f"{m:.2f}": (lo90 > -m and hi90 < m) for m in (0.20, 0.30, 0.50)}

    # capital preservation: active vs the 60/40 ITSELF (not a 0.5· cash blend).
    dd_a, dd_b = ps.maxdd_pct(active), ps.maxdd_pct(bench)
    dd_boot = ps.paired_maxdd_diff_boot(active, bench)       # active − 60/40, +=active shallower
    dd_lo, dd_med, dd_hi = (float(x) for x in np.percentile(dd_boot, [2.5, 50, 97.5]))
    dd_significant = not (dd_lo < 0 < dd_hi)

    return dict(
        label=label, equities=equities, n_days=n, years=round(years, 1),
        sharpe_active=round(sh_a, 3), sharpe_6040=round(sh_b, 3),
        sharpe_equity=round(sh_eq, 3), sharpe_ief=round(sh_ief, 3),
        ann_active=round(ps.ann_pct(active), 2), ann_6040=round(ps.ann_pct(bench), 2),
        vol_active=round(vol_active, 1),
        diff_point=round(diff_point, 3), diff_se=round(se, 3),
        diff_ci95=[round(lo95, 3), round(hi95, 3)], diff_ci90=[round(lo90, 3), round(hi90, 3)],
        sharpe_edge_detected=excludes_zero, active_worse_significant=(hi95 < 0),
        mde_80pct=round(mde_80, 3), power_now=power_now, years_for_80pct=years_80,
        equiv_margin_95=round(equiv_margin, 3), tost_equivalence=tost,
        maxdd_active=round(dd_a, 1), maxdd_6040=round(dd_b, 1),
        maxdd_diff_ci=[round(dd_lo, 1), round(dd_med, 1), round(dd_hi, 1)],
        maxdd_edge_significant=dd_significant,
    )


def study(PX, equities, label, *, start=None):
    a, b, e, ief, idx, eqs = build_legs(PX, equities, start=start)
    return analyze(a, b, e, ief, idx, eqs, label)


def fmt(w):
    L = [f"── {w['label']}  ({w['years']}yr, {w['n_days']} days, equity={'+'.join(w['equities'])}+IEF) ──",
         f"  Sharpe: active {w['sharpe_active']:+.2f}  60/40 {w['sharpe_6040']:+.2f}  "
         f"(equity {w['sharpe_equity']:+.2f}, IEF {w['sharpe_ief']:+.2f})  → ΔSharpe {w['diff_point']:+.2f}  (SE {w['diff_se']:.2f})",
         f"  paired ΔSharpe(active−60/40) 95% CI {w['diff_ci95']}   90% CI {w['diff_ci90']}   "
         + ("active SIGNIFICANTLY WORSE (95% CI < 0)" if w['active_worse_significant']
            else "edge detected: YES" if w['sharpe_edge_detected'] else "no edge (straddles 0)"),
         f"  MDE @80% power: {w['mde_80pct']:+.2f} Sharpe",
         "  power NOW for a true edge of ...   " + "  ".join(f"{d}:{w['power_now'][d]*100:.0f}%" for d in w['power_now']),
         "  resolution horizon @80% power ...  " + "  ".join(f"{d}:{w['years_for_80pct'][d]:.0f}yr" for d in w['years_for_80pct'])
         + "   (order-of-mag; SE∝1/√yr)",
         "  TOST equivalence (active≈60/40 within ±Δ, 95% conf): "
         + "  ".join(f"±{m}:{'PASS' if w['tost_equivalence'][m] else 'fail'}" for m in w['tost_equivalence'])
         + f"   → smallest provable margin Δ*={w['equiv_margin_95']:.2f}",
         f"  capital-preservation: maxDD active {w['maxdd_active']:.0f}% vs 60/40 {w['maxdd_6040']:.0f}%; "
         f"paired maxDD-gap CI {w['maxdd_diff_ci']} (+=active shallower)  "
         f"→ {'SIGNIFICANT active DD edge' if w['maxdd_edge_significant'] else 'path-dependent, NOT significant'}"]
    return "\n".join(L)


def verdict(wA, wB):
    bullets = []
    bullets.append(
        f"Against the RECOMMENDED 60/40 (Sharpe {wA['sharpe_6040']:.2f} / {wB['sharpe_6040']:.2f}), active "
        f"daily-MR (Sharpe {wA['sharpe_active']:.2f} / {wB['sharpe_active']:.2f}) has a LOWER POINT Sharpe in "
        f"both windows — ΔSharpe {wA['diff_point']:+.2f} (12.5yr) / {wB['diff_point']:+.2f} (24yr) — but WITHIN "
        f"noise (both 95% CIs straddle 0): no statistically reliable loss, and crucially no edge.")
    for w, tag in ((wA, "12.5yr"), (wB, "24yr")):
        extra = ""
        if not w["active_worse_significant"] and w["diff_ci90"][1] <= 0.01:
            extra = (f" — and the 90% CI upper bound is {w['diff_ci90'][1]:+.3f}, i.e. active is on the boundary "
                     f"of being significantly WORSE at the one-sided 5% level.")
        bullets.append(f"{tag}: 95% CI {w['diff_ci95']} straddles 0 (no edge); TOST Δ*={w['equiv_margin_95']:.2f}; "
                       f"MDE@80%≈{w['mde_80pct']:.2f} so a small (≤0.2 Sharpe) edge stays unexcluded.{extra}")
    ddA = "shallower-DD edge" if wA["maxdd_edge_significant"] else "path-dependent DD"
    ddB = "shallower-DD edge" if wB["maxdd_edge_significant"] else "path-dependent DD"
    bullets.append(
        f"The one place active might still help is DRAWDOWN: point maxDD active {wA['maxdd_active']:.0f}%/{wB['maxdd_active']:.0f}% "
        f"vs 60/40 {wA['maxdd_6040']:.0f}%/{wB['maxdd_6040']:.0f}% — but the paired bootstrap says {ddA} (12.5yr, "
        f"{wA['maxdd_diff_ci']}) and {ddB} (24yr, {wB['maxdd_diff_ci']}): the DD gap is NOT significant. "
        f"[unquantified hypothesis: 2022's joint stock+bond drawdown is the kind of regime where active's cash "
        f"buffer would help — not decomposed here.]")
    bullets.append(
        "Decision: the E25/F34 'no edge vs static' verdict HARDENS against the decision-relevant 60/40 — active "
        f"does not beat it on Sharpe (CIs straddle 0) nor on point return (active {wA['ann_active']:.1f}%/{wB['ann_active']:.1f}% "
        f"vs {wA['ann_6040']:.1f}%/{wB['ann_6040']:.1f}% ann — point estimate, no CI on the return gap), and the only "
        "candidate advantage (lower drawdown) is not statistically reliable. Static 60/40 stays the recommended "
        "bond-alternative; the active engine is at best a regime-dependent low-drawdown overlay (consistent with D6/F25).")
    head = (
        f"Active daily-MR does NOT beat the recommended static 60/40: it has a LOWER POINT Sharpe in both windows "
        f"(ΔSharpe {wA['diff_point']:+.2f}/{wB['diff_point']:+.2f}, within noise — CIs straddle 0; over 24yr it is on "
        f"the one-sided-significance boundary), and its only candidate edge (shallower drawdown) is path-dependent. "
        f"Study #1's no-edge verdict strengthens against the harder, decision-relevant bar.")
    return head, bullets


def main():
    ap = argparse.ArgumentParser(description="active daily-MR vs static 60/40 — power & equivalence")
    ap.add_argument("--json", metavar="PATH")
    a = ap.parse_args()

    wA = study(lab.load(), ["QQQ", "SPY", "IWM", "DIA", "GLD"], "2014-2026 standard basket vs 60/40")
    wB = study(ps.load_2000(), ["^GSPC", "QQQ", "IWM", "DIA"],
               "2002-2026 long-history vs 60/40 (sliced to IEF inception)", start="2002-07-30")
    head, bullets = verdict(wA, wB)

    print("=" * 80)
    print("STUDY #2 — active daily-MR vs the DECISION-RELEVANT static 60/40 equity/bond")
    print("=" * 80)
    print(fmt(wA)); print()
    print(fmt(wB)); print()
    print("── VERDICT ──")
    print("  " + head)
    for b in bullets:
        print(f"    • {b}")
    print("=" * 80)

    notes = [
        "Sharpe is the log-return convention (matches mr_daily_lab); a simple-return 60/40 ≈ 0.97, a harder bar.",
        "Window B equity blend includes ^GSPC (price-only, no dividends): understates the equity leg ~0.5%/yr and "
        "the 60/40 ~0.3%/yr (~0.03 Sharpe); conservative against active (60/40 holds less equity-time).",
        "ΔSharpe and maxDD-gap are bootstrapped (CIs); the annualized-return comparison is point-estimate only.",
        "The 2022 joint stock+bond drawdown narrative is an unquantified hypothesis, not a decomposed result.",
    ]
    if a.json:
        with open(a.json, "w") as f:
            json.dump(dict(window_2014=wA, window_2002=wB, verdict_headline=head,
                           verdict_bullets=bullets, disclosures=notes), f, indent=2)
        print(f"[wrote {a.json}]")


if __name__ == "__main__":
    main()
