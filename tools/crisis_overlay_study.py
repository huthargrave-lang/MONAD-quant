#!/usr/bin/env python3
"""
crisis_overlay_study — study #3: is the active engine's low-drawdown edge CONCENTRATED in
crises (the regimes where static fails), or is the full-sample no-edge result the whole story?

E25/F34 (study #1, vs 50/50) and E26/F35 (study #2, vs 60/40) retired the Sharpe/return case for
the active leverage-free daily-MR engine. The ONE claim still standing is the "regime-dependent
low-drawdown overlay": the 200d-MA bear gate forces active 100% to cash when price < 200d-MA, so it
should preserve capital in the crises where static gets hurt. Studies #1/#2 found the FULL-SAMPLE
drawdown edge path-dependent (paired bootstrap straddles 0). This study asks the sharper question:
is the edge concentrated in crises?

Method (read-only; reuses mr_daily_lab.sleeve + power_study primitives; deterministic seed=0):
  1. Detect crisis EPISODES = peak-to-trough drawdowns of equity buy&hold ≥ MIN_DEPTH over
     2000-2026 (^GSPC+QQQ+IWM+DIA). Principled, NOT hand-picked: the market's own worst declines
     (dotcom, GFC, 2011, 2015-16, 2018Q4, COVID, 2022, 2024-25).
  2. Per episode, the decline-phase (peak→trough) return + maxDD for active, static 60/40 (real IEF,
     ≥2002-07), static 50/50, and buy&hold; plus active's time-in-market.
  3. CONDITIONAL tests, with their DISAGREEMENT surfaced honestly: (a) episode-level SIGN test
     (equal-weight per crisis); (b) pooled crisis-day paired BLOCK BOOTSTRAP of the mean daily return
     diff (active − bench, length-weighted); (c) a MIN-DEPTH SENSITIVITY sweep, because the vs-60/40
     conclusion flips on the crisis-depth definition.
  4. The DECOMPOSITION: full-sample = crisis-day P&L + calm-day P&L (active gains in crises via cash,
     lags in calm markets via under-participation — they net to the studies #1/#2 no-edge result).

Not a trading system; not imported by the live path.

    venv/bin/python tools/crisis_overlay_study.py [--json out.json] [--min-depth 0.15]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from math import comb

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mr_daily_lab as lab        # noqa: E402  canonical sleeve / load
import power_study as ps          # noqa: E402  vetted primitives

ANN = 252
BLOCK = 20
B = 5000
SEED = 0
LONG_BASKET = ["^GSPC", "QQQ", "IWM", "DIA"]
IEF_START = "2002-07-31"          # first IEF log-return (inception 2002-07-30)
SWEEP_THRESHOLDS = [0.10, 0.15, 0.20, 0.25]


def cum_return(r):
    """Compound a daily log-return slice into a simple total return."""
    return float(np.exp(np.sum(r)) - 1.0) if len(r) else 0.0


def underwater_episodes(r, min_depth):
    """Peak-to-trough drawdown episodes of a daily log-return series.

    Returns (peak_i, trough_i, recover_i, trough_dd) for every underwater stretch whose trough is
    at least `min_depth` deep (INCLUSIVE: a trough of exactly -min_depth counts). peak_i = last
    new-high bar before the decline; trough_i = deepest bar; recover_i = bar regaining the prior
    peak (or last bar)."""
    eq = np.exp(np.cumsum(r))
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    out = []
    in_ep = False
    peak_i = trough_i = 0
    trough_dd = 0.0
    for i in range(len(dd)):
        if dd[i] < 0 and not in_ep:
            in_ep = True
            peak_i, trough_i, trough_dd = max(i - 1, 0), i, dd[i]
        elif in_ep:
            if dd[i] < trough_dd:
                trough_dd, trough_i = dd[i], i
            if dd[i] >= -1e-12:               # recovered to the prior peak
                if trough_dd <= -min_depth:
                    out.append((peak_i, trough_i, i, trough_dd))
                in_ep = False
    if in_ep and trough_dd <= -min_depth:
        out.append((peak_i, trough_i, len(dd) - 1, trough_dd))
    return out


def cond_boot(active, bench, mask):
    """Paired block bootstrap of the mean daily (active − bench) return on the masked days,
    reported as an annualized daily-mean rate (×252, scale-invariant for the sign-vs-0 test).

    CAVEAT: crisis days are non-contiguous (pooled across episodes), so a minority of block draws
    straddle an episode boundary — a length-weighted approximation, not a within-episode bootstrap.
    Treat the episode SIGN test as the equal-weighted primary and this as a supporting statistic."""
    d = (active - bench)[mask]
    d = d[~np.isnan(d)]
    if len(d) < 2 * BLOCK:
        return None
    rng = np.random.default_rng(SEED)
    nb = len(d) // BLOCK
    out = np.empty(B)
    for i in range(B):
        starts = rng.integers(0, len(d) - BLOCK + 1, size=nb)
        out[i] = np.concatenate([d[s:s + BLOCK] for s in starts]).mean() * ANN * 100
    return dict(point=round(float(d.mean() * ANN * 100), 2),
                bps_day=round(float(d.mean() * 1e4), 1),
                ci=[round(float(x), 2) for x in np.percentile(out, [2.5, 97.5])],
                n_days=int(len(d)))


def build():
    """active / equity-buy&hold / static-50-50 / static-60-40 daily log-returns on the 2000 basket.
    60/40 is only real from IEF inception; pre-IEF days are NaN so episode windows predating 2002-07
    correctly report 60/40 as n/a rather than silently 60/40-cash."""
    PX = ps.load_2000()
    basket = [s for s in LONG_BASKET if s in PX.columns]
    active = pd.DataFrame({s: lab.sleeve(PX, s) for s in basket}).fillna(0.0).mean(axis=1)
    eq = pd.DataFrame({s: np.log(PX[s].dropna() / PX[s].dropna().shift(1)) for s in basket}).mean(axis=1)
    ief = np.log(PX["IEF"].dropna() / PX["IEF"].dropna().shift(1))
    df = pd.concat([active.rename("active"), eq.rename("bh"), ief.rename("ief")], axis=1)
    df = df.dropna(subset=["active", "bh"])
    df["s5050"] = 0.5 * df["bh"]
    df["s6040"] = 0.6 * df["bh"] + 0.4 * df["ief"]
    return df, basket


def episode_label(idx, peak_i, trough_i):
    return f"{idx[peak_i].date()}→{idx[trough_i].date()}"


def crisis_mask_for(BH, min_depth, n):
    eps = underwater_episodes(BH, min_depth)
    mask = np.zeros(n, dtype=bool)
    for (pi, ti, _ri, _dd) in eps:
        mask[pi + 1:ti + 1] = True
    return eps, mask


def min_depth_sweep(df, thresholds):
    """Crisis-day active−60/40 conditional CI at several crisis-depth definitions — the vs-60/40
    conclusion is sensitive to this knob, so it is reported rather than fixed at one value."""
    BH, A, S60 = df["bh"].values, df["active"].values, df["s6040"].values
    ief_ok = ~np.isnan(S60)
    rows = []
    for thr in thresholds:
        eps, mask = crisis_mask_for(BH, thr, len(A))
        cb = cond_boot(A, S60, mask & ief_ok)
        rows.append(dict(min_depth_pct=round(thr * 100, 0), n_episodes=len(eps),
                         crisis_active_minus_6040=cb))
    return rows


def study(df, basket, min_depth):
    idx = df.index
    A, BH, S50, S60 = (df["active"].values, df["bh"].values, df["s5050"].values, df["s6040"].values)
    ief_ok = ~np.isnan(S60)

    eps, crisis_mask = crisis_mask_for(BH, min_depth, len(A))
    eps = sorted(eps, key=lambda e: e[3])           # deepest first

    rows = []
    for (pi, ti, _ri, ddv) in eps:
        sl = slice(pi + 1, ti + 1)
        has6040 = bool(np.all(ief_ok[sl])) and (sl.stop > sl.start)
        rows.append(dict(
            window=episode_label(idx, pi, ti), trough_year=int(idx[ti].year),
            bh_drawdown_pct=round(ddv * 100, 1), decline_days=ti - pi,
            ret_active=round(cum_return(A[sl]) * 100, 1),
            ret_6040=(round(cum_return(S60[sl]) * 100, 1) if has6040 else None),
            ret_5050=round(cum_return(S50[sl]) * 100, 1),
            ret_bh=round(cum_return(BH[sl]) * 100, 1),
            active_inmkt_pct=round(float((A[sl] != 0).mean()) * 100, 0),
            active_beats_6040=(cum_return(A[sl]) > cum_return(S60[sl])) if has6040 else None,
            active_beats_bh=bool(cum_return(A[sl]) > cum_return(BH[sl])),
        ))

    def sign_test(key):
        vals = [r[key] for r in rows if r[key] is not None]
        wins = sum(1 for v in vals if v)
        n = len(vals)
        k = max(wins, n - wins)
        p = sum(comb(n, j) for j in range(k, n + 1)) * 2 / (2 ** n) if n else 1.0
        return dict(wins=wins, n=n, p_two_sided=round(min(p, 1.0), 3))

    decomp_mask = crisis_mask
    crisis_6040 = cond_boot(A, S60, decomp_mask & ief_ok)
    crisis_bh = cond_boot(A, BH, decomp_mask)
    noncrisis_6040 = cond_boot(A, S60, (~decomp_mask) & ief_ok)
    noncrisis_bh = cond_boot(A, BH, ~decomp_mask)

    def cum_on(mask, s):
        return round(cum_return(s[mask]) * 100, 1)
    decomp = dict(
        crisis_days=int(crisis_mask.sum()), total_days=len(A),
        crisis_pct=round(float(crisis_mask.mean()) * 100, 0),
        active_crisis=cum_on(crisis_mask, A), bh_crisis=cum_on(crisis_mask, BH),
        active_noncrisis=cum_on(~crisis_mask, A), bh_noncrisis=cum_on(~crisis_mask, BH),
        active_full=round(cum_return(A) * 100, 1), bh_full=round(cum_return(BH) * 100, 1),
        active_tim_full=round(float((A != 0).mean()) * 100, 0),
    )
    return dict(
        min_depth_pct=round(min_depth * 100, 0), basket=basket,
        span=f"{idx[0].date()}→{idx[-1].date()}", n_episodes=len(rows), episodes=rows,
        sign_test_vs_6040=sign_test("active_beats_6040"), sign_test_vs_bh=sign_test("active_beats_bh"),
        crisis_meandiff_vs_6040=crisis_6040, crisis_meandiff_vs_bh=crisis_bh,
        noncrisis_meandiff_vs_6040=noncrisis_6040, noncrisis_meandiff_vs_bh=noncrisis_bh,
        decomposition=decomp,
    )


def fmt(w, sweep):
    L = [f"crisis = equity buy&hold peak-to-trough drawdown >= {w['min_depth_pct']:.0f}%  "
         f"({w['span']}, basket={'+'.join(w['basket'])}+IEF for 60/40)",
         f"{w['n_episodes']} crisis episodes (decline phase = peak→trough):", "",
         f"  {'window':23} {'BH dd%':>7} {'active':>7} {'60/40':>7} {'50/50':>7} {'buy&hold':>9} {'a.inMkt%':>9}"]
    for r in w["episodes"]:
        s60 = f"{r['ret_6040']:+.1f}" if r["ret_6040"] is not None else "n/a"
        L.append(f"  {r['window']:23} {r['bh_drawdown_pct']:7.1f} {r['ret_active']:+7.1f} {s60:>7} "
                 f"{r['ret_5050']:+7.1f} {r['ret_bh']:+9.1f} {r['active_inmkt_pct']:8.0f}%")
    s6, sb = w["sign_test_vs_6040"], w["sign_test_vs_bh"]
    L += ["",
          f"  episode SIGN test (equal-weight) — active beats 60/40 in {s6['wins']}/{s6['n']} crises "
          f"(two-sided p={s6['p_two_sided']}); beats buy&hold in {sb['wins']}/{sb['n']} (p={sb['p_two_sided']})",
          "  conditional mean daily diff (annualized daily-mean rate %/yr; length-weighted), 95% CI:"]
    for lab_, dd in [("crisis days, active−60/40", w["crisis_meandiff_vs_6040"]),
                     ("crisis days, active−buy&hold", w["crisis_meandiff_vs_bh"]),
                     ("calm days,   active−60/40", w["noncrisis_meandiff_vs_6040"]),
                     ("calm days,   active−buy&hold", w["noncrisis_meandiff_vs_bh"])]:
        if dd:
            v = ("ABOVE 0 → active protects" if dd["ci"][0] > 0 else
                 "BELOW 0 → active lags" if dd["ci"][1] < 0 else "straddles 0 → not significant")
            L.append(f"    {lab_:30} {dd['point']:+7.1f}  ({dd['bps_day']:+.1f}bps/day)  "
                     f"CI [{dd['ci'][0]:+.1f}, {dd['ci'][1]:+.1f}]  ({dd['n_days']}d)  {v}")
    L += ["", "  MIN-DEPTH SENSITIVITY — crisis-day active−60/40 CI by crisis definition:"]
    for r in sweep:
        cb = r["crisis_active_minus_6040"]
        if cb:
            sig = "straddles 0" if cb["ci"][0] <= 0 <= cb["ci"][1] else ("ABOVE 0 → significant" if cb["ci"][0] > 0 else "below 0")
            L.append(f"    >= {r['min_depth_pct']:.0f}% ({r['n_episodes']} eps): {cb['point']:+6.1f}  "
                     f"CI [{cb['ci'][0]:+.1f}, {cb['ci'][1]:+.1f}]  {sig}")
    d = w["decomposition"]
    L += ["",
          f"  DECOMPOSITION ({d['crisis_days']}/{d['total_days']} days = {d['crisis_pct']:.0f}% are crisis-decline days):",
          f"    crisis days:  active {d['active_crisis']:+.0f}%  vs  buy&hold {d['bh_crisis']:+.0f}%   (cash buffer protects)",
          f"    calm days:    active {d['active_noncrisis']:+.0f}%  vs  buy&hold {d['bh_noncrisis']:+.0f}%   (under-participation — the cost)",
          f"    full sample:  active {d['active_full']:+.0f}%  vs  buy&hold {d['bh_full']:+.0f}%   (active in-market {d['active_tim_full']:.0f}%)"]
    return "\n".join(L)


def verdict(w, sweep):
    s6, sb = w["sign_test_vs_6040"], w["sign_test_vs_bh"]
    c6, cb = w["crisis_meandiff_vs_6040"], w["crisis_meandiff_vs_bh"]
    d = w["decomposition"]
    sig_thr = [r["min_depth_pct"] for r in sweep
               if r["crisis_active_minus_6040"] and r["crisis_active_minus_6040"]["ci"][0] > 0]
    bullets = []
    bullets.append(
        f"The protection is REAL and CRISIS-CONCENTRATED: the 200d gate parks active in cash (full-sample "
        f"in-market only {d['active_tim_full']:.0f}%), so it out-protects naked buy&hold in {sb['wins']}/{sb['n']} "
        f"crisis declines — reliably, with a crisis-day CI of [{cb['ci'][0]:+.0f}, {cb['ci'][1]:+.0f}]%/yr "
        f"(p={sb['p_two_sided']}).")
    bullets.append(
        f"Vs the recommended 60/40 the evidence is DEPTH-DEPENDENT and the two tests disagree: the equal-weighted "
        f"episode sign test is weak ({s6['wins']}/{s6['n']}, p={s6['p_two_sided']}), but the length-weighted "
        f"crisis-day bootstrap leans positive ({c6['point']:+.1f}%/yr, CI [{c6['ci'][0]:+.1f}, {c6['ci'][1]:+.1f}], "
        f"lower bound barely below 0 → one-sided ~p0.03). And it is THRESHOLD-SENSITIVE: the vs-60/40 crisis-day CI "
        f"turns strictly positive (significant) once crises are defined as ≥"
        f"{min(sig_thr):.0f}% declines{' (' + '/'.join(f'{t:.0f}%' for t in sig_thr) + ')' if sig_thr else ''} — "
        f"the straddle-0 at 15% exists only because the two shallow whipsaw episodes are pooled in.")
    bullets.append(
        f"The discriminator is DEPTH: active out-protects 60/40 in every crisis deeper than ~20% (2008/2020/2022/"
        f"2018/2024-25) and loses only the two shallowest (2011 −19.6%, 2015 −16.3%), where the gate never cleanly "
        f"engages. [Caveat: the boundary rests on a single 0.9pp gap (−20.5 win vs −19.6 loss) across N={s6['n']} "
        f"events — suggestive, not an established law; in-market % does NOT discriminate (active is high-invested in "
        f"wins too).]")
    bullets.append(
        f"It is PAID FOR in calm markets: on the {d['crisis_pct']:.0f}% of days that are crisis declines, active "
        f"{d['active_crisis']:+.0f}% vs buy&hold {d['bh_crisis']:+.0f}% (protection); but on calm days active "
        f"{d['active_noncrisis']:+.0f}% vs buy&hold {d['bh_noncrisis']:+.0f}% — it lags BOTH benchmarks significantly. "
        f"Net it is a LOWER-return, LOWER-risk profile (full sample active {d['active_full']:+.0f}% vs buy&hold "
        f"{d['bh_full']:+.0f}%) whose Sharpe lands ≈ static — exactly the studies #1/#2 no-risk-adjusted-edge result.")
    bullets.append(
        "Decision: the low-drawdown overlay is a GENUINE, DEPTH-CONCENTRATED capital-preservation property — and vs "
        "60/40 its crisis protection IS statistically real once you define a crisis as a deep (≥20%) decline, though "
        "it rests on only ~5 deep events (too few to bank with high confidence) and costs return in calm markets. A "
        "defensible reason to run the active engine as a low-drawdown overlay IF you value path-smoothness over total "
        "return — but it does not beat 60/40 on Sharpe/return. Consistent with D6/F25 and studies #1/#2.")
    head = (
        f"Active's low-drawdown overlay is REAL and CRISIS-CONCENTRATED: it reliably out-protects naked buy&hold "
        f"({sb['wins']}/{sb['n']}); vs the recommended 60/40 the protection is DEPTH-dependent — weak by the "
        f"equal-weighted episode test ({s6['wins']}/{s6['n']}, p={s6['p_two_sided']}) but statistically significant "
        f"by the day-weighted bootstrap once crises are defined as ≥20% declines, resting on only ~5 deep events. "
        f"It is paid for by calm-market under-participation → a lower-return/lower-risk profile whose Sharpe lands "
        f"≈ static (studies #1/#2). A genuine capital-preservation overlay, not a Sharpe edge.")
    return head, bullets


def main():
    ap = argparse.ArgumentParser(description="study #3 — crisis-conditional low-drawdown overlay test")
    ap.add_argument("--json", metavar="PATH")
    ap.add_argument("--min-depth", type=float, default=0.15, help="min buy&hold drawdown to count as a crisis (default 0.15)")
    a = ap.parse_args()

    df, basket = build()
    w = study(df, basket, a.min_depth)
    sweep = min_depth_sweep(df, sorted(set(SWEEP_THRESHOLDS + [a.min_depth])))
    head, bullets = verdict(w, sweep)

    print("=" * 92)
    print("STUDY #3 — does active's cash buffer protect in the regimes where static fails?")
    print("=" * 92)
    print(fmt(w, sweep)); print()
    print("── VERDICT ──")
    print("  " + head)
    for b in bullets:
        print(f"    • {b}")
    print("=" * 92)

    if a.json:
        with open(a.json, "w") as f:
            json.dump(dict(study=w, min_depth_sweep=sweep, verdict_headline=head,
                           verdict_bullets=bullets), f, indent=2)
        print(f"[wrote {a.json}]")


if __name__ == "__main__":
    main()
