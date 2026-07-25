# CA-00 — when a terminal value may be called zero, and what a free provider actually covers

**Status:** validation fixture plus a coverage diagnostic. Eight actions, one free
provider, two refreshes. No price-correctness claim, no return claim, no event sample.
This document records where [`F115`](../../RESEARCH_WEB.md)'s and
[`F113`](../../RESEARCH_WEB.md)'s figures come from — both were flagged uncited — and one
inconsistency found while checking them.

**Artifacts:** `docs/research/data/ca00_corporate_action_fixture.json` (the eight actions
and their outcome models), `docs/research/data/ca00_free_provider_coverage.json` (the
coverage audit), and `docs/research/data/ca01_sec_state_machine_fixture.json` for the
cross-check on the BBBYQ acceptance timestamp. Code: `tools/corporate_action_outcome_lab.py`.

---

## Part 1 — the zero-value rule (F115)

A cancelled equity is not automatically worth zero. "The shares were cancelled" says the
security stopped existing; it does not say holders received nothing. Plan distributions,
contingent value rights and litigation trusts all cancel the old equity while paying
*something*. So CA-00 refuses to write a numeric terminal value unless the issuer's own
filing supplies the facts.

`validate_fixture()` gates an explicit zero on a **three-fact conjunction**:

```
equity_canceled_without_consideration is True
issuer_stated_no_value               is True
cash_usd_per_share                   == 0
```

* All three present → the action *must* be labelled
  `terminal_zero_value_confirmed_no_consideration` with
  `value_completeness = complete_for_numeric_terminal_value`.
* Any missing → `value_completeness` *must* be `insufficient_for_numeric_terminal_value`,
  and asserting a numeric zero raises
  `"cancellation alone cannot infer a numeric zero"`.

### BBBYQ

The confirmed-plan filing established cancellation but not a number. The **September 29,
2023 effective-date 8-K, accepted 16:23:06 ET**, states that all equity interests were
cancelled without consideration and have no value. That filing supplies all three facts,
so BBBYQ common resolves to **0.00 USD per share** — and only then.

The acceptance timestamp reconciles against the CA-01 state fixture, where the same event
appears as the `plan_effective` assertion with `observed_at = 2023-09-29T16:23:06-04:00`.

### The inconsistency (fixed here)

`consideration_legs()` — the resolver — checked only the **first two** of the three
conditions. An action recording "cancelled without consideration, issuer states no value"
alongside a **non-zero** `cash_usd_per_share` therefore resolved to `0.00`, `status:
resolved`, while `validate_fixture()` rejected the very same action.

No committed result was affected: `load_fixture()` always validates, so every action on
the normal path already satisfies all three. The exposure was a caller assembling an
action dict and calling `resolve_terminal_value()` directly — which is how a future study
would use this lab. The resolver now applies the same conjunction as the validator.

The general shape is worth naming: **a resolver more permissive than its validator is a
validator that can be walked around.** The two predicates were written separately and
drifted by one clause.

### A remaining sharp edge (not fixed)

When resolution refuses, the output still carries the action's own `label_type` and
`formula` — so an unresolved BBBYQ-shaped action returns `status: unresolved` while
`label_type` still reads `terminal_zero_value_confirmed_no_consideration`. A consumer that
reads the label without checking `status` sees a confirmed zero. Changing that means
deciding whether the resolver should recompute the label or echo it, which is a design
question rather than a bug; it is recorded and guarded rather than silently altered.

---

## Part 2 — free-provider coverage (F113)

The same eight actions, queried against Yahoo Finance via yfinance 1.2.0 on 2026-07-24.
Each action declares the price roles it needs (`subject_pre_effective`,
`successor_first_effective`, and so on); the audit records which resolved.

| symbol | action type | roles | complete |
|---|---|---:|:--:|
| SGEN | cash_merger | 0 / 1 | ✗ |
| ATVI | cash_merger | 0 / 1 | ✗ |
| SPLK | cash_merger | 0 / 1 | ✗ |
| TWTR | cash_merger | 0 / 1 | ✗ |
| XLNX | stock_merger | 1 / 2 | ✗ |
| GE | spinoff | 3 / 3 | ✓ |
| BBBYQ | bankruptcy_cancellation | 1 / 1 | ✓ |
| FB | ticker_change | 2 / 2 | ✓ |
| | **total** | **7 / 12** | **3 / 8** |

Role coverage **58.33%**; complete actions **3 of 8**. Both figures re-derive from the
per-action rows, and two refreshes produced the identical coverage-decision fingerprint
`171209f5…b43fcf`.

**The pattern is not random attrition.** All four fixed-cash mergers fail on exactly the
leg that matters — the subject's last pre-effective session. The successor AMD is
available while the disappearing XLNX is not. Survivors resolve; the acquired do not.
Current-symbol data therefore **select against precisely the securities whose terminal
outcomes a corporate-action study exists to measure.**

Two near-misses show the fix is aliasing, not a different vendor: BBBYQ is unavailable but
the required session appears under the older **BBBY** symbol, and FB is unavailable while
**META** exposes both sides of the unchanged-CUSIP ticker transition. Time-bounded symbol
aliases would recover both.

---

## Limits

`raw_documents_committed` and `raw_data_committed` are both `false` — the fixture holds
transformed facts and source URLs, the audit holds coverage decisions. Availability from
one free current-symbol provider is not proof that a security never traded, and coverage
metadata establish nothing about price correctness, corporate-action adjustment, or
redistribution rights. BBBY history appearing under `BBBY` rather than `BBBYQ` needs
security-master validation before any return research. A complete price-role check does
**not** make the bankruptcy terminal value complete — plan distribution rights remain
unresolved, which is exactly what the three-fact rule above is protecting.

## Guard

`tests/test_f115_f113_terminal_value_and_coverage.py` re-derives both coverage figures
from the per-action rows, pins the three-fact rule in both directions, asserts that the
validator and the resolver now agree on the same conjunction, and records the label/status
sharp edge so it cannot be forgotten.
