"""
live/broker.py — Interactive Brokers API wrapper for bracket order execution.

All order placement, cancellation, and account queries go through this module.
Uses ib_insync to communicate with TWS or IB Gateway running locally.

Paper vs live mode is controlled by config.LIVE_PAPER_MODE:
  - Paper: connects to port config.IBKR_PORT_PAPER (default 7497)
  - Live:  connects to port config.IBKR_PORT_LIVE  (default 7496)

No API keys required — IBKR authenticates via the TWS/Gateway GUI login.
"""

import logging
from dataclasses import dataclass

import config

log = logging.getLogger(__name__)

# Module-level IB singleton — reused across calls within a session
_ib = None


def _ensure_connected():
    """Returns a connected IB instance. Reconnects if disconnected."""
    global _ib
    from ib_insync import IB

    if _ib is not None and _ib.isConnected():
        return _ib

    _ib = IB()
    host = config.IBKR_HOST
    port = config.IBKR_PORT_PAPER if config.LIVE_PAPER_MODE else config.IBKR_PORT_LIVE
    client_id = config.IBKR_CLIENT_ID

    log.info(f"Connecting to IBKR at {host}:{port} (clientId={client_id})")
    _ib.connect(host, port, clientId=client_id)
    log.info("IBKR connected")
    return _ib


def disconnect():
    """Cleanly disconnect from IBKR. Call on shutdown."""
    global _ib
    if _ib is not None and _ib.isConnected():
        _ib.disconnect()
        log.info("IBKR disconnected")
    _ib = None


# ── Account info ──────────────────────────────────────────────────────────────

@dataclass
class AccountSnapshot:
    equity: float
    cash: float
    buying_power: float


def get_account() -> AccountSnapshot:
    """Returns current account equity, cash, and buying power."""
    ib = _ensure_connected()
    summary = ib.accountSummary()

    values = {}
    for item in summary:
        if item.tag in ("NetLiquidation", "TotalCashValue", "BuyingPower"):
            values[item.tag] = float(item.value)

    return AccountSnapshot(
        equity=values.get("NetLiquidation", 0.0),
        cash=values.get("TotalCashValue", 0.0),
        buying_power=values.get("BuyingPower", 0.0),
    )


# ── Price ─────────────────────────────────────────────────────────────────────

def get_latest_price(symbol: str) -> float:
    """Returns the latest market price for a symbol."""
    from ib_insync import Stock

    ib = _ensure_connected()
    contract = Stock(symbol, "SMART", "USD")
    ib.qualifyContracts(contract)

    [ticker] = ib.reqTickers(contract)
    # Use last price; fall back to close if market is closed
    price = ticker.last if ticker.last > 0 else ticker.close
    log.debug(f"Latest price {symbol}: {price}")
    return float(price)


# ── Orders ────────────────────────────────────────────────────────────────────

def place_bracket_order(symbol: str, qty: int, entry_price: float,
                        target_pct: float, stop_pct: float) -> str:
    """
    Places a market buy with linked take-profit (limit sell) and stop-loss legs.

    IBKR bracket orders: parent fills first, then child orders (TP + SL) go live.
    When either child fills, IBKR auto-cancels the other (OCA group).

    Returns the parent order ID as string (needed for time-exit cancellation).
    """
    from ib_insync import Stock

    ib = _ensure_connected()
    contract = Stock(symbol, "SMART", "USD")
    ib.qualifyContracts(contract)

    target_price = round(entry_price * (1 + target_pct), 2)
    stop_price   = round(entry_price * (1 - stop_pct), 2)

    bracket = ib.bracketOrder(
        action="BUY",
        quantity=qty,
        limitPrice=entry_price,  # limit at current price (effectively market)
        takeProfitPrice=target_price,
        stopLossPrice=stop_price,
    )

    # Submit all three legs (parent + TP + SL)
    parent_order = bracket[0]
    for order in bracket:
        ib.placeOrder(contract, order)

    parent_id = str(parent_order.orderId)
    log.info(
        f"Bracket order placed | id={parent_id} | {qty} {symbol} | "
        f"target={target_price:.2f} (+{target_pct:.2%}) | stop={stop_price:.2f} (-{stop_pct:.2%})"
    )
    return parent_id


def cancel_and_close(symbol: str, bracket_order_id: str, qty: int) -> None:
    """
    Cancels all open child orders from the bracket and places a market sell.
    Used for the time-exit path when position exceeds MAX_TRADE_BARS.
    """
    from ib_insync import Stock, MarketOrder

    ib = _ensure_connected()

    # Cancel all open orders for this symbol (catches both TP and SL legs)
    open_orders = ib.openOrders()
    parent_id = int(bracket_order_id)
    for order in open_orders:
        if getattr(order, "parentId", None) == parent_id:
            try:
                ib.cancelOrder(order)
                log.info(f"Cancelled child order {order.orderId} (parent={parent_id})")
            except Exception as exc:
                log.warning(f"Cancel child order {order.orderId} failed: {exc}")

    # Place market sell to exit
    contract = Stock(symbol, "SMART", "USD")
    ib.qualifyContracts(contract)
    sell_order = MarketOrder("SELL", qty)
    trade = ib.placeOrder(contract, sell_order)
    log.info(f"Time-exit market sell placed | id={trade.order.orderId} | {qty} {symbol}")


def get_open_position(symbol: str) -> dict | None:
    """
    Returns position info from IBKR, or None if no position exists.
    Used on startup to reconcile state DB with actual broker state.
    """
    ib = _ensure_connected()
    positions = ib.positions()

    for pos in positions:
        if pos.contract.symbol == symbol:
            return {
                "qty":          int(pos.position),
                "avg_price":    float(pos.avgCost),
                "market_value": float(pos.position * pos.avgCost),
            }
    return None
