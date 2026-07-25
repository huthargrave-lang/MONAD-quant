# IX-00 — Index Membership Event Lab

**Status:** source-contract audit, three complete batches, one partial survivorship diagnostic, and a revision-aware continuation<br>
**Decision:** proceed to a rights-cleared, point-in-time event ledger; reject a pooled directional rule<br>
**Reproduce:** `venv/bin/python tools/index_membership_event_pilot.py --batch <sp500-2026-03|ndx-2022-12|ndx-2024-12|ndx-2025-12>`<br>
**Derived artifacts:** [S&P 2026](data/ix00_sp500_march2026_event_pilot.json) · [Nasdaq 2025](data/ix00_ndx_december2025_event_replication.json) · [Nasdaq 2024](data/ix00_ndx_december2024_event_replication.json) · [Nasdaq 2022 partial](data/ix00_ndx_december2022_partial_diagnostic.json) · [complete Nasdaq panel](data/ix00_ndx_recent_complete_panel.json)<br>
**Continuation:** [IX-01 revision-aware ledger](IX01_nasdaq_2023_revision_ledger.md)<br>
**Research-web nodes:** `H50`, `E97`–`E101`, `F108`–`F112`, `H56`–`H61`, `D13`

## Executive result

Index addition and deletion research is worth continuing, but the useful object is
not the binary membership label.

The economically relevant treatment is the **signed net forced flow across every
affected index, divided by the security's available liquidity**, observed on a
three-clock event ledger:

1. when the announcement became public and tradable;
2. the close at which index trackers implemented the change; and
3. the open at which the new membership became effective.

A March 2026 S&P 500 pilot shows why this distinction is material. The four
additions rose 10.87% relative to SPY from the first tradable open through the
implementation close, while the four deletions fell 3.46%. Implementation-session
volume was 8.65× and 13.75× the prior 20-session median, respectively.

An exact-clock December 2025 Nasdaq-100 replication immediately breaks the
directional story. Its six additions lagged QQQ by 1.56% from the first tradable
open through implementation; its six deletions lagged by 0.64%. The exceptional
implementation-session volume did replicate—17.14× the prior median for additions
and 8.60× for deletions.

A complete December 2024 batch adds a second Nasdaq year. Pooling the two complete
Nasdaq batches produces only −0.38 percentage point of addition-minus-deletion
relative performance from first tradable open through implementation—no evidence of
pressure continuation. But additions underperform deletions by 2.23 points after
one session and 3.17 points after five. A 12-of-13 December 2022 diagnostic has the
same five-session sign, but is excluded because Yahoo no longer supplies Splunk's
delisted history.

These are **descriptive observations from 26 complete-batch event rows, plus a
partial 12-row diagnostic—not an index-effect estimate**. There are only two
complete Nasdaq annual batches, no credible counterfactual, and longer-horizon
outcomes are dominated by the selection process and company-specific moves. The
pilots validate the clock and coverage contract, reject a pooled directional claim,
and generate a narrow short-reversal hypothesis for proper historical testing.

The research prior is also hostile to a simple rule. Greenwood and Sammon report
that the S&P 500 addition effect fell from roughly 7.4% in the 1990s to less than
1% in the most recent decade they studied, and deletion effects were about 0.1%
from 2010–2020. The modern opportunity, if one exists, is therefore likely in
**heterogeneous flow pressure, anticipation, liquidity provision, and reversal**,
not “buy every addition.”

## What this node establishes

IX-00 establishes eight durable facts:

- “addition” and “deletion” mix direct entry/exit with migrations inside an index
  family;
- provider effective dates do not identify the implementation trade;
- provider announcements differ materially in clock precision and revision
  structure;
- ticker symbols are not durable security identifiers;
- the best microstructure outcomes and much historical membership data are
  licensed, so a free public product must separate open evidence from restricted
  inputs;
- the raw directional sign fails its first cross-provider replication while the
  implementation-volume spike survives;
- free current-symbol data silently lose acquired/delisted event members unless
  coverage is reconciled to the official list;
- both complete recent Nasdaq batches show additions underperforming deletions over
  one and five sessions after implementation, but two batches cannot establish a
  model.

It does **not** establish:

- abnormal performance caused by index membership;
- a profitable long-additions/short-deletions portfolio;
- the closing-auction imbalance or implementation shortfall;
- a complete historical constituent panel;
- a lawful right to redistribute provider constituent histories.

## Why the naïve study is wrong

A conventional event table contains:

```text
symbol | added_or_deleted | effective_date
```

That table silently introduces at least six errors.

### 1. It trades on the wrong clock

“Effective before the open Monday” usually means index trackers rebalance at the
preceding session's official close. Measuring only around Monday's open misses the
implementation auction and can mislabel the weekend return as the event.

### 2. It treats a migration as a gross new flow

When a company moves from the S&P MidCap 400 into the S&P 500, some passive demand
buys while other passive demand sells. Gross S&P 500 inclusion is not net family
flow. The same is true in reverse for a 500-to-600 migration.

### 3. It confuses a security with its ticker

EchoStar was announced under `SATS`, then changed its ticker to `ECHO` on
2026-06-24 without changing CUSIP. A current-symbol Yahoo query for `SATS` returned
no useful history, while `ECHO` returned the pre-change series. Historical event
rows need a time-bounded identifier map.

### 4. It mixes selection mechanisms

S&P selection is committee-discretionary. Nasdaq-100 and Russell membership are
substantially more rules-based. The information in “selected” is therefore not
comparable across families, and the appropriate counterfactual changes.

### 5. It overwrites preliminary knowledge with the final answer

Russell publishes a preliminary list and several updates before lockdown and
implementation. Replacing that sequence with the final membership table gives the
model information the market did not have on the first announcement date.

### 6. It mistakes accessible data for redistributable data

Public announcements may be readable while bulk constituent histories, index
weights, corporate-action files, and auction imbalances remain licensed. A free
research interface cannot simply mirror them.

## Primary-source reconnaissance

### S&P U.S. indices

The [March 2026 S&P rebalance announcement](https://www.spglobal.com/spdji/en/documents/indexnews/announcements/20260306-1482263/1482263_march2026rebalance1546.pdf)
named VRT, LITE, COHR, and SATS as S&P 500 additions effective before the
2026-03-23 open, with MTCH, MOH, LW, and PAYC deleted. The same tables show that
LITE, COHR, and SATS left the S&P MidCap 400, while all four S&P 500 deletions
entered the S&P SmallCap 600. VRT was the batch's only direct S&P 500 entry.

The [July 2026 S&P U.S. methodology](https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-us-indices.pdf)
states that the Index Committee chooses S&P 500/400/600 constituents using
eligibility and sector-balance considerations; migrations do not necessarily meet
every outside-addition criterion. Composite 1500 changes occur as needed rather
than through one scheduled annual reconstitution, and notice is normally at least
three business days but can be shorter.

That makes a selected S&P event partly an information event. A company may have
become larger, more liquid, more representative, or otherwise committee-eligible
before the announcement. A same-size non-event is not automatically a valid
control.

The [Ciena replacement announcement](https://press.spglobal.com/2026-02-04-Ciena-Set-to-Join-S-P-500-Arrowhead-Pharmaceuticals-to-Join-S-P-MidCap-400-ADT-and-OneSpaWorld-Holdings-to-Join-S-P-SmallCap-600)
shows another required distinction: a corporate-action vacancy can create a chain
of linked migrations on short notice. These events should not be pooled blindly
with scheduled batches.

S&P's [terms](https://www.spglobal.com/spdji/en/documents/legal/dow-jones-indexes-terms-conditions.pdf)
and [data-licensing page](https://www.spglobal.com/spdji/en/about-us/data-index-licensing/)
make constituent and corporate-action data a licensing question. IX-00 therefore
stores a transformed eight-security evidence card and source links, not a mirrored
constituent database.

### Nasdaq-100

Nasdaq's [2025 annual changes release](https://www.nasdaq.com/press-release/annual-changes-nasdaq-100-indexr-2025-12-13)
was published at 8:00 p.m. EST on Friday 2025-12-12 and made six additions and six
deletions effective before the 2025-12-22 open. An exact after-hours timestamp
supports an unambiguous next-session tradable clock.

Nasdaq's [reconstitution research](https://indexes.nasdaq.com/docs/202601%20NDX%20Reconstitution%20and%20Performance%20Highlights.pdf)
describes the index as systematically rule-based, with annual December
reconstitution and quarterly rebalancing. This branch can support threshold,
eligibility, and anticipation designs that would be inappropriate for S&P
committee selections.

### Russell U.S. indices

FTSE Russell's [2026 reconstitution release](https://www.lseg.com/en/media-centre/press-releases/ftse-russell/2026/ftse-russell-begins-june-2026-semi-annual-russell-us-indexes-reconstitution)
published preliminary membership on 2026-05-22, scheduled updates after the closes
of May 29, June 5, June 12, and June 18, and implemented the result after the
2026-06-26 close for membership from the June 29 open. It also marks a methodology
regime change from annual to semiannual reconstitution.

The [2026 FAQ](https://www.lseg.com/content/dam/ftse-russell/en_us/documents/policy-documents/ftse-faq-document-russell-us-equity-2026.pdf)
defines rank, cutoff, announcement, lockdown, and effective dates. A Russell event
ledger must retain every published revision, not only the final list.

Russell threshold assignments are appealing for causal work, but they are not
trivial to reconstruct. Research on an
[improved assignment method](https://www.nber.org/papers/w26370.pdf) notes that the
actual Russell rank market capitalization is not public and can differ from CRSP
because of combined share classes and nonpublic shares. A recent
[causal-design validation](https://www.sciencedirect.com/science/article/abs/pii/S0929119924001470)
also finds that a common instrumental-variable design can be invalid, while
difference-in-differences and sufficiently strong fuzzy regression-discontinuity
designs perform better.

### MSCI

MSCI's [May 2026 review announcement](https://app2.msci.com/webapp/index_ann/DocGet?format=html&lang=en&pub_key=y7TFqUuK86k%3D)
has an exact 2026-05-12 21:14 UTC publication time and distinguishes implementation
at the May 29 close from effectiveness on June 1. Its
[historical review page](https://www.msci.com/eqb/fm/index_review.html) provides
public review artifacts, but its [legal notice](https://www.msci.com/legal/notice-and-disclaimer)
restricts database population and AI-training uses. This family remains
researchable only after a rights review defines permissible ingestion, retention,
and publication.

### Auction and execution data

The [NYSE historical TAQ imbalance product](https://www.nyse.com/market-data/historical/taq-order-imbalances)
offers the most mechanism-aligned auction evidence but is a paid product. Daily
OHLCV can observe a whole-session volume spike; it cannot isolate the closing
auction, imbalance side, spread, auction-only volume, or a tracker's implementation
shortfall.

SEC [Rule 605 execution-quality reports](https://www.sec.gov/rules-regulations/staff-guidance/trading-markets-frequently-asked-questions/frequently-asked-questions-rule-605-regulation-nms)
are free and useful as monthly venue/security/order-category liquidity controls.
They do not identify event-specific closing-auction pressure and are not a
substitute for imbalance data.

## Canonical event schema

Every observation should be append-only and versioned:

```text
event_id
provider
index_family
index_name
provider_event_type
transition_type
security_id
event_symbol
source_url
source_document_hash
source_published_at
source_time_quality
first_tradable_at
preliminary_or_final
revision_of
implementation_session
implementation_benchmark
effective_session
old_memberships
new_memberships
concurrent_corporate_action
rights_tier
first_seen_at
ingested_at
parser_version
```

`source_published_at` is provider evidence. `first_seen_at` is the collector's
observation. They must never be silently substituted for one another.

### Required clock policy

- Exact timestamp during market hours: first tradable moment is that timestamp
  plus a frozen processing lag.
- Exact timestamp outside regular hours: first tradable moment is the next regular
  session open.
- Date only: use the next regular session open for the primary conservative test;
  report same-close measurement only as a non-tradable descriptive sensitivity.
- Implementation “after close”: anchor the implementation outcome to that session's
  official close.
- Effective “before open”: preserve the next session open separately.
- Holiday/weekend: resolve using a versioned exchange calendar.

### Required event taxonomy

At minimum:

- `direct_entry`
- `direct_exit`
- `family_up_migration`
- `family_down_migration`
- `corporate_action_replacement`
- `scheduled_reconstitution`
- `preliminary_revision`
- `IPO_or_fast_entry`
- `float_or_classification_change`
- `methodology_change`

One event can carry several tags, but the transition state must be mutually
reconcilable from old to new memberships.

## Cross-provider pilot design

The first pilot was frozen to the March 2026 S&P 500 batch:

- announcement source date: Friday 2026-03-06;
- conservative first tradable session: Monday 2026-03-09;
- implementation close: Friday 2026-03-20;
- effective open: Monday 2026-03-23;
- assets: four additions and four deletions;
- benchmark: SPY;
- price basis: split/dividend-adjusted open and close;
- implementation volume: session volume divided by the prior 20-session median;
- post-implementation horizons: 1, 5, 20, and 60 sessions.

The replication then froze Nasdaq's December 2025 annual reconstitution:

- exact announcement: Friday 2025-12-12 at 8:00 p.m. EST;
- first tradable session: Monday 2025-12-15;
- inferred implementation close: quadruple-witching Friday 2025-12-19;
- effective open: Monday 2025-12-22;
- assets: six additions and six deletions;
- benchmark: QQQ;
- identical price, volume, and horizon definitions.

The clean Nasdaq panel also includes the final December 2024 batch: three additions,
three deletions, exact Friday 8:00 p.m. publication, December 20 implementation
close, and December 23 effective open.

The December 2022 source lists six additions and seven deletions. The free provider
returns no historical rows for acquired Splunk, so the tool records 12/13 coverage,
keeps `SPLK` in an explicit exclusion ledger, changes the batch status to
`partial`, and bars it from pooled directional inference.

The December 2023 source is not represented as a clean batch. Nasdaq revised the
initial December 8 list on December 12 after the expected Seagen acquisition,
adding TTWO and removing SGEN while leaving the other events intact. That requires
security-specific first-known clocks and belongs in `IX-REVISION`.

The tool downloads data without committing raw vendor rows. It emits retrieval
metadata, yfinance version, an exact SHA-256 fingerprint of the sorted normalized
input slice, a decision-level result fingerprint, derived measurements, and
limitations. The first retained S&P input fingerprint is:

```text
9c88c32203332dc8f85111b99babdd5fca43ba5c94ed5f5fdce0557044c9c88e
```

The first retained Nasdaq input fingerprint is:

```text
6761aadceaf13677efd9fefba0c4f1e6154edb71904e14de5ced56acf070ee71
```

Repeated same-day refreshes revealed exact-input drift. Multiple observed hashes for
every batch differ even though displayed results are unchanged. The tool
therefore does not blur the source with arbitrary input rounding. It preserves each
exact snapshot hash and separately hashes exactly what the study displays: returns
as percentage points rounded to two decimals and volume multiples rounded to two:

| Batch | Paired decision-level hash | Consecutive repeats |
|---|---|---:|
| S&P March 2026 | `3530409a...22b7d6` | 2/2 identical |
| Nasdaq December 2025 | `b27565f0...765982` | 2/2 identical |
| Nasdaq December 2024 | `a3ef110b...ea62d3` | 2/2 identical |
| Nasdaq December 2022 partial | `834c66b3...255399` | 2/2 identical |

The raw data remain **vendor-backed and not clone-only reproducible**. The paired
audit establishes decision-level stability at declared precision, not immutable
Yahoo history. A production study needs retained rights-cleared raw snapshots or a
vendor revision protocol.

## S&P pilot results

All returns below are compounded relative returns versus SPY. There are no
standard errors or p-values because an eight-name convenience batch cannot support
credible inference.

| Group | n | Announce close → first open | First open → implementation close | Implementation close → effective open | Implementation volume / prior 20d median | Post 5d | Post 20d | Post 60d |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Additions | 4 | +3.33% | +10.87% | +0.44% | 8.65× | +1.90% | +16.59% | +8.50% |
| Deletions | 4 | +0.67% | −3.46% | −0.81% | 13.75× | −0.36% | +2.08% | +3.59% |
| Direct entry | 1 | +4.95% | +4.28% | — | 12.70× | — | +12.45% | +1.23% |
| Family up-migration | 3 | +2.79% | +13.07% | — | 7.30× | — | +17.97% | +10.93% |

The result validates three design choices:

1. announcement-to-implementation and implementation-to-effective are observably
   different windows;
2. the implementation session carries exceptional whole-day volume;
3. migration events cannot be assumed to have smaller price moves than direct
   entries—at least not before controlling for security-specific information.

The third point is a warning, not a discovered anomaly. LITE's relative move from
the first tradable open to implementation was over 25%, far too large to attribute
to index-fund demand without contemporaneous-news controls. The three
up-migrations outperformed the direct entry in this batch, contradicting a casual
“family netting means small reaction” story.

## Nasdaq replication results

| Group | n | Announce close → first open | First open → implementation close | Implementation close → effective open | Implementation volume / prior 20d median | Post 1d | Post 5d | Post 20d | Post 60d |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Additions | 6 | −0.06% | −1.56% | +1.30% | 17.14× | −1.46% | −2.05% | +7.76% | +20.32% |
| Deletions | 6 | −0.51% | −0.64% | −0.57% | 8.60× | −0.12% | −0.75% | +2.42% | −3.30% |

This replication changes the decision:

1. The S&P addition-versus-deletion direction does not generalize even to the next
   recent provider batch.
2. Exceptional implementation-session whole-day volume does generalize.
3. Additions underperformed for the first five post-implementation sessions, which
   is compatible with short reversal but cannot identify auction pressure.
4. Their later outperformance is not persuasive index evidence. Nasdaq explicitly
   reports that all six additions had risen at least 50% during 2025; WDC and STX
   continued to dominate the small group's 60-session mean.

The cross-provider evidence therefore supports `IX-AUCTION` and `IX-FLOW` as
mechanism studies while rejecting “recent additions go up into implementation” as a
general result.

## Complete recent Nasdaq panel

The complete panel contains December 2024 and 2025 only: two annual batches, nine
additions, and nine deletions. Values are security-weighted descriptive means.

| Group | n | Announcement gap | First open → implementation | Implementation volume | Post 1d | Post 5d | Post 20d | Post 60d |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Additions | 9 | +0.21% | −1.27% | 12.87× | −2.38% | −4.05% | +3.99% | +14.32% |
| Deletions | 9 | −1.86% | −0.89% | 7.26× | −0.15% | −0.88% | +2.03% | −1.93% |
| Add − delete | — | +2.07 pp | −0.38 pp | — | −2.23 pp | −3.17 pp | +1.96 pp | +16.25 pp |

This sharpens, but does not prove, the mechanism story:

- The next-open gap has the expected addition/deletion sign.
- That separation does not continue into the implementation close.
- Whole-day implementation volume is extreme, especially for additions.
- Additions reverse relative to deletions over one and five sessions in both
  complete batches.
- Longer-horizon results reverse again and are dominated by prior winners, making
  them poor evidence of temporary index pressure.

The correct next test is a batch-clustered historical panel with matched eligibility,
momentum, beta, volatility, and news controls. The current two-batch pattern is
`IX-REVERSAL`, a preregistered hypothesis—not a short-additions recommendation.

## 2022 survivorship diagnostic

The incomplete 2022 batch shows additions at −2.43% relative to QQQ over five
post-implementation sessions versus +0.36% for the six observable deletions. Its
implementation-volume ratios are 8.82× and 6.15×. The sign agrees with the complete
panel, but the official seventh deletion—SPLK—is absent from Yahoo after acquisition.

That missing row is not ignorable. It can change a seven-name deletion mean and is
correlated with the outcome pathway being studied: acquisitions and delistings are
not random data loss. IX-00 therefore uses 2022 only to demonstrate:

1. free current-symbol history is not a point-in-time security master;
2. official-list reconciliation must precede analysis;
3. attractive partial-batch results must remain quarantined.

## The treatment: net forced flow, not membership sign

For security \(i\) in event \(e\), the ideal signed exposure is:

\[
\text{flow pressure}_{i,e} =
\frac{\sum_k AUM_{k,e^-}\,\Delta w_{i,k,e}}
     {ADV^{\$}_{i,e^-}}
\]

where \(k\) covers every affected tracker/index family, \(AUM\) is point-in-time
indexed capital, \(\Delta w\) is the signed weight change, and dollar ADV is known
before the announcement.

The numerator should include:

- demand from the destination index;
- supply from the source index;
- linked changes in overlapping style, size, or country indexes;
- float/share-count changes;
- estimated benchmarked assets, explicitly separated from licensed provider AUM.

A public-data version may have to use coarser proxies:

- direct entry versus family migration;
- destination/source index market-cap bucket;
- pre-event market cap divided by dollar ADV;
- estimated tracker AUM from public fund filings;
- implementation-day volume shock;
- threshold distance for rule-based families.

These proxies must be labeled estimates, not disguised as exact passive flow.

## Historical panel design

### Stage A — source and rights validation

1. Freeze one provider family and methodology regime.
2. Obtain written clarity on permitted ingestion, derived storage, and public
   display.
3. Backfill announcements with raw document hashes and first-seen metadata.
4. Reconstruct every preliminary/final/revision link.
5. Build time-bounded security and share-class identity.
6. Reconcile old/new memberships and quarantine impossible transitions.

### Stage B — descriptive event study

Measure:

- announcement gap and close-to-close abnormal return;
- announcement-to-implementation pressure;
- implementation-close-to-effective-open return;
- 1/5/20/60-session post-implementation reversal;
- daily volume and volatility;
- comovement with destination and source indexes;
- dispersion by transition type and flow/liquidity proxy.

Use market, sector, size, momentum, liquidity, beta, and pre-event-return controls.
Cluster uncertainty by announcement batch and security because provider decisions
arrive in correlated sets.

### Stage C — matched counterfactuals

For discretionary S&P events, match within:

- eligibility region and market-cap neighborhood;
- sector;
- dollar ADV and free float;
- pre-event beta, momentum, volatility, and profitability;
- earnings/news distance;
- prior index-family membership.

For rule-based families, freeze the true eligibility and rank construction before
using a threshold design. If the assignment proxy has a weak first stage or cannot
reproduce published membership, reject the design.

### Stage D — mechanism test

Only a rights-cleared microstructure tier should test:

- closing-auction imbalance;
- auction volume and price impact;
- imbalance publication path;
- official-close implementation shortfall;
- reversal conditional on signed flow/ADV.

The mechanism passes only if larger ex-ante signed flow pressure predicts larger
implementation impact in the correct direction and a prespecified fraction of that
impact subsequently reverses. A volume spike alone is not sufficient.

## Confounder and exclusion ledger

Every event needs machine-readable flags for:

- earnings and guidance;
- merger, acquisition, spin-off, or bankruptcy;
- IPO/seasoning;
- analyst day or investor presentation;
- major product/regulatory decision;
- capital raise, buyback, or secondary offering;
- share-class/ticker/CUSIP change;
- sector or country classification change;
- dividend/split;
- provider methodology change;
- marketwide volatility shock.

The primary analysis should exclude or stratify the most severe concurrent events.
A sensitivity may retain them with controls, but it cannot call the residual an
index effect merely because a regression contains dummy variables.

## Published priors and what they imply

Greenwood and Sammon's
[The Disappearing Index Effect](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4294297)
finds substantial decay in S&P inclusion effects and similar weakening in other
families. The proposed mechanisms—family migration/netting, improved liquidity
provision, and anticipation—map directly to IX-00's child studies.

Chang, Hong, and Liskovich's
[Russell index study](https://www.nber.org/papers/w19290) uses the rank cutoff for a
more mechanical treatment and reports price effects for additions and deletions.
Later assignment and design critiques mean that this is a useful prior, not a
template to copy without validation.

The combined prior is:

- average event effects have probably decayed;
- cross-sectional flow pressure may still matter;
- the most crowded and predictable events may be pre-positioned;
- any remaining return may compensate liquidity providers rather than offer a
  simple directional strategy;
- identification quality matters more than adding another event-window chart.

## Preregistered falsification gates

The branch should be killed or narrowed if any of these occur:

1. Event timestamps cannot be reconstructed to a conservative tradable clock.
2. Revisions or family migrations cannot be recovered point in time.
3. Security identity mismatches exceed a frozen tolerance.
4. Rights do not permit the required analysis or public derived output.
5. Exact or proxy flow pressure has the wrong sign against implementation impact.
6. Apparent effects vanish after batch clustering and concurrent-event exclusions.
7. Results depend on one provider family, methodology era, or horizon.
8. A transparent market/sector/momentum/liquidity baseline performs equally well.
9. Threshold assignment cannot reproduce actual membership with a strong first
   stage.
10. Predictive results fail an untouched later-era test after all feature and
    horizon choices are frozen.

Multiple families, horizons, outcomes, transition types, and flow proxies form one
research family. Adjust inference family-wide and report every tried specification,
including negative ones.

## Model-factory children

### IX-FLOW — signed forced flow versus liquidity

Predict implementation-session impact and post-close reversal from signed net
flow/ADV. Compare exact licensed flow with public coarse proxies. This is the
highest-value causal/mechanism branch.

### IX-MIGRATE — direct entries versus family migrations

Test whether source-index selling offsets destination demand after matching on size,
liquidity, momentum, news, and provider family. The March pilot is explicitly
insufficient and points in the opposite raw direction.

### IX-REVISION — preliminary-list surprise

Treat each Russell preliminary, revision, lockdown, and final publication as a new
information event. Predict which preliminary names survive and measure the return
to revision surprise, not the ex-post final label.

### IX-SELECTION — discretionary information versus mechanical demand

Compare S&P committee-selected events with strongly rule-based Nasdaq/Russell
events. Test whether post-announcement continuation is stronger for discretionary
selections while implementation-close reversal is stronger for mechanical flow.

### IX-AUCTION — liquidity provision and reversal

With licensed imbalance data, model closing-auction impact from imbalance/ADV,
destination/source flow, volatility, and dealer capacity. Ask whether public
pre-close imbalance information supports a useful forecast after realistic
execution latency and cost.

### IX-ANTICIPATE — candidate probability and pre-positioning

Build a point-in-time eligibility model before provider announcements. Separate
expected membership probability from surprise, then test whether more-anticipated
events have smaller announcement responses and larger pre-announcement drift.

### IX-COMOVE — change in factor and peer comovement

Measure whether membership changes alter beta to the destination index, source
index, sector, and ETF-flow shocks. This can be economically useful even if
directional abnormal returns disappear.

### IX-PUBLIC — rights-safe event evidence cards

Expose source links, clocks, transition class, methods, derived aggregate results,
uncertainty, and falsification status in SQLite without republishing licensed
constituent history. Users may suggest hypotheses, but suggestions enter a review
queue rather than becoming findings.

## Public-product contract

The free public resource should publish:

- a human-readable event evidence card;
- provider/source URL and document hash;
- conservative tradable and implementation clocks;
- transition taxonomy;
- derived aggregate outcomes with uncertainty;
- clear rights tier and source limitations;
- model cards, attempted hypotheses, and negative results;
- a suggestion queue with provenance and moderation state.

It should not publish:

- copied historical constituent databases;
- provider weights or corporate-action feeds without rights;
- raw licensed auction imbalance;
- “predictions” without timestamped vintages and frozen evaluation;
- a ranking that hides failed specifications or transaction-cost assumptions.

SQLite is an appropriate local/public prototype for the evidence cards and
suggestion queue. The large raw analytical panels should remain separate,
content-addressed artifacts (Parquet/object storage) rather than SQLite blobs.

## Next implementation queue

1. Convert the event schema into a small SQLite migration shared with the Context
   Web rather than creating a second disconnected graph.
2. Add source-document hashing and exact timestamp-quality fields.
3. Recover SPLK from a rights-cleared historical source before admitting 2022 to
   the complete panel.
4. Represent the December 2023 Nasdaq update with security-specific revision clocks
   and preserve both preliminary and revised knowledge states.
5. Extend the clean annual sample and freeze `IX-REVERSAL` before inspecting pooled
   factor-adjusted outcomes.
6. Build security identity tests spanning ticker changes, share classes, mergers,
   and delistings.
7. Add batch-clustered event-study primitives with leave-one-event-out diagnostics.
8. Run a candidate-universe feasibility study before any Russell causal analysis.
9. Obtain rights guidance before retaining or exposing bulk provider history.
10. Keep IX-FLOW, IX-REVISION, IX-REVERSAL, and IX-SELECTION separate.

## Bottom line

The index-membership branch has a credible research program, not a discovered
strategy. Three complete batches show that event clock, family transition, and
security identity materially change the measurement, that raw directional effects
are unstable, and that implementation volume is the most repeatable observation.
Two complete Nasdaq years generate a short-horizon addition-reversal hypothesis;
the 2022 backfill also demonstrates why incomplete delisted history must not be
silently pooled. Existing literature says the easy average effect has decayed. The
promising next question remains:

> Conditional on what the market knew, how much signed passive flow had to cross
> at the implementation close relative to available liquidity—and how much of that
> pressure later reversed?

That question is falsifiable, economically grounded, and capable of spawning
useful public models even if the final directional alpha is zero.
