#!/usr/bin/env python3
"""
MONAD Quant — the EDGAR ledger's command line (src/research/edgar_ledger.py; the operator's
doc is docs/EDGAR_LEDGER.md, the design record docs/research/EDGAR_LEDGER_QUESTION.md).

Runs where EDGAR is reachable: the ``edgar-ledger`` GitHub workflow, pointed at its clone of
the ``edgar-ledger`` branch through ``MONAD_EDGAR_LEDGER_DIR``. Every mode that fetches needs
``SEC_USER_AGENT`` (a real contact; reserved domains are refused) and spaces requests at
0.25 s. Nothing here edits a row: rows are appended, frozen files written once.

    edgar_ledger.py probe  --quarter 2024Q1 [--n 500]     Step 0: runner / header / FSDS facts
    edgar_ledger.py fsds   --quarter 2024Q1               slice 1: one FSDS sub.txt extract
    edgar_ledger.py daily  [--today YYYY-MM-DD] [--cap 10] slice 2: every pending ET business day
    edgar_ledger.py sweep  --quarter 2024Q1               monthly: revisions vs the rebuilt index
    edgar_ledger.py verify [--against REF] [--report-gaps] shard checks; append-only history
    edgar_ledger.py freeze --from D --to D [--allow-partial] [--data-dir DIR]
    edgar_ledger.py freeze-fsds --quarter 2024Q1 [--quarter ...] [--data-dir DIR]

``daily`` and ``fsds`` refuse to run until a COMMITTED probe_summary with P0 = PASS and a
decided header source is on the branch; ``daily`` then exits 0 with a ``::warning::`` so the
schedule stays green and ``verify --report-gaps`` counts the probe-less days. ``verify``
exits 1 on any problem; the workflow runs it before the push, so a violation is never pushed.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.research import edgar_ledger as el  # noqa: E402
from src.research import trials  # noqa: E402


def _ledger_dir(args) -> Path:
    if getattr(args, "ledger", None):
        return Path(args.ledger)
    env = os.environ.get(el.LEDGER_DIR_ENV)
    return Path(env) if env else REPO / el.LEDGER_REL


def _run_id() -> str:
    return os.environ.get("GITHUB_RUN_NUMBER") or _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _fetcher(store: el.Store, run_id: str, get=None) -> el.Fetcher:
    inputs: list[dict] = []
    f = el.Fetcher(get=get, on_input=inputs.append, run_id=run_id)
    f.pending_inputs = inputs  # type: ignore[attr-defined]
    return f


def _flush_inputs(store: el.Store, fetcher: el.Fetcher) -> int:
    rows = getattr(fetcher, "pending_inputs", [])
    if rows:
        store.append_inputs(rows)
    return len(rows)


def _ledger_repo(store: el.Store) -> Path | None:
    """The git work tree holding the ledger directory — found from the nearest EXISTING
    ancestor, because before the first probe the data directory itself does not exist yet."""
    probe = store.root.resolve()
    while not probe.is_dir() and probe.parent != probe:
        probe = probe.parent
    top = trials._git(probe, "rev-parse", "--show-toplevel")
    return Path(top.stdout.decode().strip()) if top.returncode == 0 else None


def _ledger_head(store: el.Store) -> str | None:
    repo = _ledger_repo(store)
    if repo is None:
        return None
    r = trials._git(repo, "rev-parse", "HEAD")
    return r.stdout.decode().strip() if r.returncode == 0 else None


def cmd_probe(args, get=None) -> int:
    store = el.Store(_ledger_dir(args))
    run_id = _run_id()
    fetcher = _fetcher(store, run_id, get)
    path, summary = el.run_probe(store, fetcher, args.quarter, args.n, run_id=run_id)
    n = _flush_inputs(store, fetcher)
    print(f"probe {args.quarter} n={args.n}: {summary['verdict']} (P0 {summary['p0']['status']}, "
          f"P1 {summary['p1']['status']} hdr_source={summary['hdr_source']}, P2 {summary['p2']['status']} "
          f"role={summary['p2']['fsds_role']}, coverage originals={summary['p2']['coverage_originals']} "
          f"amendments={summary['p2']['coverage_amendments']})")
    print(f"wrote {path} and {n} inputs line(s)")
    if summary["verdict"] == "FAIL_RUNNER":
        print("::warning::edgar-ledger: the runner was refused (403/429); the runner question moves to the Pi")
    return 0


def cmd_fsds(args, get=None) -> int:
    store = el.Store(_ledger_dir(args))
    run_id = _run_id()
    fetcher = _fetcher(store, run_id, get)
    try:
        result = el.run_fsds(store, fetcher, args.quarter, run_id=run_id,
                             require_committed=not args.uncommitted_probe_ok)
    except el.EdgarLedgerError as e:
        print(f"REFUSED: {e}")
        return 2
    finally:
        _flush_inputs(store, fetcher)
    print(json.dumps(result, sort_keys=True))
    return 0


def cmd_daily(args, get=None) -> int:
    store = el.Store(_ledger_dir(args))
    run_id = _run_id()
    today = _dt.date.fromisoformat(args.today) if args.today else None
    first = _dt.date.fromisoformat(args.first_day) if args.first_day else None
    if store.passing_probe(require_committed=not args.uncommitted_probe_ok) is None:
        print("::warning::edgar-ledger: no committed passing probe on the branch; the daily job wrote nothing "
              "(dispatch mode=probe first; `verify --report-gaps` counts these days)")
        return 0
    fetcher = _fetcher(store, run_id, get)
    try:
        result = el.run_daily(store, fetcher, today=today, cap=args.cap, run_id=run_id, first_day=first,
                              require_committed=not args.uncommitted_probe_ok)
    except el.EdgarLedgerError as e:
        print(f"FAIL: {e}")
        return 1
    finally:
        _flush_inputs(store, fetcher)
    for d in result["days"]:
        s = d["seal"]
        print(f"{d['day']}: idx {d['idx_status']}, accessions {s['accessions']}, hdr_ok {s['hdr_ok']}, "
              f"hdr_failed {s['hdr_failed']}, complete {s['complete']}, +{d['rows']} row(s)")
    if result.get("rolled_forward"):
        print(f"::warning::edgar-ledger: {result['rolled_forward']} weekday(s) still pending after the cap of {args.cap}")
    print(f"daily: {len(result['days'])} day(s) processed (hdr_source={result.get('hdr_source')})")
    return 0


def cmd_sweep(args, get=None) -> int:
    store = el.Store(_ledger_dir(args))
    run_id = _run_id()
    fetcher = _fetcher(store, run_id, get)
    try:
        result = el.run_sweep(store, fetcher, args.quarter, run_id=run_id,
                              require_committed=not args.uncommitted_probe_ok)
    except el.EdgarLedgerError as e:
        print(f"REFUSED: {e}")
        return 2
    finally:
        _flush_inputs(store, fetcher)
    print(json.dumps(result, sort_keys=True))
    return 0


def cmd_verify(args) -> int:
    store = el.Store(_ledger_dir(args))
    problems = el.verify_shards(store.root)
    for p in problems:
        print(f"FAIL {p}")
    history: list[str] = []
    if args.against:
        repo = _ledger_repo(store)
        if repo is None:
            history = [f"{store.root} is not inside a git repository; --against needs one"]
        else:
            rel = store.root.resolve().relative_to(repo.resolve())
            history = el.verify_history(args.against, repo=repo, rel_dir=rel)
        for p in history:
            print(f"FAIL history: {p}")
    if args.report_gaps:
        today = _dt.date.fromisoformat(args.today) if args.today else None
        gaps = el.report_gaps(store, today=today, require_committed=not args.uncommitted_probe_ok)
        print(json.dumps({"gaps": gaps}, sort_keys=True))
        if gaps["passing_probe"] is None:
            print(f"::warning::edgar-ledger: no passing probe; {gaps['probe_less_days']} probe-less weekday(s)")
        if gaps["missing_seal_days"] or gaps["partial_days"]:
            print(f"::warning::edgar-ledger: {len(gaps['missing_seal_days'])} weekday(s) without a seal, "
                  f"{len(gaps['partial_days'])} partial")
    print(f"shards: {len(problems)} problem(s)" + (f"; append-only vs {args.against}: {len(history)} violation(s)"
                                                    if args.against else ""))
    return 1 if problems or history else 0


def cmd_freeze(args) -> int:
    store = el.Store(_ledger_dir(args))
    data_dir = Path(args.data_dir) if args.data_dir else None
    try:
        sha, manifest = el.freeze(store, _dt.date.fromisoformat(args.start), _dt.date.fromisoformat(args.end),
                                  allow_partial=args.allow_partial, data_dir=data_dir, ledger_head=_ledger_head(store))
    except el.EdgarLedgerError as e:
        print(f"REFUSED: {e}")
        return 2
    print(f"{el.PREFIX}-{sha}: {manifest['rows']} row(s), {manifest['sealed_days']}/{manifest['weekdays']} weekdays sealed, "
          f"partial {manifest['partial_days']}, missing {manifest['missing_seal_days']}, "
          f"allow_partial={manifest['allow_partial']}")
    return 0


def cmd_freeze_fsds(args) -> int:
    store = el.Store(_ledger_dir(args))
    data_dir = Path(args.data_dir) if args.data_dir else None
    try:
        sha, manifest = el.freeze_fsds(store, args.quarter, data_dir=data_dir, ledger_head=_ledger_head(store))
    except el.EdgarLedgerError as e:
        print(f"REFUSED: {e}")
        return 2
    print(f"{el.FSDS_PREFIX}-{sha}: {manifest['rows']} row(s) from {manifest['quarters']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="MONAD EDGAR ledger (append-only; see docs/EDGAR_LEDGER.md)")
    p.add_argument("--ledger", help=f"ledger directory (default ${el.LEDGER_DIR_ENV} or {el.LEDGER_REL})")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--uncommitted-probe-ok", action="store_true",
                        help="accept a probe file that git does not track (local experiments only)")

    s = sub.add_parser("probe", help="Step 0: P0 runner, P1 header source, P2 FSDS facts")
    s.add_argument("--quarter", required=True)
    s.add_argument("--n", type=int, default=500)
    s.set_defaults(func=cmd_probe)

    s = sub.add_parser("fsds", help="slice 1: one FSDS quarter's sub.txt extract")
    s.add_argument("--quarter", required=True)
    common(s)
    s.set_defaults(func=cmd_fsds)

    s = sub.add_parser("daily", help="slice 2: every pending ET business day since the last complete seal")
    s.add_argument("--today", help="ET date to plan from (default: now in America/New_York)")
    s.add_argument("--cap", type=int, default=el.DAILY_CAP)
    s.add_argument("--first-day", help="with no seal yet, the first day to process (default: yesterday)")
    common(s)
    s.set_defaults(func=cmd_daily)

    s = sub.add_parser("sweep", help="monthly: revisions against the quarter's rebuilt full index")
    s.add_argument("--quarter", required=True)
    common(s)
    s.set_defaults(func=cmd_sweep)

    s = sub.add_parser("verify", help="shard checks; with --against, append-only history")
    s.add_argument("--against", help="git ref the history is judged against (origin/edgar-ledger in CI)")
    s.add_argument("--report-gaps", action="store_true")
    s.add_argument("--today")
    common(s)
    s.set_defaults(func=cmd_verify)

    s = sub.add_parser("freeze", help="EDGARLEDGER-<sha>.csv.gz + manifest through data_store")
    s.add_argument("--from", dest="start", required=True)
    s.add_argument("--to", dest="end", required=True)
    s.add_argument("--allow-partial", action="store_true")
    s.add_argument("--data-dir")
    s.set_defaults(func=cmd_freeze)

    s = sub.add_parser("freeze-fsds", help="EDGARFSDS-<sha>.csv.gz + manifest from branch FSDS extracts")
    s.add_argument("--quarter", action="append", required=True)
    s.add_argument("--data-dir")
    s.set_defaults(func=cmd_freeze_fsds)
    return p


def main(argv=None, *, get=None) -> int:
    """``get`` injects the HTTP function (tests); the workflow uses the default urllib one."""
    args = build_parser().parse_args(argv)
    if args.cmd in ("probe", "fsds", "daily", "sweep"):
        return args.func(args, get)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
