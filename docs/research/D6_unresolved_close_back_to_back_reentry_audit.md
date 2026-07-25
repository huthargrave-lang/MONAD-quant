# Study 60 — Unresolved-close back-to-back re-entry audit

**Date:** 2026-07-24<br>
**Status:** reproducible reachability + archive-boundary audit; no
live/config/order-path change authorized<br>
**Artifact:** `tools/overnight_gap_risk_study.py` →
`unresolved_close_back_to_back_reentry_audit`

## Question

After an exit path deletes local state, is a momentarily flat broker position
enough to place a replacement bracket in the same cycle if the old parent,
children, or explicit market-close order have not reached terminal states?

## Verdict

**No. The re-entry guard checks positions, not outstanding orders, and it is not
atomic with the successor submission.**

Software stop, software take-profit, and time exit all set an `exit_action` and
fall through to the same-cycle entry block. That block performs one valuable
defense:

```text
get_open_position(symbol)
if broker quantity is nonzero:
    block entry
```

But it checks none of:

```text
openOrders  openTrades  orderStatus  remaining
permId      orderRef    prior lifecycle terminal state
```

A flat position is a snapshot of net exposure. It does not prove that orders
capable of changing that exposure are gone.

The committed archive makes this boundary concrete. It has 32 application-level
back-to-back entries. Two were placed about 14 seconds after the same cycle had
logged that a time-exit fill was unavailable after its ten-second poll. These
pairs prove that a new bracket submission path crossed an unresolved execution
boundary after the broker-position guard passed. They do **not** prove the old
close was still working, that either new parent was accepted/filled, or that a
collision occurred.

## Reproduce

```bash
venv/bin/python tools/overnight_gap_risk_study.py \
  --selfcheck --json /tmp/gap_program_study60.json
```

The audit only hashes and reads source/archive files and performs deterministic
signed-position arithmetic. It does not import `live.*`, contact IBKR, submit or
cancel an order, or modify a protected path.

## Why position-flat is weaker than lifecycle-terminal

The current same-cycle handoff is:

```text
old exit path:
    request child cancellations
    submit explicit market close
    observe first fill OR time out
    delete old local position

successor path:
    query current net broker position
    if flat, submit a new bracket
```

There is no proof between those blocks that:

- both old attached children are cancelled;
- an old parent remainder is cancelled;
- the explicit market close is fully filled/cancelled/rejected;
- cumulative executions reconcile to the old position;
- no old order can execute after the flat snapshot; or
- the flat check and new-order intent belong to one atomic lifecycle handoff.

IBKR exposes active orders to the submitting client through its open-order APIs
([official active-order documentation](https://interactivebrokers.github.io/tws-api/open_orders.html)).
Its order-status surface distinguishes filled and remaining quantity and terminal
states
([official order-status documentation](https://interactivebrokers.github.io/tws-api/order_submission.html)).
The current re-entry block uses neither surface.

## Deterministic old-order/new-generation collision

One valid interleaving is:

1. Old lifecycle holds long 100 with two attached `SELL 100` children.
2. A force exit requests child cancellation and submits market `SELL 100`.
3. No close fill callback arrives within ten seconds; the caller estimates PnL
   and deletes old local state.
4. While cancellation is unresolved, an old child `SELL 100` fills and makes
   the broker position flat. The explicit market close remains working.
5. The re-entry guard sees broker quantity zero and checks no active orders.
6. A new bracket parent `BUY 100` fills; local state records the new long 100.
7. The old market `SELL 100` then fills against the new exposure.

Terminal state:

| state | quantity |
|---|---:|
| broker position | **0** |
| local new position | **long 100** |
| new bracket children | potentially working for 100 |

The old lifecycle has erased the new economic exposure without deleting the new
local record. A partial late close produces the same mismatch at a smaller
quantity:

| late old close fill | broker final qty | local qty | broker − local |
|---:|---:|---:|---:|
| 0 | 100 | 100 | 0 |
| 25 | 75 | 100 | −25 |
| 40 | 60 | 100 | −40 |
| 100 | **0** | **100** | **−100** |

This is a reachability counterexample, not an assertion that IBKR followed this
schedule historically.

## Archive boundary

The archive contains these application-level back-to-back labels:

| prior exit action | entries |
|---|---:|
| retrieved bracket exit | 22 |
| time exit | 5 |
| inferred target | 3 |
| retrieved target | 1 |
| software stop | 1 |
| **total** | **32** |

Four time exits explicitly logged “fill unavailable” after the close poll.
Two have an entry event in the same application cycle:

| timeout event | entry event | elapsed | requested new qty |
|---:|---:|---:|---:|
| 116 | 117 | 14.332509 s | 129 |
| 152 | 153 | 14.041136 s | 109 |

The entry messages identify `back-to-back after exit_time_exit`; the short
elapsed time is only a chronology check. As Study 52 established, `ENTRY placed`
means three application submission calls returned and local state was written,
not that the destination accepted or filled the new parent.

The archive contains no `remaining`, `orderStatus`, `permId`, `execId`, or
confirmed-cancellation identity with which to decide whether the old close was
terminal. Therefore:

- observed: unresolved fill evidence followed by application re-entry;
- not observed: a nonterminal old order or a late execution;
- not identifiable: actual broker exposure across either pair.

## Existing test boundary

`test_back_to_back_entry_after_exit` deliberately mocks:

```text
old bracket fill returned
broker position flat
new signal actionable
```

and asserts that a new bracket is placed. It does not model:

- a close timeout;
- pending child cancellation;
- an outstanding explicit close;
- a flat snapshot produced by a competing old fill;
- a late old execution after successor submission; or
- an atomic lifecycle-generation transition.

The test is correct for a terminal old lifecycle. It does not establish that the
runtime verifies that precondition.

## Relationship to prior findings

- Study 58 / F93 proves old parent/child cancellation and close quantity are not
  reconciled.
- Study 59 / F94 proves an explicit close is considered complete on one
  execution—or abandoned into estimated local flatness after timeout.
- Study 56 / F91 proves an older local cycle can erase a newer local generation.
- This study proves the order-level analogue: an older broker order can remain
  capable of mutating a successor generation even after a broker-flat snapshot.

The defects share one missing primitive: a durable lifecycle with an atomic
retirement/successor boundary.

## Falsification / repair gate

Before any protected-path remediation:

1. retain the old lifecycle in `pending_close` after exit submission;
2. reconcile the old parent, both children, and explicit close to terminal
   statuses and cumulative executions;
3. require both exact broker flatness and zero active order remainder for the
   symbol/lifecycle before successor intent;
4. identify orders by durable `permId`/`orderRef` and executions by `execId`;
5. make lifecycle retirement and successor intent one atomic state transition;
6. recheck broker position and active orders after successor acknowledgement;
7. deterministically test the child-fill → flat snapshot → new parent → late
   old-close schedule for long and short positions.

## Limits

- The two archived pairs prove a risky boundary was crossed, not a late-fill
  incident.
- The broker-position check is useful defense in depth; the defect is treating
  it as sufficient and not atomic with submission.
- Normal liquid-market execution may make the harmful interleaving rare. Safety
  still requires an invariant rather than an assumption about the usual path.

## Decision

Do not allow same-cycle successor entries until every order from the prior
lifecycle is terminal and executions reconcile to exact broker flatness. A
momentarily flat position is necessary, not sufficient.
