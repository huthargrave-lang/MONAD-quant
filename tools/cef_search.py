"""
cef_search — run the frozen closed-end-fund discount grid (src/research/cef_classes.grid)
through the counted evaluator, and judge it against the equal-weight CEF universe.

Domain ``cef_discount``: every grid point is one trial in ``cef_discount.v1``; the
equal-weight benchmark is one trial in ``cef_discount_reference.v1``. Every trial names
both frozen datasets (the daily price snapshot and the weekly NAV panel) and is scored on
the same sessions: from the first with ``cef_classes.MIN_ELIGIBLE_FOR_WINDOW`` eligible
funds, through the snapshot's end. Funds trade at the CEF cost tier, at the close.

The report reads the ledger afterwards: per point, excess-over-cash Sharpe, CAGR, max
drawdown, and the ACTIVE Sharpe over the benchmark (whole window and per era); the look-
ahead check with both datasets erased after each cut; Hansen's SPA over the family; and the
best point's active DSR, N = effective trials + ``PRIOR_SEARCH_TRIALS``.

  venv/bin/python tools/cef_search.py --snapshot <DS sha> --panel <CEFNAV sha>
  venv/bin/python tools/cef_search.py --snapshot <DS sha> --panel <CEFNAV sha> --report-only
"""
from __future__ import annotations

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from daily_search import _latest, json_point  # noqa: E402

from src.research import allocation_stats as stats  # noqa: E402
from src.research import cef_classes as cc  # noqa: E402
from src.research import cef_data, daily_data, trials  # noqa: E402
from src.research.backtest_trials import family_members  # noqa: E402
from src.research.daily_classes import ERAS  # noqa: E402
from src.research.daily_strategy import evaluate_daily  # noqa: E402
from src.research.daily_trials import (CEF_FAMILY, CEF_REFERENCE_FAMILY, daily_data_spec,  # noqa: E402
                                       daily_spec, record_daily, stored_returns)

DOMAIN = "cef_discount"
#: Declared 2026-10-05, before any CEF trial ran: discount mean reversion is a published
#: anomaly (Thompson 1978, Pontiff 1995) with many practitioner variants (counted as the
#: survivor of 3), plus this repo's own descriptive pilot (F257, 1).
#: 2026-10-06, before the tax-loss grid ran: the CEF January effect is published too (+3).
#: The constant only grows; every deflation in the family uses the current value.
PRIOR_SEARCH_TRIALS = 7


def window(snap, panel):
    from src.research.daily_domains import CEF, Context
    return CEF.window(Context(snap=snap, panel=panel))


def run_search(snap, panel, grid_name: str = "v1") -> tuple[str | None, str]:
    start, end = window(snap, panel)
    rets = snap.returns()
    tiers = cc.tiers(snap, panel)
    data = daily_data_spec(snap.sha, start, end, panel_sha=panel.sha)
    ref_id = None
    existing = _latest(family_members(trials.iter_trials(), CEF_REFERENCE_FAMILY), snap.sha,
                       start, end, panel_sha=panel.sha)
    if not existing:
        with trials.open_run(producer="tools/cef_search.py", family=CEF_REFERENCE_FAMILY,
                             context={"snapshot": snap.sha, "nav_panel": panel.sha,
                                      "role": "reference"}) as ref_run:
            t = ref_run.begin(params=daily_spec(cc.REFERENCE, domain=DOMAIN), data=data)
            result = evaluate_daily(cc.decide(snap, panel, cc.REFERENCE), snap, start=start,
                                    end=end, rets=rets, tiers=tiers)
            record_daily(t, result)
        ref_id = ref_run.run_id
    points = cc.GRIDS[grid_name]()
    dupes = stats.duplicate_points({json.dumps(p, sort_keys=True): cc.decide(snap, panel, p)
                                    for p in points})
    if dupes:
        raise SystemExit(f"refusing to run: grid points with identical orders: {dupes}")
    with trials.open_run(producer="tools/cef_search.py", family=CEF_FAMILY,
                         context={"snapshot": snap.sha, "nav_panel": panel.sha,
                                  "grid": grid_name, "grid_size": len(points),
                                  "prior_search_trials": PRIOR_SEARCH_TRIALS}) as run:
        for point in points:
            t = run.begin(params=daily_spec(point, domain=DOMAIN), data=data)
            try:
                tranches = cc.decide(snap, panel, point)
                result = evaluate_daily(tranches, snap, start=start, end=end, rets=rets, tiers=tiers)
            except Exception as exc:  # noqa: BLE001 — counted as an error, then reported
                t.fail(f"{type(exc).__name__}: {exc}")
                continue
            record_daily(t, result)
    return ref_id, run.run_id


def report(snap, panel) -> dict:
    start, end = window(snap, panel)
    everything = trials.iter_trials()
    fam = _latest(family_members(everything, CEF_FAMILY), snap.sha, start, end, panel_sha=panel.sha)
    ref = _latest(family_members(everything, CEF_REFERENCE_FAMILY), snap.sha, start, end,
                  panel_sha=panel.sha)
    if len(ref) != 1 or not fam:
        raise SystemExit(f"need one benchmark and the grid on this window (found {len(ref)}, {len(fam)})")
    (ref_rec,) = ref.values()
    series = trials.load_returns(list(fam.values()) + [ref_rec])
    ref_r = stored_returns(series[ref_rec.key])
    active, rows = {}, []
    for lab, rec in sorted(fam.items()):
        a = stats.active_series(stored_returns(series[rec.key]), ref_r)
        active[lab] = a
        m = rec.metrics or {}
        rows.append({"label": lab, "key": rec.key, "excess_sharpe": m.get("excess_sharpe"),
                     "cagr": m.get("cagr"), "max_drawdown": m.get("max_drawdown"),
                     "turnover_per_year": m.get("turnover_per_year"),
                     "cost_per_year": m.get("cost_per_year"),
                     "active_sharpe": stats.annualized_sharpe(a),
                     "active_return_ann": float(a.mean() * 252),
                     "era_active_sharpe": [e["active_sharpe"] for e in stats.era_sharpes(a, ERAS)]})
    rows.sort(key=lambda x: -x["active_sharpe"])
    best = rows[0]["label"]
    cuts = stats.default_cuts(snap, start)
    lookahead = {lab: cc.truncation_violations(snap, panel, json_point(lab), cuts) for lab in fam}
    fw = stats.familywise(active, best)
    members = family_members(everything, CEF_FAMILY)
    unknown = ({r.spec_hash for r in members if r.status != "ok"}
               - {r.spec_hash for r in members if r.status == "ok"})
    defl = stats.deflate_active(active, best, calendar=snap.dates,
                                prior_trials=PRIOR_SEARCH_TRIALS, unknown_specs=len(unknown))
    counts = cc.eligible_counts(snap, panel).loc[start:end]
    return {"snapshot": snap.sha, "nav_panel": panel.sha,
            "window": [start.date().isoformat(), end.date().isoformat()],
            "eligible_funds": {"min": int(counts.min()), "median": int(counts.median()),
                               "max": int(counts.max())},
            "benchmark": {"key": ref_rec.key, **(ref_rec.metrics or {})}, "rows": rows,
            "lookahead_violations": {k: v for k, v in lookahead.items() if v},
            "best": best, "familywise": fw, "deflation": defl.__dict__}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--panel", required=True)
    ap.add_argument("--grid", choices=sorted(cc.GRIDS), default="v1",
                    help="which frozen grid to run (the report always covers the whole family)")
    ap.add_argument("--acknowledge-live", nargs="*", default=[], metavar="H",
                    help="live registered hypotheses in the family this run is allowed to cost")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    snap = daily_data.load_snapshot(args.snapshot)
    panel = cef_data.load_panel(args.panel)
    if not args.report_only:
        from src.research.daily_trials import refuse_unacknowledged
        refuse_unacknowledged(CEF_FAMILY, args.acknowledge_live)
        ref_id, run_id = run_search(snap, panel, args.grid)
        print(f"ledger: benchmark {ref_id or '(already recorded)'}, search {run_id}")
    rep = report(snap, panel)
    b = rep["benchmark"]
    e = rep["eligible_funds"]
    print(f"\nwindow {rep['window'][0]}..{rep['window'][1]}  eligible funds {e['min']}-{e['max']} "
          f"(median {e['median']})")
    print(f"benchmark equal-weight CEFs: excess Sharpe {b['excess_sharpe']:.2f}  CAGR {b['cagr']:.2%}  "
          f"maxDD {b['max_drawdown']:.1%}  cost/y {b['cost_per_year']:.2%}")
    print(f"\n{'point':48} {'exSh':>5} {'CAGR':>6} {'maxDD':>6} {'cost/y':>6} {'actSh':>6}  eras")
    for r in rep["rows"]:
        eras = " ".join(f"{x:+.2f}" if x is not None else "  n/a" for x in r["era_active_sharpe"])
        print(f"{r['label'][:48]:48} {r['excess_sharpe']:5.2f} {r['cagr']:6.2%} {r['max_drawdown']:6.1%} "
              f"{r['cost_per_year']:6.2%} {r['active_sharpe']:+6.2f}  {eras}")
    print(f"\nlook-ahead violations: {rep['lookahead_violations'] or 'none at 12 cuts'}")
    print(f"best by active Sharpe: {rep['best']}")
    for f in rep["familywise"]:
        print(f"  SPA block {f['mean_block']:>3}: family p={f['spa_pvalue']:.3f}  candidate adjusted "
              f"p={f['candidate_pvalue']:.3f}  (t={f['candidate_t']:+.2f}, K={f['family_size']})")
    d = rep["deflation"]
    print(f"  active DSR {d['dsr']:.4f}  (active Sharpe {d['sharpe_ann']:+.2f} vs SR0 {d['sr0_ann']:.2f}; "
          f"N {d['n_trials']:.1f} = {d['n_effective']:.1f} effective + {d['prior_trials']} prior "
          f"+ {d['unknown_specs']} unknown)")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
