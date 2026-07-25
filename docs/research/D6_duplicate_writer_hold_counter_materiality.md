# Study 62 — Duplicate-writer hold-counter materiality

**Date:** 2026-07-24<br>
**Status:** observed sanitized-archive state-mutation audit; causal PnL
counterfactual unidentified; no live/config/order-path change authorized<br>
**Artifact:** `tools/overnight_gap_risk_study.py` →
`duplicate_writer_hold_counter_materiality`

## Question

Did the historical duplicate writer merely duplicate signals/orders, or did it
also make the shared `bar_count` holding clock advance twice per logical hourly
cycle and trigger time exits before ten distinct cycles had elapsed?

## Verdict

**Yes. The duplicate writer materially compressed the local holding clock.**

`increment_bar_count` performs:

```text
UPDATE position SET bar_count = bar_count + 1
```

once per admitted trader invocation. It has no completed-bar ID, cycle ID, or
conditional “newer bar only” predicate. The trader force-closes once the returned
counter reaches `MAX_TRADE_BARS_LIVE` (10).

The sanitized archive contains nine `time_exit` trades, all recorded at
`bars_held=10`:

- seven map **exactly** to ten signal-history writes across only five distinct
  minute slots;
- every one of those five slots has exactly two writes;
- eight of nine time exits occur in fewer than ten distinct archived cycle
  slots; and
- the strict seven therefore reached the nominal ten-bar threshold after
  exactly five logical cycle minutes.

This proves premature local time-exit triggering relative to ten unique cycles.
It does not identify whether holding longer would improve or worsen PnL, because
the position could hit a bracket target/stop during the additional path.

## Reproduce

```bash
venv/bin/python tools/overnight_gap_risk_study.py \
  --selfcheck --json /tmp/gap_program_study62.json
```

The study reads current source and the committed sanitized archive, plus creates
a temporary SQLite counterexample that is deleted automatically. It does not
import `live.*`, contact IBKR, modify the operational database, or touch a
protected path.

## Source contract

The archived metadata identifies:

```text
archive: archive_2026-06-18_pre_clean_run
branch:  pi-ops-automation
commit:  b37a8a8
```

Study 48 previously verified the archived source at that commit. Its counter
path matches the current source:

```text
bar_count = state.increment_bar_count()
...
if bar_count >= MAX_TRADE_BARS_LIVE:
    time exit
```

Each invocation first writes signal history, then—when a local and broker
position are open—advances the shared counter. SQLite serializes the updates, so
two writers do not lose an increment; they preserve **both**:

```text
initial counter       0
writer A update       1
writer B update       2
logical cycle slots   1
inflation factor      2×
```

Write serialization therefore makes this defect deterministic rather than
preventing it.

## Strict attribution rule

Signal history has no PID or cycle ID, so the study uses a conservative rule.
A time-exit interval is “strict exact-double” only when:

1. the trade records `bars_held=10`;
2. exactly ten signal-history rows occur after entry and through exit;
3. those rows occupy exactly five distinct UTC minute slots; and
4. every slot contains exactly two writes.

Why this is strong:

- every trader invocation writes its signal record before management;
- ten counter increments require ten admitted management invocations;
- the interval contains exactly ten invocation records, leaving no missing or
  extra writer to impute; and
- all ten records form five exact pairs.

Intervals with additional/missing writes are reported descriptively but excluded
from the strict seven.

## Archived intervals

| interval | wall hours | recorded bars | signal rows | distinct slots | writes/slot | strict |
|---:|---:|---:|---:|---:|---|---|
| 1 | 22.00 | 10 | 10 | **5** | 2,2,2,2,2 | yes |
| 2 | 5.00 | 10 | 10 | **5** | 2,2,2,2,2 | yes |
| 3 | 23.00 | 10 | 12 | 6 | all 2 | no—two extra writes |
| 4 | 5.00 | 10 | 10 | **5** | 2,2,2,2,2 | yes |
| 5 | 5.00 | 10 | 10 | **5** | 2,2,2,2,2 | yes |
| 6 | 5.00 | 10 | 10 | **5** | 2,2,2,2,2 | yes |
| 7 | 119.00 | 10 | 40 | 20 | all 2 | no—many failed/non-incrementing cycles |
| 8 | 22.01 | 10 | 10 | **5** | 2,2,2,2,2 | yes |
| 9 | 22.00 | 10 | 10 | **5** | 2,2,2,2,2 | yes |

Summary:

| diagnostic | result |
|---|---:|
| time-exit trades | 9 |
| all record bars held = 10 | 9/9 |
| fewer than ten distinct cycle slots | **8/9** |
| at most six distinct cycle slots | **8/9** |
| strict exact-double intervals | **7/9** |
| exact five-slot half-holds | **7/9** |
| median distinct slots | **5** |
| strict wall-clock hours, min / median / max | 5.00 / 5.00 / 22.01 |

Wall-clock hours differ because overnight closures sit between hourly cycle
slots. The decision-relevant denominator is distinct admitted cycle minutes,
not elapsed clock time.

## What is and is not identified

Observed:

- the archive has paired trader invocations;
- the shared counter records ten;
- seven time exits map exactly onto five paired minute slots;
- eight time exits use fewer than ten unique slots; and
- the time-exit state transition therefore occurred early relative to its
  nominal unique-cycle interpretation.

Not identified:

- whether both writers shared one process, scheduler, environment, or host;
- whether the current preflight permits the same historical launch condition;
- where each position would exit under ten unique completed bars;
- whether extra holding would increase or reduce realized return; or
- how broker fills would differ.

All nine time exits are recorded as profitable. That makes an intuitive
“premature exits lost profits” story tempting and invalid. A longer path could
hit either TP or SL; no sign is assigned without replay-quality execution data.

## Relationship to prior findings

- Study 48 / F83 proves 210 paired signal minutes, decision disagreement, and
  seven double application-entry paths.
- Studies 45–46 / F80–F81 show repeated scheduler cycles can reuse one bar on
  closed/short sessions.
- This study establishes a separate **state mutation**: even without another
  order, duplicate invocations advance holding age.
- Study 60 / F95 shows old and successor order lifecycles can overlap; compressed
  exits increase the number of such handoff boundaries.

## Existing test boundary

Tests cover:

- one counter increment returning a mocked value;
- continued holding below ten; and
- a time exit at ten.

They do not cover:

- two writers on one completed bar;
- repeated invocations with the same bar timestamp;
- a unique lifecycle+bar constraint;
- holidays/retries;
- archive reconstruction; or
- a ten-distinct-bar invariant.

## Falsification / repair gate

Before any protected-path remediation:

1. define holding age as the count of **distinct completed exchange bars**;
2. store the last counted bar timestamp/ID on the lifecycle;
3. increment with a conditional update only when the incoming bar is strictly
   newer;
4. enforce uniqueness on lifecycle + completed-bar ID so concurrent writers
   cannot both claim it;
5. test duplicate writers, retries, stale bars, holidays, DST, and restart
   schedules; and
6. obtain adequate market/order evidence before assigning historical PnL to the
   five deferred unique bars.

## Limits

- The strict rule deliberately discards two non-exact intervals.
- Signal rows identify invocations, not PID/process ownership.
- Current singleton preflight was added after the archive and reduces recurrence,
  but the counter remains non-idempotent by bar.

## Decision

Treat the archived nine `time_exit` rows as invocation-count exits, not clean
ten-unique-bar holds. Replace `bar_count += 1` with one atomic
lifecycle+completed-bar transition before using holding duration as strategy
evidence.
