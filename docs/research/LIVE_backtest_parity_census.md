# Backtest ↔ live parity census — nothing agrees by construction

**Status:** measured, re-runnable, guarded. **Tool:** `tools/live_backtest_parity.py`
(frozen at `docs/research/data/live_backtest_parity.json`).
**Guard:** `tests/test_live_backtest_parity.py`.

---

## Why

The project's central unexplained fact is that the backtest shows an edge and the live bot
is flat. Individual divergences are on record — [`F141`](../../RESEARCH_WEB.md) (the entry
gate), [`F148`](../../RESEARCH_WEB.md) (the UTC time gate),
[`F26`](../../RESEARCH_WEB.md) (the slope flags) — but the decision inputs had never been
enumerated in one place and each marked agree or diverge.

Every row below is extracted from source when the tool runs, so the table cannot rot as
the code moves.

## The table

| dimension | backtest | live | verdict |
|---|---|---|---|
| entry regime gate | omitted → default `True` | `False` (explicit) | **DIVERGE** |
| intraday time gate | `trade_hours` (UTC hour slice) | `_is_market_hours()` (ET) | **DIVERGE** |
| max hold (time exit) | `MAX_TRADE_BARS = 8` | `MAX_TRADE_BARS_LIVE = 10` | **DIVERGE** |
| position size | `config.FIXED_POSITION_PCT` = 0.10 | literal `0.10` | COINCIDENT |
| slope-regime flags | omitted (default False) | `False` (explicit) | COINCIDENT |
| opposing-signal exit | supported (off) | absent | dormant |
| ATR dynamic stops | supported (off) | absent | dormant |

**0 agree · 2 coincident · 2 dormant · 3 divergent.**

Not one of the seven agrees *by construction*. The two that agree numerically do so by
coincidence of two independent definitions.

## The one this census found

**`MAX_TRADE_BARS = 8` versus `MAX_TRADE_BARS_LIVE = 10`.** The backtest closes a stale
trade after 8 bars; the bot holds for 10. A **25%** difference in the time exit.

That matters more here than it would elsewhere. The target and stop are narrow — 1.00% and
0.50% on the live mode — so a large share of trades resolve on the clock rather than on a
band. [`F17`](../../RESEARCH_WEB.md), the project's most actionable finding, is precisely
*"replace the %-stop with a horizon/time exit"*. The horizon is the mechanism under active
study, and the two paths use different ones.

## The one that is quietly worse

**Position size is duplicated, not shared.**

```python
# src/backtest/runner.py
fixed_pos_pct = getattr(config, "FIXED_POSITION_PCT", 0.08)

# live/state.py::get_position_plan  — "Returns the position sizing plan (fixed 10%)"
position_pct = 0.10
```

Both are 10% today. Nothing connects them. Editing `FIXED_POSITION_PCT` — the obvious way
to change position size, and the value `sweep_sizing.py` documents as the live-alignment
setting — moves the backtest and leaves the bot exactly where it was. This is the most
consequential parameter after the entry gate, and it is the *same class of defect* the
config census found: two paths, one fact, nothing keeping them in step.

## The dormant pair, and why they are counted apart

The backtest supports an opposing-signal exit and ATR dynamic stops. The live path has
neither. **Both flags are off**, so there is no behavioural difference today — counting
them as divergences would inflate the headline.

They are not harmless, though. A sweep that turns either on is modelling an exit the bot
cannot execute, and the result would look like an improvement that fails to reproduce
live. The guard fails if either flag is turned on while the live path still lacks the
capability.

## What this does and does not establish

* It does **not** explain the flat live result. It establishes that the two paths are not
  comparable in at least three ways at once, so the backtest's number was never a
  prediction of the bot's.
* It does **not** rank them. Which divergence costs the most is a question for a
  measurement none of these cycles can run offline — every one needs market data.
* Nothing was changed. `live/**` is fenced and `config.py` is fenced; aligning
  `MAX_TRADE_BARS_LIVE`, or making `get_position_plan` read the config, are one-line
  owner decisions that move live behaviour.
* The census covers **decision inputs**, not execution. Fills, slippage, partial
  execution and the bracket-order mechanics are a separate axis, already covered by the
  execution-semantics work.
