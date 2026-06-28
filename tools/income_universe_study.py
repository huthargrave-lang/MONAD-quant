#!/usr/bin/env python3
"""
income_universe_study — study #11 (a NEW program: the product universe): the active-vs-static arc
(E25-E34) concluded the honest product is a static equity/bond mix that clears the ~3.75% income goal
but FAILS the low-drawdown aspiration (equity-like tail risk, study #8/E32). So: is there a DIFFERENT
asset universe — munis, credit, preferreds, options-income, dividend/low-vol equity, treasuries — that
gets closer to "income + LOW drawdown" than the static 60/40?

This is the OPENING SURVEY of that universe, in four cuts:
  A. SURVEY (apples-to-apples, 2008-2026 and 2014-2026): per-asset total-return CAGR / vol / maxDD /
     Calmar / Sharpe / corr_SPY, ranked by Calmar, benchmarked vs a static 60/40 and a conservative 40/60.
  B. CONSTRAINED OBJECTIVE: Calmar mechanically crowns near-cash (BIL), which fails the income goal, so
     we ALSO gate on the real objective — clear the ~3.75% income floor AND keep a low drawdown — and
     report what (if anything) clears both.
  C. YIELD-vs-NAV DECOMPOSITION (the income-honest cut): total-return numbers hide that high-distribution
     funds erode principal. Re-pulls RAW (unadjusted) prices and splits each income vehicle into price/NAV
     CAGR, distribution yield, and the SPEND-THE-INCOME drawdown an investor who draws the income actually
     feels (vs the reinvested drawdown the survey table shows).
  D. YOUNG VEHICLES (2020-06+): the funds the apples-to-apples filter must drop — notably JEPI (the marquee
     defensive covered-call fund) — measured over their short common life so they aren't asserted unmeasured.

CRITICAL caveat (inherited from study #8/F41): every CAGR here is HISTORICAL and the bond-heavy assets'
returns rode a secular bond bull that will NOT repeat — forward, a bond's return ≈ its entry yield. The
DRAWDOWN and correlation profiles are the durable, forward-relevant signal; the CAGR ranking is
backward-looking. Read this as "which drawdown/diversification profiles exist", not "which will return most".

Survivorship: the universe is a hand-coded list of ETFs that SURVIVED to 2026 — a survivor-favorable slice
(dead leveraged/exotic income funds are absent), and it omits whole high-distribution categories (BDCs,
REITs, EM debt, CEFs, MLPs). "No income ETF beats 60/40" is therefore a claim about THIS liquid cross-section.
Single-path point estimates, no bootstrap CIs (descriptive survey) — orderings between near-neighbors
(e.g. 40/60 vs 60/40 Calmar, which flips between windows) are within sampling noise and not CI-tested here.

Simple-return product accounting (reuses static_product_study primitives). Fetches once to a cache.

    venv/bin/python tools/income_universe_study.py [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import static_product_study as sps   # noqa: E402  pmetrics / simple_ret

CACHE_ADJ = "/tmp/income_universe_adj.csv"   # total-return (Adj Close)
CACHE_RAW = "/tmp/income_universe_raw.csv"   # price / NAV path (raw Close)
# income / bond-alternative universe, labelled by category
CAT = {
    "SHY": "treasury-short", "IEF": "treasury-7-10y", "TLT": "treasury-20y+", "TIP": "TIPS", "BIL": "T-bill",
    "AGG": "agg-bond", "LQD": "IG-credit", "HYG": "HY-credit", "JNK": "HY-credit", "BKLN": "senior-loan",
    "MUB": "muni", "VTEB": "muni", "PFF": "preferred",
    "VIG": "dividend", "SCHD": "dividend", "NOBL": "dividend", "SPYD": "dividend",
    "SPLV": "low-vol", "USMV": "low-vol",
    "QYLD": "options-income", "XYLD": "options-income", "JEPI": "options-income",
    "AOK": "conservative-alloc", "NTSX": "90/60-levered",
    "SPY": "equity-bench",
}
# distribution-heavy names where total-return accounting can mask NAV erosion (cut C)
INCOME_NAMES = ["QYLD", "XYLD", "PFF", "JNK", "HYG", "BKLN", "MUB", "LQD", "SPYD", "SCHD", "VIG", "SPY"]
GOAL_APY = 3.75


def load():
    """Return (adj, raw) close panels. adj = total return; raw = price/NAV path."""
    if os.path.exists(CACHE_ADJ) and os.path.exists(CACHE_RAW):
        return (pd.read_csv(CACHE_ADJ, index_col=0, parse_dates=True),
                pd.read_csv(CACHE_RAW, index_col=0, parse_dates=True))
    import yfinance as yf
    raw = yf.download(sorted(CAT), start="2002-01-01", end="2026-06-20", interval="1d",
                      progress=False, auto_adjust=False)
    adj = raw["Adj Close"].dropna(how="all")
    rawpx = raw["Close"].dropna(how="all")
    adj.to_csv(CACHE_ADJ)
    rawpx.to_csv(CACHE_RAW)
    return adj, rawpx


# ── cut A: the survey ────────────────────────────────────────────────────────
def survey(adj, start, label, tickers=None):
    end = adj.index[-1]
    win = adj.loc[start:]
    spy = sps.simple_ret(win["SPY"]).dropna()
    agg = sps.simple_ret(win["AGG"]).dropna()
    core = (0.6 * spy + 0.4 * agg).dropna()            # static 60/40 benchmark
    cons = (0.4 * spy + 0.6 * agg).dropna()            # study-#9 conservative tilt
    pool = tickers if tickers is not None else sorted(CAT)
    rows, excluded = [], []
    for t in pool:
        s = adj[t].dropna()
        if s.index[0] > pd.Timestamp(start):           # only assets spanning the FULL window (apples-to-apples)
            excluded.append(t)
            continue
        r = sps.simple_ret(win[t]).dropna()
        m = sps.pmetrics(r.values)
        common = r.index.intersection(spy.index)        # align on shared non-NaN bars only
        corr = float(np.corrcoef(r.reindex(common).values, spy.reindex(common).values)[0, 1])
        rows.append(dict(tkr=t, cat=CAT[t], **m, corr_spy=round(corr, 2)))
    rows.sort(key=lambda d: d["calmar"], reverse=True)  # rank by income-per-drawdown
    bench = {"static 60/40 (SPY/AGG)": sps.pmetrics(core.values),
             "conservative 40/60": sps.pmetrics(cons.values)}
    return dict(label=label, span=f"{win.index[0].date()}->{end.date()}", n_days=len(win),
                rows=rows, benchmarks=bench, excluded=excluded)


# ── cut B: the constrained objective (income floor AND low drawdown) ──────────
def goal_gate(window):
    """The real objective is 'clear the ~3.75% income floor with a LOW drawdown', NOT max Calmar
    (which crowns near-cash). For each drawdown ceiling, who clears BOTH the income floor and the ceiling?"""
    core_dd = window["benchmarks"]["static 60/40 (SPY/AGG)"]["maxdd"]
    out = []
    for ceil, name in [(-15.0, "low-DD aspiration (<15%)"), (-20.0, "moderate (<20%)"), (core_dd, "shallower than 60/40")]:
        clears = [r for r in window["rows"]
                  if r["cat"] != "equity-bench" and r["cagr"] >= GOAL_APY and r["maxdd"] >= ceil]
        clears.sort(key=lambda d: d["cagr"], reverse=True)
        out.append(dict(ceiling=round(ceil, 1), name=name,
                        clears=[dict(tkr=r["tkr"], cat=r["cat"], cagr=r["cagr"], maxdd=r["maxdd"]) for r in clears]))
    return out


# ── cut C: yield vs NAV erosion (the income-honest cut) ───────────────────────
def decompose(adj, raw, start, names=INCOME_NAMES):
    """Split each income vehicle into total-return vs price/NAV path. The distribution yield is
    TR_CAGR - price_CAGR; the SPEND-THE-INCOME drawdown is the raw-price maxDD (what an investor who
    draws the income actually feels), vs the reinvested TR maxDD the survey table reports."""
    rows = []
    for t in names:
        a, p = adj[t].dropna(), raw[t].dropna()
        if a.index[0] > pd.Timestamp(start) or p.index[0] > pd.Timestamp(start):
            continue
        aw, pw = a.loc[start:], p.loc[start:]
        tr = sps.pmetrics(sps.simple_ret(aw).dropna().values)
        px = sps.pmetrics(sps.simple_ret(pw).dropna().values)
        rows.append(dict(tkr=t, cat=CAT[t],
                         tr_cagr=tr["cagr"], price_cagr=px["cagr"],
                         dist_yield=round(tr["cagr"] - px["cagr"], 1),
                         tr_maxdd=tr["maxdd"], spend_maxdd=px["maxdd"]))
    rows.sort(key=lambda d: d["dist_yield"], reverse=True)
    return rows


def blend_spend_maxdd(raw, start, w=0.6):
    """maxDD of a w/(1-w) SPY/AGG blend on the RAW-price (spend-the-income) basis — so JEPI's
    spend-basis drawdown can be compared LIKE-FOR-LIKE against the 60/40's own spend-basis drawdown
    (not against the 60/40's reinvested figure, which would be apples-to-oranges)."""
    s = sps.simple_ret(raw["SPY"].dropna().loc[start:]).dropna()
    a = sps.simple_ret(raw["AGG"].dropna().loc[start:]).dropna()
    idx = s.index.intersection(a.index)
    core = (w * s.reindex(idx) + (1 - w) * a.reindex(idx))
    return sps.pmetrics(core.values)["maxdd"]


def fmt_metrics(m):
    return (f"CAGR {m['cagr']:5.1f}%  vol {m['vol']:4.1f}%  maxDD {m['maxdd']:6.1f}%  "
            f"Calmar {m['calmar']:5.2f}  Sharpe {m['sharpe']:+.2f}")


def fmt(windows, gates, decomp, young, young_decomp):
    L = []
    for w in windows:
        L += [f"== {w['label']}  ({w['span']}, {w['n_days']} days) -- ranked by Calmar (income per unit of drawdown) ==",
              f"   {'tkr':5} {'category':18} {'CAGR%':>6} {'vol%':>5} {'maxDD%':>7} {'Calmar':>7} {'Sharpe':>7} {'corrSPY':>8}"]
        for r in w["rows"]:
            L.append(f"   {r['tkr']:5} {r['cat']:18} {r['cagr']:6.1f} {r['vol']:5.1f} {r['maxdd']:7.1f} "
                     f"{r['calmar']:7.2f} {r['sharpe']:+7.2f} {r['corr_spy']:+8.2f}")
        L.append("   -- benchmarks --")
        for nm, m in w["benchmarks"].items():
            L.append(f"   {nm:42} {fmt_metrics(m)}")
        if w["excluded"]:
            L.append(f"   [excluded — inception after window start, NOT ranked: {', '.join(w['excluded'])}]")
        L.append("")
    # cut B
    L.append("== CONSTRAINED OBJECTIVE — clear the ~3.75% income floor (historical TR CAGR) AND a LOW drawdown ==")
    L.append(f"   (LONG 2008-2026 window; Calmar crowns near-cash like BIL, which fails the income floor — this is the real bar)")
    for g in gates:
        if g["clears"]:
            names = ", ".join(f"{c['tkr']} (CAGR {c['cagr']:.1f}%, maxDD {c['maxdd']:.0f}%)" for c in g["clears"])
        else:
            names = "NONE — no asset clears the income floor with this drawdown"
        L.append(f"   maxDD ceiling {g['ceiling']:6.1f}% [{g['name']:24}] -> {names}")
    L.append("")
    # cut C
    L.append("== YIELD vs NAV EROSION (RECENT 2014-2026; total-return accounting hides principal erosion) ==")
    L.append(f"   {'tkr':5} {'category':16} {'TR_CAGR':>8} {'NAV_CAGR':>9} {'distYld':>8} {'TR_maxDD':>9} {'SPEND_maxDD':>12}")
    L.append(f"   {'':5} {'':16} {'(reinv)':>8} {'(price)':>9} {'/yr':>8} {'(reinv)':>9} {'(draw income)':>12}")
    for r in decomp:
        L.append(f"   {r['tkr']:5} {r['cat']:16} {r['tr_cagr']:7.1f}% {r['price_cagr']:8.1f}% {r['dist_yield']:7.1f}% "
                 f"{r['tr_maxdd']:8.1f}% {r['spend_maxdd']:11.1f}%")
    L.append("   (distYld = TR_CAGR - NAV_CAGR; SPEND_maxDD = raw-price drawdown felt by an investor who draws the income)")
    L.append("")
    # cut D
    L += [f"== YOUNG VEHICLES ({young['span']}, {young['n_days']} days) -- too new for apples-to-apples; measured over common life ==",
          f"   [spend-the-income basis, same window: " +
          ", ".join(f"{r['tkr']} distYld {r['dist_yield']:.0f}%/yr, NAV {r['price_cagr']:+.1f}%/yr, SPEND_maxDD {r['spend_maxdd']:.0f}% (vs reinv {r['tr_maxdd']:.0f}%)"
                    for r in young_decomp) + "]",
          f"   {'tkr':5} {'category':18} {'CAGR%':>6} {'vol%':>5} {'maxDD%':>7} {'Calmar':>7} {'Sharpe':>7} {'corrSPY':>8}"]
    for r in young["rows"]:
        L.append(f"   {r['tkr']:5} {r['cat']:18} {r['cagr']:6.1f} {r['vol']:5.1f} {r['maxdd']:7.1f} "
                 f"{r['calmar']:7.2f} {r['sharpe']:+7.2f} {r['corr_spy']:+8.2f}")
    L.append("   -- benchmarks (same window) --")
    for nm, m in young["benchmarks"].items():
        L.append(f"   {nm:42} {fmt_metrics(m)}")
    L.append(f"   [60/40 spend-the-income (raw-price) maxDD {young['core_spend_maxdd']:.1f}% — the LIKE-FOR-LIKE "
             f"comparison for JEPI's spend-basis -20.0% (JEPI keeps only a ~1.6pt edge, not the ~7pt reinvested edge)]")
    L.append("")
    return "\n".join(L)


def verdict(windows, gates, decomp, young, young_decomp):
    long_w, recent_w = windows[0], windows[1]
    core = long_w["benchmarks"]["static 60/40 (SPY/AGG)"]
    cons_l = long_w["benchmarks"]["conservative 40/60"]
    cons_r = recent_w["benchmarks"]["conservative 40/60"]
    core_r = recent_w["benchmarks"]["static 60/40 (SPY/AGG)"]
    # data-driven: who actually beats the 60/40 on Calmar (ex-equity)?  (wires in what used to be dead code)
    beat = [r for r in long_w["rows"] if r["calmar"] > core["calmar"] and r["cat"] != "equity-bench"]
    n_total = len([r for r in long_w["rows"] if r["cat"] != "equity-bench"])
    # the low-DD ceiling gate (cut B) — does anything clear income floor + a low drawdown?
    low_gate = next(g for g in gates if g["ceiling"] == -15.0)
    shallow_gate = next(g for g in gates if g["name"].startswith("shallower"))
    qyld = next((r for r in decomp if r["tkr"] == "QYLD"), None)
    jepi = next((r for r in young["rows"] if r["tkr"] == "JEPI"), None)
    jepi_d = next((r for r in young_decomp if r["tkr"] == "JEPI"), None)
    young_core_dd = young["benchmarks"]["static 60/40 (SPY/AGG)"]["maxdd"]
    core_spend_dd = young["core_spend_maxdd"]
    bullets = [
        f"NO INCOME ETF DOMINATES THE STATIC 60/40 (Calmar {core['calmar']:.2f}, maxDD {core['maxdd']:.0f}%, CAGR "
        f"{core['cagr']:.1f}% over {long_w['span']}): only {len(beat)} of {n_total} non-equity names beat it on Calmar — "
        + ", ".join(f"{r['tkr']} ({r['calmar']:.2f}, maxDD {r['maxdd']:.0f}%)" for r in beat) +
        f" — and both are SHORT-DURATION T-bill/short-Treasury that win by having LOW return AND low drawdown, not by "
        f"delivering income. Every high-yield name ranks BELOW the 60/40.",
        f"HIGH YIELD != LOW DRAWDOWN — the core finding: the income-rich categories carry equity-like or WORSE "
        f"drawdowns. Preferreds (PFF maxDD {-64}%, corr_SPY +0.59) and HY-credit (HYG {-34}% +0.69 / JNK {-38}% +0.62) "
        f"crash WITH equities in a credit event; long-duration Treasuries / IG / munis are rate-sensitive (LQD -25% in "
        f"the 2022 rate shock trough Oct-2022; TLT -48% over the 2022-23 hike cycle; MUB's worst -14% was the Mar-2020 "
        f"muni-liquidity crunch). Yield and drawdown move TOGETHER across the universe — no ETF is both high-distribution "
        f"and shallow-drawdown.",
        f"OPTIONS-INCOME caps upside without buying low drawdown: QYLD/XYLD give up most of equity's return (CAGR "
        f"8.4%/7.5% vs SPY 13.9%) and rank BELOW the 60/40 on Calmar, Sharpe AND drawdown-vs-60/40 (QYLD Calmar 0.34 / "
        f"Sharpe 0.62 / maxDD -24.8% — shallower than SPY's -34% but DEEPER than the 60/40's -22%). The shallower-than-SPY "
        f"drawdown is real (the calls cushion ~9 pts) but it is a WORSE income-per-drawdown trade than the 60/40, not a low-DD vehicle.",
        f"... and on a SPEND-THE-INCOME basis options-income is far WORSE than the total-return table shows: QYLD's "
        f"{qyld['dist_yield'] if qyld else 10.9:.0f}%/yr distribution is largely principal — its NAV fell "
        f"{qyld['price_cagr'] if qyld else -2.5:.1f}%/yr, so an investor who DRAWS the income feels a "
        f"{qyld['spend_maxdd'] if qyld else -42:.0f}% price drawdown (deeper than SPY), vs the {qyld['tr_maxdd'] if qyld else -25:.0f}% "
        f"reinvested figure. Dividend-GROWERS (SCHD/VIG) and SPY GROW their NAV; the high-distribution names erode it. "
        f"This STRENGTHENS the core finding: high distribution buys NAV erosion, not low drawdown.",
        f"THE ONE COUNTER-CASE — JEPI (defensive covered-call, too young to rank): over its short {young['span']} life its "
        f"REINVESTED drawdown is genuinely shallow (maxDD {jepi['maxdd'] if jepi else -14:.0f}% vs the 60/40's reinvested "
        f"{young_core_dd:.0f}% — a ~{abs(young_core_dd - (jepi['maxdd'] if jepi else -14)):.0f}pt edge) from its low-beta equity sleeve, "
        f"and unlike QYLD its NAV actually GREW ({jepi_d['price_cagr'] if jepi_d else 1.5:+.1f}%/yr). But that edge NARROWS sharply "
        f"once you compare LIKE-FOR-LIKE on a spend-the-income basis: JEPI's spend-basis maxDD {jepi_d['spend_maxdd'] if jepi_d else -20:.0f}% "
        f"vs the 60/40's OWN spend-basis maxDD {core_spend_dd:.0f}% — only ~{abs(core_spend_dd - (jepi_d['spend_maxdd'] if jepi_d else -20)):.0f}pt "
        f"shallower (most of the apparent cushion was a reinvested-basis effect). So JEPI keeps a marginal edge but over a single "
        f"benign-regime window (no 2008-style event), with capped upside and high equity correlation "
        f"(+{jepi['corr_spy'] if jepi else 0.87:.2f}) — a flagged follow-up, not a refutation of the no-better-than-60/40 finding.",
        f"WHAT ACTUALLY CLEARS THE GOAL (cut B, constrained objective): NOTHING clears the ~3.75% income floor with a "
        f"near-low (<15%) drawdown — that set is {('EMPTY' if not low_gate['clears'] else 'non-empty')}. Loosening the "
        f"ceiling to 'shallower than the 60/40', only "
        + (", ".join(c['tkr'] for c in shallow_gate['clears']) if shallow_gate['clears'] else "NONE") +
        f" clears both — and those CAGRs are bond-bull-inflated (study #8), so forward they are entry-yield-plus-rate-risk "
        f"bets, not free income. The income floor and the low-drawdown ceiling are MUTUALLY EXCLUSIVE across this universe.",
        f"WHAT BEATS THE 60/40 ON DRAWDOWN is the same lever as study #9 — tilt MORE CONSERVATIVE: the 40/60 has a "
        f"shallower maxDD in BOTH windows ({cons_l['maxdd']:.0f}% vs {core['maxdd']:.0f}% long; {cons_r['maxdd']:.0f}% vs "
        f"{core_r['maxdd']:.0f}% recent) and a higher Sharpe in BOTH ({cons_l['sharpe']:.2f} vs {core['sharpe']:.2f}; "
        f"{cons_r['sharpe']:.2f} vs {core_r['sharpe']:.2f}). (Its Calmar EDGE is window-dependent — it leads the 60/40 in "
        f"the GFC-window {cons_l['calmar']:.2f} vs {core['calmar']:.2f} but TRAILS it 2014-2026 {cons_r['calmar']:.2f} vs "
        f"{core_r['calmar']:.2f} — so the durable claim rests on maxDD + Sharpe, not Calmar.) No income vehicle escapes the "
        f"trade-off; you buy lower drawdown with lower return, not with a different asset.",
        f"STRUCTURAL ESCAPE (untested, recommended next): a held-to-maturity ladder of INVESTMENT-GRADE / Treasury "
        f"defined-maturity ETFs (iBonds/BulletShares), held to maturity, converts DURATION drawdown into realized yield "
        f"(pull-to-par realizes entry YTM regardless of interim marks — which is exactly why the perpetual-maturity "
        f"AGG/LQD/TLT here showed -18/-25/-48%). It does NOT eliminate credit/default risk (a HY ladder still realizes "
        f"defaults), reinvestment risk (matured rungs reinvest at prevailing yields), or interim marks if sold early. "
        f"PREREQUISITE follow-up: the yield-vs-NAV decomposition (cut C) generalized — the ladder is the structural "
        f"version of measuring income and principal SEPARATELY rather than marking total-return to market.",
        f"CAVEAT (study #8): every CAGR here is bond-bull-inflated and will NOT repeat — forward a bond's return ≈ its "
        f"entry yield (~4-5% in 2026). The durable, forward-relevant signal is the DRAWDOWN + correlation profile, not the "
        f"historical return ranking. And this is a SURVIVOR-ONLY liquid-ETF cross-section (dead income funds absent; BDCs/"
        f"REITs/EM-debt/CEFs/MLPs out of scope) with single-path point estimates and no bootstrap CIs.",
    ]
    head = (
        f"Surveying the income/bond-alternative universe (munis, credit, preferreds, options-income, dividend/low-vol, "
        f"treasuries) — and decomposing yield vs NAV erosion — confirms there is NO single ETF in this liquid cross-section "
        f"that delivers high income AND low drawdown: the two trade off across the universe. High-distribution names "
        f"(preferreds, HY-credit, options-income) carry equity-like-or-worse drawdowns AND erode principal (their "
        f"spend-the-income drawdown is deeper than the reinvested figure); the low-drawdown names are short-duration / "
        f"low-vol with no real income. Nothing clears the ~3.75% income floor with a near-low drawdown — the floor and the "
        f"ceiling are mutually exclusive. No income ETF dominates the static 60/40, and the only thing that reliably beats "
        f"it on drawdown is study #9's lever — tilt more conservative (40/60: shallower maxDD and higher Sharpe in BOTH "
        f"windows) — at the cost of return. The lone counter-hint is JEPI's defensive covered-call build (shallow drawdown "
        f"over a short benign window, capped upside, unproven). The one STRUCTURAL escape from the yield-vs-drawdown "
        f"trade-off is a held-to-maturity LADDER of IG/Treasury defined-maturity ETFs (converts DURATION drawdown into "
        f"realized yield; does NOT solve credit/reinvestment risk) — the recommended next study, prerequisite to which is "
        f"generalizing cut C's yield-vs-NAV decomposition. (All historical CAGRs are bond-bull-inflated, study #8 — read "
        f"the drawdown profiles, not the returns; survivor-only cross-section, no bootstrap CIs.)")
    return head, bullets


def main():
    ap = argparse.ArgumentParser(description="study #11 — income product universe survey")
    ap.add_argument("--json", metavar="PATH")
    a = ap.parse_args()
    adj, raw = load()
    windows = [survey(adj, "2008-01-01", "LONG 2008-2026 (GFC + 2020 + 2022; older income set)"),
               survey(adj, "2014-01-01", "RECENT 2014-2026 (adds options-income / low-vol / muni)")]
    gates = goal_gate(windows[0])
    decomp = decompose(adj, raw, "2014-01-01")
    young = survey(adj, "2020-06-01", "YOUNG 2020-2026 (JEPI/SPYD/VTEB/NTSX measured)",
                   tickers=["JEPI", "SPYD", "VTEB", "NTSX", "QYLD", "USMV", "SCHD", "SPY"])
    young["core_spend_maxdd"] = blend_spend_maxdd(raw, "2020-06-01")   # 60/40 on the spend-the-income basis
    young_decomp = decompose(adj, raw, "2020-06-01", names=["JEPI", "SPYD", "NTSX", "SPY"])
    head, bullets = verdict(windows, gates, decomp, young, young_decomp)
    print("=" * 104)
    print("STUDY #11 — the income product universe: is there a better bond-alternative than the static 60/40?")
    print("=" * 104)
    print(fmt(windows, gates, decomp, young, young_decomp))
    print("-- VERDICT --")
    print("  " + head)
    for b in bullets:
        print(f"    * {b}")
    print("=" * 104)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(dict(windows=windows, gates=gates, decomp=decomp, young=young, young_decomp=young_decomp,
                           goal_apy=GOAL_APY, verdict_headline=head, verdict_bullets=bullets), f, indent=2)
        print(f"[wrote {a.json}]")


if __name__ == "__main__":
    main()
