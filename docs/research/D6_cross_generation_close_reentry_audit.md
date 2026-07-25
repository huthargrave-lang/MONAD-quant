# Study 56 — Cross-generation close/re-entry audit

**Date:** 2026-07-24<br>
**Status:** reproducible reachability proof; no live/config/order-path change authorized<br>
**Artifact:** `tools/overnight_gap_risk_study.py` → `cross_generation_close_reentry_audit`

## Question

If two cycles overlap around an exit and same-cycle re-entry, can an older cycle
attach its exit evidence to the newer position and delete the newer local state?

## Verdict

**Yes. The current close is not generation-safe.** A cycle resolves exit evidence
using the `Position` object it loaded near the beginning of the cycle. It later
calls:

```text
close_position(return_pct, exit_type, exit_price)
```

The call carries no expected position, bracket, order, or lifecycle ID.
`close_position` opens a new connection, selects whichever row happens to exist,
inserts a trade using that row's metadata plus the caller's already-computed exit
economics, and executes an unqualified `DELETE FROM position`.

A deterministic temporary-SQLite schedule therefore does all of the following:

1. cycle B caches old bracket `100` and resolves its old exit;
2. cycle A closes bracket `100`;
3. cycle A places and persists new bracket `200`;
4. cycle B calls the current implementation-shaped close with bracket-100
   economics;
5. the close independently selects bracket `200`, records bracket-200 metadata
   with bracket-100 economics, then deletes bracket `200`.

The final local position count is zero. That does not undo the externally
submitted bracket `200`.

This is a **source-level reachability proof**, not a claim that the archived or
current deployment experienced the schedule.

## Reproduce

```bash
venv/bin/python tools/overnight_gap_risk_study.py \
  --selfcheck --json /tmp/gap_program_study56.json
```

The experiment creates a temporary database, never imports `live.state`, never
touches `live/state.db`, never starts the trader, and never contacts IBKR.

## The identity boundary is missing

The open-position schema contains `bracket_order_id`, but:

- `position` has no primary key or unique lifecycle constraint;
- `close_position` does not accept the expected bracket/lifecycle ID;
- its `DELETE` has no `WHERE` predicate;
- it does not inspect the delete cursor's affected-row count;
- `trades` does not retain `bracket_order_id` or another lifecycle ID; and
- the close result does not tell the caller whether it won, lost, or encountered
  a generation mismatch.

SQLite's transaction guarantee does not repair that application identity gap.
Python's connection context manager commits or rolls back an already-open
transaction; it does not itself open one. The driver exposes affected-row
counts, but the current close does not use them
([Python `sqlite3` documentation](https://docs.python.org/3/library/sqlite3.html)).
SQLite also documents that transactions serialize database writes, not external
broker side effects or an identity-free read/modify workflow
([SQLite transaction documentation](https://www.sqlite.org/lang_transaction.html)).

## Deterministic crossed-generation result

The synthetic values are deliberately far apart so field mixing is unmistakable:

| Field | old generation | new generation |
|---|---:|---:|
| bracket ID | 100 | 200 |
| entry price | 100.00 | 200.00 |
| quantity | 100 | 50 |
| old exit price | 101.00 | — |
| old computed return | +1.00% | — |

The stale close selects the new row, so the second trade record contains:

- new entry time and quantity 50;
- old exit price 101.00;
- old recorded return +1.00%; and
- no durable bracket ID in the production-equivalent trade schema.

Relative to the selected new entry price, 101.00 implies **−49.50%**, not
+1.00%. The 50.50 percentage-point discrepancy is a diagnostic proof of mixed
generations, **not an estimate of historical PnL error**.

After that insert, the unqualified delete removes the new row. The experiment
ends with two local trade rows and zero local positions.

## Events can describe two different positions

There is a second observability split:

- `state.close_position` emits its exit monitor event using the row it freshly
  selected—which may be the new generation;
- the trader sends its exit alert using the cycle-cached `position`—the old
  generation; and
- both use exit price/return derived earlier from the old bracket.

Without a shared expected lifecycle ID, one logical close can therefore produce
state/event metadata for generation B while the caller's alert describes
generation A.

IBKR exposes the identity needed to avoid this ambiguity. Its order status
includes `orderId`, `permId`, `parentId`, `clientId`, filled quantity, remaining
quantity, and average fill price
([official TWS API documentation](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/)).
Its execution record distinguishes the API-client order ID—which may not be
account-unique—from `ExecId`, client ID, account, shares, price, and `PermId`
([official API reference](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-ref/)).
The project currently carries none of that durable chain through its closed
trade.

## What the archive can and cannot answer

Study 48 found seven historical minutes with two entry-success events. This
study rechecks their retained identity:

| archive diagnostic | result |
|---|---:|
| double-entry minutes | 7 |
| success events inside them | 14 |
| pairs whose two quantities differ | 3 |
| success events retaining a parent/order/bracket ID | **0 / 14** |
| closed-trade export retains `bracket_order_id` | **no** |

The archive proves overwrite-shaped duplicate entry paths and that the later
state survived in each eventual local trade row. It cannot establish whether a
cross-generation close occurred, because the entry events and closed-trade rows
discard the identity needed to join old exit evidence to the exact open
lifecycle.

This is not negative evidence. It is an **unidentifiable historical question**.

## Broker consequences

Deleting the new local row has different consequences depending on broker state:

1. **New parent filled.** On a later cycle, local-flat plus broker-long should
   trigger the existing position-desync block. That contains additional entry,
   but the local record no longer identifies the bracket that needs management.
2. **New parent still working/unfilled.** Broker positions may still appear
   flat. As Study 51 established, the entry guard does not inspect working
   orders, so another bracket path remains reachable.
3. **New parent rejected/cancelled.** The local deletion may accidentally agree
   with economic flatness, but no retained status proves that outcome.

In every case, committing or rolling back SQLite cannot undo an order already
submitted to the broker.

## Current test boundary

The repository tests cover ordinary sequential open/close behavior. Study 55
now proves a two-reader duplicate-close schedule. The tests still do not stage:

```text
old cycle loads A
other cycle closes A
other cycle opens B
old cycle tries to close A
```

There is no assertion that the stale call must be a no-op, that B survives, that
no mixed trade is inserted, or that the losing caller suppresses alerts and
re-entry.

## Falsification gate

The finding is falsified only by a complete identity boundary:

1. create a durable lifecycle/position ID before broker submission;
2. retain it with client order ID, `permId`, and execution IDs through open
   state, closed trade, events, and exports;
3. require every close/finalize call to carry the expected lifecycle ID;
4. atomically claim that exact row, insert one uniquely keyed closed trade, and
   `DELETE ... WHERE lifecycle_id = ?`, requiring exactly one affected row;
5. return a typed outcome and allow only the winning close to sync, alert, set
   `exit_action`, or evaluate re-entry; and
6. pass staged two-cycle cut-point tests proving a stale A close neither records
   nor deletes B.

An explicit write transaction helps serialize the local claim, but it is not
sufficient by itself. The expected generation must also be part of the claim.

## Decision

Treat local “flat” as potentially lossy state, not proof that the most recent
broker lifecycle ended. The immediate design requirement is one durable
economic-lifecycle identity propagated from intent through broker order,
execution, local position, close, event, and export. Until that exists,
reconciliation cannot reliably distinguish “old exit finished” from “new state
was erased.”
