"""
live/trader.py — Scheduler and main trading loop for hourly ETF live trading.

Execution model (unified with backtest):
    1. Signal fires on completed bar N (RSI, MACD, VWAP computed from bar N's OHLCV).
    2. Entry fills at current market price (live equivalent of bar N+1's open).
    3. TP/SL bracket levels are relative to the fill price, not bar N's close.
    4. Exit via IBKR bracket (TP limit sell / SL stop sell / time-exit market sell).

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
    python -m live.trader --dry-run  # signals only, no orders placed
"""

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import config
from live import broker, signals, state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("trader")


def _get_git_hash() -> str:
    """Returns the short git commit hash, or 'unknown' if not in a repo."""
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(Path(__file__).parent.parent),
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


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
    import time as _time
    t0 = _time.monotonic()
    cycle_action = "unknown"

    log.info("─" * 60)
    log.info(f"on_bar() | {config.LIVE_SYMBOL} | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    state.set_monitor_status(status="running", cycle_action="started", details="on_bar cycle started")
    try:
        cycle_action = _on_bar_inner()
        state.set_monitor_status(status="ok", cycle_action=cycle_action, details="on_bar cycle completed")
    except Exception as exc:
        cycle_action = "error"
        state.set_monitor_status(status="error", cycle_action=cycle_action, details=str(exc))
        state.add_monitor_event("ERROR", "cycle", f"Unhandled on_bar exception: {exc}")
        raise
    finally:
        elapsed = _time.monotonic() - t0
        log.info(f"CYCLE | action={cycle_action} | elapsed={elapsed:.1f}s")


def _on_bar_inner() -> str:
    """Core on_bar logic. Returns a short action label for cycle logging."""
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
                # Fill data unavailable (e.g. connection gap after restart).
                # Record as pending_close — actual PnL unknown until fill is reconciled.
                ref_price = broker.get_reference_price(position.symbol)
                ret = (ref_price - position.entry_price) / position.entry_price
                warning_msg = (
                    f"Fill data unavailable — recording as pending_close | "
                    f"ref={ref_price:.2f} | estimated_ret={ret:+.4%} (NOT recorded as PnL)"
                )
                log.warning(warning_msg)
                state.add_monitor_event("WARNING", "fill", warning_msg)
                exit_type = "pending_close"
            state.close_position(return_pct=ret if fill else 0.0, exit_type=exit_type,
                                 exit_price=fill["fill_price"] if fill else None)
            _log_summary()
            return f"exit_{exit_type}"

        bar_count = state.increment_bar_count()
        log.info(f"Open position: {position.qty} {position.symbol} @ {position.entry_price:.2f} | bar {bar_count}/{config.MAX_TRADE_BARS_LIVE}")

        if bar_count >= config.MAX_TRADE_BARS_LIVE:
            log.info("Time-exit triggered — cancelling bracket and selling")
            sell_fill = broker.cancel_and_close(position.symbol, position.bracket_order_id, position.qty)
            if sell_fill is not None:
                # Actual fill price from the market sell — preferred PnL source
                exit_price = sell_fill["fill_price"]
                ret = (exit_price - position.entry_price) / position.entry_price
                log.info(f"Time-exit filled | price={exit_price:.2f} | ret={ret:+.4%}")
            else:
                # Fill retrieval failed — fall back to reference price estimate.
                # This is the one live exit path where PnL may be estimated.
                exit_price = broker.get_reference_price(position.symbol)
                ret = (exit_price - position.entry_price) / position.entry_price
                warning_msg = (
                    f"Time-exit fill unavailable — using reference price {exit_price:.2f} | "
                    f"estimated_ret={ret:+.4%}"
                )
                log.warning(warning_msg)
                state.add_monitor_event("WARNING", "time_exit", warning_msg)
            state.close_position(return_pct=ret, exit_type="time_exit", exit_price=exit_price)
            _log_summary()
            return "exit_time_exit"

        # Position is still open and within bar limit — wait for bracket exit
        log.info("Position within bar limit, bracket order monitoring exit")
        return f"holding_bar_{bar_count}"

    # ── Check for new entry signal ────────────────────────────────────────────
    try:
        sig_info = signals.get_current_signal()
    except RuntimeError as exc:
        log.error(f"Signal computation failed: {exc}")
        state.add_monitor_event("ERROR", "signal", f"Signal computation failed: {exc}")
        return "signal_error"

    state.save_signal_snapshot(sig_info["signal"], str(sig_info["bar_time"]), sig_info["bar_close"])

    if sig_info["signal"] != 1:
        log.info(f"No entry signal (signal={sig_info['signal']})")
        return "no_signal"

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
    # Use bar_close for qty estimation. The actual entry basis (live market price)
    # is determined by broker.place_bracket_order() and returned as fill_basis.
    bar_close = sig_info["bar_close"]
    log.info(f"Signal bar close: ${bar_close:.2f} (bar={sig_info['bar_time']})")
    qty = int(sizing["position_dollars"] / bar_close)

    if qty < 1:
        warning_msg = f"Position too small for one share (${sizing['position_dollars']:.0f} / ${bar_close:.2f})"
        log.warning(warning_msg)
        state.add_monitor_event("WARNING", "sizing", warning_msg)
        return "qty_too_small"

    if config.LIVE_DRY_RUN:
        # In dry-run, use bar_close as approximate basis (no broker call)
        target_p = round(bar_close * (1 + asset_config["target_gain_pct"]), 2)
        stop_p = round(bar_close * (1 - asset_config["stop_loss_pct"]), 2)
        log.info(
            f"DRY RUN — would place: {qty} {config.LIVE_SYMBOL} @ ~{bar_close:.2f} | "
            f"TP~={target_p:.2f} | SL~={stop_p:.2f} (approx; live uses broker price)"
        )
        return "dry_run_entry"

    result = broker.place_bracket_order(
        symbol=config.LIVE_SYMBOL,
        qty=qty,
        target_pct=asset_config["target_gain_pct"],
        stop_pct=asset_config["stop_loss_pct"],
    )
    if result is None:
        error_msg = "Bracket order failed — skipping this entry. Will retry next bar if signal persists."
        log.error(error_msg)
        state.add_monitor_event("ERROR", "order", error_msg)
        return "order_failed"

    # Record the broker's fill_basis as entry price — this is the live market price
    # at order time, matching the backtest convention of entering at next-bar open.
    entry_price = result["fill_basis"]
    order_id = result["order_id"]
    state.open_position(config.LIVE_SYMBOL, entry_price, qty, order_id)
    log.info(f"ENTRY placed: {qty} shares @ ~{entry_price:.2f} (fill_basis)")
    state.add_monitor_event("INFO", "entry", f"Entry placed: {qty} {config.LIVE_SYMBOL} @ {entry_price:.2f}")
    return "entry_placed"


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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute signals but do not place any orders (safe observation mode).",
    )
    args = parser.parse_args()

    if args.symbol:
        config.LIVE_SYMBOL = args.symbol.upper()

    if args.dry_run:
        config.LIVE_DRY_RUN = True

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
    git_hash = _get_git_hash()
    log.info("─" * 60)
    log.info("Startup config:")
    log.info(f"  Symbol:       {config.LIVE_SYMBOL}")
    log.info(f"  Mode:         {'PAPER' if config.LIVE_PAPER_MODE else 'LIVE'} (port {port})")
    log.info(f"  IB host:      {config.IBKR_HOST}:{port} (clientId={config.IBKR_CLIENT_ID})")
    log.info(f"  Position:     fixed 10%")
    log.info(f"  Target:       {asset_cfg['target_gain_pct']*100:.2f}%")
    log.info(f"  Stop:         {asset_cfg['stop_loss_pct']*100:.2f}%")
    log.info(f"  R:R:          {asset_cfg['target_gain_pct']/asset_cfg['stop_loss_pct']:.1f}:1")
    log.info(f"  Max bars:     {config.MAX_TRADE_BARS_LIVE}")
    log.info(f"  Warmup bars:  {signals._WARMUP_BARS}")
    log.info(f"  Schedule:     :32 past each hour, Mon-Fri 9:32-15:32 ET")
    log.info(f"  Timezone:     America/New_York")
    log.info(f"  Git hash:     {git_hash}")
    if getattr(config, 'LIVE_DRY_RUN', False):
        log.info(f"  DRY RUN:      YES — no orders will be placed")
    log.info("─" * 60)

    state.init_db()
    state.set_monitor_status(status="idle", cycle_action="startup", details="trader initialized")

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
