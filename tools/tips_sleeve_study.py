#!/usr/bin/env python3
"""
tips_sleeve_study — study #14 ([[H42]]): does a TIPS SLEEVE inside the recommended static mix
earn its place? Study #13 ([[F46]]) established TIPS as the structural mitigation of the
bonds-don't-hedge regime, but tested them only as (a) a FULL bond-leg swap in the 2021-23 shock
and (b) a forward held-to-maturity ladder claim. The obvious retail-implementable middle ground —
carve a modest TIPS sleeve out of the conservative mix's nominal-bond leg — was never tested, and
study #5's gold lesson ([[F38]]/[[F39]]) says candidate sleeves usually die under a fair paired
bootstrap + a family-wise correction. This study runs exactly that discipline:

  BASE: the recommended conservative mix, 40% SPY / 60% IEF (F42's goal-optimal shape), daily
        rebalanced, 2004-2026 (TIP's ETF life).
  SLEEVES: carve ws ∈ {5%, 10%, 15%, 20%} of PORTFOLIO from the IEF leg into a TIPS variant:
        TIP  (7-10yr real duration ~6.7, 2004+),
        STIP (0-5yr TIPS, 2011+),
        VTIP (0-5yr TIPS, 2013+)   — short-duration variants F46 flagged as the interesting case
        (TIP itself ate the 2022 duration shock: -13.9% nominal / -22.5% real).
  CUTS: full variant life · the negative-corr regime portion (2004..2021) · the 2022+ flip era
        (the ONE observed bonds-don't-hedge event TIPS have lived through) · the acute 2021-06..
        2023-12 shock window. Every mix scored NOMINAL and REAL (CPI-deflated).
  INFERENCE: paired block bootstrap (block=20d, B=5000, seed=0) of (sleeved − base) dSharpe and
        dMaxDD on the full window and the flip cut, plus a FAMILY-WISE band: the sleeve family is
        4 sizes x 3 variants = 12 comparisons, so any "significant" CI is re-tested at the
        Bonferroni x12 level before it may be called real.

PRE-REGISTERED READS (stated before the numbers): (1) a sleeve is an UPGRADE only if its flip-cut
nominal dMaxDD CI excludes 0 at the family-wise level AND its full-window dSharpe CI is not
significantly negative AND its flip-cut REAL maxDD is shallower in point terms; (2) anything
weaker is at best an OOS HYPOTHESIS (the gold standard: [[F39]] — borderline sleeves die out of
sample); (3) the flip era is a SINGLE regime event (n=1) — no sleeve verdict from this study can
be regime-general; it can only qualify or fail to qualify a candidate for a future OOS test;
(4) short-TIPS sleeves mechanically shorten the bond leg's duration — a duration-matched nominal
control (IEI, 3-7yr Treasuries) is scored alongside, so "TIPS helped" is only claimed if the TIPS
sleeve beats the SAME-SIZE nominal-duration-shortening sleeve (else the effect is just duration,
the F45 lesson).

KNOWN CONSTRUCTIONS (folded in after a 3-lens skeptic panel, 2026-07-07): (a) the same-size IEI
control UNDERCORRECTS duration (IEI ~4.5yr vs STIP/VTIP ~2.5yr), biasing the direct test TOWARD a
TIPS effect — a duration-MATCHED control (IEI sleeve sized x5/3) is therefore the verdict-bearing
comparison, and under it BOTH dMaxDD and dSharpe CIs include 0: the earlier "inflation-carry hint"
was a residual-duration artifact; (b) the mechanical CI-excludes-0 tests use UNROUNDED bootstrap
percentiles (a verdict must never hinge on display rounding) and knife-edge bounds (<0.1pp) are
labeled as such; (c) 2022+ was a REAL-YIELD-driven shock — the structurally worst case for
marked-to-market TIPS, whose MTM hedges inflation-EXPECTATIONS moves; only the carry channel got
tested here, so the null cannot rule out value in an expectations-led inflation event; (d) the
neg-corr 2004-2021 cut is printed (the sleeves' cost side) — H42's original wording ("no
significant Sharpe cost in the negative-corr cut") is checked there alongside the full-window
criterion; (e) monthly CPI is stamped at month-end ~2-6wk before real-world publication — a
symmetric, measurement-only convention (orderings survive a 1-month lag probe).

Deterministic (seed=0); fetches once to /tmp caches; end date pinned 2026-06-30.

    venv/bin/python tools/tips_sleeve_study.py [--json out.json] [--selfcheck]
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
import bond_ladder_study as bls   # noqa: E402  load_cpi (FRED CPIAUCSL cache)

CACHE_PX = "/tmp/tips_sleeve_prices.csv"
TICKERS = ["SPY", "IEF", "TIP", "STIP", "VTIP", "IEI"]
END = "2026-06-30"
ANN = 252
BLOCK = 20
B = 5000
SEED = 0
FAMILY = 12                        # 4 sleeve sizes x 3 TIPS variants (pre-registered family)
SLEEVES = [0.05, 0.10, 0.15, 0.20]
CUTS = [("full", None, None),
        ("neg_corr 2004-2021", None, "2021-12-31"),
        ("flip 2022+", "2022-01-01", None),
        ("shock 2021H2-2023", "2021-06-01", "2023-12-31")]


# ── data ──────────────────────────────────────────────────────────────────────
def load_px():
    if os.path.exists(CACHE_PX):
        cached = pd.read_csv(CACHE_PX, index_col=0, parse_dates=True)
        if all(t in cached.columns for t in TICKERS):
            return cached
    import yfinance as yf
    raw = yf.download(TICKERS, start="2003-12-01", end=END, interval="1d",
                      progress=False, auto_adjust=True)["Close"]
    raw.to_csv(CACHE_PX)
    return raw


# ── metrics (daily) ───────────────────────────────────────────────────────────
def pm(r):
    r = np.asarray(pd.Series(r).dropna(), dtype=float)
    n = len(r)
    if n < 5 or r.std() == 0:
        return dict(n=n, cagr=0.0, vol=0.0, sharpe=0.0, maxdd=0.0)
    eq = np.cumprod(1.0 + r)
    cagr = eq[-1] ** (ANN / n) - 1.0 if eq[-1] > 0 else -1.0
    dd = (eq / np.maximum.accumulate(eq) - 1.0).min()
    return dict(n=n, cagr=round(cagr * 100, 2), vol=round(r.std() * math.sqrt(ANN) * 100, 2),
                sharpe=round(r.mean() / r.std() * math.sqrt(ANN), 3), maxdd=round(dd * 100, 1))


def real_stats(r, cpi):
    """REAL (CPI-deflated) CAGR%/maxDD% of a daily nominal return series (monthly CPI ffilled)."""
    eq = (1.0 + r).cumprod()
    cpi_d = cpi.reindex(eq.index, method="ffill")
    req = (eq / cpi_d).dropna()
    if len(req) < 5:
        return dict(real_cagr=None, real_maxdd=None)
    cagr = (req.iloc[-1] / req.iloc[0]) ** (ANN / (len(req) - 1)) - 1.0
    dd = (req / req.cummax() - 1.0).min()
    return dict(real_cagr=round(cagr * 100, 2), real_maxdd=round(dd * 100, 1))


def _m2(r):
    eq = np.cumprod(1.0 + r)
    dd = (eq / np.maximum.accumulate(eq) - 1.0).min()
    sh = r.mean() / r.std() * math.sqrt(ANN) if r.std() > 0 else 0.0
    return sh, dd * 100


def paired_boot(a, b, block=BLOCK, nboot=B, seed=SEED, family=FAMILY):
    """Paired block bootstrap of (a − b): 95% and family-wise (Bonferroni x`family`) CIs."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    n = len(a)
    nb = max(1, n // block)
    rng = np.random.default_rng(seed)
    ds, dd = np.empty(nboot), np.empty(nboot)
    for i in range(nboot):
        st = rng.integers(0, n - block + 1, size=nb)
        sa = np.concatenate([a[s:s + block] for s in st])
        sb = np.concatenate([b[s:s + block] for s in st])
        sha, dda = _m2(sa)
        shb, ddb = _m2(sb)
        ds[i], dd[i] = sha - shb, dda - ddb
    pc = lambda x, q, nd=3: [round(float(v), nd) for v in np.percentile(x, q)]
    afw = 0.05 / family / 2 * 100
    return dict(dSharpe=pc(ds, [2.5, 97.5]), dMaxDD=pc(dd, [2.5, 97.5], 1),
                dMaxDD_fw=pc(dd, [afw, 100 - afw], 1),
                # UNROUNDED bounds for mechanical CI tests — a verdict must never hinge on
                # display rounding (panel-forced: the ws=10 raw lower bound was +0.0049)
                dMaxDD_lo_raw=float(np.percentile(dd, 2.5)),
                dSharpe_lo_raw=float(np.percentile(ds, 2.5)),
                prob_dd_shallower=round(float(np.mean(dd > 0)), 3))


# ── the sweep ─────────────────────────────────────────────────────────────────
def build_returns():
    px = load_px()
    return {t: px[t].dropna().pct_change().dropna() for t in TICKERS}


def mix(rets, ws, sleeve_ticker):
    """40% SPY + (60−ws)% IEF + ws% sleeve, daily-rebalanced, on the sleeve's aligned life."""
    cols = {"e": rets["SPY"], "b": rets["IEF"]}
    if sleeve_ticker is not None:
        cols["s"] = rets[sleeve_ticker]
    df = pd.DataFrame(cols).dropna()
    base = 0.4 * df["e"] + 0.6 * df["b"]
    if sleeve_ticker is None:
        return df.index, base, base
    sleeved = 0.4 * df["e"] + (0.6 - ws) * df["b"] + ws * df["s"]
    return df.index, base, sleeved


def run_sweep(rets, cpi):
    out = {}
    boots = {}
    for var in ["TIP", "STIP", "VTIP", "IEI"]:        # IEI = duration-shortening nominal CONTROL
        vrows = []
        for ws in SLEEVES:
            idx, base, sleeved = mix(rets, ws, var)
            row = dict(ws=int(ws * 100), span=f"{idx[0].date()}->{idx[-1].date()}")
            for cut, a, b in CUTS:
                sl = sleeved.loc[a:b]
                ba = base.loc[a:b]
                if len(sl) < 100:
                    continue
                m = pm(sl)
                m.update(real_stats(sl, cpi))
                mb = pm(ba)
                mb.update(real_stats(ba, cpi))
                row[cut] = dict(sleeved=m, base=mb)
            vrows.append(row)
            # bootstrap the pre-registered comparisons for the 10% + 20% sizes (keeps runtime sane;
            # the read only needs the family-wise test on whichever size looks best)
            if ws in (0.10, 0.20):
                key = f"{var}_{int(ws*100)}"
                boots[key] = {}
                for cut, a, b in [("full", None, None), ("flip 2022+", "2022-01-01", None)]:
                    sl = sleeved.loc[a:b]
                    ba = base.loc[a:b]
                    if len(sl) >= 100:
                        boots[key][cut] = paired_boot(sl.values, ba.values)
        out[var] = vrows
    # the DIRECT duration-honesty test (pre-registered read #4): paired boot of the short-TIPS
    # sleeve MINUS a nominal (IEI) sleeve on the flip cut. TWO controls (panel-forced):
    #   same-size   — duration-CONFOUNDED (IEI ~4.5yr vs VTIP ~2.5yr: replacing IEF with VTIP
    #                 sheds ~5/3 as much duration as the same-size IEI swap), biased TOWARD TIPS;
    #   dur-matched — IEI sleeve sized x5/3 so both swaps shed the same portfolio duration.
    # The TIPS claim exists only if the DUR-MATCHED difference excludes 0.
    tips_vs_dur = {}
    for ws in (0.10, 0.20):
        _, _, sv = mix(rets, ws, "VTIP")
        _, _, si = mix(rets, ws, "IEI")
        _, _, sim = mix(rets, min(ws * 5 / 3, 0.6), "IEI")
        j = pd.concat([sv.rename("v"), si.rename("i"), sim.rename("m")], axis=1).dropna().loc["2022-01-01":]
        tips_vs_dur[f"VTIP{int(ws*100)}_minus_IEI{int(ws*100)} (duration-confounded)"] = \
            paired_boot(j["v"].values, j["i"].values)
        tips_vs_dur[f"VTIP{int(ws*100)}_minus_IEI{round(ws*500/3):d} (dur-MATCHED)"] = \
            paired_boot(j["v"].values, j["m"].values)
    return out, boots, tips_vs_dur


# ── report ────────────────────────────────────────────────────────────────────
def fmt(sweep, boots):
    L = []
    for var, rows in sweep.items():
        tag = "duration CONTROL (nominal 3-7yr)" if var == "IEI" else "TIPS variant"
        L.append(f"== {var} ({tag}; span {rows[0]['span']}) ==")
        L.append(f"   {'ws%':>4} {'cut':22} {'Sharpe':>7} {'maxDD%':>7} {'realDD%':>8} | {'base Sh':>8} {'base DD':>8} {'base rDD':>9}")
        for row in rows:
            for cut in ["full", "neg_corr 2004-2021", "flip 2022+", "shock 2021H2-2023"]:
                if cut not in row:
                    continue
                s, b = row[cut]["sleeved"], row[cut]["base"]
                rd = f"{s['real_maxdd']:8.1f}" if s.get("real_maxdd") is not None else "     n/a"
                brd = f"{b['real_maxdd']:9.1f}" if b.get("real_maxdd") is not None else "      n/a"
                L.append(f"   {row['ws']:4d} {cut:22} {s['sharpe']:7.3f} {s['maxdd']:7.1f} {rd} | "
                         f"{b['sharpe']:8.3f} {b['maxdd']:8.1f} {brd}")
        L.append("")
    L.append("== PAIRED BOOTSTRAP (sleeved − base; 95% CI + family-wise x12 on dMaxDD) ==")
    for key, cuts in boots.items():
        for cut, bo in cuts.items():
            L.append(f"   {key:9} {cut:12} dSharpe CI[{bo['dSharpe'][0]:+.3f},{bo['dSharpe'][1]:+.3f}]  "
                     f"dMaxDD CI[{bo['dMaxDD'][0]:+.2f},{bo['dMaxDD'][1]:+.2f}]  "
                     f"fw x12 [{bo['dMaxDD_fw'][0]:+.2f},{bo['dMaxDD_fw'][1]:+.2f}]  "
                     f"P(shallower)={bo['prob_dd_shallower']*100:.0f}%")
    return "\n".join(L)


def verdict(sweep, boots):
    """Apply the pre-registered reads mechanically."""
    def flip_row(var, ws):
        row = next(r for r in sweep[var] if r["ws"] == ws)
        return row.get("flip 2022+")
    # the read: any sleeve whose flip dMaxDD fw-CI excludes 0 AND full dSharpe not sig-negative
    passes, hypotheses = [], []
    for key, cuts in boots.items():
        var, ws = key.rsplit("_", 1)
        if var == "IEI":
            continue
        flip, full = cuts.get("flip 2022+"), cuts.get("full")
        if not flip or not full:
            continue
        fr = flip_row(var, int(ws))
        real_better = (fr and fr["sleeved"].get("real_maxdd") is not None
                       and fr["sleeved"]["real_maxdd"] > fr["base"]["real_maxdd"])
        fw_excl = flip["dMaxDD_fw"][0] > 0
        ci_excl = flip["dMaxDD_lo_raw"] > 0            # UNROUNDED (panel-forced)
        # faithful to the pre-registration: "full-window dSharpe CI not significantly negative"
        # = the CI is not entirely below 0 (no post-hoc tolerance branch)
        sharpe_ok = full["dSharpe"][1] >= 0
        if fw_excl and sharpe_ok and real_better:
            passes.append(key)
        elif ci_excl and real_better:
            hypotheses.append(key)
    return passes, hypotheses


def selfcheck(rets, cpi):
    # sleeve accounting identity: a ws=0 sleeve must equal the base EXACTLY (panel-forced fix:
    # the first draft's assertion here was vacuous — `... or True`)
    _, b0, s0 = mix(rets, 0.0, "TIP")
    assert np.allclose(b0.values, s0.values), "ws=0 sleeve must equal the base exactly"
    ref = pd.DataFrame({"e": rets["SPY"], "b": rets["IEF"], "s": rets["TIP"]}).dropna()
    assert np.allclose(b0.values, (0.4 * ref["e"] + 0.6 * ref["b"]).values)
    # duration ordering through the 2022 shock: VTIP (0-5yr) shallower than TIP (~6.7yr) than IEF (~7.5yr)
    dd = {}
    for t in ["VTIP", "TIP", "IEF"]:
        r = rets[t].loc["2021-06-01":"2023-12-31"]
        eq = (1 + r).cumprod()
        dd[t] = float((eq / eq.cummax() - 1).min())
    assert dd["VTIP"] > dd["TIP"] > dd["IEF"], f"2022 duration ordering violated: {dd}"
    assert cpi is not None and len(cpi) > 500
    print(f"[selfcheck OK] ws=0 sleeve == base exactly; 2022 shock DD ordering VTIP {dd['VTIP']*100:.1f}% > "
          f"TIP {dd['TIP']*100:.1f}% > IEF {dd['IEF']*100:.1f}% (duration monotone); CPI loaded (n={len(cpi)}).")


def main():
    ap = argparse.ArgumentParser(description="study #14 — TIPS sleeve inside the static mix")
    ap.add_argument("--json", metavar="PATH")
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    rets = build_returns()
    cpi = bls.load_cpi()
    if cpi is None:
        sys.exit("FRED CPI unavailable — the real-terms read needs it; retry with network.")
    if a.selfcheck:
        selfcheck(rets, cpi)
        return
    sweep, boots, tips_vs_dur = run_sweep(rets, cpi)
    passes, hypotheses = verdict(sweep, boots)
    print("=" * 100)
    print("STUDY #14 — a TIPS SLEEVE inside the recommended static mix (40/60), under study #5 discipline")
    print("=" * 100)
    print(fmt(sweep, boots))
    print()
    print("-- PRE-REGISTERED READS, APPLIED MECHANICALLY --")
    print(f"   UPGRADES (flip dMaxDD family-wise-significant + Sharpe not hurt + real DD shallower): "
          f"{passes or 'NONE'}")
    print(f"   OOS HYPOTHESES at best (unadjusted CI only — the F39 gold tier): {hypotheses or 'NONE'}")
    print("   duration honesty (read #4) — DIRECT paired boots, VTIP sleeve MINUS IEI sleeve, flip cut")
    print("   (the dur-MATCHED rows are verdict-bearing; same-size rows are duration-confounded by construction):")
    for key, bo in tips_vs_dur.items():
        matched = "dur-MATCHED" in key
        dd_excl = bo["dMaxDD_lo_raw"] > 0                                # unrounded (panel-forced)
        sh_excl = bo["dSharpe_lo_raw"] > 0
        knife = abs(bo["dMaxDD_lo_raw"]) < 0.1
        if matched:
            verdict_s = ("TIPS-specific effect beyond duration" if (dd_excl or sh_excl)
                         else "indistinguishable from plain duration-shortening (the F45 lesson)")
        else:
            verdict_s = "duration-confounded — see the dur-MATCHED row"
        if knife:
            verdict_s += " [knife-edge bound: raw lo %+.4f — block-sensitive]" % bo["dMaxDD_lo_raw"]
        print(f"     {key}: dMaxDD CI[{bo['dMaxDD'][0]:+.2f},{bo['dMaxDD'][1]:+.2f}]  "
              f"dSharpe CI[{bo['dSharpe'][0]:+.3f},{bo['dSharpe'][1]:+.3f}]  -> {verdict_s}")
    print("=" * 100)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(dict(sweep=sweep, bootstraps=boots, passes=passes, hypotheses=hypotheses,
                           tips_vs_duration_control=tips_vs_dur), f, indent=2, default=str)
        print(f"[wrote {a.json}]")


if __name__ == "__main__":
    main()
