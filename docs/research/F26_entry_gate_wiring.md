# F26 — which entry gates in `generate_trades()` actually move entries

**Status:** code measurement, reproducible offline. No market data, no return claim.
Written because [`F26`](../../RESEARCH_WEB.md) was flagged as carrying figures with no
reachable document. Its figures reproduce. The probe also **corrects one of my own earlier
findings** ([`F194`](../../RESEARCH_WEB.md)), which is the more consequential half.

**Artifacts:** `tools/entry_gate_probe.py`, output frozen at
`docs/research/data/f26_entry_gate_probe.json`. Reproduce with:

```
python3 tools/entry_gate_probe.py --json docs/research/data/f26_entry_gate_probe.json
```

**On the data.** This repo ships no cached market panel and the market-data hosts are
network-blocked here, so every panel below is a seeded synthetic tape. That is adequate
for the wiring questions — whether a flag can reach `entry_signal` at all is a property of
the code, and a synthetic frame exercises the same branches — and it is why every
*magnitude* is reported as a range over several generated regimes rather than as a single
number. Where a figure would change with real data, it is labelled.

---

## 1. The slope flags cannot reach `entry_signal` — structurally, not just empirically

F26 claim (c) says "all 4 `(use_slope_regime, longs_only)` combos give byte-identical
entries". That reproduces, but the empirical check is the weaker statement. The AST says
why:

```
generate_trades():
  entry_signal written at lines      [151, 152, 153, 187]
  use_slope_regime/longs_only read   [190, 190, 200, 200]
  regime_kelly_mult written at       [195, 205, 206]
```

Every read of either flag is **after** the last write to `entry_signal` (line 187, inside
the soft 50-MA block), and every statement guarded by them assigns to `regime_kelly_mult`.
The flags therefore cannot change entries *for any input*, which is stronger than "did not
change entries on the panels tried". The empirical run is a check on the source reading,
not the evidence for it: across 8 panels (4 regimes × hourly/daily), the four combinations
produced **1 distinct `entry_signal` hash each time**.

They are not inert on the column they do write. `regime_kelly_mult` took up to **3 distinct
values** across the four combinations on the same panel — so the flags are live code that
mutates a quantity `runner.py` and `sizing.py` never read (that no-reader fact is
[`F145`](../../RESEARCH_WEB.md), independently guarded).

`runner.py:107` passes `require_signals`, `target_gain_pct`, `stop_loss_pct`,
`trade_hours` — and nothing else. So the flags are never even supplied.

> Reading `regime_kelly_mult` here tripped F145's "consumed by nothing" guard, which
> counts any first-party file mentioning the name. The probe reads it to *demonstrate* the
> knob is dead, which is evidence for that claim rather than a counterexample, so
> `tests/test_web_code_claims.py` now carries a one-file observer exemption — ratcheted,
> and paired with a check that no exempted file ever multiplies anything by a dead knob.
> Applying it would still fail the guard.

## 2. The gate that *does* run, sized

`use_regime_filter` defaults to `True` in the signature and `runner.py` never overrides it,
while `config.USE_REGIME_FILTER` is `False` — F26's "separate non-inert bug", also
[`H27`](../../RESEARCH_WEB.md)/[`F140`](../../RESEARCH_WEB.md)/[`F141`](../../RESEARCH_WEB.md).
Entry counts with the gate as-run versus as-configured:

| panel | timeframe | as-run (default `True`) | as-configured (`False`) | retained |
|---|---|---:|---:|---:|
| drift_up | hourly | 181 | 898 | 20.2% |
| drift_down | hourly | 92 | 908 | 10.1% |
| flat | hourly | 138 | 875 | 15.8% |
| choppy | hourly | 190 | 907 | 20.9% |
| drift_up | daily | 22 | 139 | 15.8% |
| drift_down | daily | 4 | 99 | 4.0% |
| flat | daily | 16 | 129 | 12.4% |
| choppy | daily | 24 | 184 | 13.0% |

The backtest keeps **4.0%–20.9%** of the entries its own config asks for. F140 measured
12.5% on one synthetic panel; this is the same effect across eight, on both timeframes,
and the spread shows the figure is panel-dependent — it should be cited as a range, not as
"12.5%".

## 3. The correction: the soft 50-MA gate's "hourly" branch is unreachable

`generate_trades` branches the soft 50-MA gate on whether a `regime` column exists:

```python
if "regime" in df.columns:
    # Daily mode: only gate STRONG_BULL entries
    gate_mask = long_mask & (df["regime"] == "STRONG_BULL") & deep_below
else:
    # Hourly mode: gate all long entries (no regime column)
    gate_mask = long_mask & deep_below
```

**`add_momentum_features` writes `regime` unconditionally** (`momentum.py:176`), and
`build_features` calls it on both timeframes. Every production caller —
`runner.py:107`, `walk_forward.py:70`, `live/signals.py:96`,
`tools/overnight_gap_risk_study.py:230` — passes a frame straight from `build_features`.
So the `else` branch never executes anywhere, and the comment naming it "Hourly mode" is
describing a path hourly does not take.

F194 asserted the opposite — *"There is no `regime` column on the hourly path, so the code
takes the else-branch"* — and built its headline on it. That claim is wrong. What follows
from the branch actually taken is that the hourly gate is STRONG_BULL-conditional, and
`STRONG_BULL` on an hourly frame means the **252-hour** MA rose >2% over 20 bars, which is
much rarer than the daily analogue.

Measured at F194's own generator setting (σ ≈ 1.1%/bar, "3× ETF-like", 6000 hourly bars),
counting long *candidates* with the gate disabled and then the longs each branch removes:

| panel | STRONG_BULL bars | candidates | blocked, branch taken | blocked, branch F194 assumed | overstatement |
|---|---:|---:|---:|---:|---:|
| seed 3 | 11.4% | 768 | 5.1% | 25.0% | 4.9× |
| seed 5 | 17.8% | 874 | 6.3% | 30.0% | 4.8× |
| seed 9 | 10.8% | 684 | 1.9% | 15.1% | 7.9× |
| seed 21 | 20.1% | 595 | 7.4% | 21.2% | 2.9× |
| seed 33 | 19.2% | 791 | 9.0% | 24.4% | 2.7× |

The gate blocks **1.9%–9.0%** of entry candidates, not the ~28%-of-bars / 42%-of-dip-bars
F194 reported — an overstatement of **2.7×–7.9×**. On the lower-volatility panels of §2
(σ = 0.6%/bar) `STRONG_BULL` is 0–4.9% of bars and the gate blocks **0 or 1 long out of
~174**, while the assumed branch would have blocked 10–28.

### What survives of F194

* **Fact 1 survives.** The gate is active on the live mode: `STRONG_BULL_SOFT_50MA_PCT` is
  `0.02` and the block runs whenever `ma_50d` exists.
* **Fact 2 is wrong** and is corrected here.
* **Fact 3 survives, and now matters more.** `ma_50d` on hourly is a 50-*hour* mean, so a
  threshold calibrated from 50-*day* distances is applied to a 2.5-day mean. The timeframe
  mismatch is unchanged; what changes is that it now compounds with a *second* timeframe
  mismatch in the same gate — `STRONG_BULL` on hourly is a 252-hour regime label wearing
  the name of a 252-day one.
* **F194's conclusion about H21 stands**, by a different route. H21 proposes 0.02 → 0.05
  from daily observations. That recalibration still cannot be justified from daily
  evidence — and it would now move a gate that is already close to inert on the hourly
  path, so the expected gain from the change is smaller than F194 implied.

### Why the error survived a guard

`tests/test_h21_soft_50ma_gate_timeframe.py` asserted the *source text* of both branches
and the fraction of bars sitting below the MA. Both assertions are true and neither
touches reachability, so a passing guard coexisted with a false claim. The measurement it
did make — distance below the MA — is an upper bound on the block rate, and I cited the
bound as the rate. The new guard runs the frame through `build_features` and asserts which
branch fires, which is the thing that was actually in question.

---

## What is not claimed

* No return, Sharpe or drawdown consequence. Changing which longs are blocked changes the
  trade set, and this document does not run an equity curve.
* No claim about real TQQQ. `STRONG_BULL` frequency on hourly bars is volatility- and
  drift-dependent (0%–20.1% across the panels here); on real data it could sit outside that
  range and the block rate would move with it. The *reachability* result does not depend
  on the data.
* Nothing was changed in `src/strategy/**`. The misleading `# Hourly mode: … (no regime
  column)` comment is left in place, on the fenced-path rule; correcting it is a one-line
  owner-gated edit, and `tests/test_h21_soft_50ma_gate_timeframe.py` will fail loudly with
  a pointer here if anyone does.
