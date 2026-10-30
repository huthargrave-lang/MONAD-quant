# minimal-research-web — Research Idea Web
<!-- schema_version: 0.1 -->

> **What this is.** A worked example for the Context Kit (`CONTEXT_KIT.md` at the repo root):
> a small software-benchmarking research web — one hypothesis, two experiments, three findings,
> one decision, and one supersession carrying a machine-readable reason. Nothing here is finance.
> Link nodes with `[[ID]]` or `[[ID|type]]`; walk it with `ctx --repo examples/minimal-research-web web`,
> lint it with `web --lint`, explain a node with `why <ID>`, draw it with `graph --html`.

## Findings

### F1 — [SUPERSEDED by F3] Link-time optimisation cuts JSON serialisation time by 14%
<!-- status: superseded; by: F3; reason: data-fixed; conf: 0.3; at: 2026-10-20 -->
Microbenchmark result ([[E1|evidenced_by]]): serialising a 1 KB record 10^6 times took 0.86 s
with LTO against 1.00 s without — a 14% cut, read at the time as "the serialiser is the hot
path, ship LTO". The number was an artefact of the harness, not of the compiler flag; the
superseding finding says how. Kept as history, never deleted — `ctx why F1` reports the reason.

### F2 — p99 request latency is dominated by collector pauses, not serialisation
<!-- conf: 0.8; at: 2026-10-22 -->
In the end-to-end load test ([[E2|evidenced_by]]) p99 was 41 ms on both builds, and the pause
trace attributes ~70% of the p99 tail to garbage-collector pauses. Serialisation is under 2 ms
per request on either build, so no serialiser-side win can move the tail. Bears on [[D1|drives]].

### F3 — LTO's end-to-end effect is ≈3% on p50 — inside run-to-run noise
<!-- conf: 0.75; at: 2026-10-24 -->
Supersedes [[F1|supersedes]]: the 14% in the microbenchmark was a measurement artefact — the CPU
frequency governor was left on `ondemand`, so the LTO build, run second on an already boosted
core, got a warmer clock. [[E2|evidenced_by]] pins the governor to `performance`, alternates the
two builds, and repeats each configuration three times: p50 24.1 ms (LTO) vs 24.8 ms (baseline),
−2.8%, with a 1.1 ms spread between repeats. Resolves [[H1|resolves]]. Bears on [[D1|drives]].

## Hypotheses

### H1 — RESOLVED: does link-time optimisation cut request latency by at least 10%? → NO
Premise: the serialiser is the hot path, so a double-digit serialisation win should show up
end-to-end. Tested by [[E1|drives]] (microbenchmark) and [[E2|drives]] (load test). Closed by
F3's `resolves` edge (`ctx why H1` prints the path); the answer is no — the measured effect is
≈3%, inside noise.

## Experiments

### E1 — DONE: serialiser microbenchmark (1 KB record × 10^6, 5 repeats, warm cache)
Single-process timing loop around the JSON serialiser; the LTO build was run after the baseline
build on the same core. Produced [[F1|produces]]. Harness defect found later: the CPU frequency
governor was not pinned (see F3). Kept as history, not deleted.

### E2 — DONE: end-to-end load test (10k requests at 200 rps, p50/p99, 3 repeats, pinned governor)
Load generator against the service on an otherwise idle host; governor pinned to `performance`,
builds alternated, a GC pause trace captured per run. Produced [[F2|produces]], [[F3|produces]].

## Decisions / Gates

### D1 — Do not ship LTO as a latency fix; spend the next cycle on collector tuning
<!-- conf: 0.7; at: 2026-10-25 -->
Rests on [[F3|relies_on]] (the p50 effect is inside noise) and [[F2|relies_on]] (the p99 tail is
collector pauses). Resolves [[H1|resolves]]. Recommendation applied: LTO stays off the latency
roadmap; a pause-time-budget experiment is the next E-node to add.
