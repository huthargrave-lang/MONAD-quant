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

### …and then measured, which corrected the framing

The first draft of this section argued the gap was a first-order driver *because* a narrow
band means many trades resolve on the clock. **That was an assumption, and measurement
refutes it** at the volatility this strategy trades. At 0.8%/bar with the live band, across
four seeded panels:

| σ/bar | trades ending on the clock (8 bars) | mean return, 10 bars − 8 bars |
|---:|---:|---:|
| 0.08% | 21.5% | +0.79 bp |
| 0.15% | 14.9% | +1.72 bp |
| 0.25% | 6.3% | +0.93 bp |
| 0.40% | 2.0% | +0.24 bp |
| **0.80%** | **0.2%** (3 of 1759) | **+0.05 bp** |
| 1.10% | 0.2% | +0.04 bp |

The row stays **DIVERGE** — the two configs really do disagree — but its behavioural cost
today is about zero, and the *reason* is what to keep: **the bands resolve before the clock
does.** That reason expires the moment the bands widen, which is why the finding is
recorded rather than dropped.

It also reframes [`F17`](../../RESEARCH_WEB.md), whose recommendation is to replace the
%-stop with a horizon exit. At this volatility the horizon currently fires on roughly 1
trade in 500. Adopting it is therefore not a tweak to an existing mechanism — it is a
**replacement of the exit model**, and its effect cannot be extrapolated from how the time
exit behaves now.

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
* It does **not** rank them by realised cost. It does now size them where a synthetic
  panel can: the entry gate retains 4.0–20.9% of configured entries
  ([`F211`](../../RESEARCH_WEB.md)), the UTC/ET gate keeps 2–3 of 7 session bars
  ([`F148`](../../RESEARCH_WEB.md)), and the max-hold gap is worth ~0.05 bp above
  0.4%/bar ([`F230`](../../RESEARCH_WEB.md), above). Which matters most *on real data*
  still needs market data none of these cycles can reach.
* Nothing was changed. `live/**` is fenced and `config.py` is fenced; aligning
  `MAX_TRADE_BARS_LIVE`, or making `get_position_plan` read the config, are one-line
  owner decisions that move live behaviour.
* The census covers **decision inputs**, not execution. Fills, slippage, partial
  execution and the bracket-order mechanics are a separate axis, already covered by the
  execution-semantics work.
