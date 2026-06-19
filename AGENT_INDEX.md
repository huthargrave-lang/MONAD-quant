# 🧭 AGENT INDEX — start here (don't read the whole codebase)

You are working on **MONAD-quant**. Get oriented in ~30 seconds, then drill in only where routed.

## Step 1 — query, don't read
Most facts are a command away (read-only, stdlib-only):

```bash
venv/bin/python tools/ctx.py route "<your task>"   # which files to read + tools to run
venv/bin/python tools/ctx.py where <symbol>        # file:line of a def/class/config key
venv/bin/python tools/ctx.py schema                # state.db tables/columns/counts
venv/bin/python tools/ctx.py config <KEY>          # a config value + where it's set
venv/bin/python tools/ctx.py perf                  # headline + the HONEST confirmed-fill edge
venv/bin/python tools/ctx.py status                # live deploy/runtime state
venv/bin/python tools/ctx.py recent [N]            # recent commits + changed files
venv/bin/python tools/ctx.py map [area]            # the manifest (or one area)
venv/bin/python tools/ctx.py web [node]            # walk the research idea-web (findings→hypotheses→evidence)
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
| Performance / "is it real" | `data/live_runs/analysis_2026-06-17/`, `model_phase_recommendations.md` | `ctx perf` | — |
| Research / edge / which params | `RESEARCH_WEB.md` | `ctx web`, `tools/walkforward_eval.py` | trusting holdout-selected sweep numbers (biased) |

(Or just `ctx route "<task>"`.)

## Step 3 — the docs, layered (read only what you're routed to)

- **`AGENT_INDEX.md`** (this) + **`context_map.json`** + **`AGENT_CONTEXT_PLAN.md`** — navigation/router.
- **Area context (1 screen each):** `live/CONTEXT.md`, `src/CONTEXT.md`, `ops/README.md`.
- **Deep "why":** `CLAUDE.md` / `AGENTS.md` (strategy/model). **Deep "how it runs":** `OPERATIONS.md` (live/ops).

## Non-negotiable invariants (also asserted in CI)
- **Paper only.** API port **7497**; the live port **7496 must never be used**. `config.LIVE_PAPER_MODE=True`, symbol **TQQQ**.
- **Don't modify live trading/order/strategy logic** without explicit approval — the trader auto-starts from `pi-ops-automation`.
- **Never commit** `.env`, raw `*.db`, logs, credentials, or **account IDs**. Push via **SSH**, never to `main`.
- **Heads-up:** the headline **+35%** is mostly broken-bracket artifact; the honest confirmed-fill edge is ~flat (run `ctx perf`).

## Convention
Prefer a `ctx`/tool call over reading a file for any computable fact, and cite `file:line` so the next agent can jump there.
