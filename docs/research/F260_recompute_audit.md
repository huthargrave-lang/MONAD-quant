# F260 — a detector for values computed twice with different parameters

**Date:** 2026-07-26 · **Tool:** `tools/recompute_audit.py` · **Guard:**
`tests/test_f246_recompute_audit.py` (12 tests)

## The question F145 does not ask

The dead-lever census asks *"is this knob read?"*. That question cannot find the two most
expensive defects in `src/signals/`, because those knobs **are** read:

- `engine.py:35` forwards `rsi_period=RSI_PERIOD_<MODE>`
- `add_momentum_features` honours it and writes a correct `df["rsi"]`
- every artifact a reader would inspect — the column, the log, the dashboard — is right

And the entry gate still ignores it, because `momentum_signal()` calls `compute_rsi(close)`
a second time at the function's default period. **The correctness of the visible artifact is
what hides the divergence.** Nobody audits a value that is right.

So this tool asks a different question: **does the value that is displayed equal the value
that governs?** The mechanical signature of a No is a *recomputation that drops parameters*:

```python
df["rsi"] = compute_rsi(df["close"], period=rsi_period)   # canonical — forwards the knob
...
rsi = compute_rsi(close)                                   # divergent — silently defaults
```

## What it finds here

Two divergences, both in `src/signals/momentum.py:38-39`, both inside `momentum_signal()`:

| producer | canonical | drops | consequence |
|---|---|---|---|
| `compute_rsi` | `momentum.py:164` | `period` | gate at default period, column at 7 |
| `compute_macd` | `momentum.py:165` | `fast, slow, signal` | gate at defaults, column at 6/13/4 |

Every hourly mode configures non-default values for **both**. So on every hourly mode the
indicators that are logged, charted and swept are not the indicators that decide trades.
The RSI half was proven empirically in F244 (386/386 agreement with a default-period rule,
381/386 with the configured one); the MACD half is the identical code path.

`config.py` already carries a **third** wrong diagnosis of this family:

```python
MACD_FAST_TQQQ_HOURLY = 6     # DEAD LEVER (confirmed: same as QQQ/BTC hourly)
```

The deadness was observed correctly and attributed to a coincidence between modes, rather
than to the knob never reaching the gate.

## The detector's own first version was wrong

It counted **keyword arguments only**, and reported a third finding: `compute_bb_width`
inside `volatility_regime()`. That call forwards `window` **positionally**:

```python
bb_width = compute_bb_width(df["close"], window)     # correct, and invisible to a kwarg count
```

Binding positional arguments against the callee's signature removed the false positive and
left the two real ones. That fix is also why `volume_signal()` is correctly silent: it
recomputes its inputs in exactly the same shape as `momentum_signal()`, but forwards its
parameters. **`momentum.py` is the outlier precisely because it forwards nothing** — which
is a much stronger statement than "this pattern is risky", and only the corrected detector
can make it.

Kept as a regression test, because the false-positive direction is the one that would make
the tool useless: a census that cries wolf gets ignored, which is how F145's five dead knobs
sat unexamined.

## Precision over recall, deliberately

Not flagged: a `compute_*` that backs no column, a helper called once, or a recomputation
whose parameters match (reported separately as `duplicate`, never as a finding). Five benign
duplicates exist in `src/signals/` and are listed but not counted.

## Usage

```
python3 tools/recompute_audit.py [--json] [PATH ...]     # exit 1 while divergences exist
```

`scan()` and `divergent()` are importable; the CLI exit code makes it usable as a gate once
the two known divergences are resolved.

## Guards

`tests/test_f246_recompute_audit.py`, bidirectional:

- fails if the divergence set changes — **if one is fixed, supersede this node**, do not
  edit the expectation; if a new one appears it needs its own analysis;
- fails if `compute_bb_width` is flagged divergent again (the detector regressed to
  counting keywords), or if `volume_signal`'s benign recomputes start being flagged;
- **non-vacuity on synthetic source, both directions:** a planted parameter-dropping
  recompute must be caught, and a planted correct positional forward must not be. A
  detector that only ever says one thing is not a detector;
- fails if any hourly mode starts configuring the MACD defaults (the divergence would be
  latent rather than live for it), and asserts BTC daily genuinely matches the defaults so
  the finding is not inherited as "every mode is broken";
- fails if the CLI stops signalling through its exit code.

## Not fixed

`src/signals/**` is fenced, and correcting either call changes which bars produce entries on
every hourly mode. The swept parameters were selected *under* the wrong indicators, so
fixing invalidates them while leaving them means the knobs should be deleted rather than
tuned. Same owner decision as F244, now with two instances and a tool that will find the
third.
