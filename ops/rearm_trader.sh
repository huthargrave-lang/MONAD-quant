#!/usr/bin/env bash
#
# rearm_trader.sh — Recovery-only re-arm for the MONAD paper trader.
#
# THE PROBLEM IT SOLVES
#   The trader is a long-running process, not a per-day one. An overnight
#   position is reconciled on the next hourly cycle INSIDE that process
#   (live/trader.py — get_open_position() empty -> get_bracket_fill() ->
#   close_position()), NOT at startup. Two real examples from trader.log:
#       2026-07-07 09:32  Bracket filled | 73.54 | ret=-4.0073% -> stop_hit
#       2026-07-15 09:32  Bracket filled | 76.37 | ret=+1.4749% -> target_hit
#   Both brackets filled at 09:30:11 ET and the 09:32 cycle booked them.
#
#   Because the process survives across days, systemd's 09:22 ET
#   monad-trader.timer is a no-op on a normal morning (unit already active =>
#   ExecStartPre never re-runs). So preflight only ever gates COLD starts —
#   and preflight check #6 refuses a cold start while a position is open
#   ("account is NOT flat"). That rule assumes "cold start = starting clean
#   from flat", which held by luck on every previous cold start.
#
#   If the process dies while holding overnight (host reboot, power loss), the
#   09:22 start is vetoed and the bot stays down for the WHOLE session, even
#   though the GTC bracket closes the position at the broker minutes later and
#   the account is flat by ~09:31. Precedent: 2026-06-22 (blocked, 1 check);
#   2026-07-31 (Pi unplugged mid-hold).
#
# WHAT THIS DOES
#   Polls during the session and starts the trader the moment a cold start
#   would genuinely succeed. It NEVER bypasses or weakens preflight — it uses
#   preflight ITSELF as the gate, so all 10 original safety checks still apply.
#   A fixed-time retry would not work: the bracket only fills when price
#   touches TP or SL, which may be minutes or hours after the open.
#
# IDEMPOTENT + FAIL-CLOSED
#   trader already running   -> silent no-op
#   gateway down / not flat  -> silent no-op; NO start attempted, so no
#                               systemd start-burst is consumed
#                               (monad-trader.service: StartLimitBurst=2/600s)
#   preflight passes         -> systemctl start monad-trader.service
#
# Touches NO armed code: monad-trader.service, ops/start_trader.sh,
# ops/preflight_trader_start.sh and live/trader.py are all unchanged. This is
# purely an additional caller of the existing, unmodified start path.
#
# PAPER ONLY — inherits every paper-only guarantee from preflight.
#
set -uo pipefail

REPO="$HOME/MONAD-quant"
LOG_DIR="$REPO/local_logs"
LOG="$LOG_DIR/trader_rearm.log"
UNIT="monad-trader.service"

mkdir -p "$LOG_DIR" 2>/dev/null || true
ts() { date '+%Y-%m-%d %H:%M:%S %Z'; }
note() { echo "$(ts) [rearm] $*" >> "$LOG"; }

# 1. Already running — the normal case on any healthy day. Nothing to do, and
#    we stay silent so the log only ever records real recovery events.
if systemctl is-active --quiet "$UNIT"; then
    exit 0
fi

# 2. systemd latches a unit into 'failed' after StartLimitBurst is exceeded and
#    then refuses further starts until reset. Clear that latch so a legitimate
#    start is not blocked by earlier vetoed attempts. This resets a systemd
#    counter only — it changes no safety gate.
if [ "$(systemctl is-failed "$UNIT" 2>/dev/null)" = "failed" ]; then
    note "unit in failed state — reset-failed before retry"
    sudo systemctl reset-failed "$UNIT" 2>/dev/null || true
fi

# 3. THE GATE: the real preflight, unmodified. Exits 0 only if all 10 checks
#    pass (branch, gateway up, paper port open, live port closed, IBKR connect,
#    ACCOUNT FLAT, no duplicate trader, state.db writable, logs writable, no
#    recent healthcheck failure). Anything else -> quiet no-op, try again next
#    tick. Preflight logs its own verdict to local_logs/trader_preflight.log.
if ! "$REPO/ops/preflight_trader_start.sh" >/dev/null 2>&1; then
    exit 0
fi

# 4. Clear to start. --no-block so this oneshot never waits on another unit's
#    job (systemd will re-run the real preflight as ExecStartPre; if anything
#    changed in the last second it fails closed there).
note "preflight passed on a cold trader — starting $UNIT"
if sudo systemctl --no-block start "$UNIT"; then
    note "start issued for $UNIT"
else
    note "start command FAILED (rc=$?)"
fi
exit 0
