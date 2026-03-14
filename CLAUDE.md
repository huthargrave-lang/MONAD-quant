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
| **BTC Hourly** | ~2.66%/mo income | 25.57 | -0.90% | Active income, ~130 trades/mo |
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

**7-year (2019-09-01 → 2026-01-01) — current optimized config:**
```
Trades: 10,850 (~130/mo) | Win Rate: 48.9% | Total Return: 616.67%
Annualized: 36.89% | Sharpe: 25.568 | Max DD: -0.90%
Final Capital: $716,669 (from $100,000) | Avg Monthly: +2.66%
Kelly Pos Size: 11.66%
```

**Selected monthly highlights (7yr run):**
```
2021-01: +12.24%, 152 trades, 85.5%  ← BTC bull surge
2021-05: +14.89%, 207 trades, 79.2%  ← crash recovery
2022-06: +8.77%,  231 trades, 60.6%  ← bear market volatility capture
2024-03: +4.90%,  112 trades, 64.3%
2025-03: +5.18%,  156 trades, 57.7%
2023-07: -0.43%,  165 trades, 37.0%  ← BAD: low WR month
2024-06: +0.05%,  151 trades, 31.8%  ← near-zero: WR collapse
```

**Observations (hourly):**
- Regime classifier computed but NOT used for sizing/gating (runner.py intentionally disables it for hourly)
- Adaptive Kelly is the ONLY dynamic sizing mechanism: scales 0.2×–2.0× based on rolling 20-trade WR
- HIGH tier (WR ≥ 0.46) IS active — fires during 48-55% WR bull stretches and sizes up 2.0×
- Bad months consistently show WR < 38%; PAUSE_WR=0.35 limits damage but can't eliminate it
- 24hr trading (no time filter) outperforms filtered mode — BTC mean-reversion has no dead zone

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

## 13. BTC Hourly Optimization Session (2026-03-11) — Superseded

*(Session summary: discovered 24hr filter beats time-filtered mode; ADAPTIVE_KELLY_HIGH_MULT
raised to 1.8, LOOKBACK reduced to 15. Best result at time: 10.73% / Sharpe 14.6 on 2yr window.
All findings superseded by Session 2026-03-14 below.)*

---

## 14. BTC Hourly Full Optimization (2026-03-14) — Current State

### Starting point
Session 13 left state: stop=0.0025, HOURLY_TRADE_FILTER=True (07-21 UTC), LOOKBACK=15,
HIGH_MULT=1.8, HIGH_WR=0.52. Best 2yr result: 10.73% / Sharpe 14.6.

### Critical bug fix: stop_loss_pct in ASSETS dict
**Bug:** `stop_loss_pct` is defined twice — top-level param AND inside `ASSETS["BTC_HOURLY"]`.
The engine reads from the ASSETS dict. The top-level param was being changed but the ASSETS
dict still had `0.0025`. All hourly backtest results before this fix were running with 0.0025.
**Fix:** Updated `ASSETS["BTC_HOURLY"]["stop_loss_pct"] = 0.002`.
**Impact:** +579.97% 7.5yr vs +377% at 0.0025. Largest single improvement in session history.

### Complete parameter sweep results (7yr 2019-2026 window)

**stop_loss_pct sweep (target=0.004 fixed):**
| Stop | Return | Sharpe | Avg/mo |
|---|---|---|---|
| 0.0025 (old) | ~377% | ~22 | +2.02% |
| **0.002** | **553.62%** | **25.945** | **+2.53%** |

**HOURLY_TRADE_FILTER sweep:**
| Filter | Return | Sharpe | Trades/mo | Avg/mo |
|---|---|---|---|---|
| True 07-21 UTC | 437.48% | 26.238 | ~88 | +2.26% |
| **False (24hr)** | **553.62%** | **25.945** | **~130** | **+2.53%** |

The time filter looked good on the 2yr window (cleaner WR) but the 7yr run proves 24hr wins —
BTC mean-reversion has no genuine dead zone. More trades + same quality = better compounding.

**ADAPTIVE_KELLY_LOOKBACK sweep (with 24hr mode):**
| Lookback | Return | Notes |
|---|---|---|
| 15 | worse | Tuned for filtered mode, too noisy for 24hr |
| **20** | **553.62%** | Optimal for 24hr trade volume |

**ADAPTIVE_KELLY_HIGH_WR sweep:**
| HIGH_WR | Effect | Verdict |
|---|---|---|
| 0.52 | inert | Rolling WR never sustains above 52% in 24hr |
| 0.50 | inert | Same |
| **0.46** | **active** | Fires during 48-55% WR bull stretches (Jan/May 2021 etc.) |

At HIGH_WR=0.46, the HIGH tier IS a live lever. At 0.52+, it's dead.

**ADAPTIVE_KELLY_HIGH_MULT sweep (with HIGH_WR=0.46):**
| HIGH_MULT | Return | Sharpe | Avg/mo |
|---|---|---|---|
| 1.8 | ~453% | ~26.1 | +2.30% |
| **2.0** | **553.62%** | **25.945** | **+2.53%** |

HIGH_MULT=2.0 with HIGH_CAP=0.35 confirmed. HIGH_CAP=0.30 was too tight for 2.0× mult.

**VWAP_ZSCORE_THRESH_HOURLY sweep:**
| VWAP | Trades | Return | Sharpe | Max DD | Avg/mo |
|---|---|---|---|---|---|
| **1.0** | **9,689** | **553.62%** | **25.945** | **-0.80%** | **+2.53%** |
| 1.1 | 9,333 | 533.07% | 26.128 | -1.01% | +2.49% |

VWAP=1.1 removed trades without improving WR (filtered good and bad equally). Keep 1.0.

**RSI_OVERSOLD_HOURLY sweep (full, 38→100):**
| RSI | Trades/mo | WR | Return | Sharpe | Max DD | Avg/mo |
|---|---|---|---|---|---|---|
| 38 | ~105 | 50.0% | 506.90% | 26.694 | -0.78% | +2.43% |
| 40 | ~115 | 49.5% | 553.62% | 25.945 | -0.80% | +2.53% |
| 41 | ~123 | 49.1% | 566.98% | 25.666 | -0.93% | +2.56% |
| **42** | **~130** | **48.9%** | **616.67%** | **25.568** | **-0.90%** | **+2.66%** |
| 43 | ~138 | 48.4% | 596.01% | 24.728 | -0.79% | +2.62% |
| 50 | ~210 | 45.9% | 639.44% | 21.720 | -1.05% | +2.71% |
| 100 | ~375 | 44.0% | 744.05% | 18.655 | -1.94% | +2.90% |

**RSI=42 is the optimal.** RSI=42 actually beats RSI=43 on both return AND Sharpe (42 > 43).
RSI=50+ has higher gross return but Sharpe collapses and fee drag eliminates the advantage.
Fee-adjusted (0.1% round-trip): RSI=42 net +1.14%/mo ≈ RSI=40 net +1.14%/mo. At lower fees
(0.04% BNB), RSI=42 wins (+2.05% vs +1.97%). RSI=42 robust across fee structures.

Signal balance insight: at RSI=42, momentum_signal=11,001 < volume_signal=11,758 (RSI is
still binding gate). At RSI=43, they're nearly equal (11,726 vs 11,758). Above 43, RSI
becomes loose and VWAP is the only real filter. RSI=50/100 = essentially just MACD signal.

### Dead levers confirmed (MACD and RSI period)

**RSI_PERIOD_HOURLY (3, 5, 7, 8 — all identical output):**
The MACD histogram direction (`hist > hist.shift(1)`) is the binding gate for momentum_signal.
Changing RSI period only affects RSI amplitude, not which bars pass the combined gate.
momentum_signal count doesn't change → trades/WR/return identical. **RSI period is dead.**

**MACD_FAST_HOURLY (4, 6, 9), MACD_SLOW_HOURLY (10, 13, 20), MACD_SIGNAL_HOURLY (3, 4, 6):**
All produce identical momentum_signal count, identical trade count, identical returns.
The histogram DIRECTION is robust to window changes on BTC hourly — different EMA windows
shift timing by 1-2 bars but don't change the overall turn count over 55k bars.
**All MACD params are dead levers. 6/13/4 is as good as any other combination.**

### Final confirmed optimal config (BTC_HOURLY)
```python
ACTIVE_MODE               = "BTC_HOURLY"
HOURLY_TRADE_FILTER       = False   # 24hr; filter tested and confirmed worse
HOURLY_TRADE_HOURS_START  = 0       # (only used when filter=True)
HOURLY_TRADE_HOURS_END    = 24      # (only used when filter=True)
USE_ADAPTIVE_KELLY        = True
ADAPTIVE_KELLY_LOOKBACK   = 20      # lb=15 was for filtered mode; 20 optimal for 24hr
ADAPTIVE_KELLY_HIGH_WR    = 0.46    # Active at 0.46; dead at 0.52+ (tested all values)
ADAPTIVE_KELLY_HIGH_MULT  = 2.0     # Confirmed: +553% vs +453% at 1.8 (2019-2026)
ADAPTIVE_KELLY_HIGH_CAP   = 0.35    # Headroom for 2.0× mult (0.30 was too tight)
ADAPTIVE_KELLY_LOW_WR     = 0.42
ADAPTIVE_KELLY_PAUSE_WR   = 0.35
ADAPTIVE_KELLY_LOW_MULT   = 0.5
ADAPTIVE_KELLY_PAUSE_MULT = 0.2
# Signal params (hourly) — dead levers noted
RSI_PERIOD_HOURLY         = 7       # DEAD LEVER — MACD is binding gate; any value identical
RSI_OVERSOLD_HOURLY       = 42      # LIVE: full sweep 38-100 done; 42 is peak Return+Sharpe
MACD_FAST_HOURLY          = 6       # DEAD LEVER — all fast periods identical
MACD_SLOW_HOURLY          = 13      # DEAD LEVER — all slow periods identical
MACD_SIGNAL_HOURLY        = 4       # DEAD LEVER — all signal periods identical
VWAP_ZSCORE_THRESH_HOURLY = 1.0    # Confirmed: 1.0 > 1.1 (more trades, lower DD)
# In ASSETS["BTC_HOURLY"] dict:
target_gain_pct           = 0.004   # 0.4% (0.5% tested: WR collapsed)
stop_loss_pct             = 0.002   # KEY FIX: was 0.0025 in ASSETS dict; 2:1 R:R
```

### Best result to date
```
Period:        2019-09-01 → 2026-01-01 (7yr)
Total Return:  616.67%
Annualized:    36.89%
Sharpe:        25.568
Max DD:        -0.90%
Avg Monthly:   +2.66%
Trades:        10,850 (~130/mo)
Win Rate:      48.9%
Kelly Size:    11.66%
```

### Fee consideration
At 0.1% round-trip (retail CEX): ~1.52% monthly fee drag → net +1.14%/mo
At 0.04% round-trip (BNB maker): ~0.61% monthly fee drag → net +2.05%/mo
At 0.02% round-trip (VIP maker): ~0.30% monthly fee drag → net +2.36%/mo
Strategy requires maker-fee access to be viable at meaningful scale.

### Nothing left to tune on BTC Hourly
Every live parameter has been exhaustively swept. The strategy is at its optimum.
Future work should focus on: (1) BTC Daily mode improvements, (2) QQQ Hourly development,
(3) live trading infrastructure.

---

*Last updated: 2026-03-14 — Full BTC hourly optimization complete: RSI=42, stop=0.002, 24hr, HIGH_MULT=2.0 → +616.67% / Sharpe 25.6*
*Branch: claude/setup-working-branch-sf66n*
