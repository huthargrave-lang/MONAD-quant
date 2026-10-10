# Overnight handoff, 2026-10-09 → 10-10

**TL;DR.**
- **The overnight study read NO CREDIT.** A fallen-angel credit sleeve does not improve the
  static 60/40.
  - Against the product, the effect is within noise.
  - Against a sleeve holding only its own stock and bond exposure, it is measurably worse.
  - It deepens the drawdown before 2022 and in the 2007-12 credit crisis.
  - F404731's credit-sleeve wording is retracted (F366209).
- **A correction is recorded:** the metal-trust tilt's return partly reflects metal timing (F366210).
- **All forward records are current.** Both watches are logged through 2026-10-09 on one
  branch, and the H404702 weekly line is in.
- **Two small fixes are open as PRs:** #67 (buckets page) and #68 (trial-ledger provenance).
- **Nothing was merged.**

## What changed overnight

| Item | Where | Result |
|---|---|---|
| Next-study board (3 members) | — | 2-1 for the credit-sleeve study. A second board was unanimous for no second study |
| Credit-sleeve mix study | #64 (`CREDIT_SLEEVE_MIX_PROTOCOL.md`, frozen after two adversarial review rounds) | **NO CREDIT** at 5, 10 and 20% (F366209) |
| Metal-trust correction | #64, web only | The frozen watch protocol says the negative control "confirmed no beta exposure". It read UNDERPOWERED: metal timing +0.23 of +0.56%/yr (t 2.4), hedged α t 1.1 (F366210). The frozen doc and spec are untouched. |
| Forward watches | sessions logged through 2026-10-09 (H366200, H366201) | Both chains verify, and each evaluator hash matches its attestation |
| H366200 evaluator attest | #65 | #65's data-store change touches a pinned source, so it is attested where it is introduced. Every merge prefix of the stack is self-consistent |
| Logging branch | #66 only, from now on | Lower branches hold prefixes of the chains |
| H404702 weekly forward line | #66 | 160 holdings as of 2026-10-09; the log verifies (2 entries) |
| H366201 fetch (Saturday) | #66 | CEFConnect still returns the panel through 2026-10-02; Friday's weekly NAV was not yet published. Monday's run will pick it up |
| Buckets page fix | PR #67 | `PRICES` redeclaration and the `LEDGER` stripped on Pages, both fixed and browser-verified |
| Trial-ledger provenance | PR #68 | A run's own fresh snapshot no longer reads as dirty code. New data is named with its hash, and admission still requires it committed |

**CI at handoff:** #64 and #65 green; #66 running; #63, #67 and #68 red, on `h38` only (see 2).

## Decisions that are yours

1. **Merge order:** #63 → #64 → #65 → #66. #67 and #68 are independent.
   - Merging the stack is what opens both watch windows: they open on the first session after each spec is on `development`.
   - Forward days before that are logged but not counted.
2. **The `h38` routing vocabulary.** Every PR whose merge view crosses the bound fails it.
   - `development` sits at 79/400 missed commit subjects, and a PR's synthetic merge commit adds the 80th, against a strict < 20% bound.
   - **No fix is committed anywhere.** Correcting an earlier statement: #63 contains no synonym change.
   - A measured addition is ready for your sign-off, because `context_map.json` is protected. It adds 23 domain keywords to three routing entries, generic single words removed:
     - Entry 12 (daily-strategy research): protocol frozen, product domain, spinoff, buyback, micro-cap, illiquidity premium, credit sleeve, deletion rebound, insider purchase, insider cluster, forward watch, metal trust, miner tilt, miner overshoot, trial ledger, familywise, dsr, parity census, dollar volume.
     - Entry 10: handoff, workqueue.
     - Entry 11: stocktwits, allocation page.
   - Its effect, measured in memory:

     | Measure | Today | With the addition |
     |---|---|---|
     | Commit-subject misses | 19.75% | 14.75% |
     | Same, in CI's merge view | 20.00% | 15.00% |
     | Web titles | 15.99% | unchanged |
     | Off-domain controls routed | 1 of 12 | unchanged |

   - The alternative is to have the audit skip machine-written merge subjects. That changes the metric's definition.
3. **Ratify FORWARD_ROUTE_PROPOSAL.md:** the drawdown budget and the founding-cohort split.
   - The credit study read its drawdowns at a zero budget. Its numbers must not be used to set the budget.
4. **Public or private book states**, and whether to **schedule the daily fetch and log.** Scheduling needs your permission.

## Operations (until the stack merges)

- **Daily, after the US close,** in the #66 worktree with a clean tree, then commit and push there:
  - `forward_watch.py log H366200`
  - `forward_watch.py fetch H366201`
  - `forward_watch.py log H366201`
  - H366201's session t reads only NAVs dated before t, so a same-evening log is valid.
- **Weekly, after Friday's NAVs,** on #66: `forward_log.py H404702`. Its fetched data stays local by design (`local_logs/forward_data/`).
- **When a pinned source changes:** `attest-evaluator` on the branch that introduces the change, then merge it up the stack.
- **Nothing is scheduled.** No process keeps running after this session.
