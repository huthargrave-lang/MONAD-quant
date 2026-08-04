# BOND-NEOCLOUD-01: Treasury auction demand versus neocloud performance

**Research nodes:** `E248101`, `F248103`, `F248104`, `H248101`, `D248101`  
**Audit date:** 2026-08-03  
**Status:** useful macro-feature lead; no tradable neocloud signal

## Executive result

Treasury coupon auctions are a credible scheduled macro input for AI-infrastructure
research, but this first public-data study does **not** justify trading neoclouds from
auction results.

The study joined 103 single-auction, 1:00 p.m. ET nominal coupon events from
2025-04-08 through 2026-07-28 to hourly prices for:

- core neoclouds: CoreWeave (`CRWV`) and Nebius (`NBIS`);
- adjacent AI infrastructure: Applied Digital (`APLD`) and IREN (`IREN`);
- equity controls: `QQQ` and `SOXX`; and
- rate controls: `TLT` and `IEF`.

The official auction fields form a deliberately modest
`historical_relative_demand_score`: the mean of trailing-tenor robust z-scores for
bid-to-cover, indirect-bidder accepted share, and the inverse of primary-dealer
accepted share. It is computed from the prior 12 auctions of the same original tenor.
It is **not** the auction tail and it does not measure the surprise relative to market
expectations.

In the 12:30-to-13:30 ET straddling window, stronger demand was associated with:

| Outcome | N | Pearson r | Spearman rho | High-minus-low demand tercile |
|---|---:|---:|---:|---:|
| TLT return | 103 | 0.467 | 0.509 | +29.6 bp |
| CRWV/NBIS abnormal return | 103 | 0.224 | 0.103 | +37.8 bp |
| APLD/IREN abnormal return | 103 | 0.292 | 0.260 | +80.5 bp |

The bond result validates that the historical-demand score contains rate-relevant
information. The equity result does not survive the stronger stability checks:

| Half | Dates | Demand vs core r | Demand vs adjacent r | Demand vs TLT r |
|---|---|---:|---:|---:|
| Early | 2025-04-08–2025-11-19 | 0.289 | 0.439 | 0.534 |
| Late | 2025-11-24–2026-07-28 | 0.121 | 0.105 | 0.436 |

The TLT relationship persists; both equity relationships fade. A recent 13-event
5-minute timing pilot tells the same cautious story: demand versus TLT remained
directionally positive (`r=0.514`), while demand versus the core and adjacent equity
cohorts was only `0.189` and `0.037`. That pilot is far too small for inference, but it
does not rescue the equity claim.

There is also no clean continuation. Demand-score correlations with abnormal equity
returns after 13:30, over the full auction day, and through the next close are weak or
unstable. The apparent edge is concentrated in the coarse hour that includes 30
minutes before auction close, exactly where anticipation and dealer positioning can
contaminate a result-response story.

**Decision:** keep auction demand as a macro state feature and build a financing-
sensitivity panel. Do not promote an auction-to-neocloud strategy until a true
when-issued tail and sub-minute equity response are available and the effect survives
forward time splits.

The aggregate artifact, source hashes, exact factor contract, sensitivity tables, and
kill criteria are in
[`bond_auction_neocloud_2026.json`](data/bond_auction_neocloud_2026.json).

## Why the mechanism is plausible

The Treasury's [auction dataset](https://fiscaldata.treasury.gov/datasets/treasury-securities-auctions-data/)
publishes security terms, close times, stop yields, bid-to-cover, and bidder awards.
TreasuryDirect documents the regular note and bond
[auction schedule](https://www.treasurydirect.gov/auctions/general-auction-timing/),
and competitive coupon auctions normally close at 1:00 p.m. ET. Results are released
within minutes of the close. The New York Fed's 2026 study of 33 years of intraday
Treasury data finds yields rising before auctions and reversing afterward, with the
pattern related to dealer constraints and investor demand
([Fleming, Liu, and Nguyen](https://www.newyorkfed.org/research/staff_reports/sr1188.html)).

AI infrastructure is a reasonable place to look for equity spillovers because its
public issuers repeatedly describe large, externally financed buildouts:

- CoreWeave says it expects significant continuing investment and that future needs
  may require substantial debt or equity financing; its 2025 filing also describes
  substantial indebtedness
  ([2025 Form 10-K](https://www.sec.gov/Archives/edgar/data/1769628/000176962826000104/crwv-20251231.htm)).
- Nebius reports purchases of property, equipment, and intangibles rising from $807.5
  million in 2024 to $4.066 billion in 2025, primarily GPUs and data-center hardware
  ([2025 Form 20-F](https://www.sec.gov/Archives/edgar/data/1513845/000110465926052948/nbis-20251231x20f.htm)).
- IREN describes repurposing mining sites for AI services and disclosed multibillion-
  dollar GPU purchase commitments
  ([March 2026 Form 10-Q](https://www.sec.gov/Archives/edgar/data/1878848/000187884826000026/iren-20260331.htm)).
- Applied Digital is better classified as adjacent infrastructure than a pure
  neocloud: it designs, builds, and operates data centers, while its cloud-services
  business was classified as held for sale. Its February 2026 filing reports $2.276
  billion of long-term debt in a project subsidiary and a $2.35 billion note financing
  for data-center construction
  ([February 2026 Form 10-Q](https://www.sec.gov/Archives/edgar/data/1144879/000114487926000030/apld-20260228.htm)).

Those facts support a cost-of-capital hypothesis. They do not imply that every auction
changes each issuer's financing cost or valuation mechanically. Most obligations are
fixed, project-specific, hedged, prepaid by customers, or repriced on different clocks.

## Study contract

### Exposure

The source population is the official FiscalData Treasury Securities Auctions API
from 2022 onward. Only nominal 2-, 3-, 5-, 7-, 10-, 20-, and 30-year coupons are used.
TIPS, bills, FRNs, non-1:00 p.m. closes, and dates with multiple 1:00 p.m. coupon
records are excluded.

Reopenings require special care. Treasury's `security_term` becomes the remaining
maturity (`9-Year 11-Month`, for example), while `original_security_term` retains the
stable tenor. The latter governs the rolling baseline. Using the remaining-maturity
label silently omits most reopenings and materially understates the sample.

For each tenor, the score uses only prior auctions:

```text
demand_score = mean(
  robust_z(bid_to_cover),
  robust_z(indirect_accepted / total_accepted),
 -robust_z(primary_dealer_accepted / total_accepted)
)
```

Each robust z-score uses the prior 12 same-tenor observations, requires at least eight,
uses median/MAD scaling, and is clipped to `[-3, 3]`. The three components point in the
same broad direction in the full sample, but none is a consensus-adjusted surprise.

### Outcomes

The core and adjacent baskets are equal-weighted separately. Abnormal return subtracts
an equal-weighted `QQQ`/`SOXX` benchmark. `TLT` is the long-duration rate-reaction
proxy.

Yahoo's historical 60-minute bars begin at 30 minutes past the hour. Therefore the
primary window is the 12:30 open to the 13:30 open. It contains 30 minutes before and
30 minutes after the auction close. Calling it a post-result return would be false.
The 13:30-to-14:30 window is a cleaner delayed response but misses the immediate move.

The recent timing pilot uses 5-minute bars from 12:55 to 13:10. It contains only 13
events and is a clock check, not a confirmation sample.

Raw quote payloads are not committed because redistribution rights were not verified.
The artifact retains retrieval times and SHA-256 hashes for each source response and
commits only aggregate statistics. Official Treasury data and the quote-derived
aggregates have separate provenance and rights labels.

## What survived and what failed

### Survived: the auction score carries bond-market information

Demand versus TLT remains positive in both temporal halves and is strongest for the
long-tenor bucket. Removing any one original tenor leaves the full-sample relationship
positive. The 5-minute pilot is also directionally consistent. This makes the score a
reasonable free-data proxy for an auction-demand state.

It is still not a substitute for the standard when-issued tail. A market can anticipate
a high bid-to-cover or strong indirect share, and the historical baseline does not know
that expectation.

### Failed: a stable unconditional neocloud response

The full-sample equity correlations are attractive but live almost entirely in the
early half. They disappear in the later half even as the score-to-TLT link persists.
The delayed hour and next-close horizons do not show robust continuation. The recent
5-minute window does not confirm an immediate equity relationship.

Ticker-level results also weaken the idea that a single clean neocloud factor was
found. Full-sample demand correlations range from `0.124` for CRWV to `0.324` for IREN;
NBIS is `0.257` and APLD is `0.207`. That ordering may reflect leverage, volatility,
business mix, crypto exposure, or the 2025 AI-risk regime—not neocloud purity.

The stronger next hypothesis is conditional:

> auction-driven rate shocks affect AI-infrastructure equities in regimes where the
> market is actively pricing their financing gap, and the loading scales with a
> point-in-time capital-structure exposure rather than a static sector label.

## The research node this should spawn

`H248101` should become a two-layer model, not another mean-reversion strategy.

### 1. True auction shock layer

Acquire licensed or otherwise redistributable point-in-time data for:

- 12:59:xx when-issued yield and the official stop yield;
- exact result-release timestamp;
- Treasury futures and on-the-run yields from 30 minutes before to 60 minutes after;
- auction size surprise relative to the refunding announcement; and
- expected bidder statistics if a genuinely timestamped consensus exists.

The primary shock should be stop yield minus pre-result when-issued yield, with sign
normalized so positive means stronger demand. Bidder shares remain explanatory
features, not the definition of surprise.

### 2. Financing-exposure layer

Build a point-in-time quarterly panel from SEC filings:

- net debt / enterprise value and debt / contracted revenue;
- floating-rate share, spread over SOFR, hedges, and the next 24 months of maturities;
- committed capex / liquidity and capex / revenue;
- customer prepayments and project-finance coverage;
- GPU lease versus ownership mix;
- power and data-center commitments not yet revenue-producing; and
- equity issuance capacity and dilution already observed by the event timestamp.

The test is a cross-sectional interaction:

```text
abnormal_return ~ auction_tail
                + financing_exposure
                + auction_tail * financing_exposure
                + market/rate/volatility controls
```

Walk forward by auction date, freeze every filing feature at SEC acceptance time, and
keep all observations for one issuer in the same validation group. Compare against a
simple `TLT`-return model; the filing layer has no value if it cannot improve calibration
or rank ordering beyond the realized rate move.

### 3. Regime layer

Pre-register only a few state variables: real-yield level, credit-spread regime,
issuer implied volatility, recent AI-infrastructure drawdown, and upcoming financing
need. The temporal decay in this pilot makes unconstrained interaction mining especially
dangerous.

## Kill criteria

- Kill the equity strategy if a true tail does not predict the sign of the immediate
  Treasury reaction out of sample.
- Kill the static neocloud basket if its auction loading remains unstable across time.
- Kill the filing interaction if it cannot beat `TLT` alone in issuer-grouped,
  forward-chained validation.
- Kill any event whose exact auction-result and quote clocks cannot be reconstructed.
- Do not infer causality from hourly bars or unadjusted permutation p-values.
- Do not use this node for live orders, sizing, or parameter changes.

## Public-resource path

Even before it becomes predictive, this can support a useful free dashboard: upcoming
coupon auctions, official results, trailing-tenor demand percentiles, rate reactions,
and issuer financing-exposure cards with direct filing citations. The public interface
should show a bright distinction between official auction facts, calculated historical
baselines, market reactions, and model estimates. Community suggestions can propose
issuer mappings or exposure fields, but they must enter a review queue rather than
rewrite the observation ledger.

