# Study #47 — Sanitized Observed Holiday-Runtime Evidence

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python -B tools/overnight_gap_risk_study.py --selfcheck --json /tmp/gap-program.json`<br>
**RESEARCH_WEB nodes:** E71 (study) · F82 (finding) · refines [[F81]]/[[F79]]<br>
**Status:** observed sanitized archive audit; no raw database, account identifier, or protected path changed.

## Question

Do committed operational records show that the paper trader actually ran on an official market
holiday, or is the calendar defect supported only by static code and counterfactual replay?

## Evidence and provenance

The only committed export with cycle-level history is
[`data/live_runs/archive_2026-06-18_pre_clean_run/`](../../data/live_runs/archive_2026-06-18_pre_clean_run/).
Its metadata identifies branch `pi-ops-automation`, commit `b37a8a8`, and sanitized source database
SHA-256 `fd8504c0…50aff7`. Account identifiers and the raw database are not committed.

Audited files:

| file | SHA-256 |
|---|---|
| `metadata.json` | `88499f682a06fef50230af463099e7c1893e159a3a7b76fcd9befd76997dbc0c` |
| `signal_history.jsonl` | `5f4df3a752853487dbdb97928c9382ca06dc2a38ea34b7e6ad77b16011313558` |
| `monitor_events.jsonl` | `c5d54080ad5a2929d6f485a0ebcd7312ceaa4ceee03da0906654ca5f00cd9975` |
| `trades.jsonl` | `bc845e9dcb95294b13f48df6434966a7ffecd54de8489dc50baf9f3d058bf6ec` |

Signal-history coverage contains two official Nasdaq full-market closures—Good Friday, April 3,
2026, and Memorial Day, May 25, 2026—and no early-close date. The archive cannot answer what
happened on other holidays or any 13:00 close.

## Observed holiday records

| date | signal rows | unique ET slots | rows/slot | reused raw bar time | signal | paper-7497 connection failures | trade endpoints |
|---|---:|---:|---:|---|---:|---:|---:|
| 2026-04-03 | 8 | 4 (09:32–12:32) | 2 | `2026-04-02 19:30:00` | +1 | 8 | 0 |
| 2026-05-25 | 14 | 7 (09:32–15:32) | 2 | `2026-05-22 19:30:00` | 0 | 14 | 0 |

The raw `bar_time` values are stored UTC-naive in this historical export; 19:30 corresponds to
15:30 ET on these dates.

This proves the scheduler/cycle path ran on both closed dates and reused one prior-session bar.
Good Friday is especially decision-relevant because the stored signal was long at every recorded
cycle.

Every recorded holiday invocation then emitted a connection failure to paper port 7497. No trade
entry or exit timestamp occurs on either date. The paper Gateway outage prevented downstream
behavior by circumstance; there is no exchange-calendar rejection in the record.

## Historical double-write diagnostic

The holiday rows reveal two records at every minute. The pattern is broader:

| archive diagnostic | result |
|---|---:|
| signal-history rows | 543 |
| unique ET minute slots | 333 |
| single-write slots | 123 |
| double-written slots | **210** |
| double-written slots with identical signal payload | 13 |
| double-written slots with divergent payload | **197** |
| first/last double-written slot | 2026-03-26 09:32 / 2026-05-29 15:32 ET |
| extra identical monitor events | 25 |

At archived commit `b37a8a8`, `_on_bar_inner()` calls `save_signal_snapshot()` once, and that
function inserts one `signal_history` row. Two writes per minute are therefore consistent with
duplicate invocations or writers. The archive does not preserve process IDs or service-manager
state, so it cannot identify whether the cause was two trader processes, a second launcher, or
another form of re-entry.

The current repository's preflight now rejects startup when another `-m live.trader` process is
visible. That is relevant mitigation, so this historical concurrency finding must not be projected
onto the current deployment without fresh process/service evidence. It does not repair the current
exchange-calendar gap.

## Evidence hierarchy

This study upgrades only one claim:

- static code: off-calendar cycles **can** be admitted;
- pinned replay: those cycles **would often** encounter open state or nonzero signals;
- sanitized archive: cycles **were recorded** on two official closures.

It does not establish order placement, broker acceptance, or fills. The absence of trade endpoints
is affirmative for the committed trade table, but the archive is not a complete broker audit log.

## Decision and falsification

The calendar defect is observed, not merely hypothetical. Its downstream trading consequence
remains unobserved because paper connectivity failed on both covered holidays.

Falsification requires a new sanitized export showing:

1. complete coverage of every official closed/short session;
2. zero cycle or signal-history records outside valid exchange hours;
3. one signal-history write per admitted bar time; and
4. service/process evidence sufficient to explain any duplicated minute.

No live/configuration/order change is authorized by this finding.
