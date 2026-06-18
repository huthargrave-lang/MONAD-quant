"""
run_window.py — Pure helpers for the dashboard "current run" view.

A run marker (local_runtime/current_run.json) records when the current run
started. The dashboard filters append-only history rows (trades, signal_history,
monitor_events) by that timestamp so the default view shows only the current run,
while "all" and "archive" views remain available. No database writes; no trader
coupling — this is display-side filtering only.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

VALID_MODES = ("current", "all", "archive")


def parse_ts(value) -> Optional[datetime]:
    """Parse a timestamp from the DB into a UTC-aware datetime, or None.

    Handles ISO-8601 with offset (``2026-06-18T09:32:00+00:00``), ISO naive
    (assumed UTC), and space-separated ``YYYY-MM-DD HH:MM:SS`` (e.g. bar_time).
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        text = text.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            # Last resort: space-separated without 'T'
            try:
                dt = datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _row_ts(row: dict, ts_keys: Iterable[str]) -> Optional[datetime]:
    """Return the first parseable timestamp among ts_keys for a row."""
    for k in ts_keys:
        ts = parse_ts(row.get(k))
        if ts is not None:
            return ts
    return None


def filter_rows(rows, ts_keys, started_at: Optional[datetime], mode: str = "current") -> list:
    """Filter append-only history rows by run window.

    mode="current": keep rows with timestamp >= started_at
    mode="archive": keep rows with timestamp <  started_at
    mode="all":     keep everything
    If started_at is None (no marker), every mode returns all rows unchanged.
    Rows with an unparseable/missing timestamp are kept in "all", and in
    "current"/"archive" are treated conservatively as NOT in the current run
    (so a malformed row never pollutes a fresh run view).
    """
    rows = list(rows)
    if mode not in VALID_MODES:
        mode = "current"
    if mode == "all" or started_at is None:
        return rows
    out = []
    for r in rows:
        ts = _row_ts(r, ts_keys)
        if ts is None:
            if mode == "archive":
                out.append(r)  # undated rows are "old"
            continue
        if mode == "current" and ts >= started_at:
            out.append(r)
        elif mode == "archive" and ts < started_at:
            out.append(r)
    return out


def load_run_marker(path) -> Optional[dict]:
    """Load the current-run marker JSON, or None if absent/invalid."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
    except (ValueError, OSError):
        return None
    return data if isinstance(data, dict) else None


def marker_started_at(marker: Optional[dict]) -> Optional[datetime]:
    """Extract started_at from a marker dict as a UTC datetime, or None."""
    if not marker:
        return None
    return parse_ts(marker.get("started_at"))
