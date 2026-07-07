# MONAD Quant

> An open-source **research substrate for quantitative finance**: a queryable
> **evidence graph** (Context Kit), a **validation funnel**, and a growing,
> **adversarially-verified research library** — fifteen studies and counting —
> with a full trading stack (signals → backtest → sweep → live paper broker)
> as the reference implementation that exercises it end-to-end.
>
> Direction: **[VISION.md](VISION.md)** · graph model: **[SCHEMA.md](SCHEMA.md)** ·
> research compendium: **[docs/research/](docs/research/README.md)** ·
> agent entry point: **[AGENT_INDEX.md](AGENT_INDEX.md)**

---

## Why this exists

Most public quant repos publish a backtest. This repo publishes the **scrutiny**:
every claim it has ever made is a node in a versioned knowledge graph
([`RESEARCH_WEB.md`](RESEARCH_WEB.md), 134+ nodes) with typed evidence links —
and when a claim dies under testing, it is **superseded with a tombstone**, never
silently edited. The headline result of that discipline is itself the best
advertisement for it: this project's own early Sharpe-25 backtest was traced to a
**data-sampling artifact**, proven wrong, and replaced by one of the most carefully
verified negative results you will find in an open repo.

Negative results, rigorously proven, are quant knowledge — usually the expensive
kind that funds keep private. Here they are free:

**The library so far** (each finding links to a deterministic, re-runnable study
tool, a standalone writeup, and its graph nodes — see the
[fifteen-study compendium](docs/research/README.md)):

| What we established | Why it matters beyond this repo | Nodes |
|---|---|---|
| A Sharpe-25 intraday backtest was a **morning-only data-sampling artifact**; the "edge" tracked bar-sampling frequency, not instrument or time-of-day | Validate data representativeness before believing *any* intraday edge | F13/F14 |
| Daily mean-reversion (lag-1 autocorrelation) is **real and robust over 26 years** — but naive t-stats overstate its significance ~3× | Use block-bootstrap CIs, not t-stats, on autocorrelated returns | F16/F18 |
| The **exit, not the entry, is the dominant lever**: a fixed %-stop destroys a mean-reversion edge that a multi-day horizon exit recovers | Stop placement inside intrabar noise silently converts edge to churn | F17/F19/F7 |
| A **real signal ≠ a tradable edge**: active daily MR is provably *equivalent-or-worse* vs a static blend (TOST, evidence-of-absence down to ~0.3 Sharpe over 26yr) | The benchmark that kills most timing strategies is a trivial static mix, not buy&hold | F22/F25/F34/F35 |
| Active timing's one honest contribution is **crisis drawdown reduction** — paid for in calm-market under-participation (Sharpe-neutral) | "Low drawdown" claims need a static-blend control | F36/F37 |
| The static 60/40 is **hard to improve reliably**: third sleeves, vol-targeting, and risk parity all fail fair paired bootstraps; gold fails clean OOS | Most "improvements" are regime bets or multiple-comparisons artifacts | F38/F39/F40 |
| Forward-looking (2026 yields), a 60/40 returns ~5–6%/yr at **Sharpe ~0.5** — half its bond-bull-flattered history; the goal-optimal mix is **more conservative than 60/40** | Historical 60/40 stats are a regime, not an expectation | F41/F42 |
| Across the income-ETF universe, **high yield ≠ low drawdown** — nothing beats the 60/40 on both; the one structural escape (held-to-maturity ladder) has a **definitional, nominal-only** 0% drawdown | Distribution yield is not return; amortized-cost accounting is not safety | F44/F45 |
| Everything above is **correlation-regime-conditional**: bonds hedged stocks in only ~22 of the last 64 years; in the 1965–81 inflation regime every bond-heavy mix lost purchasing power for a decade, and the conservative tilt's drawdown edge *inverts* in real terms | The stock-bond hedge is the exception, not the rule — and it flipped again in 2022 | F46 |
| There is **no escape from the regime bet by composition**: a marked-to-market TIPS sleeve is duration-shortening in disguise (indistinguishable from a duration-matched nominal sleeve), and no fixed cash/bond blend or barbell dominates both correlation regimes — a 50/50 blend *halves* the worst-case bet, nothing removes it | Test any "inflation hedge" against a duration-matched control before crediting the label | F48/F49 |
| Sweep/holdout winners are **selection-biased best-of-many**; live-vs-backtest gaps decompose into measurable causes (bar frequency dominated here) | Reconcile live to backtest quantitatively before blaming execution | F2/F28/F43 |

## The methodology (what makes the library trustworthy)

Every study in [`docs/research/`](docs/research/README.md) follows the same
disciplines, enforced in code rather than promised in prose:

- **Deterministic, re-runnable artifacts** — each study is a committed CLI tool
  (`tools/*_study.py`, seed=0, cached fetches, byte-reproducible output), not a notebook.
- **Leak-free by construction** — entries/weights use only lagged information;
  windows verified byte-identical to truncated recomputation.
- **Uncertainty on every claim** — paired block bootstrap CIs (shared, unit-tested
  module: [`src/backtest/uncertainty.py`](src/backtest/uncertainty.py)); family-wise
  corrections on any "clearly positive" result.
- **Pre-registration** — pass criteria stated in the tool's docstring before the
  numbers are computed.
- **Adversarial verification** — every study is attacked by an independent
  multi-lens skeptic panel (data construction, math, statistics, interpretation)
  that re-runs the code and tries to refute the verdict; forced corrections are
  **folded into the tool, not caveated around**.
- **Supersession, not revisionism** — overturned claims are tombstoned in the graph
  with a reason (`inverted`, `reversed`, …) and every citation is re-pointed;
  `ctx web --lint` fails the build on stale cites.

---

## The Context Kit — a knowledge graph you can query

The **Context Kit** is a portable, stdlib-only layer that agents (and humans) query
instead of reading the whole codebase. It unifies:

- **Ideas** — findings, hypotheses, experiments, decisions in `RESEARCH_WEB.md`
- **Code** — modules, symbols, config keys, test coverage (auto-extracted)
- **Bridges** — which finding lives in which symbol, guarded by which test

**Start here:** [`AGENT_INDEX.md`](AGENT_INDEX.md) · [`CONTEXT_KIT.md`](CONTEXT_KIT.md) · schema: [`SCHEMA.md`](SCHEMA.md)

```bash
# Orient to a task (files to read + commands to run)
venv/bin/python tools/ctx.py route "fix dashboard stale mark price"

# Walk the research graph
venv/bin/python tools/ctx.py web F46        # read a finding + its evidence links
venv/bin/python tools/ctx.py why D6         # provenance: why believe this decision?
venv/bin/python tools/ctx.py contradicts F15  # dispute/supersession state

# Blast radius before editing
venv/bin/python tools/ctx.py impact live/broker.py
venv/bin/python tools/ctx.py can_edit config.py   # DENY on live/strategy paths

# Honest performance state (never trust stale headline numbers)
venv/bin/python tools/ctx.py perf

# Capture a new finding (dry-run by default; --commit to write)
venv/bin/python tools/note.py add --kind F --title "..." --body "..."
```

### Interactive context map (browser)

Serve the unified idea + code graph as a read-only web app:

```bash
venv/bin/python tools/ctx.py serve --host 127.0.0.1 --port 8001
# → http://127.0.0.1:8001/
```

The map is a self-contained D3/SVG page (no backend credentials):

- **Dark 3D layout** — deterministic depth, shift-drag to orbit, click a node for a slow cruise
- **Explore drawer** — kind-specific prompts (evidence chain, config impact, area brief, …) with copy-to-clipboard
- **Search / fit / flat** — filter nodes, frame selection + one-hop neighbors, reset camera
- **Fresh on every load** — rebuilt from the manifest each request

On the Pi this runs as a separate read-only service on `:8001`, deliberately isolated
from the trading dashboard. See `OPERATIONS.md` and `deploy/monad-ctxweb.service`.

Static export (no server):

```bash
venv/bin/python tools/ctx.py graph --html > context_map.html
```

---

## The reference implementation — a full trading stack

The research substrate is exercised end-to-end by a real system: a long-only
mean-reversion engine (RSI dips in confirmed uptrends, regime-gated, bracket
exits) with a universal parameter sweep, three backtest-fairness modes, and a
live paper trader on Interactive Brokers. It is the **testbed the library's
findings were proven on** — including the finding that its own hourly timescale
carries no edge (`F13`/`F43`), which is why it runs paper-only and the honest
product recommendation is a static allocation (`D6`).

> **Do not trust headline Sharpe/return numbers in older docs** — they came from
> optimistic-mode backtests on morning-only data. Run `venv/bin/python tools/ctx.py perf`
> and `ctx web --live` for the current verdict.

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

The backtest and live trading system share a unified execution rule:

```
1. Signal fires on completed bar N (RSI, MACD, VWAP from bar N's OHLCV)
2. Entry at the next tradeable price:
     Backtest: bar N+1's open
     Live:     broker market price at order time (fill_basis)
3. TP/SL bracket levels computed relative to the entry fill price
4. Exit: target hit  /  stop hit  /  time limit (MAX_TRADE_BARS)
```

**Remaining structural differences** (inherent to backtest vs live):

| Aspect | Backtest | Live |
|---|---|---|
| Fill price | Deterministic (bar N+1 open) | Market price ± spread/slippage |
| Exit monitoring | Bar-by-bar OHLC scan | Continuous IBKR bracket order |
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

# REAL MONEY — requires explicit --live flag (port 7496)
python -m live.trader --live
```

### Key Design Decisions

**Fixed 10% sizing:** Live uses a fixed 10% position size, not Kelly. Backtest
Kelly is intentionally disabled in the live path — a small live trade sample
produces noisy Kelly estimates that could over-size positions. Fixed sizing
is safe until the live trade log has enough data for reliable estimates.

**Entry basis:** TP/SL brackets are computed from the broker's live market price
at order time (`fill_basis`), not from the signal bar's close. The signal bar
close is used only for qty estimation.

**Pending close / unresolved exits:** When a bracket exit is detected but IBKR
fill data is unavailable (connection gap, session restart), the position is
marked `pending_close` — it stays in the database and **blocks new entries**
until reconciliation succeeds. On each subsequent cycle, the bot retries
`get_bracket_fill()`. Only when actual fill data is found does the trade
finalize with real exit price, real return, and real exit type. Estimated
prices may appear in the dashboard UI but are never recorded as final PnL.

**Exit PnL sources by path:**

| Exit path | PnL source | Accuracy |
|---|---|---|
| Bracket target/stop | Actual IBKR fill price | Exact |
| Time-exit (fill confirmed) | Market sell fill price | Exact |
| Time-exit (fill unavailable) | Reference price estimate | Approximate |
| Pending close (unresolved) | Not recorded (0.0 placeholder) | Blocks until reconciled |

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

## Setup

```bash
git clone <repo-url>
cd MONAD-quant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

For live trading: `pip install -r requirements-live.txt`
For Raspberry Pi: `pip install -r requirements-pi.txt`

## Run

```bash
# Reproduce any research study (deterministic, seed=0)
venv/bin/python tools/bond_ladder_study.py
venv/bin/python tools/correlation_regime_study.py --selfcheck

# Standard backtest
python main.py

# Walk-forward optimizer (daily mode only)
python main.py --mode=walk-forward

# Override date range
python main.py --start 2023-01-01 --end 2023-12-31

# Parameter sweep
python sweep.py GDXU
python sweep.py SOXL --start 2024-06-01 --mode realistic
python sweep.py TQQQ --mode harsh --validate-best

# Live trading
python -m live.trader --dry-run --once    # verify signals
python -m live.trader                      # paper mode
python -m live.trader --live --symbol TQQQ # real money

# Context map (read-only, separate from trading dashboard)
venv/bin/python tools/ctx.py serve --port 8001

# Tests (unittest — NOT pytest)
python -m unittest discover -s tests
```

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

## Project Structure

```
MONAD-quant/
├── config.py               <- All params; change ACTIVE_MODE here
├── context_map.json        <- Context Kit manifest (areas, routing, idea↔code bridges)
├── RESEARCH_WEB.md         <- Research idea web (findings, experiments, decisions)
├── AGENT_INDEX.md          <- Agent router — start here for navigation
├── CONTEXT_KIT.md          <- Context Kit design + portability guide
├── SCHEMA.md               <- Canonical context-web schema
├── VISION.md               <- Public vision + Stage 0–4 roadmap
├── config_modules/
│   ├── base.py             <- Shared risk/sizing/backtest settings
│   └── live.py             <- IBKR connection, dry-run flag, bootstrap stats
├── main.py                 <- Entry point (backtest)
├── sweep.py                <- Universal parameter sweep tool
├── tools/
│   ├── ctx.py              <- Context Kit CLI (query, graph, serve, guard)
│   ├── note.py             <- Append/supersede research-web nodes
│   └── *_study.py          <- The fifteen deterministic research-study tools
├── docs/research/          <- Fifteen-study research program writeups + compendium
├── experiments.jsonl        <- Experiment log (one JSON line per sweep run)
├── live/
│   ├── trader.py           <- Scheduler + on_bar() loop, pending_close retry
│   ├── signals.py          <- Real-time signal computation
│   ├── broker.py           <- IBKR bracket orders + fill reconciliation
│   ├── state.py            <- SQLite position/trade state, pending_close management
│   ├── dashboard.py        <- FastAPI read-only dashboard
│   └── templates/
│       └── dashboard.html  <- Dashboard UI template
├── deploy/
│   ├── setup-pi.sh         <- Raspberry Pi deployment script
│   ├── smoke-test.sh       <- Post-deployment verification
│   ├── monad-trader.service <- systemd service template
│   ├── monad-ctxweb.service <- systemd unit for ctx serve (:8001)
│   └── healthcheck.sh      <- Health check for monitoring
├── src/
│   ├── data/               <- yfinance + Alpha Vantage fetchers
│   ├── signals/
│   │   ├── momentum.py     <- RSI, MACD, 6-state regime classifier
│   │   ├── volume.py       <- VWAP z-score
│   │   └── volatility.py   <- ATR, Bollinger Bands, ADX
│   ├── strategy/
│   │   ├── engine.py       <- Signal orchestration + trade simulation
│   │   └── sizing.py       <- Fractional Kelly calculator (backtest)
│   └── backtest/
│       ├── runner.py       <- Equity curve, monthly P&L, diagnostics
│       └── uncertainty.py  <- Block-bootstrap CIs, win-rate posteriors, MC bands
├── tests/
│   ├── test_context_map.py <- Manifest drift guards
│   ├── test_research_web.py <- Idea-web + graph HTML template guards
│   ├── test_state.py       <- State DB + config tests
│   ├── test_execution_model.py <- Execution model + regression tests
│   └── test_dashboard.py   <- Dashboard route + rendering tests
└── sweep_results_*.json    <- Saved sweep results per ticker
```

---

## Honest Disclosures

The library's credibility rests on saying these plainly:

- **The active engine has no demonstrated edge.** Full-session, leak-free backtests
  and live paper reconcile to flat at the hourly frequency it trades (`F13`/`F43`);
  the active daily engine does not beat a static allocation risk-adjusted (`D6`).
  The honest product recommendation is a static, conservatively-weighted mix —
  read with `F46`'s regime qualifiers.
- **Paper-testing phase.** The live system has not been validated on real money at
  scale. Backtest results are not a guarantee of live performance.
- **Sweep holdout scores are selection-biased.** A sweep winner is the best-of-many
  on its holdout — use `--validate-best` and `ctx perf`, not Phase-3 numbers alone.
- **Pending close reconciliation** depends on IBKR making fill data available on
  subsequent cycles. If IBKR never surfaces the fill (e.g., prolonged outage), the
  position stays blocked until manual intervention.
- **Dashboard mark price / unrealized PnL** accuracy depends on the available price
  source. The fallback chain (live → delayed → bar_close → estimated → entry) means
  the displayed price may be stale or approximate.
- **Hourly monitoring cadence** means bracket exits that fill between cycles are
  detected on the next cycle, not immediately. PnL is still computed from actual
  fill data when available.
- **Backtest-to-live gap** is unavoidable: live slippage, broker fill timing, spread
  costs, and execution delays will differ from backtest assumptions. The `realistic`
  mode is a conservative estimate, not a prediction.
- **BTC modes** require crypto exchange infrastructure with fee tiers that erode
  returns at retail rates. ETF modes are preferred for retail deployment.

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

## License

(c) 2026 Monad Industries

This project is licensed under the MIT License.
