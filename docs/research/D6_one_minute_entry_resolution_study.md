# Study #22 — Expiring One-Minute Entry-Bar Resolution

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Derived audit:** [`data/entry_bar_1m_resolution_2026.csv`](data/entry_bar_1m_resolution_2026.csv)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --selfcheck`<br>
**RESEARCH_WEB nodes:** E46 (study) · F56 (finding) · refines [[F54]]<br>
**Status:** one of three unresolved five-minute events recovered before one-minute retention
expired; two remain unresolved.

## Question

Study #20 identified the three unresolved five-minute dual hits as the highest-value data. Could
one-minute history resolve them before the vendor's rolling retention window closed?

## Retrieval and provenance

On 2026-07-23, Yahoo rejected the June 23–24 requests as outside its stated rolling 30-day range.
It returned 1,170 one-minute TQQQ bars for July 6–8. The raw CSV is intentionally not committed;
the derived event, thresholds, first-hit times, source coverage, row count, and raw-source SHA-256
(`faf659…4576`) are durable in the audit CSV.

The July 6 entry was $75.529999:

| threshold | price | first one-minute hit |
|---|---:|---|
| 0.5% stop | $75.152349 | **09:30 ET** |
| 1.0% target | $76.285299 | 09:34 ET |

The 09:30 bar traded down to $75.11 but only up to $75.84. The event is therefore definitively
**stop-first**. This is price-path evidence, not an assertion about queue position or exact fill.

## Updated calibration

| calibration | target-first | stop-first | unresolved | target-first rate | Wilson 95% |
|---|---:|---:|---:|---:|---:|
| original five-minute audit | 5 | 11 | 3 | 31.25% of 16 resolved | 14.16%–55.60% |
| best available, including July 6 one-minute | 5 | 12 | 2 | **29.41% of 17** | **13.28%–53.13%** |
| one-position subset | 4 | 11 | 2 | **26.67% of 15** | **10.90%–51.95%** |

The exact-stop paths remain unidentified:

- Overlapping diagnostic break-even is 33.76%; predictive P(total > 0) is 27.1%–62.4%
  across treatments of the two unresolved events.
- One-position exact-stop break-even is 26.09%, almost identical to 26.67% observed. At that
  rate, a Wilson interval would need roughly **21,887 resolved events** to sit wholly above the
  threshold. The apparent exact-stop sign is effectively unresolvable by incremental sampling.

The open-aware path becomes harder to rescue:

- Break-even remains 72/138 = 52.17% target-first.
- The resolved-only Wilson upper bound is 51.95%, just 0.22 pp below break-even.
- Jeffreys beta-binomial P(total > 0) falls to **3.05%** when unresolved events are excluded,
  **1.24%** if both are stop-first, and **9.89%** if both are target-first.
- Predictive medians are −5.02%, −5.59%, and −3.30%, respectively.

The Wilson crossing is fragile because excluding unresolved events is not conservative. Two
target-first resolutions would reopen it. The posterior sensitivity, which explicitly includes
that bound, is the safer interpretation.

## Finding

The time-sensitive retrieval paid off: it converted one ambiguous event to stop-first and reduced
the gap-aware rescue probability. It did **not** identify the exact-stop strategy's sign, whose
break-even is now even closer to the observed rate.

The remaining June 23–24 events require another historical vendor, IBKR order/tick archives, or an
existing local capture. Do not impute them from the July result and do not turn 17 clustered
events into a simulator parameter.

## Caveats

- Yahoo one-minute bars are not broker executions and still hide within-minute ordering when both
  thresholds occur in one minute; July 6 did not have that problem.
- Only one of the three unresolved cases was recoverable.
- Source retention and the raw-file hash establish provenance, not vendor independence.
- All predictive probabilities retain study #20's strong exchangeability assumption.
