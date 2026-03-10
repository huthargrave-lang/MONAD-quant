# 🔺 MONAD Quant

> Momentum + mean-reversion strategy engine for ETFs and BTC. Built on Alpha Vantage and Yfinance data with Claude AI integration via the Anthropic financial-services-plugins framework.

## Strategy

Generates alpha through small, consistent gains (1–2% per trade) using a multi-signal approach:

- **Momentum**: RSI divergence, MACD crossovers, Rate of Change
- **Volume**: VWAP z-score deviation with volume confirmation  
- **Volatility**: Bollinger Band regime detection (trending vs ranging)
- **Sizing**: Half-Kelly Criterion with 20% max position cap

Trades only when 2+ signals agree. Target 1.5% gain, 1.0% stop loss (1.5:1 R:R).

## Setup

```bash
git clone git@github.com:huthargrave-lang/MONAD-quant.git
cd MONAD-quant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Add your Alpha Vantage key to `.env`:
```
ALPHA_VANTAGE_KEY=your_key_here
```

## Run

```bash
python main.py
```

Configure assets, signal params, and backtest window in `config.py`.

## Structure

```
MONAD-quant/
├── .claude-plugin/     # Claude Code plugin manifest
├── commands/           # Slash commands (/screen, /backtest, /report)
├── skills/             # Domain knowledge for Claude
├── src/
│   ├── data/           # Alpha Vantage fetcher + caching
│   ├── signals/        # Momentum, volume, volatility modules
│   ├── strategy/       # Signal engine + Kelly sizing
│   └── backtest/       # Backtest runner + metrics
├── config.py           # All tunable parameters
└── main.py             # Entry point
```

## Performance Targets

| Metric | Target |
|--------|--------|
| Sharpe Ratio | > 1.5 |
| Max Drawdown | < 15% |
| Win Rate | > 50% |
| Avg Trade Duration | 1–5 bars |

## Built with

- [Alpha Vantage](https://www.alphavantage.co/) — Market data
- [Anthropic Financial Services Plugins](https://github.com/anthropics/financial-services-plugins) — Claude integration
- Monad Industries © 2026
