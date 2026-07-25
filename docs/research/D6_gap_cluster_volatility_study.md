# Study #23 — Overnight-Gap Clustering and Lagged-Volatility Control

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --json /tmp/gap-program.json`<br>
**Data:** adjusted TQQQ/QQQ daily history, 2010-02-12–2026-07-22; live-shaped hourly path,
2024-08-01–2026-07-22<br>
**RESEARCH_WEB nodes:** E47 (study) · F57 (finding) · builds on [[F53]]/[[F55]]<br>
**Status:** structural risk evidence; lagged-volatility policies are same-sample
counterfactuals, not approved controls.

## Questions

1. Are severe TQQQ overnight gaps independent, or do they arrive in clusters?
2. Can a lagged, observable volatility state capture ordinary-weekday risk that calendar rules
   miss without becoming daily flatten in disguise?

## Leak-free construction

The instrument panel defines a severe gap as TQQQ open at least 2% below the prior adjusted close.
The classifier is QQQ's annualized 20-session close-to-close volatility, shifted one session.
Thus the value assigned to an open uses only returns known by the previous close.

Fixed thresholds from 12.5% to 50% form a descriptive risk ROC. They are not optimized alpha
parameters. Strategy rows close an already-existing position at the official daily-close proxy
when the next session's lagged-vol state is above the threshold.

## Dependence

Across 4,113 nights after volatility warmup, 483 opened down at least 2%:

| statistic | result |
|---|---:|
| severe-gap rate | 11.74% |
| independent Wilson 95% | 10.79%–12.76% |
| circular block-20 bootstrap 95% | **10.41%–13.13%** |
| P(severe next night \| severe previous night) | **15.77%**, 1.34× baseline |
| P(severe \| any severe in previous 5 nights) | **15.35%**, 1.31× baseline |
| maximum severe gaps in 5 / 20 sessions | **4 / 10** |
| worst five-session sum of close-to-open gaps | **−45.97%**, ending 2020-03-12 |

This is moderate, economically meaningful clustering—not a claim that gap signs are predictable
trade by trade. The wider block interval is the relevant uncertainty read.

## Instrument-level volatility classifier

| lagged QQQ vol threshold | nights with exposure removed | severe gaps captured | downside excess captured | 2010–19 exposure / capture | 2020–26 exposure / capture |
|---:|---:|---:|---:|---:|---:|
| 12.5% | 71.43% | 85.09% | 85.34% | 61.01% / 75.11% | 87.06% / 93.80% |
| 15.0% | 56.50% | 75.16% | 75.93% | 43.94% / 63.56% | 75.33% / 85.27% |
| 17.5% | 42.11% | 62.94% | 66.03% | 30.40% / 51.56% | 59.66% / 72.87% |
| 20.0% | 30.61% | 49.07% | 52.61% | 20.19% / 34.67% | 46.23% / 61.63% |
| 25.0% | 18.84% | 36.23% | 39.90% | 12.04% / 25.78% | 29.04% / 45.35% |
| 30.0% | 10.50% | 23.81% | 26.94% | 5.92% / 15.56% | 17.38% / 31.01% |

The classifier works as a risk ranking, but its low thresholds are broad market-state filters.
At 15%, it removes three quarters of post-2020 overnight exposure. It does not isolate a small set
of dangerous nights.

## Strategy-conditioned frontier

Baseline is the same −10.15% total / −10.19% maxDD / 34 gap-stop path from study #16.

| threshold | flatten exits | gaps removed | directly targeted damage | total | maxDD | gate |
|---:|---:|---:|---:|---:|---:|:---:|
| 12.5% | 98 | 88.24% | 85.93% | −5.50% | −6.30% | pass |
| 15.0% | 66 | 61.76% | 65.22% | −6.10% | −6.81% | pass |
| 17.5% | 46 | 44.12% | 53.95% | −6.83% | −7.51% | fail |
| 20.0% | 19 | 20.59% | 19.41% | −9.01% | −9.38% | fail |
| 25.0% | 8 | 8.82% | 11.58% | −9.61% | −9.86% | fail |

The gate requires ≥50% event removal, ≥2 pp maxDD improvement, and no worse than −1 pp total
versus baseline. The two passing rows remain negative and were discovered on the evaluation path.
The sharp 15%→17.5% boundary is a warning against promoting “15%” as a magic constant.

## Finding

Severe overnight risk is clustered and lagged volatility captures it better than calendar spacing.
But the useful thresholds work by turning off overnight exposure for most sessions:

- 12.5% is nearly daily flatten in the recent regime.
- 15% halves the 126 daily closes and captures 62% of strategy events, a real turnover/risk
  compromise.
- 17.5% already fails the event gate.

Therefore lagged volatility is the best partial mechanism found so far, but only as a hypothesis
for genuine future/OOS auction-fill testing. It is not evidence of alpha or an authorized live
change.

## Caveats

- Thresholds and strategy outcomes share the same two-year path.
- The 2010–19/2020–26 split validates the instrument classifier, not the strategy signals.
- A volatility state can rank risk but cannot foresee isolated news shocks; the unflagged
  historical worst remains −10.54% at the 15% threshold.
- Flattening changes later position availability and uses an official-close proxy.
- The QQQ-volatility feature is one deliberately simple classifier; searching many predictors
  would create a new multiple-comparisons problem.

The empirical clustering direction agrees with recent cross-market research finding that
overnight volatility clusters across time scales
([Zhao et al., 2024](https://doi.org/10.1016/j.jempfin.2024.101487)). The MONAD result is
independently computed on its pinned leveraged-instrument panel.
