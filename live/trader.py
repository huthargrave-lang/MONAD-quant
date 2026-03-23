"""
live/trader.py — Scheduler and main trading loop for hourly ETF live trading.

Runs as a long-lived process. APScheduler fires on_bar() 2 minutes after each
hourly bar close during US market hours (ET):
    9:32, 10:32, 11:32, 12:32, 13:32, 14:32, 15:32

The 2-minute delay ensures yfinance has the completed bar available.

Connects to Interactive Brokers via TWS or IB Gateway running locally.
Paper vs live mode controlled by config.LIVE_PAPER_MODE (port 7497 vs 7496).

Usage:
    python -m live.trader            # paper mode (default, port 7497)
    python -m live.trader --live     # REAL MONEY — requires explicit flag (port 7496)
    python -m live.trader --symbol GDXU  # override instrument
"""

import argparse
import logging
import sys
from datetime import datetime, timezone

import config
from live import broker, signals, state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("trader")


def _get_asset_config() -> dict:
    """Returns the ASSETS dict entry for the current LIVE_SYMBOL."""
    mode = f"{config.LIVE_SYMBOL}_HOURLY"
    if mode not in config.ASSETS:
        raise ValueError(f"No ASSETS config for mode '{mode}'. Check config.LIVE_SYMBOL.")
    return config.ASSETS[mode]


# ── Core logic ────────────────────────────────────────────────────────────────

def on_bar() -> None:
    """
    Called once per completed hourly bar.
    Handles: position bar-count tracking, time-exits, and new entry signals.
    """
    log.info("─" * 60)
    log.info(f"on_bar() | {config.LIVE_SYMBOL} | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    position = state.get_position()

    # ── Manage existing position ──────────────────────────────────────────────
    if position is not None:
        # Reconcile: check if bracket TP/SL already filled since last bar
        broker_pos = broker.get_open_position(position.symbol)
        if broker_pos is None or broker_pos["qty"] == 0:
            # Bracket order already exited — fetch actual fill data from IBKR
            fill = broker.get_bracket_fill(position.bracket_order_id)
            if fill is not None:
                ret = (fill["fill_price"] - position.entry_price) / position.entry_price
                exit_type = fill["exit_type"]
                log.info(
                    f"Bracket filled | fill_price={fill['fill_price']:.2f} | "
                    f"fill_time={fill['fill_time']} | ret={ret:+.4%} → {exit_type}"
                )
            else:
                # Fallback: fill data unavailable (e.g. connection gap), use reference price
                ref_price = broker.get_reference_price(position.symbol)
                ret = (ref_price - position.entry_price) / position.entry_price
                asset_cfg = _get_asset_config()
                exit_type = "target_hit" if ret >= asset_cfg["target_gain_pct"] * 0.8 else "stop_hit"
                log.warning(
                    f"Fill data unavailable — inferred from reference price | "
                    f"ref={ref_price:.2f} | ret={ret:+.4%} → {exit_type} (inferred)"
                )
            state.close_position(return_pct=ret, exit_type=exit_type,
                                 exit_price=fill["fill_price"] if fill else None)
            _log_summary()
            return

        bar_count = state.increment_bar_count()
        log.info(f"Open position: {position.qty} {position.symbol} @ {position.entry_price:.2f} | bar {bar_count}/{config.MAX_TRADE_BARS_LIVE}")

        if bar_count >= config.MAX_TRADE_BARS_LIVE:
            log.info("Time-exit triggered — cancelling bracket and selling")
            broker.cancel_and_close(position.symbol, position.bracket_order_id, position.qty)
            # Fetch fill from the time-exit market sell
            ref_price = broker.get_reference_price(position.symbol)
            ret = (ref_price - position.entry_price) / position.entry_price
            state.close_position(return_pct=ret, exit_type="time_exit", exit_price=ref_price)
            _log_summary()
            return

        # Position is still open and within bar limit — wait for bracket exit
        log.info("Position within bar limit, bracket order monitoring exit")
        return

    # ── Check for new entry signal ────────────────────────────────────────────
    try:
        sig_info = signals.get_current_signal()
    except RuntimeError as exc:
        log.error(f"Signal computation failed: {exc}")
        return

    if sig_info["signal"] != 1:
        log.info(f"No entry signal (signal={sig_info['signal']})")
        return

    # ── Size and place the trade ──────────────────────────────────────────────
    account = broker.get_account()
    capital = account.equity
    log.info(f"Account equity: ${capital:,.2f}")

    sizing = state.get_position_plan(capital)
    log.info(
        f"Position sizing: pct={sizing['position_pct']:.3f} | "
        f"${sizing['position_dollars']:,.0f}"
    )

    asset_config = _get_asset_config()
    # Use the completed bar's close for bracket pricing — matches backtest convention
    # where entry = signal bar's close (next bar's open is approximated by close).
    entry_price = sig_info["bar_close"]
    log.info(f"Entry price from bar close: ${entry_price:.2f} (bar={sig_info['bar_time']})")
    qty = int(sizing["position_dollars"] / entry_price)

    if qty < 1:
        log.warning(f"Position too small for one share (${sizing['position_dollars']:.0f} / ${entry_price:.2f})")
        return

    order_id = broker.place_bracket_order(
        symbol=config.LIVE_SYMBOL,
        qty=qty,
        entry_price=entry_price,
        target_pct=asset_config["target_gain_pct"],
        stop_pct=asset_config["stop_loss_pct"],
    )
    if order_id is None:
        log.error("Bracket order failed — skipping this entry. Will retry next bar if signal persists.")
        return
    state.open_position(config.LIVE_SYMBOL, entry_price, qty, order_id)
    log.info(f"ENTRY placed: {qty} shares @ ~{entry_price:.2f}")


def _log_summary() -> None:
    summary = state.get_trade_summary()
    if summary["total"] == 0:
        return
    log.info(
        f"Live stats | trades={summary['total']} | WR={summary['win_rate']:.1%} | "
        f"total_ret={summary['total_ret']:+.4%} | exits={summary['exit_types']}"
    )


# ── Scheduler ─────────────────────────────────────────────────────────────────

def _is_market_hours() -> bool:
    """Returns True if current UTC time falls within US market hours (ET 9:30–16:00)."""
    from zoneinfo import ZoneInfo
    et_now = datetime.now(ZoneInfo("America/New_York"))
    if et_now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    market_open  = et_now.replace(hour=9,  minute=30, second=0, microsecond=0)
    market_close = et_now.replace(hour=16, minute=0,  second=0, microsecond=0)
    return market_open <= et_now <= market_close


def _scheduled_on_bar() -> None:
    """Wrapper that guards on_bar() with a market-hours check."""
    if not _is_market_hours():
        log.debug("Outside market hours — skipping")
        return
    try:
        on_bar()
    except Exception:
        log.exception("Unhandled error in on_bar() — will retry next bar")


def run_scheduler() -> None:
    """Starts the APScheduler process. Blocks until interrupted."""
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BlockingScheduler(timezone="America/New_York")
    # Fire at :32 past the hour, every hour, Mon–Fri, 9–15 ET
    # (covers bars closing at 9:30, 10:30, 11:30, 12:30, 13:30, 14:30, 15:30)
    scheduler.add_job(
        _scheduled_on_bar,
        CronTrigger(
            day_of_week="mon-fri",
            hour="9-15",
            minute="32",
            timezone="America/New_York",
        ),
        id="hourly_bar",
        name=f"{config.LIVE_SYMBOL} Hourly Bar Check",
        max_instances=1,
        coalesce=True,
    )

    mode_str = "PAPER (port 7497)" if config.LIVE_PAPER_MODE else "*** LIVE MONEY (port 7496) ***"
    log.info(f"Scheduler started | mode={mode_str} | symbol={config.LIVE_SYMBOL}")
    log.info("Firing at :32 past each hour, Mon–Fri 9:32–15:32 ET")
    log.info("Requires IB Gateway or TWS running locally")
    log.info("Press Ctrl+C to stop")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Shutting down...")
        broker.disconnect()
        log.info("Scheduler stopped")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="MONAD Quant — Hourly ETF Live Trader (IBKR)")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live IBKR account (real money, port 7496). Omit for paper trading (port 7497).",
    )
    parser.add_argument(
        "--symbol",
        default=None,
        help=f"Override instrument (default: {config.LIVE_SYMBOL}). E.g., --symbol GDXU",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run on_bar() once immediately then exit (for testing).",
    )
    args = parser.parse_args()

    if args.symbol:
        config.LIVE_SYMBOL = args.symbol.upper()

    if args.live:
        config.LIVE_PAPER_MODE = False
        log.warning("=" * 60)
        log.warning("LIVE MODE — THIS WILL TRADE WITH REAL MONEY")
        log.warning(f"Symbol: {config.LIVE_SYMBOL} | IBKR port: {config.IBKR_PORT_LIVE}")
        log.warning("=" * 60)
    else:
        config.LIVE_PAPER_MODE = True
        log.info(f"Paper mode | symbol={config.LIVE_SYMBOL} | port={config.IBKR_PORT_PAPER}")

    # Verify IBKR connection
    try:
        account = broker.get_account()
        log.info(f"IBKR connected | equity=${account.equity:,.2f} | cash=${account.cash:,.2f}")
    except Exception as exc:
        log.error(f"Cannot connect to IBKR: {exc}")
        log.error("Ensure IB Gateway or TWS is running on localhost")
        sys.exit(1)

    # ── Startup self-check: log active config ────────────────────────────
    asset_cfg = _get_asset_config()
    port = config.IBKR_PORT_PAPER if config.LIVE_PAPER_MODE else config.IBKR_PORT_LIVE
    log.info("─" * 60)
    log.info("Startup config:")
    log.info(f"  Symbol:       {config.LIVE_SYMBOL}")
    log.info(f"  Mode:         {'PAPER' if config.LIVE_PAPER_MODE else 'LIVE'} (port {port})")
    log.info(f"  Position:     fixed 10%")
    log.info(f"  Target:       {asset_cfg['target_gain_pct']*100:.2f}%")
    log.info(f"  Stop:         {asset_cfg['stop_loss_pct']*100:.2f}%")
    log.info(f"  R:R:          {asset_cfg['target_gain_pct']/asset_cfg['stop_loss_pct']:.1f}:1")
    log.info(f"  Max bars:     {config.MAX_TRADE_BARS_LIVE}")
    log.info(f"  Warmup bars:  {signals._WARMUP_BARS}")
    log.info("─" * 60)

    state.init_db()

    if args.once:
        on_bar()
        _log_summary()
        broker.disconnect()
        return

    # Disconnect the startup connection — APScheduler runs in a worker thread
    # and will create its own connection. Keeping the main-thread connection alive
    # would cause ib_insync event loop conflicts (responses never processed).
    broker.disconnect()
    run_scheduler()


if __name__ == "__main__":
    main()
