#!/usr/bin/env python3
"""
prereg — freeze what a hypothesis claims before its evidence exists.

Writes ONLY docs/research/prereg/<H>.json, once. Dry-run by default (prints the record it
would write); pass --commit to write. Never git add/commit/push. See
src/research/prereg.py for the schema, the floors no registration may go below, and why
a changed spec is a new, refining hypothesis rather than an edit.

  venv/bin/python tools/prereg.py template > /tmp/H97.json      # a spec skeleton to fill in
  venv/bin/python tools/prereg.py register /tmp/H97.json [--commit]
  venv/bin/python tools/prereg.py show H97
  venv/bin/python tools/prereg.py verify [--against origin/development]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from src.research import prereg  # noqa: E402

TEMPLATE = {
    "hypothesis": "H<n>",
    "family": "long_only_rsi_vwap_mr_hourly:<TICKER>",
    "claim": "What is claimed, in one or two sentences, including the direction and the instrument.",
    "profile": "price_strategy",
    "universe": ["<TICKER>"],
    "development_window": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
    "metric": "deflated_sharpe",
    "threshold": prereg.MIN_THRESHOLD,
    "min_trades": prereg.MIN_TRADES_FLOOR,
    "holdout": {"kind": "forward_paper", "min_days": 90, "min_trades": 30, "min_psr": 0.8},
    "cost_model": {"round_trip_cost_pct": "instrument-derived (sweep_costs.round_trip_cost_pct)"},
    # The frozen candidate the admission gate re-runs: exactly these five keys.
    "params": {"target_gain_pct": 0.01, "stop_loss_pct": 0.005, "rsi_oversold": 35,
               "vwap_zscore_thresh": -1.0, "max_trade_bars": 8},
}


def cmd_template(args) -> int:
    print(json.dumps(TEMPLATE, indent=2))
    return 0


def cmd_register(args) -> int:
    with open(args.spec, encoding="utf-8") as fh:
        spec = json.load(fh)
    errs = prereg.validate(spec)
    if errs:
        for e in errs:
            print(f"REFUSED: {e}")
        return 1
    if not args.commit:
        print("DRY RUN (nothing written). Would register:")
        print(json.dumps(spec, indent=2, sort_keys=True))
        print("\nRe-run with --commit to freeze it. It can never be edited afterwards.")
        return 0
    try:
        path, h = prereg.register(spec)
    except prereg.PreregError as exc:
        print(f"REFUSED: {exc}")
        return 1
    print(f"registered {spec['hypothesis']} -> {os.path.relpath(path, REPO)}\nspec_hash {h}")
    return 0


def cmd_show(args) -> int:
    try:
        record, h = prereg.load(args.hypothesis)
    except prereg.PreregError as exc:
        print(f"REFUSED: {exc}")
        return 1
    print(json.dumps(record, indent=2, sort_keys=True))
    print(f"spec_hash {h}")
    return 0


def cmd_verify(args) -> int:
    problems = []
    for path in sorted(prereg.PREREG_DIR.glob("*.json")) if prereg.PREREG_DIR.is_dir() else []:
        try:
            prereg.load(path.stem)
        except prereg.PreregError as exc:
            problems.append(str(exc))
    if args.against:
        problems += prereg.verify_history(args.against)
    for p in problems:
        print(f"FAIL {p}")
    print(f"{len(problems)} problem(s)")
    return 1 if problems else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("template", help="print a spec skeleton").set_defaults(fn=cmd_template)
    r = sub.add_parser("register", help="freeze a spec (dry-run unless --commit)")
    r.add_argument("spec")
    r.add_argument("--commit", action="store_true")
    r.set_defaults(fn=cmd_register)
    s = sub.add_parser("show", help="print a registration and its hash")
    s.add_argument("hypothesis")
    s.set_defaults(fn=cmd_show)
    v = sub.add_parser("verify", help="every registration loads; --against: none edited or deleted")
    v.add_argument("--against", metavar="REF")
    v.set_defaults(fn=cmd_verify)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
