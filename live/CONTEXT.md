# live/ — area context (read before editing here)

**Purpose:** the live **paper** trading runtime — scheduler, broker I/O, state DB, read-only dashboard.
**Run `ctx route "<task>"` or `ctx where <symbol>` instead of grepping.**

## Entry points (file:line via `ctx where`)
- `live/trader.py::_on_bar_inner` — the per-bar loop: signal → reconcile/exit → entry. The brain.
- `live/trader.py::main` / `run_scheduler` — APScheduler, fires ~:32 each market hour (ET).
- `live/state.py::init_db` — SQLite schema (idempotent migrations). All DB reads/writes.
- `live/broker.py::place_bracket_order` / `get_open_position` — IBKR (ib_insync) bracket + fills.
- `live/dashboard.py::dashboard` — read-only FastAPI monitor.
- `live/signals.py` — live signal fetch (yfinance) + freshness/staleness safety gates.

## The two correctness fixes here (do not regress)
- **Reconciliation guard** in `_on_bar_inner`: blocks entries if the broker holds a position while the DB is flat (`entry_blocked_desync`). Tests: `tests/test_trader_reconcile.py`.
- **Software take-profit** (`USE_SOFTWARE_TAKE_PROFIT`): caps winners at target because the paper bracket TP is unreliable. Tests: `tests/test_software_take_profit.py`.

## Do NOT touch without explicit approval
`trader.py` entry/exit/order logic, `broker.py` order submission, `signals.py` decision logic.
The trader **auto-starts from `pi-ops-automation`** — a bug here corrupts a live paper run.
The dashboard is safe to edit (it does **not** import the trader); never edit `state.py` *writers* for a dashboard task.

## Facts to query, not read
`ctx schema` (DB tables), `ctx status` (is it running), `ctx perf` (real edge), `ctx config <KEY>`.

Deep context: `OPERATIONS.md` (how it runs). Strategy "why": `CLAUDE.md`.
