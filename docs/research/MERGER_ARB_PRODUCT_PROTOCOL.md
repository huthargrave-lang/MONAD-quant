# Merger arbitrage as a bond sleeve, live product: protocol

**Frozen and committed before any MNA or IEF price was loaded (2026-10-07).**

## The question

D6 recommends a static allocation as the bond alternative. Merger arbitrage (buying
announced targets below their deal price) earns a deal-risk premium with low volatility.
It is the classic candidate for a bond-like sleeve, and the premium is published (Mitchell
and Pulvino 2001). The IQ Merger Arbitrage ETF (**MNA**, November 2009) runs it live. The
question is static: as a sleeve, does MNA beat the intermediate Treasuries (**IEF**) it
would replace in a static allocation?

## Design

| Item | Frozen choice |
|---|---|
| Candidate (`static_product` MNA) | 100% MNA |
| Benchmark (`product_benchmark` IEF) | 100% IEF |
| Execution | the daily evaluator's static rule, every 21 sessions in 21 tranches, at the open; distributions reinvested; tier1 costs |
| Price data | a new snapshot: SPY (calendar), IEF, SHY, MNA, 2009-06-01..2026-10-02. SPY and SHY are diagnostics only. |
| Window | from the first session both MNA and IEF have been priced for 21 sessions |
| Counting | `tools/domain_search.py merger_arb_product` (one point plus the benchmark). Prior search 3, for a published premium. |

## Verdict, stated in advance

- **Corroborates:** active Sharpe > 0 with t > 1.0, and SPA at 5%.
- **Contradicts:** active Sharpe ≤ 0.
- **Uninformative:** anything else.

Also reported: drawdowns, correlation with SPY, and the 2020 and 2022 eras. A bond sleeve
is judged partly by what it does when stocks fall.

## Known weaknesses, stated in advance

- **Different risks.** IEF carries rate risk and is a crisis hedge; MNA carries deal and
  equity tail risk (2008 is before MNA's inception; 2020 is in the window). A win on
  active Sharpe can coexist with being a worse hedge. The SPY correlation is reported for
  that reason.
- **One product.** MNA has a hedge overlay and its own fees; it is not the generic merger
  arbitrage premium.
- **The window includes the 2022 rate shock,** which hurt IEF badly. The eras are
  reported so one year cannot carry the verdict unseen.
