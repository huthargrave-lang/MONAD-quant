# Proposal — first slice of VISION Stage 1 ("engine seam" inside `tools/ctx.py`)

Role: PROPOSER. Repo at `2ef7c0c`. Everything below was checked against live code, not docs.

## Question

What is the first change toward Stage 1 that is (1) safe against the existing guards, (2) useful on its own, (3) one PR? Stage 1 names five deliverables (seam, config vocab, `--repo`, engine tests, frozen `graph --json`); the slice must pick.

## Structure found (file:line)

**`tools/ctx.py` — 3,897 lines, 0 commits in the last 60 days (last 2026-08-15)**, so merge-conflict risk is low.

| Region | Lines | Role | Rim coupling inside it |
|---|---|---|---|
| Globals | 30–47 | `REPO/MANIFEST/WEB/DB`, `_ACCT/_CONID`, `_redact` | DB = `live/state.db`; IBKR regexes |
| Query/navigate | 63–740 | route/where/find/usages/defs/tree/summary/covers/can_edit/impact | `_is_protected` (646) hard-codes `live.`/`config_modules.` |
| **Rim block** | 741–1000 | schema/events/config/audit/perf/status/recent | state.db, `config.py`, `ops/status_check.sh`, "Run on the Pi" prose (919–945) |
| **Engine: web** | 1143–1470 | `EDGE_TYPES`/`RELIANCE_EDGES` (1150–1154), cues, `_LINK_RX`, `_parse_web_text`, `STATUS_VALUES/REASON_CODES`, `_propagation_violations`, bridges | none |
| `cmd_web` | 1471–1619 | lint/live/pending | none |
| **Engine: graph** | 1620–1891 | `build_graph`, neighbors/walk/why/contradicts | none |
| **Engine: render** | 1892–2516 | HTML, `_graph_compact` (hard-codes `idea={F,H,E,D,area}` at 2236), `_graph_details`, `_serve_route`, `cmd_graph` | `_graph_details` → `_redact` (2331); `_ui_tokens` resolves `REPO/tools` (2444) |
| **Rim block** | 2517–2742 | SEC lab SQLite projections for `serve` | all rim |
| Engine: health | 2836–3020 | health/claims/staleness | none |
| Rim: drift | 3021–3228 | `operator_fact_drift` | `ops/preflight_*`, `.github/workflows` |
| Engine | 3229–3607 | claims/delta/**init** (3359)/frontier/related | `cmd_frontier` → `_web_banner()` (3490) |
| Rim | 3608–3798 | `_web_banner` → `perf_summary()` (3652), `_RESEARCH_PATHS` (CLAUDE.md, IMPROVEMENT_PLAN), brief/reverts | all rim |
| argparse | 3799–3897 | subcommands scraped by regex `add_parser\("(\w+)"\)` | — |

Hard-coded kind vocabulary: `[FHED]` at ctx 169, 1350, 3021, 3524; `note.py:38 KINDS`, `note.py:246/253`.

**`graph --json` today** (`cmd_graph`, 2480–2516): `{project:str, nodes:[{id,kind,title≤120,status}], edges:[{from,to,type}]}`; 1,113 nodes / 3,028 edges here; **deterministic** (identical md5 on repeat runs). Kinds observed: F,H,E,D,module,config,code,area. Edge types: the 12 web types **plus** bridge relations (`concerns/gated_by/implemented_in`, vocab pinned at `tests/test_context_map.py:164` incl. `measured_by`) **plus** code-layer types (`imports/owns/tested_by/reads_config/defined_in`) that no constant declares. `/api/graph.json` (2374–2386) is a superset (`+summary,+details`); `tests/test_research_web.py:1164` pins its key set **exactly**.

**What the guards pin.** 38 test files import `ctx`; 669 test functions. The four named files = 164 tests, green (`python3 -m unittest …`, 65 s; pytest is not installed here). They pin: module attribute names (`ctx._parse_web`, `ctx.build_graph`, `ctx.EDGE_TYPES`, `ctx.RELIANCE_EDGES`, `ctx.WEB`, `ctx.REPO`, `ctx._render_graph_html`, `ctx._serve_route`, …); stdout strings of `cmd_*` via `redirect_stdout`; node ids `^[FHED]\d+$` (test_research_web:84); every registered subcommand listed in `AGENT_INDEX.md` (test_context_map:245–269); every subcommand smoke-run (`test_cli_smoke`, `init` excluded); `edit_policy.deny` must contain `context_map.json` (test_edit_policy:30). **Nothing consumes `graph --json` output** — the CLI contract is free to gain keys. Tests and `note.py:331` inject by **reassigning `ctx.WEB`**, so the globals are already the de-facto injection point.

**Second-consumer probe.** Copied `ctx.py` into a fresh 3-file git repo: `init --write` works; `graph --json` → 7 nodes / 5 edges; `health` reports **170/100** (scaffold puts `tools/ctx.py` in the `tools` area *and* the allowlist, which the kit's own `test_area_coverage` rejects); `perf` prints "CLAUDE.md … Run on the Pi"; with no manifest, `graph`/`route` die with `FileNotFoundError` (`_manifest`, 48). CONTEXT_KIT's "lift it in 5 minutes" is currently false in three measurable ways.

## Proposal

### (a) The slice — four small cuts, all inside `ctx.py`, no new module

1. **Section seam.** Reorder nothing; add `# ═══ ENGINE ═══` / `# ═══ RIM (MONAD) ═══` banners at the region boundaries above, and a module-level `ENGINE_API = (...)` tuple naming the surface the five in-repo consumers already import (`_parse_web_text, _parse_web, build_graph, _node_meta, _is_superseded, _classify_edge, _code_spans, _propagation_violations, _render_graph_html, _serve_route, EDGE_TYPES, RELIANCE_EDGES, STATUS_VALUES, REASON_CODES`). A guard asserts every name exists and that `note.py`, `export_pages.py`, `research_ui.py`, `graphify_bridge.py`, `epistemic_audit_lab.py` import only from it (research_ui's three `_*_response` SEC calls get listed under a `RIM_API` tuple, so the guard documents the debt instead of hiding it).
2. **Three dependency cuts** so the engine stops reaching into the rim: `REDACT = _redact` hook used by `_graph_details` (default stays MONAD's redactor → identical output here); `BANNER = _web_banner` hook used by `cmd_frontier`; `_manifest()` returns `_EMPTY_MANIFEST` (the `cmd_init` skeleton shape) when the file is absent. Plus `_ui_tokens` resolves `__file__`, not `REPO`.
3. **Vocabulary consolidation, not yet a file.** One `SCHEMA = {"schema_version":"0.1","kinds":{F,H,E,D},"edge_types":…,"reliance":…,"propagation_exempt":…,"bridge_relations":{concerns,implemented_in,measured_by,gated_by},"code_edge_types":{…},"status":…,"reasons":…}` in the engine section; `EDGE_TYPES`, `RELIANCE_EDGES`, etc. become aliases (names unchanged, so 38 importers are untouched); the four `[FHED]` regexes and `_graph_compact`'s `idea` set derive from `SCHEMA["kinds"]`; `note.py` imports `ctx.SCHEMA["kinds"]` and drops its own `KINDS`. **Where it lives:** in code, for this slice. The file-backed override (`context_schema.json`, repo root — *not* `context_map.json`, which is deny-fenced; written by `ctx init`; CI-pinned to `SCHEMA.md §5a`) is slice 2, because an unfenced file that widens `EDGE_TYPES` loosens `note.py`'s link validation — that belongs with Stage 2's `integrations`/fence design, not a refactor PR.
4. **`--repo PATH`** as a top-level argparse option (not a subparser, so the AGENT_INDEX regex guard is unaffected): `_bind_repo(path)` reassigns the same four globals tests already monkeypatch. Lands now — it is what makes the second-consumer test possible without copying files.

### (b) `graph --json` contract

Add exactly two keys; everything else byte-identical:

```
{ "contract": "ctx.graph/1", "schema_version": "0.1", "project": str,
  "nodes": [{"id","kind","title"(≤120),"status"∈STATUS}],
  "edges": [{"from","to","type"}] }
```

Contract test (`tests/test_graph_contract.py`, stdlib only — no jsonschema dep): top-level key set exact; per-node key set exact; `kind ∈ kinds ∪ {module,config,code,area}`; `type ∈ edge_types ∪ bridge_relations ∪ code_edge_types`; all edge endpoints resolve to node ids; no duplicate `(from,to,type)`; two runs equal; `--ideas-only` kinds ⊆ `SCHEMA["kinds"]`; served `/api/graph.json` `nodes`/`edges` equal the CLI's. The served route is **not** changed in this slice (its exact-key pin stays green); it gains the two keys in slice 2 with that one assertion updated. Shape, not content, is frozen — a golden node dump would rot with every `note add`.

### (c) Migration safety

Covered by: `test_research_web` (97 tests: parser, propagation, why/conf, render, served route), `test_context_map` (38: route, impact, bridges, subcommand registry), `test_ctx_drift` (22), `test_edit_policy` (7), `test_cli_smoke`, `test_note*`, `test_web_integrity`, `test_h36/h40/h41` — all 38 ctx-importing files run before and after. Byte-identity proof, scripted in the PR: capture md5 of `graph --json` (after stripping the two new keys), `graph --json --ideas-only`, `graph --html`, `web --lint`, `health`, `why F13`, `frontier "exit logic"`, `claims` on this repo at base and head; all must match. The new fresh-repo test runs `ctx --repo <tmp> init --write` then `graph --json`, `web --lint`, `health` as a subprocess, asserting exit 0 and the contract — the second consumer, in CI.

### (d) Cost and risks

~150 changed lines in `ctx.py`/`note.py` (banners 40, hooks 20, `_manifest` default 10, `SCHEMA` + derivations 45, `--repo` 25, contract keys 5), ~220 lines of tests, ~40 lines docs (CONTEXT_KIT "Repo-wired commands" → point at `RIM_API`; AGENT_INDEX `--repo`; SCHEMA §9 row). 6–10 hours including the before/after run.

Risks: (1) `--repo` must rebind the *same* globals, not add indirection, or `note.py:331`'s `ctx.WEB = tmp` swap silently stops working — guarded by `test_note`. (2) Any `REPO` captured at import I missed shows up as the fresh-repo test reading MONAD files — that is the test's job. (3) Hook defaults must equal current behaviour or the md5 script fails. (4) Fresh-repo `health` 170/100 and the `perf` prose leak are *recorded* by the test as expected-for-now (assert exit 0, not the score), so the slice does not grow into Stage 2. (5) Parallel branches touching `ctx.py`: none in 60 days.

### (e) What Stage 2 then needs

A manifest `integrations` block consumed by `RIM_API` functions (perf/events/status/config/audit/drift/SEC projections no-op when absent); `cmd_init` fixes the allowlist overlap and writes `context_schema.json`; `health` denominators exclude allowlisted modules; guard templates read deny-paths/ports from the manifest; `note.py --repo`; `_is_protected` reads areas instead of `live.`/`config_modules.` literals.

## Objection and answer

**"A seam without a second repo using it is speculative generality."** Three answers. First, the second consumer is not hypothetical: the probe above ran `ctx init` on a fresh repo and found three real defects (score > 100, rim prose leak, manifest crash) that no in-repo test can see; the slice ships that probe as CI, so the seam is *measured*, not asserted. Second, five tools in this repo already import the engine surface — `ENGINE_API` writes down a contract they are already relying on; it adds no abstraction, no module, no indirection, and if Stage 2 never happens the residue is forty comment lines and a `--repo` flag that worktrees/CI need anyway (`perf` already special-cases "worktree/CI" at 919–923). Third, the cheapest honest alternative — do nothing until a real second repo appears — leaves CONTEXT_KIT.md advertising a five-minute lift that demonstrably fails; the slice is what makes that document true, which is a public-readiness blocker in its own right.

## What would change my mind

- The before/after md5 script differs on any command → the hooks changed behaviour; stop and shrink.
- More than one existing assertion needs editing → the seam cuts through pinned surface; redraw it.
- `--repo` needs more than the four globals plus `_ui_tokens` → drop it from the slice, keep the rest.
- The owner decides Stage 2 will move files after all → do the sibling-module split once, not a comment seam first.
- A real external repo adopts the kit before this lands → replace the synthetic fresh repo with it.
