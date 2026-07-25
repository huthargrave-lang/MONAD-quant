# Study #43 — Closing-Auction Benchmark Identity and Cost-Endpoint Correction

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --selfcheck --json /tmp/gap-program.json`<br>
**RESEARCH_WEB nodes:** E67 (study) · F78 (finding) · supersedes [[F69]]<br>
**Status:** primary-source endpoint correction; no order, live, strategy, or configuration change.

## Question

Can fill price minus Nasdaq Official Closing Price identify the execution cost of a TQQQ
market-on-close liquidation?

## Primary-source answer

Not for a standard qualifying Nasdaq Closing Cross.

- Nasdaq Equity 4 Rule 4702 says a Market On Close order executes only in the Nasdaq Closing Cross
  and at the Closing Cross price.
- Rule 4754 says all orders executed in the Cross receive one Cross price and, for a qualifying
  Cross in a Nasdaq-listed security, that price becomes the NOCP.
- The current Nasdaq FAQs describe the same single-price Cross, the 15:55 MOC acceptance cutoff,
  the 15:50 cancellation/modification restriction, and the fact that execution is not guaranteed.

Primary sources:

- [Nasdaq Equity 4 Rules 4702 and 4754](https://listingcenter.nasdaq.com/rulebook/nasdaq/rules/Nasdaq%20Equity%204)
- [Nasdaq Closing Cross FAQ](https://www.nasdaqtrader.com/content/productsservices/Trading/ClosingCrossfaq.pdf)
- [Nasdaq Opening/Closing Cross FAQs](https://www.nasdaqtrader.com/content/productsservices/trading/crosses/openclose_faqs.pdf)
- [IBKR MOC order rules](https://investors.interactivebrokers.com/en/trading/ordertypes.php)
- [IBKR paper-account limitations](https://www.interactivebrokers.com/campus/glossary-terms/paper-trading-account/)
- [IBKR exchange fees](https://investors.interactivebrokers.com/en/index.php?f=936)

For a successful standard MOC:

`fill VWAP = Closing Cross price = published NOCP`

The difference is therefore a reconciliation identity. Treating it as an implementation-shortfall
sample would manufacture the appearance of zero price cost by benchmarking the order against the
same price formation in which it participated.

## Important ETP exception

Rule 4754 gives Nasdaq-listed exchange-traded products a fallback when there is no Closing Cross
or the Cross executes less than one round lot. In that case, NOCP is the time-weighted average of
the NBBO midpoint from 15:58:00 through 15:59:55.

Every event record must therefore classify the NOCP method and retain Cross volume/round-lot
status. A time-weighted-midpoint fallback, halt, contingency, partial fill, rejection, or unfilled
order is not pooled with a standard qualifying Cross.

## What is observable

The directly observable incremental cost for a standard Cross is:

`(commissions + fees) / notional × 10,000 bp`

IBKR currently publishes a $0.0016/share Nasdaq MOC exchange fee. Its scale is:

| reference price | fee in bp | share of vol15 61.40 bp ceiling | share of daily 34.62 bp ceiling |
|---:|---:|---:|---:|
| $40 | 0.4000 | 0.651% | 1.155% |
| $60 | 0.2667 | 0.434% | 0.770% |
| $80 | 0.2000 | 0.326% | 0.578% |

The table is arithmetic, not a forecast. It excludes commissions, future fee changes, and market
impact.

## What is not identifiable

The submitted MOC order helps form the published Cross price and NOCP. Comparing its fill with
that published NOCP cannot recover the counterfactual price that would have formed without the
order. Self-impact is therefore unidentified by this design.

A future record should retain order shares, paired shares, imbalance, and indicative-price
changes. Those fields can diagnose capacity risk, but they do not by themselves establish causal
impact. A causal impact study would require separately authorized real orders and an independent
design; this research does not propose or authorize one.

## Corrected 60-event gate

Study #35 originally described 60 completed fills with zero price-cost breaches and a bootstrap
mean test. That endpoint is invalid because standard-Cross fill-minus-NOCP has no independent
variation. The corrected gate uses **60 intended events**:

- zero rejects or unfilled flattens;
- 100% required-field completeness;
- standard-Cross fills reconcile exactly to the Cross price;
- commissions plus fees remain below the applicable ceiling;
- all fallback, halt, contingency, partial, rejected, and unfilled events remain visible and
  separately classified;
- policy logic and threshold remain frozen.

Zero operational failures in 60 intended events gives a one-sided exact 95% upper failure-rate
bound of 4.87%. The expected horizon remains about 1.79 years for the observed vol15 exit rate and
0.94 years for daily flatten, but these are backtest-rate planning estimates.

## Decision

The old F69 cost claim is superseded by [[F78]]. Sixty intended events can test operational
reliability and observable charges; they cannot estimate fill slippage versus NOCP or self-impact.
IBKR paper accounts do not support Auction orders, so MONAD paper can validate only the decision
clock, schema, joins, and logging. No mitigation is approved, and no protected live/config path
was changed.
