# [`E18`](../../RESEARCH_WEB.md)'s flag is not a kill switch — the breakout signal is orphaned

**Status:** E18's figures are **not recoverable** here; its structural situation is, and it
is worse than recorded. **Guard:** `tests/test_e18_breakout_orphaned.py`.

---

## The figures, and why they cannot be checked

E18 records the Phase-B experiment: STRONG_BULL breakout entries (price > 20-day high,
ADX > 25, MACD bullish) dropped win rate **49.4% → 39.6%**, with CLAUDE.md §7 adding that
5-year trades went **83 → 141**.

Those come from a BTC daily backtest over 2020–2024. Reproducing them needs multi-year
daily price history: no panel is committed and the providers return 403 at this
environment's egress proxy. The run wrote no artifact. **So the four win-rate/trade-count
figures are unverifiable from this repository, by anyone**, exactly as for
[`F176`](../../RESEARCH_WEB.md)'s quoted Sharpes. That is the honest answer for them.

## What *is* checkable, and it changes how the node should be read

E18 ends with `BULL_BREAKOUT_ENABLED=False`, and CLAUDE.md §3 lists the signal as
**"BUILT BUT DISABLED"**. Both read as: the feature exists, it is switched off, and
flipping the switch would bring it back.

It would not. The flag gates only whether a **column is computed**:

```python
# src/strategy/engine.py — inside build_features()
if getattr(config, "BULL_BREAKOUT_ENABLED", False) and "adx" in df.columns:
    ...
    df["bull_breakout_signal"] = 0
    df.loc[(df["regime"] == "STRONG_BULL") & (df["close"] > high_n)
           & macd_pos & (df["adx"] > adx_min), "bull_breakout_signal"] = 1
```

Those are the **only two references to `bull_breakout_signal` in the entire codebase**,
and both are writes. `generate_trades` builds its vote from `momentum_signal +
volume_signal` and nothing else. The column has no reader.

### Measured

On four seeded daily panels, `entry_signal` is byte-identical with the flag off and on.
The comparison is non-vacuous — on a panel chosen so both quantities are large, the
breakout condition **fires 40 times** while the strategy takes **30 entries**, and the
entry hash is unchanged:

| panel | breakout firings | entries, flag off | entries, flag on | entry hash |
|---|---:|---:|---:|---|
| seed 26, σ 1.4% | 40 | 30 | 30 | identical |
| drift_up | 0 | 25 | 25 | identical |
| flat | 1 | 14 | 14 | identical |
| choppy | 0 | 24 | 24 | identical |

## Why this matters for the recorded lesson

E18's lesson — *"breakout signals are traps at tops; the core is mean-reversion"* — may
well be right. But the way it is written invites a specific mistake: someone re-testing it
would flip `BULL_BREAKOUT_ENABLED = True`, observe **no change whatsoever**, and conclude
the finding was overstated. They would be measuring an orphaned column, not the mechanism
the 2026 experiment tested.

So the node's practical status is not "built, disabled". It is **"built, disabled, and
disconnected"** — reviving it needs a routing change in `generate_trades`, not a config
flip, and the 49.4%/39.6% comparison could not be reproduced even with market data until
that wiring is restored.

This is the third member of the same family found in this codebase: the ADX multiplier and
`regime_kelly_mult` are computed and never read ([`F145`](../../RESEARCH_WEB.md)), the
slope-regime gate is stripped from the entry path ([`F26`](../../RESEARCH_WEB.md)), and
now a signal whose flag governs only its own computation. The shared shape is a config
knob that reads like a feature toggle and is really a compute toggle.

## Scope

* Nothing here says the breakout idea is good or bad. It says the switch does not test it.
* `src/strategy/**` was **not** modified — it is fenced. Rewiring the signal, or deleting
  it, is an owner decision; the guard records the current state either way.
* The panels are seeded synthetic. That is sufficient for a reachability claim (no reader
  exists for any input) and the guard asserts the *structural* fact via AST as well as the
  empirical one.
