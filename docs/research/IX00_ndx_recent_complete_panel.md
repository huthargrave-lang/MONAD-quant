# IX-00 — recent complete Nasdaq-100 annual-reconstitution panel

**Status:** exploratory. Two batches, eighteen securities, no inference and no tradable
edge claimed. This document exists because [`F111`](../../RESEARCH_WEB.md) states twelve
figures and cited no document — the numbers were recoverable, and this records where each
one comes from and how the panel was assembled.

**Scope of this write-up.** Nothing here is a new measurement. Every figure below is read
from artifacts already committed under `docs/research/data/`, and the arithmetic relating
them is re-derived and checked. Raw vendor bytes are deliberately not committed (see
"Provenance"), so the panel cannot be regenerated offline — it can only be *reconciled*,
which is what this document and `tests/test_f111_ndx_panel_figures.py` do.

---

## What the panel is

The Nasdaq-100 is reconstituted annually in December. For each event batch the study
measures four windows against QQQ, security-weighted within each side:

| window | meaning |
|---|---|
| `announcement_close_to_first_open_relative` | announcement close → next tradable open |
| `first_open_to_implementation_close_relative` | first tradable open → implementation-session close |
| `implementation_close_to_effective_open_relative` | implementation close → effective-session open |
| `post_implementation_{1,5,20,60}_sessions_relative` | drift after the event completes |

plus `implementation_volume_ratio_to_prior_20d_median`, the implementation session's
whole-day volume against the security's own prior 20-day median.

### Batches

| batch | artifact | coverage | in panel |
|---|---|---|---|
| Dec 2024 | `ix00_ndx_december2024_event_replication.json` | 6 of 6 events | ✅ |
| Dec 2025 | `ix00_ndx_december2025_event_replication.json` | 12 of 12 events | ✅ |
| Dec 2022 | `ix00_ndx_december2022_partial_diagnostic.json` | 12 of 13 — **SPLK missing** | ❌ diagnostic only |
| Dec 2023 | `ix00_ndx_2023_revision_fixture.json` | list revised post-Seagen | ❌ needs revision clocks |

The 2022 batch names its deletion group `observed_deletions` rather than `deletions` —
a deliberate schema signal that the set is incomplete, so it cannot be silently pooled.

---

## The pooled figures

Security-weighted across the two complete batches (n = 3 + 6 = 9 per side):

| metric (relative %, vs QQQ) | additions | deletions | add − delete |
|---|---:|---:|---:|
| announcement close → first open | +0.2136 | −1.8604 | **+2.0740** |
| first open → implementation close | −1.2663 | −0.8910 | **−0.3752** |
| implementation close → effective open | +0.6315 | −0.5150 | **+1.1465** |
| post-implementation, 1 session | −2.3754 | −0.1489 | **−2.2264** |
| post-implementation, 5 sessions | −4.0522 | −0.8848 | **−3.1674** |
| post-implementation, 20 sessions | +3.9900 | +2.0342 | +1.9558 |
| post-implementation, 60 sessions | +14.3182 | −1.9336 | +16.2518 |
| implementation volume ÷ prior 20d median | **12.87×** | **7.26×** | — |

The volume row has no difference column on purpose: a difference of two ratios is not a
meaningful quantity, and the artifact does not report one.

### Reconciliation

Two identities were re-derived from the batch artifacts and hold to 1e-5:

1. **Pooling is a plain n-weighted mean.** For every metric and both sides,
   `(m₂₄·n₂₄ + m₂₅·n₂₅) / (n₂₄ + n₂₅)` equals the panel value. There is no reweighting,
   winsorising or trimming hidden in the pooling step.
2. **`addition_minus_deletion` is exactly the difference of the two pooled sides.** No
   separately-estimated contrast.

### The excluded 2022 diagnostic

F111 reports the 2022 batch's five-session figure as **−2.794 pp**, which reconciles as
`additions (−2.4339) − observed_deletions (+0.3601)`. It is quoted only as a *sign*
sensitivity — the batch is barred from the pooled estimate because a missing deletion
(SPLK, acquired/delisted) makes the deletion mean survivorship-biased in the favourable
direction.

---

## What this does and does not support

**Does:** the same post-implementation sign appears in both complete batches and in the
excluded diagnostic; implementation-session volume is extreme on both sides; additions
separate positively at the next tradable open but do not continue into implementation.

**Does not:** anything inferential. Eighteen securities, two batch clusters, no p-values,
no matched candidate universe, no factor controls, no flow estimates, no auction data, no
transaction costs. The addition group contains extreme prior winners, which is the obvious
explanation for the 20- and 60-session outperformance and the reason those rows are not
bolded above. The five-session reversal is a **hypothesis generator** — it justifies
freezing IX-REVERSAL for a larger rights-cleared panel and nothing more.

The 60-session add−delete figure (+16.25 pp) is the clearest illustration of why: it is
the largest number in the table and the least trustworthy one.

---

## Provenance

All four artifacts record `raw_data_committed: false`, provider `Yahoo Finance via
yfinance 1.2.0`, and retrieval timestamps on 2026-07-24. The event batches additionally
carry `normalized_input_sha256`, `derived_result_sha256`, a `fingerprint_contract`, and a
`refresh_audit` — the dual-hash discipline from [`F110`](../../RESEARCH_WEB.md), which
records 3–4 *distinct* exact input hashes against *identical* paired derived hashes
(vendor bytes move on same-day re-fetch; the decision, hashed at 0.001pp, does not).

Consequence: this panel is **decision-stable but vendor-backed**, not clone-only
reproducible. Regenerating it requires network access to the provider; verifying it
requires only this repository.

---

## Addendum — this document also holds [`E100`](../../RESEARCH_WEB.md)'s counts

E100 is the experiment node behind the panel, and it was queued as "uncited" long after
this document was published. Its statements reconcile against the same artifacts:

| E100 states | artifact | field | value |
|---|---|---|---|
| the complete Dec-2024 batch has three additions/deletions | `ix00_ndx_december2024_event_replication.json` | `group_summary_percent.{additions,deletions}.n` | 3 / 3 |
| pooled with complete 2025 it yields nine per side | `ix00_ndx_recent_complete_panel.json` | `security_weighted_summary_percent.{additions,deletions}.n` | 9 / 9 |
| the 2022 official list has 13 security events | `ix00_ndx_december2022_partial_diagnostic.json` | `coverage.official_events` | 13 |
| Yahoo supplies only 12 | same | `coverage.analyzed` (and `coverage.complete: false`) | 12 |
| acquired Splunk is unavailable; the tool records the exclusion | same | `excluded_security` | `SPLK`, deletion |
| 2022 is barred from the complete panel | `ix00_ndx_recent_complete_panel.json` | `excluded_batches["ndx-2022-12"]` | "incomplete free-provider coverage: SPLK missing" |
| 2023 excluded — list revised after Seagen | same | `excluded_batches["ndx-2023-12"]` | "…requires security-specific revision clocks" |

Nothing had to be reconstructed. **The gap was that this document names `F111` and never
named `E100`**, and doc-reachability is measured one hop. F111 does not itself cite the
document — [`F182`](../../RESEARCH_WEB.md) does — so from E100 the document sits two hops
away and was invisible.

**Raising the hop limit is the wrong fix, and the cost is measurable.** Re-running the
reachability walk over the whole web at increasing depth:

| depth | nodes left in the uncited queue |
|---:|---:|
| 1 (current) | 51 |
| 2 | 23 |
| 3 | 2 |
| unbounded | 1 |

Depth 2 would silently mark 28 nodes as documented by a document that need not be about
them; depth 3 all but empties the queue. Reaching *a* document is not the same as reaching
one that holds *your* figures, and the coupling only holds at one hop. A "the doc names
the node id" rule fails for a different reason: 19 of the 51 are named in some document,
but mostly by `EPI00_epistemic_audit.md` and the handoff notes, which *list* nodes as
audit subjects rather than documenting their numbers.

*(Counts are after the figure-counter fix below, over 166 candidate nodes clearing the
five-measurement floor; before it the same walk gave 67 / 27 / 4 / 1 over 209.)*

So the fix is the cheap exact one, applied here: **when a study documents a node's
figures, cite that node.**

E100 also leaves the queue on its own merits once the figure counter stops counting
non-measurements — see the guard below.

## Guard

`tests/test_f111_ndx_panel_figures.py` binds every figure F111 states in prose to the
artifact value it came from, at the precision the prose uses, and re-checks both
reconciliation identities. If a node's number drifts from its artifact, or an artifact is
regenerated with different values, it fails and names the pair.

`tests/test_e100_figures_and_measurement_floor.py` binds the table above to the same
artifacts, and guards the figure-counter fix: ISO timestamps, clock times and index names
carrying digits are not measurements. E100's "5 figures" were `-07`, `00`, `100`, `12`,
`13` — a date fragment, a clock fragment, half of "Nasdaq-100", and two real counts.
