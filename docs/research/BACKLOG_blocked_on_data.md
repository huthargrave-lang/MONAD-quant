# Six queue items are blocked, not untested ([`H46`](../../RESEARCH_WEB.md) and siblings)

**Status:** measured and mechanised. **Guard:** `tests/test_h46_blocked_queue.py`.

---

## What the backlog asked

*"Test H46 or retire it. An untested hypothesis that is never closed biases the project's
self-measured error rate toward looking stable."* The instruction is right. It just
assumes the item is testable.

## Why H46 is not

H46 is RN-01: estimate the language expected from contemporaneous XBRL results and test
the residual against next-period fundamentals. It needs filing **text** plus **XBRL**, and
the frontier program orders it explicitly — *"only after FD-01 establishes the numeric
baseline"* — while FD-01 waits on the FD-00 corpus backfill.

Probed directly rather than assumed:

```
https://www.sec.gov/                 403 Forbidden  (proxy CONNECT)
https://data.sec.gov/                403 Forbidden  (proxy CONNECT)
https://query1.finance.yahoo.com/    403 Forbidden  (proxy CONNECT)
```

And nothing is committed to substitute: the only FD-00 artifact in the repository is
`fd00_sec_event_clock_fixtures_2026.json` — eight hand-authored clock expectations, not a
corpus. So H46 can be neither tested nor killed here. Retiring it would be worse than
leaving it: nothing has been learned about it.

## It was not alone

The five items directly behind it in the queue are blocked on the same sources:

| node | study | needs |
|---|---|---|
| H46 | RN-01 | filing text + contemporaneous XBRL (and FD-01 first) |
| H48 | TA-01 | multi-year cross-asset price history — equities, ETFs, BTC |
| H49 | EV-01/NG-00 | ALFRED macro vintages, 8-K event codes, CFTC positioning, GDELT, SEC fails-to-deliver |
| H51 | FD-NUM | accession-scoped XBRL facts |
| H52 | FD-AMEND | paired 10-K/A and 10-Q/A accessions plus originals |
| H53 | FD-GRAPH | the filing ledger H51/H52 would produce — blocked twice over |

Six consecutive cycles would each have ended in the same sentence.

## The gap in the queue

The backlog already distinguishes one non-runnable state: `DEFERRED`, for items **an owner
chose not to do**, with the reason recorded and the count reported so a deferral is
visible rather than a disappearance. Nothing covered items **nobody can do here**. The two
are different states with different resolution paths — approval versus access — and a
reader who cannot tell them apart cannot tell what would unblock the work.

`BLOCKED_ON_DATA` now carries the second state, with the same visibility discipline:

* excluded from the ranked queue, so a cycle is not spent re-confirming a block;
* **counted in `next`** — *"6 item(s) blocked on unreachable data and excluded"*;
* listed with per-item reasons under `list --blocked`;
* never silently dropped.

## A block that is never re-tested is a permanent excuse

`list --blocked --recheck` probes each distinct host and reports reachability:

```
https://data.sec.gov/                blocked   URLError: Tunnel connection failed: 403 Forbidden
https://query1.finance.yahoo.com/    blocked   URLError: Tunnel connection failed: 403 Forbidden
https://www.sec.gov/                 blocked   URLError: Tunnel connection failed: 403 Forbidden
```

Any `REACHABLE` line means those items can be un-blocked — delete the entry from
`BLOCKED_ON_DATA` and they return to rotation on the next run.

It is **not** run automatically. A network call inside a plain backlog listing would be
slow and flaky, and the guard asserts that `collect`, `blocked_on_data` and `command_next`
never call it — `recheck_blocks` is the only place this otherwise-offline tool touches the
network.

## The defect this cycle exposed by tripping it

Capturing the finding above linked `H46:relates` — and H46 promptly vanished from the
queue *and* from the blocked list. `source_unresolved` treated **any** Finding→Hypothesis
edge as "answered", so a finding whose entire content was *"H46 cannot be tested here"*
marked H46 tested.

Measured across the web: of **69 open hypotheses**, 24 carry a `resolves` edge and **28
more were suppressed by a non-answering edge alone** — 13 behind a bare `relates`, 14
behind `refines`, 3 `drives`, 2 `supports`. The queue displayed **17**; the honest count
with only `resolves` is **45**.

`ANSWERING_EDGES = {resolves, supports, contradicts}` now decides. `resolves` closes a
hypothesis; `supports`/`contradicts` are evidence bearing on it, i.e. it was tested. The
rest are not answers — `relates` is the weakest link in the vocabulary, `builds_on` and
`drives` point forward rather than back, and `refines` *narrows* a hypothesis while
leaving it open ([`F194`](../../RESEARCH_WEB.md) refines H21, whose 0.02→0.05 proposal is
still untested). The unresolved queue goes **17 → 43**.

That delta is the point: **26 more items now appear** (17 → 43), because that many open
hypotheses were invisible for no better reason than that someone had mentioned them. It is the mirror image of the doc-reachability decision in
[`F212`](../../RESEARCH_WEB.md), where widening the traversal was rejected — same
principle in both directions, that **the edge must actually carry the meaning the metric
assumes.**

A second bug surfaced in the same minute: `blocked_on_data()` filtered the *ranked, limited*
task list, so as soon as the widened queue pushed the frontier children out of the top-6
the blocked count silently went to **zero**. It now builds from unlimited sources, and a
guard pins that — a blocked item must not disappear because something older outranks it.

## What is not claimed

* Nothing about whether H46's hypothesis is *true*. It is untested and remains so; this
  records only that it cannot be tested from here, and what would change that.
* The block is environmental, not a judgement about SEC or any provider — the 403 comes
  from this environment's egress proxy at the CONNECT stage, before any request reaches
  them.
* Six entries is a snapshot. A new frontier child will need a new entry, which is a
  deliberate cost: adding one is a decision someone makes and explains, not something the
  tool infers.
