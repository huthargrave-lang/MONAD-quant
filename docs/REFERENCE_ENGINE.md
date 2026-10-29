# The reference engine — MONAD's long-only mean-reversion test bench

> This document describes the trading engine that ships with the research base: a
> long-only, regime-gated RSI/VWAP mean-reversion strategy with bracket exits, a universal
> parameter sweep, three backtest-fairness modes, and a **paper-only** Interactive Brokers
> trader. It is the **reference implementation** the research methodology was built on and
> proven against — the system whose claims the evidence graph first learned to test. The
> research base itself is described in the [README](../README.md); the research record in
> [`docs/research/README.md`](research/README.md).
>
> **Research status of the engine.** Its hourly timescale carries no demonstrated edge
> (`F13`/`F43`); its daily variant does not beat a static allocation on risk-adjusted terms
> (`D6`); and the execution-risk program (studies 16–69) catalogued the backtest↔live
> differences listed below. Those results are why it runs paper-only and why the headline
> numbers in older documents (`CLAUDE.md`, `docs/history/`) are optimization history, not
> current fact. For the current verdict run `venv/bin/python tools/ctx.py perf` and
> `ctx web --live`.

---

## What the engine is

A real system: data → features → signals → backtest → walk-forward → sweep → funnel →
paper broker, exercised end-to-end so that every research discipline in the base (leak-free
construction, bootstrap uncertainty, pre-registration, supersession) has a concrete subject.

**Engine principles:**

- **Long-only** — bear alpha is defined as *not losing money*, not chasing shorts
- **Regime-gated** — a 6-state MA classifier blocks entries in downtrends (backtest); hourly modes use adaptive Kelly instead
- **Tight exits** — bracket orders with fixed target/stop, typically 2:1–7:1 R:R
- **Zero commission** — targets US-brokerage ETFs (TQQQ, GDXU, QQQ) at $0/trade

### Strategy Modes

Switch modes by changing `ACTIVE_MODE` in `config.py`.

| Mode | Instrument | Style | Typical trades/mo |
|---|---|---|---|
| `BTC_DAILY` | BTC | Daily dip-buying, capital preservation | ~1–5 |
| `BTC_HOURLY` | BTC | Hourly mean-reversion, high frequency | ~130 |
| `QQQ_HOURLY` | QQQ | Hourly ETF mean-reversion | ~24 |
| `TQQQ_HOURLY` | TQQQ (3x) | Leveraged Nasdaq-100 | ~21 |
| `GDXU_HOURLY` | GDXU (3x) | Leveraged gold miners | ~27 |

> All backtest numbers should be generated fresh with `python main.py` or
> `python sweep.py TICKER --mode realistic`. Sweep holdout scores are
> selection-biased (`F2`). Detailed history lives in `CLAUDE.md` and `RESEARCH_WEB.md`.

### Execution Model

The backtest and live trading system target this execution rule:

```
1. Signal fires on completed bar N (RSI, MACD, VWAP from bar N's OHLCV)
2. Entry at the next tradeable price:
     Backtest: bar N+1's open
     Live:     pre-submission broker quote (fill_basis; actual fill is not persisted)
3. TP/SL bracket levels computed relative to that quote basis
4. Exit: target hit  /  stop hit  /  time limit (MAX_TRADE_BARS)
```

> **Known mismatch (studies #17/#20, F51/F54):** `compute_trade_returns()` currently begins
> bracket scanning on N+2, while the live bracket can execute during entry bar N+1.
> This affects 64.6% of paired entries. Hourly OHLC cannot identify the correction's
> return sign because 157 entry bars hit both target and stop; do not describe the
> current implementation as execution-identical or use a pessimistic N+1 replay as
> a fully resolved repair.

**Structural and known implementation differences:**

| Aspect | Backtest | Live |
|---|---|---|
| Entry basis | Deterministic (bar N+1 open) | Pre-submission quote; actual parent fill is not persisted |
| Exit monitoring | Bar-by-bar OHLC scan beginning N+2 (known mismatch) | Continuous IBKR bracket after parent fill |
| Same-bar ambiguity | Configurable (pessimistic in `realistic` mode) | Resolved by actual order execution |
| Time-exit fill | Last future bar's close | Market sell; reference price estimate if fill unavailable |
| Monitoring cadence | Every bar | Hourly cycle (:32 past each hour) |
| Position sizing | Kelly Criterion (capped, regime-scaled) | Fixed 10% of equity |

These differences mean that live performance will not exactly match backtest
results. The `realistic` backtest mode (2 bps slippage, pessimistic ambiguity,
rolling Kelly) is designed to be a conservative estimate.

### Backtest Fairness Modes

| Mode | Slippage | Same-bar ambiguity | Sizing |
|---|---|---|---|
| `optimistic` | 0 bps | Assumes target hit | Full-sample Kelly (lookahead) |
| **`realistic`** | **2 bps** | **Assumes stop hit** | **Rolling Kelly (no lookahead)** |
| `harsh` | 5 bps | Assumes stop hit | Rolling Kelly (no lookahead) |

Set via `BACKTEST_MODE` in `config.py` (default: `realistic`).

---

## Live Trading (paper)

The live system connects to **Interactive Brokers** (TWS or IB Gateway) and
runs as a long-lived process. APScheduler fires at :32 past each hour during
US market hours (9:32–15:32 ET, Mon–Fri).

**Status: paper-testing / validation.** The system runs on IBKR paper accounts.
It has not been validated on real money at scale — and per `D6`, the evidence
does not currently justify arming the active engine with real capital.

### Quick Start

```bash
# Dry run — compute signals, log actions, place no orders
python -m live.trader --dry-run --once

# Paper trading (default — port 7497)
python -m live.trader

# Override instrument
python -m live.trader --symbol GDXU

# PROHIBITED BY PROJECT POLICY: do not use --live / port 7496
```

### Key Design Decisions

**Fixed 10% sizing:** Live uses a fixed 10% position size, not Kelly. Backtest
Kelly is intentionally disabled in the live path — a small live trade sample
produces noisy Kelly estimates that could over-size positions. Fixed sizing is
the current conservative paper configuration, not a proof that the strategy or
deployment is safe.

**Entry basis:** TP/SL brackets are computed from the broker quote obtained
before submission (`fill_basis`), not from the signal bar's close. Despite the
name, `fill_basis` is not an execution price: the current entry path does not
wait for or persist the parent fill. The signal bar close is used only for qty
estimation. Consequently, the nominal 1% target / 0.5% stop are quote-relative:
at the parent buy-limit cap they are approximately +0.5% / −1.0% from fill,
and actual notional can differ from the bar-close plan. See Studies #52/#57
and F87/F92.

**Missing bracket evidence:** For a normal open local position, a flat broker
position plus unavailable child fill currently triggers immediate TP/SL
inference from the stored boundaries, closes local state, and can allow another
entry in the same cycle. It does not check whether the parent remains active,
was rejected, or ever executed. Legacy rows already marked `pending_close`
still use the retry/finalize branch. The local close is also not exactly once:
two connections can cache one position and each append a trade, while callers
cannot distinguish a winning close from an already-closed no-op. Worse, an old
cycle can select a newer re-entry row, record old exit economics against its
metadata, and delete it because close carries no expected lifecycle ID. See
Studies #53/#55/#56 and F88/F90/F91.

**Force-close quantity:** Software stop, software take-profit, and time exit
currently forward the originally requested local quantity after checking only
that broker quantity is nonzero. They do not cancel a partial parent remainder,
wait for child-cancel confirmation, derive the close from a fresh signed broker
position, or assert broker flat afterward. A partial or racing fill can therefore
overshoot into the opposite position. See Study #58 / F93.

**Force-close completion:** A nonempty close-order fill list is currently enough
to return success; filled quantity, remaining quantity, terminal status, and
post-close broker position are not checked, and one execution component is used
instead of VWAP. A ten-second timeout returns `None`, after which all three callers
still estimate PnL and delete local state. Four of nine archived time exits
explicitly reached that uncertainty boundary. See Study #59 / F94.

**Successor lifecycle handoff:** Force-close paths can evaluate a same-cycle
replacement signal after deleting old local state. The entry guard verifies net
broker position but not active old orders or terminal cancellation/completion.
The archive has 32 back-to-back application entries, including two about 14
seconds after explicit time-exit fill-unavailable warnings. This proves the
boundary was crossed, not that a late old fill occurred. See Study #60 / F95.

**Account/model scope:** Broker account summaries are reduced by tag without
account/currency filtering, TQQQ position lookup returns the first symbol match,
orders set no explicit destination, and local state stores no account identity.
This is dormant in a single-account login but order-dependent in linked/model
sessions; sanitized evidence intentionally cannot identify the current account
structure. See Study #61 / F96.

**Holding-clock compression:** `bar_count` increments once per trader invocation,
not once per unique completed bar. Seven of nine archived time exits reached
bar 10 through exactly five minute slots with two writes apiece; eight used
fewer than ten distinct slots. This proves premature local time-exit triggering,
not whether a longer hold would gain or lose. See Study #62 / F97.

**Exit PnL sources by path:**

| Exit path | PnL source | Accuracy |
|---|---|---|
| Retrieved bracket child fill | Retrieved exit execution; quote-derived entry basis | Entry not fill-confirmed |
| Inferred bracket close | Stored TP/SL boundary; quote-derived entry basis | Execution-unverified |
| Time-exit (any fill observed) | One market-close execution component; quote-derived entry basis | Neither full close nor VWAP confirmed |
| Time-exit (fill unavailable) | Reference-price exit; quote-derived entry basis | Approximate |
| Legacy pending close (unresolved) | Not recorded (0.0 placeholder) | Blocks until reconciled |

**Dry-run mode:** Computes signals and updates operational UI state (signal
snapshots, monitor status) but does **not** create fake trade-history records,
open positions, or place orders.

### Architecture

```
live/
├── trader.py   <- Scheduler + on_bar() loop (cycle logging, dry-run support)
├── signals.py  <- Wraps build_features() + generate_trades() on live bars
├── broker.py   <- IBKR bracket orders, fill reconciliation, price queries
└── state.py    <- SQLite position/trade log, pending_close state, fixed 10% sizing
```

---

## Read-Only Monitoring Dashboard

A separate FastAPI process provides a **read-only** dashboard over `live/state.db`.
It does **not** place orders and does not expose trade or config controls.

```bash
# Install live + dashboard deps
pip install -r requirements-live.txt

# Terminal 1: run trader
python -m live.trader

# Terminal 2: run dashboard (separate process, read-only)
uvicorn live.dashboard:app --host 0.0.0.0 --port 8080
```

### What the dashboard shows

- **Bot status** — health indicator, last cycle time, stale-age detection
- **Latest signal** — signal value, RSI, VWAP z-score, momentum/volume components
- **Current position** — three states:
  - *Open* — entry price, qty, bars held/remaining, TP/SL with distance, unrealized PnL
  - *Pending close* — warning banner, estimated exit price, blocked status
  - *Flat* — no open position, last trade summary
- **Mark price** — fallback chain: live broker → delayed IBKR → signal bar close → estimated exit (pending_close) → entry price. Source shown as a badge.
- **Recent trades** — closed trade table and Plotly charts (requires 3+ trades), filtered to production exit types only
- **Warnings & events** — monitor event log
- **Next scheduled run** — computed from APScheduler cron trigger

### Data freshness

Dashboard data is only as fresh as the latest trader cycle write to `state.db`.
There is no separate refresh path — if the trader stops cycling, dashboard data
goes stale (the stale-age indicator reflects this).

---

## Universal Sweep Tool

The sweep tool (`sweep.py`) finds optimal parameters for any equity or ETF on
hourly bars. It performs parameter search, holdout evaluation, robustness testing,
and optional post-sweep validation — designed to evaluate **live-worthiness**,
not just in-sample fit.

### Quick start

```bash
python sweep.py GDXU                        # Full sweep (2yr lookback)
python sweep.py TQQQ --mode realistic        # With backtest fairness mode
python sweep.py SOXL --start 2024-06-01      # Custom date range
python sweep.py LABU --min-stop 0.15         # Minimum stop floor
python sweep.py GDXU --apply                 # Auto-apply to config.py
```

### Parameter overrides

Pin one or more params to skip sweeping them:

```bash
# Lock target/stop/rsi/vwap — sweep only the remaining params
python sweep.py TQQQ --mode realistic --target 1.4 --stop 0.5 --rsi 80 --vwap 0.3

# Run a full sweep then validate top candidates across splits and modes
python sweep.py TQQQ --mode harsh --holdout-pct 20 --validate-best
```

| Flag | Effect |
|---|---|
| `--rsi N` | Force a single RSI oversold value instead of sweeping |
| `--vwap X` | Force a single VWAP z-score threshold |
| `--target X` | Force a single target % (e.g. `1.4` = 1.4%) |
| `--stop X` | Force a single stop % (e.g. `0.65` = 0.65%) |
| `--validate-best` | After sweep, cross-validate top candidates across multiple holdout splits and modes |

### Sweep phases

| Phase | What it does |
|---|---|
| 1a | Target/stop coarse grid (2:1 R:R) |
| 1b | R:R ratio variations at best target |
| 1c | VWAP z-score threshold |
| 1d | RSI oversold threshold |
| 2a–c | Fine-tune target, stop, RSI around Phase 1 best |
| 2d | MAX_TRADE_BARS sweep [8, 10, 12, 15, 20] on best params |
| 3 | Holdout evaluation — top 20 candidates on out-of-sample data |
| 4 | Perturbation robustness — jitter params to test stability |
| 5 | Final preset selection |

### Holdout evaluation (warm-context)

Holdout evaluation runs the backtest on the **full dataset** so that indicators
(moving averages, RSI, MACD) are fully warmed up, then filters trades to only
those occurring in the holdout period. This avoids the false "zero holdout
trades" problem that occurs when running on an isolated holdout slice where
indicators haven't had enough history to initialize.

If a candidate still produces zero holdout trades after warm-context evaluation,
it is displayed for diagnostics but penalized in ranking so it cannot
accidentally win preset selection.

### Interpreting the output

**Phase 3 — Holdout ranking:** Candidates are ranked by a composite key:
candidates with holdout trades rank above those without, then by holdout
live-score, then by train score as tiebreaker. The live-score function
penalizes high stop-hit ratio, negative months, ambiguous exits, too few
trades, spread-unsafe stops, and train→holdout degradation.

**Phase 4 — Robustness:** Each top candidate is tested with jittered params
(small perturbations to target, stop, RSI, VWAP). The average score and
percent-positive across neighbours measure whether the optimum is stable or
fragile.

**Phase 5 — Presets:** Four presets are selected: `best_overall` (highest
holdout score), `most_robust` (highest average perturbation score), `high_rr`
(highest risk/reward ratio), `high_trade_count` (most trades).

**Validation stage** (`--validate-best`): Cross-validates up to 3 top
candidates across multiple holdout splits (10%, 20%, 30%) and backtest modes
(realistic, harsh). Reports per-candidate averages and flags split-sensitive
or mode-sensitive results. "Best raw performer" maximizes average return;
"best robust performer" maximizes average score with fewest zero-trade cells.

### Recommended workflow

1. Run `python sweep.py TICKER` — review the Phase 5 presets
2. Use `--validate-best` to cross-validate the top candidates automatically
3. Move the top 1–2 presets to paper trading before live deployment
4. Results are saved to `sweep_results_TICKER.json` and `experiments.jsonl`

### Output files

- **`sweep_results_TICKER.json`** — full results: params, train/holdout metrics, robustness scores, presets, validation (if `--validate-best`)
- **`experiments.jsonl`** — one line per sweep run (append-only log)

---

## How It Works

```
Price data (yfinance)
        |
        v
Signal layer:
  +-- RSI dip  +  MACD histogram inflection  -> momentum_signal
  +-- VWAP z-score deviation                 -> volume_signal
        |
        v
Regime gate (6-state MA slope classifier, daily/backtest modes):
  STRONG_BULL / BULL / STALLING / RECOVERING / BEAR / STRONG_BEAR
  -> blocks entries in downtrends, scales position size by conviction
        |
        v
Position sizing:
  Backtest: Kelly Criterion x regime_mult x ADX_mult (capped 20-30%)
  Live:     fixed 10% of equity
        |
        v
Entry at next tradeable price -> bracket order (TP + SL + time limit)
```

---

---

## Deployment

### Branches

- **`development`** — the canonical running branch and the GitHub default. All
  reviewed work lands here; it is what the Pi runs.
- **`pi-ops-automation`** — prior deploy branch, now folded into `development`.
- **`main`** — legacy/divergent; not used for deployment.

The systemd preflight gate (`ops/preflight_trader_start.sh`) hard-checks that the
working tree is on `development` before the paper trader will start, so the trader
can never run from an unreviewed branch.

### Raspberry Pi Deployment

The Pi runs the **paper** trader from `development`. Stay on that branch when
updating:

```bash
git checkout development && git pull        # the only branch the preflight allows

chmod +x deploy/setup-pi.sh
./deploy/setup-pi.sh
./deploy/smoke-test.sh

sudo systemctl start monad-trader
sudo systemctl status monad-trader
journalctl -u monad-trader -f
```


---

## Known limitations (engine-specific)

These are properties of the reference engine, recorded so nobody rediscovers them:

- **No demonstrated edge at the frequency it trades.** Full-session, leak-free backtests and
  live paper reconcile to flat at the hourly frequency (`F13`/`F43`); the daily engine does
  not beat a static allocation risk-adjusted (`D6`). The honest product recommendation from
  that program is a static, conservatively-weighted mix — read with `F46`'s regime qualifiers.
- **Paper-testing only.** The live system has not been validated on real money, and per
  `D6` the evidence does not justify arming the active engine with real capital.
- **Sweep holdout scores are selection-biased.** A sweep winner is the best-of-many on its
  holdout — use `--validate-best`, the trial ledger, and `ctx perf`, not Phase-3 numbers alone
  (`F2`).
- **Pending close reconciliation** depends on IBKR making fill data available on subsequent
  cycles. If IBKR never surfaces the fill (e.g. a prolonged outage), the position stays
  blocked until manual intervention.
- **Dashboard mark price / unrealized PnL** accuracy depends on the available price source.
  The fallback chain (live → delayed → bar_close → estimated → entry) means the displayed
  price may be stale or approximate.
- **Hourly monitoring cadence** means bracket exits that fill between cycles are detected on
  the next cycle, not immediately. PnL is still computed from actual fill data when available.
- **Backtest-to-live gap** is structural: live slippage, broker fill timing, spread costs,
  and execution delays differ from backtest assumptions. The `realistic` mode is a
  conservative estimate, not a prediction. The execution-risk studies (`F47`–`F104`) are the
  quantified version of this list.
- **BTC modes** require crypto exchange infrastructure with fee tiers that erode returns at
  retail rates. ETF modes are preferred for paper deployment.

---

## Why ETFs Over BTC?

BTC Hourly produces higher gross returns but trades on a crypto CEX with fees
that erode 40–60% of returns at retail rates. ETFs at US brokerages have zero
commission — gross return equals net return.

| | BTC Hourly (retail fees) | TQQQ Hourly | GDXU Hourly |
|---|---|---|---|
| Commission | 0.1% round-trip | $0 | $0 |
| Monthly fee drag | ~1.5%/mo | $0 | $0 |
| Custody | Exchange counterparty risk | SIPC-insured | SIPC-insured |
| Tax reporting | Complex crypto basis | Standard 1099-B | Standard 1099-B |
| Operating hours | 24/7 | Market hours only | Market hours only |

---

