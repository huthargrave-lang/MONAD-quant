# MONAD Quant — Momentum Strategy Skill

## Overview
This skill governs how MONAD Quant analyzes assets, generates signals, and makes trade decisions. The strategy prioritizes small, consistent gains (1–2% per trade) with tight risk management over high-variance swings.

## Signal Framework

### Entry Requirements
A trade is entered only when **2 or more** of the following signals agree in direction:

1. **Momentum Signal** — RSI + MACD + ROC composite
   - Long: RSI < 35, MACD bullish crossover, positive ROC
   - Short: RSI > 65, MACD bearish crossover, negative ROC

2. **Volume Signal** — VWAP z-score with volume confirmation
   - Long: Price > 1.5 std below VWAP, above-avg volume
   - Short: Price > 1.5 std above VWAP, above-avg volume

3. **Regime Filter** — Bollinger Band width determines trending vs ranging
   - Only trade when BB width > rolling median (trending regime)

### Exit Rules
- **Take profit**: 1.5% from entry
- **Stop loss**: 1.0% from entry (1.5:1 reward/risk)
- **Time stop**: Exit at close of bar 5 if neither triggered

## Position Sizing
Uses half-Kelly Criterion based on historical win rate and payoff ratio. Maximum position size capped at 20% of capital per trade.

## Assets
Designed for high-volatility assets: BTC/USD, QQQ, SOXL, ARKK. Crypto and ETF data fetched via Alpha Vantage API with local caching.

## Performance Targets
- Sharpe Ratio > 1.5
- Max Drawdown < 15%
- Win Rate > 50%
- Average trade duration: 1–5 bars