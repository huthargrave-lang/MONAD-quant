#!/usr/bin/env bash
#
# healthcheck.sh — Periodic health probe for the MONAD paper-trading stack.
# Designed to run every few minutes during market hours (via systemd timer).
#
# Checks: Gateway process, API port 7497, trader process, state.db freshness,
# recent ConnectionRefused storms, bracket/order failure warnings, disk space.
# Writes a JSON snapshot to local_logs/healthcheck.json and a line to the log.
# Read-only. No secrets printed. Exit 0 = healthy, 1 = degraded/warn.
#
set -uo pipefail
REPO="$HOME/MONAD-quant"
LOG_DIR="$REPO/local_logs"
JSON="$LOG_DIR/healthcheck.json"
LOG="$LOG_DIR/healthcheck.log"
DB="$REPO/live/state.db"
API_PORT=7497
STALE_MIN=20          # state.db should update within this many minutes during market hours
mkdir -p "$LOG_DIR"

now_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
warn=0; problems=""

add_problem() { problems="${problems}${problems:+; }$1"; warn=1; }

# 1. Gateway process
if pgrep -f "ibcalpha.ibc.IbcGateway" >/dev/null 2>&1; then gw=true; else gw=false; add_problem "gateway_down"; fi

# 2. API port 7497
if (exec 3<>"/dev/tcp/127.0.0.1/$API_PORT") 2>/dev/null; then exec 3>&-; port=true; else port=false; add_problem "port_7497_closed"; fi

# 3. Trader process (systemd service)
if systemctl is-active --quiet monad-trader.service; then trader=true; else trader=false; fi  # not always a problem (off-hours)

# 4. state.db freshness (minutes since last monitor cycle)
db_age_min=null
if [ -f "$DB" ]; then
    last=$("$REPO/venv/bin/python" - "$DB" <<'PY' 2>/dev/null
import sqlite3,sys,datetime
c=sqlite3.connect(f"file:{sys.argv[1]}?mode=ro",uri=True)
r=c.execute("SELECT last_cycle_time FROM monitor_status").fetchone()
print(r[0] if r and r[0] else "")
PY
)
    if [ -n "$last" ]; then
        db_age_min=$("$REPO/venv/bin/python" - "$last" <<'PY' 2>/dev/null
import sys,datetime
try:
    t=datetime.datetime.fromisoformat(sys.argv[1].replace("Z","+00:00"))
    if t.tzinfo is None: t=t.replace(tzinfo=datetime.timezone.utc)
    print(round((datetime.datetime.now(datetime.timezone.utc)-t).total_seconds()/60))
except Exception: print("null")
PY
)
    fi
fi

# 5. Recent ConnectionRefused storm + bracket/order failures (last 25 events)
conn_refused=0; order_fail=0
if [ -f "$DB" ]; then
    read conn_refused order_fail < <("$REPO/venv/bin/python" - "$DB" <<'PY' 2>/dev/null
import sqlite3,sys,datetime
c=sqlite3.connect(f"file:{sys.argv[1]}?mode=ro",uri=True)
cutoff=datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(minutes=60)
def recent(ts):
    try:
        t=datetime.datetime.fromisoformat((ts or "").replace("Z","+00:00"))
        if t.tzinfo is None: t=t.replace(tzinfo=datetime.timezone.utc)
        return t>=cutoff
    except Exception: return False
rows=[(et,m or "") for et,m in c.execute("SELECT event_time,message FROM monitor_events ORDER BY id DESC LIMIT 60")]
rows=[m for et,m in rows if recent(et)]   # only events within the last 60 min
cr=sum(1 for m in rows if "ConnectionRefused" in m or "Connect call failed" in m)
of=sum(1 for m in rows if ("bracket" in m.lower() and ("fail" in m.lower() or "did not execute" in m.lower())) or "order failed" in m.lower())
print(cr, of)
PY
)
    conn_refused=${conn_refused:-0}; order_fail=${order_fail:-0}
    [ "${conn_refused:-0}" -ge 3 ] 2>/dev/null && add_problem "connection_refused_storm(${conn_refused})"
    [ "${order_fail:-0}" -ge 1 ] 2>/dev/null && add_problem "order_failures(${order_fail})"
fi

# 6. Disk space
disk_pct=$(df --output=pcent "$REPO" 2>/dev/null | tail -1 | tr -dc '0-9')
[ "${disk_pct:-0}" -ge 90 ] 2>/dev/null && add_problem "disk_full(${disk_pct}%)"

status="ok"; [ "$warn" -eq 1 ] && status="warn"

cat > "$JSON" <<JSON
{
  "time_utc": "$now_utc",
  "status": "$status",
  "gateway_running": $gw,
  "port_7497_open": $port,
  "trader_active": $trader,
  "state_db_age_min": $db_age_min,
  "recent_connection_refused": ${conn_refused:-0},
  "recent_order_failures": ${order_fail:-0},
  "disk_used_pct": ${disk_pct:-null},
  "problems": "$problems"
}
JSON
echo "$now_utc status=$status gw=$gw port=$port trader=$trader db_age_min=$db_age_min connrefused=${conn_refused:-0} orderfail=${order_fail:-0} disk=${disk_pct:-?}% ${problems:+| $problems}" >> "$LOG"
echo "healthcheck: $status ${problems:+($problems)}"
exit "$warn"
