#!/usr/bin/env python3
"""
edge_scorecard — how the edge hunt is going, from the records alone.

Read-only. Joins the four accountability stores into one table per registered
hypothesis, plus totals:

  trial ledger       docs/research/trials/       (tools/trial_ledger.py)
  registrations      docs/research/prereg/       (tools/prereg.py)
  refutations        docs/research/refutations/  (tools/refute.py)
  verdicts           docs/research/verdicts/     (tools/admit.py)

The numbers that hold claim-making to account: how many hypotheses were registered,
how many the gate admitted, how many objections were upheld, and how many trials the
search spent per admission. A loop that registers many hypotheses and admits none is
working; one that admits many from little search is the thing to look at.

  venv/bin/python tools/edge_scorecard.py [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd  # noqa: E402

from src.research import prereg, refutations, trials  # noqa: E402
from src.research.backtest_trials import family_members  # noqa: E402
import admit  # noqa: E402


def latest_verdict(hypothesis: str, verdict_dir=None, prereg_dir=None) -> dict | None:
    """The newest verdict record that VERIFIES (admit.verify_record). A record that does
    not is reported as INVALID RECORD rather than silently skipped or trusted."""
    base = (verdict_dir if verdict_dir is not None else admit.VERDICT_DIR) / hypothesis
    files = sorted(base.glob("*.json")) if base.is_dir() else []
    if not files:
        return None
    record = json.loads(files[-1].read_text(encoding="utf-8"))
    problems = admit.verify_record(record, prereg_dir=prereg_dir)
    if problems:
        return {**record, "verdict": "INVALID RECORD", "problems": problems}
    return record


def scorecard(*, prereg_dir=None, refutations_dir=None, verdict_dir=None) -> dict:
    """The joined view. Raises if the ledger is invalid (a scorecard over tampered
    evidence would be worse than none)."""
    records = trials.iter_trials()
    by_family = Counter(r.family for r in records)
    pdir = prereg_dir if prereg_dir is not None else prereg.PREREG_DIR
    rows = []
    for path in sorted(pdir.glob("H*.json")) if pdir.is_dir() else []:
        spec, _ = prereg.load(path.stem, prereg_dir=pdir)
        cutoff = pd.Timestamp(spec["registered_at"])
        searched = sum(1 for r in family_members(records, spec["family"])
                       if pd.Timestamp(r.opened_at) < cutoff)
        ref = refutations.status(spec["hypothesis"], refutations_dir)
        v = latest_verdict(spec["hypothesis"], verdict_dir, pdir)
        rows.append({"hypothesis": spec["hypothesis"], "family": spec["family"],
                     "registered_at": spec["registered_at"],
                     "trials_before_registration": searched,
                     "objections": {k: len(ref[k]) for k in ("open", "upheld", "refuted")},
                     "verdict": v["verdict"] if v else "NOT EVALUATED",
                     "verdict_at": v["evaluated_at"] if v else None})
    verdicts = Counter(r["verdict"] for r in rows)
    admitted = verdicts.get(admit.ADMIT, 0)
    return {
        "hypotheses": rows,
        "totals": {
            "trials_recorded": len(records),
            "families": dict(by_family),
            "registered": len(rows),
            "verdicts": dict(verdicts),
            "admitted": admitted,
            "objections_upheld": sum(r["objections"]["upheld"] for r in rows),
            "objections_open": sum(r["objections"]["open"] for r in rows),
            "trials_per_admission": (len(records) / admitted) if admitted else None,
        },
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        card = scorecard()
    except trials.LedgerError as exc:
        print(f"REFUSED: the ledger is invalid, so no scorecard: {exc}")
        return 1
    if args.json:
        print(json.dumps(card, indent=2, sort_keys=True))
        return 0
    t = card["totals"]
    print(f"trials recorded      {t['trials_recorded']} across {len(t['families'])} famil"
          f"{'y' if len(t['families']) == 1 else 'ies'}")
    print(f"hypotheses           {t['registered']} registered, {t['admitted']} admitted "
          f"{dict(t['verdicts']) or ''}")
    print(f"objections           {t['objections_open']} open, {t['objections_upheld']} upheld")
    tpa = t["trials_per_admission"]
    print(f"trials per admission {tpa:.0f}" if tpa else "trials per admission (none admitted)")
    for r in card["hypotheses"]:
        o = r["objections"]
        print(f"  {r['hypothesis']:<7} {r['verdict']:<14} searched {r['trials_before_registration']:>5}  "
              f"objections {o['open']}/{o['upheld']}/{o['refuted']} (open/upheld/refuted)  {r['family']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
