# Re-evaluating findings that predate the admission gate

Decision (2026-09-22): the Findings already in RESEARCH_WEB.md are re-evaluated, not
grandfathered. `tools/reevaluate_web.py` (`src/research/reeval.py`) sorts every Finding
into one tier and queues the ones that need work; `tools/research_backlog.py` feeds that
queue to the research loop.

| Tier | Meaning | Action |
|---|---|---|
| settled | superseded or retracted | none |
| decided | has a decision in `decisions.jsonl` | none |
| guarded | a test named after it exists | CI re-checks it |
| **market** | mentions performance and has no decision | **classify first** |
| traceable | cites evidence | spot-check later |
| unverified | cites nothing | locate evidence, or narrow and supersede |

`decisions.jsonl` is append-only (CI-checked). A **positive edge** claim must end as one of:
`admitted` (cite the `docs/research/verdicts/` record), `reproduced` (cite the `TR-` ledger
run), `narrowed` (cite the superseding node), or `unadmitted_historical`. It cannot be closed
with `no_action`: before the gate, nothing checked those claims, and saying so is the result.

When the queue is empty, the next step is making a Finding without a reproducible run
record a lint error (the plan's schema stage 3), which this re-evaluation is the
prerequisite for.
