# Study 52 — Entry acknowledgement and basis audit

**Date:** 2026-07-24<br>
**Status:** read-only evidence-semantics audit; no live/config/order-path change authorized<br>
**Artifact:** `tools/overnight_gap_risk_study.py` → `entry_acknowledgement_and_basis_audit`

## Question

What do the current `Bracket order placed` / `ENTRY placed` records actually
prove? Is `fill_basis` an execution price, and is the project's “CONFIRMED”
live return fully fill-confirmed?

## Verdict

**The current entry success record is application-level, not execution-level.**
The function proves that three `placeOrder` calls returned and that local state
was written. It does not wait for or persist:

- TWS `openOrder` / `orderStatus` acknowledgement;
- IB server or destination acceptance;
- parent fill / `execDetails`;
- actual entry price or fill time;
- permanent order ID (`permId`); or
- active-order reconciliation after restart.

`fill_basis` is the broker quote obtained **before** bracket construction and
submission. It is not a fill.

The historical no-edge conclusion survives and becomes more conservative, but
the evidence label must change: `bracket_exit + stop_hit` is at most
**exit-confirmed / project-classified**, not fully fill-confirmed. In the
sanitized archive, 47 such rows compound to only **+0.204664%** on the recorded
quote basis. A uniform **+0.435020 bp** adverse entry-basis error changes that
point estimate's sign.

That 0.435 bp is a sensitivity threshold, **not an estimate of actual
slippage**.

## Method

The audit hashes and token-checks the current:

- entry adapter (`live/broker.py`);
- entry orchestration (`live/trader.py`);
- SQLite schema (`live/state.py`);
- broker and entry-basis tests;
- pinned `ib-insync==0.9.86` dependency; and
- Study 10 reconciliation input declaration.

It isolates `place_bracket_order`, searches it for acknowledgement/fill
operations, maps crash cutpoints, and deterministically reprices the committed
sanitized archive under small uniform entry-basis shifts.

Reproduce:

```bash
venv/bin/python tools/overnight_gap_risk_study.py \
  --selfcheck --json /tmp/gap_program_study52.json
```

No trader was started and no broker connection was made.

## The current entry chronology

Current source executes:

```text
get tradeable broker quote
compute parent limit / target / stop from quote
construct bracket
placeOrder(parent)
placeOrder(take profit)
placeOrder(stop loss)
return parent order ID + quote as fill_basis
write local position row using fill_basis
write local "ENTRY placed" event
send alert
```

Inside `place_bracket_order`, the ten searched evidence operations all have zero
matches:

```text
orderStatus  .fills  waitUntil  filledEvent  statusEvent
execDetails  openOrders  reqOpenOrders  reqAllOpenOrders  permId
```

The three `Trade` return objects are not retained.

## What the bracket protocol guarantees

The pinned `ib-insync` bracket helper follows IBKR's documented transmit
sequence:

1. parent limit: `transmit=False`;
2. take-profit child: `transmit=False`;
3. stop-loss child: `transmit=True`.

The final child asks TWS to transmit the whole attached bracket. This protects
against the parent executing before both children are staged; it does not make
the caller's return an acceptance or execution acknowledgement.

IBKR says order activity arrives asynchronously through `openOrder`,
`orderStatus`, errors, and executions; it explicitly recommends automated
systems monitor those callbacks. It also warns that status callbacks are not
guaranteed for every transition, so executions must be monitored too:

- [IBKR bracket transmission](https://interactivebrokers.github.io/tws-api/bracket_order.html)
- [IBKR order submission and states](https://interactivebrokers.github.io/tws-api/order_submission.html)
- [IBKR automated-system monitoring](https://interactivebrokers.github.io/tws-api/automated_considerations.html)

For `ib-insync` 0.9.86, a new `placeOrder` call returns a live `Trade` initialized
to `PendingSubmit`; later events update it. The current adapter discards that
object before inspecting any later state.

## Evidence ladder

| Stage | Current durable evidence? | What exists |
|---|---:|---|
| tradeable quote obtained | yes | `live_price` |
| three API calls returned | yes | control reaches function return |
| TWS acknowledgement | **no** | returned `Trade` objects discarded |
| IB server / destination acceptance | **no** | no accepted state or error persisted |
| parent execution | **no** | no entry `execDetails` / fills wait |
| actual entry price/time | **no** | no schema fields |
| local position | yes | parent API ID + quote basis |
| local entry event | yes | emitted after local write |

Consequently, the words “placed” mean “application submission path completed,”
not “accepted” or “filled.”

## Crash-cutpoint analysis

| Crash point | Broker-side possibility | Local position | Entry event |
|---|---|---:|---:|
| before final stop-child call | parent/TP staged but untransmitted in current TWS session | no | no |
| after final transmit, before SQLite | full bracket transmitted, working, rejected, or filled | no | no |
| after SQLite, before event | same unresolved outcomes | yes | no |
| after event, before alert | same unresolved outcomes | yes | yes |

IBKR documents that untransmitted orders remain local to that TWS session and
are cleared on restart. Once the final transmit occurs, however, a crash can
leave a working parent without local state.

The restart gap is concrete:

- preflight checks account positions, not working orders;
- the entry guard checks positions, not working orders;
- the same client ID can request its active orders
  ([IBKR open-order recovery](https://interactivebrokers.github.io/tws-api/open_orders.html));
- current startup does not do so before declaring itself flat.

Thus a transmitted but unfilled parent can coexist with a flat account and an
absent local row.

## Entry-basis sensitivity

The sanitized archive contains 47 rows in the project's prior
`{bracket_exit, stop_hit}` bucket. Those rows do not store entry price, but their
recorded quote basis is recovered exactly from:

```text
recorded basis = exit price / (1 + recorded return)
```

Maximum reconstruction identity error is `1.1e-16`.

For a hypothetical uniform entry-basis shift, actual long return becomes:

```text
exit / (recorded basis × (1 + shift)) − 1
```

| Uniform entry-basis shift | Repriced compound return |
|---:|---:|
| −10 bp (favorable) | +5.029184% |
| −5 bp | +2.587964% |
| −2 bp | +1.151124% |
| −1 bp | +0.676758% |
| 0 bp (recorded) | **+0.204664%** |
| +0.25 bp | +0.086994% |
| +0.50 bp | **−0.030534%** |
| +1 bp | −0.265169% |
| +2 bp | −0.732753% |
| +5 bp | −2.122117% |
| +10 bp | −4.393747% |

Exact adverse break-even: **+0.435020 bp per entry**.

The sign fragility is unsurprising for an already-flat 47-trade sample. Its
decision use is narrow: without actual entry executions, the point return cannot
validate edge or execution quality.

## Correction to Study 10 terminology

Study 10 called 51 `{bracket_exit, stop_hit}` rows “CONFIRMED (actually-filled)”
and reported +1.55%. The declared input,
`data/live_runs/pi_export_2026-06-26/trades.jsonl`, is absent from the current
checkout, so those 51 rows cannot be entry-repriced here.

This study does **not** numerically revise +1.55%. It corrects what the label can
mean:

- the exit category may support an actual-exit interpretation under the prior
  project classification;
- the stored entry basis is still a quote, not an execution;
- the sample is therefore **exit-confirmed**, not fully fill-confirmed.

The substantive conclusion—live is flat and does not rescue the active
engine—stands. The execution-evidence claim is weaker than previously stated.

## What the tests prove

Current unit tests prove:

- long/short quote math;
- three `placeOrder` calls;
- GTC children;
- returned dictionary shape; and
- quote-derived `fill_basis` is written to state and used for PnL.

They do not simulate or assert:

- TWS acknowledgement;
- broker rejection;
- parent fill;
- actual entry price;
- partial bracket failure;
- crash between transmit and SQLite; or
- restart reconciliation of working orders.

The test named around “fill-basis consistency” therefore proves internal
arithmetic consistency, not fill provenance.

## Falsification gates

The entry evidence could be called fully confirmed only when a durable ledger
links one cycle/order intent to:

1. parent API order ID and account-wide `permId`;
2. acknowledged broker status and any reject/error;
3. entry execution ID, shares, price, and time;
4. all child order IDs/statuses;
5. local state commit result; and
6. startup reconciliation of positions **and active orders** before another
   submission.

Because order-status callbacks can be skipped for immediate fills, the gate must
use execution callbacks as well as status.

## Decision use

Use “application-submitted” for entry events and “exit-confirmed” for the prior
PnL bucket. Do not use `fill_basis` to claim exact live PnL or execution quality.
Any implementation belongs to the protected broker/trader/state path and
requires explicit approval with the trader stopped.
