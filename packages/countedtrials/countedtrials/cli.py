"""
countedtrials — inspect, verify and deflate a trial ledger.

  countedtrials stats                          # trials attempted per family
  countedtrials verify                         # every shard's hash chain and invariants
  countedtrials verify --require-closed --against origin/main     # the CI gate
  countedtrials show TR-20260922T170000Z-ab12cd34
  countedtrials report <family>                # SPA verdict, DSR and PBO of the family's best trial
  countedtrials deflate 'TR-20260922T170000Z-ab12cd34#17'
  countedtrials seal TR-20260922T170000Z-ab12cd34                 # close a crashed run

The ledger directory is ``--ledger DIR``, else ``$COUNTEDTRIALS_LEDGER``, else ``./trials``.
``verify`` exits 1 on any violation, so CI can gate on it. This CLI never writes a trial;
its one mutating command is ``seal``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from countedtrials import analysis, ledger


def _resolve(args, run: str):
    name = run if run.endswith(".jsonl") else f"{run}.jsonl"
    path = ledger._dir(args.ledger) / os.path.basename(name)
    if not path.is_file():
        sys.exit(f"no such run: {path}")
    return path


def cmd_stats(args) -> int:
    counts = ledger.family_counts(args.ledger)
    if args.json:
        print(json.dumps(counts, indent=2, sort_keys=True))
        return 0
    if not counts:
        print(f"ledger {ledger._dir(args.ledger)} is empty")
        return 0
    cols = ("runs", "intents", "ok", "error", "abandoned", "orphans", "invalid_runs")
    width = max(len(f) for f in counts)
    print(f"{'family':<{width}}  " + "  ".join(f"{c:>9}" for c in cols))
    for fam in sorted(counts):
        print(f"{fam:<{width}}  " + "  ".join(f"{counts[fam].get(c, 0):>9}" for c in cols))
    print("\nintents = trials attempted (errors, abandonments and crash orphans included).")
    return 0


def cmd_verify(args) -> int:
    reports = ledger.verify_ledger(args.ledger, require_closed=args.require_closed)
    bad = [r for r in reports if not r.ok]
    for r in bad:
        for e in r.errors:
            print(f"FAIL {r.path.name}: {e}")
    history = []
    if args.against:
        history = ledger.verify_append_only(args.against, ledger_dir=args.ledger)
        for p in history:
            print(f"FAIL history: {p}")
    print(f"{len(reports)} shard(s) checked, {len(bad)} invalid"
          + (f"; append-only vs {args.against}: {len(history)} violation(s)" if args.against else ""))
    return 1 if bad or history else 0


def cmd_show(args) -> int:
    r = ledger.verify_shard(_resolve(args, args.run))
    print(f"run        {r.run_id}\nfamily     {r.family}\nhypothesis {r.hypothesis}")
    print(f"closed     {r.closed} ({r.close_status})\nintents    {r.intents}")
    print(f"outcomes   {json.dumps(r.outcomes, sort_keys=True)}\norphans    {r.orphans}")
    for e in r.errors:
        print(f"FAIL       {e}")
    return 0 if r.ok else 1


def cmd_deflate(args) -> int:
    try:
        d = analysis.deflate(args.candidate, ledger_dir=args.ledger,
                             prior_search_trials=args.prior)
    except (ValueError, ledger.LedgerError) as exc:
        print(f"REFUSED: {exc}")
        return 1
    print(analysis.format_deflation(d))
    return 0


def cmd_report(args) -> int:
    try:
        rep = analysis.report(args.family, candidate=args.candidate, ledger_dir=args.ledger,
                              n_boot=args.n_boot, prior_search_trials=args.prior,
                              alpha=args.alpha)
    except (ValueError, ledger.LedgerError) as exc:
        print(f"REFUSED: {exc}")
        return 1
    print(rep)
    return 0


def cmd_seal(args) -> int:
    try:
        print(ledger.seal(_resolve(args, args.run)))
    except ledger.LedgerError as exc:
        print(f"REFUSED: {exc}")
        return 1
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="countedtrials", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ledger", metavar="DIR", default=None,
                    help="ledger directory (default: $COUNTEDTRIALS_LEDGER or ./trials)")
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
    rp = sub.add_parser("report", help="DSR, SPA and PBO of a family's best (or a named) trial")
    rp.add_argument("family")
    rp.add_argument("--candidate", metavar="RUN#TRIAL", default=None)
    rp.add_argument("--n-boot", type=int, default=None, help="bootstrap draws (default: >= 5000)")
    rp.add_argument("--alpha", type=float, default=0.05)
    rp.add_argument("--prior", type=int, default=0, metavar="N",
                    help="attempts made before the ledger existed; charged against the result")
    rp.set_defaults(fn=cmd_report)
    de = sub.add_parser("deflate", help="Deflated Sharpe of one trial against its whole family")
    de.add_argument("candidate", help="<run_id>#<trial>")
    de.add_argument("--prior", type=int, default=0, metavar="N")
    de.set_defaults(fn=cmd_deflate)
    se = sub.add_parser("seal", help="close a run whose process died")
    se.add_argument("run")
    se.set_defaults(fn=cmd_seal)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
