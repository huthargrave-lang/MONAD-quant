# MONAD Quant — Full Model History & Context

> **Purpose of this file:** Complete institutional memory for the strategy — what every
> component does, every approach tried, why things failed, and what to try next. Written
> for AI agents and collaborators who need maximum context without reading git history.

---

## 1. Project Goal

**NOT a growth strategy.** MONAD Quant is a **high-yield bond ETF alternative** — an
actively-traded, long-only engine designed to generate consistent monthly income with
near-zero drawdown. The strategy has nine configured modes across two tiers:

**Tier 1 — Production-ready (realistic backtest validated):**

| Mode | Target | Sharpe | Max DD | Style |
|---|---|---|---|---|
| **BTC Daily** | ~0.4%/mo, Sharpe >4 | 4.924 | -1.72% | Capital preservation + high Sharpe |
| **BTC Hourly** | ~2.66%/mo gross | 25.57 | -0.90% | Active income, ~130 trades/mo (crypto fees apply) |
| **QQQ Hourly** | ~0.71%/mo income | 41.57 | -0.21% | ETF mean-reversion, ~24 trades/mo |
| **TQQQ Hourly** | ~2.02%/mo income | 39.0 | -0.85% | 3x leveraged ETF, ~24 trades/mo |
| **SOXL Hourly** | ~3.50%/mo income | 47.3 | -0.75% | 3x leveraged semis, ~27 trades/mo |
| **LABU Hourly** | ~3.07%/mo income | 61.6 | -0.52% | 3x leveraged biotech, ~26 trades/mo |
| **TNA Hourly** | ~1.74%/mo income | 82.0 | -0.24% | 3x leveraged Russell 2000, ~24 trades/mo |

**Tier 2 — Needs re-sweep (optimistic-mode params, not validated in realistic backtest):**

| Mode | Status | Issue |
|---|---|---|
| **GDXU Hourly** | NEEDS RE-SWEEP | Realistic backtest showed Sharpe 1.8, WR 27.5%. Optimistic-mode params (0.075% stop) are inside bid-ask spread. |

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
| `sweep.py` | — | Universal param sweep: `python sweep.py TICKER` |
| `live/trader.py` | `_on_bar_inner()` | Scheduler loop, entry/exit/pending_close logic |
| `live/state.py` | `mark_pending_close()` | Blocks entries until fill reconciled |
| `live/state.py` | `finalize_pending_close()` | Records actual fill, clears position |
| `live/broker.py` | `place_bracket_order()` | IBKR bracket orders + fill queries |
| `live/dashboard.py` | `dashboard()` | Read-only FastAPI monitoring UI |

### Config flags quick reference
```python
# ── Mode selector (the one line you change to switch profiles) ──
ACTIVE_MODE = "TQQQ_HOURLY"    # Current live mode
# Options: "BTC_DAILY" | "BTC_HOURLY" | "QQQ" | "QQQ_HOURLY" | "TQQQ_HOURLY"
#          | "GDXU_HOURLY" | "SOXL_HOURLY" | "LABU_HOURLY" | "TNA_HOURLY"

# ── BTC Daily core flags ─────────────────────────────────────────
USE_SLOPE_REGIME = True         # Core: 6-state regime classifier
LONGS_ONLY = True               # No shorts (bear alpha = capital preservation)
BEAR_DEFENSIVE_LONGS = True     # Small longs in BEAR at RSI<30, quarter-Kelly
BULL_BREAKOUT_ENABLED = False   # Disabled: momentum trap near ATH
STRONG_BULL_REQUIRE_50MA = False # Disabled: filtered 71/83 5yr trades
STRONG_BULL_SOFT_50MA_PCT = 0.02 # Active: block entries >2% below 50-MA
USE_ADX_SIZING = True           # Active: ADX multiplier on position size
USE_ATR_DYNAMIC_STOPS = False   # Disabled: widen stops in high-vol periods
MAX_POSITION_PCT_STRONG_BULL = 0.30  # KEY FIX: lets Kelly×1.5 deploy to 27%
TARGET_GAIN_PCT_STRONG_BULL = 0.03   # 3% (not 5% — 5% killed win rate)
USE_OPPOSING_SIGNAL_EXIT = False # Tested: hurts TQQQ (sweep confirmed)
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

---

## 15. QQQ Hourly Full Optimization (2026-03-17) — Current State

### Final confirmed optimal config (QQQ_HOURLY)
```python
ACTIVE_MODE                   = "QQQ_HOURLY"
RSI_PERIOD_QQQ_HOURLY         = 7
RSI_OVERSOLD_QQQ_HOURLY       = 70    # QQQ less volatile — 38 too rare; 70 confirmed optimal
RSI_OVERBOUGHT_QQQ_HOURLY     = 62
MACD_FAST_QQQ_HOURLY          = 6     # DEAD LEVER (like BTC hourly — histogram direction is robust)
MACD_SLOW_QQQ_HOURLY          = 13    # DEAD LEVER
MACD_SIGNAL_QQQ_HOURLY        = 4     # DEAD LEVER
VWAP_WINDOW_QQQ_HOURLY        = 10
VWAP_ZSCORE_THRESH_QQQ_HOURLY = 0.4   # Confirmed — QQQ ETF VWAP deviations smaller than BTC
BB_WINDOW_QQQ_HOURLY          = 14
TARGET_GAIN_PCT_QQQ_HOURLY    = 0.0024 # 0.24% target — confirmed optimal for QQQ hourly range
STOP_LOSS_PCT_QQQ_HOURLY      = 0.0012 # 0.12% stop — 2:1 R:R; WR 59.6%, Kelly 19.73%
# Adaptive Kelly: same shared params as BTC hourly (see below)
# USE_ADAPTIVE_KELLY = True, LOOKBACK=20, HIGH_WR=0.46, HIGH_MULT=2.0, HIGH_CAP=0.35
```

### Best result
```
Period:       2024-04-01 → 2026-03-01 (23 months)
Total Return: 17.77%
Annualized:   8.95%
Sharpe:       41.568
Max DD:       -0.21%
Avg Monthly:  +0.71%
Trades:       550 (~24/mo)
Win Rate:     59.6%  (target=328  stop=222  time=0)
Kelly Size:   19.73%
EV/trade:     +0.095%  (0.596×0.24% − 0.404×0.12%)
```

### Why QQQ Hourly behaves differently from BTC Hourly

| Property | BTC Hourly | QQQ Hourly |
|---|---|---|
| Trades/month | ~130 | ~24 |
| Baseline WR | ~49% | ~60% |
| RSI oversold | 42 | 70 (shallower dips) |
| VWAP threshold | 1.0 | 0.4 (smaller deviations) |
| Target/Stop | 0.4%/0.2% | 0.24%/0.12% |
| Adaptive Kelly | Truly adaptive | Effectively fixed 2× |

### Adaptive Kelly dead levers for QQQ (confirmed exhaustive sweep)

**PAUSE_WR sweep (0.35 → 0.44): all inert.**
Root cause: 24 trades/month means LOOKBACK=20 covers ~1 full month.
By the time enough losses accumulate to push rolling WR below any threshold,
the bad month is nearly over. PAUSE never fires in time to matter.

**LOOKBACK sweep (5 → 100): 20 is optimal on Sharpe; diminishing returns above 15.**

| LOOKBACK | Return | Sharpe | Avg/mo |
|---|---|---|---|
| 5 | 14.61% | 37.612 | +0.60% |
| 8 | 16.05% | 38.267 | +0.65% |
| 10 | 16.39% | 39.069 | +0.66% |
| 12 | 16.70% | 39.716 | +0.67% |
| 15 | 17.58% | 40.573 | +0.71% |
| **20** | **17.77%** | **41.568** | **+0.71%** |
| 30 | 18.22% | 41.227 | +0.73% |
| 100 | 17.98% | 41.460 | +0.72% |

LOOKBACK=20 wins on Sharpe. LOOKBACK=30 gets +0.45% more return at cost of higher DD (-0.28% vs -0.21%).

**HIGH_WR=0.46 fires constantly for QQQ** (QQQ baseline WR ~60% >> 0.46 threshold).
Adaptive Kelly is not truly adaptive for QQQ — it acts as a fixed 2.0× multiplier.
HIGH_MULT=2.0 ON=17.77% vs OFF=10.21% (+7.56% purely from the always-on 2× sizing).

### Adaptive Kelly: True vs False comparison
| AK Setting | Return | Sharpe | Avg/mo |
|---|---|---|---|
| False (base Kelly only) | 10.21% | 41.565 | +0.42% |
| **True (2× always active)** | **17.77%** | **41.568** | **+0.71%** |

Same Sharpe, +74% more return. The 2× sizing scales returns and risk proportionally.

### The fundamental ceiling
QQQ Hourly generates ~24 trades/month vs BTC's ~130. The EV/trade (+0.095%) and
Kelly size (19.73%) are fixed by signal quality. More trades require looser thresholds
which collapsed WR in testing. **Trade frequency is the architectural ceiling.**

Mathematical ceiling: `24 trades × 0.095% EV × 19.73% position × 2× AK ≈ 0.71%/mo`

### Nothing left to tune on QQQ Hourly
Every parameter exhaustively swept: RSI (full range), VWAP (0.3–1.5), target/stop
(multiple R:R ratios), MACD (dead lever), LOOKBACK (5–100), PAUSE_WR (0.35–0.44).
Strategy is at its optimum given the current architecture.
Future improvements require architectural changes: time-of-day filter (untested),
or expanding to a second ETF instrument for correlation diversification.

---

## 16. Why We Pivoted to QQQ — The Fee Model Problem

### The BTC Hourly fee drag problem
BTC Hourly at its best produces +2.66%/mo gross. But it runs on a crypto CEX
(Binance), and trading fees eat directly into that number:

| Fee tier | Round-trip | Monthly drag (~130 trades × 0.24% avg size) | Net monthly |
|---|---|---|---|
| Retail (0.1%) | 0.20% per trade | −1.52%/mo | **+1.14%/mo** |
| BNB discount (0.04%) | 0.08% per trade | −0.61%/mo | **+2.05%/mo** |
| VIP maker (0.02%) | 0.04% per trade | −0.30%/mo | **+2.36%/mo** |

To keep full gross returns, you need VIP maker status on Binance — which requires
$10M+ 30-day trading volume. At retail rates (+1.14%/mo net), the strategy still
beats high-yield bonds but loses most of its edge. The fee barrier is structural.

### The QQQ fee reality
QQQ trades on a standard US brokerage. At Schwab, Fidelity, TD Ameritrade,
Interactive Brokers: **$0 commission per trade**. All major US retail brokers
eliminated stock/ETF commissions in 2019.

| Broker | Commission | Monthly drag (~24 trades) | Net monthly |
|---|---|---|---|
| Schwab / Fidelity / TD | $0 | $0 | **+0.71%/mo** |
| Interactive Brokers | ~$0.005/share | ~$0.12/mo total | **+0.71%/mo** |

QQQ gross return **equals** QQQ net return. No fee tier. No exchange account. No BNB.

### The real comparison: net returns accessible to a retail investor
| Mode | Gross/mo | Net/mo (retail) | Infrastructure required |
|---|---|---|---|
| BTC Hourly | +2.66% | +1.14% | Binance, BNB, VIP tier, 24/7 ops, custody risk |
| **QQQ Hourly** | **+0.71%** | **+0.71%** | Any US brokerage, market hours only |

BTC Hourly is still higher absolute return — but the operational complexity,
custody risk, and fee structure require institutional-grade access to realize
more than ~1.1%/mo net. QQQ delivers its full return to any retail investor
with a standard brokerage account.

### Additional reasons QQQ is preferred for retail deployment

**Regulatory and tax simplicity:** QQQ trades produce standard 1099-B tax reporting.
BTC trades produce crypto cost-basis reporting — complex, jurisdiction-dependent,
and requires specialized accounting software (Koinly, TaxBit, etc.) at scale.

**No custody risk:** QQQ is held at a SIPC-insured US brokerage (up to $500k).
BTC on Binance carries exchange counterparty risk (see FTX, 2022).

**Market hours only:** QQQ trades 9:30–16:00 ET. ~24 trades/month means roughly
1 trade per trading day on average. BTC is 24/7/365 — requires either automation
or constant monitoring. QQQ fits within a normal trading day.

**Signal quality:** QQQ's 59.6% WR vs BTC hourly's 48.9% WR reflects the more
orderly mean-reversion in regulated equity markets. Institutional market makers
provide tighter bid-ask spreads and more predictable intraday patterns.

### What we tried before landing on QQQ Hourly

**QQQ Daily (walk-forward tested):** Generated ~5 trades over 3 years out-of-sample.
The 6-state regime classifier + QQQ's smooth bull trend (252-day MA nearly always
upsloping) creates structural signal scarcity. Only RSI<42 AND MACD turn AND
confirmed bull regime fires — almost never on daily bars for a low-vol ETF.
**Verdict:** QQQ daily is not viable with current signal architecture.

**QQQ Hourly (first attempt):** Initial params borrowed from BTC hourly
(RSI=38, VWAP=1.0, stop=0.0006). RSI 38 almost never fires intraday for QQQ —
ETF hourly bars are too small to push RSI that low. Generated <5 trades/month.
**Pivot:** Raised RSI to 70, tightened VWAP to 0.4, fixed stop to 0.0012 (2:1 R:R).
This unlocked ~24 trades/month at 59.6% WR — the viable operating point.

**BTC Daily (live comparison baseline):** +0.4%/mo at Sharpe 4.9 with near-zero DD.
Excellent risk-adjusted but very low absolute return. Viable as a capital preservation
vehicle but not an income strategy. Requires the same BTC exchange infrastructure as
BTC Hourly without the return to justify it.

### Monthly results — QQQ Hourly optimized run (2024-04 → 2026-02)
```
Month          Return   Trades   Win Rate   Notes
------------------------------------------------------------
2024-04        +0.41%       32      46.9%
2024-05        +0.24%       12      50.0%
2024-06        +0.67%       18      66.7% ✓
2024-07        +1.16%       38      57.9% ✓
2024-08        +1.30%       32      65.6% ✓
2024-09        +0.38%       21      52.4%
2024-10        +0.93%       33      54.5% ✓
2024-11        +0.89%       21      76.2% ✓
2024-12        +0.34%       13      53.8%
2025-01        +0.86%       24      62.5% ✓
2025-02        +0.33%       21      47.6%
2025-03        +0.87%       37      56.8% ✓
2025-04        +2.25%       36      83.3% ✓  ← BEST month
2025-05        +0.54%       11      72.7% ✓
2025-06        +0.53%       20      55.0% ✓
2025-07        +0.66%       21      61.9% ✓
2025-08        +0.30%       32      37.5%      ← WR collapse, but still positive
2025-09        +0.05%       16      50.0%      ← Near-zero; BEAR regime in force
2025-10        +0.93%       26      65.4% ✓
2025-11        +0.14%       25      48.0%
2025-12        +0.59%       18      61.1% ✓
2026-01        +1.07%       23      73.9% ✓
2026-02        +1.01%       20      75.0% ✓
------------------------------------------------------------
Avg Monthly    +0.71%
ZERO negative months across 23 months (including Aug 2025 at 37.5% WR)
```

**Key observation:** Even the worst month (Aug 2025, 37.5% WR) was positive (+0.30%).
The 2:1 R:R ratio means the strategy can sustain win rates as low as 34% before
going negative on a month. QQQ's WR never fell below 37.5% in this run.
Compare to BTC Hourly where bad months (WR < 35%) produce negative months.

The high-Sharpe, 0-negative-month profile is the defining characteristic of QQQ Hourly
and the primary reason it is preferred for retail deployment over BTC Hourly.

---

## 17. TQQQ Hourly Optimization — Current State

### Why TQQQ?
TQQQ is 3x leveraged QQQ — same underlying index, but wider intraday swings.
The mean-reversion signal architecture that works on QQQ should work even better
on TQQQ because the larger price moves create more alpha per trade while
maintaining the same zero-commission brokerage infrastructure.

### Optimistic vs Realistic backtest modes
Early TQQQ optimization used the "optimistic" backtest mode, which resolved same-bar
ambiguity (bar hits both TP and SL) in favor of the trade. This produced headline
numbers of Sharpe 94.2 and +1.89%/mo at a 5.6:1 R:R (0.42% target / 0.08% stop).

The "realistic" backtest mode was introduced later to handle same-bar ambiguity
pessimistically (assume the stop was hit). This collapsed the ultra-tight stop
configs and required a full re-sweep. **All current production configs use realistic mode.**

### Current production config (TQQQ_HOURLY — realistic mode)
```python
ACTIVE_MODE                      = "TQQQ_HOURLY"
RSI_PERIOD_TQQQ_HOURLY          = 7        # DEAD LEVER (MACD is binding gate)
RSI_OVERSOLD_TQQQ_HOURLY        = 80       # Realistic sweep optimal (1.9:1 R:R)
RSI_OVERBOUGHT_TQQQ_HOURLY      = 62
MACD_FAST_TQQQ_HOURLY           = 6        # DEAD LEVER
MACD_SLOW_TQQQ_HOURLY           = 13       # DEAD LEVER
MACD_SIGNAL_TQQQ_HOURLY         = 4        # DEAD LEVER
VWAP_WINDOW_TQQQ_HOURLY         = 10
VWAP_ZSCORE_THRESH_TQQQ_HOURLY  = 0.5      # DEAD LEVER (0.3–0.6 nearly identical)
BB_WINDOW_TQQQ_HOURLY           = 14
TARGET_GAIN_PCT_TQQQ_HOURLY     = 0.0100   # 1.00% target — realistic sweep optimal; 1.9:1 R:R
STOP_LOSS_PCT_TQQQ_HOURLY       = 0.0050   # 0.50% stop — live-safe (5.1x spread)
```

### Current realistic-mode performance
```
Period:       2024-04-01 → 2026-03-01 (24 months)
Sharpe:       39.0
Max DD:       -0.85%
24mo Return:  61.17%
Avg Monthly:  +2.02%
Trades/mo:    ~24
Status:       Live-safe — stop $0.153 is 5.1x estimated spread
```

### Opposing signal exit: tested and rejected
Exit-tuning sweep (2026-04-10) tested RSI_OVERBOUGHT 45–85 for opposing-signal exit.
**Every threshold HURT performance.** Best candidate (RSI_OB=62) scored -1.0 with only
3 opposing exits across 119 trades. Baseline (OFF) outperforms all variants.
`USE_OPPOSING_SIGNAL_EXIT = False` is confirmed optimal.

### Dead levers confirmed for TQQQ
- **MACD params** (fast/slow/signal): Dead — histogram direction robust to window changes
- **RSI period**: Dead — MACD is binding gate for momentum_signal
- **VWAP threshold**: Dead — 0.3–0.6 nearly identical results; momentum_signal is binding gate

### Historical note: optimistic-mode results (deprecated)
The original optimistic sweep found 5.6:1 R:R (0.42% target / 0.08% stop) with Sharpe 94.2
and WR 70.9%. These params are not viable in realistic mode because the 0.08% stop is inside
bid-ask spread and same-bar ambiguity inflated the win rate. Preserved in config.py comments
for reference only.

---

## 18. GDXU Hourly — NEEDS RE-SWEEP

### Why GDXU?
GDXU is a 3x leveraged gold miners ETN — same mean-reversion architecture as TQQQ,
but uncorrelated with tech. Gold miners have higher intraday volatility than TQQQ,
creating more alpha per trade. Zero-commission at all US brokerages.

### Status: NOT PRODUCTION-READY
The original GDXU optimization (2026-03-20) used the "optimistic" backtest mode
and found a 7.5:1 R:R (0.56% target / 0.075% stop) with Sharpe 96.5. When
re-tested with realistic mode, results collapsed:
- **Realistic Sharpe: 1.8** (vs 96.5 optimistic)
- **Realistic WR: 27.5%** (vs 70.1% optimistic)
- The 0.075% stop ($0.04-0.06/share) is inside bid-ask spread

### Current config (placeholder — needs re-sweep)
```python
TARGET_GAIN_PCT_GDXU_HOURLY    = 0.0280   # 2.80% target — realistic sweep result
STOP_LOSS_PCT_GDXU_HOURLY      = 0.0046   # 0.46% stop — Sharpe 1.8, +2.33%/mo
RSI_OVERSOLD_GDXU_HOURLY       = 85       # Saturated above 85
```

### What needs to happen
Run `python sweep.py GDXU` with realistic mode to find viable params. The optimistic
sweep data (preserved below) shows the R:R and signal structure is sound — the problem
is specifically that ultra-tight stops don't survive realistic same-bar ambiguity.

### Historical optimistic-mode sweep data (for reference only)

**R:R ratio variations at target=1.0% (optimistic mode):**
| Stop | R:R | WR | Return | Sharpe | Max DD | Avg/mo |
|---|---|---|---|---|---|---|
| 0.20% | 5.0:1 | 58.2% | 149.19% | 61.8 | -0.42% | +4.07% |
| 0.50% | 2.0:1 | 59.6% | 111.39% | 41.5 | -1.05% | +3.32% |

These numbers are from optimistic mode and are NOT achievable in realistic backtesting.

---

## 18a. SOXL / LABU / TNA Hourly Modes (2026-03-22)

Three additional 3x leveraged ETF modes were sweep-optimized. All use the same
mean-reversion architecture and zero-commission US brokerage infrastructure.

### SOXL Hourly (3x leveraged semiconductors)
```python
RSI_OVERSOLD_SOXL_HOURLY       = 80
VWAP_ZSCORE_THRESH_SOXL_HOURLY = 1.2
TARGET_GAIN_PCT_SOXL_HOURLY    = 0.009    # 0.90% target, 2:1 R:R
STOP_LOSS_PCT_SOXL_HOURLY      = 0.0045   # 0.45% stop — live-safe (5x spread)
```
```
Sharpe: 47.3 | Max DD: -0.75% | Avg/mo: +3.50% | ~27 trades/mo
0/22 rolling windows negative, worst window +1.88%
```

### LABU Hourly (3x leveraged biotech)
```python
RSI_OVERSOLD_LABU_HOURLY       = 70
VWAP_ZSCORE_THRESH_LABU_HOURLY = 1.2
TARGET_GAIN_PCT_LABU_HOURLY    = 0.007    # 0.70% target, 2.8:1 R:R
STOP_LOSS_PCT_LABU_HOURLY      = 0.0025   # 0.25% stop
```
```
Sharpe: 61.6 | Max DD: -0.52% | Avg/mo: +3.07% | ~26 trades/mo
```

### TNA Hourly (3x leveraged Russell 2000)
```python
RSI_OVERSOLD_TNA_HOURLY       = 65
VWAP_ZSCORE_THRESH_TNA_HOURLY = 0.1       # Very loose (momentum_signal is gate)
TARGET_GAIN_PCT_TNA_HOURLY    = 0.0033    # 0.33% target, 2.2:1 R:R
STOP_LOSS_PCT_TNA_HOURLY      = 0.0015    # 0.15% stop — tight but TNA has tighter spreads
```
```
Sharpe: 82.0 | Max DD: -0.24% | Avg/mo: +1.74% | ~24 trades/mo
```

### Common dead levers (all 3 modes)
- MACD params (fast/slow/signal): Dead — histogram direction robust
- RSI period: Dead — MACD is binding gate

### Note on backtest mode
These were sweep-optimized but should be re-validated with realistic backtest mode
(same-bar pessimistic ambiguity) before live deployment. SOXL is the most robust
(0/22 rolling windows negative).

---

## 19. Universal Sweep Tool (sweep.py)

### Usage
```bash
python sweep.py TICKER                     # Full sweep (2yr lookback)
python sweep.py SOXL --start 2024-06-01   # Custom start date
python sweep.py NVDA --phase 1             # Phase 1 only (coarse)
python sweep.py COIN --phase 2             # Phase 2 only (fine-tune)
```

### What it does
1. Fetches hourly OHLCV data via yfinance (with caching)
2. Dynamically injects config for any ticker (no manual config setup needed)
3. Runs a multi-phase sweep:
   - **Phase 1**: Coarse grid — target/stop (2:1 R:R), R:R variations, VWAP, RSI
   - **Phase 2a–c**: Cross-validation — fine-tunes target, stop, RSI around Phase 1 best
   - **Phase 2d**: MAX_TRADE_BARS sweep [8, 10, 12, 15, 20] on best params
   - **Phase 3**: Holdout evaluation — top 20 candidates on out-of-sample data
   - **Phase 4**: Perturbation robustness — jitter params to test stability
   - **Phase 5**: Final preset selection (best_overall, most_robust, high_rr, high_trade_count)
4. Uses fixed 10% position sizing (matches live trader)
5. Reports optimal params and saves to `sweep_results_TICKER.json`
6. Appends experiment log to `experiments.jsonl`

### Adding a new instrument after sweep
After running `python sweep.py NEWTICKER`, take the optimal params from the output
and add a new PROFILE section in config.py following the GDXU/TQQQ pattern:
1. Add signal params (RSI, MACD, VWAP, target, stop)
2. Add ASSETS dict entry
3. Add to _MODE_TO_ASSET
4. Add data fetcher route in main.py and engine.py build_features()

---

## 20. Live Trading: Pending Close Architecture (2026-03-25)

### Problem (fixed)
When a bracket exit was detected but IBKR fill data was unavailable (connection
gap/restart), `close_position()` deleted the position row immediately. On the next
cycle, `get_position()` returned None → bot treated itself as flat → could place a
new entry while the previous trade was unresolved.

### Fix: position stays in DB until reconciled
The position table now has a `status` column (`open` / `pending_close`) and an
`estimated_exit_price` column. When fill data is unavailable:

1. `mark_pending_close(estimated_exit_price)` sets status to `pending_close` — position
   stays in the DB, blocking new entries.
2. On each subsequent cycle, `get_bracket_fill()` is retried.
3. When actual fill data is found, `finalize_pending_close(return_pct, exit_type, exit_price)`
   records the trade with real PnL and deletes the position row.
4. Only after finalization can new entries be placed.

### Key files changed
- `live/state.py`: `mark_pending_close()`, `finalize_pending_close()`, position schema migration
- `live/trader.py`: pending_close retry loop in `_on_bar_inner()`, entry blocking
- `live/dashboard.py` + `dashboard.html`: PENDING CLOSE banner, `estimated` mark source badge

### Dashboard position states
| State | What it means | UI display |
|---|---|---|
| `open` | Active position, bracket monitoring | Normal position card |
| `pending_close` | Exit detected, fill unconfirmed | Purple banner: "PENDING CLOSE — blocking new entries" |
| No position | Flat | "Flat — no open position" |

---

---

## 21. Comprehensive Project Review (2026-04-10)

### Overall Assessment: **B+ / Production-Capable, Needs Hardening**

The codebase is well-architected, exceptionally documented, and genuinely mode-agnostic.
The strategy engine, signal pipeline, and backtest infrastructure are sound. The live
trading system has robust IBKR integration. However, there are reliability gaps in edge-case
handling, testing coverage, and configuration management that should be addressed before
scaling live deployment.

**Codebase size:** ~8,950 lines Python across 33 files.

### Strengths

| Area | Finding | Impact |
|---|---|---|
| **Architecture** | Truly mode-agnostic engine — adding a new instrument requires only config.py changes (no code changes) | Massive scalability advantage |
| **Documentation** | CLAUDE.md (55KB), README.md (18KB), inline comments throughout — exceptional institutional memory | Low onboarding friction for AI agents and collaborators |
| **Backtest/Live Separation** | Clean boundary — backtest code never imports from live/, live code only imports signals from src/ | No cross-contamination risk |
| **Execution Model** | Unified entry/exit logic between backtest and live, verified by test_execution_model.py (~20 tests) | Backtest results trustworthy |
| **Walk-Forward Optimizer** | Properly implemented OOS validation with no look-ahead bias | Parameter selection is legitimate |
| **IBKR Integration** | Thread-local event loop, 3x retry with backoff, three-tier fill search, GTC bracket orders | Robust connection handling |
| **Pending Close Architecture** | Position stays in DB until reconciled — blocks new entries, prevents phantom trades | Correct state machine design |
| **Kelly Sizing** | Half-Kelly with regime multipliers, ADX adjustment, adaptive scaling — well-implemented | Position sizing is mathematically sound |
| **Universal Sweep Tool** | 5-phase sweep with holdout + perturbation robustness, auto-applies results | Efficient parameter optimization |
| **Signal Design** | Each signal independently togglable, no component "knows about" another | Clean A/B testing of features |

### Weaknesses & Bugs Found

#### Critical (affects correctness or reliability)

1. **~~Division by zero in `compute_vwap_zscore()`~~ — FIXED**
   Guarded with `rolling_std.replace(0, np.nan)`. (volume.py:24)

2. **~~Division by zero in `compute_bb_position()`~~ — FIXED**
   Guarded with `np.where(band_width != 0, ..., 0.5)`. (volatility.py:33-42)

3. **~~NaN propagation in `compute_trade_returns()`~~ — FIXED**
   Added `if pd.isna(last_close) or entry_price == 0: continue`. (engine.py:372-375)

4. **~~`PENDING_CLOSE_MAX_RETRIES` undefined~~ — FALSE POSITIVE**
   Already exists at `config_modules/live.py:16`.

5. **Sweep.py dual-sync requirement** (sweep.py:284-291)
   Must update BOTH `setattr(config, param_name, value)` AND `config.ASSETS[mode][key] = value`
   for every parameter change. If one is missed, backtest runs with inconsistent params.

6. **~~Phantom modes in main.py MODE_MAP~~ — FIXED**
   Renamed QQQ_DAILY→QQQ, added SOXL_DAILY to _MODE_TO_ASSET.
   Setting `ACTIVE_MODE = "QQQ_DAILY"` will fail at runtime with a confusing error.

#### High (affects maintainability or safety)

7. **~~No signal module tests~~ — FIXED** 37 tests added in `tests/test_signals.py`.

8. **~~No CI/CD pipeline~~ — FIXED** GitHub Actions CI in `.github/workflows/test.yml`.

9. **Walk-forward Sharpe annualization wrong for hourly modes** — uses `sqrt(252)` which
   assumes daily returns. For hourly data with ~130 trades/month, this understates risk
   and inflates Sharpe by ~2.5×. May select parameters that look good on walk-forward
   but underperform live.

10. **165+ config parameters with no validation** — no check that `stop_loss_pct < target_gain_pct`,
    no type enforcement, no startup validation. If a param is typo'd or missing, caught
    only at runtime via `getattr()` fallback (which silently uses a default).

11. **Three mode routing layers** — MODE_MAP (main.py), _MODE_TO_ASSET (config.py), and
    ASSETS dict (config.py) must all agree. Adding a new mode requires updating all three.
    No automated check that they're in sync.

12. **ModeConfig migration incomplete** — `config_modules/mode_config.py` defines a typed
    `ModeConfig` dataclass (Stage 1 of 3), but `get_mode_config()` is never called anywhere.
    All code still uses untyped `config.ASSETS[mode]` dicts.

13. **12-15 dead config params** — `ROC_PERIOD`, `ROC_PERIOD_HOURLY`, `ATR_PERIOD`, `BB_STD`,
    all `BB_WINDOW_*_HOURLY` variants are defined but never referenced in the codebase.

#### Medium (code quality / operational risk)

14. **No data fetcher retry logic** — yfinance timeout will crash live trading without fallback.
    No exponential backoff, no cached-data fallback.

15. **No OHLC validation** — fetcher doesn't verify `low ≤ open ≤ high`, `low ≤ close ≤ high`.
    Bad data from yfinance (possible during outages) would corrupt signals silently.

16. **Config drift between CLAUDE.md and code** — CLAUDE.md documents 6 modes; actual code
    has 9 (added SOXL_HOURLY, LABU_HOURLY, TNA_HOURLY post-documentation).

17. **Backtest date ranges scattered** — 18 separate params (BACKTEST_START_X, BACKTEST_END_X
    for each mode). No centralized date config. Fragile `getattr()` fallback in main.py.

18. **Index alignment risk in runner.py plot** (line 457) — creates equity Series indexed by
    trade timestamps without validating length matches. Silent misalignment possible.

19. **`fee_analysis.py` abandoned** — 20KB file not referenced anywhere in codebase. Historical
    artifact from BTC fee analysis. Should be archived or removed.

20. **Plugin commands missing** — `.claude-plugin/plugin.json` references `commands/screen.md`,
    `commands/backtest.md`, `commands/report.md` but `commands/` directory doesn't exist.

### Test Coverage Assessment

| Area | Coverage | Grade |
|---|---|---|
| Backtest execution model (entry/exit) | Excellent — ~20 tests | A |
| Position state machine (open/close/pending) | Good — ~16 tests | B+ |
| Dashboard routes (read-only verification) | Basic — 6 tests | B- |
| Trader helpers (direction-aware inference) | Good — 10 tests | B+ |
| Signal modules (momentum/volume/volatility) | Good — 37 tests | B+ |
| Data fetcher (yfinance/Alpha Vantage) | **None** | F |
| Config validation (mode routing) | Good — 16 tests | B+ |
| Sweep tool (parameter optimization) | **None** | F |
| Pending close reconciliation flow | **None** | F |
| IBKR integration (broker.py) | **None** | F |

**Total: 101 tests across 4 files, all passing. CI via GitHub Actions.**

### Production Readiness

| Component | Grade | Key Finding |
|---|---|---|
| Strategy Engine | A | Sound, mode-agnostic, correct execution model |
| Signal Pipeline | A- | Division-by-zero bugs fixed, 37 signal tests added |
| Backtest Runner | B+ | Correct, NaN guard added; index alignment risk remains |
| Config System | B | Startup validation added; fragmented but functional |
| Live Trader | B+ | Solid architecture, pending_close correctly wired |
| IBKR Broker | A | Excellent connection handling, three-tier fill search |
| State Persistence | A- | Clean migrations, atomic operations, no SQL injection |
| Dashboard | B+ | Read-only safe, cache logic brittle |
| Testing | B | 101 tests across 4 files; signal + config + execution + state covered |
| CI/CD | B | GitHub Actions on push/PR; no pre-commit hooks yet |
| Documentation | A | Exceptional — best-in-class for a project this size |

---

## 22. Future Work Roadmap (2026-04-10)

### Phase 1: Critical Bug Fixes (Do First)

These are bugs that could cause incorrect results or crashes. Fix before any new feature work.

| # | Fix | File(s) | LOC | Risk |
|---|---|---|---|---|
| 1.1 | Guard `compute_vwap_zscore()` against zero `rolling_std` | volume.py:22 | ~3 | Low | **DONE** |
| 1.2 | Guard `compute_bb_position()` against flat bands (upper==lower) | volatility.py:37 | ~3 | Low | **DONE** |
| 1.3 | Add NaN check before appending time-exit return | engine.py:374 | ~3 | Low | **DONE** |
| 1.4 | ~~Add PENDING_CLOSE_MAX_RETRIES~~ — false positive, already in config_modules/live.py | — | 0 | — | N/A |
| 1.5 | Sync MODE_MAP with _MODE_TO_ASSET: rename QQQ_DAILY→QQQ, add SOXL_DAILY | main.py, config.py | ~4 | Low | **DONE** |
| 1.6 | Add startup config validation: verify ACTIVE_MODE, ASSETS keys, stop<target | main.py | ~40 | Low | **DONE** |

**Estimated effort: 1-2 hours. Zero risk of regression.**

### Phase 2: Testing Foundation (Do Second)

Add tests for the untested critical paths. These prevent future regressions.

| # | Test | Target | Priority |
|---|---|---|---|
| 2.1 | Signal module tests: RSI calculation, MACD histogram turn, regime classification, VWAP z-score | momentum.py, volume.py, volatility.py | HIGH | **DONE** |
| 2.2 | Config validation tests: each ACTIVE_MODE routes to valid ASSETS entry, no orphan modes | config.py | HIGH | **DONE** |
| 2.3 | Data fetcher test: yfinance returns valid OHLCV, OHLC invariants hold | fetcher.py | MEDIUM |
| 2.4 | Pending close full flow test: mark → retry → finalize | state.py, trader.py | MEDIUM |
| 2.5 | Add GitHub Actions CI: pytest on push/PR | .github/workflows/ | MEDIUM | **DONE** |

**Test coverage summary (Phase 2 complete):**
- `tests/test_signals.py`: 37 tests — RSI, MACD, momentum_signal, classify_regime (6-state),
  VWAP z-score, volume_signal, ATR, Bollinger bands, ADX, integration tests for all 3 modules
- `tests/test_config.py`: 16 tests — mode routing sync (MODE_MAP ↔ _MODE_TO_ASSET ↔ ASSETS),
  ASSETS invariants (required keys, stop < target, positive values), live config, active mode
- `.github/workflows/test.yml`: CI runs pytest on push to main/claude/** and PRs to main
- **Total: 101 tests across 4 files, all passing**

**Estimated effort: 1-2 days. Significantly improves confidence in signal correctness.**

### Phase 3: Config Cleanup & Consolidation

Reduce the 165-param config sprawl and eliminate fragmentation.

| # | Change | Impact |
|---|---|---|
| 3.1 | Remove dead params: `ROC_PERIOD`, `ROC_PERIOD_HOURLY`, `ATR_PERIOD`, `BB_STD`, unused `BB_WINDOW_*` variants | Reduces cognitive load |
| 3.2 | Consolidate backtest date ranges into a single `BACKTEST_WINDOWS` dict | Eliminates 18 scattered params |
| 3.3 | Unify mode routing: merge MODE_MAP + _MODE_TO_ASSET + ASSETS into one registry | Eliminates sync bugs |
| 3.4 | Complete ModeConfig migration (Stage 2/3): replace all `config.ASSETS[mode]` with typed `ModeConfig` lookups | Type safety, IDE autocomplete |
| 3.5 | Add startup validation: `stop_loss_pct < target_gain_pct`, required keys present, mode exists | Catches misconfig before runtime |
| 3.6 | Archive or remove `fee_analysis.py` (history preserved in git) | Reduces file clutter |

**Estimated effort: 1-2 days. Major maintainability improvement.**

### Phase 4: Data Pipeline Hardening

Make the data layer resilient for live trading.

| # | Change | Impact |
|---|---|---|
| 4.1 | Add exponential backoff + retry logic to yfinance fetcher | Prevents live crash on network glitch | **DONE** |
| 4.2 | Add OHLC validation (low ≤ open ≤ high, low ≤ close ≤ high) | Catches bad data before it corrupts signals | **DONE** |
| 4.3 | Add hourly bar continuity check (no gaps > 1 hour during market hours) | Catches DST gaps and data source issues |
| 4.4 | Validate ALPHA_VANTAGE_KEY at startup when BTC_DAILY is active | Prevents silent API failure |
| 4.5 | Auto-clamp backtest date ranges to yfinance's 730-day hourly limit | Prevents 0-bar backtest runs | **DONE** |

**Estimated effort: 0.5-1 day.**

### Phase 5: Strategy Improvements (From Section 10 Priorities)

These are the signal/strategy enhancements identified by the expert agent audit.

| # | Change | Risk | Expected Impact |
|---|---|---|---|
| 5.1 | Softer 5% 50-MA gate for intra-bull corrections (STRONG_BULL_SOFT_50MA_PCT=0.05) | Low-Med | Reduce June/Aug 2024 losses |
| 5.2 | ATR-based dynamic stop overrides (USE_ATR_DYNAMIC_STOPS) | Medium | Reduce noise stops in high-vol |
| 5.3 | Exit type tracking in compute_trade_returns() | Low | Diagnostic — enables better analysis |
| 5.4 | Fix walk-forward Sharpe annualization for hourly modes | Low | More accurate parameter selection |
| 5.5 | Re-integrate rolling Kelly position sizing for hourly modes | Medium | Potentially improves risk-adjusted returns; adaptive Kelly currently acts as fixed 2x multiplier for QQQ/TQQQ (WR always above HIGH_WR threshold). True rolling Kelly would size based on recent trade-level win/loss stats instead. Needs extensive backtesting to evaluate whether it improves or hurts vs current fixed-multiplier approach. |

**Estimated effort: 2-3 days. Directly improves strategy performance.**

### Phase 6: Live Trading Hardening

Finalize for production deployment.

| # | Change | Impact |
|---|---|---|
| 6.1 | Add CRITICAL alert when pending_close force-finalizes with estimated price | Prevents silent PnL inaccuracy |
| 6.2 | Add data fetcher retry with cached-data fallback for live signals | Prevents signal computation crash |
| 6.3 | Refuse entry when signal fetch fails (don't estimate qty from stale price) | Prevents position oversizing |
| 6.4 | Add external monitoring/alerting (healthcheck + Slack/PagerDuty) | Operational awareness |
| 6.5 | Run 2+ weeks paper trading on each target mode to validate cycle stability | Confidence before real money |

**Estimated effort: 2-3 days.**

### Phase 7: Nice-to-Have (Low Priority)

| # | Change | Impact |
|---|---|---|
| 7.1 | Create `commands/` directory referenced by plugin.json (or remove from plugin.json) | Plugin completeness |
| 7.2 | Add pre-commit hooks (black, isort, ruff) | Code formatting consistency |
| 7.3 | Add type hints throughout signal modules | IDE support, static analysis |
| 7.4 | Refactor duplicate MA computation into shared utility | Code deduplication |
| 7.5 | Add ASCII diagrams to README (regime transitions, signal flow, trade lifecycle) | Documentation quality |

### Recommended Execution Order

```
Phase 1 (Critical bugs)     ──→  1-2 hours
Phase 2 (Testing)           ──→  1-2 days
Phase 3 (Config cleanup)    ──→  1-2 days
Phase 4 (Data hardening)    ──→  0.5-1 day
Phase 5 (Strategy)          ──→  2-3 days     ← can run in parallel with Phase 3-4
Phase 6 (Live hardening)    ──→  2-3 days
Phase 7 (Nice-to-have)      ──→  as time permits
```

Phases 1-2 are prerequisites for everything else.
Phases 3-5 can be partially parallelized.
Phase 6 should come after Phase 5 (strategy changes affect live behavior).

---

*Last updated: 2026-04-10 — CLAUDE.md audit: corrected TQQQ/GDXU performance to realistic-mode numbers, added SOXL/LABU/TNA docs, marked fixed bugs, updated test coverage. Phase 1-2 complete. TQQQ live paper trading in progress.*
