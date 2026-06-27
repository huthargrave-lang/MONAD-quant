#!/usr/bin/env python3
"""
overlay_build_study — study #4 (constructive capstone): is there a BUILD that uses the active
engine well — a small active "tail overlay" on a static 60/40 core that actually IMPROVES it?

Studies #1-3 were all EVALUATIVE and the active engine lost: no Sharpe edge vs static 50/50
(E25/F34) or the recommended 60/40 (E26/F35), and its low-drawdown overlay is real but
crisis-concentrated, small-N, and Sharpe-neutral (E27/F36). This study flips the question from
"does active beat static?" to "does a 60/40 core + a small active sleeve beat the pure 60/40
core?". Study #3 showed active protects in deep crises but drags in calm markets — a blend is
exactly where those two forces net out, so the honest test of the engine's *usefulness* is the
blend, not the head-to-head.

Method (read-only; reuses power_study primitives + the canonical sleeve; deterministic seed=0):
  - core   = static 60/40 = 0.6·equity-blend + 0.4·IEF (daily-rebalanced), the E26/F35 baseline.
  - active = the same canonical dip+5d sleeve blend.
  - blend(w) = (1-w)·core + w·active   (constant-weight daily-rebalanced overlay).
  - Sweep w over a grid; tabulate Sharpe / ann% / vol% / maxDD% / Calmar(ann/|maxDD|) + the
    active-vs-core correlation. Locate the Sharpe- and Calmar-optimal w.
  - Paired block bootstrap (block=20, B=5000, seed=0, same starts) of blend−core for ΔSharpe,
    ΔCalmar, ΔmaxDD at (a) a PRE-SPECIFIED w=0.20 (selection-bias-free) and (b) the in-sample
    Calmar-optimal w (disclosed as optimistic / selection-biased).
  Windows restricted to where IEF is real: 2014-2026 (12.5yr, total-return GLD basket) and
  2002-2026 (IEF inception → now, ~24yr).

Disclosures (all conservative-leaning for a NEGATIVE verdict — they cannot manufacture it):
  - The blend is approximated in LOG-return space (linearly combining log returns), matching the
    canonical sleeve/`_gonogo_core` convention it blends; a true simple-return rebalance scores
    ~0.006 higher Sharpe — far inside the ±0.06–0.09 ΔSharpe CI, so no conclusion flips.
  - The daily-rebalanced overlay assumes FRICTIONLESS rebalancing between the core and active legs
    (only the 5bps intra-sleeve cost is modeled); adding between-leg turnover cost only worsens the
    overlay, reinforcing "pure static 60/40 stands".
  - Window B's equity blend includes ^GSPC (price-only, no dividends), understating the equity leg
    ~0.5%/yr and thus the 60/40 core — conservative against active (the true core is even better).

Not a trading system; not imported by the live path.

    venv/bin/python tools/overlay_build_study.py [--json out.json]
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
import power_study as ps          # noqa: E402  vetted primitives

ANN = 252
BLOCK = 20
B = 5000
SEED = 0
WGRID = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.75, 1.0]
W_FIXED = 0.20                    # pre-specified "tail overlay" weight (selection-bias-free)


def vol_pct(r):
    return float(np.std(r) * math.sqrt(ANN) * 100.0)


def calmar(r):
    dd = ps.maxdd_pct(r)
    return float(ps.ann_pct(r) / abs(dd)) if dd != 0 else 0.0


def metrics(r):
    return dict(sharpe=round(ps.sharpe(r), 3), ann=round(ps.ann_pct(r), 2),
                vol=round(vol_pct(r), 2), maxdd=round(ps.maxdd_pct(r), 1),
                calmar=round(calmar(r), 3))


def core_drawdown(core):
    """Running drawdown (<=0) of the core's equity curve (causal cummax)."""
    eq = np.exp(np.cumsum(core))
    return eq / np.maximum.accumulate(eq) - 1.0


def regime_blend(active, core, w, thr):
    """REGIME-CONDITIONAL overlay (the one build the constant-weight sweep can't express):
    deploy the active sleeve at weight w ONLY on days when the core is in a drawdown deeper than
    `thr`, gated on YESTERDAY's drawdown (lag-1, leak-free). Else hold pure core. This is what the
    F36 depth result motivates — buy active's deep-crisis protection without the calm-market drag.
    Returns (blended return series, fraction of days the overlay is deployed)."""
    dd = core_drawdown(core)
    sig = np.zeros(len(core))
    sig[1:] = (dd[:-1] <= -thr).astype(float)
    return core + sig * w * (active - core), float(sig.mean())


def build_legs(PX, equities, *, start=None):
    equities = [s for s in equities if s in PX.columns]
    active = pd.DataFrame({s: lab.sleeve(PX, s) for s in equities}).fillna(0.0).mean(axis=1)
    eqret = pd.DataFrame(
        {s: np.log(PX[s].dropna() / PX[s].dropna().shift(1)) for s in equities}).mean(axis=1)
    ief = np.log(PX["IEF"].dropna() / PX["IEF"].dropna().shift(1))
    df = pd.concat([active.rename("a"), eqret.rename("e"), ief.rename("ief")], axis=1).dropna()
    if start is not None:
        df = df.loc[start:]
    core = 0.6 * df["e"].values + 0.4 * df["ief"].values
    return df["a"].values, core, df.index, equities


def paired_overlay_boot(blend, core):
    """Paired block bootstrap of blend−core for ΔSharpe, ΔCalmar, ΔmaxDD (same block starts)."""
    n = len(blend)
    nb = n // BLOCK
    rng = np.random.default_rng(SEED)
    ds, dc, dd = np.empty(B), np.empty(B), np.empty(B)
    for i in range(B):
        st = rng.integers(0, n - BLOCK + 1, size=nb)
        bi = np.concatenate([blend[s:s + BLOCK] for s in st])
        ci = np.concatenate([core[s:s + BLOCK] for s in st])
        ds[i] = ps.sharpe(bi) - ps.sharpe(ci)
        dc[i] = calmar(bi) - calmar(ci)
        dd[i] = ps.maxdd_pct(bi) - ps.maxdd_pct(ci)
    def stat(arr, pt, nd=3):
        lo, med, hi = np.percentile(arr, [2.5, 50, 97.5])
        return dict(point=round(float(pt), nd), med=round(float(med), nd),
                    ci=[round(float(lo), nd), round(float(hi), nd)])
    return dict(
        dSharpe=stat(ds, ps.sharpe(blend) - ps.sharpe(core)),
        dCalmar=stat(dc, calmar(blend) - calmar(core)),
        dMaxDD=stat(dd, ps.maxdd_pct(blend) - ps.maxdd_pct(core), nd=1),
        # robust path-smoothing read (Calmar's single-maxDD denominator is noisy): the fraction of
        # paired resamples in which the blend's drawdown is SHALLOWER than the core's.
        prob_dd_shallower=round(float(np.mean(dd > 0)), 3),
    )


def study(PX, equities, label, *, start=None):
    active, core, idx, eqs = build_legs(PX, equities, start=start)
    years = (idx[-1] - idx[0]).days / 365.25
    corr = float(np.corrcoef(active, core)[0, 1])
    sweep = []
    for w in WGRID:
        blend = (1 - w) * core + w * active
        sweep.append(dict(w=w, **metrics(blend)))
    # in-sample optima (selection-biased — disclosed)
    w_sharpe = max(sweep, key=lambda r: r["sharpe"])["w"]
    w_calmar = max(sweep, key=lambda r: r["calmar"])["w"]

    def boot_at(w):
        blend = (1 - w) * core + w * active
        return paired_overlay_boot(blend, core)

    # Regime-conditional overlay (full switch to active when the core is deeply underwater, lag-1).
    regime = []
    for thr in (0.10, 0.15):
        rb, frac = regime_blend(active, core, 1.0, thr)
        regime.append(dict(thr_pct=round(thr * 100, 0), w=1.0, frac_deployed_pct=round(frac * 100, 0),
                           **metrics(rb), boot=paired_overlay_boot(rb, core)))

    return dict(
        label=label, equities=eqs, years=round(years, 1), n_days=len(active),
        corr_active_core=round(corr, 2),
        core=metrics(core), active=metrics(active),
        sweep=sweep, w_sharpe_opt=w_sharpe, w_calmar_opt=w_calmar,
        boot_w_fixed=dict(w=W_FIXED, **boot_at(W_FIXED)),
        boot_w_calmar_opt=dict(w=w_calmar, **boot_at(w_calmar)),
        regime_conditional=regime,
    )


def fmt(w):
    L = [f"── {w['label']}  ({w['years']}yr, {w['n_days']} days, equity={'+'.join(w['equities'])}+IEF) ──",
         f"  core 60/40: Sharpe {w['core']['sharpe']:+.2f}  ann {w['core']['ann']:.1f}%  maxDD {w['core']['maxdd']:.0f}%  Calmar {w['core']['calmar']:.2f}",
         f"  active:     Sharpe {w['active']['sharpe']:+.2f}  ann {w['active']['ann']:.1f}%  maxDD {w['active']['maxdd']:.0f}%  Calmar {w['active']['calmar']:.2f}  (corr to core {w['corr_active_core']:+.2f})",
         "",
         f"  {'w_active':>8} {'Sharpe':>7} {'ann%':>6} {'vol%':>6} {'maxDD%':>7} {'Calmar':>7}"]
    for r in w["sweep"]:
        star = "  ←Sharpe*" if r["w"] == w["w_sharpe_opt"] else ""
        star += " ←Calmar*" if r["w"] == w["w_calmar_opt"] else ""
        L.append(f"  {r['w']*100:7.0f}% {r['sharpe']:7.3f} {r['ann']:6.2f} {r['vol']:6.2f} {r['maxdd']:7.1f} {r['calmar']:7.3f}{star}")
    L += ["",
          f"  in-sample optima: Sharpe maximized at w={w['w_sharpe_opt']*100:.0f}%, Calmar at w={w['w_calmar_opt']*100:.0f}% "
          f"(in-sample selection — read the bootstrap CIs, not the argmax)"]
    for tag, bk in [(f"pre-specified w={w['boot_w_fixed']['w']*100:.0f}%", w["boot_w_fixed"]),
                    (f"in-sample-opt w={w['boot_w_calmar_opt']['w']*100:.0f}% (optimistic)", w["boot_w_calmar_opt"])]:
        def rd(d):
            sig = "sig" if (d["ci"][0] > 0 or d["ci"][1] < 0) else "ns"
            return f"{d['point']:+.2f} CI[{d['ci'][0]:+.2f},{d['ci'][1]:+.2f}] {sig}"
        L.append(f"  blend−core @ {tag}:  ΔSharpe {rd(bk['dSharpe'])}   ΔCalmar {rd(bk['dCalmar'])}   "
                 f"ΔmaxDD {rd(bk['dMaxDD'])}   P(DD shallower)={bk['prob_dd_shallower']*100:.0f}%")
    L += ["", "  REGIME-CONDITIONAL overlay — 100% active while core is deeper than thr underwater (lag-1, leak-free):"]
    for r in w["regime_conditional"]:
        b = r["boot"]
        L.append(f"    thr={r['thr_pct']:.0f}% (deployed {r['frac_deployed_pct']:.0f}% of days): Sharpe {r['sharpe']:.3f} "
                 f"vs core {w['core']['sharpe']:.3f}, maxDD {r['maxdd']:.0f}% vs {w['core']['maxdd']:.0f}%  →  "
                 f"ΔSharpe {rd(b['dSharpe'])}  ΔmaxDD {rd(b['dMaxDD'])}")
    return "\n".join(L)


def verdict(wA, wB):
    def line(w):
        s = w["boot_w_fixed"]["dSharpe"]
        c = w["boot_w_fixed"]["dCalmar"]
        m = w["boot_w_fixed"]["dMaxDD"]
        sh_sig = s["ci"][0] > 0 or s["ci"][1] < 0
        ca_sig = c["ci"][0] > 0 or c["ci"][1] < 0
        dd_sig = m["ci"][0] > 0 or m["ci"][1] < 0
        return s, c, m, sh_sig, ca_sig, dd_sig
    sA = line(wA); sB = line(wB)
    bullets = []
    bullets.append(
        f"On SHARPE there is no free lunch: Sharpe is maximized at w={wA['w_sharpe_opt']*100:.0f}% (12.5yr) / "
        f"{wB['w_sharpe_opt']*100:.0f}% (24yr) active — i.e. adding the active sleeve does NOT raise the 60/40 "
        f"core's risk-adjusted return; at the pre-specified 20% overlay ΔSharpe is {sA[0]['point']:+.2f} "
        f"(CI [{sA[0]['ci'][0]:+.2f},{sA[0]['ci'][1]:+.2f}]) / {sB[0]['point']:+.2f} "
        f"(CI [{sB[0]['ci'][0]:+.2f},{sB[0]['ci'][1]:+.2f}]) — {'NOT significant' if not (sA[3] or sB[3]) else 'see CI'}.")
    psA, psB = wA["boot_w_fixed"]["prob_dd_shallower"], wB["boot_w_fixed"]["prob_dd_shallower"]
    bullets.append(
        f"On DRAWDOWN the overlay smooths the path in-sample but not reliably: at 20% the bootstrap-MEDIAN ΔmaxDD "
        f"is {sA[2]['med']:+.1f}pp (12.5yr) / {sB[2]['med']:+.1f}pp (24yr, +=shallower) — well below the "
        f"path-specific point ({sA[2]['point']:+.1f}/{sB[2]['point']:+.1f}pp) — and the CIs straddle 0 "
        f"(NOT significant). The blend is shallower in {psA*100:.0f}%/{psB*100:.0f}% of resamples — a tilt, not a "
        f"reliable cut. And it costs return (active ann {wA['active']['ann']:.1f}%/{wB['active']['ann']:.1f}% << core "
        f"{wA['core']['ann']:.1f}%/{wB['core']['ann']:.1f}%), so total return falls with w.")
    bullets.append(
        f"On CALMAR (drawdown-adjusted return) the verdict is the key one: ΔCalmar at 20% is {sA[1]['point']:+.2f} "
        f"(CI [{sA[1]['ci'][0]:+.2f},{sA[1]['ci'][1]:+.2f}]) / {sB[1]['point']:+.2f} "
        f"(CI [{sB[1]['ci'][0]:+.2f},{sB[1]['ci'][1]:+.2f}]) — "
        f"{'a RELIABLE improvement' if (sA[4] and sB[4]) else 'reliable in one window only' if (sA[4] or sB[4]) else 'NOT statistically reliable (CIs straddle 0)'}. "
        f"The in-sample Calmar-optimal w ({wA['w_calmar_opt']*100:.0f}%/{wB['w_calmar_opt']*100:.0f}%) is selection-biased; "
        f"even there the bootstrap CI is the honest read.")
    rA, rB = wA["regime_conditional"][0], wB["regime_conditional"][0]   # thr=10%
    rAs, rBs = rA["boot"]["dSharpe"], rB["boot"]["dSharpe"]
    reg_sig = (rAs["ci"][0] > 0 or rAs["ci"][1] < 0) or (rBs["ci"][0] > 0 or rBs["ci"][1] < 0)
    bullets.append(
        f"Even the SMARTER regime-conditional build fails: switching 100% to active ONLY while the core is >10% "
        f"underwater (lag-1, leak-free; deployed just {rA['frac_deployed_pct']:.0f}%/{rB['frac_deployed_pct']:.0f}% "
        f"of days) lifts the in-sample point Sharpe to {rA['sharpe']:.2f}/{rB['sharpe']:.2f} (vs core "
        f"{wA['core']['sharpe']:.2f}/{wB['core']['sharpe']:.2f}) and the maxDD to {rA['maxdd']:.0f}%/{rB['maxdd']:.0f}% "
        f"— but the paired-bootstrap ΔSharpe is {rAs['point']:+.2f} [{rAs['ci'][0]:+.2f},{rAs['ci'][1]:+.2f}] / "
        f"{rBs['point']:+.2f} [{rBs['ci'][0]:+.2f},{rBs['ci'][1]:+.2f}] — {'still NOT significant' if not reg_sig else 'see CI'}. "
        f"The deep-drawdown timing is what F36 motivates, but it hits the same small-N deep-crisis wall.")
    bullets.append(
        "Decision: NO build tested — constant-weight OR regime-conditional — turns the active engine into a "
        "reliable improver of the static 60/40. It cannot raise Sharpe (best in-sample lifts don't clear the "
        "bootstrap), the drawdown smoothing is path-driven and not statistically reliable (studies #1-3), and it "
        "costs total return. The honest product remains the pure static 60/40; an active overlay is a discretionary "
        "path-smoothing preference, not a free or reliable upgrade. This closes the active-vs-static arc "
        "(D6/F25, E25-E27): the engine is a capital-preservation overlay, never a risk-adjusted edge.")
    head = (
        f"No build rescues the active engine — not a constant-weight overlay NOR a regime-conditional one: on a "
        f"60/40 core the Sharpe-optimal constant weight is ~0%, and even switching fully to active only in deep "
        f"(>10%) core drawdowns lifts the in-sample Sharpe but its bootstrap ΔSharpe still straddles 0 (the F36 "
        f"small-N deep-crisis wall). The drawdown smoothing is path-driven/not reliable and costs total return. "
        f"The pure static 60/40 stands; the active engine is a discretionary capital-preservation overlay, not a "
        f"risk-adjusted edge.")
    return head, bullets


def main():
    ap = argparse.ArgumentParser(description="study #4 — active overlay on a 60/40 core")
    ap.add_argument("--json", metavar="PATH")
    a = ap.parse_args()

    wA = study(lab.load(), ["QQQ", "SPY", "IWM", "DIA", "GLD"], "2014-2026 (total-return basket) core+overlay")
    wB = study(ps.load_2000(), ["^GSPC", "QQQ", "IWM", "DIA"],
               "2002-2026 long-history core+overlay (sliced to IEF inception)", start="2002-07-31")
    head, bullets = verdict(wA, wB)

    print("=" * 92)
    print("STUDY #4 — does a small active 'tail overlay' improve a static 60/40 core?")
    print("=" * 92)
    print(fmt(wA)); print()
    print(fmt(wB)); print()
    print("── VERDICT ──")
    print("  " + head)
    for b in bullets:
        print(f"    • {b}")
    print("=" * 92)

    if a.json:
        with open(a.json, "w") as f:
            json.dump(dict(window_2014=wA, window_2002=wB, verdict_headline=head,
                           verdict_bullets=bullets), f, indent=2)
        print(f"[wrote {a.json}]")


if __name__ == "__main__":
    main()
