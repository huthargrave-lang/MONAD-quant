"""
live/broker.py — Alpaca API wrapper for QQQ bracket order execution.

All order placement, cancellation, and account queries go through this module.
Uses alpaca-py (the newer official SDK). Reads credentials from environment vars
ALPACA_API_KEY and ALPACA_SECRET_KEY.

Paper vs live mode is controlled by config.LIVE_PAPER_MODE.
"""

import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv

import config

load_dotenv()

log = logging.getLogger(__name__)

_PAPER_URL = "https://paper-api.alpaca.markets"
_LIVE_URL  = "https://api.alpaca.markets"


def _get_client():
    """Returns an alpaca-py TradingClient (lazy import to keep startup fast)."""
    from alpaca.trading.client import TradingClient
    api_key    = os.environ["ALPACA_API_KEY"]
    secret_key = os.environ["ALPACA_SECRET_KEY"]
    paper      = config.LIVE_PAPER_MODE
    return TradingClient(api_key, secret_key, paper=paper)


def _get_data_client():
    """Returns an alpaca-py StockHistoricalDataClient for latest quote."""
    from alpaca.data.historical import StockHistoricalDataClient
    api_key    = os.environ["ALPACA_API_KEY"]
    secret_key = os.environ["ALPACA_SECRET_KEY"]
    return StockHistoricalDataClient(api_key, secret_key)


# ── Account info ──────────────────────────────────────────────────────────────

@dataclass
class AccountSnapshot:
    equity: float
    cash: float
    buying_power: float


def get_account() -> AccountSnapshot:
    client  = _get_client()
    account = client.get_account()
    return AccountSnapshot(
        equity=float(account.equity),
        cash=float(account.cash),
        buying_power=float(account.buying_power),
    )


# ── Price ─────────────────────────────────────────────────────────────────────

def get_latest_price(symbol: str) -> float:
    """Returns the latest trade price for a symbol."""
    from alpaca.data.requests import StockLatestTradeRequest
    client = _get_data_client()
    req    = StockLatestTradeRequest(symbol_or_symbols=symbol)
    trade  = client.get_stock_latest_trade(req)
    price  = float(trade[symbol].price)
    log.debug(f"Latest price {symbol}: {price}")
    return price


# ── Orders ────────────────────────────────────────────────────────────────────

def place_bracket_order(symbol: str, qty: int, entry_price: float,
                        target_pct: float, stop_pct: float) -> str:
    """
    Places a market buy with linked take_profit and stop_loss legs.

    The broker monitors and auto-cancels the inactive leg when either fires.
    Returns the bracket order ID (needed for time-exit cancellation).
    """
    from alpaca.trading.requests import (
        MarketOrderRequest,
        TakeProfitRequest,
        StopLossRequest,
    )
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass

    target_price = round(entry_price * (1 + target_pct), 2)
    stop_price   = round(entry_price * (1 - stop_pct), 2)

    req = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.BRACKET,
        take_profit=TakeProfitRequest(limit_price=target_price),
        stop_loss=StopLossRequest(stop_price=stop_price),
    )

    client = _get_client()
    order  = client.submit_order(req)

    log.info(
        f"Bracket order placed | id={order.id} | {qty} {symbol} | "
        f"target={target_price:.2f} (+{target_pct:.2%}) | stop={stop_price:.2f} (-{stop_pct:.2%})"
    )
    return str(order.id)


def cancel_and_close(symbol: str, bracket_order_id: str, qty: int) -> None:
    """
    Cancels the open bracket order (target + stop legs) and places a
    market sell to exit the position. Used for the time-exit path.
    """
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    client = _get_client()

    try:
        client.cancel_order_by_id(bracket_order_id)
        log.info(f"Cancelled bracket order {bracket_order_id}")
    except Exception as exc:
        # Order may have already been filled/cancelled — log and continue to the sell
        log.warning(f"Cancel order {bracket_order_id} failed (may already be gone): {exc}")

    sell_req = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    )
    sell_order = client.submit_order(sell_req)
    log.info(f"Time-exit market sell placed | id={sell_order.id} | {qty} {symbol}")


def get_open_position(symbol: str) -> dict | None:
    """
    Returns position info from Alpaca, or None if no position exists.
    Used on startup to reconcile state DB with actual broker state.
    """
    from alpaca.common.exceptions import APIError
    client = _get_client()
    try:
        pos = client.get_open_position(symbol)
        return {
            "qty":       int(pos.qty),
            "avg_price": float(pos.avg_entry_price),
            "market_value": float(pos.market_value),
        }
    except APIError:
        return None
