#!/usr/bin/env python3
"""
forward_watch — keep a frozen, chained, daily paper record of a rule the admission gate
cannot admit (src/research/forward_watch.py; docs/research/MINER_TILT_FORWARD_WATCH.md).

  venv/bin/python tools/forward_watch.py freeze <draft.json>     # once; needs the web node
  venv/bin/python tools/forward_watch.py genesis <ID>            # once: state at the last close
  venv/bin/python tools/forward_watch.py fetch <ID>              # domain watches: a NAV vintage, daily
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
import os
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


def _git(*args, repo: Path = REPO) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)


def reached(rel: str, base_ref: str, *, repo: Path = REPO) -> pd.Timestamp | None:
    """When ``rel`` reached ``base_ref``: the committer date (UTC) of the FIRST-PARENT
    commit of ``base_ref`` that added it, which is the merge commit when it arrived through
    a merge. A spec's own commit date would open a window retroactively: freeze on a
    branch, log for weeks, merge if pleasing (board, METAL_TRUST_FORWARD_WATCH.md)."""
    out = _git("log", "--first-parent", base_ref, "--diff-filter=A", "--format=%cI", "--", rel, repo=repo)
    stamps = [s for s in out.stdout.split() if s]
    if out.returncode != 0 or not stamps:
        return None
    return pd.Timestamp(stamps[-1]).tz_convert("UTC").tz_localize(None)


def spec_reached(watch: str, base_ref: str) -> pd.Timestamp | None:
    """When the spec reached ``base_ref`` (``reached``), or None if it is not there yet."""
    return reached(fw.spec_path(watch).relative_to(REPO).as_posix(), base_ref)


def opens_at(watch: str, snap, base_ref: str) -> str | None:
    """The first snapshot session strictly after the spec reached ``base_ref``."""
    reached = spec_reached(watch, base_ref)
    if reached is None:
        return None
    later = snap.dates[snap.dates.normalize() > reached.normalize()]
    return str(later[0].date()) if len(later) else None


def fresh_snapshot(spec: dict):
    end = (pd.Timestamp.today().normalize() + pd.Timedelta(days=1)).date().isoformat()
    if fw.is_domain(spec):
        from src.research import daily_data
        # the frozen universe, in its frozen order (the engine's sums depend on it)
        sha = daily_data.build_snapshot(list(spec["snapshot_universe"]), spec["snapshot_start"], end, private=True)
        return daily_data.load_snapshot(sha)
    return fw.load_snapshot(fw.build_snapshot(spec, end))


def fetch_panel(spec: dict):
    """A NAV vintage of the watch's trusts: fetched strictly (a failure or a lost trust
    raises, so nothing is recorded), observations private, manifest committed."""
    from src.research import cef_data
    if not hasattr(cef_data, "data_store"):
        raise SystemExit("this branch's cef_data has no private store (option A, PR #65): a NAV "
                         "vintage would be written to the committed tree; fetch on a branch that has it")
    frames, report = cef_data.build_panel(tickers=list(spec["domain_rule"]["trusts"]), strict=True)
    return cef_data.load_panel(cef_data.write_panel(frames, report))


def cmd_freeze(args) -> int:
    draft = json.loads(Path(args.draft).read_text(encoding="utf-8"))
    sources = list(draft.get("evaluator_sources") or fw.EVALUATOR_SOURCES)
    draft = {**draft, "evaluator_sources": sources, "evaluator_sha256": fw.evaluator_sha256(tuple(sources))}
    path, h = fw.freeze(draft)
    print(f"frozen {path.relative_to(REPO)} sha256 {h}")
    return 0


def _refuse_dirty():
    state = trials.code_state()
    if state.get("dirty"):
        raise SystemExit("the working tree is dirty: commit first, so every line names the code it ran on")
    return state


def cmd_fetch(args) -> int:
    code = _refuse_dirty()
    spec, _h = fw.load(args.watch)
    if not fw.is_domain(spec):
        raise SystemExit(f"{args.watch} reads no NAV vintages")
    panel = fetch_panel(spec)
    line = fw.append_vintage(args.watch, panel, code=code)
    print(f"{args.watch}: vintage {panel.sha[:12]} fetched {line['fetched_at']}")
    return 0


def cmd_genesis(args) -> int:
    code = _refuse_dirty()
    spec, _h = fw.load(args.watch)
    if fw.is_domain(spec):
        return _genesis_domain(args, spec, code)
    snap = fresh_snapshot(spec)
    session = pd.Timestamp(args.session) if args.session else snap.dates[-1]
    with trials.open_run(producer=fw.PRODUCER, family=family(args.watch),
                         context={"watch": args.watch, "role": "genesis"}) as run:
        line = fw.write_genesis(args.watch, snap, session, run=run, code=code)
    print(f"{args.watch}: genesis at {line['session']} (index {line['session_index']}, snapshot {snap.sha[:12]})")
    return 0


def _genesis_domain(args, spec: dict, code) -> int:
    """The domain watch's genesis on its frozen data (exact), the fresh replay reported,
    and the fresh NAV vintage recorded right after it."""
    from src.research import cef_data, daily_data
    snap = daily_data.load_snapshot(spec["genesis_data"]["snapshot"])
    panel = cef_data.load_panel(spec["genesis_data"]["nav_panel"])
    fresh_panel = fetch_panel(spec)
    fresh = (fresh_snapshot(spec), fresh_panel)
    with trials.open_run(producer=fw.PRODUCER, family=family(args.watch),
                         context={"watch": args.watch, "role": "genesis"}) as run:
        line = fw.write_genesis_domain(args.watch, snap, panel, run=run, fresh=fresh, code=code)
    fw.append_vintage(args.watch, fresh_panel, code=code)
    diffs = {n: d["max_abs_diff"] for n, d in line["fresh_replay"]["books"].items()}
    print(f"{args.watch}: genesis at {line['session']} reproduces the recorded books; fresh replay "
          f"max |diff| {diffs}; vintage {fresh_panel.sha[:12]} recorded")
    return 0


def cmd_log(args) -> int:
    code = _refuse_dirty()
    spec, _h = fw.load(args.watch)
    snap = fresh_snapshot(spec)
    start = opens_at(args.watch, snap, args.base_ref)
    with trials.open_run(producer=fw.PRODUCER, family=family(args.watch),
                         context={"watch": args.watch, "role": "forward paper"}) as run:
        if fw.is_domain(spec):
            from src.research import cef_data
            written = fw.log_sessions_domain(args.watch, snap, cef_data.load_panel, run=run,
                                             opens_at=start, code=code)
        else:
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
    ids = fw.watches_ever_frozen()
    print(f"forward-evidence route (docs/research/forward_watch/policy/route.json): m = {len(ids)} "
          f"{ids}; a promoted watch's LLR must reach {fw.route_boundary(spec, len(ids)):.3f}")
    if fw.is_domain(spec) and sessions:
        from src.research import daily_data
        snap = daily_data.load_snapshot(sessions[-1]["data"]["snapshot"])
        print("legs and episodes:", json.dumps(fw.legs_and_episodes(spec, rows, snap), default=float))
        if args.sec:
            filings = []
            for cik in spec["identity"]["sec_cik"].values():
                filings += sec_filings(int(cik))
            print("issuance split:", json.dumps(fw.issuance_split(rows, fw.atm_windows(filings)), default=float))
    return 0


def sec_filings(cik: int) -> list[dict]:
    """Every filing's form and filing date from data.sec.gov submissions (SEC_USER_AGENT)."""
    import time
    from src.research.bdc_text_nav import SUBMISSIONS, _get
    first = json.loads(_get(SUBMISSIONS.format(f"CIK{cik:010d}.json")))
    pages = [first["filings"]["recent"]]
    for f in first["filings"].get("files", []):
        time.sleep(0.2)
        pages.append(json.loads(_get(SUBMISSIONS.format(f["name"]))))
    return [{"form": form, "filed": filed} for p in pages for form, filed in zip(p["form"], p["filingDate"])]


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
    # The exact-reproduction tests need the private store; a skip would attest nothing, so
    # the store is required and any skip refuses (board, METAL_TRUST_FORWARD_WATCH.md).
    env = {**os.environ, "MONAD_REQUIRE_PRIVATE_STORE": "1"}
    test = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rs", "tests/test_forward_watch.py"],
                          cwd=REPO, capture_output=True, text=True, env=env)
    tail = (test.stdout.strip().splitlines() or [""])[-1]
    if test.returncode != 0:
        raise SystemExit(f"tests/test_forward_watch.py failed ({tail}); the change is not attested")
    if "skipped" in tail:
        raise SystemExit(f"tests/test_forward_watch.py skipped tests ({tail}); restore the private "
                         f"store (tools/data_inventory.py import) before attesting")
    spec, h = fw.load(args.watch)
    fw.append(args.watch, {"kind": "evaluator_change", "evaluator_sha256": fw.spec_evaluator_sha256(spec),
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
    p = sub.add_parser("fetch", help="record a NAV vintage (domain watches); run daily after the close")
    p.add_argument("watch")
    p.set_defaults(fn=cmd_fetch)
    p = sub.add_parser("report")
    p.add_argument("watch")
    p.add_argument("--sec", action="store_true",
                   help="also split by at-the-market windows from SEC filings (needs SEC_USER_AGENT)")
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
