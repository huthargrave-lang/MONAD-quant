# Fallen-angel credit sleeve: protocol

**Frozen and committed before any ANGL or HYG price was loaded (2026-10-07).**

## The question

When a bond is downgraded from investment grade to high yield, insurers, IG funds and
CLO-like mandates must sell it, whatever the price. Fallen-angel indices have historically
beaten the broad high-yield market (Ambrose, Cai and Helwege 2012; index-provider
research). For this repo's goal, a bond alternative (D6 recommends a static allocation),
the question is static: **as the credit sleeve, does a fallen-angel fund beat the broad
high-yield fund?** Nothing is timed.

## Design

| Item | Frozen choice |
|---|---|
| Candidate (`static_sleeve` ANGL) | 100% ANGL (VanEck Fallen Angel High Yield Bond ETF, since 2012) |
| Benchmark (`sleeve_benchmark` HYG) | 100% HYG (iShares iBoxx $ High Yield Corporate Bond ETF) |
| Execution | the daily evaluator's static rule, every 21 sessions in 21 tranches, at the open; distributions reinvested by the evaluator; tier1 costs |
| Price data | a new snapshot: ANGL, HYG, IEF, SPY (the last two for diagnostics), 2012-01-01..2026-10-02 |
| Window | from the first session both ANGL and HYG have been priced for 21 sessions |
| Counting | `tools/domain_search.py credit_sleeve` (one point plus the benchmark). Prior search 3. |

## Verdict, stated in advance

- **Corroborates:** active Sharpe > 0 with t > 1.0, and SPA at 5% (K = 1, so the
  bootstrap p of the active mean).
- **Contradicts:** active Sharpe ≤ 0.
- **Uninformative:** anything else.

The report includes the vol-matched active Sharpe. ANGL carries more duration and more
BB-rated paper than HYG, so a "win" that is only extra rate or quality exposure would show
as a vol-matched active Sharpe near zero. Under gate rules v2, admission needs
p × (1 + 3) ≤ 0.05.

## Known weaknesses, stated in advance

- **Two products, one comparison.** The result is about these two funds, including fees
  (ANGL 0.25-0.35%, HYG about 0.49%) and index construction, not only the mechanism.
- **Duration and quality differ.** IEF is in the snapshot so the report can show how much
  of any difference rates explain.
- **About 14 years** is short for credit cycles: 2015-16 energy, 2020, 2022.

**Correction before any result was read (2026-10-07).** The first run recorded its trials
(benchmark TR-20261007T041712Z-eb23cf97, search TR-20261007T041713Z-2cbc8fe5), but the
report refused to judge them. The benchmark shared the candidate's class name, so it could
not tell them apart, and printed no statistic. The benchmark is renamed
`sleeve_benchmark`, and the domain is re-run. The first run's trials stay in the ledger
and are counted. Its ANGL trial is the same point as the re-run's.

## Result: CORROBORATES under the pre-stated criterion (2026-10-07)

- **Data.** Snapshot DS-62945d51 (SPY, HYG, IEF, ANGL; 2012-2026).
- **Ledger.** Benchmark TR-20261007T041712Z-eb23cf97. The search ran twice on the same
  ANGL point: TR-20261007T041713Z-2cbc8fe5 and TR-20261007T041737Z-d7a2fb16.
- **Window.** About 14.4 years.
- **Reporting fix.** The report now drops members with no active variance. The first
  run's HYG benchmark, recorded under the candidate's class name, appears as a point
  identical to the benchmark. Dropping it is an exact equivalence (gate rules v2 consensus
  (ii)).

| | Excess Sharpe | CAGR | Max DD | Active Sharpe vs HYG | Vol-matched | Eras |
|---|---|---|---|---|---|---|
| HYG (benchmark) | 0.36 | 4.36% | -22.0% | | | |
| ANGL | 0.51 | 6.24% | -29.3% | **+0.30** | +0.20 | +0.42 / +0.51 / -0.50 |

- **Statistics.** SPA p 0.026, 0.022 and 0.024 at blocks 20/63/126. t = 0.30 × √14.4 ≈
  1.1. No look-ahead violations.
- **Verdict: corroborates.**

**Diagnostics** (from the recorded series):
- The ANGL − HYG return is +1.9%/yr, with essentially no loading on IEF (beta 0.07) or SPY
  (-0.03), R² 0.01.
- The alpha after both is +2.2%/yr (OLS t 1.33). The edge is not just longer duration or
  more equity beta.
- 2022 was negative (-0.50 active Sharpe).

**What it means for the product (D6).** For a static allocation's credit sleeve, ANGL
historically beat HYG by about 2%/yr, not through rate or equity exposure, at the cost of
deeper drawdowns (-29% against -22%). The evidence is moderate: it clears SPA at 5%, but
under gate rules v2 a registered version would need p × (1 + 3) ≤ 0.05, and 0.024 × 4 ≈
0.10 would fail. This is a reasonable sleeve choice, not an admitted edge.
