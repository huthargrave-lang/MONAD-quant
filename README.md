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

| Metric | Result |
|---|---|
| Period | 2020–2024 (5 years) |
| Total Return | 11.05% |
| Annualized | 2.12% |
| **Sharpe Ratio** | **4.924** |
| Max Drawdown | -1.72% |
| Avg Monthly | ~0.40% |
| Trades | 83 over 5yr |
| Win Rate | 49.4% |

Best for: accounts prioritizing near-zero drawdown and exceptional risk-adjusted returns.
The 14 flat months (zero trades) during 2022's -65% BTC crash are a feature, not a bug.

---

### BTC Hourly — Active Income
```python
ACTIVE_MODE = "BTC_HOURLY"
```

High-frequency mean-reversion on BTC hourly bars. ~130 trades per month, each targeting
0.4% gain with a 0.2% stop. Adaptive Kelly scales position size based on rolling win rate.

| Metric | Result |
|---|---|
| Period | 2019–2026 (7 years) |
| Total Return | 616.67% |
| Annualized | 36.89% |
| **Avg Monthly** | **+2.66%** |
| Sharpe Ratio | 25.57 |
| Max Drawdown | -0.90% |
| Trades/month | ~130 |
| Win Rate | 48.9% |

Best for: active income generation with crypto infrastructure in place. Requires
maker-fee access on Binance — retail fees (0.1% round-trip) reduce net return to
~+1.14%/mo. See "Why ETFs?" section below for the fee model comparison.
<img width="1414" height="856" alt="BTChourly" src="https://github.com/user-attachments/assets/af88b297-d79e-40bc-aabd-bf377e98867a" />

---

### QQQ Hourly — Retail Income
```python
ACTIVE_MODE = "QQQ_HOURLY"
```

Same mean-reversion framework applied to QQQ (Nasdaq-100 ETF) on hourly bars.
Trades during US market hours (~24 trades/month). Zero commission at all major US
brokerages — gross return equals net return, no fee tier required.

| Metric | Result |
|---|---|
| Period | Apr 2024 – Feb 2026 (23 months) |
| Total Return | 17.77% |
| Annualized | 8.95% |
| **Avg Monthly** | **+0.71%** |
| Sharpe Ratio | 41.57 |
| Max Drawdown | -0.21% |
| Trades/month | ~24 |
| Win Rate | 59.6% |
| Kelly Position | 19.73% |

**23-month results — zero negative months:**

| Month | Return | Trades | Win Rate | |
|---|---|---|---|---|
| 2024-04 | +0.41% | 32 | 46.9% | |
| 2024-05 | +0.24% | 12 | 50.0% | |
| 2024-06 | +0.67% | 18 | 66.7% | |
| 2024-07 | +1.16% | 38 | 57.9% | |
| 2024-08 | +1.30% | 32 | 65.6% | |
| 2024-09 | +0.38% | 21 | 52.4% | |
| 2024-10 | +0.93% | 33 | 54.5% | |
| 2024-11 | +0.89% | 21 | 76.2% | |
| 2024-12 | +0.34% | 13 | 53.8% | |
| 2025-01 | +0.86% | 24 | 62.5% | |
| 2025-02 | +0.33% | 21 | 47.6% | |
| 2025-03 | +0.87% | 37 | 56.8% | |
| 2025-04 | +2.25% | 36 | 83.3% | best month |
| 2025-05 | +0.54% | 11 | 72.7% | |
| 2025-06 | +0.53% | 20 | 55.0% | |
| 2025-07 | +0.66% | 21 | 61.9% | |
| 2025-08 | +0.30% | 32 | 37.5% | worst WR, still positive |
| 2025-09 | +0.05% | 16 | 50.0% | |
| 2025-10 | +0.93% | 26 | 65.4% | |
| 2025-11 | +0.14% | 25 | 48.0% | |
| 2025-12 | +0.59% | 18 | 61.1% | |
| 2026-01 | +1.07% | 23 | 73.9% | |
| 2026-02 | +1.01% | 20 | 75.0% | |

The 2:1 R:R ratio (0.24% target / 0.12% stop) means the strategy stays positive
even at 37.5% WR — the breakeven win rate is ~34%. QQQ never approached it.


---<img width="1496" height="864" alt="qqqtest" src="https://github.com/user-attachments/assets/26c164fe-b031-40a4-b612-fad5a78b3c73" />

### TQQQ Hourly — Leveraged ETF Income
```python
ACTIVE_MODE = "TQQQ_HOURLY"
```

3x leveraged Nasdaq-100 ETF. Same mean-reversion architecture as QQQ but with wider
intraday swings creating more alpha per trade. Ultra-tight 5.6:1 R:R (0.42% target /
0.08% stop) — mean-reversion either works fast or fails immediately. Zero commission
at all US brokerages.

| Metric | Result |
|---|---|
| Period | Apr 2024 – Feb 2026 (23 months) |
| Total Return | 56.54% |
| Annualized | 25.93% |
| **Sharpe Ratio** | **94.2** |
| Max Drawdown | -0.13% |
| Avg Monthly | +1.89% |
| Trades/month | ~21 |
| Win Rate | 70.9% |
| Neg Months | 0/23 |

**Live trading caution:** The 0.08% stop is near the bid-ask spread (~$0.06/share on
TQQQ). If live WR degrades due to slippage, a fallback config is available at 2:1 R:R
(0.70%/0.35%) — still strong at Sharpe 39.8, +2.14%/mo.

---

### GDXU Hourly — Gold Miners Income (Highest Sharpe)
```python
ACTIVE_MODE = "GDXU_HOURLY"
```

3x leveraged gold miners ETN. Uncorrelated with tech, higher intraday volatility than
TQQQ. Ultra-tight 7.5:1 R:R (0.56% target / 0.075% stop). Highest Sharpe ratio and
lowest max drawdown of all modes.

| Metric | Result |
|---|---|
| Period | Apr 2024 – Mar 2026 (24 months) |
| Total Return | 116.55% |
| Annualized | ~49% |
| **Sharpe Ratio** | **96.5** |
| Max Drawdown | -0.10% |
| Avg Monthly | +3.28% |
| Trades/month | ~27 |
| Win Rate | 70.1% |
| Neg Months | 0/24 |

**Live trading caution:** The 0.075% stop is at the boundary of bid-ask spread
(~$0.04-0.06/share on GDXU). Fallback config at 5:1 R:R (1.0%/0.20%) — still
excellent at Sharpe 61.8, +4.07%/mo.

---

## All Modes Comparison

| Mode | Avg/mo | Sharpe | Max DD | Trades/mo | Zero-commission |
|---|---|---|---|---|---|
| BTC Daily | +0.40% | 4.9 | -1.72% | ~1.4 | No |
| QQQ Hourly | +0.71% | 41.6 | -0.21% | ~24 | Yes |
| TQQQ Hourly | +1.89% | 94.2 | -0.13% | ~21 | Yes |
| BTC Hourly | +2.66% | 25.6 | -0.90% | ~130 | No (fees) |
| **GDXU Hourly** | **+3.28%** | **96.5** | **-0.10%** | **~27** | **Yes** |

---

## Why ETFs? The Fee Model Problem

BTC Hourly is theoretically the higher-return mode, but trading on a crypto CEX
introduces fee drag that severely erodes returns for retail investors:

| BTC Hourly fee tier | Round-trip cost | Monthly fee drag | Net monthly |
|---|---|---|---|
| Retail (0.1%) | 0.20%/trade | -1.52%/mo | +1.14%/mo |
| BNB discount (0.04%) | 0.08%/trade | -0.61%/mo | +2.05%/mo |
| VIP maker (0.02%) | 0.04%/trade | -0.30%/mo | +2.36%/mo |

Accessing the full +2.66%/mo gross requires Binance VIP maker status ($10M+/month
trading volume). At retail rates, fee drag eats 57% of gross return.

**ETFs have zero fee drag.** All major US brokerages (Schwab, Fidelity, TD Ameritrade,
Interactive Brokers) eliminated ETF commissions in 2019. QQQ, TQQQ, and GDXU all
retain their full gross return for any retail investor.

| Mode | Gross/mo | Net/mo (retail) | Infrastructure |
|---|---|---|---|
| BTC Hourly | +2.66% | **+1.14%** | Binance, BNB, VIP tier, 24/7, custody risk |
| QQQ Hourly | +0.71% | **+0.71%** | Any US brokerage, market hours only |
| TQQQ Hourly | +1.89% | **+1.89%** | Any US brokerage, market hours only |
| **GDXU Hourly** | **+3.28%** | **+3.28%** | Any US brokerage, market hours only |

Additional ETF advantages for retail deployment:
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
├── trader.py      ← Scheduler + main on_bar() loop
├── signals.py     ← Real-time signal computation from yfinance bars
├── broker.py      ← IBKR connection, order placement, position queries
└── state.py       ← Trade state tracking (position, bars held, entry price)
```

The live trader uses the same signal logic as the backtester (`src/signals/`) to
compute RSI, MACD, and VWAP signals on the latest hourly bar, then routes through
the same entry/exit rules. Paper vs live mode is controlled by `config.LIVE_PAPER_MODE`.

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
python sweep.py SOXL --start 2024-06-01 --broker ibkr

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

## Performance Philosophy

| | BTC Daily | BTC Hourly | QQQ Hourly | TQQQ Hourly | GDXU Hourly | BTC Buy & Hold |
|---|---|---|---|---|---|---|
| Period | 5yr | 7yr | 23mo | 23mo | 24mo | 5yr |
| Total Return | 11% | 617% | 17.8% | 56.5% | 116.6% | 1,194% |
| Sharpe | 4.9 | 25.6 | 41.6 | 94.2 | 96.5 | ~0.9 |
| Max Drawdown | -1.7% | -0.9% | -0.2% | -0.13% | -0.10% | -83% |
| Avg Monthly | +0.4% | +2.66% | +0.71% | +1.89% | +3.28% | High variance |
| Negative months | Rare | Occasional | **Zero** | **Zero** | **Zero** | Frequent |
| Retail net/mo | ~0.4% | ~1.1% | **+0.71%** | **+1.89%** | **+3.28%** | N/A |

MONAD is not trying to beat buy-and-hold on raw returns. It is trying to generate
consistent, bond-like income with near-zero drawdown.
The benchmark is a 4-6% high-yield bond ETF — not crypto lottery tickets.
GDXU Hourly at +3.28%/mo net = ~49%/yr with a -0.10% max drawdown and zero negative
months. No high-yield bond fund comes close to that risk-adjusted profile.

---
## License

(c) 2026 Monad Industries

This project is licensed under the MIT License.
