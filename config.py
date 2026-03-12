"""
MONAD Quant — Strategy Configuration
=====================================
Change ACTIVE_MODE to switch between strategy profiles.
All other parameters are pre-tuned for their respective mode.
"""

# ═══════════════════════════════════════════════════════════════════════════
#  ACTIVE MODE — the only line you normally need to change
#  Options: "BTC_DAILY" | "BTC_HOURLY" | "QQQ"
# ═══════════════════════════════════════════════════════════════════════════
ACTIVE_MODE = "BTC_DAILY"

ACTIVE_MODE   = "BTC_HOURLY"  # Options: BTC_HOURLY, BTC_DAILY, QQQ_DAILY, SOXL_DAILY

# Signal params — daily bars
RSI_PERIOD        = 14
RSI_OVERSOLD      = 38       # BTC in uptrends rarely hits 30 — 38 catches shallow bull dips
RSI_OVERBOUGHT    = 62
MACD_FAST         = 12
MACD_SLOW         = 26
MACD_SIGNAL       = 9
ROC_PERIOD        = 10       # Legacy param — computed but unused; kept for config compatibility
VWAP_WINDOW       = 20
VWAP_ZSCORE_THRESH = 1.3     # Fires ~15-20% of bars; 1.5 too rare on BTC daily
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
BULL_KELLY_MULTIPLIER = 0.75 # Kelly multiplier when trend direction is bullish
MAX_POSITION_PCT  = 0.20     # Never risk more than 20% per trade

# ── Regime ──────────────────────────────────────────────────────────────────
TREND_SMA_PERIOD  = 200      # Period for trend direction SMA (bull/bear filter)

# ── Hourly Trade Filter ──────────────────────────────────────────────────────
HOURLY_TRADE_FILTER      = True   # Master toggle
HOURLY_TRADE_HOURS_START = 8      # UTC hour to start accepting entries (inclusive)
HOURLY_TRADE_HOURS_END   = 22     # UTC hour to stop accepting entries (exclusive)

# ── Backtest ────────────────────────────────────────────────────────────────
BACKTEST_START    = "2020-01-01"
BACKTEST_END      = "2024-12-31"
PLOT_RESULTS      = True
