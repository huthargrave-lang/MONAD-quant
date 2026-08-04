# BIOCAT FDA pre-notice response census: submission is not posting

**Research nodes:** `E248100`, `F248100`, `F248101`, `H248100`, `D248100`

**Audit date:** 2026-08-03

**Decision:** continue as a sponsor-compliance and regulatory-escalation node;
do not treat registry posting as the sponsor-response clock or as a default
tradable catalyst.

## Executive result

The FDA's complete published pre-notice table through June 2026 contains 246
letters and 315 valid notice-by-NCT rows representing 314 unique trial IDs. The
current ClinicalTrials.gov API returned 313 of those unique records. Every
available letter was downloaded to temporary storage and text-extracted; 190
letters covering 249 trial rows explicitly alleged missing results. Older PDFs
with corrupt text encoding left 56 letters / 66 rows unclassified, and they are
excluded rather than silently assumed to be results notices.

The central finding is a three-clock separation:

| Horizon after notice | First submitted | First met QC | First publicly posted |
|---:|---:|---:|---:|
| 30 days | 54.2% (135/249) | 10.8% (27/249) | 3.2% (8/249) |
| 60 days | 71.1% (167/235) | 25.5% (60/235) | 18.3% (43/235) |
| 90 days | 77.4% (178/230) | 36.5% (84/230) | 31.3% (72/230) |
| 180 days | 85.5% (194/227) | 60.8% (138/227) | 55.9% (127/227) |
| 365 days | 88.7% (181/204) | 84.3% (172/204) | 83.3% (170/204) |

Each denominator is independently right-censored: a row enters a horizon only
when the notice is at least that old on 2026-08-03. These are selected-population
descriptives, not estimates of what the notice caused.

For post-notice responders, median first submission was 24 days while median
public posting was 122 days. The median interval from first submission to a
QC-accepted submission was 64 days and from first submission to public posting
was 85 days. A public registry date therefore measures sponsor response plus an
often-long correction/QC pipeline.

The durable row-level census and full query/source contract are in
[`biocat_fda_pre_notice_census_2026.json`](data/biocat_fda_pre_notice_census_2026.json).

## Sources and population integrity

The exposure comes from the FDA's [Pre-Notices for Potential
Noncompliance](https://www.fda.gov/science-research/fdas-role-clinicaltrialsgov-information/pre-notices-potential-noncompliance)
table. FDA says a pre-notice describes potential noncompliance and asks the
responsible party to address it within 30 days; the agency then decides whether
to close the matter or issue a formal Notice of Noncompliance. The table is
intended to be updated quarterly and, at this audit, covered letters through June
2026.

Registry outcomes use the supported [ClinicalTrials.gov API
v2](https://clinicaltrials.gov/data-api/api), version 2.0.5 with data timestamp
`2026-08-03T09:00:05`. ClinicalTrials.gov's [study-data
definitions](https://clinicaltrials.gov/data-api/about-api/study-data-structure)
distinguish:

- `ResultsFirstSubmitDate`: the first sponsor/investigator submission of summary
  results;
- `ResultsFirstSubmitQCDate`: the first such submission consistent with NLM QC
  criteria; and
- `ResultsFirstPostDate`: the date summary results first became public after QC.

The source projection, not raw source documents, is committed. It records the
FDA HTML hash, every downloaded letter's PDF hash, the API response hash, API
version and timestamp, letter URL, exact source dates, and the censor date. Raw
HTML, API payloads, PDFs, and extracted text remain uncommitted cache inputs.

The source itself exposed two integrity defects that a permissive join would
hide:

- the Celgene table and letter print `NCT027047734`, which has nine digits after
  `NCT`; the parser records it as malformed instead of truncating it into a
  plausible ID;
- `NCT02922592`, listed in Pacira's letter, is absent from the current API result
  even though the other four trials in that letter resolve.

One valid trial, `NCT03931291`, appears in two pre-notices one week apart under
Aprea Therapeutics and BeyondSpring. The census preserves both exposure rows and
reports one duplicate rather than deduplicating away the regulatory history.

## What the response curve actually says

### The 30-day request primarily moves the submission clock

Among the 206 rows with a post-notice first submission, the lag distribution was:

| Statistic | Days |
|---|---:|
| Minimum | 0 |
| 25th percentile | 13 |
| Median | 24 |
| 75th percentile | 43.75 |
| 90th percentile | 104 |
| Maximum | 684 |

The mass around 30 days is consistent with an operational response to the
letter, but consistency is not causality. FDA selects trials already suspected
of noncompliance, there is no untreated comparison group, the publication date
need not equal receipt date, and sponsor work may have started before the letter.

The letter-level calculation prevents multi-trial notices from receiving extra
weight. Of 190 results-scope letters old enough for a 30-day outcome, 56.8% had
at least one trial submitted within 30 days and 54.7% had every linked trial
submitted. By 365 days, the corresponding rates were 89.5% and 87.6% among 153
eligible letters. Row and letter estimates are therefore close; the result is
not an artifact of the 41 multi-NCT letters.

### Public posting is mainly a delayed availability label

For 207 post-notice postings, median lag was 122 days, the 25th–75th percentile
range was 70.5–215 days, and the 90th percentile was 314.4 days. Even among
letters at least 365 days old, every linked trial was posted within one year for
only 81.0% of letters.

This clock is useful for predicting when a structured public result will become
available. It is not a clean label for whether a sponsor reacted within the
FDA's 30-day window, and the preceding BIOCAT disclosure-order pilot found that
issuer trial disclosures can lead registry results by years. A posting model is
therefore better interpreted as a data-availability or compliance-operations
model than as a clinical surprise model.

### Sponsor class is not the obvious separator

The results-scope population contains 209 industry rows and 40 non-industry
rows. Industry versus non-industry first-submission rates were 53.1% versus
60.0% at 30 days and 88.7% versus 88.9% at 365 days. Public-posting curves were
also similar. These unadjusted groups are imbalanced and historically selected,
but the coarse class flag does not look like a sufficient model by itself.

Notice-year differences are not safely interpretable yet. Text extraction
failed disproportionately on the older 2013–2021 PDFs because their embedded
font maps are corrupt; the year strata therefore have a changing inclusion
mechanism. A production history needs OCR or reviewed allegation labels for
those letters before any enforcement-trend claim.

## The escalation-tail lead

The registry's current violation annotations identify the same eight trials on
FDA's published [Notices of Noncompliance and Civil Money Penalty
Actions](https://www.fda.gov/science-research/fdas-role-clinicaltrialsgov-information/clinicaltrialsgov-notices-noncompliance-and-civil-money-penalty-actions)
page. None had a first-results submission within 180 days of its pre-notice:

- six first submitted after 279, 282, 295, 408, 502, and 684 days; and
- two still have no `ResultsFirstSubmitDate` in the current snapshot.

That is a clean qualitative separation in the eight observed formal cases, but
it is not yet a prediction result. Formal escalation is downstream, extremely
rare, and the current annotation is an outcome-bearing field. It must never
enter features. The useful target is whether point-in-time information available
at or shortly after a pre-notice predicts later escalation better than a simple
elapsed-time rule.

## Model contract spawned by the census

`H248100` is a sponsor-compliance prior, not a return model. A candidate dataset
should preserve:

| Block | Point-in-time fields |
|---|---|
| Notice | letter date, allegation scope, NCT count, center, request window |
| Trial obligation | primary completion, delay certification/extension state, applicable-trial fields, days overdue |
| Sponsor history | prior notices and response lags observed before the forecast, unresolved obligation count |
| Registry operations | revision count, last pre-notice update, prior QC cycles, responsible-party changes |
| Outcomes | first submit, first QC-accepted submit, first post, administrative close, formal escalation |
| Grouping | responsible party, parent issuer, notice/letter, trial program |

The evaluation order is:

1. reconstruct each registry record exactly as it appeared on the notice date;
2. build matched overdue controls for a causal enforcement study, separately
   from the targeted-population prediction task;
3. walk forward by notice date with every responsible party and parent issuer in
   one fold;
4. beat notice-year, elapsed-time, sponsor-class, and unresolved-count baselines
   on calibration and recall of the slow/escalation tail; and
5. test residual market information only on reviewed cases where the registry
   posting precedes or materially changes the first issuer disclosure.

Kill the sponsor prior if it loses its gain under grouped out-of-sponsor
validation. Kill causal language until point-in-time matched controls exist.
Kill registry-posting return research if reviewed issuer disclosures already
contain the result or if event purity cannot reach the required precision.

## Public-resource product path

This node can create a useful free resource even if it never produces excess
returns:

- an auditable unresolved-notice explorer with letter, trial, sponsor, first
  submission, QC, posting, and escalation clocks;
- a transparent sponsor reporting-history card that separates observed facts
  from a calibrated prediction;
- alerts when the 30/60/90/180-day state changes; and
- research-suggestion endpoints for users to propose issuer joins, missing
  aliases, OCR corrections, and matched controls without editing the frozen
  observation ledger.

That product should use SQLite as a projection/cache behind an append-only event
ledger, preserving source hashes and effective/observed timestamps. Community
suggestions belong in a separate review queue; they must not mutate the verified
source facts directly.

## Decision

Continue `H248100`. The notice event contains a measurable operational response
curve and the slow tail aligns with all eight formal escalations in the current
registry. The most defensible near-term model predicts compliance timing and
regulatory escalation, while the most defensible public product exposes the
underlying clocks and provenance for free. No causal enforcement claim and no
price-edge claim survive this census alone.
