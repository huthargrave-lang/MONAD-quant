# Config reachability census — 29 of 203 constants are unread by shipping code

**Status:** measured, re-runnable, guarded. **Tool:** `tools/config_reachability.py`
(output frozen at `docs/research/data/config_reachability.json`).
**Guard:** `tests/test_config_reachability.py`.

---

## Why count

Three findings in this repository say the same thing about a single knob each:

* [`F145`](../../RESEARCH_WEB.md) — a sizing flag with no reader anywhere, and two
  multiplier columns computed and consumed by nothing.
* [`F224`](../../RESEARCH_WEB.md) — `BULL_BREAKOUT_ENABLED` gates only whether its own
  column is computed; flipping it leaves entries byte-identical.
* [`F225`](../../RESEARCH_WEB.md) — the backlog's supersession filter read a key the
  parser never emits, so it never fired.

Three anecdotes are a pattern claim without a denominator. Nobody had counted.

## The census

| class | n | % | meaning |
|---|---:|---:|---|
| static | 95 | 47% | a first-party module names it literally |
| dynamic | 79 | 39% | reached via a `getattr(config, f"PREFIX_{mode}")` template WITH a resolvable suffix |
| tests-only | 6 | 3% | named only under `tests/` |
| unreferenced | 23 | 11% | named nowhere outside the config layer |
| **dead to shipping** | **29** | **14%** | unreferenced + tests-only |

**Modelling the dynamic dispatch is what makes the number honest.** A literal-name grep
calls **108** constants dead. **29** actually are. The other 79 are resolved through
per-mode templates — `build_features` alone resolves nine parameters that way
(`RSI_PERIOD_{suffix}`, `MACD_FAST_{suffix}`, `VWAP_ZSCORE_THRESH_{suffix}`, …), and
`strategy_funnel.py`, `walkforward_eval.py` and `sweep.py` add more. Any audit of this
config that does not model the dispatch over-reports dead knobs by **4×**.

`dynamic` is a *reachability* claim, not proof any run reads it: a per-mode constant for a
mode nobody selects is reachable and unread. It is kept as its own class for that reason
rather than folded into `static`.

**And a prefix match alone is not reachability.** The first version of this census
credited any name matching a template, which over-credited two constants whose suffix is a
**regime**, not a mode — `TARGET_GAIN_PCT_STRONG_BULL` and `RSI_OVERSOLD_BEAR`. No code
anywhere builds those names, because the only dispatch is mode-keyed. The suffix is now
validated against `config.ASSETS`, which moved both into the dead set (27 → 29). See
[`F227`](../../RESEARCH_WEB.md).

## Why the headline is a union

`unreferenced` is not stable under observation. Naming a dead constant in a guard moves it
to `tests-only` — so a test that pins the dead set changes the dead set. Writing the guard
for this study moved three constants across that line (`BEAR_SHORT_MAX_BARS`,
`BEAR_SHORT_STOP_PCT`, `ROC_PERIOD`).

The question worth asking is **"does shipping code read this?"**, and
`unreferenced + tests-only` answers it invariantly. The sub-classes are still reported,
because "documented only by its own guard" and "documented nowhere" are different
situations — but the ratchet is on the union.

## What the dead set contains

Not a uniform pile:

* **14 per-mode backtest windows** — `BACKTEST_START_*` / `BACKTEST_END_*` for QQQ,
  QQQ_HOURLY, TQQQ_HOURLY, SOXL_HOURLY, LABU_HOURLY, TNA_HOURLY, GDXU_HOURLY. Every mode
  declares a date range and **nothing reads any of them.** A reader picking a mode would
  reasonably assume its backtest span is configured here. It is not.
* **2 reverted-experiment parameters** — `BEAR_SHORT_MAX_BARS`, `BEAR_SHORT_STOP_PCT`,
  from the bear-shorts attempt CLAUDE.md §7 records as reverted at 0% win rate. Dead
  because the feature was removed, which is the *benign* case.
* **2 live knobs** — `LIVE_BOOTSTRAP`, `LIVE_MIN_TRADES_FOR_ADAPTIVE`, defined in
  `config_modules/live.py` and read by nothing under `live/`.
* **2 hold limits** — `MAX_TRADE_BARS_QQQ`, `MAX_TRADE_BARS_STRONG_BULL` (the latter
  commented "6 weeks max in strong bull").
* **indicator periods** — `ATR_PERIOD`, `BB_STD`, `ROC_PERIOD`, `ROC_PERIOD_HOURLY`.
  `ROC_PERIOD` is the one knob in the whole set that is honestly labelled: its own comment
  reads *"Legacy param — computed but unused; kept for config compatibility."*

## What this does and does not say

* It does **not** say the 27 are bugs. A reverted experiment leaving its parameters behind
  is tidy-up debt, not a defect. The backtest windows are different — they read as
  configuration for something the code decides elsewhere.
* It does **not** say the 176 reachable ones do anything. Reachability is not effect:
  F145's `regime_kelly_mult` is *written* and read by nothing, and F224's breakout column
  is computed and read by nothing — neither is a config constant, so neither appears here.
  A companion census over *computed columns* would be a different measurement.
* The tool cites F145's flag by node id rather than by name. Naming it in prose made the
  census itself the flag's only "reader" and tripped F145's own guard — a detector that
  changes what it measures by describing it, the seventh instance of that class here.
* Nothing was deleted. `config.py` and `config_modules/` are fenced, and removing a
  constant is an owner decision; the guard ratchets the count in both directions so the
  number cannot drift silently either way.
