"""
domain_search — run a daily-strategy domain's frozen grid through the counted evaluator,
and judge every family member against the domain's benchmark, relatively.

One tool for every domain in src/research/daily_domains.py (ETF timing vs the static 60/40,
CEF selection vs the equal-weight CEF universe, crypto trend vs a static half-crypto blend).
The domain defines the data, rules, benchmark, costs, window, eras, frozen grids and
declared prior search; this tool only runs and reports. ``tools/daily_search.py`` and
``tools/cef_search.py`` are kept as named entry points for their domains.

Before any trial: the grid must have no two points with identical orders, and every live
registered hypothesis in the family must be acknowledged (``--acknowledge-live``), because
new trials count against it (F404708). The benchmark is recorded once per data and window.

The report reads the ledger: per point, excess-over-cash Sharpe, CAGR, max drawdown, cost,
mean exposure, the ACTIVE Sharpe over the benchmark (whole window and per era) and the
VOL-MATCHED active Sharpe (positive iff the Sharpe beats the benchmark's; it exposes a
"win" that is only more exposure to a rising asset); look-ahead at 12 cuts;
Hansen's SPA over the family at mean blocks 20/63/126; the best point's active DSR.

  venv/bin/python tools/domain_search.py crypto_trend --snapshot <sha>
  venv/bin/python tools/domain_search.py cef_discount --snapshot <sha> --panel <sha> --grid banded
"""
from __future__ import annotations

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import pandas as pd  # noqa: E402

from src.research import allocation_stats as stats  # noqa: E402
from src.research import trials  # noqa: E402
from src.research.backtest_trials import family_members  # noqa: E402
from src.research.daily_domains import DOMAINS, Context, Domain  # noqa: E402
from src.research.daily_strategy import evaluate_daily  # noqa: E402
from src.research.daily_trials import (daily_spec, family_name, record_daily,  # noqa: E402
                                       refuse_unacknowledged, stored_returns)

PRODUCER = "tools/domain_search.py"


def label(params) -> str:
    return f"{params['class']} " + json.dumps(params["params"], sort_keys=True, separators=(",", ":"))


def point_of(lab: str) -> dict:
    cls, _, params = lab.partition(" ")
    return {"class": cls, "params": json.loads(params)}


def latest(records, data: dict, start, end, *, cost_multiple=1.0) -> dict:
    """{label: record}: the latest ok trial of each point on this data and window."""
    out = {}
    for r in records:
        d = r.spec.get("data") or {}
        p = r.spec.get("params") or {}
        if (r.status == "ok" and d.get("snapshot") == data["snapshot"]
                and d.get("nav_panel") == data.get("nav_panel")
                and d.get("start") == pd.Timestamp(start).date().isoformat()
                and d.get("end") == pd.Timestamp(end).date().isoformat()
                and p.get("cost_multiple") == cost_multiple):
            out[label(p)] = r
    return out


def run(domain: Domain, ctx: Context, grid_name: str, *, producer: str = PRODUCER) -> tuple:
    start, end = domain.window(ctx)
    data = ctx.data_spec(start, end)
    tiers = domain.tiers(ctx)
    points = domain.grids()[grid_name]()
    dupes = stats.duplicate_points({label(p): domain.decide(ctx, p) for p in points})
    if dupes:
        raise SystemExit(f"refusing to run grid {grid_name!r}: points with identical orders "
                         f"(the same idea counted twice): {dupes}")
    fam, ref_fam = family_name(domain.name), family_name(domain.name, reference=True)
    ref_id = None
    if not latest(family_members(trials.iter_trials(), ref_fam), data, start, end):
        with trials.open_run(producer=producer, family=ref_fam,
                             context={**data, "role": "reference"}) as ref_run:
            t = ref_run.begin(params=daily_spec(domain.reference, domain=domain.name), data=data)
            record_daily(t, evaluate_daily(domain.decide(ctx, domain.reference), ctx.snap,
                                           start=start, end=end, tiers=tiers))
        ref_id = ref_run.run_id
    with trials.open_run(producer=producer, family=fam,
                         context={**data, "grid": grid_name, "grid_size": len(points),
                                  "prior_search_trials": domain.prior_search_trials}) as run_:
        for point in points:
            t = run_.begin(params=daily_spec(point, domain=domain.name), data=data)
            try:
                result = evaluate_daily(domain.decide(ctx, point), ctx.snap, start=start,
                                        end=end, tiers=tiers)
            except Exception as exc:  # noqa: BLE001 — counted as an error, then reported
                t.fail(f"{type(exc).__name__}: {exc}")
                continue
            record_daily(t, result)
    return ref_id, run_.run_id


def stress(domain: Domain, ctx: Context, grid_name: str, *, multiple: float,
           producer: str = PRODUCER) -> dict:
    """The cost stress: the benchmark and every point of ``grid_name`` run at ``multiple``
    x the domain's costs, COUNTED (in the domain's families, run context role
    "cost_stress"). A run already recorded on this data, window and multiple is reused,
    not repeated. Returns {label: {"active_sharpe", "active_ann"}} against the benchmark
    at the same multiple, read back from the ledger."""
    if multiple <= 0:
        raise ValueError("a cost multiple must be positive")
    start, end = domain.window(ctx)
    data = ctx.data_spec(start, end)
    tiers = domain.tiers(ctx)
    points = domain.grids()[grid_name]()
    fam, ref_fam = family_name(domain.name), family_name(domain.name, reference=True)

    def recorded(family):
        return latest(family_members(trials.iter_trials(), family), data, start, end,
                      cost_multiple=float(multiple))

    def record(family, todo):
        with trials.open_run(producer=producer, family=family,
                             context={**data, "role": "cost_stress", "cost_multiple": float(multiple)}) as run_:
            for point in todo:
                t = run_.begin(params=daily_spec(point, cost_multiple=multiple, domain=domain.name), data=data)
                record_daily(t, evaluate_daily(domain.decide(ctx, point), ctx.snap, start=start, end=end,
                                               cost_multiple=multiple, tiers=tiers))

    if not recorded(ref_fam):
        record(ref_fam, [domain.reference])
    have = recorded(fam)
    todo = [p for p in points if label(daily_spec(p, cost_multiple=multiple, domain=domain.name)) not in have]
    if todo:
        record(fam, todo)
    fam_recs, (ref_rec,) = recorded(fam), recorded(ref_fam).values()
    series = trials.load_returns(list(fam_recs.values()) + [ref_rec])
    ref_r = stored_returns(series[ref_rec.key])
    out = {}
    for lab, rec in sorted(fam_recs.items()):
        a = stats.active_series(stored_returns(series[rec.key]), ref_r)
        out[lab] = {"active_sharpe": stats.annualized_sharpe(a), "active_ann": float(a.mean() * 252)}
    return out


def report(domain: Domain, ctx: Context) -> dict:
    start, end = domain.window(ctx)
    data = ctx.data_spec(start, end)
    everything = trials.iter_trials()
    members = family_members(everything, family_name(domain.name))
    fam = latest(members, data, start, end)
    ref = latest(family_members(everything, family_name(domain.name, reference=True)), data, start, end)
    if len(ref) != 1 or not fam:
        raise SystemExit(f"need one benchmark and a searched grid on this data and window "
                         f"(found {len(ref)} benchmark(s), {len(fam)} point(s))")
    (ref_rec,) = ref.values()
    series = trials.load_returns(list(fam.values()) + [ref_rec])
    ref_r = stored_returns(series[ref_rec.key])
    cash = ctx.snap.returns().cash.reindex(ref_r.index).fillna(0.0)
    active, primary, rows = {}, {}, []
    for lab, rec in sorted(fam.items()):
        strat = stored_returns(series[rec.key])
        a = stats.active_series(strat, ref_r)
        active[lab] = a
        vm = stats.vol_matched_active(strat, ref_r, cash)
        # The verdict's series (Domain.primary, Domain.sign): what the SPA, the ranking and
        # the deflation read. The plain active series is reported either way.
        primary[lab] = domain.sign * (vm if domain.primary == "vol_matched" else a)
        m = rec.metrics or {}
        rows.append({"label": lab, "key": rec.key, "excess_sharpe": m.get("excess_sharpe"),
                     "cagr": m.get("cagr"), "max_drawdown": m.get("max_drawdown"),
                     "turnover_per_year": m.get("turnover_per_year"),
                     "cost_per_year": m.get("cost_per_year"),
                     "active_sharpe": stats.annualized_sharpe(a),
                     "vol_matched_sharpe": stats.annualized_sharpe(vm),
                     "mean_exposure": m.get("mean_exposure"),
                     "active_return_ann": float(a.mean() * 252),
                     "primary_sharpe": stats.annualized_sharpe(primary[lab]),
                     "era_active_sharpe": [e["active_sharpe"] for e in stats.era_sharpes(a, domain.eras)],
                     "era_primary_sharpe": [e["active_sharpe"]
                                            for e in stats.era_sharpes(primary[lab], domain.eras)]})
    rows.sort(key=lambda x: -x["primary_sharpe"])
    best = rows[0]["label"]
    cuts = stats.default_cuts(ctx.snap, start)
    lookahead = {lab: domain.truncation(ctx, point_of(lab), cuts) for lab in fam}
    unknown = ({r.spec_hash for r in members if r.status != "ok"}
               - {r.spec_hash for r in members if r.status == "ok"})
    defl = stats.deflate_active(primary, best, calendar=ctx.snap.dates,
                                prior_trials=domain.prior_search_trials, unknown_specs=len(unknown))
    return {"domain": domain.name, "primary": domain.primary, "sign": domain.sign, "data": data,
            "window": [start.date().isoformat(), end.date().isoformat()],
            "reference": {"key": ref_rec.key, **(ref_rec.metrics or {})}, "rows": rows,
            "lookahead_violations": {k: v for k, v in lookahead.items() if v}, "best": best,
            "familywise": stats.familywise(primary, best), "deflation": defl.__dict__}


def print_report(rep: dict) -> None:
    ref = rep["reference"]
    print(f"\n{rep['domain']}  window {rep['window'][0]}..{rep['window'][1]}")
    if (rep.get("primary"), rep.get("sign")) != ("active", 1):
        print(f"verdict series: {'-' if rep['sign'] < 0 else '+'}{rep['primary']} "
              f"(ranking, SPA, DSR and 'primary' eras read it)")
    print(f"benchmark: excess Sharpe {ref['excess_sharpe']:.2f}  CAGR {ref['cagr']:.2%}  "
          f"maxDD {ref['max_drawdown']:.1%}  cost/y {ref['cost_per_year']:.2%}")
    print(f"\n{'point':58} {'exSh':>5} {'CAGR':>7} {'maxDD':>6} {'cost/y':>6} {'expo':>5} "
          f"{'actSh':>6} {'vmSh':>6}  eras")
    for r in rep["rows"]:
        eras = " ".join(f"{x:+.2f}" if x is not None else "  n/a" for x in r["era_active_sharpe"])
        print(f"{r['label'][:58]:58} {r['excess_sharpe']:5.2f} {r['cagr']:7.2%} {r['max_drawdown']:6.1%} "
              f"{r['cost_per_year']:6.2%} {r['mean_exposure'] or 0:5.2f} {r['active_sharpe']:+6.2f} "
              f"{r['vol_matched_sharpe']:+6.2f}  {eras}")
        if (rep.get("primary"), rep.get("sign")) != ("active", 1):
            pe = " ".join(f"{x:+.2f}" if x is not None else "  n/a" for x in r["era_primary_sharpe"])
            print(f"{'':58} primary Sharpe {r['primary_sharpe']:+.2f}  primary eras {pe}")
    print(f"\nlook-ahead violations: {rep['lookahead_violations'] or 'none at 12 cuts'}")
    print(f"best by the verdict series: {rep['best']}")
    for f in rep["familywise"]:
        print(f"  SPA block {f['mean_block']:>3}: family p={f['spa_pvalue']:.3f}  candidate adjusted "
              f"p={f['candidate_pvalue']:.3f}  (t={f['candidate_t']:+.2f}, K={f['family_size']})")
    d = rep["deflation"]
    print(f"  active DSR {d['dsr']:.4f}  (active Sharpe {d['sharpe_ann']:+.2f} vs SR0 {d['sr0_ann']:.2f}; "
          f"N {d['n_trials']:.1f} = {d['n_effective']:.1f} effective + {d['prior_trials']} prior "
          f"+ {d['unknown_specs']} unknown)")


def main(argv=None, *, domain_name: str | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    if domain_name is None:
        ap.add_argument("domain", choices=sorted(DOMAINS))
    ap.add_argument("--snapshot", required=True, help="DS sha (docs/research/data/DS-<sha>.csv.gz)")
    ap.add_argument("--panel", help="CEFNAV sha, for domains that decide from a NAV panel")
    ap.add_argument("--grid", default="v1", help="which frozen grid to run")
    ap.add_argument("--acknowledge-live", nargs="*", default=[], metavar="H",
                    help="live registered hypotheses in the family this run is allowed to cost")
    ap.add_argument("--report-only", action="store_true", help="do not run trials; report the ledger")
    ap.add_argument("--cost-stress", type=float, metavar="M",
                    help="also run (counted) the benchmark and the grid at M x costs and report them")
    ap.add_argument("--json", help="also write the report as JSON to this path")
    args = ap.parse_args(argv)
    domain = DOMAINS[domain_name or args.domain]
    data = {"snapshot": args.snapshot}
    if args.panel:
        data["nav_panel"] = args.panel
    ctx = domain.load(data)
    if not args.report_only:
        if args.grid not in domain.grids():
            raise SystemExit(f"unknown grid {args.grid!r}; {domain.name} has {sorted(domain.grids())}")
        refuse_unacknowledged(family_name(domain.name), args.acknowledge_live)
        ref_id, run_id = run(domain, ctx, args.grid)
        print(f"ledger: benchmark {ref_id or '(already recorded)'}, search {run_id}")
    rep = report(domain, ctx)
    print_report(rep)
    if args.cost_stress:
        if args.report_only:
            raise SystemExit("--cost-stress runs trials; it cannot be combined with --report-only")
        rep["cost_stress"] = {"multiple": args.cost_stress,
                              "points": stress(domain, ctx, args.grid, multiple=args.cost_stress)}
        for lab, v in rep["cost_stress"]["points"].items():
            print(f"  cost x{args.cost_stress:g}: {lab[:58]:58} active Sharpe {v['active_sharpe']:+.2f} "
                  f"({v['active_ann']:+.2%}/yr)")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
