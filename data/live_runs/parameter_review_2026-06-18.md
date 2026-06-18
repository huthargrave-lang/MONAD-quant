# Parameter & Codebase Review — 2026-06-18

Read-only review of the codebase, tests, and parameters (no trading logic or live
params changed; the trader was armed for the 09:22 ET run). Branch: `pi-ops-automation`.

## Headline conclusion

**No parameter changes are warranted — the live config already matches the documented
realistic-mode optima for every mode.** BUT a fresh empirical backtest shows those
documented optima **do not reproduce their claimed performance**, which is the finding
that actually matters.

## 1. Tests
- **156/162 pass.** The only failure is `test_dashboard.py` failing to *collect* (the Pi
  venv lacked `httpx`) — a dependency gap, not a logic failure. **Fixed** by adding
  `requirements-dev.txt` + a CI that installs it and runs the whole `tests/` dir.
- Startup `_validate_config` (main.py) enforces `stop < target`, required keys, valid mode routing.

## 2. The parameters are at the documented optimum
Every `ASSETS[mode]` entry matches CLAUDE.md's realistic-mode sweep (all 2:1 R:R except the
GDXU placeholder). The live mode, **TQQQ_HOURLY** = `target 1.0% / stop 0.5% / RSI 80 / VWAP 0.5`,
is the documented realistic optimum and the only leveraged-ETF mode that was *explicitly
re-swept under realistic same-bar pessimism*. So by the docs, TQQQ is the right live choice;
SOXL/LABU/TNA show higher headline Sharpes but were not realistic-revalidated; GDXU is not
production-ready.

## 3. ⚠️ The empirical reality (the important part)
A fresh **realistic-mode backtest of the live TQQQ config** on current data
(2024-06-23 → 2026-04-10, 3,117 hourly bars):

| Metric | Fresh realistic backtest | Documented (CLAUDE.md §17) |
|---|---|---|
| Avg monthly | **+0.08%** | +2.02% |
| Sharpe | **~1.19** | 39.0 |
| Trades/yr | **~84 (~7/mo)** | ~288 (~24/mo) |
| Total return | +1.45% | +61% (24mo) |

**The documented numbers are ~30× optimistic and not reproducible.** This **agrees with the
live evidence**: the paper run's confirmed-fill edge is ~flat (+0.2%; `ctx perf`). Likely
causes (not yet root-caused — a follow-up, not done here): far fewer signals fire than
documented (~7 vs ~24/mo), the realistic same-bar pessimism, a possibly favorable documented
window, and the known walk-forward `sqrt(252)` Sharpe inflation for hourly modes.

**Implication:** the "ideal parameters" are settled, but the *ideal evidence* (a clean live
run + a re-validated realistic sweep) is not. Do **not** rely on the documented +2%/mo.

## 4. Issues fixed in this review (safe, non-trader)
- **`matplotlib` made optional** in `src/backtest/runner.py` → the backtest now runs on the
  minimal Pi venv (it crashed on import before). Stats unchanged; only the PNG is skipped.
- **Backtest date clamp bug fixed** (`main.py`): clamped `bt_start` to *exactly* the 730-day
  boundary (which yfinance rejects) and ignored future `bt_end`; now clamps a 5-day margin
  inside and caps `bt_end` at today. The backtest was previously unrunnable (0 bars).
- **`requirements.txt` regenerated** from the live Pi venv (the old one was stale: pinned
  `numpy==1.23.5`/`pandas==2.3.3`/`matplotlib`, missing `ib-insync`/`fastapi`/`uvicorn`).
  Added **`requirements-dev.txt`** (matplotlib, httpx, pytest).
- **CI fixed**: installs the right deps, runs the **whole** `tests/` dir, and triggers on
  `pi-ops-automation` / `fix-**` (was 4 hard-coded files on `main`/`claude/**`).
- **`AGENTS.md` deduplicated** to a pointer — it was a stale copy of CLAUDE.md carrying
  optimistic TQQQ params (RSI 60 / target 0.42% / stop 0.08%) that contradicted `config.py`.

## 5. Deferred (would touch the armed trader / runtime — do after a clean run)
- Removing the ~12–15 dead config params (`ROC_PERIOD`, `ATR_PERIOD`, `BB_STD`, `BB_WINDOW_*`).
- `pip install` of matplotlib/httpx into the **live** venv (could perturb numpy/pandas).
- A fresh realistic **re-sweep** to establish honest optima (heavy; needs the dep + compute).
- Fixing the walk-forward `sqrt(252)` Sharpe annualization for hourly modes (roadmap A.2).

## Recommendation
Leave the parameters as-is and **let the clean paper run produce the real number.** The next
analytical step is a realistic re-sweep (post-run), not re-tuning blind — the current optima
demonstrably don't deliver their documented performance.
