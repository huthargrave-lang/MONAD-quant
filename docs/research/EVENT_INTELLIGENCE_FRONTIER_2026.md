# Event intelligence frontier: public events as a model factory

**Date:** 2026-08-03

**Status:** research architecture and preregistration; no return result and no trading mandate

**Durable specification:** `data/event_intelligence_frontier_2026.json`

## Conclusion first

MONAD should expand by building **event state models**, not by adding more indicator
variants. The highest-value research unit is not “does metric X correlate with the
next return?” It is:

> Given exactly what the public could know at time *t*, did an issuer, contract,
> trial, owner, regulator, or market-plumbing process change state—and can that
> transition predict a real subsequent outcome beyond a transparent baseline?

This creates new nodes that can spawn their own studies. A clinical-trial node can
branch by phase, indication, sponsor, endpoint revision and peer read-through. A
government-award node can branch by agency, award type, funded obligation,
recipient, supplier and backlog impact. The shared infrastructure—clocks, identity,
versions and outcomes—can serve all of them without pretending the events are
economically interchangeable.

The recommended first two pilots are:

1. **BIOCAT-01:** a trial/FDA/issuer catalyst state machine.
2. **GOVCON-01:** a federal-award obligation and supplier-propagation model.

Schedule 13D intent changes and structured 8-K shocks follow them. SEC comment
letters are useful chiefly as delayed training labels. Reg SHO is a guarded null
study, not a “naked short” narrative engine.

## What is new relative to the current frontier

The existing H44/H49 direction is correct but broad: build a point-in-time public
intelligence graph, then add sources one at a time. F219 showed why that root is not
yet operational: artifact versions are fairly mature, but entity identity, callable
clock rules and a trial registry are sparse.

This proposal gives H44 a set of economically distinct consumers and makes their
contracts concrete:

| Program | State being modeled | First non-price outcome | Why it can reproduce |
|---|---|---|---|
| BIOCAT-01 | trial → result → regulatory state | success/failure and milestone hazard | phase, indication, endpoint, sponsor and issuer form a family of child studies |
| GOVCON-01 | award transaction and modification state | backlog/revenue revision | agency, award type, recipient and supply chain create reusable branches |
| OWNERSHIP-01 | passive/active ownership and purpose state | campaign escalation or concession | filer, stake, purpose and outcome become a repeatable campaign panel |
| 8K-SHOCK-01 | item-specific operational shock state | amendment, distress or recovery | each item has its own head over a shared filing encoder |
| COMMENT-LABEL-01 | filing-review conversation state | amendment/restatement risk | delayed correspondence can label earlier filing features honestly |
| SETTLE-STRESS-01 | threshold-list and delayed FTD state | liquidity/settlement normalization | a null-first design separates mechanics from squeeze stories |

This is not a proposal to pool all events into one model. Sharing a ledger is useful;
sharing a label before each source earns it is leakage with nicer plumbing.

## The six-agent research loop

Every program should be produced by six narrow roles. They can be separate software
agents later, but the boundaries matter now:

1. **Clock auditor** — records source event, publication, first-seen, conservative
   tradable and revision times; quarantines ambiguity.
2. **Identity resolver** — maps source entity → issuer → date-valid security and
   retains the mapping method and confidence.
3. **State builder** — emits append-only transitions. A corrected record supersedes
   an earlier version; it never silently rewrites it.
4. **Outcome labeler** — builds operational and fundamental labels after the cutoff,
   before anyone looks at returns.
5. **Baseline challenger** — tries to explain the result using mechanical fields,
   issuer characteristics, common factors, publicity and selection.
6. **Falsifier** — deliberately delays clocks, shuffles identities, removes revised
   fields and runs placebo events. Failed ideas become durable outcomes.

The key development is organizational as much as statistical: ingestion agents do
not get to grade their own signal.

## Program 1 — BIOCAT-01: biotechnology catalyst state machine

### Why this is a root, not a one-off study

Clinical development is already a stateful process. Trials change status; enrollment,
endpoints and completion dates are revised; results appear; regulatory applications
and approvals follow; issuers disclose their interpretation. Those transitions can
spawn independent models for:

- outcome hazard by phase and indication;
- endpoint or completion-date revision significance;
- sponsor financing needs and dilution risk;
- first issuer disclosure versus later registry posting;
- target/indication peer read-through;
- differences between sponsor narrative and registry state.

ClinicalTrials.gov API v2 is machine-readable and publishes a dataset timestamp, but
the live API is fundamentally a current-record surface. The site exposes record
history, and record updates follow their own submission/posting process. Therefore a
current API snapshot must never be used to reconstruct what an investor knew months
earlier. Historical versions must be captured or sourced from the archive, and a
registry-post clock must not be confused with the sponsor's original event clock.

FDA approval records supply outcomes, not necessarily the first public timestamp.
SEC accepted-at times, company releases and registry posting times may disagree.
The first pilot should preserve all three rather than choose the most convenient.

### First model and kill test

Predict trial success/failure/termination and time to the next milestone before any
return study. The minimum baseline is phase + indication + intervention type +
sponsor class + issuer size + pre-event price state. A transparent discrete-time
hazard model goes first; text or temporal-graph features only earn a place if they
beat it in a later era with issuer-grouped folds.

Kill the program if reviewed sponsor-to-public-issuer precision is below 95%, if
historical versions cannot be reconstructed, or if the result disappears when every
feature is delayed to collector first-seen.

## Program 2 — GOVCON-01: awards, obligations and supplier propagation

### Why headline contract studies are usually wrong

USAspending exposes award and transaction data without an API key, including action
dates, action types, modification numbers, descriptions and federal obligations.
That sounds easy and is not. A press headline may report a maximum ceiling while the
economically relevant funded amount is a much smaller obligation. A “new award” may
be a modification. A recipient may be a subsidiary of a listed company. An action
date, database update and public first-seen time are different fields. Coverage and
linkage also vary across agencies and eras.

Those hazards make this a strong agent problem: identity resolution, modification
deduplication and clock auditing are reusable capabilities, not cleanup for one
regression.

### First model and kill test

Start with contract transactions, not press releases. Separate new awards,
incremental obligations, de-obligations and option exercises. Scale obligation by
the mapped public parent's revenue and market value. Predict next-two-quarter backlog
or revenue revision before testing returns.

The minimum baseline is scaled obligation + agency + award type + industry + prior
recipient/agency relationship. Only then test supplier or competitor propagation in
an agency-recipient-supplier graph.

Kill the program if reviewed public-parent mapping precision is below 95%, if new
awards cannot be separated from modifications and ceilings, or if action-date results
fail when delayed to collector first-seen.

## Program 3 — OWNERSHIP-01: 13D intent transitions

Schedule 13D is useful because the unit is a delta, not a bag of sentiment. The model
should track initial 13D filings, Schedule 13G→13D transitions, Item 4 purpose changes,
ownership and derivative-exposure deltas, group changes, and later outcomes such as a
board seat, settlement, tender, escalation or withdrawal.

The SEC's beneficial-ownership modernization changed initial and amendment deadlines
and introduced structured-data requirements. That creates a regime break around
2024. A responsible panel uses EDGAR accepted-at time and tests eras separately.

The first prediction is campaign outcome and time to amendment. Stake size + filer
history + issuer size + initial event return is the baseline. Purpose-language deltas
must beat it; otherwise “NLP” is only rediscovering who the activist is and how much
they own.

## Program 4 — 8K-SHOCK-01: a common encoder with separate outcome heads

Form 8-K provides structured item codes for economically different shocks:

- 1.02 — material contract termination;
- 1.05 — material cybersecurity incident;
- 2.04 — triggering event or default;
- 2.05 — exit or disposal plan;
- 2.06 — material impairment;
- 4.01 — auditor change;
- 5.02 — executive transition.

The opportunity is a common point-in-time filing encoder with **item-specific**
prediction heads. Pooling all items behind one return label would erase the causal
story. Initial targets should be the next amendment/quantification, distress or
financing hazard, later impairment/restructuring, and peer/supplier spillover.

The mechanical baseline is item + size + industry + leverage + pre-event price
state. Language must add value in a later-era holdout. Amendment lineage and
mandatory-versus-voluntary context must remain explicit so a later quantified update
cannot leak into the initial disclosure.

## Program 5 — COMMENT-LABEL-01: delayed supervision, not backdated alpha

Corp Fin comment letters are appealing because they form a conversation: SEC UPLOAD,
issuer CORRESP, another round, an amendment, and completion. The timing makes them
dangerous. SEC guidance says correspondence is made public only after review is
complete and at least 20 business days have passed. The private letter date is not a
tradable timestamp.

That does not make the data useless. It makes it a **label factory**. Topic, rounds
and response latency can label filing characteristics associated with later review,
amendment or restatement. A model trained on public-at-the-time filing features and a
later comment-cycle label is honest; a return study backdated to the letter date is
not.

This changes the existing frontier rank: comment letters remain useful, but should
not be the first live event feed.

## Program 6 — SETTLE-STRESS-01: null-first market plumbing

Reg SHO threshold status and fails-to-deliver data are market-structure state, not
proof of naked short selling. Fails can arise from long or short sales. FINRA daily
short-sale volume is trade flow and is not the twice-monthly outstanding short-interest
stock. Treating either as a “squeeze probability” input without this distinction
would encode a social-media narrative, not a measurement.

A defensible study asks whether first threshold appearance, persistence, exit and
delayed FTD magnitude predict future liquidity/borrow stress or settlement
normalization after size, liquidity, volatility and corporate-action controls.
Return is a secondary null test. If threshold persistence adds nothing after those
controls, record the null and stop.

## Shared schema and evaluation contract

Every event version should carry at least:

```text
logical_event_id
source_revision_id
source_event_at
source_published_at
collector_first_seen_at
conservative_first_tradable_at
source_entity_id
issuer_id
security_id_valid_at_event
identity_mapping_method + confidence
payload_hash + rights tier
feature_cutoff
label_window + label_vintage
```

Evaluation order is fixed:

1. Clock and identity review on a hand-labeled sample.
2. Reconstruct state as of an arbitrary historical cutoff.
3. Freeze outcome, baseline, horizon and exclusion rules.
4. Beat the transparent baseline on an issuer-grouped chronological holdout.
5. Run revision-leak, delayed-clock, publicity and shuffled-identity placebos.
6. Only then inspect returns and implementability.

This ordering prevents a familiar failure: picking a price horizon that looks good,
then retrofitting an event story around it.

## Recommended build sequence

### Gate 0 — complete the H44 substrate

- Implement one callable conservative-tradable-time function for the existing SEC
  clock fixtures and have at least one research tool consume it.
- Standardize date-valid issuer/security identity on event artifacts.
- Add a machine-readable trial registry with preregistration and recorded outcome.

### Gate 1 — two 100-record reviewed samples

- BIOCAT: registry version ↔ sponsor ↔ public issuer ↔ first disclosure ↔ outcome.
- GOVCON: transaction ↔ obligation/modification ↔ recipient ↔ public parent.

The target is not a positive return. It is ≥95% reviewed identity precision, exact
version lineage and an auditable conservative clock.

### Gate 2 — outcome models

- BIOCAT: trial outcome and milestone hazard.
- GOVCON: backlog/revenue revision.
- OWNERSHIP: campaign outcome and amendment hazard.
- 8K-SHOCK: item-specific operational outcomes.

### Gate 3 — propagation and market labels

Only programs that pass Gate 2 can spawn peer, supplier, competitor and return
studies. Combine programs only after each earns independent holdout evidence.

## Source register

Primary and official sources used for the design:

- [SEC beneficial-ownership modernization final rule](https://www.sec.gov/rules-regulations/2023/10/33-11180)
- [SEC Form 8-K compliance and disclosure interpretations](https://www.sec.gov/rules-regulations/staff-guidance/compliance-disclosure-interpretations/exchange-act-form-8-k)
- [SEC guidance for searching EDGAR correspondence](https://www.sec.gov/search-filings/edgar-search-assistance/how-search-edgar-correspondence)
- [SEC Regulation SHO investor bulletin](https://www.sec.gov/investor/pubs/regsho.htm)
- [FINRA short-sale volume catalog](https://www.finra.org/finra-data/browse-catalog/short-sale-volume)
- [ClinicalTrials.gov API v2](https://clinicaltrials.gov/data-api/api)
- [ClinicalTrials.gov record-editing and posting guidance](https://clinicaltrials.gov/submit-studies/prs-help/how-edit-record)
- [openFDA Drugs@FDA endpoint](https://open.fda.gov/apis/drug/drugsfda/how-to-use-the-endpoint/)
- [USAspending API v2 endpoint documentation](https://api.usaspending.gov/docs/endpoints)
- [USAspending data sources and download guide](https://www.usaspending.gov/data/data-sources-download.pdf)
- [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)

Research precedents were used only to establish that these are legitimate empirical
domains, not as MONAD results: a large trial-outcome event study, an open clinical
trial outcome benchmark, and recent government-contract event studies all motivate
independent point-in-time replication. None is evidence that these programs will
produce investable alpha here.

## Decision

Promote BIOCAT-01 and GOVCON-01 to the next data-contract pass. Keep OWNERSHIP-01 and
8K-SHOCK-01 immediately behind them. Reclassify comment letters as delayed labels.
Require a guarded null-first design for settlement stress. Do not build another broad
opaque “news sentiment” agent until these source-specific clocks, identities,
baselines and outcome labels work independently.
