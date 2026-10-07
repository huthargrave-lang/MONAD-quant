# The CEF discount mechanism as a live product: protocol

**Frozen and committed before any CEFS or PCEF price was loaded (2026-10-07).**

## The question

H404702 (backtest) finds that holding closed-end funds cheap against their own discount
history beats owning them all. The Saba Closed-End Funds ETF (**CEFS**, launched 2017)
runs a version of that mechanism live: it buys discounted CEFs and pushes boards to
close the discounts (tender offers, conversions). The Invesco CEF Income Composite ETF
(**PCEF**) owns a broad, cap-weighted CEF index.

CEFS against PCEF is an out-of-sample, survivorship-free test of whether discount capture
survives real trading, fees and capacity. Neither the rule nor the funds were chosen by a
search in this repo. It is not a CEF-family trial, so it does not count against H404702.

## Design

| Item | Frozen choice |
|---|---|
| Candidate (`static_product` CEFS) | 100% CEFS |
| Benchmark (`product_benchmark` PCEF) | 100% PCEF |
| Execution | the daily evaluator's static rule, every 21 sessions in 21 tranches, at the open; distributions reinvested; tier1 costs |
| Price data | a new snapshot: SPY (calendar), PCEF, CEFS, 2017-01-01..2026-10-02 |
| Window | from the first session both funds have been priced for 21 sessions |
| Counting | `tools/domain_search.py cef_product` (one point plus the benchmark). Prior search 3, conservatively. |

## Verdict, stated in advance

- **Corroborates:** active Sharpe > 0 with t > 1.0, and SPA at 5%.
- **Contradicts:** active Sharpe ≤ 0.
- **Uninformative:** anything else.

The vol-matched active Sharpe is reported, because CEFS uses some leverage and holds more
discounted, riskier funds.

## Known weaknesses, stated in advance

- **One manager, not the rule.** CEFS is Saba's discretion plus activism plus leverage.
  A win shows that discount capture can survive costs; it does not validate H404702's
  exact rule.
- **Fees.** CEFS reports a large acquired-fund-fee figure, as both funds hold CEFs.
- **About 9.5 years**, including 2020 and 2022.
