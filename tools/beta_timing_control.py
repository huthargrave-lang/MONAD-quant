"""
beta_timing_control — the beta-exposure control of the admission candidates
(docs/research/BETA_TIMING_CONTROL_PROTOCOL.md, frozen with clarifications 1-2).

  venv/bin/python tools/beta_timing_control.py run --acknowledge-live H404702

Reads the recorded series of H404702 and its benchmark, of the positive (F366204) and
negative (F366202) controls, and of CEFS and MDCEX against PCEF. The three replayed pairs
need weights, so each book is replayed once, as a counted trial with its recorded spec in
its recorded family. A replay must reproduce the record to 1e-12 and satisfy the book
identity, and H404702's gate inputs must be identical before and after; otherwise the
result is NOT RUN. Writes docs/research/data/beta_timing_control.json (statistics only).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import admit_tactical as at  # noqa: E402
import cef_etf_report  # noqa: E402

from src.research import beta_control as bc  # noqa: E402
from src.research import daily_data, prereg, trials  # noqa: E402
from src.research.backtest_trials import family_members  # noqa: E402
from src.research.daily_domains import DOMAINS  # noqa: E402
from src.research.daily_strategy import cost_matrix, evaluate_daily  # noqa: E402
from src.research.daily_trials import (daily_spec, family_name, record_daily,  # noqa: E402
                                       refuse_unacknowledged, stored_returns)

PRODUCER = "tools/beta_timing_control.py"
PROTOCOL = "docs/research/BETA_TIMING_CONTROL_PROTOCOL.md"
OUT = REPO / "docs/research/data/beta_timing_control.json"

PAIRS = {
    "H404702": {"domain": "cef_discount", "cand": "TR-20261006T034817Z-5245a64f#3",
                "bench": "TR-20261006T012341Z-86834435#0"},
    "positive_control_F366204": {"domain": "cef_etf_tilt", "cand": "TR-20261009T073545Z-b39f895c#0",
                                 "bench": "TR-20261009T073344Z-da2b0d8d#0"},
    "negative_control_F366202": {"domain": "metal_trust_discount", "cand": "TR-20261008T185930Z-9488e29b#0",
                                 "bench": "TR-20261008T185928Z-5c567742#0"},
}
PRODUCTS = {
    "CEFS": {"cand": "TR-20261007T045202Z-1202df3f#0", "bench": "TR-20261007T045201Z-e56e6db5#0",
             "role": "decision series"},
    "MDCEX": {"cand": "TR-20261007T051701Z-9672d791#0", "bench": "TR-20261007T051659Z-dfb4dff7#0",
              "role": "corroboration only"},
}
H404702_REFERENCE_SHA = "23aa6231"
EXPOSED = 1.0 - 1e-9
PRIMARY_WINDOW, PRIMARY_MIN = 156, 48
PRODUCT_WINDOW, PRODUCT_MIN = 104, 52
SHORT_WINDOW, SHORT_MIN = 26, 13
MIN_CATEGORY_OTHERS = 4


class NotRun(RuntimeError):
    """A pre-stated check failed: the result is NOT RUN, disclosed."""


def iso(t) -> str:
    return pd.Timestamp(t).date().isoformat()


# ── ledger ───────────────────────────────────────────────────────────────────
def records() -> dict:
    return {r.key: r for r in trials.iter_trials()}


def recorded_series(recs: dict, *keys) -> dict:
    missing = [k for k in keys if k not in recs or recs[k].status != "ok"]
    if missing:
        raise NotRun(f"cited trials missing or not ok: {missing}")
    loaded = trials.load_returns([recs[k] for k in keys])
    return {k: stored_returns(loaded[k]) for k in keys}


def check_h404702_references(recs: dict) -> list[str]:
    """The four 1x reference trials on H404702's window share one returns sha."""
    bench = recs[PAIRS["H404702"]["bench"]]
    peers = [r for r in recs.values() if r.family == bench.family and r.status == "ok"
             and (r.spec.get("data") or {}) == bench.spec["data"]
             and (r.spec.get("params") or {}).get("cost_multiple") == 1.0
             and r.producer != PRODUCER]
    shas = {r.returns_sha for r in peers}
    if len(peers) < 4 or len(shas) != 1 or not next(iter(shas)).startswith(H404702_REFERENCE_SHA):
        raise NotRun(f"H404702's 1x reference trials ({len(peers)}) do not share returns sha "
                     f"{H404702_REFERENCE_SHA}: {sorted(s[:12] for s in shas)}")
    return sorted(r.key for r in peers)


def gate_inputs(hypothesis: str, ctx, dom) -> dict:
    """What H404702's gate reads from the ledger, through its own functions: the latest
    ok trial per point on the registered window (with its returns sha), the benchmark's
    latest recorded run, the unknown specs, and m."""
    spec, _ = prereg.load(hypothesis)
    p = spec["params"]
    start, end = dom.window(ctx)
    everything = trials.iter_trials()
    searched = [r for r in family_members(everything, family_name(dom.name)) if r.producer != at.PRODUCER]
    refs = [r for r in family_members(everything, family_name(dom.name, reference=True))
            if r.producer != at.PRODUCER]
    ref_rec = [r for r in refs if r.status == "ok" and at._same_window(r, p["data"], start, end)]
    cand = recorded_series(records(), PAIRS[hypothesis]["cand"])[PAIRS[hypothesis]["cand"]]
    fam = at.family_active(searched, refs, p["data"], start, end, p["candidate"], cand)
    m, parts = at.familywise_m(searched, fam.latest, p, fam.unknown)
    return {"latest": {f"{k[0]} {dict(k[1])}": r.returns_sha for k, r in sorted(fam.latest.items())},
            "reference": ref_rec[-1].returns_sha, "unknown": sorted(fam.unknown), "m": m, "m_parts": parts}


# ── replays ──────────────────────────────────────────────────────────────────
def carries_in(tranches, start) -> bool:
    start = pd.Timestamp(start)
    return any((len(o) and o.index.min() < start)
               for t in tranches for o in (t.open_orders, t.close_orders))


def replay(rec, ctx, dom, *, acknowledged, context: dict):
    """One counted, exact replay of ``rec``: same point, data, window, costs and family."""
    start, end = dom.window(ctx)
    point = {"class": rec.spec["params"]["class"], "params": rec.spec["params"]["params"]}
    mult = rec.spec["params"]["cost_multiple"]
    data = ctx.data_spec(start, end)
    params = daily_spec(point, cost_multiple=mult, domain=dom.name)
    if data != rec.spec["data"] or params != rec.spec["params"]:
        raise NotRun(f"{rec.key}: the replay's spec would differ from the record's")
    refuse_unacknowledged(rec.family, acknowledged)
    tranches = dom.decide(ctx, point)
    tiers = dom.tiers(ctx)
    with trials.open_run(producer=PRODUCER, family=rec.family,
                         context={**data, "role": f"beta-exposure control: exact replay of {rec.key}",
                                  **context}) as run:
        t = run.begin(params=params, data=data)
        res = evaluate_daily(tranches, ctx.snap, start=start, end=end, cost_multiple=mult, tiers=tiers)
        record_daily(t, res)
        key = f"{run.run_id}#0"
    i0 = int(ctx.snap.dates.searchsorted(start))
    bound = 3.0 * float(cost_matrix(list(ctx.snap.assets), ctx.snap.dates[i0:i0 + 1], tiers).max()) * 1e-4 * mult
    return res, key, carries_in(tranches, start), bound


def total_returns(snap) -> pd.DataFrame:
    r = snap.returns()
    return (1 + r.night) * (1 + r.day) - 1


def replay_pair(name: str, recs: dict, *, acknowledged) -> dict:
    """Replay a pair's two books and run every pre-stated check on them."""
    cfg = PAIRS[name]
    dom = DOMAINS[cfg["domain"]]
    cand, bench = recs[cfg["cand"]], recs[cfg["bench"]]
    if bench.spec["data"] != cand.spec["data"]:
        raise NotRun(f"{name}: the candidate and benchmark trials ran on different data or windows")
    ctx = dom.load(cand.spec["data"])
    recorded = recorded_series(recs, cfg["cand"], cfg["bench"])
    tot = total_returns(ctx.snap)
    out = {"ctx": ctx, "dom": dom, "tot": tot, "recorded": recorded, "checks": {}}
    for role, rec in (("cand", cand), ("bench", bench)):
        res, key, carry, bound = replay(rec, ctx, dom, acknowledged=acknowledged,
                                        context={"control": name, "book": role})
        new = records()[key]
        problems = bc.reproduction_problems(res.returns, recorded[rec.key])
        problems += bc.weight_identity_problems(res.returns, res.weights, tot, res.cash, res.cost_paid,
                                                carry_in=carry, first_session_fee_bound=bound)
        out["checks"][role] = {"recorded": rec.key, "replay": key, "carry_in": carry,
                               "same_spec_hash": new.spec_hash == rec.spec_hash,
                               "same_returns_sha": new.returns_sha == rec.returns_sha,
                               "max_abs_diff": float(np.max(np.abs(res.returns.to_numpy()
                                                                   - recorded[rec.key].to_numpy()))),
                               "problems": problems}
        if problems or new.spec_hash != rec.spec_hash:
            raise NotRun(f"{name} {role}: {problems or ['spec hash differs']}")
        out[role] = res
    return out


# ── the control on one book pair ─────────────────────────────────────────────
def statistics(active: pd.Series, delta: pd.DataFrame, asset_r: pd.DataFrame, grid: pd.Series,
               min_blocks: int, variants: dict, tm_factor: pd.Series) -> dict:
    """``variants``: name -> (factor frames, window, minimum, self-factor assets), with
    "primary" among them. Returns the primary statistic, the robustness checks, the
    static/timing split and the verdict."""
    sample = grid[grid >= min_blocks]
    a_w = bc.block_sums(active, sample).to_numpy()
    if np.isnan(a_w).any():
        raise NotRun("the active series has a missing session inside the sample")
    asset_blocks = bc.block_sums(asset_r, grid)
    out, robust = {}, {}
    for vname, (factors, window, minimum, selfs) in variants.items():
        betas = bc.dimson_betas(asset_blocks, [bc.block_sums(F.reindex(grid.index), grid) for F in factors],
                                window=window, min_blocks=minimum, self_factor=selfs)
        X = bc.exposure(delta, factors, betas, sample)
        X_w = bc.block_sums(X.daily, sample).to_numpy()
        stat = bc.primary(a_w, X_w)
        stat["fallback_share"] = X.fallback_share
        stat["static_ann"] = X.static_daily * 252.0
        stat["timing_ann"] = stat["explained_ann"] - stat["static_ann"]
        if vname == "primary":
            out["primary"] = stat
            out["R0"] = bc.free_g(a_w, X_w)
            robust["R0"] = {"s": out["R0"]["s"]}
            out["_betas"], out["_X"] = betas, X
        else:
            out[vname] = stat
            robust[vname] = {"s": stat["s"], "t_E": stat["t_E"]}
    F_all = bc.block_sums(tm_factor.reindex(grid.index), grid).to_numpy()
    F_w = F_all[min_blocks:]
    out["R2"] = bc.treynor_mazuy(a_w, F_w)
    out["R2b"] = bc.conditional_beta(a_w, F_w, bc.trailing(F_all)[min_blocks:])
    robust["R2"], robust["R2b"] = {"s": out["R2"]["s"]}, {"s": out["R2b"]["s"]}
    v, reasons = bc.verdict(out["primary"], robust)
    out["verdict"], out["reasons"] = v, reasons
    out["sample"] = [iso(sample.index[0]), iso(sample.index[-1])]
    return out


def exposure_start(cand, bench) -> pd.Timestamp:
    both = (cand.exposure >= EXPOSED) & (bench.exposure >= EXPOSED)
    if not both.any():
        raise NotRun("the books never reach full exposure together")
    return both.idxmax()


def category_factor(tot: pd.DataFrame, funds: list, elig: pd.DataFrame, category: dict) -> pd.DataFrame:
    """For fund i on session t: the equal-weight return of the OTHER funds of i's
    category that held benchmark weight at the previous close; the global equal-weight
    eligible return when fewer than MIN_CATEGORY_OTHERS others exist."""
    sessions = elig.index
    R = tot.reindex(index=sessions, columns=funds)
    if (elig & R.isna()).to_numpy().any():
        raise NotRun("an eligible fund has no return on a session")
    E = elig.astype(float)
    Rz = R.where(elig, 0.0)
    glob = R.where(elig).mean(axis=1)
    out = {}
    cats = pd.Series({f: category.get(f) for f in funds})
    for cat, fs in cats.groupby(cats, dropna=False):
        fs = list(fs.index)
        S, N = Rz[fs].sum(axis=1), E[fs].sum(axis=1)
        for f in fs:
            others = N - E[f]
            loo = (S - Rz[f]) / others.where(others > 0)
            out[f] = loo.where(others >= MIN_CATEGORY_OTHERS, glob) if isinstance(cat, str) else glob
    return pd.DataFrame(out, index=sessions)


def frame_of(series: pd.Series, columns) -> pd.DataFrame:
    return pd.DataFrame({c: series for c in columns})


def run_h404702(pair: dict) -> dict:
    ctx, tot, recorded = pair["ctx"], pair["tot"], pair["recorded"]
    cand, bench = pair["cand"], pair["bench"]
    funds = [a for a in ctx.snap.assets if a in ctx.panel.category]
    start = exposure_start(cand, bench)
    grid = bc.block_grid(cand.returns.index, start)
    delta = (cand.weights[funds] - bench.weights[funds]).shift(1).fillna(0.0)
    elig = bench.weights[funds].shift(1).fillna(0.0) > 0
    Fcat = category_factor(tot, funds, elig, ctx.panel.category)
    b_rec = recorded[PAIRS["H404702"]["bench"]]
    active = recorded[PAIRS["H404702"]["cand"]] - b_rec
    variants = {
        "primary": ([Fcat], PRIMARY_WINDOW, PRIMARY_MIN, frozenset()),
        "R1a": ([frame_of(b_rec, funds)], PRIMARY_WINDOW, PRIMARY_MIN, frozenset()),
        "R1b": ([frame_of(tot["SPY"], funds)], PRIMARY_WINDOW, PRIMARY_MIN, frozenset()),
        "R3": ([Fcat, frame_of(tot["IEF"], funds)], PRIMARY_WINDOW, PRIMARY_MIN, frozenset()),
        "R4": ([Fcat], SHORT_WINDOW, SHORT_MIN, frozenset()),
    }
    out = statistics(active, delta, tot[funds], grid, PRIMARY_MIN, variants, b_rec)
    out["exposure_start"] = iso(start)
    return out


def matched_factor(tot: pd.DataFrame, assets: list, etf_of: dict) -> tuple[pd.DataFrame, frozenset]:
    """Each fund's matched ETF return; an ETF is its own factor."""
    selfs = frozenset(a for a in assets if a not in etf_of)
    return pd.DataFrame({a: tot[etf_of.get(a, a)] for a in assets}), selfs


def run_fund_vs_etf(name: str, pair: dict, etf_of: dict, *, families: dict | None) -> dict:
    ctx, tot, recorded = pair["ctx"], pair["tot"], pair["recorded"]
    cand, bench = pair["cand"], pair["bench"]
    # every fund the mapping names and every ETF, held or not: Delta is 0 where not held,
    # and the within-family split needs each fund's beta (F366204's decomposition spans
    # every matched fund)
    universe = set(etf_of) | set(etf_of.values())
    held = [a for a in cand.weights.columns
            if a in universe or cand.weights[a].abs().sum() > 0 or bench.weights[a].abs().sum() > 0]
    start = exposure_start(cand, bench)
    grid = bc.block_grid(cand.returns.index, start)
    delta = (cand.weights[held] - bench.weights[held]).shift(1).fillna(0.0)
    b_rec = recorded[PAIRS[name]["bench"]]
    active = recorded[PAIRS[name]["cand"]] - b_rec
    Fm, selfs = matched_factor(tot, held, etf_of)
    variants = {
        "primary": ([Fm], PRIMARY_WINDOW, PRIMARY_MIN, selfs),
        "R1b": ([frame_of(tot["SPY"], held)], PRIMARY_WINDOW, PRIMARY_MIN, frozenset()),
        "R4": ([Fm], SHORT_WINDOW, SHORT_MIN, selfs),
    }
    out = statistics(active, delta, tot[held], grid, PRIMARY_MIN, variants, b_rec)
    out["exposure_start"] = iso(start)
    if families is not None:
        out["A_within"] = within_part(pair, out, held, etf_of, families, grid)
    return out


def within_part(pair, out, held, etf_of, families, grid) -> dict:
    """F366204's within-family part under this control (reported, not decisive): the
    realised within part, cross-checked against cef_etf_report.decompose, and its
    exposure from the primary betas, x_hat_i = (b0_i - 1) E_t + b1_i E_t-5."""
    ctx, tot = pair["ctx"], pair["tot"]
    funds = [f for f in etf_of if f in pair["cand"].weights.columns]     # decompose's fund set
    dw = (pair["cand"].weights[funds] - pair["bench"].weights[funds]).shift(1).fillna(0.0)
    x = pd.DataFrame({f: tot[f] - tot[etf_of[f]] for f in funds}).reindex(dw.index).fillna(0.0)
    live = (dw != 0) | (x != 0)
    within = bc.within_category_part(dw, x, families, live)
    ref = cef_etf_report.decompose(ctx.panel, ctx.snap, pair["cand"], pair["bench"])["within"]
    common = within.index.intersection(ref.index)
    gap = float((within.reindex(common) - ref.reindex(common)).abs().max())
    if gap > 1e-12:
        raise NotRun(f"the within-family part disagrees with cef_etf_report.decompose by {gap:.3e}")
    sample = grid[grid >= PRIMARY_MIN]
    betas = out["_betas"]
    blk = sample.to_numpy()
    cols = [betas.assets.index(f) for f in funds]
    E = pd.DataFrame({f: tot[etf_of[f]] for f in funds})
    cur = E.reindex(sample.index).to_numpy()
    lag = E.shift(bc.BLOCK).reindex(sample.index).to_numpy()
    xhat = (betas.coef[blk][:, cols, 0] - 1.0) * cur + betas.coef[blk][:, cols, 1] * lag
    xhat = pd.DataFrame(np.nan_to_num(xhat), index=sample.index, columns=funds)
    X_within = bc.within_category_part(dw.reindex(sample.index), xhat, families,
                                       live.reindex(sample.index))
    a_w = bc.block_sums(within, sample).to_numpy()
    X_w = bc.block_sums(X_within, sample).to_numpy()
    return bc.primary(a_w, X_w)


def run_product(name: str, recs: dict) -> dict:
    cfg = PRODUCTS[name]
    series = recorded_series(recs, cfg["cand"], cfg["bench"])
    P, Q = series[cfg["cand"]].iloc[1:], series[cfg["bench"]].iloc[1:]   # drop the build session
    if not P.index.equals(Q.index):
        raise NotRun(f"{name}: the product and PCEF series cover different sessions")
    snap = daily_data.load_snapshot(recs[cfg["cand"]].spec["data"]["snapshot"])
    spy = total_returns(snap)["SPY"]
    grid = bc.block_grid(P.index, P.index[0])
    assets = pd.DataFrame({name: P, "PCEF": Q})
    delta = pd.DataFrame({name: 1.0, "PCEF": -1.0}, index=P.index)
    variants = {
        "primary": ([frame_of(Q, assets.columns)], PRODUCT_WINDOW, PRODUCT_MIN, frozenset({"PCEF"})),
        "R1b": ([frame_of(spy, assets.columns)], PRODUCT_WINDOW, PRODUCT_MIN, frozenset()),
        "R4": ([frame_of(Q, assets.columns)], SHORT_WINDOW, SHORT_MIN, frozenset({"PCEF"})),
    }
    out = statistics(P - Q, delta, assets, grid, PRODUCT_MIN, variants, Q)
    out["role"] = cfg["role"]
    return out


# ── controls and the record ──────────────────────────────────────────────────
def apply_controls(results: dict) -> list[str]:
    """The protocol's method-validity rules, applied to H404702's verdict."""
    notes = []
    pos = results["positive_control_F366204"]["verdict"]
    neg = results["negative_control_F366202"]["verdict"]
    h = results["H404702"]
    if pos not in (bc.BETA, bc.BETA_LIKE) and h["verdict"] == bc.SURVIVES:
        h["verdict"] = bc.INCONCLUSIVE
        notes.append(f"positive control read {pos}: H404702 cannot read SURVIVES (demoted)")
    if neg == bc.BETA and h["verdict"] == bc.BETA:
        h["verdict"] = bc.INCONCLUSIVE
        notes.append("negative control read BETA EXPOSURE: H404702's BETA EXPOSURE demoted")
    return notes


def public(d: dict) -> dict:
    return {k: v for k, v in d.items() if not k.startswith("_")}


def cmd_run(args) -> int:
    if trials.code_state().get("dirty"):
        raise SystemExit("the protocol requires a clean tree: commit first")
    recs = records()
    out = {"schema_version": 1, "vintage": pd.Timestamp.today().date().isoformat(), "protocol": PROTOCOL}
    try:
        out["h404702_reference_peers"] = check_h404702_references(recs)
        dom = DOMAINS["cef_discount"]
        ctx = dom.load(recs[PAIRS["H404702"]["cand"]].spec["data"])
        before = gate_inputs("H404702", ctx, dom)
        pairs = {n: replay_pair(n, recs, acknowledged=args.acknowledge_live) for n in PAIRS}
        recs = records()
        after = gate_inputs("H404702", ctx, dom)
        out["gate_invariance"] = {"identical": before == after, "before": before, "after": after}
        if before != after:
            raise NotRun("H404702's gate inputs changed across the replays")
        results = {"H404702": run_h404702(pairs["H404702"])}
        inputs = pairs["positive_control_F366204"]["ctx"].panel
        etf_of = {f: m["etf"] for f, m in inputs.matched.items()}
        results["positive_control_F366204"] = run_fund_vs_etf("positive_control_F366204",
                                                              pairs["positive_control_F366204"], etf_of,
                                                              families=inputs.data["families"])
        mt_pairs = recs[PAIRS["negative_control_F366202"]["cand"]].spec["params"]["params"]["pairs"]
        results["negative_control_F366202"] = run_fund_vs_etf("negative_control_F366202",
                                                              pairs["negative_control_F366202"],
                                                              {t: e for t, e in mt_pairs}, families=None)
        for name in PRODUCTS:
            results[name] = run_product(name, recs)
        out["control_notes"] = apply_controls(results)
        out["replays"] = {n: p["checks"] for n, p in pairs.items()}
        out["results"] = {n: public(r) for n, r in results.items()}
    except NotRun as exc:
        out["verdict"] = "NOT RUN"
        out["reason"] = str(exc)
    text = json.dumps(out, indent=1, default=float, sort_keys=True) + "\n"
    Path(args.json).write_text(text, encoding="utf-8")
    sha = hashlib.sha256(text.encode()).hexdigest()
    print(f"wrote {args.json} (sha256 {sha})")
    if "results" not in out:
        print(f"NOT RUN: {out['reason']}")
        return 1
    for n, r in out["results"].items():
        p = r["primary"]
        print(f"{n:28} {r['verdict']:26} s {p['s']:+.2f}  alpha {p['alpha_ann']:+.4f}  raw {p['raw_ann']:+.4f}  "
              f"t_alpha {min(p['t_alpha']):+.2f}  t_E {min(p['t_E']):+.2f}  {'; '.join(r['reasons'])}")
    for note in out["control_notes"]:
        print("control:", note)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--acknowledge-live", nargs="*", default=[])
    r.add_argument("--json", default=str(OUT))
    r.set_defaults(fn=cmd_run)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
