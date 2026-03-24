"""
live/state.py — SQLite-backed persistence for open position and trade log.

Tables:
  position         — zero or one row (the currently open trade)
  trades           — append-only log of closed trades
  monitor_status   — singleton row with latest heartbeat/status metadata
  signal_snapshot  — latest computed signal payload
  signal_history   — append-only signal snapshots for monitoring charts
  monitor_events   — append-only recent operational events/warnings
  account_snapshot — latest IBKR/account snapshot from trader process
"""

import sqlite3
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import config

log = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent / "state.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist and apply additive migrations."""
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
                exit_price  REAL,
                symbol      TEXT,
                qty         INTEGER,
                bars_held   INTEGER
            );

            CREATE TABLE IF NOT EXISTS monitor_status (
                id                  INTEGER PRIMARY KEY CHECK (id = 1),
                last_cycle_time     TEXT,
                status              TEXT,
                cycle_action        TEXT,
                details             TEXT,
                live_symbol         TEXT,
                live_paper_mode     INTEGER,
                live_dry_run        INTEGER
            );

            CREATE TABLE IF NOT EXISTS signal_snapshot (
                id                  INTEGER PRIMARY KEY CHECK (id = 1),
                updated_at          TEXT,
                signal              INTEGER,
                bar_time            TEXT,
                bar_close           REAL,
                rsi                 REAL,
                vwap_zscore         REAL,
                momentum_signal     INTEGER,
                volume_signal       INTEGER
            );

            CREATE TABLE IF NOT EXISTS signal_history (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                updated_at          TEXT,
                signal              INTEGER,
                bar_time            TEXT,
                bar_close           REAL,
                rsi                 REAL,
                vwap_zscore         REAL,
                momentum_signal     INTEGER,
                volume_signal       INTEGER
            );

            CREATE TABLE IF NOT EXISTS monitor_events (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                event_time          TEXT NOT NULL,
                level               TEXT NOT NULL,
                category            TEXT NOT NULL,
                message             TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS account_snapshot (
                id                  INTEGER PRIMARY KEY CHECK (id = 1),
                updated_at          TEXT,
                equity              REAL,
                cash                REAL,
                buying_power        REAL,
                position_value      REAL,
                ibkr_connected      INTEGER
            );
        """)

        # Additive migrations for existing DBs.
        existing_trade_cols = {
            row["name"] for row in conn.execute("PRAGMA table_info(trades)").fetchall()
        }
        if "symbol" not in existing_trade_cols:
            conn.execute("ALTER TABLE trades ADD COLUMN symbol TEXT")
        if "qty" not in existing_trade_cols:
            conn.execute("ALTER TABLE trades ADD COLUMN qty INTEGER")
        if "bars_held" not in existing_trade_cols:
            conn.execute("ALTER TABLE trades ADD COLUMN bars_held INTEGER")
        if "exit_price" not in existing_trade_cols:
            conn.execute("ALTER TABLE trades ADD COLUMN exit_price REAL")

        existing_signal_cols = {
            row["name"] for row in conn.execute("PRAGMA table_info(signal_snapshot)").fetchall()
        }
        for col, ctype in [
            ("rsi", "REAL"),
            ("vwap_zscore", "REAL"),
            ("momentum_signal", "INTEGER"),
            ("volume_signal", "INTEGER"),
        ]:
            if col not in existing_signal_cols:
                conn.execute(f"ALTER TABLE signal_snapshot ADD COLUMN {col} {ctype}")


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
        conn.execute("DELETE FROM position")
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
            """
            INSERT INTO trades (
                entry_time, exit_time, return_pct, exit_type, exit_price,
                symbol, qty, bars_held
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pos["entry_time"],
                exit_time,
                return_pct,
                exit_type,
                exit_price,
                pos["symbol"],
                pos["qty"],
                pos["bar_count"],
            ),
        )
        conn.execute("DELETE FROM position")
    price_str = f" @ {exit_price:.2f}" if exit_price else ""
    log.info(f"Position closed: {return_pct:+.4%} ({exit_type}){price_str}")


# ── Position sizing ──────────────────────────────────────────────────────────

def get_position_plan(capital: float) -> dict:
    """Returns the position sizing plan for the next trade (fixed 10%)."""
    position_pct = 0.10
    position_dollars = capital * position_pct
    return {
        "position_pct": position_pct,
        "position_dollars": position_dollars,
    }


# ── Diagnostics / monitor helpers ────────────────────────────────────────────

def get_trade_summary() -> dict:
    with _conn() as conn:
        rows = conn.execute("SELECT return_pct, exit_type FROM trades").fetchall()
    if not rows:
        return {"total": 0}
    returns = [r["return_pct"] for r in rows]
    win_rate = sum(1 for r in returns if r > 0) / len(returns)
    total_ret = sum(returns)
    by_type = {}
    for r in rows:
        by_type[r["exit_type"]] = by_type.get(r["exit_type"], 0) + 1
    return {
        "total": len(returns),
        "win_rate": win_rate,
        "total_ret": total_ret,
        "exit_types": by_type,
    }


def get_recent_trades(limit: int = 20) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM trades
            ORDER BY exit_time DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    normalized_rows = []
    for row in rows:
        r = dict(row)
        normalized_rows.append(
            {
                "entry_time": r.get("entry_time"),
                "exit_time": r.get("exit_time"),
                "return_pct": r.get("return_pct"),
                "exit_type": r.get("exit_type"),
                "exit_price": r.get("exit_price"),
                "symbol": r.get("symbol"),
                "qty": r.get("qty"),
                "bars_held": r.get("bars_held"),
            }
        )
    return normalized_rows


def get_exit_type_counts(limit: int = 250) -> dict[str, int]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT exit_type, COUNT(*) AS c
            FROM (
                SELECT exit_type FROM trades ORDER BY exit_time DESC LIMIT ?
            ) t
            GROUP BY exit_type
            """,
            (limit,),
        ).fetchall()
    return {r["exit_type"]: r["c"] for r in rows}


def set_monitor_status(status: str, cycle_action: str, details: str = "") -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO monitor_status (
                id, last_cycle_time, status, cycle_action, details,
                live_symbol, live_paper_mode, live_dry_run
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                last_cycle_time = excluded.last_cycle_time,
                status = excluded.status,
                cycle_action = excluded.cycle_action,
                details = excluded.details,
                live_symbol = excluded.live_symbol,
                live_paper_mode = excluded.live_paper_mode,
                live_dry_run = excluded.live_dry_run
            """,
            (
                now,
                status,
                cycle_action,
                details,
                config.LIVE_SYMBOL,
                int(bool(config.LIVE_PAPER_MODE)),
                int(bool(getattr(config, "LIVE_DRY_RUN", False))),
            ),
        )


def get_monitor_status() -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM monitor_status WHERE id = 1").fetchone()
    return dict(row) if row else None


def save_signal_snapshot(
    signal: int,
    bar_time: str,
    bar_close: float,
    rsi: float | None = None,
    vwap_zscore: float | None = None,
    momentum_signal: int | None = None,
    volume_signal: int | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO signal_snapshot (
                id, updated_at, signal, bar_time, bar_close,
                rsi, vwap_zscore, momentum_signal, volume_signal
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                updated_at = excluded.updated_at,
                signal = excluded.signal,
                bar_time = excluded.bar_time,
                bar_close = excluded.bar_close,
                rsi = excluded.rsi,
                vwap_zscore = excluded.vwap_zscore,
                momentum_signal = excluded.momentum_signal,
                volume_signal = excluded.volume_signal
            """,
            (
                now,
                signal,
                str(bar_time),
                bar_close,
                rsi,
                vwap_zscore,
                momentum_signal,
                volume_signal,
            ),
        )
        conn.execute(
            """
            INSERT INTO signal_history (
                updated_at, signal, bar_time, bar_close,
                rsi, vwap_zscore, momentum_signal, volume_signal
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now,
                signal,
                str(bar_time),
                bar_close,
                rsi,
                vwap_zscore,
                momentum_signal,
                volume_signal,
            ),
        )


def get_signal_snapshot() -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM signal_snapshot WHERE id = 1").fetchone()
    return dict(row) if row else None


def get_signal_history(limit: int = 20) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT updated_at, signal, bar_time, bar_close, rsi,
                   vwap_zscore, momentum_signal, volume_signal
            FROM signal_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def add_monitor_event(level: str, category: str, message: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO monitor_events (event_time, level, category, message) VALUES (?, ?, ?, ?)",
            (now, level.upper(), category, message),
        )


def get_recent_monitor_events(limit: int = 25) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT event_time, level, category, message FROM monitor_events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def save_account_snapshot(
    *,
    equity: float | None,
    cash: float | None,
    buying_power: float | None = None,
    position_value: float | None = None,
    ibkr_connected: bool = True,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO account_snapshot (
                id, updated_at, equity, cash, buying_power, position_value, ibkr_connected
            )
            VALUES (1, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                updated_at = excluded.updated_at,
                equity = excluded.equity,
                cash = excluded.cash,
                buying_power = excluded.buying_power,
                position_value = excluded.position_value,
                ibkr_connected = excluded.ibkr_connected
            """,
            (
                now,
                equity,
                cash,
                buying_power,
                position_value,
                1 if ibkr_connected else 0,
            ),
        )


def get_account_snapshot() -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM account_snapshot WHERE id = 1").fetchone()
    return dict(row) if row else None


def get_dashboard_freshness_status() -> dict:
    """Return lightweight freshness metrics for read-only dashboard health cards."""
    status = get_monitor_status()
    signal = get_signal_snapshot()
    events = get_recent_monitor_events(limit=1)
    account = get_account_snapshot()

    return {
        "last_cycle_time": status.get("last_cycle_time") if status else None,
        "last_signal_time": signal.get("updated_at") if signal else None,
        "last_event_time": events[0]["event_time"] if events else None,
        "last_broker_sync_time": account.get("updated_at") if account else None,
    }
