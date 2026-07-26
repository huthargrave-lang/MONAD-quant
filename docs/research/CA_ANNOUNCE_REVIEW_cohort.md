# CA-ANNOUNCE-REVIEW — clock-joined January cohort with right-censor mass

**Status:** 11 deals with exact announcement clocks; 2 right-censored at
2025-01-01; raw filing bytes still unvalidated<br>
**Parents:** [CA-ANNOUNCE-POP](CA_ANNOUNCE_POP_discovery.md),
[CA-ANNOUNCE cohort seed](CA_ANNOUNCE_cohort_seed.md)<br>
**Spec:** `docs/research/data/ca_announce_population_review_spec.json`<br>
**Artifact:** `docs/research/data/ca_announce_population_reviewed.json`<br>
**Tool:** `tools/sec_announce_review_lab.py`<br>
**Research graph:** H74, E116, F137

## Question

Can the January announcement discovery frame become a deal-level cohort that
keeps unresolved observations right-censored at a fixed horizon?

## Result

| Field | Value |
|---|---:|
| Classified submissions | 17 |
| Primary deals | 11 |
| Exact announcement clocks | 11 / 11 |
| close_as_announced | 8 |
| negative_termination | 1 |
| censored at 2025-01-01 | 2 |
| Open at early censor 2023-04-01 | 5 |
| Raw content hash validated | no |

```text
resolved closes: Albireo, CinCor, Duck Creek, Evoqua, IAA, Umpqua, Concert, DCP
negative term:   First Guaranty (also in CA-FAILFRAME)
censored:        WBA Jan-2023 agreement, Orchestra Jan-2023 agreement
excluded:        Kimco OP, HealthLynked, Electro Sensors
```

Censored deals have **no** target-CIK Form 25 / 8-K item 2.01 / 1.02 signal on
or before 2025-01-01. WBA’s first later 1.02 is 2025-04-25; Orchestra’s is
2025-10-28. Their January agreement identity vs later 1.02 events is still
content-unvalidated.

## Why this unblocks survival work

The schema seed had `zero_censored_blocks_survival_claim=true`. This reviewed
frame flips that flag. Five of eleven deals were still open at a 90-day early
censor (2023-04-01), so right-censor mass is not a corner case.

## Corrections vs the provisional v1 labels

- DCP is the target primary; Phillips 66 is counterparty (was reversed).
- Several completion dates aligned to the first Form 25-NSE / item 2.01 signal
  (IAA 2023-03-21, Concert 2023-03-06, DCP 2023-06-15).
- Announcement clocks are data.sec.gov acceptance times, not file dates.

## Kill criteria

- treating censored WBA/Orchestra rows as confirmed classic public-target mergers
  before content hashes;
- claiming failure rates from this 11-deal non-population sample;
- dropping censored rows to make logistic models look better;
- pretending raw EDGAR bytes were validated.

## Next node

1. Obtain raw filing bytes and hash-validate announcement + resolution markers.
2. Expand beyond the hand-picked 11 into the remaining classic Item 1.01 queue.
3. Attach market-implied snapshots on cash closes.
4. Run deal-grouped logistic / survival baselines.

## Reproduce

```bash
venv/bin/python tools/sec_announce_review_lab.py build
venv/bin/python -m unittest tests.test_sec_announce_review_lab -v
```
