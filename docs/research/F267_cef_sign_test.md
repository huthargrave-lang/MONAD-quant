# F267 — the sign test looks significant and is not

**Date:** 2026-07-30 · **Guard:** `tests/test_f267_cef_sign_test_does_not_rescue.py` (11 tests)
· **Refines:** F266 · **Evidence:** E130

## The check worth running, reported negative

F266 recorded that the committed CEF artifact carries no dispersion, so the effect "cannot
be distinguished from noise." A **sign test needs no dispersion**, so it is the obvious
attempt to rescue significance:

```
8 of 8 tickers negative  ->  exact two-tailed binomial p = 0.0078
```

That looks decisive. It is not — the exact test assumes eight **independent** draws, and
these are same-market closed-end funds.

## Effective sample size, and why the collapse is fatal

Kish-style, `n_eff = n / (1 + (n−1)·rho)`:

| rho | n_eff |
|---:|---:|
| 0.00 | 8.00 |
| 0.30 | **2.58** |
| 0.60 | 1.54 |
| 0.90 | 1.10 |

A sign test on ~2 observations cannot reach significance at any threshold — the smallest
attainable two-tailed p at n=2 is **0.5**. So the honest reading is a bound,
**p ∈ [0.0078, 1.0]**, with the realistic end nowhere near the left edge.

**F266's original claim stands.** This node exists because the check was worth running and
reporting negative, not because it changed the verdict.

## The artifact cannot narrow the bound — so the lab now can

Nothing in the committed artifact records cross-ticker correlation.
`cef_discount_lab.cross_ticker_correlation()` now emits mean/min/max pairwise rho and the
derived `effective_n`, wired into the summary, so the next run states a real p instead of a
bound.

## Two genuinely new facts

### 1. The tradable form is 7 of 8, not 8 of 8

The **correlation** is negative on every ticker. The **quintile spread** — long the
low-trailing quintile, short the high, which is what you would actually trade — is positive
on only seven. EOS's control is **−0.43%**.

```
sign test on the tradable spread:  7 of 8  ->  p = 0.0703
```

Even under the generous independence assumption it does not clear 0.05. **The headline
8-of-8 describes a statistic nobody trades.**

### 2. The fixed-income / equity split does not separate the price signal

F266 proposed testing whether fixed-income CEFs behave differently. On the tradable spread
they do not:

| group | price-only spread | corr(trailing, future) |
|---|---:|---:|
| fixed income (PDI, BBN, HYT, NUV) | +1.47% | **−0.224** |
| equity / infra (BDJ, EOS, RVT, UTF) | +1.54% | −0.144 |

The correlation *is* stronger in fixed income, but the spread is flat across the split — so
a fixed-income-only universe is **not** the free improvement it looked like.

What the split does isolate is the **discount thesis's** fragility, which sits entirely in
the equity group: UTF (−4.17%) and EOS (negative control) are both there.

## Where this leaves the strategy

Unchanged in direction, weaker in support than F266's headline suggested:

- the effect is economically meaningful and cost-survivable (F266);
- its tradable form is 7/8 with p = 0.0703 under an assumption known to be too generous;
- the real p is unavailable until the lab re-runs with cross-ticker correlation;
- and the universe cannot be improved by restricting to fixed income.

## Guards

Bidirectional: fail if the sign counts change, if the effective-n arithmetic stops
collapsing under correlation (which would make the sign test usable — **supersede**), if a
3-observation sign test ever became significant, if the artifact gains cross-ticker
correlation (which replaces the bound with a number — **supersede**), or if the two groups'
price-only spreads separate. Also asserts `cross_ticker_correlation` is **wired into** the
summary rather than computed and dropped — a helper nothing reads is the F145 dead-lever
shape, which this branch has now hit three times.
