---
name: monad-sweep
description: Run a MONAD-quant parameter sweep for a ticker and interpret the result honestly. Use when asked to tune/optimize params or explore a new symbol. Sweep numbers are holdout-selection-biased — validate the edge before trusting them, and never apply params to the live trader without approval.
---

# monad-sweep — explore params, then distrust the headline

`sweep.py` is the universal parameter sweep. Its top result is optimistic:
sweep scores are inflated by holdout-selection bias (the best-of-N pick looks better
than it will trade). Treat a sweep as a hypothesis generator, not a verdict. Run from
the repo root.

## Steps

1. **Orient first** — run the commands directly, do NOT invoke `monad-orient`:
   that skill is now an autonomous continuous-research loop and would not return
   here. Its Phase 0 is exactly the two lines below.
   ```bash
   venv/bin/python tools/ctx.py route "sweep params for <TICKER>"
   venv/bin/python tools/ctx.py brief optimization --task "sweep <TICKER>"
   ```

2. **Run the sweep:**
   ```bash
   python sweep.py <TICKER>      # e.g. python sweep.py QQQ
   ```
   (If the lean venv is needed for imports, use `venv/bin/python sweep.py <TICKER>`.)

3. **Validate the edge before trusting any param set** — use the
   `monad-validate-edge` skill:
   ```bash
   venv/bin/python tools/ctx.py perf      # read the CONFIRMED-FILL line
   venv/bin/python tools/ctx.py web --live # current, non-superseded findings
   ```
   Remember F2: holdout-selection bias inflates the sweep. A sweep "win" that does not
   survive the confirmed-fill / research-web check is not a real edge.

4. **Run the relevant tests** (use the `monad-test` skill):
   ```bash
   venv/bin/python tools/ctx.py tests optimization
   venv/bin/python -m unittest tests.test_sweep_scoring tests.test_sweep_repro -v
   ```

## Invariants

- Sweep numbers are biased upward — never quote the sweep's best score as the edge.
- NEVER apply swept params to `config.py` / the live trader without explicit human
  approval. Editing `config.py` hits the strategy path — `ctx can_edit config.py`
  returns `DENY`; treat it as a `monad-preflight` gate.
- PAPER ONLY (port 7497, never 7496). Do not touch the live/order/strategy path.
