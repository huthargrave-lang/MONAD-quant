#!/usr/bin/env python3
"""
analyze_run.py — Honest, read-only analysis of a paper run from live/state.db.

Operationalizes the "is the clean run trustworthy, and what's the real edge?"
question: separates confirmed fills from artifacts, counts software-net fires and
fill provenance, checks for desync blocks, and renders a pass/fail verdict against
a clean-run rubric. Defaults to the CURRENT run (local_runtime/current_run.json).

Read-only. No trades, no writes. Redacts IBKR account IDs.

    venv/bin/python ops/analyze_run.py            # current run
    venv/bin/python ops/analyze_run.py --all      # all of state.db
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(REPO, "live", "state.db")
MARKER = os.path.join(REPO, "local_runtime", "current_run.json")
ACTUAL = {"bracket_exit", "stop_hit"}          # exits with a confirmed fill price
ARTIFACT = {"time_exit"}                         # rode past target — broken-bracket artifact
SYNTH = {"estimated_close", "paper_reset"}       # estimated / bookkeeping
_ACCT = re.compile(r"\bD?U[0-9]{5,}\b")


def _parse(ts):
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t
    except Exception:
        return None


# `return_pct` is a PRICE return on a position sized at a fixed fraction of equity
# (live/state.py: position_pct = 0.10), so compounding it raw gives a return on
# 10%-of-equity NOTIONAL, not on the account -- about 10x the account effect.
# See RESEARCH_WEB.md F160.
LIVE_POSITION_FRACTION = 0.10


def _compound(rs, fraction=1.0):
    """Compound returns; `fraction` scales each into account units."""
    e = 1.0
    for r in rs:
        e *= (1 + r * fraction)
    return (e - 1) * 100


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="analyze all of state.db, ignore the run marker")
    args = ap.parse_args()
    if not os.path.exists(DB):
        raise SystemExit("live/state.db not found")

    started_at = None
    if not args.all and os.path.exists(MARKER):
        try:
            started_at = _parse(json.load(open(MARKER)).get("started_at"))
        except Exception:
            started_at = None
    scope = "ALL history" if started_at is None else f"current run (since {started_at.isoformat()})"

    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    trades = [dict(zip([d[0] for d in c.execute("SELECT * FROM trades LIMIT 0").description], r))
              for r in c.execute("SELECT * FROM trades").fetchall()]
    events = [dict(zip([d[0] for d in c.execute("SELECT * FROM monitor_events LIMIT 0").description], r))
              for r in c.execute("SELECT * FROM monitor_events").fetchall()]
    if started_at is not None:
        trades = [t for t in trades if (_parse(t.get("entry_time")) or datetime.max.replace(tzinfo=timezone.utc)) >= started_at]
        events = [e for e in events if (_parse(e.get("event_time")) or datetime.min.replace(tzinfo=timezone.utc)) >= started_at]

    print(f"== Run analysis ({scope}) — {datetime.now(timezone.utc).isoformat(timespec='seconds')} ==\n")

    # ── Exit-type breakdown + performance tiers ──────────────────────────────
    by_type = {}
    for t in trades:
        by_type.setdefault(t["exit_type"], []).append(t["return_pct"])
    def stats(rs):
        n = len(rs)
        wr = sum(1 for x in rs if x > 0) / n * 100 if n else 0
        return n, wr, _compound(rs)
    allr = [t["return_pct"] for t in trades]
    actual = [t["return_pct"] for t in trades if t["exit_type"] in ACTUAL]
    artifact = [t["return_pct"] for t in trades if t["exit_type"] in ARTIFACT]
    synth = [t["return_pct"] for t in trades if t["exit_type"] in SYNTH]

    print("  exit types:", {k: len(v) for k, v in sorted(by_type.items())})
    for label, rs in [("ALL trades", allr), ("CONFIRMED fills (bracket_exit+stop_hit)", actual),
                      ("broken-bracket artifacts (time_exit)", artifact), ("estimated/reset", synth)]:
        n, wr, comp = stats(rs)
        if n:
            print(f"  {label:42} n={n:3} WR={wr:5.1f}%  compounded={comp:+8.3f}%")

    # ── Event signals (the trust markers) ────────────────────────────────────
    def count(substr):
        return sum(1 for e in events if substr.lower() in (e.get("message") or "").lower())
    sw_tp = count("software take-profit")
    sw_stop = count("software stop")
    inferred = count("inferred")
    estimated = count("force-finalized") + count("estimated_ret")
    desync = count("entry_blocked_desync") + count("position desync")
    conn_ref = count("connectionrefused") + count("connect call failed")
    print("\n  trust markers (current scope):")
    print(f"    software take-profit fires : {sw_tp}")
    print(f"    software stop fires        : {sw_stop}")
    print(f"    inferred-fill warnings     : {inferred}")
    print(f"    estimated/force-finalized  : {estimated}")
    print(f"    entry blocked on desync    : {desync}")
    print(f"    IBKR connection refused    : {conn_ref}")

    # ── Clean-run verdict ────────────────────────────────────────────────────
    n_all = len(allr)
    n_actual = len(actual)
    confirmed_frac = (n_actual / n_all) if n_all else 0
    checks = [
        ("at least 1 trade in scope", n_all >= 1),
        (">=80% of fills are confirmed (bracket_exit/stop_hit)", n_all == 0 or confirmed_frac >= 0.80),
        ("no broken-bracket time_exit artifacts", len(artifact) == 0),
        ("no estimated/force-finalized fills", estimated == 0),
        ("no entry-desync blocks", desync == 0),
        ("no connection-refused storm (<3)", conn_ref < 3),
    ]
    print("\n  CLEAN-RUN RUBRIC:")
    passed = True
    for label, ok in checks:
        print(f"    [{'PASS' if ok else 'FAIL'}] {label}")
        passed = passed and ok
    print(f"\n  VERDICT: {'CLEAN — performance is trustworthy' if passed else 'NOT yet clean — see FAILs above'}")
    if n_all:
        print(f"  Honest edge (confirmed fills): {_compound(actual, LIVE_POSITION_FRACTION):+.3f}% "
              f"ON THE ACCOUNT over {n_actual} trades")
        print(f"    ({_compound(actual):+.3f}% on 10%-of-equity notional — the raw dashboard")
        print(f"     convention, which reports ~10x the account effect; see F160)")


if __name__ == "__main__":
    main()
