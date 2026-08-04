# DI-01 — 424B5 “at-the-market” discovery + price pilot

**Status:** discovery + descriptive SPY-relative pilot; not a tradable edge<br>
**Parents:** ideas frontier (ATM / shelf overhang)<br>
**Spec:** `docs/research/data/atm_424b5_spec.json`<br>
**Artifact:** `docs/research/data/atm_424b5_discovery.json`<br>
**Tool:** `tools/atm_424b5_lab.py`

## Question

Do EFTS hits for `424B5` + `"at-the-market"` look like a usable dilution-clock
population, and does a capped Q1-2024 slice show immediate underperformance vs SPY?

## Frozen search

```text
"at-the-market"
Form 424B5
2024-01-01 .. 2024-03-31
sampling: first 100 of 463 index hits
```

| Stage | Count |
|---|---:|
| Index document hits | 463 |
| Fetched / unique submissions | 100 |
| Parsed ticker from display name | ~99 |

2023 full-year index for same query: **1,480** (not in this artifact).

Raw sha256:

```text
5cbec46bdfea4322396fce51bfe589e160305dbccc8aa7807a601da13039c4c7
```

## Price pilot (invalidated 2026-08-03)

The table below is retained as a failure record, **not evidence**. Every one of the
19 rows entered on 2024-07-25 even though the filings occurred from January through
March. The downloaded charts began months after the events, and the original window
function silently treated the first cached price as the next post-filing session.
Consequently these statistics describe a shared late-July window, not ATM filing
reactions. `forward_window` now rejects an entry more than seven calendar days after
the filing, and a regression test pins the exact failure mode.

Yahoo charts joined where available (20 tickers attempted; dead tickers skip).

| Metric | Value |
|---|---:|
| Events with price | 19 |
| Median SPY-excess 10d | −9.3% (**invalid**) |
| Mean SPY-excess 10d | +1.1% (outlier-pulled) |
| Fraction xs_10d < 0 | 68% |
| Median SPY-excess 20d | −21.6% (**invalid**) |

## Superseded interpretation

- No return statistic in this pilot can support an overhang story because the event
  clock was not represented in the price cache.
- Phrase hits include shelf boilerplate and REITs (e.g. APLE) alongside microcap
  biotech — not a homogeneous ATM-takedown cohort.
- Newest-first Q1 cap + microcap death (404 charts) bias the pilot.

## What this does *not* claim

- No confirmation that shares were actually sold under the ATM
- No float/% sold feature
- No costs, borrow, or sector ETF residualization

## Next

The original return branch is superseded by `ATM-FP-01`. See
`docs/research/ATM_FINANCING_PRESSURE_DEEP_DIVE_2026.md` for the corrected 76-episode
audit and the future-utilization model specification. The next gate is a reviewed,
point-in-time active-program ledger with next-period sales/no-sales labels; returns
remain closed until that model beats financing-need and issuer-propensity baselines.
