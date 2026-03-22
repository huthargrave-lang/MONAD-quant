#!/bin/bash
# ══════════════════════════════════════════════════════════════════════
#  MONAD Quant — Health Check
#  Checks that the trader service and IB Gateway are running.
#  Add to cron for periodic monitoring:
#    */30 9-16 * * 1-5 /home/pi/MONAD-quant/deploy/healthcheck.sh
# ══════════════════════════════════════════════════════════════════════

LOG_TAG="monad-health"
ISSUES=0

# Check 1: Is the trader service running?
if ! systemctl is-active --quiet monad-trader; then
    logger -t "$LOG_TAG" "ALERT: monad-trader service is NOT running"
    echo "ALERT: monad-trader service is NOT running"
    ISSUES=$((ISSUES + 1))
fi

# Check 2: Is Java running (IB Gateway)?
if ! pgrep -f "ibgateway\|IBC\|java.*jts" > /dev/null 2>&1; then
    logger -t "$LOG_TAG" "ALERT: IB Gateway does not appear to be running"
    echo "ALERT: IB Gateway does not appear to be running"
    ISSUES=$((ISSUES + 1))
fi

# Check 3: Has the trader logged anything in the last 2 hours?
LAST_LOG=$(journalctl -u monad-trader --since "2 hours ago" --no-pager -q 2>/dev/null | tail -1)
if [ -z "$LAST_LOG" ]; then
    # Only alert during market hours (Mon-Fri 9-16 ET)
    HOUR=$(TZ=America/New_York date +%H)
    DOW=$(date +%u)  # 1=Mon, 7=Sun
    if [ "$DOW" -le 5 ] && [ "$HOUR" -ge 9 ] && [ "$HOUR" -le 16 ]; then
        logger -t "$LOG_TAG" "WARNING: No trader logs in last 2 hours during market hours"
        echo "WARNING: No trader logs in last 2 hours during market hours"
        ISSUES=$((ISSUES + 1))
    fi
fi

if [ "$ISSUES" -eq 0 ]; then
    echo "OK: All checks passed"
fi

exit $ISSUES
