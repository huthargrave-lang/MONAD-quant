# Study 58 — Partial-fill force-close quantity audit

**Date:** 2026-07-24<br>
**Status:** reproducible reachability audit; no live/config/order-path change authorized<br>
**Artifact:** `tools/overnight_gap_risk_study.py` → `partial_fill_force_close_quantity_audit`

## Question

If the bracket parent fills only part of its requested quantity—or a child fills
while cancellation is pending—does the current force-close path derive its
market order from the live signed broker position and prove the account flat?

## Verdict

**No. The force-close path is not quantity-safe.**

Current entry state records the full requested quantity before any parent fill.
On later cycles, the broker does return the real signed position quantity, but
the trader only checks whether it is zero:

```text
if broker position is zero:
    reconcile exit
else:
    manage the local position
```

It does not compare broker quantity or direction with local state. All three
forced-exit paths—software stop, software take-profit, and time exit—then call
`cancel_and_close(..., position.qty)`, where `position.qty` is the original
requested quantity.

A deterministic counterexample is enough:

```text
requested/local quantity     100 long
actual partial parent fill    50 long
forced market close          SELL 100
final signed broker position -50 short
```

The code also cancels only orders whose `parentId` equals the bracket parent ID.
A partially filled parent itself has that value as its `orderId`, not its
`parentId`, so the working parent remainder is not cancelled. Child cancellation
requests are not awaited to terminal confirmation before the full market close
is placed.

The sanitized archive retains no filled/remaining/average-fill/cancellation
status, so this study proves reachability—not historical frequency or an
incident.

## Reproduce

```bash
venv/bin/python tools/overnight_gap_risk_study.py \
  --selfcheck --json /tmp/gap_program_study58.json
```

The study is source/archive read-only. It does not import `live.*`, connect to
IBKR, cancel an order, submit an order, or touch `state.db`.

## Current quantity chronology

The entry path is:

```text
compute requested qty
submit parent + TP + SL
store requested qty immediately
```

No parent execution is awaited. On a later position-management cycle:

```text
broker_pos = get_open_position(symbol)  # includes real signed qty

if broker_pos is nonzero:
    increment local bar count
    possibly call cancel_and_close(local requested qty)
```

The broker's `qty` and `avg_price` are not used to correct the local quantity,
direction, entry basis, or close size.

The force-close adapter then:

1. finds open orders whose `parentId` equals the stored parent ID;
2. calls `cancelOrder` for each one;
3. does not wait for a cancellation terminal state;
4. does not cancel an open parent remainder;
5. constructs a market order from its caller-supplied `qty`; and
6. returns after seeing the first close fill, without asserting final account
   quantity zero.

## Partial fills are specifically exposed

IBKR documents that `orderStatus` carries:

- status;
- filled quantity;
- remaining quantity;
- average fill price;
- permanent order ID;
- parent/client IDs; and
- last fill price.

It also states that attached children stay on hold until the parent is
**completely filled**
([official order/attached-order documentation](https://interactivebrokers.github.io/tws-api/order_submission.html)).

That means a partial parent creates a dangerous intermediate state:

- economic exposure is nonzero;
- local quantity overstates exposure;
- attached TP/SL children are not yet active;
- the hourly software path is the remaining protection;
- the working parent remainder can still change exposure; and
- the software path closes using the overstated local quantity.

This is not a claim about how often marketable TQQQ limits partially fill.
TQQQ is usually liquid. Frequency is unknowable here because parent
`filled/remaining` status is not retained.

## Deterministic signed-quantity table

For requested/local quantity 100:

| actual parent fill | forced close | long final signed qty | short final signed qty | opposite position |
|---:|---:|---:|---:|---:|
| 1 | 100 | −99 | +99 | 99 |
| 25 | 100 | −75 | +75 | 75 |
| 50 | 100 | **−50** | **+50** | **50** |
| 75 | 100 | −25 | +25 | 25 |
| 99 | 100 | −1 | +1 | 1 |
| 100 | 100 | 0 | 0 | 0 |

For a long, negative final quantity is a short. For a short, the same mismatch
creates an unintended long.

This table assumes the parent does not fill more shares during the close. If its
uncancelled remainder or a child also executes, the terminal exposure changes
again. That does not restore an invariant; it adds more interleavings.

## Cancel request is not cancellation

IBKR distinguishes:

- `PendingCancel`: a cancellation request was sent but confirmation has not
  arrived; and
- `Cancelled`: the remaining order balance is confirmed cancelled
  ([official order-state documentation](https://interactivebrokers.github.io/tws-api/order_submission.html)).

`cancel_and_close` retains none of the returned cancellation `Trade` state and
checks none of:

```text
PendingCancel  Cancelled  cancelledEvent  statusEvent
isDone         orderStatus  remaining      waitOnUpdate
```

It immediately submits the market close after issuing child cancel requests.

For a fully filled 100-share long:

| child SELL fill after cancel request | market SELL | final signed position |
|---:|---:|---:|
| 0 | 100 | 0 |
| 25 | 100 | −25 |
| 100 | 100 | −100 |

The late child quantity becomes the opposite short. A cancel error is also only
logged and ignored, after which the market close still proceeds.

## Parent remainder is outside the cancellation loop

The loop condition is:

```text
open_order.parentId == stored_parent_id
```

That selects attached children. A partially filled parent has:

```text
orderId  == stored_parent_id
parentId == 0
```

So its unfilled remainder survives the loop. Even if the market close happens
to flatten the partial position, the parent can later buy more shares.

Active orders can be recovered for the same API client ID, and IBKR exposes
status/filled/remaining data for them
([official open-order documentation](https://interactivebrokers.github.io/tws-api/open_orders.html)).
The current close does not use that recovery surface to obtain terminal state.

## Archive observability

The committed archive contains:

| field | result |
|---|---:|
| entry success events | 72 |
| requested quantity range | 109–269 (median 167.5) |
| closed trade rows | 65 |
| `partial` tokens | 0 |
| `remaining` tokens | 0 |
| `avgFill` tokens | 0 |
| filled/cumulative-quantity tokens | 0 |
| cancellation status retained | no |

As a **scale illustration only**, if each archived request had filled exactly
half before a full-local-qty close, the opposite exposure would range from
55 to 135 shares, median 84. Nothing in the archive says those parents did
partially fill. The calculation merely maps the proven arithmetic onto observed
request sizes.

The absence of partial-fill records is not evidence of complete fills. Entry
success is emitted before execution evidence, and the trade schema repeats the
local requested quantity.

## Next-cycle containment is late

After an overshoot, the existing local-flat/broker-nonzero entry guard should
block a later entry if the opposite position is visible. That is useful defense
in depth, but it:

- detects the problem only after exposure has flipped;
- does not flatten or reconstruct the residual;
- no longer has durable identity for the deleted lifecycle; and
- cannot stop a still-working parent remainder from changing quantity again.

“A later cycle should block” is not the same as “the close was safe.”

## Current test boundary

Current tests correctly assert:

- long close quantity 10 creates `SELL 10`;
- short close quantity 5 creates `BUY 5`;
- matching child orders receive cancellation requests; and
- each trader force-exit path calls `cancel_and_close`.

They do not stage:

- local 100 versus broker 50;
- opposite broker direction;
- partially filled parent remainder;
- `PendingCancel` followed by child execution;
- cancellation failure followed by market close;
- final close fill plus a nonzero broker residual; or
- post-close assertion that the account is exactly flat.

The tests prove that the requested local quantity is forwarded, which is the
problem under mismatch.

## Falsification gate

Quantity safety requires all of the following:

1. persist parent status, signed filled and remaining quantity, average fill
   price, `permId`, and executions under one lifecycle ID;
2. compare signed broker quantity and direction with local state on every
   management cycle;
3. route any mismatch to a typed reconciliation state, never ordinary holding;
4. cancel the parent remainder and both children;
5. wait for confirmed terminal cancellation/fill states;
6. read a fresh signed broker position and size the close from that value—not
   the request;
7. aggregate the market close fill; and
8. assert a fresh broker position of exactly zero before deleting lifecycle
   state or allowing re-entry.

Regression tests must cover partial fills and child-fill-during-cancel schedules
for both directions, reconnects, and DAY-parent expiry.

## Decision

The correct force-close invariant is not “send the local quantity.” It is:

```text
terminally stop all quantity-changing orders
read current signed broker position
close exactly that residual
verify broker flat
then close local lifecycle
```

Until that sequence and its evidence are durable, software stop, software
take-profit, and time exit can turn a partial or racing close into the opposite
position. Treat the current adapter as a best-effort close request, not a
verified flatten operation.
