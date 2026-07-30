# F266 — the CEF pilot's control is the strategy; the thesis is mostly redundant

**Date:** 2026-07-27 · **Guard:** `tests/test_f266_cef_price_reversion.py` (11 tests)
· **Evidence:** E130 (`cef_discount_pilot_result.json`) · **Changed:** `tools/cef_discount_lab.py`

## What the pilot claimed

`CEF-DISCOUNT` asked whether a NAV-discount z-score predicts 20-bar forward returns across
eight closed-end funds, and reported `first_cut_supports_long_cheap: true`, mean
cheap-minus-rich spread **+1.76%**. It also ran a **price-only control** — rank by trailing
return instead of by discount — annotated *"negative high_minus_low is price MR; not the
discount thesis"*, i.e. carried as a nuisance to be dismissed.

## The nuisance captures 86% of it

| | spread |
|---|---:|
| discount thesis | **+1.76%** |
| price-only control | **+1.50%** |
| excess earned by the NAV data | **+0.25%** |

Per ticker, the discount signal beats its own control on **6 of 8**, and one name carries
most of the dispersion:

| ticker | discount | price-only | excess |
|---|---:|---:|---:|
| PDI | +2.89% | +1.01% | +1.88% |
| BDJ | +4.51% | +2.35% | +2.16% |
| BBN | +2.14% | +2.38% | −0.24% |
| **UTF** | **−4.17%** | +0.99% | **−5.16%** |
| HYT | +1.76% | +1.49% | +0.27% |
| EOS | +1.34% | −0.43% | +1.77% |
| NUV | +1.13% | +1.00% | +0.13% |
| RVT | +4.45% | +3.24% | +1.21% |

The price-only effect is the steadier one: trailing-vs-forward correlation is **negative on
8 of 8** tickers (mean −0.184, range −0.297 to −0.007).

**So the tradable candidate is CEF price mean-reversion, not the discount thesis** — and it
needs only price data, while the NAV proxies the thesis depends on are exactly what this
environment cannot fetch.

## Why this is not the strategy D6 killed

D6 found no risk-adjusted edge for active mean-reversion on BTC/QQQ/TQQQ — instruments with
**no anchor**, where "cheap" means only "down recently." A closed-end fund has a NAV anchor
and a structurally persistent discount, so its price reverting *is* the discount reverting.
The 86% overlap is evidence they are one phenomenon measured two ways, not two signals.

Whether that anchor makes the reversion survive out of sample is the **open question**.
These numbers do not settle it.

## The economics clear costs — the easy part

A 1.5% gross spread over ~20 bars against round-trip friction on a $15 name:

| broker | per leg | two legs | net per rebalance |
|---|---:|---:|---:|
| IBKR | 0.067% | 0.13% | **~1.37%** |
| retail | 0.20% | 0.40% | **~1.10%** |

Against the project's 4–6%/yr bond-ETF benchmark, that is comfortably material. **Caveat:**
equity spread tiers stand in for CEF spreads, and CEFs are typically wider — so this is
optimistic by construction, and F242 established this repo's cost model is a point estimate
that under-charges precisely where a reversion strategy trades.

## The blocker is power — and it is a recording gap, not a data gap

The pilot reports `n_pairs = 421` per ticker. Windows overlap at step 1 with a 20-bar
horizon, so over 501 aligned bars there are only **25 non-overlapping windows per ticker**.
The eight names are same-market, so pooling does not buy 8× the information.

Worse: the artifact records **means with no dispersion**, and `raw_charts_committed: false`.
No later reader can compute a standard error from what is committed. The effect **cannot be
distinguished from noise** — and not because the data is unreachable.

## Fixed at write time, which costs nothing

`cef_discount_lab._quintile_spread` now emits per-side **SD** and **n** alongside the means,
and both the ticker rows and the control carry **`n_independent`** (the non-overlapping
count) so a standard error is built on the right denominator. A single-member quintile
reports `None` rather than a fabricated `0.0`.

The next run is decisive; this one could only ever be descriptive. Same gap F262 found when
F204's single RSI figure turned out to sit at the 97th percentile of its own distribution.

## What would settle it

1. Re-run the pilot with dispersion (needs Yahoo — blocked here).
2. Extend the window: 25 independent observations is thin for a 1.5% effect.
3. Widen the universe beyond 8 names, and test whether fixed-income CEFs (PDI, BBN, HYT,
   NUV) behave differently from equity CEFs (BDJ, EOS, RVT, UTF) — UTF, the outlier, is
   infrastructure.
4. Real CEF spreads, not equity tiers.

## Guards

`tests/test_f266_cef_price_reversion.py`, bidirectional — pins the pilot's own verdict as
the premise being reframed, the 86% share, the +0.25% excess and its 6-of-8 count, UTF as
the outlier, and the 8-of-8 sign consistency; pins the power arithmetic; asserts the
committed artifact carries **no** dispersion and no raw charts, so when that check **fails**
the significance question has become answerable and this node should be superseded; and
covers the new helper on synthetic input, including that dispersion varies with input so a
constant-returning helper would not pass.
