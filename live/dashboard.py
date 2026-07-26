"""Read-only monitoring dashboard for the live trading bot (v2 UI).

PRESENTATION ONLY below the data layer: this module reads `live/state.db`, builds
figures, and renders a template. It places no orders, holds no position state, and is
never in the trading path.

Its palette comes from `tools/ui_tokens.py` — the same one every other HTML surface in
this repository uses (F232/F233). Two layers, because a plotting library and a
stylesheet reach colour differently:

* **CSS** — the tokens are passed into the template and the page's historic variable
  names (`--bg`, `--panel`, `--text`, …) are aliased onto them, so the ~200 lines of
  layout below the alias block are untouched.
* **Figures** — plotly bakes literal colours into the figure at build time and cannot
  read a custom property, so series colours come from `ui_tokens.PLOT` (validated
  against BOTH card grounds) while the chart CHROME — background, font, grid, tick,
  zero-line, marker ring — is left neutral here and pushed in by the page at run time
  from the resolved variables. A server cannot know the viewer's theme; the page can.
"""

import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import plotly.graph_objects as go
import yfinance as yf
from plotly.offline.offline import get_plotlyjs_version
from plotly.subplots import make_subplots
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

import config
from live import state
from src.analysis import run_window

_TOOLS = str(Path(__file__).resolve().parents[1] / "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)
import ui_tokens  # noqa: E402  — the one palette; see F233

PLOT = ui_tokens.PLOT

DB_PATH = Path(__file__).parent / "state.db"
# Optional "current run" marker (gitignored runtime). When present, history
# sections default to rows at/after its started_at. Absent → behaves as before.
RUN_MARKER_PATH = Path(__file__).parent.parent / "local_runtime" / "current_run.json"
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
TEMPLATES.env.filters["commafy"] = lambda v, fmt="{:,.0f}": fmt.format(v) if v is not None else "—"

app = FastAPI(title="MONAD Read-Only Monitor", version="2.0.0")
UI_VERSION = "v2"

# Ensure DB schema is up-to-date (adds mark_price columns if missing).
# Safe to call multiple times — uses CREATE TABLE IF NOT EXISTS + ALTER TABLE migrations.
state.init_db()

# Valid production exit types — anything else is debug/test and filtered from charts
_PROD_EXIT_TYPES = {"target_hit", "stop_hit", "time_exit", "bracket_exit", "pending_close"}
_UI_QUOTE_CACHE_TTL_SEC = 2.5
_UI_QUOTE_STALE_OK_SEC = 60.0
_UI_QUOTE_HEADERS = {"Cache-Control": "no-store, max-age=0"}
_PLOTLY_JS_URL = f"https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js"
_MARKET_TZ = ZoneInfo("America/New_York")
_ui_quote_cache: dict[str, dict[str, float | str]] = {}


def _filter_prod_trades(trades: list[dict]) -> list[dict]:
    """Exclude debug/test trades (e.g. cancelled_test) from production views."""
    return [t for t in trades if t.get("exit_type") in _PROD_EXIT_TYPES]


def _summarize_trades(trades: list[dict]) -> dict:
    if not trades:
        return {"total": 0, "win_rate": 0.0, "total_ret": 0.0, "exit_types": {}}

    returns = [float(t.get("return_pct") or 0.0) for t in trades]
    win_rate = sum(1 for ret in returns if ret > 0) / len(returns)
    total_ret = 1.0
    for ret in returns:
        total_ret *= (1.0 + ret)
    total_ret -= 1.0

    exit_types: dict[str, int] = {}
    for trade in trades:
        exit_type = trade.get("exit_type") or "unknown"
        exit_types[exit_type] = exit_types.get(exit_type, 0) + 1

    return {
        "total": len(returns),
        "win_rate": win_rate,
        "total_ret": total_ret,
        "exit_types": exit_types,
    }


def _coerce_price(value) -> float | None:
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    return price if price > 0 else None


def _coerce_timestamp(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    # live/signals.py stores yfinance hourly bars as UTC-naive timestamps
    # (`tz_convert(None)`), so normalize them into New York market time for UI use.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_MARKET_TZ).replace(tzinfo=None)


def _get_cached_ui_quote(symbol: str, max_age_sec: float) -> dict | None:
    cached = _ui_quote_cache.get(symbol)
    if not cached:
        return None
    fetched_monotonic = _coerce_price(cached.get("fetched_monotonic"))
    if fetched_monotonic is None:
        return None
    age_sec = time.monotonic() - fetched_monotonic
    if age_sec > max_age_sec:
        return None
    return {
        "symbol": symbol,
        "price": cached["price"],
        "source": cached["source"],
        "fetched_at": cached["fetched_at"],
        "stale": bool(cached.get("stale", False)),
    }


def _store_ui_quote(symbol: str, price: float, source: str, *, stale: bool = False) -> dict:
    quote = {
        "price": price,
        "source": source,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "fetched_monotonic": time.monotonic(),
        "stale": stale,
    }
    _ui_quote_cache[symbol] = quote
    return {
        "symbol": symbol,
        "price": price,
        "source": source,
        "fetched_at": quote["fetched_at"],
        "stale": stale,
    }


def _fetch_ui_quote(symbol: str) -> tuple[float, str]:
    ticker = yf.Ticker(symbol)
    fast_info = getattr(ticker, "fast_info", None)
    if fast_info is not None:
        for candidate in (
            getattr(fast_info, "last_price", None),
            fast_info.get("lastPrice") if hasattr(fast_info, "get") else None,
            fast_info.get("regularMarketPreviousClose") if hasattr(fast_info, "get") else None,
        ):
            price = _coerce_price(candidate)
            if price is not None:
                return price, "yfinance_fast"

    info = getattr(ticker, "info", {}) or {}
    price = _coerce_price(info.get("regularMarketPrice"))
    if price is not None:
        return price, "yfinance_info"

    from live.broker import _yfinance_fallback

    return _yfinance_fallback(symbol), "yfinance_close"


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


def _resolve_asset_config(symbol: str | None = None) -> tuple[str | None, dict | None]:
    candidates = [config.DEFAULT_ASSET]
    if symbol:
        candidates.extend([f"{symbol}_HOURLY", symbol])

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        cfg = config.ASSETS.get(candidate)
        if cfg is not None:
            return candidate, cfg
    return None, None


def _figure_to_html(fig: go.Figure, *, div_id: str) -> str:
    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        div_id=div_id,
        config={
            "displayModeBar": False,
            "displaylogo": False,
            "scrollZoom": True,
            "responsive": True,
        },
        default_width="100%",
    )


def _build_returns_chart(trades: list[dict]) -> str:
    if not trades:
        return ""
    rows = [dict(r) for r in trades]
    if len(rows) < 3:
        return ""

    rows.sort(key=lambda r: r.get("exit_time") or r.get("entry_time") or "")
    x = []
    cumulative = []
    custom = []
    marker_colors = []
    equity = 1.0
    for row in rows:
        ts = row.get("exit_time") or row.get("entry_time")
        ret = float(row.get("return_pct") or 0.0)
        equity *= (1.0 + ret)
        x.append(ts)
        cumulative.append((equity - 1.0) * 100.0)
        custom.append([ret * 100.0, row.get("exit_type") or "unknown"])
        marker_colors.append(PLOT["gain"] if ret >= 0 else PLOT["loss"])

    line_color = PLOT["gain"] if cumulative[-1] >= 0 else PLOT["loss"]
    fill_color = ui_tokens.plot_rgba(
        "gain" if cumulative[-1] >= 0 else "loss", 0.12)
    hovertemplate = (
        "%{x}<br>Cumulative %{y:.2f}%"
        "<br>Trade %{customdata[0]:+.3f}%"
        "<br>%{customdata[1]}<extra></extra>"
    )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x,
            y=cumulative,
            mode="lines",
            fill="tozeroy",
            line=dict(color=line_color, width=2),
            fillcolor=fill_color,
            customdata=custom,
            hovertemplate=hovertemplate,
            name="Equity Curve",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=cumulative,
            mode="markers",
            marker=dict(color=marker_colors, size=7,
                        line=dict(color=PLOT["transparent"], width=1)),
            customdata=custom,
            hovertemplate=hovertemplate,
            showlegend=False,
        )
    )
    fig.update_layout(
        title="Cumulative Equity Curve",
        paper_bgcolor=PLOT["transparent"],
        plot_bgcolor=PLOT["transparent"],
        font_color=PLOT["ink"],
        margin=dict(l=60, r=20, t=40, b=50),
        height=300,
        xaxis_title="Exit time",
        yaxis_title="Compounded return %",
        hovermode="x unified",
        showlegend=False,
    )
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)
    return _figure_to_html(fig, div_id="returns-chart")


def _build_trade_scatter_chart(trades: list[dict]) -> str:
    points = []
    for trade in trades:
        bars_held = trade.get("bars_held")
        return_pct = trade.get("return_pct")
        if bars_held is None or return_pct is None:
            continue
        try:
            points.append(
                {
                    "bars_held": int(bars_held),
                    "return_pct": float(return_pct) * 100.0,
                    "symbol": trade.get("symbol") or "—",
                    "exit_type": trade.get("exit_type") or "unknown",
                    "exit_time": trade.get("exit_time") or "—",
                }
            )
        except (TypeError, ValueError):
            continue

    if not points:
        return ""

    x_bars = [point["bars_held"] for point in points]
    y_rets = [point["return_pct"] for point in points]
    colors = [PLOT["gain"] if ret >= 0 else PLOT["loss"] for ret in y_rets]
    custom = [[point["symbol"], point["exit_type"], point["exit_time"]] for point in points]

    fig = go.Figure()

    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color=ui_tokens.PLOT_AXIS,
        line_width=2,
    )
    fig.add_trace(
        go.Scatter(
            x=x_bars,
            y=y_rets,
            mode="markers",
            marker=dict(
                size=12,
                color=colors,
                opacity=0.85,
                line=dict(width=1.5, color=PLOT["transparent"]),
            ),
            customdata=custom,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Return: %{y:+.2f}%<br>"
                "Duration: %{x} bars<br>"
                "Exit: %{customdata[1]}<br>"
                "Closed: %{customdata[2]}<extra></extra>"
            ),
            showlegend=False,
        )
    )
    fig.update_layout(
        title="Trade Efficiency",
        paper_bgcolor=PLOT["transparent"],
        plot_bgcolor=PLOT["transparent"],
        font_color=PLOT["ink"],
        margin=dict(l=60, r=20, t=40, b=40),
        height=300,
        xaxis_title="Duration (Bars)",
        yaxis_title="Return (%)",
        hovermode="closest",
    )
    max_x = max(x_bars) if x_bars else 10
    fig.update_xaxes(
        automargin=True,
        range=[-1, max_x + (max_x * 0.1)],
        gridcolor=ui_tokens.PLOT_GRID,
        zeroline=False,
    )
    fig.update_yaxes(
        automargin=True,
        gridcolor=ui_tokens.PLOT_GRID,
        zeroline=False,
    )
    return _figure_to_html(fig, div_id="trade-scatter-chart")


def _build_signal_chart(
    signal_history: list[dict],
    *,
    position: dict | None = None,
    asset_label: str | None = None,
    rsi_oversold: float | None = None,
    rsi_overbought: float | None = None,
) -> str:
    if not signal_history:
        return ""

    # signal_history is fetched by insertion id, but live snapshots can contain
    # duplicate or slightly delayed bar_time values. Sort and de-dup by actual
    # bar timestamp so the plotted line never folds backward in time.
    deduped_rows: dict[str, dict] = {}
    for row in reversed(signal_history):
        raw_x = row.get("bar_time") or row.get("updated_at")
        parsed_x = _coerce_timestamp(raw_x)
        dedupe_key = parsed_x.isoformat() if parsed_x is not None else str(raw_x)
        deduped_rows[dedupe_key] = {
            **row,
            "_chart_x": parsed_x or raw_x,
            "_chart_dt": parsed_x,
        }

    rows = sorted(
        deduped_rows.values(),
        key=lambda row: (
            row.get("_chart_dt") is None,
            row.get("_chart_dt") or datetime.max,
            str(row.get("_chart_x")),
        ),
    )
    if not rows:
        return ""

    x = [r.get("_chart_x") for r in rows]
    close = [r.get("bar_close") for r in rows]
    rsi = [r.get("rsi") for r in rows]
    signals = [r.get("signal") for r in rows]
    use_market_session_breaks = not (asset_label or "").upper().startswith("BTC")

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.72, 0.28],
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=close,
            mode="lines",
            name="Close",
            line=dict(color=PLOT["price"], width=2),
            hovertemplate="%{x}<br>Close $%{y:.2f}<extra></extra>",
        ),
        row=1,
        col=1,
    )

    if position:
        entry_price = _coerce_price(position.get("entry_price"))
        target_price = _coerce_price(position.get("target_price"))
        stop_price = _coerce_price(position.get("stop_price"))

        if target_price is not None:
            fig.add_hline(
                y=target_price,
                line_dash="dash",
                line_color=ui_tokens.plot_rgba("gain", 0.70),
                annotation_text=f"Target ${target_price:.2f}",
                annotation_position="top right",
                row=1,
                col=1,
            )
        if entry_price is not None:
            fig.add_hline(
                y=entry_price,
                line_dash="dot",
                line_color=ui_tokens.PLOT_AXIS,
                annotation_text=f"Entry ${entry_price:.2f}",
                annotation_position="top left",
                row=1,
                col=1,
            )
        if stop_price is not None:
            fig.add_hline(
                y=stop_price,
                line_dash="dash",
                line_color=ui_tokens.plot_rgba("loss", 0.70),
                annotation_text=f"Stop ${stop_price:.2f}",
                annotation_position="bottom right",
                row=1,
                col=1,
            )

    long_x, long_y, short_x, short_y = [], [], [], []
    for idx, sig in enumerate(signals):
        price = close[idx]
        if price is None or sig is None:
            continue
        if sig > 0:
            long_x.append(x[idx])
            long_y.append(price)
        elif sig < 0:
            short_x.append(x[idx])
            short_y.append(price)

    if long_x:
        fig.add_trace(
            go.Scatter(
                x=long_x,
                y=long_y,
                mode="markers",
                name="LONG",
                marker=dict(symbol="triangle-up", color=PLOT["gain"], size=12),
                hovertemplate="%{x}<br>LONG @ $%{y:.2f}<extra></extra>",
            ),
            row=1,
            col=1,
        )
    if short_x:
        fig.add_trace(
            go.Scatter(
                x=short_x,
                y=short_y,
                mode="markers",
                name="SHORT",
                marker=dict(symbol="triangle-down", color=PLOT["loss"], size=12),
                hovertemplate="%{x}<br>SHORT @ $%{y:.2f}<extra></extra>",
            ),
            row=1,
            col=1,
        )

    fig.add_trace(
        go.Scatter(
            x=x,
            y=rsi,
            mode="lines",
            name="RSI",
            line=dict(color=PLOT["rsi"], width=2),
            hovertemplate="%{x}<br>RSI %{y:.2f}<extra></extra>",
        ),
        row=2,
        col=1,
    )

    # Neutral momentum reference line. Keep the strategy-specific thresholds too,
    # since entries are still governed by the actual configured RSI levels.
    fig.add_hline(
        y=50,
        line_dash="dot",
        line_color=ui_tokens.PLOT_AXIS,
        row=2,
        col=1,
    )

    if rsi_oversold is not None:
        fig.add_hline(
            y=rsi_oversold,
            line_dash="dash",
            line_color=ui_tokens.plot_rgba("gain", 0.55),
            annotation_text=f"Bot Long Limit ({rsi_oversold:g})",
            annotation_position="top left",
            row=2,
            col=1,
        )
    if rsi_overbought is not None:
        fig.add_hline(
            y=rsi_overbought,
            line_dash="dash",
            line_color=ui_tokens.plot_rgba("loss", 0.55),
            annotation_text=f"Bot Short Limit ({rsi_overbought:g})",
            annotation_position="bottom left",
            row=2,
            col=1,
        )

    fig.update_layout(
        title=f"{asset_label or 'Signal'} Price Action & RSI",
        paper_bgcolor=PLOT["transparent"],
        plot_bgcolor=PLOT["transparent"],
        font_color=PLOT["ink"],
        margin=dict(l=60, r=20, t=40, b=30),
        height=450,
        showlegend=False,
        hovermode="x unified",
    )
    xaxis_kwargs = {"showgrid": False, "automargin": True}
    if use_market_session_breaks:
        xaxis_kwargs["rangebreaks"] = [
            dict(bounds=["sat", "mon"]),
            dict(pattern="hour", bounds=[16, 9.5]),
        ]
    fig.update_xaxes(**xaxis_kwargs)
    fig.update_yaxes(
        title_text="Price",
        gridcolor=ui_tokens.PLOT_GRID,
        zeroline=False,
        automargin=True,
        row=1,
        col=1,
    )
    fig.update_yaxes(
        title_text="RSI",
        range=[0, 100],
        gridcolor=ui_tokens.PLOT_GRID,
        zeroline=False,
        automargin=True,
        row=2,
        col=1,
    )
    return _figure_to_html(fig, div_id="signal-history-chart")


def _build_position_gauge(position: dict | None) -> str:
    if not position:
        return ""

    mark = position.get("mark_price")
    entry = position.get("entry_price")
    target = position.get("target_price")
    stop = position.get("stop_price")
    if None in (mark, entry, target, stop):
        return ""

    mark = float(mark)
    entry = float(entry)
    target = float(target)
    stop = float(stop)
    lower = min(stop, entry, target, mark)
    upper = max(stop, entry, target, mark)
    if lower == upper:
        pad = abs(lower) * 0.01 if lower else 1.0
        lower -= pad
        upper += pad
    range_span = upper - lower
    line_half_width = max(range_span * 0.0025, 1e-6)

    fig = go.Figure(
        go.Indicator(
            mode="gauge",
            value=mark,
            # The mark price is already shown in the position table above.
            # Use the full width here for the risk/reward visualization.
            domain={"x": [0.02, 0.98], "y": [0, 1]},
            gauge={
                "shape": "bullet",
                "axis": {"range": [lower, upper], "tickcolor": PLOT["ink"]},
                "threshold": {
                    "line": {"color": PLOT["price"], "width": 4},
                    "thickness": 0.8,
                    "value": mark,
                },
                "steps": [
                    {"range": [stop, entry], "color": ui_tokens.plot_rgba("loss", 0.25)},
                    {"range": [entry - line_half_width,
                               entry + line_half_width], "color": PLOT["ink"]},
                    {"range": [entry, target], "color": ui_tokens.plot_rgba("gain", 0.25)},
                ],
                "bar": {"color": "rgba(0,0,0,0)", "thickness": 0},
            },
        )
    )
    fig.update_layout(
        paper_bgcolor=PLOT["transparent"],
        plot_bgcolor=PLOT["transparent"],
        font_color=PLOT["ink"],
        margin=dict(t=20, b=20, l=10, r=20),
        height=120,
    )
    return _figure_to_html(fig, div_id="position-gauge-chart")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "utc": datetime.now(timezone.utc).isoformat()}


@app.get("/api/ticker/{symbol}", response_class=JSONResponse)
def get_live_ticker(symbol: str) -> JSONResponse:
    symbol = symbol.strip().upper()
    if not symbol:
        return JSONResponse(
            content={"error": "symbol is required"},
            status_code=400,
            headers=_UI_QUOTE_HEADERS,
        )

    cached = _get_cached_ui_quote(symbol, _UI_QUOTE_CACHE_TTL_SEC)
    if cached is not None:
        return JSONResponse(content=cached, headers=_UI_QUOTE_HEADERS)

    try:
        price, source = _fetch_ui_quote(symbol)
        payload = _store_ui_quote(symbol, price, source)
        return JSONResponse(content=payload, headers=_UI_QUOTE_HEADERS)
    except Exception as exc:
        stale = _get_cached_ui_quote(symbol, _UI_QUOTE_STALE_OK_SEC)
        if stale is not None:
            stale["stale"] = True
            return JSONResponse(content=stale, headers=_UI_QUOTE_HEADERS)
        return JSONResponse(
            content={"symbol": symbol, "error": str(exc)},
            status_code=500,
            headers=_UI_QUOTE_HEADERS,
        )


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, view: str = "current") -> HTMLResponse:
    # ── Run-window filter (display-side only; never touches state.db) ─────────
    # "current" (default) shows rows at/after the run marker's started_at;
    # "all" shows everything; "archive" shows pre-marker history. If no marker
    # exists, every mode returns all rows (backward compatible).
    if view not in run_window.VALID_MODES:
        view = "current"
    run_marker = run_window.load_run_marker(RUN_MARKER_PATH)
    run_started_at = run_window.marker_started_at(run_marker)

    status = state.get_monitor_status()
    signal = state.get_signal_snapshot()
    # Fetch generously, then filter the append-only history by run window.
    sig_hist = run_window.filter_rows(
        state.get_signal_history(limit=1000), ["updated_at", "bar_time"], run_started_at, view)
    signal_history = sig_hist[:20]
    signal_chart_history = sig_hist
    position = state.get_position()
    position_dict = position.__dict__ if position else None
    all_trades = run_window.filter_rows(
        state.get_recent_trades(limit=250), ["entry_time", "exit_time"], run_started_at, view)
    trades = _filter_prod_trades(all_trades)[:30]
    chart_trades = _filter_prod_trades(all_trades)
    summary = _summarize_trades(chart_trades)
    events = run_window.filter_rows(
        state.get_recent_monitor_events(limit=250), ["event_time"], run_started_at, view)[:30]
    account = state.get_account_snapshot()
    freshness = state.get_dashboard_freshness_status()  # current-state: NOT filtered

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
        symbol = position_dict["symbol"]
        _asset_key, cfg = _resolve_asset_config(symbol)
        target_pct = None
        stop_pct = None
        if cfg is not None:
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

        qty = int(position_dict["qty"])
        cost_basis_total = entry_price * qty

        position_view = {
            **position_dict,
            "bars_remaining": bars_remaining,
            "target_price": target_price,
            "stop_price": stop_price,
            "mark_price": mark_price,
            "mark_source": mark_source,
            "mark_time": mark_time,
            "cost_basis_total": cost_basis_total,
            "unrealized_pct": unrealized_pct,
            "unrealized_dollar": unrealized_dollar,
            "dist_target": dist_target,
            "dist_stop": dist_stop,
            "market_value": mark_price * qty if mark_price else None,
        }

    signal_badge = {1: ("LONG", "green"), 0: ("NO SIGNAL", "yellow"), -1: ("SHORT", "red")}.get(
        signal.get("signal") if signal else None,
        ("UNKNOWN", "red"),
    )

    returns_chart = Markup(_build_returns_chart(chart_trades))
    trade_scatter_chart = Markup(_build_trade_scatter_chart(chart_trades))
    signal_asset_key, signal_asset_cfg = _resolve_asset_config(status.get("live_symbol") if status else None)
    active_asset_key = signal_asset_key or config.DEFAULT_ASSET
    active_asset_cfg = signal_asset_cfg or config.ASSETS.get(config.DEFAULT_ASSET, {})
    config_mode_mismatch = bool(
        status and status.get("live_symbol") and signal_asset_key and signal_asset_key != config.DEFAULT_ASSET
    )
    rsi_oversold = active_asset_cfg.get("rsi_oversold") if active_asset_cfg else None
    rsi_overbought = active_asset_cfg.get("rsi_overbought") if active_asset_cfg else None
    signal_chart = Markup(
        _build_signal_chart(
            signal_chart_history,
            position=position_view,
            asset_label=active_asset_key or (status.get("live_symbol") if status else None),
            rsi_oversold=rsi_oversold,
            rsi_overbought=rsi_overbought,
        )
    )
    position_gauge = Markup(_build_position_gauge(position_view))

    return TEMPLATES.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ui_version": UI_VERSION,
            "git_hash": _get_git_hash(),
            "plotly_js_url": _PLOTLY_JS_URL,
            # The palette, passed in rather than restated in the template. A second copy
            # in dashboard.html would be exactly the defect F231 catalogued.
            "ui_tokens_css": Markup(ui_tokens.TOKENS),
            "status": status,
            "signal": signal,
            "signal_badge": signal_badge,
            "summary": summary,
            "position": position_view,
            "account": account,
            "active_mode": config.ACTIVE_MODE,
            "active_asset_key": active_asset_key,
            "asset_cfg": active_asset_cfg,
            "config_mode_mismatch": config_mode_mismatch,
            "run_marker": run_marker,
            "run_view": view,
            "run_started_at": run_started_at.isoformat() if run_started_at else None,
            "trades": trades,
            "events": events,
            "signal_history": signal_history,
            "returns_chart": returns_chart,
            "trade_scatter_chart": trade_scatter_chart,
            "signal_chart": signal_chart,
            "position_gauge": position_gauge,
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
