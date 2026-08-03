# BIOCAT-01 source contract: versioned clinical catalysts

**Research node:** `H18501`

**Audit date:** 2026-08-03

**Decision:** proceed with a versioned discovery pipeline; do **not** train a return model yet.

## Executive result

Clinical-trial data can support a useful public biotech research system, but the
current ClinicalTrials.gov record is not a safe historical feature table. It is a
mutable latest snapshot. In a 25-record Phase 3 industry discovery cohort:

- all 25 records exposed machine-readable histories, with 5–94 versions per trial;
- 24/25 initial enrollment values differed from the current value;
- 2/25 records moved from `COMPLETED` to `TERMINATED` in a later version;
- results appeared a median of about 23 months after primary completion, and
  12/25 took more than 24 months;
- only 6/20 unique sponsor names matched an SEC company name after conservative
  normalization (30% automatic coverage);
- intervention-name lookup in Drugs@FDA can return a generic ANDA ahead of the
  originator application, and a development code can return no record at all.

The investable object is therefore not “trial row predicts return.” It is a
time-aware event graph:

`trial version -> intervention -> sponsor at t -> parent issuer at t -> first public disclosure -> tradable security at t`.

The derived sample and exact audit metadata are in
[`biocat_source_discovery_2026.json`](data/biocat_source_discovery_2026.json).

## Question and pre-model gate

`H18501` asks whether versioned ClinicalTrials.gov, FDA, and first issuer SEC
disclosures can predict clinical outcomes or price reactions without hindsight.
The source-contract gate comes first because a model can look excellent merely by
joining today's corrected registry row to yesterday's price.

The gate is passed only when:

1. every feature has an observable-at or first-seen timestamp;
2. sponsor-to-security mappings have effective dates and reviewed precision of at
   least 95%;
3. mapping coverage is reported separately from mapping precision;
4. trial results are labels unless their public posting preceded every other
   disclosure; and
5. a source-clock baseline survives realistic trading delays.

## Sources and reproducible cohort

The supported [ClinicalTrials.gov API v2](https://clinicaltrials.gov/data-api/api)
reported version `2.0.5` and data timestamp `2026-08-03T09:00:05`. The audit used:

```text
AREA[Phase]PHASE3
AND AREA[LeadSponsorClass]INDUSTRY
AND AREA[HasResults]true
overallStatus = COMPLETED | TERMINATED
```

The query reported 11,133 records. This audit retained the first 25 records in the
API's default order. That is deliberately a source-discovery sample, not a random
or representative population and not an estimate of strategy performance.
ClinicalTrials.gov says its API refreshes on weekdays and exposes a data timestamp;
its reporting guidance also explains that results are generally due after primary
completion and may be delayed under applicable rules. See the
[API documentation](https://clinicaltrials.gov/data-api/api),
[reporting requirements](https://clinicaltrials.gov/policy/reporting-requirements),
and [PRS results guidance](https://clinicaltrials.gov/submit-studies/prs-help/user-guide).

For every sampled NCT ID, the website's machine-readable history interface returned
a version list at:

```text
https://clinicaltrials.gov/api/int/studies/{nct_id}/history
https://clinicaltrials.gov/api/int/studies/{nct_id}/history/{version}
```

This `/api/int` surface is not the documented stable v2 contract. It is useful for
research discovery but must be treated as fragile: archive permitted responses,
record their hashes and ingestion timestamps, monitor schemas, and fail closed.
ClinicalTrials.gov states that each study-record version remains available, but the
supported API documentation does not promise this internal JSON route. The public
[site overview](https://clinicaltrials.gov/about) is the authoritative statement
about record-version availability.

Issuer-name checks used the SEC's
[company/ticker/exchange file](https://www.sec.gov/file/company-tickers-exchange).
The SEC warns that these associations are periodically updated and do not have
guaranteed accuracy or scope; its
[EDGAR data guidance](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
also notes that CIKs are stable while company names can change.

Drug probes used the official
[Drugs@FDA endpoint](https://open.fda.gov/apis/drug/drugsfda/how-to-use-the-endpoint/).

## Finding 1: the latest row rewrites the past

Two records demonstrate why current status cannot be used as a historical label:

| Trial | Earlier version | Later version | What changed |
|---|---:|---:|---|
| NCT01252355 | v53, 2013-05-14: `COMPLETED` | v54, 2013-06-06: `TERMINATED` | Added sponsor-stop reason; stated it was not a safety issue |
| NCT02691182 | v4, 2020-10-19: `COMPLETED` | v5, 2024-04-22: `TERMINATED` | Added lack-of-efficacy stop reason and results years later |

The second case is especially dangerous: a backtest built from the current record
could assign a 2024 lack-of-efficacy fact to the 2020 study status. That is direct
lookahead leakage.

Enrollment is mutable too. Initial enrollment differed from the current value in
24 of 25 records. Large examples include 430 -> 62 (NCT05569174), 620 -> 117
(NCT00893789), and 1,455 -> 534 (NCT01252355). Some changes are ordinary planned-to-
actual reconciliation; others can encode operational trouble. Either way, only the
then-visible value belongs in a feature vector.

## Finding 2: registry results are usually a delayed label

Approximate lag from primary completion to `ResultsFirstPostDate` ranged from 11 to
199 months, with a 23-month median. Twelve of 25 exceeded two years. The maximum was
NCT00473343: primary completion in 2006 and results posting in 2023.

This does not imply noncompliance: coverage and deadlines vary, dates can be
corrected, and extensions can apply. It does imply a market-timing rule:

- use `ResultsFirstPostDate` as the public registry-results timestamp;
- do not use the internal history change date as a public timestamp without proof;
- search issuer filings, releases, publications, conference abstracts, and FDA
  actions for an earlier public disclosure;
- when two sources disagree, retain both clocks and select the earliest verifiable
  public clock for reaction studies.

## Finding 3: sponsor identity is the central entity-resolution problem

Conservative normalization (case/punctuation and common legal suffixes) matched
only 6 of 20 unique sponsors exactly to the SEC ticker file. The matched sponsors
were AbbVie, Axsome, Eli Lilly, Sanofi, Supernus, and Talphera.

Naive fuzzy matching was actively unsafe. Examples included:

- `Cephalon, Inc.` -> Haleon;
- `Chelsea Therapeutics` -> Celldex Therapeutics;
- `Hoffmann-La Roche` -> Pan Global Resources;
- `Otsuka Pharmaceutical` -> Takeda.

These are lexical coincidences, not issuer mappings. The unresolved set mixes
subsidiaries, acquired sponsors, private companies, foreign issuers/ADRs, brand
names, and delisted securities. A precision target alone is insufficient: an
engine can obtain 100% precision by mapping almost nothing. The dashboard must show
both reviewed precision and usable event coverage.

Required mapping key:

```text
(normalized sponsor, effective_from, effective_to)
  -> legal entity
  -> historical parent issuer / CIK
  -> security identifier and exchange validity interval
```

No model row should survive an ambiguous or temporally invalid mapping.

## Finding 4: FDA joins need product lineage, not string equality

Five intervention probes were enough to reject a simple name join:

| Search term | Drugs@FDA observation | Hazard |
|---|---|---|
| baricitinib | NDA207924 / Eli Lilly | Clean first result in this probe |
| cariprazine | NDA204370 / AbbVie | Clean first result in this probe |
| tirzepatide | Two results; first was NDA217806 / Eli Lilly | Multiple applications/products |
| teriflunomide | 13 results; first was generic ANDA218663 | First hit was not the originator application |
| mRNA-1273 | No result for development code | Needs brand/generic/synonym expansion |

The observed Drugs@FDA record has application, sponsor, product, submission, and
openFDA fields but no NCT identifier. The join must distinguish NDA/BLA from ANDA,
maintain intervention aliases, and preserve application/supplement lineage.

## Minimum viable event ledger

One immutable row per observation, not one mutable row per trial:

| Field | Meaning |
|---|---|
| `nct_id`, `version` | Trial identity and registry version |
| `source_observed_at` | When our collector first saw the payload |
| `source_event_at` | Source-provided submission/posting/acceptance clock |
| `payload_hash` | Detect silent revisions and deduplicate |
| `changed_modules` | Status, enrollment, outcomes, sponsor, dates, locations |
| `sponsor_entity_id` | Versioned sponsor identity, never raw fuzzy output |
| `issuer_cik`, `security_id` | Historical issuer/security mapping |
| `mapping_valid_from/to` | Prevent acquisition and delisting leakage |
| `disclosure_type` | Registry, 8-K/6-K, release, FDA, paper, conference |
| `public_at` | Earliest verified public timestamp |
| `tradable_at` | Next permissible market timestamp plus delay |
| `mapping_confidence` | Reviewed/automatic/ambiguous and evidence |

Store source payloads separately from derived rows. The public research interface
can expose provenance, transformations, and rejected joins without distributing
credentials or licensed market data.

## New research branches created by this audit

These are distinct future studies, not extra features forced into one model:

1. **H253200 — Disclosure-order alpha.** Which source speaks first—issuer filing/release,
   registry results, publication, conference abstract, or FDA action—and how much
   reaction remains at each later source?
2. **H253201 — Registry-revision hazard.** Do enrollment haircuts, completion-date slippage,
   endpoint churn, location contraction, or status reversals predict subsequent
   failure after controlling for phase, indication, sponsor size, and trial age?
3. **H253202 — Sponsor-behavior prior.** Measure each sponsor's historical delay, correction,
   and endpoint-change behavior using only information available before a new trial.
4. **H253203 — Rhetoric/registry divergence.** Compare issuer language about a program in
   8-K/10-Q/6-K releases with contemporaneous registry changes. The interesting
   signal is disagreement, not generic sentiment.
5. **Product-lineage graph.** Link development codes, generic names, brands,
   NDA/BLA/ANDA applications, supplements, and acquired programs with effective
   dates; measure whether regulatory lineage adds information beyond filings.
6. **Information-decay curve.** Estimate reaction by source order and delay bucket,
   including after-hours disclosures and the next liquid session. This determines
   whether the signal is public-research useful but not realistically tradable.

## Falsification plan

The next implementation should stop before predictive modeling if any of these
tests fail:

- version history cannot be collected reliably and lawfully with immutable caches;
- reviewed sponsor-to-security precision is below 95%;
- mapping coverage is too low to support a representative evaluation;
- first-public-event completeness is inferior to a simpler SEC/news-only ledger;
- a preregistered filing/news baseline is not beaten out of time;
- any apparent edge disappears after first-seen timestamps, corporate actions,
  delistings, spreads, and realistic reaction delays.

## Honest conclusion

BIOCAT-01 survives as infrastructure research, not yet as a strategy. The strongest
lead is cross-source disclosure ordering plus registry-revision behavior. The most
important negative result is that a current-snapshot trial table joined by sponsor
name is structurally contaminated by hindsight and identity error. Fixing those two
problems is likely more valuable than trying another model architecture.
