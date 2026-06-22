# MONAD Quant — Agent Context Architecture (Plan)

> **Goal:** Give coding agents the *specific* information a task needs **without reading
> the whole codebase every time.** Replace "read 10k lines to orient" with "read a small
> index, route to the minimal set, and *run a tool* for anything that can be computed."
>
> This is a **plan**. Sections marked **[EXISTS]** are already in the repo; **[BUILD]**
> are proposed artifacts with enough spec to implement directly. Suggested build order is in §8.

---

## 0. The problem

The repo has excellent but **prose-heavy** memory: `CLAUDE.md` + `AGENTS.md` (~1,160 lines of
strategy), `OPERATIONS.md` (live/ops), `README.md`, `ops/README.md`, and several
`data/live_runs/*.md`. An agent that reads all of it burns thousands of tokens before
doing anything, and most of it is irrelevant to any single task. We want **progressive
disclosure**: tiny index → area context → deep docs/code, plus **tools that answer
questions** so agents query instead of read.

## 1. Principles

1. **Query > read.** If a fact can be *computed* (DB schema, current deploy state, where a
   symbol is defined, what changed recently), expose a **tool call**, not a doc to scan.
2. **Progressive disclosure.** Three layers (§2). An agent should be able to do 80% of
   tasks reading only **L0 + one L1 file**.
3. **Machine-readable first.** A small structured manifest (`context_map.yaml`) an agent
   greps, instead of parsing prose.
4. **Task-routing.** Map task *types* → the minimal file/section set (§3).
5. **Stable anchors.** Cite `file.py:line` and stable section IDs; keep deep docs append-only
   where possible so anchors don't drift.
6. **Auto-fresh.** Anything derivable from code/DB/git is **generated**, never hand-maintained,
   so it can't go stale (§7).

## 2. The three-layer context model

| Layer | Artifact | Size | When an agent reads it |
|---|---|---|---|
| **L0 — Index/Router** | `AGENT_INDEX.md` + `context_map.yaml` **[BUILD]** | ≤1 screen | **Always, first.** "What do I read/run for task X?" |
| **L1 — Area context** | `CONTEXT.md` in each key dir **[BUILD]** + existing `OPERATIONS.md`, `ops/README.md` | ≤1 screen each | When the task touches that area |
| **L2 — Deep memory + code** | `CLAUDE.md`/`AGENTS.md`, the modules themselves, `data/live_runs/*` | large | Only the specific section the router pointed to |

## 3. Task → context routing table (the core mechanism)

Lives in `AGENT_INDEX.md` (and machine-readable in `context_map.yaml`). Example:

| If the task is… | Read (minimal) | Run (instead of reading) | Don't touch |
|---|---|---|---|
| Strategy / signal / param change | `CLAUDE.md` (relevant §), `config.py`, `src/signals/`, `src/strategy/engine.py` | `python sweep.py TICKER` | live trader paths |
| Live trader behavior | `OPERATIONS.md` §4–6, `live/trader.py::_on_bar_inner`, `tests/test_trader_*` | `bash ops/status_check.sh` | strategy logic |
| IBKR / orders / brackets | `live/broker.py`, `OPERATIONS.md` §5 | `venv/bin/python tools/diagnose_brackets.py` | order-submission logic w/o approval |
| Dashboard / UI | `live/dashboard.py`, `live/templates/dashboard.html`, `src/analysis/run_window.py` | `bash ops/dashboard_smoke_test.sh` | `live/state.py` writers |
| Ops / systemd / deploy | `OPERATIONS.md` §6–9, `ops/README.md`, `ops/systemd/` | `systemctl list-timers 'monad-*' 'ibkr-*'` | trader autostart enable w/o approval |
| Data / DB schema | — | `ctx schema` (or read `live/state.py::init_db`) | committing raw `.db` |
| Performance / "is the edge real" | `data/live_runs/analysis_*`, `model_phase_recommendations.md` | `ctx perf` | — |
| "What's running right now" | — | `bash ops/status_check.sh` | — |

## 4. Proposed artifacts

### 4.1 `context_map.yaml` **[BUILD]** — the machine-readable manifest
One small file an agent greps to route. Sketch:

```yaml
project: MONAD-quant
deploy_branch: pi-ops-automation
invariants:                 # facts agents repeatedly need
  paper_only: true
  api_port_paper: 7497
  api_port_live_forbidden: 7496
  active_symbol: TQQQ
  timezone_pi: Europe/London
  schedule_tz: America/New_York
areas:
  live_trader:
    files: [live/trader.py, live/state.py, live/broker.py, live/signals.py]
    entrypoints: ["live/trader.py::_on_bar_inner", "live/trader.py::main"]
    tests: [tests/test_trader_reconcile.py, tests/test_software_take_profit.py]
    docs: ["OPERATIONS.md#4", "OPERATIONS.md#6"]
    do_not_touch_without_approval: true
  signals:
    files: [src/signals/momentum.py, src/signals/volume.py, src/signals/volatility.py]
    docs: ["CLAUDE.md#3", "CLAUDE.md#4"]
  dashboard:
    files: [live/dashboard.py, live/templates/dashboard.html, src/analysis/run_window.py]
    tests: [tests/test_run_window.py]
  ops:
    files: [ops/]
    docs: ["OPERATIONS.md#6", "ops/README.md"]
facts:                      # how to GET a value rather than where it's documented
  current_mode: "config.LIVE_SYMBOL"
  deploy_state: "run: bash ops/status_check.sh"
  db_schema: "run: ctx schema"
  recent_changes: "run: git log --oneline -15 pi-ops-automation"
```

### 4.2 Per-area `CONTEXT.md` stubs **[BUILD]**
≤1 screen each, in `live/`, `src/`, (and reuse `ops/README.md`). Template:
`Purpose · key entrypoints (file:line) · what NOT to touch · the 3 facts you need · link to the deep doc.`
These prevent "read the whole module to understand it."

### 4.3 Symbol / definition index **[BUILD, auto-generated]**
`AGENT_SYMBOLS.md` (or `tags`) mapping `function/class/config_key → file:line`, generated by
`ctags -R` or a tiny AST walker. Lets an agent jump straight to a definition instead of grepping
blindly. Regenerate on commit (§7).

### 4.4 The context CLI: `tools/ctx.py` **[BUILD]** — query, don't read
A single read-only entrypoint so an agent *asks*:

| Command | Returns |
|---|---|
| `ctx route "<task description>"` | The routing-table row(s): files to read + tools to run |
| `ctx where <symbol>` | `file:line` for a function/class/config key (from the symbol index) |
| `ctx schema` | `live/state.db` tables, columns, row counts (read-only) |
| `ctx config <KEY>` | the value of a `config.py` key + where it's set |
| `ctx status` | wraps `ops/status_check.sh` (deploy state) |
| `ctx perf [--view current|all]` | headline metrics from `state.db` (compounded, confirmed-fill) |
| `ctx recent [N]` | last N commits + changed files on the deploy branch |
| `ctx tests <area>` | which test files cover an area (from `context_map.yaml`) |
| `ctx map [area]` | print the `context_map.yaml` entry |

Design notes: read-only; no network unless asked; **redacts account IDs**; refuses nothing
(pure information). ~150 LOC wrapping git/sqlite/grep + the manifest.

## 5. Tool-call catalog (run these instead of reading)

**Already available [EXISTS]:**
- `bash ops/status_check.sh` — full deploy/runtime state (system, gateway, trader, data freshness).
- `venv/bin/python tools/diagnose_brackets.py` — IBKR connection + positions + bracket state (read-only).
- `cat local_logs/healthcheck.json` — latest health snapshot.
- `bash ops/dashboard_smoke_test.sh` — verify the dashboard server.
- `git log --oneline -N pi-ops-automation` / `git diff --stat` — recent change surface.

**Proposed [BUILD]:** the `tools/ctx.py` subcommands above (the single highest-leverage item).

## 6. Conventions for agents (write these into `AGENT_INDEX.md`)

- **Read L0 first; drill down only as routed.** Don't read `CLAUDE.md`/`AGENTS.md` whole —
  jump to the cited section.
- **Prefer a tool call over a file read** for any computable fact (state, schema, symbol, diff).
- **Cite `file:line`** in your reasoning/output so the next agent can jump there.
- **Respect the invariants** block (paper-only/7497, don't-touch lists) before editing.
- **Keep deep docs append-only** where practical so anchors stay stable.

## 7. Keeping it fresh (auto-generation)

The fast layer must never lie. Generate the volatile parts:
- `AGENT_SYMBOLS.md` and the `db_schema` portion → regenerated by a `make context` / pre-commit
  hook (`ctags` + `ctx schema --emit`).
- `context_map.yaml` `invariants`/`facts` → validated against `config.py` in CI (a test that asserts
  e.g. `api_port_paper == config.IBKR_PORT_PAPER`), so drift fails the build.
- `OPERATIONS.md` §11 changelog → append one line per significant ops change (cheap, manual).
- Everything else (prose memory) stays human/agent-maintained but is *pointed to*, not *required reading*.

## 8. Suggested build order (low effort → high leverage)

> **Status (2026-06-18): items 1–5 are BUILT and committed.** Only item 6 (auto-generated
> symbol index) is deferred — `ctx where <symbol>` already covers definition lookup live.
> The manifest is JSON (`context_map.json`), not YAML, to avoid adding a venv dependency.

1. **`AGENT_INDEX.md`** ✅ — the L0 router + the §3 table + §6 conventions.
2. **`context_map.json`** ✅ — machine-readable manifest (§4.1). Consumed by `ctx` + CI.
3. **`tools/ctx.py`** ✅ — `route`, `where`, `schema`, `config`, `perf`, `status`, `recent`, `map`, `tests`.
4. **CI invariants test** ✅ — `tests/test_context_map.py` asserts the manifest matches `config.py` + files exist.
5. **Per-area `CONTEXT.md`** ✅ — `live/CONTEXT.md`, `src/CONTEXT.md`.
6. **Auto-generated `AGENT_SYMBOLS.md`** ⬜ (deferred) — `ctags`/AST + a `make context` hook.

## 9. Anti-patterns to avoid

- **More prose ≠ more context.** Don't add long docs that must be read in full; add *routers* and *tools*.
- **Hand-maintained derived data** (schemas, symbol maps, "current state") rots — generate it.
- **Duplicating facts** across `CLAUDE.md`/`AGENTS.md`/`OPERATIONS.md`/manifest → pick one source of
  truth per fact (code for invariants, manifest for routing, deep docs for *why*).
- **Unstable anchors** — renaming sections/reordering files breaks every citation; prefer append-only.

---

### How this complements existing files
- `CLAUDE.md` / `AGENTS.md` = **why** (strategy/model). `OPERATIONS.md` = **how it runs** (live/ops).
- This plan adds the **routing + query layer** on top so agents reach the right `why`/`how`
  without reading all of it.

---

# Part II — The Context Web (v2): a navigable idea map

> **Status (2026-06-22):** Part I (the L0/L1 router + `ctx` query layer) is **built**. Part II
> upgrades the *research/idea* memory from "linked notes" to a **typed, self-invalidating
> knowledge graph** an agent can walk. **Phase 1 (items 1, 2, 4 below) is shipping now**;
> 3, 5–11 are specified for later. Pure-stdlib, git-diffable, CI-enforced — **no new runtime
> dependency** (the deployed Pi venv stays clean).

## 10. Why v2 — the gap Part I leaves

Part I made *structural* facts queryable (`ctx route/where/impact/map`) and *anti-drift*
(`test_context_map.py` asserts the manifest matches `config.py`). But the project's
**highest-stakes evolving knowledge** — the research idea web (`RESEARCH_WEB.md`: Findings,
Hypotheses, Experiments, Decisions) — is still effectively linked notes. Three gaps keep it
from being a navigable idea map:

1. **Edges are untyped.** Every relation — *supersedes, evidence-for, relies-on, contradicts,
   drives* — collapses to one `[[ID]]`. `ctx web --lint` even says so: it can only emit an
   advisory "stale-cite" because it "needs typed edges to tell produced-from from relies-on"
   (`tools/ctx.py`, the `--lint` branch). The relation verbs are already written in the prose
   (*supersedes / evidence / resolves / refines / drives*) — recovering them is the single
   highest-leverage, lowest-cost change.
2. **The idea graph and the code graph never touch.** `F17` ("the fixed %-stop exit is the
   architectural flaw") doesn't point at `engine.py::compute_trade_returns` or
   `config.STOP_LOSS_PCT_*`. An agent told "retune the TQQQ stop" never discovers the finding
   that says the whole approach is dead.
3. **Fact *content* is unguarded.** Part I's guards protect *structure* (do files/tests exist?
   do manifest invariants match config?) — not the *numbers in prose*. That's exactly where
   this repo rots: `config.py` ships `TARGET_GAIN_PCT_TQQQ_HOURLY = 0.0100 # 2.80% target`
   (value 1.00%, comment 2.80%) and `STOP_LOSS_PCT_TQQQ_HOURLY = 0.0050 # 1.50% stop` (0.50% vs
   1.50%); `CLAUDE.md` §6 says `MAX_TRADE_BARS=20` while `config.MAX_TRADE_BARS=8`. The docs lie
   and nothing catches it.

## 11. The four-layer stack

| Layer | What it adds | Generalizes (proven pattern) |
|---|---|---|
| **L0 — Substrate** | one in-memory graph `G` built at `ctx` startup from all sources, one ID namespace | the on-demand `_import_graph()` / `_parse_web()` |
| **L1 — Representation** | typed nodes (research F/H/E/D + code A/S/P + truth M/INV/X) and **typed, directed edges** | the `[[ID]]` link parser |
| **L2 — Truth maintenance** | source-of-truth *binding*, contradiction detection, structured supersession, confidence decay | `invariant_sources` + `test_invariants_match_config` |
| **L3 — Navigation** | typed traversal (`walk/why/contradicts`), spreading-activation `frontier`, budget-aware packet | `_route_rules` + `ctx brief` |
| **L4 — Authoring** | `ctx note add/supersede` write-fenced capture, auto-extract vs hand-author split, freshness GC | `ctx reverts` (git-mined ledger) + `ctx can_edit` fence |

### L1 — typed edges (the load-bearing addition)
Extend the link syntax to **`[[ID|type]]`** (explicit wins). Untyped `[[ID]]` falls back to a
deterministic **cue classifier** that reads the nearest preceding relation verb in the prose,
degrading to `relates` so nothing regresses. Canonical edge vocabulary, split by what `--lint`
needs to know:

- **Reliance** (this node's claim *depends on* the target being true): `relies_on`, `supports`,
  `refines`, `builds_on`. A reliance edge into a **superseded** node is a real stale-cite **problem**.
- **Lineage / provenance** (points back at history or evidence — fine to be old): `supersedes`,
  `contradicts`, `evidenced_by`, `produces`, `derived_from`, `drives`, `resolves`.
- **`relates`** (default / unknown): stays **advisory**, never a hard error.

This resolves the ambiguity the code laments today and turns the "produced-from vs relies-on"
distinction from a comment into a check.

### L2 — truth maintenance (the hit on "context storage rots")
Context stops being a pile of summaries that silently decay and becomes **self-invalidating**:
- **Source-of-truth binding.** Generalize `test_invariants_match_config` (which already asserts
  `invariants[k] == getattr(config, source[k])`) to *all* fact content: a `param_claims` table
  binds documented params to `config.KEY`; CI fails on mismatch. **(Phase 1, item 4.)**
- **Contradiction detection.** A stdlib check parses `config.py` lines `NAME = <num> # <num>% …`
  and asserts comment == value — catching the TQQQ `0.0100`/"2.80%" class the moment it appears.
  **(Phase 1, item 1 — `ctx audit`.)**
- **Structured supersession + reason codes** (item 3): replace the `"SUPERSEDED"`-in-title string
  match with `status: {current|superseded|retracted}` + `reason: {reversed|refined|data-fixed}`.
- **Confidence decay** (item 9): `eff_conf = base × decay(age) × (0 if any relies_on is retracted)`.
  Stale ≠ deleted — decayed nodes stay navigable as history, demoted, never surfaced as current.

### L3 — navigation (the hit on "I don't want basic summaries")
Replace fixed-resolution summaries with **task-shaped progressive disclosure**:
- Entry resolution = keyword (`_route_rules`) + structural exact-match + git-recency boost.
- **Spreading activation** `frontier(task)`: seed at entry nodes, spread along edges with
  type-weighted decay; `supersedes`/`contradicts` edges get ~0.95 decay so any task near a stale
  claim pulls the correction into context with high rank — *deterministically*.
- Typed verbs: `ctx walk F13 --edge supersedes`, `ctx why <node>`, `ctx contradicts <node>`;
  cross-graph `ctx impact` already does the code side.
- **Budget-aware packet** (`--budget 900`, matching `ctx brief`): always include the honest-state
  spine + any `supersedes`/`contradicts` neighbor of a seed; pack the rest by activation; mark
  the overflow `[+expand N tok]`.

The worked example Phase 1 unlocks: **"retune the TQQQ hourly stop"** → seeds `config.ACTIVE_MODE`
+ `area:strategy_engine` → the `concerns`/`contradicts` bridges surface `F13` (Sharpe superseded —
sampling artifact), `F17` (the %-stop exit *is* the flaw → `compute_trade_returns`), and `D4`
(goal reachable only as daily-MR + horizon exit) **before** the agent reads `CLAUDE.md`'s wrong
headline number.

### L4 — authoring & lifecycle (so the map populates itself)
Bright line: **auto-extract** anything a deterministic AST/git walk can recompute (modules,
symbols, config keys, reverted-experiment nodes via `ctx reverts`); **hand/agent-author** only
judgment (findings, decisions, what-failed-and-why). `ctx note add/supersede` is a write-fenced
capture verb (writes only to `RESEARCH_WEB.md`, never code/live path, refuses on lint failure) that
auto-stamps provenance (SHA, branch, `file:line`). Convention for agents: *a result not in the
graph is one the next agent will re-derive.*

## 12. Prioritized roadmap

| # | Change | Effort | Phase |
|---|---|---|---|
| 1 | `config.py` comment-vs-value drift guard (`ctx audit` + `test_config_comment_matches_value`) | ~1 hr, stdlib | **1 ✅** |
| 2 | Typed edges in `_parse_web` (`[[ID\|type]]` + cue classifier; grouped `ctx web` output + typed `--lint`) | ~60 LOC | **1 ✅** |
| 4 | `param_claims` bindings + drift test (MAX_TRADE_BARS / RSI / GDXU) | ~30 LOC | **1 ✅** |
| 3 | Structured `status`/`reason` metadata (retire the `"SUPERSEDED"` string match) | ~40 LOC | **2 ✅** |
| 5 | `graph_bridges` (idea↔code) + CI target check (~15 curated rows) | tiny | **2 ✅** |
| 6 | Unified `build_graph()` + traversal verbs (`walk`, `why`, `contradicts`, `neighbors`) | ~200 LOC | **2 ✅** |
| 7 | `ctx frontier` — spreading activation + budget packer | ~120 LOC | **2 ✅** |
| 8 | note-capture (`add`/`supersede`) + self-capture convention | ~250 LOC | 3 (scoped) |
| 9 | Confidence decay + confidence-weighted `ctx brief/route/frontier` | ~80 LOC | 3 (scoped) |
| 10 | `experiments.jsonl` ledger commit + CI freshness guard | ~50 LOC | 3 (scoped) |
| 11 | (optional) Embedding/TF-IDF sidecar (offline precompute, `ctx related`) | ~6 hr | deferred (scoped) |

## 13. What Phase 1 + 2 shipped (built & CI-guarded)
**Phase 1** — `ctx audit` config comment-vs-value guard (catches the two live TQQQ bugs, baselined
since `config.py` is deny-fenced); typed edges (`[[ID|type]]` + cue classifier, reliance-vs-provenance
`--lint`); `param_claims` binding drift-prone params to `config.py`.
**Phase 2** — structured `<!-- status:…;reason:… -->` supersession (`_node_meta`, retires the title
substring match); `graph_bridges` idea↔code edges (so `ctx impact compute_trade_returns` surfaces F17
+ D4); unified `build_graph()` + `ctx neighbors/walk/why/contradicts`; `ctx frontier` spreading-
activation packet (corrections pulled in first, budget-bounded). All stdlib, read-only, no new venv dep.

## 14. Phase 3 scoping outcomes (explore pass — decisions for the owner)
- **#8 note-capture — recommend a SEPARATE `tools/note.py`, not a `ctx` subcommand.** `ctx` advertises
  *"Read-only: never writes"* (`tools/ctx.py:16`); a write verb would break that contract. `tools/note.py`
  would `add`/`supersede` nodes in `RESEARCH_WEB.md` (freely writable — not deny-fenced) with: refuse-on-
  `ctx web --lint`-failure, only-ever-write-`RESEARCH_WEB.md`, auto-assign next ID, atomic temp+rename,
  and provenance auto-stamp via `_git()` (SHA/branch/date). **Owner decision: do we want agents to write
  to the research web at all?**
- **#9 confidence decay — feasible now (git ages are free) but modest value; minimal slice only.** Only 3
  nodes carry `conf:` and none carry `at:`; `git log -S "### F13" -- RESEARCH_WEB.md` cheaply dates a node
  (headers are immutable). Minimal slice: weight `ctx frontier` seeds by `eff_conf = conf × decay(age)` and
  demote stale nodes. Defer the full framework until `conf:`/`at:` are populated (e.g. by #8).
- **#10 `experiments.jsonl` ALREADY EXISTS** (5 records, appended by `sweep.py:1696`) but is **`.gitignore`d**
  (line 8) — *correcting the earlier "does not exist" note*. `src/optimization/sweep_repro.py::data_fingerprint(df, requested_start, requested_end) -> dict`
  (SHA256[:16] of the OHLCV) is real and reusable but **not yet in the record**. Remaining work: enrich the
  record with `data_fingerprint`, add a read-only `ctx experiments` + freshness guard, and **un-ignore +
  commit the ledger — gated on a secrets/PII audit + owner approval** (it's data, currently untracked by design).
- **#11 embedding sidecar — recommend a stdlib TF-IDF sidecar (offline-precomputed, committed JSON) with a
  `difflib` fallback, NOT a real model** (torch on ARM Pi is unviable; the venv must stay clean). ~6 hr.
  Deferred: the typed graph + `ctx frontier` already cover safety-critical navigation; `ctx related` is a
  nice-to-have semantic search, non-blocking.
