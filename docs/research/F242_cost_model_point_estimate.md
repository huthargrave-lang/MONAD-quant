# F242 — the sweep's cost model is one number, and the strategy trades where it is wrong

**Date:** 2026-07-26 · **Guard:** `tests/test_f242_cost_model_point_estimate.py` (12 tests)
· **Bears on:** H24, H25 · **Data:** committed live paper run, no network

## The model

`sweep.py:228-245` reduces execution cost to a single scalar for the entire sweep window:

```python
median_price      = df_raw["close"].median()
est_spread        = estimate_spread(median_price, broker)
SLIPPAGE_PCT      = round_trip_cost_pct(est_spread, median_price)   # charged to EVERY trade
auto_min_stop_pct = max(0.15, (5 * est_spread / median_price) * 100)
```

Both the per-trade cost and the minimum-stop floor are point estimates at the window median.
Neither had ever been evaluated against real prices: H24/H25 prescribe running `sweep.py`,
which needs market data the providers 403 on here, so
`tests/test_h24_h25_stop_vs_spread_floor.py` correctly stops at *"the verdict needs one
median price per instrument."*

## The prices were already in the repo

`data/live_runs/archive_2026-06-18_pre_clean_run/` is a committed export of the live paper
run: **543 logged TQQQ bars** (2026-03-24 → 2026-06-17) and **65 logged trades**. That is one
instrument, not the three H24 asks about — but it is enough to test the model end to end for
the first time.

## 1 — TQQQ's stop clears, on real prices

Median close **$64.79**.

| broker | est. spread | floor (5× spread, min 0.15%) | TQQQ stop | verdict |
|---|---:|---:|---:|:--|
| IBKR | $0.01 | 0.150% | 0.50% | clears |
| Schwab / Fidelity | $0.03 | 0.232% | 0.50% | clears |
| retail | $0.04 | 0.309% | 0.50% | clears |

H24's TQQQ row is now confirmed rather than assumed. Note *how* it clears at IBKR: the
spread term (0.077%) is **below** the hard 0.15% minimum, so the hard minimum binds and the
IBKR floor carries no information about the spread at all. At retail the spread term does
bind. The two tiers differ in kind, not just degree — the guard asserts both.

## 2 — the window is far too wide for one number

Those 543 bars span **$37.37 – $84.75**, a **2.27×** range that crosses the `$50` spread tier.
Computing the true round-trip cost per bar instead of once at the median:

| broker | modelled (constant) | true min | true median | true max |
|---|---:|---:|---:|---:|
| IBKR | 0.0154% | 0.0118% | 0.0154% | 0.0268% |
| retail | 0.0617% | 0.0472% | 0.0608% | 0.0803% |

The modelled constant sits inside a **2.3× spread** of real values. At the run's low the true
IBKR cost is **1.73×** what the model charges.

## 3 — the error is not mean-zero over *trades*, because this is a dip-buyer

Over **bars**, the point estimate is nearly unbiased — mean error −0.0015 pp (IBKR). The
median is doing exactly its job on the window it was fitted to. That control is what makes
the next number mean something.

Over the **65 real logged trades** it is a **10.7% understatement** (IBKR), with **62% of
trades under-charged**. The mechanism is not subtle: spread-as-a-fraction-of-price rises as
price falls, and an RSI-dip mean-reversion entry selects for low prices by construction.
Logged trade entries sit below the bar median — **$61.87 vs $64.79**.

So a model that is unbiased over the *sampling distribution of bars* is biased over the
*sampling distribution of trades*, and the strategy only pays costs on the latter.

**Magnitude, stated plainly so it is not oversold:** ≈0.0017 pp per trade, ≈0.04 pp/month at
TQQQ's ~24 trades/mo. Small. The contribution is the direction and the mechanism, not the
size — and the size scales with trade count and with an instrument's price range.

## 4 — TNA is the mode with no margin

`config.py:359` sets `STOP_LOSS_PCT_TNA_HOURLY = 0.0015` — **exactly** the hard 0.15% floor,
annotated *"tight but TNA has tighter spreads"*, an assumption nothing in this repository
supports. A parameter resting exactly on its own safety boundary means the constraint bound
and the unconstrained optimum was below it.

That makes TNA the one mode where the median-price point estimate decides pass/fail outright.
At a 0.15% stop the spread term must not exceed the floor, which pins a minimum price of
**≈$33.3** at IBKR spreads (checked as a fixed point — the spread used to solve is the spread
that applies at the solved price). SOXL (0.45%) and LABU (0.25%) have margin; TQQQ is clear.

## What remains blocked

SOXL, LABU and TNA median prices. **H24 cannot be closed for those three here**, and this
node does not claim to. What changed is that its threshold table is now a *time-varying*
precondition validated end-to-end on one instrument, rather than an untested formula — and
the mode with zero margin is identified.

## Guards

`tests/test_f242_cost_model_point_estimate.py`, bidirectional throughout:

- fails if the committed run's bar/trade counts drift (every number would be measuring
  something else);
- fails if the window stops crossing a spread tier — the point-estimate critique needs a wide
  window;
- fails if TQQQ stops clearing its floor, or if *no* broker tier exercises the spread term;
- fails if the true per-bar cost stops spanning >2× — one constant would then be defensible;
- **control:** fails if the estimate becomes materially biased over *bars* too, which would
  make the trade-selection mechanism redundant rather than causal;
- fails if the dip-buyer skew inverts, or if the 10.7% understatement moves — including
  upward, since the finding is recorded as *small*;
- fails if TNA gains margin, or if SOXL/LABU lose theirs.

Where the good-news direction fires (a per-trade cost model, TNA gaining margin), the
instruction is to **supersede this node, not retune the numbers**.
