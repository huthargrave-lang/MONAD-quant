# CA-FAILFRAME — 2023 merger-termination review seed

**Status:** 14 unique, content-reviewed 2023 terminations from one frozen SEC
full-text query; candidate-universe and censored controls remain open<br>
**Parent:** [CA-FUND](CA_FUND_reviewed_seed.md)<br>
**Spec:** `docs/research/data/ca_failframe_review_spec.json`<br>
**Fixture:** `docs/research/data/ca_failframe_reviewed_seed.json`

## Question

Can failed actions be added by searching SEC filings for an explicit termination
phrase and treating every result as one failed deal?

No. The phrase is useful for a reviewed schema seed, but the search output needs
three collapses:

| Stage | Count |
|---|---:|
| SEC document hits | 31 |
| Unique SEC submissions | 23 |
| Primary in-year termination sources | 14 |
| Counterparty or amendment duplicates | 4 |
| Excluded false/wrong-period matches | 5 |
| Unique reviewed 2023 deal terminations | 14 |

The frozen query is:

```text
"mutually agreed to terminate" "merger agreement"
Form 8-K, filed 2023-01-01 through 2023-12-31
```

The search response, every source accession, exact acceptance second, normalized
content marker, and SHA-256 are frozen. Raw search and filing bytes remain outside
the repository.

## Why five submissions were excluded

Full-text search matched:

- a 2023 Dominion filing that described a transaction terminated in 2021;
- a 2023 filing that repeated a November 2022 bank-merger termination;
- an employment-agreement termination near merger language;
- a collaboration/license termination near merger language; and
- a forward-purchase transaction termination while the business combination
  remained separate.

Filing date is not event date, and a phrase near `merger agreement` does not prove
that the merger itself terminated. Content-level event identity is mandatory.

## Why four submissions were duplicates

Amedisys/Option Care, Diversified Healthcare/Office Properties, and Great
Ajax/Ellington each produced counterparty filings for one event. Artemis later
amended its original 8-K. Treating submissions as independent outcomes would
double-count three deals and count one correction as a new failure.

The natural modeling unit is the deal chain, clustered across parties,
accessions, amendments, and exhibits.

## Failure mechanisms are heterogeneous

The 14 reviewed deals contain:

- four explicit regulatory or market-condition cases;
- four SPAC deadline/liquidation reason cases;
- one superior-proposal switch;
- one litigation settlement;
- one structured mutual settlement; and
- three mutual terminations whose selected source does not establish a more
  specific reason.

Examples show why a single `failed=1` label throws away economically important
state:

- **First Horizon/TD:** regulatory-timing uncertainty; TD agreed to USD 200
  million plus a USD 25 million fee reimbursement.
- **Adobe/Figma:** no clear regulatory path in Europe/UK; Adobe agreed to a USD
  1 billion termination payment.
- **Amedisys/Option Care:** Amedisys paid USD 106 million before entering a
  competing UnitedHealth agreement.
- **Great Ajax/Ellington:** USD 5 million cash plus an USD 11 million stock
  purchase rather than one simple fee.
- **Malacca/Indiev** and **Industrial Tech/NEXT:** deal termination flows into
  SPAC liquidation and estimated trust redemptions.
- **10X III/Sparks:** the termination is part of a litigation settlement and
  the reimbursement amount is not disclosed in the public text.

Termination payments belong to the deal/company state. They are not direct
per-share merger consideration and cannot be added to shareholder wealth without
capital structure and price evidence.

## The failure clock also lags

Only seven primary sources were accepted on the event date. The other seven were
accepted one to five calendar days later:

| Filing-day lag from date-only event | Deals |
|---:|---:|
| 0 | 7 |
| 1 | 3 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |

The event labels provide dates, not intraday times, so the artifact does not
invent midnight timestamps or exact hour lags. Predictive features may only use
the filing acceptance clock unless a separate contemporaneous source is frozen.

## What this seed can and cannot do

It can:

- exercise termination, duplicate, exclusion, reason, settlement, liquidation,
  and observation-clock schemas;
- provide exact reviewed examples for future extraction tests; and
- seed case studies of regulatory, market, competing-bid, litigation, and SPAC
  failure paths.

It cannot estimate a deal's probability of failure. The query starts from known
termination language, so it excludes completed, pending, delayed, unilaterally
terminated, vote-rejected, expired, and silently abandoned deals. It is
conditioned on outcome availability and on one phrase family.

## Next node

Build the cohort forward from contemporaneous **deal announcements**, not
backward from termination outcomes:

1. freeze announcement-time parties, terms, outside dates, conditions, and
   observation clocks;
2. follow amendments, votes, regulatory milestones, competing bids, litigation,
   completion, termination, and censoring;
3. include unresolved deals at a fixed horizon;
4. group by deal and time-split before modeling; and
5. benchmark transparent survival and logistic models before any text model.

That is the first frame on which a public deal-risk model could make an honest
out-of-sample claim.

## Reproduce

```bash
venv/bin/python tools/sec_failed_action_lab.py build
venv/bin/python -m unittest tests.test_sec_failed_action_lab -v
```
