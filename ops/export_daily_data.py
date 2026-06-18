#!/usr/bin/env python3
"""
export_daily_data.py — Export sanitized paper-trading data from live/state.db
into data/live_runs/pi_export_<date>/ for analysis.

Safety:
  * Read-only on state.db. NEVER copies the raw .db.
  * Redacts IBKR account IDs (DU…/U…) from any text fields it writes.
  * Writes only JSON/JSONL (no secrets, no credentials).

Usage:
    venv/bin/python local_ops/export_daily_data.py
    venv/bin/python local_ops/export_daily_data.py --date 2026-06-18
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
_ACCT_RE = re.compile(r"\bD?U[0-9]{5,}\b")  # DU1234567 / U1234567 paper/live ids


def _redact(value):
    if isinstance(value, str):
        return _ACCT_RE.sub("<acct-redacted>", value)
    return value


def _rows(conn, query):
    cur = conn.execute(query)
    cols = [d[0] for d in cur.description]
    for r in cur.fetchall():
        yield {c: _redact(v) for c, v in zip(cols, r)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    args = ap.parse_args()

    if not os.path.exists(DB):
        raise SystemExit(f"FATAL: {DB} not found")

    out = os.path.join(REPO, "data", "live_runs", f"pi_export_{args.date}")
    os.makedirs(out, exist_ok=True)
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    # Multi-row history -> JSONL ; single-row state -> JSON
    jsonl = {
        "trades": "SELECT * FROM trades ORDER BY entry_time",
        "signal_history": "SELECT * FROM signal_history ORDER BY id",
        "monitor_events": "SELECT * FROM monitor_events ORDER BY id",
    }
    js = {
        "monitor_status": "SELECT * FROM monitor_status",
        "signal_snapshot": "SELECT * FROM signal_snapshot",
        "account_snapshot": "SELECT * FROM account_snapshot",
    }
    meta = {
        "export_time_utc": datetime.now(timezone.utc).isoformat(),
        "source_database": DB,
        "note": "Paper-trading data only. Account IDs redacted. Raw .db NOT exported.",
        "tables": {},
    }

    def _drange(rows, *cols):
        vals = [r[c] for r in rows for c in cols if r.get(c)]
        return [min(vals), max(vals)] if vals else [None, None]

    for t, q in jsonl.items():
        rows = list(_rows(conn, q))
        with open(os.path.join(out, f"{t}.jsonl"), "w") as f:
            for r in rows:
                f.write(json.dumps(r, default=str) + "\n")
        if t == "trades":
            dr = _drange(rows, "entry_time", "exit_time")
        elif t == "signal_history":
            dr = _drange(rows, "bar_time")
        else:
            dr = _drange(rows, "event_time")
        meta["tables"][t] = {"format": "jsonl", "rows": len(rows), "date_range": dr}

    for t, q in js.items():
        try:
            rows = list(_rows(conn, q))
        except sqlite3.OperationalError:
            continue
        with open(os.path.join(out, f"{t}.json"), "w") as f:
            json.dump(rows, f, indent=2, default=str)
        meta["tables"][t] = {"format": "json", "rows": len(rows)}

    with open(os.path.join(out, "metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)
    conn.close()

    print(f"Exported to {out}")
    for fn in sorted(os.listdir(out)):
        print(f"  {fn}  ({os.path.getsize(os.path.join(out, fn))} bytes)")
    print("\nReminder: review, then commit the export dir (no raw .db, no secrets).")


if __name__ == "__main__":
    main()
