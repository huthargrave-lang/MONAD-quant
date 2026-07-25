---
name: monad-orient
description: First move on ANY MONAD-quant task. Use before reading code or editing anything. Routes you to the minimal files via the ctx tooling and pins the non-negotiable invariants so you don't read the whole 42k-LOC repo or touch the live path.
---

# monad-orient — cold-start in ~30 seconds, then drill in only where routed

Do NOT open files blindly. Most facts are one read-only command away (stdlib-only,
no network). Run from the repo root with `venv/bin/python`.

## Steps

1. **Read the index first (once):** open `AGENT_INDEX.md`. It is the router; this repo
   is large and CLAUDE.md is deep "why" history with SUPERSEDED performance numbers.

2. **Route the task:**
   ```bash
   venv/bin/python tools/ctx.py route "<your task in plain words>"
   ```
   It prints the minimal files to READ, the tools to RUN, and what to AVOID.

3. **Get the one-screen brief for the area.** Areas are the keys
   `live_trader`, `signals`, `strategy_engine`, `backtest`, `optimization`,
   `dashboard`, `ops`, `config` — NOT `live` or `src`:
   ```bash
   venv/bin/python tools/ctx.py brief <area> --task "<your task>"
   ```
   This emits invariants + the HONEST performance state + the area's files + a
   task route + recent commits.

4. **Jump to definitions instead of reading whole files:**
   ```bash
   venv/bin/python tools/ctx.py where <symbol>        # file:line of a def/class/config key
   venv/bin/python tools/ctx.py defs <file>           # a file's symbol outline
   venv/bin/python tools/ctx.py usages <symbol>       # every reference, classified
   venv/bin/python tools/ctx.py config <KEY>          # a config.py value + where set
   venv/bin/python tools/ctx.py map [area]            # the manifest (or one area)
   ```
   Read ONLY the files ctx routes you to. Cite `file:line` for the next agent.

5. **Before considering ANY edit, check the blast radius and the edit fence:**
   ```bash
   venv/bin/python tools/ctx.py impact <file|symbol|config.KEY>   # reverse-deps + live-boundary reach
   venv/bin/python tools/ctx.py can_edit <file>                   # ALLOW / WARN / DENY
   ```
   A `DENY` line means the live-trader/order/strategy/secret path — STOP and get approval.

6. **Pin these invariants for the whole task (also asserted in CI):**
   - PAPER ONLY. API port is **7497**; the live port **7496 must never be used**.
     `config.LIVE_PAPER_MODE=True`, active symbol **TQQQ**.
   - Do NOT modify live trading / order / strategy logic (`live/**`,
     `src/strategy/**`, `src/signals/**`, `config.py`) without explicit approval —
     the trader auto-starts from `development`.
   - Never commit `.env`, raw `*.db`, logs, credentials, or account IDs. Push via
     SSH; **never push to `main`**.
   - The headline Sharpe 25–94 / "+0.7–3.5%/mo" in CLAUDE.md is SUPERSEDED (a
     data-sampling artifact). For the truth, use the `monad-validate-edge` skill.

7. **If the task is open-ended** — "explore", "find something interesting", "take any
   direction" — stop here and use the **`monad-explore`** skill instead. This repo's
   research substrate (`RESEARCH_WEB.md` + the labs) is a first-class object, and that
   skill gives you the latitude, the live open threads, and the house style for it.
