# Daily strategies through the accountable workflow

The hourly engine has no edge (F13, D6), and its numbers are upper bounds until its
execution matches live (F404703). This is the path for strategies that trade daily,
built so that a result can be checked rather than trusted.

```
frozen data ──> counted evaluator ──> trial ledger ──> relative statistics ──> web finding
  DS-<sha>         evaluate_daily      one family per      active vs the domain's
  CEFNAV-<sha>     (refuses to run     domain + evaluator  benchmark: SPA, DSR,
                    without a trial)   version             eras, look-ahead
```

## Data: frozen, content-addressed, validated

| Artifact | Module | What it pins |
|---|---|---|
| `docs/research/data/DS-<sha>.csv.gz` | `src/research/daily_data.py` | raw daily open/close per asset plus distributions (total returns are built, not taken from a vendor's adjustment), and FRED DTB3 cash cross-checked against ^IRX |
| `docs/research/data/CEFNAV-<sha>.csv.gz` | `src/research/cef_data.py` | weekly closed-end-fund price and NAV from CEFConnect; inconsistent rows removed, never repaired |
| `docs/research/data/fomc_scheduled_meetings.json` | `src/research/fomc_calendar.py` | the Fed's scheduled meetings, parsed from federalreserve.gov, with page hashes |

The sha is of the decompressed canonical CSV, so the same data always names the same
snapshot and a tampered file is refused on load.

**Validation.** Core assets must pass every check, or nothing is written:
- the open is not synthesised (tick-aware: a price pinned at its tick legitimately repeats);
- no unadjusted split;
- no hole after listing;
- no cash gap.

**Large universes.** Assets marked `optional`, such as every closed-end fund, are dropped
with the reason recorded. An asset with synthesised opens is kept but flagged, and the
evaluator refuses to trade it at the open.

**Extreme sessions.** A move beyond ±50% in one session is accepted only when an
independent source corroborates it. Closed-end funds really did this in October 2008 and
March 2020.

## Execution model (`src/research/daily_strategy.py`)

- **Timing.** A decision at the close of day t trades at day t+1's open or close, never at
  the price it was computed from.
- **Returns.** Holdings drift between rebalances. The night and day legs compound. Cash
  earns the lagged bill rate over calendar days.
- **Costs.** One-way, per asset tier and era (`COST_BPS`); the gate's cost stress doubles them.
- **Tranches.** Monthly rules run as 21 equal-capital tranches, one per rebalance-day offset,
  so no single day's luck decides a result.
- **Limits.** Long only, no leverage.

## Domains, families and benchmarks

| Domain | Family | Benchmark (own `*_reference` family) | Tool |
|---|---|---|---|
| ETF timing | `daily_alloc.v1` | static 60/40 SPY/IEF, same execution model | `tools/daily_search.py` |
| CEF selection | `cef_discount.v1` | equal-weight eligible CEF universe | `tools/cef_search.py` |

Membership is structural: same evaluator version and domain, under any label. Every grid
is frozen in code before it runs, and `PRIOR_SEARCH_TRIALS` declares the search the ledger
cannot see. Each famous rule is counted as the survivor of 3 published variants. The
constant only ever grows.

## Statistics: every one relative (`src/research/allocation_stats.py`)

A long stock/bond portfolio earns a positive Sharpe from beta alone. So the unit of
evidence is the **active** series, strategy minus benchmark on identical sessions, costs
and cash.

- **Familywise.** Hansen's SPA_c over every family member, at mean block lengths 20, 63 and
  126 sessions. A candidate must clear the bar at every one.
- **Active DSR.** N = effective independent active series + unknown results + declared prior search.
- **Eras.** The active Sharpe in each pre-declared era: 2007-13, 2014-21, 2022+.
- **Look-ahead.** Orders computed with all prices, and NAV observations, after a cut erased
  must equal the full-data orders up to that cut, at 12 cuts.

## Results so far

| Finding | Search | Verdict |
|---|---|---|
| F404704 | 27 ETF timing rules (trend, dual momentum, turn-of-month, overnight, SMA) | none beats the 60/40, on return or on Sharpe |
| F404705 | 4 calendar tilts (pre-FOMC, sell-in-May) | null; pre-FOMC decays after publication |

## Admission (`tactical_allocation` profile, `tools/admit_tactical.py`)

A daily candidate is registered with `profile: tactical_allocation`. Its `params` freeze:
- the domain and the candidate, which must be a point of the domain's frozen grid;
- the data shas, the eras, `min_years` (at least 10) and the declared prior search;
- a familywise alpha of at most 0.05.

`tools/admit.py <H>` then runs the chain:

| Stage | What it checks |
|---|---|
| registration | the candidate is a point of its domain's frozen grid |
| code | clean tree at a known commit |
| refutations | objections filed and all refuted |
| witness | registration, searched runs and data files are on the deploy branch |
| lookahead | orders unchanged with data erased after each of 12 cuts |
| development | the counted re-run must reproduce the recorded search trial exactly |
| deflation | active DSR against the family's search plus declared prior |
| familywise | SPA adjusted p at most the registered alpha, at every block length |
| eras | active Sharpe > 0 in every registered era |
| cost_stress | still ahead with both portfolios at 2x cost |
| forward | on a new snapshot fetched after registration, which must reproduce the old one where they overlap |
