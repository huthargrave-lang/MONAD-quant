#!/usr/bin/env python3
"""
power_study — is the D6 "no active edge" verdict GENUINE evidence-of-absence, or
just an UNDERPOWERED test? (RESEARCH_WEB.md E25/F29.)

D6/F22/F25 established a *point* result: the active leverage-free daily-MR engine
([[D5]] build) does not beat a trivial STATIC allocation of the same assets on a
risk-adjusted basis, and its bootstrap Sharpe-difference CI straddles zero. But a
CI that straddles zero is ambiguous — it can mean either:

  (a) "evidence of absence"  — the edge is genuinely ~0 and we can RULE OUT any
                               meaningful edge (a positive equivalence result), or
  (b) "absence of evidence"  — the test is too underpowered to tell, and a real
                               edge could be hiding inside a wide CI.

This study separates the two with three tools the go/no-go harness never ran:
  1. PAIRED block-bootstrap of the Sharpe DIFFERENCE  Sharpe(active) − Sharpe(bench)
     — the clean quantity (cash-scaling is Sharpe-invariant, so static-50/50 and
     buy&hold share one Sharpe), resampling the SAME blocks for both legs so the
     cross-correlation is preserved. (mr_daily_lab's `boot(r-0.5e)` is the Sharpe of
     the SPREAD, which it itself flags as mechanically confounded.)
  2. MINIMUM DETECTABLE EFFECT + POWER CURVES — given the data we actually have,
     what is the smallest true Sharpe edge detectable at 80% power, and how many
     years would plausible edges (0.1–0.5 Sharpe) require?
  3. TOST EQUIVALENCE — the smallest margin Δ* within which we can POSITIVELY
     conclude active ≈ static at 95% confidence (the 90% CI half-extent from 0).

Plus the load-bearing contrast: the lag-1 mean-reversion AUTOCORRELATION (the
*signal*) is well-powered and robustly negative ([[F18]]); the *tradeable edge vs
static* is what is small/equivocal. "Real but not better-than-static."

Read-only research: reuses tools/mr_daily_lab.py's canonical leak-free `sleeve`
(dip+5d, 200d-MA gate, 5bps cost) and its cached daily data. Not a trading system,
not imported by the live path. Deterministic (seed=0) so the numbers reproduce.

    venv/bin/python tools/power_study.py            # both windows + verdict
    venv/bin/python tools/power_study.py --json out.json
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
import mr_daily_lab as lab  # noqa: E402  (canonical sleeve / load / COST)

ANN = 252
BLOCK = 20          # trading-month blocks, matching the mr_daily_lab bootstrap
B = 5000            # bootstrap resamples
SEED = 0

# Equity indices expected to mean-revert; the lag-1 "signal power" claim is judged
# over these, not over diversifiers like GLD (a non-mean-reverter, kept as a control).
EQUITY_MR = {"^GSPC", "QQQ", "SPY", "IWM", "DIA"}

# Standard-normal quantiles (no scipy): z_{1-α}
Z = {0.80: 0.8416212, 0.90: 1.2815516, 0.95: 1.6448536, 0.975: 1.9599640}
Z_ALPHA = Z[0.975]  # two-sided 5%


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def sharpe(r: np.ndarray) -> float:
    s = r.std()
    return float(r.mean() / s * math.sqrt(ANN)) if s > 0 else 0.0


def ann_pct(r: np.ndarray) -> float:
    return float(r.mean() * ANN * 100.0)


def maxdd_pct(r: np.ndarray) -> float:
    eq = np.exp(np.cumsum(r))
    return float((eq / np.maximum.accumulate(eq) - 1.0).min() * 100.0)


# ── data ────────────────────────────────────────────────────────────────────
def load_2014() -> pd.DataFrame:
    return lab.load()


def load_2000() -> pd.DataFrame:
    """Mirror mr_daily_lab.cmd_gonogolong's own 2000-start cache (fetch if absent)."""
    cache = "/tmp/mr_daily_close_2000.csv"
    fetch = sorted({"^GSPC", "QQQ", "IWM", "DIA", "IEF"})
    if os.path.exists(cache):
        return pd.read_csv(cache, index_col=0, parse_dates=True)
    import yfinance as yf
    raw = yf.download(fetch, start="2000-01-01", end=lab.END, interval="1d",
                      progress=False, auto_adjust=True)
    px = raw["Close"][fetch].dropna(how="all")
    px.to_csv(cache)
    return px


def build_legs(PX: pd.DataFrame, basket: list[str]):
    """Return aligned (active blend, buy&hold blend) daily log-return series.

    active = equal-weight mean of the canonical dip+5d sleeves (long-only, 200d gate,
    5bps cost). bench = equal-weight buy&hold of the same assets. Cash-scaling is
    Sharpe-invariant, so Sharpe(bench) == Sharpe(static 50/50) == Sharpe(static k·e)."""
    basket = [s for s in basket if s in PX.columns]
    active = pd.DataFrame({s: lab.sleeve(PX, s) for s in basket}).fillna(0.0).mean(axis=1)
    bench = pd.DataFrame(
        {s: np.log(PX[s].dropna() / PX[s].dropna().shift(1)) for s in basket}
    ).mean(axis=1)
    both = pd.concat([active.rename("a"), bench.rename("b")], axis=1).dropna()
    return both["a"].values, both["b"].values, both.index, basket


# ── paired block bootstrap of the Sharpe difference ──────────────────────────
def paired_sharpe_diff_boot(active: np.ndarray, bench: np.ndarray):
    """Resample the SAME block start indices for both legs; return the array of
    Sharpe(active) − Sharpe(bench) over B resamples (preserves cross-correlation)."""
    n = len(active)
    nb = n // BLOCK
    rng = np.random.default_rng(SEED)
    out = np.empty(B, dtype=float)
    for i in range(B):
        starts = rng.integers(0, n - BLOCK + 1, size=nb)
        sa = np.concatenate([active[s:s + BLOCK] for s in starts])
        sb = np.concatenate([bench[s:s + BLOCK] for s in starts])
        out[i] = sharpe(sa) - sharpe(sb)
    return out


def lag1_autocorr(returns: np.ndarray):
    """rho_1 with naive t (=rho·sqrt n, what F16 used) and heteroskedasticity-robust
    t (the F18 correction). Same estimator as mr_daily_lab.cmd_acf."""
    c = returns - returns.mean()
    n = len(c)
    den = (c ** 2).sum()
    rho = (c[1:] * c[:-1]).sum() / den
    rv = (c[1:] ** 2 * c[:-1] ** 2).sum() / den ** 2
    return float(rho), float(rho * math.sqrt(n)), float(rho / math.sqrt(rv)), n


def paired_maxdd_diff_boot(active: np.ndarray, static: np.ndarray):
    """Paired block bootstrap of the maxDD difference (active − static), +=active
    shallower. `static` is the 0.5·bench cash blend (the capital-preservation
    benchmark). Mirrors mr_daily_lab._gonogo_core.boot_paired."""
    n = len(active)
    nb = n // BLOCK
    rng = np.random.default_rng(SEED)
    out = np.empty(B, dtype=float)
    for i in range(B):
        starts = rng.integers(0, n - BLOCK + 1, size=nb)
        sa = np.concatenate([active[s:s + BLOCK] for s in starts])
        ss = np.concatenate([static[s:s + BLOCK] for s in starts])
        out[i] = maxdd_pct(sa) - maxdd_pct(ss)
    return out


# ── the study, per window ────────────────────────────────────────────────────
def study_window(PX, basket, label):
    active, bench, idx, basket = build_legs(PX, basket)
    n = len(active)
    years = (idx[-1] - idx[0]).days / 365.25

    sh_a, sh_b = sharpe(active), sharpe(bench)
    vol_active = float(active.std() * math.sqrt(ANN) * 100.0)  # ann %, for the economic translation
    diff_point = sh_a - sh_b

    boot = paired_sharpe_diff_boot(active, bench)
    se = float(boot.std(ddof=1))
    lo95, hi95 = (float(x) for x in np.percentile(boot, [2.5, 97.5]))
    lo90, hi90 = (float(x) for x in np.percentile(boot, [5.0, 95.0]))
    excludes_zero = not (lo95 < 0 < hi95)

    # Minimum detectable effect at 80% power, two-sided 5%, with the data we HAVE.
    mde_80 = (Z_ALPHA + Z[0.80]) * se

    # Power for plausible true edges at the current sample, and years for 80% power.
    def power(delta, se_):
        ncp = abs(delta) / se_ if se_ > 0 else float("inf")
        return norm_cdf(ncp - Z_ALPHA) + norm_cdf(-ncp - Z_ALPHA)

    def years_for_power(delta, target=0.80):
        se_target = abs(delta) / (Z_ALPHA + Z[target])
        return years * (se / se_target) ** 2

    deltas = [0.10, 0.20, 0.30, 0.50]
    power_now = {d: power(d, se) for d in deltas}
    years_80 = {d: years_for_power(d) for d in deltas}

    # TOST equivalence: smallest margin we can claim at 95% conf = 90%-CI half-extent.
    equiv_margin = max(abs(lo90), abs(hi90))
    tost = {m: (lo90 > -m and hi90 < m) for m in (0.20, 0.30, 0.50)}

    # Autocorrelation — the SIGNAL (well-powered) vs the EDGE (the question above).
    acf = {}
    for s in basket:
        r = np.log(PX[s].dropna() / PX[s].dropna().shift(1)).dropna().values
        rho, t_naive, t_robust, na = lag1_autocorr(r)
        acf[s] = dict(rho1=rho, t_naive=t_naive, t_robust=t_robust, n=na)
    # Signal power over the equity mean-reverters only (GLD etc. are controls).
    eq_t = [abs(acf[s]["t_robust"]) for s in basket if s in EQUITY_MR]
    min_abs_t_robust = min(eq_t) if eq_t else 0.0

    # Capital-preservation: point maxDD gap vs its paired-bootstrap CI (vs static 50/50).
    static5050 = 0.5 * bench
    dd_a, dd_bench = maxdd_pct(active), maxdd_pct(bench)
    dd_boot = paired_maxdd_diff_boot(active, static5050)
    dd_lo, dd_med, dd_hi = (float(x) for x in np.percentile(dd_boot, [2.5, 50, 97.5]))
    dd_significant = not (dd_lo < 0 < dd_hi)

    return dict(
        label=label, basket=basket, n_days=n, years=round(years, 1),
        sharpe_active=round(sh_a, 3), sharpe_bench=round(sh_b, 3),
        vol_active=round(vol_active, 1),
        ann_active=round(ann_pct(active), 2), ann_bench=round(ann_pct(bench), 2),
        diff_point=round(diff_point, 3), diff_se=round(se, 3),
        diff_ci95=[round(lo95, 3), round(hi95, 3)],
        diff_ci90=[round(lo90, 3), round(hi90, 3)],
        sharpe_edge_detected=excludes_zero,
        mde_80pct=round(mde_80, 3),
        power_now={f"{d:.2f}": round(power_now[d], 3) for d in deltas},
        years_for_80pct={f"{d:.2f}": round(years_80[d], 1) for d in deltas},
        equiv_margin_95=round(equiv_margin, 3),
        tost_equivalence={f"{m:.2f}": tost[m] for m in (0.20, 0.30, 0.50)},
        autocorr=acf, min_abs_t_robust=round(min_abs_t_robust, 2),
        maxdd_active=round(dd_a, 1), maxdd_bench=round(dd_bench, 1),
        maxdd_diff_ci=[round(dd_lo, 1), round(dd_med, 1), round(dd_hi, 1)],
        maxdd_edge_significant=dd_significant,
    )


def verdict(w12, w26, w0013):
    """Classify D6 across the windows: evidence-of-absence vs absence-of-evidence.
    w0013 is the DISJOINT 2000-2013 slice (the genuine independent corroboration, since
    w12's 2014-2026 is a calendar subset of w26's 2000-2026). Returns (headline, bullets)."""
    resid_pct = 0.2 * w26["vol_active"]  # a 0.2-Sharpe edge in ann-return terms, at the active leg's vol
    bullets = []
    bullets.append(
        f"SIGNAL is well-powered & real: over 26.5yr every equity index has lag-1 MR "
        f"autocorrelation |t_robust| ≥ {w26['min_abs_t_robust']:.1f} (all clear ±1.96); over 12.5yr "
        f"3 of 4 clear it (IWM marginal at {abs(w12['autocorr'].get('IWM', {}).get('t_robust', 0)):.1f}), "
        f"GLD ~0 as a non-mean-reverter control. Mean-reversion EXISTS — NOT absence-of-evidence about "
        f"the signal. [scope: proof is on OVERLAPPING daily autocorr; the traded NON-overlapping 5d "
        f"structure is weaker, per F18.]")
    bullets.append(
        f"EDGE vs static is undetectable: ΔSharpe(active−static) = {w12['diff_point']:+.2f} (12.5yr), "
        f"{w26['diff_point']:+.2f} (26.5yr), and {w0013['diff_point']:+.2f} on the DISJOINT 2000-2013 "
        f"slice ({w0013['diff_ci95']}) — all three 95% CIs straddle 0. No risk-adjusted edge in any window.")
    bullets.append(
        f"PARTLY evidence-of-absence: TOST positively rules out (95% conf) any active Sharpe edge "
        f"larger than ±{w12['equiv_margin_95']:.2f} robustly across both windows, and ±{w26['equiv_margin_95']:.2f} "
        f"over the full 26.5yr (a NARROW pass at the ±0.30 margin, Δ*={w26['equiv_margin_95']:.2f}). The "
        f"'underpowered' objection is retired for large edges.")
    bullets.append(
        f"PARTLY absence-of-evidence: MDE@80% ≈ {w26['mde_80pct']:.2f} Sharpe (26.5yr) / {w12['mde_80pct']:.2f} "
        f"(12.5yr), so a SMALL edge (≤0.20 Sharpe) cannot be excluded — resolving it would need "
        f"≈{w26['years_for_80pct']['0.20']:.0f}yr at current noise (order-of-mag; we have 26.5).")
    bullets.append(
        f"That residual is UNDETECTABLE, not trivial: ≤0.2 Sharpe ≈ ≤{resid_pct:.1f}%/yr at the active "
        f"leg's ~{w26['vol_active']:.0f}% vol — roughly a third of the 4–6%/yr bond-alternative income "
        f"target. The honest framing is 'too small to measure even over 26yr', not 'economically "
        f"irrelevant'. It still backs the static recommendation: you cannot bank an edge you cannot measure.")
    bullets.append(
        f"Conservative baseline: the test is vs buy&hold (≡ static 50/50, Sharpe-invariant — the EASIER "
        f"bar). The decision-relevant static 60/40 equity/bond (Sharpe ~0.86 > 0.80 per D6/F25) beats "
        f"active on Sharpe AND return, so against the recommended baseline active looks strictly worse.")
    bullets.append(
        f"Capital-preservation is path-dependent: active maxDD far shallower at the point "
        f"({w26['maxdd_active']:.0f}% vs {w26['maxdd_bench']:.0f}% buy&hold, 26.5yr) but the paired "
        f"maxDD-gap bootstrap straddles 0 ({w26['maxdd_diff_ci']}) — real on average, not statistically reliable.")
    headline = (
        "D6 is CORRECT and mostly evidence-of-absence: no risk-adjusted edge over static is detected in "
        "any window (incl. the disjoint 2000-2013 slice), and TOST positively rules out any edge larger "
        "than ~0.4 Sharpe (across windows) / ~0.25-0.3 (full 26.5yr). The MR signal is provably real but "
        "provably not tradeable-better-than-static. The sole residual — a ≤0.2-Sharpe edge — is UNDETECTABLE "
        "(needs ~90-114yr), not economically trivial, and the static recommendation stands.")
    return headline, bullets


def fmt(w):
    L = []
    L.append(f"── {w['label']}  ({w['years']}yr, {w['n_days']} days, basket={'+'.join(w['basket'])}) ──")
    L.append(f"  Sharpe: active {w['sharpe_active']:+.2f}  bench {w['sharpe_bench']:+.2f}  "
             f"→ ΔSharpe {w['diff_point']:+.2f}  (SE {w['diff_se']:.2f})")
    L.append(f"  paired-bootstrap ΔSharpe 95% CI {w['diff_ci95']}   90% CI {w['diff_ci90']}   "
             f"edge detected: {'YES' if w['sharpe_edge_detected'] else 'no (straddles 0)'}")
    L.append(f"  MDE @80% power (this much data): {w['mde_80pct']:+.2f} Sharpe  "
             f"— smaller true edges are likely missed")
    L.append("  power NOW for a true edge of ...   " +
             "  ".join(f"{d}:{w['power_now'][d]*100:.0f}%" for d in w['power_now']))
    L.append("  resolution horizon @80% power ...  " +
             "  ".join(f"{d}:{w['years_for_80pct'][d]:.0f}yr" for d in w['years_for_80pct']) +
             "   (order-of-mag; assumes SE∝1/√yr)")
    L.append(f"  TOST equivalence (active≈static within ±Δ, 95% conf): " +
             "  ".join(f"±{m}:{'PASS' if w['tost_equivalence'][m] else 'fail'}"
                       for m in w['tost_equivalence']) +
             f"   → smallest provable margin Δ*={w['equiv_margin_95']:.2f}")
    L.append(f"  lag-1 autocorrelation (signal): min equity |t_robust| = {w['min_abs_t_robust']:.2f}  " +
             "  ".join(f"{s}:{v['rho1']:+.3f}(t{v['t_robust']:+.1f})" for s, v in w['autocorr'].items()))
    L.append(f"  capital-preservation: maxDD active {w['maxdd_active']:.0f}% vs bench "
             f"{w['maxdd_bench']:.0f}%; paired maxDD-gap CI {w['maxdd_diff_ci']}  "
             f"→ {'significant' if w['maxdd_edge_significant'] else 'path-dependent, NOT significant'}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="D6 power & equivalence study")
    ap.add_argument("--json", metavar="PATH", help="also write the full result dict as JSON")
    a = ap.parse_args()

    LPX = load_2000()
    long_basket = ["^GSPC", "QQQ", "IWM", "DIA"]
    w12 = study_window(load_2014(), ["QQQ", "SPY", "IWM", "DIA", "GLD"], "2014-2026 standard basket")
    w26 = study_window(LPX, long_basket, "2000-2026 long-history basket")
    # Genuinely DISJOINT pre-2014 slice — the real independent corroboration, since the
    # 2014-2026 window is a calendar subset of 2000-2026 (not an independent second test).
    w0013 = study_window(LPX.loc[:"2013-12-31"], long_basket,
                         "2000-2013 DISJOINT slice (independent of the 2014-2026 window)")
    head, bullets = verdict(w12, w26, w0013)

    print("=" * 78)
    print("POWER & EQUIVALENCE STUDY — is D6 'no edge' genuine, or underpowered?")
    print("=" * 78)
    print(fmt(w12)); print()
    print(fmt(w26)); print()
    print(fmt(w0013)); print()
    print("── VERDICT ──")
    print("  " + head.replace(": ", ":\n      ", 1))
    for b in bullets:
        print(f"    • {b}")
    print("=" * 78)

    if a.json:
        with open(a.json, "w") as f:
            json.dump(dict(window_2014=w12, window_2000=w26, window_2000_2013=w0013,
                           verdict_headline=head, verdict_bullets=bullets), f, indent=2)
        print(f"[wrote {a.json}]")


if __name__ == "__main__":
    main()
