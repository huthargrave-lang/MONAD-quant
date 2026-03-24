"""
live/state.py — SQLite-backed persistence for open position and trade log.

Two tables:
  position  — zero or one row (the currently open trade)
  trades    — append-only log of closed trades (for rolling stats and sizing)
"""

import sqlite3
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Optional

import config
from src.strategy.sizing import compute_position_size

log = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent / "state.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS position (
                symbol           TEXT NOT NULL,
                entry_time       TEXT NOT NULL,
                entry_price      REAL NOT NULL,
                qty              INTEGER NOT NULL,
                bracket_order_id TEXT NOT NULL,
                bar_count        INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS trades (
                entry_time  TEXT NOT NULL,
                exit_time   TEXT NOT NULL,
                return_pct  REAL NOT NULL,
                exit_type   TEXT NOT NULL,
                exit_price  REAL
            );
        """)


# ── Position management ───────────────────────────────────────────────────────

@dataclass
class Position:
    symbol: str
    entry_time: str
    entry_price: float
    qty: int
    bracket_order_id: str
    bar_count: int


def get_position() -> Optional[Position]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM position LIMIT 1").fetchone()
    if row is None:
        return None
    return Position(**dict(row))


def open_position(symbol: str, entry_price: float, qty: int,
                  bracket_order_id: str) -> None:
    entry_time = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute("DELETE FROM position")  # ensure no stale row
        conn.execute(
            "INSERT INTO position VALUES (?, ?, ?, ?, ?, 0)",
            (symbol, entry_time, entry_price, qty, bracket_order_id),
        )
    log.info(f"Position opened: {qty} {symbol} @ {entry_price:.4f}")


def increment_bar_count() -> int:
    """Increments bar_count for the open position. Returns new count."""
    with _conn() as conn:
        conn.execute("UPDATE position SET bar_count = bar_count + 1")
        row = conn.execute("SELECT bar_count FROM position LIMIT 1").fetchone()
    new_count = row["bar_count"] if row else 0
    log.debug(f"Bar count: {new_count}")
    return new_count


def close_position(return_pct: float, exit_type: str,
                   exit_price: float = None) -> None:
    """Records the closed trade and removes the position row."""
    exit_time = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        pos = conn.execute("SELECT * FROM position LIMIT 1").fetchone()
        if pos is None:
            log.warning("close_position called but no open position found")
            return
        conn.execute(
            "INSERT INTO trades (entry_time, exit_time, return_pct, exit_type, exit_price) "
            "VALUES (?, ?, ?, ?, ?)",
            (pos["entry_time"], exit_time, return_pct, exit_type, exit_price),
        )
        conn.execute("DELETE FROM position")
    price_str = f" @ {exit_price:.2f}" if exit_price else ""
    log.info(f"Position closed: {return_pct:+.4%} ({exit_type}){price_str}")


# ── Position sizing ──────────────────────────────────────────────────────────

def get_position_plan(capital: float) -> dict:
    """
    Returns the position sizing plan for the next trade.

    Currently uses a fixed 10% position size. When adaptive sizing
    is re-enabled for live trading, this function will compute it from
    the rolling trade log in state.db.
    """
    position_pct = 0.10
    position_dollars = capital * position_pct
    return {
        "position_pct": position_pct,
        "position_dollars": position_dollars,
    }


# ── Diagnostics ───────────────────────────────────────────────────────────────

def get_trade_summary() -> dict:
    with _conn() as conn:
        rows = conn.execute("SELECT return_pct, exit_type FROM trades").fetchall()
    if not rows:
        return {"total": 0}
    returns   = [r["return_pct"] for r in rows]
    win_rate  = sum(1 for r in returns if r > 0) / len(returns)
    total_ret = sum(returns)
    by_type   = {}
    for r in rows:
        by_type[r["exit_type"]] = by_type.get(r["exit_type"], 0) + 1
    return {
        "total":      len(returns),
        "win_rate":   win_rate,
        "total_ret":  total_ret,
        "exit_types": by_type,
    }
