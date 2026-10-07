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
| Benchmark (`static_sleeve` HYG) | 100% HYG (iShares iBoxx $ High Yield Corporate Bond ETF) |
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
