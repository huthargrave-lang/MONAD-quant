"""
sleeve_break_even — how large would a CEF sleeve's alpha over its own benchmark have to be
before carving it out of the static 60/40 raised the product's excess Sharpe, or stopped
deepening its drawdown? (docs/research/SLEEVE_BREAK_EVEN_PROTOCOL.md, frozen first.)

  venv/bin/python tools/sleeve_break_even.py [--json docs/research/data/sleeve_break_even.json]

Descriptive: recorded series only (the 60/40, the equal-weight CEF reference, PCEF), no
evaluation, no trial, no fitted weight.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import daily_data, trials  # noqa: E402
from src.research.daily_trials import stored_returns  # noqa: E402

PROTOCOL = "docs/research/SLEEVE_BREAK_EVEN_PROTOCOL.md"
OUT = REPO / "docs/research/data/sleeve_break_even.json"
PRODUCT = "TR-20261006T005053Z-9336581d#0"
PRODUCT_SNAPSHOT = "32c992fb5395668529a6bfca3214bf59a1242fbc1c6efb52ab97664154c3aaaf"
SLEEVES = {"ew_cef (H404702's benchmark)": {"trial": "TR-20261006T012341Z-86834435#0", "alpha": 0.0226},
           "pcef (CEFS's benchmark)": {"trial": "TR-20261007T051659Z-dfb4dff7#0", "alpha": 0.0440}}
CARVE_OUTS = (0.05, 0.10, 0.20)
REGIME_CUT = pd.Timestamp("2022-08-01")
LO, HI = -0.20, 0.40


def sharpe(r: pd.Series, cash: pd.Series) -> float:
    x = r - cash.reindex(r.index).fillna(0.0)
    sd = float(x.std(ddof=1))
    return float(x.mean() / sd * math.sqrt(252)) if sd > 0 else float("nan")


def max_drawdown(r: pd.Series) -> float:
    eq = (1.0 + r).cumprod()
    return float((eq / eq.cummax() - 1.0).min())


def mix(p: pd.Series, b: pd.Series, x: float, alpha: float) -> pd.Series:
    return (1.0 - x) * p + x * (b + alpha / 252.0)


def no_crossing(metric, target: float, p, b, x) -> str | None:
    """Why ``break_even`` found none: the mix already beats the product at the lowest alpha,
    or still falls short at the highest."""
    if metric(mix(p, b, x, LO)) > target:
        return f"none: better even at {LO:+.0%}/yr"
    if metric(mix(p, b, x, HI)) < target:
        return f"none: worse even at {HI:+.0%}/yr"
    return None


def break_even(metric, target: float, p, b, x) -> float | None:
    """The alpha in [LO, HI] at which ``metric(mix)`` equals ``target`` (it rises with
    alpha), or None when there is no crossing (``no_crossing`` says which side)."""
    f = lambda a: metric(mix(p, b, x, a)) - target          # noqa: E731
    lo, hi = LO, HI
    if f(lo) > 0 or f(hi) < 0:
        return None
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
    return 0.5 * (lo + hi)


def windows(index: pd.DatetimeIndex) -> dict:
    return {"full": (index[0], index[-1]),
            "negative stock-bond correlation (to 2022-07)": (index[0], REGIME_CUT - pd.Timedelta(days=1)),
            "positive correlation (2022-08 on)": (REGIME_CUT, index[-1])}


def study() -> dict:
    keys = [PRODUCT] + [s["trial"] for s in SLEEVES.values()]
    recs = {r.key: r for r in trials.iter_trials() if r.key in keys}
    series = {k: stored_returns(v) for k, v in trials.load_returns([recs[k] for k in keys]).items()}
    cash = daily_data.load_snapshot(PRODUCT_SNAPSHOT).returns().cash
    out = {}
    for name, cfg in SLEEVES.items():
        p_all, b_all = series[PRODUCT], series[cfg["trial"]]
        common = p_all.index.intersection(b_all.index)
        rows = {}
        for wname, (a, z) in windows(common).items():
            idx = common[(common >= a) & (common <= z)]
            p, b = p_all.reindex(idx), b_all.reindex(idx)
            sh_p = sharpe(p, cash)
            dd_p = max_drawdown(p)
            per = {}
            for x in CARVE_OUTS:
                a_s = break_even(lambda r: sharpe(r, cash), sh_p, p, b, x)
                a_d = break_even(max_drawdown, dd_p, p, b, x)
                per[f"{x:.0%}"] = {"alpha_sharpe_break_even": a_s, "alpha_drawdown_break_even": a_d,
                                   "sharpe_no_crossing": no_crossing(lambda r: sharpe(r, cash), sh_p, p, b, x),
                                   "drawdown_no_crossing": no_crossing(max_drawdown, dd_p, p, b, x),
                                   "corroborated_alpha_clears_sharpe": None if a_s is None else cfg["alpha"] > a_s,
                                   "corroborated_alpha_clears_drawdown": None if a_d is None else cfg["alpha"] > a_d}
            rows[wname] = {"first": str(idx[0].date()), "last": str(idx[-1].date()), "sessions": int(len(idx)),
                           "product_sharpe": sh_p, "product_max_drawdown": dd_p,
                           "benchmark_sharpe": sharpe(b, cash), "benchmark_max_drawdown": max_drawdown(b),
                           "correlation": float(p.corr(b)), "carve_outs": per}
        out[name] = {"corroborated_alpha": cfg["alpha"], "windows": rows}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", default=str(OUT))
    args = ap.parse_args(argv)
    out = {"schema_version": 1, "vintage": pd.Timestamp.today().date().isoformat(), "protocol": PROTOCOL,
           "product": PRODUCT, "results": study()}
    text = json.dumps(out, indent=1, sort_keys=True, default=float) + "\n"
    Path(args.json).write_text(text, encoding="utf-8")
    print(f"wrote {args.json} (sha256 {hashlib.sha256(text.encode()).hexdigest()})")
    for name, res in out["results"].items():
        print(f"\n{name}: corroborated alpha {res['corroborated_alpha']:+.2%}/yr")
        for w, r in res["windows"].items():
            print(f"  {w:46} {r['first']}..{r['last']}  60/40 Sh {r['product_sharpe']:.2f} DD {r['product_max_drawdown']:.1%}"
                  f" | bench Sh {r['benchmark_sharpe']:.2f} DD {r['benchmark_max_drawdown']:.1%} corr {r['correlation']:.2f}")
            for x, c in r["carve_outs"].items():
                print(f"      carve {x:>3}: alpha for Sharpe "
                      f"{c['sharpe_no_crossing'] or format(c['alpha_sharpe_break_even'], '+.2%')}, for drawdown "
                      f"{c['drawdown_no_crossing'] or format(c['alpha_drawdown_break_even'], '+.2%')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
