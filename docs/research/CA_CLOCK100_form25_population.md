# CA-CLOCK100 — SEC Form 25-NSE population backbone

**Status:** descriptive population infrastructure; no return join and no alpha claim<br>
**Frozen frame:** all 2023 Form 25-NSE accessions in the SEC quarterly master indexes<br>
**Content sample:** 100 filings, deterministic SHA-256 rank, 25 per quarter<br>
**Tool:** `tools/sec_form25_population_lab.py`<br>
**Transformed artifact:** `docs/research/data/ca_clock100_form25_2023.json`

## Question

Can the three hand-built CA-01 chains be scaled into a reproducible corporate-action
event population without confusing index rows, exchange filers, subject issuers,
filing dates, acceptance times, security types, or listing events with issuer
outcomes?

Yes for the population and exchange-event clock. Not yet for the outcome-balanced
issuer/exchange chains that would be needed for a predictive study.

The durable result is a free, official-data sampling backbone that future nodes can
join to issuer 8-Ks, merger terms, bankruptcy outcomes, inactive prices, and index
membership events. It is deliberately not a delisting-return backtest.

## Official source contract

The SEC documents quarterly `master` indexes as complete filing indexes containing
company name, form, CIK, filing date, and archive path. Static quarterly indexes can
later reflect post-acceptance corrections because the SEC rebuilds them weekly
([Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)).
This study therefore freezes both the transformed census hash and each downloaded
quarterly `master.gz` hash; “2023 index” is not treated as an eternally immutable
byte stream.

The content harvester uses the SEC submission header's second-resolution
`ACCEPTANCE-DATETIME` as `accepted_at`, interpreted in the SEC's stated Eastern
acceptance clock. The SEC says filing content is often available one to three
minutes after that timestamp, with no public first-availability timestamp. The
acceptance clock is consequently exact as a filing-system observation but is not an
exact website-availability clock
([SEC webmaster FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions)).

The collector declares a user agent, caches raw submissions outside the repository,
and spaces requests at 0.12 seconds. That is below the SEC's maximum ten requests
per second
([SEC Developer Resources](https://www.sec.gov/about/developer-resources)).
No raw master index, submission text, account data, or credential is committed.

Form 25-NSE is exchange-filed. The SEC's own validation documentation requires its
`filed by` CIK to be a national exchange
([EDGAR message reference](https://www.sec.gov/submit-filings/filer-support-resources/how-do-i-guides/understand-messages-reported-edgar)).
More importantly, Form 25 concerns removal of a security class from exchange listing
and/or Section 12(b) registration. It does not by itself terminate other reporting
obligations or determine holder consideration
([SEC Rule 12d2-2 release](https://www.sec.gov/rules-regulations/2004/06/removal-listing-registration-securities-pursuant-section-12d-securities-exchange-act-1934),
[Form 25](https://www.sec.gov/files/form25.pdf)).

## The population bug the study caught

A naive filter finds **2,282** 2023 master-index rows:

| Quarter | Raw 25-NSE rows | Unique accessions |
|---|---:|---:|
| 2023Q1 | 582 | 291 |
| 2023Q2 | 524 | 262 |
| 2023Q3 | 522 | 261 |
| 2023Q4 | 654 | 327 |
| **Total** | **2,282** | **1,141** |

The master index emits two identities for each accession: the national exchange
filer and the subject issuer. A row-count study would therefore double the event
population and could sometimes label the exchange itself as the delisted issuer.

The accession prefix is not a safe fix. For example, a NYSE American filing can use
an accession whose first ten digits correspond to a different NYSE-family CIK. The
parser instead resolves exactly one exchange-name row and one subject row, retains
both identities, and rejects any accession that does not satisfy the contract. It
then verifies the subject CIK again against the Form 25 XML. The 1,141-accession
census contains **920 unique subject issuers**; 103 issuers have multiple filings.
Repeated filings are often separate notes, ETF classes, rights, or other security
classes rather than duplicated common-equity events. Barclays Bank alone has 21.

This correction is more consequential than the initial descriptive statistics: it
defines the right unit of observation for every child study.

## Frozen sample

The committed artifact contains the complete 1,141-accession sampling manifest and
a 100-filing content sample. Within each quarter, accessions are ranked by
`SHA256("MONAD-CA-CLOCK100-v1|<accession>")`; the lowest 25 are selected without
replacement. Selection is independent of issuer name, event outcome, and later
price data.

Every enriched record retains:

- exchange and subject CIK/name, accession, filing date, quarter, and official URL;
- exact Eastern acceptance time plus UTC equivalent;
- pre-open, regular-session, or post-close bucket;
- security description and a conservative security-family heuristic;
- Rule 12d2-2 provision, signature date, and exchange identity;
- whether the EX-99.25 reason exhibit is informative, plus only its classification,
  length, and hash—not its raw text;
- source-content SHA-256 and explicit `raw_document_committed=false`.

The fixture validates its census and sample hashes on every read. A CIK mismatch,
missing primary document, missing exact acceptance clock, unexpected master-index
identity shape, duplicate accession, or transformed-data mutation fails closed.

## Descriptive findings

### 1. “Form 25” is not one economically coherent event

The sample contains:

| Security family | Filings |
|---|---:|
| Common equity | 31 |
| Debt or notes | 11 |
| Warrants, rights, units, or multi-class descriptions containing them | 40 |
| Preferred equity | 1 |
| Other or unknown | 17 |

Pooling these into a single “delisted stock” return label would be invalid. A matured
note, acquired common share, reorganized warrant, ETF liquidation, and
exchange-enforcement removal require different terminal-wealth and price-coverage
rules.

The rule mix is also heterogeneous: 17 filings under `(a)(1)`, 12 under `(a)(2)`,
57 under `(a)(3)`, and 14 under `(b)`. Rule provision is a useful stratification
field, not an outcome label. Even the simple reason-text heuristic finds mergers,
redemptions, compliance/distress, and unclassified cases within the rule groups.

### 2. Exchange workflow strongly structures the apparent event clock

Across the sample, 21 filings were accepted pre-open, 48 during the regular session,
and 31 post-close. The aggregate hides a large exchange split:

| Exchange | Sample | Pre-open | Session | Post-close |
|---|---:|---:|---:|---:|
| Nasdaq | 46 | 10 | 8 | 28 |
| NYSE | 33 | 6 | 25 | 2 |
| NYSE Arca | 16 | 4 | 11 | 1 |
| NYSE American | 4 | 1 | 3 | 0 |
| Cboe BZX | 1 | 0 | 1 | 0 |

This is descriptive and not exchange-quality evidence. It does show that a model
which converts all Form 25s to filing dates—or pools event-time returns without
exchange and market-window controls—will manufacture clock error. It also gives a
concrete reason to model source workflow before interpreting a post-close versus
intraday response.

All 100 signature dates equal the acceptance calendar date, and all master-index
filing dates match the acceptance date. No two sampled submissions share the exact
same second. Those checks validate internal clock consistency; they do not identify
when a market participant first downloaded the document.

### 3. The reason exhibit is exchange-dependent and incomplete

Eighty of 100 sampled EX-99.25 exhibits contain more than a placeholder. Coverage is
33/33 for NYSE, 16/16 for NYSE Arca, 4/4 for NYSE American, 27/46 for Nasdaq, and
0/1 for Cboe BZX in this sample. Missing or placeholder reason text is therefore
not plausibly random with respect to exchange workflow.

The conservative keyword baseline labels 18 informative exhibits as
merger/acquisition, nine as redemption/maturity, one as distress/compliance, and 52
as other/unclassified; 20 are not informative. These are routing features for
manual or model-assisted labeling, not ground-truth outcomes. The large
unclassified bucket is a feature, not a failure: it prevents a brittle keyword
model from laundering uncertainty into a confident label.

### 4. Issuer-level sampling would answer a different question

The census has 1,141 filings but only 920 issuers. One issuer can have many security
classes removed. Any later standard error, train/test split, or event-study
bootstrap must cluster at least by issuer and action chain, not treat every Form 25
as independent. An issuer-balanced cohort would underweight the security-class
question; a filing-balanced cohort would overweight frequent debt and fund issuers.
Both can be valid, but the estimand must be named.

## What this node enables next

This backbone intentionally spawns several independent research nodes:

1. **CA-CLOCK100B — issuer/exchange sequence join.** Start with the 31 sampled
   common-equity filings, then extend the same deterministic frame until 100
   outcome-aware chains exist. Join point-in-time issuer 8-Ks, amendments, merger
   completion, bankruptcy effectiveness, and Form 15. Measure which source leads,
   which state is missing, and how often CA-01's source order reverses.
2. **CA-OUTCOME100 — outcome-balanced terminal wealth.** Freeze completed cash,
   stock, mixed, delayed, failed, bankruptcy, and unresolved cohorts. Apply CA-00's
   consideration-leg and inactive-price coverage rules before any return estimate.
3. **CA-HAZARD — competing-risks state model.** Estimate transition hazards from
   announced to completed, failed, delayed, reporting-terminated, or rights-canceled
   states using only information observed by each prediction time.
4. **CA-TEXT — reason/rhetoric model.** Compare transparent rule, exchange, and
   keyword baselines with a small text model. Score abstention and missing-exhibit
   behavior explicitly; do not impute exchange-specific absence as neutral prose.
5. **CA-MARKET — clock-aware market response.** Only after rights and price coverage
   pass, compare pre-open, intraday, and post-close responses with exchange,
   security-family, and issuer-cluster controls.
6. **IX-CA-JOIN — index exit versus corporate-action exit.** Reconcile provider
   deletions with merger, bankruptcy, listing-transfer, and exchange-enforcement
   states so an index-removal study does not mistake terminal wealth mechanics for
   forced-flow effects.

The immediate continuation should be CA-CLOCK100B. It converts the present
filing-level backbone into the outcome-aware multi-source chains the user ultimately
wants for public event prediction.

## Limitations and verdict

- The 100-file content sample is quarter-balanced, not exchange-, security-, or
  outcome-balanced. Exchange comparisons are diagnostics, not population estimates.
- The complete 2023 accession frame is frozen from SEC indexes retrieved in July
  2026. SEC post-acceptance corrections mean a later download can legitimately
  differ; hashes make that difference auditable.
- Security and reason families are transparent heuristics. The raw official fields
  remain available for reclassification, and “other/unclassified” is retained.
- Form 25 does not establish the announcement clock, completion clock, holder
  consideration, terminal price, or reporting termination. Those require joined
  sources and CA-01's parallel state vectors.
- No market price, benchmark, fundamental outcome, or prediction is joined here.
  There is no evidence of alpha, correlation with returns, or a deployable strategy.

**Verdict:** CA-CLOCK100's population backbone passes. It reduces 2,282 ambiguous
index rows to 1,141 identity-verified filings, freezes a reproducible 100-file clock
sample, and reveals security-, exchange-, and disclosure-workflow heterogeneity
that would invalidate a naive delisting study. The outcome-balanced model cohort
remains the next node, not a conclusion already earned.

## Reproduce

Raw inputs and the cache must remain outside the repository:

```bash
venv/bin/python tools/sec_form25_population_lab.py build \
  --index /tmp/sec-master-2023-q1.gz --quarter 2023Q1 \
  --index /tmp/sec-master-2023-q2.gz --quarter 2023Q2 \
  --index /tmp/sec-master-2023-q3.gz --quarter 2023Q3 \
  --index /tmp/sec-master-2023-q4.gz --quarter 2023Q4 \
  --cache-dir /tmp/monad-sec-form25-2023 \
  --per-quarter 25

venv/bin/python tools/sec_form25_population_lab.py summary
venv/bin/python tools/sec_form25_population_lab.py build-db \
  --database /tmp/monad-sec-form25-population.sqlite3
venv/bin/python -m unittest tests.test_sec_form25_population_lab -v
```

The local Context Web can attach the projection with
`--form25-population-db /tmp/monad-sec-form25-population.sqlite3` and exposes
read-only `/form25-population` and `/api/form25-population` routes.
