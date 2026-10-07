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
| ETF timing | `daily_alloc.v1` | static 60/40 SPY/IEF, same execution model | `tools/domain_search.py etf_alloc` |
| CEF selection | `cef_discount.v1` | equal-weight eligible CEF universe | `tools/domain_search.py cef_discount` |
| crypto trend | `crypto_trend.v1` | static 50% BTC / 50% cash | `tools/domain_search.py crypto_trend` |
| country selection | `country_select.v1` | equal-weight country ETFs | `tools/domain_search.py country_select` |
| BDC selection | `bdc_discount.v1` | equal-weight listed BDCs | `tools/domain_search.py bdc_discount` |

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

| Finding | Domain and search | Verdict |
|---|---|---|
| F404704 | ETF: 27 timing rules (trend, dual momentum, turn-of-month, overnight, SMA) | none beats the 60/40, on return or on Sharpe |
| F404705 | ETF: pre-FOMC and sell-in-May tilts | null; pre-FOMC decays after publication |
| F404707 | ETF: Treasury auction-cycle tilt | null (announcement gate; duplicate points disclosed) |
| F404711 | ETF: Fed-liquidity (WALCL) tilt | null |
| F404712 | ETF: lunar and geomagnetic tilts | null |
| F404709 | crypto: BTC trend vs a 50% blend | wins only through exposure; vol-matched null |
| F404710 | country ETFs: momentum, reversal, low-vol | null |
| F404706 | CEF: cheapest 20% by raw discount (H404701) | passed every development stage, then REJECT-bound after a later search in its family (F404708) |
| F404708 | CEF: tax-loss season | null, and it cost H404701 its deflation pass |
| F404713 | CEF: within-category z-score with hysteresis (H404702) | passes every development stage; forward window to 2027-10-07 |
| F404714 | BDC: the H404701 rule on a disjoint universe | same sign (+0.5 active Sharpe), underpowered (3.9 years); caveat: split-adjusted closes against as-reported NAV excluded OCSL and GLAD from cheap selection for some months (F404726) |
| F404722 | BDC: the same rule on 2012-2022 (`BDC_PREPERIOD_TEST.md`) | not run: the filing-text NAV extractor failed its frozen pre-2022 cross-check (96.9% vs 98%) |
| F404728 (superseded by F404733) | spin-offs: buy 21 sessions after listing, hold a year (`SPINOFF_PROTOCOL.md`) | corroborated in a survivor-only backtest (+0.80 vs IWM), but the live product CSD shows no drift over 20 years: a sample artifact |
| F404729 | spin-offs: H404703 registered | REJECT-bound under gate rules v2: p_gate 0.0216 × (1+3) = 0.086 |
| F404730 | S&P 500 deletions: buy after the forced selling (`INDEX_DELETION_PROTOCOL.md`) | uninformative: active Sharpe +0.31, vol-matched +0.14, SPA p 0.20 |
| F404731 | credit sleeve: ANGL (fallen angels) vs HYG, static (`FALLEN_ANGEL_PROTOCOL.md`) | corroborates: +1.9%/yr, active Sharpe +0.30, SPA p 0.024, no IEF/SPY beta; a sleeve choice, too weak for the v2 gate |
| F404732 | CEF mechanism, live: CEFS (Saba) vs PCEF, static (`CEF_PRODUCT_PROTOCOL.md`) | corroborates: +5.4%/yr, active Sharpe +0.59, SPA p 0.001, all eras positive; registrable only after the 10-year floor (about 2027-05) |
| F404733 | spin-offs, live: CSD (Invesco S&P Spin-Off ETF) vs IJH, static (`SPINOFF_PRODUCT_PROTOCOL.md`) | uninformative, null in substance: active Sharpe +0.04 over 19.7 years, max DD -70.5% |
| F404734 | bond sleeve: MNA (merger arbitrage ETF) vs IEF, static (`MERGER_ARB_PRODUCT_PROTOCOL.md`) | null: active Sharpe +0.05; equity-correlated (+0.45), fell 12.6% in the COVID crash |
| F404735 | buybacks, live: PKW (BuyBack Achievers ETF) vs SPY, static (`BUYBACK_PRODUCT_PROTOCOL.md`) | contradicts: active Sharpe -0.04 over 19.7 years |
| F404727 | small caps: earnings-announcement premium (`EARNINGS_PREMIUM_PROTOCOL.md`) | contradicts: active Sharpe -1.62 / -2.69 after 30 bps costs (15-34%/yr of turnover cost) |
| F404725, F404726 | mREIT: the rule on mortgage REITs vs book value (`MREIT_DISCOUNT_TEST*.md`) | not run twice: XBRL misses series-tagged preferred; stated-value extraction failed its blind audit (3/27 vs 2) |

**The pattern.** Every published effect on liquid instruments has decayed or vanished.
The surviving effect is discount selection in closed-end funds: capacity-constrained, in
instruments institutions cannot trade at size. It replicates in sign on BDCs.

H404702 in practice:
- **Capacity.** A sleeve of single-digit to low-tens of millions; exit liquidity binds
  first (F404723).
- **Risk.** The active edge gains in crashes, but the strategy itself draws down 44.5%:
  an overlay, not a bond (F404724).

**What blocks more replication is measurement, not the hypothesis.** Three tests on other
NAV vehicles each closed NOT RUN on their own data validation, before any return was seen:
- BDC 2012-2022 (F404722);
- mREIT v1 (F404725);
- mREIT v2 (F404726).

Per-share NAV and book value read from SEC filings is unreliable: preferred stock tagged
per series or in custom elements, text tables with look-alike rows, split bases.
CEFConnect's consistent price/NAV pair is what makes the CEF test measurable.

Next unlocks, in order:
1. H404702's forward window, which matures 2027-10-07.
2. A vendor source of consistent price/NAV (or price/book) pairs for BDCs and mREITs.
3. An audited hourly source of at least 1480 days, which the price profile needs
   (`DEFLATION_RULE_QUESTION.md`).

**Guards added along the way.** A search refuses to run:
- a grid with duplicate points;
- in a family holding a live registered hypothesis, unless that hypothesis is
  acknowledged with `--acknowledge-live`.

Every report shows exposure and the vol-matched active Sharpe.

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
