"""
credit_sleeve_mix — would carving part of the static 60/40 into a fallen-angel (ANGL) sleeve
measurably raise its excess Sharpe in both stock-bond correlation regimes without deepening its
drawdown, beyond the same carve in HYG and beyond a sleeve that only reproduces ANGL's lagged
stock and bond exposure? (docs/research/CREDIT_SLEEVE_MIX_PROTOCOL.md, frozen first.)

  venv/bin/python tools/credit_sleeve_mix.py [--json docs/research/data/credit_sleeve_mix.json]

Descriptive, like tools/sleeve_break_even.py (whose statistics it reuses): recorded series and
frozen snapshots only, no evaluation, no trial, no fitted portfolio weight, no recommended size.
The crisis proxy reads a private snapshot (option A); only aggregates are written, and the tool
refuses to write if the trial ledger or H366200's evaluator changed while it ran.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from src.research import beta_control, daily_data, trials  # noqa: E402
from src.research.daily_trials import stored_returns  # noqa: E402
from sleeve_break_even import max_drawdown, sharpe  # noqa: E402

PROTOCOL = "docs/research/CREDIT_SLEEVE_MIX_PROTOCOL.md"
OUT = REPO / "docs/research/data/credit_sleeve_mix.json"
PRODUCT = "TR-20261006T005053Z-9336581d#0"
PRODUCT_SNAPSHOT = "32c992fb5395668529a6bfca3214bf59a1242fbc1c6efb52ab97664154c3aaaf"
ANGL = "TR-20261007T041713Z-2cbc8fe5#0"
HYG = "TR-20261007T041712Z-eb23cf97#0"
ROBUSTNESS = {"FALN": "TR-20261007T043055Z-b289eaaa#0", "ANGL": "TR-20261007T043113Z-f6ceb5cb#0",
              "HYG": "TR-20261007T043054Z-91da6309#0"}
PROXY_SNAPSHOT = "c6ac870a"            # prefix; resolved to the one committed manifest
WATCH = "H366200"                      # the forward watch whose evaluator this branch carries
CARVE_OUTS = (0.05, 0.10, 0.20)
SECONDARY_CARVE = 0.025                # statistics only, no verdict
REGIME_CUT = pd.Timestamp("2022-08-01")
STRESS = (pd.Timestamp("2007-06-11"), pd.Timestamp("2012-05-09"))
BLOCK = beta_control.BLOCK
BETA_WINDOW, BETA_MIN = 104, 52        # F366205's product settings, in 5-session blocks
SCREEN_CORRELATION, SCREEN_MEAN_GAP = 0.995, 0.0025
BAND_PER_CARVE = 0.25                  # delta(x) = 0.25 x, F38's half-width at a 10% carve
MAX_LIST = 10                          # option A: no daily series in the output

NEGATIVE = "negative correlation (to 2022-07)"
POSITIVE = "positive correlation (2022-08 on)"
PASS, FAIL, UNRESOLVED = "pass", "fail", "unresolved"
ADD, SHARPE_ONLY, NO_EFFECT, NO_CREDIT = "ADD", "SHARPE ONLY", "NO MEASURABLE EFFECT", "NO CREDIT"
UNTESTED = f"{ADD} (untested in a credit crisis)"
RANK = {ADD: 3, UNTESTED: 3, SHARPE_ONLY: 2, NO_EFFECT: 1, NO_CREDIT: 0}


# ── series ───────────────────────────────────────────────────────────────────
def session_total(returns: daily_data.SessionReturns, asset: str) -> pd.Series:
    """Session return, distributions reinvested at the open (the engine's convention):
    (1 + night)(1 + day) - 1. The snapshot's first session has none."""
    return ((1.0 + returns.night[asset]) * (1.0 + returns.day[asset]) - 1.0).dropna()


def holding(recorded: pd.Series) -> pd.Series:
    """A recorded series without its build session (the first: the book is built at that
    session's open, so it is not a holding return; F366205's rule)."""
    return recorded.iloc[1:]


def mix(p: pd.Series, s: pd.Series, x: float) -> pd.Series:
    """The 60/40 with ``x`` carved out pro rata into the sleeve, rebalanced each session."""
    idx = p.index.intersection(s.index)
    return (1.0 - x) * p.reindex(idx) + x * s.reindex(idx)


def regimes(index: pd.DatetimeIndex) -> dict:
    return {NEGATIVE: index[index < REGIME_CUT], POSITIVE: index[index >= REGIME_CUT]}


def block_sharpe(r: pd.Series, cash: pd.Series) -> float:
    """Excess Sharpe of consecutive 5-session block sums from ``r``'s first session (an
    incomplete final block dropped), annualised by sqrt(252/5)."""
    grid = beta_control.block_grid(r.index, r.index[0])
    b = beta_control.block_sums(r - cash.reindex(r.index).fillna(0.0), grid).dropna()
    sd = float(b.std(ddof=1))
    return float(b.mean() / sd * math.sqrt(252 / BLOCK)) if sd > 0 else float("nan")


def replica(sleeve: pd.Series, spy: pd.Series, ief: pd.Series, cash: pd.Series) -> tuple[pd.Series, dict]:
    """The sleeve's lagged stock-and-bond replica (F366205's convention):
    c_t + sum_f [b0_f,k (F_t - c_t) + b1_f,k (F_t-5 - c_t-5)], betas from the sleeve's block
    excess return on SPY's and IEF's (same and previous block), estimated only from blocks
    strictly before k (104-block window, minimum 52 usable). ``spy``, ``ief`` and ``cash``
    are on the full calendar, so the lag reaches before the sleeve's first session."""
    idx = sleeve.index
    for name, s in (("SPY", spy), ("IEF", ief), ("cash", cash)):
        if s.reindex(idx).isna().any():
            raise ValueError(f"{name} must cover every sleeve session")
    excess = {"spy": spy - cash, "ief": ief - cash}
    lagged = {k: v.shift(BLOCK) for k, v in excess.items()}
    grid = beta_control.block_grid(idx, idx[0])
    blocks = beta_control.block_sums(pd.DataFrame({"y": sleeve - cash.reindex(idx),
                                                   **{k: v.reindex(idx) for k, v in excess.items()}}), grid)
    betas = beta_control.dimson_betas(pd.DataFrame({"s": blocks["y"]}),
                                      [pd.DataFrame({"s": blocks["spy"]}), pd.DataFrame({"s": blocks["ief"]})],
                                      window=BETA_WINDOW, min_blocks=BETA_MIN)
    coef = pd.DataFrame(betas.coef[:, 0, :], index=blocks.index, columns=["s0", "s1", "i0", "i1"])
    coef = coef[~betas.fallback[:, 0]]
    k = grid[grid.isin(coef.index)]
    sessions = k.index
    if not len(sessions):
        return pd.Series(dtype=float), {"first": None, "sessions": 0}
    b = coef.reindex(k.to_numpy()).set_axis(sessions)
    for name, s in (("SPY lag", lagged["spy"]), ("IEF lag", lagged["ief"])):
        if s.reindex(sessions).isna().any():
            raise ValueError(f"{name} must cover every replica session")
    rep = (cash.reindex(sessions)
           + b["s0"] * excess["spy"].reindex(sessions) + b["s1"] * lagged["spy"].reindex(sessions)
           + b["i0"] * excess["ief"].reindex(sessions) + b["i1"] * lagged["ief"].reindex(sessions))
    return rep, {"first": str(sessions[0].date()), "sessions": int(len(sessions)),
                 "mean_beta_spy": float((coef["s0"] + coef["s1"]).mean()),
                 "mean_beta_ief": float((coef["i0"] + coef["i1"]).mean())}


def crisis_regression(sleeve: pd.Series, hyg: pd.Series, cash: pd.Series) -> dict:
    """OLS of the sleeve's block excess return on HYG's same- and previous-block excess
    returns over the sleeve's sessions (in-sample): beta = b0 + b1, alpha = intercept x 252/5."""
    idx = sleeve.index
    grid = beta_control.block_grid(idx, idx[0])
    blocks = beta_control.block_sums(pd.DataFrame({"y": sleeve - cash.reindex(idx),
                                                   "h": hyg.reindex(idx) - cash.reindex(idx)}), grid)
    Z = np.column_stack([np.ones(len(blocks)), blocks["h"].to_numpy(), np.r_[np.nan, blocks["h"].to_numpy()[:-1]]])
    y = blocks["y"].to_numpy()
    ok = np.isfinite(y) & np.isfinite(Z).all(axis=1)
    coef, *_ = np.linalg.lstsq(Z[ok], y[ok], rcond=None)
    return {"alpha_hat": float(coef[0] * 252 / BLOCK), "beta_hat": float(coef[1] + coef[2]),
            "b0": float(coef[1]), "b1": float(coef[2]), "blocks": int(ok.sum())}


def proxy_screen(proxy_hyg: pd.Series, recorded_hyg: pd.Series) -> dict:
    """The frozen screen of the private HYG series against the recorded one, on the recorded
    one's sessions: correlation >= 0.995 and |annualised mean difference| <= 0.25%/yr."""
    idx = recorded_hyg.index
    a, b = proxy_hyg.reindex(idx), recorded_hyg
    if a.isna().any():
        return {"passes": False, "reason": f"{int(a.isna().sum())} recorded sessions missing from the proxy"}
    corr = float(a.corr(b))
    gap = float((a - b).mean() * 252)
    return {"passes": bool(corr >= SCREEN_CORRELATION and abs(gap) <= SCREEN_MEAN_GAP),
            "correlation": corr, "annualised_mean_gap": gap,
            "sessions": int(len(idx)), "first": str(idx[0].date()), "last": str(idx[-1].date())}


# ── criteria ─────────────────────────────────────────────────────────────────
def band(x: float) -> float:
    return BAND_PER_CARVE * x


def status(deltas: list[float], delta: float) -> str:
    """One frequency of a Sharpe criterion: pass if every window's Δ >= +delta, fail if any
    window's Δ <= -delta, unresolved otherwise."""
    if any(d <= -delta for d in deltas):
        return FAIL
    return PASS if all(d >= delta for d in deltas) else UNRESOLVED


def combine(daily: str, block: str) -> str:
    """Both frequencies: pass at both passes, fail at either fails, otherwise unresolved."""
    if FAIL in (daily, block):
        return FAIL
    return PASS if daily == block == PASS else UNRESOLVED


def pair_stats(p: pd.Series, sleeves: dict, x: float, idx: pd.DatetimeIndex, cash: pd.Series) -> dict:
    """The product and each sleeve's mix at carve ``x`` on sessions ``idx``, both frequencies."""
    pw = p.reindex(idx)
    out = {"first": str(idx[0].date()), "last": str(idx[-1].date()), "sessions": int(len(idx)),
           "product": {"sharpe": sharpe(pw, cash), "block_sharpe": block_sharpe(pw, cash),
                       "max_drawdown": max_drawdown(pw)}}
    for name, s in sleeves.items():
        m = mix(pw, s.reindex(idx), x)
        out[name] = {"sharpe": sharpe(m, cash), "block_sharpe": block_sharpe(m, cash),
                     "max_drawdown": max_drawdown(m), "sleeve_correlation_with_product": float(pw.corr(s.reindex(idx)))}
        out[name]["extra_drawdown_pp"] = 100.0 * (out["product"]["max_drawdown"] - out[name]["max_drawdown"])
    return out


def statistics(p, angl, hyg, rep, cash, x: float, stress: dict | None) -> dict:
    """Every window's statistics at carve ``x`` (no criteria)."""
    common = p.index.intersection(angl.index)
    rep_idx = common.intersection(rep.index)
    out = {}
    for name, idx in regimes(common).items():
        out[name] = {"vs_product_and_hyg": pair_stats(p, {"angl": angl, "hyg": hyg}, x, idx, cash),
                     "vs_replica": pair_stats(p, {"angl": angl, "replica": rep}, x, idx.intersection(rep_idx), cash)}
    if stress is not None:
        sp = stress["product"]
        out["crisis stress"] = {"first": str(sp.index[0].date()), "last": str(sp.index[-1].date()),
                                "sessions": int(len(sp)), "product_max_drawdown": max_drawdown(sp),
                                "mix_max_drawdown": max_drawdown(mix(sp, stress["proxy"], x)),
                                "reported_at_zero_alpha": max_drawdown(mix(sp, stress["proxy_zero_alpha"], x)),
                                "reported_plain_proxy": max_drawdown(mix(sp, stress["plain_proxy"], x))}
        c = out["crisis stress"]
        c["extra_drawdown_pp"] = 100.0 * (c["product_max_drawdown"] - c["mix_max_drawdown"])
    return out


def criteria(stats: dict, x: float) -> dict:
    """C1-C5 at carve ``x`` (CREDIT_SLEEVE_MIX_PROTOCOL.md) from ``statistics``."""
    d = band(x)
    deltas = {"C1": {}, "C3": {}, "C4": {}}
    for freq, key in (("daily", "sharpe"), ("block", "block_sharpe")):
        for c in deltas:
            deltas[c][freq] = []
        for w in (NEGATIVE, POSITIVE):
            ph, pr = stats[w]["vs_product_and_hyg"], stats[w]["vs_replica"]
            deltas["C1"][freq].append(ph["angl"][key] - ph["product"][key])
            deltas["C3"][freq].append(ph["angl"][key] - ph["hyg"][key])
            deltas["C4"][freq].append(pr["angl"][key] - pr["replica"][key])
    out = {}
    for c, by_freq in deltas.items():
        st = {f: status(v, d) for f, v in by_freq.items()}
        out[c] = {"status": combine(st["daily"], st["block"]), "by_frequency": st,
                  "deltas": {f: dict(zip((NEGATIVE, POSITIVE), v)) for f, v in by_freq.items()}}
    out["C2"] = {"status": PASS if all(stats[w]["vs_product_and_hyg"]["angl"]["max_drawdown"]
                                       >= stats[w]["vs_product_and_hyg"]["product"]["max_drawdown"]
                                       for w in (NEGATIVE, POSITIVE)) else FAIL}
    cs = stats.get("crisis stress")
    out["C5"] = {"status": None if cs is None else (PASS if cs["mix_max_drawdown"] >= cs["product_max_drawdown"] else FAIL)}
    out["band"] = d
    return out


def verdict(crit: dict) -> str:
    sharpe_side = [crit[c]["status"] for c in ("C1", "C3", "C4")]
    if FAIL in sharpe_side:
        return NO_CREDIT
    if UNRESOLVED in sharpe_side:
        return NO_EFFECT
    if crit["C2"]["status"] == FAIL or crit["C5"]["status"] == FAIL:
        return SHARPE_ONLY
    return ADD if crit["C5"]["status"] == PASS else UNTESTED


def overall(per_carve: dict) -> dict:
    """Every carve's verdict; the headline is the best; ADD lists its carves and sizes nothing.
    A consequence applies to the carves that read it, so NO CREDIT carves are named whatever
    the headline."""
    verdicts = {k: c["verdict"] for k, c in per_carve.items()}
    best = max(verdicts.values(), key=lambda v: RANK[v])
    return {"headline": best, "by_carve": verdicts,
            "carves_reading_add": [k for k, v in verdicts.items() if v in (ADD, UNTESTED)],
            "carves_reading_no_credit": [k for k, v in verdicts.items() if v == NO_CREDIT]}


# ── reported only ────────────────────────────────────────────────────────────
def robustness(series: dict, p: pd.Series, cash: pd.Series) -> dict:
    """FALN and ANGL of DS-1fc68b55 against its own HYG: the C1-C3 statistics (no verdict)."""
    out = {}
    for sleeve in ("FALN", "ANGL"):
        common = p.index.intersection(series[sleeve].index)
        out[sleeve] = {f"{x:.0%}": {w: pair_stats(p, {"sleeve": series[sleeve], "hyg": series["HYG"]}, x, idx, cash)
                                    for w, idx in regimes(common).items()} for x in CARVE_OUTS}
    return out


def calendar_2022(p, angl, hyg, cash) -> dict:
    idx = p.index.intersection(angl.index)
    idx = idx[(idx >= "2022-01-01") & (idx <= "2022-12-31")]
    return {f"{x:.0%}": pair_stats(p, {"angl": angl, "hyg": hyg}, x, idx, cash) for x in CARVE_OUTS}


# ── invariants ───────────────────────────────────────────────────────────────
def ledger_state() -> dict:
    from src.research import forward_watch as fw
    spec, _h = fw.load(WATCH)
    return {"family_counts": trials.family_counts(),
            "evaluator_sha256": {WATCH: fw.evaluator_sha256(tuple(spec["evaluator_sources"]))}}


_DATE_KEY = re.compile(r"^\d{4}-\d{2}-\d{2}")


def series_like(obj, path="$") -> list[str]:
    """Paths that could carry a daily series (option A: aggregates only): a list longer than
    MAX_LIST, or an object keyed by date."""
    if isinstance(obj, dict):
        own = [path] if any(_DATE_KEY.match(str(k)) for k in obj) else []
        return own + [p for k, v in obj.items() for p in series_like(v, f"{path}.{k}")]
    if isinstance(obj, (list, tuple)):
        own = [path] if len(obj) > MAX_LIST else []
        return own + [p for i, v in enumerate(obj) for p in series_like(v, f"{path}[{i}]")]
    return []


# ── run ──────────────────────────────────────────────────────────────────────
def _resolve(prefix: str) -> str:
    found = sorted((REPO / "docs/research/data").glob(f"DS-{prefix}*.json"))
    if len(found) != 1:
        raise SystemExit(f"expected one DS-{prefix}* manifest, found {len(found)}")
    return found[0].name[3:-5]


def study() -> dict:
    keys = [PRODUCT, ANGL, HYG, *ROBUSTNESS.values()]
    recs = {r.key: r for r in trials.iter_trials() if r.key in keys}
    missing = sorted(set(keys) - set(recs))
    if missing:
        raise SystemExit(f"recorded trials not found: {missing}")
    loaded = {k: holding(stored_returns(v)) for k, v in trials.load_returns([recs[k] for k in keys]).items()}
    p, angl, hyg = loaded[PRODUCT], loaded[ANGL], loaded[HYG]
    product = daily_data.load_snapshot(PRODUCT_SNAPSHOT).returns()
    cash = product.cash
    rep, rep_info = replica(angl, session_total(product, "SPY"), session_total(product, "IEF"), cash)

    reg = crisis_regression(angl, hyg, cash)
    proxy_sha = _resolve(PROXY_SNAPSHOT)
    h = session_total(daily_data.load_snapshot(proxy_sha).returns(), "HYG")
    screen = proxy_screen(h, hyg)
    sidx = p.index[(p.index >= STRESS[0]) & (p.index <= STRESS[1])]
    stress = None
    if screen["passes"] and h.reindex(sidx).isna().any():
        screen = {**screen, "passes": False, "reason": "the proxy misses crisis-window sessions"}
    if screen["passes"]:
        c, hs = cash.reindex(sidx), h.reindex(sidx)
        mean_gap = float((angl - hyg.reindex(angl.index)).mean())
        stress = {"product": p.reindex(sidx),
                  "proxy": c + reg["beta_hat"] * (hs - c) + reg["alpha_hat"] / 252.0,
                  "proxy_zero_alpha": c + reg["beta_hat"] * (hs - c),
                  "plain_proxy": hs + mean_gap}

    per_carve = {}
    for x in CARVE_OUTS:
        st = statistics(p, angl, hyg, rep, cash, x, stress)
        cr = criteria(st, x)
        per_carve[f"{x:.0%}"] = {"criteria": cr, "verdict": verdict(cr), "statistics": st}
    return {"carve_outs": per_carve, "overall": overall(per_carve),
            "reported": {"carve_2.5%": statistics(p, angl, hyg, rep, cash, SECONDARY_CARVE, stress),
                         "calendar_2022": calendar_2022(p, angl, hyg, cash),
                         "provider_robustness": robustness({k: loaded[v] for k, v in ROBUSTNESS.items()}, p, cash)},
            "replica": rep_info,
            "crisis_proxy": {"screen": screen, "regression": reg, "snapshot": proxy_sha,
                             "window": [str(STRESS[0].date()), str(STRESS[1].date())], "run": stress is not None},
            "inputs": {"returns_sha256": {k: recs[k].returns_sha for k in keys},
                       "cash_and_factor_snapshot": PRODUCT_SNAPSHOT, "proxy_snapshot": proxy_sha}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", default=str(OUT))
    args = ap.parse_args(argv)
    before = ledger_state()
    res = study()
    after = ledger_state()
    if before != after:
        raise SystemExit("the trial ledger or the watch's evaluator changed during the run; nothing written")
    out = {"schema_version": 1, "vintage": pd.Timestamp.today().date().isoformat(), "protocol": PROTOCOL,
           "product": PRODUCT, **res, "invariants": {"unchanged_during_run": True,
                                                     "evaluator_sha256": after["evaluator_sha256"],
                                                     "family_counts_sha256": hashlib.sha256(json.dumps(
                                                         after["family_counts"], sort_keys=True).encode()).hexdigest()}}
    series = series_like(out)
    if series:
        raise SystemExit(f"refusing to write a series (option A): {series[:3]}")
    text = json.dumps(out, indent=1, sort_keys=True, default=float) + "\n"
    Path(args.json).write_text(text, encoding="utf-8")
    print(f"wrote {args.json} (sha256 {hashlib.sha256(text.encode()).hexdigest()})")
    cp = res["crisis_proxy"]
    print(f"crisis proxy: run={cp['run']} screen {json.dumps(cp['screen'], default=float)}")
    print(f"crisis regression: {json.dumps(cp['regression'], default=float)}")
    print(f"replica: {json.dumps(res['replica'], default=float)}")
    for x, c in res["carve_outs"].items():
        cr = c["criteria"]
        print(f"\ncarve {x} (band {cr['band']:.4f}): {c['verdict']}  "
              + "  ".join(f"{k}={cr[k]['status']}" for k in ("C1", "C2", "C3", "C4", "C5")))
        for k in ("C1", "C3", "C4"):
            print(f"  {k} " + "  ".join(f"{f}: " + " / ".join(f"{d:+.3f}" for d in v.values())
                                        for f, v in cr[k]["deltas"].items()))
        for w in (NEGATIVE, POSITIVE):
            s = c["statistics"][w]["vs_product_and_hyg"]
            print(f"  {w:34} DD 60/40 {s['product']['max_drawdown']:.1%} ANGL mix {s['angl']['max_drawdown']:.1%}"
                  f" (extra {s['angl']['extra_drawdown_pp']:+.2f}pp)")
        if "crisis stress" in c["statistics"]:
            s = c["statistics"]["crisis stress"]
            print(f"  crisis stress {s['first']}..{s['last']}: DD 60/40 {s['product_max_drawdown']:.1%}"
                  f" mix {s['mix_max_drawdown']:.1%} (zero alpha {s['reported_at_zero_alpha']:.1%},"
                  f" plain proxy {s['reported_plain_proxy']:.1%})")
    print(f"\noverall: {res['overall']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
