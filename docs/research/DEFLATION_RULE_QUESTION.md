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
