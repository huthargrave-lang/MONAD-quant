#!/usr/bin/env python3
"""
MONAD Quant — the commodity-linkage discovery atlas (docs/research/COMMODITY_LINKAGE_DISCOVERY.md).

Descriptive statistics, on the DISCOVERY window only, of how commodity anchors (oil, gas,
gold, silver, copper, bitcoin) relate to the stocks and ETFs that produce or depend on
them: exposure, lead-lag, moving-average state, ratio reversion, and scheduled-news days.

Firewall: every fetch carries an ``end`` bound, and ``fetch`` refuses any row on or after
it. The output records the window, the bound and the number of statistics computed (the
confirmation protocol's declared prior search). No trial is recorded: nothing is
selected here.

    venv/bin/python tools/commodity_atlas.py --out docs/research/data/commodity_atlas_discovery.json
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import sys
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research.fomc_calendar import announcements  # noqa: E402

#: (start, exclusive end) per block. The confirmation window starts at each end.
WINDOWS = {"main": ("2006-01-01", "2016-01-01"), "crypto": ("2018-01-01", "2022-01-01")}
CONTROLS = ("SPY", "IEF", "UUP")
#: group -> (block, anchors, members); the first member that is an ETF is the group's
#: event proxy, otherwise an equal-weight basket of the members.
GROUPS = {
    "oil_producers": ("main", ("CL=F",), ("XLE", "XOP", "XOM", "CVX", "COP", "APA", "DVN", "OXY")),
    "oil_services": ("main", ("CL=F",), ("OIH", "SLB", "HAL")),
    "tankers": ("main", ("CL=F", "BZ=F"), ("FRO", "DHT", "TNK", "NAT", "TK", "STNG")),
    "refiners": ("main", ("CL=F",), ("VLO", "MPC")),
    "natural_gas": ("main", ("NG=F",), ("FCG", "EQT", "RRC")),
    "gold_miners": ("main", ("GC=F",), ("GDX", "GDXJ", "NEM", "GOLD", "AEM", "KGC", "AU", "GFI")),
    "royalty": ("main", ("GC=F",), ("FNV", "RGLD", "WPM")),
    "silver": ("main", ("SI=F",), ("SIL", "PAAS", "HL", "CDE")),
    "copper": ("main", ("HG=F",), ("COPX", "FCX", "SCCO", "TECK")),
    "crypto_equities": ("crypto", ("BTC-USD",), ("BLOK", "MSTR", "MARA", "RIOT")),
}
ETFS = {"XLE", "XOP", "OIH", "FCG", "GDX", "GDXJ", "SIL", "COPX", "BLOK"}
SMAS = (50, 100, 200)
FWD = 20                     # sessions: the forward horizon of the daily metrics
Z_WINDOW = 60
PLACEBO_SHIFTS = 500
MIN_SHIFT_WEEKS = 26
MIN_WEEKS = 104


# ── data ─────────────────────────────────────────────────────────────────────
def yahoo_closes(symbols, start: str, end: str) -> pd.DataFrame:
    import yfinance as yf
    raw = yf.download(list(symbols), start=start, end=end, auto_adjust=True, progress=False,
                      group_by="column", threads=True)
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    close.index = pd.DatetimeIndex(close.index.date)
    return close


def fetch(symbols, start: str, end: str, *, get: Callable = yahoo_closes) -> pd.DataFrame:
    """Closes on [start, end), refusing any row on or after ``end`` (the firewall)."""
    close = get(symbols, start, end)
    if len(close) and close.index.max() >= pd.Timestamp(end):
        raise RuntimeError(f"firewall: data on {close.index.max().date()} is at or after {end}")
    return close.dropna(how="all")


# ── statistics ───────────────────────────────────────────────────────────────
def weekly(close: pd.DataFrame) -> pd.DataFrame:
    return close.resample("W-FRI").last().pct_change(fill_method=None)


def ols(y: pd.Series, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Coefficients and plain t-stats of y on [1, X] over complete rows."""
    d = pd.concat([y, X], axis=1).dropna()
    if len(d) < MIN_WEEKS:
        return np.full(X.shape[1] + 1, np.nan), np.full(X.shape[1] + 1, np.nan)
    A = np.column_stack([np.ones(len(d)), d.iloc[:, 1:].to_numpy()])
    b, *_ = np.linalg.lstsq(A, d.iloc[:, 0].to_numpy(), rcond=None)
    resid = d.iloc[:, 0].to_numpy() - A @ b
    s2 = resid @ resid / (len(d) - A.shape[1])
    se = np.sqrt(np.diag(s2 * np.linalg.inv(A.T @ A)))
    return b, b / se


def newey_west_t(y: np.ndarray, x: np.ndarray, lag: int) -> tuple[float, float]:
    """Slope of y on [1, x] with a Newey-West (Bartlett, ``lag``) t-stat."""
    ok = np.isfinite(y) & np.isfinite(x)
    y, x = y[ok], x[ok]
    if len(y) < 3 * lag or x.std() == 0:
        return float("nan"), float("nan")
    A = np.column_stack([np.ones(len(y)), x])
    b, *_ = np.linalg.lstsq(A, y, rcond=None)
    u = (y - A @ b)[:, None] * A
    S = u.T @ u
    for k in range(1, lag + 1):
        w = 1 - k / (lag + 1)
        G = u[k:].T @ u[:-k]
        S += w * (G + G.T)
    inv = np.linalg.inv(A.T @ A)
    V = inv @ S @ inv
    return float(b[1]), float(b[1] / math.sqrt(V[1, 1]))


def placebo_p(x: pd.Series, y: pd.Series, observed: float, rng: np.random.Generator) -> float:
    """Share of circular shifts of ``x`` (at least MIN_SHIFT_WEEKS) whose |corr| with y
    reaches |observed|."""
    d = pd.concat([x, y], axis=1).dropna()
    n = len(d)
    if n < 2 * MIN_SHIFT_WEEKS + 1 or not np.isfinite(observed):
        return float("nan")
    a, b = d.iloc[:, 0].to_numpy(), d.iloc[:, 1].to_numpy()
    shifts = rng.integers(MIN_SHIFT_WEEKS, n - MIN_SHIFT_WEEKS, PLACEBO_SHIFTS)
    hits = sum(abs(np.corrcoef(np.roll(a, s), b)[0, 1]) >= abs(observed) for s in shifts)
    return (hits + 1) / (PLACEBO_SHIFTS + 1)


def exposure(wk: pd.DataFrame, member: str, anchor: str) -> dict:
    d = wk[[member, anchor]].dropna()
    corr = float(d.corr().iloc[0, 1]) if len(d) >= MIN_WEEKS else float("nan")
    beta = float(d[member].cov(d[anchor]) / d[anchor].var()) if len(d) >= MIN_WEEKS else float("nan")
    controls = [c for c in CONTROLS if c in wk]
    b, t = ols(wk[member], wk[[anchor, *controls]])
    return {"weeks": int(len(d)), "corr": corr, "beta": beta,
            "partial_beta": float(b[1]), "partial_t": float(t[1])}


def lead_lag(wk: pd.DataFrame, member: str, anchor: str, rng: np.random.Generator) -> dict:
    a, m = wk[anchor], wk[member]
    spy_beta = m.cov(wk["SPY"]) / wk["SPY"].var()
    resid = m - spy_beta * wk["SPY"]
    fwd = lambda s, h: s[::-1].rolling(h).sum()[::-1].shift(-1)       # noqa: E731  sum of t+1..t+h
    trail = lambda s, h: s.rolling(h).sum()                            # noqa: E731
    out = {}
    for name, x, ys in (("a1_m1", a, (m.shift(-1), resid.shift(-1))),
                        ("a1_m4", a, (fwd(m, 4), fwd(resid, 4))),
                        ("a4_m4", trail(a, 4), (fwd(m, 4), fwd(resid, 4))),
                        ("a12_m4", trail(a, 12), (fwd(m, 4), fwd(resid, 4)))):
        for kind, y in zip(("raw", "spy_resid"), ys):
            d = pd.concat([x, y], axis=1).dropna()
            c = float(d.corr().iloc[0, 1]) if len(d) >= MIN_WEEKS else float("nan")
            out[f"{name}_{kind}"] = {"corr": c, "placebo_p": placebo_p(x, y, c, rng)}
    return out


def fwd_return(close: pd.Series, h: int = FWD) -> pd.Series:
    """log return from t's close to t+h's close (the decision is taken at t's close)."""
    lc = np.log(close)
    return lc.shift(-h) - lc


def ma_state(close: pd.DataFrame, member: str, anchor: str) -> dict:
    out = {}
    f = fwd_return(close[member])
    fx = f - fwd_return(close["SPY"])
    for who in (anchor, member):
        px = close[who]
        for n in SMAS:
            state = (px > px.rolling(n).mean()).astype(float).where(px.rolling(n).mean().notna())
            for kind, y in (("raw", f), ("spy_excess", fx)):
                d = pd.concat([state, y], axis=1).dropna()
                if len(d) < 252:
                    continue
                slope, t = newey_west_t(d.iloc[:, 1].to_numpy(), d.iloc[:, 0].to_numpy(), FWD)
                above = d.iloc[:, 1][d.iloc[:, 0] == 1].mean() * 252 / FWD
                below = d.iloc[:, 1][d.iloc[:, 0] == 0].mean() * 252 / FWD
                out[f"{'anchor' if who == anchor else 'own'}_sma{n}_{kind}"] = {
                    "above_ann": float(above), "below_ann": float(below),
                    "spread_ann": float(slope * 252 / FWD), "nw_t": t,
                    "share_above": float(d.iloc[:, 0].mean())}
    return out


def ratio_reversion(close: pd.DataFrame, member: str, anchor: str) -> dict:
    d = close[[member, anchor]].dropna()
    if len(d) < 2 * 252:
        return {}
    lr = np.log(d[member]) - np.log(d[anchor])
    z = (lr - lr.rolling(Z_WINDOW).mean()) / lr.rolling(Z_WINDOW).std()
    rel = fwd_return(d[member]) - fwd_return(d[anchor])
    q = pd.qcut(z, 5, labels=False, duplicates="drop")
    by_q = rel.groupby(q).mean() * 252 / FWD
    slope, t = newey_west_t(rel.to_numpy(), z.to_numpy(), FWD)
    dlr = lr.diff()
    b, _ = ols(dlr, lr.shift(1).to_frame()) if len(lr) > 300 else (np.array([np.nan, np.nan]), None)
    hl = float(-math.log(2) / math.log(1 + b[1])) if np.isfinite(b[1]) and -1 < b[1] < 0 else float("inf")
    return {"rel_ann_by_z_quintile": [float(v) for v in by_q.values],
            "q1_minus_q5_ann": float(by_q.iloc[0] - by_q.iloc[-1]) if len(by_q) >= 2 else float("nan"),
            "slope_per_z_ann": float(slope * 252 / FWD), "nw_t": t, "half_life_sessions": hl}


def eia_days(sessions: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Wednesday sessions, or Thursday in a week whose Monday is not a session."""
    s = pd.Series(sessions, index=sessions)
    out = []
    for _, wk in s.groupby(sessions.to_period("W-SUN")):
        days = wk.index
        has_monday = any(d.weekday() == 0 for d in days)
        target = 2 if has_monday else 3
        hit = [d for d in days if d.weekday() == target]
        if hit:
            out.append(hit[0])
    return pd.DatetimeIndex(out)


def event_stats(ret: pd.Series, days: pd.DatetimeIndex) -> dict:
    r = ret.dropna()
    on = r.index.isin(days)
    a, b = r[on], r[~on]
    if len(a) < 10:
        return {}
    se = math.sqrt(a.var() / len(a) + b.var() / len(b))
    se_abs = math.sqrt(a.abs().var() / len(a) + b.abs().var() / len(b))
    return {"n": int(len(a)), "mean_bp": float(a.mean() * 1e4), "other_mean_bp": float(b.mean() * 1e4),
            "mean_t": float((a.mean() - b.mean()) / se),
            "abs_bp": float(a.abs().mean() * 1e4), "other_abs_bp": float(b.abs().mean() * 1e4),
            "abs_t": float((a.abs().mean() - b.abs().mean()) / se_abs)}


def group_proxy(close: pd.DataFrame, members) -> pd.Series:
    etf = next((m for m in members if m in ETFS and m in close), None)
    if etf is not None:
        return close[etf].pct_change(fill_method=None).rename(etf)
    rets = close[[m for m in members if m in close]].pct_change(fill_method=None)
    return rets.mean(axis=1, skipna=True).rename("basket")


# ── the atlas ────────────────────────────────────────────────────────────────
def build(get: Callable = yahoo_closes, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    fomc = pd.DatetimeIndex(announcements())
    out = {"schema_version": 1, "vintage": _dt.date.today().isoformat(),
           "protocol": "docs/research/COMMODITY_LINKAGE_DISCOVERY.md", "windows": WINDOWS,
           "built": _dt.date.today().isoformat(), "groups": {}, "missing": {}, "cells": 0}
    data = {}
    for block, (start, end) in WINDOWS.items():
        syms = sorted({s for g in GROUPS.values() if g[0] == block for s in (*g[1], *g[2])} | set(CONTROLS))
        data[block] = fetch(syms, start, end, get=get)
        out.setdefault("last_row", {})[block] = data[block].index.max().date().isoformat()
    cells = 0
    for gname, (block, anchors, members) in GROUPS.items():
        close = data[block]
        present = [m for m in members if m in close and close[m].notna().sum() >= 252]
        out["missing"][gname] = [m for m in members if m not in present]
        wk = weekly(close)
        g = {"block": block, "anchors": list(anchors), "members": {}}
        for m in present:
            row = {}
            for a in anchors:
                if a not in close or close[a].notna().sum() < 252:
                    continue
                cell = {"exposure": exposure(wk, m, a), "lead_lag": lead_lag(wk, m, a, rng),
                        "ma_state": ma_state(close, m, a), "ratio": ratio_reversion(close, m, a)}
                cells += 4 + len(cell["lead_lag"]) + len(cell["ma_state"]) + 3
                row[a] = cell
            g["members"][m] = row
        proxy = group_proxy(close, present)
        sessions = close["SPY"].dropna().index
        f_days = fomc[(fomc >= sessions[0]) & (fomc <= sessions[-1])]
        f_before = pd.DatetimeIndex([sessions[sessions.get_loc(d) - 1] for d in f_days
                                     if d in sessions and sessions.get_loc(d) > 0])
        ev = {"proxy": proxy.name, "fomc_day": event_stats(proxy, f_days),
              "fomc_day_before": event_stats(proxy, f_before)}
        if anchors[0] in ("CL=F", "BZ=F", "NG=F"):
            ev["eia_day"] = event_stats(proxy, eia_days(sessions))
        cells += 2 * (len(ev) - 1)
        g["events"] = ev
        out["groups"][gname] = g
    out["cells"] = cells
    return out


def _fmt(x, spec="+.2f"):
    return "  n/a" if x is None or not np.isfinite(x) else format(x, spec)


def summary(atlas: dict, top: int = 15) -> list[str]:
    lines = [f"atlas cells: {atlas['cells']}  last rows: {atlas['last_row']}"]
    ll, ma, rr, ev = [], [], [], []
    for gname, g in atlas["groups"].items():
        for m, row in g["members"].items():
            for a, c in row.items():
                for k, v in c["lead_lag"].items():
                    ll.append((v["placebo_p"], gname, m, a, k, v["corr"]))
                for k, v in c["ma_state"].items():
                    ma.append((abs(v["nw_t"]) if np.isfinite(v["nw_t"]) else 0, gname, m, a, k, v))
                if c["ratio"]:
                    rr.append((abs(c["ratio"]["nw_t"]) if np.isfinite(c["ratio"]["nw_t"]) else 0, gname, m, a, c["ratio"]))
        for k, v in g["events"].items():
            if isinstance(v, dict) and v:
                ev.append((max(abs(v["mean_t"]), abs(v["abs_t"])), gname, g["events"]["proxy"], k, v))
    lines.append("\nEXPOSURE (weekly corr / beta / partial beta t vs controls)")
    for gname, g in atlas["groups"].items():
        for m, row in g["members"].items():
            for a, c in row.items():
                e = c["exposure"]
                lines.append(f"  {gname:16} {m:6} ~ {a:7} corr {_fmt(e['corr'])} beta {_fmt(e['beta'])} "
                             f"partial {_fmt(e['partial_beta'])} (t {_fmt(e['partial_t'], '+.1f')})")
    lines.append(f"\nLEAD-LAG, lowest placebo p (of {len(ll)})")
    for p, gname, m, a, k, c in sorted(ll, key=lambda x: (x[0] if np.isfinite(x[0]) else 9))[:top]:
        lines.append(f"  p {p:.3f}  {gname:16} {a:7} -> {m:6} {k:16} corr {_fmt(c)}")
    lines.append(f"\nMA STATE, largest |NW t| (of {len(ma)})")
    for t, gname, m, a, k, v in sorted(ma, key=lambda x: -x[0])[:top]:
        lines.append(f"  t {v['nw_t']:+.2f}  {gname:16} {m:6} {k:24} above {v['above_ann']:+.1%} "
                     f"below {v['below_ann']:+.1%} (share above {v['share_above']:.0%})")
    lines.append(f"\nRATIO REVERSION, largest |NW t| (of {len(rr)})")
    for t, gname, m, a, r in sorted(rr, key=lambda x: -x[0])[:top]:
        lines.append(f"  t {r['nw_t']:+.2f}  {gname:16} {m:6}/{a:7} Q1-Q5 {r['q1_minus_q5_ann']:+.1%}/yr  "
                     f"half-life {r['half_life_sessions']:.0f}")
    lines.append("\nSCHEDULED NEWS (event day vs others: mean bp (t), |ret| bp (t))")
    for t, gname, proxy, k, v in sorted(ev, key=lambda x: -x[0]):
        lines.append(f"  {gname:16} {proxy:6} {k:16} n {v['n']:4} mean {v['mean_bp']:+6.1f} vs {v['other_mean_bp']:+5.1f} "
                     f"(t {v['mean_t']:+.2f})  abs {v['abs_bp']:5.1f} vs {v['other_abs_bp']:5.1f} (t {v['abs_t']:+.2f})")
    return lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args(argv)
    atlas = build()
    Path(args.out).write_text(json.dumps(atlas, indent=1, default=float), encoding="utf-8")
    print("\n".join(summary(atlas, args.top)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
