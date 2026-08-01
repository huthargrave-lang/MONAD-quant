#!/usr/bin/env bash
#
# status_check.sh — One-shot human-readable status of the MONAD paper stack.
# Read-only. Safe to run anytime. No secrets printed (account IDs redacted).
#
set -uo pipefail
REPO="$HOME/MONAD-quant"
DB="$REPO/live/state.db"
red() { sed -E 's/D?U[0-9]{5,}/<acct-redacted>/g'; }

echo "===================================================================="
echo " MONAD status — $(date '+%a %Y-%m-%d %H:%M:%S %Z')"
echo "===================================================================="

echo "-- system --"
echo "  host=$(hostname) up=$(uptime -p 2>/dev/null | sed 's/up //')"
echo "  disk=$(df -h "$REPO" | tail -1 | awk '{print $5" used, "$4" free"}')  mem_free=$(free -h | awk '/Mem:/{print $7}')"
echo "  load=$(cut -d' ' -f1-3 /proc/loadavg)"

echo "-- repo --"
cd "$REPO" 2>/dev/null && echo "  branch=$(git branch --show-current)  clean=$([ -z "$(git status --porcelain)" ] && echo yes || echo no)"

# Deploy sync — READ-ONLY consumer of local_logs/git_drift.json (ops/git_drift.sh).
# Renders here because `branch=development clean=yes` looked perfectly healthy for
# the seven days this checkout sat 129 commits behind origin. Absence renders as
# loudly as divergence: no artifact, or a stale one, prints UNKNOWN rather than
# nothing, because a surface that goes quiet when its sensor dies is the bug.
# This script is read-only and nothing gates on its exit status, so this cannot
# affect arming.
printf '  sync='
"$REPO/venv/bin/python" "$REPO/tools/drift_render.py" "$REPO/local_logs/git_drift.json" \
    2>/dev/null || echo "UNKNOWN (drift renderer unavailable)"

echo "-- gateway --"
pgrep -f "ibcalpha.ibc.IbcGateway" >/dev/null 2>&1 && echo "  gateway: RUNNING" || echo "  gateway: down"
if (exec 3<>/dev/tcp/127.0.0.1/7497) 2>/dev/null; then exec 3>&-; echo "  port 7497 (paper): OPEN"; else echo "  port 7497 (paper): closed"; fi
if (exec 3<>/dev/tcp/127.0.0.1/7496) 2>/dev/null; then exec 3>&-; echo "  port 7496 (LIVE): OPEN  <-- should be closed for paper!"; else echo "  port 7496 (live): closed (good)"; fi
echo "  timer: $(systemctl is-enabled ibkr-gateway-paper.timer 2>/dev/null)/$(systemctl is-active ibkr-gateway-paper.timer 2>/dev/null)  next=$(systemctl list-timers ibkr-gateway-paper.timer --no-pager 2>/dev/null | sed -n '2p' | awk '{print $1,$2,$3}')"

echo "-- trader --"
echo "  monad-trader.service: $(systemctl is-enabled monad-trader.service 2>/dev/null)/$(systemctl is-active monad-trader.service 2>/dev/null)"

echo "-- data (state.db) --"
if [ -f "$DB" ]; then
  "$REPO/venv/bin/python" - "$DB" <<'PY' 2>/dev/null | red
import sqlite3,sys,datetime
c=sqlite3.connect(f"file:{sys.argv[1]}?mode=ro",uri=True)
def one(q):
    try: return c.execute(q).fetchone()[0]
    except Exception: return "n/a"
print(f"  trades={one('SELECT COUNT(*) FROM trades')} signals={one('SELECT COUNT(*) FROM signal_history')} events={one('SELECT COUNT(*) FROM monitor_events')} open_positions={one('SELECT COUNT(*) FROM position')}")
lc=one("SELECT last_cycle_time FROM monitor_status")
print(f"  last_cycle={lc}")
print(f"  latest_signal_bar={one('SELECT MAX(bar_time) FROM signal_history')}")
print(f"  latest_event={one('SELECT MAX(event_time) FROM monitor_events')}")
if isinstance(lc,str) and lc:
    try:
        t=datetime.datetime.fromisoformat(lc.replace('Z','+00:00'))
        if t.tzinfo is None: t=t.replace(tzinfo=datetime.timezone.utc)
        age=(datetime.datetime.now(datetime.timezone.utc)-t).total_seconds()/60
        print(f"  data_age={age:.0f} min {'(STALE)' if age>20 else '(fresh)'}")
    except Exception: pass
PY
else
  echo "  state.db missing"
fi
echo "===================================================================="
