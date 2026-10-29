#!/usr/bin/env bash
#
# decommission_trader.sh — ONE-SHOT, IDEMPOTENT decommission of the MONAD paper
# trader as a live process on the Pi. Decision: docs/research/DECOMMISSION_TRADER_QUESTION.md
# Runbook: OPERATIONS.md §6.1 (the revival condition lives there and nowhere else).
#
# What it does, in order (each step is state-checked, so re-running is a no-op):
#   0. invariants: paper port only (7496 must be closed), tracked marker present;
#      "already decommissioned" (receipt present + all four trader units masked) exits 0
#   1. disarm the schedulers: rearm timer+service, trader timer
#   2. broker probe (read-only, clientId 71): positions AND resting orders for
#      LIVE_SYMBOL, plus the local position row and trader liveness -> decision matrix
#   3. stop the trader only when broker flat, no resting orders, no local row
#   4. final archive via ops/archive_and_start_new_run.py (raw .db -> local_backups/,
#      sanitized -> data/live_runs/archive_<date>_decommission/), analysis, stop_exits
#   5. leak assertion: the exact broker account strings must appear nowhere in ANY
#      directory the runbook says to commit (the archive and every pi_export_* dir)
#   6. park unit files in /etc/systemd/system/.decommissioned/ and mask them
#   7. disable gateway/healthcheck/daily-export timers; stop the gateway
#   8. receipt (sanitized) -> archive dir + local_logs; print the unit table
#
# Fail-closed: any assertion failure aborts BEFORE the receipt is written. Exit 75 =
# "not now, rerun later" (position open, orders resting, gateway down). PAPER ONLY.
# Never prints or logs an account ID. Cancelling resting orders is opt-in
# (--cancel-resting-orders) because it is an order action.
#
# Args: [--cancel-resting-orders] [--date=YYYY-MM-DD] [-h|--help]
#
set -uo pipefail

REPO="$HOME/MONAD-quant"
LOG_DIR="$REPO/local_logs"
LOG="$LOG_DIR/decommission.log"
RUNTIME="$REPO/local_runtime"
BACKUPS="$REPO/local_backups"
MARKER="$REPO/ops/DECOMMISSIONED.json"
UNIT_DIR="/etc/systemd/system"
PARK="$UNIT_DIR/.decommissioned"
PAPER_PORT=7497
LIVE_PORT=7496
PROBE_CID=71            # trader=1, diagnose=51, preflight=70
ACCT_FILE="$RUNTIME/.decommission_accts"   # 600, deleted on exit
PY="$REPO/venv/bin/python"
TRADER_UNITS="monad-trader-rearm.timer monad-trader-rearm.service monad-trader.timer monad-trader.service"

DATE="$(date -u +%Y-%m-%d)"
CANCEL_ORDERS=0
for a in "$@"; do
    case "$a" in
        --cancel-resting-orders) CANCEL_ORDERS=1 ;;
        --date=*) DATE="${a#--date=}" ;;
        -h|--help) sed -n '2,27p' "$0"; exit 0 ;;
        *) echo "unknown arg: $a"; exit 2 ;;
    esac
done
ARCHIVE_ID="archive_${DATE}_decommission"
ARCHIVE_DIR="$REPO/data/live_runs/$ARCHIVE_ID"
RECONCILE_PASSES=0

mkdir -p "$LOG_DIR" "$RUNTIME" "$BACKUPS" 2>/dev/null || true
ts()   { date '+%Y-%m-%d %H:%M:%S %Z'; }
note() { echo "$(ts) [decommission] $*" >> "$LOG"; }
say()  { echo "[decommission] $*"; note "$*"; }
die()  { say "ABORT: $*"; exit "${2:-1}"; }
must() { "$@" || die "command failed: $*"; }
cleanup() { rm -f "$ACCT_FILE" 2>/dev/null || true; }
trap cleanup EXIT

ALL_UNITS="monad-trader.service monad-trader.timer monad-trader-rearm.service monad-trader-rearm.timer monad-dashboard.service ibkr-gateway-paper.timer ibkr-gateway-paper.service monad-healthcheck.timer monad-daily-export.timer monad-gitdrift.timer monad-screener.timer monad-ctxweb.service monad-researchui.service"
unit_table() {  # human-readable state table (no account data anywhere in it)
    local u
    printf '%-32s %-12s %s\n' "UNIT" "ENABLED" "ACTIVE" | tee -a "$LOG"
    for u in $ALL_UNITS; do
        printf '%-32s %-12s %s\n' "$u" "$(systemctl is-enabled "$u" 2>/dev/null || echo not-found)" "$(systemctl is-active "$u" 2>/dev/null || echo inactive)" | tee -a "$LOG"
    done
    systemctl list-timers 'monad-*' 'ibkr-*' --no-pager 2>/dev/null | tee -a "$LOG"
}
all_trader_units_masked() {
    local u
    for u in $TRADER_UNITS; do
        [ "$(systemctl is-enabled "$u" 2>/dev/null)" = "masked" ] || return 1
    done
}

say "================ start (date=$DATE archive=$ARCHIVE_ID) ================"

# ── 0. Invariants ──────────────────────────────────────────────────────────────
if (exec 3<>"/dev/tcp/127.0.0.1/$LIVE_PORT") 2>/dev/null; then exec 3>&-; die "LIVE port $LIVE_PORT is OPEN — this host is paper-only; refusing to touch anything"; fi
[ -f "$MARKER" ] || die "tracked marker $MARKER is missing — pull development (commit A) first"
[ "$(git -C "$REPO" branch --show-current 2>/dev/null)" = "development" ] || die "checkout is not on development"
paper=$(REPO="$REPO" "$PY" - <<'PY' 2>/dev/null
import sys; sys.path.insert(0, __import__("os").environ["REPO"])
import config; print("yes" if getattr(config, "LIVE_PAPER_MODE", False) else "no")
PY
)
[ "$paper" = "yes" ] || die "config.LIVE_PAPER_MODE is not True"

# ── 0b. Already decommissioned? ────────────────────────────────────────────────
# After a successful run the Gateway is down, so the probe in step 2 would exit 75
# ("cannot reach IBKR") on every rerun instead of saying "already done". A receipt
# (this date's archive, or the copy in local_logs/) plus all four trader units
# reporting `masked` is the completed state: print the table and stop.
if { [ -f "$ARCHIVE_DIR/receipt.json" ] || [ -f "$LOG_DIR/decommission_receipt.json" ]; } && all_trader_units_masked; then
    say "already decommissioned: receipt present and all four trader units are masked — nothing to do"
    unit_table
    exit 0
fi

# ── 1. Disarm schedulers first (rearm would otherwise restart the trader mid-run) ──
disarm() {  # disable --now if enabled or active; idempotent
    local u="$1"
    if systemctl is-enabled --quiet "$u" 2>/dev/null || systemctl is-active --quiet "$u" 2>/dev/null; then
        must sudo systemctl disable --now "$u"; say "disabled $u"
    else say "already disabled: $u"; fi
}
disarm monad-trader-rearm.timer
disarm monad-trader-rearm.service
disarm monad-trader.timer

# ── 2. Broker + local probe ────────────────────────────────────────────────────
probe() {
    REPO="$REPO" CID="$PROBE_CID" ACCT_FILE="$ACCT_FILE" CANCEL="$1" "$PY" - <<'PY' 2>/dev/null
import os, sys, json
sys.path.insert(0, os.environ["REPO"])
try:
    import config
    from ib_insync import IB
    ib = IB(); ib.connect(config.IBKR_HOST, config.IBKR_PORT_PAPER, clientId=int(os.environ["CID"]), timeout=12)
    sym = getattr(config, "LIVE_SYMBOL", "TQQQ")
    accts = [a for a in ib.managedAccounts() if a]
    with open(os.environ["ACCT_FILE"], "w") as f:   # exact strings for the leak assertion only
        f.write("\n".join(accts))
    os.chmod(os.environ["ACCT_FILE"], 0o600)
    pos = sum(p.position for p in ib.positions() if p.contract.symbol == sym)
    ib.reqAllOpenOrders(); ib.sleep(1.0)
    resting = [t for t in ib.openTrades() if t.contract.symbol == sym]
    if os.environ["CANCEL"] == "1" and pos == 0 and resting:
        for t in resting: ib.cancelOrder(t.order)
        ib.sleep(2.0); ib.reqAllOpenOrders(); ib.sleep(1.0)
        resting = [t for t in ib.openTrades() if t.contract.symbol == sym]
    orders = ";".join(f"{t.order.orderId}:{t.order.orderType}:{t.orderStatus.status}" for t in resting)
    ib.disconnect()
    print(f"CONNECTED=yes POS={int(pos)} ORDERS={len(resting)} LIST={orders}")
except Exception as exc:
    print(f"CONNECTED=no ERROR={type(exc).__name__}")
PY
}
local_rows() { REPO="$REPO" "$PY" - <<'PY' 2>/dev/null
import sqlite3, os
p = os.path.join(os.environ["REPO"], "live", "state.db")
if not os.path.exists(p): print(0)
else:
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True); print(c.execute("SELECT COUNT(*) FROM position").fetchone()[0])
PY
}
trader_alive() { systemctl is-active --quiet monad-trader.service || pgrep -f "[-]m live.trader" >/dev/null 2>&1; }

pr=$(probe "$CANCEL_ORDERS")
case "$pr" in *CONNECTED=yes*) ;; *) die "cannot reach IBKR paper ($pr) — start the Gateway (sudo systemctl start ibkr-gateway-paper.service) and rerun; resting orders cannot be verified while it is down" 75 ;; esac
pos=$(sed -n 's/.*POS=\(-\?[0-9]*\).*/\1/p' <<<"$pr"); orders=$(sed -n 's/.*ORDERS=\([0-9]*\).*/\1/p' <<<"$pr")
rows=$(local_rows); alive=0; trader_alive && alive=1
say "probe: broker_pos=$pos resting_orders=$orders local_rows=$rows trader_alive=$alive"

if [ "$pos" != "0" ]; then
    [ "$alive" = 1 ] && die "broker position $pos open and trader running — let the bracket/trader finish; rerun later" 75
    die "broker position $pos open with NO trader — run venv/bin/python tools/diagnose_brackets.py and flatten with approval, then rerun" 75
fi
if [ "$orders" != "0" ]; then
    say "resting orders for LIVE_SYMBOL (id:type:status): $(sed -n 's/.*LIST=//p' <<<"$pr")"
    die "orphaned resting orders would stay live at IBKR while the Pi is dark — cancel them in TWS, or rerun with --cancel-resting-orders" 75
fi
if [ "$rows" != "0" ]; then
    # A pending_close row WITHOUT an estimated_exit_price never force-finalizes
    # (live/trader.py:421 requires one), so a running trader can keep this row
    # forever and this branch would say "rerun after" forever. Hence the second
    # sentence: stop the trader by hand to reach the reconcile branch below.
    [ "$alive" = 1 ] && die "local position row present and trader running — the next :32 cycle books it; rerun after. If the row survives three cycles it is a pending_close without estimated_exit_price (live/trader.py:421 never force-finalizes it): stop the trader (sudo systemctl stop monad-trader.service), then rerun to reach the reconcile branch" 75
    say "broker flat but local position row present and trader dead — reconciling via the trader's own path (dry-run suppresses entries)"
    for i in 1 2 3; do
        RECONCILE_PASSES=$i
        (cd "$REPO" && timeout 300 "$PY" -m live.trader --once --dry-run) >> "$LOG" 2>&1 || true
        rows=$(local_rows); say "reconcile pass $i -> local_rows=$rows"; [ "$rows" = "0" ] && break; sleep 20
    done
    [ "$rows" = "0" ] || die "local position row still present after 3 reconcile passes — inspect live/state.db position table by hand" 75
fi

# ── 3. Stop the trader (only reached when flat, clean, no local row) ───────────
if systemctl is-active --quiet monad-trader.service; then
    must sudo systemctl stop monad-trader.service; say "stopped monad-trader.service"
fi
for i in $(seq 1 30); do pgrep -f "[-]m live.trader" >/dev/null 2>&1 || break; sleep 1; done
pgrep -f "[-]m live.trader" >/dev/null 2>&1 && die "a live.trader process is still running (pid $(pgrep -f '[-]m live.trader' | head -1)) — stop it by PID, then rerun"
if systemctl is-enabled --quiet monad-dashboard.service 2>/dev/null; then must sudo systemctl disable monad-dashboard.service; say "disabled monad-dashboard.service"; fi

# ── 4. Final archive + export (idempotent on receipt) ──────────────────────────
if [ -f "$ARCHIVE_DIR/receipt.json" ]; then
    say "archive already complete: $ARCHIVE_DIR (skipping export)"
else
    (cd "$REPO" && "$PY" ops/archive_and_start_new_run.py --date "$DATE" --archive-id "$ARCHIVE_ID" --no-run-marker --notes "decommission") >> "$LOG" 2>&1 \
        || die "archive_and_start_new_run.py failed — see $LOG"
    (cd "$REPO" && "$PY" ops/analyze_run.py --all) > "$ARCHIVE_DIR/analysis.txt" 2>/dev/null || say "analyze_run.py failed (non-fatal)"
    (cd "$REPO" && "$PY" ops/export_stop_exits.py --archive "$ARCHIVE_DIR" --trader-log "$LOG_DIR/trader.log" --bars "$REPO/data/cache/TQQQ_1h.csv" --date "$DATE") >> "$LOG" 2>&1 \
        || say "export_stop_exits.py failed (non-fatal; stop_exits.jsonl missing)"
    if ls -d "$REPO"/data/live_runs/pi_export_* >/dev/null 2>&1; then
        pi_dirs=()
        for d in "$REPO"/data/live_runs/pi_export_*; do pi_dirs+=("$(basename "$d")"); done
        tar czf "$BACKUPS/pi_exports_${DATE}.tgz" -C "$REPO/data/live_runs" "${pi_dirs[@]}" && say "pi_export_* tarred to local_backups/"
    fi
    cp "$LOG_DIR/trader.log" "$BACKUPS/trader_${DATE}.log" 2>/dev/null || true
fi

# ── 5. Leak assertion: exact account strings + widened regex + secret scan ─────
# Scope = every directory the runbook says to commit: the archive AND every
# data/live_runs/pi_export_* dir (pi_export_2026-06-26 is referenced by tracked
# tools and goes in with the receipt; it was sanitized with the OLD regex).
commit_dirs="$ARCHIVE_DIR"
for d in "$REPO"/data/live_runs/pi_export_*; do [ -d "$d" ] && commit_dirs="$commit_dirs:$d"; done
leak=$(ACCT_FILE="$ACCT_FILE" DIRS="$commit_dirs" "$PY" - <<'PY' 2>/dev/null
import os, re
accts = [a.strip() for a in open(os.environ["ACCT_FILE"]).read().split() if a.strip()] if os.path.exists(os.environ["ACCT_FILE"]) else []
rx = re.compile(r"\b(?:DU[A-Z]?|U)[0-9]{5,}\b")
hits = 0; scanned = 0
for d in os.environ["DIRS"].split(":"):
    for root, _, files in os.walk(d):
        for fn in files:
            scanned += 1
            txt = open(os.path.join(root, fn), errors="replace").read()
            hits += sum(txt.count(a) for a in accts) + len(rx.findall(txt))
print(f"HITS={hits} ACCTS={len(accts)} FILES={scanned}")
PY
)
case "$leak" in HITS=0\ ACCTS=[1-9]*) say "leak assertion passed ($leak) over: $commit_dirs" ;; *) die "ACCOUNT-ID LEAK or no accounts to check ($leak) — DO NOT COMMIT $commit_dirs; fix redaction and rerun" ;; esac
IFS=':' read -r -a scan_dirs <<<"$commit_dirs"
(cd "$REPO" && "$PY" ops/secret_scan.py "${scan_dirs[@]}") >> "$LOG" 2>&1 || die "ops/secret_scan.py flagged one of: $commit_dirs — do not commit"

# ── 6. Park + mask the trader units (mask needs the real file out of the way) ──
parked=""
park_mask() {
    local u="$1"
    if [ "$(systemctl is-enabled "$u" 2>/dev/null)" = "masked" ]; then say "already masked: $u"; return; fi
    if [ -f "$UNIT_DIR/$u" ]; then
        must sudo mkdir -p "$PARK"; must sudo mv "$UNIT_DIR/$u" "$PARK/$u"; parked="$parked $u"
    fi
    must sudo systemctl daemon-reload
    must sudo systemctl mask "$u"
    [ "$(systemctl is-enabled "$u" 2>/dev/null)" = "masked" ] || die "$u is not masked after mask — stopping before writing a false receipt"
    say "masked $u"
}
park_mask monad-trader-rearm.timer
park_mask monad-trader-rearm.service
park_mask monad-trader.timer
park_mask monad-trader.service

# ── 7. Gateway / healthcheck / daily export ────────────────────────────────────
disarm ibkr-gateway-paper.timer
if systemctl is-active --quiet ibkr-gateway-paper.service; then must sudo systemctl stop ibkr-gateway-paper.service; say "stopped ibkr-gateway-paper.service"; fi
disarm monad-healthcheck.timer
disarm monad-daily-export.timer
must sudo systemctl daemon-reload

# ── 8. Receipt (sanitized) ─────────────────────────────────────────────────────
{
    echo "{"
    echo "  \"archive_id\": \"$ARCHIVE_ID\","
    echo "  \"decommissioned_at_utc\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
    echo "  \"git_commit\": \"$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null)\","
    echo "  \"parked_unit_files\": \"$(echo $parked)\","
    echo "  \"reconcile_passes\": $RECONCILE_PASSES,"
    echo "  \"leak_assertion\": \"$leak\","
    echo "  \"leak_scope\": \"$(echo "$commit_dirs" | sed "s#$REPO/##g")\","
    echo "  \"units\": {"
    first=1
    for u in $ALL_UNITS; do
        [ $first = 1 ] || echo ","
        first=0
        printf '    "%s": {"enabled": "%s", "active": "%s"}' "$u" "$(systemctl is-enabled "$u" 2>/dev/null || echo not-found)" "$(systemctl is-active "$u" 2>/dev/null || echo inactive)"
    done
    echo ""; echo "  },"
    echo "  \"revival\": \"OPERATIONS.md §6.1 — reviewed commit deleting ops/DECOMMISSIONED.json citing the admitted ENGINE_VERSION 3 hypothesis ID\""
    echo "}"
} > "$ARCHIVE_DIR/receipt.json"
cp "$ARCHIVE_DIR/receipt.json" "$LOG_DIR/decommission_receipt.json"
say "receipt written: $ARCHIVE_DIR/receipt.json (reconcile_passes=$RECONCILE_PASSES)"
unit_table
say "================ done. Review $ARCHIVE_DIR (and data/live_runs/pi_export_2026-06-26 if present), then commit them — no raw .db, no logs ================"
exit 0
