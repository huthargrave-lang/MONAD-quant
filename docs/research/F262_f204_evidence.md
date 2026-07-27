# F262 — F204's evidence regenerated: eight figures exact, one an upper-tail draw

**Date:** 2026-07-27 · **Guard:** `tests/test_f262_f204_evidence.py` (10 tests)
· **Closes:** F204's uncited status (9 figures, 0 reachable docs, 2 reliance dependents)

## Regenerated, not located

Every F204 figure is reproducible offline. `validate_ohlc` takes a frame, so synthetic
panels suffice and no market data is involved — which makes this a stronger form of
citation than finding an old artifact would have been: the numbers were re-derived from
scratch and the guard re-derives them on every run.

## Eight of nine reproduce exactly

**All six corruption classes drop exactly one bar**, as recorded:

| corruption | bars | dropped |
|---|---|---:|
| `low > high` | 400 → 399 | 1 |
| close above high | 400 → 399 | 1 |
| open below low | 400 → 399 | 1 |
| zero close | 400 → 399 | 1 |
| NaN close | 400 → 399 | 1 |
| negative volume | 400 → 399 | 1 |

**And the hole is invisible to every downstream check:**

- corrupting three recent bars of a 400-bar hourly panel leaves **397** bars with a
  **4-hour** gap in an otherwise 1-hour series;
- the `min_bars` floor (200) does **not** fire — the panel is still long;
- the latest bar is untouched, so the staleness check sees nothing;
- no NaN survives, so the live NaN gate sees finite values, because they are finite.

F204's structural conclusion is confirmed exactly: **the validation catches bad VALUES;
nothing catches the DISCONTINUITY it creates.**

## The ninth figure is series-dependent

F204 records *"RSI moves 2.82 points"*. Across 40 synthetic panels, the shift from the
identical 3-bar hole is:

| min | median | mean | p90 | max |
|---:|---:|---:|---:|---:|
| 0.05 | **1.22** | 1.20 | 2.06 | 3.57 |

**2.82 is exceeded by 1 of 40 panels — roughly the 97th percentile.** The effect is real
and the direction is right, but the magnitude was a single draw quoted as characteristic.
Two of 40 panels show essentially no shift (<0.1), so the corruption is not reliably
visible downstream either.

This does not weaken F204. Its claim is structural — that nothing checks continuity — and
that reproduces exactly. What changes is that **2.82 should not be cited as a typical
magnitude**, which is precisely what an uncited figure invites and why the node was
top-ranked.

## Why this is the recurring shape

F204's own closing observation is that the drop leaves no durable trace: `validate_ohlc`
emits a `log.warning`, not a monitor event, making it the third instance of *degraded paths
announcing themselves to a log nobody keeps* (F172, F202). This node adds a fourth angle on
the same theme — a figure that was measured once, published without its distribution, and
then relied on by two downstream nodes.

## Guards

`tests/test_f262_f204_evidence.py`, bidirectional:

- fails if any corruption class stops being caught (the validation regressed), or if it
  starts **raising** instead of dropping — that is the fix F204 asked for, so **supersede**;
- fails if the hole stops being invisible: if the panel falls under the floor, if the latest
  bar is no longer untouched, or if a NaN survives;
- fails if the median shift moves off 1.22, or if 2.82 stops being an upper-tail draw
  (>4 of 40 panels exceeding it would make quoting it as typical fair);
- **non-vacuity:** asserts the effect is real — some panel must shift more than 2 points and
  the median must exceed 0.5 — so the correction cannot be read as "the effect is nothing";
- asserts at least one panel shifts almost not at all, since that tail is what makes the
  corruption hard to notice downstream.
