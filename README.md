# MONAD Quant

> A systematic, long-only trading engine designed to behave like a **high-yield bond ETF** —
> consistent monthly income, capital preservation during downturns, no shorts, no leverage.

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
~+1.14%/mo. See "Why QQQ?" section below for the fee model comparison.
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
| 2024-06 | +0.67% | 18 | 66.7% | ✓ |
| 2024-07 | +1.16% | 38 | 57.9% | ✓ |
| 2024-08 | +1.30% | 32 | 65.6% | ✓ |
| 2024-09 | +0.38% | 21 | 52.4% | |
| 2024-10 | +0.93% | 33 | 54.5% | ✓ |
| 2024-11 | +0.89% | 21 | 76.2% | ✓ |
| 2024-12 | +0.34% | 13 | 53.8% | |
| 2025-01 | +0.86% | 24 | 62.5% | ✓ |
| 2025-02 | +0.33% | 21 | 47.6% | |
| 2025-03 | +0.87% | 37 | 56.8% | ✓ |
| 2025-04 | +2.25% | 36 | 83.3% | ✓ ← best month |
| 2025-05 | +0.54% | 11 | 72.7% | ✓ |
| 2025-06 | +0.53% | 20 | 55.0% | ✓ |
| 2025-07 | +0.66% | 21 | 61.9% | ✓ |
| 2025-08 | +0.30% | 32 | 37.5% | ← worst WR, still positive |
| 2025-09 | +0.05% | 16 | 50.0% | |
| 2025-10 | +0.93% | 26 | 65.4% | ✓ |
| 2025-11 | +0.14% | 25 | 48.0% | |
| 2025-12 | +0.59% | 18 | 61.1% | ✓ |
| 2026-01 | +1.07% | 23 | 73.9% | ✓ |
| 2026-02 | +1.01% | 20 | 75.0% | ✓ |

The 2:1 R:R ratio (0.24% target / 0.12% stop) means the strategy stays positive
even at 37.5% WR — the breakeven win rate is ~34%. QQQ never approached it.


---<img width="1496" height="864" alt="qqqtest" src="https://github.com/user-attachments/assets/26c164fe-b031-40a4-b612-fad5a78b3c73" />


## Why QQQ? The Fee Model Problem

BTC Hourly is theoretically the higher-return mode, but trading on a crypto CEX
introduces fee drag that severely erodes returns for retail investors:

| BTC Hourly fee tier | Round-trip cost | Monthly fee drag | Net monthly |
|---|---|---|---|
| Retail (0.1%) | 0.20%/trade | −1.52%/mo | +1.14%/mo |
| BNB discount (0.04%) | 0.08%/trade | −0.61%/mo | +2.05%/mo |
| VIP maker (0.02%) | 0.04%/trade | −0.30%/mo | +2.36%/mo |

Accessing the full +2.66%/mo gross requires Binance VIP maker status ($10M+/month
trading volume). At retail rates, fee drag eats 57% of gross return.

**QQQ has zero fee drag.** All major US brokerages (Schwab, Fidelity, TD Ameritrade,
Interactive Brokers) eliminated ETF commissions in 2019. The full +0.71%/mo gross
is retained by any retail investor with a standard brokerage account.

| Mode | Gross/mo | Net/mo (retail) | Infrastructure |
|---|---|---|---|
| BTC Hourly | +2.66% | **+1.14%** | Binance, BNB, VIP tier, 24/7, custody risk |
| **QQQ Hourly** | **+0.71%** | **+0.71%** | Any US brokerage, market hours only |

Additional QQQ advantages for retail deployment:
- **No custody risk** — SIPC-insured brokerage vs crypto exchange counterparty risk
- **Tax simplicity** — standard 1099-B vs complex crypto cost-basis tracking
- **Market hours only** — 9:30–16:00 ET, roughly 1 trade/day, no 24/7 monitoring
- **Tighter spreads** — institutional market makers provide more orderly mean-reversion

### How we got to QQQ Hourly

1. **QQQ Daily (tested, failed):** Walk-forward produced ~5 trades over 3 years
   out-of-sample. The 6-state regime classifier + QQQ's smooth bull trend keeps the
   strategy in BULL/STRONG_BULL almost permanently, but RSI almost never dips below
   38 on daily bars for a low-volatility ETF. Signal scarcity is structural.

2. **QQQ Hourly (first attempt, failed):** Borrowed BTC params (RSI=38, VWAP=1.0,
   stop=0.0006). RSI 38 fires almost never on QQQ hourly bars — ETF intraday moves
   are too small to push RSI that low. Generated <5 trades/month, unusable.

3. **QQQ Hourly (pivoted params, current):** Raised RSI threshold to 70 (QQQ dips
   are shallower), tightened VWAP to 0.4 (ETF deviations are smaller), corrected
   stop to 0.0012 for a clean 2:1 R:R. Unlocked ~24 trades/month at 59.6% WR.

---

## How It Works

```
Price data (yfinance / Alpha Vantage)
        │
        ▼
Signal layer:
  ├── RSI dip  +  MACD histogram inflection  → momentum_signal
  └── VWAP z-score deviation                 → volume_signal
        │
        ▼
Regime gate (6-state MA slope classifier):
  STRONG_BULL / BULL / STALLING / RECOVERING / BEAR / STRONG_BEAR
  → blocks entries in downtrends, sizes Kelly by regime conviction
        │
        ▼
Kelly Criterion position sizing:
  base_kelly × regime_mult × ADX_mult → capped at 20–30%
        │
        ▼
Exit: 3% target  OR  1.5% stop  OR  20-bar time limit
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
```

## Project Structure

```
MONAD-quant/
├── config.py               ← All params; change ACTIVE_MODE here
├── main.py                 ← Entry point
└── src/
    ├── data/               ← yfinance + Alpha Vantage fetchers
    ├── signals/
    │   ├── momentum.py     ← RSI, MACD, 6-state regime classifier
    │   ├── volume.py       ← VWAP z-score
    │   └── volatility.py   ← ATR, Bollinger Bands, ADX
    ├── strategy/
    │   ├── engine.py       ← Signal orchestration + trade generation
    │   └── sizing.py       ← Fractional Kelly calculator
    └── backtest/
        └── runner.py       ← Equity curve, monthly P&L, diagnostics
```

## Performance Philosophy

| | BTC Daily | BTC Hourly | QQQ Hourly | BTC Buy & Hold |
|---|---|---|---|---|
| Period | 5yr | 7yr | 23mo | 5yr |
| Total Return | 11% | 617% | 17.8% | 1,194% |
| Sharpe | 4.9 | 25.6 | 41.6 | ~0.9 |
| Max Drawdown | -1.7% | -0.9% | -0.2% | -83% |
| Avg Monthly | +0.4% | +2.66% (gross) | +0.71% (net) | High variance |
| Negative months | Rare | Occasional | **Zero (23mo)** | Frequent |
| Retail net/mo | ~0.4% | ~1.1% | **~0.71%** | N/A |

MONAD is not trying to beat buy-and-hold on raw returns. It is trying to generate
consistent, bond-like income with near-zero drawdown.
The benchmark is a 4-6% high-yield bond ETF — not crypto lottery tickets.
QQQ Hourly at +0.71%/mo net = +8.5%/yr with a -0.21% max drawdown and zero negative
months. No high-yield bond fund comes close to that risk-adjusted profile.

---

Monad Industries © 2026
