# Study #35 — Closing-Auction Evidence Protocol (Corrected by Study #43)

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --selfcheck --json /tmp/gap-program.json`<br>
**RESEARCH_WEB nodes:** E59 (study) · F69 (superseded finding) · F78 (corrected finding)<br>
**Status:** corrected evidence specification only; MONAD remains paper-only.

## Decision question

What evidence can a future closing-auction record actually identify, and what would constitute an
operationally reliable MOC workflow?

Studies #24, #26, and #34 identify the cost boundary but cannot observe it. This protocol freezes
the fields, horizon, and rejection rules so a future dataset cannot be judged after seeing a
favorable result. Study #43 corrected this document's original endpoint: for a standard Nasdaq
Closing Cross, fill versus published NOCP is an exchange-price reconciliation, not an independent
slippage experiment.

## Current exchange and broker facts

- TQQQ is Nasdaq-listed and its official close is the Nasdaq Official Closing Price (NOCP)
  ([Nasdaq TQQQ historical NOCP](https://www.nasdaq.com/market-activity/etf/tqqq/historical-nocp)).
- A Nasdaq MOC executes only in the Closing Cross, and all orders executed in a qualifying Cross
  receive one Cross price; that price becomes the NOCP
  ([Nasdaq Equity 4 Rules 4702 and 4754](https://listingcenter.nasdaq.com/rulebook/nasdaq/rules/Nasdaq%20Equity%204)).
- For a Nasdaq-listed exchange-traded product with no Closing Cross or a Cross smaller than one
  round lot, Rule 4754 instead defines NOCP from the time-weighted NBBO midpoint observed from
  15:58:00 through 15:59:55. Those fallback events are not standard-Cross observations.
- Nasdaq accepts MOC orders until 3:55 p.m. ET, while cancellation/modification becomes
  restricted after 3:50 p.m.; the regular Closing Cross begins at 4:00 p.m.
  ([current Nasdaq Closing Cross FAQ](https://www.nasdaqtrader.com/content/productsservices/Trading/ClosingCrossfaq.pdf),
  [Nasdaq cross overview](https://www.nasdaqtrader.com/Trader.aspx?id=OpenClose)).
- NOII data expose paired shares, imbalance, and indicative/reference prices, but require a
  subscription through TotalView, DataStore, or a distributor
  ([Nasdaq cross overview](https://www.nasdaqtrader.com/Trader.aspx?id=OpenClose)).
- Nasdaq does not guarantee an MOC execution
  ([Nasdaq Opening/Closing Cross FAQ](https://www.nasdaqtrader.com/content/productsservices/trading/crosses/openclose_faqs.pdf)).
- IBKR documents `MOC`/`DAY` for stock orders and says Smart-routed MOC orders target the primary
  listing exchange ([IBKR API order types](https://www.interactivebrokers.com/campus/ibkr-api-page/order-types/),
  [IBKR order-type rules](https://investors.interactivebrokers.com/en/trading/ordertypes.php)).
- IBKR paper accounts do not support Auction orders, so paper fills cannot validate this endpoint
  ([IBKR paper limitations](https://www.interactivebrokers.com/campus/glossary-terms/paper-trading-account/)).
- The currently published IBKR Nasdaq MOC exchange fee is $0.0016/share; pricing can change and
  must be captured at execution time
  ([IBKR exchange fees](https://investors.interactivebrokers.com/en/index.php?f=936)).
- Nasdaq's 2026 calendar has 1:00 p.m. early closes; holiday alerts supply the adjusted cross
  schedule ([Nasdaq calendar](https://www.nasdaqtrader.com/trader.aspx?id=Calendar)).

These are operational facts as checked on 2026-07-24, not timeless constants.

## Required event record

Each planned flatten event must preserve:

1. a pseudonymous trial-event ID—**never a broker account ID**;
2. exchange session date and early-close flag;
3. frozen policy version and pre-close decision timestamp in ET;
4. direction, share quantity, and a pre-order position snapshot;
5. order type, TIF, route, submission timestamp, and broker acknowledgement;
6. every status transition, reject, cancel, and reason code;
7. fill timestamps, quantities, prices, commissions, and fees;
8. Nasdaq NOCP;
9. NOCP method: qualifying Cross, ETP time-weighted-midpoint fallback, halt, or contingency;
10. total Closing Cross shares and whether at least one round lot executed;
11. sourced 15:49:xx bid, ask, and sizes;
12. licensed NOII fields when available;
13. corporate-action, halt, and exceptional-session flags.

Unfilled or rejected events remain failures in the dataset. They may not be discarded as
“non-trades.”

## Corrected endpoint

For a standard qualifying Cross:

`observable incremental cost bp = (commission + fees) / notional × 10,000`

The fill VWAP must reconcile to the Cross/NOCP price. A nonzero fill-minus-NOCP difference is an
exception to investigate, not a normal random cost observation. Time-weighted-midpoint, halt,
contingency, partial, rejected, and unfilled events are reported in separate strata and never
silently pooled.

Published NOCP already incorporates the submitted MOC order. It therefore cannot reveal the
counterfactual NOCP that would have formed without that order. Order self-impact remains
unidentified unless a separate causal design is authorized; order shares, paired shares,
imbalance, and indicative-price changes are diagnostics, not proof of zero impact.

## Fixed operational gate

- exactly **60 intended auction events minimum** before testing;
- 100% required-field completeness;
- zero broker rejects/unfilled flattens;
- every standard-Cross fill reconciles to the Cross price;
- commissions plus fees remain below the relevant conservative 61.40 or 34.62 bp ceiling;
- fallback, halt, contingency, partial, rejected, and unfilled events are separately reported;
- no policy/threshold change before the horizon.

With zero rejects or unfilled flattens among 60 **intended** events, the exact one-sided 95% upper
bound on the operational-failure probability is 4.87%. This is why the denominator cannot be
“executed fills”: conditioning on fills would erase the failures the gate is meant to measure.

| policy | conservative ceiling | observed proxy exits/year | expected time to 60 |
|---|---:|---:|---:|
| vol20 ≥15% flatten | 61.40 bp | 33.48 | 1.79 years |
| daily flatten | 34.62 bp | 63.92 | 0.94 years |

The horizon estimates extrapolate the two-year backtest exit rate and are planning figures only.

At IBKR's currently published $0.0016/share Nasdaq MOC exchange fee, the fee itself is small
relative to either ceiling:

| reference price | exchange fee | share of 61.40 bp ceiling | share of 34.62 bp ceiling |
|---:|---:|---:|---:|
| $40 | 0.4000 bp | 0.651% | 1.155% |
| $60 | 0.2667 bp | 0.434% | 0.770% |
| $80 | 0.2000 bp | 0.326% | 0.578% |

This arithmetic does not include commissions, future fee changes, or self-impact.

## What can be done under MONAD's paper-only guardrail

The project may validate the frozen decision logic, timestamps, schema, NOCP joins, and rejection
handling without submitting an order. It cannot test Auction routing, rejection, or self-impact
with simulated paper fills. Actual auction evidence would need a separately authorized execution
study outside this repository's current scope or a suitable independent real-fill dataset.

No live/order/configuration code is changed, and this study is not authorization to place trades.

## Falsification

Reject the operational workflow if any intended flatten is rejected/unfilled, any required field
is absent, a standard-Cross fill fails price reconciliation, commissions plus fees exceed the
applicable ceiling, an exceptional NOCP event is pooled into the standard sample, or the fixed
policy changes before 60 intended events. Even a pass supports only operational reliability and
observable charges. It does not identify self-impact, validate the classifier, or approve
production; Study #26's longer forward gap-capture endpoint remains separate.
