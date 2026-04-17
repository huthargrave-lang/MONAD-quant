"""
live/alerts.py — Slack webhook alerts for live trading events.

Sends formatted Slack messages for:
  * Position entries (symbol, qty, price, Kelly sizing)
  * Position exits (exit_type, return, running stats)
  * CRITICAL/ERROR events (signal failures, force-finalize, software stops)

No-op when SLACK_WEBHOOK_URL is not set. Rate-limits duplicate messages
to avoid spam during failure loops. Includes a dashboard link if
DASHBOARD_URL is configured.
"""

import json
import logging
import os
import time
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
_DASHBOARD_URL = os.getenv("DASHBOARD_URL", "")

_DEDUPE_WINDOW_SECS = 300
_recent: dict[str, float] = {}


def _should_send(key: str) -> bool:
    now = time.monotonic()
    expired = [k for k, t in _recent.items() if now - t > _DEDUPE_WINDOW_SECS]
    for k in expired:
        del _recent[k]
    if key in _recent:
        return False
    _recent[key] = now
    return True


def _post(text: str, color: str = "#36a64f") -> None:
    if not _WEBHOOK_URL:
        return
    footer = f"\n<{_DASHBOARD_URL}|View Dashboard>" if _DASHBOARD_URL else ""
    payload = {
        "attachments": [{
            "color": color,
            "text": text + footer,
            "ts": int(time.time()),
        }]
    }
    try:
        req = Request(
            _WEBHOOK_URL,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        urlopen(req, timeout=10)
    except Exception as exc:
        log.warning(f"Slack webhook failed: {exc}")


def alert_entry(symbol: str, direction: str, qty: int, price: float,
                position_pct: float, back_to_back: str | None = None) -> None:
    context = f" (back-to-back after {back_to_back})" if back_to_back else ""
    text = (
        f"*ENTRY* | {direction.upper()} {qty} {symbol} @ ${price:.2f}{context}\n"
        f"Position size: {position_pct:.1%}"
    )
    if _should_send(f"entry-{symbol}"):
        _post(text, color="#2196F3")


def alert_exit(symbol: str, direction: str, entry_price: float, exit_price: float,
               return_pct: float, exit_type: str, total_trades: int = 0,
               win_rate: float = 0.0, inferred: bool = False) -> None:
    emoji = "+" if return_pct >= 0 else ""
    source = " _(inferred)_" if inferred else ""
    stats = ""
    if total_trades > 0:
        stats = f"\nRunning: {total_trades} trades | {win_rate:.1%} WR"
    text = (
        f"*EXIT* | {exit_type}{source} | {direction.upper()} {symbol}\n"
        f"Entry ${entry_price:.2f} -> Exit ${exit_price:.2f} | "
        f"Return: *{emoji}{return_pct:.2%}*{stats}"
    )
    if _should_send(f"exit-{symbol}-{exit_type}"):
        _post(text, color="#4CAF50" if return_pct >= 0 else "#F44336")


def alert_error(message: str, level: str = "ERROR") -> None:
    prefix = "CRITICAL" if level.upper() == "CRITICAL" else "ERROR"
    text = f"*{prefix}*: {message}"
    if _should_send(f"error-{message[:80]}"):
        _post(text, color="#FF0000" if level.upper() == "CRITICAL" else "#FF5722")
