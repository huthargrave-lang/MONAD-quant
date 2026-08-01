# F263 — F203's evidence reproduced, and its ambiguity resolved: the gate says FAIL

**Date:** 2026-07-27 · **Guard:** `tests/test_f263_f203_evidence.py` (9 tests)
· **Closes:** F203's uncited status (10 figures, 0 reachable docs, 1 reliance dependent)

## Everything F203 recorded reproduces

Every figure comes from the committed 65-trade live archive, so all of them regenerate
offline. Against `ops/analyze_run.py`'s "≥ 80% of fills are confirmed" bar:

| partition | trades | share | verdict |
|---|---:|---:|:--|
| `bracket_exit + stop_hit` (as written) | 47/65 | 72.3% | FAIL |
| `bracket_exit` only (provably actual) | 41/65 | 63.1% | FAIL |
| `bracket_exit + stop_hit + target_hit` | 53/65 | 81.5% | **PASS** |

The duplication reproduces too: `ops/analyze_run.py`'s `ACTUAL` and `ctx.CONFIRMED` are the
same set — `{"bracket_exit", "stop_hit"}` — declared in two files. Both include `stop_hit`,
which the software net can produce without a fill; both exclude `target_hit`, which the
broker fills for real. Two implementations of one fact, wrong the same way, so neither can
catch the other.

## But F203 stopped one step short

F203's conclusion is that the verdict **flips** on "a distinction the ledger cannot make."
That was true of the ledger. It is no longer true of the evidence: **F245** made the
distinction from the *monitor event log* instead.

14 of the 65 trades carry a return that was never read from a real fill —
6 `target_hit` inferred from the TP price (all six recorded at exactly +1.00%),
6 `stop_hit` from the software net after IBKR brackets did not execute, and
2 `estimated_close` force-finalised when fill data never arrived.

Applying that provenance yields a fourth partition — and it is the one the gate's own
wording demands, since it asks whether *fills* are *confirmed*:

| partition | trades | share | verdict |
|---|---:|---:|:--|
| exits with an **observed fill** (`bracket_exit + time_exit`) | 50/65 | **76.9%** | **FAIL** |

## The resolution

| partition | share | verdict |
|---|---:|:--|
| as written | 72.3% | FAIL |
| bracket only | 63.1% | FAIL |
| **provenance-correct** | **76.9%** | **FAIL** |
| bracket + stop + target | 81.5% | PASS |

**Three of four fail, and the only PASS is the one that counts the twelve exits F245 proved
were never observed.** The 81.5% branch clears the bar *precisely by* counting `target_hit`
and `stop_hit` — the two classes with no confirmed fill price.

So the honest reading is not "the verdict is ambiguous." It is **FAIL, by 3.1 points**, and
the ambiguity was an artifact of a partition that never distinguished observed fills from
inferred ones.

That is a stronger and more actionable statement than the flip: this is the gate that
authorises real money, and on the only definition consistent with its own wording, the
committed run does not clear it.

## Guards

`tests/test_f263_f203_evidence.py`, bidirectional:

- fails if any partition's arithmetic moves, or if the 80% bar stops sitting inside the band;
- fails if the two duplicate definitions stop agreeing — that would mean one was corrected,
  so **supersede** rather than edit the expectation;
- fails if the provenance-correct share crosses the bar (the gate would then pass on observed
  fills alone);
- fails if the set of passing partitions changes — the claim that the *only* PASS is the
  synthetic one is the load-bearing one;
- **non-vacuity:** the gap between the synthetic and provenance-correct partitions must
  exceed 3 points, so the FAIL is attributable to provenance rather than to a bar nothing
  could clear; and the synthetic classes must remain a meaningful share (14 trades, >20%).

## Not changed

`ops/analyze_run.py` and `ctx.CONFIRMED` are left as they are. Correcting the set changes a
published go/no-go verdict and touches the live-ops rubric — an owner decision, recorded
with the number it would produce.
