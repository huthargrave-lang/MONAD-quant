#!/usr/bin/env bash
#
# start_trader.sh — Safely start the MONAD paper trader.
#
# Two modes:
#   (default)  manual: runs guards, then `systemctl start monad-trader.service`
#              (the service re-runs its own preflight gate).
#   --exec     foreground: runs guards, then exec the trader process directly.
#              Used by monad-trader.service ExecStart (after the preflight gate),
#              so the service runs THIS guarded starter without recursion.
#
# Guards (both modes):
#   * PAPER mode only (refuses if config.LIVE_PAPER_MODE is False).
#   * IBKR Gateway API port 7497 must be open (Gateway up + logged in).
#
# Does NOT enable boot-start (that's a deliberate, separate decision).
#
set -uo pipefail
REPO="$HOME/MONAD-quant"
API_PORT=7497
EXEC_MODE=0
[ "${1:-}" = "--exec" ] && EXEC_MODE=1

echo "== start_trader$([ "$EXEC_MODE" = 1 ] && echo ' --exec'): $(date '+%Y-%m-%d %H:%M:%S %Z') =="

# 1. Paper-mode safety gate
paper=$("$REPO/venv/bin/python" - <<'PY' 2>/dev/null
import config
print("yes" if getattr(config, "LIVE_PAPER_MODE", False) else "no")
PY
)
if [ "$paper" != "yes" ]; then
    echo "REFUSING: config.LIVE_PAPER_MODE is not True. This launcher is paper-only."
    exit 2
fi
echo "[ok] paper mode confirmed"

# 2. Gateway must be reachable
if (exec 3<>"/dev/tcp/127.0.0.1/$API_PORT") 2>/dev/null; then
    exec 3>&-; echo "[ok] API port $API_PORT open"
else
    echo "REFUSING: API port $API_PORT is closed — start IB Gateway first:"
    echo "    sudo systemctl start ibkr-gateway-paper.service"
    exit 1
fi

# 3a. --exec mode (systemd): run the trader in the foreground, no sudo, no recursion.
if [ "$EXEC_MODE" = 1 ]; then
    echo "[exec] launching trader in foreground (systemd-managed, paper)"
    cd "$REPO"
    exec "$REPO/venv/bin/python" -m live.trader
fi

# 3b. Manual mode: start the systemd service (which re-runs its preflight gate).
echo "Starting monad-trader.service ..."
sudo systemctl start monad-trader.service
sleep 3
if systemctl is-active --quiet monad-trader.service; then
    echo "[ok] monad-trader.service is active"
    echo "Follow logs: journalctl -u monad-trader.service -f"
else
    echo "[FAIL] monad-trader.service did not become active. Check: systemctl status monad-trader.service"
    exit 1
fi
