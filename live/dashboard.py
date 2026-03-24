"""Read-only monitoring dashboard for the live trading bot (v2 UI)."""

import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import plotly.graph_objects as go
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

import config
from live import state

DB_PATH = Path(__file__).parent / "state.db"
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app = FastAPI(title="MONAD Read-Only Monitor", version="2.0.0")


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


def _build_returns_chart(trades: list[dict]) -> str:
    rows = list(reversed(trades[-30:]))
    if not rows:
        return ""
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


def _build_exit_type_chart(exit_counts: dict[str, int]) -> str:
    if not exit_counts:
        return ""
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
    return fig.to_html(full_html=False, include_plotlyjs=False)


def _build_signal_chart(signal_history: list[dict]) -> str:
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
    return fig.to_html(full_html=False, include_plotlyjs=False)


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
    trades = state.get_recent_trades(limit=30)
    events = state.get_recent_monitor_events(limit=30)
    exit_counts = state.get_exit_type_counts(limit=250)
    account = state.get_account_snapshot()

    cycle_age_min = _minutes_ago(status.get("last_cycle_time") if status else None)
    cycle_text, cycle_color = _stale_band(cycle_age_min)

    signal_age_min = _minutes_ago(signal.get("updated_at") if signal else None)
    event_age_min = _minutes_ago(events[0]["event_time"]) if events else None
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

    latest_price = signal.get("bar_close") if signal else None
    position_view = None
    if position_dict:
        mode_name = f"{position_dict['symbol']}_HOURLY"
        target_pct = None
        stop_pct = None
        if mode_name in config.ASSETS:
            cfg = config.ASSETS[mode_name]
            target_pct = cfg.get("target_gain_pct")
            stop_pct = cfg.get("stop_loss_pct")

        entry_price = float(position_dict["entry_price"])
        target_price = entry_price * (1 + target_pct) if target_pct is not None else None
        stop_price = entry_price * (1 - stop_pct) if stop_pct is not None else None
        bars_remaining = max(0, config.MAX_TRADE_BARS_LIVE - int(position_dict["bar_count"]))

        unrealized_pct = None
        unrealized_dollar = None
        dist_target = None
        dist_stop = None
        if latest_price is not None:
            latest = float(latest_price)
            unrealized_pct = (latest - entry_price) / entry_price
            unrealized_dollar = (latest - entry_price) * int(position_dict["qty"])
            if target_price:
                dist_target = (target_price - latest) / latest
            if stop_price:
                dist_stop = (latest - stop_price) / latest

        position_view = {
            **position_dict,
            "bars_remaining": bars_remaining,
            "target_price": target_price,
            "stop_price": stop_price,
            "unrealized_pct": unrealized_pct,
            "unrealized_dollar": unrealized_dollar,
            "dist_target": dist_target,
            "dist_stop": dist_stop,
        }

    signal_badge = {1: ("LONG", "green"), 0: ("NO SIGNAL", "yellow"), -1: ("SHORT", "red")}.get(
        signal.get("signal") if signal else None,
        ("UNKNOWN", "red"),
    )

    returns_chart = Markup(_build_returns_chart(trades))
    exit_chart = Markup(_build_exit_type_chart(exit_counts))
    signal_chart = Markup(_build_signal_chart(signal_history))

    return TEMPLATES.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "generated_at": datetime.now(timezone.utc).isoformat(),
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
            "health_label": health_label,
            "health_color": health_color,
            "ibkr_connected": ibkr_connected,
            "trader_alive": trader_alive,
            "db_write_at": db_write_at,
            "db_age_min": db_age_min,
            "signal_age_min": signal_age_min,
            "event_age_min": event_age_min,
        },
    )
