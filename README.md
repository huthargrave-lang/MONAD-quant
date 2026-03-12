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

High-frequency mean-reversion on BTC hourly bars. ~116 trades per month, each targeting
0.4% gain with a 0.25% stop. Compounds into substantial monthly income.

| Metric | Result |
|---|---|
| Period | Mar 2024 – Feb 2026 (2 years) |
| Total Return | 7.80% |
| **Avg Monthly** | **+5.75%** |
| Sharpe Ratio | 2.365 |
| Max Drawdown | -0.39% |
| Trades/month | ~116 |
| Win Rate | 46.2% |

Monthly breakdown:

| Month | Return | WR |
|---|---|---|
| 2024-11 | +11.39% | 53.6% |
| 2025-02 | +17.11% | 61.7% |
| 2025-03 | +11.27% | 53.0% |
| 2025-12 | +11.55% | 57.1% |
| 2025-07 | -0.95% | 37.4% |
| 2025-11 | -3.64% | 33.6% |

Best for: active income generation. Lower Sharpe than daily but significantly higher
monthly cash flow. Negative months exist but max drawdown stays under 0.5%.

---

### QQQ — Coming Soon
```python
ACTIVE_MODE = "QQQ"
```

Same mean-reversion framework applied to QQQ (Nasdaq-100 ETF). Parameters are scaffolded
but not yet walk-forward optimized. Lower volatility than BTC → tighter targets (1%),
tighter stops (0.6%), looser RSI threshold (42 vs 38).

Status: placeholder params — do not use for live trading until walk-forward tuned.

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

| | MONAD Daily | MONAD Hourly | BTC Buy & Hold |
|---|---|---|---|
| 5yr Return | 11% | — | 1,194% |
| Sharpe | 4.9 | 2.4 | ~0.9 |
| Max Drawdown | -1.7% | -0.4% | -83% |
| Bear market | Flat (cash) | Low DD | -65% in 2022 |
| Avg Monthly | 0.4% | 5.75% | High variance |

MONAD is not trying to beat buy-and-hold on raw returns. It is trying to generate
consistent, bond-like income with equity-level upside and near-zero drawdown.
The comparison to buy-and-hold (-1,183% alpha) is intentionally unfavorable — that
is not the benchmark. The benchmark is a 4-6% high-yield bond ETF.

---

Monad Industries © 2026
