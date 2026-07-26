# CA-ANNOUNCE-POP — January 2023 announcement-search discovery frame

**Status:** frozen SEC full-text search discovery frame; submissions collapsed;
no deal outcomes or censor labels assigned<br>
**Parents:** [CA-ANNOUNCE cohort seed](CA_ANNOUNCE_cohort_seed.md),
[CA-FAILFRAME](CA_FAILFRAME_termination_seed.md)<br>
**Spec:** `docs/research/data/ca_announce_population_spec.json`<br>
**Artifact:** `docs/research/data/ca_announce_population_discovery.json`<br>
**Tool:** `tools/sec_announce_population_lab.py`<br>
**Research graph:** H79, E123, F247

## Question

Can we freeze a contemporaneous announcement-language SEC search and collapse it
to submissions without pretending the phrase match is already a deal cohort?

## Frozen query

```text
"entered into an Agreement and Plan of Merger"
Form 8-K
2023-01-01 through 2023-01-31
```

| Stage | Count |
|---|---:|
| Document hits | 106 |
| Unique submissions | 93 |
| Submissions with Item 1.01 | 47 |
| Submissions with Item 1.02 | 6 |
| Both 1.01 and 1.02 | 2 |
| SPAC-ish heuristic | 29 |
| Classic-ish + Item 1.01 | 31 |

A provisional-then-clock-joined review
([CA-ANNOUNCE-REVIEW](CA_ANNOUNCE_REVIEW_cohort.md)) promotes 11 primary deals
with exact announcement acceptance times. Two remain right-censored at
2025-01-01; five were still open at a 2023-04-01 early censor. Raw EDGAR byte
hashes remain open.

Raw response sha256:

```text
714ce403c957ccad585994e5d913ed7ac2a847568d96ff046d213c1ac425cea4
```

Raw bytes stay in `/private/tmp/monad-merger-announcement-search-2023-01.json`
and are not committed.

## Structural result

Phrase hits are **not** announcement events.

Only 47/93 submissions carry Item 1.01. The other matches include later status
updates, completions, and filings that merely quote the merger agreement. This
extends F127: documents ≠ submissions ≠ deals, and phrase presence ≠ entry
event.

SPAC-ish heuristics (SIC 6770 / “Acquisition Corp” stems) tag 27 submissions.
They are discovery strata, not labels.

No outcomes are assigned. The artifact explicitly keeps
`right_censor_population_still_open=true`.

## Why this still matters

CA-FAILFRAME entered from termination language. This frame enters from
announcement language and preserves the unresolved mass for later review. It is
the first machine-checked population gate for H79, not the finished cohort.

## Next node

1. Content-review the 31 classic-ish Item 1.01 submissions into deal IDs
   (provisional 9-primary seed exists; raw archives.sec.gov bytes are currently
   403 in this environment — acceptance clocks can still come from
   data.sec.gov).
2. Hash-validate provisional labels once raw filings are obtainable.
3. Follow each deal to completion / higher-bid / negative termination / censor
   at 2025-01-01 — **force inclusion of unresolved deals**.
4. Only then wire calibrated market-implied and survival baselines.

## Reproduce

```bash
# requires the frozen local search response
venv/bin/python tools/sec_announce_population_lab.py build
venv/bin/python -m unittest tests.test_ca_announce_next_labs -v
```
