# OPPORTUNISTIC-ATM-01: financing occurrence before instrument choice

**Date:** 2026-08-04

**Status:** three-case selected, reviewed, point-in-time pilot; not a population,
fitted model, financing-motive label, or investment edge

**Tool:** `tools/atm_424b5_lab.py --build-opportunistic-atm`

**Seed:** `data/opportunistic_atm_01_gold_seed.json`

**Frozen artifact:** `data/opportunistic_atm_01_gold_pilot.json`

## Decision

Advance the research, but split it into two estimands:

1. the hazard of **any financing** in the next 90/180 days; and
2. conditional on financing, the choice among ATM, underwritten offering, PIPE,
   debt, royalty/partnership cash, or another instrument.

Do not create an observed `opportunistic` label from runway. Financing motive is
latent until a later, separately reviewed disclosure-language exercise. Model need
and opportunity as feature blocks, explain their contributions, and predict the
observable event, instrument, size, and terms.

The pilot supports one important architectural change: market opportunity must be a
daily or event-refreshed state. A financial filing can supply the slow balance-sheet
state, but it cannot freeze the opportunity features for the entire forward horizon.
Scholar Rock moved from a low opportunity state at its August filing to a radically
different state after positive Phase 3 data on October 7, before launching an
underwritten offering that evening.

## What the selected cases say

The transparent pilot rule calls opportunity `high` only when both 63-session
XBI-relative return is at least +20% and price is at least 95% of its 63-session
high. The thresholds were chosen to make the mechanism inspectable; they were not
fit, optimized, or validated.

| Cutoff / latest eligible state | Need state | 63-session XBI excess | Price / 63-session high | Forward observation | Instrument |
|---|---|---:|---:|---|---|
| RYTM, 2024-11-06 | low near-term | +20.17% | 100.00% | ~$73.3M net disclosed through Jan. 21; sales began within 90 days | ATM |
| VKTX, 2024-10-24 | low near-term | -2.38% | 85.70% | exact zero ATM shares through quarter-end (68 days) | none |
| SRRK, refreshed 2024-10-07 | elevated | +332.93% | 100.00% | ~$324.4M net financing launched the same evening | underwritten |

Both selected high-opportunity cases financed; the selected low-opportunity case
did not. But the two financing cases chose different instruments. This is useful
mechanism evidence, not a hit rate: the sample is hand-selected, contains only three
issuers, has no high-need/low-opportunity case, and the VKTX zero is observed for 68
days rather than the population target of 90.

The RYTM amount is also interval-censored: the source discloses sales through January
21, before the February 4 horizon end. It establishes the financing occurrence and a
minimum observed amount, not complete proceeds for every day in the 90-day window.

The SRRK scale comparison points toward an instrument-choice feature. Its reviewed
offering represented about 11.82% of the post-catalyst market capitalization and
roughly 43 median trailing dollar-volume days. Its ATM had $100 million of original
gross capacity, but exact remaining capacity cannot be computed by subtracting the
disclosed $5.2 million of **net** proceeds from that gross authorization. A large,
rapid raise after a binary catalyst may favor an underwritten book even while an ATM
remains active.

## Why the state must refresh

At the August 7 close, before Scholar Rock's Q2 filing became tradable, SRRK had
underperformed XBI by 46.10% over 63 sessions and traded at 56.70% of its 63-session
high. On October 7 the company disclosed positive Phase 3 SAPPHIRE topline results in
an 8-K accepted at 08:00:33 ET. At that day's close, before the preliminary offering
prospectus was accepted at 16:55:16 ET, SRRK had outperformed XBI by 332.93% over 63
sessions and sat at the window high.

A quarterly-only model would feed the August opportunity state into the October
financing decision and get the economic mechanism backward. The implementation
contract should therefore be:

```text
slow state:  latest eligible 10-Q/10-K cash, burn, debt, runway, shelf and ATM state
fast state:  recomputed each session and immediately after a material public event
event clock: exact SEC acceptance -> conservative tradable time
prediction:  financing hazard first -> instrument and terms conditional on financing
```

The catalyst itself may be used only after its exact public clock. The pilot market
snapshot uses the October 7 close at 16:05 and precedes the 16:55 preliminary
prospectus. The later final terms and 10-K confirmation remain label-only.

## Point-in-time evidence

All filing facts come from official SEC documents with response hashes and exact
acceptance/tradability clocks. Raw responses and Yahoo chart payloads are not
committed; their URLs, retrieval timestamps, rights tier, and SHA-256 hashes are.

- Rhythm's [2024Q3 10-Q](https://www.sec.gov/Archives/edgar/data/1649904/000155837024014532/rytm-20240930x10q.htm)
  reported $298.4 million of cash plus short-term investments, $95.0 million of
  operating cash used over 274 days, funding into 2026, and a $200 million ATM.
  Its [2024 10-K](https://www.sec.gov/Archives/edgar/data/1649904/000155837025001889/rytm-20241231x10k.htm)
  disclosed about $41.2 million of net ATM proceeds through year-end and another
  $32.1 million through January 21.
- Viking's [2024Q3 10-Q](https://www.sec.gov/Archives/edgar/data/1607678/000095017024116708/vktx-20240930.htm)
  reported $930.4 million of cash plus investments and $151.9 million of remaining
  ATM capacity. Its [2024 10-K](https://www.sec.gov/Archives/edgar/data/1607678/000095017025027824/vktx-20241231.htm)
  kept both cumulative ATM shares and remaining capacity unchanged at December 31,
  supporting an exact Q4 zero without differencing rounded proceeds.
- Scholar Rock's [2024Q2 10-Q](https://www.sec.gov/Archives/edgar/data/1727196/000155837024011461/srrk-20240630x10q.htm)
  reported $190.5 million of liquid assets, $99.0 million of operating cash used over
  182 days, an active $100 million ATM, and the expected Q4 SAPPHIRE readout. The
  [catalyst 8-K](https://www.sec.gov/Archives/edgar/data/1727196/000110465924106461/tm2425688d7_8k.htm)
  and same-day [preliminary prospectus](https://www.sec.gov/Archives/edgar/data/1727196/000110465924106713/tm2425688-11_424b5.htm)
  establish the event order. The [final prospectus](https://www.sec.gov/Archives/edgar/data/1727196/000110465924107346/tm2425688-13_424b5.htm)
  supplies the terms, while the [2024 10-K](https://www.sec.gov/Archives/edgar/data/1727196/000155837025001682/srrk-20241231x10k.htm)
  confirms no ATM sales during 2024.

The SEC's official [EDGAR API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
and [data-access guidance](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
define the scalable retrieval surface and fair-access posture. Production collection
should use submissions metadata for exact acceptance times and archive immutable raw
responses outside Git.

## Labels and leakage guard

The observable population targets should be:

```text
any_financing_next_90d, any_financing_next_180d
instrument_if_financed
net_proceeds / pre-event market_cap
net_proceeds / trailing_dollar_volume
offer_price / pre-launch_VWAP
common-equivalent dilution
warrant coverage and tenor
```

Every no-financing label needs a compatible start/end reconciliation for the same
program and measurement basis. The VKTX pilot uses identical cumulative share counts
and identical remaining capacity at Q3 and year-end. It is explicitly right-censored
at 68 days. Rounded net proceeds alone cannot establish a zero.

All outcomes store `predictive_features_allowed=false`. No future return labels were
inspected, no model was trained, and no population inference is allowed. Market
features were inspected because they are the mechanism being tested; future financing
documents were used only to form labels.

## Population design

Build an issuer-session panel only while an ATM or shelf is active, plus matched
issuer-sessions without active capacity. Keep zero-sale intervals. A practical model
stack is:

```text
head 1: discrete-time hazard of any financing in 90/180 days
head 2: competing instrument choice, conditional on financing
head 3: size and shareholder terms, conditional on instrument
```

Need features include liquid runway, burn acceleration, debt maturities, planned
trial count, milestone coverage, and disclosed going-concern language. Opportunity
features include XBI-relative momentum, distance from highs, market-cap percentile,
dollar volume, volatility, post-catalyst persistence, active shelf/ATM capacity, and
days since prior sale. Issuer propensity includes prior rally-following issuance,
historical ATM utilization, underwriter continuity, and management dilution history.

Split by issuer and time. Fit all transforms inside the training fold. Compare against
issuer base rate, runway-only, opportunity-only, and active-capacity-only baselines.
Evaluate calibration and proper scoring rules for occurrence; multinomial log loss
and confusion matrices for instrument; and MAE/quantile loss for size and terms.

## Child nodes

1. **OPPORTUNISTIC-ATM-02 — active-capacity panel.** Build 50+ issuers with daily
   eligible states and exact 90/180-day financing and zero labels.
2. **FINANCING-INSTRUMENT-01 — execution feasibility.** Test desired raise size /
   remaining ATM capacity, market cap, and trailing dollar volume as drivers of ATM
   versus underwritten choice.
3. **CATALYST-REFRESH-01 — state transitions.** Measure whether catalyst-day refreshes
   improve financing-hazard calibration over filing-frozen opportunity features.
4. **ATM-PROPENSITY-01 — issuer behavior.** Estimate issuer-specific rally-following
   utilization with shrinkage rather than one-hot memorization.
5. **FINANCING-TERMS-01 — shareholder outcome.** Predict discount, common-equivalent
   dilution, warrants, and execution speed after the occurrence head fires.
6. **FINANCING-MOTIVE-01 — reviewed rhetoric.** Create separately adjudicated motive
   labels from filing and management language, never from runway arithmetic alone.

The immediate population gate is OPPORTUNISTIC-ATM-02. The most interesting model
lead is FINANCING-INSTRUMENT-01: opportunity appears to open the financing window,
while raise size relative to executable ATM capacity may determine how management
walks through it.
