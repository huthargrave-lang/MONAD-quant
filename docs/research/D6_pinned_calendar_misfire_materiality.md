# Study #46 — Pinned Calendar-Misfire Materiality Replay

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python -B tools/overnight_gap_risk_study.py --selfcheck --json /tmp/gap-program.json`<br>
**RESEARCH_WEB nodes:** E70 (study) · F81 (finding) · supersedes [[F80]]<br>
**Status:** structural counterfactual replay; no protected runtime path or broker state was changed.

## Question

Inside the pinned 2024-08 through 2026-07 sample, are off-calendar jobs merely theoretical, or do
they coincide with reusable nonzero signals and clean-path open positions?

## Calendar evidence

The event set comes from Nasdaq primary sources:

- [2024 trading calendar](https://www.nasdaqtrader.com/content/technicalsupport/2024tradingcalendar.pdf)
- [2025 trading calendar](https://www.nasdaqtrader.com/content/technicalsupport/2025tradingcalendar.pdf)
- [2026 holiday schedule](https://www.nasdaqtrader.com/trader.aspx?id=Calendar)
- [January 9, 2025 Carter closure](https://nasdaqtrader.com/TraderNews.aspx?id=ECA2024-632)

The pinned window contains 21 fully closed weekdays and five 13:00 early-close weekdays.
The current scheduler admits seven cycles on each fully closed weekday and three cycles after each
early close:

`21 × 7 + 5 × 3 = 162 off-exchange-calendar cycles`

## Causal replay

For each fully closed date, the tool selects the last TQQQ hourly signal bar strictly before that
date. For each early close, it selects the final bar of that session. `entry_signal` is already
causal because the signal pipeline uses only information available at that bar.

The cycle is intersected with the clean gap-aware one-position path:

- **clean baseline open** means a clean-path trade spans the off-calendar cycle timestamp;
- **flat + signal** means the clean path is flat and the reused signal is nonzero;
- neither condition claims actual Pi state because a prior scheduler misfire could change all
  subsequent state.

## Results

| diagnostic | result |
|---|---:|
| off-calendar cycles | **162** |
| full holidays with nonzero reused signal | **14/21** |
| early closes with nonzero reused signal | **4/5** |
| full holidays with clean baseline position open | **8/21** |
| early closes with clean baseline position open at 13:32 | **3/5** |
| admitted cycles while clean baseline is open | **65** |
| dates clean-flat with a nonzero signal | **9/26** |
| frozen-clean-state nonzero cycle upper bound | **59** |
| early-close sessions with exactly three Yahoo hourly bars | **5/5** |
| post-close cycles reusing the 12:32-processable final bar | **15/15** |

The 59 figure is deliberately not labeled “attempts” or “orders.” It freezes the clean state for
classification; after the first real cycle, reconciliation, sizing, broker response, or state
mutation could change every later cycle.

## Event ledger

| date | session | cycles | reused bar | signal | clean position | flat + signal |
|---|---|---:|---|---:|---|---|
| 2024-09-02 | closed | 7 | 2024-08-30 15:30 −04:00 | 0 | no | no |
| 2024-11-28 | closed | 7 | 2024-11-27 15:30 −05:00 | 1 | yes | no |
| 2024-12-25 | closed | 7 | 2024-12-24 11:30 −05:00 | 1 | yes | no |
| 2025-01-01 | closed | 7 | 2024-12-31 15:30 −05:00 | 1 | no | yes |
| 2025-01-09 | closed | 7 | 2025-01-08 15:30 −05:00 | 1 | no | yes |
| 2025-01-20 | closed | 7 | 2025-01-17 15:30 −05:00 | 0 | no | no |
| 2025-02-17 | closed | 7 | 2025-02-14 15:30 −05:00 | 0 | no | no |
| 2025-04-18 | closed | 7 | 2025-04-17 15:30 −04:00 | 1 | no | yes |
| 2025-05-26 | closed | 7 | 2025-05-23 15:30 −04:00 | 1 | no | yes |
| 2025-06-19 | closed | 7 | 2025-06-18 15:30 −04:00 | 0 | no | no |
| 2025-07-04 | closed | 7 | 2025-07-03 11:30 −04:00 | 1 | yes | no |
| 2025-09-01 | closed | 7 | 2025-08-29 15:30 −04:00 | 1 | yes | no |
| 2025-11-27 | closed | 7 | 2025-11-26 15:30 −05:00 | 0 | yes | no |
| 2025-12-25 | closed | 7 | 2025-12-24 11:30 −05:00 | 1 | no | yes |
| 2026-01-01 | closed | 7 | 2025-12-31 15:30 −05:00 | 1 | yes | no |
| 2026-01-19 | closed | 7 | 2026-01-16 15:30 −05:00 | 0 | yes | no |
| 2026-02-16 | closed | 7 | 2026-02-13 15:30 −05:00 | 1 | no | yes |
| 2026-04-03 | closed | 7 | 2026-04-02 15:30 −04:00 | 1 | no | yes |
| 2026-05-25 | closed | 7 | 2026-05-22 15:30 −04:00 | 0 | no | no |
| 2026-06-19 | closed | 7 | 2026-06-18 15:30 −04:00 | 1 | yes | no |
| 2026-07-03 | closed | 7 | 2026-07-02 15:30 −04:00 | 1 | no | yes |
| 2024-11-29 | early 13:00 | 3 | 2024-11-29 11:30 −05:00 | 1 | yes | no |
| 2024-12-24 | early 13:00 | 3 | 2024-12-24 11:30 −05:00 | 1 | yes | no |
| 2025-07-03 | early 13:00 | 3 | 2025-07-03 11:30 −04:00 | 1 | yes | no |
| 2025-11-28 | early 13:00 | 3 | 2025-11-28 11:30 −05:00 | 0 | no | no |
| 2025-12-24 | early 13:00 | 3 | 2025-12-24 11:30 −05:00 | 1 | no | yes |

## Correction to Study #45

Study #45's source-only reasoning said an early close creates three post-close counts, with a
generic minimum of two duplicate final-bar counts. The actual pinned Yahoo sessions contain only
three timestamps—09:30, 10:30, and 11:30. The 11:30 bar is already old enough to pass the
60-minute completeness test at 12:32. Therefore **all three** later jobs at 13:32, 14:32, and
15:32 reuse a previously processable bar. F81 supersedes F80 for this sample-specific count.

## What the replay does not establish

- It does not observe the Pi's historical process uptime or `state.db`.
- It does not establish that the live account matched the clean backtest position.
- A nonzero signal is not sufficient for an order; broker reconciliation and sizing still run.
- A first misfire can change state, so cycle exposures are dependent and not additive attempts.
- It does not infer broker acceptance, queueing, rejection, cancellation, or eventual fill.

## Decision and falsification

The defect is material enough to prioritize for a separately approved, trader-stopped remediation:
the vulnerable cycles repeatedly coincide with both open clean-path positions and nonzero signals.
This is still not authority to edit or submit orders.

Falsify the finding by rerunning against an approved implementation that:

1. admits zero jobs on every fully closed exchange date;
2. admits zero jobs after each official early close;
3. rejects a `bar_time` already processed, regardless of scheduler invocation count; and
4. passes clock-controlled tests across the complete exchange calendar, including special closures.
