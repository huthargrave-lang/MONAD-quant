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

## Decision-debate consensus (2026-10-06)

Ratified by Hudson in advance. One proposer and one skeptic, three rounds. Round 1:
DISPUTE. Round 2: DISPUTE, narrowly. Round 3: CONCUR once off-window points join m. Every
fix below was adopted verbatim.

**Decision: option E, amended (gate rules v2), applied prospectively.**

- **(i) The gate.**
  - `p_gate = (worst SPA-adjusted p over mean blocks 20/63/126) × (1 + m) ≤ familywise_alpha`,
    with `m = prior_search_trials + unknown_specs + off_window_points`.
  - `off_window_points`: each distinct point the family searched (producer not the gate)
    that has no ok trial in the SPA matrix.
  - p is estimated as (b+1)/(B+1) with B ≥ max(5000, ⌈20(1+m)/alpha⌉). The verifier
    recomputes with the same B and seed.
  - The union bound needs no independence among members; correlation only makes it
    conservative.
- **(ii) Found-nothing members** are observed members with t = 0, dropped from the matrix
  as an exact equivalence. They do not add to m.
- **(iii) Price-profile basis.**
  - v3 trials record per-trade entry and exit timestamps plus a daily mark-to-market PnL
    and exposure series at session closes, under fixed notional.
  - f = the mean close exposure.
  - The benchmark is daily-rebalanced f × the instrument's daily total return from a
    frozen snapshot, at zero cost.
  - The SPA and the DSR diagnostic both run on the mark-to-market active series.
  - Pre-v3 members count in m.
- **(iv) Registrations.**
  - New fields: `gate_rules`; for the price profile also `familywise_alpha` (≤ 0.05) and
    `prior_search_trials`. New metric value `familywise_spa`.
  - `register()` requires `gate_rules == 2`.
  - A missing `gate_rules` is accepted only in `load()`, for H404700, H404701 and H404702
    keyed by exact spec_hash.
  - Under v2 `threshold` is a non-gating diagnostic DSR level.
  - Until the price trigger passes, a v2 price registration's familywise stage is BLOCK
    ("v2 price chain not ratified"), never judged by the DSR.
- **(v) Versioned chains and verifiers.**
  - ADMIT chains are a function of the rules version read from the hash-verified
    registration.
  - In v2 a `deflation_diagnostic` stage must be exactly SKIP; `familywise` gates.
  - v2 verifiers recompute the seeded SPA and (1+m) from the ledger, for both profiles.
- **(vi) Triggers.**
  - The price profile switches when SPA's size has a Wilson 95% upper bound ≤ 0.075 at
    alpha 0.05 over ≥ 1000 replications, at production settings, on the (iii) basis, with a
    withheld-members design testing (i) at m > 0.
  - The tactical profile switches on the same criterion, from a rerun of the dense study at
    production settings (worst of 20/63/126, n_boot ≥ 1000).
- **(vii) Dilution.** SPA's recentering removes only badly losing members. Every member with
  mean ≥ about 0, null or real, still raises the max-t bar: the accepted cost of counting
  every trial.
- **(viii) Docs.** prereg's `MIN_FORWARD_PSR_FLOOR` comment is updated for v2.

## Measured: the tactical trigger (2026-10-06, `tools/spa_size_study.py`)

The dense study rerun at production settings: `allocation_stats.familywise_gate`, worst of
mean blocks 20/63/126, n_boot 1000, alpha 0.05. Each family is one idea with 4 correlated
variants plus unrelated null ideas plus `m` withheld null members the gate cannot see; the
candidate is the best visible variant. Size uses 1000 replications per cell, power 300.
Results are in `docs/research/spa_size_study.json`.

| Null ideas | Withheld m | Size (passes / 1000) | Wilson 95% upper |
|---|---|---|---|
| 0 | 0 | 5.3% (53) | **0.0687** (worst) |
| 0 | 5 | 0.5% | 0.0117 |
| 0 | 20 | 0.1% | 0.0056 |
| 2 | 0 | 2.1% | 0.0319 |
| 2 | 5 | 0.5% | 0.0117 |
| 2 | 20 | 0.3% | 0.0088 |
| 6 | 0 | 1.3% | 0.0221 |
| 6 | 5 | 0.2% | 0.0073 |
| 6 | 20 | 0.0% | 0.0038 |

| True active Sharpe | Null ideas | m = 0 | m = 20 |
|---|---|---|---|
| 0.6 | 0 / 2 / 6 | 88% / 86% / 81% | 38% / 37% / 35% |
| 1.0 | 0 / 2 / 6 | 100% / 100% / 100% | 97% / 95% / 89% |

**The trigger passes:** the worst upper bound, 0.0687, is ≤ 0.075, so the tactical
profile runs under gate rules v2 (`tools/admit_tactical.py`, `ADMIT_CHAIN_V2`).
`tests/test_admit_tactical.py` pins this file against the trigger.

What the numbers say:
- With nothing withheld, one idea sits at nominal size (5.3%). Null competitors pull it
  below nominal, as recentering predicts.
- The union-bound charge is strongly conservative at m > 0: about 0.5% at m = 5. Its
  price is power. A Sharpe-0.6 edge passes about 37% of the time at m = 20, against
  about 85% at m = 0. An undeclared search is not free, and it should not be.
- The gate itself uses B ≥ max(5000, ⌈20(1+m)/alpha⌉). The study's B = 1000 makes
  (b+1)/(B+1) slightly larger, which is the conservative direction for size.

The price profile stays BLOCKED. Its trigger needs the (iii) mark-to-market basis, which
v3 trials do not record yet.

## Measured: the price trigger fails at two years (2026-10-06, `tools/spa_price_size_study.py`)

This is the sparse daily mark-to-market basis. Moves are Student-t(5), scaled like a 3x index. Each idea has 4 hold-length variants sharing its signals, one position at a time. The gate uses the worst of mean blocks 20/63/126, n_boot 1000, and 1000 reps per size cell.

| Sessions | Moves | Size cells passing | Worst cell (one idea, m = 0) | Evidence |
|---|---|---|---|---|
| 504 | iid | 8 / 9 | 6.1%, Wilson upper **0.0776** | `spa_price_size_study.json` |
| 504 | GARCH | (that cell) | 5.2%, 0.0676 | `spa_price_sessions_garch.json` |
| 1008 | iid | 9 / 9 | 4.5%, 0.0597 | `spa_price_size_study_1008.json` |
| 1008 | GARCH | 9 / 9 | 3.7%, 0.0506 | `spa_price_size_study_1008_garch.json` |
| 1512 / 2520 | iid | (that cell) | 3.7% / 4.4% | `spa_price_sessions.json` |

Power at 1008 sessions (iid), with true active Sharpe 1.0:
- 89%, 81% and 72% at 0, 2 and 6 null ideas, with m = 0;
- 52% down to 35% at m = 20.

The hourly source serves 729 days, about 500 sessions.

## Decision-debate consensus (2026-10-06, price trigger)

There was one proposer and one skeptic over three rounds. The skeptic's drift probe found a defect in (iii). A no-skill strategy holding intraday earns intraday drift, and the close-exposure benchmark never charges it. At 0.1%/day intraday drift, size was 8.5% (n = 400), and the error grows with n. Every item below reached CONCUR. R4's versioning follows the skeptic's evidence that `ENGINE_VERSION` is part of the family name.

- **R1 Session floor.**
  - `prereg.MIN_PRICE_SESSIONS = 1008`. This is the measured minimum at which every size cell passed under both iid and GARCH moves. It binds trials, not the test.
  - `validate` refuses a v2 price development window shorter than `MIN_PRICE_WINDOW_DAYS = 1480`.
  - A test counts sessions on the rules-based NYSE calendar (`src/research/nyse_calendar.py`) for every start date from 2000 to 2030. The calendar matches a 1996-2026 SPY snapshot day for day. Its special closures are 2001-09-11..14, 2004-06-11, 2007-01-02, 2012-10-29/30, 2018-12-05 and 2025-01-09.
  - While `MAX_HOURLY_LOOKBACK_DAYS` (729) is less than the floor plus the forward floor, **no v2 price registration can be registered**. `validate` says so, and a test pins it.
- **R2 Admission floor.**
  - The price familywise stage FAILs when the candidate's scored mark-to-market series has fewer than 1008 sessions.
  - The v2 price verifier applies the same floor.
- **R3 Not ratified.** `PRICE_V2_RATIFIED` stays False. The evidence is a tuple of files, and each must pass with reps ≥ 1000. The required cells are m > 0 cells, drift cells, the regime cell and the exit-bar cell, all present and passing. Each file must also carry `basis: "iii-prime runner+mark_to_market"`, a `dgp` label, and `sessions ≤ MIN_PRICE_SESSIONS`.
- **R4 Amendment (iii'): the slot-profile benchmark.**
  - `bar_exposure` is the notional held at each bar's open. `h_b` is the trial's mean exposure in each time-of-day slot: the regular-session hourly slots plus one overnight slot.
  - benchmark_d = Σ_b h_b · r_{d,b}, and active = PnL − benchmark.
  - This centres the no-timing null for any slot-dependent drift, up to two named second-order terms, both measured and reported:
    - the optional-stopping offset μ_b(1 − E[τ]) on exit bars;
    - the in-sample h_b bias, of order (1/n)·Σ|cov(e_{d+k}, r_d)|.
  - The partition must cover every calendar dimension the engine's exposure can follow. That is time of day under ENGINE_VERSION 3. On half days, missing slots get r = 0 and the overnight slot spans the gap.
  - Named size risk: regime-scale exposure–drift covariance longer than a 126-session block.
  - **Versioning:**
    - The basis is recorded in each trial's spec as `mtm_basis`. It changes the hash, not the family. `ENGINE_VERSION` stays the execution version.
    - The matrix holds only members on the candidate's basis. Others count in m.
    - **Family lineage:** distinct points searched under any earlier `ENGINE_VERSION` for the same strategy and symbol count in m. A version bump must never erase a search. This applies now, since the v2 → v3 bump split the families.
- **R5 Phased trigger work.** This is done when an audited hourly source of at least 1480 days is wired; the profile is unregistrable until then.
  - The study builds families through the real `runner` and `mark_to_market` path, with fresh seeds, at `sessions = MIN_PRICE_SESSIONS`.
  - It adds drift cells at ±0.1%/day, overnight and intraday.
  - (e) A regime cell: drift sign switching in blocks of about 252 sessions, signal rate rising with trailing realised volatility, negative vol/return correlation. If (e) fails, ratification is blocked.
  - (f) The exit-bar convention, reporting the offset in the mean.
  - (iii') itself is implemented with this work.
