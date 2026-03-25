"""Read-only monitoring dashboard for the live trading bot (v2 UI)."""

import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import plotly.graph_objects as go
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

import config
from live import state

DB_PATH = Path(__file__).parent / "state.db"
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
TEMPLATES.env.filters["commafy"] = lambda v, fmt="{:,.0f}": fmt.format(v) if v is not None else "—"

app = FastAPI(title="MONAD Read-Only Monitor", version="2.0.0")
UI_VERSION = "v2"

# Ensure DB schema is up-to-date (adds mark_price columns if missing).
# Safe to call multiple times — uses CREATE TABLE IF NOT EXISTS + ALTER TABLE migrations.
state.init_db()

# Valid production exit types — anything else is debug/test and filtered from charts
_PROD_EXIT_TYPES = {"target_hit", "stop_hit", "time_exit", "bracket_exit", "pending_close"}


def _filter_prod_trades(trades: list[dict]) -> list[dict]:
    """Exclude debug/test trades (e.g. cancelled_test) from production views."""
    return [t for t in trades if t.get("exit_type") in _PROD_EXIT_TYPES]


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _db_last_write_time() -> str | None:
    if not DB_PATH.exists():
        return None
    return datetime.fromtimestamp(DB_PATH.stat().st_mtime, tz=timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _minutes_ago(value: str | None) -> float | None:
    dt = _parse_iso(value)
    if dt is None:
        return None
    return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 60)


def _stale_band(minutes: float | None) -> tuple[str, str]:
    if minutes is None:
        return "Unknown", "red"
    if minutes <= 10:
        return f"last trader cycle {minutes:.0f} min ago", "green"
    if minutes <= 60:
        return f"last trader cycle {minutes:.0f} min ago", "yellow"
    return f"last trader cycle {minutes:.0f} min ago", "red"


def _get_git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(Path(__file__).parent.parent),
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


def _next_scheduled_run() -> str | None:
    """Compute next scheduled on_bar() fire time from cron: minute=32, hour=9-15, mon-fri ET."""
    try:
        et = ZoneInfo("America/New_York")
    except Exception:
        return None
    now = datetime.now(et)
    # Start from current hour at :32
    candidate = now.replace(minute=32, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(hours=1)
    # Search forward (covers weekends)
    for _ in range(7 * 24):
        if candidate.weekday() < 5 and 9 <= candidate.hour <= 15:
            return candidate.strftime("%a %H:%M ET")
        if candidate.hour > 15 or candidate.weekday() >= 5:
            # Jump to next day 9:32
            candidate = (candidate + timedelta(days=1)).replace(hour=9, minute=32)
        else:
            candidate = candidate.replace(hour=9, minute=32)
    return None


def _build_returns_chart(trades: list[dict]) -> str:
    rows = list(reversed(trades[-30:]))
    if len(rows) < 3:
        return ""  # Too few trades for a meaningful chart; template shows compact fallback
    colors = {
        "target": "#2ecc71",
        "stop": "#e74c3c",
        "time_exit": "#f1c40f",
        "pending_close": "#9b59b6",
        "ambiguous_same_bar": "#e67e22",
    }
    x = [r.get("exit_time") or r.get("entry_time") for r in rows]
    y = [float(r.get("return_pct") or 0.0) * 100 for r in rows]
    c = [colors.get(r.get("exit_type"), "#4aa3ff") for r in rows]
    fig = go.Figure(
        data=[
            go.Bar(
                x=x,
                y=y,
                marker_color=c,
                hovertemplate="%{x}<br>Return %{y:.3f}%<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        title="Recent Trade Returns (%)",
        paper_bgcolor="#121a2f",
        plot_bgcolor="#121a2f",
        font_color="#e8ecf6",
        margin=dict(l=30, r=20, t=40, b=30),
        height=300,
        xaxis_title="Exit time",
        yaxis_title="Return %",
    )
    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def _build_exit_type_chart(exit_counts: dict[str, int], needs_plotlyjs: bool = False) -> str:
    total = sum(exit_counts.values()) if exit_counts else 0
    if total < 3:
        return ""  # Too few trades for a meaningful donut
    labels = list(exit_counts.keys())
    values = [exit_counts[k] for k in labels]
    fig = go.Figure(
        data=[go.Pie(labels=labels, values=values, hole=0.45, textinfo="label+percent")]
    )
    fig.update_layout(
        title="Exit Type Breakdown",
        paper_bgcolor="#121a2f",
        plot_bgcolor="#121a2f",
        font_color="#e8ecf6",
        margin=dict(l=20, r=20, t=40, b=20),
        height=300,
    )
    return fig.to_html(full_html=False, include_plotlyjs="cdn" if needs_plotlyjs else False)


def _build_signal_chart(signal_history: list[dict], needs_plotlyjs: bool = False) -> str:
    rows = list(reversed(signal_history))
    if not rows:
        return ""
    x = [r.get("bar_time") or r.get("updated_at") for r in rows]
    y = [r.get("signal") for r in rows]
    fig = go.Figure(data=[go.Scatter(x=x, y=y, mode="lines+markers", line_color="#4aa3ff")])
    fig.update_layout(
        title="Signal Snapshot History",
        paper_bgcolor="#121a2f",
        plot_bgcolor="#121a2f",
        font_color="#e8ecf6",
        margin=dict(l=30, r=20, t=40, b=30),
        height=240,
        xaxis_title="Timestamp",
        yaxis_title="Signal",
    )
    return fig.to_html(full_html=False, include_plotlyjs="cdn" if needs_plotlyjs else False)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "utc": datetime.now(timezone.utc).isoformat()}


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    status = state.get_monitor_status()
    signal = state.get_signal_snapshot()
    signal_history = state.get_signal_history(limit=20)
    position = state.get_position()
    position_dict = position.__dict__ if position else None
    all_trades = state.get_recent_trades(limit=50)
    trades = _filter_prod_trades(all_trades)[:30]
    events = state.get_recent_monitor_events(limit=30)
    all_exit_counts = state.get_exit_type_counts(limit=250)
    exit_counts = {k: v for k, v in all_exit_counts.items() if k in _PROD_EXIT_TYPES}
    account = state.get_account_snapshot()
    freshness = state.get_dashboard_freshness_status()

    cycle_age_min = _minutes_ago(freshness.get("last_cycle_time"))
    cycle_text, cycle_color = _stale_band(cycle_age_min)

    signal_age_min = _minutes_ago(freshness.get("last_signal_time"))
    event_age_min = _minutes_ago(freshness.get("last_event_time"))
    broker_sync_age_min = _minutes_ago(freshness.get("last_broker_sync_time"))
    db_write_at = _db_last_write_time()
    db_age_min = _minutes_ago(db_write_at)

    ibkr_connected = bool(account and account.get("ibkr_connected"))
    trader_alive = cycle_age_min is not None and cycle_age_min <= 20

    if status and status.get("status") == "error":
        health_label, health_color = "Error", "red"
    elif trader_alive:
        health_label, health_color = "Healthy", "green"
    elif cycle_age_min is not None and cycle_age_min <= 60:
        health_label, health_color = "Stale", "yellow"
    else:
        health_label, health_color = "Stale", "red"

    # ── Resolve mark price: account_snapshot (broker-sourced) > signal bar_close > entry_price ─
    mark_price = None
    mark_source = "unavailable"
    mark_time = None
    if account:
        mp = account.get("mark_price")
        ms = account.get("mark_source")
        mt = account.get("mark_time")
        if mp is not None and float(mp) > 0:
            mark_price = float(mp)
            mark_source = ms or "live"
            mark_time = mt
    # Fallback 1: use signal bar_close
    if mark_price is None and signal and signal.get("bar_close"):
        bc = signal["bar_close"]
        if bc is not None and float(bc) > 0:
            mark_price = float(bc)
            mark_source = "last_close"
            mark_time = signal.get("updated_at")
    # Fallback 2: use estimated_exit_price for pending_close positions
    if mark_price is None and position_dict and position_dict.get("status") == "pending_close":
        eep = position_dict.get("estimated_exit_price")
        if eep is not None and float(eep) > 0:
            mark_price = float(eep)
            mark_source = "estimated"
            mark_time = None

    # Fallback 3: use entry_price from position (always available when position exists)
    if mark_price is None and position_dict:
        ep = position_dict.get("entry_price")
        if ep is not None and float(ep) > 0:
            mark_price = float(ep)
            mark_source = "entry"
            mark_time = position_dict.get("entry_time")

    position_view = None
    if position_dict:
        # Try the active mode's asset key first, then fall back to symbol_HOURLY / symbol
        asset_key = config.DEFAULT_ASSET
        symbol = position_dict["symbol"]
        if asset_key not in config.ASSETS:
            for candidate in [f"{symbol}_HOURLY", symbol]:
                if candidate in config.ASSETS:
                    asset_key = candidate
                    break
        target_pct = None
        stop_pct = None
        if asset_key in config.ASSETS:
            cfg = config.ASSETS[asset_key]
            target_pct = cfg.get("target_gain_pct")
            stop_pct = cfg.get("stop_loss_pct")

        entry_price = float(position_dict["entry_price"])
        qty = int(position_dict["qty"])
        target_price = entry_price * (1 + target_pct) if target_pct is not None else None
        stop_price = entry_price * (1 - stop_pct) if stop_pct is not None else None
        bars_remaining = max(0, config.MAX_TRADE_BARS_LIVE - int(position_dict["bar_count"]))

        unrealized_pct = None
        unrealized_dollar = None
        dist_target = None
        dist_stop = None
        if mark_price is not None:
            unrealized_pct = (mark_price - entry_price) / entry_price
            unrealized_dollar = (mark_price - entry_price) * qty
            if target_price:
                dist_target = (target_price - mark_price) / mark_price
            if stop_price:
                dist_stop = (mark_price - stop_price) / mark_price

        position_view = {
            **position_dict,
            "bars_remaining": bars_remaining,
            "target_price": target_price,
            "stop_price": stop_price,
            "mark_price": mark_price,
            "mark_source": mark_source,
            "mark_time": mark_time,
            "unrealized_pct": unrealized_pct,
            "unrealized_dollar": unrealized_dollar,
            "dist_target": dist_target,
            "dist_stop": dist_stop,
            "cost_basis_total": entry_price * qty,
            "market_value": mark_price * qty if mark_price else None,
        }

    signal_badge = {1: ("LONG", "green"), 0: ("NO SIGNAL", "yellow"), -1: ("SHORT", "red")}.get(
        signal.get("signal") if signal else None,
        ("UNKNOWN", "red"),
    )

    returns_chart = Markup(_build_returns_chart(trades))
    exit_chart_needs_js = not returns_chart
    exit_chart = Markup(_build_exit_type_chart(exit_counts, needs_plotlyjs=exit_chart_needs_js))
    signal_chart_needs_js = not returns_chart and not exit_chart
    signal_chart = Markup(_build_signal_chart(signal_history, needs_plotlyjs=signal_chart_needs_js))

    return TEMPLATES.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ui_version": UI_VERSION,
            "git_hash": _get_git_hash(),
            "status": status,
            "signal": signal,
            "signal_badge": signal_badge,
            "position": position_view,
            "account": account,
            "trades": trades,
            "events": events,
            "signal_history": signal_history,
            "exit_counts": exit_counts,
            "returns_chart": returns_chart,
            "exit_chart": exit_chart,
            "signal_chart": signal_chart,
            "cycle_age_min": cycle_age_min,
            "cycle_text": cycle_text,
            "cycle_color": cycle_color,
            "next_run": _next_scheduled_run(),
            "health_label": health_label,
            "health_color": health_color,
            "ibkr_connected": ibkr_connected,
            "trader_alive": trader_alive,
            "db_write_at": db_write_at,
            "db_age_min": db_age_min,
            "signal_age_min": signal_age_min,
            "event_age_min": event_age_min,
            "broker_sync_age_min": broker_sync_age_min,
        },
    )
