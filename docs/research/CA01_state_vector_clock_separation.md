# CA-01 — corporate actions as parallel state vectors, and what an effective-date join costs

**Status:** architecture fixture. Three hand-selected action chains, 27 assertions. Not
population evidence, not alpha evidence. This document exists because
[`F114`](../../RESEARCH_WEB.md) states its figures and cited no document; every one of
them is recoverable from `docs/research/data/ca01_sec_state_machine_fixture.json`, and
that reconciliation is recorded here along with one consequence F114 does not state.

---

## The shape of the fixture

A corporate action is not one status moving through one lifecycle. CA-01 models it as
**parallel dimensions**, each carrying its own state, and each assertion separating two
clocks:

* `effective_on` (+ optional `effective_at`) — the **event clock**: when the thing
  happened.
* `observed_at` — the **decision clock**: when EDGAR accepted the source that makes it
  knowable.

Six dimensions appear across the three chains: `transaction`, `listing`, `reporting`,
`security_rights`, `bankruptcy`, `disclosure`.

| chain | symbol | assertions |
|---|---|---|
| `cash-merger:TWTR:2022-10-27` | TWTR | 9 |
| `cash-merger:ATVI:2023-10-13` | ATVI | 7 |
| `bankruptcy-cancellation:BBBYQ:2023-09-29` | BBBYQ | 11 |
| | **total** | **27** |

Each assertion also carries a `knowledge_role`: `predictive_status`,
`post_effective_confirmation`, `outcome_label`, or `administrative_status`. That field is
what keeps a retrospective confirmation from being used as a forward-looking feature.

---

## Source order is not universal

F114's central claim, verified from the fixture's `observed_at` values:

| chain | ordering | gap |
|---|---|---|
| TWTR | exchange **Form 25-NSE** precedes the issuer completion **8-K** | **11:51:17** |
| ATVI | issuer **completion** precedes the exchange **Form 25-NSE** | **00:26:14** |

Same action family (`cash_merger`), opposite order. A pipeline that assumes "the exchange
files first" or "the issuer files first" is right about one of these and wrong about the
other, and the error is not a rounding artifact — on TWTR it is most of a trading day.

The BBBY chain adds the third pattern: **retrospective confirmation**. Its
`trading_suspended` assertion is effective 2023-05-03 but only observable 2023-07-10, when
the Form 25 was filed — **68 calendar days** later.

---

## What an effective-date join actually costs

F114 says an effective-date join "leaks information". Measured across all 27 assertions,
it is worse than that: **the error runs in both directions.**

| relationship | count | meaning under an effective-date join |
|---|---:|---|
| `observed_at` **after** `effective_on` | 7 | **leak** — the fact appears before its source existed |
| `observed_at` **before** `effective_on` | 4 | **suppression** — a knowable, already-filed fact is hidden |
| same day | 16 | no error |

**The leaks**, worst first:

| symbol | state | leak | knowledge_role |
|---|---|---:|---|
| BBBYQ | `trading_suspended` | **68 d** | post_effective_confirmation |
| BBBYQ | `plan_confirmed` | 6 d | predictive_status |
| TWTR | `shareholder_approved` | 1 d | predictive_status |
| TWTR | `completed` | 1 d | post_effective_confirmation |
| TWTR | `cash_claim_54_20_usd` | 1 d | outcome_label |
| BBBYQ | `chapter11_petitioned` | 1 d | predictive_status |
| BBBYQ | `delisting_determined_no_appeal` | 1 d | predictive_status |

**The suppressions** — forward-looking assertions, filed before they take effect:

| symbol | state | filed ahead by | knowledge_role |
|---|---|---:|---|
| TWTR | `removal_scheduled` | 11 d | administrative_status |
| BBBYQ | `removal_scheduled` | 10 d | administrative_status |
| BBBYQ | `cancellation_expected_on_plan_effective_date` | 10 d | predictive_status |
| BBBYQ | `suspension_scheduled` | 8 d | predictive_status |

This half matters for a different reason than the leak. A leak inflates backtest
performance and is caught by the usual suspicion of good results. A suppression *hides*
information the market genuinely had — scheduled removals and expected cancellations were
public one to two weeks ahead — and makes a strategy look worse than it was, or removes a
signal from consideration entirely. It fails silently.

Note also that both failure modes hit `predictive_status` assertions, so neither is
confined to retrospective bookkeeping.

---

## Limits

Three chains, chosen as architecture tests: one clean cash merger, one cash merger with
the opposite filing order, one bankruptcy with a retrospective confirmation. They are
deliberately unrepresentative — the point was to find orderings a single-status model
cannot express, not to estimate how often each occurs. Nothing here supports a frequency
claim, and the fixture's own `market_access_policy` is explicit that EDGAR acceptance is
not investor ingestion: a downstream study must still add dissemination, parsing and
next-tradable-time assumptions before any of these timestamps become executable.

`raw_documents_committed` is `false` — the fixture records assertions and their EDGAR
acceptance times, not the filings themselves.

## Guard

`tests/test_f114_state_vector_clocks.py` recomputes every figure F114 states from the
fixture, re-derives the leak/suppression census, and fails if the ordering reversal ever
stops being present — that reversal is the whole reason the state-vector model exists.
