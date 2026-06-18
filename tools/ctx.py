#!/usr/bin/env python3
"""
ctx — read-only context query tool for coding agents.

Lets an agent ASK for project facts instead of reading the whole codebase:

    venv/bin/python tools/ctx.py route "fix the dashboard equity curve"
    venv/bin/python tools/ctx.py where classify_regime
    venv/bin/python tools/ctx.py schema
    venv/bin/python tools/ctx.py config LIVE_SYMBOL
    venv/bin/python tools/ctx.py perf
    venv/bin/python tools/ctx.py status
    venv/bin/python tools/ctx.py recent 10
    venv/bin/python tools/ctx.py map dashboard

Read-only: never writes, never trades, never places orders. Redacts IBKR
account IDs. Backed by context_map.json (the manifest).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(REPO, "context_map.json")
DB = os.path.join(REPO, "live", "state.db")
PROD = {"target_hit", "stop_hit", "time_exit", "bracket_exit", "pending_close"}
CONFIRMED = {"bracket_exit", "stop_hit"}  # actually-filled exits (drop inferred target_hit + artifacts)
_ACCT = re.compile(r"\bD?U[0-9]{5,}\b")


def _redact(s: str) -> str:
    return _ACCT.sub("<acct-redacted>", s)


def _manifest() -> dict:
    with open(MANIFEST) as f:
        return json.load(f)


def _git(*args) -> str:
    try:
        return subprocess.check_output(["git", "-C", REPO, *args],
                                       stderr=subprocess.DEVNULL).decode().rstrip()
    except Exception:
        return ""


# ── commands ─────────────────────────────────────────────────────────────────

def cmd_route(args):
    task = " ".join(args.task).lower()
    rules = _manifest()["routing"]
    scored = []
    for r in rules:
        hits = [k for k in r["keywords"] if k in task]
        if hits:
            scored.append((len(hits), hits, r))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        print("No routing match. Try keywords like: trader, signal, dashboard, ops, db, ibkr, performance.")
        print("Or: ctx map   (see all areas)")
        return
    for _, hits, r in scored[:3]:
        print(f"• matched: {', '.join(hits)}")
        print(f"    READ:  {', '.join(r['read']) or '—'}")
        print(f"    RUN:   {', '.join(r['run']) or '—'}")
        print(f"    AVOID: {', '.join(r['avoid']) or '—'}\n")


def cmd_where(args):
    sym = args.symbol
    pat = rf"(^\s*(def|class)\s+{re.escape(sym)}\b)|(^\s*{re.escape(sym)}\s*=)"
    rx = re.compile(pat)
    found = 0
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in
                   (".git", "venv", "__pycache__", "local_logs", "local_backups", "local_runtime")]
        for fn in files:
            if not fn.endswith((".py",)):
                continue
            p = os.path.join(root, fn)
            try:
                with open(p, errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        if rx.search(line):
                            rel = os.path.relpath(p, REPO)
                            print(f"  {rel}:{i}: {line.strip()[:100]}")
                            found += 1
            except OSError:
                continue
    if not found:
        print(f"  no definition of '{sym}' found (try `ctx grep {sym}` style search yourself)")


def cmd_schema(args):
    if not os.path.exists(DB):
        print("live/state.db not present.")
        return
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    tables = [r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    for t in tables:
        cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})")]
        try:
            n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except Exception:
            n = "?"
        print(f"  {t} ({n} rows): {', '.join(cols)}")


def cmd_config(args):
    sys.path.insert(0, REPO)
    try:
        import config
    except Exception as exc:
        print(f"could not import config: {exc}")
        return
    key = args.key
    val = getattr(config, key, "<not found>")
    print(f"  config.{key} = {val}")
    # where is it set?
    for sub in ("config.py",) + tuple(
            os.path.join("config_modules", f) for f in
            sorted(os.listdir(os.path.join(REPO, "config_modules")))
            if f.endswith(".py")) if os.path.isdir(os.path.join(REPO, "config_modules")) else ("config.py",):
        p = os.path.join(REPO, sub)
        if not os.path.exists(p):
            continue
        with open(p, errors="ignore") as fh:
            for i, line in enumerate(fh, 1):
                if re.match(rf"\s*{re.escape(key)}\s*=", line):
                    print(f"    set at {sub}:{i}: {line.strip()[:90]}")


def _compound(returns):
    e = 1.0
    for r in returns:
        e *= (1 + r)
    return (e - 1) * 100


def cmd_perf(args):
    if not os.path.exists(DB):
        print("live/state.db not present.")
        return
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = c.execute("SELECT return_pct, exit_type FROM trades").fetchall()
    if not rows:
        print("  no trades recorded yet.")
        return
    allr = [r for r, _ in rows]
    prodr = [r for r, e in rows if e in PROD]
    confr = [r for r, e in rows if e in CONFIRMED]
    def wr(v):
        return sum(1 for x in v if x > 0) / len(v) * 100 if v else 0
    print(f"  ALL trades:        n={len(allr):3}  WR={wr(allr):5.1f}%  compounded={_compound(allr):+8.3f}%  simple_sum={sum(allr)*100:+8.3f}%")
    print(f"  PROD (dashboard):  n={len(prodr):3}  WR={wr(prodr):5.1f}%  compounded={_compound(prodr):+8.3f}%")
    print(f"  CONFIRMED fills:   n={len(confr):3}  WR={wr(confr):5.1f}%  compounded={_compound(confr):+8.3f}%   <- the honest edge")
    print("  (CONFIRMED = bracket_exit + stop_hit; excludes time_exit artifacts and inferred target_hit)")


def cmd_status(args):
    sc = os.path.join(REPO, "ops", "status_check.sh")
    if os.path.exists(sc):
        out = subprocess.run(["bash", sc], capture_output=True, text=True)
        print(_redact(out.stdout))
    else:
        print("ops/status_check.sh not found")


def cmd_recent(args):
    n = args.n
    print(_git("log", "--oneline", "-n", str(n), "--stat", "--no-decorate") or "(no git)")


def cmd_map(args):
    m = _manifest()
    if args.area:
        a = m["areas"].get(args.area)
        print(json.dumps(a, indent=2) if a else f"no area '{args.area}'. areas: {', '.join(m['areas'])}")
    else:
        print(f"project: {m['project']}  deploy_branch: {m['deploy_branch']}")
        print(f"areas: {', '.join(m['areas'])}")
        print("\ninvariants:")
        for k, v in m["invariants"].items():
            if not k.startswith("_"):
                print(f"  {k} = {v}")
        print("\ntools (read-only):")
        for t in m["tools_readonly"]:
            print(f"  {t['cmd']:42} {t['returns']}")


def cmd_tests(args):
    m = _manifest()
    a = m["areas"].get(args.area)
    if not a:
        print(f"no area '{args.area}'. areas: {', '.join(m['areas'])}")
        return
    print("  " + ("\n  ".join(a.get("tests", [])) or "(no tests listed)"))


def main():
    p = argparse.ArgumentParser(description="ctx — read-only context query tool for agents")
    sub = p.add_subparsers(dest="cmd")
    sp = sub.add_parser("route"); sp.add_argument("task", nargs="+"); sp.set_defaults(fn=cmd_route)
    sp = sub.add_parser("where"); sp.add_argument("symbol"); sp.set_defaults(fn=cmd_where)
    sub.add_parser("schema").set_defaults(fn=cmd_schema)
    sp = sub.add_parser("config"); sp.add_argument("key"); sp.set_defaults(fn=cmd_config)
    sp = sub.add_parser("perf"); sp.set_defaults(fn=cmd_perf)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sp = sub.add_parser("recent"); sp.add_argument("n", nargs="?", type=int, default=10); sp.set_defaults(fn=cmd_recent)
    sp = sub.add_parser("map"); sp.add_argument("area", nargs="?"); sp.set_defaults(fn=cmd_map)
    sp = sub.add_parser("tests"); sp.add_argument("area"); sp.set_defaults(fn=cmd_tests)
    args = p.parse_args()
    if not getattr(args, "fn", None):
        # default: print the index summary
        cmd_map(argparse.Namespace(area=None))
        print("\nUsage: ctx {route|where|schema|config|perf|status|recent|map|tests}")
        return
    args.fn(args)


if __name__ == "__main__":
    main()
