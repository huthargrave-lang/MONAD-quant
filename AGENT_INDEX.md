# 🧭 AGENT INDEX — start here (don't read the whole codebase)

You are working on **MONAD-quant**. Get oriented in ~30 seconds, then drill in only where routed.

## Step 1 — query, don't read
Most facts are a command away (read-only, stdlib-only):

```bash
venv/bin/python tools/ctx.py route "<your task>"   # which files to read + tools to run
venv/bin/python tools/ctx.py where <symbol>        # file:line of a def/class/config key
venv/bin/python tools/ctx.py find <text-or-regex>  # search code BODIES for behavior → enclosing symbol + governing finding
venv/bin/python tools/ctx.py claims                # implemented_in findings: is each code-behavior claim GUARDED by a test?
venv/bin/python tools/ctx.py delta [--since X]     # git-based 'what changed' in the web/manifest since a base rev (default HEAD~12)
venv/bin/python tools/ctx.py tree [path]           # AST repomap: each module → docstring + class/def names
venv/bin/python tools/ctx.py summary [area]        # per-area rollup of the repomap (one line/module)
venv/bin/python tools/ctx.py covers <symbol>       # which test(s) exercise a symbol (direct + area tests)
venv/bin/python tools/ctx.py schema                # state.db tables/columns/counts
venv/bin/python tools/ctx.py config <KEY>          # a config value + where it's set
venv/bin/python tools/ctx.py perf                  # headline + the HONEST confirmed-fill edge
venv/bin/python tools/ctx.py audit                 # content drift: config %-comments that disagree with the value
venv/bin/python tools/ctx.py status                # live deploy/runtime state
venv/bin/python tools/ctx.py recent [N]            # recent commits + changed files
venv/bin/python tools/ctx.py map [area]            # the manifest (or one area)
venv/bin/python tools/ctx.py web [node]            # walk the research idea-web (findings→hypotheses→evidence)
venv/bin/python tools/ctx.py neighbors <node>      # unified-graph neighbors (idea + code bridges) by edge type
venv/bin/python tools/ctx.py walk <node> [--edge T --depth N]  # BFS the idea graph (e.g. follow a supersedes chain)
venv/bin/python tools/ctx.py why <node>            # grounding experiments + decisions a node bears on (provenance path)
venv/bin/python tools/ctx.py contradicts <node>    # what overturns this node / what it overturns
venv/bin/python tools/ctx.py frontier "<task>" [--budget N]  # task-shaped packet: seeds + corrections, not a fixed summary
venv/bin/python tools/ctx.py graph [--json|--html]  # the whole unified map (idea web ∪ code graph); --html = interactive browser map
venv/bin/python tools/ctx.py serve [--host H --port N]  # serve the live context map as a read-only web app (stdlib; 0.0.0.0 for Tailscale); / = map, /api/graph.json = data
venv/bin/python tools/ctx.py health                # context-map health score: coverage + freshness + bridge/lint integrity
venv/bin/python tools/ctx.py related <node|query>  # semantic search: nodes most similar to a node or free-text (TF-IDF)
venv/bin/python tools/ctx.py uncaptured            # strategy/research commits since the web last moved — what to capture via note.py
venv/bin/python tools/ctx.py init [--write]        # scaffold the context layer for a fresh repo (the kit's portability entrypoint)
venv/bin/python tools/note.py add --kind F --title "..." --body "..." [--link ID:type] [--commit]   # capture a finding into the web (dry-run by default)
venv/bin/python tools/note.py supersede <OLD> --by <NEW> [--reason <code>] [--commit]   # mark a node superseded (write-fenced, lint-gated)
venv/bin/python tools/ctx.py brief <area> --task ".."  # ≤900-tok orientation packet (best first move)
venv/bin/python tools/ctx.py impact <file|symbol|config.KEY>  # blast radius + ⛔ if it hits the live boundary
venv/bin/python tools/ctx.py can_edit <file>       # edit gate ALLOW/WARN/DENY (exit 0/2/1, scriptable)
venv/bin/python tools/ctx.py usages <symbol>       # all references to a symbol, classified
venv/bin/python tools/ctx.py defs <file>           # symbol outline of one file
venv/bin/python tools/ctx.py events [N]            # the trader's own error/event narrative (redacted)
venv/bin/python tools/ctx.py reverts [area]        # what we already tried & abandoned (mined from git)
venv/bin/python tools/ctx.py tests <area>          # which test files cover an area
```

Machine-readable routing/invariants live in **`context_map.json`** (kept honest by
`tests/test_context_map.py`, which fails CI if it drifts from `config.py`).

## Step 2 — task → where to look (quick table)

| Task | Read (minimal) | Run | Don't touch |
|---|---|---|---|
| Strategy / signals / params | `CLAUDE.md` §, `config.py`, `src/signals/`, `src/strategy/engine.py` | `python sweep.py TICKER` | live trader paths |
| Live trader behavior | `OPERATIONS.md`, `live/trader.py::_on_bar_inner`, `live/CONTEXT.md` | `ctx status` | strategy logic |
| IBKR / brackets / orders | `live/broker.py`, `OPERATIONS.md` | `tools/diagnose_brackets.py` | order logic w/o approval |
| Dashboard / UI | `live/dashboard.py`, `templates/dashboard.html`, `src/analysis/run_window.py` | `ops/dashboard_smoke_test.sh` | `live/state.py` writers |
| Ops / systemd / deploy | `OPERATIONS.md`, `ops/README.md`, `ops/systemd/` | `ctx status` | enabling trader autostart w/o approval |
| DB / schema / data model | `live/state.py::init_db` | `ctx schema` | committing raw `.db` |
| Performance / "is it real" | `RESEARCH_WEB.md` (honest edge) | `ctx perf`, `ctx web --live` | CLAUDE.md headlines (superseded) |
| Research / edge / which params | `RESEARCH_WEB.md` | `ctx web`, `tools/walkforward_eval.py` | trusting holdout-selected sweep numbers (biased) |

(Or just `ctx route "<task>"`.)

## Step 3 — the docs, layered (read only what you're routed to)

- **`AGENT_INDEX.md`** (this) + **`context_map.json`** + **`AGENT_CONTEXT_PLAN.md`** — navigation/router.
- **Area context (1 screen each):** `live/CONTEXT.md`, `src/CONTEXT.md`, `ops/README.md`.
- **Deep "why":** `CLAUDE.md` / `AGENTS.md` (strategy/model). **Deep "how it runs":** `OPERATIONS.md` (live/ops).

## Non-negotiable invariants (also asserted in CI)
- **Paper only.** API port **7497**; the live port **7496 must never be used**. `config.LIVE_PAPER_MODE=True`, symbol **TQQQ**.
- **Don't modify live trading/order/strategy logic** without explicit approval — the trader auto-starts from `development`.
- **Never commit** `.env`, raw `*.db`, logs, credentials, or **account IDs**. Push via **SSH**, never to `main`.
- **Heads-up:** the headline **+35%** is mostly broken-bracket artifact; the honest confirmed-fill edge is ~flat (run `ctx perf`).

## Convention
Prefer a `ctx`/tool call over reading a file for any computable fact, and cite `file:line` so the next agent can jump there.
