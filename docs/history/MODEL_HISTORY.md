# MONAD Quant — Model History (archived from CLAUDE.md, 2026-06-19)

> Dated optimization session logs, per-mode sweep results, audits, and roadmaps,
> moved out of CLAUDE.md to keep the auto-loaded file lean (agent context-rot fix).
> **⚠ The headline numbers here (Sharpe 25–94, +0.7–3.5%/mo) are SUPERSEDED** — see
> `RESEARCH_WEB.md` (F13/F14/F15/F16/F17/D4) and `ctx web --live` for current truth.
> This is institutional history, not current fact.

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

## 21. Comprehensive Project Review (2026-04-17)

### Overall Assessment: **B / Production-Capable on Paper, Ops Gaps for Real Money**

Significant hardening work has landed since the April 10 audit. All 130 tests pass locally.
Phase 1 (critical bugs), Phase 2 (testing foundation), Phase 4 (data hardening ~80% done),
and Phase 6.1–6.3 (live signal safety, cache fallback, CRITICAL escalation) are complete.
The system is running live TQQQ paper trades on a Pi and reconciling correctly.

The grade stepped down slightly from B+ because three issues previously flagged remain
unfixed (walk-forward Sharpe bug, sweep.py dual-sync, CI cannot collect `test_dashboard.py`),
and two workstreams are barely started: Phase 3 (config cleanup, 0/6 items) and Phase 5
(strategy improvements, 1/5 items). Real-money deployment is blocked on Phase 6.4 (external
alerting — CRITICAL events are logged but no one is paged) and Phase 6.5 (documented 2-week
paper validation protocol).

**Codebase size:** ~10,170 lines Python across 36 files (+1,220 since April 10).
**Test suite:** 130 tests, all passing when `test_dashboard.py` is excluded.

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

## 22. Future Work Roadmap (2026-04-17)

### Progress summary (since the 2026-04-10 audit)

| Phase | Scope | Status |
|---|---|---|
| **1** | Critical bug fixes | ✅ 6/6 complete |
| **2** | Testing foundation | ✅ 5/5 complete — 130 tests, all pass locally |
| **3** | Config cleanup | ⬜ 0/6 — **not started** |
| **4** | Data pipeline hardening | 🟡 3/5 — 4.1, 4.2, 4.5 done; 4.3, 4.4 pending |
| **5** | Strategy improvements | 🟡 2/5 — 5.1 active, 5.3 instrumented; 5.2, 5.4, 5.5 pending |
| **6** | Live trading hardening | 🟡 3/5 — 6.1, 6.2, 6.3 done; 6.4, 6.5 pending |
| **7** | Nice-to-have | 🟡 1/5 — pre-commit and plugin cleanup still open |

Overall: ~30/44 roadmap items done (~68%). Live paper trading is active on TQQQ.
Real-money deployment remains blocked on 6.4 (no external alerting) and 6.5 (no
documented validation protocol).

### Phase A: Critical — fix or lose confidence in results

These three items were flagged on April 10 but never shipped. They actively hurt
the project today: one makes CI unreliable, one biases walk-forward selection,
one is a sharp edge waiting to cut someone editing sweep.py.

| # | Fix | File | Why it matters |
|---|---|---|---|
| **A.1** | CI can't collect `tests/test_dashboard.py` (fastapi missing) | `.github/workflows/test.yml` + `requirements.txt` | Any future test-discovery change that includes the dashboard file will break CI. Also means `test_live_signals.py` (Phase 6.3) and `test_trader_helpers.py` aren't even running in CI — the workflow hard-codes a list of 4 files. Fix: install `fastapi` in the CI step and run `pytest tests/` (whole dir). |
| **A.2** | Walk-forward Sharpe uses `sqrt(252)` for hourly modes | `src/optimization/walk_forward.py:42` | Hourly bars with ~1,500+ observations/year inflate Sharpe by ~2.5×. Parameter selection may look great in walk-forward and underperform live. Fix: choose the annualization factor based on timeframe (or compute directly from the returns index). |
| **A.3** | `sweep.py` requires dual-sync for every param (setattr + ASSETS dict) | `sweep.py:284–291` and every `setattr` block | Miss one layer and the backtest runs with inconsistent params. Extract to `_update_mode_param(mode, key, value)` that touches both in one place. |

### Phase B: High — config sprawl and untouched strategy work

| # | Change | Risk | Notes |
|---|---|---|---|
| **B.1** | Remove dead params: `ROC_PERIOD`, `ROC_PERIOD_HOURLY`, `ATR_PERIOD`, `BB_STD`, unused `BB_WINDOW_*_HOURLY` variants | Low | `grep -r` confirms none referenced outside config.py itself |
| **B.2** | Collapse mode routing into one registry (MODE_MAP + `_MODE_TO_ASSET` + `ASSETS`) — derive the first two as views of `ASSETS` | Low-Med | Eliminates the 3-way sync bug every new mode can hit |
| **B.3** | Complete ModeConfig migration (stage 2/3): have `live/trader.py` and `live/signals.py` call `get_mode_config()` instead of indexing `config.ASSETS[mode]` | Low | `get_mode_config()` is defined but never called |
| **B.4** | Consolidate scattered backtest date params into a single `BACKTEST_WINDOWS` dict keyed by mode | Low | 18 BACKTEST_START_*/END_* variables today |
| **B.5** | Implement ATR-based dynamic stops (5.2) — `USE_ATR_DYNAMIC_STOPS` flag is defined but no implementation in `compute_trade_returns()` | Medium | Expected impact: fewer noise-triggered stops in high-vol periods (June/Aug 2024) |
| **B.6** | Rolling Kelly re-integration (5.5) — current adaptive Kelly acts as a fixed 2× multiplier for QQQ/TQQQ because baseline WR (~60%) always exceeds HIGH_WR threshold | Medium | Size from rolling trade stats instead of fixed regime multipliers. Must backtest extensively before shipping. |

### Phase C: Medium — operational readiness for real money

Real-money deployment should not happen until C.1 and C.2 are done.

| # | Change | Why |
|---|---|---|
| **C.1** | External alerting for CRITICAL monitor events (Slack webhook or similar) | CRITICAL events (force-finalize with estimated PnL, software-stop triggered, N consecutive signal failures) land in SQLite but nobody is paged. On a Pi this means the operator finds out next time they open the dashboard. |
| **C.2** | Documented 2-week paper validation protocol (pre-flight checklist) | Nothing in the repo defines "ready for real money." Should cover: cycle stability over a full trading week, no pending_close retries beyond 1 cycle, no CRITICAL events, dashboard mark sources ≥95% "live"/"delayed" (not "last_close"). |
| **C.3** | Data pipeline 4.3: hourly bar continuity check (no gaps > 1h during market hours) | DST transitions and yfinance outages can silently drop bars. |
| **C.4** | Data pipeline 4.4: validate `ALPHA_VANTAGE_KEY` at startup when BTC_DAILY is active | Currently fails silently at runtime if the key is missing. |
| **C.5** | Tests for `live/broker.py` (mock IBKR) — bracket parsing, fill-search fallbacks, reconnect logic | Zero coverage today. Biggest untested risk surface in live/. |
| **C.6** | Test for the Phase 6.3 escalation path in `trader.py` (consecutive failures → CRITICAL) | `test_live_signals.py` covers `signals.py`; the escalation in `trader.py` is only verified by hand. |

### Phase D: Low — quality of life

| # | Change | Notes |
|---|---|---|
| **D.1** | Delete `commands` array from `.claude-plugin/plugin.json` (referenced files don't exist) or create the three `commands/*.md` files | Trivial; fixes a broken manifest |
| **D.2** | Add pre-commit hooks (black, isort, ruff) | 10-minute setup, catches trivial diffs |
| **D.3** | Fix CLAUDE.md §1 and README.md mode tables — both still reference 6 modes; current code has 9 live modes (BTC daily/hourly, QQQ hourly, TQQQ, GDXU, SOXL, LABU, TNA, + QQQ/SOXL daily variants) | Documentation drift |
| **D.4** | Refactor duplicate MA / MACD-histogram-turn logic into `src/signals/utils.py` | ~30 LOC dedup across momentum.py, volume.py |
| **D.5** | Split `compute_trade_returns()` (181 LOC) — extract exit-type classification into a helper | Readability only; tests cover the current structure |
| **D.6** | Archive or remove `fee_analysis.py` (20KB, no imports reference it) | Historical artifact |

### Recommended execution order

```
Phase A (Critical)     ──→  half day     — do before any new feature work
Phase C.1 + C.2        ──→  2–3 days     — gate real-money deployment on these
Phase B (Config + 5.2) ──→  2–3 days     — parallelizable with C
Phase C.3–C.6          ──→  1–2 days
Phase B.6 (rolling Kelly) ──→ 2–3 days   — needs its own backtest sweep
Phase D                ──→  as time permits
```

Phase A is the only hard prerequisite. C.1 and C.2 should come before scaling from
paper to real money. Everything else can be parallelized.

---

*Last updated: 2026-04-17 — fresh audit after Phases 4/6.1/6.2/6.3 landed. 130 tests passing, live paper on TQQQ reconciling correctly. Three April-10 criticals (walk-forward Sharpe, sweep dual-sync, CI dashboard collection) still unfixed; Phase 3 not started; Phase 6.4–6.5 gate real-money deployment.*

---

## 22-ARCHIVE. Original Future Work Roadmap (2026-04-10)

*Preserved for history. The April-17 audit (Section 22 above) supersedes this.
Items marked DONE here are still done; items not marked DONE were re-scored
in the April-17 view, which is the current source of truth.*

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
| 6.1 | Add CRITICAL alert when pending_close force-finalizes with estimated price | Prevents silent PnL inaccuracy | **DONE** — force-finalize path and software-stop-fill-unavailable path both escalated from WARNING → CRITICAL (log.critical + monitor_event CRITICAL). Software stop trigger itself also now emits CRITICAL monitor event. |
| 6.2 | Add data fetcher retry with cached-data fallback for live signals | Prevents signal computation crash | **DONE** — `_fetch_recent_bars()` caches last successful OHLCV in memory; on yfinance transient failure (exception or empty), falls back to cache. Cached data still passes ALL Phase 6.3 validation (staleness, min_bars). Cache only updates from live fetches (not re-cached from fallback). 6 cache-specific tests added. |
| 6.3 | Refuse entry when signal fetch fails (don't estimate qty from stale price) | Prevents position oversizing | **DONE** — `live/signals.py` raises RuntimeError on yfinance exceptions, empty/partial data, stale bars (LIVE_MAX_BAR_STALENESS_HOURS=120), or NaN features. `live/trader.py` escalates to CRITICAL monitor events after LIVE_SIGNAL_FAIL_ALERT_THRESHOLD (=2) consecutive failures. Entry block is mandatory: `sig_info is None` → `return signal_error`, never trades on stored snapshot. 9 unit tests in `tests/test_live_signals.py`. |
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

*Original Phase 1-2 completion note (2026-04-10): corrected TQQQ/GDXU performance to realistic-mode numbers, added SOXL/LABU/TNA docs, marked fixed bugs, updated test coverage. TQQQ live paper trading in progress.*

