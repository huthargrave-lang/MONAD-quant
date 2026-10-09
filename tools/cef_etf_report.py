#!/usr/bin/env python3
"""
cef_etf_report — build the frozen inputs of the CEF vs matched-ETF discount tilt, and
compute its pre-stated verdict and diagnostics (docs/research/CEF_ETF_TILT_PROTOCOL.md).

  # 1. the private price snapshot, the SEC calendar, the matching, screens and tiers
  SEC_USER_AGENT='name contact' venv/bin/python tools/cef_etf_report.py build
  # 2. the counted searches
  venv/bin/python tools/domain_search.py cef_etf_tilt --snapshot <DS> --panel <CEFETF> --cost-stress 2
  venv/bin/python tools/domain_search.py cef_etf_tilt_lag --snapshot <DS> --panel <CEFETF>
  venv/bin/python tools/domain_search.py cef_etf_tilt_staged --snapshot <DS> --panel <CEFETF>
  # 3. the verdict (records counted diagnostic runs for weights and leave-one-family-out)
  venv/bin/python tools/cef_etf_report.py report --snapshot <DS> --panel <CEFETF> --json out.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from src.research import allocation_stats as stats  # noqa: E402
from src.research import cef_data, cef_etf_tilt as ce, daily_data, trials  # noqa: E402
from src.research.daily_classes import total_return_index  # noqa: E402
from src.research.daily_domains import DOMAINS, Context  # noqa: E402
from src.research.daily_strategy import evaluate_daily  # noqa: E402
from src.research.daily_trials import daily_spec, family_name, record_daily, stored_returns  # noqa: E402

PRODUCER = "tools/cef_etf_report.py"
PANEL = "fd7099e252ccd34aec6829b5617dface66318c8a3756808d95c4a21d6b19b35f"


def yahoo_volume(symbols, start, end) -> pd.DataFrame:
    import yfinance as yf
    cols = {}
    for s in symbols:
        try:
            h = yf.Ticker(s).history(start=start, end=end, auto_adjust=False)
        except Exception:  # noqa: BLE001 — a missing volume makes the fund thin (conservative)
            continue
        if h is not None and len(h):
            idx = pd.DatetimeIndex(h.index)
            if idx.tz is not None:
                idx = idx.tz_convert("America/New_York").tz_localize(None)
            cols[s] = pd.Series(h["Volume"].to_numpy(dtype=float), index=idx.normalize())
    return pd.DataFrame(cols)


def cmd_build(args) -> int:
    from src.research.bdc_text_nav import _get
    panel = cef_data.load_panel(args.panel_source)
    fams = ce.universe(panel)
    funds = sorted(f for f in fams if f not in ce.EXCLUDED)
    universe = ["SPY"] + [e for e in ce.candidates() if e != "SPY"] + funds
    sha = daily_data.build_snapshot(universe, ce.SNAPSHOT_START, ce.END, optional=universe[1:],
                                    independent_closes={f: panel.price[f] for f in funds if f in panel.price},
                                    independent_source="CEFConnect weekly price (NAV panel)", private=True)
    snap = daily_data.load_snapshot(sha)
    volume = yahoo_volume([f for f in funds if f in snap.assets], ce.SNAPSHOT_START, ce.END)
    inputs_sha, payload = ce.build_inputs(panel, snap, sec_get=_get, volume=volume)
    print(json.dumps({"snapshot": sha, "inputs": inputs_sha, "window_start": payload["window_start"],
                      "matched": len(payload["mapping"]), "unmatched": len(payload["unmatched"]),
                      "excluded": len(payload["excluded"]),
                      "by_family": pd.Series(payload["families"]).value_counts().to_dict(),
                      "screens_failed_share": payload["screens"]["share_failed"],
                      "not_run": payload["not_run"],
                      "dropped_from_snapshot": snap.manifest.get("validation", {}).get("dropped", {})},
                     indent=1, default=str))
    return 0


# ── diagnostics ──────────────────────────────────────────────────────────────
def counted_eval(domain, ctx, point, *, role: str, start, end):
    data = ctx.data_spec(start, end)
    with trials.open_run(producer=PRODUCER, family=family_name(domain.name, reference=point["class"] == "cef_etf_bench"),
                         context={**data, "role": role}) as run:
        t = run.begin(params=daily_spec(point, domain=domain.name), data=data)
        res = evaluate_daily(domain.decide(ctx, point), ctx.snap, start=start, end=end, tiers=domain.tiers(ctx))
        record_daily(t, res)
    return res


def nw_t(x: np.ndarray, lag: int) -> float:
    u = x - x.mean()
    lrv = u @ u / len(u)
    for k in range(1, lag + 1):
        lrv += 2 * (1 - k / (lag + 1)) * (u[k:] @ u[:-k]) / len(u)
    return float(x.mean() / math.sqrt(lrv / len(u))) if lrv > 0 else float("nan")


def nw_ols(y: np.ndarray, X: np.ndarray, lag: int) -> tuple[np.ndarray, np.ndarray]:
    A = np.column_stack([np.ones(len(y)), X])
    b, *_ = np.linalg.lstsq(A, y, rcond=None)
    u = (y - A @ b)[:, None] * A
    S = u.T @ u
    for k in range(1, lag + 1):
        w = 1 - k / (lag + 1)
        G = u[k:].T @ u[:-k]
        S += w * (G + G.T)
    inv = np.linalg.pinv(A.T @ A)
    V = inv @ S @ inv
    return b, b / np.sqrt(np.maximum(np.diag(V), 1e-300))


def decompose(inputs, snap, tilt_res, bench_res) -> dict:
    """Exact split of sum_i Delta_i x_i (x_i = fund total return minus its ETF's) into
    within-family and category parts, from the realised weights (previous close)."""
    rets = snap.returns()
    tot = (1 + rets.night) * (1 + rets.day) - 1
    funds = [f for f in inputs.matched if f in tilt_res.weights.columns]
    dw = (tilt_res.weights[funds] - bench_res.weights[funds]).shift(1).dropna(how="all").fillna(0.0)
    x = pd.DataFrame({f: tot[f] - tot[inputs.matched[f]["etf"]] for f in funds}).reindex(dw.index).fillna(0.0)
    fams = inputs.data["families"]
    within = pd.Series(0.0, index=dw.index)
    cat = pd.Series(0.0, index=dw.index)
    for fam in sorted(set(fams[f] for f in funds)):
        fs = [f for f in funds if fams[f] == fam]
        d, xx = dw[fs], x[fs]
        live = (d != 0) | (xx != 0)
        n = live.sum(axis=1).replace(0, np.nan)
        dbar = d.where(live).mean(axis=1)
        xbar = xx.where(live).mean(axis=1)
        within += ((d.sub(dbar, axis=0)) * (xx.sub(xbar, axis=0))).where(live).sum(axis=1).fillna(0.0)
        cat += (n * dbar * xbar).fillna(0.0)
    return {"within": within, "cat": cat, "dw": dw, "x": x}


def beta_control(inputs, snap, active: pd.Series, dw: pd.DataFrame, lag: int = 4) -> dict:
    """a_w = alpha + sum_family (g X_f,w + g' X_f,w-1) on non-overlapping 5-session sums;
    X_f = sum_{i in f} Delta_i (beta_i - 1) r_ETF,i (Delta already carries the share)."""
    rets = snap.returns()
    tot = (1 + rets.night) * (1 + rets.day) - 1
    fams = inputs.data["families"]
    cols = {}
    for fam in sorted(set(fams[f] for f in dw.columns)):
        fs = [f for f in dw.columns if fams[f] == fam]
        cols[fam] = sum(dw[f] * (inputs.matched[f]["beta"] - 1.0) * tot[inputs.matched[f]["etf"]].reindex(dw.index)
                        for f in fs).fillna(0.0)
    X = pd.DataFrame(cols).reindex(active.index).fillna(0.0)
    block = np.arange(len(active)) // 5
    a_w = active.groupby(block).sum()
    X_w = X.groupby(block).sum()
    regs = np.column_stack([X_w.to_numpy(), X_w.shift(1).fillna(0.0).to_numpy()])
    b, t = nw_ols(a_w.to_numpy(), regs, lag)
    return {"alpha_weekly": float(b[0]), "alpha_ann": float(b[0] * 52), "alpha_t": float(t[0]),
            "weeks": int(len(a_w))}


def price_nav_component(inputs, snap, dw: pd.DataFrame) -> pd.Series:
    """D: weekly sum_i Delta_i (r_price,i - r_NAV,i), Friday to Friday, same distributions."""
    out = {}
    panel = inputs.panel
    for f in dw.columns:
        nav = panel.nav[f].dropna()
        px = snap.close[f]
        dist = snap.dist[f].fillna(0.0).cumsum()
        at = lambda s, d: s.reindex(s.index.union(d)).ffill().reindex(d)   # noqa: E731
        paid = at(dist, nav.index).diff()
        r_nav = (nav + paid) / nav.shift(1) - 1
        p = at(px, nav.index)
        r_px = (p + paid) / p.shift(1) - 1
        delta = at(dw[f], nav.index).shift(1)
        out[f] = (delta * (r_px - r_nav))
    return pd.DataFrame(out).sum(axis=1, min_count=1).dropna()


def cmd_report(args) -> int:
    dom = DOMAINS["cef_etf_tilt"]
    ctx = dom.load({"snapshot": args.snapshot, "nav_panel": args.panel})
    inputs, snap = ctx.panel, ctx.snap
    start, end = dom.window(ctx)
    out = {"schema_version": 1, "vintage": pd.Timestamp.today().date().isoformat(),
           "protocol": "docs/research/CEF_ETF_TILT_PROTOCOL.md", "window": [str(start.date()), str(end.date())]}
    if inputs.data.get("not_run"):
        out["verdict"] = {"verdict": "NOT RUN", "reason": "data screens failed > 10% of fund-years"}
        Path(args.json).write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
        print(json.dumps(out["verdict"]))
        return 0
    (point,) = dom.grid()
    tilt = counted_eval(dom, ctx, point, role="diagnostic: weights", start=start, end=end)
    bench = counted_eval(dom, ctx, dom.reference, role="diagnostic: weights", start=start, end=end)
    active = stats.active_series(tilt.returns, bench.returns)
    sh = stats.annualized_sharpe(active)
    dec = decompose(inputs, snap, tilt, bench)
    bc_total = beta_control(inputs, snap, active, dec["dw"])
    bc_cat = beta_control(inputs, snap, dec["cat"].reindex(active.index).fillna(0.0), dec["dw"])
    D = price_nav_component(inputs, snap, dec["dw"])
    weekly_active = active.resample("W-FRI").sum()
    recon = float(pd.concat([D, weekly_active], axis=1).dropna().corr().iloc[0, 1])
    # long leg: days with any fund overweight
    long_days = (dec["dw"] > 0).any(axis=1).reindex(active.index).fillna(False)
    long_leg = float(active[long_days].sum() / (len(active) / 252))
    # leave-one-family-out (counted runs of tilt and benchmark on the subset)
    fams = sorted(set(inputs.data["families"].values()))
    lofo = {}
    for fam in fams:
        keep = [f for f in fams if f != fam]
        p_t = {"class": "cef_etf_tilt", "params": {"lag": 1, "families": keep}}
        p_b = {"class": "cef_etf_bench", "params": {"families": keep}}
        rt = counted_eval(dom, ctx, p_t, role=f"diagnostic: leave out {fam}", start=start, end=end)
        rb = counted_eval(dom, ctx, p_b, role=f"diagnostic: leave out {fam}", start=start, end=end)
        a = stats.active_series(rt.returns, rb.returns)
        dsub = decompose(inputs, snap, rt, rb)
        lofo[fam] = {"sharpe": stats.annualized_sharpe(a), "alpha": beta_control(inputs, snap, a, dsub["dw"])}
    # episodes per family
    episodes = {}
    for f in inputs.matched:
        st = ce.fund_states(inputs, snap, f).loc[start:end]
        fam = inputs.data["families"][f]
        from src.research.metal_trust_classes import episodes as count
        episodes[fam] = episodes.get(fam, 0) + count(st)
    out["verdict_inputs"] = {
        "sharpe": sh, "t": sh * math.sqrt(len(active) / 252),
        "sharpe_2017_on": stats.annualized_sharpe(active.loc["2017-01-01":]),
        "beta_control_total": bc_total, "beta_control_cat": bc_cat,
        "within_ann": float(dec["within"].mean() * 252), "cat_ann": float(dec["cat"].mean() * 252),
        "D_mean_weekly": float(D.mean()), "D_t": nw_t(D.to_numpy(), 4), "D_reconciliation_corr": recon,
        "long_leg_ann": long_leg, "leave_one_family_out": lofo, "episodes_by_family": episodes,
        "eras": [e["active_sharpe"] for e in stats.era_sharpes(active, dom.eras)]}
    Path(args.json).write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(json.dumps(out, indent=1, default=float))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build")
    p.add_argument("--panel-source", default=PANEL)
    p.set_defaults(fn=cmd_build)
    p = sub.add_parser("report")
    p.add_argument("--snapshot", required=True)
    p.add_argument("--panel", required=True, help="the CEFETF inputs sha")
    p.add_argument("--json", required=True)
    p.set_defaults(fn=cmd_report)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
