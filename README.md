# MONAD Quant

> Mean-reversion strategy engine for leveraged ETFs and BTC. Designed for
> consistent monthly income with near-zero drawdown — a high-yield bond ETF
> alternative, not a growth strategy.

---

## What This Is

MONAD Quant is a long-only, capital-preservation engine that trades RSI dips
in confirmed uptrends. It sits flat during bear markets and buys mean-reversion
setups during bull regimes.

- **Long-only** — bear alpha is defined as *not losing money*, not chasing shorts
- **Regime-gated** — a 6-state MA classifier blocks entries in downtrends
- **Tight exits** — bracket orders with fixed target/stop, typically 2:1–7:1 R:R
- **Zero commission** — targets US-brokerage ETFs (TQQQ, GDXU, QQQ) at $0/trade

---

## Strategy Modes

Switch modes by changing `ACTIVE_MODE` in `config.py` — one line.

| Mode | Instrument | Style | Typical trades/mo |
|---|---|---|---|
| `BTC_DAILY` | BTC | Daily dip-buying, capital preservation | ~1–5 |
| `BTC_HOURLY` | BTC | Hourly mean-reversion, high frequency | ~130 |
| `QQQ_HOURLY` | QQQ | Hourly ETF mean-reversion | ~24 |
| `TQQQ_HOURLY` | TQQQ (3x) | Leveraged Nasdaq-100 | ~21 |
| `GDXU_HOURLY` | GDXU (3x) | Leveraged gold miners | ~27 |

> **Important:** All backtest results should be generated fresh with
> `python main.py` or `python sweep.py TICKER --mode realistic`. See
> CLAUDE.md for detailed historical performance data and parameter sweep results.

---

## Execution Model

The backtest and live trading system share a unified execution rule:

```
1. Signal fires on completed bar N (RSI, MACD, VWAP from bar N's OHLCV)
2. Entry at the next tradeable price:
     Backtest: bar N+1's open
     Live:     broker market price at order time
3. TP/SL bracket levels computed relative to the entry fill price
4. Exit: target hit  /  stop hit  /  time limit
```

**Remaining structural differences** (inherent to backtest vs live):

| Aspect | Backtest | Live |
|---|---|---|
| Fill price | Deterministic (bar N+1 open) | Market price ± spread |
| Exit monitoring | Bar-by-bar OHLC scan | Continuous IBKR bracket |
| Same-bar ambiguity | Configurable (pessimistic in `realistic` mode) | Resolved by order execution |
| Time-exit fill | Last future bar's close | Market sell (reference price estimate) |

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
US market hours (9:32–15:32 ET).

### Quick Start

```bash
# Dry run — compute signals, log hypothetical trades, place no orders
python -m live.trader --dry-run --once

# Paper trading (default — port 7497)
python -m live.trader

# Override instrument
python -m live.trader --symbol GDXU

# REAL MONEY — requires explicit --live flag (port 7496)
python -m live.trader --live
```

### Key Design Decisions

**Sizing:** Live uses a fixed 10% position size, not Kelly. Backtest Kelly is
intentionally disabled in the live path — a small live trade sample produces
noisy Kelly estimates that could over-size positions. Fixed sizing is safe
until the live trade log has hundreds of trades.

**Entry basis:** TP/SL brackets are computed from the broker's live market price
at order time (the `fill_basis`), not from the signal bar's close. This matches
the backtest convention where entry = bar N+1's open. The signal bar close is
used only for qty estimation.

**Exit PnL:** Bracket exits (target/stop) use actual IBKR fill prices. When fill
data is unavailable (connection gap), the trade is recorded as `pending_close`
with zero PnL rather than guessing. Time-exits use a reference price estimate
(the one path where PnL is approximate).

### Architecture

```
live/
├── trader.py   <- Scheduler + on_bar() loop (cycle logging, dry-run support)
├── signals.py  <- Wraps build_features() + generate_trades() on live bars
├── broker.py   <- IBKR bracket orders, fill reconciliation, price queries
└── state.py    <- SQLite position/trade log, fixed 10% sizing
```


### Read-Only Monitoring Dashboard

A separate FastAPI process provides a **read-only** dashboard over `live/state.db`.
It does **not** place orders and does not expose trade/config controls.

```bash
# Install live + dashboard deps
pip install -r requirements-live.txt

# Terminal 1: run trader (paper/live as desired)
python -m live.trader

# Terminal 2: run read-only monitor (separate process)
uvicorn live.dashboard:app --host 0.0.0.0 --port 8080

# Open dashboard
# http://localhost:8080
```

Dashboard shows:
- Bot status / heartbeat
- Latest computed signal snapshot
- Current open position
- Recent closed trades
- Warnings and recent operational events

### Raspberry Pi Deployment

```bash
# On the Pi:
chmod +x deploy/setup-pi.sh
./deploy/setup-pi.sh

# Verify deployment:
./deploy/smoke-test.sh
```

The setup script installs system dependencies, creates a venv, and configures
a systemd service. After setup:

```bash
sudo systemctl start monad-trader
sudo systemctl status monad-trader
journalctl -u monad-trader -f
```

---

## Why ETFs Over BTC?

BTC Hourly produces higher gross returns but trades on a crypto CEX with fees
that erode 40-60% of returns at retail rates. ETFs at US brokerages have zero
commission — gross return equals net return.

| | BTC Hourly (retail fees) | TQQQ Hourly | GDXU Hourly |
|---|---|---|---|
| Commission | 0.1% round-trip | $0 | $0 |
| Monthly fee drag | ~1.5%/mo | $0 | $0 |
| Custody | Exchange counterparty risk | SIPC-insured | SIPC-insured |
| Tax reporting | Complex crypto basis | Standard 1099-B | Standard 1099-B |
| Operating hours | 24/7 | Market hours only | Market hours only |

---

## Universal Sweep Tool

The sweep tool finds optimal parameters for **any** equity or ETF on hourly bars.
Results are saved as JSON artifacts (`sweep_results_TICKER.json`); config rewriting
is optional.

```bash
python sweep.py GDXU                        # Full sweep (2yr lookback)
python sweep.py TQQQ --mode realistic        # With backtest fairness
python sweep.py SOXL --start 2024-06-01      # Custom date range
python sweep.py LABU --min-stop 0.15         # Minimum stop floor
python sweep.py GDXU --apply                 # Auto-apply to config.py
```

**Phases:** Coarse sweep (target/stop, R:R, VWAP, RSI) → Cross-validation →
Robustness check (rolling windows, fragility detection, spread-safety scoring).

**Output:** `sweep_results_TICKER.json` contains optimal params, performance
metrics, robustness results, and holdout evaluation. This JSON is the primary
artifact — config rewriting is a convenience, not the source of truth.

Experiment results are also appended to `experiments.jsonl` (one line per sweep
run) for longitudinal tracking across parameter changes.

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
Regime gate (6-state MA slope classifier, backtest only):
  STRONG_BULL / BULL / STALLING / RECOVERING / BEAR / STRONG_BEAR
  -> blocks entries in downtrends, scales position size by conviction
        |
        v
Position sizing:
  Backtest: Kelly Criterion x regime_mult x ADX_mult (capped 20-30%)
  Live:     fixed 10% (Kelly disabled — see "Key Design Decisions" above)
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

# Live trading
python -m live.trader --dry-run --once    # verify signals
python -m live.trader                      # paper mode
python -m live.trader --live --symbol TQQQ # real money

# Tests
python -m unittest discover tests -v
```

## Project Structure

```
MONAD-quant/
├── config.py               <- All params; change ACTIVE_MODE here
├── config_modules/
│   ├── base.py             <- Shared risk/sizing/backtest settings
│   └── live.py             <- IBKR connection settings, dry-run flag
├── main.py                 <- Entry point (backtest)
├── sweep.py                <- Universal parameter sweep tool
├── experiments.jsonl        <- Experiment log (one JSON line per sweep run)
├── live/
│   ├── trader.py           <- Scheduler + on_bar() loop
│   ├── signals.py          <- Real-time signal computation
│   ├── broker.py           <- IBKR bracket orders + fill reconciliation
│   └── state.py            <- SQLite position/trade state, fixed sizing
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
│   ├── test_state.py       <- State DB + config tests (14 tests)
│   └── test_execution_model.py <- Execution model + regression tests (12 tests)
└── sweep_results_*.json    <- Saved sweep results per ticker
```

---

## License

(c) 2026 Monad Industries

This project is licensed under the MIT License.
