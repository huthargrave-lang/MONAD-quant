# Forward-evidence admission route: proposal for Hudson to ratify

Status: **PROPOSAL** (decision debate, 2026-10-09). Nothing here is implemented, and no watch
can be admitted until Hudson ratifies a route.

## TL;DR

- **The gap.** The forward watches (H366200, H366201) were frozen as "not admission
  candidates". Gate rules v2 charges their historical search (m = 1401 and 22), so the tactical
  gate can never admit them, and **no route exists that could**.
- **The proposal:** an `admit` profile, **`forward_watch`**, that admits a watch on its own
  frozen sequential test, against a boundary raised for every watch ever frozen.
- **What admission grants:** eligibility, not a position size. Sizing stays a separate product
  decision under D8's drawdown mandate, because F366206 showed that sleeves of this kind deepen
  drawdowns.
- **Honest power:** at a true active Sharpe of 0.3, reaching the boundary takes decades. The
  route makes admission *possible and honest*, not likely.

```mermaid
flowchart LR
  A[frozen watch spec on development<br/>first-parent date] --> B[daily chained log<br/>verify + attested evaluator]
  B --> C{anniversary report}
  C -->|LLR ≥ ln m·(1−β)/α<br/>and the spec's own conditions| D[ADMIT: eligible sleeve]
  C -->|LLR ≤ ln β/(1−α)| E[CLOSED]
  C -->|otherwise| B
  D --> F{the log continues}
  F -->|close boundary or VOID| G[DE-ADMIT]
  D --> H[sizing: separate D8 decision]
```

## Contested questions

### Q1: What must a watch show to be admitted?

- **Evidence:**
  - Each spec freezes a Wald SPRT (θ1 0.3, α 0.05, β 0.2, anniversaries only), plus
    rule-specific conditions:
    - H366200: a 2x-cost Sharpe > 0;
    - H366201: a 2x-cost Sharpe > 0, a long leg > 0, at least 20 episodes, and the issuance
      rule.
  - `forward_watch.decide` computes the anniversaries.
  - The policy `docs/research/forward_watch/policy/route.json` (frozen) sets the route boundary
    at ln(m(1−β)/α).
- **Proposed fix.** Admission requires, at an anniversary report:
  - (a) LLR ≥ ln(m(1−β)/α), with α and β from the watch's own spec and m from the policy;
  - (b) **every** corroboration condition in the watch's spec;
  - (c) the chain verifies, every evaluator change is attested, and there is no VOID.
- **Rejected alternatives:**
  - *A fixed-horizon Bonferroni t-test.* It discards the frozen sequential design and invites
    picking the horizon after the fact.
  - *The tactical gate's P(Sharpe > 0) ≥ 0.9 over one year.* It ignores m, and its power is
    40-55% even at good Sharpes.
- **Hard to reverse:** an admission that later decays. Q4 handles it.

### Q2: What is m?

- **Evidence:** the policy, frozen before any window opened, sets m as every watch ever frozen
  (voided, closed, never merged and pooled ones included). Today m = 2.
- **Proposed fix:** keep the policy exactly as frozen. `report` already prints m and the
  boundary. A pooled watch, a frozen combination of watches, is one more record (m + 1).
- **Rejected alternatives:**
  - *Charging only live watches.* Voiding or closing would shrink m, an incentive to void
    losers.
  - *Charging the development search.* Forward data has no search to charge. That is the whole
    reason the route exists.

### Q3: What does admission grant?

- **Evidence:**
  - F366206: at their corroborated alphas, CEF sleeves raise a 60/40's Sharpe but deepen its
    drawdown in almost every window.
  - D8 frames the product as capital preservation. F366208: H404702's edge is convex in
    category moves.
- **Proposed fix:**
  - Admission makes a watch's rule **eligible** as a sleeve.
  - Its size is a separate product decision. Hudson ratifies it against a stated drawdown
    budget, using the F366206 machinery on the watch's own forward record.
  - Until then, nothing is traded. The bot stays paper-only, port 7497.
- **Rejected alternatives:**
  - *An automatic fixed cap (say 5%).* It sizes before anyone has measured the sleeve's
    drawdown cost.
  - *Admitting straight into the live config.* It violates the never-edit-live-without-approval
    invariant.

### Q4: What happens after admission?

- **Evidence:** the SPRT is valid whenever it stops, and the log is append-only.
- **Proposed fix:**
  - The log continues after admission, with anniversary reports as before.
  - The watch is **de-admitted** when its full-record LLR reaches the close boundary
    ln(β/(1−α)), or on a VOID.
  - No other trigger: an extra rolling or drawdown trigger would be a new fork, decided after
    seeing data.
- **Rejected alternatives:**
  - *A 3-year rolling-Sharpe trigger.* Unspecified power and multiple looks.
  - *Admission for life.* It ignores decay.

### Q5: How is it built?

- **Evidence:**
  - `tools/admit.py` dispatches on prereg profiles, and its stages are named and append
    verdicts.
  - Watch specs are not preregistrations: they lack the prereg schema, by design.
- **Proposed fix.** A new profile in the admission tool, `admit.py --watch <ID>`. Its stages,
  reusing `forward_watch.verify`, `decide`, `watches_ever_frozen` and `route_boundary`:
  - registration: the spec is on development, with its first-parent date;
  - chain: verification;
  - evaluator: attestation continuity;
  - window: opened;
  - sequential: the route boundary;
  - corroboration: the spec's conditions;
  - void.

  Verdicts are written the same way (`docs/research/verdicts/<ID>/`). Tests cover synthetic
  logs: an admit, a close, a void, an unattested evaluator, and an m increase.
- **Rejected alternatives:**
  - *Converting watches into preregistrations.* The prereg schema cannot express the
    sequential rule, and the specs are frozen.
  - *A separate admission tool.* It would duplicate verdict writing.

## Round 2 (2026-10-09): revisions after the skeptic's DISPUTE on all five questions

The skeptic's evidence is adopted where it is stronger. Each item below replaces the round-1
fix above.

### Q1 (revised): an explicit route test

**Engine defects found.** These are fixed in the engine now, because they misimplement the
watches' own frozen specs whatever route is chosen:
- `_anniversaries` stops at a watch's first own-boundary verdict, so a higher route boundary
  could never be read.
- `decide` evaluates year 1 for H366200, whose spec says "the first (365 days) decides nothing".
  It could close H366201 before year 4, whose spec says "readings in years 1-3 change nothing".
- `decide` ignores H366201's leg, episode and issuance conditions.
- A correction booked after an anniversary can rewrite that anniversary.

**The route test.**
- Each watch i gets an α_i fixed at freeze (Q2).
- **Upper (route) boundary:** ln((1−β)/α_i).
- **Lower (close) boundary:** ln(β/(1−α)), unchanged from the watch's spec.
- **The watch's own promote is a non-terminal trigger.** Its frozen consequences still apply at
  the watch's own boundary: H366201's close-on-issuance (long leg ≤ 0) closes the watch. The log
  and the anniversary reports continue to the route boundary or the close boundary.
- **The first decisive anniversary** is the spec's: year 2 for H366200, year 4 for H366201. New
  specs must state it as a structured field.
- **Pinned inputs.** Anniversary k is computed from the log lines dated up to its cut plus 63
  sessions, the correction lookback, and is written once.
- **Error rates.** At m = 2, Wald's bounds keep β' ≈ 0.205. The route's own error-rate table is
  published with the implementation; the 76% eventual-promotion figure no longer applies.

### Q2 (revised): online alpha-spending on a freeze ledger

- **The freeze ledger.** An append-only file on development lists every watch at freeze, with
  its ordinal i. CI checks it with the prefix rule, and `freeze`, `genesis` and `log` refuse an
  ID not on it.
- **The spending.** α_i = α · γ_i with γ_i = 1/(i(i+1)), so Σγ ≤ 1. This controls family error
  for an open-ended stream of watches. A boundary set by a decision-time m does not: admitting
  H366200 at m = 2 and later watches at m ≥ 10 spends about 1.3α in total.
- **Values:**
  - H366200 (i = 1): α_1 = 0.025, boundary ln(0.8/0.025) = 3.47, the same as round 1's m = 2;
  - H366201 (i = 2): α_2 = 0.0083, boundary 4.57.
- **The amendment is legitimate now:** `route.json` is not on development, and no window has
  opened.
- **Rejected:** m from `git log --all`. It depends on the clone, so deleting and pruning a
  branch shrinks it.

### Q3 (revised): a sizing procedure frozen at ratification

- **The host:** the D6 static 60/40.
- **The sleeve:** the watch's *tilt book* (benchmark + active). The active return itself cannot
  be held long-only.
- **Carve-outs:** x ∈ {0, 2.5, 5, 10}%.
- **Risk** comes from the full recorded books. **Alpha** is the lower 80% bound of the forward
  record's annualised active.
- **The rule:** the largest x that raises the excess Sharpe in both F46 regimes and keeps the
  extra maximum drawdown within a numeric budget. **Hudson sets the budget at ratification**;
  the proposed default is 1 percentage point of extra drawdown.
- **The record:** a deterministic sizing record, immutable, due within 30 days of an ADMIT. Its
  absence means size 0. Paper only until Hudson approves any live change.

### Q4 (revised): CUSUM de-admission plus the drawdown cut

- **CUSUM.** From admission, a CUSUM on the yearly LLR increments: W = max(0, W − ΔLLR), alarm
  at h = 2.0, which de-admits.
  - The skeptic's 200k-path simulation, from the most favourable start:

    | True Sharpe | Outcome |
    |---|---|
    | 0.3 | false alarm within 20 years 6% of the time |
    | −0.3 | detected 81% of the time, median 13 years |
    | 0 | median detection 26 years |

  - The close boundary alone de-admits at Sharpe −0.3 only 4.7% of the time within 20 years.
- **The drawdown cut.** The sleeve goes to size 0 if its extra drawdown in the host exceeds the
  Q3 budget.
- **Both are frozen now,** so neither is a post-data fork.

### Q5 (revised): its own chain and verifier

- **The chain.** An `admit_watch` ADMIT chain with its own verifier. The registration stage
  does not run through `prereg.load`: a watch is not a preregistration.
- **Stages:**
  - registration: the spec is on development's first-parent history;
  - freeze-ledger entry;
  - chain;
  - **evaluator continuity:** the evaluator hash is recomputed at each line's `code.sha`, and
    attestations count only from commits on development;
  - code;
  - refutations;
  - witness: the log prefix is on development, with `witnessed_sha` recorded;
  - window;
  - sequential, pinned by the log prefix's line sha;
  - corroboration;
  - void;
  - sizing (Q3).
- **Records.**
  - Verdict records are keyed per anniversary (O_EXCL); the latest one governs.
  - A DE-ADMIT state exists.
  - The verifier recomputes everything from the prefix, so a hand-written ADMIT cannot
    verify (red-team 7b).
- **Tests:**
  - own-promote first, then a route-admit at a later anniversary;
  - a late correction does not change a written verdict;
  - deleting a branch does not lower m;
  - H366201's year-3 close is suppressed;
  - a long leg ≤ 0 closes the watch;
  - the CUSUM alarm de-admits.

## Round 3 (2026-10-09): narrow revisions after round 2

**Round-2 verdicts:** Q1 CONCUR (with wording fixes); Q2-Q5 DISPUTE on narrow points.
Revisions:

- **Q1 wording.**
  - Anniversaries are pinned by **log position**: an anniversary settles after the 64th session
    line past the cut, counted in log order. This is what the engine now does (commit b5582a6). It does not
    depend on `recorded_at`, which varies with when catch-up runs happen.
  - The two frozen specs cannot gain a structured field. Their first decisive anniversary is
    read from their frozen wording and pinned by a test on the committed spec (H366200 → 2;
    H366201 → 4).
  - New specs must carry the field.
  - β' is restated per α_i: about 0.205 at α/2 and 0.209 at α/6.
- **Q2: the founding cohort split, and an honest statement about later watches.**
  - H366200 and H366201 froze two hours apart, before the policy existed, so their order
    carries no information. They share γ_1 + γ_2 = 2/3 equally: α_i = α/3 = 0.0167 each,
    boundary ln(0.8/0.0167) = ln 48 = 3.87.
  - From ordinal 3 on, γ_i = 1/(i(i+1)), so Σγ = 2/3 + 1/3 = 1.
  - **Stated plainly in the policy:** ordinal 5's boundary is 6.17 nats, about 137 years of
    drift at a true Sharpe of 0.3. **Watches from about ordinal 4 on have no practical route.**
    A new watch is a record, not an admission path, unless a later policy (frozen before its
    window) re-allocates unspent α.
  - **Simulated route admission at a true Sharpe of 0.3 (skeptic, 100k paths), for comparison:**

    | Boundary | By 20 years | By 40 years | By 100 years |
    |---|---|---|---|
    | ln 32 = 3.47 | 3.5% | 24.6% | 69% |
    | ln 96 = 4.56 | 0.4% | 9.6% | 56% |
    | ln 48 = 3.87 (adopted) | between those | between those | between those |

    The implementation publishes the exact figures.
- **Q3: the alpha input for sizing.** The **stagewise-ordering lower confidence bound** for the
  frozen route test, at 80%, computed by seeded simulation (the standard for group-sequential
  designs). A naive bound at a stopping time covers the truth only 64-72% of the time, and 0% at
  a true Sharpe of 0.15. A sleeve is never sized up later on the same record.
- **Q4: the CUSUM increment.**
  - **The increment** is ΔLLR_k = t_k(θ S_k − θ²/2), from **year k's own data only**. A
    difference of full-record LLRs would revalue the past whenever σ̂ moves.
  - **The drawdown cut** is checked daily on the paper path. It is a risk limit, not a look.
    It is the host-with-sleeve nominal maximum drawdown minus the host's alone. A breach sets the
    size to 0 until a new debate.
- **Q5: records and ordinals.**
  - Sizing is a **separate record citing the ADMIT**, not a stage of the ADMIT chain.
  - An ID must be on the development freeze ledger before `freeze`. Concurrent branches get
    ordinals in first-parent merge order.
  - Tests: deleting a branch changes no ordinal and no α_i; a volatility shift alone does not
    trip the CUSUM.

## Decision-debate consensus (2026-10-09)

**Outcome: three rounds; the skeptic CONCURs on Q1-Q5.** Hudson has not ratified it yet.
Nothing is implemented beyond the engine corrections to `decide()` (commit b5582a6), which
fix how the two frozen specs were read and stand whatever route is chosen.

| Q | Agreed fix | Why (evidence) |
|---|---|---|
| Q1 test | Upper boundary ln((1−β)/α_i) and lower ln(β/(1−α)) (unchanged). The own promote is non-terminal, but its frozen consequences apply (H366201's close-on-issuance). First decisive anniversary 2 (H366200) and 4 (H366201). Each anniversary settles after the **64th** session line past its cut, by log position, and is written once. | The old loop stopped at the own promote, so the route could never fire. Wald's bound keeps β' ≈ 0.205-0.209 |
| Q2 multiplicity | An append-only freeze ledger on development (an ID must be listed before `freeze`; concurrent branches take ordinals in first-parent merge order). The founding cohort H366200 and H366201 gets α/3 each (boundary ln 48 = 3.87); from ordinal 3, γ_i = 1/(i(i+1)). α already assigned, including to a closed or voided watch, is **never recycled**; a later policy may reshape only the unassigned tail. **From ordinal 3 on there is no practical route** (5.26 nats: 4.5% by 40 years at a Sharpe of 0.3). | A decision-time m does not control family error in an open-ended stream (about 1.3α). `git log --all` can forget branches |
| Q3 sizing | Host: the D6 60/40. Sleeve: the tilt book, x ∈ {0, 2.5, 5, 10}%. Risk from the full recorded books. **Alpha:** the stagewise-ordering 80% lower bound, simulated on the full route design. The largest x that lifts the excess Sharpe in both F46 regimes within an extra-drawdown budget **Hudson sets** (proposed: 1 pp). A separate sizing record citing the ADMIT is due in 30 days, or the size is 0. Never sized up later; paper only until Hudson approves. | A naive bound at a stopping time covers the truth only 64-72% of the time (0% at a true Sharpe of 0.15) |
| Q4 de-admission | A CUSUM on per-year own-data ΔLLR_k (the same pinned windows as the anniversaries), h = 2.0. A daily drawdown cut on the paper path (host-with-sleeve nominal max drawdown minus the host's alone) sets the size to 0 until a new debate. | The close boundary alone de-admits a Sharpe of −0.3 only 4.7% of the time in 20 years. The CUSUM catches 81% (median 13 years), with 6% false alarms |
| Q5 build | An `admit_watch` ADMIT chain with its own verifier. Stages: registration on first-parent, ledger, chain, evaluator continuity at each line's `code.sha` (attestations only from development), code, refutations, witness, window, sequential, corroboration, void. Records per anniversary (O_EXCL), and a DE-ADMIT state. Sizing is a separate record. Tests: as round 2, plus branch deletion changes no ordinal or α_i, and a volatility shift alone does not trip the CUSUM. | `admit.evaluate` starts with `prereg.load`, and `verify_record` re-loads the preregistration. A hand-written ADMIT must not verify (red-team 7b) |

**Route admission at a true active Sharpe of 0.3** (skeptic, 100k simulated paths, yearly
checks, close absorbing):

| Boundary | By 20 years | By 40 years | By 100 years |
|---|---|---|---|
| ln 48 = 3.87 (founding cohort) | 1.7% | 17.9% | 64.7% |
| 5.26 (ordinal 3) | 0.1% | 4.5% | 47% |

**For Hudson:** Accept all / Amend Q<n> / Explain Q<n>. Two values are his to set:
- Q3's drawdown budget (proposed: 1 pp);
- whether the founding-cohort split (Q2) is preferred over strict freeze order (α/2 and α/6).

**After ratification:**
- `docs/research/forward_watch/policy/route.json` is replaced by the ratified policy and the
  freeze ledger, before either watch's PR merges (no window has opened);
- the `admit_watch` chain is built with its tests;
- H366201's committed-spec test lands on its branch.
