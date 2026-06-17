#!/usr/bin/env python3
"""
diagnose_brackets.py — Find out WHY IBKR bracket take-profit / stop-loss legs
are not filling in the MONAD-quant live trader.

Background (from data/live_runs/analysis_2026-06-17):
  In ~9 weeks of TQQQ paper trading, BOTH bracket legs failed systematically:
    - 9 `time_exit` trades rode PAST the +1% take-profit (a resting LMT child
      should have filled at +1%).
    - 6 CRITICAL "software stop triggered — IBKR bracket did not execute".
  When both legs fail, the likely cause is that the child orders are not LIVE at
  the broker (not transmitted / cancelled / inactive / not simulated by the paper
  engine) rather than a one-off price-simulation miss. This script queries IBKR
  directly to confirm.

It does TWO things:
  1. READ-ONLY inspection (default, always safe): connects and dumps open orders,
     completed orders, today's executions, and current positions — with the exact
     fields that reveal a broken bracket (status, orderType, tif, transmit,
     parentId, ocaGroup, lmtPrice, auxPrice).
  2. --place-test-bracket (opt-in, PAPER ONLY, takes NO position): places a parent
     BUY LMT a few % BELOW market so it never fills, with the same GTC bracket
     children the live code uses, waits, prints each leg's status, then cancels
     the whole bracket. This shows whether the broker ACCEPTS and HOLDS the child
     legs (expected: children sit 'PreSubmitted' pending the parent). If children
     show 'Inactive' / 'ApiCancelled' / never appear, that is the bug.

Run on the Pi with the project venv:
    venv/bin/python tools/diagnose_brackets.py
    venv/bin/python tools/diagnose_brackets.py --place-test-bracket --i-understand-this-trades

Uses a DISTINCT clientId (default 51) so it will not collide with the running
trader (clientId=1). It NEVER modifies state.db and makes NO live-account changes.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

# Import project config the same way live/broker.py does.
sys.path.insert(0, ".")
try:
    import config
except Exception as exc:  # pragma: no cover - env issue
    print(f"FATAL: cannot import config: {exc}")
    sys.exit(2)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hr(title: str) -> None:
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78)


def _fmt_order(o) -> str:
    """One-line dump of the fields that matter for diagnosing a stuck bracket."""
    return (
        f"id={getattr(o, 'orderId', '?')} "
        f"parent={getattr(o, 'parentId', 0) or '-'} "
        f"{getattr(o, 'action', '?')} {getattr(o, 'totalQuantity', '?')} "
        f"type={getattr(o, 'orderType', '?')} "
        f"tif={getattr(o, 'tif', '?')} "
        f"transmit={getattr(o, 'transmit', '?')} "
        f"lmt={getattr(o, 'lmtPrice', '')} aux={getattr(o, 'auxPrice', '')} "
        f"oca={getattr(o, 'ocaGroup', '') or '-'}"
    )


def connect(args):
    from ib_insync import IB

    ib = IB()
    port = config.IBKR_PORT_PAPER if config.LIVE_PAPER_MODE else config.IBKR_PORT_LIVE
    mode = "PAPER" if config.LIVE_PAPER_MODE else "LIVE"
    print(f"[{_ts()}] Connecting to IBKR {mode} at "
          f"{config.IBKR_HOST}:{port} (clientId={args.client_id}) ...")
    try:
        ib.connect(config.IBKR_HOST, port, clientId=args.client_id, timeout=args.timeout)
    except Exception as exc:
        print(f"\nCONNECT FAILED: {type(exc).__name__}: {exc}")
        print("\nThis itself is a finding: the live trader logged 46 "
              "ConnectionRefused errors over the run.")
        print("Checklist: is IB Gateway / TWS running? Is the API enabled "
              f"(Configure > API > Settings) on port {port}? Is "
              "'Allow connections from localhost' on? Is the clientId free?")
        sys.exit(1)
    print(f"[{_ts()}] Connected. serverVersion={ib.client.serverVersion()} "
          f"accounts={ib.managedAccounts()}")
    return ib


def inspect(ib) -> None:
    # ── Open orders (across all API clients) ──────────────────────────────────
    _hr("OPEN ORDERS (reqAllOpenOrders) — live resting orders at the broker")
    try:
        ib.reqAllOpenOrders()
        ib.sleep(1.0)
    except Exception as exc:
        print(f"  reqAllOpenOrders error: {exc}")
    open_trades = ib.openTrades()
    if not open_trades:
        print("  (none) — no resting orders. If a position is open with no TP/SL "
              "here, the bracket children are MISSING — the core bug.")
    for t in open_trades:
        st = t.orderStatus
        print(f"  • {_fmt_order(t.order)}  status={st.status} "
              f"filled={st.filled} remaining={st.remaining}")

    # ── Current positions at broker ───────────────────────────────────────────
    _hr("BROKER POSITIONS (ib.positions) — should each have matching TP+SL above")
    positions = ib.positions()
    if not positions:
        print("  (flat) — no open positions at IBKR.")
    for p in positions:
        print(f"  • {p.contract.symbol} qty={p.position} avgCost={p.avgCost}")
    print("\n  → Cross-check: every open position should have a LMT (take-profit) "
          "AND a STP (stop) in OPEN ORDERS above. A position with no children = "
          "unprotected = the failure mode behind the time_exit/software-stop events.")

    # ── Completed orders (survives reconnects) ────────────────────────────────
    _hr("COMPLETED ORDERS (reqCompletedOrders) — how recent brackets ENDED")
    try:
        completed = ib.reqCompletedOrders(apiOnly=False)
        ib.sleep(1.0)
    except Exception as exc:
        completed = []
        print(f"  reqCompletedOrders error: {exc}")
    if not completed:
        completed = ib.trades()
    shown = 0
    for t in completed:
        st = getattr(t, "orderStatus", None)
        status = st.status if st else "?"
        otype = getattr(t.order, "orderType", "?")
        # Highlight the smoking gun: TP/SL children that were Cancelled/Inactive
        # instead of Filled.
        flag = ""
        if otype in ("LMT", "STP", "STP LMT") and getattr(t.order, "parentId", 0):
            if status in ("Cancelled", "ApiCancelled", "Inactive"):
                flag = "   <-- child ended WITHOUT filling (suspect)"
            elif status == "Filled":
                flag = "   <-- child FILLED (healthy)"
        print(f"  • {_fmt_order(t.order)}  status={status}{flag}")
        shown += 1
        if shown >= args_max:
            print(f"  ... (truncated at {args_max}; use --max to see more)")
            break
    if shown == 0:
        print("  (none in this session — completed-order history resets per session/day)")

    # ── Today's executions / fills ────────────────────────────────────────────
    _hr("EXECUTIONS / FILLS today (ib.fills) — what actually traded")
    fills = ib.fills()
    if not fills:
        print("  (none today)")
    for f in fills[-args_max:]:
        ex = f.execution
        print(f"  • {f.contract.symbol} {ex.side} qty={ex.shares} px={ex.price} "
              f"time={ex.time} orderId={ex.orderId} perm={ex.permId}")


def place_test_bracket(ib, args) -> None:
    """PAPER-ONLY. Places an UNFILLABLE parent (BUY LMT well below market) with the
    same GTC bracket children as live/broker.py, inspects child statuses, cancels.
    Takes NO position (parent never fills)."""
    if not config.LIVE_PAPER_MODE:
        print("\nREFUSING: --place-test-bracket only runs in PAPER mode "
              "(config.LIVE_PAPER_MODE is False). Aborting.")
        sys.exit(3)
    if not args.i_understand_this_trades:
        print("\nThis mode submits (then cancels) real PAPER orders. Re-run with "
              "--i-understand-this-trades to proceed.")
        sys.exit(3)

    from ib_insync import Stock

    symbol = config.LIVE_SYMBOL
    _hr(f"TEST BRACKET on {symbol} (PAPER, unfillable parent, no position taken)")
    contract = Stock(symbol, "SMART", "USD")
    ib.qualifyContracts(contract)

    # Reference price: try market data, else yfinance (project's own fallback path).
    ref = None
    try:
        tk = ib.reqMktData(contract, "", False, False)
        ib.sleep(2.0)
        for attr in ("last", "close", "marketPrice"):
            v = getattr(tk, attr, None) if attr != "marketPrice" else tk.marketPrice()
            if v and v == v and v > 0:  # not NaN, positive
                ref = float(v)
                break
    except Exception as exc:
        print(f"  market data unavailable ({exc}); falling back to yfinance")
    if ref is None:
        try:
            import yfinance as yf
            fi = yf.Ticker(symbol).fast_info
            ref = float(getattr(fi, "last_price", None) or fi["lastPrice"])
        except Exception as exc:
            print(f"  could not determine reference price: {exc}; using 50.0 placeholder")
            ref = 50.0
    print(f"  reference price ≈ {ref:.2f}")

    # Parent BUY LMT 5% BELOW market → rests, never fills → no position.
    limit_price = round(ref * 0.95, 2)
    target_price = round(limit_price * (1 + 0.01), 2)   # +1% TP (LMT child)
    stop_price = round(limit_price * (1 - 0.005), 2)    # -0.5% SL (STP child)
    print(f"  parent BUY LMT @ {limit_price} (rests, won't fill) | "
          f"TP={target_price} | SL={stop_price}")

    bracket = ib.bracketOrder("BUY", 1, limitPrice=limit_price,
                              takeProfitPrice=target_price, stopLossPrice=stop_price)
    for o in bracket[1:]:
        o.tif = "GTC"   # mirror live/broker.py exactly
    trades = []
    try:
        for o in bracket:
            trades.append(ib.placeOrder(contract, o))
        ib.sleep(3.0)
        print("\n  Leg statuses after placement (the key result):")
        for t in trades:
            role = "PARENT" if not getattr(t.order, "parentId", 0) else \
                   ("TP(LMT)" if t.order.orderType == "LMT" else "SL(STP)")
            print(f"    [{role:8}] {_fmt_order(t.order)}  status={t.orderStatus.status}")
        print("\n  Interpretation:")
        print("    • children 'PreSubmitted' (held pending parent) = broker ACCEPTED them (healthy).")
        print("    • children 'Submitted' = live and working.")
        print("    • children 'Inactive'/'ApiCancelled'/absent = broker rejected/dropped them = BUG.")
        print("    • If children look healthy here but live trades still ride past TP, the issue is the")
        print("      PAPER fill-simulation engine, not order submission — a known IBKR paper limitation;")
        print("      the software take-profit fallback is then the correct mitigation.")
    finally:
        _hr("CLEANUP — cancelling test bracket")
        for t in trades:
            try:
                ib.cancelOrder(t.order)
                print(f"  cancelled order {t.order.orderId}")
            except Exception as exc:
                print(f"  cancel {t.order.orderId} failed: {exc}")
        ib.sleep(2.0)
        # Safety: confirm no position was taken.
        pos = [p for p in ib.positions() if p.contract.symbol == symbol]
        if pos:
            print(f"  WARNING: unexpected {symbol} position {pos[0].position} — "
                  "the parent must have filled. Flatten manually in TWS.")
        else:
            print(f"  confirmed flat on {symbol} — no position taken.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--client-id", type=int, default=51,
                    help="IBKR clientId (default 51; live trader uses 1 — keep distinct)")
    ap.add_argument("--timeout", type=float, default=10.0, help="connect timeout seconds")
    ap.add_argument("--max", type=int, default=40, help="max rows per section")
    ap.add_argument("--place-test-bracket", action="store_true",
                    help="PAPER ONLY: submit+cancel an unfillable test bracket to check child acceptance")
    ap.add_argument("--i-understand-this-trades", action="store_true",
                    help="required confirmation for --place-test-bracket")
    args = ap.parse_args()
    global args_max
    args_max = args.max

    ib = connect(args)
    try:
        inspect(ib)
        if args.place_test_bracket:
            place_test_bracket(ib, args)
        _hr("DONE")
        print("Share this output (it contains no secrets — only order metadata) "
              "to decide between: (a) order-submission fix, or (b) software "
              "take-profit fallback for a paper fill-engine limitation.")
    finally:
        ib.disconnect()


if __name__ == "__main__":
    main()
