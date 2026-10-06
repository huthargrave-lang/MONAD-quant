# Open question: which trials should count against a registered hypothesis?

**Status:** open, for a decision debate (`/decision-debate`). Any change applies
**prospectively**, to hypotheses registered after it is ratified. It must never rescue
one that the current rule rejects (H404701).

## What happened (F404708)

```
H404701 registered ──> 2 more CEF trials run in its family ──> its active DSR: 1.00 -> 0.94 (< 0.95)
   (cheapest CEFs)       (tax-loss tilt, active Sharpe 0.09)     gate: REJECT at deflation
                                                                  familywise SPA: still passes (p 0.0002)
```

The gate deflates a hypothesis against **every trial its family has ever recorded**,
whenever it ran. That rule came from the harness red team, round 2: a cutoff at the
author-written `registered_at` let a backdated registration drop the real search from N.

## The two problems

1. **Later searches cost earlier hypotheses.** Exploring after registering penalises the
   registered idea, even though the later trials could not have chosen it. A guard now
   refuses such runs unless acknowledged (`--acknowledge-live`), but the cost remains.
2. **The DSR treats different ideas as selection noise.** SR0 grows with the spread of
   cluster Sharpes. A family that mixes a real effect (clusters near 1.0) with an
   unrelated null idea (0.09) gets an inflated bar. Hansen's SPA does not have this
   problem: it recentres badly losing strategies out of the null.

## Options

| Option | What changes | Risk it reintroduces |
|---|---|---|
| A. Keep as is | nothing | the costs above; researchers stop exploring families with live hypotheses |
| B. Git-witnessed cutoff | count only family trials committed to the deploy branch **before the registration's own commit**; the cutoff is a commit date git records, not a timestamp the author writes | trials kept off the branch until after registration (the witness stage already requires searched runs on the branch) |
| C. Cluster-scoped deflation | deflate within the candidate's effective-idea cluster plus the declared prior, and leave cross-idea control to the SPA stage | the cluster threshold becomes a tuning knob |
| D. B and C | both | both |

## Evidence the board should weigh

- `docs/research/refutations/boards/H404701.json`, the F404706 and F404708 nodes, and
  `src/research/deflation.py`'s docstring (red-team history).
- `allocation_stats.deflate_active` and `significance.effective_trials`: how SR0 is built.

## Measured: how the two stages behave (2026-10-06, `tools/deflation_power_study.py`)

Each synthetic family has one real idea (4 variants, correlation ~0.64) at a given true
active Sharpe, plus some unrelated null ideas, over 20 years. The candidate is the real
idea's best variant. Pass rates over 60 replications:

| True active Sharpe | Null ideas | DSR passes (≥ 0.95) | SPA passes (p ≤ 0.05) |
|---|---|---|---|
| 0.0 | 0 | **12%** | 2% |
| 0.0 | 2 | 0% | 5% |
| 0.0 | 6 | 0% | 7% |
| 0.6 | 0 | 98% | 88% |
| 0.6 | 2 | **2%** | 90% |
| 0.6 | 6 | 3% | 83% |
| 1.0 | 0 | 100% | 100% |
| 1.0 | 2 | **2%** | 100% |
| 1.0 | 6 | 35% | 100% |

The DSR stage fails in two directions:

1. **Too lenient for a one-idea family.** When every trial clusters into one idea, the
   cross-cluster Sharpe variance is near zero. Then SR0 is near zero whatever N is,
   declared prior included, and a null candidate passes 12% of the time against a nominal 5%.
2. **Nearly powerless for a mixed family.** One or two unrelated ideas inflate the variance,
   and a genuine 1.0 active Sharpe over 20 years passes 2% of the time.

**SPA** stays near nominal size under the null (2-7%) and keeps its power (83-100%).

This adds an option for the board:
- **E.** For the tactical profile, make the familywise SPA the multiple-testing stage, and
  keep the DSR as a reported diagnostic.

Like the others, it would apply prospectively only.
