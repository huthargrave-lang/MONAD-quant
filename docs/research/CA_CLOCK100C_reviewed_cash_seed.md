# CA-CLOCK100C — reviewed fixed-cash outcome seed

**Status:** 12 content-verified fixed-cash outcomes; deliberately not
outcome-balanced<br>
**Parent:** [CA-CLOCK100B](CA_CLOCK100B_action_chain_join.md)<br>
**Review spec:** `docs/research/data/ca_clock100c_review_spec.json`<br>
**Reviewed fixture:** `docs/research/data/ca_clock100c_reviewed_seed.json`

## Why this seed exists

CA-CLOCK100B proved that transparent phrase flags can route documents but cannot
serve as outcome labels. This seed establishes the stricter promotion contract:

1. a human selects the exact issuer submission from the frozen evidence manifest;
2. the submission must state that eligible common shares converted into a fixed
   cash right;
3. currency and per-share amount are recorded from that content;
4. exact issuer and exchange acceptance times and source-content SHA-256 are copied
   mechanically from the harvested evidence;
5. the result remains an outcome label (`predictive_for_outcome=false`), never a
   contemporaneous predictive feature;
6. raw filing content remains outside the repository.

The tool rejects missing evidence accessions, non-positive or non-finite cash,
contingent consideration, non-USD terms in this first seed, sources without
holder-conversion language, duplicate chains, and any attempt to mark a reviewed
outcome predictive.

## Reviewed chains

| Issuer | Cash/share | Issuer minus exchange | First source |
|---|---:|---:|---|
| 1Life Healthcare | $18.00 | +6:46:47 | Exchange |
| Myovant Sciences | $27.00 | −4:00:08 | Issuer |
| Cardiovascular Systems | $20.00 | −0:40:05 | Issuer |
| Sumo Logic | $12.05 | +3d 7:17:36 | Exchange |
| IVERIC bio | $40.00 | −1:02:10 | Issuer |
| Home Point Capital | $2.33 | +0:05:51 | Exchange |
| ForgeRock | $23.25 | −0:59:56 | Issuer |
| Reata Pharmaceuticals | $172.50 | +8:04:22 | Exchange |
| SciPlay | $22.95 | −0:18:23 | Issuer |
| Fiesta Restaurant Group | $8.50 | +3:11:44 | Exchange |
| New Relic | $87.00 | −0:24:47 | Issuer |
| Patriot Transportation | $16.26 | +1:05:59 | Exchange |

Positive lag means the reviewed issuer evidence arrived after exchange Form 25.
Negative means issuer evidence arrived first.

The 12 cases split **6 issuer-first / 6 exchange-first**. Eleven are within 36
hours and split 6/5; Sumo's completion 8-K arrived more than three days after Form
25, which is exactly why the content selector now preserves the nearest issuer
report on both sides of the exchange event. The 8-K immediately before Sumo's Form
25 covered shareholder approval, while the later 8-K carried the holder conversion.

The fixed cash amounts range from $2.33 to $172.50. That range is not a return
distribution; it only confirms that the schema retains exact terms instead of
normalizing economically different transactions to a binary “completed” label.

## What the equal source-order split means

The split was not selected or balanced by source order; review chose clear fixed-cash
holder-conversion evidence from the frozen seed. It is still a convenience sample,
so 6/6 is not a population estimate or hypothesis test.

It does provide a stronger falsification than automated phrase routing:

- every order comparison is backed by an exact, manually reviewed cash-conversion
  source;
- source hashes make the label reproducible from the cached official bytes;
- neither exchange-first nor issuer-first can be treated as an exceptional case;
- a date-only event table would collapse lags ranging from minutes to days and can
  leak same-day after-close evidence into an earlier decision.

This reinforces the state-machine rule: legal outcome, listing state, reporting
state, rights conversion, and disclosure observation are separate axes.

## What remains unreviewed

This seed intentionally excludes:

- stock or successor-share outcomes;
- redomiciliations and listing transfers;
- contingent value rights and mixed consideration;
- fund mergers and liquidations;
- bankruptcy cancellation, recovery, and unresolved rights;
- failed and delayed transactions;
- non-USD consideration;
- payment and successor-delivery clocks;
- inactive predecessor prices and returns.

Those exclusions prevent the easy fixed-cash cases from masquerading as an
outcome-balanced panel. CA-CLOCK100C still fails its original ≥100 diverse-chain
gate.

## Next review batches

1. **Rights-aware continuation completed:** [CA-NONCASH](CA_NONCASH_reviewed_seed.md)
   adds successor equity, fixed cash plus a contingent-value right, explicit
   bankruptcy zero, and unresolved bankruptcy labels without collapsing them into
   cash-equivalent outcomes.
2. **Funds completed:** [CA-FUND](CA_FUND_reviewed_seed.md) recovers all five
   structurally missing chains with successor, cash-plus-trust, and scheduled
   cash-at-NAV rights.
3. **Failure/delay:** extend beyond completed 2023 removals; otherwise the eventual
   model would learn only successful outcomes.

## Verdict

The content-to-label promotion contract passes on 12 fixed-cash chains. It
strengthens the source-order reversal to manually reviewed outcomes and creates a
small exact-terms benchmark for future extraction models. It does not establish an
outcome-balanced cohort, a price effect, or alpha.

## Reproduce

```bash
venv/bin/python tools/sec_action_chain_join_lab.py build-reviewed
venv/bin/python -m unittest tests.test_sec_action_chain_join_lab -v
```
