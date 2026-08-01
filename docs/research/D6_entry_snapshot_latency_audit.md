# Study 64 — Entry snapshot latency and decision-age audit

**Date:** 2026-07-24<br>
**Status:** observed sanitized runtime timing plus byte-matched source audit;
causal latency attribution and broker execution latency unidentified; no
live/config/order-path change authorized<br>
**Artifact:** `tools/overnight_gap_risk_study.py` →
`entry_snapshot_latency_audit`

## Question

How long after the nominal signal cycle does the application declare an entry,
and does the current workflow bound or revalidate that delay?

## Verdict

**The application entry path is a repeated blocking-snapshot workflow with no
decision-to-submit deadline.**

Every entry path obtains:

1. one broker price through `_sync_account_and_mark`; then
2. a separate broker price inside `place_bracket_order`.

Each `get_tradeable_price` call makes one blocking live snapshot request and can
make a second delayed snapshot request. The two higher-level callers do not
share the first result. Consequently:

| path | snapshot requests | explicit `ib.sleep(2)` time |
|---|---:|---:|
| both price calls succeed on nominal-live branch | at least 2 | 4 seconds |
| both calls exhaust live and use delayed branch | up to 4 | 12 seconds |

Those are source-level counts, not total latency predictions. Contract
qualification, broker position/account queries, signal computation, callback
timing, submission calls, and local writes also consume time.

The sanitized archive contains 72 application `Entry placed` events:

| schedule → application event | result |
|---|---:|
| minimum | 14.377 s |
| median | 20.292 s |
| p75 | 31.269 s |
| p90 | 44.487 s |
| p95 | 48.127 s |
| maximum | 62.949 s |
| at least 30 seconds | **22 / 72** |
| at least 40 seconds | **8 / 72** |
| at least 50 seconds | **3 / 72** |

This endpoint still does **not** prove broker acceptance or execution.

## Reproduce

```bash
venv/bin/python tools/overnight_gap_risk_study.py \
  --selfcheck --json /tmp/gap_program_study64.json
```

The study reads current source and the committed sanitized archive. It does not
import `live.*`, connect to IBKR, submit orders, or modify a protected path.

## Source identity

Archive metadata:

```text
archive  archive_2026-06-18_pre_clean_run
branch   pi-ops-automation
commit   b37a8a8
```

Study 48 previously verified the archived checkout. Fresh `git show` hashing
establishes that its broker and trader files are byte-identical to current:

```text
live/broker.py  492ea965e052780745926e6bcf00984ef2fc8be9b4905f00ef8b4456cb68bcef
live/trader.py  59dfd80451093a3d79d74c3b12b21be53ab66489bc11529496d7bdbd814772ed
```

The observed timings therefore apply to the audited call structure, not merely
to an unrelated historical implementation.

## Current call chain

```text
compute and persist signal
    ↓
verify broker position
    ↓
sync account and mark
    → _resolve_mark_price
    → get_tradeable_price
    → blocking live snapshot (+ delayed snapshot if needed)
    ↓
read account again and size from signal-bar close
    ↓
place_bracket_order
    → get_tradeable_price again
    → blocking live snapshot (+ delayed snapshot if needed)
    → three placeOrder calls
    ↓
write local position
    ↓
emit application "Entry placed"
```

The pre-entry mark quote is not reused to construct the order. The second
snapshot can be newer, which is good for the bracket price, but the signal and
sizing decision continue aging. No code:

- caps total decision-to-submit age;
- re-runs the signal after quote/account waits;
- rejects a cycle that crosses a time boundary;
- joins the two quote requests to one cycle ID; or
- persists quote request/callback/order timing.

The official [IBKR snapshot documentation](https://interactivebrokers.github.io/tws-api/md_request.html)
says snapshots deliver available data over an approximately 11-second span
before `tickSnapshotEnd`. Pinned
[`ib-insync` source](https://ib-insync.readthedocs.io/_modules/ib_insync/ib.html)
shows `reqTickers` blocks on that snapshot future, ends the ticker, then returns.
The adapter’s two-second sleeps happen after the blocking returns, so they add
delay without refreshing the ended snapshot.

## Archive attribution

All 72 entry events occur at minute `:32` or `:33`. Measuring from the nominal
hourly `:32` schedule anchor is complete and does not require joining duplicate
writers:

```text
14.377 to 62.949 seconds; median 20.292 seconds
```

A stricter signal-history join requires a prior signal write in the same UTC
minute:

| strict diagnostic | lower-bound attribution | upper-bound attribution |
|---|---:|---:|
| joined events | 70 | 70 |
| minimum | 12.353 s | 14.169 s |
| median | 18.214 s | 18.242 s |
| p90 | 38.415 s | 38.469 s |
| maximum | 53.795 s | 53.862 s |
| at least 30 seconds | 18 | 20 |

In double-written minutes, the event lacks a writer/cycle ID. Matching the
latest possible signal gives the lower bound; matching the earliest gives the
upper bound. The maximum attribution span is only 1.966 seconds, so duplicate
identity does not explain the tens-of-seconds result.

Two application events spill into `:33` and are excluded from the strict join.
They occur 62.949 and 62.812 seconds after their `:32` anchors.

The archive also has 65 unique entry minutes and seven double-entry minutes,
matching Study 48.

## What the timing does and does not prove

Proved:

- application entry success occurred 14–63 seconds after the nominal anchor;
- current/archived source performs repeated independent price snapshots;
- there is no maximum-latency gate or post-wait signal revalidation; and
- the event occurs only after local state and three submission calls.

Not proved:

- which portion of each observation came from snapshot, account, connection,
  duplicate-writer, or submission work;
- when the selected quote tick itself was produced;
- broker acceptance time;
- parent fill time; or
- whether any archived economic entry occurred.

Total cycle age must not be mislabeled quote age. The second order-construction
snapshot occurs late in the workflow; Study 63 separately shows its field/type
and timestamp are not validated.

## Existing test boundary

Tests mock broker price and order functions. They do not assert:

- number of snapshot requests per entry;
- decision-to-submit deadline;
- reuse versus duplication of mark/order snapshots;
- signal revalidation after broker waits;
- delayed fallback timing;
- minute-boundary behavior; or
- application-event versus broker-acceptance/fill latency.

## Decision

Before any protected-path remediation:

1. eliminate the pre-entry mark snapshot or reuse one validated side-aware
   snapshot under a strict age bound;
2. persist one cycle ID across signal, quote request/callback, order,
   acknowledgement, and execution;
3. impose a maximum decision-to-submit deadline;
4. recompute or reject the signal after deadline breach;
5. test live, delayed, timeout, duplicate-writer, re-entry, and minute-boundary
   paths; and
6. continue to label `Entry placed` as application submission, not execution.
