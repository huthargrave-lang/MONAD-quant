# Study 54 — Bracket-fill identity and retention audit

**Date:** 2026-07-24<br>
**Status:** read-only evidence audit; no protected-path change authorized<br>
**Artifact:** `tools/overnight_gap_risk_study.py` → `bracket_fill_identity_and_retention_audit`

## Question

When `get_bracket_fill` does return a price, does the project durably prove that
the execution belongs to the stored position and calculate the complete fill
price correctly? Does its seven-day fallback actually work on IB Gateway?

## Verdict

**No. “Retrieved fill” currently means project-matched execution, not a durable
end-to-end ledger.**

All three recovery tiers ultimately identify executions with the client API
order number:

1. current-session trades match child `parentId`;
2. the synchronized fill cache accepts a known child ID or `parent+1/+2`; and
3. `reqExecutions` accepts `parent+1/+2`.

None checks contract symbol/conId, account, client ID, permanent order ID,
execution ID, cumulative quantity, or broker average price. The result retains
only `fill_price`, `fill_time`, and `exit_type`.

The code's “historical fills up to 7 days” comment is also false for the
deployed IB Gateway shape. IBKR says executions default to since midnight; TWS
can extend this through its Trade Log setting, but **IB Gateway cannot change
that setting and remains limited to since midnight**. Passing a seven-day
timestamp cannot retrieve records the Gateway does not expose.

## Current three-tier matcher

| Tier | Match key | Price chosen | Durable identity / VWAP |
|---|---|---|---|
| `ib.trades()` | first child whose `parentId` equals stored parent ID | last execution on that child | no |
| `ib.fills()` | known child ID or `parent+1/+2`, exit side, shares > 0 | first matching execution | no |
| `reqExecutions()` | `parent+1/+2`, exit side, shares > 0 | first matching execution | no |

Direction-side filtering is useful: it avoids confusing a long BUY entry with a
SELL exit and vice versa. It is not a complete identity join. The execution
object already exposes stronger fields, including `execId`, `permId`,
`clientId`, cumulative quantity, average price, and the associated contract:

- [Current IBKR TWS API documentation](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/)
- [IBKR execution retrieval and Gateway retention](https://interactivebrokers.github.io/tws-api/executions_commissions.html)

IBKR describes `permId` as account-wide and the API order ID as specific to an
API client. The current state schema stores only the parent API ID.

## Partial-fill arithmetic

The matcher does not aggregate executions. A deterministic illustration:

```text
60 shares @ 100
40 shares @ 101
correct VWAP = 100.40
```

Tier 1 selects the last execution, 101.00: **+59.761 bp** versus VWAP. Tiers 2
and 3 select the first match, 100.00: **−39.841 bp** versus VWAP.

This is not an estimate of historical error. It proves only that the current
selection rule is not a quantity-weighted fill aggregator. The normal
reconciliation path waits until the broker position is flat, which reduces the
risk of recording an incomplete position, but does not make one component
execution the full-position VWAP.

## Why retention matters to Study 53

Four of the five execution-unverified inferred rows began on a prior UTC date:
trade rows 17, 21, 34, and 45. The fifth entered and was inferred on the same
date.

That 4/5 timing is consistent with the deterministic Gateway midnight
retention gap: a prior-day child execution may be unavailable on the next
cycle even though the code requested seven days. It does **not** prove that
those brackets filled, when they filled, or that retention caused each missing
record.

This refines Study 53's alternatives:

- some inference can plausibly be a real prior-day exit that Gateway cannot
  return;
- an unfilled/rejected parent remains equally compatible without a durable
  parent/execution ledger; and
- even a returned execution price is not presently persisted with enough
  identity and quantity to close the ambiguity.

## Test boundary

Current broker tests cover single executions for the three tiers, side
filtering, and no-fill/error cases. They do not cover:

- multiple partial executions and VWAP;
- wrong-symbol executions with the same numeric order ID;
- permanent-ID mismatch;
- duplicate execution IDs;
- cumulative quantity reconciliation; or
- reconnect across midnight/weekend under Gateway retention.

## Falsification gate

A reliable ledger must persist parent and child permanent IDs, contract
identity, entry/exit execution IDs, shares, cumulative quantity, broker average
price, status, and timestamps. It must deduplicate and aggregate partial
executions, then reconcile their quantity to the economic position.

Prior-day Gateway recovery should be treated as unavailable unless the project
has already captured those callbacks into its own durable store. Crash,
reconnect, midnight, weekend, partial-fill, duplicate-callback, and
wrong-contract cases need isolated paper tests before any protected-path
change.

## Decision use

Use “project-matched exit execution” rather than “fully confirmed fill” for the
current recovered-price path. This does not numerically change Study 52's flat
47-row quote-basis sensitivity; it weakens how confidently any individual exit
price can be attributed without a durable broker ledger.
