#!/usr/bin/env python3
"""
archive_and_start_new_run.py — Archive current dashboard/bot history and start a
fresh "current run" window, WITHOUT deleting or rotating live/state.db.

Safety:
  * Refuses to run if the trader service is active.
  * Refuses to run if an open position exists.
  * Read-only on state.db (plus a local raw backup copy). Never deletes rows.
  * Exports are sanitized (account IDs redacted). Never commits the raw .db.

Outputs:
  * data/live_runs/archive_<date>_pre_clean_run/   (sanitized JSONL/JSON + metadata)
  * local_backups/state_<date>_pre_clean_run.db    (gitignored raw backup)
  * local_runtime/current_run.json                 (gitignored run marker)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(REPO, "live", "state.db")
ACCT_RE = re.compile(r"\bD?U[0-9]{5,}\b")
PROD = {"target_hit", "stop_hit", "time_exit", "bracket_exit", "pending_close"}


def _redact(v):
    return ACCT_RE.sub("<acct-redacted>", v) if isinstance(v, str) else v


def _rows(conn, q):
    cur = conn.execute(q)
    cols = [d[0] for d in cur.description]
    return [{c: _redact(v) for c, v in zip(cols, r)} for r in cur.fetchall()]


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(*args):
    try:
        return subprocess.check_output(["git", "-C", REPO, *args],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def _compounded(returns):
    e = 1.0
    for r in returns:
        e *= (1 + r)
    return (e - 1) * 100


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--notes", default="pre clean run archive")
    args = ap.parse_args()

    if not os.path.exists(DB):
        raise SystemExit(f"FATAL: {DB} not found")

    # ── Safety gates ─────────────────────────────────────────────────────────
    try:
        active = subprocess.run(["systemctl", "is-active", "monad-trader.service"],
                                capture_output=True, text=True).stdout.strip()
    except Exception:
        active = "unknown"
    if active == "active":
        raise SystemExit("REFUSING: monad-trader.service is active. Stop the trader first.")

    ro = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    open_positions = ro.execute("SELECT COUNT(*) FROM position").fetchone()[0]
    if open_positions > 0:
        raise SystemExit(f"REFUSING: {open_positions} open position(s) in state.db. "
                         "Reconcile/flatten first.")

    archive_id = f"archive_{args.date}_pre_clean_run"
    out = os.path.join(REPO, "data", "live_runs", archive_id)
    os.makedirs(out, exist_ok=True)

    # ── Export append-only history → JSONL ───────────────────────────────────
    history = {
        "trades": "SELECT * FROM trades ORDER BY entry_time",
        "signal_history": "SELECT * FROM signal_history ORDER BY id",
        "monitor_events": "SELECT * FROM monitor_events ORDER BY id",
    }
    counts, ranges = {}, {}
    for t, q in history.items():
        rows = _rows(ro, q)
        with open(os.path.join(out, f"{t}.jsonl"), "w") as f:
            for r in rows:
                f.write(json.dumps(r, default=str) + "\n")
        counts[t] = len(rows)

    # ── Export current-state snapshots → JSON ────────────────────────────────
    snapshots = {
        "position_snapshot": "SELECT * FROM position",
        "monitor_status": "SELECT * FROM monitor_status",
        "signal_snapshot": "SELECT * FROM signal_snapshot",
        "account_snapshot": "SELECT * FROM account_snapshot",
    }
    for t, q in snapshots.items():
        rows = _rows(ro, q)
        with open(os.path.join(out, f"{t}.json"), "w") as f:
            json.dump(rows, f, indent=2, default=str)
        counts[t] = len(rows)

    # ── Timestamp ranges ─────────────────────────────────────────────────────
    def rng(q):
        r = ro.execute(q).fetchone()
        return [r[0], r[1]]
    ranges["trades"] = rng("SELECT MIN(entry_time), MAX(exit_time) FROM trades")
    ranges["signal_history"] = rng("SELECT MIN(bar_time), MAX(bar_time) FROM signal_history")
    ranges["monitor_events"] = rng("SELECT MIN(event_time), MAX(event_time) FROM monitor_events")

    # ── Headline metrics (reproduce dashboard + alert numbers) ───────────────
    trows = ro.execute("SELECT return_pct, exit_type FROM trades").fetchall()
    allr = [r for r, _ in trows]
    prodr = [r for r, e in trows if e in PROD]
    headline = {
        "dashboard_prod_trades": len(prodr),
        "dashboard_win_rate_pct": round(sum(1 for x in prodr if x > 0) / len(prodr) * 100, 4) if prodr else 0,
        "dashboard_compounded_pct": round(_compounded(prodr), 4),
        "alert_all_trades": len(allr),
        "alert_simple_sum_pct": round(sum(allr) * 100, 4),
        "open_positions": open_positions,
    }

    # ── Raw backup (gitignored), then sha256 of the live DB ──────────────────
    backup_dir = os.path.join(REPO, "local_backups")
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, f"state_{args.date}_pre_clean_run.db")
    shutil.copy2(DB, backup_path)
    db_sha = _sha256(DB)

    meta = {
        "archive_id": archive_id,
        "export_time_utc": datetime.now(timezone.utc).isoformat(),
        "source_database": DB,
        "source_database_sha256": db_sha,
        "raw_backup_local_only": backup_path,
        "git_branch": _git("branch", "--show-current"),
        "git_commit": _git("rev-parse", "--short", "HEAD"),
        "row_counts": counts,
        "timestamp_ranges": ranges,
        "headline_metrics": headline,
        "note": "Sanitized export. Account IDs redacted. Raw .db NOT committed "
                "(local backup only). No rows were deleted from state.db.",
    }
    with open(os.path.join(out, "metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)

    # ── Run marker (gitignored runtime) ──────────────────────────────────────
    started_at = datetime.now(timezone.utc).isoformat()
    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    runtime_dir = os.path.join(REPO, "local_runtime")
    os.makedirs(runtime_dir, exist_ok=True)
    marker = {
        "run_id": run_id,
        "started_at": started_at,
        "archive_id": archive_id,
        "git_commit": meta["git_commit"],
        "notes": args.notes,
    }
    with open(os.path.join(runtime_dir, "current_run.json"), "w") as f:
        json.dump(marker, f, indent=2)

    # ── Report ───────────────────────────────────────────────────────────────
    print("✅ Archive + new-run marker created.")
    print(f"\n  Archive (committable, sanitized): {out}")
    for fn in sorted(os.listdir(out)):
        print(f"    {fn}  ({os.path.getsize(os.path.join(out, fn))} b)")
    print(f"\n  Raw backup (LOCAL ONLY, gitignored): {backup_path}")
    print(f"  Run marker (gitignored): {os.path.join(runtime_dir, 'current_run.json')}")
    print(f"  run_id={run_id}  started_at={started_at}")
    print(f"\n  Headline at archive: dashboard {headline['dashboard_prod_trades']} trades / "
          f"{headline['dashboard_compounded_pct']:+.2f}% compounded")
    print("\n  Verify with:")
    print(f"    venv/bin/python - <<'PY'\n"
          f"    import json,sqlite3\n"
          f"    m=json.load(open('{os.path.join(out,'metadata.json')}'))\n"
          f"    c=sqlite3.connect('file:{DB}?mode=ro',uri=True)\n"
          f"    print('trades db vs archive:', c.execute('SELECT COUNT(*) FROM trades').fetchone()[0], m['row_counts']['trades'])\n"
          f"    PY")


if __name__ == "__main__":
    main()
