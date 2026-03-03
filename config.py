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
        "target_gain_pct": 0.030,
        "stop_loss_pct": 0.015,
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

DEFAULT_ASSET = "BTC"

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
REQUIRE_SIGNALS      = 1        # Minimum signals to agree for entry (1-3)
TARGET_GAIN_PCT      = 0.030    # 3.0% take profit (BTC daily ATR is 2-5%, 1.5% was within noise)
STOP_LOSS_PCT        = 0.015    # 1.5% stop loss  (2:1 R:R vs old 1.5:1)
MAX_TRADE_BARS       = 20       # Bars to hold before closing at market (4 trading weeks)
USE_REGIME_FILTER    = False    # Vol-regime binary gate — too blunt for trending periods; MA filter handles regime
MA_REGIME_WINDOW     = 252      # 52-week MA lookback (trading days)
USE_MA_REGIME_FILTER = False    # Legacy binary gate — disabled, replaced by slope regime below
VERBOSE_SIGNALS      = True     # Print per-filter bar counts before each backtest

# ── MA Slope Regime ──────────────────────────────────────────────────────────
# 6-state slope-based classifier (replaces the binary USE_MA_REGIME_FILTER gate).
# Regimes: STRONG_BULL / BULL / STALLING / RECOVERING / BEAR / STRONG_BEAR
# Direction constrained per regime; Kelly scaled continuously per trade.
USE_SLOPE_REGIME      = True    # Enable slope-based regime (replaces USE_MA_REGIME_FILTER)
LONGS_ONLY            = True    # Sit flat in BEAR/STRONG_BEAR — capital preservation IS the bear alpha
MA_SLOPE_WINDOW       = 20      # Bars over which to measure MA slope
MA_SHORT_WINDOW       = 50      # 50-day MA — RECOVERING fires when price crosses above this
MA_STRONG_BULL_SLOPE  = 0.02    # MA rises >2% over slope window → STRONG_BULL
MA_STRONG_BEAR_SLOPE  = -0.02   # MA falls >2% over slope window → STRONG_BEAR

# Per-regime Kelly multipliers (applied per-trade in runner.py)
KELLY_MULT_STRONG_BULL = 1.5    # Trend accelerating up — size up
KELLY_MULT_BULL        = 1.0    # Trend steady upward — base Kelly
KELLY_MULT_STALLING    = 0.75   # Above MA but MA rolling over — cautious, both directions
KELLY_MULT_RECOVERING  = 0.75   # Below MA but price rising — longs only, cautious
KELLY_MULT_BEAR        = 0.75   # Trend declining — base for shorts (defensive longs use KELLY_MULT_BEAR_LONG)
KELLY_MULT_STRONG_BEAR = 0.5    # Trend accelerating down — size down, sit flat in longs_only

# ── Bear Market Defensive Longs ──────────────────────────────────────────────
# In BEAR regime (mild downtrend, not STRONG_BEAR), allow very small long entries
# when RSI is deeply oversold. These capture bear-market bounces (+20-30% in 2022)
# without fighting a confirmed downtrend. STRONG_BEAR stays completely flat for longs.
BEAR_DEFENSIVE_LONGS  = True   # Allow longs in BEAR regime (True/False to toggle)
RSI_OVERSOLD_BEAR     = 30     # Deeply oversold only — much tighter than bull threshold (38)
KELLY_MULT_BEAR_LONG  = 0.25   # Quarter-Kelly — capital preservation, not full sizing
BEAR_MAX_TRADE_BARS   = 10     # Exit in 2 weeks — don't hold into a deepening downtrend

# ── Bear Market Shorts (rally fading) ────────────────────────────────────────
# In BEAR/STRONG_BEAR, dead-cat bounces push RSI to 60-70 before reversing.
# Short when RSI > threshold + MACD hist turning down — fade the rally.
# Threshold is lower than the standard overbought (62) since bears suppress RSI peaks.
RSI_OVERBOUGHT_BEAR        = 60    # Bear rally exhaustion — lower than standard 62
RSI_OVERBOUGHT_STRONG_BEAR = 58    # Even lower in accelerating downtrend
KELLY_MULT_BEAR_SHORT      = 0.5   # Half-Kelly — shorts in bears are volatile
KELLY_MULT_STRONG_BEAR_SHORT = 0.75 # More conviction in confirmed strong bear
BEAR_SHORT_MAX_BARS        = 10    # Quick exit — don't hold short into sudden reversal
BEAR_SHORT_STOP_PCT        = 0.025 # 2.5% stop for shorts — crypto swings 3-5% intraday, 1.5% is noise

# ── Bull Breakout Signal (Phase B) ───────────────────────────────────────────
# In STRONG_BULL, add a trend-following breakout entry alongside mean-reversion.
# Fires when price breaks 20-day high + ADX confirms trend strength + MACD bullish.
# This is a momentum signal — distinct from the RSI dip-buying mean-reversion signal.
BULL_BREAKOUT_ENABLED = False  # Disabled — fires too frequently at ATH in STRONG_BULL, momentum trap
BREAKOUT_WINDOW       = 20     # N-day high breakout confirmation window
ADX_BREAKOUT_MIN      = 25     # Minimum ADX trend strength for breakout entry

# ── Bull Market Participation ─────────────────────────────────────────────────
# In confirmed uptrends, dips are shallower so the RSI rarely drops to the
# neutral threshold (38). Looser thresholds + wider targets let the strategy
# participate in bull runs without touching bear/neutral behaviour.
# Walk-forward optimizer consistently selected RSI<40 in bull windows, RSI<30 in bears.
RSI_OVERSOLD_STRONG_BULL  = 42    # Looser — strong uptrend, shallower dips are buyable
RSI_OVERSOLD_BULL         = 40    # Slightly looser than neutral (38)
TARGET_GAIN_PCT_STRONG_BULL = 0.03  # Same 3% target — BTC daily ATR ~1.5-2%, 5% was too greedy
MAX_TRADE_BARS_STRONG_BULL  = 30    # Hold up to 6 weeks instead of 4 in strong bull

# ── ADX (Average Directional Index) ─────────────────────────────────────────
# Layered Kelly multiplier: trend strength independent of direction.
ADX_PERIOD        = 14
ADX_WEAK_THRESH   = 20    # ADX < 20: choppy/no trend → Kelly × 0.8
ADX_STRONG_THRESH = 35    # ADX > 35: strong trend    → Kelly × 1.2
USE_ADX_SIZING    = True  # Apply ADX multiplier to per-trade Kelly

# ── Risk & Sizing ───────────────────────────────────────────────────────────
INITIAL_CAPITAL   = 100_000
KELLY_MULTIPLIER  = 0.5      # Fractional Kelly (0.5 = half-Kelly)
MAX_POSITION_PCT  = 0.20     # Never risk more than 20% per trade
MIN_POSITION_PCT  = 0.02     # Floor: deploy at least 2% even when Kelly sample is thin

# ── Hourly Signal Parameters (BTC intraday) ─────────────────────────────────
RSI_PERIOD_HOURLY      = 7
RSI_OVERSOLD_HOURLY    = 40   # 35 is too rare on hourly BTC during bull runs
RSI_OVERBOUGHT_HOURLY  = 60
MACD_FAST_HOURLY       = 6
MACD_SLOW_HOURLY       = 13
MACD_SIGNAL_HOURLY     = 4
ROC_PERIOD_HOURLY      = 5
VWAP_WINDOW_HOURLY     = 10
VWAP_ZSCORE_THRESH_HOURLY = 1.0  # passed to volume signal (was defaulting to 1.5)
BB_WINDOW_HOURLY       = 14
USE_REGIME_FILTER_HOURLY = False  # regime filter too noisy on hourly bars

# ── Backtest ────────────────────────────────────────────────────────────────
BACKTEST_START        = "2020-01-01"
BACKTEST_END          = "2024-12-31"
BACKTEST_START_HOURLY = "2024-03-01"   # yfinance: max 730 days rolling from today
BACKTEST_END_HOURLY   = "2026-02-01"
PLOT_RESULTS          = True
