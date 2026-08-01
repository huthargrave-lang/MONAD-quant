# F245 — H33 root-caused from committed data: two failure modes, not one

**Date:** 2026-07-26 · **Guard:** `tests/test_f245_bracket_nonfill_root_cause.py` (11 tests)
· **Bears on:** H33 (narrowed, not closed)

## No gateway required

H33 prescribes running `tools/diagnose_brackets.py` against a live IBKR gateway plus
TWS/IBC logs. None is reachable here — and none was needed.
`data/live_runs/archive_2026-06-18_pre_clean_run/` is a committed export of a 12-week live
paper run: **149 monitor events, 65 trades, 2026-03-27 → 2026-06-17**. The evidence was
already in the repository, as it was for F242.

## The run had two independent failure modes

H33 treats "IBKR paper brackets fill unreliably" as one phenomenon. The log shows two.

| mode | events | days | share of cycle errors |
|---|---:|---:|---:|
| IBKR connectivity (`ConnectionRefusedError` / `Connect call failed`) | 46 | 9 | **84%** |
| bracket non-execution (CRITICAL software stop) | 6 | 4 | — |
| `Position` schema mismatch (fixed) | 8 | 1 | 15% |

Connectivity is the dominant live-ops failure **by volume** — 9 distinct days between
2026-04-03 and 2026-05-27 — and it is not a bracket problem at all.

## They do not coincide, which is the load-bearing result

The natural sceptical reading of "the bracket did not execute" is that it *did* execute and
the bot could not see it, because it was disconnected. The dates rule that out:

```
connection-loss days : 04-03, 04-28, 05-04, 05-14, 05-19, 05-22, 05-25, 05-26, 05-27
bracket-failure days :               05-12, 05-18, 05-19, 05-21
overlap              :                             05-19          (1 of 4)
```

On **3 of the 4** bracket-failure days the bot was connected, price breached the stop, and
the bracket did not fire.

## Magnitude

Every CRITICAL event carries the mark and the stop it breached:

| date | mark | stop | past the stop |
|---|---:|---:|---:|
| 2026-05-12 | 72.94 | 74.72 | **2.38%** |
| 2026-05-18 | 75.50 | 75.58 | 0.11% |
| 2026-05-19 | 73.82 | 73.91 | 0.12% |
| 2026-05-19 | 73.75 | 73.91 | 0.22% |
| 2026-05-21 | 75.11 | 75.51 | 0.53% |
| 2026-05-21 | 75.09 | 75.51 | 0.56% |

The six resulting trades returned **−0.52% to −3.08%** against a configured **0.50%** stop.
The worst is **6.2×** the intended loss. The software net caught them all — which is why the
run survived — but it caught them late.

## What this narrows, and what it does not

Entries filled normally throughout, so submission works and the bracket was accepted: the
order existed and did not trigger. **Submission failure is ruled out.** It does *not*
separate OCA-group handling from `tif` from paper-engine non-execution — that still needs
TWS/IBC logs. H33 stays open for that question, with a much smaller one to answer.

## A provenance cost nobody had counted

**14 of 65 trades (21.5%)** carry a return that was never read from a real fill:

| exit_type | n | provenance |
|---|---:|---|
| `bracket_exit` | 41 | genuine fill |
| `time_exit` | 9 | genuine |
| `target_hit` | 6 | **inferred from the TP price** — all six recorded at exactly +1.00% |
| `stop_hit` | 6 | **software net** after bracket non-execution |
| `estimated_close` | 2 | **estimated** — fill data never arrived |
| `paper_reset` | 1 | — |

The synthetic part is not merely uncertain, it is **biased in opposite directions**: the
inferred exits sit exactly on the target, while the software stops sit far past the stop.
Any live-vs-backtest comparison drawn from this record is comparing against a
fifth-part-synthetic sample.

## A correction to F242

F242 recovered trade entry prices as `exit_price / (1 + return_pct/100)`. `return_pct` is
stored as a **fraction** despite its name — a 1% target exit is logged as `0.01`, while the
event log prints the same quantity as `"+1.0010%"`. Corrected:

| quantity | as F242 shipped | corrected |
|---|---:|---:|
| trade entry median | $61.87 | **$61.76** |
| cost understatement over trades | 10.7% | **11.1%** |
| under-charged trades | 40 / 65 | 40 / 65 |

Every conclusion survives — direction, mechanism and magnitude are unchanged, and the
under-charged count is identical. The arithmetic is now right, and F242's guard is repinned.

## A third defect, historical

Eight cycle errors on a single day (2026-03-30) read `Position.__init__() got an unexpected
keyword argument 'pending_close_retries'` — a migration that ran before the code that reads
it. `live/state.py:183` now declares the field and `:148` carries the migration, so it is
fixed. Recorded because it fired in the very retry path meant to recover from missing fills.

## Guards

Bidirectional throughout: they fail if the archive stops witnessing either mode, if the two
modes start coinciding on more than one day (connectivity would then explain the non-fills
after all), if the worst breach narrows from 2.38%, if the worst software-stop loss drops
below 5× the configured stop, if the synthetic share of the trade record changes, if the
inferred target exits stop sitting exactly on the target, or if `Position` loses the field
whose absence caused the crash. Non-vacuity: the genuine `bracket_exit` majority (41 of 65)
is asserted, so "a fifth is synthetic" means something.

**Nothing in `live/**` was modified.** This is a read of a committed archive.
