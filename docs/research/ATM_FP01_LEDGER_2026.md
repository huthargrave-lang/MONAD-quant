# ATM-FP-01: reviewed utilization-ledger seed

**Date:** 2026-08-04
**Status:** implemented schema seed; not a population, model, or return claim
**Tool:** `tools/atm_424b5_lab.py --build-ledger`
**Reviewed seed:** `data/atm_fp01_gold_seed.json`
**Frozen artifact:** `data/atm_fp01_gold_ledger.json`

## Decision

Proceed from phrase-level ATM discovery to a reviewed, append-only program ledger.
The first fixture proves the clocks, program identities, transitions, labels, and
SQLite read model needed by the future-utilization study. It does **not** estimate a
utilization rate or train a model: three issuers are a schema test, not a population.

The prediction target remains next-period utilization. A prospectus, remaining
capacity, or active agreement is a feature available at its public clock. Shares and
proceeds later disclosed for a reporting interval are labels available only after the
later filing. They are never backdated to estimated execution days.

## Reviewed cases

| Issuer | Program state | Reviewed outcome | Clock treatment |
|---|---|---|---|
| Apple Hospitality REIT (`APLE`) | Active; $500M remaining at 2024-09-30 | Explicitly zero shares sold in 2024Q3 and YTD | Exhibit filing date only; conservatively tradable next session |
| Ainos (`AIMD`) | H.C. Wainwright agreement active | 262,383 shares and $719,358 net proceeds in 2025H1 | Exact EDGAR acceptance; label available next session |
| Adial Pharmaceuticals (`ADIL`) | H.C. Wainwright agreement terminated and replaced by A.G.P. | 2,348,520 shares and about $4M net proceeds since inception | Exact EDGAR acceptance; cumulative label quarantined from quarter training |

These cases intentionally cover a positive period label, a zero period label, and a
program supersession. Adial's disclosed sales cover April 2024 through July 2025.
Without an earlier cumulative observation, allocating that total to individual
quarters would invent labels. The fixture therefore sets `quarter_trainable=false`.

## Source findings

Apple Hospitality states that it had $500 million remaining under its ATM program at
September 30, 2024 and sold no shares under the current or prior program during the
three- and nine-month periods. The same filing reports acquisitions, capex, liquidity,
debt, and repurchases, illustrating why active capacity alone is not financing
pressure.

Ainos reports an agreement entered May 31, 2024, a prospectus amount of $1,840,350,
and 262,383 shares sold for $719,358 net through June 30, 2025. Its filing also shows
why security normalization is required: share counts were retroactively adjusted for
a reverse split.

Adial reports a clean state transition: its April 2024 Wainwright agreement terminated
effective July 31, 2025 after cumulative sales, while an August 2025 A.G.P. agreement
replaced it with up to $4,983,000 available under the Form S-3 I.B.6 limitation. A
mutable issuer-level `atm_active` flag would erase this history; separate program IDs
preserve it.

Primary sources:

- [Apple Hospitality 2024Q3 exhibit](https://www.sec.gov/Archives/edgar/data/1418121/000095017024120710/aple-ex99_1.htm)
- [Ainos 2025Q2 Form 10-Q](https://www.sec.gov/Archives/edgar/data/1014763/000149315225011908/form10-q.htm)
- [Ainos filing detail and acceptance clock](https://www.sec.gov/Archives/edgar/data/1014763/000149315225011908/0001493152-25-011908-index.html)
- [Adial replacement and termination Form 8-K](https://www.sec.gov/Archives/edgar/data/1513525/000121390025070671/ea0251183-8k_adial.htm)
- [Adial filing detail and acceptance clock](https://www.sec.gov/Archives/edgar/data/1513525/000121390025070671/0001213900-25-070671-index.html)
- [SEC Form S-3 General Instruction I.B.6](https://www.sec.gov/files/forms-3.pdf)
- [SEC EDGAR API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)

## Ledger contract

### Identity

Every program belongs to a CIK-scoped issuer and an explicit security ID. Current
tickers are retained only with an identity-quality flag; the seed does not claim a
complete effective-dated security master.

### Sources and clocks

Each source stores:

- accession, form, exact document URL, and filing date;
- exact `accepted_at` when reviewed from EDGAR filing detail;
- a `source_time_quality` distinguishing exact acceptance from date-only evidence;
- `conservative_tradable_at`, never earlier than acceptance;
- reviewed excerpt, source span, and excerpt hash;
- `raw_content_hash_validated=false` because raw EDGAR bytes are not committed.

Date-only evidence is conservatively moved to the next regular session. This is
deliberately stricter than assuming a midnight or pre-open clock.

### Programs and assertions

Programs are versioned economic objects, not issuer flags. They carry agent,
agreement date and quality, stated capacity, I.B.6 status, and an optional
`supersedes_program_id`. Append-only assertions currently represent program status
and remaining capacity at an effective date.

The next expansion should add amendment, suspension, exhaustion, prospectus
withdrawal, forward-sale pricing, forward settlement, and cash receipt as distinct
assertion types. They should not be collapsed into one utilization flag.

### Utilization labels

Every label has a reporting interval and disclosure clock. The validator enforces:

1. the period ends before the filing date;
2. `label_available_at` comes from the source's conservative tradable clock;
3. all outcome fields have `predictive_features_allowed=false`;
4. cumulative labels cannot be marked quarter-trainable;
5. sales, proceeds, prices, and capacity cannot be negative;
6. missing gross proceeds or weighted-average price remain null rather than inferred.

## SQLite projection

The JSON fixture is authoritative. The tool optionally creates a disposable SQLite
read model outside the repository with tables for issuers, sources, programs,
assertions, and utilization labels. Two views are provided:

- `latest_program_status` resolves the latest status assertion per program;
- `quarter_label_outcomes` excludes cumulative/non-trainable labels.

The builder refuses to overwrite an existing database. This prevents a convenient
read model from becoming hidden mutable evidence.

Reproduce with a fresh database path:

```bash
venv/bin/python tools/atm_424b5_lab.py \
  --build-ledger \
  --ledger-db /tmp/monad-atm-fp01-new.sqlite3
```

The frozen seed currently produces three issuers, four programs, five assertions,
three labels, two quarter-trainable interval labels, two exact clocks, and one
date-only clock.

## Next population build

The next useful unit is not another handpicked issuer; it is a deterministic discovery
frame followed by blinded review:

1. Freeze all ATM-related 8-K, 424B5, 10-Q, and 10-K candidate accessions for a fixed
   filing window before reviewing outcomes.
2. Assign candidates into program-start, amendment, status, utilization, termination,
   false-positive, and duplicate-source roles.
3. Resolve program identity within CIK before constructing issuer-period rows.
4. Difference cumulative disclosures only when compatible consecutive observations
   exist; otherwise preserve them as cumulative and non-trainable.
5. Add point-in-time cash, burn, debt, capex, float, market cap, and ADV features using
   a feature cutoff strictly before each outcome period.
6. Hold out entire issuers and later calendar periods. Compare against last utilization,
   capacity, size, industry, volatility, and issuance-propensity baselines.

The first scale gate should be 50 issuers with at least two consecutive reviewed
disclosures. That is large enough to expose program-identity and cumulative-difference
failures while still permitting complete human audit. Model fitting should remain
closed until reviewed program precision reaches 95% and label coverage/missingness are
reported.

## What this establishes—and what it does not

Established:

- an executable, append-only ATM program and utilization-label contract;
- explicit clock quality and conservative availability;
- program termination/replacement without history loss;
- mechanical quarantine of cumulative labels;
- a rebuildable SQLite surface suitable for later UI/API work.

Not established:

- ATM prevalence or utilization frequency;
- parser precision on an unbiased filing population;
- a relationship between financing pressure and future utilization;
- a relationship between ATM use and returns;
- production-grade security-master or raw-document integrity.

The result is infrastructure evidence. Its value is that the next population study can
fail honestly instead of succeeding on backdated outcomes or collapsed program states.
