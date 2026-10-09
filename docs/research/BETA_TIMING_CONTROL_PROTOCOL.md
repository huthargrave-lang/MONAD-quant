# Beta-exposure control of the admission candidates (H404702; CEFS and MDCEX vs PCEF)

Status: **FROZEN** with the board record below (2026-10-09). This was before any beta,
regression or control series was computed on real data, and before any replay was run.

## Why this test, and why now

- F366204 found that CEF discounts close, but against matched ETFs the profit was **beta
  timing**: the rule bought levered funds after sell-offs, and the controlled α was +0.13%/yr
  (t 0.46).
- Two candidates are on course for admission in 2027:
  - **H404702**: within-category CEF discount with hysteresis; registered; forward window to
    2027-10-07.
  - **CEFS vs PCEF** (F404732): v2 p_gate about 0.005; blocked only by the 10-year floor until
    about 2027-05. MDCEX vs PCEF corroborates it.
- Neither has been controlled for *time-varying* beta. F404724's unconditional active beta
  (−0.002) cannot see a beta that is high just before rebounds.
- The prior for beta exposure is not low. F366204's own control implies a within-family
  controlled α of about 0.16 of 0.62%/yr (by subtraction, s ≈ 0.26) for H404702-type selection
  against ETFs.
- If the edge is beta exposure, a 2027 admission would be valid on paper and misleading in
  substance. It would also be exactly the exposure a low-drawdown product must avoid. Either
  answer changes a decision.

**Board ruling (2026-10-09; strategy, skeptic and data members)** on the next steps, in order:
1. this control;
2. a forward watch for the F366202 metal-trust tilt (a separate protocol);
3. single-country CEF vs country ETF, only if this control finds beta exposure in H404702;
4. commodity event days: already answered, null (F366200, F404705).

## What this is and is not

- No new rule, point, search or candidate. The control reads recorded series. Weights come
  from **exact replays** of recorded trials, run with the recorded spec in the recorded
  family. The gate keys family members by point (`admit_tactical._point_key`), so an exact
  replay adds no member and changes no statistic. No new family or domain key is created.
- **Gate-invariance check (required).** Before and after the replays, the tool records
  H404702's gate inputs:
  - the family's latest-ok trial per point key with its returns sha;
  - the benchmark's latest recorded returns sha;
  - the unknown-spec set.

  They must be identical, or the result is **NOT RUN** (disclosed).
- H404702's prereg, forward window and gate code do not change. Its admission evidence does,
  through the record in "Consequences".

## Data (all frozen; no fetch)

| Series | Source |
|---|---|
| H404702 candidate | `TR-20261006T034817Z-5245a64f#3` (`cef_banded {"exit": 0.5, "signal": "z52_cat"}`), DS-18cef162 + CEFNAV-fd7099e2, 2003-12-31..2026-10-02 |
| H404702 benchmark | `TR-20261006T012341Z-86834435#0` (`cef_equal_weight`, 1x), the search's own reference, which the gate pairs it with. The tool asserts that all four 1x reference trials on this window share returns sha 23aa6231, or NOT RUN |
| Positive control: the F366204 tilt | `TR-20261009T073545Z-b39f895c#0` (`cef_etf_tilt {"lag": 1}`, after correction 1) vs `TR-20261009T073344Z-da2b0d8d#0` (`cef_etf_bench`), DS-c6ac870a + CEFETF-0bea95e6 |
| Negative control: the F366202 metal-trust tilt | `TR-20261008T185930Z-9488e29b#0` (`trust_tilt`) vs `TR-20261008T185928Z-5c567742#0` (`pairs_static`), DS-6edd69e3 + CEFNAV-fd7099e2 |
| CEFS vs PCEF (the decision series) | `TR-20261007T045202Z-1202df3f#0` vs `TR-20261007T045201Z-e56e6db5#0`, DS-6e2f0f62 |
| MDCEX vs PCEF (corroboration only) | `TR-20261007T051701Z-9672d791#0` vs `TR-20261007T051659Z-dfb4dff7#0`, DS-84167824 |
| Asset, SPY and IEF returns | each snapshot's `(1 + night)(1 + day) − 1` from `snap.returns()`, which is what holdings earn |

## Replays (for weights)

- **Call.** `D = daily_domains.DOMAINS[<domain>]`, `ctx = D.load(<recorded data>)`, then
  `evaluate_daily(D.decide(ctx, point), ctx.snap, start, end, cost_multiple=1.0, tiers=D.tiers(ctx))`.
  - `(start, end) = D.window(ctx)` must equal the recorded window.
  - Each replay is a counted trial with the recorded spec (`daily_spec(point, domain=<domain>)`),
    in the recorded family, on a clean tree. The hypothesis is named in the run context, never
    as `open_run(hypothesis=)`.
- **Reproduction.** The index must be identical and the maximum absolute difference against
  the recorded series must be ≤ 1e-12, or NOT RUN. Whether the returns sha is identical is
  reported.
- **Weight identity.** Per book, from the second session on,
  `f_t = Σ_i w_i,t−1 r_i,t + (1 − Σ_i w_i,t−1) c_t − return_t`.
  - Every `f_t` must be ≥ −1e-12, and Σ f_t must equal `cost_paid` within 1e-9, or NOT RUN.
  - This proves `weights.shift(1)` is the weight held during session t. Cash has beta 0, so X
    needs no cash leg.
- **The products are static books** (100% one asset). Their recorded series are the products'
  total returns, so no replay is needed. Their first scored session (the build) is dropped.

## The control (pre-registered)

### Sample and blocks

- **Start.** For a replayed pair, the first session at which both books' exposure is ≥ 1 − 1e-9,
  which removes the build-up. For the products, the second scored session.
- **Blocks.** Consecutive 5-session sums of daily returns, anchored at the start. An incomplete
  final block is dropped. One grid per candidate serves both the betas and the regressions.
- **Regression sample.** From the first block that has the minimum number of complete prior
  blocks (below) to the end. Every share (s, the robustness shares) uses this identical set of
  blocks.

### Ex-ante Dimson betas

- For asset i and factor F: `b0_i` and `b1_i` are the OLS slopes of i's block return on
  `F_w` and `F_{w−1}`.
- **Data used.** Only blocks that end before the block in which the beta is used, and only
  blocks in which i has 5 finite returns.
- **Windows:**

  | Use | Window | Minimum | Below the minimum |
  |---|---|---|---|
  | Primary, replayed books | the last 156 such blocks | 48 | b0 = 1, b1 = 0 |
  | Primary, products | 104 blocks | 52 | — |
  | R4 | 26 blocks | 13 | — |

- **Reported:** the |Δ|-weighted share of exposure that uses the fallback.

### The exposure series X (daily, then summed per block)

- **Replayed pairs.** `X_t = Σ_i Δ_i,t (b0_i F_i,t + b1_i F_i,t−5)`, with
  `Δ_i,t = w^cand_i,t−1 − w^bench_i,t−1`.
  - The sum runs over every asset either book holds.
  - The positive and negative controls include the ETFs: an ETF's factor is its own return,
    with b0 = 1 and b1 = 0.
- **Products.** `X_t = (b0 − 1) F_t + b1 F_t−5`, with F = PCEF.

### Primary factor F

| Candidate | F |
|---|---|
| H404702 | for fund i, the **equal-weight daily return of the other funds in i's CEFConnect category** that hold benchmark weight at the previous close; the global equal-weight eligible return when fewer than 4 others exist |
| Positive and negative controls | each fund's matched ETF (F366204's mapping; PHYS → GLD, PSLV → SLV) |
| Products | PCEF |

H404702 is category-neutral, so any beta exposure it carries is within a category. Leaving
fund i out stops it pulling its own beta toward 1.

### Primary statistic (g fixed at 1)

- `α = mean_w(a_w − X_w)`, the beta-hedged active return. `t_α` is its Newey-West t.
- `E = mean_w(X_w)`, the explained part. `t_E` is its Newey-West t.
- `s = α / mean_w(a_w)`, the share of the raw active return the control keeps.
- **Newey-West lag.** Both lag 4 and lag `floor(4 (T/100)^{2/9})`. Each t condition below must
  hold at both lags.
- **Annualisation.** × 252/5.
- **Reported:**
  - the 95% Fieller interval for s, from the NW long-run covariance of `(a_w − X_w, a_w)`;
  - E split into its static part, `mean(Σ Δ β) · mean(F)` (the products: `(β̄ − 1) · mean(F)`),
    and its timing remainder.

### Robustness (computed for every candidate on the same blocks)

| Check | What it is |
|---|---|
| R0 | free g: `a_w = α + g X_w + e_w`; report g, its CI and the t of g − 1 |
| R1a | H404702 only: F = the global equal-weight eligible return (the benchmark) |
| R1b | F = SPY. For the products, `X = (β_prod − β_PCEF)` applied to SPY, each a Dimson beta to SPY |
| R3 | two factors, F = the primary factor plus IEF, Dimson betas on both. H404702 and the positive control only (IEF is in their snapshots) |
| R4 | the primary with 26-block betas (minimum 13): beta that ratchets up as NAVs fall |
| R2 | Treynor-Mazuy: `a_w = α + b F_w + c F_w² + d F_{w−1} + e_w`, with F the benchmark's or PCEF's return. Report c and its t; "convexity detected" if c > 0 at t ≥ 2 |
| R2b | conditional beta: `a_w = α + b F_w + c S_{w−1} F_w + d F_{w−1} + e_w`, with S the benchmark's trailing 13-block return |

For each check, `s_R` is its α divided by mean(a_w).

### Limitations, stated

- Long-window ex-ante betas capture timing *across* funds, not a fund's own beta rising after a
  sell-off. Only R4, R2 and R2b can see that.
- CEF prices are stale. Dimson betas reduce the bias, but they do not remove it.

## Verdict, stated in advance (per candidate)

**Primary rules**

| Verdict | Condition |
|---|---|
| **SURVIVES** | `s ≥ 0.5` and `t_α ≥ 2`, and every robustness share (R0, R1a, R1b, R3, R4, R2, R2b, where computed) is ≥ 0.25 |
| **UNDERPOWERED** | the SURVIVES conditions except `t_α ≥ 2` |
| **BETA EXPOSURE** | `s < 0.25` and `t_E ≥ 2` (static or timed beta; the finding states which part dominates) |
| **BETA-LIKE (underpowered)** | `s < 0.25` and `t_E < 2` |
| **INCONCLUSIVE** | anything else, including mean(a_w) ≤ 0 on the sample |

**Robustness can establish BETA EXPOSURE**, naming the factor, when all three hold:
- one of R1a, R1b, R3 or R4 has `s_R < 0.25`;
- its explained part has t ≥ 2.5 (Bonferroni over the four);
- the primary is not SURVIVES. If the primary is SURVIVES, the verdict is INCONCLUSIVE.

R0, R2 and R2b can only downgrade.

**Controls (method validity)**
- **Positive control.** The F366204 tilt must read BETA EXPOSURE or BETA-LIKE. If it reads
  SURVIVES or UNDERPOWERED, the method cannot detect what the repository already found, and
  H404702 cannot read SURVIVES (demoted to INCONCLUSIVE). Its within-family part (`A_within`,
  F366204's decomposition) is reported under this control. It is not decisive.
- **Negative control.** The metal-trust tilt must not read BETA EXPOSURE (the expected s is
  about 1, since X ≈ 0 by construction). If it does, the control is absorbing discount
  co-movement, and an H404702 BETA EXPOSURE is demoted to INCONCLUSIVE.

**Power, stated (t_raw ≈ Sharpe × √years)**
- H404702: about 6.7. SURVIVES is within reach if beta explains little.
- CEFS: about 1.7 over its sample. MDCEX: about 2.1.
- t_α ≈ s · t_raw / √(1 − R²_X). For the products X is small against about 9%/yr of tracking
  error, so SURVIVES would need s ≳ 1.2 (CEFS) or ≳ 0.95 (MDCEX). UNDERPOWERED is their
  realistic ceiling.
- CEFS is the decision series; MDCEX corroborates only.

## Consequences (mechanical)

- **H404702 reads BETA EXPOSURE, BETA-LIKE or INCONCLUSIVE.** File the objection as follows:

  ```
  venv/bin/python tools/refute.py object H404702 --by beta-exposure-control \
      --claim "H404702's active return is not shown to be selection: beta-hedged α keeps s = <s> of the raw active (verdict <V>, BETA_TIMING_CONTROL_PROTOCOL.md)" \
      --evidence "docs/research/data/beta_timing_control.json sha256 <sha>; trials <replay keys>"
  ```

  - The admission gate's refutations stage BLOCKs while the objection is open.
  - Only a board other than this protocol's author may resolve it.
  - The web finding links `[[H404702|contradicts]]` and `[[F404713|contradicts]]`.
- **H404702 reads SURVIVES or UNDERPOWERED.** The finding records the controlled α, and links
  `[[H404702|supports]]`.
- **The products.** The finding links `[[F404732|...]]`. Any future CEFS registration must cite
  it. If CEFS reads BETA EXPOSURE, BETA-LIKE or INCONCLUSIVE, the same objection is filed
  against that hypothesis on its registration day. A BETA EXPOSURE reading would mean Saba's
  edge is leverage or beta, not discount capture.

## Implementation

- `tools/beta_timing_control.py`:
  - reads the recorded series (`trials.load_returns`);
  - runs the replays and checks reproduction, weight identity and gate invariance;
  - computes the statistics above;
  - writes `docs/research/data/beta_timing_control.json` (statistics only, no observations).
- Pure functions live in `src/research/beta_control.py`.
- Tests on synthetic data, with each expected label stated in advance:

  | Case | Expected |
  |---|---|
  | pure timing (Δβ high before up-blocks) | BETA EXPOSURE |
  | pure selection (α + noise) | SURVIVES |
  | a fund's own beta rising after drawdowns | R4 or R2b detects it, so not SURVIVES |
  | idiosyncratic discount reversion | SURVIVES |
  | reversion only in up-blocks | R2 "convexity detected", not SURVIVES |
  | betas use no data from the current block | (property check) |
  | an altered series | fails reproduction |
  | an altered fee | fails the weight identity |

## Board record (2026-10-09)

| Amendment | Source |
|---|---|
| g = 1 for the verdict; free g as R0 | statistics (attenuation of a free g biases toward SURVIVES), adversary |
| Dimson betas replace the regression lag g′X_{w−1} | statistics, adversary (a free lag can absorb the reversion itself), mechanics |
| Within-category leave-one-out factor as H404702's primary; the global EW as R1a; SPY as R1b | statistics, adversary (R3a) |
| R3 with IEF (half the universe is bonds); R4 26-block betas; R2b conditional beta | adversary |
| Blocks anchored at the start; incomplete final block dropped; complete fund-blocks only; one grid; one sample for all shares | statistics, mechanics |
| Symmetric evidence: SURVIVES needs t_α ≥ 2, BETA EXPOSURE needs t_E ≥ 2; underpowered labels; Fieller interval reported; mean(a) ≤ 0 is INCONCLUSIVE | statistics, adversary |
| Robustness: all shares ≥ 0.25 for SURVIVES; R1a/R1b/R3/R4 may establish BETA EXPOSURE at t ≥ 2.5 unless the primary is SURVIVES | statistics (downgrade only), adversary (may establish); resolved as stated |
| NW lag both 4 and floor(4(T/100)^{2/9}); annualisation × 252/5 (F366204 used × 52; s is unaffected) | statistics |
| No diagnostic family: exact replays in the recorded families plus a gate-invariance check | adversary (`daily_family_members` and red-team attack 4a: a new domain key would be the off-book route); mechanics confirmed that a point-keyed gate is unchanged by an exact replay |
| Benchmark `86834435#0`, the search's own reference; the four 1x references are asserted identical | mechanics |
| Replay call stated exactly; reproduction to 1e-12; weight-identity check; build-up excluded; the products' build session dropped | mechanics |
| Positive control (F366204) and negative control (metal trusts) | adversary |
| Mechanical consequence through `refute.py object`; web links | adversary |
| "Explained" split into static and timing parts; CEFS decides and MDCEX corroborates; the power text corrected | adversary, statistics |
| Not adopted: Vasicek shrinkage of betas. With g = 1, beta noise adds variance only, and shrinkage would add a choice | statistics (suggested) |

## Clarification 1 (2026-10-09, before any computation on real data)

- **R3 is computed for H404702 only.** The protocol says IEF is in the positive control's
  snapshot. It is not: DS-c6ac870a's universe has no IEF.
  - Substituting another bond ETF would be a new choice, so R3 is not computed for the
    positive control.
  - The positive control's verdict uses the remaining checks.
  - This changes nothing about H404702 (DS-18cef162 holds IEF).
- **The replays use each recorded trial's own point** (`class` and `params` from its ledger
  spec), not a domain default. This guarantees they are the same points.

## Clarification 2 (2026-10-09, before any computation on real data; found by the synthetic tests)

- **Weight identity when a book carries in orders.**
  - Some books have orders dated before the window. The evaluator builds those targets at
    the first session's open, which closing weights cannot express.
  - For those books the identity is checked from the second session (`f_t ≥ −1e-12`, as
    stated). The first session's fee, `cost_paid − Σ_{t≥2} f_t`, must lie in
    `[0, 3 × the dearest one-way rate on that session]`.
  - Books without a carry-in are checked on every session, with weight 0 before the first,
    and the exact sum. H404702's books have no order before 2003-12-31 (mechanics review),
    so the exact check applies to them.
  - An exact first-session fee would need a second evaluation, which the counted guard
    allows only as another recorded trial.
  - The per-session sign check is what catches a misaligned weight series. It is negative on
    some sessions of thousands.
- **The synthetic expectation for "reversion only in up-blocks" is corrected to match the
  verdict rule.**
  - The verdict rule takes Treynor-Mazuy into account only through `s_R2 < 0.25`, and reports
    "convexity detected" separately. The statistics member ruled this way because `α_TM`
    and `c` are collinear.
  - The table's "not SURVIVES" contradicted that rule. Its correct expectation is
    "convexity detected" reported, with the verdict following the rule.
  - A purely convex payoff (`a ∝ F²`) is added as a test that must not SURVIVE
    (`s_R2 < 0.25`).
  - The finding will state any convexity it detects.

## Result (2026-10-09): H404702 INCONCLUSIVE (procedural), CEFS SURVIVES, MDCEX BETA EXPOSURE

Run `tools/beta_timing_control.py run --acknowledge-live H404701 H404702` on tool commit `74ac9e1`, result `docs/research/data/beta_timing_control.json`
(sha256 3a8abd4c…, commit e5b553a).

**Checks.**
- Every replay reproduced its record exactly (max difference 0.0), with an identical returns
  sha and spec hash.
- The book identity held: exact for H404702, and with the carry-in rule for the controls.
- The gate inputs of both live registrations (H404701, H404702) were identical before and
  after the replays.

| Series | Verdict | Raw active | Beta-hedged α | s | t_α | Explained (t_E) | Robustness shares |
|---|---|---|---|---|---|---|---|
| **H404702** (2005-01..2026-09) | **INCONCLUSIVE** (demoted from SURVIVES by the positive-control rule) | +2.19%/yr | +2.26%/yr | 1.03 | 7.29 | −0.07%/yr (−0.35) | R0 1.02, R1a 0.90, R1b 0.88, R3 1.03, R4 0.92, R2 1.03, R2b 0.99 |
| Positive control: F366204 tilt (2017-08..) | INCONCLUSIVE (R2 share −0.45) | +0.81%/yr | +0.48%/yr | 0.59 | 1.31 | +0.33%/yr (1.31) | Treynor-Mazuy convexity c > 0 at t 6.3; R2b t −4.1 |
| Negative control: metal trusts (2012-10..) | UNDERPOWERED | +0.56%/yr | +0.33%/yr | 0.59 | 1.10 | +0.23%/yr (2.40), all timing | R1b 0.96, R4 0.37 |
| **CEFS vs PCEF** (2018-05..), the decision series | **SURVIVES** | +5.39%/yr | +4.40%/yr | 0.82 | 2.47 | +0.99%/yr (1.58) | R0 0.92, R1b 0.72, R4 0.68, R2 1.05, R2b 0.96 |
| MDCEX vs PCEF (2013-12..), corroboration | **BETA EXPOSURE** (established by R1b) | +3.87%/yr | +2.23%/yr | 0.58 | 1.24 | SPY beta: +3.4%/yr (t 4.33), static | R1b 0.13; Treynor-Mazuy concave (t −5.1) |

**Reading.**

1. **H404702.** Its active return carries no ex-ante beta exposure on any of the five factor
   definitions, and no convexity.
   - The formal verdict is INCONCLUSIVE only because the method's positive control did not read
     BETA.
   - F366204's known problem appears here as a strongly convex payoff (gains in rallies), which
     the linear control by design does not label. Only R2 flagged it.
   - By the frozen rule, the method could not certify selection, and objection **O4** was filed
     against H404702 (`docs/research/refutations/H404702.jsonl`). A board other than this
     protocol's author must resolve it before admission.
   - What the board will weigh is substantive against procedural:
     - H404702's own numbers (s 1.03, t 7.3, every share ≥ 0.88, Treynor-Mazuy c t −0.42) pass
       every test this protocol has;
     - the open question is whether a positive control that the linear control misses
       invalidates a clean reading of a different book.
2. **F366204's within-family part** (H404702's selection, seen again against ETFs) keeps its
   whole return under this control: s 1.02, t 4.8. Its beta timing lives in the category
   part, as F366204 found.
3. **CEFS** keeps 82% of its edge after hedging ex-ante beta (t 2.47), and passes every
   robustness check. The positive-control caveat applies to it as well; the frozen demotion
   rule names only H404702.
4. **MDCEX's** edge over PCEF is mostly static equity beta (SPY explains 3.4 of 3.9%/yr). Its
   corroboration of F404732 does not survive. CEFS's does.
5. **The negative control** reads UNDERPOWERED. A part is "explained" (t 2.4, all timing):
   trust discounts co-move with the metal, the over-absorption the adversary warned of. It is
   not BETA, so no demotion follows.

**Consequences applied.**
- Objection O4 against H404702: filed.
- The web finding links H404702 and F404713 as the protocol requires.
- CEFS: no objection. Any CEFS registration must cite this result.
- Board rank 3 (single-country CEFs) stays unrun: it was conditional on beta exposure in
  H404702, which was not found.

**Deviation, disclosed: the web edge type.**
- The protocol said the finding would link H404702 and F404713 as `contradicts`. The
  repository's edge rule reserves `contradicts` for a node that shows a claim false.
- This finding shows neither claim false. The demotion is procedural, and H404702's own
  statistics pass every check. So the links are `relates`.
- The binding consequence, objection O4, is filed as frozen. A `contradicts` edge would also
  have marked fourteen dependent nodes "disputed" and failed the web lint.
