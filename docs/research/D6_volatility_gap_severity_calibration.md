# Study #30 — Volatility Capture by Gap Severity

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --json /tmp/gap-program.json`<br>
**Data:** TQQQ/QQQ daily raw-price OHLC, 2010-02-12–2026-07-22<br>
**RESEARCH_WEB nodes:** E54 (study) · F64 (finding) · refines [[F57]]/[[F62]]<br>
**Status:** descriptive tail calibration; the classifier is not a loss limit.

## Question

Is the frozen QQQ vol20 ≥15% rule useful for predicting ordinary 0.5% stop crossings, or is its
real function to identify regimes containing much larger discontinuities?

## Method

The rule flags 56.50% of all eligible nights. For nested TQQQ close-to-next-open loss thresholds
from 0.25% to 10%, report:

- event count and capture;
- **capture lift = capture / 56.50% exposure**;
- remaining unflagged events.

An exposure-matched random flag has expected lift 1. Rising lift with severity indicates a broad
catastrophic-tail state, not a precise routine-gap predictor.

## Results

| TQQQ gap loss at least | events | captured | capture lift | unflagged events |
|---:|---:|---:|---:|---:|
| 0.25% | 1,508 | 60.54% | 1.07× | 595 |
| **0.50% stop** | **1,283** | **62.82%** | **1.11×** | **477** |
| 1% | 934 | 67.67% | 1.20× | 302 |
| 2% | 483 | 75.16% | 1.33× | 120 |
| 4% | 158 | 88.61% | 1.57× | 18 |
| 6% | 58 | 91.38% | 1.62× | 5 |
| 8% | 27 | 96.30% | 1.70× | 1 |
| 10% | 14 | 92.86% | 1.64× | 1 |

Among unflagged nights, the 1% gap quantile is −3.99%, the mean below that quantile is −5.39%,
and the historical worst is **−10.54%**. At the current 10% position shape, that worst simple
translation is about **−1.05% of account** before liquidity and path effects.

## Finding

The volatility rule is only mildly discriminative at the strategy's 0.5% stop threshold:
62.8% capture costs 56.5% exposure, a lift of 1.11×. Its concentration becomes meaningful as
loss severity rises—1.57×–1.70× across 4%–8% gaps.

That resolves an apparent tension in the earlier studies:

- the rule is a **catastrophic-severity regime flag**;
- it is not a precise forecast of routine stop gaps;
- damage-weighted capture can look useful even when event-count discrimination is modest;
- the unflagged tail remains material, so the rule cannot be represented as a hard risk bound.

The strategy-conditioned 61.8% gap-stop reduction still requires forward validation because it
is stronger than the unconditional 0.5% lift would suggest.

## Caveats

- Threshold rows are nested and dependent; no independent multiple-threshold tests are claimed.
- Extreme thresholds contain few events.
- The historical unflagged worst is a scenario, never a guaranteed maximum.
- Raw prices correctly represent actual stop-level discontinuities; dividend economics and
  all-in execution are not separately decomposed here.
