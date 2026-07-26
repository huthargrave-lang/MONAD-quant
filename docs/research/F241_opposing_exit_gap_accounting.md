# F241 — the engine prices one gap two ways, and a config flag picks which

**Date:** 2026-07-26 · **Guard:** `tests/test_f241_opposing_exit_gap_accounting.py` (9 tests)
· **Scope:** backtest accounting. Not a live-risk finding — see *Scope* below.

## The result

One hand-built frame. A long entry fills at 100. Bar 2 is quiet and carries an opposing
composite vote. Bar 3 gaps to 40. Nothing else differs; one config flag is flipped:

| `USE_OPPOSING_SIGNAL_EXIT` | recorded `exit_type` | recorded return |
|---|---|---:|
| `False` | `stop_hit` | **−1.00%** |
| `True` | `opposing_signal` | **−60.00%** |

Sixty times the recorded loss, for the same market event on the same price path.

## Why

The two exits use different fill conventions, and only one of them is documented.

- **The stop path fills optimistically.** `compute_trade_returns` books a `stop_hit` at
  exactly `-stop_loss_pct` even when the triggering bar *opened* through the stop. That
  optimism is known and already measured: `D6_execution_semantics_study.md` prices the
  honest alternative ("fill opens through the stop at the open") at **−10.15%** against
  **−5.17%** on the live-shaped path.
- **The opposing path fills honestly.** `src/strategy/engine.py:362-371` gates the exit on
  the *signal* bar sitting inside the stop/target band, then fills at the **next bar's
  open**, which is bounded by nothing. So it prices the gap at the gap.

Neither number is wrong in isolation — the opposing path is arguably the more realistic
of the two. **The defect is that they disagree**, silently, on the same event.

## What that costs

`RESEARCH_WEB.md` counts this flag in the *dormant pair*: off in the backtest, absent from
live, therefore no behavioural difference today. The stated risk is that a sweep turning it
on would "model an exit the bot cannot execute." That is true and incomplete. Turning it on
also **re-prices gap risk for every trade that would otherwise have stopped out** — because
the opposing exit pre-empts the stop on exactly those bars. A sweep comparing flag-on to
flag-off is therefore not comparing two exit policies; it is comparing two gap-accounting
conventions, and the difference has nothing to do with signal quality.

That is the F12 backtest↔live divergence family again, and it compounds F200: the flag was
already advertising a live equivalent that never existed.

## Why nothing caught it

`tests/test_compute_returns_properties.py` asserts exactly the invariants that would have —
returns finite, bounded below by −1, recorded return equals the chosen exit level. Its
generator reaches **four of the five** exit types (measured over 300 generated paths:
`stop_hit` 131, `target_hit` 116, `ambiguous_same_bar` 38, `time_exit` 15). It cannot reach
the fifth, for two independent reasons:

1. `_price_path()` never builds a `signal_vote` column, so the engine falls back to
   `entry_signal`, which is `0` on every future bar — no opposing vote can ever fire.
2. No property test passes `use_opposing_signal_exit=True`.

Doubly unreachable, and **not an environment artifact**: CI installs `hypothesis` from
`requirements-dev.txt`, so these properties do run on every push. They run, they pass, and
the branch is invisible to them.

A note on why random search would not have found it anyway: the opposing exit is only
*eligible* when the signal bar sits inside a 1% band around entry, which on i.i.d. generated
paths means a near-flat path — whose next open is also near-flat, giving ≈0. The falsifying
shape is a **quiet bar followed by a gap**, which is what an overnight gap is and what random
paths almost never produce. It took a hand-built frame.

## A second, smaller finding

The property suite's `assertGreater(r, -1.0)` is justified in-file as *"price can't go below
zero."* That is a **long-only** fact. The suite generates shorts half the time, and on this
branch a short opposing exit into a 9× move records **−8.0**. The invariant is false as
written; it survives only because the branch that falsifies it is unreachable.

## Scope — what this is not

Production is `LONGS_ONLY=True` and `USE_OPPOSING_SIGNAL_EXIT=False`, and the live trader has
no opposing-signal logic under any name (F200). So:

- the −8.0 short breach is a **test-correctness** issue, not a live risk one;
- the −60% long figure is what the **backtest would record** if a sweep enabled the flag,
  not a loss the bot can take today.

The guard pins both, and asserts the long side stays above −1.0 so that if that ever changes
the finding gets re-scoped rather than quietly inherited.

## Guards

`tests/test_f241_opposing_exit_gap_accounting.py`, bidirectional throughout:

- fails if the stop path stops filling optimistically, or the opposing path stops filling at
  the next open (either would mean one convention was adopted — **supersede, don't retune**);
- fails if the 60× disagreement narrows;
- **negative control:** on a frame with no gap (bar 3 at +0.5%, inside the band) both paths
  record **+0.00500** — a deliberately non-zero agreement, since a flat frame would have both
  returning 0.0 and any two broken paths would pass;
- fails if the property generator gains `signal_vote` or a test enables the flag — that is
  good news and the instruction is again to supersede;
- fails if the short breach stops being falsifiable, or if the long side starts breaching.

Falsifiability was checked by mutation, not assumed: clamping the opposing return to
`-stop_loss_pct` in a **copy** of `engine.py` (the real file is fenced) fails 3 of the 9
guards, including the headline.

## Not fixed here

Making the two conventions agree means changing `src/strategy/engine.py`, which is fenced and
needs explicit approval — and the choice is not obvious, since the honest convention is the
one that costs −10.15%. Recorded, guarded, and left for the owner.
