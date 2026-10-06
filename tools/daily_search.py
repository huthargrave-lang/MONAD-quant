"""
daily_search — run the frozen daily-strategy grid (src/research/daily_classes.grid) through
the counted evaluator, and judge it against the static 60/40, relatively.

Every grid point is one trial in family ``daily_alloc.v1``; the static 60/40 reference is
one trial in ``daily_alloc_reference.v1``. All are scored on the SAME sessions: the first
session at which every asset any point uses has a full warm-up, through the snapshot's end.

The report reads the ledger afterwards, so what it prints is what was recorded:

  * per point: excess-over-cash Sharpe, CAGR, max drawdown, turnover, and the ACTIVE
    Sharpe over the reference (whole window and per era);
  * look-ahead: truncation invariance at 12 cuts (pure signal code, not a trial);
  * familywise: Hansen's SPA over all 27 active series at mean blocks 20/63/126;
  * the best point's DSR on its active series, N = effective trials + declared prior.

  venv/bin/python tools/daily_search.py --snapshot <sha>            # run the v1 grid + report
  venv/bin/python tools/daily_search.py --snapshot <sha> --grid events
  venv/bin/python tools/daily_search.py --snapshot <sha> --report-only
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
from src.research import daily_classes as dc  # noqa: E402
from src.research import daily_data, trials  # noqa: E402
from src.research.backtest_trials import family_members  # noqa: E402
from src.research.daily_strategy import evaluate_daily  # noqa: E402
from src.research.daily_trials import (DAILY_FAMILY, REFERENCE_FAMILY, daily_data_spec,  # noqa: E402
                                       daily_spec, record_daily, stored_returns)

#: The search this family's hypotheses were drawn from, beyond what the ledger can see,
#: declared before any run (2026-10-05) and added to N by every deflation:
#:   * the D6 product-side arc tested ~15 static and overlay builds against the same 60/40
#:     bar (F34-F49: blends, ballast, TIPS, gold, income ETFs, vol-targeting, risk parity);
#:   * the five rules here are famous BECAUSE they worked in published samples: each is
#:     counted as the survivor of 3 published variants (15).
#:   * 2026-10-05, before the event grid ran: its two rules (pre-FOMC drift, sell-in-May)
#:     are famous survivors too, 3 variants each (+6). The constant only ever grows, and
#:     every deflation in the family uses the current value, so earlier hypotheses are
#:     judged against the larger search as well.
PRIOR_SEARCH_TRIALS = 36


def scoring_window(snap) -> tuple[pd.Timestamp, pd.Timestamp]:
    """One window for every grid, so every family member's active series covers the same
    sessions (the familywise test requires it)."""
    assets = sorted({a for g in dc.GRIDS.values() for p in g() for a in dc.assets_used(p)}
                    | set(dc.assets_used(dc.REFERENCE)))
    return daily_data.common_start(snap, assets, dc.WARMUP_SESSIONS), snap.dates[-1]


def _has_reference(snap, start, end) -> bool:
    return bool(_latest(family_members(trials.iter_trials(), REFERENCE_FAMILY), snap.sha, start, end))


def run_search(snap, grid_name: str) -> tuple[str | None, str]:
    """Run one frozen grid. The reference is recorded once per snapshot and window."""
    start, end = scoring_window(snap)
    rets = snap.returns()
    data = daily_data_spec(snap.sha, start, end)
    ref_id = None
    if not _has_reference(snap, start, end):
        with trials.open_run(producer="tools/daily_search.py", family=REFERENCE_FAMILY,
                             context={"snapshot": snap.sha, "role": "reference"}) as ref_run:
            t = ref_run.begin(params=daily_spec(dc.REFERENCE), data=data)
            result = evaluate_daily(dc.decide(snap, dc.REFERENCE, rets), snap, start=start,
                                    end=end, rets=rets)
            record_daily(t, result)
        ref_id = ref_run.run_id
    points = dc.GRIDS[grid_name]()
    with trials.open_run(producer="tools/daily_search.py", family=DAILY_FAMILY,
                         context={"snapshot": snap.sha, "grid": grid_name, "grid_size": len(points),
                                  "prior_search_trials": PRIOR_SEARCH_TRIALS}) as run:
        for point in points:
            t = run.begin(params=daily_spec(point), data=data)
            try:
                tranches = dc.decide(snap, point, rets)
                result = evaluate_daily(tranches, snap, start=start, end=end, rets=rets)
            except Exception as exc:  # noqa: BLE001 — counted as an error, then reported
                t.fail(f"{type(exc).__name__}: {exc}")
                continue
            record_daily(t, result)
    return ref_id, run.run_id


def _latest(records, snap_sha, start, end, *, cost_multiple=1.0, panel_sha=None):
    """{label: record} for the latest ok trial of each (class, params) on this window
    (and NAV panel, for domains that decide from one)."""
    out = {}
    for r in records:
        d = r.spec.get("data") or {}
        p = r.spec.get("params") or {}
        if (r.status == "ok" and d.get("snapshot") == snap_sha
                and d.get("nav_panel") == panel_sha
                and d.get("start") == start.date().isoformat()
                and d.get("end") == end.date().isoformat()
                and p.get("cost_multiple") == cost_multiple):
            out[label(p)] = r
    return out


def label(params) -> str:
    return f"{params['class']} " + json.dumps(params["params"], sort_keys=True, separators=(",", ":"))


def report(snap) -> dict:
    start, end = scoring_window(snap)
    everything = trials.iter_trials()
    fam = _latest(family_members(everything, DAILY_FAMILY), snap.sha, start, end)
    ref = _latest(family_members(everything, REFERENCE_FAMILY), snap.sha, start, end)
    if len(ref) != 1:
        raise SystemExit(f"expected one reference trial on this window, found {len(ref)}")
    (ref_rec,) = ref.values()
    series = trials.load_returns(list(fam.values()) + [ref_rec])
    ref_r = stored_returns(series[ref_rec.key])
    active = {}
    rows = []
    for lab, rec in sorted(fam.items()):
        r = stored_returns(series[rec.key])
        a = stats.active_series(r, ref_r)
        active[lab] = a
        m = rec.metrics or {}
        eras = stats.era_sharpes(a, dc.ERAS)
        rows.append({"label": lab, "key": rec.key, "excess_sharpe": m.get("excess_sharpe"),
                     "cagr": m.get("cagr"), "max_drawdown": m.get("max_drawdown"),
                     "turnover_per_year": m.get("turnover_per_year"),
                     "cost_per_year": m.get("cost_per_year"),
                     "active_sharpe": stats.annualized_sharpe(a),
                     "active_return_ann": float(a.mean() * 252),
                     "era_active_sharpe": [e["active_sharpe"] for e in eras]})
    rows.sort(key=lambda x: -x["active_sharpe"])
    best = rows[0]["label"]
    cuts = stats.default_cuts(snap, start)
    lookahead = {lab: stats.truncation_violations(snap, json_point(lab), cuts) for lab in fam}
    fw = stats.familywise(active, best)
    # Distinct specs that never produced a result count +1 each in N.
    unknown = {r.spec_hash for r in family_members(everything, DAILY_FAMILY) if r.status != "ok"} \
        - {r.spec_hash for r in family_members(everything, DAILY_FAMILY) if r.status == "ok"}
    defl = stats.deflate_active(active, best, calendar=snap.dates,
                                prior_trials=PRIOR_SEARCH_TRIALS, unknown_specs=len(unknown))
    ref_m = ref_rec.metrics or {}
    return {"snapshot": snap.sha, "window": [start.date().isoformat(), end.date().isoformat()],
            "reference": {"key": ref_rec.key, **ref_m}, "rows": rows,
            "lookahead_violations": {k: v for k, v in lookahead.items() if v},
            "best": best, "familywise": fw, "deflation": defl.__dict__}


def json_point(lab: str) -> dict:
    cls, _, params = lab.partition(" ")
    return {"class": cls, "params": json.loads(params)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot", required=True, help="DS sha (docs/research/data/DS-<sha>.csv.gz)")
    ap.add_argument("--grid", choices=sorted(dc.GRIDS), default="v1",
                    help="which frozen grid to run (the report always covers the whole family)")
    ap.add_argument("--report-only", action="store_true", help="do not run trials; report the ledger")
    ap.add_argument("--json", help="also write the report as JSON to this path")
    args = ap.parse_args(argv)
    snap = daily_data.load_snapshot(args.snapshot)
    if not args.report_only:
        ref_id, run_id = run_search(snap, args.grid)
        print(f"ledger: reference {ref_id or '(already recorded)'}, search {run_id}")
    rep = report(snap)
    ref = rep["reference"]
    print(f"\nwindow {rep['window'][0]}..{rep['window'][1]}  snapshot {rep['snapshot'][:12]}")
    print(f"reference static 60/40: excess Sharpe {ref['excess_sharpe']:.2f}  CAGR {ref['cagr']:.2%}  "
          f"maxDD {ref['max_drawdown']:.1%}")
    print(f"\n{'point':58} {'exSh':>5} {'CAGR':>6} {'maxDD':>6} {'cost/y':>6} {'actSh':>6}  eras")
    for r in rep["rows"]:
        eras = " ".join(f"{x:+.2f}" if x is not None else "  n/a" for x in r["era_active_sharpe"])
        print(f"{r['label'][:58]:58} {r['excess_sharpe']:5.2f} {r['cagr']:6.2%} {r['max_drawdown']:6.1%} "
              f"{r['cost_per_year']:6.2%} {r['active_sharpe']:+6.2f}  {eras}")
    print(f"\nlook-ahead violations: {rep['lookahead_violations'] or 'none at 12 cuts'}")
    print(f"best by active Sharpe: {rep['best']}")
    for f in rep["familywise"]:
        print(f"  SPA block {f['mean_block']:>3}: family p={f['spa_pvalue']:.3f}  "
              f"candidate adjusted p={f['candidate_pvalue']:.3f}  (t={f['candidate_t']:+.2f}, "
              f"K={f['family_size']})")
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
