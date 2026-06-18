# MONAD Quant — Agent Pointer

> 🧭 **Agents: start with [`AGENT_INDEX.md`](AGENT_INDEX.md) and `tools/ctx.py`** (e.g. `venv/bin/python tools/ctx.py route "<task>"`).

**This file used to duplicate `CLAUDE.md` and drifted out of sync** (it carried stale,
optimistic TQQQ parameters that no longer match `config.py`). To kill that drift, the
full strategy memory now lives in **one** place.

## Where to look
| For… | Read / run |
|---|---|
| Strategy / model "why" (signals, regimes, sweeps, what worked/failed) | **`CLAUDE.md`** (authoritative) |
| Live deployment / ops "how it runs" | **`OPERATIONS.md`**, `ops/README.md` |
| Navigation + task routing | **`AGENT_INDEX.md`**, `context_map.json`, `AGENT_CONTEXT_PLAN.md` |
| **Current parameters / facts** (don't trust prose — it can drift) | run **`tools/ctx.py`**: `ctx config <KEY>`, `ctx schema`, `ctx perf`, `ctx status` |

## Two facts every agent should internalize
1. **`config.py` is the single source of truth for parameters** — not any markdown doc. Query it with `ctx config <KEY>`.
2. **The documented backtest headline numbers are NOT reproducible.** A fresh realistic-mode
   backtest of the live TQQQ config yields ~**+0.08%/mo (Sharpe ~1.2)**, and the live paper
   confirmed-fill edge is ~**flat (+0.2%)** — versus the ~+2%/mo / Sharpe 39 once documented.
   Treat headline performance claims with skepticism; run `ctx perf` for the honest read.
