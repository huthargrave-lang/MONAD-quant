"""
config_modules/base.py — Shared risk, sizing, and backtest settings.

These parameters apply across all modes. Imported by the top-level config.py.
"""

# ═══════════════════════════════════════════════════════════════════════════
#  SHARED — Risk & Sizing (applies to all modes)
# ═══════════════════════════════════════════════════════════════════════════
INITIAL_CAPITAL  = 100_000
KELLY_MULTIPLIER = 0.5       # Half-Kelly — reduces variance vs full Kelly
MAX_POSITION_PCT = 0.20      # Never risk more than 20% per trade
MIN_POSITION_PCT = 0.02      # Floor: deploy at least 2% when Kelly sample is thin
PLOT_RESULTS     = True

# ── Backtest fairness mode ─────────────────────────────────────────
# "optimistic" = legacy (no slippage, target wins ambiguity, full-sample Kelly)
# "realistic"  = fair (2bps slippage, stop wins ambiguity, rolling Kelly)
# "harsh"      = pessimistic (5bps slippage, stop wins, rolling Kelly)
BACKTEST_MODE    = "realistic"
BACKTEST_DEBUG   = False

# ── Position Sizing Mode ───────────────────────────────────────────
POSITION_SIZING_MODE = "fixed"
FIXED_POSITION_PCT   = 0.10
KELLY_CLAMP_MIN      = 0.02
KELLY_CLAMP_MAX      = 0.10

# ── Adaptive Kelly ─────────────────────────────────────────────────
USE_ADAPTIVE_KELLY        = True
ADAPTIVE_KELLY_LOOKBACK   = 20
ADAPTIVE_KELLY_HIGH_WR    = 0.46
ADAPTIVE_KELLY_LOW_WR     = 0.42
ADAPTIVE_KELLY_PAUSE_WR   = 0.35
ADAPTIVE_KELLY_HIGH_MULT  = 2.0
ADAPTIVE_KELLY_LOW_MULT   = 0.5
ADAPTIVE_KELLY_PAUSE_MULT = 0.2
ADAPTIVE_KELLY_HIGH_CAP   = 0.35
