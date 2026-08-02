#!/usr/bin/env bash
#
# preflight_trader_start.sh — Hard safety gate that must pass before the MONAD
# paper trader starts. Runs as ExecStartPre of monad-trader.service (and is safe
# to run by hand). Runs ALL 10 checks, logs each PASS/FAIL with a clear reason to
# local_logs/trader_preflight.log, and exits non-zero if ANY check fails.
#
# PAPER ONLY. Never connects to or accepts the live port 7496. Prints/stores no
# secrets or account IDs (the IBKR connect test emits only CONNECTED/FLAT tokens).
#
set -uo pipefail

REPO="$HOME/MONAD-quant"
LOG_DIR="$REPO/local_logs"
LOG="$LOG_DIR/trader_preflight.log"
EXPECT_BRANCH="development"
PAPER_PORT=7497
LIVE_PORT=7496
CONNECT_CLIENT_ID=70          # distinct from the trader (clientId 1)
HEALTHCHECK_MAX_AGE_MIN=15

mkdir -p "$LOG_DIR" 2>/dev/null || true
fails=0
ts() { date '+%Y-%m-%d %H:%M:%S %Z'; }
note() { echo "$(ts) [preflight] $*" >> "$LOG"; }
pass() { note "PASS: $1"; echo "[PASS] $1"; }
fail() { note "FAIL: $1"; echo "[FAIL] $1"; fails=$((fails+1)); }
# REPORT, not a check: states a fact without voting on the verdict. Used where the
# operator needs to know something that must not block arming (see H31/F205).
report() { note "INFO: $1"; echo "[INFO] $1"; }

note "================ preflight start ================"

# 1. Correct branch
br=$(git -C "$REPO" branch --show-current 2>/dev/null || echo "")
if [ "$br" = "$EXPECT_BRANCH" ]; then pass "git branch is $EXPECT_BRANCH"
else fail "git branch is '${br:-unknown}', expected '$EXPECT_BRANCH'"; fi

# 2. IBKR Gateway process running
if pgrep -f "ibcalpha.ibc.IbcGateway" >/dev/null 2>&1; then pass "IB Gateway process running"
else fail "IB Gateway process not running"; fi

# 3. Paper port 7497 open
if (exec 3<>"/dev/tcp/127.0.0.1/$PAPER_PORT") 2>/dev/null; then exec 3>&-; pass "paper port $PAPER_PORT open"
else fail "paper port $PAPER_PORT closed"; fi

# 4. Live port 7496 NOT open (paper only)
if (exec 3<>"/dev/tcp/127.0.0.1/$LIVE_PORT") 2>/dev/null; then exec 3>&-; fail "LIVE port $LIVE_PORT is OPEN — refusing (this setup is paper-only)"
else pass "live port $LIVE_PORT not open"; fi

# 5 + 6. IBKR paper connect + account flat (single read-only connection; no account ID emitted)
conn=$(REPO="$REPO" CID="$CONNECT_CLIENT_ID" "$REPO/venv/bin/python" - <<'PY' 2>/dev/null
import os, sys
sys.path.insert(0, os.environ["REPO"])
try:
    import config
    from ib_insync import IB
    if not getattr(config, "LIVE_PAPER_MODE", False):
        print("NOTPAPER"); sys.exit(0)
    ib = IB()
    ib.connect(config.IBKR_HOST, config.IBKR_PORT_PAPER,
               clientId=int(os.environ["CID"]), timeout=12)
    connected = bool(ib.managedAccounts())
    sym = getattr(config, "LIVE_SYMBOL", "TQQQ")
    open_pos = [p for p in ib.positions() if p.contract.symbol == sym and p.position != 0]
    ib.disconnect()
    print(f"CONNECTED={'yes' if connected else 'no'} FLAT={'yes' if not open_pos else 'no'}")
except Exception as exc:
    print(f"ERROR={type(exc).__name__}")
PY
)
case "$conn" in
    *CONNECTED=yes*) pass "diagnostic can connect to IBKR paper" ;;
    *NOTPAPER*)      fail "config.LIVE_PAPER_MODE is not True" ;;
    *)               fail "cannot connect to IBKR paper (${conn:-no result})" ;;
esac
case "$conn" in
    *FLAT=yes*) pass "account is flat for trading symbol" ;;
    *FLAT=no*)  fail "account is NOT flat (open position exists) — refusing to start" ;;
    *)          fail "could not verify account flat (${conn:-no result})" ;;
esac

# 7. No existing trader process already running
if pgrep -f "[-]m live.trader" >/dev/null 2>&1; then fail "a trader process is already running (duplicate) — refusing"
else pass "no existing trader process"; fi

# 8. state.db exists or can be created/written
if [ -f "$REPO/live/state.db" ]; then
    if [ -w "$REPO/live/state.db" ]; then pass "live/state.db exists and is writable"
    else fail "live/state.db exists but is NOT writable"; fi
elif [ -w "$REPO/live" ]; then pass "live/state.db absent but live/ is writable (can be created)"
else fail "live/ is not writable — cannot create state.db"; fi

# 9. local_logs/ writable
if [ -w "$LOG_DIR" ]; then pass "local_logs/ is writable"
else fail "local_logs/ is not writable"; fi

# 10. No recent critical healthcheck failure
if [ -f "$LOG_DIR/healthcheck.json" ]; then
    hc=$(LOG_DIR="$LOG_DIR" MAXAGE="$HEALTHCHECK_MAX_AGE_MIN" "$REPO/venv/bin/python" - <<'PY' 2>/dev/null
import os, json, datetime
p = os.path.join(os.environ["LOG_DIR"], "healthcheck.json")
try:
    d = json.load(open(p))
    t = datetime.datetime.fromisoformat(d["time_utc"].replace("Z", "+00:00"))
    age = (datetime.datetime.now(datetime.timezone.utc) - t).total_seconds() / 60
    recent = age <= float(os.environ["MAXAGE"])
    status = d.get("status", "unknown")
    print(f"{'RECENTFAIL' if (recent and status != 'ok') else 'OK'} status={status} age={age:.0f}min")
except Exception:
    print("NOJSON")
PY
)
    case "$hc" in
        *RECENTFAIL*) fail "recent healthcheck failure ($hc)" ;;
        *) pass "no recent critical healthcheck failure ($hc)" ;;
    esac
else
    pass "no healthcheck.json yet (treated as no recent failure)"
fi

# ── Alerting reachability — REPORTED, not gated ────────────────────────────
# live/alerts.py no-ops silently when SLACK_WEBHOOK_URL is unset, so every CRITICAL
# path can be correctly wired and still page nobody, with nothing anywhere saying so
# (H31/F205). This makes the state observable. It deliberately does NOT vote: turning
# it into a hard check would block arming on a missing env var, which is the owner's
# call, not this script's.
if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
    report "CRITICAL alerting is configured (SLACK_WEBHOOK_URL set; value not logged)"
else
    report "CRITICAL alerting is NOT configured — SLACK_WEBHOOK_URL is unset, so \
force-finalize / software-stop / desync-block / signal-failure alerts will be computed \
and discarded. Not a failure; the trader will still start."
fi

# ── Deploy sync — REPORTED, deliberately not gated ──────────────────────────
# Uses report(), which logs INFO without touching `fails` (the H31/F205 precedent
# directly above). Drift must never become a reason the bot refuses to start:
# preflight is ExecStartPre, so a veto here stops the 09:22 timer AND
# ops/rearm_trader.sh, which gates on this same exit code — one stale checkout
# would cost a whole session.
#
# The probe runs in a subshell with `set +u`, a hard timeout and `|| true`, so it
# cannot change this script's exit status by ANY route. Under `set -uo pipefail`
# an unbound expansion aborts the script before its `exit 0` — blocking arming
# without ever calling fail(), a veto with no verdict and no log line. Measured:
#   bash -c 'set -uo pipefail; echo A; echo "${NOPE}"; echo B; exit 0'
# never reaches B. Note also that `fail` called from inside a subshell cannot
# increment the parent's counter, so a subshell could not vote even if it tried.
drift_line=$( ( set +u; timeout 5 "$REPO/venv/bin/python" \
    "$REPO/tools/drift_render.py" "$LOG_DIR/git_drift.json" ) 2>/dev/null ) || true
report "deploy sync: ${drift_line:-UNKNOWN (drift probe unavailable)}"

if [ "$fails" -gt 0 ]; then
    note "================ preflight FAILED ($fails check(s)) — trader will NOT start ================"
    echo "PREFLIGHT FAILED ($fails check(s)). See $LOG"
    exit 1
fi
note "================ preflight PASSED — clear to start trader ================"
echo "PREFLIGHT PASSED"
exit 0
