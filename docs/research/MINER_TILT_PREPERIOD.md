# Miner/metal tilt: the 1984-2005 test (the last historical test of the rule)

**Frozen and committed before any ^XAU, Bundesbank gold or GC=F observation dated 1983-2005
was fetched (2026-10-09).** A board of three reviewed the draft:
- statistics;
- data provenance and market mechanics;
- an adversary.

Every amendment below is theirs, with conflicts resolved as recorded.

## Why

The frozen miner/metal ratio tilt held its sign out of sample in all three miner pairs over
2016-2026 (F366200, F366201):

| Pair | Active Sharpe |
|---|---|
| GDX/GLD | +0.27 |
| SIL/SLV | +0.34 |
| GDXJ/GLD | +0.32 |
| GLD/SLV (control) | -0.20 |
| IWM/SPY (control) | +0.10 |

None of these reached 5%. The 2006-2015 data chose the rule, so it cannot test it. Before 2006 the rule has never been run, which makes this its decisive test.

**Stopping rule.** This is the rule's last historical test. Whatever the result, the only
next step is a forward window. No further index, single stock, pair or segment from before
2006 may be tested.

## What was touched before the freeze (disclosed)

- **Overlapping data already in the repo.** Committed manifests hold daily proxies that
  overlap this window. None was ever used for a miner-versus-gold statistic:
  - DS-bae9cfd9 (1996-2003) and DS-18cef162 hold ASA (a gold-miner closed-end fund) and
    CEF (Central Fund of Canada, bullion);
  - DS-32c992fb holds GLD from 2004-11-18.

  A diagnostic for 1984-1995 is pre-stated because it ends before that overlap.
- **Development fetches, none of which read a 1983-2005 observation of the test assets:**
  - Bundesbank EUR/USD for 2020, to test the parser;
  - Bundesbank series metadata, plus a 1975 query, before the window, to find the series
    keys (it returned no gold observation);
  - Yahoo ^XAU metadata (firstTradeDate 1983-12-19), read by a board member;
  - the World Bank Pink Sheet file, of which only its header and its 2020-01 gold value
    were read.
- **The rule's designers and reviewers know the history** of gold miners in the 1980s-90s
  (the 1990s bear market, Bre-X in 1996-97, the 2001-03 miner rally). The rule is frozen.
  The window ends where the sources end, and the 2000-2005 segment is MANDATORY inside the
  verdict, so no fork shaped by that knowledge is left open.

## Data

**Redistribution.**
- The repo is public.
- LBMA gold prices are licensed (FRED withdrew them in 2022).
- Yahoo's index history may not be redistributed.
- The Bundesbank/ESCB reuse policy requires unmodified data and excludes third-party data.
  The gold fixing's source is the Frankfurt Stock Exchange.

**So no observation is committed.** Snapshots are built with `private=True`
(`src/research/daily_data.PRIVATE_DATA_DIR`, gitignored). Each committed manifest records:
- the csv sha-256, which names the exact bytes;
- the series keys and sources;
- the carries and the fixing calendar;
- the attribution: "Source: Deutsche Bundesbank (Frankfurt Stock Exchange gold fixing;
  Frankfurt official FX fixing); USD conversion own calculation. Index history: Yahoo
  Finance."

`src/research/miner_preperiod.build_segment` rebuilds each snapshot.

| | Segment A | Segment B |
|---|---|---|
| Miner leg | ^XAU (PHLX Gold & Silver Sector index), Yahoo, price index | the same |
| Gold leg | Frankfurt gold fixing (BBEX3.D.XAU.DEM.EA.AC.C01, DM/kg) / Frankfurt official USD fixing (BBEX3.D.USD.DEM.AA.AC.000, DM/USD) / 32.1507466, in USD per oz, used only on dates where both fixed | Yahoo GC=F (COMEX front month, unadjusted rolls, settle 13:30 ET; disclosed) |
| Calendar | ^GSPC (NYSE sessions) | the same |
| Fetched | 1983-12-19 (^XAU's first trade) .. the last gold fixing of 1998 | 2000-08-30 .. 2005-12-30 |
| Scored from | the first session with 60 + 21 sessions of history (about 1984-04) | the same (about 2000-12) |
| Eras | ..1989-04 / 1989-05..1994-01 / 1994-02.. | ..2002 / 2003.. |

- **Close-only.** Every series is close-only. Opens are rebuilt from the previous close and
  flagged, so the evaluator refuses open orders.
- **Carries.** A session without a gold observation carries the previous one.
  - *Explained:* the Frankfurt USD fixing is also absent, meaning the exchange was shut.
  - *Unexplained:* anything else. Unexplained carries above 0.5% of the window's sessions
    mean **NOT RUN**.
  - The sessions where gold fixed form the manifest's **fixing calendar**: a scheduled
    exchange calendar, known in advance like the NYSE's.

**Mechanical screens.** Any failure means **NOT RUN**:
- ^XAU must print a new close on at least 98% of sessions in every calendar year (an
  unchanged close counts as missing);
- no close may be zero or negative;
- every daily ^XAU move beyond 15% must be matched in sign by the median of a fund panel:
  OPGSX, VGPMX, USAGX, FSAGX and UNWPX, using dividend-adjusted closes for validation only;
- the monthly mean of the gold leg's own observations must be within 2% of the World Bank
  Pink Sheet monthly gold price in every month. The file is
  `CMO-Historical-Data-Monthly.xlsx` (URL in `miner_preperiod.WORLD_BANK_URL`); its payload
  sha-256 is recorded, and the file itself is not committed.

## Rule

The frozen F366200 rule:
- z60 of log(miner/metal);
- miner weight clip(0.5 − 0.25 z, 0, 1), with gold the rest;
- 21 tranches;
- benchmark 50/50;
- plain active, sign +1.

**Every deviation, disclosed:**
1. **Execution at the next close** (`execution: "close"`): neither leg has an opening
   print.
2. **Decide only on fresh sessions** (`fresh`): a scheduled decision on a session where
   either leg is stale (a carried fixing or an unchanged index close) moves to the next
   fresh session.
3. **Execute only on fixing sessions** (`fixings`): an execution that would fall on a
   carried fixing moves to the next fixing session. The benchmark does the same. Trading at
   a carried fixing would be look-ahead, because the miner leg has already priced the move
   the fixing misses. An unchanged ^XAU close cannot be anticipated; such executions are
   counted and reported.
4. **^XAU is a price index.** The miner dividends it omits (about 1-3%/yr) enter as a
   bound, |mean(w − 0.5)| × yield.
5. **The gold leg is a fixing or futures settle, not a traded fund.**
6. **Costs:** miner leg 35 bps one-way (1/8-dollar ticks until 1997, about 15-40 bps
   half-spread on $15-40 shares), gold 20 bps. Tiers `basket_pre_decimal` and `bullion`.

## Domains (all counted)

| Domain | Pair, segment | Role |
|---|---|---|
| `miner_preperiod_a` | ^XAU / GOLD_FFM, A | the verdict (with B) |
| `miner_preperiod_b` | ^XAU / GOLD_COMEX, B | the verdict (with A) |
| `placebo_preperiod` | ^GSPC / GOLD_FFM, A | placebo: an unlinked equity/gold pair, sharing the gold build and the Frankfurt/New York timing |
| `miner_preperiod_lags` | ^XAU / GOLD_FFM, A, executed at t+3 and t+6 | robustness to measurement noise |

`tools/domain_search.py <domain> --snapshot <sha>` runs each one.
`tools/miner_preperiod_report.py` runs the screens, records the counted 2x and 0.5x cost
runs and a counted diagnostic re-run (for per-asset weights), and computes the verdict.

## Verdict, stated in advance

The verdict series is the concatenation of segment A's and segment B's active series.
Positions never cross the 1999-2000 gap: each segment has its own warm-up. One SPA is run
on that series, under gate rules v2 with **m = 5**. The charge counts the alpha already
spent on this rule's promotion gates: the confirmation's Holm gate at up to 0.025, plus
the replication's p × 3 gate at 0.0167, leaves 0.05/6.

- **Corroborates.** All of these hold:
  - Sharpe > 0, t > 1.0, and worst-block SPA p < 0.05;
  - at **2x the primary costs**, the combined Sharpe is > 0;
  - **lag ladder:** Sharpe(t+6) > 0 and ≥ 0.5 × Sharpe(t+1), on segment A;
  - **noise bound:** segment A's active return per year ≥ 3 × 2.5 σ̂²/s̄. Here σ̂² is the
    variance-ratio noise estimate of log(^XAU/gold), [Var(Δ₁) − Var(Δ₂₁)/21] × 21/40, and
    s̄ is the ratio's mean 60-session standard deviation;
  - **noise-only placebo:** segment A's Sharpe beats the 95th percentile, at the worst ρ,
    of 1000 synthetic panels for each ρ in {0.5, 0.86, 0.95}. Each panel combines:
    - the real gold leg;
    - the real stale-print calendar;
    - a random-walk ratio at the realised volatility;
    - AR(1) noise of size σ̂ at ρ.

    Each panel goes through the exact evaluator and costs. This is synthetic, so it is
    uncounted; the exemption is in `src/strategy/counted.py`.
- **Contradicts.** Sharpe ≤ 0.
- **Uninformative.** Anything else.

**Promotion** (the tilt is an edge; register GDX/GLD for a forward window). All of these
hold:
- the result corroborates;
- p_gate = worst p × 6 ≤ 0.05;
- dropping any one of the four eras (A1, A2, A3, B) leaves the Sharpe > 0;
- the placebo does not block. It blocks when its **timing part** (see below) has a
  Newey-West t > 1 that is at least the tilt's own timing t. The placebo's raw result is
  confounded: the S&P rose about 7x against gold over 1983-98, so its z60 sits near +1.7.

**A clean failure closes the lead.** Any one of these retires the F366200 tilt family:
- the result contradicts;
- Sharpe(t+6) ≤ 0;
- the noise-only placebo fails.

After a close, nothing from before 2006 may be tested, and 2016-26 stays unregistered. An
uninformative result also ends historical testing.

**Diagnostics, stated in advance:**
- each segment's Sharpe and t;
- era Sharpes;
- Sharpe at 0.5x costs, an optimistic sensitivity;
- the lag Sharpes;
- the noise estimates of gold, ^XAU and the ratio;
- the static vs timing split, active ≈ (w̄ − 0.5)(r_m − r_g) + Σ(w_t − w̄)(r_m − r_g), for
  the tilt (A, B) and the placebo;
- mean(w − 0.5) and the dividend-bias bounds;
- the Sharpe over 1984-1995, before the ASA/CEF overlap;
- the share of the combined active return from the top 5 days (October 1987 is in era
  A1);
- a Stouffer combination of this z with the three 2016-26 z's (weights √years), labelled
  "includes seen data", with **weight 0**.

**Power, stated in advance.** The combined window is about 19.7 years, so the standard
error of the active Sharpe is about 0.225.

| Outcome | Needs an observed Sharpe of | Chance at a true 0.3 | Chance at a true 0.5 |
|---|---|---|---|
| Corroborate (before the gates) | ≥ 0.37 | about 38% | about 72% |
| Promote | ≥ 0.54 | about 14% | about 43% |
| Contradict (observed ≤ 0) | | about 9% | |

## Board record (2026-10-09)

| Amendment | Source |
|---|---|
| Promotion at p × 6 (m = 5), from alpha already spent on promotion gates; stopping rule | statistics; adversary (stopping rule) |
| 2000-2005 segment mandatory, inside the one verdict statistic | statistics (inside the verdict) and adversary (mandatory) over provenance (drop) |
| Stouffer only as a weight-0 diagnostic labelled "includes seen data" | statistics, adversary |
| Placebo judged on its timing part; never a pass condition | statistics; adversary (confound) |
| Costs 35/20 bps; 2x costs must pass; 0.5x as an optimistic sensitivity | provenance (35/20); statistics (2x); adversary (tier2 only as sensitivity) |
| Disclose all deviations; dividend bounds | adversary, provenance |
| Decide only on fresh sessions; execute only on fixing sessions | adversary (stale prints), provenance (look-ahead on carried fixings) |
| Carries: explained by an exchange closure (FX absent too); unexplained > 0.5% means NOT RUN | provenance (the 2% cap would stop every run) |
| Window from ^XAU's first trade (1983-12-19) plus warm-up; no earlier source | provenance |
| Mechanical screens (coverage, zero closes, extreme moves vs a fund panel, World Bank gold) | provenance |
| Noise gates: lag ladder, noise bound, noise-only placebo; clean-fail rules | adversary |
| No observation committed (Bundesbank/ESCB and Yahoo terms); manifests with payload hashes | provenance |
| Corrected provenance (ASA/CEF/GLD manifests) and a 1984-1995 diagnostic | provenance |
| A test that gold moving only after the fixing earns nothing, plus a positive control | provenance (the positive control was added so the zero test is not dead) |
