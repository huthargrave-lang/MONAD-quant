# src/ — area context (signals, strategy engine, backtest, analysis)

**Purpose:** the pure, testable strategy/analysis code (no live I/O).
**Run `ctx where <symbol>` to jump to a definition; `ctx route "<task>"` to route.**

## Layout
- `src/signals/` — feature engineering (independently togglable, no cross-talk):
  - `momentum.py` — RSI, MACD, **`classify_regime`** (6-state dual-MA; the core innovation — see `CLAUDE.md` §4, do not casually change).
  - `volume.py` — VWAP z-score → volume_signal.
  - `volatility.py` — ADX, Bollinger, vol_regime.
- `src/strategy/`
  - `engine.py` — **`build_features` → `generate_trades` → `compute_trade_returns`** (regime gate + exit simulation).
  - `sizing.py` — fractional Kelly.
- `src/backtest/runner.py` — backtest loop + Kelly equity curve. Driven by `main.py` / `sweep.py`.
- `src/analysis/run_window.py` — pure dashboard run-window filter helpers (current/all/archive). Tests: `tests/test_run_window.py`.

## Design rules (from CLAUDE.md §12 — do not violate)
- No ML / no inverse ETFs. Every new feature is **togglable via a config flag (default off)**.
- **Never touch the 252-MA regime classifier logic** without strong justification — it's the foundation.
- **No look-ahead bias:** any rolling window used for an entry decision must `.shift(1)`.
- Validate strategy changes on a **full 5yr run**, not a standalone year (252-MA look-ahead bias).

## Tests
`tests/test_signals.py` (signals), `tests/test_execution_model.py` (engine exits), `tests/test_run_window.py` (analysis).

Deep "why" for every parameter and what's been tried/failed: **`CLAUDE.md`** / **`AGENTS.md`**.
