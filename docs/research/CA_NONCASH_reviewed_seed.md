# CA-NONCASH — reviewed successor, contingent, and bankruptcy seed

**Status:** six manually reviewed non-fixed-cash/right-state chains; the
[CA-FUND](CA_FUND_reviewed_seed.md) child closes the five missing fund chains;
failure strata remain open<br>
**Parent:** [CA-CLOCK100C](CA_CLOCK100C_reviewed_cash_seed.md)<br>
**Spec:** `docs/research/data/ca_noncash_review_spec.json`<br>
**Fixture:** `docs/research/data/ca_noncash_reviewed_seed.json`

## Question

Can the fixed-cash promotion contract preserve successor ratios, contingent rights,
listing continuity, explicit bankruptcy zero, and unresolved bankruptcy without
flattening them into one terminal-value field?

Yes on six seed chains:

| Issuer | Outcome | Reviewed rights |
|---|---|---|
| CRH | successor/listing conversion | 1 NYSE ordinary share for an ADS that represented 1 ordinary share; ticker CRH continues |
| Ambrx | successor/redomiciliation | 1 NewCo common share per old ADS; ticker AMAM continues |
| Incannex | successor/redomiciliation | 1 Delaware common share per 4 old ADSs; ticker IXHL continues |
| Pardes | cash plus contingent right | $2.13 cash plus 1 non-tradeable CVR per share |
| RVL Pharmaceuticals | bankruptcy zero confirmed | explicit no recovery for ordinary shares/share-based instruments |
| Venator | bankruptcy unresolved | Chapter 11 and possible equity cancellation, but no final recovery or zero in the reviewed source |

Every label has an exact official-source accession, acceptance second, content hash,
manual claim, rights-specific terms, and `predictive_for_outcome=false`.

## Source clocks

The batch is not selected by order and splits four issuer-first/two exchange-first:

- **CRH:** the earliest reviewed 6-K establishing the completed primary-listing
  transition and ADS-to-ordinary conversion arrived at `06:43:16 ET`; Form 25
  arrived at `10:53:29 ET`. Issuer leads by 4:10:13.
- **Ambrx:** successor/redomiciliation 8-K leads Form 25 by 9:36:59.
- **Pardes:** cash-plus-CVR completion 8-K leads by 19:15.
- **Venator:** Chapter 11 6-K leads by 24:44:35.
- **Incannex:** Form 25 leads the successor/redomiciliation 8-K by 24:31:18.
- **RVL:** Form 25 leads the later explicit no-recovery 8-K by 7d 7:18:48.

CRH also demonstrates a subtle clock rule: several same-day 6-Ks repeat or elaborate
the listing transition. The reviewed clock must use the earliest source that
establishes the claimed fact, not whichever duplicate happens to contain the easiest
paragraph to quote.

## The bankruptcy distinction

Venator and RVL are the most important pair:

- Venator's May 18 6-K disclosed Chapter 11 and contemplated restructuring or
  cancellation of existing equity. That establishes bankruptcy risk and possible
  rights impairment, not a numeric common-share value. Its terminal value remains
  `null`.
- RVL's November 27 8-K said RVL plc retained substantially no assets or operations
  and its anticipated wind-up would result in **no recovery** for ordinary-share and
  other share-based holders. That supports explicit USD `0.00`.

The validator rejects any attempt to replace Venator's `null` with `0.00`. This is
the population-scale version of CA-00/CA-01's BBBY correction: cancellation,
delisting, or bankruptcy alone does not prove zero, while issuer-specific
no-recovery evidence can.

## Rights are legs, not labels

The successor cases preserve old and new units:

- CRH's old ADS represented one ordinary share and was exchanged into the ordinary
  share it represented;
- one Ambrx ADS represented seven ordinary shares, each converting into one-seventh
  of a NewCo common share, so the ADS-level ratio is one-for-one;
- four Incannex ADSs converted into one Delaware common share.

Pardes keeps the fixed cash and one non-tradeable CVR as separate consideration
legs. The CVR is not assigned zero merely because it is contingent or
non-tradeable, and it cannot be pooled with the 12 fixed-cash-only cases until its
payment states are modeled.

## Limitations

- Six hand-reviewed chains are schema tests, not outcome frequencies.
- The successor labels do not yet join successor prices or fractional-share cash.
- The Pardes CVR does not yet have milestone, expiration, or payment observations.
- RVL's zero is an issuer statement about no recovery; broker payment/position
  cleanup is a separate state.
- Venator needs later plan/effective-date sources outside the immediate join window.
- Fund exits are covered by the five-case [CA-FUND](CA_FUND_reviewed_seed.md)
  child; failed/delayed transactions are still absent.
- No return, spread, price, or prediction is measured.

## Verdict

The rights-aware promotion schema passes across four non-fixed-cash outcome types.
It preserves successor ratios, contingent consideration, explicit zero, and
unresolved bankruptcy while retaining exact observation clocks. CA-NONCASH does not
complete the 100-chain outcome-balanced gate; it proves the ledger can represent the
hard cases without inventing terminal wealth.

The fund continuation adds a second important distinction: cash at NAV may be a
future formula, and a liquidating-trust unit is a separate, illiquid leg rather
than cash at its initial NAV.

## Reproduce

```bash
venv/bin/python tools/sec_action_chain_join_lab.py build-diverse-reviewed
venv/bin/python -m unittest tests.test_sec_action_chain_join_lab -v
```
