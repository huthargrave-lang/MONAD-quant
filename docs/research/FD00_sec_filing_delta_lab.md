# FD-00 — SEC Filing Delta Lab: Point-in-Time Feasibility and Model Factory

**Status:** source-contract audit and preregistration; no predictive edge claimed<br>
**Created:** 2026-07-24<br>
**Program:** Public Investment Intelligence Frontier<br>
**Durable fixture:** [`data/fd00_sec_event_clock_fixtures_2026.json`](data/fd00_sec_event_clock_fixtures_2026.json)

## Decision

Proceed with the SEC Filing Delta Lab, but build the append-only filing ledger before
testing language or return prediction.

The official corpus is broad, free, and capable of supporting many related studies.
It is not safe to model directly from a current ticker list, filing date, latest
`companyfacts` value, or rebuilt quarterly index. Those shortcuts create exactly the
survivorship, timestamp, identity, and revision leakage that can turn a useful public
resource into a polished backtest of information nobody actually had.

The first production-quality research table must be accession scoped and retain:

- raw acceptance, filing, report, first-seen, and public-release times separately;
- issuer CIK independently from the accession prefix;
- original filings, amendments, private-to-public releases, and post-acceptance
  corrections as distinct events or revisions;
- the exact primary document and XBRL payload used, with content hashes;
- time-bounded security mappings and explicit unmapped/delisted outcomes;
- filing-specific, as-filed facts rather than a “latest value for period” shortcut.

This is a **feasibility verdict**, not evidence that filing deltas still predict
returns. The published effects are priors that must survive a post-publication,
point-in-time test.

## Why this node can spawn a research tree

One honest filing ledger supports much more than a single text model:

1. same-form filing changes;
2. next-filing revenue, margin, cash-flow, leverage, and dilution forecasts;
3. rhetoric-versus-numbers divergence;
4. amendments, restatements, and late-filing risk;
5. 8-K event classification and event-response distributions;
6. industry information transfer and filing propagation graphs;
7. accounting-tag consistency and data-quality warnings;
8. executive, risk-factor, legal, cybersecurity, and segment-change studies;
9. security-master and corporate-action research;
10. a free public “what changed, what usually followed, and how certain are we?”
    evidence card.

The shared ledger is therefore a model factory. A one-off sentiment score is not.

## Primary-source reconnaissance

### Corpus and access

The SEC’s [EDGAR API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
states that:

- submissions and XBRL APIs require no authentication;
- submissions include at least one year or 1,000 recent filings, with older history
  linked in additional files;
- XBRL was first required in 2009;
- submissions normally update in under a second after dissemination and XBRL in
  under a minute, with longer delays possible at peaks;
- nightly bulk `submissions.zip` and `companyfacts.zip` archives are available.

The historical text universe is older. SEC indexes cover public electronic filings
from 1994Q3 onward, and all public domestic companies were phased into EDGAR by May
1996. The SEC’s [Financial Statement Data Sets](https://www.sec.gov/file/financial-statement-data-sets)
begin on 2009-04-15 and describe their records as uncorrected, “as filed” data.

The important coverage breakpoints are therefore:

| Era | Text | Structured facts | Research use |
|---|---|---|---|
| 1994Q3–1996 | partial EDGAR population | no modern XBRL | parser archaeology only |
| 1996–2009 | broad electronic text | no required modern XBRL | text-only replication |
| 2009–2018 | text plus XBRL | phased practices and data-quality drift | development with era controls |
| 2019 onward | widespread Inline XBRL | richer document/fact integration | primary transparent baseline era |

The planned 2010 start is feasible, but 2019 is the cleaner start for models that
depend on Inline XBRL layout or tagged narrative. Era indicators are not optional.

### Access and redistribution

The SEC permits scripted access subject to its fair-access rules. Its
[developer FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions)
requires a declared user agent and currently caps access at ten requests per second.
The collector should be materially slower than the cap, use nightly bulk archives
for backfills, cache immutable payloads, and retry with bounded exponential backoff.

This audit could reach ordinary SEC pages and official documentation, but the SEC
rejected direct automated bulk/API requests from the present network even after a
declared user agent; the in-app browser also blocked the data endpoint. That is an
environment-specific collection limitation, not a finding that the public API is
unavailable. It does mean that MONAD should not pretend it completed a corpus-scale
coverage count in this run. Production backfill remains a gated task from an
approved network identity.

The SEC data are public-domain U.S. government material, but filings can contain
third-party copyrighted exhibits and personal information. The public product should
store hashes and SEC locators, quote minimally, and show transformed features rather
than redistribute an indiscriminate full-text mirror.

## PT-01 event-clock audit

### Acceptance is not availability

The SEC says filings are often available on its website one to three minutes after
the EDGAR timestamp, delays can increase under load, and there is **no timestamp for
first website availability**. Acceptance time is therefore a source event, not an
observed public-availability time.

For a live collector:

```text
source_event_time = public dissemination time when available,
                    otherwise acceptance time for an ordinary public filing

tradable_time = first eligible market bar after
                max(source_event_time, collector_first_seen_time)
                + declared processing buffer
```

For historical research without archived receipt or PDS evidence:

```text
daily default    = next regular-session open after the source event
intraday default = ineligible
```

A sensitivity view may use acceptance plus 3, 5, and 10 minutes, but it cannot be the
primary historical intraday result because the SEC explicitly does not guarantee the
lag. A model whose result disappears at the next regular open is not suitable for a
free public tool using ordinary EDGAR access.

### Filing date is not an event timestamp

The official fixture set contains several real adversarial examples:

| Case | Acceptance | Filing date | Consequence |
|---|---|---|---|
| Apple 2026 Q2 10-Q | 2026-05-01 06:01:00 | May 1 | premarket; same date |
| Alphabet 2026 Q1 10-Q | 2026-04-29 21:02:11 | Apr 30 | acceptance and filing date differ |
| Natera 2026 8-K | 2026-05-07 16:10:41 | May 7 | same date, but after regular close |
| BIO-key 2025 10-K/A | Fri 2026-06-12 19:31:12 | Mon Jun 15 | amendment plus weekend rollover |
| Enron 1999 10-K | displayed as 2000-03-30 00:00:00 | Mar 30 | midnight is not reliable intraday evidence |

The SEC’s filing detail for Alphabet is decisive: the 10-Q was accepted at 9:02 p.m.
on April 29 but has an April 30 filing date. Conversely, a 4:10 p.m. acceptance can
keep the same filing date while being untradeable at that day’s regular close.
Joining daily returns on `filing_date` alone mislabels both cases.

### Private-to-public and corrections

A particularly dangerous fixture is Circle Internet Group’s DRS/A. Its raw header
shows:

- acceptance on 2024-08-06;
- `<PRIVATE-TO-PUBLIC>`;
- `PUBLIC-REL-DATE` of 2025-04-01.

The 2024 acceptance cannot be used as public information. If public release time is
only known to the date, the conservative tradable label is the following regular
session unless a dissemination record recovers the time.

Post-acceptance corrections have a similar implication. The SEC says:

- original filings and filer amendments usually both remain;
- some SEC corrections or removals change current EDGAR;
- daily indexes incorporate same-day corrections;
- full and quarterly indexes are rebuilt weekly to incorporate later corrections or
  deletions;
- old daily/feed/oldload indexes are not necessarily rewritten.

Therefore a current rebuilt index is not a byte-for-byte reconstruction of what a
researcher saw on the original date. The ledger must retain the dissemination stream,
revision type, payload hash, and first-seen time. Corrections and deletions must not
silently overwrite the model input.

### Identity is not the accession prefix

The SEC explains that the first ten digits of an accession can identify a
third-party filing agent rather than the company. Apple’s February 2026 8-K is in
Apple’s CIK directory but has accession `0001140361-26-006577`, not an accession
beginning with Apple’s CIK `0000320193`.

The normalized issuer identity must come from the header’s role blocks (`FILER`,
`ISSUER`, `SUBJECT-COMPANY`, and so on), not by parsing the accession. Preserve both:

```text
accession_submitter_cik
issuer_cik
subject_company_cik
reporting_owner_cik
```

This becomes essential when the ledger expands to Forms 3/4/5, 13D/G, 13F, tender
offers, or agent-submitted corporate filings.

### Timezone contract

Store the raw timestamp string exactly. Interpret ordinary EDGAR operating times in
`America/New_York`, not a fixed UTC offset. SEC pages sometimes use the legacy label
“EST” while operational guidance uses Eastern Time; treating summer filings as
UTC-5 would shift the clock by an hour. Every derived UTC value must retain:

- raw local timestamp;
- parsing rule version;
- assumed IANA timezone;
- ambiguity/quality flag.

## Source hierarchy

Not every official SEC surface is equally suitable for reconstruction.

| Tier | Source | Proper use | Failure if used alone |
|---:|---|---|---|
| 0 | Feed/Oldloads/PDS dissemination plus raw SGML | immutable event history and revision order | larger operational burden |
| 1 | complete submission, header, filing directory/index | payload, roles, acceptance, documents, items | current page can reflect later correction |
| 2 | submissions API and nightly bulk | efficient discovery and filer history | current state, paginated history, not receipt time |
| 2 | filing-specific extracted XBRL | accession-scoped numeric facts | taxonomy/context errors remain |
| 3 | companyfacts/companyconcept | convenient standardized fact candidates | easy to select a later-filed value for an old period |
| 4 | current ticker/CIK/exchange files | search convenience | SEC explicitly does not guarantee accuracy or scope |

The SEC’s cumulative CIK-name list is more appropriate for historical issuer
discovery than the current ticker list, but it includes funds, individuals, inactive
entities, and multiple historical names. It is a universe seed, not a security
master.

## FD-00 coverage audit specification

The corpus-scale audit was not executed here because the official bulk endpoint
blocked this environment. The next approved backfill must produce the following
table before FD-01 modeling:

### Population

- all public 10-K, 10-K/A, 10-Q, and 10-Q/A submissions from 2010 onward;
- retain inactive CIKs, historical names, late filers, and no-longer-traded issuers;
- identify domestic operating companies using form, role, SIC, and filer metadata;
- preserve but separately flag shells, SPACs, BDCs, REITs, banks, insurers, foreign
  private issuers, funds, and transition reports;
- never start from today’s listed tickers.

### Required annual diagnostics

For every year and form:

1. filing and unique-CIK counts;
2. amendment count and time from original to amendment;
3. valid second-level acceptance-time rate;
4. acceptance/filing-date mismatch rate;
5. primary-document retrieval and hash rate;
6. exact section-extraction rate by Item;
7. XBRL presence and filing-specific instance retrieval rate;
8. standard versus custom concept share;
9. comparable prior-form pair rate;
10. CIK-to-security mapping rate at event time;
11. delisted/inactive/no-price rate;
12. parser disagreements and quarantined events.

Report these by size, SIC/industry, exchange, filer status, and outcome availability.
An aggregate 95% coverage number can hide near-total failure among small or failed
firms.

### Coverage gates

Proceed to FD-01 only if:

- at least 95% of eligible events retain a raw payload, header, and deterministic
  accession identity;
- section extraction reaches at least 95% on a hand-labeled stratified audit, with
  precision and recall reported separately;
- at least 90% of the intended test population has a valid same-form comparison;
- XBRL concepts needed by a target have at least 80% stable coverage in every split,
  or the target is explicitly restricted before test data are opened;
- unmapped securities and delistings remain labeled rather than dropped;
- a random sample of inactive issuers is reconstructable;
- every event clock can be reproduced from stored fields and a versioned rule.

Fail closed. A missing document, ambiguous clock, or conflicting issuer mapping is a
quarantined row, not an invitation to impute from future data.

## Filing-specific XBRL contract

The SEC’s APIs intentionally aggregate non-custom concepts applying to the entire
filing entity. That makes `companyfacts` useful for discovery, but it does not make
“take the last value for this fiscal period” point-in-time safe.

Rules:

1. Select facts belonging to the event accession.
2. Preserve concept namespace, tag, unit, start, end, instant/duration type,
   dimensions, decimals, scale, and filing context.
3. Do not collapse consolidated and dimensional/segment facts.
4. Prefer the filing-specific extracted XBRL instance as the auditable source.
5. Treat custom concepts as features only after an explicit semantic mapping.
6. Keep first-as-filed and corrected/restated values as separate target definitions.
7. Never manufacture quarterly Q4 from annual data without labeling the derivation.
8. For 10-Qs, distinguish single-quarter and year-to-date duration contexts.

The SEC’s own structured-data guidance documents incorrect context dates, scaling
errors, changing tags for the same item, inappropriate custom tags, and EPS/share
tagging errors. Those are not theoretical parser issues. Numeric baselines need
validation rules and an “unresolved” state.

### Canonical numeric targets

Start with high-coverage concepts and transparent fallbacks:

- revenue;
- gross and operating income/margin;
- operating cash flow;
- capital expenditure;
- cash and debt;
- interest expense;
- diluted shares and stock-based compensation;
- inventory and receivables for relevant industries.

For each target publish:

- exact standard tags accepted;
- custom-tag mapping rule;
- context constraints;
- unit and scaling checks;
- reconciliation tolerance;
- coverage by year/industry;
- fallback and exclusion counts.

## Text-delta contract

### Comparison keys

Do not mix all “previous filings” into one treatment. Create separate pair types:

| Pair type | Current | Prior | What it measures |
|---|---|---|---|
| annual | 10-K | previous 10-K | annual structural/narrative change |
| sequential quarterly | 10-Q | immediately previous 10-Q | recent disclosure evolution |
| same-fiscal-quarter | 10-Q | year-ago corresponding 10-Q | seasonally aligned change |
| amendment | 10-K/A or 10-Q/A | exact original accession | corrective change |

Sequential and same-quarter 10-Q deltas answer different questions. A cumulative
six-month cash-flow statement is not directly comparable to a three-month context.

### Canonical sections

Extract sections by filing type and preserve extraction confidence:

- Business;
- Risk Factors;
- MD&A;
- Quantitative and Qualitative Market Risk;
- Legal Proceedings;
- Controls and Procedures;
- Financial Statements and Notes;
- 10-K Item 1C Cybersecurity, only after its rule-era adoption;
- 8-K item codes and exhibits in the event branch.

Rule changes can cause synchronized additions across the market. Section birth,
renumbering, and disclosure mandates must be controlled by form-year and rule era,
not interpreted as company-specific novelty.

### Transparent feature families

Freeze these before any embeddings or large language model scores:

1. token Jaccard and cosine similarity using a fixed vocabulary;
2. normalized character and sentence edit distance;
3. added, removed, and unchanged sentence shares;
4. section appearance/disappearance and section length change;
5. numeric-token, table, exhibit, and cross-reference shares;
6. finance-specific negative, uncertainty, litigious, modal, and constraining word
   changes, subject to dictionary rights;
7. readability and boilerplate measures;
8. named executive, customer, geography, segment, product, covenant, and litigation
   entity changes with exact source spans.

Document length alone is a required adversarial baseline. If a complex model only
discovers that longer or more changed filings are different, the public product
should show the simpler fact.

## Model factory

Each child is a separately registered hypothesis family, not another feature poured
into one giant search.

### FD-NUM — future fundamentals

Can filing-specific numeric changes improve next-filing revenue growth, operating
margin, cash-flow direction, leverage, or dilution forecasts beyond:

- prior value and prior change;
- industry-year median;
- seasonal same-quarter baseline;
- size and lagged price/volatility context?

This is first because fundamentals are closer to the filing’s content than returns
and do not require an implausible trading-speed story.

### FD-TEXT — same-form section delta

Do frozen section-change features add information beyond FD-NUM, document length,
industry-year, and market context? Test one section family at a time, then a declared
joint model.

### FD-RN — rhetoric–numbers residual

Estimate expected language from current numeric results, industry, size, and prior
language using development data only. Test whether the residual—unusually
optimistic, uncertain, or constrained language conditional on the numbers—predicts
next fundamentals, amendment risk, downside, or volatility.

This is not “positive words mean buy.” The hypothesis is inconsistency between two
information channels.

### FD-AMEND — amendment anatomy

Compare each amendment to its exact original:

- what sections and facts changed;
- whether it is exhibit-only, Part III incorporation, tagging-only, or financial;
- lag to amendment;
- whether particular change types predict later restatement, control weakness, or
  downside risk.

Never replace the original row with the amendment.

### FD-TIME — processing-time heterogeneity

Test whether premarket, market-hours, postclose, and late-evening filings differ in
reaction speed after controlling for event content and self-selected timing.
Treat timing as endogenous. The primary target is response timing/volatility, not a
trading rule.

### FD-GRAPH — filing information transfer

Use industry, supplier/customer, product, and factor exposures to ask whether one
company’s filing updates forecasts for related companies before their next filings.
This is the filing-ledger successor to the failed simple daily ETF lead-lag graph:
edges are conditioned on a new public information event rather than searched across
every day.

### FD-QUALITY — disclosure and tagging instability

Test whether tag churn, custom-concept share, reconciliation failures, section
instability, late filing, or control-language change predicts amendment,
restatement, volatility, or future operating deterioration. Data quality warnings
are themselves possible outcomes, but only after separating filer complexity from
poor reporting.

### FD-EVENT — grounded 8-K taxonomy

Begin with filed item codes, form metadata, and exhibit types. Add fine-grained event
labels only if every label retains the supporting source span and passes a
hand-labeled reliability audit. Results/guidance, leadership, financing, acquisition,
impairment, bankruptcy, delisting, cybersecurity, and control events become distinct
families.

## Targets and baselines

### Fundamental targets

- next-filing direction and magnitude of revenue growth;
- gross/operating margin;
- operating cash flow and accruals;
- leverage and interest burden;
- diluted share count;
- amendment, restatement, late filing, or material-weakness indicator.

Evaluate calibration, Brier/log loss for direction, MAE for magnitude, and incremental
out-of-sample \(R^2\). Report base rates and industry dispersion.

### Market targets

- 1, 5, 20, and 60 regular-session total return;
- market, sector, and style-adjusted return;
- next-session gap and regular-session return separately;
- realized volatility and maximum adverse/favorable excursion;
- liquidity/spread response when reliable historical data exist;
- delisting return or explicit missing-outcome state.

Return prediction is secondary. A strong next-fundamental forecast with no residual
return predictability is still useful evidence that the market incorporated the
information.

### Required baselines

- unconditional and industry-year base rates;
- previous value/change;
- numeric-only regularized model;
- prior return/volatility/size/liquidity;
- length-only and filing-time-only models;
- simple seasonal random walk;
- missingness indicator model.

Every language or machine-learning model must beat the relevant simple baseline in
both validation and untouched test data.

## Validation and falsification

### Frozen time splits

- development: 2010–2018;
- validation/model selection: 2019–2022;
- untouched test: 2023 onward;
- annual expanding-window walk-forward as robustness only.

Because the influential “Lazy Prices” sample ends in 2014 and the paper was
published later, also report:

- pre-2015 reconstruction;
- 2015–publication transition;
- post-publication period;
- post-2020 and post-Inline-XBRL regimes.

A result confined to the original literature era is a replication, not a current
public edge.

### Units of dependence

Outcomes overlap and firms file repeatedly. Use:

- firm-clustered uncertainty for event models;
- date clustering or two-way firm/date clustering where appropriate;
- non-overlapping portfolio views for long horizons;
- industry and calendar-time concentration diagnostics;
- block bootstrap for pooled prediction errors.

### Multiple testing

Register each target × horizon × feature family. Use:

- a small primary family with Holm or family-wise correction;
- Benjamini–Hochberg only for explicitly exploratory child discovery;
- one untouched test opening;
- a trial ledger that records failed and abandoned branches.

No “best section, best target, best horizon” result survives unless selection is
inside development/validation and the entire search family is corrected.

### Kill tests

Reject or sharply narrow a claim if it:

- fails after 2019 or after publication;
- disappears against a length-only or numeric-only model;
- is driven by microcaps, a single industry, crisis years, or a few bankruptcies;
- depends on dropping inactive, amended, late, or delisted issuers;
- changes sign across reasonable section parsers;
- depends on a companyfacts value filed after the event;
- vanishes at the next regular-session-open clock;
- fails when synchronized rule-era text is residualized;
- cannot reproduce exact event membership from stored payload hashes;
- relies on a proprietary dictionary or price/security history that cannot be
  published or independently reproduced.

## Published priors, not imported facts

Cohen, Malloy, and Nguyen report that active changes in regular 10-K/10-Q language
over 1995–2014 relate to future operations and returns
([NBER working paper](https://www.nber.org/papers/w25084);
[Journal of Finance DOI](https://doi.org/10.1111/jofi.12885)).
That makes same-form deltas worth testing. It does not establish a post-publication
effect.

Loughran and McDonald show that a general-purpose dictionary misclassifies many
ordinary financial words and develop finance-specific categories linked to filing
outcomes
([Journal of Finance DOI](https://doi.org/10.1111/j.1540-6261.2010.01625.x)).
Their lesson is that domain context matters. The dictionary’s current licensing
terms must be checked before use in a public product.

The model factory deliberately predicts fundamentals before returns, tests document
length and numeric-only alternatives, and isolates the post-publication era. Those
choices are intended to falsify the easiest stories first.

## Free public evidence-card contract

For a filing event, the first useful product should show:

- company and security identity with effective dates;
- form, accession, acceptance, first-seen, and conservative tradable time;
- exact prior filing used for comparison;
- sections and facts that changed, with links to both filings;
- whether the event is an amendment, correction, or private-to-public release;
- current numeric changes and data-quality flags;
- model forecast, base rate, uncertainty, and relevant benchmark;
- out-of-sample record for that model version;
- known failure regimes and coverage/exclusion reason;
- “informational evidence, not investment advice.”

If the evidence card cannot explain its source clock and comparison filing, the
prediction should not be published.

## Implementation queue

### PT-01 — event-clock parser

Implement the JSON fixtures as tests before collection. Required parser outputs:

```text
event_id
accession
issuer_cik
submitter_cik
form
form_base
is_amendment
dissemination_kind
accepted_raw
accepted_at
filing_date
public_release_at/date
first_seen_at
tradable_at
clock_quality
payload_hash
revision_id
```

### FD-00A — approved bulk backfill

Use SEC nightly submissions data for discovery and Feed/Oldloads/raw submissions for
evidence. Produce annual coverage diagnostics and a manifest containing source URL,
retrieval time, byte size, and SHA-256 for every bulk input.

### FD-00B — security master

Build time-bounded CIK ↔ issuer ↔ share-class ↔ ticker mappings. Keep one-to-many
relationships, inactive securities, mapping confidence, source, and effective dates.
Do not infer history from the current SEC ticker file.

### FD-00C — dual parser audit

Run two independently implemented section parsers on a stratified hand-labeled
sample covering eras, size, industry, amendments, legacy HTML/text, and Inline XBRL.
Measure precision, recall, boundary error, and disagreement.

### FD-01A — numeric baseline

Freeze the first high-coverage fundamental targets and beat seasonal/prior-value
baselines in validation before opening any text features.

### FD-01B — transparent section delta

Add one declared section family at a time. Stop if incremental information is absent.

### FD-01C — untouched test and evidence cards

Open 2023+ once, publish all registered outcomes, and generate example evidence cards
for successes and failures.

## Bottom line

The SEC Filing Delta Lab is the best next root node because it can support many
publicly useful models from one free official corpus. The source-clock audit also
shows why it can fail:

- filing date is not acceptance time;
- acceptance is not guaranteed public availability;
- original acceptance can precede public release by months;
- corrections can rewrite current indexes;
- accession prefix is not always issuer identity;
- current ticker mappings are not a historical universe;
- structured facts contain real context, scaling, tag, and revision hazards.

Those are design requirements, not reasons to abandon the project. If MONAD builds
the ledger first and publishes coverage, uncertainty, and negative results, it can
offer something genuinely scarce: free filing intelligence that is auditable enough
to distrust.
