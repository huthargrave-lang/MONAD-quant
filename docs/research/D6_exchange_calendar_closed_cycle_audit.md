# Study #45 — 2026 Closed-Session Scheduler and Duplicate-State Audit

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python -B tools/overnight_gap_risk_study.py --selfcheck --json /tmp/gap-program.json`<br>
**RESEARCH_WEB nodes:** E69 (study) · F80 (superseded finding) · F81 (corrected finding)<br>
**Status:** read-only calendar/state audit, refined by Study #46; no protected path was changed.

## Question

How many trader jobs does the current weekday-only scheduler admit while Nasdaq is officially
closed, and can those jobs mutate position state using a repeated prior-session bar?

## Inputs

- Nasdaq's official 2026 calendar lists ten fully closed weekdays and two 13:00 ET early closes
  ([Nasdaq calendar](https://www.nasdaqtrader.com/trader.aspx?id=Calendar)).
- [`live/trader.py`](../../live/trader.py) schedules seven weekday cycles, 09:32 through 15:32
  ET, and `_is_market_hours()` treats every weekday from 09:30 through 16:00 as open.
- [`ops/systemd/monad-trader.timer`](../../ops/systemd/monad-trader.timer) starts the service on
  Monday–Friday, not on an exchange-session calendar.
- `config.LIVE_MAX_BAR_STALENESS_HOURS` is 120. This intentionally accommodates long holiday
  weekends, so prior-session bars remain data-valid during a closed holiday.
- With an open position, `_on_bar_inner()` calls `state.increment_bar_count()` once per admitted
  cycle before software stop/target/time-exit decisions. It does not first establish that
  `bar_time` is newer than the last processed bar.

## Deterministic 2026 schedule exposure

Fully closed weekdays:

`Jan 1, Jan 19, Feb 16, Apr 3, May 25, Jun 19, Jul 3, Sep 7, Nov 26, Dec 25`

Early-close weekdays:

`Nov 27, Dec 24`

| exposure | calculation | admitted cycles |
|---|---:|---:|
| fully closed holidays | 10 days × 7 jobs | 70 |
| after 13:00 early closes | 2 days × 3 jobs at 13:32/14:32/15:32 | 6 |
| **total outside the exchange calendar** | | **76** |

This is a schedule-exposure count, not evidence that 76 orders were submitted or filled.

## Why staleness does not fail closed

The 120-hour threshold is much longer than the age of the previous session's final hourly bar
during an ordinary weekday holiday. The same prior-session data can therefore pass the current
freshness check at every scheduled holiday cycle.

On a 13:00 early close:

- 13:32 can process the newly completed final bar after the exchange has closed;
- 14:32 and 15:32 can process that same final bar again;
- all three cycles are admitted by the hard-coded 16:00 guard.

On a fully closed weekday, all seven cycles can reuse the previous session's final bar.

## Conditional state consequences

If a position remains open and broker reconciliation does not close it first:

- a full holiday can add up to seven holding-bar counts from one repeated source bar;
- an early close can add three counts after 13:00; generic hourly semantics guarantee at least
  two duplicates, while Study #46's pinned Yahoo replay finds all three reuse its 11:30 final bar;
- the artificial count advance can reach the ten-bar cap and invoke the market-close path while
  the exchange is shut;
- software stop/target checks are also repeated without a new exchange bar.

If the strategy is flat, the same prior-session signal can be evaluated repeatedly because there
is no explicit last-processed-bar idempotency gate. Whether a broker accepts, holds, rejects, or
eventually fills any resulting order is outside this static audit.

## Decision

The runtime does not fail closed on the exchange calendar. Safe behavior requires both:

1. an official session calendar that suppresses full-holiday jobs and applies each early close;
2. an idempotent bar-time gate so one completed bar can mutate state at most once.

Those are prerequisites even if MOC research is abandoned. This finding does not authorize edits
to `live/**`, configuration, systemd, or order code; it identifies a protected-path remediation
candidate for an explicitly approved, trader-stopped change.

## Falsification

Re-run this study after an approved fix. The finding is falsified only if clock-controlled tests
show zero admitted cycles on every official closed weekday, zero jobs after each early close, and
repeated calls with the same `bar_time` cannot increment holding state or submit another entry.
