# Skeptic ruling, round 1 — decommission the hourly paper trader

## Verification table

| Claim | Verdict | Found |
|---|---|---|
| `deploy/monad-trader-rearm.timer:17` polls 10:00–15:50 ET | VERIFIED | `OnCalendar=Mon..Fri 10..15:00/10 America/New_York` |
| `ops/rearm_trader.sh:78-86` starts on preflight pass; `:5-25` GTC rationale | VERIFIED | |
| `preflight_trader_start.sh:52-70` read-only probe, clientId 70, `FLAT=yes` | VERIFIED | positions only — see Obj. 4 |
| `live/state.py:50-59` trades has no `stop_price`; `:152-153`; `:211` "SL=" | VERIFIED | |
| `trader.py:526-531` CRITICAL `stop` "breached stop="; `:541-544` "using mark"; `:545` `stop_hit` | VERIFIED | |
| `broker.py:405` one execution component; `:411-412` STP→`stop_hit` | VERIFIED | Source 2 (`:449`) yields untyped `bracket_exit` |
| `archive_and_start_new_run.py:79-90` refuses; `:144-149` raw backup+sha256 | VERIFIED | `--archive-id`/`--no-run-marker` **do not exist** (only `--date`, `--notes`; id hard-coded `_pre_clean_run`; always writes `current_run.json`) — say "to be added" |
| `tests/test_gap_study_derived_controls.py:150-157` launch paths | VERIFIED | six paths incl. **"foreground starter bypass"** = `start_trader.sh --exec`, not only `python -m live.trader` |
| `live_backtest_reconciliation_study.py:48` hard-coded path | VERIFIED | also `tools/overnight_gap_risk_study.py:6016,6149,6340` |
| `git ls-files \| grep pi_export` → 0 | VERIFIED | |
| Archive: 65 trades, 6 `stop_hit`, 6 CRITICAL `stop` events w/ duplicate pairs | VERIFIED | event times match 4 exits to the second → **4 software, 2 native, 1 intraday-native** |
| `DIRECTIONS.md:63-71` D-3; `:37-40` | VERIFIED | D-3 is 63-75; vendor-data text is 39-43 |
| `ctx can_edit ops/systemd/monad-trader.timer` → DENY | VERIFIED | `context_map.json` (repo root) deny also lists itself |
| `monad-gitdrift.service:5-7` habituated alarm | VERIFIED | |
| OPERATIONS "§5: paper fill engine is the problem" | WRONG section | it is §11, line 160 (changelog) |
| OPERATIONS §1.5 | VERIFIED | §1 rule 5 |
| `engine.py:326,358` gap_stop fills open − slippage | VERIFIED | |
| `monad-trader.service` has no `[Install]` | VERIFIED for `ops/systemd/`; **WRONG for `deploy/monad-trader.service`** | deploy copy has `[Install] WantedBy=multi-user.target`, no `ExecStartPre`, and `deploy/setup-pi.sh:61-65` installs **and enables** it |
| dashboard `BindsTo` | VERIFIED (`deploy/monad-dashboard.service:12,44`) | |
| F85/F87/F94/F97/F104/F160, Study 54 (no `execId`), F404703 O2, (g)/(i) text | VERIFIED | |
| Units installed by `sudo cp` into `/etc/systemd/system` | VERIFIED (`ops/README.md:31,51,94`) | bears on Obj. 1 |
| "~2 months" of Pi data; `trader.log` unrotated on the Pi; no stop-pct change | UNVERIFIABLE | Pi unreachable; clone is shallow (258 commits) |

## Objections

1. **`mask` cannot succeed as installed.** Units are regular files in `/etc/systemd/system`; `systemctl mask` refuses ("already exists") and `--runtime` masks are shadowed by `/etc`. The script runs `set -uo pipefail` without `-e`, so it logs the failure and prints a receipt claiming a refusal that does not exist. *Fix:* move the unit files to `/etc/systemd/system/.decommissioned/` before masking (templates stay in the repo), assert `is-enabled == masked`, abort otherwise.

2. **An un-gated second install path survives.** `deploy/setup-pi.sh` installs `deploy/monad-trader.service` — no preflight, boot-enabled, `python -m live.trader --symbol TQQQ`. Check 11 never runs on it. *Fix:* `setup-pi.sh` refuses while the marker exists; both deploy files carry the DECOMMISSIONED header; §6.1 names them.

3. **Real deadlock: trader dead mid-hold.** Step 1 disables rearm, whose sole purpose (`rearm_trader.sh:5-25`) is this case. With `Restart=no`, a dead process plus a `position` row is never reconciled, so Gate 1 fails forever and "rerun after the next :32" never resolves. *Fix:* a branch for broker `FLAT=yes` ∧ row>0 ∧ trader inactive: run `tools/diagnose_brackets.py`, then reconcile with `venv/bin/python -m live.trader --once --dry-run` (entries suppressed at `trader.py:724`, bracket reconciliation at `:449-470` still runs), then re-gate.

4. **Gate 1 ignores resting orders.** The probe reads `ib.positions()` only. Orders rest at IBKR's servers, not the Gateway: an orphaned GTC child (F87's "working bracket without local state"; F160's hidden short) can fill as a short while the Pi is dark. *Fix:* Gate 1 also requires `reqAllOpenOrders()` empty for `LIVE_SYMBOL` (`diagnose_brackets.py:99-105` already does it; `:241` cancels), else abort listing the orders.

5. **`trades.exit_time` is the booking cycle, not the fill** (`state.py:247`, `datetime.now()`); both archived native stops book at `:32:01`. A 15:45 fill books at 09:32 next day, so `session_boundary`/`exit_bar_open` would label it a gap stop. *Fix:* native rows take `fill_time` from the "Bracket filled | fill_time=" log line; rows without one are `fill_time_source=booking` and excluded from the intraday/gap split.

6. **(g) n is ~1, not "under-measured".** The committed archive yields one intraday-native stop; p75 of n≤3 is noise. The ratified (g) names "archived live stop exits" as the instrument; this proposal switches that instrument off without amending the decision. *Fix:* state `n_native_intraday` up front, declare the archived-live source closed, and propose the (g) amendment (a `tools/note.py` node) naming the replacement — realized-gap distribution or a stated prior — rather than "p75 or a prior".

7. **Fence sequencing.** `ops/systemd/` and `context_map.json` are DENY "approval AND the trader stopped". This session cannot stop the trader, so committing those edits now violates the second clause. *Fix:* two commits — (A) ALLOW-path content (script, check 11, `start_trader.sh` guard, export tool, docs), Pi applies, receipt committed; (B) fenced edits after the receipt.

8. **Bypass coverage and never-rules.** (a) `start_trader.sh --exec` is a documented bypass and is ALLOW: add the marker check there (covers two launch paths). (b) `trader_log_exits.redacted.txt` is a log excerpt; OPERATIONS §1 rule 3 says never commit logs — fold the fields into `stop_exits.jsonl`, keep the excerpt in `local_backups/`. (c) Rule 4 names `DUD…` IDs; both redaction regexes (`\bD?U[0-9]{5,}\b`, secret_scan `\b(?:DU|U)\d{7,}\b`) miss a `DUD` prefix — confirm the real prefix before committing anything from the Pi.

9. **Marker fragility; revival by accident.** `local_runtime/` is gitignored: a re-clone drops the marker and check 11 passes; anyone with a shell can `rm` it, and nothing ties that to the hypothesis condition. *Fix:* track the marker (`ops/DECOMMISSIONED.json`: date, archive_id, n_native, §6.1 pointer); revival is a reviewed commit deleting it that cites the admitted hypothesis ID — auditable, re-clone-proof, not accidental.

*Minor:* OPERATIONS cite §5→§11:160. Keep `local_logs/healthcheck.json` and the `systemctl stop` line in OPERATIONS (pinned by `test_h39_doc_topology.py:178`, `test_h32…:189`). Check 11 must use `fail()` so `test_drift_arming_surfaces.py:141`'s `[FAIL]` count stays coherent.

## Strongest objection — is the answer sound?

Largely yes. F94 (one component, not VWAP), Study 54 (no `execId`; executions only since midnight), OPERATIONS:160 (fill engine), and the D6 study's external check (IBKR: a triggered stop is a market order, price not guaranteed) together say real stop slippage is a market property the paper simulator does not emit. `test_f19_exit_lever_bridge.py` shows the exit arithmetic is decided by `worst_case_ambiguity`, independent of any live stream. The answer is incomplete only where Objection 6 bites: (g) as ratified still points at the instrument being retired.

## (c) check

Disabling healthcheck/gateway/daily-export breaks nothing research-side: ctxweb, researchui, screener and gitdrift have no IBKR or `healthcheck.json` dependency (the screener timer mentions the export only for scheduling); `healthcheck.json` readers are preflight check 10 (stale → PASS) and `ctx.py:3097`'s runtime-file list.

## Ruling: DISPUTE

Objections 1–7 must be answered; 8–9 I would accept as design amendments in round 2.
