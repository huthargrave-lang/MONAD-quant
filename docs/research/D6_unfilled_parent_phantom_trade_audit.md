# Study 53 — Unfilled-parent / phantom-trade audit

**Date:** 2026-07-24<br>
**Status:** read-only reachability and archive-provenance audit; no live/config/order-path change authorized<br>
**Artifact:** `tools/overnight_gap_risk_study.py` → `unfilled_parent_phantom_trade_audit`

## Question

Study 52 established that `ENTRY placed` does not prove acknowledgement or a
parent fill. What happens on the next trader cycle if the local position exists
but the parent was rejected, held, cancelled, still working, or never filled?
Can the system record a profitable round trip without proving that an economic
position ever existed?

## Verdict

**Yes, a phantom round trip is reachable in current code.** This is a
constructive control-flow result, not an allegation that a particular archived
parent was unfilled.

The current sequence can be:

1. all three application `placeOrder` calls return without durable broker
   acknowledgement or an entry execution;
2. the quote-derived local position is committed and `ENTRY placed` is emitted;
3. the parent remains unfilled, held, rejected, or cancelled, so broker
   positions are flat;
4. the next cycle checks positions—not working orders—and sees no TQQQ shares;
5. no child fill is found;
6. `_infer_bracket_exit` nevertheless selects target or stop, closes the local
   row, and may immediately evaluate another entry.

The sanitized archive contains **six inference-warning events joined to five
unique local trade rows**; the sixth warning is a duplicate writer for the same
May 6 closure. All five unique rows were recorded as `target_hit`. Three have an
explicit same-cycle `back-to-back after exit_target_hit_inferred` entry event.

Those records prove that execution-unverified inference was used. They do
**not** distinguish a missed real bracket exit from a never-filled parent.

## Method

The study:

- hashes and token-checks the current trader, broker, state, and reconcile tests;
- traces the entry-local-state → broker-flat → no-fill → inference branch;
- audits whether `_infer_bracket_exit` has an `unknown` / `unverified` outcome;
- hashes the committed sanitized archive and joins inference warnings to trade
  rows by exit type, price, and a maximum two-minute timestamp distance;
- deduplicates multiple warnings that join to the same trade row;
- partitions the six `target_hit` rows into explicitly inferred and not joined;
  and
- measures ledger materiality without pretending that row removal reconstructs
  the path-dependent counterfactual.

Reproduce:

```bash
venv/bin/python tools/overnight_gap_risk_study.py \
  --selfcheck --json /tmp/gap_program_study53.json
```

No trader was started, no broker connection was made, and no protected file was
changed.

## Why broker-flat is not proof of a bracket exit

`get_open_position` calls `ib.positions()` and searches for nonzero TQQQ
shares. A flat position answers “how many shares are held now?” It does not
answer:

- whether the parent was acknowledged or rejected;
- whether an unfilled parent remains active;
- whether any entry execution occurred;
- which order closed a real position; or
- whether a child execution exists.

IBKR exposes these as different evidence streams. Positions arrive through the
positions interface; active orders are retrieved separately; executions arrive
through execution callbacks/requests:

- [Current IBKR TWS API documentation](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/)
- [IBKR positions](https://interactivebrokers.github.io/tws-api/positions.html)
- [IBKR active-order retrieval](https://interactivebrokers.github.io/tws-api/open_orders.html)
- [IBKR executions and commissions](https://interactivebrokers.github.io/tws-api/executions_commissions.html)

IBKR's current documentation explicitly presents position, open-order, order
status, and execution information as separate objects. Therefore “no position”
cannot substitute for “the recorded parent filled and its bracket exited.”

## The inference is total, not evidential

With stored TP/SL prices, `_infer_bracket_exit` has six explicit terminal
TP/SL returns across long, short, and ambiguous cases. It has no `unknown`,
`unverified`, or `pending_close` result.

If the reference price lies beyond a boundary, the corresponding boundary is
used. If it lies between both boundaries, the nearer one is chosen. This
classification is arithmetically complete even when execution evidence is
absent. It answers “which stored boundary is nearer?” rather than “which broker
execution occurred?”

The code comment “Bracket order already exited” is stronger than the predicate
that precedes it. The predicate proves only that the current position query is
flat.

## Constructive phantom path

| State transition | Evidence available | What remains possible |
|---|---|---|
| bracket calls return | application control flow | working, rejected, held, cancelled, partially/fully filled |
| local position written | quote basis + API order ID | all broker outcomes above |
| next position query is flat | zero current shares | parent never filled **or** a real position opened and closed |
| child-fill lookup is empty | no retrieved child execution | history unavailable **or** no child execution existed |
| TP/SL inferred | stored prices + reference quote | classification is not an execution |
| local trade closed | SQLite row | economic round trip still unproved |
| entry block reached | local flat state | another application submission can follow |

This path also couples Studies 51 and 52: working-order blindness enables both
duplicate submission exposure and false local lifecycle completion.

## Sanitized archive join

The archive has 65 trade rows and 149 monitor events. Exact warning text yields
six events:

| Exit date | Trade row | Bars held | Recorded return | Join distance |
|---|---:|---:|---:|---:|
| 2026-04-14 | 17 | 4 | +1.001001% | 0.020 s |
| 2026-04-22 | 21 | 1 | +1.004329% | 0.011 s |
| 2026-04-30 | 34 | 0 | +1.003723% | 0.017 s |
| 2026-05-01 | 40 | 0 | +1.005183% | 0.017 s |
| 2026-05-06 | 45 | 2 | +1.004431% | 0.028 s |

May 6 has a second warning 22.9 seconds after the same trade row. Counting
warnings without joining would overstate the number of closures by one.

The archive contains six total `target_hit` rows. Five join to inference
warnings. The remaining May 1 13:32 row has no such warning and is deliberately
left outside this classification. “All target hits were inferred” would be
false.

Monitor entry events 54, 59, and 81 explicitly say they were placed
back-to-back after `exit_target_hit_inferred`. This proves that the inference
branch reached another application submission in the same cycle three times.
Per Study 52, those events still do not prove the new parents were accepted or
filled.

## Accounting materiality

The five execution-unverified rows compound to **+5.120432%** as a standalone
ledger slice.

| Ledger view | Compounded return |
|---|---:|
| all 65 sanitized rows | +35.411353% |
| all rows except the five inferred factors | +28.815446% |
| endpoint difference | **6.595908 pp** |

This is an accounting attribution, not a causal counterfactual. Removing a
closure can change subsequent eligibility, entry timing, sizing, and exposure;
the study therefore does not call +28.815446% the “true” result. Each inferred
row could represent:

- a real entry and real bracket exit whose execution history was unavailable;
- a real position closed by some other mechanism; or
- no economic entry at all.

The correct classification is **execution-unverified**, with unknown economic
return.

## What remains robust

Study 52's 47-row project exit-confirmed bucket is
`{bracket_exit, stop_hit}`. All five rows here are `target_hit`, so none enters
that bucket. Its recorded quote-basis compound return remains **+0.204664%** and
its adverse entry-basis break-even remains **+0.435020 bp**.

That flat result is not rescued by this audit. If anything, the broader
dashboard history has weaker execution provenance than the already-conservative
47-row slice.

## Falsification gates

A future implementation can eliminate this ambiguity only if it durably joins:

1. signal cycle / intent ID;
2. parent API ID and account-wide permanent ID;
3. acknowledged, held, rejected, cancelled, and active-order states;
4. entry execution ID, shares, price, and time;
5. child permanent IDs and executions;
6. local transaction outcome; and
7. restart reconciliation of both positions and active orders.

When position and execution evidence disagree or are absent, the lifecycle
needs an explicit `unverified` state. It must not force TP/SL PnL merely to
unblock new entries.

Tests should cover rejected, held, never-filled, partial-fill, active-parent,
disconnect, stale-execution-history, manual-close, and crash-between-transmit-
and-SQLite cases in an isolated paper harness.

## Decision use

Treat the five archived inferred rows as execution-unverified and exclude them
from claims of observed fill performance. Do not claim they are proven phantom
trades; the available archive lacks parent acknowledgement and execution data.

Any remediation touches protected broker/trader/state paths. It requires
explicit approval, a stopped trader, paper-only validation, and a durable
order/execution ledger before promotion to `development`.
