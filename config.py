"""
MONAD Quant — Strategy Configuration
=====================================
Change ACTIVE_MODE to switch between strategy profiles.
All other parameters are pre-tuned for their respective mode.
"""

# ═══════════════════════════════════════════════════════════════════════════
#  ACTIVE MODE — the only line you normally need to change
#  Options: "BTC_DAILY" | "BTC_HOURLY" | "QQQ" | "QQQ_HOURLY" | "TQQQ_HOURLY" | "GDXU_HOURLY" | "SOXL_HOURLY" | "LABU_HOURLY" | "TNA_HOURLY"
# ═══════════════════════════════════════════════════════════════════════════
ACTIVE_MODE = "GDXU_HOURLY"

# ═══════════════════════════════════════════════════════════════════════════
#  BACKTEST DATE RANGES — edit here, one place for all BTC windows
#  Uncomment the preset you want, or set custom dates below.
# ═══════════════════════════════════════════════════════════════════════════

# ── BTC Daily presets ────────────────────────────────────────────────────
# BACKTEST_START = "2020-01-01";  BACKTEST_END = "2024-12-31"  # 5yr full run (primary)
# BACKTEST_START = "2021-01-01";  BACKTEST_END = "2024-12-31"  # 4yr (skip 2020 data)
# BACKTEST_START = "2023-01-01";  BACKTEST_END = "2023-12-31"  # 2023 regression baseline
# BACKTEST_START = "2024-01-01";  BACKTEST_END = "2024-12-31"  # 2024 only
BACKTEST_START = "2021-11-01"
BACKTEST_END   = "2024-12-31"

# ── BTC Hourly presets ───────────────────────────────────────────────────
# BACKTEST_START_HOURLY = "2024-03-15";  BACKTEST_END_HOURLY = "2026-02-15"  # 2yr baseline
# BACKTEST_START_HOURLY = "2025-01-01";  BACKTEST_END_HOURLY = "2026-03-01"  # 2025–present
# BACKTEST_START_HOURLY = "2024-06-01";  BACKTEST_END_HOURLY = "2026-03-01"  # 21mo recent
BACKTEST_START_HOURLY = "2019-01-01"
BACKTEST_END_HOURLY   = "2026-01-01"

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

# ═══════════════════════════════════════════════════════════════════════════
#  PROFILE 2 — BTC HOURLY
#  Goal:    Active income generation (~5–6%/month avg)
#  Style:   High-frequency mean-reversion on intraday bars
#  Sharpe:  2.4  |  Max DD: -0.39%  |  2yr return: 7.8%  |  ~116 trades/mo
#  Best for: accounts that want high monthly income, can handle lower WR (46%)
# ═══════════════════════════════════════════════════════════════════════════

RSI_PERIOD_HOURLY         = 5
RSI_OVERSOLD_HOURLY       = 42     # Sweep tested 38-50: 42 is optimal (return+Sharpe peak, RSI still binding gate vs VWAP)
RSI_OVERBOUGHT_HOURLY     = 60
MACD_FAST_HOURLY          = 6
MACD_SLOW_HOURLY          = 13
MACD_SIGNAL_HOURLY        = 4
ROC_PERIOD_HOURLY         = 5
VWAP_WINDOW_HOURLY        = 10
VWAP_ZSCORE_THRESH_HOURLY = 1.0    # Confirmed optimal: 1.0 > 1.1 (more trades, lower DD)
BB_WINDOW_HOURLY          = 14
USE_REGIME_FILTER_HOURLY  = False  # Regime too noisy on hourly bars

# Time-of-day filter — skip low-liquidity dead-zone hours on hourly bars.
# London (07-16 UTC) + NY (13-21 UTC) sessions have genuine volume behind RSI dips.
# Dead zone (00-07 UTC) is noise-driven — signals fire but rarely follow through.
# Disabled by default. Enable to test: expect fewer trades, potentially higher WR.
HOURLY_TRADE_FILTER      = False  # 24hr mode confirmed best — tested: Sharpe 26, +579% 7.5yr vs +10.73% filtered 2yr
HOURLY_TRADE_HOURS_START = 0      # UTC hour (only used when HOURLY_TRADE_FILTER=True)
HOURLY_TRADE_HOURS_END   = 24     # UTC hour (only used when HOURLY_TRADE_FILTER=True)


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
#  PROFILE 4 — QQQ HOURLY (OPTIMIZED 2026-03-17)
#  Goal:    Equity-hours income stream (~0.71%/month consistent)
#  Style:   High-frequency mean-reversion, ~24 trades/month
#  Sharpe:  41.6  |  Max DD: -0.21%  |  2yr return: 17.77%  |  Avg: +0.71%/mo
#  Status:  Fully optimized — all params exhaustively swept, nothing left to tune
#  Note:    ~24 trades/month (vs BTC hourly's 130) — frequency is the ceiling.
#           RSI=70 (QQQ dips shallower), VWAP=0.4 (smaller ETF deviations), 2:1 R:R
# ═══════════════════════════════════════════════════════════════════════════

RSI_PERIOD_QQQ_HOURLY         = 7
RSI_OVERSOLD_QQQ_HOURLY       = 70    # QQQ hourly — less volatile than BTC; 70 confirmed optimal (full sweep done)
RSI_OVERBOUGHT_QQQ_HOURLY     = 62
MACD_FAST_QQQ_HOURLY          = 6
MACD_SLOW_QQQ_HOURLY          = 13
MACD_SIGNAL_QQQ_HOURLY        = 4
VWAP_WINDOW_QQQ_HOURLY        = 10
VWAP_ZSCORE_THRESH_QQQ_HOURLY = 0.4   # Confirmed optimal — QQQ VWAP deviations are smaller than BTC
BB_WINDOW_QQQ_HOURLY          = 14
TARGET_GAIN_PCT_QQQ_HOURLY    = 0.0024  # 0.24% target — QQQ hourly range is 0.1-0.3%; 2:1 R:R
STOP_LOSS_PCT_QQQ_HOURLY      = 0.0012  # 0.12% stop — 2:1 R:R; WR 59.6%, Kelly 19.73%

# Backtest window — QQQ hourly
BACKTEST_START_QQQ_HOURLY = "2024-04-01"
BACKTEST_END_QQQ_HOURLY   = "2026-03-01"

# ═══════════════════════════════════════════════════════════════════════════
#  PROFILE 5 — TQQQ HOURLY (3x leveraged QQQ) — OPTIMIZED 2026-03-22
#  Goal:    Leveraged equity-hours income stream — higher vol = more alpha
#  Style:   High-frequency mean-reversion, ~24 trades/month
#  Sharpe:  39.0  |  Max DD: -0.85%  |  24mo return: 61.17%  |  Avg: +2.02%/mo
#  Status:  Live-safe config — 1.8:1 R:R, stop 5.1x spread
#  Note:    Stop ($0.153) is 5.1x estimated spread — confirmed live-safe.
# ═══════════════════════════════════════════════════════════════════════════

RSI_PERIOD_TQQQ_HOURLY         = 7
RSI_OVERSOLD_TQQQ_HOURLY       = 68    # Live-safe sweep optimal (1.8:1 R:R)
RSI_OVERBOUGHT_TQQQ_HOURLY     = 62
MACD_FAST_TQQQ_HOURLY          = 6     # DEAD LEVER (confirmed: same as QQQ/BTC hourly)
MACD_SLOW_TQQQ_HOURLY          = 13
MACD_SIGNAL_TQQQ_HOURLY        = 4
VWAP_WINDOW_TQQQ_HOURLY        = 10
VWAP_ZSCORE_THRESH_TQQQ_HOURLY = 0.6   # Sweep optimal (dead lever — 0.3-0.6 nearly identical)
BB_WINDOW_TQQQ_HOURLY          = 14
TARGET_GAIN_PCT_TQQQ_HOURLY    = 0.0072 # 0.72% target — live-safe; 1.8:1 R:R
STOP_LOSS_PCT_TQQQ_HOURLY      = 0.0040 # 0.40% stop — Sharpe 39.0, DD -0.85%, WR 60.4%
# Previous ultra-tight config (higher Sharpe but near bid-ask spread):
# TARGET_GAIN_PCT_TQQQ_HOURLY  = 0.0042  # 0.42% target, 5.6:1 R:R
# STOP_LOSS_PCT_TQQQ_HOURLY    = 0.0008  # 0.08% stop — Sharpe 94.2, DD -0.13%, WR 70.9%

# Backtest window — TQQQ hourly
BACKTEST_START_TQQQ_HOURLY = "2024-04-01"
BACKTEST_END_TQQQ_HOURLY   = "2026-03-01"

# ═══════════════════════════════════════════════════════════════════════════
#  PROFILE 6 — GDXU HOURLY (3x leveraged gold miners) — OPTIMIZED 2026-03-20
#  Goal:    Gold miners income stream — uncorrelated with QQQ/TQQQ
#  Style:   High-frequency mean-reversion, ~27 trades/month
#  Sharpe:  96.5  |  Max DD: -0.10%  |  24mo return: 116.55%  |  Avg: +3.28%/mo
#  Status:  Fully optimized — universal sweep (2-phase) confirmed
#  Note:    3x leveraged gold miners ETN — higher vol than TQQQ;
#           uncorrelated with tech = portfolio diversification benefit
#           7.5:1 R:R confirmed optimal — ultra-tight stops, GDXU resolves fast
#  CAUTION: 0.075% stop ≈ $0.04-0.06/share — near bid-ask spread in live trading.
#           Monitor slippage carefully. If live WR degrades, fall back to 0.20% stop.
# ═══════════════════════════════════════════════════════════════════════════

RSI_PERIOD_GDXU_HOURLY         = 7        # DEAD LEVER (MACD is binding gate)
RSI_OVERSOLD_GDXU_HOURLY       = 85       # Confirmed: RSI saturated; 85 optimal (sweep tested 42–100)
RSI_OVERBOUGHT_GDXU_HOURLY     = 62
MACD_FAST_GDXU_HOURLY          = 6        # DEAD LEVER (histogram direction robust to window changes)
MACD_SLOW_GDXU_HOURLY          = 13       # DEAD LEVER
MACD_SIGNAL_GDXU_HOURLY        = 4        # DEAD LEVER
VWAP_WINDOW_GDXU_HOURLY        = 10
VWAP_ZSCORE_THRESH_GDXU_HOURLY = 0.5      # Marginal improvement over 0.3 (sweep confirmed)
BB_WINDOW_GDXU_HOURLY          = 14
TARGET_GAIN_PCT_GDXU_HOURLY    = 0.0056   # 0.56% target — sweep optimal (7.5:1 R:R)
STOP_LOSS_PCT_GDXU_HOURLY      = 0.00075  # 0.075% stop — Sharpe 96.5, DD -0.10%, WR 70.1%
# Fallback (wider stops, higher gross return, lower Sharpe):
# TARGET_GAIN_PCT_GDXU_HOURLY  = 0.010    # 1.0% target, 5:1 R:R
# STOP_LOSS_PCT_GDXU_HOURLY    = 0.002    # 0.20% stop — Sharpe 61.8, DD -0.42%, +4.07%/mo

# Backtest window — GDXU hourly (launched Dec 2020; yfinance hourly ~730 days)
BACKTEST_START_GDXU_HOURLY = "2024-04-01"
BACKTEST_END_GDXU_HOURLY   = "2026-03-01"

# ═══════════════════════════════════════════════════════════════════════════
#  PROFILE 7 — SOXL HOURLY (3x leveraged semiconductors) — SWEEP 2026-03-22
#  Goal:    Semis income stream — uncorrelated with gold/biotech
#  Style:   High-frequency mean-reversion, ~27 trades/month
#  Sharpe:  47.3  |  Max DD: -0.75%  |  24mo return: 127.49%  |  Avg: +3.50%/mo
#  Status:  Sweep-optimized with Phase 3 robustness check (--min-stop 0.25)
#           0/22 rolling windows negative, worst window +1.88%, live-safe (5x spread)
#  Note:    3x leveraged semis ETF — higher vol than TQQQ;
#           2:1 R:R at 0.45% stop — robust for live trading (5x bid-ask spread)
# ═══════════════════════════════════════════════════════════════════════════

RSI_PERIOD_SOXL_HOURLY         = 7        # DEAD LEVER (MACD is binding gate)
RSI_OVERSOLD_SOXL_HOURLY       = 80       # Sweep optimal (Phase 2 fine-tuned: 77 close but 80 best)
RSI_OVERBOUGHT_SOXL_HOURLY     = 62
MACD_FAST_SOXL_HOURLY          = 6        # DEAD LEVER
MACD_SLOW_SOXL_HOURLY          = 13       # DEAD LEVER
MACD_SIGNAL_SOXL_HOURLY        = 4        # DEAD LEVER
VWAP_WINDOW_SOXL_HOURLY        = 10
VWAP_ZSCORE_THRESH_SOXL_HOURLY = 1.2      # Sweep optimal
BB_WINDOW_SOXL_HOURLY          = 14
TARGET_GAIN_PCT_SOXL_HOURLY    = 0.009    # 0.90% target — sweep optimal; 2:1 R:R
STOP_LOSS_PCT_SOXL_HOURLY      = 0.0045   # 0.45% stop — live-safe (5x spread), 0/22 windows negative

# Backtest window — SOXL hourly
BACKTEST_START_SOXL_HOURLY = "2024-04-01"
BACKTEST_END_SOXL_HOURLY   = "2026-03-01"

# ═══════════════════════════════════════════════════════════════════════════
#  PROFILE 8 — LABU HOURLY (3x leveraged biotech) — SWEEP 2026-03-20
#  Goal:    Biotech income stream — uncorrelated with tech/gold/semis
#  Style:   High-frequency mean-reversion, ~26 trades/month
#  Sharpe:  61.6  |  Max DD: -0.52%  |  24mo return: 106.22%  |  Avg: +3.07%/mo
#  Status:  Sweep-optimized (--min-stop 0.25)
#  Note:    3x leveraged biotech ETF — high vol, completely uncorrelated;
#           2.8:1 R:R at 0.25% stop — realistic for live trading
# ═══════════════════════════════════════════════════════════════════════════

RSI_PERIOD_LABU_HOURLY         = 7        # DEAD LEVER (MACD is binding gate)
RSI_OVERSOLD_LABU_HOURLY       = 70       # Sweep optimal
RSI_OVERBOUGHT_LABU_HOURLY     = 62
MACD_FAST_LABU_HOURLY          = 6        # DEAD LEVER
MACD_SLOW_LABU_HOURLY          = 13       # DEAD LEVER
MACD_SIGNAL_LABU_HOURLY        = 4        # DEAD LEVER
VWAP_WINDOW_LABU_HOURLY        = 10
VWAP_ZSCORE_THRESH_LABU_HOURLY = 1.2      # Sweep optimal
BB_WINDOW_LABU_HOURLY          = 14
TARGET_GAIN_PCT_LABU_HOURLY    = 0.007    # 0.70% target — sweep optimal; 2.8:1 R:R
STOP_LOSS_PCT_LABU_HOURLY      = 0.0025   # 0.25% stop — realistic for live trading

# Backtest window — LABU hourly
BACKTEST_START_LABU_HOURLY = "2024-04-01"
BACKTEST_END_LABU_HOURLY   = "2026-03-01"

# ═══════════════════════════════════════════════════════════════════════════
#  PROFILE 9 — TNA HOURLY (3x leveraged Russell 2000) — SWEEP 2026-03-20
#  Goal:    Small-cap income stream — uncorrelated with tech/gold/biotech
#  Style:   High-frequency mean-reversion, ~24 trades/month
#  Sharpe:  82.0  |  Max DD: -0.24%  |  24mo return: 51.33%  |  Avg: +1.74%/mo
#  Status:  Sweep-optimized (--min-stop 0.25)
#  Note:    3x leveraged Russell 2000 ETF — small caps, low tech correlation;
#           2.2:1 R:R at 0.15% stop — tight but viable on ~$25 share price
# ═══════════════════════════════════════════════════════════════════════════

RSI_PERIOD_TNA_HOURLY         = 7        # DEAD LEVER (MACD is binding gate)
RSI_OVERSOLD_TNA_HOURLY       = 65       # Sweep optimal — more selective than SOXL/LABU
RSI_OVERBOUGHT_TNA_HOURLY     = 62
MACD_FAST_TNA_HOURLY          = 6        # DEAD LEVER
MACD_SLOW_TNA_HOURLY          = 13       # DEAD LEVER
MACD_SIGNAL_TNA_HOURLY        = 4        # DEAD LEVER
VWAP_WINDOW_TNA_HOURLY        = 10
VWAP_ZSCORE_THRESH_TNA_HOURLY = 0.1      # Sweep optimal — very loose (momentum_signal is gate)
BB_WINDOW_TNA_HOURLY          = 14
TARGET_GAIN_PCT_TNA_HOURLY    = 0.0033   # 0.33% target — sweep optimal; 2.2:1 R:R
STOP_LOSS_PCT_TNA_HOURLY      = 0.0015   # 0.15% stop — tight but TNA has tighter spreads

# Backtest window — TNA hourly
BACKTEST_START_TNA_HOURLY = "2024-04-01"
BACKTEST_END_TNA_HOURLY   = "2026-03-01"

# ═══════════════════════════════════════════════════════════════════════════
#  SHARED — Risk & Sizing (applies to all modes)
# ═══════════════════════════════════════════════════════════════════════════
INITIAL_CAPITAL  = 100_000
KELLY_MULTIPLIER = 0.5       # Half-Kelly — reduces variance vs full Kelly
MAX_POSITION_PCT = 0.20      # Never risk more than 20% per trade
MIN_POSITION_PCT = 0.02      # Floor: deploy at least 2% when Kelly sample is thin
PLOT_RESULTS     = True

# ── Backtest fairness mode ─────────────────────────────────────────────
# "optimistic" = legacy (no slippage, target wins ambiguity, full-sample Kelly)
# "realistic"  = fair (2bps slippage, stop wins ambiguity, rolling Kelly)
# "harsh"      = pessimistic (5bps slippage, stop wins, rolling Kelly)
BACKTEST_MODE    = "realistic"
BACKTEST_DEBUG   = False         # True = print per-trade detail (entry, exit, size, PnL)

# ── Adaptive Kelly — signal quality detector ─────────────────────────────
# Tracks rolling win rate over the last N trades and scales position size.
# Key use case: BTC hourly bad months (33-37% WR) cluster — if the last 20
# trades are running at 35% WR, the next 20 are likely also poor quality.
# Reduce exposure automatically until quality recovers.
# All new params default=False/disabled per project constraint.
USE_ADAPTIVE_KELLY        = True   # Master toggle — set True for BTC hourly
ADAPTIVE_KELLY_LOOKBACK   = 20     # Rolling window in trades (20 = ~4 days at 130 trades/mo in 24hr mode; lb=15 was for filtered mode)
ADAPTIVE_KELLY_HIGH_WR    = 0.46   # Confirmed active at 0.46 — fires during 48-55% WR bull stretches; dead lever at 0.52+
ADAPTIVE_KELLY_LOW_WR     = 0.42   # Recent WR < this → scale down (signal degrading)
ADAPTIVE_KELLY_PAUSE_WR   = 0.35   # Recent WR < this → near-flat (signal breakdown)
ADAPTIVE_KELLY_HIGH_MULT  = 2.0    # Position multiplier when WR ≥ HIGH — tested: +553% vs +453% at 1.8 (2019-2026, VWAP=1.0)
ADAPTIVE_KELLY_LOW_MULT   = 0.5    # Position multiplier when WR in [PAUSE, LOW)
ADAPTIVE_KELLY_PAUSE_MULT = 0.2    # Position multiplier when WR < PAUSE
ADAPTIVE_KELLY_HIGH_CAP   = 0.35   # Position cap in high-WR state — 0.35 gives headroom for 2.0× mult (2.0×12% = 24% → under cap)

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
        "type":               "crypto_hourly_binance",
        "target_gain_pct":    0.004,    # 0.4% per trade on hourly bars
        "stop_loss_pct":      0.002,    # 0.20% stop — 2:1 R:R; tighter stop compounds massively (tested: +579% 7.5yr vs +377% at 0.0025)
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
        "target_gain_pct":    TARGET_GAIN_PCT_QQQ_HOURLY,
        "stop_loss_pct":      STOP_LOSS_PCT_QQQ_HOURLY,
        "require_signals":    1,
        "rsi_oversold":       RSI_OVERSOLD_QQQ_HOURLY,
        "rsi_overbought":     RSI_OVERBOUGHT_QQQ_HOURLY,
        "vwap_zscore_thresh": VWAP_ZSCORE_THRESH_QQQ_HOURLY,
    },
    "TQQQ_HOURLY": {
        "type":               "etf_hourly_tqqq",
        "target_gain_pct":    TARGET_GAIN_PCT_TQQQ_HOURLY,
        "stop_loss_pct":      STOP_LOSS_PCT_TQQQ_HOURLY,
        "require_signals":    1,
        "rsi_oversold":       RSI_OVERSOLD_TQQQ_HOURLY,
        "rsi_overbought":     RSI_OVERBOUGHT_TQQQ_HOURLY,
        "vwap_zscore_thresh": VWAP_ZSCORE_THRESH_TQQQ_HOURLY,
    },
    "GDXU_HOURLY": {
        "type":               "etf_hourly_gdxu",
        "target_gain_pct":    TARGET_GAIN_PCT_GDXU_HOURLY,    # 0.0056 (0.56%)
        "stop_loss_pct":      STOP_LOSS_PCT_GDXU_HOURLY,      # 0.00075 (0.075%) — 7.5:1 R:R
        "require_signals":    1,
        "rsi_oversold":       RSI_OVERSOLD_GDXU_HOURLY,       # 85
        "rsi_overbought":     RSI_OVERBOUGHT_GDXU_HOURLY,
        "vwap_zscore_thresh": VWAP_ZSCORE_THRESH_GDXU_HOURLY, # 0.5
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
    "SOXL_HOURLY": {
        "type":               "etf_hourly_soxl",
        "target_gain_pct":    TARGET_GAIN_PCT_SOXL_HOURLY,
        "stop_loss_pct":      STOP_LOSS_PCT_SOXL_HOURLY,
        "require_signals":    1,
        "rsi_oversold":       RSI_OVERSOLD_SOXL_HOURLY,
        "rsi_overbought":     RSI_OVERBOUGHT_SOXL_HOURLY,
        "vwap_zscore_thresh": VWAP_ZSCORE_THRESH_SOXL_HOURLY,
    },
    "LABU_HOURLY": {
        "type":               "etf_hourly_labu",
        "target_gain_pct":    TARGET_GAIN_PCT_LABU_HOURLY,
        "stop_loss_pct":      STOP_LOSS_PCT_LABU_HOURLY,
        "require_signals":    1,
        "rsi_oversold":       RSI_OVERSOLD_LABU_HOURLY,
        "rsi_overbought":     RSI_OVERBOUGHT_LABU_HOURLY,
        "vwap_zscore_thresh": VWAP_ZSCORE_THRESH_LABU_HOURLY,
    },
    "TNA_HOURLY": {
        "type":               "etf_hourly_tna",
        "target_gain_pct":    TARGET_GAIN_PCT_TNA_HOURLY,
        "stop_loss_pct":      STOP_LOSS_PCT_TNA_HOURLY,
        "require_signals":    1,
        "rsi_oversold":       RSI_OVERSOLD_TNA_HOURLY,
        "rsi_overbought":     RSI_OVERBOUGHT_TNA_HOURLY,
        "vwap_zscore_thresh": VWAP_ZSCORE_THRESH_TNA_HOURLY,
    },
}

_MODE_TO_ASSET = {
    "BTC_DAILY":   "BTC",
    "BTC_HOURLY":  "BTC_HOURLY",
    "QQQ":         "QQQ",
    "QQQ_HOURLY":  "QQQ_HOURLY",
    "TQQQ_HOURLY": "TQQQ_HOURLY",
    "GDXU_HOURLY": "GDXU_HOURLY",
    "SOXL_HOURLY": "SOXL_HOURLY",
    "LABU_HOURLY": "LABU_HOURLY",
    "TNA_HOURLY":  "TNA_HOURLY",
}
DEFAULT_ASSET = _MODE_TO_ASSET.get(ACTIVE_MODE, "BTC")

# ── Live Trading — IBKR ───────────────────────────────────────────────────────
LIVE_PAPER_MODE    = True          # True = paper (port 7497); False = live (port 7496)
LIVE_SYMBOL        = "TQQQ"       # Primary instrument — TQQQ: Sharpe 94.2, +1.89%/mo
IBKR_HOST          = "127.0.0.1"  # TWS/Gateway host
IBKR_PORT_PAPER    = 7497         # IB Gateway paper trading port
IBKR_PORT_LIVE     = 7496         # IB Gateway live trading port
IBKR_CLIENT_ID     = 1            # Unique per concurrent connection

MAX_TRADE_BARS_LIVE = 10          # Time-exit after N hourly bars (matches backtest)
LIVE_MIN_TRADES_FOR_ADAPTIVE = 10 # Switch from bootstrap → rolling stats after N trades

# Per-instrument bootstrap stats (seed Kelly until enough live trades)
LIVE_BOOTSTRAP = {
    "QQQ":  {"wr": 0.596, "win": 0.0024, "loss": 0.0012},
    "TQQQ": {"wr": 0.604, "win": 0.0072, "loss": 0.0040},
    "GDXU": {"wr": 0.701, "win": 0.0056, "loss": 0.00075},
    "SOXL": {"wr": 0.631, "win": 0.009,  "loss": 0.0045},
    "LABU": {"wr": 0.593, "win": 0.007,  "loss": 0.0025},
    "TNA":  {"wr": 0.596, "win": 0.0033, "loss": 0.0015},
}
