"""
live/trader.py — Scheduler and main trading loop for QQQ Hourly live trading.

Runs as a long-lived process. APScheduler fires on_bar() 2 minutes after each
hourly bar close during US market hours (ET):
    9:32, 10:32, 11:32, 12:32, 13:32, 14:32, 15:32

The 2-minute delay ensures yfinance has the completed bar available.

Usage:
    python -m live.trader            # paper mode (default)
    python -m live.trader --live     # REAL MONEY — requires explicit flag

The LIVE_PAPER_MODE config flag also controls which Alpaca endpoint is used.
Running with --live overrides config.LIVE_PAPER_MODE to False.
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


# ── Core logic ────────────────────────────────────────────────────────────────

def on_bar() -> None:
    """
    Called once per completed hourly bar.
    Handles: position bar-count tracking, time-exits, and new entry signals.
    """
    log.info("─" * 60)
    log.info(f"on_bar() | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    position = state.get_position()

    # ── Manage existing position ──────────────────────────────────────────────
    if position is not None:
        bar_count = state.increment_bar_count()
        log.info(f"Open position: {position.qty} {position.symbol} @ {position.entry_price:.2f} | bar {bar_count}/{config.MAX_TRADE_BARS_QQQ_LIVE}")

        if bar_count >= config.MAX_TRADE_BARS_QQQ_LIVE:
            log.info("Time-exit triggered — cancelling bracket and selling")
            current_price = broker.get_latest_price(position.symbol)
            ret = (current_price - position.entry_price) / position.entry_price
            broker.cancel_and_close(position.symbol, position.bracket_order_id, position.qty)
            state.close_position(return_pct=ret, exit_type="time_exit")
            _log_summary()
            return

        # Position is still open and within bar limit — wait for bracket exit
        log.info("Position within bar limit, bracket order monitoring exit")
        return

    # ── Check for new entry signal ────────────────────────────────────────────
    try:
        signal = signals.get_current_signal()
    except RuntimeError as exc:
        log.error(f"Signal computation failed: {exc}")
        return

    if signal != 1:
        log.info(f"No entry signal (signal={signal})")
        return

    # ── Size and place the trade ──────────────────────────────────────────────
    account = broker.get_account()
    capital = account.equity
    log.info(f"Account equity: ${capital:,.2f}")

    kelly = state.get_current_kelly(capital)
    log.info(
        f"Kelly sizing: full={kelly['kelly_full']:.3f} | "
        f"adj={kelly['kelly_adjusted']:.3f} | "
        f"capped={kelly['kelly_capped']:.3f} | "
        f"${kelly['position_dollars']:,.0f}"
    )

    entry_price = broker.get_latest_price(config.LIVE_SYMBOL)
    qty = int(kelly["position_dollars"] / entry_price)

    if qty < 1:
        log.warning(f"Kelly position too small for one share (${kelly['position_dollars']:.0f} / ${entry_price:.2f})")
        return

    order_id = broker.place_bracket_order(
        symbol=config.LIVE_SYMBOL,
        qty=qty,
        entry_price=entry_price,
        target_pct=config.TARGET_GAIN_PCT_QQQ_HOURLY,
        stop_pct=config.STOP_LOSS_PCT_QQQ_HOURLY,
    )
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
        id="qqq_hourly_bar",
        name="QQQ Hourly Bar Check",
        max_instances=1,
        coalesce=True,
    )

    mode_str = "PAPER" if config.LIVE_PAPER_MODE else "*** LIVE MONEY ***"
    log.info(f"Scheduler started | mode={mode_str} | symbol={config.LIVE_SYMBOL}")
    log.info("Firing at :32 past each hour, Mon–Fri 9:32–15:32 ET")
    log.info("Press Ctrl+C to stop")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="MONAD Quant — QQQ Hourly Live Trader")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live Alpaca account (real money). Omit for paper trading.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run on_bar() once immediately then exit (for testing).",
    )
    args = parser.parse_args()

    if args.live:
        config.LIVE_PAPER_MODE = False
        log.warning("=" * 60)
        log.warning("LIVE MODE — THIS WILL TRADE WITH REAL MONEY")
        log.warning("=" * 60)
    else:
        config.LIVE_PAPER_MODE = True
        log.info("Paper mode (safe for testing)")

    state.init_db()

    if args.once:
        on_bar()
        _log_summary()
        return

    run_scheduler()


if __name__ == "__main__":
    main()
