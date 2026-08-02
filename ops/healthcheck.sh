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

# ── Deploy sync — RECORDED, never voted on ───────────────────────────────────
# New top-level keys only. NEVER add_problem(): that sets warn=1 -> status="warn"
# -> preflight check 10 fails -> the trader does not start, on BOTH cold-start
# paths. Being behind origin is a fact to report, not a safety fault, and the bot
# not trading is a real cost. Follows this file's own precedent: trader_active and
# state_db_age_min are recorded and never vote.
#
# The three variables are initialised BEFORE the probe, and that is load-bearing.
# The JSON below is a heredoc: under `set -u` an unbound expansion aborts the
# script BEFORE `cat > "$JSON"` runs, so healthcheck.json is never written — and
# preflight check 10 treats a missing file as a PASS. A bug here would therefore
# silently disable the entire health gate (gateway-down, port-closed, disk-full
# all stop voting) while arming proceeds: the incident's own shape, reproduced
# inside the fix. Bounded by timeout, errors swallowed, defaults always defined.
drift_verdict="unknown"; drift_behind="null"; drift_armed="null"
_drift_raw=$(timeout 5 "$REPO/venv/bin/python" -c '
import json, sys
try:
    o = json.load(open(sys.argv[1]))
    b, a = o.get("behind"), o.get("armed_behind")
    v = o.get("verdict")
    # Whitelist: a value the oracle never emits (wrong type, unknown string) must
    # degrade to "unknown", not be echoed into the record as if it were a verdict.
    if v not in ("in_sync", "behind", "ahead", "diverged", "unknown"):
        v = "unknown"
    print(v,
          b if isinstance(b, int) else "null",
          a if isinstance(a, int) else "null")
except Exception:
    print("unknown", "null", "null")
' "$LOG_DIR/git_drift.json" 2>/dev/null) || true
if [ -n "${_drift_raw:-}" ]; then
    drift_verdict=$(printf '%s' "${_drift_raw}" | awk '{print $1}')
    drift_behind=$(printf '%s' "${_drift_raw}" | awk '{print $2}')
    drift_armed=$(printf '%s' "${_drift_raw}" | awk '{print $3}')
fi
# Re-assert defaults: awk on malformed input can yield empty, and an empty
# expansion would emit invalid JSON, which preflight's parser treats as a PASS.
[ -n "${drift_verdict:-}" ] || drift_verdict="unknown"
[ -n "${drift_behind:-}" ]  || drift_behind="null"
[ -n "${drift_armed:-}" ]   || drift_armed="null"

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
  "problems": "$problems",
  "git_drift_verdict": "$drift_verdict",
  "git_drift_behind": $drift_behind,
  "git_drift_armed_behind": $drift_armed
}
JSON
echo "$now_utc status=$status gw=$gw port=$port trader=$trader db_age_min=$db_age_min connrefused=${conn_refused:-0} orderfail=${order_fail:-0} disk=${disk_pct:-?}% ${problems:+| $problems}" >> "$LOG"
echo "healthcheck: $status ${problems:+($problems)}"
exit "$warn"
