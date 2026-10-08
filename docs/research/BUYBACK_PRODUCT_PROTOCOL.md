# Buyback drift, live product: protocol

**Frozen and committed before any PKW price was loaded (2026-10-07).**

## The question

Firms that buy back their own shares have outperformed afterwards (Ikenberry, Lakonishok
and Vermaelen 1995): managers buy when they think the stock is cheap, and the market
under-reacts. The Invesco BuyBack Achievers ETF (**PKW**, December 2006) holds US
companies that have cut their share count by at least 5% over the trailing year, from an
index the repo did not choose. Against the market (**SPY**), it is a survivorship-free,
fee-paying, out-of-sample test of the effect, over about 20 years.

## Design

| Item | Frozen choice |
|---|---|
| Candidate (`static_product` PKW) | 100% PKW |
| Benchmark (`product_benchmark` SPY) | 100% SPY |
| Execution | the daily evaluator's static rule, every 21 sessions in 21 tranches, at the open; distributions reinvested; tier1 costs |
| Price data | a new snapshot: SPY (calendar and benchmark), IJH, PKW, 2006-06-01..2026-10-02. IJH is a diagnostic only. |
| Window | from the first session both PKW and SPY have been priced for 21 sessions |
| Counting | `tools/domain_search.py buyback_product` (one point plus the benchmark). Prior search 3, for a published effect. |

## Verdict, stated in advance

- **Corroborates:** active Sharpe > 0 with t > 1.0, and SPA at 5%.
- **Contradicts:** active Sharpe ≤ 0.
- **Uninformative:** anything else.

## Known weaknesses, stated in advance

- **Size tilt.** PKW is equal-weighted-ish across mid and large caps, while SPY is
  cap-weighted. The 2013-2026 large-cap dominance works against PKW for reasons that have
  nothing to do with buybacks. IJH is reported as a size diagnostic.
- **Index rule.** PKW holds companies that already bought back (the trailing year), not
  fresh announcements. That is a slower, more crowded version of the published effect.

## Result: CONTRADICTS (2026-10-07)

Data: snapshot DS-7b7b5eba (SPY, IJH, PKW), from PKW's first 21 sessions to 2026-10-02
(about 19.7 years).

| | Excess Sharpe | CAGR | Max DD | Active Sharpe vs SPY | Vol-matched | Eras |
|---|---|---|---|---|---|---|
| PKW | 0.52 | 10.46% | -54.6% | **-0.04** | -0.06 | +0.12 / -0.09 / -0.18 |

- **Statistics.** SPA p 1.00 at every block; active DSR 0.42. No look-ahead violations.
- **Declared size diagnostic:** against IJH, +0.04 (+0.3%/yr).
- **Verdict: contradicts.**
- **Reading.** Twenty years of a live buyback product show no drift against the market,
  and essentially none against mid caps. It joins the published liquid-equity effects that
  do not survive in this repo.
