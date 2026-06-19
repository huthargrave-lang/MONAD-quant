---
name: monad-validate-edge
description: Get the HONEST trading edge for MONAD-quant before quoting any performance number. Use whenever a task involves "is the strategy profitable", Sharpe, returns, or whether a result is real. The CLAUDE.md headline numbers (Sharpe 25–94) are a data-sampling artifact — do not trust them.
---

# monad-validate-edge — the truth, not the headline

The performance tables in CLAUDE.md (Sharpe 25–94, "+0.7–3.5%/mo",
"Production-ready") are SUPERSEDED. They came from optimistic-mode backtests on
morning-only data. On full-session, live-representative data the hourly signal has
**no reliable edge** and the live bot is roughly flat — the apparent edge tracked
bar-sampling frequency, not a real instrument or time-of-day effect. Always derive
the number yourself with the tools below. Run from the repo root.

## Steps

1. **Read the confirmed-fill edge from the live state DB:**
   ```bash
   venv/bin/python tools/ctx.py perf
   ```
   Trust the **CONFIRMED-FILL** line, not the compounded/headline line. The
   confirmed-fill figure is the honest, live-representative result. (If it reports
   `live/state.db not present`, you are in a worktree without the DB — run it against
   the deployed checkout, or rely on the research web in step 3.)

2. **See current vs. superseded history:**
   ```bash
   venv/bin/python tools/ctx.py perf --view all
   ```

3. **Walk the research idea-web for the reasoning behind the honest verdict:**
   ```bash
   venv/bin/python tools/ctx.py web          # full graph: findings → hypotheses → evidence
   venv/bin/python tools/ctx.py web --live    # ONLY current, non-superseded nodes
   ```
   `--live` hides retracted nodes. Key honest findings: the edge is a morning-only
   data-sampling artifact (F13), it tracks bar-sampling FREQUENCY not instrument/time
   (F14), and a real edge survives only at a coarse (~3 bars/day) timescale, not the
   hourly cadence the live bot trades.

4. **When you report a number, label it.** Say which line it came from
   (confirmed-fill vs. compounded) and the date. Never paste a CLAUDE.md headline
   Sharpe as if it were current.

## Invariants

- The honest edge ≈ flat at hourly; warn the reader the headline numbers are a
  data-sampling artifact.
- There is NO `validate.py` in this repo — do not cite it. Use `ctx perf` / `ctx web`.
- Read-only task. PAPER ONLY (port 7497, never 7496). Do not edit the strategy/live
  path to "improve" a number without explicit approval.
