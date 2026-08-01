# CA-FUND — reviewed fund-exit rights seed

**Status:** all five structurally missing CA-CLOCK100B fund chains recovered;
payment, successor-price, and failure strata remain open<br>
**Parent:** [CA-NONCASH](CA_NONCASH_reviewed_seed.md)<br>
**Spec:** `docs/research/data/ca_fund_review_spec.json`<br>
**Fixture:** `docs/research/data/ca_fund_reviewed_seed.json`

## Question

Were the five CA-CLOCK100B chains with no corporate-form candidate scrape
failures, or do fund exits require a different evidence and rights model?

They require a different model. All five are recoverable, but they resolve into
three different mechanisms:

| Ticker | Structure | Reviewed state | Holder right |
|---|---|---|---|
| NKG | closed-end fund | successor merger | 0.85425383 NZF shares per NKG share |
| NIQ | closed-end term fund | completed liquidation | USD 12.4082 plus one liquidating-trust unit initially valued at USD 0.5768 |
| NSL | closed-end fund | successor merger | 0.58066176 JFR shares per NSL share |
| NZRO | ETF | scheduled liquidation and confirmed trading cessation | cash equal to NAV; amount and payment confirmation absent |
| EDI | closed-end fund | successor merger | 1.153733 EDF shares per EDI share |

Three labels come directly from exchange Form 25 exhibits. NIQ comes from an
issuer shareholder report on Form N-CSR, and NZRO comes from a prospectus
supplement on Form 497. Raw submissions remain outside the repository; the
fixture retains exact accessions, acceptance seconds, hashes, official URLs, and
validated content markers.

## Why the corporate-form join missed them

The original join looked for nearby issuer 8-K, 6-K, tender, reporting-exit, and
selected fund forms. That is insufficient for funds:

- a prospectus supplement can announce an ETF's liquidation schedule;
- an annual shareholder report can establish completed term-fund distributions;
- an exchange reason exhibit can be the most exact source for a closed-end fund's
  NAV-based successor ratio;
- acquiring-fund filings may sit under a different CIK; and
- legal completion, trading cessation, cash payment, and liquidation-trust
  realization are separate clocks.

Adding every fund form to one corporate query would not solve the semantic
problem. The collector must resolve series/class identity, target and acquiring
funds, consideration legs, and source role.

## Source-clock reversals

The two issuer sources sit on opposite sides of Form 25:

- **NZRO:** the Form 497 schedule arrived 31d 1:57:33 before Nasdaq's Form 25.
  It established the expected October 16 last-trading date and cash-at-NAV
  formula, but it did not know the later NAV or prove cash receipt.
- **NIQ:** NYSE Form 25 arrived June 30 at 15:24:14 ET. The N-CSR that
  retrospectively specified the June 30 liquidation legs arrived 33d 20:49:08
  later. It proved a USD 12.4082 cash distribution plus one trust unit with
  initial NAV USD 0.5768.

The three successor ratios are established in the exchange source itself. No
fixed issuer-before-exchange or exchange-before-issuer rule survives.

## Rights cannot be flattened to one return

The three mergers create successor-share positions, not cash exits. Their
terminal wealth requires successor prices and any fractional-share treatment.

NIQ's USD 12.9850 close-date value is also not an immediate all-cash payment.
USD 12.4082 was cash; USD 0.5768 was the initial NAV of one non-transferable
liquidating-trust unit. The issuer said the timing of a final trust distribution
could not be predicted. The validator reconciles the two initial legs but forces
the trust's final timing to stay unresolved.

NZRO is weaker still: the advance source promises cash equal to NAV on or about
October 20, but supplies neither an amount nor payment confirmation. The
artifact labels the right and cessation, not a completed terminal cash amount.

## Official-source contradiction

NKG's NYSE exhibit says the securities came to evidence replacement rights on
April 17, 2023 and that trading was suspended that day, but its intervening
merger sentence says April 17, **2027**. The 0.85425383 ratio is unambiguous, but
the legal-date sentence is internally inconsistent. The reviewed row preserves
that conflict rather than silently correcting official text.

This is a concrete reason to store claim-level evidence quality even when the
source is official.

## Limitations

- Five hand-reviewed cases establish schema coverage, not fund-exit frequencies.
- The three successor cases do not yet join successor prices or fractional cash.
- NIQ's trust needs later NAV, disposition, distribution, and tax observations.
- NZRO still needs an exact liquidation NAV and payment confirmation.
- The source graph does not yet resolve acquiring-fund filings or series/class
  identifiers automatically.
- No spread, return, alpha, or predictive model is measured.

## Verdict

The fund-specific recovery closes the five-case missing-source gap while
rejecting the idea that every delisting has one terminal cash label. It adds
three exact successor ratios, one cash-plus-trust liquidation, one
cash-at-NAV schedule, an issuer/exchange clock reversal in both directions, and
an explicit official-source contradiction.

The next valuable node is not a larger same-shaped scrape. It is a
series-aware fund source graph plus payment/successor valuation. The first
failed-action child, [CA-FAILFRAME](CA_FAILFRAME_termination_seed.md), now adds
14 reviewed termination chains while making explicit that an outcome-conditioned
query is not yet a predictive cohort.

## Reproduce

```bash
venv/bin/python tools/sec_fund_exit_lab.py build
venv/bin/python -m unittest tests.test_sec_fund_exit_lab -v
```
