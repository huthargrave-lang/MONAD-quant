# F244 — the entry signal ignores RSI_PERIOD, and the logged RSI is not the one it used

**Date:** 2026-07-26 · **Guard:** `tests/test_f245_rsi_period_not_used_by_signal.py` (12 tests)
· **Status:** diagnosed, **not fixed** — `src/signals/**` is fenced and a fix moves every
hourly backtest number.

## The defect

`add_momentum_features()` computes the RSI column at the **configured** period:

```python
df["rsi"] = compute_rsi(df["close"], period=rsi_period)          # momentum.py:164
```

`momentum_signal()` then computes its **own**, and never reads that column:

```python
rsi = compute_rsi(close)                                          # momentum.py:38 — period=14
long_cond = (rsi < rsi_oversold) & (hist > hist.shift(1))
```

`engine.py:35` passes `rsi_period=RSI_PERIOD_<MODE>`, which is **7 for every hourly mode**
(5 for BTC hourly, 14 only for BTC daily). So on every hourly mode the strategy **enters on
a 14-period RSI**, while the **7-period** RSI is what lands in `df["rsi"]` — logged by
`live/signals.py`, shown on the dashboard, and swept.

## Proof

On a synthetic 400-bar series with `rsi_period=7, oversold=80`:

| rule tested against `momentum_signal == 1` | agreement |
|---|---:|
| `(RSI(14) < 80) & (hist rising)` — the default period | **386 / 386** |
| `(RSI(7) < 80) & (hist rising)` — the configured period | 381 / 386 |

Exact agreement with the default, not with the configured one. The 5 disagreements are all
bars that **fired long while the logged RSI read ≥ 80** — up to 86.3.

## It is visible in production, and was never diagnosed

The committed live archive (`data/live_runs/archive_2026-06-18_pre_clean_run/`, 322 distinct
TQQQ bars) contains **18 bars (5.6%)** where `momentum_signal == 1` while the logged RSI is
**above** the oversold threshold — ranging to **86.8** against a threshold of 80.

Read literally, the log says the bot bought overbought bars. It did not. It bought on an RSI
that nobody recorded.

The innocent explanation is ruled out: the highest oversold threshold *any* mode configures
is 85 (GDXU), below the observed 86.8, and the TQQQ threshold's git history is 68 → 70 → 80.
No threshold in force at any time explains those bars.

## The wrong diagnosis is already in the config

The project noticed the lever does nothing and wrote down a different cause — on four modes:

```python
RSI_PERIOD_GDXU_HOURLY = 7        # DEAD LEVER (MACD is binding gate)
RSI_PERIOD_SOXL_HOURLY = 7        # DEAD LEVER (MACD is binding gate)
RSI_PERIOD_LABU_HOURLY = 7        # DEAD LEVER (MACD is binding gate)
RSI_PERIOD_TNA_HOURLY  = 7        # DEAD LEVER (MACD is binding gate)
```

The *symptom* was observed correctly — changing `RSI_PERIOD` does not move results. The
*mechanism* is not that MACD dominates; it is that `momentum_signal()` never reads the knob.
This is the F145 dead-lever family with a sharper edge: a lever whose deadness was noticed,
mis-explained, and the mis-explanation committed as documentation.

## What it blocked

This is why exact shadow replay (H26) is unattainable. Recovering the unlogged MACD term by
inverting the logged signal is sound in one direction only — `momentum_signal == 1` does
imply the term held — but a logged `0` is ambiguous, because it may mean the *signal's* RSI
was above the threshold while the *logged* RSI sat below it. Those are different series.

`tools/shadow_replay.py:entry_bounds()` therefore brackets instead of pretending: a sound
lower bound from the confirmed firings, and `replay()`'s marginal as the upper. On the
archive at live settings that is **39.4% – 81.4%** — wide, and honestly wide. Exact replay is
blocked on this being fixed, which is the useful thing to know.

## Not fixed, deliberately

`src/signals/**` is fenced. Correcting `momentum_signal()` to accept the period changes which
bars produce entries on **every hourly mode**, so every backtest, sweep and stored result
moves — the same class of change as F148's UTC gate, which is owner-deferred for exactly this
reason. It needs explicit approval plus a full re-sweep.

Note also that the fix is not purely mechanical: whichever way it goes, one of two bodies of
recorded work becomes wrong. The swept parameters were selected under the 14-period gate, so
"fixing" the period invalidates them; leaving it means `RSI_PERIOD_*` should be deleted
rather than tuned.

## Guards

`tests/test_f245_rsi_period_not_used_by_signal.py`, bidirectional:

- fails if `momentum_signal` starts matching the configured-period rule (that is the fix —
  **supersede this node**, do not retune);
- fails if the RSI *column* stops honouring the configured period (the other half of the
  bug's shape — the column being right is why nothing looked wrong);
- fails if no bar fires above the oversold threshold any more;
- **non-vacuity:** fails if any hourly mode's period becomes 14, which would make the bug
  latent rather than live for that mode; and asserts BTC daily's 14 is genuinely unaffected,
  so the finding is not inherited as "every mode is broken";
- fails if the archive's 18 witnessing bars change count, or if a configured threshold grows
  large enough to explain them innocently;
- brackets: the shadow-replay bounds must stay non-degenerate, must shrink when the candidate
  tightens, must refuse looser candidates, and the lower bound must only count bars the log
  itself marked as firing.
