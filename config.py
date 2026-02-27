"""
MONAD Quant - Strategy Configuration
Tune parameters here without touching core logic.
"""

# ── Assets ─────────────────────────────────────────────────────────────────
ASSETS = {
    "BTC":  {"type": "crypto", "market": "USD"},
    "QQQ":  {"type": "etf"},
    "SOXL": {"type": "etf"},
    "ARKK": {"type": "etf"},
}

DEFAULT_ASSET = "BTC"

# ── Signal Parameters ───────────────────────────────────────────────────────
RSI_PERIOD        = 14
RSI_OVERSOLD      = 35
RSI_OVERBOUGHT    = 65
MACD_FAST         = 12
MACD_SLOW         = 26
MACD_SIGNAL       = 9
ROC_PERIOD        = 10
VWAP_WINDOW       = 20
VWAP_ZSCORE_THRESH = 1.5
ATR_PERIOD        = 14
BB_WINDOW         = 20
BB_STD            = 2.0

# ── Strategy Parameters ─────────────────────────────────────────────────────
REQUIRE_SIGNALS   = 2        # Minimum signals to agree for entry (1-3)
TARGET_GAIN_PCT   = 0.015    # 1.5% take profit
STOP_LOSS_PCT     = 0.010    # 1.0% stop loss
USE_REGIME_FILTER = True     # Only trade in trending regimes

# ── Risk & Sizing ───────────────────────────────────────────────────────────
INITIAL_CAPITAL   = 100_000
KELLY_MULTIPLIER  = 0.5      # Fractional Kelly (0.5 = half-Kelly)
MAX_POSITION_PCT  = 0.20     # Never risk more than 20% per trade

# ── Backtest ────────────────────────────────────────────────────────────────
BACKTEST_START    = "2022-01-01"
BACKTEST_END      = "2024-12-31"
PLOT_RESULTS      = True
