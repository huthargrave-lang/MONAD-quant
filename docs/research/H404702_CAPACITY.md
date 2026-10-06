# H404702 capacity: how much capital the CEF rule can run

`tools/cef_capacity.py` replays H404702's registered orders. It uses the same
`cef_classes.decide` the gate uses, computes no returns and records no trial. It sizes
each tranche's trades at a portfolio value and compares them with each fund's 20-session
median dollar volume (Yahoo share volume × raw close). The window is 2016-01-01 to
2026-10-02, covering 319 funds ever traded.

| Portfolio | Median trade participation | p90 | Trades above 10% of ADV | Above 20% | Days to exit the largest holding at 10% of ADV (median) |
|---|---|---|---|---|---|
| $1M | 0.01% | 0.13% | 0.04% | 0.01% | 4 |
| $5M | 0.03% | 0.64% | 0.32% | 0.15% | 20 |
| $10M | 0.06% | 1.28% | 0.68% | 0.32% | 41 |
| $25M | 0.16% | 3.20% | 2.06% | 0.85% | 102 |
| $50M | 0.32% | 6.39% | 5.95% | 2.06% | 203 |
| $100M | 0.64% | 12.78% | 12.62% | 5.95% | 407 |

The median fund trades $1.25M a day. In the latest portfolio, 40.7% of the weight sits in
funds trading under $1M a day.

## What it says

- **Routine trading is gentle to about $25M.** The 21 monthly tranches split every
  rebalance into small pieces. At $25M, 9 in 10 trades are at most 3.2% of a day's volume.
  Above $50M, 1 trade in 6-8 exceeds 10% of a day's volume, and the backtest's flat cost
  tier stops being credible.
- **Exit liquidity binds first.** The rule concentrates in the thinnest funds, which is
  the mechanism: discounts persist where institutions cannot trade. At $10M the largest
  holding takes about 41 sessions to sell at 10% of volume, and at $25M about 100. A forced
  exit in a stress, the moment discounts widen, would cost far more than the modelled
  15 bps.
- **For the product question (D6),** this is a sleeve measured in single-digit to low
  tens of millions, not a fund-sized bond alternative. That fits a personal or small
  managed account, the repo's real use case.

## Limits

- The volume source is Yahoo, and pre-2016 volume is not used.
- Spreads are not measured. The backtest's 15/30 bps tier and the gate's 2× cost stress
  are the only cost evidence. Funds under $1M of ADV plausibly trade wider.
- Participation is measured against same-period median volume. Volume itself dries up in
  stress.
