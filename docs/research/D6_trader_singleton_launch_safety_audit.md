# Study 51 — Trader singleton and launch-safety audit

**Date:** 2026-07-24<br>
**Status:** read-only operational-risk audit; no live/config/service change authorized<br>
**Artifact:** `tools/overnight_gap_risk_study.py` → `trader_singleton_launch_safety_audit`

## Question

Does the current paper-trader deployment prove exactly one trader process and
exactly one entry intent per symbol/bar, or can a second launch still reach the
bracket path?

## Verdict

**The managed systemd path is substantially safer than the historical
deployment, but end-to-end uniqueness is not proved.** Six repository-visible
launch paths were audited:

- two route through the named service and its ten-check preflight;
- four bypass the full preflight;
- none acquires a shared process-lifetime lock;
- none atomically claims a durable `symbol + bar + direction` order intent;
- `--once` bypasses the scheduler's market-hours wrapper; and
- the direct `--live` CLI contradicts the repository's PAPER-ONLY guardrail.

This does **not** explain Study 48's seven historical double-entry minutes.
It establishes only that current source still lacks an end-to-end proof that
the failure class is unreachable.

## Method

The audit hashes and token-checks the current launch, scheduling, broker, state,
and policy surfaces:

- `AGENTS.md`, `README.md`, and `OPERATIONS.md`
- `ops/preflight_trader_start.sh`
- `ops/start_trader.sh`
- `ops/systemd/monad-trader.service`
- `live/trader.py`, `live/broker.py`, and `live/state.py`
- `config_modules/live.py`

It then enumerates every repository-documented or directly callable launch path,
maps its guards, and constructs an adversarial interleaving from the actual
check/order/state sequence. No trader process was started, no IBKR connection
was made, and no protected file was changed.

Reproduce:

```bash
venv/bin/python tools/overnight_gap_risk_study.py \
  --selfcheck --json /tmp/gap_program_study51.json
```

## Launch-path matrix

| Path | Full preflight | Named-unit scope | Market-hours wrapper | Atomic cross-process lock | Durable cycle key |
|---|---:|---:|---:|---:|---:|
| systemd timer/service | yes | yes | yes | no | no |
| `ops/start_trader.sh` | yes, via service | yes | yes | no | no |
| `ops/start_trader.sh --exec` | no | no | yes | no | no |
| `python -m live.trader` | no | no | yes | no | no |
| `python -m live.trader --once` | no | no | **no** | no | no |
| `python -m live.trader --live` | no | no | yes | no | no |

The default starter is correctly routed through `systemctl`; the service then
runs `ExecStartPre` before `--exec`. The weakness is boundary leakage:
`--exec` is itself callable and verifies only paper configuration plus port
7497, while the documented direct module command bypasses branch, live-port-
closed, account-flat, duplicate-process, health, and writable-state checks.

The README claim that the trader "can never run from an unreviewed branch" is
therefore true only for the service path, not for the documented direct command.

## What each current control really guarantees

### 1. Named systemd unit

Starts addressed to the same service unit stay within one manager-owned unit
path. That is the safest normal route. It does not give repository code
ownership over a separately launched Python process, so the conclusion is
scoped to the unit rather than the host.

### 2. Preflight `pgrep`

The duplicate check is an observation:

```text
pgrep -f "[-]m live.trader"
```

It is followed later by `exec`. There is no atomic claim between them, so two
independent invocations can both observe "absent" before either becomes visible.
The pattern also recognizes the `-m live.trader` form, not every possible way
the module could be invoked.

### 3. APScheduler `max_instances=1`

This prevents overlap for the `hourly_bar` job inside one scheduler. Each
Python process constructs its own `BlockingScheduler` and default in-memory job
store, so a second process owns a second limit. APScheduler itself describes
`max_instances` as the number of instances a scheduler lets run for a job and
warns that job stores must not be shared between schedulers
([official user guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html#limiting-the-number-of-concurrently-executing-instances-of-a-job)).

### 4. Fixed IBKR `clientId=1`

This is meaningful defense in depth. IBKR documents that client IDs distinguish
API clients and that connecting with an ID already in use raises a socket-side
exception
([official connectivity guide](https://interactivebrokers.github.io/tws-api/connection.html)).

It is not a process lease here:

- the trader disconnects after every cycle;
- connection conflicts are retried after 2, 4, and 6 seconds; and
- a later successful connection continues the already-started cycle.

The broker-position reconciliation then usually blocks the second process if
the first entry is filled and visible. But it checks positions, not working
entry orders. A still-working/unfilled first parent can leave the account flat
at exactly the point the second process checks.

### 5. SQLite state

SQLite permits only one simultaneous writer, but that does not make an external
workflow exactly once. The official transaction documentation distinguishes
implicit/deferred transactions from an up-front `BEGIN IMMEDIATE` write claim
([SQLite transaction documentation](https://www.sqlite.org/lang_transaction.html)).

Current business flow crosses separate connections and external side effects:

```text
read local position
check broker position
submit parent
submit take-profit
submit stop
DELETE local position
INSERT local position
```

There is no explicit transaction around that sequence, no uniqueness constraint
on the position or signal bar, and no durable order-intent row. Serializing the
final SQLite writes cannot undo two broker submissions; the later
`DELETE + INSERT` can retain only the second local state.

## Constructive residual race

The following is reachable from current source; it is a possibility proof, not
an observed current incident:

1. P1 and P2 both read `state.get_position() == None`.
2. P1 connects with client ID 1 and verifies the broker position is flat.
3. P2 collides on client ID 1 and enters the built-in retry loop.
4. P1 submits its three-leg bracket, writes local state, finishes, and
   disconnects.
5. P2 connects on a later retry. It does not reread local state.
6. If P1's parent remains working but unfilled, the broker position is still
   flat; the entry guard does not inspect the working order.
7. P2 submits another three-leg bracket and its `DELETE + INSERT` replaces P1's
   local row.

Three common outcomes are safer: P2 may exhaust retries, P1 may fill before P2's
broker check, or only the managed unit may ever be launched. Those possibilities
reduce frequency; they do not falsify reachability.

## Policy contradictions

1. `AGENTS.md` says PAPER ONLY and port 7496 must never be used; `live/trader.py`
   and two README command blocks explicitly expose `--live` and flip
   `LIVE_PAPER_MODE=False`.
2. README's unconditional branch-safety claim applies only to the service
   preflight; direct module launch never checks the branch.
3. `start_trader.sh --exec` is safe when systemd has just completed
   `ExecStartPre`; the executable path itself cannot establish that precondition.

These are documentation/control-plane contradictions, not instructions to
change the protected path in this study.

## Falsification gates

The unresolved verdict would be overturned by evidence of any complete boundary:

1. every launch is mechanically constrained to the named service unit and
   direct invocations are rejected;
2. one nonblocking host lock is acquired before startup side effects and held
   for process lifetime;
3. a durable, atomically unique `symbol + bar + direction` intent is claimed
   before broker submission and reconciled against working orders on retry; or
4. a broker order ledger proves every working parent becomes a visible position
   before any later client-ID retry can pass the current guard.

Operator habit is not a falsifier. Neither are `pgrep`, per-scheduler
`max_instances`, SQLite write serialization, or the client ID in isolation.

## Decision use

For current paper operation, use only the service/default starter path and treat
other entry points as bypasses. Before any production-readiness claim, require
both process ownership and per-bar order-intent idempotency to be mechanically
demonstrable. Any implementation touches the protected live/config/service path
and therefore needs explicit approval with the trader stopped.
