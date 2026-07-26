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

## Price pilot (descriptive)

Yahoo charts joined where available (20 tickers attempted; dead tickers skip).

| Metric | Value |
|---|---:|
| Events with price | 19 |
| Median SPY-excess 10d | **−9.3%** |
| Mean SPY-excess 10d | +1.1% (outlier-pulled) |
| Fraction xs_10d < 0 | 68% |
| Median SPY-excess 20d | **−21.6%** |

## Interpretation

- Sign of the **median** matches an overhang story; the **mean** does not —
  fat right tail / survivors.
- Phrase hits include shelf boilerplate and REITs (e.g. APLE) alongside microcap
  biotech — not a homogeneous ATM-takedown cohort.
- Newest-first Q1 cap + microcap death (404 charts) bias the pilot.

## What this does *not* claim

- No confirmation that shares were actually sold under the ATM
- No float/% sold feature
- No costs, borrow, or sector ETF residualization

## Next

1. Text-review / exhibit parse for true ATM program vs boilerplate.
2. Broader random sample across 2023–2024, not newest 100.
3. Kill if reviewed ATM subset median xs_10d ≥ −2% and unstable across years.
