# MONAD Quant — Live Operations & Deployment Context (for agents)

> **Purpose:** Institutional memory for the **live/paper deployment on the Raspberry Pi** —
> the infrastructure, the recent fixes, the honest performance picture, the safety
> conventions, and a session changelog. This is the operational counterpart to the
> **strategy** bible.
>
> - **Strategy / model / backtests / signal logic** → see `CLAUDE.md` and `AGENTS.md`.
> - **Live deployment, Pi ops, dashboard, this session's work** → this file.
>
> *Last updated: 2026-10-29 (trader decommissioned — §6.1). Deployment branch: `development`.*

---

## 0. TL;DR for an agent landing here

- **The paper trader is DECOMMISSIONED (2026-10-29) — `ops/DECOMMISSIONED.json`. Do not re-arm it.** Disabled/masked timers, a dark dashboard and `systemctl is-enabled monad-trader.timer` = `masked` are the **designed state**, not a failure. Revival: **§6.1 only** (a reviewed commit, not an ops action). Decision record: `docs/research/DECOMMISSION_TRADER_QUESTION.md` (direction D-3).
- This Pi ran **IBKR paper trading only** (TQQQ), never live. Paper API port **7497**; the live port **7496 must never be used**. The Pi's remaining role is the **research host** (ctxweb :8001, researchui :8002, screener and gitdrift timers — the D-1 forward watches).
- The trader, Gateway autostart, healthchecks and exports were driven by **systemd timers** (timezone-aware, scheduled in **America/New_York**; the Pi clock is **Europe/London**); the **dashboard** is a systemd service **coupled to the trader** (up iff the trader is up — §6/§8). All of these are now disabled or masked (§6).
- The deployment branch is **`development`** — it has the two correctness fixes + all ops tooling. Keep it checked out; the trader runs whatever is checked out.
- **Do not modify live trading/order/strategy logic** without explicit approval. Most tasks here are ops/observability/reporting.
- The headline backtest/paper numbers (e.g. **+35.20%**) are **inflated by broken-bracket artifacts** — the honest confirmed-fill edge is far lower. See §5.

---

## 1. Critical safety rules (read before touching anything)

1. **Paper only.** `config.LIVE_PAPER_MODE = True`, `config.LIVE_SYMBOL = "TQQQ"`. The trader connects to **7497**. Never enable live or touch 7496.
2. **Don't touch live trading logic** (`live/trader.py`, `live/broker.py`, `live/signals.py`, `live/state.py`, strategy/order code) without explicit user approval. The trader **was armed to auto-start; it is now decommissioned (§6.1)** — the `live/` fence stays, because this code is the reference the research evaluator (`src/strategy/engine.py`, ENGINE_VERSION 3) is checked against, and revival would re-arm exactly this path.
3. **Never commit:** `.env`, `~/.ibkr-paper.env`, raw `*.db`/`*.sqlite`, logs, credentials, **IBKR account IDs**, PID/runtime files, or raw trading data. `.gitignore` enforces most of this; always scan staged diffs.
4. **Redact account IDs** (`DUD…`/`U…`) in any output, export, or commit. They appear in `local_logs/`, `~/ibc`, `~/Jts` logs (all gitignored / outside the repo) — don't echo or share raw logs.
5. **Before changing runtime data / rotating anything:** confirm the **trader is inactive** and the **account is flat** (0 open positions). If a position is open or the trader is active, **stop and ask**.
6. **Pushing:** `origin` is HTTPS **without stored credentials**. Push via the SSH URL instead: `git push git@github.com:huthargrave-lang/MONAD-quant.git <branch>` (the Pi's SSH key is authorized for `huthargrave-lang`). **Never push to `main`** — use feature/`development` branches.
7. **Confirm hard-to-reverse / outward actions** (commits, pushes, service start/stop, order placement) before doing them unless already authorized.

---

## 2. The Pi environment

| Item | Value |
|---|---|
| Host / user | `raspberrypi` / `hudson` |
| OS / arch | Debian 12 (bookworm), Raspberry Pi 5 (aarch64) |
| **Timezone** | **Europe/London** (BST/GMT) — schedules use `America/New_York` explicitly |
| Repo | `/home/hudson/MONAD-quant` |
| venv / Python | `/home/hudson/MONAD-quant/venv` · Python 3.11.2 · `ib-insync 0.9.86`, `yfinance`, `fastapi`, `uvicorn`, `apscheduler`, `pandas` |
| Network | WiFi `wlan0`; **Tailscale** `100.76.6.75` (dashboard reachable at `http://100.76.6.75:8000` when running) |
| IB Gateway | 10.37 at `~/Jts/ibgateway/1037`; **IBC 3.23.0** at `~/ibc`; headless via **Xvfb :99** |
| Credentials | `~/.ibkr-paper.env` (chmod 600, **outside the repo**) — read at runtime, never committed |

Time conversions you'll need: **08:00 ET = 13:00 BST**, **09:22 ET = 14:22 BST**, **16:15 ET = 21:15 BST** (BST = ET + 5h in summer).

---

## 3. Branch map

| Branch | What it is |
|---|---|
| `main` | Base. **Behind** the dev tip — lacks Phase 6.4 `alerts` and later work. Don't deploy from it. |
| `claude/project-review-roadmap-A9Kdr` | The de-facto **dev tip** (has Phase 6.4 Slack alerts). Fixes branch off this, not `main`. |
| `pi-live-run-analysis` | The deep historical data analysis + the read-only diagnostic (`tools/diagnose_brackets.py`) + exports. |
| `fix-state-reconciliation` | The entry-time broker/state reconciliation guard (commit `ef967b6`). |
| `fix-software-take-profit` | The software take-profit fallback (commit `99847cb`). |
| **`development`** | **The deployment branch.** Integrates dev tip + both fixes + diagnostic + all `ops/` tooling + dashboard run-window reset. **This is what the Pi runs.** |

To deploy clean code, keep `development` checked out (`monad-trader.service` runs `python -m live.trader` from the checked-out tree).

---

## 4. The two correctness fixes (live in `development`)

1. **Entry-time reconciliation guard** (`live/trader.py::_on_bar_inner`): before opening a trade while `state.db` says flat, it verifies the **broker is actually flat**. If the broker holds a position the DB doesn't know about → **blocks the entry** (`entry_blocked_desync`, CRITICAL alert). Fail-safe: also blocks if the broker can't be verified. *Fixes the bug where the bot traded into a hidden short.* Tests: `tests/test_trader_reconcile.py`.
2. **Software take-profit fallback** (`config_modules/live.py: USE_SOFTWARE_TAKE_PROFIT=True`): mirrors the existing software stop — force-closes at market when the mark reaches target, because the **IBKR paper bracket TP frequently fails to fill** (letting winners ride to the time-exit and inflating returns). Tests: `tests/test_software_take_profit.py`.

---

## 5. The honest performance picture (important — don't be misled by headline numbers)

The historical paper run showed **+35.20% compounded** (62 "prod" trades). **That is mostly an artifact, not edge:**
- **9 `time_exit` trades (~+27 pp)** rode *past* the +1% target because the **bracket take-profit didn't fill** in the IBKR paper engine.
- Several `target_hit` were **inferred** (fill data unavailable), and 2 `estimated_close` were force-finalized with estimated prices.
- A **state desync** even let the bot trade on top of a hidden short.

**Confirmed-fill-only performance is roughly flat (~+0.2%) to ~+6%** over the same window. With the software take-profit now capping winners at +1%, **future numbers will look lower but honest.** A smaller, clean, desync-free week is the win condition. Full detail: `data/live_runs/analysis_2026-06-17/` (on `pi-live-run-analysis`) and `data/live_runs/model_phase_recommendations.md`.

Also note a **reporting discrepancy** (by design, not a bug): the dashboard computes **compounded** return over PROD-filtered trades; the trader's alert path (`state.get_trade_summary`) computes a **simple sum** over all trades. They will never match — unify before trusting cross-source numbers.

---

## 6. Live infrastructure (systemd, all paper, timezone-aware)

| Unit | Schedule (ET) | What it does | State |
|---|---|---|---|
| `ibkr-gateway-paper.timer` → `.service` | weekdays **08:00** | Start IB Gateway Paper headless (IBC+Xvfb), full re-auth from `~/.ibkr-paper.env`, open 7497. Runs `ops/start_ibkr_gateway.sh` (hard-gates `TradingMode=paper`+`7497`). | **DISABLED (decommissioned)**; service stopped. Unit files stay installed. |
| `monad-healthcheck.timer` → `.service` | weekdays **every 5 min 09:00–16:55** | `ops/healthcheck.sh` → `local_logs/healthcheck.json`. Read-only. | **DISABLED (decommissioned)** — with the Gateway off it would warn every 5 min forever (the habituated alarm `deploy/monad-gitdrift.service` warns against). |
| `monad-daily-export.timer` → `.service` | weekdays **16:15** | `ops/export_daily_data.py` → sanitized `data/live_runs/pi_export_<date>/`. | **DISABLED (decommissioned)** after the final export — a stated deviation from D-3 ("keep the export"): daily dumps of a frozen DB are clutter. Unit stays installed; re-enable on revival. |
| `monad-trader.timer` → `.service` | weekdays **09:22** | **Preflight-gated** trader autostart: `ExecStartPre=ops/preflight_trader_start.sh` (11 checks; check 11 fails while `ops/DECOMMISSIONED.json` exists) → `ops/start_trader.sh --exec` (also refuses on the marker). `Restart=no`. Logs to `local_logs/trader.log`. | **MASKED** (both units) — unit files parked in `/etc/systemd/system/.decommissioned/` by `ops/decommission_trader.sh` |
| `monad-trader-rearm.timer` → `.service` | weekdays **10:00–15:50 every 10 min** | Recovery-only re-arm attempt through the same preflight (`ops/rearm_trader.sh`). | **MASKED** (both units) — parked as above; disarmed FIRST by the decommission script, or it would restart the trader inside the decommission window |
| `monad-dashboard.service` | **with the trader** (no timer) | Read-only FastAPI monitor (`live.dashboard:app`) **coupled to the trader**: `BindsTo=monad-trader.service` (dies when the trader stops/crashes) + `[Install] WantedBy=monad-trader.service` (the trader's `.wants` symlink pulls it up after the trader starts). Tailnet-only at `http://100.76.6.75:8000`. `Restart=on-failure`. Template: `deploy/monad-dashboard.service`. | **DISABLED (decommissioned)** — dark by design; it monitors a process that must not run. The archive view is one ad-hoc localhost command (§8). |
| `monad-gitdrift.timer`, `monad-screener.timer`, `monad-ctxweb.service`, `monad-researchui.service` | unchanged | The Pi's post-decommission role: research host (D-1). No IBKR or `local_logs/healthcheck.json` dependency. | **KEEP — enabled** |

- **Dashboard ↔ trader coupling:** the dashboard is wired entirely from the dashboard-side unit — `monad-trader.service` is **not** edited. `systemctl enable monad-dashboard` creates `monad-trader.service.wants/monad-dashboard.service`; `BindsTo` provides the stop-side. Net effect: the dashboard runs **iff** the trader runs. To decouple (keep the dashboard always-on like `ctxweb`), drop `BindsTo`/`After=monad-trader.service` and change `WantedBy=` to `multi-user.target`.
- IB Gateway does an **IBKR-forced nightly shutdown (~23:45 BST / 18:45 ET)** requiring full re-auth; the morning timer restarts it. There is **no mid-market auto-recovery** yet — the healthcheck *observes* but doesn't restart. If the Gateway dies mid-session, restart manually: `sudo systemctl start ibkr-gateway-paper.service`.
- The trader **preflight** refuses to start unless: on `development`, Gateway up, 7497 open, **7496 closed**, IBKR connects, **account flat**, no duplicate trader, `state.db` writable, `local_logs/` writable, no recent healthcheck failure, **and not decommissioned** (check 11, a real `fail()` while `ops/DECOMMISSIONED.json` exists). A failed preflight = no trade that day (safe).
- Nothing was uninstalled. The parked unit files are listed in the Pi's receipt (`data/live_runs/archive_<date>_decommission/receipt.json`, committed with the archive), together with `reconcile_passes` (how many `--once --dry-run` reconcile cycles the script ran, which explains any trailing signal-snapshot rows in the archive) and the leak-assertion result.

### 6.1 Revival condition (stated once; everywhere else links here)

**Condition — D-3 verbatim:** *an hourly hypothesis registered against ENGINE_VERSION 3 that clears the admission gate. None exists.*

**Mechanics.** A **reviewed commit on `development` that deletes `ops/DECOMMISSIONED.json` and cites the admitted hypothesis ID** → the Pi pulls → `sudo systemctl unmask` the four trader units (`monad-trader.service`, `monad-trader.timer`, `monad-trader-rearm.service`, `monad-trader-rearm.timer`) → move the parked unit files back from `/etc/systemd/system/.decommissioned/` → `sudo systemctl daemon-reload` → re-enable in **reverse order** (Gateway timer, healthcheck, daily-export, trader timer, **rearm last**) → `ops/archive_and_start_new_run.py` for a fresh run window. Revival is auditable and re-clone-proof because the marker is tracked; deleting it locally changes nothing on the next pull.

**The three install paths the marker gates.** (1) `ops/systemd/` templates — `monad-trader.service` runs `ops/preflight_trader_start.sh`, whose check 11 fails on the marker (covers the timer, the rearm path and a habitual `systemctl start`); (2) `deploy/setup-pi.sh` — installs and **boot-enables** `deploy/monad-trader.service` with no preflight, so it refuses outright (exit 3) while the marker exists, and the deploy templates carry a DECOMMISSIONED header; (3) `ops/start_trader.sh --exec` — the documented foreground bypass refuses (exit 3) in both modes.

**Deliberately ungated:** the direct-module launch `venv/bin/python -m live.trader` stays ungated **by design** — `live/trader.py` is fenced, no scheduler calls it, and `ops/decommission_trader.sh`'s reconcile branch needs `--once --dry-run` to book a dead-trader `position` row through the trader's own reconciliation path. It is a research/diagnostic entry point, not an arming path.

**Do not** edit the units, the preflight or the marker on the Pi to "get it running again"; that is the accident this section exists to prevent.

---

## 7. `ops/` tooling (tracked, no secrets)

| Script | Purpose |
|---|---|
| `ops/status_check.sh` | One-shot human-readable status (system, gateway, trader, data freshness). Read-only. |
| `ops/healthcheck.sh` | Lightweight probe → `local_logs/healthcheck.json` (timer-driven). |
| `ops/healthcheck_ibkr.sh` | Deeper manual check incl. a live diagnostic connect. |
| `ops/start_ibkr_gateway.sh` | Headless IBC+Xvfb paper Gateway launcher (reads `~/.ibkr-paper.env`). |
| `ops/start_trader.sh` | Guarded trader starter. `--exec` mode = run trader in foreground (used by the service); no-arg = `systemctl start` (manual). |
| `ops/preflight_trader_start.sh` | The 11-check hard gate (logs `local_logs/trader_preflight.log`); check 11 = not decommissioned (§6.1). |
| `ops/export_daily_data.py` | Sanitized export of `state.db` → `data/live_runs/pi_export_<date>/`. |
| `ops/archive_and_start_new_run.py` | Archive history + raw backup + write run marker (refuses if trader active or position open). `--archive-id` and `--no-run-marker` (defaults unchanged) serve the decommission's final archive. |
| `ops/decommission_trader.sh` | **One-shot, idempotent, fail-closed** decommission of the trader as a live process (§6.1; decision record `docs/research/DECOMMISSION_TRADER_QUESTION.md`). Disarms rearm first, probes positions **and** resting orders, stops only when flat and clean, archives + exports, asserts no account id leaks, parks + masks the four trader units, writes a receipt. Exit 75 = rerun later. |
| `ops/export_stop_exits.py` | Read-only exporter of every stop-type exit with labelled provenance (fill source, fill time source, stop-level source) → `data/live_runs/archive_<date>_decommission/stop_exits.jsonl`, for ENGINE_V3 item (g). Data points, not an estimate. |
| `ops/DECOMMISSIONED.json` | The **tracked** decommission marker read by preflight check 11, `ops/start_trader.sh`, `deploy/setup-pi.sh` and the decommission script. Deleting it is the revival act (§6.1). |
| `ops/dashboard_smoke_test.sh` | Read-only dashboard server validation (endpoints, no-secret-leak, no DB mutation). |
| `ops/systemd/*` | Unit/timer templates (canonical source for the installed units). |
| `ops/README.md` | The ops runbook (install/enable, logs, manual trader start, export). |

---

## 8. Data model & dashboard

- **DB:** `live/state.db` (SQLite, gitignored). History tables: `trades`, `signal_history`, `monitor_events`. Current-state (single-row, overwritten each cycle): `position`, `monitor_status`, `signal_snapshot`, `account_snapshot`.
- **Dashboard:** `live/dashboard.py` (FastAPI, read-only for data; `init_db()` at import is an idempotent no-op). **Ran as `monad-dashboard.service`, coupled to the trader; disabled since the decommission** (see §6/§6.1 — dark by design; the ad-hoc localhost command below still serves the archive view) — bound to the Tailscale IP at `http://100.76.6.75:8000`. Manual/ad-hoc run (localhost): `venv/bin/python -m uvicorn live.dashboard:app --host 127.0.0.1 --port 8000` (from repo root — it imports `src.analysis.run_window`). Endpoints: `GET /`, `GET /health`, `GET /api/ticker/{symbol}`. Install/manage: `sudo cp deploy/monad-dashboard.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now monad-dashboard`.
- **Context-web map (separate service, :8001):** `tools/ctx.py serve` — the context layer's own read-only web view (interactive force-graph, rebuilt fresh each load; no DB/broker/secrets), kept deliberately separate from the fenced trading dashboard. Run ad-hoc: `venv/bin/python tools/ctx.py serve --host 0.0.0.0 --port 8001` → reachable over Tailscale at `http://100.76.6.75:8001`. Persistent: install the unit template `deploy/monad-ctxweb.service` (`sudo cp deploy/monad-ctxweb.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now monad-ctxweb`). Endpoints: `GET /` (the map), `GET /health`. Safe to auto-restart/enable on boot (unlike the trader). Restrict to tailnet-only with `--host 100.76.6.75`.
- **Current-run view:** an optional gitignored marker `local_runtime/current_run.json` (written by `ops/archive_and_start_new_run.py`) sets `started_at`. The dashboard defaults to **`?view=current`** (history filtered to ≥ `started_at`), with **`all`** and **`archive`** toggles. Health/staleness/current-state are **never** filtered. No marker → behaves as before. Pure logic: `src/analysis/run_window.py` (tested: `tests/test_run_window.py`).
- **Archives:** `data/live_runs/archive_2026-06-18_pre_clean_run/` (sanitized) and, once the Pi has run the decommission script and the operator has committed it, `data/live_runs/archive_<date>_decommission/` (the final archive, plus the stop-exit rows for ENGINE_V3 (g), the analyzer output and the decommission receipt — all under that directory) and `data/live_runs/pi_export_2026-06-26/` (referenced by tracked tools). Raw DB backups, the trader-log excerpt and the `pi_export_*` tarball are local-only at `local_backups/` (gitignored).

---

## 9. Runtime / local-only paths (all gitignored — never commit)

| Path | Contents |
|---|---|
| `~/.ibkr-paper.env` | IBKR paper credentials (600, in `$HOME`, outside repo) |
| `~/ibc/config.ini` | IBC config rendered at runtime with creds (600) |
| `local_logs/` | trader / gateway / healthcheck logs (may contain the paper account ID) |
| `local_runtime/current_run.json` | current-run marker |
| `local_backups/*.db` | raw `state.db` backups |
| `live/state.db`, `state.db` | the live SQLite DBs |

---

## 10. Known gotchas (will bite you)

- **`pgrep -f` / `pkill -f` self-match:** a pattern like `ibgateway` or `uvicorn live.dashboard` matches the *shell running the command* (its argv contains the pattern). For checks use a specific pattern (`ibcalpha.ibc.IbcGateway`) or the bracket trick (`[u]vicorn`); for kills use a **specific PID**, never `pkill -f "<broad pattern>"` (it can kill your own shell → exit 144).
- **Backgrounding a server inside an agent harness** can exit 144 (job control). Run `uvicorn … & UVPID=$!; curl …; kill $UVPID` inline works; the smoke-test script works fine in a real terminal.
- **yfinance 429s:** the signal source and dashboard ticker can rate-limit. Cache/tolerate; a 429 makes the trader correctly *block* entries (no bad data) but yields no trades.
- **BST vs ET confusion:** the Pi clock is Europe/London but everything is *scheduled* in ET. `systemctl list-timers` shows BST. "Tomorrow morning 09:22 ET" can display as "today 14:22 BST".

---

## 11. Session changelog (2026-06-17 → 2026-06-18)

Chronological summary of the live-ops work done in this stretch (all on/toward `pi-ops-automation`):

1. **Exported & analyzed** the historical paper data → found the +35% is mostly broken-bracket artifacts; brackets don't fill reliably in paper; a state desync let the bot trade into a hidden short. (`pi-live-run-analysis`)
2. **Built `tools/diagnose_brackets.py`** (read-only IBKR bracket/position diagnostic); confirmed via live probe that **order submission works** but the **paper fill engine is the problem**, and **flattened** an orphaned −1,059 TQQQ short (with approval) + reconciled `state.db`.
3. **Set up Gateway autostart** (IBC 3.23.0 + Xvfb + systemd timer, paper-only, creds in `~/.ibkr-paper.env`).
4. **Shipped two fixes** on their own branches: reconciliation guard (`ef967b6`), software take-profit (`99847cb`).
5. **Built `ops/` tooling + run plan** (`data/live_runs/next_week_run_plan.md`); installed healthcheck + daily-export timers.
6. **Added preflight-gated trader autostart** (`monad-trader.timer`, 09:22 ET) and enabled it (verified next fire pre-market, paper-only).
7. **Dashboard smoke test + model observability plan** (`data/live_runs/model_phase_recommendations.md`) — verified the dashboard is read-only and internally consistent.
8. **Run archive + current-run dashboard reset** — archived history, wrote the run marker, added the current/all/archive view toggle (dashboard-side only; `state.db` untouched).
9. **Agent context system** — `AGENT_INDEX.md`, `context_map.json`, `tools/ctx.py` (query CLI), anti-drift tests, per-area `CONTEXT.md`; pointers from `CLAUDE.md`/`AGENTS.md`.
10. **Parameter/codebase review** (`data/live_runs/parameter_review_2026-06-18.md`) — config matches documented optima, but a fresh realistic backtest yields **+0.08%/mo (Sharpe ~1.2)** vs the documented +2%/mo, agreeing with the ~flat live edge. Fixed: optional matplotlib in the backtest, the 730-day date-clamp bug, stale `requirements.txt`, CI (full suite + `pi-ops-automation`), and deduped `AGENTS.md`.
11. **Position-sizing extraction + 25 tests** — adaptive Kelly is now a pure, tested function (`src/strategy/sizing.position_fraction`); sweep gains `--sizing`/`--adaptive` so it can run fixed-10% (matching live) or adaptive Kelly. Backtest output unchanged.
12. **Next-changes audit** (`data/live_runs/next_changes_audit_2026-06-18.md`) — realistic WR is **41%** (EV +0.115%/trade), so the edge is marginal, not broken plumbing. Added **`ops/analyze_run.py`** (read-only run analyzer + clean-run rubric) for the pending clean run.

---

## 12. Open items / next steps

- **The trader is decommissioned (2026-10-29, §6.1).** Pending on the Pi: run `ops/decommission_trader.sh`, review and commit the final archive + `pi_export_2026-06-26` + receipt, fill the two null fields in `ops/DECOMMISSIONED.json`; then commit B (`ops/systemd/` headers, `context_map.json` routing) lands. The decision record is `docs/research/DECOMMISSION_TRADER_QUESTION.md`.
- **Benchmark comparison** on the dashboard (Bot vs QQQ/SPY/TQQQ, same window, compounded) — **planned and paused**; design is in the prior session notes. `src/analysis/` exists for the shared perf util.
- **Observability (post-run, trader stopped only):** `fill_source` column (`actual`/`inferred`/`estimated`), `model_version` stamping, signal-reason + no-trade-reason logging, unify the dashboard/alert return calc. See `data/live_runs/model_phase_recommendations.md`.
- **Mid-market Gateway auto-recovery** (healthcheck currently observes but doesn't restart).
- Three April-audit criticals remain (per `CLAUDE.md` §22): walk-forward Sharpe annualization for hourly, `sweep.py` dual-sync, CI dashboard collection.

## 13. Key docs to read next

- `CLAUDE.md` / `AGENTS.md` — strategy/model institutional memory (signals, regimes, sweeps, what worked/failed).
- `ops/README.md` — operational runbook.
- `data/live_runs/next_week_run_plan.md` — morning/EOD commands + failure recovery.
- `data/live_runs/model_phase_recommendations.md` — server-test results + observability roadmap.
- `data/live_runs/analysis_2026-06-17/` — the deep historical data analysis (on `pi-live-run-analysis`).
