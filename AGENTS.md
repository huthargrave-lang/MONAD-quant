# MONAD Quant — Agent Pointer

> 🧭 **Agents: start with [`AGENT_INDEX.md`](AGENT_INDEX.md) and `tools/ctx.py`** (e.g. `venv/bin/python tools/ctx.py route "<task>"`).
>
> MONAD Quant is a **quantitative finance research base** (evidence graph + research compendium +
> governance tools + Context Kit); the trading engine is its **reference test bench**
> (`docs/REFERENCE_ENGINE.md`). Public framing: `README.md`, `VISION.md`; contribution workflow:
> `CONTRIBUTING.md`.

**This file used to duplicate `CLAUDE.md` and drifted out of sync** (it carried stale,
optimistic TQQQ parameters that no longer match `config.py`). To kill that drift, the
full strategy memory now lives in **one** place.

## Where to look
| For… | Read / run |
|---|---|
| Strategy / model "why" (signals, regimes, sweeps, what worked/failed) | **`CLAUDE.md`** (authoritative) |
| Reference engine as documented for users (modes, execution model, sweep tool, paper trader, deployment) | **`docs/REFERENCE_ENGINE.md`** |
| Research programs, methodology, how a study is made | **`docs/research/README.md`**, **`CONTRIBUTING.md`** |
| Live deployment / ops "how it runs" | **`OPERATIONS.md`**, `ops/README.md` |
| Navigation + task routing | **`AGENT_INDEX.md`**, `context_map.json`, `CONTEXT_KIT.md` (run `ctx docs`) |
| **Current parameters / facts** (don't trust prose — it can drift) | run **`tools/ctx.py`**: `ctx config <KEY>`, `ctx schema`, `ctx perf`, `ctx status` |

## Two facts every agent should internalize
1. **`config.py` is the single source of truth for parameters** — not any markdown doc. Query it with `ctx config <KEY>`.
2. **The engine's documented headline numbers are superseded research history, not current fact.**
   A fresh realistic-mode backtest of the live TQQQ config yields ~**+0.08%/mo (Sharpe ~1.2)**,
   and the live paper confirmed-fill edge is ~**flat (+0.2%)** — versus the ~+2%/mo / Sharpe 39
   once documented. That reconciliation is a recorded, verified result (`F13`/`F43`/`D6`), so
   cite it rather than re-deriving it; run `ctx perf` for the current read.
3. **A result not in the web is one the next agent re-derives — capture it.** When you establish
   a finding/decision, record it with `tools/note.py add` (dry-run by default; `--commit` to write);
   walk it with `ctx web`. Don't leave hard-won conclusions only in chat.

## Commands (imperative — this is the cross-tool surface)
```bash
# orient (do this first — don't read the whole codebase)
venv/bin/python tools/ctx.py route "<task>"        # files to read + tools to run
venv/bin/python tools/ctx.py brief <area> --task "<task>"   # ≤900-tok orientation packet
# test — uses unittest (NOT pytest; the venv is lean). discover, or one module:
venv/bin/python -m unittest discover -s tests
venv/bin/python -m unittest tests.test_<area> -v
# before committing
venv/bin/python tools/ctx.py can_edit <file>       # ALLOW/WARN/DENY (DENY ⇒ stop)
venv/bin/python ops/secret_scan.py --staged        # blocks secrets/raw DBs (install: bash ops/hooks/install.sh)
```

## Guardrails (non-negotiable — also enforced in CI + a PreToolUse hook)
- **PAPER ONLY.** IBKR paper port **7497**; the live port **7496 must never be used**.
  `config.LIVE_PAPER_MODE=True`, active symbol **TQQQ**.
- **Do NOT modify the live-trader / order / config path** (`live/**`, `config.py`,
  `config_modules/`) without explicit approval and the trader stopped — `ctx can_edit` and
  `ops/guard_edit.py` (a PreToolUse hook) mechanically **DENY** these writes (the Pi runs
  whatever is checked out on `development`). The **strategy/signal layer** (`src/strategy/**`,
  `src/signals/**`) is *not* mechanically fenced — it's editable, but it feeds the live signal,
  so get approval and validate before it reaches `development`.
- **Never commit** `.env`, raw `*.db`, logs, credentials, or **account IDs**. Push via **SSH**,
  never to `main`. `ops/secret_scan.py` is the commit-time gate.
- **Validate on the full realistic backtest / `ctx perf`**, never a standalone year or the
  superseded headline numbers.
