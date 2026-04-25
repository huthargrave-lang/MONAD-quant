"""
src/research/fill_audit.py — Read-only fill audit for calibrating slippage.

Reads trade records from live/state.db (the live trading database where
the bot records actual fills) and computes slippage statistics between
intended and actual fill prices. Output can feed into autosweep.py for
realistic slippage assumptions.

Note: this reads from state.db, not directly from the IBKR API.
The bot's trader.py writes fill data to state.db during live operation.

Safety: ALL operations are read-only. No writes to state.db.
"""

import json
import sqlite3
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np


_DEFAULT_DB = Path(__file__).parent.parent.parent / "live" / "state.db"


@dataclass
class FillRecord:
    entry_time: str
    exit_time: str
    return_pct: float
    exit_type: str
    exit_price: Optional[float] = None
    symbol: Optional[str] = None
    qty: Optional[int] = None
    bars_held: Optional[int] = None


@dataclass
class SlippageStats:
    n_trades: int = 0
    mean_slippage_bps: float = 0.0
    median_slippage_bps: float = 0.0
    p75_slippage_bps: float = 0.0
    p95_slippage_bps: float = 0.0
    max_slippage_bps: float = 0.0
    target_hit_slippage_bps: float = 0.0
    stop_hit_slippage_bps: float = 0.0
    by_exit_type: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def read_trades(db_path: str = None, limit: int = 500) -> list[FillRecord]:
    """Read trade records from state.db. Read-only."""
    path = Path(db_path) if db_path else _DEFAULT_DB
    if not path.exists():
        return []

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM trades ORDER BY exit_time DESC LIMIT ?",
            (limit,),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()

    results = []
    for r in rows:
        d = dict(r)
        results.append(FillRecord(
            entry_time=d["entry_time"],
            exit_time=d["exit_time"],
            return_pct=d["return_pct"],
            exit_type=d["exit_type"],
            exit_price=d.get("exit_price"),
            symbol=d.get("symbol"),
            qty=d.get("qty"),
            bars_held=d.get("bars_held"),
        ))
    return results


def compute_slippage_stats(
    trades: list[FillRecord],
    expected_target_pct: float = 0.01,
    expected_stop_pct: float = 0.005,
) -> SlippageStats:
    """Compute slippage statistics from fill records.

    For target_hit trades: slippage = expected_target - actual_return
    For stop_hit trades: slippage = actual_loss - expected_stop
    Positive slippage = worse than expected (adverse).
    """
    if not trades:
        return SlippageStats()

    all_slippage = []
    by_type: dict[str, list[float]] = {}

    for t in trades:
        if t.exit_type == "target_hit":
            slip_pct = expected_target_pct - t.return_pct
        elif t.exit_type == "stop_hit":
            slip_pct = abs(t.return_pct) - expected_stop_pct
        else:
            continue

        slip_bps = slip_pct * 10000
        all_slippage.append(slip_bps)
        by_type.setdefault(t.exit_type, []).append(slip_bps)

    if not all_slippage:
        return SlippageStats(n_trades=len(trades))

    arr = np.array(all_slippage)
    target_slips = by_type.get("target_hit", [])
    stop_slips = by_type.get("stop_hit", [])

    type_summary = {}
    for etype, slips in by_type.items():
        a = np.array(slips)
        type_summary[etype] = {
            "count": len(slips),
            "mean_bps": round(float(a.mean()), 2),
            "median_bps": round(float(np.median(a)), 2),
            "p95_bps": round(float(np.percentile(a, 95)), 2),
        }

    return SlippageStats(
        n_trades=len(all_slippage),
        mean_slippage_bps=round(float(arr.mean()), 2),
        median_slippage_bps=round(float(np.median(arr)), 2),
        p75_slippage_bps=round(float(np.percentile(arr, 75)), 2),
        p95_slippage_bps=round(float(np.percentile(arr, 95)), 2),
        max_slippage_bps=round(float(arr.max()), 2),
        target_hit_slippage_bps=round(float(np.mean(target_slips)), 2) if target_slips else 0.0,
        stop_hit_slippage_bps=round(float(np.mean(stop_slips)), 2) if stop_slips else 0.0,
        by_exit_type=type_summary,
    )


def export_fill_audit(
    db_path: str = None,
    output_path: str = "live_fill_audit.json",
    expected_target_pct: float = 0.01,
    expected_stop_pct: float = 0.005,
    limit: int = 500,
) -> dict:
    """Export fill audit as JSON. Returns the audit dict."""
    trades = read_trades(db_path, limit)
    stats = compute_slippage_stats(trades, expected_target_pct, expected_stop_pct)

    audit = {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "db_path": str(db_path or _DEFAULT_DB),
        "total_trades_read": len(trades),
        "expected_target_pct": expected_target_pct,
        "expected_stop_pct": expected_stop_pct,
        "slippage_stats": stats.to_dict(),
        "exit_type_distribution": {},
    }

    type_counts: dict[str, int] = {}
    for t in trades:
        type_counts[t.exit_type] = type_counts.get(t.exit_type, 0) + 1
    audit["exit_type_distribution"] = type_counts

    if output_path:
        with open(output_path, "w") as f:
            json.dump(audit, f, indent=2, default=str)

    return audit


def get_slippage_for_autosweep(
    db_path: str = None,
    expected_target_pct: float = 0.01,
    expected_stop_pct: float = 0.005,
) -> float:
    """Return median slippage in decimal (e.g., 0.0003 = 3bps) for autosweep."""
    trades = read_trades(db_path, limit=200)
    if not trades:
        return 0.0002  # default 2bps if no data
    stats = compute_slippage_stats(trades, expected_target_pct, expected_stop_pct)
    return max(0.0, stats.median_slippage_bps / 10000)
