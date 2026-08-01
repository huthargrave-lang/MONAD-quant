# Study #24 — Mitigation Dependence, Auction-Cost, and Selection Stress

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --json /tmp/gap-program.json`<br>
**Data:** live-shaped TQQQ path, 2024-08-01–2026-07-22<br>
**RESEARCH_WEB nodes:** E48 (study) · F58 (finding) · tests [[F52]]/[[F55]]/[[F57]]<br>
**Status:** dependence- and cost-stressed counterfactual; no policy is approved.

## Question

The candidate flatten policies improve one observed path before incremental auction cost. Do
their relative-wealth effects survive clustered resampling, calendar slices, and explicit extra
cost—or are they single-event artifacts?

## Method

Three mechanism-distinct candidates are compared with the −10.15% gap-aware baseline:

1. flatten every close;
2. flatten only before weekends/long closures;
3. flatten when lagged 20-session QQQ volatility is at least 15%.

Trade wealth effects are aligned to exit sessions. Circular block bootstraps resample paired daily
log-return differences at 5-, 20-, and 60-session blocks, preserving local dependence. The output
is a **relative-wealth effect**, not a maxDD confidence interval.

Additional costs of 0–80 bp are charged once per flatten exit at the instrument-return level,
before 10% position scaling. Existing modeled slippage and the policy's changed number of trades
remain in the path.

## Dependence stress

| policy | flatten exits | observed total delta | block-5 relative-wealth 95% | block-20 | block-60 |
|---|---:|---:|---:|---:|---:|
| daily flatten | 126 | +4.37 pp | +1.75% to +8.56% | **+1.82% to +8.58%** | +1.94% to +8.67% |
| weekend/long closure | 29 | +1.54 pp | −0.47% to +4.60% | **−0.50% to +4.70%** | −0.61% to +4.55% |
| lagged QQQ vol ≥15% | 66 | +4.05 pp | +2.16% to +7.61% | **+1.99% to +7.83%** | +1.96% to +7.86% |

The daily and volatility policies remain positive under these same-path block resamples.
Weekend-only flatten does not: every band includes zero. A block bootstrap cannot create unseen
crises or turn this into independent OOS evidence.

## Calendar slices

Relative-wealth effects versus hold-overnight:

| policy | 2024 partial | 2025 | 2026 partial |
|---|---:|---:|---:|
| daily flatten | +0.63% | +3.03% | +1.14% |
| weekend/long closure | **−0.18%** | +1.50% | +0.40% |
| lagged QQQ vol ≥15% | +0.35% | +3.04% | +1.07% |

The daily/volatility directions appear in every slice, but these are dependent partitions of the
same selected two-year history. Weekend flatten already reverses in 2024.

## Extra-cost frontier

Total-return delta versus baseline:

| extra cost per flatten exit | daily | weekend/long | lagged vol ≥15% |
|---:|---:|---:|---:|
| 0 bp | +4.37 pp | +1.54 pp | +4.05 pp |
| 10 bp | +3.19 pp | +1.28 pp | +3.43 pp |
| 20 bp | +2.03 pp | +1.01 pp | +2.82 pp |
| 40 bp | **−0.26 pp** | +0.49 pp | +1.60 pp |
| 60 bp | −2.49 pp | **−0.04 pp** | +0.40 pp |
| 80 bp | −4.66 pp | −0.56 pp | **−0.78 pp** |

The first-order break-even budgets are about 34.7 bp for daily flatten, 53.2 bp for
weekend/long-closure flatten, and 61.3 bp for the 15%-volatility rule. These are budgets, not
expected auction costs.

## Primary-source execution boundary

An official close is not a guaranteed fill assumption:

- IBKR defines MOC as an attempt to execute at or near the close and warns that auction
  imbalances can move the price
  ([IBKR](https://www.interactivebrokers.com/campus/glossary-terms/market-on-close-order/)).
- Nasdaq publishes imbalance information before its 4:00 p.m. Closing Cross
  ([Nasdaq](https://www.nasdaqtrader.com/trader.aspx?id=openclose)).
- NYSE's official auction guide sets a 3:50 p.m. MOC/LOC cutoff and restricts changes afterward
  ([NYSE](https://www.nyse.com/publicdocs/nyse/markets/nyse/NYSE_Opening_and_Closing_Auctions_Fact_Sheet.pdf)).

The repository's final 15:32 cycle is early enough in principle, but implementation would still
need bracket cancellation, quantity reconciliation, rejection/partial-fill handling, and actual
auction-fill capture. This study does not modify that path.

## Finding

The policies separate cleanly:

- **Daily flatten:** strongest mechanism, but its modest 34.7 bp budget makes it most
  cost-sensitive.
- **Weekend flatten:** lowest turnover, but its benefit is statistically fragile and
  reverses in one calendar slice.
- **Lagged-volatility flatten:** best observed turnover/cost compromise—roughly daily flatten's
  risk benefit with half the exits—but it is a threshold selected on this same path and disables
  most recent overnight exposure.

The lagged-volatility policy is the only partial control worth a future forward trial. The
appropriate next test is paper-only shadow accounting of real closing-auction fills and
would-have-held overnight outcomes, with the 15% threshold frozen in advance. Until then, none is
production-ready and every active path remains negative.

## Caveats

- The bootstrap resamples one two-year path; it is not independent replication.
- MaxDD uncertainty is not inferred from daily relative-return blocks.
- Extra cost is applied once per flatten exit; implementation may add other legs and operational
  failures.
- Official closes are historical proxies, not executable quotes.
- The 15% policy is selected from the threshold frontier, so its favorable interval is
  post-selection.
