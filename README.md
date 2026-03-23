# MONAD Quant

> Momentum + mean-reversion strategy engine for ETFs and BTC. Built on Alpha Vantage and Yfinance data with Claude AI integration via the Anthropic financial-services-plugins framework.

---

## What This Is

MONAD Quant is **not** a "beat Bitcoin" strategy. It is a capital-preservation and income engine
for investors who want low-volatility, consistent gains rather than riding the full crypto
lottery ticket up and down.

The analogy is a high-yield bond ETF that actively trades to generate income:
- Sits flat (cash) during confirmed bear markets — does not fight downtrends
- Buys RSI dips during confirmed bull regimes — mean-reversion, not momentum chasing
- Sizes positions via fractional Kelly Criterion — risk scales with signal conviction
- Long-only across all modes — bear alpha is defined as **not losing money**

---

## Strategy Modes

Switch modes by changing `ACTIVE_MODE` in `config.py` — one line.

### BTC Daily — Capital Preservation
```python
ACTIVE_MODE = "BTC_DAILY"
```
High-conviction dip-buying on BTC daily bars. A 6-state regime classifier blocks all entries
during bear markets, sitting in cash until conditions recover.

### BTC Hourly — Active Income
```python
ACTIVE_MODE = "BTC_HOURLY"
```
High-frequency mean-reversion on BTC hourly bars. Adaptive Kelly scales position size
based on rolling win rate. Requires maker-fee access on a crypto CEX — retail fees
significantly erode returns.

### QQQ Hourly — Retail Income
```python
ACTIVE_MODE = "QQQ_HOURLY"
```
Same mean-reversion framework applied to QQQ (Nasdaq-100 ETF) on hourly bars.
Zero commission at all major US brokerages — gross return equals net return.

### TQQQ Hourly — Leveraged ETF Income
```python
ACTIVE_MODE = "TQQQ_HOURLY"
```
3x leveraged Nasdaq-100 ETF. Wider intraday swings create more alpha per trade.
Zero commission at all US brokerages.

### GDXU Hourly — Gold Miners Income
```python
ACTIVE_MODE = "GDXU_HOURLY"
```
3x leveraged gold miners ETN. Uncorrelated with tech — portfolio diversification benefit.
Zero commission at all US brokerages.

> **Note:** Performance results are being re-validated after backtest fairness fixes
> (rolling Kelly, worst-case same-bar ambiguity, slippage). Run `python main.py` or
> `python sweep.py TICKER` to generate current numbers with the realistic backtest mode.

---

## Backtest Modes

The backtester supports three fairness levels:

| Mode | Slippage | Same-bar ambiguity | Kelly sizing |
|---|---|---|---|
| `optimistic` | 0 bps | Assumes target hit | Full-sample (lookahead) |
| **`realistic`** | **2 bps** | **Assumes stop hit** | **Rolling (no lookahead)** |
| `harsh` | 5 bps | Assumes stop hit | Rolling (no lookahead) |

Set via `BACKTEST_MODE` in `config.py` (default: `realistic`). The sweep tool also
accepts `--mode realistic` to sweep under fair assumptions.

---

## Why ETFs?

BTC Hourly is theoretically the higher-return mode, but trading on a crypto CEX
introduces fee drag that severely erodes returns for retail investors. ETFs at major
US brokerages have zero commission — gross return equals net return.

Additional ETF advantages:
- **No custody risk** — SIPC-insured brokerage vs crypto exchange counterparty risk
- **Tax simplicity** — standard 1099-B vs complex crypto cost-basis tracking
- **Market hours only** — 9:30-16:00 ET, no 24/7 monitoring required
- **Tighter spreads** — institutional market makers provide more orderly mean-reversion

---

## Universal Sweep Tool (`sweep.py`)

The sweep tool finds optimal signal and risk parameters for **any** equity or ETF on
hourly bars. It fetches data via yfinance, runs a multi-phase parameter sweep, performs
robustness checks, and can auto-apply the results to `config.py`.

### Basic Usage

```bash
# Full sweep for any ticker (2yr lookback by default)
python sweep.py GDXU

# Realistic backtest mode (recommended)
python sweep.py TQQQ --mode realistic

# Custom date range
python sweep.py SOXL --start 2024-06-01

# Run only one phase
python sweep.py TQQQ --phase 1    # Phase 1: coarse sweep only
python sweep.py NVDA --phase 2    # Phase 2: cross-validation only

# Set minimum stop loss floor (prevents unrealistic tight stops)
python sweep.py LABU --min-stop 0.15

# Specify broker for spread estimates
python sweep.py GDXU --broker ibkr

# Auto-apply optimal params to config.py (no interactive prompt)
python sweep.py GDXU --apply
```

### How It Works

The sweep runs in three phases:

**Phase 1 — Coarse Sweep:**
- **1a: Target/Stop at 2:1 R:R** — tests targets from 0.3% to 2.0% with matching stops
- **1b: R:R ratio variations** — at the best target, tests stops from 0.15% to 0.60%
  to find the optimal reward:risk ratio
- **1c: VWAP threshold** — sweeps VWAP z-score from 0.1 to 1.2
- **1d: RSI oversold threshold** — sweeps RSI from 42 to 100

**Phase 2 — Cross-Validation:**
- Fine-tunes target, stop, and RSI around the Phase 1 best with tighter increments
- Validates that Phase 1 results aren't edge-case artifacts

**Phase 3 — Robustness Check:**
- Runs the optimal params across rolling 2-month windows (30-day slide)
- Reports negative window count, worst/best window performance
- Flags **fragile** configs (>25% negative windows, DD > -2%, or stop too close to spread)
- If fragile, auto-tests a fallback config with a wider (live-safe) stop at the same R:R

### Live-Safety Features

The sweep auto-calculates a **safe stop floor** based on the ticker's price level and
estimated bid-ask spread. Stops below 5x the spread are penalized in scoring because
they won't survive live slippage. The scoring function:
- **Severe penalty (0.3x)** if stop < 3x spread
- **Moderate penalty (0.7x)** if stop < 5x spread
- Full score if stop >= 5x spread

Override with `--min-stop 0` to disable (for backtesting only) or `--broker ibkr` to
use tighter spread estimates for IBKR accounts.

### Output

Results are saved to `sweep_results_TICKER.json` with optimal params, performance
metrics, live-trading viability info, and robustness check results.

At the end of a sweep, you're prompted to auto-apply the optimal params to `config.py`.
Use `--apply` to skip the prompt.

### Adding a New Instrument After Sweep

After running `python sweep.py NEWTICKER`:
1. Take the optimal params from the output
2. Add signal params to `config.py` (RSI, MACD, VWAP, target, stop) following the
   GDXU/TQQQ pattern
3. Add an `ASSETS` dict entry
4. Add to `_MODE_TO_ASSET` mapping
5. Add data fetcher route in `main.py` and `engine.py`

---

## Live Trading

The live trading system connects to **Interactive Brokers** (TWS or IB Gateway) and
runs as a long-lived process. APScheduler fires the trading logic 2 minutes after each
hourly bar close during US market hours.

### Quick Start

```bash
# Paper trading (default — connects to IB Gateway on port 7497)
python -m live.trader

# Override instrument
python -m live.trader --symbol GDXU

# REAL MONEY — requires explicit --live flag (port 7496)
python -m live.trader --live
```

### Architecture

```
live/
├── trader.py      <- Scheduler + main on_bar() loop
├── signals.py     <- Real-time signal computation from yfinance bars
├── broker.py      <- IBKR connection, order placement, position queries
└── state.py       <- Trade state tracking (position, bars held, entry price)
```

The live trader uses the same signal logic as the backtester (`src/signals/`) to
compute RSI, MACD, and VWAP signals on the latest hourly bar, then routes through
the same entry/exit rules. Paper vs live mode is controlled by `config.LIVE_PAPER_MODE`.

**Sizing:** Live trading uses a fixed 10% position size (not Kelly). The backtest
Kelly sizing is intentionally disabled in the live path to avoid compounding
estimation error from a small live trade sample. See `live/state.py:get_position_plan()`.

**Dry-run mode:** Use `--dry-run` to compute signals and log hypothetical trades
without placing any orders — useful for verifying deployment before going live.

### Raspberry Pi Deployment

For always-on headless operation, the strategy can be deployed to a Raspberry Pi
(or any Linux server) as a systemd service:

```bash
# On the Pi:
chmod +x deploy/setup-pi.sh
./deploy/setup-pi.sh
```

The setup script:
1. Installs system dependencies (Python, Java for IB Gateway)
2. Creates a Python virtual environment with `requirements-pi.txt` (lightweight)
3. Installs and configures the systemd service (`monad-trader.service`)
4. Sets up a health check script (`deploy/healthcheck.sh`)
5. Auto-detects the username and repo path (works on any user, not just `pi`)

After setup, manage the service with:
```bash
sudo systemctl start monad-trader    # start trading
sudo systemctl stop monad-trader     # stop
sudo systemctl status monad-trader   # check status
journalctl -u monad-trader -f        # tail logs
```

---

## How It Works

```
Price data (yfinance / Alpha Vantage)
        |
        v
Signal layer:
  +-- RSI dip  +  MACD histogram inflection  -> momentum_signal
  +-- VWAP z-score deviation                 -> volume_signal
        |
        v
Regime gate (6-state MA slope classifier):
  STRONG_BULL / BULL / STALLING / RECOVERING / BEAR / STRONG_BEAR
  -> blocks entries in downtrends, sizes Kelly by regime conviction
        |
        v
Kelly Criterion position sizing:
  base_kelly x regime_mult x ADX_mult -> capped at 20-30%
        |
        v
Exit: target  OR  stop  OR  time limit (mode-specific values)
```

The regime classifier is the core innovation. In BTC's 2022 bear market (-65%),
the strategy made zero long entries for 14 consecutive months — sitting in cash
while every other entry system was buying falling knives.

---

## Setup

```bash
git clone <repo-url>
cd MONAD-quant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

For live trading, install the extended dependencies:
```bash
pip install -r requirements-live.txt
```

For Raspberry Pi deployment (lightweight, no plotting):
```bash
pip install -r requirements-pi.txt
```

Optionally add an Alpha Vantage key to `.env` for premium data (yfinance is used by default):
```
ALPHA_VANTAGE_KEY=your_key_here
```

## Run

```bash
# Standard backtest (uses ACTIVE_MODE from config.py)
python main.py

# Walk-forward optimizer (daily mode only)
python main.py --mode=walk-forward

# Override date range
python main.py --start 2023-01-01 --end 2023-12-31

# Universal parameter sweep for any ticker
python sweep.py GDXU
python sweep.py SOXL --start 2024-06-01 --mode realistic

# Live trading (paper mode)
python -m live.trader

# Live trading (real money)
python -m live.trader --live --symbol TQQQ
```

## Project Structure

```
MONAD-quant/
├── config.py               <- All params; change ACTIVE_MODE here
├── main.py                 <- Entry point (backtest)
├── sweep.py                <- Universal parameter sweep tool
├── fee_analysis.py         <- Fee drag analysis and comparison
├── live/
│   ├── trader.py           <- Live trading scheduler + main loop
│   ├── signals.py          <- Real-time signal computation
│   ├── broker.py           <- IBKR connection + order management
│   └── state.py            <- Trade state tracking
├── deploy/
│   ├── setup-pi.sh         <- Raspberry Pi deployment script
│   ├── monad-trader.service <- systemd service file
│   └── healthcheck.sh      <- Health check for monitoring
├── src/
│   ├── data/               <- yfinance + Alpha Vantage fetchers
│   ├── signals/
│   │   ├── momentum.py     <- RSI, MACD, 6-state regime classifier
│   │   ├── volume.py       <- VWAP z-score
│   │   └── volatility.py   <- ATR, Bollinger Bands, ADX
│   ├── strategy/
│   │   ├── engine.py       <- Signal orchestration + trade generation
│   │   └── sizing.py       <- Fractional Kelly calculator
│   └── backtest/
│       └── runner.py       <- Equity curve, monthly P&L, diagnostics
└── sweep_results_*.json    <- Saved sweep results per ticker
```

---
## License

(c) 2026 Monad Industries

This project is licensed under the MIT License.
