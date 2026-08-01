# Study 55 — Concurrent close idempotency audit

**Date:** 2026-07-24<br>
**Status:** read-only source/archive audit plus isolated temporary-SQLite experiment<br>
**Artifact:** `tools/overnight_gap_risk_study.py` → `concurrent_close_idempotency_audit`

## Question

Study 53 found two May 6 inference warnings but only one local trade row. Does
SQLite guarantee that concurrent trader cycles can record a position close only
once, or did that particular race merely happen to collapse?

## Verdict

**The current close is not idempotent. Two stale readers can sequentially
commit two closed-trade rows for one position.**

`close_position` and `finalize_pending_close` execute this shape:

```text
SELECT the singleton position
if present:
    INSERT a trade using the fetched row
    DELETE the singleton position
commit on context-manager exit
```

The code uses `sqlite3.connect(path)` defaults and no explicit `BEGIN`.
Under Python's current legacy transaction handling:

- the connection context manager does not open a transaction;
- `SELECT` does not trigger the driver's implicit DML transaction; and
- the transaction starts immediately before `INSERT`.

Therefore the following schedule is legal and was reproduced:

```text
A SELECTs and caches position P
B SELECTs and caches position P
A INSERTs trade(P), DELETEs P, commits
B INSERTs trade(P) from its cached row, DELETEs zero rows, commits
```

Result: **two trade rows, zero position rows, no database error**.

SQLite correctly serializes the two write transactions. Serialization is not
the same as an atomic “claim this lifecycle once” operation.

## Deterministic experiment

The artifact creates a temporary SQLite file outside the repository with the
relevant schema and uses two connections. It deliberately stages both reads
before either write, then lets A and B commit in sequence.

| Observation | Result |
|---|---:|
| connection A in transaction after `SELECT` | false |
| connection B in transaction after `SELECT` | false |
| committed trade rows | **2** |
| writer labels | A, B |
| remaining position rows | 0 |
| unique lifecycle constraint | absent |

The experiment does not import `live.state`, touch `live/state.db`, start the
trader, or connect to IBKR.

Python's official documentation says the context manager neither opens a
transaction nor closes the connection, and legacy handling implicitly opens
transactions for `INSERT`/`UPDATE`/`DELETE`/`REPLACE`, not other statements.
SQLite documents that it allows multiple readers and only one writer at a time:

- [Python `sqlite3` transaction control](https://docs.python.org/3/library/sqlite3.html)
- [SQLite transaction semantics](https://www.sqlite.org/lang_transaction.html)
- [SQLite isolation](https://www.sqlite.org/isolation.html)

These primary-source semantics match the experiment on both project runtimes.

## Why the May 6 archive does not prove safety

The sanitized archive contains:

- two `Fill data unavailable — inferred target_hit @ 68.38` warnings;
- 22.9 seconds between the warnings; and
- one local May 6 `target_hit` trade row.

Both writers therefore reached the warning before or around local closure. The
single trade row means the observed scheduling likely let the second
`close_position` re-read after the first delete, or otherwise fail to append.
It does not supply a uniqueness constraint and cannot refute the staged
two-reader interleaving.

This distinction matters: “one row was observed” is an outcome; “at most one
row is possible” is an invariant. The former does not establish the latter.

## Side effects remain duplicated even when the row collapses

`close_position` returns `None` on both success and “no open position.” The
caller does not inspect a result. After the call it can still:

1. synchronize account/mark state;
2. log the summary;
3. send an exit alert;
4. set `exit_action`; and
5. evaluate a new entry in the same cycle.

Thus a losing concurrent caller cannot distinguish “I closed the position”
from “another process already closed it.” Even when only one trade row survives,
duplicate alerts and duplicate entry paths remain reachable. This connects the
close race directly to Studies 48, 51, and 53.

## Accounting sensitivity

The recorded May 6 factor is +1.004431%. Applying it once more to the sanitized
65-row endpoint changes:

| Ledger | Compounded return |
|---|---:|
| observed archive | +35.411353% |
| one duplicated May 6 factor | +36.771467% |
| endpoint difference | **+1.360114 pp** |

This is only a ledger sensitivity. A real duplicate cycle could also create
additional broker exposure, change sizing, or alter later entries; it is not a
counterfactual estimate.

## Schema and test boundary

The `trades` table has no:

- lifecycle/intent ID;
- parent or child permanent order ID;
- uniqueness constraint on an economic close; or
- foreign-key claim tying a close to one position generation.

Current tests cover a successful sequential close and a sequential no-position
no-op. They do not stage two connections after both have read the position.
They also do not require the caller to gate alerts or re-entry on a typed close
outcome.

The same read-then-write pattern exists in `finalize_pending_close`; legacy
pending rows therefore share the risk.

## Falsification gate

An exactly-once local close needs all of:

1. a durable unique lifecycle/intent key;
2. a database uniqueness constraint on that lifecycle;
3. atomic ownership before reading, such as an explicit immediate transaction,
   or a conditional claim whose affected-row count is checked;
4. a typed result distinguishing `closed`, `already_closed`, `conflict`, and
   failure; and
5. caller side effects and re-entry permitted only for the winning close.

Tests must stage two independent connections at SELECT/INSERT/DELETE cutpoints
for inferred bracket exits, retrieved fills, time exits, and pending-close
finalization.

## Decision use

Do not interpret SQLite write serialization as exactly-once trade accounting.
The May 6 one-row outcome is reassuring only for that occurrence. Current code
still admits duplicate PnL rows and, independently, duplicate close side effects.

Any remediation changes protected state/trader paths and requires explicit
approval with the trader stopped. This study records the required invariant and
falsification test; it does not authorize the implementation.
