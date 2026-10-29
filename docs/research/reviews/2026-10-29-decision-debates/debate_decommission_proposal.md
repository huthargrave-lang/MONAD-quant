# Proposal: decommission the hourly paper trader as a live process on the Pi

**Role:** proposer. **Scope:** Pi runtime, expressed as repo content the Pi applies. `live/` stays fenced reference code; `engine.py` (ENGINE_VERSION 3) stays the research evaluator.

## Question

Should `monad-trader` stop being armed on the Pi, with the ~2 months of paper data preserved and exported sanitized so ENGINE_V3 item (g) (`stop_slippage_pct`) can be measured from it?

## Evidence

- **No edge, one-directional.** D6 (active no better than static 50/50–60/40, CI straddles 0); F13/F43 (hourly edge was a morning-only sampling artifact; live bot flat); F404703 (3-0 board rejection; O2: backtest stops fill exactly at the stop). D8 is the fallback.
- **The live record cannot validate anything.** F85 (≥40/65 entries on an in-progress bar), F87 (`fill_basis` is a quote), F97 (cycles counted, not bars), F104 (46 unhandled connection failures), F160 (10%-notional reported as account return; +35% is +3.1%; a hidden short). F94/Study 54: one execution component, no `execId`/VWAP (`live/broker.py:405`).
- **Already drafted as direction.** `docs/DIRECTIONS.md:63-71` (D-3) proposes exactly this and states the revival condition once.
- **Data at risk.** `git ls-files | grep pi_export` → **0**. `tools/live_backtest_reconciliation_study.py:48` hard-codes `data/live_runs/pi_export_2026-06-26/trades.jsonl`, which exists only on the Pi. The only committed live record is `archive_2026-06-18_pre_clean_run` (65 trades, 6 `stop_hit`).
- **Stop level is not persisted on closed trades.** `trades` has no `stop_price` (`live/state.py:50-59`); it lives on the transient `position` row (`state.py:152-153`), deleted at close. Recoverable from `trader.log` "Position opened … SL=" (`state.py:211`), the CRITICAL `stop` event "breached stop=" (`trader.py:526-531`), or reconstruction. Software and native stops share `exit_type="stop_hit"` (`trader.py:545` vs `broker.py:411-412`), so they must be split by event co-occurrence.
- **Fence.** `ctx can_edit ops/systemd/monad-trader.timer` → DENY, "needs explicit approval AND the trader stopped". Owner approval is granted; the script below enforces "stopped".
- **Re-arm hazard.** `deploy/monad-trader-rearm.timer:17` polls 10:00–15:50 ET and starts the trader whenever preflight passes (`ops/rearm_trader.sh:78-86`): stopping the trader first is undone within 10 minutes.

## Proposal

### (a) Units — order matters

| Step | Unit | Action | Why |
|---|---|---|---|
| 1 | `monad-trader-rearm.timer` + `.service` | `disable --now`, then `mask` | Must go first or it re-arms (above) |
| 2 | `monad-trader.timer` | `disable --now` | Stops the 09:22 ET cold start |
| 3 | `monad-trader.service` | **wait for flat**, `stop`, then `mask` | Never stop mid-hold: the GTC bracket would close with no local reconciler (OPERATIONS §1.5, `rearm_trader.sh:5-25`). No `[Install]`, so `mask` is the only refusal of a habitual `systemctl start`; the file stays |
| 4 | `monad-dashboard.service` | `disable` | Removes the `.wants` symlink; `BindsTo` already took it down |
| 5 | **final export + archive** (see b, c) | run once | Needs the Gateway up for the flat probe, so before step 6 |
| 6 | `ibkr-gateway-paper.timer` + `.service` | `disable --now`, `stop` | Only consumer was the trader; forward watches need vendor data, not IBKR (`DIRECTIONS.md:37-40`) |
| 7 | `monad-healthcheck.timer` | `disable --now` | Gateway off → `status=warn` every 5 min forever, the habituated alarm `deploy/monad-gitdrift.service:5-7` warns against |
| 8 | `monad-daily-export.timer` | `disable --now` **after** the final export | Daily dumps of a frozen DB are clutter. Deviates from D-3 ("keep the export"); unit stays installed, re-enable on revival |
| keep | `monad-gitdrift.timer`, `monad-screener.timer`, `monad-ctxweb`, `monad-researchui` | unchanged | The Pi's post-decommission role is research host (D-1) |

Nothing is uninstalled; `ops/systemd/*` templates stay as the canonical record with a header comment "DECOMMISSIONED <date> — see OPERATIONS.md §6.1".

### (b) `ops/decommission_trader.sh` — one shot, idempotent, fail-closed

- `set -uo pipefail`; log to `local_logs/decommission.log`; every step is `is-enabled`/`is-active`-guarded, so a re-run prints "already" and exits 0.
- **Gate 0:** port 7496 open → abort. **Gate 1:** flatness = preflight's read-only probe (`preflight_trader_start.sh:52-70`, clientId 70) says `FLAT=yes` **and** `SELECT COUNT(*) FROM position` = 0. Not flat → exit 75 ("rerun after the next :32 cycle books the exit"); timers 1–2 are already off so nothing re-arms meanwhile. Gateway down with a `position` row → exit 75 (cannot verify).
- Steps 1–4 above; assert `pgrep -f "[-]m live.trader"` is empty.
- **Archive via the existing tool:** `ops/archive_and_start_new_run.py --archive-id archive_<date>_decommission --no-run-marker` — two additive flags, defaults unchanged; it still refuses on active trader/open position (`:79-90`) and backs up the raw `.db` to gitignored `local_backups/` (`:144-149`) with sha256. Then `ops/analyze_run.py --all` → `analysis.txt`, and the new `ops/export_stop_exits.py` (c). Tar the untracked `pi_export_*` dirs into `local_backups/`.
- `ops/secret_scan.py` over the archive dir before printing "review and commit".
- Write `local_runtime/DECOMMISSIONED` (date, archive_id, commit, pointer to §6.1). **Preflight check 11** fails while it exists: one additive check covers the timer, rearm and manual-`systemctl` paths; `python -m live.trader` stays today's documented bypass (`tests/test_gap_study_derived_controls.py:150-157`).
- Steps 6–8; `daemon-reload`; print `systemctl list-timers 'monad-*' 'ibkr-*'` plus an `is-enabled/is-active` table as the receipt.

### (c) Sanitized export for (g)

**Lands in** `data/live_runs/archive_<date>_decommission/`: the eight standard files (regex `\bD?U[0-9]{5,}\b`, no raw `.db`), plus `stop_exits.jsonl`, `trader_log_exits.redacted.txt` (lines matching `Position opened|Bracket filled|Software stop filled|SOFTWARE STOP|fill unavailable`), `analysis.txt`, `metadata.json`. Also commit `pi_export_2026-06-26/` so the tracked study resolves.

**`stop_exits.jsonl`** — one row per `trades` row with `exit_type="stop_hit"`, or `bracket_exit` with `return_pct<0`:
`entry_time, exit_time, symbol, qty, direction, entry_basis` (= `exit_price/(1+return_pct)`, longs), `stop_level, stop_level_source ∈ {log_sl, event_stop, reconstructed}`, `exit_price`, `fill_source ∈ {ibkr_native_stp, ibkr_native_untyped, software_fill, software_mark_estimate, inferred}`, `exit_bar_open` (from `data/cache/TQQQ_1h.csv`), `session_boundary` (exit session ≠ entry session), `duplicate_writer` (another exit event within 60 s; F97/F160).
`software_*` iff a CRITICAL `stop` event sits within 120 s before `exit_time`; `software_mark_estimate` iff "using mark" (`trader.py:541-544`); `inferred` iff the WARNING "inferred stop_hit". The last two are **excluded** (not fills).

**Statistics (g), price units, no compounding (F160):**
- Intraday native: `slip = (stop_level − exit_price)/stop_level` (long; sign flipped for shorts), positive = adverse. Report n, median, mean, p75, p90.
- Gap native (`session_boundary`): `slip_gap = (exit_bar_open − exit_price)/exit_bar_open`, since v3 rule (b)1 fills at the open and charges `stop_slippage_pct` on top (`engine.py:326,358`). **Not** pooled.
- Software: `slip_sw = (stop_trigger − exit_price)/stop_trigger` — the :32-mark lateness declared DIVERGE in (i); reported, never used for `stop_slippage_pct`.
- `stop_slippage_pct` = median of intraday native; the admission record states value, source file, n. If n < 10 it says "under-measured" and uses p75 or a stated prior, per (g).

### (d) Revival condition (stated once, `OPERATIONS.md` §6.1)

Verbatim from D-3: *an hourly hypothesis registered against ENGINE_VERSION 3 that clears the admission gate. None exists.* Mechanically: owner sign-off → remove `local_runtime/DECOMMISSIONED` → `unmask` → re-enable in reverse order (rearm last) → fresh `archive_and_start_new_run.py`. Everywhere else links to §6.1.

### (e) What `OPERATIONS.md` says

§0 bullet 1 becomes: "**The paper trader is DECOMMISSIONED (<date>). Do not re-arm it.** Disabled timers, a dark dashboard and `is-enabled monad-trader.timer = disabled` are the *designed* state, not a failure. Revival: §6.1 only." §6 State column reads `DISABLED (decommissioned)` per unit, with the keep-list. §1 rule 2: "'armed to auto-start' is no longer true; the `live/` fence stays." `ops/README.md` "Preflight-gated autostart" and "Manually start the trader" become pointers to §6.1; `ctx route trader|archive` AVOID lines read "re-arming the decommissioned trader" (`context_map.json` edit, approval granted). `CLAUDE.md` §11 "Current live mode" → "reference mode; not live".

## Strongest objection and answer

*"You are shutting the only live-fill evidence stream just as (g) needs native stop fills; the dashboard goes dark; and the Pi has to stay up for the forward watches anyway, so keeping the trader is free."*

1. The stream's value is known and near zero (F85/F87/F97/F104/F160). For (g) it is worse: 6 `stop_hit` in 65 trades, several software (6 CRITICAL `stop` events incl. duplicate pairs), one execution component not VWAP (F94), no `execId` (Study 54), and **IBKR paper fills are a simulator property** (OPERATIONS §5: "the paper fill engine is the problem"). Two more months yields ~4 more biased simulator stops. If (g) needs n, the honest instrument is a purpose-built stop-fill probe or the realized-gap distribution in the D6 gap studies, not the strategy.
2. A dark dashboard is correct: it monitors a process that should not run. The research UIs (:8001/:8002) stay; the archive view is one ad-hoc localhost command.
3. Retiring the trader is not retiring the Pi. The watch records need vendor data, not IBKR (D-1). Keeping the trader is not free: rearm, preflight, healthcheck and Gateway exist only to feed it, cost operator attention, and produce "nothing admissible" (D-3).

## What would change my mind

- A v3-registered hourly hypothesis that clears admission (the revival condition itself).
- Evidence that paper-engine stop fills predict real-money slippage; then the stream is data, not simulator noise.
- The owner wants the IBKR Gateway for another research purpose (e.g. a dedicated stop-fill probe): keep `ibkr-gateway-paper.timer`, still retire the trader.
- The Pi's `pi_export_*` dirs and `state.db` disagree: that raises the archive's urgency, not a case for continued trading.
