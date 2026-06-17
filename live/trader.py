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
from live import alerts, broker, signals, state

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


def _infer_bracket_exit(position, ref_price: float) -> tuple[float, str]:
    """Infer which bracket leg (TP or SL) filled when IBKR fill data is unavailable.

    Direction-aware. For longs: TP > entry > SL, target is "above", stop is "below".
    For shorts: TP < entry < SL, target is "below", stop is "above". The
    ordering is inferred from the stored TP/SL values rather than the direction
    column so legacy positions without `direction` still work.
    """
    tp = position.target_price
    sl = position.stop_price
    entry = position.entry_price
    direction = getattr(position, "direction", None) or (
        "long" if (tp is not None and sl is not None and tp >= sl) else "long"
    )

    if tp is None or sl is None:
        # Legacy position without stored TP/SL — use reference price
        if direction == "long":
            exit_type = "target_hit" if ref_price >= entry else "stop_hit"
        else:
            exit_type = "target_hit" if ref_price <= entry else "stop_hit"
        log.info(f"Infer exit (no TP/SL stored, {direction}): ref={ref_price:.2f}, entry={entry:.2f} → {exit_type}")
        return ref_price, exit_type

    if direction == "long":
        # TP is above entry, SL is below entry.
        if ref_price >= tp:
            log.info(f"Infer exit (long): ref={ref_price:.2f} >= TP={tp:.2f} → target_hit")
            return tp, "target_hit"
        if ref_price <= sl:
            log.info(f"Infer exit (long): ref={ref_price:.2f} <= SL={sl:.2f} → stop_hit")
            return sl, "stop_hit"
    else:  # short
        # TP is below entry, SL is above entry.
        if ref_price <= tp:
            log.info(f"Infer exit (short): ref={ref_price:.2f} <= TP={tp:.2f} → target_hit")
            return tp, "target_hit"
        if ref_price >= sl:
            log.info(f"Infer exit (short): ref={ref_price:.2f} >= SL={sl:.2f} → stop_hit")
            return sl, "stop_hit"

    # Ambiguous: price is between SL and TP. Use distance to decide.
    dist_to_tp = abs(ref_price - tp)
    dist_to_sl = abs(ref_price - sl)
    if dist_to_tp <= dist_to_sl:
        log.info(f"Infer exit (ambiguous {direction}, closer to TP): ref={ref_price:.2f}, TP={tp:.2f}, SL={sl:.2f} → target_hit")
        return tp, "target_hit"
    else:
        log.info(f"Infer exit (ambiguous {direction}, closer to SL): ref={ref_price:.2f}, TP={tp:.2f}, SL={sl:.2f} → stop_hit")
        return sl, "stop_hit"


def _get_asset_config() -> dict:
    """Returns the ASSETS dict entry for the current LIVE_SYMBOL."""
    mode = f"{config.LIVE_SYMBOL}_HOURLY"
    if mode not in config.ASSETS:
        raise ValueError(f"No ASSETS config for mode '{mode}'. Check config.LIVE_SYMBOL.")
    return config.ASSETS[mode]


# ── Core logic ────────────────────────────────────────────────────────────────

def _resolve_mark_price(symbol: str, bar_close: float | None = None) -> tuple[float | None, str]:
    """Resolve mark price using the best available source.

    Returns (price, source) where source is one of:
      "live"       — real-time IBKR price
      "delayed"    — delayed IBKR data
      "last_close" — most recent bar close from signal data
      "unavailable"
    """
    # 1. Try live broker price (get_tradeable_price tries live then delayed)
    try:
        price = broker.get_tradeable_price(symbol)
        # get_tradeable_price logs whether it used live or delayed attr
        # We check: if it succeeded, it's at least "delayed" quality
        # The function tries live first, then delayed — we can't distinguish
        # from the return value alone, so call it "live" (broker-sourced)
        return price, "live"
    except RuntimeError:
        pass

    # 2. Try yfinance as delayed fallback
    try:
        from live.broker import _yfinance_fallback
        price = _yfinance_fallback(symbol)
        if price and price > 0:
            return price, "delayed"
    except Exception:
        pass

    # 3. Fall back to stored bar close
    if bar_close is not None and bar_close > 0:
        return bar_close, "last_close"

    return None, "unavailable"


def _sync_account_and_mark(bar_close: float | None = None) -> None:
    """Sync account snapshot + mark price to state.db every cycle."""
    mark_price, mark_source = _resolve_mark_price(config.LIVE_SYMBOL, bar_close=bar_close)
    mark_time = datetime.now(timezone.utc).isoformat() if mark_price else None

    try:
        account = broker.get_account()
        state.save_account_snapshot(
            equity=getattr(account, "equity", None),
            cash=getattr(account, "cash", None),
            buying_power=getattr(account, "buying_power", None),
            position_value=getattr(account, "position_value", None),
            ibkr_connected=True,
            mark_price=mark_price,
            mark_source=mark_source,
            mark_time=mark_time,
        )
    except Exception as exc:
        log.warning(f"Account sync failed: {exc}")
        # Still try to save mark even without account data
        state.save_account_snapshot(
            equity=None, cash=None,
            ibkr_connected=False,
            mark_price=mark_price,
            mark_source=mark_source,
            mark_time=mark_time,
        )

    if mark_price:
        log.info(f"Mark: ${mark_price:.2f} ({mark_source})")


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
        exc_detail = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
        state.set_monitor_status(status="error", cycle_action=cycle_action, details=exc_detail)
        state.add_monitor_event("ERROR", "cycle", f"Unhandled on_bar exception: {exc_detail}")
        alerts.alert_error(f"Unhandled on_bar exception: {exc_detail}", level="ERROR")
        raise
    finally:
        # Always disconnect at end of cycle. With hourly scheduling, keeping a
        # connection open for ~60min causes stale sockets and clientId conflicts.
        # Connect-per-cycle is clean and reliable for this cadence.
        try:
            broker.disconnect()
        except Exception:
            pass
        elapsed = _time.monotonic() - t0
        log.info(f"CYCLE | action={cycle_action} | elapsed={elapsed:.1f}s")


def _on_bar_inner() -> str:
    """Core on_bar logic. Returns a short action label for cycle logging.

    Control flow:
        1. Compute + persist the signal snapshot (always).
        2. If a position exists: reconcile/exit as needed. The *reconcile* and
           *force-close* paths set ``exit_action`` and fall through to the
           entry block. The *holding* and *pending_close-unresolved* paths
           return early because a new entry would stack onto an open trade.
        3. If flat (or we just closed in this cycle), evaluate the entry
           signal and place a new bracket. A trade on the same cycle that
           just closed another is labeled ``{exit_action}_then_entry`` — this
           is the fix for the "signal on chart but no trade" bug.
    """

    # ── Always compute and persist signal snapshot ──────────────────────────
    # This runs every cycle (holding, exit, entry, no-signal) so the dashboard
    # always has fresh signal data and a recent bar_close for mark fallback.
    #
    # Safety contract: signals.get_current_signal() is the sole source of truth
    # for entry evaluation. If it raises (yfinance down, stale data, insufficient
    # bars, NaN features) we leave sig_info=None and the entry block below
    # refuses to place a trade. We NEVER fall back to a stale stored signal
    # snapshot for entry decisions — stored snapshots are only used for the
    # mark-price display on the dashboard.
    sig_info = None
    bar_close_fallback = None
    try:
        sig_info = signals.get_current_signal()
        bar_close_fallback = sig_info.get("bar_close")
        state.save_signal_snapshot(
            sig_info["signal"],
            str(sig_info["bar_time"]),
            sig_info["bar_close"],
            sig_info.get("rsi"),
            sig_info.get("vwap_zscore"),
            sig_info.get("momentum_signal"),
            sig_info.get("volume_signal"),
        )
    except RuntimeError as exc:
        # Escalation: first failure = ERROR, N+ consecutive failures = CRITICAL.
        # Operator should wake up when signal fetch has been broken multiple cycles.
        recent = state.get_recent_monitor_events(limit=5)
        consecutive_failures = 1
        for ev in recent:
            cat = ev.get("category", "")
            lvl = (ev.get("level") or "").upper()
            if cat == "signal" and lvl in ("ERROR", "CRITICAL"):
                consecutive_failures += 1
            else:
                break
        threshold = getattr(config, "LIVE_SIGNAL_FAIL_ALERT_THRESHOLD", 2)
        level = "CRITICAL" if consecutive_failures >= threshold else "ERROR"
        log.error(
            f"Signal computation failed ({level}, streak={consecutive_failures}): {exc}"
        )
        alerts.alert_error(
            f"Signal fetch failed ({consecutive_failures}x): {exc}. Entries blocked.",
            level=level,
        )
        state.add_monitor_event(
            level, "signal",
            f"Signal fetch failed ({consecutive_failures}x): {exc}. Entries blocked.",
        )
        # Use stored snapshot's bar_close ONLY for dashboard mark fallback.
        # sig_info stays None so the entry block below refuses any trade.
        stored = state.get_signal_snapshot()
        if stored:
            bar_close_fallback = stored.get("bar_close")

    position = state.get_position()
    exit_action: str | None = None  # set when we close a position this cycle

    # ── Manage existing position ──────────────────────────────────────────────
    if position is not None:
        position_direction = getattr(position, "direction", None) or "long"

        # ── Retry reconciliation for pending_close positions ────────────────
        if position.status == "pending_close":
            fill = broker.get_bracket_fill(
                position.bracket_order_id, direction=position_direction,
                tp_order_id=getattr(position, "tp_order_id", None),
                sl_order_id=getattr(position, "sl_order_id", None),
            )
            if fill is not None:
                ret = _signed_return(position_direction, position.entry_price, fill["fill_price"])
                exit_type = fill["exit_type"]
                log.info(
                    f"Pending close reconciled | fill_price={fill['fill_price']:.2f} | "
                    f"fill_time={fill['fill_time']} | ret={ret:+.4%} → {exit_type}"
                )
                state.finalize_pending_close(
                    return_pct=ret, exit_type=exit_type,
                    exit_price=fill["fill_price"],
                )
                state.add_monitor_event("INFO", "fill", f"Pending close reconciled: {exit_type} @ {fill['fill_price']:.2f}")
                _sync_account_and_mark(bar_close=fill["fill_price"])
                _log_summary()
                summary = state.get_trade_summary()
                alerts.alert_exit(
                    position.symbol, position_direction, position.entry_price,
                    fill["fill_price"], ret, exit_type,
                    total_trades=summary["total"], win_rate=summary["win_rate"],
                )
                exit_action = f"reconciled_{exit_type}"
                # Fall through to entry check — same cycle can place a new trade
            else:
                retries = state.increment_pending_close_retries()
                # After N failed retries, finalize with estimated price.
                # IBKR fill data is permanently unavailable (e.g. filled on a previous
                # trading day and reqExecutions also failed). Continuing to block
                # new entries indefinitely is worse than recording estimated PnL.
                max_retries = config.PENDING_CLOSE_MAX_RETRIES
                if retries >= max_retries and position.estimated_exit_price is not None:
                    est_price = position.estimated_exit_price
                    ret = _signed_return(position_direction, position.entry_price, est_price)
                    warning_msg = (
                        f"Pending close force-finalized after {retries} retries | "
                        f"est_price={est_price:.2f} | est_ret={ret:+.4%} (ESTIMATED — fill data never found)"
                    )
                    log.critical(warning_msg)
                    state.add_monitor_event("CRITICAL", "fill", warning_msg)
                    alerts.alert_error(warning_msg, level="CRITICAL")
                    state.finalize_pending_close(
                        return_pct=ret, exit_type="estimated_close",
                        exit_price=est_price,
                    )
                    _sync_account_and_mark(bar_close=est_price)
                    _log_summary()
                    exit_action = "reconciled_estimated"
                    # Fall through to entry check
                else:
                    log.info(
                        f"Pending close still unresolved ({retries}/{max_retries}) — blocking new entries | "
                        f"bracket_id={position.bracket_order_id}"
                    )
                    _sync_account_and_mark(bar_close=bar_close_fallback)
                    return "pending_close_unresolved"

        else:
            # Reconcile: check if bracket TP/SL already filled since last bar
            broker_pos = broker.get_open_position(position.symbol)
            if broker_pos is None or broker_pos["qty"] == 0:
                # Bracket order already exited — fetch actual fill data from IBKR
                fill = broker.get_bracket_fill(
                    position.bracket_order_id, direction=position_direction,
                    tp_order_id=getattr(position, "tp_order_id", None),
                    sl_order_id=getattr(position, "sl_order_id", None),
                )
                if fill is not None:
                    ret = _signed_return(position_direction, position.entry_price, fill["fill_price"])
                    exit_type = fill["exit_type"]
                    log.info(
                        f"Bracket filled | fill_price={fill['fill_price']:.2f} | "
                        f"fill_time={fill['fill_time']} | ret={ret:+.4%} → {exit_type}"
                    )
                    state.close_position(return_pct=ret, exit_type=exit_type,
                                         exit_price=fill["fill_price"])
                    _sync_account_and_mark(bar_close=fill["fill_price"])
                    _log_summary()
                    summary = state.get_trade_summary()
                    alerts.alert_exit(
                        position.symbol, position_direction, position.entry_price,
                        fill["fill_price"], ret, exit_type,
                        total_trades=summary["total"], win_rate=summary["win_rate"],
                    )
                    exit_action = f"exit_{exit_type}"
                    # Fall through to entry check
                else:
                    # Fill data unavailable — IBKR paper doesn't retain execution
                    # history across disconnections. Infer exit from stored TP/SL
                    # prices and finalize immediately instead of blocking entries.
                    ref_price = broker.get_reference_price(position.symbol)
                    exit_price, exit_type = _infer_bracket_exit(position, ref_price)
                    ret = _signed_return(position_direction, position.entry_price, exit_price)
                    warning_msg = (
                        f"Fill data unavailable — inferred {exit_type} @ {exit_price:.2f} | "
                        f"ret={ret:+.4%} (inferred from TP/SL prices, not actual fill)"
                    )
                    log.warning(warning_msg)
                    state.add_monitor_event("WARNING", "fill", warning_msg)
                    state.close_position(return_pct=ret, exit_type=exit_type,
                                         exit_price=exit_price)
                    _sync_account_and_mark(bar_close=exit_price)
                    _log_summary()
                    summary = state.get_trade_summary()
                    alerts.alert_exit(
                        position.symbol, position_direction, position.entry_price,
                        exit_price, ret, exit_type, inferred=True,
                        total_trades=summary["total"], win_rate=summary["win_rate"],
                    )
                    exit_action = f"exit_{exit_type}_inferred"
                    # Fall through to entry check
            else:
                bar_count = state.increment_bar_count()
                log.info(
                    f"Open {position_direction} position: {position.qty} {position.symbol} @ "
                    f"{position.entry_price:.2f} | bar {bar_count}/{config.MAX_TRADE_BARS_LIVE}"
                )

                # ── Software stop-loss: safety net if IBKR doesn't trigger the stop ──
                # IBKR paper accounts can miss stop triggers. Also protects against
                # stale DAY-tif stops that expired overnight before the GTC fix.
                asset_config = _get_asset_config()
                mark_price, mark_source = _resolve_mark_price(position.symbol, bar_close=bar_close_fallback)
                use_sw_tp = getattr(config, "USE_SOFTWARE_TAKE_PROFIT", True)
                if position_direction == "long":
                    stop_trigger = round(position.entry_price * (1 - asset_config["stop_loss_pct"]), 2)
                    stop_hit = mark_price is not None and mark_price <= stop_trigger
                    target_trigger = round(position.entry_price * (1 + asset_config["target_gain_pct"]), 2)
                    target_hit_sw = use_sw_tp and mark_price is not None and mark_price >= target_trigger
                else:
                    stop_trigger = round(position.entry_price * (1 + asset_config["stop_loss_pct"]), 2)
                    stop_hit = mark_price is not None and mark_price >= stop_trigger
                    target_trigger = round(position.entry_price * (1 - asset_config["target_gain_pct"]), 2)
                    target_hit_sw = use_sw_tp and mark_price is not None and mark_price <= target_trigger

                if stop_hit:
                    log.critical(
                        f"SOFTWARE STOP triggered ({position_direction}) | mark={mark_price:.2f} ({mark_source}) "
                        f"vs stop={stop_trigger:.2f} | IBKR stop did not fire — forcing close"
                    )
                    state.add_monitor_event(
                        "CRITICAL", "stop",
                        f"SOFTWARE STOP triggered: mark={mark_price:.2f} ({mark_source}) "
                        f"breached stop={stop_trigger:.2f} but IBKR bracket did not execute. "
                        f"Forcing close. Check IBKR bracket order status.",
                    )
                    close_fill = broker.cancel_and_close(
                        position.symbol, position.bracket_order_id, position.qty,
                        direction=position_direction,
                        tp_order_id=getattr(position, "tp_order_id", None),
                        sl_order_id=getattr(position, "sl_order_id", None),
                    )
                    if close_fill is not None:
                        exit_price = close_fill["fill_price"]
                        ret = _signed_return(position_direction, position.entry_price, exit_price)
                        log.info(f"Software stop filled | price={exit_price:.2f} | ret={ret:+.4%}")
                    else:
                        exit_price = mark_price
                        ret = _signed_return(position_direction, position.entry_price, exit_price)
                        log.critical(f"SOFTWARE STOP fill unavailable — using mark {exit_price:.2f} | est_ret={ret:+.4%}")
                        state.add_monitor_event("CRITICAL", "stop", f"Software stop fill unavailable — using mark={exit_price:.2f}, est_ret={ret:+.4%}. Verify position is actually closed.")
                    state.close_position(return_pct=ret, exit_type="stop_hit", exit_price=exit_price)
                    _sync_account_and_mark(bar_close=exit_price)
                    _log_summary()
                    summary = state.get_trade_summary()
                    alerts.alert_error(
                        f"SOFTWARE STOP triggered on {position.symbol} | "
                        f"mark={mark_price:.2f} vs stop={stop_trigger:.2f} | ret={ret:+.4%}",
                        level="CRITICAL",
                    )
                    alerts.alert_exit(
                        position.symbol, position_direction, position.entry_price,
                        exit_price, ret, "stop_hit (software)",
                        total_trades=summary["total"], win_rate=summary["win_rate"],
                    )
                    exit_action = "exit_software_stop"
                    # Fall through to entry check
                elif target_hit_sw:
                    # ── Software take-profit: safety net if IBKR doesn't fill the TP ──
                    # The paper bracket TP frequently fails to fill, letting winners
                    # ride past target until the time-exit (which inflated returns and
                    # left the position unprotected). Cap the winner at target by
                    # force-closing at market, mirroring the software stop above.
                    log.warning(
                        f"SOFTWARE TAKE-PROFIT triggered ({position_direction}) | mark={mark_price:.2f} ({mark_source}) "
                        f"vs target={target_trigger:.2f} | IBKR TP did not fire — forcing close"
                    )
                    state.add_monitor_event(
                        "WARNING", "take_profit",
                        f"SOFTWARE TAKE-PROFIT triggered: mark={mark_price:.2f} ({mark_source}) "
                        f"reached target={target_trigger:.2f} but IBKR bracket TP did not execute. "
                        f"Forcing close. Check IBKR bracket order status.",
                    )
                    close_fill = broker.cancel_and_close(
                        position.symbol, position.bracket_order_id, position.qty,
                        direction=position_direction,
                    )
                    if close_fill is not None:
                        exit_price = close_fill["fill_price"]
                        ret = _signed_return(position_direction, position.entry_price, exit_price)
                        log.info(f"Software take-profit filled | price={exit_price:.2f} | ret={ret:+.4%}")
                    else:
                        exit_price = mark_price
                        ret = _signed_return(position_direction, position.entry_price, exit_price)
                        log.warning(f"Software take-profit fill unavailable — using mark {exit_price:.2f} | est_ret={ret:+.4%}")
                        state.add_monitor_event("WARNING", "take_profit", f"Software take-profit fill unavailable — using mark={exit_price:.2f}, est_ret={ret:+.4%}. Verify position is actually closed.")
                    state.close_position(return_pct=ret, exit_type="target_hit", exit_price=exit_price)
                    _sync_account_and_mark(bar_close=exit_price)
                    _log_summary()
                    summary = state.get_trade_summary()
                    alerts.alert_exit(
                        position.symbol, position_direction, position.entry_price,
                        exit_price, ret, "target_hit (software)",
                        total_trades=summary["total"], win_rate=summary["win_rate"],
                    )
                    exit_action = "exit_software_take_profit"
                    # Fall through to entry check
                elif bar_count >= config.MAX_TRADE_BARS_LIVE:
                    log.info("Time-exit triggered — cancelling bracket and closing")
                    close_fill = broker.cancel_and_close(
                        position.symbol, position.bracket_order_id, position.qty,
                        direction=position_direction,
                        tp_order_id=getattr(position, "tp_order_id", None),
                        sl_order_id=getattr(position, "sl_order_id", None),
                    )
                    if close_fill is not None:
                        # Actual fill price from the market close — preferred PnL source
                        exit_price = close_fill["fill_price"]
                        ret = _signed_return(position_direction, position.entry_price, exit_price)
                        log.info(f"Time-exit filled | price={exit_price:.2f} | ret={ret:+.4%}")
                    else:
                        # Fill retrieval failed — fall back to reference price estimate.
                        # This is the one live exit path where PnL may be estimated.
                        exit_price = broker.get_reference_price(position.symbol)
                        ret = _signed_return(position_direction, position.entry_price, exit_price)
                        warning_msg = (
                            f"Time-exit fill unavailable — using reference price {exit_price:.2f} | "
                            f"estimated_ret={ret:+.4%}"
                        )
                        log.warning(warning_msg)
                        state.add_monitor_event("WARNING", "time_exit", warning_msg)
                    state.close_position(return_pct=ret, exit_type="time_exit", exit_price=exit_price)
                    _sync_account_and_mark(bar_close=exit_price)
                    _log_summary()
                    summary = state.get_trade_summary()
                    alerts.alert_exit(
                        position.symbol, position_direction, position.entry_price,
                        exit_price, ret, "time_exit",
                        total_trades=summary["total"], win_rate=summary["win_rate"],
                    )
                    exit_action = "exit_time_exit"
                    # Fall through to entry check
                else:
                    # Position is still open and within bar limit — wait for bracket exit
                    log.info("Position within bar limit, bracket order monitoring exit")
                    _sync_account_and_mark(bar_close=bar_close_fallback)
                    return f"holding_bar_{bar_count}"

    # ── Check for new entry signal ────────────────────────────────────────────
    # Reached when (a) we were flat at the top of the cycle, or (b) we just
    # closed a position and want to place a back-to-back trade on the same bar.
    if sig_info is None:
        # Signal fetch failed at the top of the cycle — the monitor event was
        # already logged there (with escalation level). Just refuse the entry
        # and return. Never trade on a missing signal.
        log.error("Entry refused: signal fetch failed this cycle (see monitor event)")
        if exit_action is None:
            _sync_account_and_mark(bar_close=bar_close_fallback)
        return exit_action or "signal_error"

    raw_signal = sig_info["signal"]

    # Resolve the trade direction for this signal. The live signal pipeline
    # computes both longs (+1) and shorts (-1); shorts only route through when
    # config.TRADER_ALLOW_SHORTS is explicitly enabled.
    entry_direction: str | None = None
    if raw_signal == 1:
        entry_direction = "long"
    elif raw_signal == -1:
        if getattr(config, "TRADER_ALLOW_SHORTS", False):
            entry_direction = "short"
        else:
            log.info("Short signal fired but TRADER_ALLOW_SHORTS is False — skipping")

    if entry_direction is None:
        log.info(f"No actionable entry signal (signal={raw_signal})")
        if exit_action is None:
            _sync_account_and_mark(bar_close=bar_close_fallback)
        return exit_action or "no_signal"

    # ── Size and place the trade ──────────────────────────────────────────────
    # Skip re-sync when we already synced immediately after the exit — the
    # broker.get_account() call below is what actually feeds sizing.
    if exit_action is None:
        _sync_account_and_mark(bar_close=bar_close_fallback)
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
        return exit_action or "qty_too_small"

    if config.LIVE_DRY_RUN:
        # In dry-run, use bar_close as approximate basis (no broker call)
        if entry_direction == "long":
            target_p = round(bar_close * (1 + asset_config["target_gain_pct"]), 2)
            stop_p = round(bar_close * (1 - asset_config["stop_loss_pct"]), 2)
        else:
            target_p = round(bar_close * (1 - asset_config["target_gain_pct"]), 2)
            stop_p = round(bar_close * (1 + asset_config["stop_loss_pct"]), 2)
        log.info(
            f"DRY RUN — would place: {entry_direction.upper()} {qty} {config.LIVE_SYMBOL} "
            f"@ ~{bar_close:.2f} | TP~={target_p:.2f} | SL~={stop_p:.2f} "
            f"(approx; live uses broker price)"
        )
        return f"{exit_action}_then_dry_run_entry" if exit_action else "dry_run_entry"

    result = broker.place_bracket_order(
        symbol=config.LIVE_SYMBOL,
        qty=qty,
        target_pct=asset_config["target_gain_pct"],
        stop_pct=asset_config["stop_loss_pct"],
        direction=entry_direction,
    )
    if result is None:
        error_msg = "Bracket order failed — skipping this entry. Will retry next bar if signal persists."
        log.error(error_msg)
        state.add_monitor_event("ERROR", "order", error_msg)
        return exit_action or "order_failed"

    # Record the broker's fill_basis as entry price — this is the live market price
    # at order time, matching the backtest convention of entering at next-bar open.
    entry_price = result["fill_basis"]
    order_id = result["order_id"]
    state.open_position(
        config.LIVE_SYMBOL, entry_price, qty, order_id,
        target_price=result.get("target_price"),
        stop_price=result.get("stop_price"),
        direction=entry_direction,
        tp_order_id=result.get("tp_order_id"),
        sl_order_id=result.get("sl_order_id"),
    )
    log.info(f"ENTRY placed: {entry_direction.upper()} {qty} shares @ ~{entry_price:.2f} (fill_basis)")
    entry_event = f"Entry placed: {entry_direction.upper()} {qty} {config.LIVE_SYMBOL} @ {entry_price:.2f}"
    if exit_action:
        entry_event = f"{entry_event} (back-to-back after {exit_action})"
    state.add_monitor_event("INFO", "entry", entry_event)
    alerts.alert_entry(
        config.LIVE_SYMBOL, entry_direction, qty, entry_price,
        position_pct=sizing["position_pct"],
        back_to_back=exit_action,
    )
    return f"{exit_action}_then_entry" if exit_action else "entry_placed"


def _signed_return(direction: str, entry_price: float, exit_price: float) -> float:
    """Return percentage, signed by direction.

    Longs profit when exit > entry; shorts profit when exit < entry.
    """
    raw = (exit_price - entry_price) / entry_price
    return raw if direction == "long" else -raw


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

    state.init_db()
    state.set_monitor_status(status="idle", cycle_action="startup", details="trader initialized")

    # Verify IBKR connection
    try:
        account = broker.get_account()
        state.save_account_snapshot(
            equity=getattr(account, "equity", None),
            cash=getattr(account, "cash", None),
            buying_power=getattr(account, "buying_power", None),
            position_value=getattr(account, "position_value", None),
            ibkr_connected=True,
        )
        log.info(f"IBKR connected | equity=${account.equity:,.2f} | cash=${account.cash:,.2f}")
    except Exception as exc:
        state.save_account_snapshot(
            equity=None,
            cash=None,
            buying_power=None,
            position_value=None,
            ibkr_connected=False,
        )
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
