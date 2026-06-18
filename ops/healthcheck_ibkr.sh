#!/usr/bin/env bash
#
# healthcheck_ibkr.sh — Verify IB Gateway PAPER is up and reachable by the bot.
#
# Checks, in order:
#   1. IB Gateway process is running
#   2. API port 7497 is open
#   3. The MONAD-quant diagnostic can actually connect to IBKR
#
# Read-only. No credentials printed. Exit 0 = healthy, non-zero = problem.
#
set -uo pipefail

REPO="$HOME/MONAD-quant"
TWS_VERSION="1037"
API_PORT=7497
rc=0

echo "== IBKR Gateway PAPER healthcheck — $(date '+%Y-%m-%d %H:%M:%S %Z') =="

# 1) Process
if pgrep -f "ibcalpha.ibc.IbcGateway" >/dev/null 2>&1; then
    echo "[OK]   IB Gateway process is running (pid: $(pgrep -f "ibcalpha.ibc.IbcGateway" | tr '\n' ' '))"
else
    echo "[FAIL] IB Gateway process not found."
    rc=1
fi

# 2) Port
if (exec 3<>"/dev/tcp/127.0.0.1/$API_PORT") 2>/dev/null; then
    exec 3>&- 2>/dev/null || true
    echo "[OK]   API port $API_PORT is open."
else
    echo "[FAIL] API port $API_PORT is not open."
    rc=1
fi

# 3) systemd unit + timer status (informational)
echo "-- systemd --"
systemctl is-active ibkr-gateway-paper.service >/dev/null 2>&1 \
    && echo "[OK]   ibkr-gateway-paper.service active" \
    || echo "[..]   ibkr-gateway-paper.service not active (normal if it ran oneshot / Gateway detached)"
if systemctl is-enabled ibkr-gateway-paper.timer >/dev/null 2>&1; then
    echo "[OK]   ibkr-gateway-paper.timer enabled"
    systemctl list-timers ibkr-gateway-paper.timer --no-pager 2>/dev/null | sed -n '1,2p'
else
    echo "[..]   ibkr-gateway-paper.timer not enabled"
fi

# 4) Real connection test via the project's diagnostic (definitive)
echo "-- bot connectivity (tools/diagnose_brackets.py) --"
if [ "$rc" -eq 0 ]; then
    cd "$REPO" && venv/bin/python tools/diagnose_brackets.py --client-id 77 --timeout 8 || rc=$?
else
    echo "[skip] Gateway/port down — skipping connect test. Fix the above first."
fi

echo "== healthcheck exit code: $rc =="
exit "$rc"
