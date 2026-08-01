# Study #50 — Archived Incomplete-Bar Materiality

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python -B tools/overnight_gap_risk_study.py --selfcheck --json /tmp/gap-program.json`<br>
**RESEARCH_WEB nodes:** E74 (study) · F85 (finding) · refines [[F84]]/[[F43]]<br>
**Status:** observed sanitized-archive audit; no broker session, raw database, protected runtime, signal, or config path changed.

## Question

How much of the archived paper runtime actually evaluated an hourly bar before that hour completed,
and how much entry/trade history can be attributed to those incomplete information sets without
guessing across missing cycle IDs?

## Classification

The signal archive stores:

- `updated_at` as a timezone-aware UTC observation time; and
- `bar_time` as the yfinance hourly **bar-start** label converted to UTC-naive.

This study re-localizes `bar_time` to UTC and computes:

`true_bar_age = updated_at_utc - bar_start_utc`

For a normal hourly bar, age below 60 minutes is in progress. The final regular-session bar is only
30 minutes long, but the archived job runs at 15:32 ET, two minutes into the 15:30–16:00 bar, so
the same classification is unambiguous there.

## Signal-history result

| archive diagnostic | result |
|---|---:|
| signal rows | 543 |
| rows with true age <60 minutes | **297 (54.7%)** |
| negative true ages | 0 |
| incomplete-row age min / median / max | 2.003 / **2.005** / 2.085 minutes |
| exchange dates with incomplete rows | 43 |
| first / last date | 2026-03-30 / 2026-05-29 |
| single-write rows | 123 |
| incomplete single-write rows | **100/123 (81.3%)** |
| rows inside 210 paired slots | 420 |
| incomplete paired rows | 197 |

Incomplete rows occurred at every scheduled hour:

| ET cycle hour | incomplete rows |
|---:|---:|
| 09 | 43 |
| 10 | 43 |
| 11 | 43 |
| 12 | 42 |
| 13 | 42 |
| 14 | 42 |
| 15 | 42 |

Their signals are 107 long, 75 flat, and 115 short. This is not just a duplicated-writer artifact:
100 incomplete rows occur in single-write minutes.

## Conservative entry attribution

The archive lacks a cycle ID or PID joining a signal row to an entry event. The study therefore
uses a deliberately strict rule:

- count a single-write entry minute only if its sole signal row is incomplete; or
- count a paired minute only if exactly one row is long and that unique long row is incomplete.

Paired minutes where both rows are long are excluded even when two entry events exist.

| entry-minute class | unique slots | event rows |
|---|---:|---:|
| single incomplete | 24 | 24 |
| paired; only long is incomplete | 16 | 16 |
| paired; only long is completed | 10 | 10 |
| paired; both long, one incomplete | 11 | 18 |
| single completed | 2 | 2 |
| no same-minute signal history | 2 | 2 |
| total | 65 | 72 |

The strict lower bound is therefore:

- **40/65 unique entry minutes (61.5%)**; and
- **40/72 entry event rows (55.6%)**

whose only actionable archived information set was an in-progress bar. All 40 minutes later appear
as one local trade row. The excluded 11 both-long minutes mean the true fraction may be higher;
the study does not impute it.

## Local trade-accounting consequence

The 40 strictly attributed local trades contain:

| exit category | rows |
|---|---:|
| `bracket_exit` | 30 |
| `stop_hit` | 3 |
| `target_hit` | 4 |
| `time_exit` | 3 |

Using the archive's existing “confirmed” split (`bracket_exit` + `stop_hit`):

| descriptive partition | rows | compounded return |
|---|---:|---:|
| all archive-confirmed rows | 47 | +0.2047% |
| strict incomplete-attributed confirmed rows | **33** | **+1.4388%** |
| remaining completed/ambiguous/unmatched confirmed rows | 14 | −1.2166% |

This is not an additive or causal P&L decomposition: sequential compounding depends on order, and
the remainder mixes completed, ambiguous both-long, and unmatched information sets. It does show
that the archive's approximately flat confirmed result is not a clean validation of the intended
completed-bar strategy. Its small positive component is concentrated in decisions that the
intended chronology would not have made from the same completed information.

The counts here are specific to the committed 65-trade archive and need not equal later `state.db`
counts used in Study #10. The archive has no broker order-status or execution ledger; a local
trade row can also contain inferred accounting.

## Decision and falsification

The timezone bug materially contaminated the historical paper run:

- more than half of signal rows were captured about two minutes into the hour;
- 81% of single-write rows were incomplete;
- at least 61.5% of unique entry minutes were uniquely attributable to an incomplete information
  set; and
- 33/47 archive-confirmed local trades fall inside that strict lower bound.

The overall live verdict remains flat, but it is not clean completed-bar validation.

Falsification requires fresh cycle-keyed evidence showing, for every admitted run:

1. timezone-aware observation time and bar start/end;
2. `bar_end <= decision_time`;
3. the same selected bar whether the vendor includes or omits its current tail;
4. one cycle and one position transition per bar; and
5. broker order/status/fill reconciliation keyed to that cycle.

No live/configuration/order change is authorized by this finding.
