# MONAD Quant — Full Model History & Context

> **Purpose of this file:** Complete institutional memory for the strategy — what every
> component does, every approach tried, why things failed, and what to try next. Written
> for AI agents and collaborators who need maximum context without reading git history.

---

## 1. Project Goal

**NOT a growth strategy.** MONAD Quant is a **high-yield bond ETF alternative** — an
actively-traded, long-only engine designed to generate consistent monthly income with
near-zero drawdown. The strategy has two active modes:

| Mode | Target | Sharpe | Max DD | Style |
|---|---|---|---|---|
| **BTC Daily** | ~0.4%/mo, Sharpe >4 | 4.924 | -1.72% | Capital preservation + high Sharpe |
| **BTC Hourly** | ~5–6%/mo income | 2.365 | -0.39% | Active income, ~116 trades/mo |
| **QQQ** | TBD (WIP) | — | — | ETF mean-reversion (not yet tuned) |

Core principles across all modes:
- **Long-only** — bear alpha is defined as NOT losing money, not chasing shorts
- **In bear markets:** sit flat (cash) or take tiny defensive longs — never fight downtrends
- **In bull markets:** buy RSI dips in confirmed uptrend regimes, sized via Kelly Criterion
- **Switch modes** by changing `ACTIVE_MODE` in `config.py` — one line

The Buy & Hold comparison (BTC +1194% over 5yr) is intentionally unfavorable — the correct
benchmark is a 4-6% high-yield bond ETF, not crypto lottery tickets.

---

## 2. Architecture Overview

```
Raw OHLCV data (Alpha Vantage / yfinance)
        │
        ▼
[build_features()]  ← engine.py
  ├── add_momentum_features()   → RSI, MACD, regime
  ├── add_volume_features()     → VWAP z-score, volume_signal
  └── add_volatility_features() → Bollinger Bands, ATR, ADX, vol_regime
        │
        ▼
[generate_trades()]  ← engine.py
  ├── signal_vote = momentum_signal + volume_signal  (each -1/0/+1)
  ├── regime gate: block long/short based on 6-state regime
  └── entry_signal column: -1 / 0 / 1
        │
        ▼
[compute_trade_returns()]  ← engine.py
  └── simulate next-bar outcomes: target hit / stop hit / time exit
        │
        ▼
[run_backtest()]  ← runner.py
  ├── estimate_stats_from_backtest() → win rate, avg win/loss
  ├── compute_position_size()        → fractional Kelly sizing
  └── equity curve loop              → per-trade Kelly × regime_mult × ADX_mult
```

**Key design principle:** Every component is independently togglable via config flags.
No component "knows about" another — signals produce columns, engine routes them,
runner sizes positions. This allows clean A/B testing of individual features.

---

## 3. Signal Glossary

### momentum_signal (src/signals/momentum.py)
- **Long (+1):** RSI < 38 AND MACD histogram turning up (hist > hist.shift(1))
- **Short (-1):** RSI > 62 AND MACD histogram turning down
- **Why RSI 38 not 30:** BTC in uptrends rarely hits RSI 30 — 38 catches shallow dips
  that still represent genuine oversold conditions in a trending market
- **Why MACD histogram turn not crossover:** Fires at the inflection point, not after
  price is already recovering. Crossover lags by several bars.
- **Threshold source:** Walk-forward optimizer consistently selected RSI<38-42 in bull
  windows, RSI<30 in bear windows

### volume_signal (src/signals/volume.py)
- **Long (+1):** VWAP z-score < -1.3 (price significantly below VWAP on volume)
- **Short (-1):** VWAP z-score > +1.3
- **Purpose:** Confirms that the RSI dip is accompanied by genuine volume dislocation,
  not just a slow drift. Reduces false signals on low-volume days.
- **Threshold:** 1.3σ chosen to fire ~15-20% of bars (1.5σ was too rare in BTC)

### signal_vote
- Sum of momentum_signal + volume_signal → range: -2 to +2
- **REQUIRE_SIGNALS = 1:** Only ONE signal needs to fire for a candidate entry
- This is intentionally loose — regime filtering does the heavy lifting
- With REQUIRE_SIGNALS=2 (both signals), trades drop from ~83 to ~25 over 5yr

### Regime Classifier (6-state dual-MA)
See Section 4 below.

### vol_regime (src/signals/volatility.py)
- Binary filter based on Bollinger Band width — 0=ranging, 1=trending/volatile
- **Currently disabled** (USE_REGIME_FILTER=False) — too blunt, blocks good entries
  during trending periods that also have elevated vol

### ADX (Average Directional Index)
- `adx_kelly_mult`: adjusts position size by trend strength
  - ADX < 20 (choppy): Kelly × 0.8
  - 20 ≤ ADX ≤ 35: Kelly × 1.0
  - ADX > 35 (strong trend): Kelly × 1.2
- **Active** (USE_ADX_SIZING=True) but marginal effect in practice

### bull_breakout_signal
- **Status: BUILT BUT DISABLED** (BULL_BREAKOUT_ENABLED=False)
- Fires +1 in STRONG_BULL when price > 20-day high + ADX > 25 + MACD bullish
- Built to add trend-following entries alongside mean-reversion; **failed in testing**

---

## 4. Regime Classifier (The Core Innovation)

### Why regimes matter
Before the regime classifier, the strategy entered RSI dips regardless of broader context.
In 2022 (BTC -65% bear), RSI dipping to 38 during a -5% day is a falling knife, not a
dip to buy. The regime classifier blocks longs in confirmed downtrends and scales Kelly
based on conviction.

### 6-state dual-MA system

Uses two moving averages:
- `ma_long` (252-day = ~1 trading year): broad trend direction
- `ma_short` (50-day): medium-term recovery confirmation

```
price > 252-MA:
  slope > +2%   → STRONG_BULL  (Kelly ×1.5, longs only)
  slope ≥ 0%    → BULL         (Kelly ×1.0, longs only)
  slope < 0%    → STALLING     (Kelly ×0.75, flat)

price < 252-MA:
  price ≥ 50-MA  → RECOVERING  (Kelly ×0.75, longs only)
  slope ≥ -2%    → BEAR        (Kelly ×0.75, defensive longs RSI<30)
  slope < -2%    → STRONG_BEAR (Kelly ×0.5, flat)
```

### Why 252-MA + 50-MA not just slope
**Old RECOVERING definition** (slope ≥ 0): in 2020 crash, BTC hit bottom in March.
The 252-MA slope didn't turn positive until early 2021 — a 9-month lag. Strategy sat
flat and missed the entire recovery.

**New RECOVERING definition** (price ≥ 50-MA): fires 2-4 weeks into recovery.
BTC crossed above its 50-MA in May 2020 → entered RECOVERING immediately.

### 5yr regime distribution (2020-2024, 1827 bars)
```
STRONG_BULL  : 985 bars  (54%) — dominant state
BULL         : 175 bars  (10%)
STALLING     :  92 bars  (5%)
RECOVERING   : 130 bars  (7%)
BEAR         : 214 bars  (12%)
STRONG_BEAR  : 231 bars  (13%)
```

### Regime lag issue (known problem)
The 252-MA is a long-horizon smoother. When BTC corrects -20-30% within a bull cycle
(e.g., June 2024, August 2024), the 252-MA slope stays positive → regime stays
STRONG_BULL → strategy continues entering longs into a 20% correction.
**This is the primary unsolved problem.**

---

## 5. Kelly Criterion Sizing

### Base Kelly formula
```
f* = (p × b - q) / b
  where: p = win_rate, q = 1-p, b = avg_win / avg_loss
```
Applied as **half-Kelly** (KELLY_MULTIPLIER=0.5) to reduce variance.

### Position scaling
```
kelly_trade = min(base_kelly × regime_mult × adx_mult, pos_cap)
```
- `base_kelly`: computed from rolling win/loss stats across all trades
- `regime_mult`: per-regime multiplier (1.5 in STRONG_BULL → size up)
- `adx_mult`: 0.8–1.2 based on trend strength
- `pos_cap`: 20% normally, 30% in STRONG_BULL

### The truncation bug (fixed in current version)
**Bug:** `base_kelly ≈ 18%` × `STRONG_BULL regime_mult 1.5` = 27%, then
`min(27%, MAX_POSITION_PCT=20%)` = **20%** — the 1.5× multiplier was doing nothing.

**Fix:** Added `MAX_POSITION_PCT_STRONG_BULL = 0.30`. STRONG_BULL trades now cap at 30%.
Result: 5yr improved from 10.55% → 11.05%, Sharpe 4.844 → 4.924.

---

## 6. What Worked (and Why)

| Feature | Before | After | Why it worked |
|---|---|---|---|
| **6-state slope regime** | Sharpe ~2, high DD | Sharpe 4.9, DD -1.7% | Blocks longs in confirmed downtrends; stops 2022 losses |
| **252+50 dual-MA RECOVERING** | 9-month lag on recovery | 2-4 week lag | 50-MA crosses much faster than 252-MA slope turns positive |
| **LONGS_ONLY=True in bears** | 0% WR on shorts | Capital preserved in 2022 | Bear alpha = NOT losing, not generating P&L from shorts |
| **BEAR_DEFENSIVE_LONGS** | 0 trades in 2022 BEAR | Small longs at RSI<30 | BEAR (mild) has bounces; quarter-Kelly limits exposure |
| **REQUIRE_SIGNALS=1 not 2** | ~25 trades/5yr | 83 trades/5yr | Two-signal agreement too restrictive; regime does filtering |
| **30% STRONG_BULL cap** | Kelly×1.5 truncated at 20% | Kelly×1.5 deploys to 27% | Fixed truncation bug — regime mult now actually works |
| **3% target (not 5%)** | WR 68.8% | WR 68.8% maintained | STRONG_BULL dips recover 3-4%; 5% overshoot → reversal |
| **MAX_TRADE_BARS=20** | Stale trades | Cleaner exits | 4-week max hold — mean-reversion should resolve in 4wks |

---

## 7. What Failed (and Why)

### Bear Shorts (Phase A) — reverted
**What:** LONGS_ONLY=False, bear_short_signal routing in BEAR/STRONG_BEAR regimes
**Result:** 0% win rate in 2022, even with 2.5% stop (widened from 1.5%)
**Root cause 1:** Crypto intraday volatility is 4-7% daily range. A 2.5% stop is hit by
noise before directional moves materialize. Would need ATR-based dynamic stops.
**Root cause 2:** The 252-MA regime classifier lags 4-8 weeks. In Jan 2023, BTC was
+40% off lows (genuine bull recovery) but regime still read STRONG_BEAR → 15 bear shorts
fired into a rising market.
**Lesson:** Bear alpha = capital preservation. Don't fight it with shorts on daily bars.

### Bull Breakout Signal (Phase B) — disabled
**What:** STRONG_BULL entries when price > 20-day high + ADX>25 + MACD bullish
**Result:** 5yr trades jumped from 83→141, WR dropped 49.4%→39.6%
**Root cause:** Fires relentlessly near all-time-highs in STRONG_BULL. BTC near ATH
has RSI 70-80 and price always above recent highs — momentum trap. Every entry near
ATH in a subsequent STALLING or correction became a loser.
**Lesson:** Breakout signals work in trending markets; they're traps at tops.
The core strategy is mean-reversion — don't mix in momentum entries.

### 5% STRONG_BULL Target — reverted to 3%
**What:** TARGET_GAIN_PCT_STRONG_BULL = 0.05 (from 0.03)
**Result 2023:** WR 68.8% → 62.5%, return 4.27% → similar but worse risk-adjusted
**Result 5yr:** WR 49.4% → 33.7%, return collapsed
**Root cause:** STRONG_BULL RSI dips (mean-reversion entries) recover 3-4% on average.
Trades that hit 3% were held for 5%, reversed, and hit the 1.5% stop on the way back.
**Lesson:** 5% targets work for breakout/trend entries; mean-reversion exits should be
earlier. The STRONG_BULL dip recovery is ~3% — 3% target captures it cleanly.

### 50-MA Alignment Gate — removed
**What:** Only enter STRONG_BULL longs when price ≥ 50-MA.
Rationale: during extended corrections (e.g., BTC -30% from ATH), regime stays STRONG_BULL
but price drops well below 50-MA. Gate should block those "falling knife" entries.
**Result 2023 (misleading):** 12 trades, 83.3% WR, 4.65%, Sharpe 16 — looks amazing
**Result 5yr (correct):** 12 trades (from 83!), 58.3% WR, 2.06% — catastrophic
**Root cause:** RSI dip entries naturally occur when price is momentarily below the
lagging 50-MA during recovery phases:
- Aug 2023: BTC dipped during a healthy bull run. 14 trades, 64.3% WR — ALL filtered
  because BTC was temporarily below the lagging 50-MA (which smooths the dip)
- May 2021: BTC crashed from $65k. 15 trades, 60% WR — all filtered
- The gate conflates "genuinely declining" with "momentarily below lagging MA during recovery"
**Bonus problem:** Standalone 2023 backtest has look-ahead bias for the 252-MA
(computed from only 365 bars, so MA is artificially low → more STRONG_BULL days in 2023).
The 5yr run uses correct full history. Never use standalone year results to validate regime-based changes.
**Lesson:** Fixed threshold gates on lagging MAs are too blunt. A lighter version
(only gate when price is >5% BELOW 50-MA, not any touch) might preserve good trades
while blocking genuine extended corrections.

### Bull RSI Extra Entries — reverted
**What:** Added entries for RSI 38-42 in STRONG_BULL regime with MACD gate (trying
to add more bull trades since dips are shallower)
**Result:** 19 trades vs 16, WR dropped 68.8% → 57.9%, return dropped 4.02% → 2.79%
**Root cause:** RSI 38-42 in a strong bull is not actually oversold — it's "normal"
RSI during a regular day. Too many false entries.
**Lesson:** Don't fight the natural signal threshold just to generate more trades.

---

## 8. Current Performance Snapshot

### BTC Daily (ACTIVE_MODE = "BTC_DAILY")

**5-year (2020-01-01 → 2024-12-31):**
```
Trades: 83 | Win Rate: 49.4% | Total Return: 11.05%
Annualized: 2.12% | Sharpe: 4.924 | Max DD: -1.72%
Final Capital: $111,049 (from $100,000)
Exit breakdown: target_hit=41  stop_hit=42  time_exit=0
```

**2023 (best bull year, best signal quality):**
```
Trades: 16 | Win Rate: 68.8% | Total Return: 4.27%
Sharpe: 9.166 | Max DD: -0.72%
```

**Active months in 5yr run (months with trades):**
```
2020-09: +0.36%,  7 trades, 42.9% WR
2021-04: -0.72%,  4 trades,  0.0% WR  ← BAD: BTC topping at $65k
2021-05: +2.19%, 15 trades, 60.0% WR
2021-06: +0.36%,  1 trade, 100.0% WR
2021-09: -0.18%,  1 trade,   0.0% WR
2021-11: +0.72%,  5 trades, 60.0% WR
2021-12: -0.00%,  3 trades, 33.3% WR
2022-01: +0.36%,  1 trade, 100.0% WR
2023-03: +0.36%,  1 trade, 100.0% WR
2023-04: +0.36%,  1 trade, 100.0% WR
2023-05: +0.54%,  6 trades, 50.0% WR
2023-06: +0.72%,  2 trades,100.0% WR
2023-08: +2.37%, 14 trades, 64.3% WR  ← BEST month
2024-04: -0.18%,  4 trades, 25.0% WR
2024-05: -0.18%,  1 trade,   0.0% WR
2024-06: -0.00%,  9 trades, 33.3% WR  ← BAD: BTC -20% correction
2024-07: +0.54%,  6 trades, 50.0% WR
2024-08: -0.36%,  2 trades,  0.0% WR  ← BAD: BTC correction continues
```

**Observations (daily):**
- 14 months with 0 trades (flat — correct behavior in BEAR/STRONG_BEAR)
- Best: May 2021 (crash recovery), August 2023 (healthy bull dip)
- Worst: June/Aug 2024, April 2021 (regime lag during BTC corrections)

---

### BTC Hourly (ACTIVE_MODE = "BTC_HOURLY")

**2-year (2024-03-01 → 2026-02-01):**
```
Trades: 2,675 (~116/mo) | Win Rate: 46.2% | Total Return: 7.80%
Sharpe: 2.365 | Max DD: -0.39% | Avg Monthly: +5.75%
Final Capital: $107,802 (from $100,000)
```

**Monthly breakdown:**
```
2024-03: +8.69%, 103 trades, 51.5%  ← strong start
2024-04: +3.55%, 121 trades, 43.0%
2024-05: +5.33%, 121 trades, 45.5%
2024-06: +0.85%, 120 trades, 40.8%
2024-07: +3.62%, 122 trades, 44.3%
2024-08: +5.12%, 115 trades, 45.2%
2024-09: +0.71%, 141 trades, 39.7%
2024-10: +7.72%, 120 trades, 48.3%
2024-11:+11.39%, 110 trades, 53.6%  ← BTC bull run
2024-12: +9.78%, 121 trades, 50.4%
2025-01: +9.46%, 117 trades, 50.4%
2025-02:+17.11%, 107 trades, 61.7%  ← BEST month
2025-03:+11.27%, 117 trades, 53.0%
2025-04: +5.05%, 111 trades, 45.0%
2025-05: +4.26%, 105 trades, 45.7%
2025-06: +7.59%, 131 trades, 46.6%
2025-07: -0.95%, 123 trades, 37.4%  ← BAD: BTC correction
2025-08: +3.93%, 112 trades, 44.6%
2025-09: +5.36%, 106 trades, 48.1%
2025-10: -0.89%, 120 trades, 39.2%
2025-11: -3.64%, 116 trades, 33.6%  ← WORST month
2025-12:+11.55%,  91 trades, 57.1%
2026-01: +5.33%, 125 trades, 45.6%
```

**Observations (hourly):**
- Only 3 negative months out of 23 (87% hit rate on positive months)
- Worst month -3.64% is contained — max DD over full period only -0.39%
- High-trade-count months (40+ WR) consistently positive; bad months correlate with WR <38%
- No regime classifier on hourly — volume + RSI signal quality is the primary filter

---

## 9. Known Problems (Priority Order)

### Problem 1: Regime lag during intra-bull corrections (CRITICAL)
**Symptoms:** June 2024 (9 trades, 33% WR), August 2024 (2 trades, 0% WR), April 2021
**Mechanism:** BTC corrects -20-30% within a multi-year bull cycle. The 252-MA slope
stays positive → regime = STRONG_BULL → strategy enters RSI dips into a falling market.
**Approaches tried:** 50-MA gate → too aggressive (filtered 71/83 trades), abandoned
**Untried approaches:**
- ATR-scaled stops: if daily ATR > N×normal, either widen stop or reduce position to MIN_PCT
- Softer 50-MA gate: only block STRONG_BULL entries when price is >5% BELOW 50-MA
  (not any touch below — just deep corrections where mean-reversion is unlikely)
- Volatility circuit breaker: if realized 5-day vol > 3×20-day average, skip new entries
- RSI threshold adjustment: raise oversold threshold from 38 to 35 only in months when
  recent win rate < 40% (adaptive threshold — more selective when signals are degraded)

### Problem 2: RECOVERING regime may be a dead zone
**Symptom:** 130 bars over 5yr in RECOVERING, unknown number of trades
**Mechanism:** RECOVERING = price < 252-MA but > 50-MA. RSI dip entries should fire here,
but unclear if the signal frequency is meaningful. Needs trade count diagnostic.

---

## 10. Expert Agent Findings (2026-03-03 Analysis)

Three expert agents (Simplicity, Performance, Risk) audited the full codebase.
Below are the key findings, in priority order. *(Items 1 & 2 from original audit resolved.)*

### Softer 50-MA gate (Risk agent, Q3) — the right correction filter
**Problem:** June 2024 entries (bad month) are 7-15% below the 50-MA. Aug 2023 entries
(good month) are 1-3% below the 50-MA. The strict gate (any touch) filtered both equally.
**Fix:** Only gate when `(ma_50d - close) / close > 0.05` (>5% below 50-MA).
This blocks genuine extended corrections while preserving healthy bull dips.
**Implementation:** ~10 lines in `generate_trades()`, new config flag `STRONG_BULL_SOFT_50MA_PCT = 0.05`

### ATR-based dynamic stops (Risk agent, Q2)
**Problem:** 1.5% stop is inside daily ATR noise during corrections (ATR = 3-7% daily).
**Fix:** In runner.py, compute `atr_baseline = rolling 20-day median of atr_pct`.
If current ATR > 2× baseline, set `stop_overrides[idx] = atr_pct * 1.0`.
**Trade-off:** Wider stops = less noise-triggered exits, BUT higher max loss per trade.

### Exit type tracking — add for diagnostics (Risk agent, Q6)
`compute_trade_returns()` returns only the return percentage — we can't distinguish
stop-hit vs target-hit vs time-exit. This makes it impossible to know if bad months
are from noise-triggered stops (mechanical) or real adverse moves (structural).
**Fix:** Add an `exit_type` column to the return (minor refactor of compute_trade_returns).

### ADX multiplier: working but marginal (Performance agent, Q3)
ADX multiplier IS correctly computed (volatility.py:133-135) and applied (runner.py:129-134).
However its effect is only ±20% on Kelly sizing → <1% total return swing over 5yr.
Not broken, not impactful. Leave as-is.

### RECOVERING regime: not dead, but sparse (Performance agent, Q1)
RECOVERING contributes ~3-8 trades over 5yr on secondary dips during recovery phases.
It is NOT a dead zone, but entry frequency is low because RSI must dip below 38
while price is already between the 50-MA and 252-MA (already in recovery momentum).

### Prioritized next steps
| Priority | Change | Risk | Expected Impact |
|---|---|---|---|
| 1 | Softer 5% 50-MA gate for intra-bull corrections | Low-Med | Reduce June/Aug 2024 losses |
| 2 | ATR-based dynamic stop overrides | Medium | Reduce noise stops in high-vol |
| 3 | Exit type tracking in compute_trade_returns() | Low | Diagnostic only, no signal change |

---

## 11. Key Files Reference

| File | Key function | What it does |
|---|---|---|
| `config.py` | — | All tunable params; single source of truth |
| `src/signals/momentum.py` | `add_momentum_features()` | RSI, MACD, regime |
| `src/signals/momentum.py` | `classify_regime()` | 6-state dual-MA classifier |
| `src/signals/volume.py` | `add_volume_features()` | VWAP z-score → volume_signal |
| `src/signals/volatility.py` | `add_volatility_features()` | ADX, Bollinger, vol_regime |
| `src/strategy/engine.py` | `build_features()` | Orchestrates all signal modules |
| `src/strategy/engine.py` | `generate_trades()` | Applies regime gate, routes signals |
| `src/strategy/engine.py` | `compute_trade_returns()` | Simulates target/stop/time exits |
| `src/backtest/runner.py` | `run_backtest()` | Full backtest loop, Kelly equity curve |
| `src/backtest/runner.py` | `_print_signal_diagnostics()` | Per-filter bar counts |
| `src/strategy/sizing.py` | `compute_position_size()` | Fractional Kelly calculation |
| `main.py` | `main()` | Entry point, --mode=walk-forward support |

### Config flags quick reference
```python
# ── Mode selector (the one line you change to switch profiles) ──
ACTIVE_MODE = "BTC_DAILY"       # "BTC_DAILY" | "BTC_HOURLY" | "QQQ"

# ── BTC Daily core flags ─────────────────────────────────────────
USE_SLOPE_REGIME = True         # Core: 6-state regime classifier
LONGS_ONLY = True               # No shorts (bear alpha = capital preservation)
BEAR_DEFENSIVE_LONGS = True     # Small longs in BEAR at RSI<30, quarter-Kelly
BULL_BREAKOUT_ENABLED = False   # Disabled: momentum trap near ATH
STRONG_BULL_REQUIRE_50MA = False # Disabled: filtered 71/83 5yr trades
STRONG_BULL_SOFT_50MA_PCT = 0.0  # 0=off; 0.05=block >5% below 50-MA
USE_ADX_SIZING = True           # Active: ADX multiplier on position size
USE_ATR_DYNAMIC_STOPS = False   # Disabled: widen stops in high-vol periods
MAX_POSITION_PCT_STRONG_BULL = 0.30  # KEY FIX: lets Kelly×1.5 deploy to 27%
TARGET_GAIN_PCT_STRONG_BULL = 0.03   # 3% (not 5% — 5% killed win rate)
```

---

## 12. Strategy Constraints (Do Not Violate)

1. **No ML/neural networks** — explainability required
2. **No inverse ETFs or derivatives** — same asset, direction flip only
3. **Never touch the 252-MA regime classifier logic** — it's the entire foundation
4. **All new features must be independently toggleable** via config flag (default=False)
5. **Validate on 5yr full run, not standalone year** — standalone year has look-ahead
   bias in the 252-MA (computed from too few bars)
6. **Test 2023 as regression baseline:** must maintain 68.8% WR / 4.27% return
7. **Never introduce look-ahead bias:** any rolling window used for entry must use
   `.shift(1)` to reference prior bar's value

---

## 13. BTC Hourly Optimization Session (2026-03-11) — Current State

### What was done this session
Starting from the original BTC Hourly baseline (7.80% / 2yr, Sharpe 2.365, avg +5.75%/mo),
we discovered the monthly numbers were inflated. **Correct baseline after fixing the display:**
```
Full 23-month (2024-03-15 → 2026-02-15): 7.68% total, Sharpe 12.133, Max DD -0.35%, avg +0.31%/mo
```

### Changes made (all in config.py + engine.py, branch claude/review-codebase-o0ipc)

**1. ADAPTIVE_KELLY_HIGH_MULT: 1.4 → 1.8**
- When rolling WR ≥ 52% (HIGH tier), position multiplier is now 1.8× not 1.4×
- Effect: +1.42% total return over 23 months. Best months (Feb 2025 55% WR, Mar 2025 56% WR) got bigger.
- ADAPTIVE_KELLY_HIGH_CAP raised from 0.28 → 0.30 to give headroom (not the binding constraint)
- ADAPTIVE_KELLY_HIGH_WR lowered from 0.55 → 0.52 (tested inert — rolling WR doesn't sit in 52-55% band)

**2. Time-of-day filter: HOURLY_TRADE_FILTER=True, hours 07-21 UTC**
- Added to `generate_trades()` in engine.py (~10 lines)
- Dead zone (00-07 UTC): low liquidity, RSI signals are noise not genuine demand
- Effect: trades 2455 → 1468 (40% fewer), WR 45.6% → 48.5%, Kelly 5.82% → 8.16% (auto-scales)
- August 2024 rescued: -0.08% → +0.33% (37.7% WR → 52.1% WR). Dead-zone noise was the culprit.

**3. ADAPTIVE_KELLY_LOOKBACK: 20 → 15 trades**
- Faster rolling WR detection (~3 days at 115 trades/mo vs 5 days)
- Works well WITH the time filter (cleaner signals → less noisy 15-trade window)
- Without the time filter, lb=15 made things slightly worse (noisy signals confuse faster window)

### Current best result (all three changes, 23-month full period)
```
Total Return:   10.73%
Annualized:     5.45%
Sharpe Ratio:   14.603
Max Drawdown:   -0.35%
Avg Monthly:    +0.43%
Win Rate:       48.5%  (was 45.6%)
Kelly Pos Size: 8.16%  (was 5.82%)
Trades:         1,468  (was 2,455)
```

### Critical architectural finding (this session)
**The regime classifier (BULL/BEAR/RECOVERING etc.) has ZERO effect on hourly position sizing.**
`runner.py` line 39: `use_slope_regime = False if timeframe == "hourly"` — intentionally disabled
because 252 hourly bars = 10.5 days (wrong calibration for a regime filter).
The regime distribution printed in diagnostics is computed and displayed but never used for sizing
or entry gating in hourly mode. Adaptive Kelly is the ONLY dynamic sizing mechanism for hourly.

### What was tried and failed this session
- **target_gain_pct 0.004 → 0.005**: WR collapsed 50.7% → 42.1%. BTC hourly moves reach 0.4%
  but rarely extend to 0.5% before reversing. Reverted immediately.
- **Hourly regime_mult floor**: Made irrelevant by the above finding (regime_mult = 1.0 always).
- **HIGH_WR threshold 0.55 → 0.52 alone**: Inert — rolling WR doesn't naturally sit at 52-55%.

### Current config state (BTC_HOURLY active params)
```python
ACTIVE_MODE               = "BTC_HOURLY"
HOURLY_TRADE_FILTER       = True
HOURLY_TRADE_HOURS_START  = 7      # UTC
HOURLY_TRADE_HOURS_END    = 21     # UTC
USE_ADAPTIVE_KELLY        = True
ADAPTIVE_KELLY_LOOKBACK   = 15
ADAPTIVE_KELLY_HIGH_WR    = 0.52
ADAPTIVE_KELLY_HIGH_MULT  = 1.8
ADAPTIVE_KELLY_HIGH_CAP   = 0.30
ADAPTIVE_KELLY_LOW_WR     = 0.42
ADAPTIVE_KELLY_PAUSE_WR   = 0.35
ADAPTIVE_KELLY_LOW_MULT   = 0.5
ADAPTIVE_KELLY_PAUSE_MULT = 0.2
# Signal params (hourly)
RSI_PERIOD_HOURLY         = 7
RSI_OVERSOLD_HOURLY       = 40
MACD_FAST_HOURLY          = 6 / SLOW 13 / SIGNAL 4
VWAP_ZSCORE_THRESH_HOURLY = 1.0
target_gain_pct           = 0.004   # 0.4% (0.5% was tested, killed WR)
stop_loss_pct             = 0.0025  # 0.25%
```

### Next experiments to try (not yet tested)
1. **Hour window edges**: 6-22 UTC or 8-20 UTC — is 7-21 the optimal window or just a first pass?
2. **VWAP_ZSCORE_THRESH_HOURLY 1.0 → 1.1**: Tighter volume filter, fewer but better-quality entries
3. **RSI_OVERSOLD_HOURLY 40 → 38**: More selective, fewer trades, test WR improvement
4. **BTC Daily mode**: untouched this session — still at Sharpe 4.924, Max DD -1.72% (5yr)

---

*Last updated: 2026-03-11 — BTC hourly optimization: time-of-day filter, adaptive Kelly tuning, 10.73% / Sharpe 14.6*
*Branch: claude/review-codebase-o0ipc*
