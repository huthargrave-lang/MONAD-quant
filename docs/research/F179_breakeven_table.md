# Breakeven win rates for every configured exit band ([`F179`](../../RESEARCH_WEB.md))

**Status:** every figure in F179 re-derived from `config.ASSETS`, plus the full table it
did not have. All arithmetic, no market data — reproducible from a clone with no network.

**Guard:** `tests/test_f179_breakeven_table.py` (this table) and
`tests/test_f17_breakeven_arithmetic.py` (the original finding).

---

## The arithmetic

A fixed target/stop band breaks even at

```
breakeven win rate = stop / (target + stop)
```

With a round-trip cost `c` charged against both legs, the win shrinks and the loss deepens:

```
breakeven(c) = (stop + c) / ((target - c) + (stop + c))
```

## Every shipped band

Read from `config.ASSETS`, sorted by reward:risk:

| mode | target | stop | R:R | BE @ 0 | BE @ 2 bps | BE @ 5 bps |
|---|---:|---:|---:|---:|---:|---:|
| GDXU_HOURLY | 2.800% | 0.460% | 6.09:1 | 14.1% | 14.7% | 15.6% |
| LABU_HOURLY | 0.700% | 0.250% | 2.80:1 | 26.3% | 28.4% | 31.6% |
| TNA_HOURLY | 0.330% | 0.150% | 2.20:1 | 31.2% | 35.4% | **41.7%** |
| BTC (daily) | 3.000% | 1.500% | 2.00:1 | 33.3% | 33.8% | 34.4% |
| BTC_HOURLY | 0.400% | 0.200% | 2.00:1 | 33.3% | 36.7% | **41.7%** |
| QQQ_HOURLY | 0.240% | 0.120% | 2.00:1 | 33.3% | 38.9% | **47.2%** |
| TQQQ_HOURLY | 1.000% | 0.500% | 2.00:1 | 33.3% | 34.7% | 36.7% |
| SOXL_HOURLY | 0.900% | 0.450% | 2.00:1 | 33.3% | 34.8% | 37.0% |
| QQQ (daily) | 1.000% | 0.600% | 1.67:1 | 37.5% | 38.7% | 40.6% |
| SOXL (daily) | 2.000% | 1.200% | 1.67:1 | 37.5% | 38.1% | 39.1% |

Every figure F179 states reproduces: the daily ETF bands are **1.67:1** (not 2:1) with a
**37.5%** zero-cost breakeven; BTC daily is the 2:1 band at **33.3% / 33.8% / 34.4%**; and
the harsh-cost separation between the two 1.67:1 bands is **40.6% (QQQ)** vs **39.1%
(SOXL)** — the tighter band pays more for the same fixed cost.

## What the full table adds

F179's blanket claim was carefully scoped: *"no shipped band anywhere in `config.ASSETS`
has a **zero-cost** breakeven above 41%"*. That holds — the maximum is **37.5%**.

Under harsh cost it stops holding, and the exceptions are the interesting part. **Three
bands cross 41% at 5 bps**: TNA_HOURLY (41.7%), BTC_HOURLY (41.7%) and QQQ_HOURLY
(**47.2%**). Nothing about their reward:risk explains it — BTC_HOURLY and QQQ_HOURLY are
both nominally 2:1, the same ratio as BTC daily, which only reaches 34.4%.

What explains it is **band width in basis points**, i.e. how much of the whole band a
fixed cost consumes:

| mode | band (bps) | 5 bps eats | 2 bps eats |
|---|---:|---:|---:|
| QQQ_HOURLY | 36 | **13.9%** | 5.6% |
| TNA_HOURLY | 48 | **10.4%** | 4.2% |
| BTC_HOURLY | 60 | **8.3%** | 3.3% |
| LABU_HOURLY | 95 | 5.3% | 2.1% |
| SOXL_HOURLY | 135 | 3.7% | 1.5% |
| TQQQ_HOURLY | 150 | 3.3% | 1.3% |
| QQQ (daily) | 160 | 3.1% | 1.2% |
| SOXL (daily) | 320 | 1.6% | 0.6% |
| GDXU_HOURLY | 326 | 1.5% | 0.6% |
| BTC (daily) | 450 | 1.1% | 0.4% |

**Reward:risk sets the zero-cost breakeven; band width sets how fast cost moves it.** Two
bands with the same 2:1 ratio — BTC daily at 450 bps and QQQ_HOURLY at 36 bps — face
breakevens of 34.4% and 47.2% at the same 5 bps, a 12.8-point gap that the ratio alone
cannot see. Quoting a mode's R:R without its width says nothing about how much cost it can
survive.

This is the same quantity, from the other direction, as the stop-versus-spread work: a
36-bps band on QQQ is thin enough that ordinary friction is a first-order term rather than
a correction.

## Scope

* This is arithmetic about *configured* bands, not a claim about realised win rates. It
  says what a band **needs**, never what it **gets**.
* 2 bps and 5 bps are the repo's realistic and harsh cost settings; both are charged
  round-trip against both legs. Real slippage on a thin instrument can exceed either.
* GDXU_HOURLY's 6.09:1 band flatters this table. CLAUDE.md marks that mode **NEEDS
  RE-SWEEP** — its 0.46% stop came from an optimistic-mode sweep — so its 14.1% breakeven
  should be read as a property of unvalidated parameters.
