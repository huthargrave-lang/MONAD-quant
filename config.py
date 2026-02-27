"""
MONAD Quant - Strategy Configuration
Tune parameters here without touching core logic.
"""

# ── Assets ─────────────────────────────────────────────────────────────────
ASSETS = {
    "BTC": {
        "type": "crypto",
        "market": "USD",
        "rsi_oversold": 38,
        "rsi_overbought": 62,
        "target_gain_pct": 0.015,
        "stop_loss_pct": 0.010,
        "require_signals": 1,
        "vwap_zscore_thresh": 1.3,
    },
    "QQQ": {
        "type": "etf",
        "rsi_oversold": 42,
        "rsi_overbought": 58,
        "target_gain_pct": 0.010,  # tighter targets for less volatile ETF
        "stop_loss_pct": 0.007,
        "require_signals": 1,
        "vwap_zscore_thresh": 1.0,  # ETFs revert faster
    },
    "SOXL": {
        "type": "etf",
        "rsi_oversold": 38,
        "rsi_overbought": 62,
        "target_gain_pct": 0.020,  # leveraged ETF, wider targets
        "stop_loss_pct": 0.012,
        "require_signals": 1,
        "vwap_zscore_thresh": 1.3,
    },
    "BTC_HOURLY": {
        "type": "crypto_hourly",
        "target_gain_pct": 0.004,   # 0.4% per trade on hourly bars
        "stop_loss_pct": 0.0025,    # 0.25% stop (1.6:1 R/R)
        "require_signals": 1,
        "rsi_oversold": 35,
        "rsi_overbought": 65,
        "vwap_zscore_thresh": 1.0,
    },
}

DEFAULT_ASSET = "QQQ"

# ── Signal Parameters ───────────────────────────────────────────────────────
RSI_PERIOD        = 14
RSI_OVERSOLD      = 38
RSI_OVERBOUGHT    = 62
MACD_FAST         = 12
MACD_SLOW         = 26
MACD_SIGNAL       = 9
ROC_PERIOD        = 10
VWAP_WINDOW       = 20
VWAP_ZSCORE_THRESH = 1.3
ATR_PERIOD        = 14
BB_WINDOW         = 20
BB_STD            = 2.0

# ── Strategy Parameters ─────────────────────────────────────────────────────
REQUIRE_SIGNALS   = 1        # Minimum signals to agree for entry (1-3)
TARGET_GAIN_PCT   = 0.015    # 1.5% take profit
STOP_LOSS_PCT     = 0.010    # 1.0% stop loss
USE_REGIME_FILTER = True     # Only trade in trending regimes

# ── Risk & Sizing ───────────────────────────────────────────────────────────
INITIAL_CAPITAL   = 100_000
KELLY_MULTIPLIER  = 0.5      # Fractional Kelly (0.5 = half-Kelly)
MAX_POSITION_PCT  = 0.20     # Never risk more than 20% per trade

# ── Hourly Signal Parameters (BTC intraday) ─────────────────────────────────
RSI_PERIOD_HOURLY    = 7
MACD_FAST_HOURLY     = 6
MACD_SLOW_HOURLY     = 13
MACD_SIGNAL_HOURLY   = 4
ROC_PERIOD_HOURLY    = 5
VWAP_WINDOW_HOURLY   = 10
BB_WINDOW_HOURLY     = 14

# ── Backtest ────────────────────────────────────────────────────────────────
BACKTEST_START        = "2020-01-01"
BACKTEST_END          = "2024-12-31"
BACKTEST_START_HOURLY = "2024-01-01"   # yfinance: max 730 days of hourly data
BACKTEST_END_HOURLY   = "2024-12-31"
PLOT_RESULTS          = True
