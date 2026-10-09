#!/usr/bin/env python3
"""
forward_watch — keep a frozen, chained, daily paper record of a rule the admission gate
cannot admit (src/research/forward_watch.py; docs/research/MINER_TILT_FORWARD_WATCH.md).

  venv/bin/python tools/forward_watch.py freeze <draft.json>     # once; needs the web node
  venv/bin/python tools/forward_watch.py genesis <ID>            # once: state at the last close
  venv/bin/python tools/forward_watch.py log <ID>                # after each close (catch-up ok)
  venv/bin/python tools/forward_watch.py report <ID>             # anniversaries and the decision
  venv/bin/python tools/forward_watch.py verify [--against origin/development]
  venv/bin/python tools/forward_watch.py void <ID> --reason "..."
  venv/bin/python tools/forward_watch.py attest-evaluator <ID> --reason "..."

``log`` refuses a dirty working tree (each line records the code it ran on), fetches a
private snapshot (observations never committed), and records one counted trial per new
session in family ``forward_watch.<ID>.v1``. The window opens at the first session after
the spec reached the deploy branch; ``log`` writes that ``window_open`` line once it can
see the spec there.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import forward_watch as fw  # noqa: E402
from src.research import trials  # noqa: E402

FORWARD_LOG_DIR = REPO / "docs/research/forward"


def family(watch: str) -> str:
    return f"forward_watch.{watch}.v1"


def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)


def spec_reached(watch: str, base_ref: str) -> pd.Timestamp | None:
    """When the spec first appeared on ``base_ref`` (its adding commit's committer date,
    UTC), or None if it is not there yet."""
    rel = fw.spec_path(watch).relative_to(REPO).as_posix()
    out = _git("log", base_ref, "--diff-filter=A", "--format=%cI", "--", rel)
    stamps = [s for s in out.stdout.split() if s]
    if out.returncode != 0 or not stamps:
        return None
    return pd.Timestamp(stamps[-1]).tz_convert("UTC").tz_localize(None)


def opens_at(watch: str, snap, base_ref: str) -> str | None:
    """The first snapshot session strictly after the spec reached ``base_ref``."""
    reached = spec_reached(watch, base_ref)
    if reached is None:
        return None
    later = snap.dates[snap.dates.normalize() > reached.normalize()]
    return str(later[0].date()) if len(later) else None


def fresh_snapshot(spec: dict):
    end = (pd.Timestamp.today().normalize() + pd.Timedelta(days=1)).date().isoformat()
    return fw.load_snapshot(fw.build_snapshot(spec, end))


def cmd_freeze(args) -> int:
    draft = json.loads(Path(args.draft).read_text(encoding="utf-8"))
    draft = {**draft, "evaluator_sources": list(fw.EVALUATOR_SOURCES),
             "evaluator_sha256": fw.evaluator_sha256()}
    path, h = fw.freeze(draft)
    print(f"frozen {path.relative_to(REPO)} sha256 {h}")
    return 0


def _refuse_dirty():
    state = trials.code_state()
    if state.get("dirty"):
        raise SystemExit("the working tree is dirty: commit first, so every line names the code it ran on")
    return state


def cmd_genesis(args) -> int:
    code = _refuse_dirty()
    spec, _h = fw.load(args.watch)
    snap = fresh_snapshot(spec)
    session = pd.Timestamp(args.session) if args.session else snap.dates[-1]
    with trials.open_run(producer=fw.PRODUCER, family=family(args.watch),
                         context={"watch": args.watch, "role": "genesis"}) as run:
        line = fw.write_genesis(args.watch, snap, session, run=run, code=code)
    print(f"{args.watch}: genesis at {line['session']} (index {line['session_index']}, snapshot {snap.sha[:12]})")
    return 0


def cmd_log(args) -> int:
    code = _refuse_dirty()
    spec, _h = fw.load(args.watch)
    snap = fresh_snapshot(spec)
    start = opens_at(args.watch, snap, args.base_ref)
    with trials.open_run(producer=fw.PRODUCER, family=family(args.watch),
                         context={"watch": args.watch, "role": "forward paper"}) as run:
        written = fw.log_sessions(args.watch, snap, run=run, opens_at=start, code=code)
    kinds = [w["kind"] for w in written]
    print(f"{args.watch}: wrote {len(written)} line(s) {kinds} through {snap.dates[-1].date()}"
          + ("" if start else f" (window not open: the spec is not on {args.base_ref} yet)"))
    return 0


def cmd_report(args) -> int:
    spec, _h = fw.load(args.watch)
    rows = fw.read(args.watch)
    reports = fw.decide(spec, rows)
    sessions = [r for _b, r in rows if r["kind"] == "session"]
    opened = next((r["opens_at_session"] for _b, r in rows if r["kind"] == "window_open"), None)
    print(f"{args.watch}: {len(sessions)} session lines; window opens {opened or '(not yet)'}")
    for rep in reports:
        print(json.dumps(rep, default=float))
    if not reports:
        print("no anniversary reached: nothing to decide")
    return 0


def _history_rule(rel: str):
    if rel.endswith(".jsonl"):
        return "prefix"
    if rel.endswith(".json"):
        return "identical"
    return None


def cmd_verify(args) -> int:
    problems = []
    for spec_file in sorted(fw.WATCH_DIR.glob("*.json")):
        problems += [f"{spec_file.stem}: {p}" for p in fw.verify(spec_file.stem)]
    if args.against:
        problems += trials.verify_history(args.against, fw.WATCH_DIR.relative_to(REPO), rule=_history_rule,
                                          what="forward-watch record")
        problems += trials.verify_history(args.against, FORWARD_LOG_DIR.relative_to(REPO),
                                          rule=lambda rel: "prefix" if rel.endswith(".jsonl") else None,
                                          what="forward log")
    for p in problems:
        print(f"FAIL {p}")
    print(f"forward watches and logs: {len(problems)} problem(s)")
    return 1 if problems else 0


def cmd_void(args) -> int:
    _spec, h = fw.load(args.watch)
    fw.append(args.watch, {"kind": "void", "reason": args.reason}, spec_hash=h)
    print(f"{args.watch}: void ({args.reason})")
    return 0


def cmd_attest(args) -> int:
    """Record an engine change after the watch's tests pass on it (the exact-reproduction
    tests against the recorded series among them)."""
    _refuse_dirty()
    test = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_forward_watch.py"],
                          cwd=REPO, capture_output=True, text=True)
    tail = (test.stdout.strip().splitlines() or [""])[-1]
    if test.returncode != 0:
        raise SystemExit(f"tests/test_forward_watch.py failed ({tail}); the change is not attested")
    _spec, h = fw.load(args.watch)
    fw.append(args.watch, {"kind": "evaluator_change", "evaluator_sha256": fw.evaluator_sha256(),
                           "reason": args.reason, "attested_by_tests": f"tests/test_forward_watch.py: {tail}"},
              spec_hash=h)
    print(f"{args.watch}: evaluator change attested ({tail})")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("freeze")
    p.add_argument("draft")
    p.set_defaults(fn=cmd_freeze)
    p = sub.add_parser("genesis")
    p.add_argument("watch")
    p.add_argument("--session", help="the close to start from (default: the last session fetched)")
    p.set_defaults(fn=cmd_genesis)
    p = sub.add_parser("log")
    p.add_argument("watch")
    p.add_argument("--base-ref", default="origin/development")
    p.set_defaults(fn=cmd_log)
    p = sub.add_parser("report")
    p.add_argument("watch")
    p.set_defaults(fn=cmd_report)
    p = sub.add_parser("verify")
    p.add_argument("--against", help="also check append-only history against this ref (CI)")
    p.set_defaults(fn=cmd_verify)
    p = sub.add_parser("void")
    p.add_argument("watch")
    p.add_argument("--reason", required=True)
    p.set_defaults(fn=cmd_void)
    p = sub.add_parser("attest-evaluator")
    p.add_argument("watch")
    p.add_argument("--reason", required=True)
    p.set_defaults(fn=cmd_attest)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
