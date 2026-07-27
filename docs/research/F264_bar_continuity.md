# F264 — a continuity check for the holes `validate_ohlc` leaves

**Date:** 2026-07-27 · **Tool:** `tools/bar_continuity.py` · **Guard:**
`tests/test_f264_bar_continuity.py` (12 tests) · **Closes:** F204's open half = H30's
bar-continuity item

## The gap

F204 established — and F262 regenerated — that `validate_ohlc` catches every corruption
class and **drops rather than raises**. The resulting hole is invisible downstream: the
`min_bars` floor does not fire because the panel is still long, the staleness check
inspects only the latest bar, and the NaN gate sees finite values because they are finite.

> The validation catches bad VALUES; nothing catches the DISCONTINUITY it creates.

## Why this was not a one-liner

A naive "flag any gap larger than the modal step" detector is **useless** on intraday
equity data, because most gaps are legitimate. A US session is ~7 hourly bars with an
overnight break after each. On the committed live archive:

| | count |
|---|---:|
| steps exceeding the cadence | **47** |
| of those, session boundaries | **47** |
| duplicate stamps | 0 |

A flag-any-gap check would fire 47 times on a healthy panel and be ignored — which is
exactly how the original poison-cache footgun survived (F167).

The useful question is not *"is there a gap"* but **"is there a gap WITHIN a session"**,
and answering it needs no market calendar: an intra-session hole has bars on both sides on
the **same calendar date**. Cadence is inferred by **mode**, not min or mean — the min is
fooled by a duplicate bar, the mean by the overnight gaps that dominate the tail.

## It found one on its first run

```
2026-05-07 15:30:00  ->  2026-05-07 17:30:00     1 bar missing
```

One intra-session hole, against 47 correctly-classified session boundaries, in real logged
live data.

## And the durable record cannot say why

There are **zero** monitor events on 2026-05-07, and **zero anywhere** mentioning a dropped
bar — because `validate_ohlc` emits a `log.warning`, not a monitor event.

So the hole could be a validation drop, a missed scheduler cycle, or a vendor omission, and
**nothing committed distinguishes them.** That is F204's third-instance claim — degraded
paths announcing themselves to a log nobody keeps (F172, F202) — demonstrated rather than
argued.

**This node does not attribute the hole to `validate_ohlc`.** The point is precisely that
the record is insufficient to attribute it at all.

## Not wired in

Nothing on the live path calls this. It is a detector, not a behaviour change. Wiring it
into `fetch_yfinance` — to raise, or to emit a monitor event instead of a `log.warning` — is
a one-line change that alters live behaviour, so it is an owner decision and is left as one.

## Guards

`tests/test_f264_bar_continuity.py`, bidirectional:

- **synthetic, both directions:** a clean run and an *overnight break* must produce no hole
  (the noise failure that would make the tool useless), while one missing mid-session bar
  and F204's three-consecutive-bar example must be caught with the right `missing_bars`;
- a duplicate stamp must not drag the inferred cadence to zero;
- a short panel is reported as unknown rather than guessed at;
- the archive's 47 boundaries and single hole are pinned — if the hole count reaches zero
  the archive was repaired, so **supersede** rather than edit;
- the monitor-log checks fail if an event ever appears on that date, or if `validate_ohlc`
  starts emitting events — that is the fix F204 asked for;
- **non-vacuity:** the event log must be otherwise populated, so "no event explains it" is
  not merely "there are no events".
