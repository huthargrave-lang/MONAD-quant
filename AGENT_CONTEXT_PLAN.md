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
