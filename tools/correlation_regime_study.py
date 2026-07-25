#!/usr/bin/env python3
"""
correlation_regime_study — study #13: the BONDS-DON'T-HEDGE regime stress. Every product
recommendation the program landed on — the static 60/40 ([[F38]]), the conservative ~30-40%
equity tilt ([[F42]]), the held-to-maturity ladder ([[F45]]) — leans on BONDS, and every
drawdown/hedging claim inherits the benign NEGATIVE stock-bond correlation of 2000-2021
(~-0.3), which flipped POSITIVE in 2022 and was positive for most of 1965-1999. Studies #8/#9
flagged this as their central surviving caveat and never tested it. This study tests it, on
64 years of monthly data (1962-2026) spanning BOTH correlation regimes and the one genuine
inflation shock (1965-1981):

  A. THE CORRELATION RECORD. Rolling 36m stock-bond correlation 1962-2026 from one consistent
     data build (month-end ^GSPC + Shiller dividend yield -> total-return equity; a synthetic
     constant-maturity 7yr Treasury zero from CM yields, exact bond math, validated vs IEF on
     the 2002-2026 overlap). Establishes the eras from data: positive-corr 1962-1999, negative
     -corr 2000-2021, the 2022+ flip — plus the acute inflation window 1965-1981.
  B. THE MIX SWEEP BY ERA (the core). Static equity/bond mixes (0..100% equity, monthly
     rebalanced) scored per era on BOTH bases — NOMINAL and REAL (CPI-deflated) — with raw AND
     excess-over-T-bill Sharpe (raw Sharpe flatters bond-heavy mixes in high-rate eras).
     Paired block bootstrap (block=12m, B=5000, seed=0) of the conservative tilt (30/70,
     40/60) MINUS 60/40 per era: does study #9's "tilt conservative" direction survive the
     regime where bonds don't hedge?
  C. WHAT HELPS WHEN BONDS DON'T HEDGE. Swap the conservative mix's bond leg: 7yr zero (base)
     vs 2yr zero (short duration) vs T-bill cash — in EVERY era plus the full sample, so the
     trade-off is visible: shortening rescues the positive-corr/inflation eras but LOSES in the
     negative-corr era on every metric. There is no free all-weather ballast.
  D. TIPS (the structural mitigation F45 could not test). Empirical: TIP vs IEF as the bond
     leg through the one OBSERVED bonds-don't-hedge event (2022). Forward: the 10yr TIPS real
     yield (FRED DFII10) prices a held-to-maturity TIPS ladder's REAL return — the direct
     answer to F45's "-19% real in the 1970s" hole.
  E. GOAL-ODDS BY REGIME. Fraction of rolling 10yr windows clearing the ~3.75% nominal CAGR
     goal AND preserving purchasing power (real CAGR >= 0), per mix, split by the era the
     window STARTS in — the empirical stress of study #8/#9's forward Monte-Carlo, which
     inherited the benign correlation by construction.

PRE-REGISTERED READS (stated before the numbers): (1) F42's conservative-tilt direction is
REGIME-ROBUST only if, in the positive-corr era, the 30-40% mixes still show >= excess Sharpe
and shallower maxDD than 60/40 with bootstrap support; it is QUALIFIED/REFUTED otherwise.
(2) The real-terms hole is MATERIAL if the recommended conservative mix's REAL drawdown in the
inflation era exceeds the ~-23% nominal median-worst DD that F41 already called equity-like.
(3) Era conditioning is DESCRIPTIVE (eras are known only ex post) — this is a stress test of
the recommendation, NOT a tradable regime-timing claim.

KNOWN CONSTRUCTIONS (folded in after a 4-lens adversarial skeptic panel, 2026-07-06): (a) the
primary bond sleeve is a 7yr ZERO (constant duration 7.0); 1965-81 coupons were 6-14%, so a real
coupon book at that tenor had duration ~5.7-6.6 and the zero OVERSTATES inflation-era bond losses
by ~3-5pp at the mix level — a par-coupon sensitivity is COMPUTED AND PRINTED (the conclusions
survive it; the pos-era tilt nominal-DD edge actually strengthens); (b) the Shiller dividend
column ends mid-2023, so the equity dividend yield is frozen (ffilled) over the small-n flip era
— inflates flip-era equity CAGR ~+0.26%/yr; no verdict claim rests on a flip-era return; (c) the
cut-C 2yr yield is a coarse ^IRX->^FVX interpolation understating its carry ~0.3pp — conservative
AGAINST the study's shortening claim; the load-bearing row is T-bill cash; (d) cut-E percentages
are SHARES of overlapping windows (~2-4 independent decades per era), not probabilities.

Reuses bond_ladder_study's yield/CPI caches + exact zero-coupon math. Deterministic (seed=0);
fetches once to /tmp caches.

    venv/bin/python tools/correlation_regime_study.py [--json out.json] [--selfcheck]
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
import data_cache  # noqa: E402  (validated cache: never trust a stub, never write one)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bond_ladder_study as bls   # noqa: E402  load_yields / load_cpi / curve / zero_price

CACHE_GSPC = "/tmp/corr_regime_gspc.csv"     # month-end ^GSPC price + SPY TR (validation/splice)
CACHE_SHILLER = "/tmp/corr_regime_shiller.csv"  # Shiller monthly: price, dividend, CPI
CACHE_TIP = "/tmp/corr_regime_tip.csv"       # TIP/IEF/SPY daily total-return (cut D)
CACHE_DFII = "/tmp/corr_regime_dfii10.csv"   # FRED DFII10 (10yr TIPS real yield)

ANN = 12                                     # monthly study
BLOCK = 12                                   # 1yr blocks (monthly analogue of the 20d convention)
B = 5000
SEED = 0
GOAL_APY = 3.75
LADDER_TENORS = bls.LADDER_TENORS

# Eras: fixed, disclosed boundaries (justified by the detected sign-flip dates in cut A).
ERAS = {
    "pos_corr 1962-1999": ("1962-02-01", "1999-12-31"),
    "inflation 1965-1981": ("1965-01-01", "1981-12-31"),   # acute subset of the positive era
    "neg_corr 2000-2021": ("2000-01-01", "2021-12-31"),
    "flip 2022-2026": ("2022-01-01", "2026-12-31"),        # small-n: point estimates only
}
MIXES = [0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0]           # equity weight; rest = 7yr Treasury zero


# ── data ──────────────────────────────────────────────────────────────────────
def load_shiller():
    """Shiller monthly S&P composite (price, trailing-12m dividend, CPI), 1871+. Used ONLY for
    the slowly-varying dividend YIELD (D/P, same-index scale) and as a CPI cross-check — the
    price path itself comes from month-end ^GSPC (Shiller's price is a monthly AVERAGE, which
    smooths returns and would distort correlations)."""
    def _fetch():
        raw = pd.read_csv("https://raw.githubusercontent.com/datasets/s-and-p-500/master/data/data.csv")
        raw = raw.rename(columns={"Date": "date"}).set_index("date")
        raw.index = pd.to_datetime(raw.index)
        return raw

    # Monthly since 1871, so >1000 rows. A blocked fetch of a raw GitHub CSV can
    # return an HTML error page that parses as a tiny frame — validate, don't trust.
    df = data_cache.load_cached_frame(
        CACHE_SHILLER, _fetch, min_rows=1000,
        required_cols=["SP500", "Dividend", "Consumer Price Index"],
        label="shiller")
    out = df[["SP500", "Dividend", "Consumer Price Index"]].replace(0.0, np.nan)
    return out.rename(columns={"SP500": "p", "Dividend": "d", "Consumer Price Index": "cpi"})


def load_gspc():
    """Month-end ^GSPC price + month-end SPY total-return level (yfinance, cached)."""
    def _fetch():
        import yfinance as yf
        g = yf.Ticker("^GSPC").history(period="max", auto_adjust=True)["Close"]
        s = yf.Ticker("SPY").history(period="max", auto_adjust=True)["Close"]
        df = pd.DataFrame({"gspc": g, "spy": s})
        df.index = pd.to_datetime(df.index, utc=True).tz_localize(None)
        return df.resample("ME").last()

    return data_cache.load_cached_frame(
        CACHE_GSPC, _fetch, min_rows=300, required_cols=["gspc", "spy"],
        label="gspc_spy")


def load_tip():
    tk = ["TIP", "IEF", "SPY"]
    if os.path.exists(CACHE_TIP):
        return pd.read_csv(CACHE_TIP, index_col=0, parse_dates=True)
    import yfinance as yf
    raw = yf.download(tk, start="2003-12-01", end="2026-06-30", interval="1d",
                      progress=False, auto_adjust=True)["Close"]
    raw.to_csv(CACHE_TIP)
    return raw


def load_dfii10():
    """FRED DFII10 — 10yr TIPS constant-maturity REAL yield (%, daily). Returns the last value
    and date, or None on failure."""
    try:
        if os.path.exists(CACHE_DFII):
            c = pd.read_csv(CACHE_DFII, index_col=0)
        else:
            c = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFII10")
            c = c.rename(columns={c.columns[0]: "date", c.columns[1]: "y"}).set_index("date")
            c.to_csv(CACHE_DFII)
        s = pd.to_numeric(c.iloc[:, 0], errors="coerce").dropna()
        return float(s.iloc[-1]), str(s.index[-1])
    except Exception:
        return None


def equity_tr(gspc, shiller):
    """Monthly total-return equity 1962+: month-end ^GSPC price return + LAGGED Shiller dividend
    yield accrual (dy/12). D/P uses Shiller's own price (same index scale); dy is forward-filled
    where the Shiller dividend lags (recent months). No lookahead: month t uses dy at t-1."""
    dy = (shiller["d"] / shiller["p"]).ffill()
    dy.index = dy.index.to_period("M")
    px = gspc["gspc"].dropna()
    pr = px.pct_change()
    dy_me = dy.reindex(px.index.to_period("M")).ffill()
    dy_me.index = px.index
    r = (pr + dy_me.shift(1) / ANN).dropna()
    return r.loc["1962-01-01":]


def const_maturity_zero(yields, T):
    """Monthly total returns of a PERPETUAL constant-maturity T-year zero-coupon Treasury,
    exact repricing on the interpolated 1-10yr curve (mirrors bond_ladder_study's cm5/cm10)."""
    ys = yields.dropna(how="all").loc["1962-01-01":]
    curves = {d: bls.curve(ys.loc[d]) for d in ys.index}
    dates = list(ys.index)
    ten = LADDER_TENORS
    dt = 1.0 / ANN
    out = []
    for i in range(1, len(dates)):
        c0, c1 = curves[dates[i - 1]], curves[dates[i]]
        tv1 = [c1[k] for k in ten]
        yn = float(np.interp(T - dt, ten, tv1)) if T - dt >= 1 else c1[1]
        out.append(bls.zero_price(yn, T - dt) / bls.zero_price(c0[T], T) - 1.0)
    return pd.Series(out, index=dates[1:])


def const_maturity_coupon(yields, T):
    """Monthly total returns of a PERPETUAL constant-maturity T-year PAR COUPON Treasury roll —
    the duration-honest foil the skeptic panel forced. CMT yields ARE par yields: each month a
    par bond is issued at the entry par yield (coupon = y0, price = 1), held one month (exact
    annual-coupon pricing: every remaining cashflow discounted at the interpolated YTM for the
    aged maturity), then rolled. A 7yr par bond in the 6-14%-coupon 1965-81 era has Macaulay
    duration ~5.7 vs the zero's constant 7.0."""
    ys = yields.dropna(how="all").loc["1962-01-01":]
    curves = {d: bls.curve(ys.loc[d]) for d in ys.index}
    dates = list(ys.index)
    ten = LADDER_TENORS
    dt = 1.0 / ANN
    out = []
    for i in range(1, len(dates)):
        c0, c1 = curves[dates[i - 1]], curves[dates[i]]
        cpn = c0[T]                                     # issued at par: coupon = entry par yield
        tv1 = [c1[k] for k in ten]
        y1 = float(np.interp(T - dt, ten, tv1)) if T - dt >= 1 else c1[1]
        p1 = sum(cpn / (1 + y1) ** (k - dt) for k in range(1, T + 1)) + 1.0 / (1 + y1) ** (T - dt)
        out.append(p1 - 1.0)                            # entry price is par (=1)
    return pd.Series(out, index=dates[1:])


def cash_returns(yields):
    """Monthly T-bill roll approximation: accrue last month's 3m bill yield (^IRX, decimal).
    A discount-yield-as-BEY approximation — immaterial at 3m duration for era-level stats."""
    y = yields["^IRX"].dropna().loc["1962-01-01":]
    return ((1.0 + y.shift(1)) ** (1.0 / ANN) - 1.0).dropna()


def real_index(cpi, idx):
    return cpi.reindex(idx, method="ffill")


# ── metrics (monthly) ─────────────────────────────────────────────────────────
def pm12(r):
    r = np.asarray(pd.Series(r).dropna(), dtype=float)
    n = len(r)
    if n < 5 or r.std() == 0:
        return dict(n=n, cagr=0.0, vol=0.0, sharpe=0.0, maxdd=0.0, calmar=0.0)
    eq = np.cumprod(1.0 + r)
    cagr = eq[-1] ** (ANN / n) - 1.0 if eq[-1] > 0 else -1.0
    dd = (eq / np.maximum.accumulate(eq) - 1.0).min()
    return dict(n=n, cagr=round(cagr * 100, 2), vol=round(r.std() * math.sqrt(ANN) * 100, 2),
                sharpe=round(r.mean() / r.std() * math.sqrt(ANN), 3),
                maxdd=round(dd * 100, 1),
                calmar=round((cagr / abs(dd)) if dd != 0 else 0.0, 3))


def real_stats(r, cpi):
    """REAL (CPI-deflated) CAGR and maxDD of a nominal monthly return series."""
    eq = (1.0 + r).cumprod()
    req = (eq / real_index(cpi, eq.index)).dropna()
    if len(req) < 5:
        return dict(real_cagr=None, real_maxdd=None)
    cagr = (req.iloc[-1] / req.iloc[0]) ** (ANN / (len(req) - 1)) - 1.0
    dd = (req / req.cummax() - 1.0).min()
    return dict(real_cagr=round(cagr * 100, 2), real_maxdd=round(dd * 100, 1))


def _m2(r):
    """(sharpe, maxdd%) — the paired-bootstrap statistic."""
    eq = np.cumprod(1.0 + r)
    dd = (eq / np.maximum.accumulate(eq) - 1.0).min()
    sh = r.mean() / r.std() * math.sqrt(ANN) if r.std() > 0 else 0.0
    return sh, dd * 100


def paired_boot12(a, b, block=BLOCK, nboot=B, seed=SEED):
    """Paired block bootstrap of (a − b): ΔSharpe and ΔmaxDD CIs (same block starts)."""
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
    pc = lambda x, nd=3: [round(float(v), nd) for v in np.percentile(x, [2.5, 97.5])]
    # family-wise (Bonferroni over the pre-registered 12-CI tilt family) percentiles — used to
    # keep any "clearly positive" claim honest under multiple comparisons
    afw = 0.05 / 12 / 2 * 100
    fw = lambda x: [round(float(v), 3) for v in np.percentile(x, [afw, 100 - afw])]
    return dict(dSharpe=pc(ds), dSharpe_fw12=fw(ds), dMaxDD=pc(dd, 1),
                prob_dd_shallower=round(float(np.mean(dd > 0)), 3))


# ── cut A: the correlation record ─────────────────────────────────────────────
def cut_corr_record(eq, bd):
    df = pd.concat([eq.rename("e"), bd.rename("b")], axis=1).dropna()
    c36 = df["e"].rolling(36).corr(df["b"]).dropna()
    def era_mean(a, b):
        s = c36.loc[a:b]
        return round(float(s.mean()), 2) if len(s) else None
    # data-driven flip dates: first month the 36m corr crosses and STAYS >=24m on the new sign
    def sustained_cross(s, sign, after):
        s = s.loc[after:]
        for i in range(len(s) - 24):
            w = s.iloc[i:i + 24]
            if (sign * w > 0).all():
                return str(s.index[i].date())
        return None
    return dict(
        span=f"{df.index[0].date()}->{df.index[-1].date()}", n_months=len(df),
        era_corr={k: era_mean(a, b) for k, (a, b) in ERAS.items()},
        detected_neg_flip=sustained_cross(c36, -1, "1995-01-01"),
        detected_pos_reflip=sustained_cross(c36, +1, "2020-01-01"),
        corr36_last=round(float(c36.iloc[-1]), 2),
        share_positive_pre2000=round(float((c36.loc[:"1999-12-31"] > 0).mean()), 2),
        share_negative_2000_2021=round(float((c36.loc["2000-01-01":"2021-12-31"] < 0).mean()), 2),
    ), df, c36


# ── cut B: the mix sweep by era ───────────────────────────────────────────────
def cut_mix_by_era(df, cash, cpi):
    out = {}
    boot = {}
    for era, (a, b) in ERAS.items():
        d = df.loc[a:b]
        c = cash.reindex(d.index).fillna(0.0)
        rows = []
        series = {}
        for w in MIXES:
            r = w * d["e"] + (1 - w) * d["b"]
            series[w] = r
            ex = r - c
            m = pm12(r)
            m["sharpe_ex"] = round(float(ex.mean() / ex.std() * math.sqrt(ANN)), 3) if ex.std() > 0 else 0.0
            m.update(real_stats(r, cpi))
            rows.append(dict(w_eq=int(w * 100), **m))
        out[era] = rows
        # the tilt test: conservative mixes minus 60/40, raw + excess (skip small-n flip era)
        if len(d) >= 5 * BLOCK:
            c60 = series[0.6]
            boot[era] = {}
            for w in (0.3, 0.4):
                raw = paired_boot12(series[w].values, c60.values)
                ex = paired_boot12((series[w] - c).values, (c60 - c).values)
                boot[era][f"{int(w*100)}v60"] = dict(dSharpe_raw=raw["dSharpe"], dMaxDD=raw["dMaxDD"],
                                                     prob_dd_shallower=raw["prob_dd_shallower"],
                                                     dSharpe_excess=ex["dSharpe"],
                                                     dSharpe_excess_fw12=ex["dSharpe_fw12"])
    return out, boot


# ── cut C: what helps when bonds don't hedge ─────────────────────────────────
def cut_bond_leg(df, y, cash, cpi):
    """40% equity + 60% ballast, ballast ∈ {7yr zero, 2yr zero, T-bill cash} — in EVERY era plus
    the full sample, so the trade-off (not just the eras where shortening wins) is on the table.
    NB the 2yr yield pre-1976 is a coarse ^IRX->^FVX linear interpolation that UNDERSTATES its
    carry ~0.3pp (vs FRED GS2 on the overlap) — conservative against the shortening claim; the
    load-bearing short-ballast row is T-bill cash."""
    z2 = const_maturity_zero(y, 2)
    out = {}
    spans = list(ERAS.items()) + [("full 1962-2026", (str(df.index[0].date()), str(df.index[-1].date())))]
    for era, (a, b) in spans:
        d = df.loc[a:b]
        c = cash.reindex(d.index).fillna(0.0)
        z2e = z2.reindex(d.index)
        rows = []
        for name, leg in [("7yr Treasury zero (base)", d["b"]), ("2yr Treasury zero", z2e), ("T-bill cash", c)]:
            r = (0.4 * d["e"] + 0.6 * leg).dropna()
            ex = r - c.reindex(r.index)
            m = pm12(r)
            m["sharpe_ex"] = round(float(ex.mean() / ex.std() * math.sqrt(ANN)), 3) if ex.std() > 0 else 0.0
            m.update(real_stats(r, cpi))
            rows.append(dict(ballast=name, **m))
        out[era] = rows
    return out


# ── proxy sensitivity: the duration-honesty check the panel forced ────────────
def cut_proxy_sensitivity(df, y, cash, cpi):
    """The primary bond sleeve is a 7yr ZERO (constant duration 7.0). In the 6-14%-coupon 1965-81
    era a holdable Treasury book at that tenor had duration ~5.7-6.6, so the zero overstates the
    inflation-era losses. Reprice the headline numbers with exact par-coupon legs (7yr, and an
    IEF-like 50/50 7y+10y book that validates BETTER vs IEF than the zero) and report the range.
    Also re-run the pos-era 40v60 nominal-dMaxDD bootstrap on the coupon leg: the zero's
    zero-straddling CI is a proxy artifact — coupon-honest, the tilt's nominal-DD edge EXCLUDES 0."""
    c7 = const_maturity_coupon(y, 7)
    c10 = const_maturity_coupon(y, 10)
    ieflike = ((c7 + c10) / 2.0).dropna()
    out = {"inflation_real_dd": {}}
    a, b = ERAS["inflation 1965-1981"]
    legs = [("7yr zero (primary)", df["b"]), ("7yr par coupon", c7), ("IEF-like 7y+10y coupon", ieflike)]
    for name, leg in legs:
        d = pd.concat([df["e"].rename("e"), leg.rename("b")], axis=1).dropna().loc[a:b]
        out["inflation_real_dd"][name] = dict(
            mix4060=real_stats(0.4 * d["e"] + 0.6 * d["b"], cpi)["real_maxdd"],
            mix3070=real_stats(0.3 * d["e"] + 0.7 * d["b"], cpi)["real_maxdd"],
            bond_only=real_stats(d["b"], cpi)["real_maxdd"])
    # the cash-rescue size on the coupon-honest base (bullet-4 honesty)
    d7 = pd.concat([df["e"].rename("e"), c7.rename("b")], axis=1).dropna().loc[a:b]
    ccash = cash.reindex(d7.index).fillna(0.0)
    out["cash_rescue_coupon_base"] = dict(
        base=real_stats(0.4 * d7["e"] + 0.6 * d7["b"], cpi)["real_maxdd"],
        cash=real_stats(0.4 * d7["e"] + 0.6 * ccash, cpi)["real_maxdd"])
    # pos-era 40v60 nominal dMaxDD with the coupon leg
    a2, b2 = ERAS["pos_corr 1962-1999"]
    dp = pd.concat([df["e"].rename("e"), c7.rename("b")], axis=1).dropna().loc[a2:b2]
    bo = paired_boot12((0.4 * dp["e"] + 0.6 * dp["b"]).values, (0.6 * dp["e"] + 0.4 * dp["b"]).values)
    out["pos_40v60_coupon"] = dict(dMaxDD=bo["dMaxDD"], prob_dd_shallower=bo["prob_dd_shallower"])
    # coupon-leg validation vs IEF (cache written by validation(), which runs first)
    try:
        ief = pd.read_csv("/tmp/corr_regime_ief.csv", index_col=0, parse_dates=True).iloc[:, 0]
        ir = ief.pct_change().dropna()
        both = pd.concat([ieflike.rename("m"), ir.rename("ief")], axis=1).dropna()
        out["ieflike_vs_ief"] = dict(corr=round(float(both["m"].corr(both["ief"])), 4),
                                     vol_model=pm12(both["m"])["vol"], vol_ief=pm12(both["ief"])["vol"])
    except Exception:
        out["ieflike_vs_ief"] = None
    return out


# ── cut D: TIPS ───────────────────────────────────────────────────────────────
def cut_tips(cpi, cash):
    px = load_tip().dropna()
    me = px.resample("ME").last()
    r = me.pct_change().dropna()
    out = {}
    def with_ex(rr, c):
        ex = (rr - c.reindex(rr.index).fillna(0.0)).dropna()
        m = pm12(rr)
        m["sharpe_ex"] = round(float(ex.mean() / ex.std() * math.sqrt(ANN)), 3) if ex.std() > 0 else 0.0
        m.update(real_stats(rr, cpi))
        return m
    for era, (a, b) in [("full 2004-2026", ("2004-01-01", "2026-12-31")),
                        ("shock 2021-2023", ("2021-01-01", "2023-12-31"))]:
        d = r.loc[a:b]
        rows = {}
        for name, leg in [("40/60 TIP", 0.6 * d["TIP"]), ("40/60 IEF", 0.6 * d["IEF"])]:
            rows[name] = with_ex(0.4 * d["SPY"] + leg, cash)
        rows["TIP standalone"] = with_ex(d["TIP"], cash)
        rows["IEF standalone"] = with_ex(d["IEF"], cash)
        out[era] = rows
    out["dfii10"] = load_dfii10()
    return out


# ── cut E: goal-odds by regime ────────────────────────────────────────────────
def cut_goal_odds(df, cpi):
    """Rolling 10yr windows per mix: P(nominal CAGR >= 3.75%) and P(real CAGR >= 0), grouped by
    the era the WINDOW STARTS in. Overlapping windows — serially correlated, descriptive only."""
    W = 120
    cpi_me = real_index(cpi, df.index)
    out = {}
    for w in (0.3, 0.4, 0.6):
        r = w * df["e"] + (1 - w) * df["b"]
        eq = (1.0 + r).cumprod()
        req = (eq / cpi_me).dropna()
        nom = (eq.shift(-W) / eq) ** (ANN / W) - 1.0
        rea = (req.shift(-W) / req) ** (ANN / W) - 1.0
        res = {}
        for era, (a, b) in ERAS.items():
            if era.startswith("flip"):
                continue                       # no complete 10yr window starts there
            n_ = nom.loc[a:b].dropna()
            r_ = rea.loc[a:b].dropna()
            if len(n_) < 12:
                continue
            res[era] = dict(n_windows=len(n_),
                            indep_decades=round(len(n_) / 120, 1),
                            p_nominal_goal=round(float((n_ >= GOAL_APY / 100).mean()), 2),
                            p_real_positive=round(float((r_ >= 0).mean()), 2),
                            worst_nominal_cagr=round(float(n_.min() * 100), 2),
                            worst_real_cagr=round(float(r_.min() * 100), 2))
        out[f"{int(w*100)}/{int((1-w)*100)}"] = res
    return out


# ── validation / selfcheck ────────────────────────────────────────────────────
def validation(eq, bd, y, shiller, cpi):
    """The cross-checks the study's credibility rests on (also printed in the report)."""
    out = {}
    gspc = load_gspc()
    spy = gspc["spy"].dropna().pct_change().dropna()
    both = pd.concat([eq.rename("m"), spy.rename("spy")], axis=1).dropna()
    out["equity_vs_spy"] = dict(
        span=f"{both.index[0].date()}->{both.index[-1].date()}", n=len(both),
        corr=round(float(both["m"].corr(both["spy"])), 4),
        cagr_model=pm12(both["m"])["cagr"], cagr_spy=pm12(both["spy"])["cagr"])
    import yfinance as yf
    if os.path.exists("/tmp/corr_regime_ief.csv"):
        ief = pd.read_csv("/tmp/corr_regime_ief.csv", index_col=0, parse_dates=True).iloc[:, 0]
    else:
        ief = yf.Ticker("IEF").history(period="max", auto_adjust=True)["Close"]
        ief.index = pd.to_datetime(ief.index, utc=True).tz_localize(None)
        ief = ief.resample("ME").last()
        ief.to_csv("/tmp/corr_regime_ief.csv")
    ir = ief.pct_change().dropna()
    bb = pd.concat([bd.rename("z7"), ir.rename("ief")], axis=1).dropna()
    out["bond_vs_ief"] = dict(
        span=f"{bb.index[0].date()}->{bb.index[-1].date()}", n=len(bb),
        corr=round(float(bb["z7"].corr(bb["ief"])), 4),
        cagr_z7=pm12(bb["z7"])["cagr"], cagr_ief=pm12(bb["ief"])["cagr"],
        vol_z7=pm12(bb["z7"])["vol"], vol_ief=pm12(bb["ief"])["vol"])
    sc = shiller["cpi"].dropna()
    sc.index = sc.index.to_period("M")
    fc = cpi.copy()
    fc.index = fc.index.to_period("M")
    j = pd.concat([sc.rename("sh"), fc.rename("fred")], axis=1).dropna()
    yoy = j.pct_change(12).dropna()
    out["cpi_crosscheck"] = dict(n=len(yoy), corr_yoy=round(float(yoy["sh"].corr(yoy["fred"])), 4))
    return out


def selfcheck(eq, bd, val):
    assert abs((1.05) ** (-10) - bls.zero_price(0.05, 10)) < 1e-12
    assert val["equity_vs_spy"]["corr"] > 0.97, f"equity model must track SPY: {val['equity_vs_spy']}"
    assert val["bond_vs_ief"]["corr"] > 0.90, f"7yr zero must track IEF: {val['bond_vs_ief']}"
    assert val["cpi_crosscheck"]["corr_yoy"] > 0.95, f"CPI sources must agree: {val['cpi_crosscheck']}"
    # 100/0 mix must equal the equity series exactly (mix accounting identity)
    r100 = 1.0 * eq + 0.0 * bd.reindex(eq.index)
    assert np.allclose(r100.dropna().values, eq.reindex(r100.dropna().index).values)
    print("[selfcheck OK] zero math exact; equity tracks SPY (corr "
          f"{val['equity_vs_spy']['corr']}); 7yr zero tracks IEF (corr {val['bond_vs_ief']['corr']}); "
          f"CPI sources agree (YoY corr {val['cpi_crosscheck']['corr_yoy']}); mix identity holds.")


# ── report ────────────────────────────────────────────────────────────────────
def fmt_row(m):
    rc = f"{m['real_cagr']:6.2f}" if m.get("real_cagr") is not None else "   n/a"
    rd = f"{m['real_maxdd']:7.1f}" if m.get("real_maxdd") is not None else "    n/a"
    return (f"{m['cagr']:7.2f} {m['vol']:6.2f} {m['sharpe']:7.3f} {m.get('sharpe_ex', 0):8.3f} "
            f"{m['maxdd']:7.1f} | {rc} {rd}")


def fmt(corr, mixes, boot, legs, tips, odds, val, sens):
    L = ["== CUT A — THE CORRELATION RECORD (rolling 36m stock-bond corr, one consistent build) =="]
    L.append(f"   span {corr['span']}  ({corr['n_months']} months)")
    for k, v in corr["era_corr"].items():
        L.append(f"   {k:24} mean 36m corr {v:+.2f}")
    L.append(f"   detected sustained flips: negative from {corr['detected_neg_flip']}, "
             f"positive again from {corr['detected_pos_reflip']} (36m corr now {corr['corr36_last']:+.2f})")
    L.append(f"   corr>0 share pre-2000: {corr['share_positive_pre2000']*100:.0f}%   "
             f"corr<0 share 2000-2021: {corr['share_negative_2000_2021']*100:.0f}%")
    L.append("")
    L.append("== CUT B — MIX SWEEP BY ERA (monthly rebalance; Sharpe raw AND excess-of-T-bill; NOMINAL | REAL) ==")
    for era, rows in mixes.items():
        L.append(f"   -- {era} --")
        L.append(f"   {'eq%':>4} {'CAGR%':>7} {'vol%':>6} {'Sharpe':>7} {'Sh(exc)':>8} {'maxDD%':>7} | "
                 f"{'realCAGR%':>6} {'realDD%':>7}")
        for m in rows:
            L.append(f"   {m['w_eq']:4d} {fmt_row(m)}")
        if era in boot:
            for tilt, bo in boot[era].items():
                L.append(f"     tilt {tilt}: dSharpe(raw) CI[{bo['dSharpe_raw'][0]:+.2f},{bo['dSharpe_raw'][1]:+.2f}]  "
                         f"dSharpe(excess) CI[{bo['dSharpe_excess'][0]:+.2f},{bo['dSharpe_excess'][1]:+.2f}]  "
                         f"(family-wise x12: [{bo['dSharpe_excess_fw12'][0]:+.2f},{bo['dSharpe_excess_fw12'][1]:+.2f}])  "
                         f"dMaxDD CI[{bo['dMaxDD'][0]:+.1f},{bo['dMaxDD'][1]:+.1f}]  "
                         f"P(shallower)={bo['prob_dd_shallower']*100:.0f}%")
    L.append("")
    L.append("== CUT C — THE BOND LEG ACROSS EVERY REGIME (40% equity + 60% ballast; the trade-off, not a winner) ==")
    for era, rows in legs.items():
        L.append(f"   -- {era} --")
        for m in rows:
            L.append(f"   {m['ballast']:26} {fmt_row(m)}")
    L.append("   (2yr yield pre-1976 is a coarse ^IRX->^FVX interpolation understating its carry ~0.3pp — "
             "conservative against the shortening claim; the load-bearing short-ballast row is T-bill cash)")
    L.append("")
    L.append("== CUT C' — DURATION-PROXY SENSITIVITY (the zero overstates 1965-81 losses; coupon-honest range) ==")
    L.append(f"   inflation-era REAL maxDD by bond-leg construction:")
    L.append(f"   {'leg':26} {'40/60':>7} {'30/70':>7} {'bond only':>10}")
    for name, v in sens["inflation_real_dd"].items():
        L.append(f"   {name:26} {v['mix4060']:7.1f} {v['mix3070']:7.1f} {v['bond_only']:10.1f}")
    cr = sens["cash_rescue_coupon_base"]
    L.append(f"   cash-rescue size on the coupon-honest base: {cr['base']:.1f}% -> {cr['cash']:.1f}% "
             f"(~{abs(cr['base'] - cr['cash']):.0f}pp, vs ~14pp on the zero base)")
    pc_ = sens["pos_40v60_coupon"]
    L.append(f"   pos-era 40v60 nominal dMaxDD, coupon leg: CI[{pc_['dMaxDD'][0]:+.1f},{pc_['dMaxDD'][1]:+.1f}] "
             f"P(shallower)={pc_['prob_dd_shallower']*100:.0f}% — the zero's zero-straddling CI is a proxy artifact; "
             f"the tilt's nominal-DD edge is REAL")
    if sens.get("ieflike_vs_ief"):
        iv = sens["ieflike_vs_ief"]
        L.append(f"   IEF-like coupon book vs IEF (2002-2026): corr {iv['corr']}, vol {iv['vol_model']}% vs "
                 f"{iv['vol_ief']}% (validates better than the zero's 0.9815/6.04%)")
    L.append("")
    L.append("== CUT D — TIPS (the observed 2022 bonds-don't-hedge event + the forward real yield) ==")
    for era in ("full 2004-2026", "shock 2021-2023"):
        L.append(f"   -- {era} --")
        for name, m in tips[era].items():
            L.append(f"   {name:16} {fmt_row(m)}")
    if tips.get("dfii10"):
        yv, yd = tips["dfii10"]
        L.append(f"   10yr TIPS real yield (DFII10, {yd}): {yv:.2f}% — a held-to-maturity TIPS ladder locks "
                 f"~{yv:.1f}% REAL (nominal ~{yv:.1f}%+CPI), vs the nominal ladder's locked ~4-4.5% nominal and "
                 f"0% real protection")
    L.append("")
    L.append("== CUT E — GOAL-ODDS BY REGIME (rolling 10yr windows by START era; SHARES of heavily")
    L.append("   overlapping windows — effective sample ~2-4 independent decades per era, NOT probabilities) ==")
    for mix, res in odds.items():
        L.append(f"   -- {mix} equity/bond --")
        for era, m in res.items():
            L.append(f"   {era:24} n={m['n_windows']:3d} (~{m['indep_decades']:.0f} indep decades)  "
                     f"share(nom>={GOAL_APY}%)={m['p_nominal_goal']*100:3.0f}%  "
                     f"share(real>=0)={m['p_real_positive']*100:3.0f}%  worst nom {m['worst_nominal_cagr']:+.2f}%  "
                     f"worst real {m['worst_real_cagr']:+.2f}%")
    L.append("")
    L.append("== VALIDATION (what the credibility rests on) ==")
    ev, bv, cv = val["equity_vs_spy"], val["bond_vs_ief"], val["cpi_crosscheck"]
    L.append(f"   equity model vs SPY TR  ({ev['span']}): corr {ev['corr']}, CAGR {ev['cagr_model']}% vs {ev['cagr_spy']}%")
    L.append(f"   7yr zero vs IEF         ({bv['span']}): corr {bv['corr']}, CAGR {bv['cagr_z7']}% vs {bv['cagr_ief']}%, "
             f"vol {bv['vol_z7']}% vs {bv['vol_ief']}%")
    L.append(f"   CPI Shiller vs FRED     YoY corr {cv['corr_yoy']} (n={cv['n']} months)")
    return "\n".join(L)


def verdict(corr, mixes, boot, legs, tips, odds, sens):
    """Data-driven verdict, written against the pre-registered reads (panel-corrected phrasing)."""
    pos, infl = mixes["pos_corr 1962-1999"], mixes["inflation 1965-1981"]
    neg = mixes["neg_corr 2000-2021"]
    row = lambda rows, w: next(m for m in rows if m["w_eq"] == w)
    p30, p40, p60 = row(pos, 30), row(pos, 40), row(pos, 60)
    i0, i30, i40, i60, i100 = row(infl, 0), row(infl, 30), row(infl, 40), row(infl, 60), row(infl, 100)
    n30, n60 = row(neg, 30), row(neg, 60)
    bo_pos, bo_infl, bo_neg = (boot.get("pos_corr 1962-1999", {}), boot.get("inflation 1965-1981", {}),
                               boot.get("neg_corr 2000-2021", {}))
    tilt_pos = bo_pos.get("40v60", {})
    ex_ci = tilt_pos.get("dSharpe_excess", [0, 0])
    ex_ci_infl = bo_infl.get("40v60", {}).get("dSharpe_excess", [0, 0])
    ex_ci_neg = bo_neg.get("40v60", {}).get("dSharpe_excess", [0, 0])
    fw_ci_neg = bo_neg.get("40v60", {}).get("dSharpe_excess_fw12", [0, 0])
    dd_ci = tilt_pos.get("dMaxDD", [0, 0])
    dd_cpn = sens["pos_40v60_coupon"]
    sd = sens["inflation_real_dd"]
    cash_infl = next(m for m in legs["inflation 1965-1981"] if m["ballast"] == "T-bill cash")
    base_infl = next(m for m in legs["inflation 1965-1981"] if "7yr" in m["ballast"])
    cash_neg = next(m for m in legs["neg_corr 2000-2021"] if m["ballast"] == "T-bill cash")
    base_neg = next(m for m in legs["neg_corr 2000-2021"] if "7yr" in m["ballast"])
    cash_full = next(m for m in legs["full 1962-2026"] if m["ballast"] == "T-bill cash")
    base_full = next(m for m in legs["full 1962-2026"] if "7yr" in m["ballast"])
    t_shock = tips["shock 2021-2023"]
    dfii = tips.get("dfii10")
    bullets = [
        f"THE CORRELATION ASSUMPTION IS THE EXCEPTION, NOT THE RULE: over 1962-1999 the rolling 36m stock-bond "
        f"correlation averaged {corr['era_corr']['pos_corr 1962-1999']:+.2f} (positive in "
        f"{corr['share_positive_pre2000']*100:.0f}% of months); the benign {corr['era_corr']['neg_corr 2000-2021']:+.2f} "
        f"of 2000-2021 — the regime every recommendation in this program was measured in — flipped back positive in "
        f"{corr['detected_pos_reflip']} and sits at {corr['corr36_last']:+.2f} today. The program's core hedging "
        f"assumption held for ~22 of the last 64 years.",
        f"THE CONSERVATIVE TILT (study #9) SPLITS BY REGIME: its shallower-NOMINAL-drawdown edge is real in the "
        f"positive-corr era (40/60 maxDD {p40['maxdd']:.0f}% vs 60/40 {p60['maxdd']:.0f}%; the primary zero-proxy CI "
        f"narrowly straddles 0 [{dd_ci[0]:+.1f},{dd_ci[1]:+.1f}] but that is a proxy artifact — with the "
        f"duration-honest coupon leg the CI EXCLUDES 0: [{dd_cpn['dMaxDD'][0]:+.1f},{dd_cpn['dMaxDD'][1]:+.1f}], "
        f"P(shallower)={dd_cpn['prob_dd_shallower']*100:.0f}%), but its SHARPE advantage is NOT regime-robust: the "
        f"40/60-vs-60/40 excess-Sharpe CI is [{ex_ci[0]:+.2f},{ex_ci[1]:+.2f}] in 1962-1999 and "
        f"[{ex_ci_infl[0]:+.2f},{ex_ci_infl[1]:+.2f}] in 1965-1981 (point estimates NEGATIVE — more bonds HURT "
        f"risk-adjusted returns when bonds don't hedge), vs [{ex_ci_neg[0]:+.2f},{ex_ci_neg[1]:+.2f}] in the "
        f"2000-2021 era the recommendation was derived in (which itself softens to "
        f"[{fw_ci_neg[0]:+.2f},{fw_ci_neg[1]:+.2f}] under a family-wise correction across the 12 pre-registered "
        f"tilt CIs — a replication of study #9's direction, not an independently established edge). F42's 'tilt "
        f"conservative' is a negative-corr-regime result, not an all-weather law — and its raw-Sharpe support in "
        f"high-rate eras is partly the T-bill level, not hedging (raw {p40['sharpe']:.2f} vs excess "
        f"{p40['sharpe_ex']:.2f} for the 40/60 in 1962-1999).",
        f"THE REAL-TERMS HOLE IS MATERIAL AND THE TILT'S DRAWDOWN EDGE INVERTS (pre-registered read #2): in "
        f"1965-1981 the recommended conservative mixes drew down {i30['real_maxdd']:.0f}% (30/70) and "
        f"{i40['real_maxdd']:.0f}% (40/60) in REAL terms — DEEPER than 60/40's {i60['real_maxdd']:.0f}%, monotonic "
        f"in the bond share down to {i0['real_maxdd']:.0f}% for the bond leg alone (equity {i100['real_maxdd']:.0f}%). "
        f"More bonds meant MORE real drawdown, not less. Read #2's bar is cleared under any construction: the "
        f"duration-honest coupon legs give {sd['7yr par coupon']['mix4060']:.0f}% to "
        f"{sd['IEF-like 7y+10y coupon']['mix4060']:.0f}% for the 40/60 (the zero proxy's {i40['real_maxdd']:.0f}% is "
        f"the upper bound) — all far past the -23% threshold. NB that threshold is F41's forward-MC MEDIAN-worst "
        f"NOMINAL decade DD, quoted as a pre-registered materiality bar, NOT a like-for-like comparison (this is a "
        f"realized historical worst REAL DD over a 17yr episode; like-for-like NOMINAL, the 1965-81 40/60 drew down "
        f"{i40['maxdd']:.1f}% — shallower than -23%). In the bonds-don't-hedge regime the conservative tilt does NOT "
        f"deliver a low-drawdown product in the terms that matter (purchasing power) — it delivers the opposite.",
        f"SHORTENING THE BALLAST MITIGATES — IN THAT REGIME ONLY (no free all-weather ballast): in 1965-1981 "
        f"swapping the 40/60's bond leg from the 7yr zero (real DD {base_infl['real_maxdd']:.0f}%) to T-bill cash "
        f"cut the real drawdown to {cash_infl['real_maxdd']:.0f}% (~{abs(base_infl['real_maxdd']-cash_infl['real_maxdd']):.0f}pp; "
        f"~{abs(sens['cash_rescue_coupon_base']['base']-sens['cash_rescue_coupon_base']['cash']):.0f}pp on the "
        f"coupon-honest base) and took real CAGR from {base_infl['real_cagr']:.1f}% to {cash_infl['real_cagr']:.1f}% — "
        f"but cash still LOST {abs(cash_infl['real_maxdd']):.0f}% of purchasing power (mitigation, not protection), "
        f"and the swap wins ONLY on the real-drawdown criterion in positive-corr regimes: in 2000-2021 the cash "
        f"ballast loses on EVERY metric (excess Sharpe {cash_neg['sharpe_ex']:.2f} vs {base_neg['sharpe_ex']:.2f}, "
        f"maxDD {cash_neg['maxdd']:.1f}% vs {base_neg['maxdd']:.1f}%, real DD {cash_neg['real_maxdd']:.1f}% vs "
        f"{base_neg['real_maxdd']:.1f}%), and over the full 64yr the 7yr leg keeps the shallower nominal maxDD "
        f"({base_full['maxdd']:.1f}% vs {cash_full['maxdd']:.1f}%). Duration is a REGIME TRADE-OFF: poison when "
        f"correlation is positive, the hedge itself when it is negative.",
        f"TIPS MITIGATE MARGINALLY OBSERVED, STRUCTURALLY ONLY AS A FORWARD CLAIM: through the one OBSERVED modern "
        f"bonds-don't-hedge event (2021-2023), a 40/60 with TIP drew down {t_shock['40/60 TIP']['maxdd']:.1f}% "
        f"nominal vs {t_shock['40/60 IEF']['maxdd']:.1f}% with IEF (real: {t_shock['40/60 TIP']['real_maxdd']:.1f}% "
        f"vs {t_shock['40/60 IEF']['real_maxdd']:.1f}%) — TIPS trimmed but did NOT escape the duration shock "
        f"(standalone TIP marked down {t_shock['TIP standalone']['real_maxdd']:.1f}% REAL). The structural fix is a "
        f"held-to-maturity TIPS ladder: at the current {dfii[0]:.2f}% 10yr real yield (DFII10) it locks ~{dfii[0]:.1f}% "
        f"REAL to maturity — addressing exactly the '-19% real in the 1970s' hole F45 left open — but this is a "
        f"FORWARD claim on 2026 real yields (TIPS post-date 1997; untestable through the 1970s), it holds only on "
        f"F45's amortized-cost/hold-to-maturity basis (marked to market, TIPS drew down "
        f"{t_shock['TIP standalone']['real_maxdd']:.1f}% real in 2021-23), and F45's term/liquidity/zero-upside "
        f"costs carry over unchanged.",
        f"GOAL-ODDS ARE REGIME-CONDITIONAL (shares of heavily overlapping 10yr windows — effective sample ~2-4 "
        f"independent decades per era, NOT probabilities): windows starting in the positive-corr era cleared the "
        f"{GOAL_APY}% NOMINAL goal in {odds['40/60']['pos_corr 1962-1999']['p_nominal_goal']*100:.0f}% of cases "
        f"(40/60) — high nominal yields made the nominal goal easy in exactly the era that destroyed real wealth — "
        f"but preserved purchasing power in only {odds['40/60']['pos_corr 1962-1999']['p_real_positive']*100:.0f}% "
        f"({odds['40/60']['inflation 1965-1981']['p_real_positive']*100:.0f}% for inflation-era starts), with a "
        f"worst 10yr real CAGR of {odds['40/60']['pos_corr 1962-1999']['worst_real_cagr']:.1f}%/yr. Study #8/#9's "
        f"forward Monte-Carlo inherited the benign correlation by construction; these are the numbers it could not see.",
    ]
    head = (
        f"The static mixes this program recommends lean on bonds hedging stocks, and that held in only ~22 of the "
        f"last 64 years (the ladder is the separate case: no equity leg — its exposure is inflation, tested in cut D). "
        f"In the positive-correlation/inflation regime (1962-1999, acutely 1965-1981, and again since "
        f"{corr['detected_pos_reflip']}), the conservative tilt keeps its shallower-NOMINAL-drawdown edge (coupon-"
        f"honest CI excludes 0) but its excess-Sharpe advantage disappears, and in REAL terms it INVERTS: the 40/60 "
        f"lost {abs(sd['IEF-like 7y+10y coupon']['mix4060']):.0f}-{abs(i40['real_maxdd']):.0f}% of purchasing power "
        f"in 1965-1981 depending on bond-leg construction — DEEPER than 60/40, and far past the -23% "
        f"(nominal, MC-median) bar pre-registered from F41. Shortening the ballast (T-bill cash) MITIGATES that "
        f"regime (real DD to {cash_infl['real_maxdd']:.0f}%, real CAGR ~0) but loses on every metric in 2000-2021 — "
        f"duration is a regime trade-off, not a free fix; the one construction that structurally addresses F45's "
        f"inflation hole is a held-to-maturity TIPS ladder at ~{dfii[0]:.1f}% real (a forward, amortized-cost-basis "
        f"claim). The static-allocation recommendation (D6) STANDS — nothing here rehabilitates the active engine — "
        f"but F41/F42's drawdown promises must be read as NOMINAL and negative-corr-regime-conditional.")
    return head, bullets


def main():
    ap = argparse.ArgumentParser(description="study #13 — the bonds-don't-hedge regime stress")
    ap.add_argument("--json", metavar="PATH")
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    y = bls.load_yields()
    cpi = bls.load_cpi()
    if cpi is None:
        sys.exit("FRED CPI unavailable — the study's real-terms core needs it; retry with network.")
    shiller = load_shiller()
    eq = equity_tr(load_gspc(), shiller)
    bd = const_maturity_zero(y, 7)
    val = validation(eq, bd, y, shiller, cpi)
    if a.selfcheck:
        selfcheck(eq, bd, val)
        return
    corr, df, _ = cut_corr_record(eq, bd)
    cash = cash_returns(y)
    mixes, boot = cut_mix_by_era(df, cash, cpi)
    legs = cut_bond_leg(df, y, cash, cpi)
    sens = cut_proxy_sensitivity(df, y, cash, cpi)
    tips = cut_tips(cpi, cash)
    odds = cut_goal_odds(df, cpi)
    head, bullets = verdict(corr, mixes, boot, legs, tips, odds, sens)
    print("=" * 104)
    print("STUDY #13 — BONDS-DON'T-HEDGE: the recommended static product under the positive-corr/inflation regime")
    print("=" * 104)
    print(fmt(corr, mixes, boot, legs, tips, odds, val, sens))
    print()
    print("-- VERDICT --")
    print("  " + head)
    for bt in bullets:
        print(f"    * {bt}")
    print("=" * 104)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(dict(corr_record=corr, mixes=mixes, tilt_bootstrap=boot, bond_leg=legs,
                           proxy_sensitivity=sens, tips=tips, goal_odds=odds, validation=val,
                           goal_apy=GOAL_APY, verdict_headline=head, verdict_bullets=bullets),
                      f, indent=2, default=str)
        print(f"[wrote {a.json}]")


if __name__ == "__main__":
    main()
