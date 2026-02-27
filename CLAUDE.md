# MONAD Quant — Project Brief

Momentum + mean-reversion quant strategy for BTC and ETFs.

## Stack
- Alpha Vantage API for crypto data
- yfinance for ETF historical data
- Signals: RSI, MACD, VWAP z-score, Bollinger Bands
- Kelly Criterion position sizing
- Per-asset parameterization in config.py

## Current Status
- BTC backtest 2020-2024: Sharpe 6.18, 25% return, -2.45% max drawdown
- QQQ integration in progress — yfinance fetch_yfinance function has import bug in src/data/fetcher.py

## Key Files
- config.py — all tunable parameters per asset
- src/data/fetcher.py — data fetching (broken, needs fix)
- src/strategy/engine.py — signal aggregation
- src/backtest/runner.py — backtest loop