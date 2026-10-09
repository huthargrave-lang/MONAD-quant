# Miner/metal tilt: forward watch

**Ruled by a board (statistics, process integrity, adversary) on 2026-10-09, and frozen as a
watch spec before the first forward line was logged.**

## Why a watch, and why not a registration

The miner-overshoot tilt (F366200, F366201) held its sign out of sample in all three miner
pairs over 2016-2026. No single test reached 5%, and its pre-2006 test closed NOT RUN with a
stopping rule: **a forward window is the only remaining path** (F366203).

**Gate rules v2 cannot admit it.** Its development stage charges the 1401-statistic
discovery atlas as prior search (p_gate ≈ p × 1402). A pre-registration was rejected for
three reasons:
- the replication protocol pre-stated registration only if its trigger fired, and it did not;
- a registration that rejects by construction tells the reader nothing;
- the registration schema cannot express the sequential rule below.

So this is a **forward watch**: frozen, chained and tamper-evident, explicitly **not an
admission candidate**.

## The record

- **Spec.** `docs/research/forward_watch/<ID>.json`:
  - written once, canonical, named by its sha-256, and needs a current web node;
  - pins the sha-256 of the engine sources (`daily_strategy`, `daily_data`,
    `commodity_classes`, `forward_watch`).
- **Series**, exactly as pre-stated in `MINER_TILT_REPLICATION.md`:
  - daily active = 0.5 × (GDX/GLD tilt book − its 50/50 book) + 0.5 × (SIL/SLV tilt book −
    its 50/50 book), net of costs;
  - the benchmark is therefore 25% in each fund;
  - no GDXJ: adding it after seeing its +0.32 would be a fork, and it nearly duplicates GDX.
- **Rule and books.** The frozen rule (z60, clip(0.5 − 0.25 z, 0, 1)), decided at each close
  and executed at the next open, 21 tranches, tier1 costs, at 1x and 2x costs.
  - The books continue the recorded 2016-2026 books (`replay_from` 2016-01-01).
  - The logger reproduces both recorded series exactly; the tests check this to 1e-12 on the
    original snapshots.
- **Log.** `<ID>.jsonl`, daily after each close, catch-up allowed. Each line records:
  - the previous line's sha-256 (a chain), the spec hash, and a clean code sha (the logger
    refuses a dirty tree);
  - the private snapshot's sha (observations are never committed: option A of
    `DATA_REDISTRIBUTION_AUDIT.md`);
  - every book's return and cost, the pair actives and the combined active at 1x and 2x;
  - a hash of the session's inputs;
  - the book state after the session, at full precision.
- **Revisions cannot rewrite the record.** Each session's return is computed once, from the
  previous line's logged book and pending orders, and never recomputed.
  - A later vendor revision (a late-booked distribution, say) is detected by the input hash
    and booked as a **correction** line with the active delta.
  - Each logging run is a counted trial (family `forward_watch.<ID>.v1`).
- **CI.** `tools/forward_watch.py verify --against origin/development` checks:
  - the chain;
  - spec identity;
  - session contiguity;
  - append-only history, for the watch and for `docs/research/forward/` (H404702's log, which
    had no such check).

## Evaluation, stated in advance

- **When the window opens:** the first session after the spec reaches `development`.
- **Reports:** at the 365-day anniversary, then once a year. Year one decides nothing: even
  at a true Sharpe of 0.3, a negative first year has a 38% chance.
- **Test:** a Wald sequential test of annualised active Sharpe 0 against 0.3 (α 0.05,
  β 0.20), checked on anniversaries only. LLR = T (0.3 S_T − 0.045).

| | Condition | T = 5 | T = 10 | T = 20 |
|---|---|---|---|---|
| **Promote** | S_T ≥ 0.15 + 9.24/T, and the 2x-cost Sharpe > 0 | 2.00 | 1.07 | 0.61 |
| **Close** (refuted) | S_T ≤ 0.15 − 5.19/T | −0.89 | −0.37 | −0.11 |

**VOID:** a change to any of GDX, GLD, SIL or SLV's index or objective, or a merger or
delisting. A successor is a new watch, and its clock resets.

**Error rates.** These are from the board's 200k simulated paths; the tests reproduce them
with a seeded Monte Carlo.

| | 10 years | 20 years | No limit |
|---|---|---|---|
| Promote, true Sharpe 0 | 0.0% | 0.6% | 4% |
| Promote, true Sharpe 0.3 | 1% | 10% | 76% |
| Close, true Sharpe 0.3 | 3% | 7% | 16% |
| Close, true Sharpe 0 | 16% | 41% | 92% |

**What promotion means.** It cannot admit. It triggers a decision debate on a route that
admits on forward evidence (forward data carries no search charge, but the other live
forward records must be charged). Until then the status is **unproven, not tradable**.

**Dissent.** The adversary wanted a 10-year sunset. It was overruled: a sunset adds no
information, and the sequential test is valid whenever it stops.

## Operation

```
venv/bin/python tools/forward_watch.py log <ID>       # after each close; commit and push the log
venv/bin/python tools/forward_watch.py report <ID>
```

Automation (a scheduled run plus a commit) is the owner's decision, so it is not set up by
default.
