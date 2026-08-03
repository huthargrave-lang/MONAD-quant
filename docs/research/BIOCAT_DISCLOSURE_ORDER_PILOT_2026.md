# BIOCAT disclosure-order pilot: the first label is event purity

**Research node:** `H253200`

**Audit date:** 2026-08-03

**Decision:** continue disclosure-order research, but do not train a reaction
model until announcement purity, label scope, and intraday clocks are explicit.

## Executive result

Five public-issuer trials from the BIOCAT source-discovery cohort were manually
joined to an issuer disclosure and a registry-results date. This is a selected,
non-random pilot, not an edge estimate. In all five cases the issuer disclosure
preceded ClinicalTrials.gov results by 300–2,123 days (median 430 days).

That confirms the registry is normally a delayed label in these examples, but the
more important finding is that even a correctly mapped issuer event may not label
the trial named in the registry:

- Supernus trial `810P304` (`NCT02691182`, CHIME 4) is an open-label safety study.
  Its current registry record says the program stopped for lack of efficacy, but
  the issuer's 2020 announcement reported failure of the different `P302` trial
  and halted the whole SPN-810 program.
- AbbVie's exact trial release arrived seven minutes after an earnings 8-K. The
  8-K exhibit mentioned Vraylar revenue, not the trial result. Filing time alone
  would therefore assign the wrong information clock.
- The cleanest trial event, Axsome's INTERCEPT readout, opened about +5% but closed
  about -2.7% from the prior close. A daily close-to-close label reverses the sign
  of the immediate reaction.

The durable row-level record and daily price diagnostics are in
[`biocat_disclosure_order_pilot_2026.json`](data/biocat_disclosure_order_pilot_2026.json).

## Scope and method

The five records were chosen from the 25-row discovery cohort because their current
sponsors map cleanly to public issuers and a public disclosure could be located.
This selection makes the 5/5 ordering rate descriptive only. It must not be used as
an estimate of population coverage, disclosure probability, or strategy returns.

For each trial the audit:

1. matched the exact NCT ID to the issuer disclosure using the registry's
   organization study ID, trial acronym, intervention, or an explicit NCT ID;
2. retained the earliest verified public clock found in SEC acceptance metadata or
   issuer-distributed release metadata;
3. separately labeled whether the announcement describes the exact trial and what
   other information was bundled with it;
4. measured calendar days to `ResultsFirstPostDate`; and
5. inspected adjusted daily OHLC for the issuer and SPY as a diagnostic, not a
   backtest.

The search was not an exhaustive reconstruction of every conference abstract,
publication, FDA action, or wire timestamp. A production census needs a reviewed
source ledger and an explicit search-completeness flag.

## Disclosure order

| Trial | First verified issuer disclosure | Registry results | Lead | Mapping / bundle |
|---|---|---|---:|---|
| SAP302 · `NCT02447848` | 2016-08-15 07:02:26 ET, SEC 8-K | 2017-10-19 | 430d | exact trial; 8-K furnished slides and release |
| CHIME 4 · `NCT02691182` | 2020-02-25 16:40 ET, issuer release | 2024-05-16 | 1,542d | **related P302 failure** caused program halt; bundled earnings |
| INTERCEPT · `NCT04163185` | 2020-04-06 06:00 ET, issuer release | 2026-01-28 | 2,123d | exact single-trial readout |
| 3111-301-001 · `NCT03738215` | 2021-10-29 07:50 ET, issuer release | 2022-10-25 | 361d | exact trial; bundled second trial; concurrent earnings |
| SURMOUNT-4 · `NCT04660643` | 2023-07-27 06:48 ET, issuer release | 2024-05-22 | 300d | exact trial; bundled SURMOUNT-3 |

Times are Eastern daylight/standard time as applicable. Registry results expose a
date, not a time, in these derived rows. Lead is calendar-day difference between
the disclosure date and registry results date.

## Two provenance failures a flat label would hide

### A program decision is not an exact-trial outcome

Supernus announced fourth-quarter results at 16:40 ET on 2020-02-25. The release
said Phase 3 `P302` missed its primary endpoint and that the company would halt all
SPN-810 development. The selected registry record is `810P304`/CHIME 4, not P302.
Its later status reason—“The program was shut down due to a lack of efficacy”—is
therefore a program-level termination explanation triggered by a related efficacy
trial. Coding CHIME 4 itself as an efficacy failure would fabricate a label.

The [FDA's 2023 letter to Supernus](https://www.fda.gov/media/172473/download?attachment=)
then listed `NCT02691182` among four trials whose results appeared not to have been
submitted and requested prompt submission. Registry results appeared on
2024-05-16. The order is consistent with compliance-driven posting, but this pilot
does not establish that the FDA letter caused the posting.

### A same-day filing is not automatically the catalyst

AbbVie's [2021-10-29 trial release](https://news.abbvie.com/2021-10-29-AbbVies-Cariprazine-VRAYLAR-R-Met-Primary-Endpoint-in-Phase-3-Study-as-an-Adjunctive-Treatment-for-Major-Depressive-Disorder)
reported both study 3111-301-001 meeting its endpoint and 3111-302-001 missing. An
earnings 8-K was accepted at 07:42:43 ET, seven minutes before the release, but its
Exhibit 99.1 contained Vraylar sales—not the trial readout. The exact trial clock is
therefore 07:50 ET, while the stock reaction remains contaminated by earnings.

This yields two independent fields:

```text
label_scope = trial_exact | related_trial | program | regulatory_or_compliance
event_bundle = single_trial | multi_trial | earnings | financing | regulatory | other
```

Neither can be inferred safely from the current registry status.

## Daily reaction diagnostic

Adjusted daily OHLC came from Yahoo Finance through `yfinance` 1.2.0. Returns begin
at the prior close; an after-hours release uses the next session. “Excess” is the
issuer return minus SPY over the same endpoints. These figures are discovery
diagnostics with no transaction-cost, factor, beta, sector, news, or liquidity
model.

| Trial | Event session | Open gap | Close/close | 1d excess SPY | 5s excess | 20s excess |
|---|---|---:|---:|---:|---:|---:|
| SAP302 | 2016-08-15 | +0.54% | -1.61% | -1.90% | -9.42% | -10.02% |
| CHIME 4 / program halt | 2020-02-26 | -10.99% | -14.91% | -14.54% | -16.56% | -4.08% |
| INTERCEPT | 2020-04-06 | +4.96% | -2.67% | -9.39% | -1.94% | +52.45% |
| 3111-301-001 | 2021-10-29 | +2.21% | +4.56% | +4.36% | +4.86% | +6.10% |
| SURMOUNT-4 | 2023-07-27 | -0.06% | +0.31% | +0.97% | +1.38% | +25.00% |

These are not five comparable treatment effects:

- Supernus bundled earnings, a related trial failure, and a program halt during the
  COVID selloff.
- Axsome's clean positive readout had a positive opening gap and a negative close,
  while the 20-session window contains large unrelated drift.
- AbbVie bundled two trial outcomes and released alongside quarterly earnings.
- Lilly bundled two trials; its 20-session window crosses the next earnings event.

A reaction target should therefore be a microstructure object—premarket or
after-hours print, opening auction, first liquid quote, and intraday decay—not a
single daily close-to-close return. Long windows require explicit intervening-news
censoring.

## Revised research contract

The next 100-event ledger should preserve:

| Dimension | Required values |
|---|---|
| Identity | NCT, organization study ID, intervention/program, issuer and security effective at event |
| Clock | source-provided timestamp, timezone, precision, collector first-seen, executable-at |
| Mapping | exact NCT, exact organization ID/acronym, related trial, or program-only |
| Label scope | exact trial, related trial, program, regulatory/compliance |
| Bundle | single trial, multi-trial, earnings, financing, regulatory, other |
| Outcome | endpoint direction and disclosed statistics, kept separate from termination reason |
| Market target | premarket/after-hours reaction, open gap, intraday decay; daily returns only as diagnostics |
| Contamination | concurrent issuer news and intervening events with reviewed flags |

The modeling order should be:

1. predict source order and next disclosure type;
2. predict trial outcome or milestone hazard from point-in-time state;
3. test reaction only on reviewed exact-trial events, with announcement-purity
   strata and intraday data; and
4. estimate residual information at later sources only after the first-source
   clock is complete.

## New studies spawned by the pilot

1. **H13300 — Announcement-purity classifier.** Predict whether a candidate disclosure is
   exact-trial/single-event or contaminated by related trials, earnings, financing,
   or program-level language. Kill if automated extraction cannot reach at least
   95% precision on the clean stratum.
2. **Compliance-driven registry hazard.** Test whether FDA pre-notices predict
   registry results posting latency, treating the notice as a regulatory event and
   the later result as compliance behavior—not new clinical information.
3. **Gap-to-close decay.** On clean premarket catalysts, model whether the opening
   gap persists, fades, or reverses using surprise, prior expectations, float,
   liquidity, and market regime. This is distinct from predicting the trial result.
4. **Source-order census.** Manually review 100 events across positive, negative,
   terminated, and ambiguous outcomes; report search completeness, issuer mapping
   coverage, and event-purity prevalence before fitting anything.

## Decision

`H253200` survives, but its first estimand changes. The immediate deliverable is a
reviewed disclosure ledger and announcement-purity model, not a return model. The
pilot establishes that registry results can trail investable disclosure by years,
while also showing that naive exact-NCT labels and daily returns can both be wrong.
High-frequency public-market data and a contamination protocol are prerequisites
for any reaction claim.
