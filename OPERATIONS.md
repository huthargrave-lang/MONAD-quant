# MONAD Quant — Live Operations & Deployment Context (for agents)

> **Purpose:** Institutional memory for the **live/paper deployment on the Raspberry Pi** —
> the infrastructure, the recent fixes, the honest performance picture, the safety
> conventions, and a session changelog. This is the operational counterpart to the
> **strategy** bible.
>
> - **Strategy / model / backtests / signal logic** → see `CLAUDE.md` and `AGENTS.md`.
> - **Live deployment, Pi ops, dashboard, this session's work** → this file.
>
> *Last updated: 2026-06-18. Deployment branch: `development`.*

---

## 0. TL;DR for an agent landing here

- This Pi runs **IBKR paper trading only** (TQQQ), never live. Paper API port **7497**; the live port **7496 must never be used**.
- The live trader, Gateway autostart, healthchecks, exports, and dashboard are all driven by **systemd timers** (timezone-aware, scheduled in **America/New_York**; the Pi clock is **Europe/London**).
- The deployment branch is **`development`** — it has the two correctness fixes + all ops tooling. Keep it checked out; the trader runs whatever is checked out.
- **Do not modify live trading/order/strategy logic** without explicit approval. Most tasks here are ops/observability/reporting.
- The headline backtest/paper numbers (e.g. **+35.20%**) are **inflated by broken-bracket artifacts** — the honest confirmed-fill edge is far lower. See §5.

---

## 1. Critical safety rules (read before touching anything)

1. **Paper only.** `config.LIVE_PAPER_MODE = True`, `config.LIVE_SYMBOL = "TQQQ"`. The trader connects to **7497**. Never enable live or touch 7496.
2. **Don't touch live trading logic** (`live/trader.py`, `live/broker.py`, `live/signals.py`, `live/state.py`, strategy/order code) without explicit user approval — the trader is usually **armed to auto-start**, so a bug can corrupt a live run.
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
| `ibkr-gateway-paper.timer` → `.service` | weekdays **08:00** | Start IB Gateway Paper headless (IBC+Xvfb), full re-auth from `~/.ibkr-paper.env`, open 7497. Runs `ops/start_ibkr_gateway.sh` (hard-gates `TradingMode=paper`+`7497`). | **enabled** |
| `monad-healthcheck.timer` → `.service` | weekdays **every 5 min 09:00–16:55** | `ops/healthcheck.sh` → `local_logs/healthcheck.json`. Read-only. | **enabled** |
| `monad-daily-export.timer` → `.service` | weekdays **16:15** | `ops/export_daily_data.py` → sanitized `data/live_runs/pi_export_<date>/`. | **enabled** |
| `monad-trader.timer` → `.service` | weekdays **09:22** | **Preflight-gated** trader autostart: `ExecStartPre=ops/preflight_trader_start.sh` (10 checks) → `ops/start_trader.sh --exec`. `Restart=no`. Logs to `local_logs/trader.log`. | **enabled** (timer); service is `static`, started only by the timer/preflight |

- IB Gateway does an **IBKR-forced nightly shutdown (~23:45 BST / 18:45 ET)** requiring full re-auth; the morning timer restarts it. There is **no mid-market auto-recovery** yet — the healthcheck *observes* but doesn't restart. If the Gateway dies mid-session, restart manually: `sudo systemctl start ibkr-gateway-paper.service`.
- The trader **preflight** refuses to start unless: on `development`, Gateway up, 7497 open, **7496 closed**, IBKR connects, **account flat**, no duplicate trader, `state.db` writable, `local_logs/` writable, no recent healthcheck failure. A failed preflight = no trade that day (safe).

---

## 7. `ops/` tooling (tracked, no secrets)

| Script | Purpose |
|---|---|
| `ops/status_check.sh` | One-shot human-readable status (system, gateway, trader, data freshness). Read-only. |
| `ops/healthcheck.sh` | Lightweight probe → `local_logs/healthcheck.json` (timer-driven). |
| `ops/healthcheck_ibkr.sh` | Deeper manual check incl. a live diagnostic connect. |
| `ops/start_ibkr_gateway.sh` | Headless IBC+Xvfb paper Gateway launcher (reads `~/.ibkr-paper.env`). |
| `ops/start_trader.sh` | Guarded trader starter. `--exec` mode = run trader in foreground (used by the service); no-arg = `systemctl start` (manual). |
| `ops/preflight_trader_start.sh` | The 10-check hard gate (logs `local_logs/trader_preflight.log`). |
| `ops/export_daily_data.py` | Sanitized export of `state.db` → `data/live_runs/pi_export_<date>/`. |
| `ops/archive_and_start_new_run.py` | Archive history + raw backup + write run marker (refuses if trader active or position open). |
| `ops/dashboard_smoke_test.sh` | Read-only dashboard server validation (endpoints, no-secret-leak, no DB mutation). |
| `ops/systemd/*` | Unit/timer templates (canonical source for the installed units). |
| `ops/README.md` | The ops runbook (install/enable, logs, manual trader start, export). |

---

## 8. Data model & dashboard

- **DB:** `live/state.db` (SQLite, gitignored). History tables: `trades`, `signal_history`, `monitor_events`. Current-state (single-row, overwritten each cycle): `position`, `monitor_status`, `signal_snapshot`, `account_snapshot`.
- **Dashboard:** `live/dashboard.py` (FastAPI, read-only for data; `init_db()` at import is an idempotent no-op). Run: `venv/bin/python -m uvicorn live.dashboard:app --host 127.0.0.1 --port 8000` (from repo root — it imports `src.analysis.run_window`). Endpoints: `GET /`, `GET /health`, `GET /api/ticker/{symbol}`.
- **Current-run view:** an optional gitignored marker `local_runtime/current_run.json` (written by `ops/archive_and_start_new_run.py`) sets `started_at`. The dashboard defaults to **`?view=current`** (history filtered to ≥ `started_at`), with **`all`** and **`archive`** toggles. Health/staleness/current-state are **never** filtered. No marker → behaves as before. Pure logic: `src/analysis/run_window.py` (tested: `tests/test_run_window.py`).
- **Archive:** `data/live_runs/archive_2026-06-18_pre_clean_run/` (sanitized). Raw DB backup is local-only at `local_backups/` (gitignored).

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

- **Waiting on the first clean paper run** (trader armed for 09:22 ET). After it: review confirmed-fill performance; expect modest, honest numbers.
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
