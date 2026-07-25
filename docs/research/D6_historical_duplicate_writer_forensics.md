# Study #48 — Historical Duplicate-Writer and Order-Path Forensics

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python -B tools/overnight_gap_risk_study.py --selfcheck --json /tmp/gap-program.json`<br>
**RESEARCH_WEB nodes:** E72 (study) · F83 (finding) · refines [[F82]]<br>
**Status:** observed sanitized-archive audit; no raw database, broker session, protected path, or current runtime changed.

## Question

Were the 210 historical double-written signal minutes merely duplicate logging, or did the paired
cycles disagree on decisions and reach the order-submission path more than once?

## Scope and evidence boundary

The study uses only the committed sanitized archive at
[`data/live_runs/archive_2026-06-18_pre_clean_run/`](../../data/live_runs/archive_2026-06-18_pre_clean_run/)
and the archived source at commit `b37a8a8`.

The archive is not a broker audit log. An `entry` monitor event proves that the application:

1. computed an actionable long;
2. called `place_bracket_order()`;
3. ran `ib.placeOrder()` for the parent, take-profit, and stop legs without a synchronous
   exception;
4. replaced the one-row local position state; and
5. emitted the success-path event.

The function did not wait for parent fill or record broker acceptance before returning. Therefore,
the records establish application submission paths, not accepted orders, fills, or final exposure.

## Paired signal decisions

The 543 signal rows collapse to 333 ET-minute slots. Exactly 210 slots across 32 exchange dates
contain two writes, separated by a median 0.053 seconds and at most 2.112 seconds.

| paired-write result | slots | share of 210 |
|---|---:|---:|
| same input bar | 13 | 6.2% |
| different input bar | **197** | **93.8%** |
| same final three-way signal | 141 | 67.1% |
| different final three-way signal | **69** | **32.9%** |
| flat versus directional | 52 | 24.8% |
| opposite direction | 17 | 8.1% |
| different long-entry eligibility with shorts disabled | **58** | **27.6%** |

The archived configuration had `TRADER_ALLOW_SHORTS=False`. Consequently, the most relevant
decision boundary is “signal equals +1” versus everything else. Fifty-eight paired slots cross
that boundary. Twenty-six of those 58 slots have an entry success event in the same minute. This
does not mean the other 32 should have ordered: an existing position, reconciliation, sizing, or
broker failure could still block them.

The absolute input-bar gaps are highly structured:

| absolute bar-time difference | paired slots |
|---:|---:|
| 0 minutes | 13 |
| 60 minutes | 168 |
| 1,080 minutes (18 hours) | 23 |
| 3,960 minutes (66 hours) | 4 |
| 5,400 minutes (90 hours) | 2 |

Study #49 explains and falsifies this pattern as a timezone-dependent current-tail selection
failure.

## Duplicate entry success paths

The monitor archive contains 72 entry events across 65 unique minute slots:

| entry-path diagnostic | result |
|---|---:|
| single-event entry slots | 58 |
| double-event entry slots | **7** |
| extra success-path events relative to one per slot | **7** |
| extra success paths / 65 unique entry slots | **10.8%** |
| double slots with one local trade row | 7/7 |
| local trade rows matching the later event's state | 7/7 |
| additional bracket-submission paths | **7** |
| additional `ib.placeOrder()` calls (three legs each) | **21** |

Event ledger:

| ET minute | first event | second event | separation |
|---|---|---|---:|
| 2026-03-30 14:32 | 268 @ 38.13 | 268 @ 38.14 | 23.652 s |
| 2026-03-31 09:32 | 269 @ 39.14 | 259 @ 39.13 | 25.231 s |
| 2026-03-31 14:32 | 248 @ 41.32 | 247 @ 41.33 | 23.721 s |
| 2026-04-06 09:32 | 237 @ 43.83 | 233 @ 43.85 | 21.942 s |
| 2026-04-08 12:32 | 213 @ 47.93 | 213 @ 47.93 | 23.402 s |
| 2026-04-13 12:32 | 205 @ 49.38 | 205 @ 49.36 | 24.242 s |
| 2026-04-13 13:32 | 204 @ 49.97 | 204 @ 49.95 | 16.024 s |

The earlier events total 1,644 shares and $71,908 of logged notional across seven separate
episodes. Those totals must not be read as simultaneous exposure. They quantify the scale of the
first success paths that the later one-row state overwrote.

The one local trade row in every double-event slot matches the later event's quantity and timestamp
within one second. The database therefore preserves only the later local state. It cannot tell us
whether the earlier parent was rejected, accepted, filled, later closed by a child, or left as
orphan broker exposure.

## What changed after this archive

The current preflight rejects a visible duplicate `-m live.trader` process. That is relevant
mitigation, but it was added after this historical window and is not a transaction-level lock.
This study does not project the seven historical double paths onto the current deployment.

It also does not establish the launch cause. The archive has no PID, process start, environment,
cron, service-manager, broker order-status, or execution ledger.

## Decision

The historical duplicate writer was decision-relevant, not cosmetic:

- 69/210 paired minutes disagree on the final signal;
- 58/210 cross the archived long-entry eligibility boundary; and
- seven of 65 unique entry minutes reached the application success path twice, producing 21 extra
  bracket-leg submission calls while the local trade record retained only the later state.

No accepted-order or fill count is claimed. The falsifying evidence is a sanitized order/execution
ledger keyed by cycle ID, PID, bar ID, parent/child order IDs, broker statuses, and final reconciled
quantity. A safe current run must also show one admitted cycle per completed bar and one durable
position transition per cycle.
