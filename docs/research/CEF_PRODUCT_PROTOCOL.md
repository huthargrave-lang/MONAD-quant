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

## Result: CORROBORATES (2026-10-07)

Data: snapshot DS-6e2f0f62 (SPY, PCEF, CEFS). Window 2017-04-20..2026-10-02 (9.4 years,
2,377 sessions).

| | Excess Sharpe | CAGR | Max DD | Active Sharpe vs PCEF | Vol-matched | Eras |
|---|---|---|---|---|---|---|
| PCEF (benchmark) | 0.32 | 6.23% | -38.6% | | | |
| CEFS | 0.63 | **11.64%** | -39.0% | **+0.59** | +0.52 | +0.33 / +0.44 / +0.98 |

- **Statistics.** SPA p 0.0012, < 0.0002 and 0.0002 at blocks 20/63/126 (B = 5000).
  Active DSR 0.965. No look-ahead violations.
- **Verdict: corroborates.**
- **Reading.** A real, fee-paying, capacity-limited product that buys discounted CEFs and
  agitates to close the discounts beat the broad CEF index by about 5%/yr. The drawdown
  was the same, every era was positive, and the vol-matched active Sharpe barely moves,
  so leverage does not explain it. It is out of sample and survivorship-free (both funds
  live throughout), and no search in this repo chose it. This is the strongest
  independent evidence that the mechanism behind H404702 is real and survives
  implementation.
- **The v2 gate would admit it.** Worst p 0.0012 × (1 + 3) ≈ 0.005 ≤ 0.05.
- **It cannot be registered yet.** The tactical profile requires at least 10 years of
  development data (`prereg.MIN_TACTICAL_YEARS`), and CEFS launched in 2017-03. A
  registration becomes possible around 2027-05.
- **For the product (D6).** A CEF sleeve can be held as CEFS today. It carries CEF
  equity-and-credit drawdowns (-39%), so it belongs beside the static allocation, not in
  place of bonds.

## Amendment 1 (2026-10-07): two more live discount-capture products, frozen before their prices are loaded

CEFS corroborated, but it only launched in 2017 (9.4 years), short of the tactical
profile's 10-year floor. Two other live funds run discount-to-NAV strategies in closed-end
funds, with longer histories:

- **MDCEX**, Matisse Discounted Closed-End Fund Strategy (institutional class, 2012-10).
  A pure discount strategy. **Primary.**
- **RNCOX**, RiverNorth (2006-12; now an ETF share class). CEF discount trading mixed with
  tactical allocation. Secondary.

They answer the same question as CEFS, so they join the **same family** (`cef_product.v1`)
as grid `funds`, against the same benchmark (PCEF).

| Item | Frozen choice |
|---|---|
| Price data | a new snapshot: SPY (calendar), PCEF, MDCEX, RNCOX, 2009-06-01..2026-10-02. CEFS is not included, so the window is set by MDCEX. |
| Window | from the first session PCEF, MDCEX and RNCOX have all been priced for 21 sessions (about 2012-11) |
| Verdict | **corroborates** if MDCEX has active Sharpe > 0 with t > 1.0 and the family SPA over this window's points (K = 2) is below 5%; **contradicts** if MDCEX's active Sharpe ≤ 0; otherwise uninformative. RNCOX is reported but does not decide. |
| Registration | if corroborated, MDCEX's window passes the 10-year floor. Under gate rules v2 its m adds the off-window CEFS point to the declared 3. |
| Execution caveat | mutual funds trade once a day at NAV. The evaluator's open and close are both NAV for them. Positions are static, so this matters little. |
