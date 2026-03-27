# MONAD Quant

> Mean-reversion strategy engine for leveraged ETFs and BTC. Long-only,
> regime-gated, bracket-exit. Currently in paper-testing / validation.

---

## What This Is

MONAD Quant is a long-only engine that trades RSI dips in confirmed uptrends.
It sits flat during bear markets and buys mean-reversion setups during bull
regimes. The design targets consistent monthly income with low drawdown —
closer to a high-yield bond ETF than a growth strategy.

- **Long-only** — bear alpha is defined as *not losing money*, not chasing shorts
- **Regime-gated** — a 6-state MA classifier blocks entries in downtrends (backtest); hourly modes use adaptive Kelly instead
- **Tight exits** — bracket orders with fixed target/stop, typically 2:1–7:1 R:R
- **Zero commission** — targets US-brokerage ETFs (TQQQ, GDXU, QQQ) at $0/trade

---

## Strategy Modes

Switch modes by changing `ACTIVE_MODE` in `config.py`.

| Mode | Instrument | Style | Typical trades/mo |
|---|---|---|---|
| `BTC_DAILY` | BTC | Daily dip-buying, capital preservation | ~1–5 |
| `BTC_HOURLY` | BTC | Hourly mean-reversion, high frequency | ~130 |
| `QQQ_HOURLY` | QQQ | Hourly ETF mean-reversion | ~24 |
| `TQQQ_HOURLY` | TQQQ (3x) | Leveraged Nasdaq-100 | ~21 |
| `GDXU_HOURLY` | GDXU (3x) | Leveraged gold miners | ~27 |

> All backtest numbers should be generated fresh with `python main.py` or
> `python sweep.py TICKER --mode realistic`. See CLAUDE.md for detailed
> historical parameter sweep results.

---

## Execution Model

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

---

## Backtest Fairness Modes

| Mode | Slippage | Same-bar ambiguity | Sizing |
|---|---|---|---|
| `optimistic` | 0 bps | Assumes target hit | Full-sample Kelly (lookahead) |
| **`realistic`** | **2 bps** | **Assumes stop hit** | **Rolling Kelly (no lookahead)** |
| `harsh` | 5 bps | Assumes stop hit | Rolling Kelly (no lookahead) |

Set via `BACKTEST_MODE` in `config.py` (default: `realistic`).

---

## Live Trading

The live system connects to **Interactive Brokers** (TWS or IB Gateway) and
runs as a long-lived process. APScheduler fires at :32 past each hour during
US market hours (9:32–15:32 ET, Mon–Fri).

**Status: paper-testing / validation.** The system runs on IBKR paper accounts.
It has not been validated on real money at scale.

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

# Dashboard
uvicorn live.dashboard:app --port 8080

# Tests
python -m pytest tests/ -v
```

### Raspberry Pi Deployment

```bash
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
├── config_modules/
│   ├── base.py             <- Shared risk/sizing/backtest settings
│   └── live.py             <- IBKR connection, dry-run flag, bootstrap stats
├── main.py                 <- Entry point (backtest)
├── sweep.py                <- Universal parameter sweep tool
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
│       └── runner.py       <- Equity curve, monthly P&L, diagnostics
├── tests/
│   ├── test_state.py       <- State DB + config tests (16 tests)
│   ├── test_execution_model.py <- Execution model + regression tests (20 tests)
│   └── test_dashboard.py   <- Dashboard route + rendering tests (6 tests)
└── sweep_results_*.json    <- Saved sweep results per ticker
```

---

## Known Limitations

- **Paper-testing phase.** The live system has not been validated on real money at scale. Backtest results are not a guarantee of live performance.
- **Pending close reconciliation** depends on IBKR making fill data available on subsequent cycles. If IBKR never surfaces the fill (e.g., prolonged outage), the position stays blocked until manual intervention.
- **Dashboard mark price / unrealized PnL** accuracy depends on the available price source. The fallback chain (live → delayed → bar_close → estimated → entry) means the displayed price may be stale or approximate.
- **Hourly monitoring cadence** means bracket exits that fill between cycles are detected on the next cycle, not immediately. PnL is still computed from actual fill data when available.
- **Backtest-to-live gap** is unavoidable: live slippage, broker fill timing, spread costs, and execution delays will differ from backtest assumptions. The `realistic` mode is a conservative estimate, not a prediction.
- **BTC modes** require crypto exchange infrastructure with fee tiers that erode returns at retail rates. ETF modes are preferred for retail deployment.

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
