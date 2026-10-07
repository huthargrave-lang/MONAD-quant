# Spin-off drift as a live product: protocol

**Frozen and committed before any CSD or IJH price was loaded (2026-10-07).**

## The question

F404728 found, in a survivorship-limited backtest, that spin-offs bought after their
first month beat IWM. As H404703 it is REJECT-bound under gate rules v2. The Invesco S&P
Spin-Off ETF (**CSD**, December 2006) holds US spin-offs for a period after their
distribution, from an index the repo did not choose. Against mid caps (**IJH**, S&P
MidCap 400, the size most spin-offs land in), it is an out-of-sample, survivorship-free
test of the same mechanism, over about 20 years.

## Design

| Item | Frozen choice |
|---|---|
| Candidate (`static_product` CSD) | 100% CSD |
| Benchmark (`product_benchmark` IJH) | 100% IJH |
| Execution | the daily evaluator's static rule, every 21 sessions in 21 tranches, at the open; distributions reinvested; tier1 costs |
| Price data | a new snapshot: SPY (calendar), IJH, IWM, CSD, 2006-06-01..2026-10-02. IWM and SPY are diagnostics only. |
| Window | from the first session both CSD and IJH have been priced for 21 sessions |
| Counting | `tools/domain_search.py spinoff_product` (one point plus the benchmark). Prior search 3, for a published effect. |

## Verdict, stated in advance

- **Corroborates:** active Sharpe > 0 with t > 1.0, and SPA at 5%.
- **Contradicts:** active Sharpe ≤ 0.
- **Uninformative:** anything else.

With about 20 years of history, a corroborated result can be registered under gate rules
v2, which needs worst p × (1 + 3) ≤ 0.05.

## Known weaknesses, stated in advance

- **Index construction.** CSD's index rules (holding period, size and liquidity screens,
  caps) differ from F404728's rule, and it changed index provider once. A win supports
  the mechanism, not F404728's exact parameters.
- **Benchmark choice.** IJH is fixed in advance. IWM and SPY are shown only as
  diagnostics, so the benchmark cannot be shopped after the fact.
- **CSD is small and thinly traded**, so its fees and tracking matter.

## Result: UNINFORMATIVE, null in substance (2026-10-07)

Data: snapshot DS-f247566b (SPY, IJH, IWM, CSD). About 19.7 years from CSD's first 21
sessions.

| | Excess Sharpe | CAGR | Max DD | Active Sharpe vs IJH | Vol-matched | Eras |
|---|---|---|---|---|---|---|
| IJH (benchmark) | 0.45 | 9.57% | -55.1% | | | |
| CSD | 0.44 | 9.72% | **-70.5%** | +0.04 | -0.02 | -0.10 / -0.33 / +0.48 |

- **Statistics.** SPA p 0.42 at every block; active DSR 0.57; t ≈ 0.18. No look-ahead
  violations.
- **Verdict: uninformative** (active Sharpe > 0, t < 1).
- **Declared diagnostics, not deciding.** Active Sharpe against IWM +0.09 (+1.3%/yr) and
  against SPY -0.01. No benchmark shows an edge.

**What it means for F404728.** A live, survivorship-free spin-off product earned nothing
over mid caps across two decades, and drew down 15 points deeper. The survivor-only
backtest's +0.80 active Sharpe most likely came from survivorship plus a strong 2020s
cohort. CSD's only positive era is also 2020+ (+0.48), which matches that cohort, but the
effect does not persist. F404728 is now best read as an artifact of its sample, and
H404703's REJECT stands on two grounds.
