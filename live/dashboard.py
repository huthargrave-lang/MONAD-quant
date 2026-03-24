"""Read-only monitoring dashboard for the live trading bot.

This module starts a separate FastAPI process that reads from live/state.db
without placing orders or mutating trading state.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

DB_PATH = Path(__file__).parent / "state.db"
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app = FastAPI(title="MONAD Read-Only Monitor", version="1.0.0")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _safe_query_one(query: str, params: tuple = ()) -> dict | None:
    try:
        with _conn() as conn:
            row = conn.execute(query, params).fetchone()
    except sqlite3.OperationalError:
        return None
    return dict(row) if row else None


def _safe_query_many(query: str, params: tuple = ()) -> list[dict]:
    try:
        with _conn() as conn:
            rows = conn.execute(query, params).fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(r) for r in rows]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "utc": datetime.now(timezone.utc).isoformat()}


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    status = _safe_query_one("SELECT * FROM monitor_status WHERE id = 1")
    signal = _safe_query_one("SELECT * FROM signal_snapshot WHERE id = 1")
    position = _safe_query_one("SELECT * FROM position LIMIT 1")
    trades = _safe_query_many(
        """
        SELECT entry_time, exit_time, return_pct, exit_type, exit_price
        FROM trades
        ORDER BY exit_time DESC
        LIMIT 25
        """
    )
    events = _safe_query_many(
        """
        SELECT event_time, level, category, message
        FROM monitor_events
        ORDER BY id DESC
        LIMIT 25
        """
    )

    warnings = [e for e in events if e.get("level") in {"WARNING", "ERROR"}]

    return TEMPLATES.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "status": status,
            "signal": signal,
            "position": position,
            "trades": trades,
            "events": events,
            "warnings": warnings,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
