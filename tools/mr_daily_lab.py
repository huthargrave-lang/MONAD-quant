#!/usr/bin/env python3
"""
mr_daily_lab — read-only research harness for leverage-free DAILY mean-reversion.

Reproduces and extends RESEARCH_WEB.md E10/F18-F21/D5. One leak-free methodology,
many variants, on ~12yr adjusted daily data (yfinance, 2014-2026):

    venv/bin/python tools/mr_daily_lab.py [acf|exit|portfolio|xsect|conditional|bonds|kelly|all]

Entry convention everywhere: buy the close of a DOWN day (exploits the negative
lag-1 autocorrelation); long-only; 200d-MA bear gate; 5bps round-trip cost. NOT a
trading system and NOT imported by the live path — it fetches from the network and
prints tables. Findings (all surfaced in `ctx web`):
  F18  F16 replicates but its naive t-stats are ~3x inflated (use a robust SE)
  F19  the EXIT (horizon vs %-stop), not the entry, is the dominant lever
  F20  what does NOT work: long-only cross-sectional, adaptive Kelly, low-vol
       entry-filtering, bond signal-trading
  F21  honest ceiling: equal-weight + vol-targeted sizing ~Sharpe 0.66 / 4%/yr / -10% DD
"""
from __future__ import annotations
import argparse
import math
import os
import sys
import warnings

warnings.filterwarnings("ignore")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

START, END, COST = "2014-01-01", "2026-06-20", 0.0005
EQUITY = ["QQQ", "SPY", "IWM", "DIA"]
DIVERS = EQUITY + ["GLD", "HYG", "IEF", "TLT"]
SECTORS = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB"]
UNIV = sorted(set(DIVERS + SECTORS))
CACHE = "/tmp/mr_daily_close.csv"   # ephemeral; re-fetched if absent (no repo data committed)


def load():
    if os.path.exists(CACHE):
        return pd.read_csv(CACHE, index_col=0, parse_dates=True)
    import yfinance as yf
    raw = yf.download(UNIV, start=START, end=END, interval="1d", progress=False, auto_adjust=True)
    px = raw["Close"][UNIV].dropna(how="all")
    px.to_csv(CACHE)
    return px


def perf(r, ann=252):
    r = pd.Series(r).dropna()
    if len(r) < 5 or r.std() == 0:
        return dict(ann=0, vol=0, sharpe=0, maxdd=0, t=0, n=len(r))
    mu, vol = r.mean() * ann, r.std() * math.sqrt(ann)
    eq = np.exp(r.cumsum()); dd = (eq / eq.cummax() - 1).min() * 100
    return dict(ann=mu * 100, vol=vol * 100, sharpe=mu / vol, maxdd=dd,
                t=r.mean() / (r.std() / math.sqrt(len(r))), n=len(r))


def sleeve(PX, sym, H=5, gate=True, vol_filter=False):
    """Daily-return series of the non-overlapping dip+H, long-only sleeve."""
    c = PX[sym].dropna(); idx = c.index; cv = c.values; n = len(cv)
    ret = np.zeros(n); ret[1:] = np.log(cv[1:] / cv[:-1])
    ma = pd.Series(cv).rolling(200).mean().values
    v20 = pd.Series(ret).rolling(20).std().shift(1).values
    vmed = pd.Series(v20).rolling(252).median().shift(1).values
    inv = np.zeros(n); d = 1
    while d < n - 1:
        ok = ret[d] < 0
        if gate:
            ok = ok and cv[d] > ma[d]
        if vol_filter:
            ok = ok and (v20[d] < vmed[d] if not math.isnan(vmed[d]) else False)
        if ok:
            for k in range(d + 1, min(d + 1 + H, n)):
                inv[k] = 1
            d += H
        else:
            d += 1
    s = inv * ret
    ex = np.where((inv[:-1] == 1) & (inv[1:] == 0))[0] + 1; s[ex] -= COST
    return pd.Series(s, index=idx)


def vol_target(r, target=0.10, lb=60, maxlev=3.0):
    rv = r.rolling(lb).std().shift(1) * math.sqrt(252)
    lev = (target / rv).clip(upper=maxlev).fillna(0.0)
    return r * lev, lev.mean()


# ── replication: lag-1 autocorrelation, naive vs heteroskedasticity-robust t ──
def cmd_acf(PX):
    print("F18 — lag-1 autocorrelation: naive t (=rho*sqrt n, what F16 used) vs robust t")
    print(f"{'tkr':5} {'n':>5} {'rho1':>8} {'t_naive':>8} {'t_robust':>9}")
    for t in EQUITY + ["TQQQ", "SOXL"] if "TQQQ" in PX.columns else EQUITY:
        if t not in PX.columns:
            continue
        r = np.log(PX[t].dropna() / PX[t].dropna().shift(1)).dropna().values
        c = r - r.mean(); n = len(c); den = (c ** 2).sum()
        rho = (c[1:] * c[:-1]).sum() / den
        rv = (c[1:] ** 2 * c[:-1] ** 2).sum() / den ** 2
        print(f"{t:5} {n:5d} {rho:8.3f} {rho*math.sqrt(n):8.2f} {rho/math.sqrt(rv):9.2f}")


# ── F19: exit mechanism (horizon vs fixed %-stop) on the same dip entry ────────
def cmd_exit(PX):
    """F19: same dip entry, horizon exits vs a fixed ±0.8% stop/target (needs OHLC,
    so this fetches the four equities directly; leak-free — exits use only t+1.. bars)."""
    import yfinance as yf
    BAND, MAXH = 0.008, 10
    print("F19 — same dip entry, three exits (mean bps/trade, net 5bps)")
    print(f"{'tkr':5} {'H=1':>9} {'H=5 horizon':>12} {'+/-0.8% stop':>13}")
    for tk in EQUITY:
        df = yf.download(tk, start=START, end=END, interval="1d", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df = df.droplevel(1, axis=1)
        c, h, l = df["Close"].values, df["High"].values, df["Low"].values
        n = len(c); r = np.zeros(n); r[1:] = np.log(c[1:] / c[:-1])
        d1, d5, st = [], [], []
        for t in range(1, n - 1):
            if r[t] >= 0:
                continue
            e = c[t]
            d1.append(math.log(c[min(t + 1, n - 1)] / e) - COST)
            d5.append(math.log(c[min(t + 5, n - 1)] / e) - COST)
            ex = None
            for j in range(t + 1, min(t + 1 + MAXH, n)):     # stop wins ties (conservative)
                if l[j] <= e * (1 - BAND): ex = math.log(1 - BAND); break
                if h[j] >= e * (1 + BAND): ex = math.log(1 + BAND); break
            if ex is None:
                ex = math.log(c[min(t + MAXH, n - 1)] / e)
            st.append(ex - COST)
        print(f"{tk:5} {np.mean(d1)*1e4:9.1f} {np.mean(d5)*1e4:12.1f} {np.mean(st)*1e4:13.1f}")
    print("  → horizon flips positive; the tight %-stop stays negative (same entries)")


def cmd_portfolio(PX):
    print("F21 — diversified portfolio: naive vs 'smart' weighting vs vol-target")
    R = pd.DataFrame({s: sleeve(PX, s) for s in DIVERS}).fillna(0.0)
    ew = R.mean(axis=1)
    mu = R.rolling(252).mean().shift(1); sd = R.rolling(252).std().shift(1)
    shw = (mu / sd).clip(lower=0).fillna(0)
    w = shw.div(shw.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    swp = (R * w).sum(axis=1); swp_vt, lev = vol_target(swp, 0.10)
    for name, s in [("equal-weight", ew), ("trailing-Sharpe-wt", swp),
                    ("Sharpe-wt + 10% vol-target", swp_vt)]:
        p = perf(s)
        print(f"  {name:30} ann {p['ann']:5.1f}%  vol {p['vol']:4.1f}%  Sharpe {p['sharpe']:5.2f}  DD {p['maxdd']:6.1f}%")
    print(f"  avg pairwise corr {R.corr().values[np.triu_indices(len(DIVERS),1)].mean():.2f}  · vol-target lev {lev:.2f}x")


def cmd_xsect(PX):
    print("F20 — long-only cross-sectional sector rotation (vs buy&hold)")
    S = PX[SECTORS].dropna(); rets = np.log(S / S.shift(1))
    for K in (1, 2, 3):
        past = np.log(S / S.shift(5)); n = len(S); port = np.zeros(n); d = 6
        while d < n - 1:
            row = past.iloc[d].dropna().sort_values()
            if len(row) >= K:
                longs = row.index[:K]
                for k in range(d + 1, min(d + 6, n)):
                    port[k] = rets.iloc[k][longs].mean()
                port[d + 1] -= COST; d += 5
            else:
                d += 1
        p = perf(pd.Series(port, index=S.index))
        print(f"  long bottom-{K} oversold  Sharpe {p['sharpe']:5.2f}  ann {p['ann']:5.1f}%  DD {p['maxdd']:6.1f}%")
    bh = perf(rets.mean(axis=1)); print(f"  [bench] sectors B&H      Sharpe {bh['sharpe']:5.2f}  ann {bh['ann']:5.1f}%")


def cmd_conditional(PX):
    print("F20/F21 — QQQ building block: entry filter vs vol-targeted sizing")
    for name, kw in [("baseline dip+5d+gate", {}), ("+ low-vol entry filter", dict(vol_filter=True))]:
        p = perf(sleeve(PX, "QQQ", **kw))
        print(f"  {name:24} Sharpe {p['sharpe']:5.2f}  ann {p['ann']:5.1f}%  t {p['t']:4.2f}")
    qvt, _ = vol_target(sleeve(PX, "QQQ"), 0.12); p = perf(qvt)
    print(f"  {'+ 12% vol-target sizing':24} Sharpe {p['sharpe']:5.2f}  ann {p['ann']:5.1f}%  t {p['t']:4.2f}")


def cmd_bonds(PX):
    print("F20 — bonds: MR-dip vs momentum vs buy&hold")
    for sym in ("TLT", "IEF"):
        c = PX[sym].dropna(); ret = np.log(c / c.shift(1)); ma = c.rolling(200).mean()
        inv = (c > ma).shift(1).fillna(False).astype(float)
        mom = inv * ret - inv.diff().abs().fillna(0) * COST / 2
        mr = perf(sleeve(PX, sym)); mo = perf(mom); bh = perf(ret)
        print(f"  {sym}: MR {mr['sharpe']:5.2f} | momentum {mo['sharpe']:5.2f} | B&H {bh['sharpe']:5.2f}")


def cmd_kelly(PX):
    print("F20 — adaptive (variable) Kelly vs fixed fraction — QQQ dip+5d trades")
    c = PX["QQQ"].dropna().values; n = len(c); r = np.zeros(n); r[1:] = np.log(c[1:] / c[:-1])
    ma = pd.Series(c).rolling(200).mean().values; tr = []; d = 1
    while d < n - 1:
        if r[d] < 0 and c[d] > ma[d]:
            j = min(d + 5, n - 1); tr.append(c[j] / c[d] - 1 - COST); d = j + 1
        else:
            d += 1
    tr = np.array(tr); tpy = len(tr) / ((PX.index[-1] - PX.index[0]).days / 365.25)

    def series(W=30, frac=0.5, fixed=None):
        out = []
        for i, x in enumerate(tr):
            if fixed is not None:
                f = fixed
            else:
                hh = tr[max(0, i - W):i]; wins = hh[hh > 0]; loss = -hh[hh < 0]
                if len(wins) and len(loss):
                    p = len(wins) / len(hh); b = wins.mean() / loss.mean()
                    f = min(frac * max((p * b - (1 - p)) / b, 0), 1.0)
                else:
                    f = 0.5
            out.append(f * x)
        return np.array(out)

    for name, a in [("fixed f=0.5", series(fixed=0.5)), ("fixed f=0.2", series(fixed=0.2)),
                    ("variable half-Kelly W=30", series()), ("variable half-Kelly W=60", series(W=60))]:
        sh = a.mean() / a.std() * math.sqrt(tpy) if a.std() else 0
        eq = np.cumprod(1 + a); dd = (eq / np.maximum.accumulate(eq) - 1).min() * 100
        print(f"  {name:26} Sharpe {sh:5.2f}  totalReturn {(eq[-1]-1)*100:7.1f}%  maxDD {dd:6.1f}%")
    print("  (fixed-f scales return+vol equally → Sharpe-invariant; the variable-f drop is the finding)")


CMDS = {"acf": cmd_acf, "exit": cmd_exit, "portfolio": cmd_portfolio, "xsect": cmd_xsect,
        "conditional": cmd_conditional, "bonds": cmd_bonds, "kelly": cmd_kelly}


def main():
    ap = argparse.ArgumentParser(description="leverage-free daily mean-reversion research lab")
    ap.add_argument("cmd", nargs="?", default="all", choices=list(CMDS) + ["all"])
    a = ap.parse_args()
    PX = load()
    for name in (CMDS if a.cmd == "all" else {a.cmd: CMDS[a.cmd]}):
        print("=" * 64); CMDS[name](PX); print()


if __name__ == "__main__":
    main()
