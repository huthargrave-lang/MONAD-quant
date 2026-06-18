# MONAD-quant — Model Phase Recommendations (Observability)

*Prepared 2026-06-18, branch `pi-ops-automation`. Server/dashboard testing + safe
model-observability planning only. No trading logic, order logic, thresholds, or
account settings were changed. The paper trader is armed to auto-start at 09:22 ET
today from this branch — so nothing in the live trader code path was touched.*

---

## 1. Server / dashboard test results (PHASE 2)

Ran `uvicorn live.dashboard:app` bound to `127.0.0.1`, exercised every endpoint,
with the Gateway + trader **stopped** and `state.db` **stale** (worst-case).

| Check | Result |
|---|---|
| Server starts without crashing | ✅ up in ~3 s |
| `GET /health` | ✅ `{"status":"ok",...}` |
| `GET /` (dashboard HTML) | ✅ 200, ~124 KB, title "MONAD Bot Monitor" |
| `GET /api/ticker/{symbol}` | ✅ 200 (`TQQQ` 77.54, yfinance_fast) — no 429 this run |
| No secrets / account IDs in HTML or JSON | ✅ clean |
| No raw `.db` served over HTTP | ✅ no static/file routes |
| Works while Gateway/trader stopped | ✅ |
| Works with stale `state.db` | ✅ |
| Handles no-open-position state | ✅ (position=0 rendered fine) |
| **Dashboard mutates `state.db`?** | ✅ **No** — sha256 identical before/after |

**Endpoints:** `GET /health`, `GET /` (dashboard), `GET /api/ticker/{symbol}`.
**Data source:** `live/state.db` only (read-only for data). Note: importing the
module calls `state.init_db()` once — idempotent `CREATE TABLE IF NOT EXISTS` /
`ALTER`; provably a no-op here (sha256 unchanged).
**Reusable test:** `ops/dashboard_smoke_test.sh` (read-only; run on the Pi terminal).

## 2. Dashboard ↔ source consistency (PHASE 3)

The dashboard is **internally consistent** — its displayed numbers match an
independent recompute from `state.db` exactly:

| Metric | Dashboard | Independent recompute | Match |
|---|---|---|---|
| Trades (PROD) | 62 | 62 | ✅ |
| Win rate | 58.06% | 58.06% | ✅ |
| Compounded return | +35.20% | +35.20% | ✅ |
| Open positions | 0 | 0 | ✅ |

**But two by-design reporting gaps (not bugs):**

1. **Dashboard vs alert path disagree.** Dashboard = **compounded**, **PROD-filtered**
   (62 trades → +35.20%). The trader's alert path (`state.get_trade_summary`) =
   **simple-sum**, **all 65 trades** → +31.09%, WR 56.92%. They will never match.
   → *Unify on one shared performance function (compounded, one trade population).*
2. **Estimated/inferred fills silently inflate the headline.** The +35.20% PROD figure
   still includes **9 `time_exit` broken-bracket artifacts (~+27 pp)** and **6 `target_hit`
   that were inferred** (9 "inferred" monitor events). It excludes the 2 `estimated_close`
   but flags none of the rest. → *Add a fill-quality note + a confirmed-only view.*

## 3. What can safely be changed NOW (no trading-behavior change)

These are observability/reporting only and do **not** alter any trading decision:

- **Unify the performance calc** into one shared util (`src/analysis/performance.py`)
  used by both the dashboard and the alert summary. Pure refactor of *reporting*.
- **Benchmark comparison** on the dashboard (Bot vs QQQ/SPY/TQQQ, same window,
  compounded) — the plan from the previous session (currently paused). Read-only.
- **Fill-quality note** in the dashboard summary ("includes N inferred / N estimated").
- **`ops/dashboard_smoke_test.sh`** (added this session) — reusable read-only validation.
- A **standalone shadow evaluator** (separate script, reads data, places no orders).

## 4. What should WAIT until after one clean week (or until the trader is stopped)

Anything that edits the live trader code path (`live/trader.py`, `live/signals.py`,
`live/state.py`, `live/broker.py`) must wait — the trader is armed to run today from
this branch, and a bug in instrumentation could corrupt the run.

- **Model-version logging** (item below) — needs a `state.py`/schema touch.
- **Signal-reason logging** — needs `signals.py`/`trader.py` touch.
- **No-trade reason logging** — needs `trader.py` touch.
- **Data-source reliability guard** wired into the live loop — needs `signals.py` touch.

Do these on a separate branch, test, and merge **after** today's clean run (or while
the trader is stopped), never the morning of a run.

## 5. Model observability that is currently MISSING

1. **Model/rule version stamping.** No `model_version` is recorded on signals or
   trades, so we can't attribute results to a config generation. *Plan:* add a
   `MODEL_VERSION` constant in `config.py`; record it in `signal_history` and `trades`
   (additive `ALTER TABLE ... ADD COLUMN model_version TEXT`, matching the existing
   migration pattern in `state.init_db()`). Until schema changes, log it in a
   `monitor_events` row at trader startup.
2. **Signal reasoning.** `signal_history` stores `signal/rsi/vwap_zscore/momentum/volume`
   but no **decision** (enter/hold/exit/no-trade), **reason codes**, or **data-freshness**
   flag. *Plan:* extend the signal snapshot with `decision`, `reason`, `data_source`
   (`live`/`degraded`), `bar_age_min`.
3. **No-trade reasons.** The trader returns labels (`no_signal`, `entry_blocked_desync`,
   `entry_blocked_broker_unverified`, `qty_too_small`, `signal_error`) but they're not
   surfaced as first-class, queryable "why we didn't trade" records for analysis.
4. **Fill provenance.** No `fill_source` column (`actual`/`inferred`/`estimated`) — the
   single most valuable missing field for honest performance (see §2.2).
5. **Data-source health history.** yfinance 429s / stale bars / delayed prices aren't
   recorded as a time series (only ad-hoc in `local_logs/healthcheck.json`).

## 6. Recommended next model experiments — SHADOW MODE ONLY

Run these as a **non-trading offline evaluator** that replays bars and records what a
candidate config *would* have done. It must place no orders and write only to a local
analysis file or a separate shadow table. Questions to answer:

- **Confirmed-fill edge:** what is the compounded return using only `bracket_exit + stop_hit`
  (drop time_exit + inferred target_hit)? That is the honest baseline.
- **Software-TP impact:** with the new software take-profit capping winners at +1%, how
  much lower (and how much more honest) is the return vs the old artifact-inflated number?
- **Threshold sensitivity (shadow only):** would RSI/VWAP threshold tweaks have changed
  entries this week? Record counts, never trade them.
- **Benchmark-relative:** bot vs QQQ/SPY/TQQQ over the *same* window — is there alpha, or
  is it leveraged beta?

## 7. Frozen for now (PHASE 5 — do NOT change)

entry thresholds · stop-loss / take-profit levels · ticker universe · trading frequency ·
order submission logic · live/paper account settings. All unchanged.

---

### Suggested sequence
1. **Today:** let the armed paper run happen; collect a clean day.
2. **After the run (trader stopped):** add `fill_source` + `model_version` columns
   (additive migration), unify the performance calc, ship the benchmark comparison.
3. **Then:** build the shadow evaluator and run the §6 experiments offline.
4. Only after shadow evidence: consider any real strategy change (separate review).
