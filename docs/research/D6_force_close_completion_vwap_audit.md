# Study 59 — Force-close completion and VWAP audit

**Date:** 2026-07-24<br>
**Status:** reproducible reachability + observed uncertainty-boundary audit; no
live/config/order-path change authorized<br>
**Artifact:** `tools/overnight_gap_risk_study.py` →
`force_close_completion_and_vwap_audit`

## Question

Once a force-close market order has been submitted, what proves that the entire
position is closed? Does the returned price represent all executions, and what
happens when no fill callback arrives within ten seconds?

## Verdict

**One execution is treated as a completed close, while no observed execution is
treated as permission to estimate the exit and delete local state. Neither branch
proves the broker position flat.**

`cancel_and_close` polls for ten seconds and returns as soon as
`trade.fills` is nonempty. It does not inspect:

```text
orderStatus  filled  remaining  avgFillPrice
isDone       cumQty  execution.shares
```

It returns only `fill_price` and `fill_time`, selecting the last execution
component then visible. The three callers immediately calculate full-position
PnL and call `state.close_position`, which records the local requested quantity
and deletes the position row.

A deterministic partial-execution schedule therefore reaches:

```text
broker position before close       +100
market close                       SELL 100
first execution                     SELL 60 @ 100
broker remaining position            +40
local position after caller             0
local trade quantity recorded          100
```

If no execution appears within ten seconds, `cancel_and_close` returns `None`
without checking whether its market order is still working or cancelling it.
Every force-close caller substitutes a mark/reference price and still deletes
local state.

The committed archive contains **four of nine time-exit rows** with an explicit
“fill unavailable” warning at this boundary. That proves fill evidence was
missing when state was finalized. It does **not** prove those market orders
failed, partially filled, or left residual exposure.

## Reproduce

```bash
venv/bin/python tools/overnight_gap_risk_study.py \
  --selfcheck --json /tmp/gap_program_study59.json
```

The audit hashes and reads source/archive files only. It does not import
`live.*`, connect to IBKR, submit/cancel an order, or modify a protected path.

## Current state machine

The success branch is:

```text
submit market close
poll
if trade.fills is nonempty:
    return price/time from the last currently visible fill
caller:
    calculate return for the stored position
    close_position(...)
    DELETE local position
```

The timeout branch is:

```text
submit market close
poll for 10 seconds
observe no fill callback
return None
caller:
    choose mark/reference price
    calculate estimated return
    close_position(...)
    DELETE local position
```

Missing callback evidence is not evidence that an order is absent, rejected,
cancelled, working, partially filled, or fully filled. The return shape carries
no order ID, permanent ID, execution ID, filled quantity, remaining quantity,
status, or cumulative average price with which the caller could distinguish
those states.

## First-partial-execution counterexample

For an intended `SELL 100`, suppose the first reported execution is 60 shares
at $100:

| fact at return | value |
|---|---:|
| intended close quantity | 100 |
| order-status filled | 60 |
| order-status remaining | 40 |
| current success predicate | `trade.fills` nonempty |
| adapter returned quantity | absent |
| adapter returned remaining | absent |
| broker residual if no later fill | **long 40** |
| local position rows after caller | **0** |
| local trade quantity | **100** |

The residual is hidden by local flatness. A later reconciliation cycle may
notice broker-nonzero/local-flat and block a new entry, but lifecycle identity
and the close order's completion state have already been discarded.

This example assumes the close quantity was correct. Study 58 separately proves
that the caller can use the wrong quantity in the first place. The two defects
compose but do not depend on each other.

## Component price is not VWAP

Use two executions:

| execution | shares | price |
|---:|---:|---:|
| 1 | 60 | $100 |
| 2 | 40 | $101 |

The correct quantity-weighted exit price is:

```text
(60 × 100 + 40 × 101) / 100 = 100.40
```

Two callback timings produce two different wrong records from the same economic
execution:

| visible at first poll | current returned price | error vs $100.40 |
|---|---:|---:|
| only execution 1 | $100.00 | −39.841 bp |
| executions 1 and 2 | $101.00 | +59.761 bp |

The first case also returns before the order is complete. The second may be
complete, but the predicate never proves that and the price is still one
component rather than VWAP.

IBKR documents that `orderStatus` provides filled quantity, remaining quantity,
and average fill price
([official order-status documentation](https://interactivebrokers.github.io/tws-api/order_submission.html)).
IBKR also documents that each full or partial fill produces execution details
with shares and cumulative quantity
([official execution documentation](https://interactivebrokers.github.io/tws-api/executions_commissions.html)),
and that each partial fill has a separate execution ID
([official Execution reference](https://interactivebrokers.github.io/tws-api/classIBApi_1_1Execution.html)).
The current function reads none of that completion information.

## The timeout branch is historically observed

The sanitized archive retains:

| evidence | count |
|---|---:|
| local `time_exit` trade rows | 9 |
| explicit time-exit “fill unavailable” events | **4** |
| software-stop “forcing close” events | 6 |
| minimum identifiable force-close attempts | 15 |
| retained `remaining` / `avgFill` / `cumQty` / `execId` / `orderStatus` tokens | 0 |

The four warnings establish only this chronology:

1. a force-close order was submitted by the application path;
2. no fill was observed by this polling function within ten seconds;
3. the caller used a reference-price estimate; and
4. local state was finalized.

They cannot establish whether:

- the market order had already executed but its callback was delayed;
- it was partially filled;
- it filled after local deletion;
- it remained working;
- it was rejected or cancelled; or
- the final quantity and VWAP matched the local record.

Those are exactly the states a durable execution ledger should distinguish.

## Dormant pending-close machinery does not protect this path

`live/state.py` contains `mark_pending_close` and `finalize_pending_close`, and
the trader has retry logic for a position already carrying that status. However,
the force-close callers never call `mark_pending_close`; on both a first fill and
a timeout they call `close_position` directly.

So the repository already has part of the vocabulary for “exit unresolved,” but
the market-close uncertainty boundary does not use it.

## Existing test boundary

The broker tests prove:

- a nonempty fill list returns a component price;
- an empty fill list after polling returns `None`;
- longs issue `SELL` and shorts issue `BUY`.

They do not require:

- cumulative quantity equal to intended quantity;
- `remaining == 0` or terminal `Filled`;
- quantity-weighted price;
- local pending state on timeout;
- reconciliation of a later fill;
- rejection handling; or
- a fresh broker-position query proving exact flatness.

The tests accurately encode the current unsafe contract.

## Falsification / repair gate

Before any protected-path remediation is proposed:

1. derive close size from a fresh signed broker position after terminal
   cancellation of parent/children;
2. persist a lifecycle/order identity and every execution's `execId`, shares,
   cumulative quantity, price, time, and permanent ID;
3. call the close complete only when cumulative close quantity matches the
   intended residual, remaining quantity is zero, and a fresh broker-position
   query confirms exact flatness;
4. compute exit price as execution-quantity-weighted VWAP;
5. on timeout or ambiguous state, retain `pending_close`, block new entries, and
   reconcile the still-live order rather than estimating flatness; and
6. test first-partial, multi-price completion, delayed-after-timeout, rejection,
   and long/short schedules deterministically.

## Limits

- A liquid TQQQ market order normally fills rapidly. The 60/40 schedule is a
  reachability proof, not an incident-rate estimate.
- The four archived timeouts prove missing evidence, not residual exposure.
- The archive cannot recover ultimate order state or VWAP because it stores no
  execution identity or quantity.

## Decision

Treat `cancel_and_close` as **close submitted / evidence incomplete**, not as
“position closed,” until cumulative completion and broker flatness are proved.
The immediate architectural priority remains one durable lifecycle/execution
ledger spanning intent, cancellation, every partial execution, local state, and
post-close broker reconciliation.
