# Illiquidity premium, live product: protocol

**Frozen and committed before any IWC price was loaded (2026-10-07).**

## The question

The live-product tests so far split along one line. The capacity-constrained mechanisms
show an edge: CEF discount capture (F404732) and, moderately, fallen-angel forced selling
(F404731). The liquid or index-traded ones do not: spin-offs (F404733), buybacks
(F404735) and merger arbitrage (F404734). The most direct test of that line is the
illiquidity premium itself (Amihud 2002): do the least liquid listed US stocks beat small
caps?

The iShares Micro-Cap ETF (**IWC**, August 2005) against the iShares Russell 2000
(**IWM**) is a survivorship-free, fee-paying test over about 21 years.

## Design

| Item | Frozen choice |
|---|---|
| Candidate (`static_product` IWC) | 100% IWC |
| Benchmark (`product_benchmark` IWM) | 100% IWM |
| Execution | the daily evaluator's static rule, every 21 sessions in 21 tranches, at the open; distributions reinvested; tier1 costs (both are liquid ETFs) |
| Price data | a new snapshot: SPY (calendar), IWM, IWC, 2005-06-01..2026-10-02 |
| Window | from the first session both IWC and IWM have been priced for 21 sessions |
| Counting | `tools/domain_search.py microcap_product` (one point plus the benchmark). Prior search 3, for a published effect. |

## Verdict, stated in advance

- **Corroborates:** active Sharpe > 0 with t > 1.0, and SPA at 5%.
- **Contradicts:** active Sharpe ≤ 0.
- **Uninformative:** anything else.

## Known weaknesses, stated in advance

- **Owning the universe is not capturing a premium.** A micro-cap index fund holds every
  micro-cap, including the junk (the "lottery" stocks with poor average returns), and
  pays high fees (about 0.6%) and the costs of an illiquid index. CEFS selects within its
  universe; IWC does not. A null here tests "own the illiquid segment", not "select
  within it".
- **About 21 years,** including 2008, 2020 and 2022.

## Result: CONTRADICTS (2026-10-07)

Data: snapshot DS-0853b44e (SPY, IWM, IWC), from IWC's first 21 sessions (2005) to
2026-10-02.

| | Excess Sharpe | CAGR | Max DD | Active Sharpe vs IWM | Vol-matched | Eras |
|---|---|---|---|---|---|---|
| IWC | 0.35 | 7.54% | -64.6% | **-0.14** | -0.17 | -0.61 / -0.14 / +0.25 |

- **Statistics.** SPA p 1.00 at every block; active DSR 0.27. No look-ahead violations.
- **Verdict: contradicts.**

**What it means for the pattern.** Owning the illiquid segment earns no premium after a
micro-cap index fund's fees and costs. What worked, CEFS (F404732) and H404702, was
*selecting within* a capacity-constrained segment on a price-versus-value anchor
(discount to NAV). Neither illiquidity alone nor a liquid event screen (spin-offs,
buybacks) did.
