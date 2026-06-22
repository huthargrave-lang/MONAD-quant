# The Context Kit — a portable, queryable context map for any codebase

> **What this is.** Not docs. A **self-maintaining knowledge graph** of a codebase that an
> agent *queries* instead of reading. It unifies two layers in one walkable graph — the
> **code** (modules, imports, area-ownership, test-coverage, config-reads, all auto-extracted
> by AST) and the **ideas** (findings, hypotheses, experiments, decisions with *typed* edges:
> supersedes / evidenced_by / relies_on / …) — bridges them (a finding points at the symbol it
> concerns), guards it against rot in CI, **measures its own health**, and renders an
> **interactive visual map**. Pure stdlib (the runtime needs no dependency). Lift it into any repo.

## The pieces (engine vs content)

| File | Role | Portable? |
|---|---|---|
| `tools/ctx.py` | **Engine** — all query/graph/traversal/drift logic. Repo-agnostic; reads the manifest. | **Generic** — copy as-is |
| `tests/test_context_map.py`, `tests/test_research_web.py`, `tests/test_area_coverage.py` | **Anti-rot guards** — fail CI if the map drifts from the code/config. | **Generic** — copy as-is |
| `context_map.json` | **Structural content** — areas, invariants→config bindings, param-claims, edit-policy, idea↔code bridges, routing. | **Repo-specific** — `ctx init` scaffolds it |
| `RESEARCH_WEB.md` | **Idea content** — the F/H/E/D graph with typed `[[ID\|type]]` edges. | **Repo-specific** — starts empty |
| `AGENT_INDEX.md` | The ≤1-screen L0 router agents read first. | Repo-specific, tiny |

The split is the point: **one engine, two content files.** Everything trading-specific in this
repo lives in the two content files; `tools/ctx.py` knows nothing about trading.

## Lift it into another repo (≈5 minutes)

1. Copy `tools/ctx.py` + the three `tests/test_*` guards.
2. `python tools/ctx.py init --write` — introspects the source tree + import graph and writes a
   `context_map.json` skeleton (one area per top-level package) and an empty `RESEARCH_WEB.md`.
   It **never overwrites** an existing file.
3. Fill in each area's one-line `summary` + `entrypoints`; add `invariants` you want CI-pinned to
   their `config.KEY` source (the `invariant_sources` pattern); wire your CI to run the guards.
4. `python tools/ctx.py health` — see the coverage score; triage any orphan module into an area.
5. As you learn things, record them: append F/H/E/D nodes to `RESEARCH_WEB.md` with typed edges,
   and add idea↔code `graph_bridges`. `ctx graph --html > map.html` for the visual.

## Command surface

```
QUERY     ctx route "<task>"   ctx where <sym>   ctx config <KEY>   ctx defs/usages <x>
NAVIGATE  ctx brief   ctx frontier "<task>"   ctx walk/why/neighbors/contradicts <node>
MAP       ctx graph [--json|--html]   ctx tree   ctx summary   ctx web [--live|--lint]
GUARD     ctx impact <x>   ctx can_edit <f>   ctx audit   ctx health   ctx reverts
SET UP    ctx init [--write]
```

## What makes it *not plain docs*

- **Computed, never stale.** Anything derivable (symbols, imports, tests, config-reads, the whole
  code graph, the reverted-experiment ledger) is *extracted on demand*, not transcribed.
- **Typed, navigable knowledge.** Idea edges carry a relation type, so `ctx web --lint` can tell a
  *reliance* on a retracted claim (a real problem) from a *provenance* link (fine) — and a task
  near a stale finding pulls the correction into context via spreading activation (`ctx frontier`).
- **Idea↔code bridges.** Editing a symbol surfaces the findings about it (`ctx impact` →
  "F17: the %-stop exit is the architectural flaw"); a finding points back at the code it concerns.
- **CI-enforced honesty.** Drift guards assert the manifest matches `config.py`, doc prose matches
  config, bridges resolve, the web has no dangling/stale-cite edges, and every module is mapped.
- **Self-measuring.** `ctx health` scores coverage + freshness + integrity, so the map's quality
  is a number, not a feeling.
- **Visual.** `ctx graph --html` emits a self-contained interactive force-graph of the whole map.

## Design principles
1. **Query > read** — expose a tool call for any computable fact; reserve prose for *why*.
2. **Auto-extract vs author** — recompute everything deterministic; hand-author only judgment.
3. **Append-only + supersede** — ideas are never deleted; they're marked superseded (with a reason),
   so the history stays navigable and the current truth is decidable.
4. **Guard, don't trust** — every content claim is pinned to a checkable source in CI.
5. **Progressive disclosure** — L0 index → routed area → the one section/symbol you need.

> The deep design narrative (the four-layer architecture, the phased roadmap) lives in
> [`AGENT_CONTEXT_PLAN.md`](AGENT_CONTEXT_PLAN.md). This file is the *operator's* view: what the kit
> is and how to reuse it.
