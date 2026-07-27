# CEF-DISCOUNT — Yahoo NAV premium/discount pilot

**Status:** descriptive first-cut pilot; not a tradable edge claim<br>
**Parents:** research frontier (CEF discount staleness)<br>
**Spec:** `docs/research/data/cef_discount_pilot_spec.json`<br>
**Artifact:** `docs/research/data/cef_discount_pilot_result.json`<br>
**Tool:** `tools/cef_discount_lab.py`

## Question

Conditional on Yahoo `X{TICKER}X` NAV proxies, do deep-discount z-scores mean
revert enough that **cheap beats rich** over ~20 sessions — and is that distinct
from ordinary price mean-reversion?

## Panel

PDI, BDJ, BBN, UTF, HYT, EOS, NUV, RVT — 2y daily price + NAV charts
(ADX dropped: no working Yahoo NAV ticker).

| Rule | Value |
|---|---|
| Discount | `price / NAV - 1` |
| Z lookback | 60 sessions |
| Horizon | 20 sessions |
| Cheap / rich | bottom / top discount-z quintile |

## First-cut result

| Metric | Value |
|---|---:|
| Mean corr(discount z → fut 20d price) | −0.192 |
| Mean cheap − rich (20d price) | **+1.76%** |
| Mean cheap − rich (20d Δ discount) | +0.78% |
| Price-only control (high − low trail) | −1.50% (price MR present) |

`first_cut_supports_long_cheap=true` on this frozen bundle. UTF flips the price
spread negative — single-name fragility is real.

## Interpretation

- **Discount MR and price MR both show up.** That does *not* prove a discount
  edge after costs, leverage, or sector beta.
- Price-only MR is the **negative control**, not the thesis. A later kill test
  should residualize returns on sector/NAV change.
- Yahoo NAV proxies are convenient and incomplete (ADX missing; mapping ad hoc).

## What this does *not* claim

- No live trading signal
- No capacity / bid-ask / distribution-day handling
- No claim that discount staleness beats static CEF ownership

## Next

1. Residualize cheap−rich on NAV change + equity beta.
2. Add Morningstar/mstarpy for ADX-class gaps.
3. Expand panel; freeze a multi-year chart bundle hash.
