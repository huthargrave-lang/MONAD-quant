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

# ═══════════════════════════════════════════════════════════════════════════
#  PROFILE 1 — BTC DAILY
#  Goal:    Capital preservation + consistent monthly income (~0.4–0.5%/mo)
#  Style:   Mean-reversion dip-buying in confirmed bull regimes
#  Sharpe:  4.9  |  Max DD: -1.72%  |  5yr return: 11.05%
#  Best for: accounts that want near-zero drawdown, high Sharpe
# ═══════════════════════════════════════════════════════════════════════════

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

# Strategy params — daily
REQUIRE_SIGNALS       = 1        # Only 1 of 2 signals needed — regime does the heavy filtering
TARGET_GAIN_PCT       = 0.030    # 3% take-profit — dips recover 3-4%; 5% overshoots and reverses
STOP_LOSS_PCT         = 0.015    # 1.5% stop (2:1 R:R)
MAX_TRADE_BARS        = 20       # 4 trading weeks max hold — mean-reversion resolves in <4wks

# Regime — daily (6-state slope classifier; core of the strategy)
USE_SLOPE_REGIME      = True
LONGS_ONLY            = True     # Bear alpha = NOT losing, not chasing shorts
MA_SLOPE_WINDOW       = 20
MA_SHORT_WINDOW       = 50       # RECOVERING fires when price crosses above 50-MA (2-4wk lag vs 252-MA)
MA_STRONG_BULL_SLOPE  = 0.02
MA_STRONG_BEAR_SLOPE  = -0.02
MA_REGIME_WINDOW      = 252      # 1-year lookback for broad trend

# Per-regime Kelly multipliers
KELLY_MULT_STRONG_BULL = 1.5
KELLY_MULT_BULL        = 1.0
KELLY_MULT_STALLING    = 0.75
KELLY_MULT_RECOVERING  = 0.75
KELLY_MULT_BEAR        = 0.75
KELLY_MULT_STRONG_BEAR = 0.5

# Bear defensive longs — small longs at RSI<30 in BEAR (not STRONG_BEAR)
BEAR_DEFENSIVE_LONGS  = True
RSI_OVERSOLD_BEAR     = 30
KELLY_MULT_BEAR_LONG  = 0.25
BEAR_MAX_TRADE_BARS   = 10

# Strong bull tuning
TARGET_GAIN_PCT_STRONG_BULL  = 0.03   # Same 3% — mean-reversion exits stay early
MAX_TRADE_BARS_STRONG_BULL   = 30     # 6 weeks max in strong bull
MAX_POSITION_PCT_STRONG_BULL = 0.30   # 30% cap lets Kelly×1.5 deploy to 27% (was truncated at 20%)

# Soft 50-MA correction gate (0 = disabled; 0.05 = block if >5% below 50-MA)
STRONG_BULL_REQUIRE_50MA  = False
STRONG_BULL_SOFT_50MA_PCT = 0.0       # Set to 0.05 to filter extended corrections (June/Aug 2024)

# ADX sizing
ADX_PERIOD        = 14
ADX_WEAK_THRESH   = 20    # ADX < 20: Kelly × 0.8
ADX_STRONG_THRESH = 35    # ADX > 35: Kelly × 1.2
USE_ADX_SIZING    = True

# ATR dynamic stops (disabled — widen stop to 1×ATR when ATR > 2× 20-day median)
USE_ATR_DYNAMIC_STOPS = False
ATR_STOP_MULT         = 2.0
ATR_STOP_CAP_PCT      = 0.04

# Disabled features (guarded in code, kept for future activation)
USE_REGIME_FILTER    = False   # Vol-regime binary gate — too blunt
USE_MA_REGIME_FILTER = False   # Legacy binary gate — replaced by slope regime
BULL_BREAKOUT_ENABLED = False  # Momentum trap near ATH — tested, failed
VERBOSE_SIGNALS      = True

# Bear shorts (ONLY ACTIVE WHEN LONGS_ONLY=False — all code paths guarded)
RSI_OVERBOUGHT_BEAR          = 60
RSI_OVERBOUGHT_STRONG_BEAR   = 58
KELLY_MULT_BEAR_SHORT        = 0.5
KELLY_MULT_STRONG_BEAR_SHORT = 0.75
BEAR_SHORT_MAX_BARS          = 10
BEAR_SHORT_STOP_PCT          = 0.025
BREAKOUT_WINDOW              = 20
ADX_BREAKOUT_MIN             = 25

# Backtest window — daily
BACKTEST_START = "2020-01-01"
BACKTEST_END   = "2024-12-31"

# ═══════════════════════════════════════════════════════════════════════════
#  PROFILE 2 — BTC HOURLY
#  Goal:    Active income generation (~5–6%/month avg)
#  Style:   High-frequency mean-reversion on intraday bars
#  Sharpe:  2.4  |  Max DD: -0.39%  |  2yr return: 7.8%  |  ~116 trades/mo
#  Best for: accounts that want high monthly income, can handle lower WR (46%)
# ═══════════════════════════════════════════════════════════════════════════

RSI_PERIOD_HOURLY         = 7
RSI_OVERSOLD_HOURLY       = 40     # 35 too rare during bull runs; 40 fires consistently
RSI_OVERBOUGHT_HOURLY     = 60
MACD_FAST_HOURLY          = 6
MACD_SLOW_HOURLY          = 13
MACD_SIGNAL_HOURLY        = 4
ROC_PERIOD_HOURLY         = 5
VWAP_WINDOW_HOURLY        = 10
VWAP_ZSCORE_THRESH_HOURLY = 1.0    # Tighter threshold — hourly VWAP reverts faster
BB_WINDOW_HOURLY          = 14
USE_REGIME_FILTER_HOURLY  = False  # Regime too noisy on hourly bars

# Backtest window — hourly (yfinance max 730-day rolling window)
BACKTEST_START_HOURLY = "2024-03-01"
BACKTEST_END_HOURLY   = "2026-02-01"

# ═══════════════════════════════════════════════════════════════════════════
#  PROFILE 3 — QQQ (WORK IN PROGRESS)
#  Goal:    Equity-like returns with reduced drawdown vs passive index
#  Style:   Mean-reversion dip-buying in tech bull regimes
#  Status:  Params not yet optimized — needs walk-forward tuning
#  Note:    Lower volatility than BTC → tighter targets/stops, RSI higher
# ═══════════════════════════════════════════════════════════════════════════

# QQQ-specific signal params (to be refined via walk-forward optimizer)
RSI_OVERSOLD_QQQ       = 42     # QQQ dips are shallower — 42 vs BTC's 38
RSI_OVERBOUGHT_QQQ     = 58
TARGET_GAIN_PCT_QQQ    = 0.010  # 1% target — QQQ daily range is 0.5-2%, not 2-5%
STOP_LOSS_PCT_QQQ      = 0.006  # 0.6% stop (1.67:1 R:R)
VWAP_ZSCORE_THRESH_QQQ = 1.0   # ETF reverts faster than BTC
MAX_TRADE_BARS_QQQ     = 10    # Shorter hold — ETF dips tend to resolve faster

# Walk-forward optimizer note: QQQ daily generates ~5 trades/3yr OOS even at RSI<45
# — the regime classifier + QQQ's smooth bull trend creates structural signal scarcity.
# QQQ daily walk-forward is not viable; use QQQ_HOURLY instead.
# The optimizer uses DEFAULT_PARAM_GRID (in walk_forward.py) when this is unset.

# Backtest window — QQQ daily
BACKTEST_START_QQQ = "2020-01-01"
BACKTEST_END_QQQ   = "2024-12-31"

# ═══════════════════════════════════════════════════════════════════════════
#  PROFILE 4 — QQQ HOURLY (WORK IN PROGRESS)
#  Goal:    Equity-hours income stream (~2-4%/month target)
#  Style:   High-frequency mean-reversion during market hours only
#  Status:  Params not yet validated — needs backtest tuning
#  Note:    ~136 bars/month (6.5hr × 21 days) vs BTC hourly's 720/month
#           Smaller moves (0.05-0.15%/hr) but more orderly mean-reversion
# ═══════════════════════════════════════════════════════════════════════════

RSI_PERIOD_QQQ_HOURLY         = 7
RSI_OVERSOLD_QQQ_HOURLY       = 40    # QQQ hourly — less volatile than BTC, 38 too rare intraday
RSI_OVERBOUGHT_QQQ_HOURLY     = 62
MACD_FAST_QQQ_HOURLY          = 6
MACD_SLOW_QQQ_HOURLY          = 13
MACD_SIGNAL_QQQ_HOURLY        = 4
VWAP_WINDOW_QQQ_HOURLY        = 10
VWAP_ZSCORE_THRESH_QQQ_HOURLY = 0.8   # Tighter — QQQ VWAP deviations are smaller
BB_WINDOW_QQQ_HOURLY          = 14

# Backtest window — QQQ hourly (yfinance max 730-day rolling window from today)
# Note: equity ETFs enforce the 730-day limit more strictly than crypto
# 2024-04-01 → 2026-03-01 gives ~23 months safely within the window
BACKTEST_START_QQQ_HOURLY = "2024-04-01"
BACKTEST_END_QQQ_HOURLY   = "2026-03-01"

# ═══════════════════════════════════════════════════════════════════════════
#  SHARED — Risk & Sizing (applies to all modes)
# ═══════════════════════════════════════════════════════════════════════════
INITIAL_CAPITAL  = 100_000
KELLY_MULTIPLIER = 0.5       # Half-Kelly — reduces variance vs full Kelly
MAX_POSITION_PCT = 0.20      # Never risk more than 20% per trade
MIN_POSITION_PCT = 0.02      # Floor: deploy at least 2% when Kelly sample is thin
PLOT_RESULTS     = True

# ═══════════════════════════════════════════════════════════════════════════
#  ASSET ROUTING — maps ACTIVE_MODE to engine config (do not edit)
# ═══════════════════════════════════════════════════════════════════════════
ASSETS = {
    "BTC": {
        "type":               "crypto",
        "market":             "USD",
        "rsi_oversold":       RSI_OVERSOLD,
        "rsi_overbought":     RSI_OVERBOUGHT,
        "target_gain_pct":    TARGET_GAIN_PCT,
        "stop_loss_pct":      STOP_LOSS_PCT,
        "require_signals":    REQUIRE_SIGNALS,
        "vwap_zscore_thresh": VWAP_ZSCORE_THRESH,
    },
    "BTC_HOURLY": {
        "type":               "crypto_hourly",
        "target_gain_pct":    0.004,    # 0.4% per trade on hourly bars
        "stop_loss_pct":      0.0025,   # 0.25% stop
        "require_signals":    1,
        "rsi_oversold":       RSI_OVERSOLD_HOURLY,
        "rsi_overbought":     RSI_OVERBOUGHT_HOURLY,
        "vwap_zscore_thresh": VWAP_ZSCORE_THRESH_HOURLY,
    },
    "QQQ": {
        "type":               "etf",
        "rsi_oversold":       RSI_OVERSOLD_QQQ,
        "rsi_overbought":     RSI_OVERBOUGHT_QQQ,
        "target_gain_pct":    TARGET_GAIN_PCT_QQQ,
        "stop_loss_pct":      STOP_LOSS_PCT_QQQ,
        "require_signals":    1,
        "vwap_zscore_thresh": VWAP_ZSCORE_THRESH_QQQ,
    },
    "QQQ_HOURLY": {
        "type":               "etf_hourly",
        "target_gain_pct":    0.0015,   # 0.15% per trade — QQQ hourly range is 0.1-0.3%
        "stop_loss_pct":      0.0008,   # 0.08% stop (1.875:1 R:R)
        "require_signals":    1,
        "rsi_oversold":       RSI_OVERSOLD_QQQ_HOURLY,
        "rsi_overbought":     RSI_OVERBOUGHT_QQQ_HOURLY,
        "vwap_zscore_thresh": VWAP_ZSCORE_THRESH_QQQ_HOURLY,
    },
    "SOXL": {
        "type":               "etf",
        "rsi_oversold":       38,
        "rsi_overbought":     62,
        "target_gain_pct":    0.020,
        "stop_loss_pct":      0.012,
        "require_signals":    1,
        "vwap_zscore_thresh": 1.3,
    },
}

_MODE_TO_ASSET = {
    "BTC_DAILY":  "BTC",
    "BTC_HOURLY": "BTC_HOURLY",
    "QQQ":        "QQQ",
    "QQQ_HOURLY": "QQQ_HOURLY",
}
DEFAULT_ASSET = _MODE_TO_ASSET.get(ACTIVE_MODE, "BTC")
