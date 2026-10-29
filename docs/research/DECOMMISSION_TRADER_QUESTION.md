# Decision: decommission the hourly paper trader as a live process (direction D-3)

**Status:** decided 2026-10-29 by decision debate (one proposer, one skeptic, two rounds:
round 1 DISPUTE with nine objections; round 2 CONCUR with six wording/design fixes, all
adopted verbatim below). Owner approval for D-3 was granted in advance. Executed in **two
commits**: **A** (this change — ALLOW paths and the Pi-side script), then the Pi applies it and
its receipt is committed, then **B** (the fenced `ops/systemd/` headers and `context_map.json`
routing). `live/` stays edit-fenced reference code; `src/strategy/engine.py` (ENGINE_VERSION
3, `ENGINE_V3_QUESTION.md`) stays the research evaluator. The runbook and the revival
condition live in **`OPERATIONS.md` §6.1** and nowhere else.

## Question

Should `monad-trader` stop being armed on the Pi, with the ~2 months of paper data preserved
and exported sanitized, so that ENGINE_V3 item (g) (`stop_slippage_pct`) can be closed
honestly rather than left pointing at an instrument that no longer runs?

## Evidence

- **No edge, one-directional.** D6 (active no better than static 50/50–60/40, CI straddles 0);
  F13/F43 (the hourly edge was a morning-only sampling artifact; the live bot is flat);
  F404703 (3-0 board rejection of the only hourly hypothesis; O2: backtest stops fill exactly
  at the stop). D8 is the fallback.
- **The live record cannot validate anything.** F85 (≥40/65 entries on an in-progress bar),
  F87 (`fill_basis` is a quote), F97 (cycles counted, not bars), F104 (46 unhandled connection
  failures), F160 (10%-notional reported as account return; +35% is +3.1%; a hidden short).
  F94 / Study 54: one execution component, no `execId` (`live/broker.py`).
- **Already drafted as direction.** `docs/DIRECTIONS.md` D-3 (lines 63–75) proposes exactly
  this and states the revival condition once; the vendor-data text for the forward watches is
  at lines 39–43 (they need vendor data, not IBKR).
- **Data at risk.** `git ls-files | grep pi_export` → 0, while
  `tools/live_backtest_reconciliation_study.py:48` and `tools/overnight_gap_risk_study.py`
  (three sites) hard-code `data/live_runs/pi_export_2026-06-26/trades.jsonl`, which exists
  only on the Pi. The only committed live record is `archive_2026-06-18_pre_clean_run` (65
  trades, 6 `stop_hit`).
- **Stop level is not persisted on closed trades.** `trades` has no `stop_price`
  (`live/state.py`); it lives on the transient `position` row, deleted at close. Native and
  software stops share `exit_type="stop_hit"` (`live/trader.py` vs `live/broker.py`), so they
  must be split by event co-occurrence. `trades.exit_time` is the **booking** cycle
  (`datetime.now()` in `close_position`), not the fill.
- **Re-arm hazard.** `deploy/monad-trader-rearm.timer` polls 10:00–15:50 ET and
  `ops/rearm_trader.sh` starts the trader whenever preflight passes: stopping the trader
  first is undone within 10 minutes unless rearm is disarmed first.
- **Second install path.** `deploy/setup-pi.sh` installs **and boot-enables**
  `deploy/monad-trader.service` (`[Install] WantedBy=multi-user.target`, no `ExecStartPre`),
  so a preflight check alone would not cover it.
- **Fence.** `ctx can_edit ops/systemd/monad-trader.timer` → DENY ("needs explicit approval
  AND the trader stopped"); likewise `context_map.json`. Approval exists; "stopped" is proven
  only by the Pi's receipt — hence two commits.

## Options

| Option | What changes | Cost |
|---|---|---|
| A. Keep the trader armed | nothing | rearm, preflight, healthcheck and the Gateway exist only to feed a process that produces nothing admissible; two more months yields ~4 more simulator stops |
| **B. Decommission as a live process (chosen)** | timers disabled/masked, units parked, final sanitized archive, tracked marker, (g) amended | a dark dashboard (correct: it monitors a process that must not run); the Pi stays as the D-1 research host |
| C. Keep the Gateway for a research probe, retire the trader | as B but `ibkr-gateway-paper.timer` stays | only if the owner wants a dedicated stop-fill probe; not requested |

## Decision-debate consensus (2026-10-29)

### (a) Units and order

1. `monad-trader-rearm.timer` + `.service`: `disable --now`, park, mask — **first**, or it
   restarts the trader inside the decommission window.
2. `monad-trader.timer`: `disable --now`, park, mask.
3. Broker probe (positions **and** resting orders) → decision matrix (b). Only on
   flat-and-clean: stop `monad-trader.service`, park, mask.
4. `monad-dashboard.service`: `disable` (drops the `.wants` symlink; `BindsTo` already
   stopped it).
5. Final archive + export + leak assertion (Gateway still up).
6. `ibkr-gateway-paper.timer` `disable --now`; stop the service.
7. `monad-healthcheck.timer` `disable --now` (would warn forever with the Gateway off).
8. `monad-daily-export.timer` `disable --now` **after** the final export — a stated deviation
   from D-3 ("keep the export"); the unit stays installed.

Keep: `monad-gitdrift.timer`, `monad-screener.timer`, `monad-ctxweb`, `monad-researchui`.
Nothing is uninstalled. `systemctl mask` cannot succeed on a real unit file in
`/etc/systemd/system`, so each file is **parked** in `/etc/systemd/system/.decommissioned/`
(systemd ignores dot-directories), then masked, then `is-enabled == masked` is **asserted**;
the parked files are listed in the receipt.

### (b) `ops/decommission_trader.sh` — decision matrix

| Broker pos | Resting orders | `position` rows | Trader | Action |
|---|---|---|---|---|
| ≠0 | any | any | active | exit 75: let the running trader and its bracket finish; rerun later |
| ≠0 | any | any | inactive | exit 75: position with no trader — `tools/diagnose_brackets.py`, flatten with approval |
| 0 | >0 | any | any | exit 75 listing orders (`orderId:type:status`, never the account), or cancel them with `--cancel-resting-orders` (symbol-scoped, only when the broker position is 0), then re-probe |
| 0 | 0 | >0 | active | exit 75: the :32 cycle will book it; rerun after. **If the row survives three cycles** it is a `pending_close` without `estimated_exit_price`, which `live/trader.py:421` never force-finalizes: stop the trader by hand and rerun to reach the reconcile branch |
| 0 | 0 | >0 | inactive | **reconcile branch**: `venv/bin/python -m live.trader --once --dry-run` × ≤3, re-gate (dry-run suppresses the entry at `trader.py:724`; the bracket reconciliation at `:449-497` still books the row; `PENDING_CLOSE_MAX_RETRIES=3`, hence three passes). The passes write a signal snapshot and monitor status; `reconcile_passes` is recorded in the receipt so the archive's trailing rows are explained |
| 0 | 0 | 0 | active | stop the service, wait for `pgrep` empty, continue |
| 0 | 0 | 0 | inactive | continue |

Gateway down → exit 75 (resting orders unverifiable; leak check impossible). Port 7496 open →
abort before touching anything. Every state-changing step goes through `must` (abort on
failure); **no receipt is written unless every assertion passed**. Idempotent after success:
a receipt plus all four trader units `masked` prints the unit table and exits 0 instead of
dying at the probe. Never prints or logs an account id.

### (c) Sanitized export and the (g) measurement

Lands in `data/live_runs/archive_<date>_decommission/`: the eight standard files
(`ops/archive_and_start_new_run.py --archive-id … --no-run-marker`), `stop_exits.jsonl`
(`ops/export_stop_exits.py`), `analysis.txt` (`ops/analyze_run.py --all`), `receipt.json`,
`metadata.json`. Also committed: `data/live_runs/pi_export_2026-06-26/` (referenced by tracked
tools). `local_backups/` (gitignored) receives the raw `.db`, the redacted `trader.log`
exit-line excerpt (never committed — OPERATIONS §1 rule 3; its fields fold into the JSONL),
and a tarball of every `pi_export_*` dir.

`stop_exits.jsonl` — one row per `stop_hit`, or `bracket_exit` with `return_pct < 0`:
`entry_time, exit_time` (booking), `fill_time, fill_time_source ∈ {ibkr_execution,
software_cycle, booking}, symbol, qty, direction, entry_basis, stop_level, stop_level_source ∈
{log_sl, event_stop, reconstructed}, exit_price, fill_source ∈ {ibkr_native_stp,
ibkr_native_untyped, software_fill, software_mark_estimate, inferred}, exit_bar_open,
session_boundary, duplicate_writer`. `ibkr_execution` fill times are parsed from the
`Bracket filled … fill_time=` log line on the Pi; software stops fill inside the :32 cycle, so
the CRITICAL `stop` event time is the fill time to within seconds. `software_mark_estimate`,
`inferred` and `fill_time_source = booking` rows are **excluded** from any slippage statistic
(the first two are not fills; the third cannot be split into intraday vs gap). Statistics are
price units with no compounding (F160) and are **reported as data points with n stated**, not
as the estimate: intraday native = stop vs fill; gap native = exit-bar open vs fill (v3 rule
(b)1 fills at the open); software = :32 trigger vs fill (DIVERGE under (i); reported, never
used).

Redaction uses the **widened** regex `\b(?:DU[A-Z]?|U)[0-9]{5,}\b` (the previous
`\bD?U[0-9]{5,}\b` missed a `DUD…` prefix) in `ops/export_daily_data.py`,
`ops/archive_and_start_new_run.py`, `ops/analyze_run.py` and `ops/export_stop_exits.py`;
`ops/secret_scan.py` widens to `\b(?:DU[A-Z]?|U)\d{7,}\b`. **And** the script asserts that the
exact `managedAccounts()` strings from the probe (kept in a 600-mode temp file, deleted at
exit) appear in **no** directory the runbook says to commit — the archive **and** every
`pi_export_*` dir — then runs `ops/secret_scan.py` over the same set. Fails closed if the
Gateway is down.

Evidence note on n: in the committed `archive_2026-06-18_pre_clean_run` the exporter, run
without the Pi's `trader.log`, classifies both native `stop_hit` rows as
`fill_time_source = booking` (both booked at the first :32 cycle after an overnight hold); the
"1 intraday-native" reading in the consensus text is the skeptic's event-time reading and is
resolved on the Pi by the `Bracket filled … fill_time=` lines. Either way n ≤ 1.

### (d) Revival condition — `OPERATIONS.md` §6.1, stated once

D-3 verbatim: *an hourly hypothesis registered against ENGINE_VERSION 3 that clears the
admission gate. None exists.* Mechanically: a reviewed commit on `development` that deletes
`ops/DECOMMISSIONED.json` and cites the admitted hypothesis ID → the Pi pulls → `unmask`,
move the parked units back, `daemon-reload`, re-enable in reverse order (rearm last) →
`archive_and_start_new_run.py`. §6.1 names the three install paths the tracked marker gates
(`ops/systemd/` via preflight check 11, `deploy/setup-pi.sh`, `ops/start_trader.sh --exec`)
and states that the direct-module launch `python -m live.trader` stays **ungated by design**
(fenced file; the reconcile branch needs it; no scheduler calls it).

### (e) Runbook text

`OPERATIONS.md` §0 bullet 1 (DECOMMISSIONED, do not re-arm, designed state); §1 rule 2
("was armed; now decommissioned; the `live/` fence stays"); §6 State column per unit
(`MASKED` / `DISABLED (decommissioned)` / `KEEP`) with the keep-list; new §6.1. The
`local_logs/healthcheck.json` runtime path stays in §6 and the main runbook does not document
the stop command (both test-pinned). `ops/README.md`: the autostart and manual-start sections
become pointers to §6.1 (its `systemctl stop monad-trader.service` line stays). `CLAUDE.md`
§11 `ACTIVE_MODE` comment → "reference mode; the live trader is decommissioned". Commit B:
`ops/systemd/*` headers; `context_map.json` routing AVOID for `trader`/`archive` →
"re-arming the decommissioned trader (OPERATIONS.md §6.1)" and the decommission facts.

### The six round-2 fixes (adopted verbatim)

1. **Idempotency after success.** Before the probe: receipt present (this date's archive, or
   the copy in `local_logs/`) and all four trader units `masked` → print the unit table, exit 0.
2. **The prior's justification.** Keep 0.0005 / 0.0015 but state them as a conservative prior
   with no claimed derivation (bounded by the single archived native point and IBKR's "price
   not guaranteed" statement); **drop** the `harsh`-mode attribution — that `slippage_pct` is a
   round-trip cost, a different quantity from trigger-to-fill slippage.
3. **The 3× stress is a gate rule.** Recorded here as this debate's consensus, marked
   **prospective**; `ENGINE_V3_QUESTION.md` (g) carries an explicit pointer to the amendment
   rather than silently rewritten text.
4. **Leak-assertion scope.** Scan every directory the runbook says to commit (the archive and
   every existing `pi_export_*` dir — `pi_export_2026-06-26` was sanitized with the old regex),
   and run `secret_scan.py` on them.
5. **Matrix row `0 | 0 | >0 | active` can stall** on a `pending_close` row without
   `estimated_exit_price` (`trader.py:421`); the operator message now says: if the row survives
   three cycles, stop the trader and rerun to reach the reconcile branch.
6. **Reconcile passes write rows.** `reconcile_passes` is recorded in `receipt.json`.

Minor: §6.1 states in one line that the direct-module launch path stays ungated by design.

### (g) amendment — the text ratified here (also appended to `ENGINE_V3_QUESTION.md`)

*The archived-live instrument is closed: the committed archive holds n_native_intraday = 1
(6 `stop_hit` = 4 software, 2 native, 1 overnight) and the Pi's paper fills are a simulator
property (OPERATIONS.md §11, changelog item 2: "the paper fill engine is the problem"). The
gap component of a stop is already filled at the open by rule (b)1 and its severity is the
realized TQQQ close→next-open loss distribution (Study #30, E54/F64,
`tools/overnight_gap_risk_study.py`). The intraday trigger-to-fill component uses a stated
prior `stop_slippage_pct = 0.0005` (5 bps) — a conservative prior with no claimed derivation,
bounded only by the single archived native point and IBKR's own statement that a triggered
stop becomes a market order whose execution price is not guaranteed (D6 execution-semantics
study, "External execution check") — and every admission record is re-run at 0.0015 (3×) and
must survive it. The decommission export's `stop_exits.jsonl` and the single archived native
point are recorded as data, not estimates. A measured instrument (a dedicated stop-fill probe
on a venue whose fills are market events) supersedes the prior.*

This is a **prospective gate rule** of the 2026-10-29 debate. Node:
`tools/note.py add --kind F --title "(g) archived-live stop-slippage instrument closed; replacement = gap distribution + 5bp prior, 3x stress" --link F404703:relates --link D6:supports --commit`
(the moderator runs it).

## The two commits

**Commit A — ALLOW paths + the Pi-side script (this change).**
Add: `ops/decommission_trader.sh` (executable; `bash -n` clean), `ops/DECOMMISSIONED.json`
(tracked marker; `archive_id`, `pi_receipt`, `git_commit` null until the receipt is
committed), `ops/export_stop_exits.py`, this file.
Modify: `ops/preflight_trader_start.sh` (check 11 via `fail()`, after check 10 and before the
alerting/deploy-sync reports; "ALL 11 checks"); `ops/start_trader.sh` (marker guard, exit 3,
both modes); `deploy/setup-pi.sh` (refuses on the marker, exit 3); `deploy/monad-trader.service`,
`deploy/monad-trader-rearm.service`, `deploy/monad-trader-rearm.timer` (DECOMMISSIONED
header); `ops/archive_and_start_new_run.py` (`--archive-id`, `--no-run-marker`, widened
regex); `ops/export_daily_data.py`, `ops/analyze_run.py`, `ops/secret_scan.py` (widened
regex); `ops/rearm_trader.sh` (comment: 11 checks); `OPERATIONS.md`; `ops/README.md`;
`CLAUDE.md` §11 (one comment); `docs/research/ENGINE_V3_QUESTION.md` ((g) pointer +
amendment). `RESEARCH_WEB.md` gains the (g) node through `tools/note.py` (moderator).

**Commit B — fenced edits, after the Pi receipt is in git.**
`ops/systemd/monad-trader.service`, `ops/systemd/monad-trader.timer`: header
`# DECOMMISSIONED <date> — parked on the Pi at /etc/systemd/system/.decommissioned/, masked;
OPERATIONS.md §6.1`. `context_map.json`: `routing` entries `trader` and `archive` AVOID →
"re-arming the decommissioned trader (OPERATIONS.md §6.1)"; `facts` gains the decommission
date and archive id. Approval: granted; "trader stopped": proven by `receipt.json`.

## Pi runbook (the operator, after commit A is on `development`)

```bash
cd ~/MONAD-quant && git pull                       # development; brings the marker + script
bash ops/decommission_trader.sh                    # exit 75 = "not now" with the reason; rerun later
#   read the resting-orders listing if it aborts there, then optionally:
# bash ops/decommission_trader.sh --cancel-resting-orders
ls data/live_runs/archive_$(date -u +%F)_decommission/ data/live_runs/pi_export_2026-06-26/
cat data/live_runs/archive_$(date -u +%F)_decommission/receipt.json     # units masked? leak HITS=0?
venv/bin/python ops/secret_scan.py data/live_runs/archive_$(date -u +%F)_decommission data/live_runs/pi_export_*
```
Then review both directories (no raw `.db`, no logs, no account id), fill `archive_id`,
`pi_receipt` and `git_commit` in `ops/DECOMMISSIONED.json`, and commit the archive +
`pi_export_2026-06-26/` + the marker on `development` (push via the SSH URL, OPERATIONS §1
rule 6). Commit B follows in the sandbox once that commit is visible.

## Strongest objection and answer

*"You are shutting the only live-fill evidence stream just as (g) needs native stop fills;
the dashboard goes dark; the Pi has to stay up anyway, so keeping the trader is free."*
The stream is a simulator property with one usable native point in nine weeks (F94, Study
54, OPERATIONS §11 item 2, IBKR's own "price not guaranteed"); two more months yields ~4 more
biased simulator stops. A dark dashboard is correct: it monitors a process that should not
run; the research UIs (:8001/:8002) stay. Retiring the trader is not retiring the Pi — the
forward watches need vendor data, not IBKR (D-1) — and keeping it is not free: rearm,
preflight, healthcheck and the Gateway exist only to feed it and produce nothing admissible.
The skeptic found this sound except where (g) still pointed at the retired instrument, which
the amendment closes.

## What would change the decision

A v3-registered hourly hypothesis that clears admission (the revival condition itself);
evidence that paper-engine stop fills predict market slippage; the owner wanting the Gateway
for a dedicated stop-fill probe (keep its timer, still retire the trader).
