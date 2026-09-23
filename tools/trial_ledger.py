#!/usr/bin/env python3
"""
trial_ledger — inspect, verify and repair the append-only trial ledger.

The ledger itself (``docs/research/trials/``) is written only by
``src/research/trials.py``; this CLI never writes a trial. It reads, and its one
mutating command (``seal``) closes a run whose process died, under the rules in
``trials.seal``.

  venv/bin/python tools/trial_ledger.py stats                  # trials per family
  venv/bin/python tools/trial_ledger.py verify                 # every shard's invariants
  venv/bin/python tools/trial_ledger.py verify --require-closed --against origin/development
  venv/bin/python tools/trial_ledger.py show TR-20260922T170000Z-ab12cd34
  venv/bin/python tools/trial_ledger.py deflate 'TR-20260922T170000Z-ab12cd34#17'
  venv/bin/python tools/trial_ledger.py seal TR-20260922T170000Z-ab12cd34

``verify`` exits 1 on any violation, so CI can gate on it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from src.research import trials  # noqa: E402


def _resolve(run: str):
    name = run if run.endswith(".jsonl") else f"{run}.jsonl"
    path = trials.LEDGER_DIR / os.path.basename(name)
    if not path.is_file():
        sys.exit(f"no such run: {path}")
    return path


def cmd_stats(args) -> int:
    counts = trials.family_counts()
    if args.json:
        print(json.dumps(counts, indent=2, sort_keys=True))
        return 0
    if not counts:
        print("ledger is empty")
        return 0
    cols = ("runs", "intents", "ok", "error", "abandoned", "orphans", "invalid_runs")
    width = max(len(f) for f in counts)
    print(f"{'family':<{width}}  " + "  ".join(f"{c:>9}" for c in cols))
    for fam in sorted(counts):
        print(f"{fam:<{width}}  " + "  ".join(f"{counts[fam].get(c, 0):>9}" for c in cols))
    print("\nintents = trials attempted (errors, abandonments and crash orphans included).")
    return 0


def cmd_verify(args) -> int:
    reports = trials.verify_ledger(require_closed=args.require_closed)
    bad = [r for r in reports if not r.ok]
    for r in bad:
        for e in r.errors:
            print(f"FAIL {r.path.name}: {e}")
    history = []
    if args.against:
        history = trials.verify_append_only(args.against)
        for p in history:
            print(f"FAIL history: {p}")
    print(f"{len(reports)} shard(s) checked, {len(bad)} invalid"
          + (f"; append-only vs {args.against}: {len(history)} violation(s)" if args.against else ""))
    return 1 if bad or history else 0


def cmd_show(args) -> int:
    r = trials.verify_shard(_resolve(args.run))
    print(f"run        {r.run_id}\nfamily     {r.family}\nhypothesis {r.hypothesis}")
    print(f"closed     {r.closed} ({r.close_status})\nintents    {r.intents}")
    print(f"outcomes   {json.dumps(r.outcomes, sort_keys=True)}\norphans    {r.orphans}")
    for e in r.errors:
        print(f"FAIL       {e}")
    return 0 if r.ok else 1


def cmd_deflate(args) -> int:
    from src.research.deflation import deflate_candidate
    try:
        d = deflate_candidate(args.candidate)
    except (ValueError, trials.LedgerError) as exc:
        print(f"REFUSED: {exc}")
        return 1
    e, r, m = d.effective, d.result, d.moments
    print(f"candidate   {d.candidate}\nfamily      {d.family}")
    print(f"trials      {d.trials_recorded} recorded, {d.trials_with_returns} with returns, "
          f"{e.n_distinct} distinct")
    print(f"effective N {d.n_trials:.2f}  (clusters {e.n_clusters}, Li-Ji {e.n_li_ji:.2f}, "
          f"+{d.unknown_specs_added} unknown-result specs)")
    print(f"Sharpe      {d.annualized_sharpe:+.3f} annualized over {m.n_obs} days "
          f"(skew {m.skew:+.2f}, kurtosis {m.kurtosis:.2f})")
    print(f"SR0         {d.annualized_sr0:+.3f} annualized: what the best of {d.n_trials:.1f} "
          f"zero-edge tries is expected to show")
    print(f"DSR         {r.dsr:.4f}  = P(true Sharpe > SR0)")
    return 0


def cmd_seal(args) -> int:
    try:
        print(trials.seal(_resolve(args.run)))
    except trials.LedgerError as exc:
        print(f"REFUSED: {exc}")
        return 1
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stats", help="trials attempted per family")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_stats)
    v = sub.add_parser("verify", help="check shard invariants (and history with --against)")
    v.add_argument("--require-closed", action="store_true",
                   help="an unclosed run is a violation (use in CI: committed runs must be closed)")
    v.add_argument("--against", metavar="REF",
                   help="also check nothing present at merge-base(HEAD, REF) was edited or removed")
    v.set_defaults(fn=cmd_verify)
    sh = sub.add_parser("show", help="summarise one run")
    sh.add_argument("run")
    sh.set_defaults(fn=cmd_show)
    de = sub.add_parser("deflate", help="Deflated Sharpe of one trial against its whole family")
    de.add_argument("candidate", help="<run_id>#<trial>")
    de.set_defaults(fn=cmd_deflate)
    se = sub.add_parser("seal", help="close a run whose process died")
    se.add_argument("run")
    se.set_defaults(fn=cmd_seal)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
