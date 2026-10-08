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

## Result: UNINFORMATIVE, null in substance (2026-10-07)

Data: snapshot DS-fd08de9e (SPY, IEF, SHY, MNA), from MNA's first 21 sessions (late 2009)
to 2026-10-02.

| | Excess Sharpe | CAGR | Max DD | Active Sharpe vs IEF | Vol-matched | Eras |
|---|---|---|---|---|---|---|
| MNA | 0.18 | 2.63% | -16.7% | +0.05 | +0.03 | -0.23 / -0.02 / +0.49 |

- **Statistics.** SPA p 0.40-0.41; active DSR 0.57. No look-ahead violations.
- **Verdict: uninformative** (t < 1). In substance null.

**Declared diagnostics:**
- Correlation with SPY: MNA +0.45, IEF -0.25.
- Against SHY: active Sharpe +0.22 (+1.6%/yr).
- COVID crash (2020-02-19..03-23): MNA -12.6%, IEF +6.4%, SPY -33.4%.
- 2022 to the October low: MNA -2.9%, IEF -17.0%, SPY -23.8%.

**What it means for D6.** Merger arbitrage is not a better bond sleeve. It earns no
premium over intermediate Treasuries, and it trades rate risk for equity-crash risk: it
fell with stocks in 2020, when Treasuries hedged, and only helped in the 2022 rate shock.
