# Sleeve break-even: could any CEF admission change the static product?

Status: **FROZEN** (2026-10-09), before any number below was computed. This is a descriptive
study, not a test: it records no trial, fits no weights, and supports no admission.

## The question (next-step board, rank 2)

Every corroborated alpha in the CEF program is measured against a benchmark the static product
does not hold:
- **H404702:** against the equal-weight CEF universe. Its beta-hedged α is +2.26%/yr (F366205).
- **CEFS:** against PCEF. Its beta-hedged α is +4.40%/yr (F366205).

Those benchmarks draw down 39-48%. The product (D6) is a static 60/40 SPY/IEF.

**The question:** if part of the 60/40 were carved out into a CEF sleeve, how large would the
sleeve's alpha over its own benchmark have to be before the mix beat the 60/40 on excess
Sharpe, and before it stopped deepening the drawdown?
- If the break-even alphas sit far above the corroborated ones, CEF admission is off the
  product's critical path.
- If they sit below, a CEF sleeve is a product question worth the forward evidence.

## Data (recorded series only; no evaluation)

| Series | Source |
|---|---|
| The product | the recorded static 60/40 SPY/IEF reference, `TR-20261006T005053Z-9336581d#0` (DS-32c992fb, 2007-06-08..2026-10-02, 21 tranches, tier1 costs) |
| The H404702 sleeve's benchmark | the recorded equal-weight CEF reference, `TR-20261006T012341Z-86834435#0` (DS-18cef162, 2003-12-31..2026-10-02) |
| The CEFS sleeve's benchmark | the recorded PCEF series, `TR-20261007T051659Z-dfb4dff7#0` (DS-84167824, 2012-12-03..2026-10-02) |
| Cash | DTB3 from DS-32c992fb, for excess returns |

## The arithmetic (fixed now)

- **The mix:** `m_t(α) = (1 − x) p_t + x (b_t + α/252)`.
  - p is the 60/40's daily return and b is the sleeve benchmark's.
  - The mix is rebalanced daily to fixed weights. The carve-out is pro rata from the 60/40.
- **Carve-outs:** x ∈ {5%, 10%, 20%}.
- **Break-evens.** Bisection on α in [−20%, +40%]/yr; "none" is reported if there is no
  crossing.
  - α_S\* is the α at which the mix's annualised excess Sharpe equals the 60/40's.
  - α_D\* is the α at which the mix's maximum drawdown (nominal, daily compounding) equals the
    60/40's.
- **Windows.** The study uses the full overlap of each pair, plus F46's correlation regimes:

  | Window | Dates |
  |---|---|
  | negative stock-bond correlation | from the overlap start to 2022-07-31 |
  | positive correlation | 2022-08-01 to the end |

  The CEFS pair (PCEF) overlaps only from 2012-12-04.
- **Reported for each pair, carve-out and window:** α_S\*, α_D\*, the 60/40's and the
  benchmark's Sharpe and maximum drawdown, and their correlation.

## Reading (stated now)

- A corroborated α (+2.26%/yr for the equal-weight CEF sleeve; +4.40%/yr for PCEF/CEFS) that
  exceeds α_S\* in **both** regime windows means the sleeve would have raised the product's
  Sharpe in both correlation regimes. An α below α_D\* means the sleeve deepened the
  drawdown.
- Neither reading is evidence that the alpha persists. That is what the forward records are
  for.
- Real (inflation-adjusted) drawdown, F46's other metric, is not computed: no CPI series is
  frozen in the repository.

## Limits

- The alphas are in-sample estimates, from the same years as these benchmarks.
- Adding the beta-hedged α to the benchmark assumes the sleeve keeps the benchmark's beta.
  That is approximately true by construction of F366205's control.
- Daily rebalancing ignores sleeve trading costs beyond those already inside the recorded
  series.
