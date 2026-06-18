#!/usr/bin/env bash
#
# dashboard_smoke_test.sh — Read-only validation that the MONAD dashboard server
# runs correctly and exposes no secrets. Starts uvicorn bound to localhost, hits
# every endpoint, scans responses for leaks, verifies it does not mutate
# state.db, then shuts the server down.
#
# Safe: does not touch the trader, Gateway, or order logic. Bound to 127.0.0.1.
# Note: the state.db "no-mutation" check is only meaningful when the trader is
# idle (an active trader writes to state.db concurrently).
#
set -uo pipefail
REPO="$HOME/MONAD-quant"
DB="$REPO/live/state.db"
HOST=127.0.0.1
PORT="${1:-8000}"
BASE="http://$HOST:$PORT"
LOG=$(mktemp)
fails=0
red() { sed -E 's/D?U[0-9]{5,}/<acct-redacted>/g'; }
chk() { if eval "$2"; then echo "[PASS] $1"; else echo "[FAIL] $1"; fails=$((fails+1)); fi; }

echo "== dashboard smoke test @ $(date '+%H:%M:%S %Z') =="
trader_active=$(systemctl is-active monad-trader.service 2>/dev/null | head -1)
echo "trader: $trader_active (state.db mutation check is only meaningful when idle)"

db_before=$(sha256sum "$DB" 2>/dev/null | awk '{print $1}')

cd "$REPO"
venv/bin/python -m uvicorn live.dashboard:app --host "$HOST" --port "$PORT" >"$LOG" 2>&1 &
UVPID=$!
cleanup() { kill "$UVPID" 2>/dev/null || true; rm -f "$LOG"; }
trap cleanup EXIT

# Wait for startup
up=0; for _ in $(seq 1 25); do curl -fsS -o /dev/null "$BASE/health" 2>/dev/null && { up=1; break; }; sleep 1; done
chk "server starts and /health responds" "[ $up -eq 1 ]"
[ "$up" -eq 1 ] || { echo "server did not start; log:"; tail -5 "$LOG" | red; exit 1; }

# /health
hcode=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$BASE/health")
chk "/health returns 200" "[ '$hcode' = 200 ]"

# / (dashboard)
dcode=$(curl -s -o /tmp/_smoke_dash.html -w "%{http_code}" --max-time 15 "$BASE/")
chk "/ (dashboard) returns 200" "[ '$dcode' = 200 ]"
# Use always-present markup (the metric strip is hidden in a fresh current-run view)
chk "/ renders expected content" "grep -qE 'Bot status|Current run|All history' /tmp/_smoke_dash.html"
chk "/ exposes NO account id / creds / secrets" "! grep -qiE 'D?U[0-9]{5,}|password|IB_PAPER|secret|api[_-]?key|BEGIN (RSA|OPENSSH)' /tmp/_smoke_dash.html"

# /api/ticker (network; tolerate failure but must not 500/leak)
tcode=$(curl -s -o /tmp/_smoke_tick.json -w "%{http_code}" --max-time 12 "$BASE/api/ticker/TQQQ" || echo 000)
chk "/api/ticker responds (200 or graceful, not 500)" "[ '$tcode' != 500 ]"
chk "/api/ticker exposes no secrets" "! grep -qiE 'D?U[0-9]{5,}|password|secret' /tmp/_smoke_tick.json"

# No raw .db served, no tracebacks in log
chk "no traceback in server log" "! grep -qiE 'Traceback|Unhandled' '$LOG'"

# state.db not mutated (read-only) — only assert when trader idle
db_after=$(sha256sum "$DB" 2>/dev/null | awk '{print $1}')
if [ "$trader_active" != "active" ]; then
    chk "state.db not mutated by dashboard (read-only)" "[ '$db_before' = '$db_after' ]"
else
    echo "[skip] state.db mutation check (trader active — concurrent writes expected)"
fi

rm -f /tmp/_smoke_dash.html /tmp/_smoke_tick.json
echo ""
if [ "$fails" -eq 0 ]; then echo "RESULT: all checks PASSED"; else echo "RESULT: $fails check(s) FAILED"; fi
exit "$fails"
