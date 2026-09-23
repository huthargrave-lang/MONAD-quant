#!/usr/bin/env python3
"""
reevaluate_web — work through the findings that predate the accountable workflow.

Sorts every Finding in RESEARCH_WEB.md into a tier (src/research/reeval.py) and records
re-evaluation decisions in an append-only log (docs/research/reeval/decisions.jsonl).
The queue feeds tools/research_backlog.py, so the research loop works it like any other
task. Market claims come first: until one is classified, a performance claim made before
the admission gate existed is standing in the web without having passed it.

  venv/bin/python tools/reevaluate_web.py triage            # counts per tier
  venv/bin/python tools/reevaluate_web.py next              # the next node to re-evaluate
  venv/bin/python tools/reevaluate_web.py decide F14 --class negative_or_method \\
      --action no_action --by agent-1 --evidence "claims the edge VANISHES at hourly; see E23"
  venv/bin/python tools/reevaluate_web.py verify --against origin/development
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from src.research import reeval  # noqa: E402

ADVICE = {
    "market": ("Read the claim. If it asserts a POSITIVE edge, either reproduce it through a "
               "counted producer, register it and run tools/admit.py, or label it "
               "unadmitted_historical. If it denies an edge or is about method, say so."),
    "unverified": ("Locate the evidence and link it (note.py link ... evidenced_by), or narrow "
                   "the claim to what survives and supersede the node."),
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("triage")
    t.add_argument("--json", action="store_true")
    sub.add_parser("next")
    d = sub.add_parser("decide")
    d.add_argument("node")
    d.add_argument("--class", dest="classification", required=True, choices=reeval.CLASSIFICATIONS)
    d.add_argument("--action", required=True, choices=reeval.ACTIONS)
    d.add_argument("--evidence", required=True)
    d.add_argument("--by", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--against", metavar="REF", required=True)
    args = ap.parse_args(argv)

    if args.cmd == "verify":
        problems = reeval.verify_history(args.against)
        for p in problems:
            print(f"FAIL {p}")
        print(f"{len(problems)} problem(s)")
        return 1 if problems else 0
    if args.cmd == "decide":
        try:
            row = reeval.decide(args.node, classification=args.classification, action=args.action,
                                evidence=args.evidence, by=args.by)
        except reeval.ReevalError as exc:
            print(f"REFUSED: {exc}")
            return 1
        print(json.dumps(row))
        return 0

    tiers = reeval.classify()
    q = reeval.queue(tiers)
    if args.cmd == "next":
        if not q:
            print("QUEUE EMPTY: every current Finding is settled, decided, guarded or traceable.")
            return 0
        print(f"{q[0]}  [{tiers[q[0]]}]  {len(q)} queued\n{ADVICE[tiers[q[0]]]}")
        return 0
    counts = collections.Counter(tiers.values())
    if args.json:
        print(json.dumps({"counts": counts, "queue": q, "tiers": tiers}, indent=2, sort_keys=True))
        return 0
    for tier in reeval.TIERS:
        print(f"{tier:<11} {counts.get(tier, 0):>4}")
    print(f"\nqueue: {len(q)} ({counts.get('market', 0)} market claims first, then "
          f"{counts.get('unverified', 0)} unverified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
