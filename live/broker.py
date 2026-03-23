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
_ib_thread_id = None  # track which thread created the connection


def _ensure_connected():
    """Returns a connected IB instance. Reconnects if called from a different thread."""
    global _ib, _ib_thread_id
    import asyncio
    import threading
    from ib_insync import IB

    current_thread = threading.current_thread().ident

    # Force reconnect if called from a different thread than the one that connected.
    # ib_insync's event loop is thread-local — reusing a connection across threads
    # causes qualifyContracts/reqTickers to timeout (responses never processed).
    if _ib is not None and _ib.isConnected() and _ib_thread_id != current_thread:
        log.info(f"Reconnecting IBKR — thread changed (was {_ib_thread_id}, now {current_thread})")
        try:
            _ib.disconnect()
        except Exception:
            pass
        _ib = None

    # Ensure an event loop exists in this thread
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    if _ib is not None and _ib.isConnected():
        return _ib

    _ib = IB()
    _ib.RequestTimeout = 10  # seconds — prevents blocking forever on API calls
    host = config.IBKR_HOST
    port = config.IBKR_PORT_PAPER if config.LIVE_PAPER_MODE else config.IBKR_PORT_LIVE
    client_id = config.IBKR_CLIENT_ID

    log.info(f"Connecting to IBKR at {host}:{port} (clientId={client_id})")
    _ib.connect(host, port, clientId=client_id)
    _ib_thread_id = current_thread
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

def get_tradeable_price(symbol: str) -> float:
    """Returns a fresh broker-sourced price suitable for order placement.

    Only returns live or delayed IBKR data. Raises RuntimeError if no broker
    price is available — NEVER falls back to yfinance for order placement.
    """
    import math
    from ib_insync import Stock

    ib = _ensure_connected()
    contract = Stock(symbol, "SMART", "USD")

    def _valid(p):
        try:
            return p is not None and math.isfinite(p) and p > 0
        except (TypeError, ValueError):
            return False

    try:
        ib.qualifyContracts(contract)
    except Exception as exc:
        raise RuntimeError(f"Cannot qualify contract for {symbol}: {exc}")

    # Try live market data
    try:
        [ticker] = ib.reqTickers(contract)
        ib.sleep(2)
        for attr in ("last", "close", "bid", "ask"):
            p = getattr(ticker, attr, None)
            if _valid(p):
                log.info(f"Tradeable price {symbol}: {p} (live {attr})")
                return float(p)
        mp = ticker.marketPrice()
        if _valid(mp):
            log.info(f"Tradeable price {symbol}: {mp} (marketPrice)")
            return float(mp)
    except Exception as exc:
        log.warning(f"Live market data failed for {symbol}: {exc}")

    # Try delayed data
    try:
        ib.reqMarketDataType(3)
        ib.sleep(2)
        [delayed] = ib.reqTickers(contract)
        ib.sleep(2)
        for attr in ("last", "close", "bid", "ask"):
            p = getattr(delayed, attr, None)
            if _valid(p):
                log.info(f"Tradeable price {symbol}: {p} (delayed {attr})")
                ib.reqMarketDataType(1)
                return float(p)
        ib.reqMarketDataType(1)
    except Exception as exc:
        log.warning(f"Delayed market data failed for {symbol}: {exc}")
        try:
            ib.reqMarketDataType(1)
        except Exception:
            pass

    raise RuntimeError(f"No broker price available for {symbol} — refusing to place order on stale data")


def get_reference_price(symbol: str) -> float:
    """Returns a price for logging/diagnostics. May fall back to delayed or yfinance.

    NOT suitable for order placement — use get_tradeable_price() for that.
    """
    try:
        return get_tradeable_price(symbol)
    except RuntimeError:
        pass
    return _yfinance_fallback(symbol)


def get_latest_price(symbol: str) -> float:
    """Backwards-compatible alias — delegates to get_reference_price()."""
    return get_reference_price(symbol)


def _yfinance_fallback(symbol: str) -> float:
    """Fetch last close price from yfinance as a fallback."""
    log.warning(f"IBKR data unavailable for {symbol}, using yfinance last close")
    from src.data.fetcher import fetch_yfinance
    from datetime import datetime, timedelta, timezone
    end = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    start = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%d")
    hist = fetch_yfinance(symbol, start=start, end=end, interval="1d")
    if len(hist) > 0:
        price = float(hist["close"].iloc[-1])
        log.info(f"Latest price {symbol}: {price} (yfinance close)")
        return price
    raise RuntimeError(f"Cannot get price for {symbol} from IBKR or yfinance")


# ── Orders ────────────────────────────────────────────────────────────────────

def place_bracket_order(symbol: str, qty: int, entry_price: float,
                        target_pct: float, stop_pct: float) -> str | None:
    """
    Places a market buy with linked take-profit (limit sell) and stop-loss legs.

    entry_price is the signal bar's close — used for target/stop bracket levels
    (matches backtest convention). The parent limit price uses a fresh broker
    quote to ensure fill at current market.

    IBKR bracket orders: parent fills first, then child orders (TP + SL) go live.
    When either child fills, IBKR auto-cancels the other (OCA group).

    Returns the parent order ID as string, or None if the order could not be placed.
    """
    from ib_insync import Stock

    ib = _ensure_connected()
    contract = Stock(symbol, "SMART", "USD")

    try:
        ib.qualifyContracts(contract)
    except Exception as exc:
        log.error(f"Cannot qualify contract for {symbol}: {exc} — order NOT placed")
        return None

    # Get fresh broker price for the parent limit order
    try:
        live_price = get_tradeable_price(symbol)
    except RuntimeError as exc:
        log.error(f"No tradeable price for {symbol}: {exc} — order NOT placed")
        return None

    target_price = round(entry_price * (1 + target_pct), 2)
    stop_price   = round(entry_price * (1 - stop_pct), 2)

    bracket = ib.bracketOrder(
        action="BUY",
        quantity=qty,
        limitPrice=round(live_price * 1.005, 2),  # 0.5% above live price to ensure fill
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
    try:
        ib.qualifyContracts(contract)
    except Exception as exc:
        log.error(f"Cannot qualify contract for time-exit sell {symbol}: {exc}")
        raise
    sell_order = MarketOrder("SELL", qty)
    trade = ib.placeOrder(contract, sell_order)
    log.info(f"Time-exit market sell placed | id={trade.order.orderId} | {qty} {symbol}")


def get_bracket_fill(bracket_order_id: str) -> dict | None:
    """
    Fetches actual fill data for a completed bracket order's child (TP or SL).

    Returns dict with fill_price, fill_time, exit_type, or None if unavailable.
    """
    ib = _ensure_connected()
    parent_id = int(bracket_order_id)

    try:
        trades = ib.trades()
        for trade in trades:
            order = trade.order
            if getattr(order, 'parentId', 0) == parent_id and trade.fills:
                last_fill = trade.fills[-1]
                fill_price = last_fill.execution.price
                fill_time = last_fill.execution.time.isoformat() if last_fill.execution.time else None

                # Determine exit type from order type
                if order.orderType == 'LMT':
                    exit_type = "target_hit"
                elif order.orderType in ('STP', 'STP LMT'):
                    exit_type = "stop_hit"
                else:
                    exit_type = "bracket_exit"

                log.info(f"Found bracket fill: price={fill_price}, type={exit_type}, time={fill_time}")
                return {
                    "fill_price": float(fill_price),
                    "fill_time": fill_time,
                    "exit_type": exit_type,
                }

        log.warning(f"No fill data found for bracket parent {parent_id}")
        return None

    except Exception as exc:
        log.warning(f"Failed to fetch bracket fill data: {exc}")
        return None


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
