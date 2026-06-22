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
| `tools/ctx.py` | **Engine** — query/graph/traversal/drift logic, manifest-driven. | **Mostly generic** — the query/navigate/map/guard/init layer is repo-agnostic; **~6 commands are wired to this repo** (see *Repo-wired commands* below) — trim or re-point them |
| `tests/test_context_map.py`, `tests/test_research_web.py`, `tests/test_area_coverage.py` | **Anti-rot guards** — fail CI on drift. | **Templates** — keep the *patterns*; the concrete assertions (ports, golden NL queries, deny-paths) are repo-specific — **adapt, don't copy verbatim** |
| `context_map.json` | **Structural content** — areas, invariants→config bindings, param-claims, edit-policy, idea↔code bridges, routing. | **Repo-specific** — `ctx init` scaffolds a skeleton; you fill it |
| `RESEARCH_WEB.md` | **Idea content** — the F/H/E/D graph with typed `[[ID\|type]]` edges. | **Repo-specific** — starts empty |
| `AGENT_INDEX.md` | The ≤1-screen L0 router agents read first. | Repo-specific, tiny |

**The genuinely repo-agnostic surface** (works on any repo right after `ctx init`):
`route · where · usages · defs · tree · summary · covers · impact · map · tests · web · neighbors ·
walk · why · contradicts · frontier · graph · health · init · brief · can_edit · reverts`.

**Repo-wired commands** — wired to *this* repo; trim or re-point them when you lift the kit. They
degrade gracefully (print "not present" / no-op) rather than crash, but do nothing useful until adapted:
- `perf`, `events` — read this repo's `live/state.db` (`trades` / `monitor_events` schema).
- `status` — shells out to `ops/status_check.sh`.
- `config`, `audit` — assume a top-level `config.py` (+`config_modules/`); `audit`'s drift regex
  targets the `TARGET_GAIN|STOP_LOSS|_PCT` param family — broaden it for your domain.
- `impact`'s live-boundary verdict and `_redact` (IBKR account-id masking) are trading-specific;
  `impact`'s blast-radius + covering-tests output is generic.

So it is **not** "one engine, zero coupling" — it is a generic core plus a thin, clearly-listed
repo-wired rim. Lifting the kit means filling the content files **and** trimming that rim.

## Lift it into another repo (≈5 minutes)

1. Copy `tools/ctx.py`; trim/re-point the *repo-wired commands* above for your domain.
2. `python tools/ctx.py init --write` — introspects the source tree + import graph and writes a
   `context_map.json` skeleton (one area per top-level package) and an empty `RESEARCH_WEB.md`.
   It **never overwrites** an existing file.
3. Fill in each area's `summary` + `entrypoints`; add real **routing keywords/synonyms** (the
   scaffold seeds only the area name per rule — natural-language routing needs more); declare any
   `invariants` you want CI-pinned to their `config.KEY` source (the `invariant_sources` pattern).
4. Copy the three `tests/test_*` guards as **templates** and replace their repo-specific assertions
   (this repo's ports/golden-queries/deny-paths) with yours; then wire CI to run them.
5. `python tools/ctx.py health` (target high coverage / 0 orphan) and `ctx graph --html > map.html`
   (the interactive map). As you learn things, append F/H/E/D nodes with typed edges + idea↔code
   `graph_bridges`.

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
