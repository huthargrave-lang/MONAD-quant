# Study #44 — Current Closing-Auction Runtime Readiness

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python -B tools/overnight_gap_risk_study.py --selfcheck --json /tmp/gap-program.json`<br>
**RESEARCH_WEB nodes:** E68 (study) · F79 (finding) · builds on [[F78]]<br>
**Status:** read-only implementation-gap audit; protected live/order/config paths were not changed.

## Question

Does the current paper trader already have the clock, decision, order, calendar, and evidence
plumbing needed for a hypothetical closing-auction flatten?

## Audited snapshot

The artifact reads—but does not import or modify—four runtime files and records their hashes:

| source | SHA-256 |
|---|---|
| [`live/trader.py`](../../live/trader.py) | `59dfd80451093a3d79d74c3b12b21be53ab66489bc11529496d7bdbd814772ed` |
| [`live/broker.py`](../../live/broker.py) | `492ea965e052780745926e6bcf00984ef2fc8be9b4905f00ef8b4456cb68bcef` |
| [`live/signals.py`](../../live/signals.py) | `8038fbd982eace2e5a826898c5d973b229b0b5b772b81006e423f96a15fb78d4` |
| [`ops/systemd/monad-trader.timer`](../../ops/systemd/monad-trader.timer) | `242963d1c3d56d3f2815967568c20edefcce5ca7966a62b5d918203435dbcd2f` |

This makes the result drift-visible: a future source change produces different audit hashes and
must be re-evaluated.

## Readiness matrix

| requirement | current status | evidence |
|---|---|---|
| pre-cutoff nominal scheduling slot | **Partial** | The final regular-session cycle is 15:32 ET, 18 minutes before Nasdaq's 15:50 cancel/modify lock and 23 minutes before its 15:55 MOC acceptance cutoff. |
| frozen t−1 vol20 decision | **Absent** | The live adapter computes the hourly TQQQ strategy; Study #37's QQQ total-return vol20 policy is not implemented. |
| MOC order and primary-exchange workflow | **Absent** | The existing force-close path creates a SMART `MarketOrder`; no MOC constructor exists. |
| cutoff/deadline fail-closed guard | **Absent** | There is no 15:50/15:55 deadline check around the scheduled cycle or broker work. |
| exchange holiday/early-close calendar | **Absent** | The scheduler checks Monday–Friday and `_is_market_hours()` hard-codes 09:30–16:00 ET. |
| NOCP/NOII and auction-status evidence | **Absent** | The live schema does not capture NOCP method, Cross volume, imbalance, auction status, or the Study #43 event record. |
| real auction behavior in paper | **Untestable** | IBKR documents that paper accounts do not support Auction orders. |

## What the 15:32 slot does and does not prove

The 15:32 cycle is nominally early enough on a normal session. That is only a scheduling
observation:

- the cycle first fetches data and reconciles state;
- there is no absolute order deadline or fail-closed timeout;
- the process connects to the broker per cycle;
- no MOC order path exists;
- IBKR paper cannot exercise Auction behavior.

The signal adapter drops a bar whose timestamp is less than 60 minutes old. At 15:32, a Yahoo bar
timestamped 15:30 is therefore removed as incomplete; the latest normally usable bar represents
14:30–15:30. This does not block the selected vol20 hypothesis because that state uses QQQ data
only through t−1, but the live adapter does not implement that hypothesis.

## Early-close finding

Nasdaq's official 2026 calendar sets 13:00 ET closes on Friday, November 27 and Thursday,
December 24
([Nasdaq 2026 trading calendar](https://www.nasdaqtrader.com/trader.aspx?id=Calendar)).
The current scheduler still defines 13:32, 14:32, and 15:32 weekday jobs, while
`_is_market_hours()` treats every weekday through 16:00 as open.

A direct clock-controlled read-only check reproduces the behavior:

```text
2026-11-27 13:32 America/New_York -> _is_market_hours() == True
2026-11-30 16:01 America/New_York -> _is_market_hours() == False
```

At 13:32 after a 13:00 early close, the final bar can also be recent enough to pass the existing
staleness check. Data freshness is therefore not an exchange-calendar safety control. The
practical issue is broader than MOC readiness: the current guard can admit ordinary post-close
trader cycles on an official early-close weekday.

## Decision and falsification

**Not ready.** A nominal clock slot exists, but five load-bearing components are absent: the
selected decision, MOC order path, cutoff guard, exchange calendar, and auction evidence schema.
The early-close guard is additionally unsafe as an exchange-hours oracle.

This finding is falsified only by a new audited snapshot that demonstrates all of the following:

1. official holiday/early-close scheduling with fail-closed tests;
2. a frozen t−1 decision produced before the deadline;
3. a separately authorized MOC path with explicit cutoff behavior;
4. complete intended-event and auction-status logging;
5. evidence from a venue that can actually exercise Auction orders.

Nothing in this study authorizes those protected-path changes or any order submission.
