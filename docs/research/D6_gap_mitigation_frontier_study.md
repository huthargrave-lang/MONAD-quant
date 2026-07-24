# Study #18 — Overnight-Risk Mitigation Frontier

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --json /tmp/gap-program.json`<br>
**Data:** pinned full-session TQQQ hourly bars, 2024-08-01–2026-07-22<br>
**RESEARCH_WEB nodes:** E42 (study) · F52 (finding) · builds on [[F50]]<br>
**Status:** descriptive risk comparison; **no policy is approved for production**.
[Study #21](D6_calendar_gap_mitigation_study.md) tests calendar-known partial flattening as a
lower-turnover extension.

## Pre-registered decision rule

A policy is operationally interesting only if it:

1. removes at least 50% of the 34 observed gap stops;
2. improves maximum drawdown by at least 2 percentage points; and
3. does not reduce total return by more than 1 percentage point versus the already-negative
   gap-aware baseline.

Passing is necessary, not sufficient. A mechanism that directly removes overnight exposure is
preferred to a clock cutoff that selects a different in-sample trade set.

## Policy frontier

All rows use the same live-shaped, long-only, one-position replay, entry-bar bracket, 10-bar cap,
open-aware stop, and fixed 10% sizing.

| policy | trades | total | maxDD | overnight holds | gap stops | gap reduction | gate |
|---|---:|---:|---:|---:|---:|---:|:---:|
| hold overnight | 1,117 | −10.15% | −10.19% | 127 | 34 | 0% | — |
| block signals at/after 12:00 ET | 571 | −2.97% | −4.30% | 43 | 10 | 70.6% | pass |
| block signals at/after 13:00 ET | 718 | −4.24% | −5.60% | 61 | 16 | 52.9% | pass |
| block signals at/after 14:00 ET | 863 | −7.16% | −7.49% | 91 | 26 | 23.5% | fail |
| block signals at/after 15:00 ET | 985 | −8.55% | −8.68% | 127 | 34 | 0% | fail |
| flatten every survivor at end of day | 1,187 | **−5.77%** | **−6.75%** | **0** | **0** | **100%** | pass |

The noon and 13:00 cutoffs pass numerically, but they are not validated mitigations. They suppress
roughly 49% and 36% of trades and overlap the project's known morning-only selection failure
([[F13]]). Their better returns can be selection, not risk removal.

End-of-day flatten is the only mechanism-pure comparison: it removes all overnight gap stops and
improves drawdown by 3.44 pp. It also changes turnover and position availability, and the official
daily close is only a proxy for an executable market-on-close fill. It remains negative and does
not create alpha.

The observed +4.37 pp path improvement spread over 126 EOD exits corresponds to a rough
**34.7 bp of additional cost per EOD exit** at 10% position sizing before the sample benefit is
erased. This is a first-order implementation budget, not a forecast: path feedback, 70 additional
trades, auction impact, and the close-proxy error are not separately identified. The final-hour
close sensitivity is −5.81% / −6.74%, close to but not identical to the official-close proxy.

## Stop width does not cap jump loss

The target remains 1%. Stops at or above the target are stress tests, not production-valid
reward/risk choices.

| stop | production-valid | gap stops | exact total | gap-aware total | fixed-10% gap damage | worst conditional miss |
|---:|:---:|---:|---:|---:|---:|---:|
| 0.25% | yes | 24 | −5.22% | −8.60% | −3.63 pp | 9.21 pp |
| 0.50% | yes | 34 | −5.17% | −10.15% | −5.38 pp | 8.96 pp |
| 0.75% | yes | 45 | −6.50% | −12.66% | −6.80 pp | 8.71 pp |
| 1.00% | no | 50 | −6.96% | −14.12% | −7.99 pp | 8.46 pp |
| 1.50% | no | 49 | −8.29% | −16.00% | −8.75 pp | 7.96 pp |
| 2.00% | no | 42 | −9.60% | −16.21% | −7.56 pp | 7.46 pp |
| 3.00% | no | 37 | −6.06% | −11.21% | −5.61 pp | 8.64 pp |

A tighter 0.25% stop reduces the number of positions surviving into the close, so aggregate gap
damage falls. It does not bound the individual jump: the worst miss remains 9.21 pp beyond the
modeled outcome. Wider stops can increase total gap damage because more trades survive intraday
and become exposed overnight.

This is exactly how broker stop orders work: after trigger they are market orders, and the fill is
not guaranteed at the trigger
([IBKR](https://www.interactivebrokers.com/campus/glossary-terms/stop-order/)).

## Stability checks

Gap damage has the same sign in every available calendar slice:

| slice | holds | gap stops | exact total → gap-aware | exact maxDD → gap-aware |
|---|---:|---:|---:|---:|
| 2024 partial | 20 | 7 | +0.04% → −0.33% | −0.53% → −0.62% |
| 2025 | 76 | 19 | −3.74% → −6.99% | −3.74% → −6.99% |
| 2026 partial | 31 | 8 | −1.53% → −3.08% | −1.95% → −3.17% |

These are three dependent slices of one two-year path, not three independent regimes.

## Finding and decision

- **For risk modeling:** use an open-aware stop model or explicit jump stress.
- **For tail removal:** end-of-day flatten is the clean candidate for a future, separately
  costed/OOS evaluation.
- **Do not promote clock cutoffs:** they repeat the selection mechanism behind [[F13]].
- **Do not “solve” gaps by widening the stop:** the stop cannot bind a discontinuous open.
- **Do not edit live/config from this study:** a production change requires explicit approval,
  stopped trader, realistic costs, and new validation.
