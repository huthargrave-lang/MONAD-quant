# Study #19 — Long-History Leveraged-ETF Gap Tails

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --refresh`<br>
**Data:** split-adjusted daily Yahoo OHLC, 2010-02-12–2026-07-22, common panel anchored to
TQQQ inception; 4,133 close-to-next-open observations for seven tickers and 4,115 for SOXL<br>
**RESEARCH_WEB nodes:** E43 (study) · F53 (finding) · generalizes [[F50]]<br>
**Status:** mechanism **holds across instruments and regimes**; probabilities are unconditional,
not strategy-conditioned.

## Question

Is study #16's gap damage a two-year TQQQ accident, or is it a structural consequence of holding
daily leveraged ETFs across the close?

## Method

For SPY/SSO/UPRO and QQQ/QLD/TQQQ, the study computes every adjusted close-to-next-open return,
downside quantiles, 1% expected shortfall, threshold-crossing frequency, and worst event. SOXL and
TNA provide out-of-family 3× sector/small-cap checks.

For each 2×/3× fund and its underlying ETF, OLS estimates:

`leveraged overnight gap = alpha + beta × underlying overnight gap + residual`.

This is a descriptive exposure test. It does not assume the fund promises an overnight multiple.
TQQQ's stated objective is three times the **daily** Nasdaq-100 return
([ProShares](https://www.proshares.com/our-etfs/leveraged-and-inverse/tqqq)); regulators likewise
stress that leveraged ETFs reset daily and can deviate over other horizons
([Investor.gov](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-alerts/sec),
[FINRA](https://www.finra.org/investors/insights/lowdown-leveraged-and-inverse-exchange-traded-products)).

## Tail frequencies, 2010–2026

| ticker | n | 1% quantile | worst-1% mean | nights ≤−0.5% | nights ≤−2% | worst |
|---|---:|---:|---:|---:|---:|---:|
| SPY | 4,133 | −1.96% | −3.19% | 13.16% | 0.99% | −10.45% |
| SSO | 4,133 | −3.92% | −6.38% | 23.83% | 4.77% | −21.73% |
| UPRO | 4,133 | −5.60% | −9.54% | 29.76% | 9.22% | −30.88% |
| QQQ | 4,133 | −2.24% | −3.50% | 15.87% | 1.38% | −9.46% |
| QLD | 4,133 | −4.45% | −7.05% | 26.71% | 6.27% | −20.85% |
| TQQQ | 4,133 | **−6.69%** | **−10.33%** | **31.19%** | **11.71%** | **−28.82%** |
| SOXL | 4,115 | −9.91% | −13.58% | 35.87% | 18.52% | −30.90% |
| TNA | 4,133 | −7.18% | −10.75% | 32.28% | 12.22% | −21.67% |

Every series' worst observation is 2020-03-16. That common date across four product families and
their underlyings is an internal check that the minima reflect a market shock rather than an
isolated split artifact. It is not an independent data-vendor validation.

A 0.5% TQQQ stop is crossed by the unconditional open on 31.2% of nights; a 2% downside open
occurs on 11.7%. SOXL is worse. These are instrument frequencies—not the probability that this
strategy holds the position or loses that amount.

## Leverage scaling

| pair | beta | R² | median absolute-gap ratio | 1% loss ratio | worst negative residual |
|---|---:|---:|---:|---:|---:|
| SSO / SPY | 2.00 | 0.988 | 2.01× | 2.00× | −1.66% |
| UPRO / SPY | 2.99 | 0.987 | 3.01× | 2.85× | −2.89% |
| QLD / QQQ | 1.99 | 0.995 | 1.98× | 1.99× | −2.18% |
| TQQQ / QQQ | 2.95 | 0.993 | 2.97× | 2.98× | −5.04% |

Overnight gaps scale almost mechanically with nominal daily leverage in this sample. The high R²
does not make the relationship guaranteed; residual tails remain material. Direxion likewise
states that SOXL targets 300% of its index's daily performance and should not be expected to
deliver 3× cumulative returns beyond a day
([Direxion](https://www.direxion.com/product/daily-semiconductor-bull-bear-3x-etfs)).

## Regime checks

| regime | TQQQ worst | TQQQ ≤−2% count | SOXL worst | SOXL ≤−2% count |
|---|---:|---:|---:|---:|
| COVID shock, 2020-02-15–04-30 (52 nights) | −28.82% | 15 | −30.90% | 19 |
| inflation year 2022 (251 nights) | −9.70% | 70 | −12.53% | 91 |
| recent 2025–2026 (388 nights) | −12.52% | 59 | −21.54% | 106 |

The channel is not confined to COVID. The recent regime has smaller maxima than March 2020 but
still many opens beyond a 0.5% or 2% threshold.

## Account-risk translation

Multiplying the TQQQ instrument gap by the position fraction gives a simple account-level stress
before spreads and liquidity effects:

| TQQQ position | account impact at TQQQ 1% quantile | account impact at worst-1% mean | account impact at historical worst |
|---:|---:|---:|---:|
| 2% | −0.134% | −0.207% | −0.576% |
| 5% | −0.334% | −0.517% | −1.441% |
| 10% (current paper shape) | **−0.669%** | **−1.033%** | **−2.882%** |
| 20% | −1.337% | −2.066% | −5.764% |

If one mechanically capped position size against these historical scenarios, a 1% account-loss
budget would imply at most 14.95% at the TQQQ 1% quantile, 9.68% at worst-1% expected shortfall,
or 3.47% at the historical minimum. These are scenario translations, **not** sizing
recommendations or loss limits: the next gap can exceed the sample minimum, and actual fills add
spread/liquidity risk.

## Finding

Overnight jump exposure is structural to these daily leveraged instruments. For TQQQ, downside
tail magnitude and frequency are about 3× QQQ's, with beta 2.95 and R² 0.993 over more than
16 years. A fixed stop can govern continuous intraday movement; it cannot cap a discontinuous
session open.

This generalizes [[F50]] beyond one signal and one two-year path. It does **not** estimate the
strategy's annual gap loss, prove that leverage causes alpha decay, or recommend another ETF.
Those require strategy-conditioned exposures, costs, and an investable benchmark.

## Surviving caveats

- Yahoo is one adjusted-price vendor; corporate-action handling was not independently reconciled.
- Close-to-open returns omit after-hours path, spread, auction mechanics, and actual fills.
- Threshold frequencies are unconditional and serially/regime dependent.
- Daily-leverage objectives do not promise an exact overnight multiple.
- The common 2010 anchor excludes earlier SPY/QQQ history to keep pairs comparable.
- Tail estimates remain historical; the next discontinuity can exceed the observed minimum.
