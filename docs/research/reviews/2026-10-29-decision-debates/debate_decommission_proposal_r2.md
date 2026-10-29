# Proposal (round 2): decommission the hourly paper trader as a live process on the Pi

**Role:** proposer. **Round 1:** DISPUTE (9 objections; 1–7 must-answer). This revision answers each, adopts 8–9 and the corrections, and gives the moderator an executable list in two commits.

## Round 2 responses

| # | Objection | Verdict | Evidence / variant |
|---|---|---|---|
| 1 | `systemctl mask` cannot succeed on a real file in `/etc/systemd/system`; no `-e`, so the receipt would lie | **ACCEPT** | Units are `sudo cp`'d there (`ops/README.md:31,51,94`). Variant: the script **parks** each unit file in `/etc/systemd/system/.decommissioned/` (systemd ignores dot-dirs), then masks, then **asserts** `systemctl is-enabled == masked` and aborts otherwise. Every state-changing step goes through `must` (abort on failure); no receipt is written unless every assertion passed. |
| 2 | `deploy/setup-pi.sh:61-65` installs+enables `deploy/monad-trader.service` (has `[Install]`, no `ExecStartPre`); check 11 never runs | **ACCEPT** | My "no `[Install]`" was true only of `ops/systemd/monad-trader.service:33`; `deploy/monad-trader.service:26-27` has `WantedBy=multi-user.target`. Fix: `setup-pi.sh` refuses while `ops/DECOMMISSIONED.json` exists (exit 3); `deploy/monad-trader.service` and `deploy/monad-trader-rearm.{service,timer}` get the DECOMMISSIONED header; §6.1 names all three install paths. `deploy/` is ALLOW (`ctx can_edit deploy/setup-pi.sh`). |
| 3 | Disabling rearm first deadlocks a trader that died mid-hold (`Restart=no`, row never reconciles) | **ACCEPT (variant)** | Ordering stays (rearm would otherwise restart the trader inside the decommission window), and a **reconcile branch** is added for broker-flat ∧ `position` row>0 ∧ trader inactive ∧ no resting orders: `venv/bin/python -m live.trader --once --dry-run`, up to 3 passes. Verified: `--once` calls `on_bar()` immediately (`trader.py:946-950`); dry-run only suppresses the entry (`trader.py:724-737`); the bracket reconciliation at `trader.py:449-497` still runs and books the row (fill or `*_inferred`); `pending_close` force-finalizes after `PENDING_CLOSE_MAX_RETRIES=3` (`config_modules/live.py:16`), hence 3 passes. The marker deliberately does **not** gate `python -m live.trader` (fenced file; this branch needs it). |
| 4 | Gate 1 reads positions only; orphaned GTC children rest at IBKR and can fill short while the Pi is dark | **ACCEPT** | Probe adds `reqAllOpenOrders()` + `openTrades()` filtered to `LIVE_SYMBOL` (the `tools/diagnose_brackets.py:99-105` pattern). Non-empty → abort listing `orderId/type/status` (never account). Opt-in `--cancel-resting-orders` cancels symbol-scoped resting orders (`ib.cancelOrder`, as `diagnose_brackets.py:241`) **only** when the broker position is 0, then re-probes. Default is abort, because cancellation is an order action. |
| 5 | `trades.exit_time` is booking time (`state.py:247`), so a from-`exit_time` gap/intraday split misclassifies | **ACCEPT** | `stop_exits.jsonl` gains `fill_time` + `fill_time_source ∈ {ibkr_execution, software_cycle, booking}`; `ibkr_execution` is parsed from the "Bracket filled … fill_time=" line (`trader.py:456-458`) on the Pi; software stops fill inside the :32 cycle, so the CRITICAL event time is the fill time to within seconds; `booking` rows are **excluded** from the intraday/gap split. |
| 6 | (g) n_native_intraday ≈ 1; "p75 or a prior" is noise, and (g) as ratified names the instrument being retired | **ACCEPT** | Archive: 6 `stop_hit` = 4 software + 2 native, 1 intraday-native. The proposal now carries an explicit **(g) amendment** naming the replacement (below) and the `tools/note.py` node that records it. The retired instrument's final sample is recorded as data points, not an estimate. |
| 7 | Fenced edits need "approval AND trader stopped"; this session cannot stop it | **ACCEPT** | Two commits: **A** (ALLOW paths + Pi script), Pi runs it, receipt committed; **B** (`ops/systemd/`, `context_map.json`) after the receipt. |
| 8a | `start_trader.sh --exec` is a documented bypass and ALLOW | adopted | marker check at the top of `ops/start_trader.sh` (both modes). |
| 8b | No committed `trader.log` excerpt (OPERATIONS §1 rule 3) | adopted | excerpt goes to gitignored `local_backups/`; its fields fold into `stop_exits.jsonl`. |
| 8c | Both redaction regexes miss a `DUD…` prefix | adopted + stronger | regexes widened to `\b(?:DU[A-Z]?\|U)[0-9]{5,}\b` in the export and archive tools; **and** the script asserts the exact `managedAccounts()` strings from the probe appear nowhere in the archive (kept in a 600-mode temp file, deleted at exit). Fails closed if the Gateway is down. |
| 9 | Gitignored marker is fragile; revival by accident | adopted | tracked `ops/DECOMMISSIONED.json`; preflight check 11, `start_trader.sh`, `setup-pi.sh` and the script read it; revival is a reviewed commit deleting it that cites the admitted hypothesis ID. |
| — | Corrections | adopted | "paper fill engine is the problem" is OPERATIONS §11:160; D-3 is `DIRECTIONS.md:63-75`, vendor text `:39-43`; `--archive-id`/`--no-run-marker` are **additions proposed here**. Pins respected: OPERATIONS keeps `local_logs/healthcheck.json` (`test_h39_doc_topology.py:178`) and must **not** contain `systemctl stop monad-trader` (`test_h32…:189`); `ops/README.md` keeps that line (`:182`); check 11 uses `fail()` so `test_drift_arming_surfaces.py:141` sees baseline and broken counts move together. |

## Question

Stop arming `monad-trader` on the Pi; keep `live/` fenced reference code and `engine.py` (ENGINE_VERSION 3) the research evaluator; preserve and export the ~2 months of paper data sanitized so (g) can be closed honestly.

## Evidence (unchanged from round 1, corrected cites)

D6, F13/F43, F404703 (no edge; 3-0 rejection; O2 zero stop slippage). F85/F87/F97/F104/F160, F94, Study 54 (the live record cannot validate; fills keep one component, no `execId`). `DIRECTIONS.md:63-75` (D-3). `git ls-files | grep pi_export` = 0 while `tools/live_backtest_reconciliation_study.py:48` and `overnight_gap_risk_study.py:6016,6149,6340` hard-code `pi_export_2026-06-26`. `trades` has no `stop_price` (`state.py:50-59`); native and software stops share `exit_type` (`trader.py:545`, `broker.py:411`). Re-arm hazard: `deploy/monad-trader-rearm.timer:17`, `rearm_trader.sh:78-86`.

## Proposal (revised)

### (a) Units and order
1. `monad-trader-rearm.timer` + `.service`: `disable --now`, park, mask.
2. `monad-trader.timer`: `disable --now`, park, mask.
3. Broker probe (positions **and** resting orders) → decision matrix (b). Only on flat-and-clean: stop `monad-trader.service`, park, mask.
4. `monad-dashboard.service`: `disable` (drops the `.wants` symlink; `BindsTo` already stopped it).
5. Final archive + export + leak assertion (Gateway still up).
6. `ibkr-gateway-paper.timer` `disable --now`; stop the service.
7. `monad-healthcheck.timer` `disable --now` (would warn forever with the Gateway off).
8. `monad-daily-export.timer` `disable --now` after the final export (stated deviation from D-3; unit stays installed).
Keep: `monad-gitdrift.timer`, `monad-screener.timer`, `monad-ctxweb`, `monad-researchui`. Nothing is uninstalled; parked unit files are listed in the receipt.

### (b) `ops/decommission_trader.sh` — decision matrix
| Broker pos | Resting orders | `position` rows | Trader | Action |
|---|---|---|---|---|
| ≠0 | any | any | active | exit 75: let the running trader and its bracket finish; rerun later |
| ≠0 | any | any | inactive | exit 75: position with no trader — `tools/diagnose_brackets.py`, flatten with approval |
| 0 | >0 | any | any | exit 75 listing orders, or cancel them with `--cancel-resting-orders`, then re-probe |
| 0 | 0 | >0 | active | exit 75: the :32 cycle will book it; rerun after |
| 0 | 0 | >0 | inactive | **reconcile branch**: `live.trader --once --dry-run` ×≤3, re-gate |
| 0 | 0 | 0 | active | stop the service, wait for `pgrep` empty, continue |
| 0 | 0 | 0 | inactive | continue |
Gateway down → exit 75 (orders unverifiable; leak check impossible). Port 7496 open → abort. Full text below.

### (c) Sanitized export and the (g) measurement
Lands in `data/live_runs/archive_<date>_decommission/`: the eight standard files, `stop_exits.jsonl`, `analysis.txt`, `receipt.json`, `metadata.json`. Also commit `pi_export_2026-06-26/` (referenced by tracked tools). `local_backups/` (gitignored) receives the raw `.db`, the `trader.log` exit-line excerpt, and a tarball of all `pi_export_*` dirs.

`stop_exits.jsonl` (one row per `stop_hit`, or `bracket_exit` with `return_pct<0`): `entry_time, exit_time_booking, fill_time, fill_time_source, symbol, qty, direction, entry_basis, stop_level, stop_level_source ∈ {log_sl, event_stop, reconstructed}, exit_price, fill_source ∈ {ibkr_native_stp, ibkr_native_untyped, software_fill, software_mark_estimate, inferred}, exit_bar_open, session_boundary, duplicate_writer`. `software_mark_estimate`, `inferred` and `fill_time_source=booking` rows are excluded from any slippage statistic. Statistics as in round 1 (intraday native vs stop; gap native vs exit-bar open; software vs :32 trigger; price units, no compounding), **reported as data points with n stated**, not as the estimate.

**(g) amendment (proposed text for `ENGINE_V3_QUESTION.md` and a `note.py` F-node):** *The archived-live instrument is closed: the committed archive holds n_native_intraday = 1 (6 `stop_hit` = 4 software, 2 native, 1 overnight) and the Pi's paper fills are a simulator property (OPERATIONS §11:160). The gap component of a stop is already filled at the open by rule (b)1 and its severity is the realized TQQQ close→next-open loss distribution (Study #30, E54/F64, `tools/overnight_gap_risk_study.py`). The intraday trigger-to-fill component uses a stated prior `stop_slippage_pct = 0.0005` (5 bps, the `harsh`-mode cost convention) and every admission record is re-run at 0.0015 and must survive it. The decommission export's `stop_exits.jsonl` and the single archived native point are recorded as data, not estimates. A measured instrument (a dedicated stop-fill probe on a venue whose fills are market events) supersedes the prior.* Node: `tools/note.py add --kind F --title "(g) archived-live stop-slippage instrument closed; replacement = gap distribution + 5bp prior, 3x stress" --link F404703:relates --link D6:supports --commit`.

### (d) Revival condition — `OPERATIONS.md` §6.1, stated once
D-3 verbatim: *an hourly hypothesis registered against ENGINE_VERSION 3 that clears the admission gate. None exists.* Mechanically: a reviewed commit on `development` that deletes `ops/DECOMMISSIONED.json` and cites the admitted hypothesis ID → the Pi pulls → `unmask`, move the parked units back, `daemon-reload`, re-enable in reverse order (rearm last) → `archive_and_start_new_run.py`. Everywhere else links to §6.1.

### (e) Runbook text
`OPERATIONS.md` §0 bullet 1: "**The paper trader is DECOMMISSIONED (<date>) — `ops/DECOMMISSIONED.json`. Do not re-arm it.** Disabled/masked timers, a dark dashboard, `is-enabled monad-trader.timer = masked` are the designed state. Revival: §6.1 only." §6: State column `MASKED`/`DISABLED (decommissioned)` per unit; the healthcheck row keeps `local_logs/healthcheck.json`; new §6.1 names all three install paths (`ops/systemd/`, `deploy/setup-pi.sh`, `start_trader.sh --exec`). §1 rule 2: "armed to auto-start" → "was armed; now decommissioned; the `live/` fence stays". §5 cite → §11:160. `ops/README.md`: autostart and manual-start sections become pointers to §6.1 (the `systemctl stop monad-trader.service` line stays). `CLAUDE.md` §11 "Current live mode" → "reference mode; not live". Commit B: `ops/systemd/*` headers; `context_map.json` routing AVOID for `trader`/`archive` → "re-arming the decommissioned trader (OPERATIONS.md §6.1)".

## Strongest objection and answer
Unchanged in substance; the skeptic found it sound except where (g) still pointed at the retired instrument — closed by the amendment above. One line: the stream is a simulator property with one usable native point in nine weeks; a dark dashboard is correct; the Pi stays as the D-1 research host, and rearm/preflight/healthcheck/Gateway exist only to feed a process that produces nothing admissible.

## What would change my mind
A v3-registered hourly hypothesis that clears admission; evidence that paper-engine stop fills predict market slippage; the owner wanting the Gateway for a research probe (keep its timer, still retire the trader).

---

## Implementation list

### Commit A — ALLOW paths + the Pi-side script (this sandbox, now)
**Add**
- `ops/decommission_trader.sh` — full text below; `chmod +x`; passes `bash -n` (`tests/test_shell_syntax.py` globs `ops/**/*.sh`).
- `ops/DECOMMISSIONED.json` — `{"decommissioned_on": "<date>", "decision": "docs/research/DECOMMISSION_TRADER_QUESTION.md", "revival": "OPERATIONS.md §6.1: a reviewed commit deleting this file, citing the admitted ENGINE_VERSION 3 hourly hypothesis ID", "archive_id": null, "pi_receipt": null}` (the two nulls are filled when the receipt is committed).
- `ops/export_stop_exits.py` — read-only on `state.db`; args `--archive DIR --trader-log PATH --bars PATH`; writes `DIR/stop_exits.jsonl` (schema in c) and `local_backups/trader_log_exits_<date>.redacted.txt`; same redaction regex as below; never prints account IDs.
- `docs/research/DECOMMISSION_TRADER_QUESTION.md` — the question, this consensus, in the `ENGINE_V3_QUESTION.md` record style.

**Modify**
- `ops/preflight_trader_start.sh` — after check 10, before the REPORT blocks: `# 11. Not decommissioned` → `if [ -f "$REPO/ops/DECOMMISSIONED.json" ]; then fail "trader is DECOMMISSIONED (ops/DECOMMISSIONED.json) — OPERATIONS.md §6.1"; else pass "not decommissioned"; fi`; header "ALL 10 checks" → "ALL 11 checks".
- `ops/start_trader.sh` — before the paper gate: refuse (exit 3) when `$REPO/ops/DECOMMISSIONED.json` exists, both modes.
- `deploy/setup-pi.sh` — after `REPO_DIR` detection: same refusal.
- `deploy/monad-trader.service`, `deploy/monad-trader-rearm.service`, `deploy/monad-trader-rearm.timer` — header comment `# DECOMMISSIONED <date> — do not install/enable; OPERATIONS.md §6.1`.
- `ops/archive_and_start_new_run.py` — add `--archive-id` (default `archive_<date>_pre_clean_run`) and `--no-run-marker`; widen `ACCT_RE`.
- `ops/export_daily_data.py` — widen `_ACCT_RE` to `\b(?:DU[A-Z]?|U)[0-9]{5,}\b`.
- `ops/secret_scan.py` — `ACCOUNT_ID` → `\b(?:DU[A-Z]?|U)\d{7,}\b`.
- `OPERATIONS.md`, `ops/README.md`, `CLAUDE.md` §11, `docs/DIRECTIONS.md` D-3 (mark "in progress; export disabled after the final run"), `docs/research/ENGINE_V3_QUESTION.md` (g) amendment — as in (e)/(c).
- `RESEARCH_WEB.md` via `tools/note.py add … --commit` (the (g) node).

**Pi applies A:** `git pull` on `development`; `bash ops/decommission_trader.sh` (optionally `--cancel-resting-orders` after reading the listing); review `data/live_runs/archive_<date>_decommission/` and `pi_export_2026-06-26/`; commit both (sanitized) plus the two filled fields in `ops/DECOMMISSIONED.json`.

### Commit B — fenced edits, after the Pi receipt is in git
- `ops/systemd/monad-trader.service`, `monad-trader.timer` — header `# DECOMMISSIONED <date> — parked on the Pi at /etc/systemd/system/.decommissioned/, masked; OPERATIONS.md §6.1`.
- `context_map.json` — `routing` entries `trader` and `archive`: AVOID → "re-arming the decommissioned trader (OPERATIONS.md §6.1)"; `facts` gains the decommission date and archive id.
Approval: granted; "trader stopped": proven by `receipt.json`.

### `ops/decommission_trader.sh` (full text)

```bash
#!/usr/bin/env bash
#
# decommission_trader.sh — ONE-SHOT, IDEMPOTENT decommission of the MONAD paper
# trader as a live process on the Pi. Decision: docs/research/DECOMMISSION_TRADER_QUESTION.md
# Runbook: OPERATIONS.md §6.1 (the revival condition lives there and nowhere else).
#
# What it does, in order (each step is state-checked, so re-running is a no-op):
#   0. invariants: paper port only (7496 must be closed), tracked marker present
#   1. disarm the schedulers: rearm timer+service, trader timer
#   2. broker probe (read-only, clientId 71): positions AND resting orders for
#      LIVE_SYMBOL, plus the local position row and trader liveness -> decision matrix
#   3. stop the trader only when broker flat, no resting orders, no local row
#   4. final archive via ops/archive_and_start_new_run.py (raw .db -> local_backups/,
#      sanitized -> data/live_runs/archive_<date>_decommission/), analysis, stop_exits
#   5. leak assertion: the exact broker account strings must appear nowhere in the export
#   6. park unit files in /etc/systemd/system/.decommissioned/ and mask them
#   7. disable gateway/healthcheck/daily-export timers; stop the gateway
#   8. receipt (sanitized) -> archive dir + local_logs; print the unit table
#
# Fail-closed: any assertion failure aborts BEFORE the receipt is written. Exit 75 =
# "not now, rerun later" (position open, orders resting, gateway down). PAPER ONLY.
# Never prints or logs an account ID. Cancelling resting orders is opt-in
# (--cancel-resting-orders) because it is an order action.
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

DATE="$(date -u +%Y-%m-%d)"
CANCEL_ORDERS=0
for a in "$@"; do
    case "$a" in
        --cancel-resting-orders) CANCEL_ORDERS=1 ;;
        --date=*) DATE="${a#--date=}" ;;
        -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
        *) echo "unknown arg: $a"; exit 2 ;;
    esac
done
ARCHIVE_ID="archive_${DATE}_decommission"
ARCHIVE_DIR="$REPO/data/live_runs/$ARCHIVE_ID"

mkdir -p "$LOG_DIR" "$RUNTIME" "$BACKUPS" 2>/dev/null || true
ts()   { date '+%Y-%m-%d %H:%M:%S %Z'; }
note() { echo "$(ts) [decommission] $*" >> "$LOG"; }
say()  { echo "[decommission] $*"; note "$*"; }
die()  { say "ABORT: $*"; exit "${2:-1}"; }
must() { "$@" || die "command failed: $*"; }
cleanup() { rm -f "$ACCT_FILE" 2>/dev/null || true; }
trap cleanup EXIT

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
local_rows() { "$PY" - <<'PY' 2>/dev/null
import sqlite3, os
p = os.path.join(os.environ["HOME"], "MONAD-quant", "live", "state.db")
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
    [ "$alive" = 1 ] && die "local position row present and trader running — the next :32 cycle books it; rerun after" 75
    say "broker flat but local position row present and trader dead — reconciling via the trader's own path (dry-run suppresses entries)"
    for i in 1 2 3; do
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
    (cd "$REPO" && "$PY" ops/export_stop_exits.py --archive "$ARCHIVE_DIR" --trader-log "$LOG_DIR/trader.log" --bars "$REPO/data/cache/TQQQ_1h.csv") >> "$LOG" 2>&1 \
        || say "export_stop_exits.py failed (non-fatal; stop_exits.jsonl missing)"
    if ls -d "$REPO"/data/live_runs/pi_export_* >/dev/null 2>&1; then
        tar czf "$BACKUPS/pi_exports_${DATE}.tgz" -C "$REPO/data/live_runs" $(cd "$REPO/data/live_runs" && ls -d pi_export_*) && say "pi_export_* tarred to local_backups/"
    fi
    cp "$LOG_DIR/trader.log" "$BACKUPS/trader_${DATE}.log" 2>/dev/null || true
fi

# ── 5. Leak assertion: exact account strings + widened regex + secret scan ─────
leak=$(ACCT_FILE="$ACCT_FILE" DIR="$ARCHIVE_DIR" "$PY" - <<'PY' 2>/dev/null
import os, re
accts = [a.strip() for a in open(os.environ["ACCT_FILE"]).read().split() if a.strip()] if os.path.exists(os.environ["ACCT_FILE"]) else []
rx = re.compile(r"\b(?:DU[A-Z]?|U)[0-9]{5,}\b")
hits = 0
for root, _, files in os.walk(os.environ["DIR"]):
    for fn in files:
        txt = open(os.path.join(root, fn), errors="replace").read()
        hits += sum(txt.count(a) for a in accts) + len(rx.findall(txt))
print(f"HITS={hits} ACCTS={len(accts)}")
PY
)
case "$leak" in HITS=0\ ACCTS=[1-9]*) say "leak assertion passed ($leak)" ;; *) die "ACCOUNT-ID LEAK or no accounts to check ($leak) — DO NOT COMMIT $ARCHIVE_DIR; fix redaction and rerun" ;; esac
(cd "$REPO" && "$PY" ops/secret_scan.py "$ARCHIVE_DIR") >> "$LOG" 2>&1 || die "ops/secret_scan.py flagged $ARCHIVE_DIR — do not commit"

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
units="monad-trader.service monad-trader.timer monad-trader-rearm.service monad-trader-rearm.timer monad-dashboard.service ibkr-gateway-paper.timer ibkr-gateway-paper.service monad-healthcheck.timer monad-daily-export.timer monad-gitdrift.timer monad-screener.timer monad-ctxweb.service monad-researchui.service"
{
    echo "{"
    echo "  \"archive_id\": \"$ARCHIVE_ID\","
    echo "  \"decommissioned_at_utc\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
    echo "  \"git_commit\": \"$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null)\","
    echo "  \"parked_unit_files\": \"$(echo $parked)\","
    echo "  \"leak_assertion\": \"$leak\","
    echo "  \"units\": {"
    first=1
    for u in $units; do
        [ $first = 1 ] || echo ","
        first=0
        printf '    "%s": {"enabled": "%s", "active": "%s"}' "$u" "$(systemctl is-enabled "$u" 2>/dev/null || echo not-found)" "$(systemctl is-active "$u" 2>/dev/null || echo inactive)"
    done
    echo ""; echo "  },"
    echo "  \"revival\": \"OPERATIONS.md §6.1 — reviewed commit deleting ops/DECOMMISSIONED.json citing the admitted ENGINE_VERSION 3 hypothesis ID\""
    echo "}"
} > "$ARCHIVE_DIR/receipt.json"
cp "$ARCHIVE_DIR/receipt.json" "$LOG_DIR/decommission_receipt.json"
say "receipt written: $ARCHIVE_DIR/receipt.json"
systemctl list-timers 'monad-*' 'ibkr-*' --no-pager 2>/dev/null | tee -a "$LOG"
say "================ done. Review $ARCHIVE_DIR (and data/live_runs/pi_export_2026-06-26 if present), then commit them — no raw .db, no logs ================"
exit 0
```
