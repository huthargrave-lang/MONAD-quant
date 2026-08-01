# Study #28 — Volatility Classifier Regime Stability

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --json /tmp/gap-program.json`<br>
**Data:** TQQQ/QQQ daily adjusted OHLC, 2010-02-12–2026-07-22<br>
**RESEARCH_WEB nodes:** E52 (study) · F62 (finding) · decomposes [[F59]]/[[F61]]<br>
**Status:** descriptive regime audit; no policy approval.

## Question

The frozen 20-session QQQ-volatility ≥15% rule captures 85.3% of severe TQQQ gaps in
2020–2026. Is that stable discrimination, or does the rule obtain high capture by flagging nearly
every night in high-volatility years?

## Method

For every calendar year, report:

- fraction of nights flagged (“exposure removed”);
- fraction of TQQQ ≤−2% gaps captured;
- **capture lift = capture / exposure**;
- severe-gap precision among flagged nights;
- share of loss beyond the 0.5% stop captured.

A random flag with the same annual exposure has expected lift 1. A rule active every night has
100% capture but exactly 1× lift—it has no discrimination.

## Annual decomposition

| year | severe gaps | nights flagged | gaps captured | capture lift | flagged-night precision |
|---:|---:|---:|---:|---:|---:|
| 2010 partial | 26 | 62.6% | 84.6% | 1.35× | 17.3% |
| 2011 | 38 | 71.8% | 86.8% | 1.21× | 18.2% |
| 2012 | 24 | 50.8% | 66.7% | 1.31× | 12.6% |
| 2013 | 15 | 23.8% | 13.3% | **0.56×** | 3.3% |
| 2014 | 12 | 29.4% | 41.7% | 1.42× | 6.8% |
| 2015 | 21 | 50.4% | 61.9% | 1.23× | 10.2% |
| 2016 | 20 | 38.1% | 55.0% | 1.44× | 11.5% |
| 2017 | 8 | 8.8% | 37.5% | 4.28× | 13.6% |
| 2018 | 34 | 57.4% | 67.7% | 1.18× | 16.0% |
| 2019 | 27 | 50.0% | 55.6% | 1.11× | 11.9% |
| 2020 | 40 | 84.6% | 87.5% | **1.03×** | 16.4% |
| 2021 | 32 | 55.2% | 59.4% | 1.08× | 13.7% |
| 2022 | 70 | **100.0%** | **100.0%** | **1.00×** | 27.9% |
| 2023 | 35 | 84.4% | 88.6% | 1.05× | 14.7% |
| 2024 | 22 | 59.1% | 54.5% | **0.92×** | 8.1% |
| 2025 | 32 | 65.6% | 90.6% | **1.38×** | 17.7% |
| 2026 partial | 27 | 81.2% | 88.9% | 1.09× | 21.4% |

## Finding

The rule's recent **capture** is stable, but its **discrimination** is not.

- In 2022 it flagged every night. Perfect capture was mechanically guaranteed.
- In 2020, 2021, 2023, and 2026, lift is only 1.03×–1.09×: most capture comes from broad
  exposure removal.
- In 2024, lift is 0.92×; the rule captured fewer severe gaps than a random flag with the same
  exposure would in expectation.
- 2025 is the recent exception with meaningful 1.38× concentration.
- Earlier years range from 0.56× to 4.28×, with the extreme 2017 lift based on only eight severe
  events.

Leaving any one 2020–2026 year out keeps raw capture between roughly 80% and 89%, so no single
year creates the headline. But that robustness is largely **regime persistence**: the classifier
stays on across whole volatile years.

## Implication

The 15% rule is best described as a broad risk-off state, not a precise overnight-gap forecast.
That can still be operationally useful—removing exposure is the mechanism—but it changes the
forward claim:

- do not validate it by raw capture alone;
- always report exposure and capture lift;
- the strategy-conditioned 61.8% gap reduction, not unconditional 85.3% capture, is the
  decision-relevant endpoint;
- Study #26's long forward horizon cannot be shortened by citing high recent raw capture.

## Caveats

- Annual severe-event counts are small and dependent.
- Lift is a descriptive concentration ratio, not a calibrated probability score.
- Calendar years are convenient regime slices, not economically optimized states.
- The fixed 15% threshold remains a historical candidate, not a production instruction.
