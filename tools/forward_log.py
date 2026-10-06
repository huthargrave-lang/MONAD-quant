"""
forward_log — a timestamped, append-only record of what a registered CEF hypothesis
would hold, taken during its forward window.

The admission gate scores a forward window by re-fetching data when it matures. A record
made AT THE TIME (what the rule said, on which data, committed to git) is stronger evidence:
it cannot be revised by later data corrections, and git's history shows it was not written
after the fact. Each run fetches today's NAV panel and prices (written locally as frozen
files; not committed by this tool), computes the hypothesis's current holdings with the
registered rule, and appends one canonical JSON line to
``docs/research/forward/<H>.jsonl``: the as-of session, the data shas, and the weights.

Read-only with respect to strategy evaluation: no trial is recorded (``cef_picks``
computes selections; nothing is backtested). Run it weekly after Friday's NAVs publish.

  venv/bin/python tools/forward_log.py H404702
  venv/bin/python tools/forward_log.py H404702 --verify      # the log only grows, in order
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cef_picks  # noqa: E402

from src.research import prereg  # noqa: E402
from src.research.trials import canonical_json  # noqa: E402

LOG_DIR = Path(REPO) / "docs/research/forward"


def log_path(hypothesis: str) -> Path:
    return LOG_DIR / f"{hypothesis}.jsonl"


def entry(hypothesis: str, ctx, candidate: dict, spec_hash: str) -> dict:
    h = cef_picks.current_holdings(ctx, candidate)
    return {"hypothesis": hypothesis, "spec_hash": spec_hash,
            "recorded_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "as_of_session": ctx.snap.dates[-1].date().isoformat(),
            "data": {"snapshot": ctx.snap.sha, "nav_panel": ctx.panel.sha},
            "weights": {f: round(float(w), 8) for f, w in h["weight"].items()}}


def append(hypothesis: str, row: dict) -> Path:
    path = log_path(hypothesis)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = read(hypothesis)
    if rows and rows[-1]["as_of_session"] >= row["as_of_session"]:
        raise SystemExit(f"{hypothesis}: already logged as of {rows[-1]['as_of_session']}; "
                         f"the log records each session once, in order")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(canonical_json(row) + "\n")
    return path


def read(hypothesis: str) -> list[dict]:
    path = log_path(hypothesis)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def verify(hypothesis: str) -> list[str]:
    """Problems: sessions out of order or repeated, a changed spec, weights not summing to 1."""
    problems, last = [], None
    spec_hash = prereg.load(hypothesis)[1]
    for i, r in enumerate(read(hypothesis)):
        if last is not None and r["as_of_session"] <= last:
            problems.append(f"line {i + 1}: session {r['as_of_session']} not after {last}")
        if r["spec_hash"] != spec_hash:
            problems.append(f"line {i + 1}: logged against a different registration")
        total = sum(r["weights"].values())
        if abs(total - 1.0) > 1e-6:
            problems.append(f"line {i + 1}: weights sum to {total}")
        last = r["as_of_session"]
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hypothesis")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args(argv)
    if args.verify:
        problems = verify(args.hypothesis)
        for p in problems:
            print(f"FAIL {p}")
        print(f"{len(read(args.hypothesis))} entries, {len(problems)} problem(s)")
        return 1 if problems else 0
    spec, spec_hash = prereg.load(args.hypothesis)
    p = spec.get("params") or {}
    if spec["profile"] != "tactical_allocation" or p.get("domain") != "cef_discount":
        raise SystemExit(f"{args.hypothesis} is not a CEF-domain tactical hypothesis")
    ctx = cef_picks.fresh_context(spec)
    row = entry(args.hypothesis, ctx, p["candidate"], spec_hash)
    path = append(args.hypothesis, row)
    print(f"{args.hypothesis}: logged {len(row['weights'])} holdings as of {row['as_of_session']} "
          f"-> {os.path.relpath(path, REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
