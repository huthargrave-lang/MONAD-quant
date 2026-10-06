#!/usr/bin/env python3
"""
refute — object to a hypothesis, or answer an objection (append-only).

The admission gate (tools/admit.py) BLOCKS a hypothesis with an unanswered objection and
REJECTS one with an upheld objection. Objections and answers must cite checkable
evidence (a ledger run, a file:line, a command). Writes only
docs/research/refutations/<H>.jsonl, by appending. See src/research/refutations.py.

  venv/bin/python tools/refute.py object H97 --by refuter-1 \\
      --claim "entries fill at the signal bar's close" --evidence "engine.py:390"
  venv/bin/python tools/refute.py resolve H97 O1 --outcome refuted --by author \\
      --evidence "next-bar fill verified in tests/test_fill_model.py"
  venv/bin/python tools/refute.py status H97
  venv/bin/python tools/refute.py verify --against origin/development
"""
from __future__ import annotations

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from src.research import refutations  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("object")
    o.add_argument("hypothesis")
    o.add_argument("--claim", required=True)
    o.add_argument("--evidence", required=True)
    o.add_argument("--by", required=True)
    r = sub.add_parser("resolve")
    r.add_argument("hypothesis")
    r.add_argument("objection")
    r.add_argument("--outcome", required=True, choices=refutations.OUTCOMES)
    r.add_argument("--evidence", required=True)
    r.add_argument("--by", required=True)
    s = sub.add_parser("status")
    s.add_argument("hypothesis")
    v = sub.add_parser("verify")
    v.add_argument("--against", metavar="REF", required=True)
    args = ap.parse_args(argv)
    try:
        if args.cmd == "object":
            print(json.dumps(refutations.object_to(args.hypothesis, claim=args.claim,
                                                   evidence=args.evidence, by=args.by)))
        elif args.cmd == "resolve":
            print(json.dumps(refutations.resolve(args.hypothesis, args.objection,
                                                 outcome=args.outcome, evidence=args.evidence,
                                                 by=args.by)))
        elif args.cmd == "status":
            st = refutations.status(args.hypothesis)
            for k in ("open", "upheld", "refuted"):
                for e in st[k]:
                    print(f"{k.upper():8} {e['id']:4} {e['claim']}  [{e['evidence']}]")
            print(f"{len(st['open'])} open, {len(st['upheld'])} upheld, {len(st['refuted'])} refuted")
        else:
            problems = refutations.verify_history(args.against)
            for p in problems:
                print(f"FAIL {p}")
            print(f"{len(problems)} problem(s)")
            return 1 if problems else 0
    except refutations.RefutationError as exc:
        print(f"REFUSED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
