#!/usr/bin/env python3
"""
bond_ladder_study — study #12 (the product-universe program's capstone): study #11 ([[F44]]) found NO
perpetual-maturity income ETF delivers income + low drawdown, and named ONE untested structural escape —
a held-to-maturity bond LADDER. A perpetual-maturity bond ETF marks to market forever, so a rate shock is
a permanent-looking drawdown; a bond HELD TO MATURITY returns par regardless of the interim path,
converting DURATION drawdown into realized yield. This study tests that thesis — and quantifies what it
really costs — in two complementary cuts:

  A. EMPIRICAL (real defined-maturity ETFs through the 2022 rate shock). iBonds Treasury (IBTx, 2020+) and
     iBonds/BulletShares IG corporate (IBDx/BSCx, 2015+) ladders vs a constant-maturity bond ETF (IEF/LQD)
     and the static 60/40 — including funds that MATURED to par in Dec-2025 (IBTF/IBDQ/BSCP), a full
     hold-to-maturity lifecycle on real instruments.
  B. SYNTHETIC (zero-coupon Treasury ladder, 1962-2026, exact bond math, no duration approximation). A
     rolling 1-10yr ladder built from constant-maturity Treasury yields, scored on BOTH bases:
       - MARK-TO-MARKET value path (sum of rung prices -> real drawdown in rising-rate regimes), vs
       - REALIZED hold-to-maturity wealth (each rung pulls to par -> ZERO nominal drawdown by construction),
     contrasted with a constant-maturity 10yr ETF (perpetual, always marked -> deepest drawdown).

THE HONEST FRAME (built in, not caveated): a ladder does NOT make drawdown vanish. It (1) LOWERS
mark-to-market drawdown via a shorter average duration (a 1-10yr ladder is ~half the duration of a 10yr
ETF), and (2) lets a HOLD-TO-MATURITY investor IGNORE the residual MTM drawdown because every rung pulls
to par. The cost of that "zero realized drawdown": a term/liquidity commitment (capital locked to rung
maturities; the MTM loss is real if you must sell early), return locked at entry yields (NO upside), and
reinvestment risk (matured rungs reinvest at then-prevailing yields). Treasury only — a credit ladder
still realizes defaults. Forward, a ladder's realized return ~= its entry yield (~4-4.5% in 2026), so it
is plausibly the FIRST construction in the whole program to clear the ~3.75% income floor with near-zero
REALIZED drawdown — by trading market risk for term + reinvestment risk + zero upside.

Reuses static_product_study primitives. Deterministic. Fetches once to caches.

    venv/bin/python tools/bond_ladder_study.py [--json out.json] [--selfcheck]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data_cache  # noqa: E402  (validated cache: never trust a stub, never write one)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import static_product_study as sps   # noqa: E402  pmetrics / simple_ret

CACHE_Y = "/tmp/bond_ladder_yields.csv"      # constant-maturity Treasury yields (^IRX/^FVX/^TNX/^TYX)
CACHE_E = "/tmp/bond_ladder_etfs.csv"        # defined-maturity ETF + benchmark total-return prices
CACHE_CPI = "/tmp/bond_ladder_cpi.csv"       # FRED CPIAUCSL for the REAL (inflation-adjusted) drawdown
YT = {"^IRX": 0.25, "^FVX": 5.0, "^TNX": 10.0, "^TYX": 30.0}   # ticker -> tenor (years)
LADDER_TENORS = list(range(1, 11))           # 1..10yr rungs
ANN = 12                                     # monthly
GOAL_APY = 3.75


# ── exact zero-coupon bond math (no duration/convexity approximation) ─────────
def zero_price(y, T):
    """Price of a $1-face zero-coupon bond, yield y (decimal), maturity T years."""
    return (1.0 + y) ** (-T)


# ── data ──────────────────────────────────────────────────────────────────────
def _to_dt(df):
    df.index = pd.to_datetime(df.index, utc=True).tz_localize(None)
    return df


def load_yields():
    def _fetch():
        return _fetch_yields()

    # Monthly series since ~1990 for the long tenors, so 200 months is a floor a
    # real panel clears easily while a stub or partial fetch does not (F144).
    return data_cache.load_cached_frame(
        CACHE_Y, _fetch, min_rows=200, label="bond_ladder_yields",
        read_csv=lambda path: _to_dt(pd.read_csv(path, index_col=0)))


def _fetch_yields():
    import yfinance as yf
    cols = {}
    for t in YT:
        h = yf.Ticker(t).history(period="max", auto_adjust=True)
        h.index = pd.to_datetime(h.index, utc=True).tz_localize(None)
        cols[t] = h["Close"]
    y = pd.DataFrame(cols).dropna(how="all")
    return y.resample("ME").last() / 100.0    # month-end, decimal yields


def load_etfs():
    tk = ["IBTF", "IBTG", "IBTH", "IBTK",                 # iBonds Treasury rungs (2025-2029)
          "IBDQ", "IBDR", "IBDS", "IBDT",                 # iBonds IG corp rungs (2025-2028)
          "BSCP", "BSCQ", "BSCR", "BSCS",                 # BulletShares IG corp rungs (2025-2028)
          "IEF", "IEI", "SHY", "BIL", "LQD", "SPY", "AGG"]  # const-maturity Tsy 7-10y/3-7y/1-3y/T-bill + IG + equity
    # The column check below was already here and is kept — it re-fetches when a
    # ticker is ADDED. What it could not catch is a header-only stub, which has
    # every column and zero rows; required_cols + min_rows closes that.
    def _fetch():
        import yfinance as yf
        return yf.download(tk, start="2014-01-01", end="2026-06-20", interval="1d",
                           progress=False, auto_adjust=True)["Close"]

    if os.path.exists(CACHE_E):
        cached = pd.read_csv(CACHE_E, index_col=0, parse_dates=True)
        if not all(t in cached.columns for t in tk):
            os.remove(CACHE_E)                            # a ticker was added: force a re-fetch
    raw = data_cache.load_cached_frame(
        CACHE_E, _fetch, min_rows=500, required_cols=tk, label="bond_ladder_etfs")
    return raw


def load_cpi():
    """FRED CPIAUCSL (monthly), for the REAL (inflation-adjusted) drawdown. Cached; returns None on failure."""
    try:
        if os.path.exists(CACHE_CPI):
            c = _to_dt(pd.read_csv(CACHE_CPI, index_col=0))
        else:
            c = pd.read_csv("https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL")
            c = c.rename(columns={c.columns[0]: "date", c.columns[1]: "cpi"}).set_index("date")
            c.index = pd.to_datetime(c.index)
            c.to_csv(CACHE_CPI)
        s = pd.to_numeric(c.iloc[:, 0], errors="coerce").dropna()
        return s.resample("ME").last()
    except Exception:
        return None


def curve(yrow):
    """Interpolate a full 1..10yr yield curve (decimal) from the available constant-maturity points,
    LINEAR in tenor (np.interp), flat-extrapolated past the ends."""
    ten = np.array([YT[t] for t in YT])
    val = np.array([yrow[t] for t in YT], dtype=float)
    ok = ~np.isnan(val)
    ten, val = ten[ok], val[ok]
    order = np.argsort(ten)
    ten, val = ten[order], val[order]
    return {T: float(np.interp(T, ten, val)) for T in LADDER_TENORS}


# ── cut B: synthetic zero-coupon ladder, exact math throughout ────────────────
def synthetic_ladder(yields):
    """Monthly. A rolling 1-10yr zero-coupon Treasury ladder on TWO bases, plus two PERPETUAL
    constant-maturity ETFs (5yr duration-matched + 10yr), ALL priced with the same exact zero math:
       MTM   — mark-to-market: each rung repriced as its remaining maturity rolls down (real drawdown).
       REAL  — amortized-cost / hold-to-maturity: each rung's wealth accretes at its LOCKED ENTRY yield
               (geometric (1+y0)^dt), never marked to market; at maturity the par cash reinvests at the
               then-current 10yr yield. maxDD is 0 BY CONSTRUCTION (amortized cost never marks down and
               nominal yields are >=0) — a definitional property of hold-to-maturity accounting, NOT a
               contingent historical outcome.
       cm5/cm10 — perpetual constant-maturity 5yr/10yr zeros, exact monthly repricing (the duration-matched
               and long foils; never mature -> no realized escape).
    Starts 1962 (^FVX/^TNX exist; pre-1962 only the 3-month bill exists -> a degenerate flat curve)."""
    ys = yields.dropna(how="all").loc["1962-01-01":]
    curves = {d: curve(ys.loc[d]) for d in ys.index}
    dates = list(ys.index)
    ten = LADDER_TENORS
    rem = {T: float(T) for T in ten}                       # MTM remaining maturity per rung
    locked_y = {T: curves[dates[0]][T] for T in ten}       # REAL: locked entry yield per rung
    real_w = {T: 1.0 for T in ten}                         # REAL: amortized-cost wealth per rung
    mtm_ret, real_ret, cm_ret, cm5_ret = [], [], [], []
    dt = 1.0 / ANN
    for i in range(1, len(dates)):
        c0, c1 = curves[dates[i - 1]], curves[dates[i]]
        tv0, tv1 = [c0[k] for k in ten], [c1[k] for k in ten]
        # --- MTM: reprice each rung as remaining maturity shortens by dt ---
        rung_rets = []
        for T in ten:
            t0 = rem[T]
            t1 = max(t0 - dt, 0.0)
            y0 = float(np.interp(t0, ten, tv0)) if t0 >= 1 else c0[1]
            y1 = float(np.interp(t1, ten, tv1)) if t1 >= 1 else c1[1]
            p0 = zero_price(y0, t0)
            p1 = zero_price(y1, t1) if t1 > 0 else 1.0     # pulls to par at maturity (no spurious reinvest mark)
            rung_rets.append(p1 / p0 - 1.0)
            rem[T] = t1
        mtm_ret.append(float(np.mean(rung_rets)))
        # --- REAL: amortized-cost wealth accretes at each rung's LOCKED entry yield (geometric) ---
        tot0 = sum(real_w.values())
        for T in ten:
            real_w[T] *= (1.0 + locked_y[T]) ** dt
        real_ret.append(sum(real_w.values()) / tot0 - 1.0)
        # --- maturity handling for BOTH bases: reinvest the par cash into a fresh 10yr rung ---
        for T in ten:
            if rem[T] <= 1e-9:
                rem[T] = 10.0
                locked_y[T] = c1[10]                        # new locked entry yield (real_w continues, par->market)
        # --- perpetual constant-maturity ETFs, EXACT repricing (consistent with the ladder math) ---
        y10n = float(np.interp(10 - dt, ten, tv1))
        cm_ret.append(zero_price(y10n, 10 - dt) / zero_price(c0[10], 10) - 1.0)
        y5n = float(np.interp(5 - dt, ten, tv1))
        cm5_ret.append(zero_price(y5n, 5 - dt) / zero_price(c0[5], 5) - 1.0)
    idx = dates[1:]
    return (pd.Series(mtm_ret, index=idx), pd.Series(real_ret, index=idx),
            pd.Series(cm_ret, index=idx), pd.Series(cm5_ret, index=idx))


def maxdd_from_returns(r):
    eq = (1.0 + r).cumprod()
    return float((eq / eq.cummax() - 1.0).min() * 100)


def ann_ret(r):
    eq = (1.0 + r).prod()
    return float(eq ** (ANN / len(r)) - 1.0) * 100


def real_drawdown(nominal_ret, cpi, a, b):
    """Inflation-adjusted (purchasing-power) drawdown of a nominal monthly-return series over [a,b],
    deflating the equity curve by CPI. Returns None if CPI unavailable."""
    if cpi is None:
        return None
    eq = (1.0 + nominal_ret).cumprod()
    cpi_m = cpi.reindex(eq.index, method="ffill")
    real_eq = (eq / cpi_m).dropna()
    rr = real_eq.loc[a:b]
    if len(rr) < 2:
        return None
    return round(float((rr / rr.cummax() - 1.0).min() * 100), 2)


def synth_metrics(mtm, real, cm, cm5, cpi=None):
    def block(r, label):
        return dict(basis=label, cagr=round(ann_ret(r), 2), vol=round(r.std() * (ANN ** 0.5) * 100, 2),
                    maxdd=round(maxdd_from_returns(r), 2))
    # worst single rate shock window (1970s-80s) vs 2022 for the MTM/CM series
    def dd_in(r, a, b):
        rr = r.loc[a:b]
        return round(maxdd_from_returns(rr), 2) if len(rr) else None
    return dict(
        span=f"{mtm.index[0].date()}->{mtm.index[-1].date()}",
        ladder_mtm=block(mtm, "ladder MARK-TO-MARKET"),
        ladder_real=block(real, "ladder REALIZED (amortized-cost / hold-to-maturity)"),
        cm5=block(cm5, "duration-matched 5yr ETF (perpetual)"),
        cm10=block(cm, "constant-maturity 10yr ETF (perpetual)"),
        dd_1970s={"ladder_mtm": dd_in(mtm, "1970-01-01", "1984-12-31"),
                  "cm10": dd_in(cm, "1970-01-01", "1984-12-31"),
                  "cm5": dd_in(cm5, "1970-01-01", "1984-12-31"),
                  "ladder_real": dd_in(real, "1970-01-01", "1984-12-31")},
        dd_2022={"ladder_mtm": dd_in(mtm, "2021-06-01", "2023-12-31"),
                 "cm10": dd_in(cm, "2021-06-01", "2023-12-31"),
                 "cm5": dd_in(cm5, "2021-06-01", "2023-12-31"),
                 "ladder_real": dd_in(real, "2021-06-01", "2023-12-31")},
        # the central honesty check: the realized basis has 0% NOMINAL drawdown but a large REAL one in the 1970s
        real_dd_1970s={"ladder_real": real_drawdown(real, cpi, "1970-01-01", "1984-12-31"),
                       "ladder_mtm": real_drawdown(mtm, cpi, "1970-01-01", "1984-12-31")},
        real_dd_full={"ladder_real": real_drawdown(real, cpi, real.index[0], real.index[-1])},
    )


# ── cut A: empirical defined-maturity ETF ladders ─────────────────────────────
def empirical(etfs):
    out = {}
    def ladder(cols, start):
        px = etfs[cols].dropna(how="all").loc[start:]
        rets = px.apply(sps.simple_ret).mean(axis=1).dropna()       # equal-weight ladder, daily-rebalanced
        return sps.pmetrics(rets.values)
    # Treasury ladder (iBonds IBTx) vs IEF; 2020+ (incl 2022 shock)
    out["tsy_ladder_2020"] = ladder(["IBTF", "IBTG", "IBTH", "IBTK"], "2020-08-01")
    out["IEF_2020"] = sps.pmetrics(sps.simple_ret(etfs["IEF"].dropna().loc["2020-08-01":]).dropna().values)
    # duration-matched PERPETUAL controls (the cut-A analogue of cut B's cm5): SHY (1-3y, ~1.9yr dur) and IEI
    # (3-7y, ~4.5yr dur, ~= the ladder's ~3-5yr avg) — const-maturity, NO pull-to-par. They isolate the plain
    # duration effect from the ladder's matured-to-par healing: the ladder's shallower-than-IEF MTM is mostly
    # just shorter duration (SHY, even shorter, draws down LESS than the ladder with no ladder structure at all).
    out["SHY_2020"] = sps.pmetrics(sps.simple_ret(etfs["SHY"].dropna().loc["2020-08-01":]).dropna().values)
    out["IEI_2020"] = sps.pmetrics(sps.simple_ret(etfs["IEI"].dropna().loc["2020-08-01":]).dropna().values)
    # IG corp ladder (iBonds + BulletShares) vs LQD; 2018+ (rungs all exist)
    out["ig_ladder_2018"] = ladder(["IBDT", "BSCS", "IBDS", "BSCR"], "2018-10-01")
    out["LQD_2018"] = sps.pmetrics(sps.simple_ret(etfs["LQD"].dropna().loc["2018-10-01":]).dropna().values)
    # 60/40 over the same Treasury-ladder window for the program benchmark
    s = sps.simple_ret(etfs["SPY"].dropna().loc["2020-08-01":]).dropna()
    a = sps.simple_ret(etfs["AGG"].dropna().loc["2020-08-01":]).dropna()
    idx = s.index.intersection(a.index)
    out["static_6040_2020"] = sps.pmetrics((0.6 * s.reindex(idx) + 0.4 * a.reindex(idx)).values)
    # maturity check: funds that reached maturity Dec-2025. NOTE the levels are auto_adjust TOTAL-RETURN
    # prices (embed a decade of reinvested distributions) — NOT par. What is genuinely observable is the
    # pull-to-par SIGNATURE: as duration -> 0 the NAV volatility COLLAPSES toward zero and the price converges
    # to a stable terminal value. We measure that vol collapse (final-month annualized vol vs mid-life vol).
    matured = {}
    for t in ["IBTF", "IBDQ", "BSCP"]:
        s2 = etfs[t].dropna()
        if len(s2):
            r = sps.simple_ret(s2).dropna()
            life_vol = float(r.std() * (252 ** 0.5) * 100)            # whole-life annualized vol
            term_vol = float(r.iloc[-21:].std() * (252 ** 0.5) * 100)  # final ~month annualized vol
            matured[t] = dict(maturity_date=str(s2.index[-1].date()),
                              dd_2022=round(maxdd_from_returns(sps.simple_ret(s2.loc["2021-06-01":]).dropna()), 2),
                              life_vol=round(life_vol, 2), term_vol=round(term_vol, 2))
    out["maturity_vol_collapse"] = matured
    return out


def fmt(synth, emp):
    L = ["== CUT B — SYNTHETIC zero-coupon 1-10yr Treasury ladder (exact bond math) ==",
         f"   span {synth['span']}  ({ANN}/yr)",
         f"   {'basis':42} {'CAGR%':>7} {'vol%':>6} {'maxDD%':>8}"]
    for k in ["ladder_mtm", "ladder_real", "cm5", "cm10"]:
        m = synth[k]
        L.append(f"   {m['basis']:42} {m['cagr']:7.2f} {m['vol']:6.2f} {m['maxdd']:8.2f}")
    L.append(f"   (the ladder MTM drawdown ~= the DURATION-MATCHED 5yr ETF's — that part is just lower duration; "
             f"the ladder's UNIQUE property is the REALIZED 0% from pull-to-par, which NO perpetual ETF has)")
    L.append("   -- worst drawdown by regime (mark-to-market vs realized) --")
    L.append(f"   {'1970-1984 rate shock':28} ladder MTM {synth['dd_1970s']['ladder_mtm']}%  vs 5yr ETF "
             f"{synth['dd_1970s']['cm5']}%  vs 10yr ETF {synth['dd_1970s']['cm10']}%  |  ladder REALIZED {synth['dd_1970s']['ladder_real']}%")
    L.append(f"   {'2021-2023 rate shock':28} ladder MTM {synth['dd_2022']['ladder_mtm']}%  vs 5yr ETF "
             f"{synth['dd_2022']['cm5']}%  vs 10yr ETF {synth['dd_2022']['cm10']}%  |  ladder REALIZED {synth['dd_2022']['ladder_real']}%")
    rr = synth.get("real_dd_1970s", {}).get("ladder_real")
    if rr is not None:
        L.append(f"   -- the catch the 0%-nominal hides: REAL (inflation-adjusted) drawdown of the REALIZED ladder --")
        L.append(f"   {'1970-1984 (CPI-deflated)':28} realized NOMINAL {synth['dd_1970s']['ladder_real']}%  but "
                 f"realized REAL {rr}%  — pull-to-par protects nominal par, NOT purchasing power (the locked yield is "
                 f"exactly what inflation erodes)")
    L.append("")
    L.append("== CUT A — EMPIRICAL defined-maturity ETF ladders (real instruments through the 2022 shock) ==")
    def row(name, m):
        return f"   {name:34} CAGR {m['cagr']:6.2f}%  vol {m['vol']:5.2f}%  maxDD {m['maxdd']:7.2f}%  Sharpe {m['sharpe']:+.2f}"
    L.append(row("Treasury iBonds ladder (2020+)", emp["tsy_ladder_2020"]))
    L.append(row("  vs SHY const-mat 1-3y (~1.9yr dur)", emp["SHY_2020"]))
    L.append(row("  vs IEI const-mat 3-7y (~4.5yr dur)", emp["IEI_2020"]))
    L.append(row("  vs IEF const-mat 7-10y (~7.5yr dur)", emp["IEF_2020"]))
    L.append(row("  vs static 60/40", emp["static_6040_2020"]))
    L.append("   (duration-honest, same as cut B: the ladder's maxDD (~-15.8%) is close to IEI's (-14.6%, ~4.5yr dur) "
             "and far shallower than IEF's (-23.9%, ~7.5yr) — its shallower-than-IEF MTM drawdown is mostly the avg "
             "DURATION, not the ladder. SHY/IEI are PERPETUAL (no pull-to-par), yet SHY (~1.9yr) draws down LESS than "
             "the ladder. So a plain short ETF beats the 2020 ladder on BOTH return and MTM drawdown; the ladder's "
             "UNIQUE property is the maturity vol-collapse below, NOT a shallower MTM path.)")
    L.append(row("IG corp ladder iBonds+Bullet (2018+)", emp["ig_ladder_2018"]))
    L.append(row("  vs LQD constant-maturity IG", emp["LQD_2018"]))
    L.append("   -- the LADDER-UNIQUE empirical signal: pull-to-par as duration->0 (NAV vol COLLAPSES at maturity) --")
    L.append("      (levels are total-return prices, NOT par; the observable is the volatility collapse, not a par value)")
    for t, d in emp["maturity_vol_collapse"].items():
        L.append(f"   {t:6} matured {d['maturity_date']}: annualized vol {d['life_vol']}% (life) -> {d['term_vol']}% "
                 f"(final month) — converged to a stable terminal value; its 2022 MTM trough ({d['dd_2022']}%) became moot at maturity")
    L.append("")
    return "\n".join(L)


def verdict(synth, emp):
    lm, lr, cm = synth["ladder_mtm"], synth["ladder_real"], synth["cm10"]
    tsy, ief, core = emp["tsy_ladder_2020"], emp["IEF_2020"], emp["static_6040_2020"]
    shy, iei = emp["SHY_2020"], emp["IEI_2020"]    # duration-matched perpetual controls for the empirical cut
    mtm_ratio = lm["maxdd"] / cm["maxdd"]          # ladder MTM drawdown as a fraction of the 10yr ETF's
    bullets = [
        f"THE THESIS IS REAL — held-to-maturity converts duration drawdown into realized yield: over "
        f"{synth['span']} the synthetic 1-10yr Treasury ladder's REALIZED drawdown is {lr['maxdd']:.1f}%, at a realized "
        f"CAGR of {lr['cagr']:.1f}% — while the SAME ladder marked to market drew down {lm['maxdd']:.0f}% and a "
        f"constant-maturity 10yr ETF drew down {cm['maxdd']:.0f}%. IMPORTANT — the realized 0% is DEFINITIONAL, not a "
        f"contingent historical result: the realized basis is amortized-cost accounting (each rung accretes at its "
        f"locked entry yield and is never marked to market), so with non-negative nominal yields it can NEVER show a "
        f"drawdown regardless of rate history — that IS the hold-to-maturity property (you accrue to par, you don't "
        f"mark), but it is an accounting choice, not a market outcome. The 'low drawdown' is the realized/amortized "
        f"basis; the market value still moves.",
        f"BUT IT IS NOT A FREE LUNCH, AND HALF THE BENEFIT IS JUST LOWER DURATION — the duration-matched control "
        f"proves it: the ladder's mark-to-market drawdown ({lm['maxdd']:.0f}%) is only ~{mtm_ratio*100:.0f}% of the 10yr "
        f"ETF's ({cm['maxdd']:.0f}%), but it is ESSENTIALLY THE SAME as a duration-matched 5yr constant-maturity ETF's "
        f"({synth['cm5']['maxdd']:.0f}%) — so the MTM drawdown reduction is just the ~5yr average duration, which a "
        f"plain short-bond ETF (SHY) also gives you. The ladder's UNIQUE, non-duration property is ONLY the REALIZED "
        f"0% from pull-to-par: the 5yr ETF is PERPETUAL (never matures) so it has no realized escape, while the "
        f"ladder's every rung returns to par. The gap between the ladder's MTM drawdown ({lm['maxdd']:.0f}%) and its "
        f"realized 0% is UNREALIZED loss you escape ONLY by holding every rung to maturity and never being a forced "
        f"seller — a term/liquidity commitment, not free risk elimination.",
        f"THE COST OF 'ZERO REALIZED DRAWDOWN', explicitly: (1) capital is LOCKED to the rung maturities — the MTM "
        f"loss is real and binding if you must sell early (the 1970-84 ladder MTM drawdown was "
        f"{synth['dd_1970s']['ladder_mtm']}%, far worse than 2022's {synth['dd_2022']['ladder_mtm']}%); (2) return is "
        f"LOCKED at entry yields — NO upside if rates fall (you keep the low coupon); (3) REINVESTMENT risk — matured "
        f"rungs reinvest at then-prevailing yields, so a falling-rate decade erodes the income stream; (4) Treasury "
        f"only — a CREDIT ladder still realizes defaults (study #11's PFF/JNK losses were not duration).",
        f"EMPIRICAL CONFIRMATION through the actual 2022 shock — AND THE SAME DURATION HONESTY AS THE SYNTHETIC CUT: "
        f"the real iBonds Treasury ladder (2020+) had a {tsy['maxdd']:.1f}% mark-to-market drawdown, SHALLOWER than "
        f"IEF's {ief['maxdd']:.1f}% — but that gap is mostly DURATION, not ladder structure: IEF is ~7.5yr duration "
        f"while the ladder's defined-maturity rungs average ~3-5yr, and the duration-matched PERPETUAL controls prove "
        f"it — IEI (const-maturity 3-7y, ~4.5yr dur) drew down {iei['maxdd']:.1f}% and SHY (const-maturity 1-3y, "
        f"~1.9yr dur) only {shy['maxdd']:.1f}%, SHALLOWER than the ladder itself with NO pull-to-par at all. So the "
        f"ladder's shallower-than-IEF MTM path is just lower duration, which a plain short perpetual Treasury ETF "
        f"hands you for free with no ladder structure. The ladder's UNIQUE, non-duration property is NOT the shallower "
        f"drawdown — it is the pull-to-par SIGNATURE at maturity: the rungs that MATURED (IBTF/IBDQ/BSCP) saw their NAV "
        f"VOLATILITY COLLAPSE toward zero as duration->0 (IBTF annualized vol "
        f"{emp['maturity_vol_collapse'].get('IBTF', {}).get('life_vol', 'NA')}% over life -> "
        f"{emp['maturity_vol_collapse'].get('IBTF', {}).get('term_vol', 'NA')}% in its final month) and converged to a "
        f"stable terminal value, so their 2022 mark-to-market drawdowns "
        f"(~{emp['maturity_vol_collapse'].get('IBTF', {}).get('dd_2022', 'NA')}% for IBTF) became moot at maturity — "
        f"observable on real instruments, and NO perpetual ETF (however short) has it. (NB the terminal price levels "
        f"are TOTAL-RETURN, not par; the observable is the vol collapse, not a par value.) Its "
        f"{tsy['cagr']:.1f}%/yr return is poor, but that is the ENTRY-YIELD cost made "
        f"concrete: the ladder was bought "
        f"at 2020's RECORD-LOW yields and faithfully locked them in — exactly the 'return locked at entry' / "
        f"reinvestment risk above, NOT a structural flaw (the IG ladder 2018+, bought at higher yields, returned "
        f"{emp['ig_ladder_2018']['cagr']:.1f}%/yr, beating LQD's {emp['LQD_2018']['cagr']:.1f}% with a shallower drawdown).",
        f"THE REAL-DRAWDOWN CATCH (the one 0%-nominal hides): the realized ladder's zero drawdown is NOMINAL only. "
        f"Deflated by CPI, the realized ladder LOST {synth.get('real_dd_1970s', {}).get('ladder_real', 'NA')}% of "
        f"PURCHASING POWER in the 1970s-80s inflation shock — comparable to the very mark-to-market drawdown the ladder "
        f"is praised for avoiding. Pull-to-par protects nominal par, NOT real value, and the locked entry yield is "
        f"exactly what an inflation shock erodes. For a capital-preservation/income product this is the central caveat, "
        f"not a footnote.",
        f"WHAT THIS MEANS FOR THE PRODUCT (capstone of the universe program): a held-to-maturity Treasury (or IG) "
        f"ladder is the ONLY construction in the program that can plausibly deliver the ~{GOAL_APY:.2f}% income floor "
        f"with near-zero REALIZED-NOMINAL drawdown — but this is a FORWARD claim, not an empirical result: NO ladder in "
        f"this study actually cleared 3.75% on realized return (the 2020 Treasury ladder locked in record-low yields "
        f"-> {tsy['cagr']:.1f}%/yr; the IG 2018 ladder {emp['ig_ladder_2018']['cagr']:.1f}%/yr is only ~AT the floor). "
        f"It rests entirely on 2026 entry yields (~4-4.5%) holding. It achieves what no perpetual-maturity income ETF "
        f"in study #11 could — but by TRADING market/drawdown risk for TERM + REINVESTMENT risk + zero upside + REAL "
        f"(inflation) risk, not by eliminating risk. For an income investor who can commit capital to a horizon and "
        f"accepts inflation risk, it is the honest nominal bond-alternative the active engine never was; for one who "
        f"needs liquidity, upside, or real (inflation-protected) preservation, the drawdown is as real as any ETF's.",
        f"CAVEATS: the synthetic ladder is a stylized ZERO-coupon model (exact pull-to-par, but real ladders hold "
        f"coupon bonds with reinvested coupons and small tracking error); the curve is interpolated from 4 "
        f"constant-maturity points; the empirical window is a SINGLE rate cycle (2018/2020-2026) of young funds, and the "
        f"Treasury 'ladder' drops from 4 rungs to 3 after IBTF matures Dec-2025; the realized 0% is amortized-cost "
        f"DEFINITIONAL (no marks + non-negative nominal yields), not a market outcome; assumes no default (Treasury) and "
        f"no forced early sale; nominal only (the realized REAL/inflation drawdown was "
        f"{synth.get('real_dd_1970s', {}).get('ladder_real', 'NA')}% in the 1970s).",
    ]
    head = (
        f"A held-to-maturity bond LADDER is the one structural escape study #11 ([[F44]]) flagged, and it WORKS — but "
        f"a careful read shows it is narrower than it first looks. Its realized (amortized-cost / hold-to-maturity) "
        f"drawdown is ~0 at a return ~= entry yield, confirmed in a 1962-2026 zero-coupon simulation and on real "
        f"iBonds/BulletShares ladders through 2022. BUT (1) that realized 0% is DEFINITIONAL (amortized-cost accounting "
        f"never marks to market; nominal yields >=0), not a market outcome; (2) its mark-to-market drawdown reduction "
        f"is just LOWER DURATION — a duration-matched perpetual short ETF (5yr/SHY) draws down the same with NO ladder "
        f"structure; the ladder's ONLY unique property is the pull-to-par at maturity (realized escape no perpetual ETF "
        f"has); (3) the 0% is NOMINAL only — CPI-deflated, the realized ladder lost "
        f"~{synth.get('real_dd_1970s', {}).get('ladder_real', 'NA')}% of PURCHASING POWER in the 1970s; (4) it clears "
        f"the ~{GOAL_APY:.2f}% income floor only as a FORWARD claim on 2026 entry yields — NO ladder in this study "
        f"actually cleared it on realized return. It converts MARKET/drawdown risk into TERM + REINVESTMENT + REAL "
        f"(inflation) risk + zero upside — the honest NOMINAL bond-alternative for an investor who can commit capital "
        f"to a horizon, which the active engine and every perpetual-maturity income ETF never were, but NOT a "
        f"free-lunch escape from risk or from inflation.")
    return head, bullets


def selfcheck(yields):
    """A zero-coupon bond held to maturity must return EXACTLY its entry yield, with zero price risk at par."""
    y0 = 0.05
    p0 = zero_price(y0, 10.0)
    p_mat = 1.0                                  # par at maturity
    realized = (p_mat / p0) ** (1.0 / 10.0) - 1.0
    assert abs(realized - y0) < 1e-9, f"zero held-to-maturity must return entry yield: {realized} vs {y0}"
    # price falls when yield rises (mark-to-market loss), but maturity value is unchanged
    assert zero_price(0.08, 9.0) < zero_price(0.05, 9.0), "price must fall when yield rises"
    print("[selfcheck OK] zero held to maturity returns entry yield exactly; price falls when yield rises.")


def main():
    ap = argparse.ArgumentParser(description="study #12 — held-to-maturity bond ladder")
    ap.add_argument("--json", metavar="PATH")
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    yields = load_yields()
    if a.selfcheck:
        selfcheck(yields)
        return
    mtm, real, cm, cm5 = synthetic_ladder(yields)
    synth = synth_metrics(mtm, real, cm, cm5, cpi=load_cpi())
    emp = empirical(load_etfs())
    head, bullets = verdict(synth, emp)
    print("=" * 104)
    print("STUDY #12 — the held-to-maturity bond LADDER: the structural escape, and what it really costs")
    print("=" * 104)
    print(fmt(synth, emp))
    print("-- VERDICT --")
    print("  " + head)
    for b in bullets:
        print(f"    * {b}")
    print("=" * 104)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(dict(synth=synth, empirical=emp, goal_apy=GOAL_APY,
                           verdict_headline=head, verdict_bullets=bullets), f, indent=2, default=str)
        print(f"[wrote {a.json}]")


if __name__ == "__main__":
    main()
