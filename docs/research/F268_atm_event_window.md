# F268 — the ATM pilot measured one date, not nineteen events

**Date:** 2026-07-30 · **Guard:** `tests/test_f268_atm_event_window_collapse.py` (12 tests)
· **Evidence:** E132 · **Fixed:** `tools/atm_424b5_lab.py::forward_window`

## The headline

`DI-01`'s 424B5 at-the-market price pilot reports:

```
median_xs_20d        -0.2155
frac_negative_xs_10d  0.6842      (17 of 19 negative)
n_events_with_price      19
```

A −21.6% median excess return over 20 days with 17 of 19 names negative reads as strong
post-filing drift.

## It is one market draw wearing nineteen hats

| field | distinct values |
|---|---|
| `file_date` | **19** — 2024-01-11 … 2024-03-28 |
| `entry_date` | **1** — `2024-07-25` |
| `spy_10d` | **1** — −0.0367 |
| `spy_20d` | **1** — +0.0413 |

Every "event" return is measured from the same calendar date, **four to six months after**
the filing it is supposed to follow. The number describes how nineteen microcaps moved in
the ten and twenty days after 25 July 2024. It is not an event study, so it says nothing
about 424B5 filings.

And because all nineteen share one entry date and one benchmark, the **effective sample
size is 1** — the extreme case of F267's correlation problem, where n_eff collapsed from 8
to ~2. Here it collapses to one.

## The mechanism

`forward_window` scanned for the first day strictly after the filing:

```python
for i, day in enumerate(days):
    if day > file_date:
        start_idx = i
        break
```

When the price series **starts after** the event — which it does, because the chart bundle
covers only a recent window — `days[0]` already satisfies that test. So *"the day after the
event"* silently became *"the first bar I have"*, identical for every ticker fetched over
the same range.

It returned a **well-formed pair** rather than refusing, and a well-formed pair is
indistinguishable from a real one at every downstream call site.

## The stated caveats do not cover it

The artifact is labelled `descriptive_only: true` and warns:

> phrase hit != ATM takedown; capped newest-biased slice; microcaps dominate; no costs

All four are **sample-selection** caveats. None says the measurement is not aligned to the
event. A reader who accepted every one of them would still misread the number.

That is the shape this branch keeps finding: **the stated limitation and the actual
limitation differ** — F234 ("not installed", never tried), F244 (`DEAD LEVER (MACD is
binding gate)`, wrong cause), F262 (a single draw published as typical).

## The fix

`forward_window` now requires the series to cover the event:

```python
if not days or file_date < days[0]:
    return None
```

Refuse rather than substitute. The committed artifact is left as-is — regenerating it needs
SEC and Yahoo, both blocked here — so this node records what the numbers do and do not mean.

## Guards

`tests/test_f268_atm_event_window_collapse.py`, bidirectional:

- pins the single `entry_date`, the 19 distinct file dates months earlier, the single
  benchmark draw, and the headline numbers, so the size of what is invalidated is explicit;
- asserts the stated caveat does **not** mention entry/alignment/window — if alignment is
  ever disclosed, that claim is flagged stale;
- the window must **refuse** an event before the series, after the series, on an empty
  series, or with a horizon past the end;
- it must still **accept** an in-series event and the first-bar boundary — a check that
  refuses everything is not a check;
- and distinct events must now produce distinct windows, the property whose absence was the
  entire defect.

If the artifact ever gains more than one `entry_date` it was regenerated, and this node
should be superseded.
