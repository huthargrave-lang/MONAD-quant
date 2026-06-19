---
name: monad-test
description: Run the MONAD-quant test suite the right way. Use after any change, or to verify behavior. The venv is lean — tests run via Python's unittest, NEVER pytest. Picks the minimal relevant test subset via ctx tests <area>.
---

# monad-test — verify with unittest (the venv has no pytest)

The virtualenv is deliberately minimal: `pytest` is NOT installed. Always use the
stdlib `unittest` runner with `venv/bin/python`. Run from the repo root.

## Steps

1. **Find the tests that cover the area you touched** (areas are keys:
   `live_trader`, `signals`, `strategy_engine`, `backtest`, `optimization`,
   `dashboard`, `ops`, `config`):
   ```bash
   venv/bin/python tools/ctx.py tests <area>
   ```
   This prints the exact test files linked to that area, e.g.
   `signals → tests/test_signals.py`,
   `backtest → tests/test_runner_metrics.py`,
   `live_trader → tests/test_trader_flow.py` and others.

2. **Run a single module** (convert `tests/test_signals.py` → `tests.test_signals`):
   ```bash
   venv/bin/python -m unittest tests.test_signals -v
   ```

3. **Run several targeted modules at once:**
   ```bash
   venv/bin/python -m unittest tests.test_signals tests.test_sizing -v
   ```

4. **Run the full suite** (do this before committing anything non-trivial):
   ```bash
   venv/bin/python -m unittest discover -s tests
   ```

5. **If you changed config-derived facts**, also run the drift guard so the manifest
   stays honest with `config.py`:
   ```bash
   venv/bin/python -m unittest tests.test_context_map -v
   ```

## Invariants

- NEVER invoke `pytest` — it is not in the lean venv and will fail.
- A red test is a STOP. Do not commit over failing tests.
- Tests are read-only verification; they do NOT touch the live trader. Never start,
  arm, or connect a live trader to run a test. PAPER ONLY (port 7497, never 7496).
