# Credit sleeve in the static product: does a fallen-angel sleeve improve the 60/40?

Status: **FROZEN** (2026-10-09), before any mix statistic was computed, after two rounds of
adversarial review (round 2: CONCUR). This is a descriptive study like F366206: it records no
trial, fits no portfolio weight, recommends no size, and supports no admission.

## The question (next-study board, 2026-10-09: two of three for this study)

Two findings disagree about the static product (D6):

- **F38:** no single third sleeve reliably improves the 60/40; credit (HYG) "doesn't help at
  all". At a 10% carve its ΔSharpe interval was [−0.037, +0.013].
- **F404731:** ANGL beats HYG (+1.9%/yr, SPA p 0.024, alpha t 1.33) and calls ANGL "a reasonable
  credit-sleeve choice" for the static allocation.

The question is whether carving part of the 60/40 into ANGL measurably:

- raises its excess Sharpe in both stock-bond correlation regimes (F46);
- leaves the drawdown no deeper;
- beats the same carve in HYG;
- beats a sleeve that only reproduces ANGL's lagged stock and bond exposure.

**Prior expectation, stated now:** F38 (HYG adds nothing) and F366206 (CEF sleeves trade
drawdown for Sharpe) point to NO MEASURABLE EFFECT, SHARPE ONLY or NO CREDIT.

**The dissent, recorded:** one member preferred an out-of-sample replication of the metal-trust
discount mechanism on SPPP and CEF. It argued this study is largely answered by F38. This study
adds what F38 did not test:
- ANGL rather than HYG;
- a lag-matched replica control;
- a credit-crisis stress;
- a noise band anchored on F38's interval.

## Data (recorded series and frozen snapshots; nothing is fetched)

| Role | Series |
|---|---|
| The product p | the recorded static 60/40 SPY/IEF, `TR-20261006T005053Z-9336581d#0` (DS-32c992fb; recorded 2007-06-08..2026-10-02) |
| The sleeve | the recorded static 100% ANGL, `TR-20261007T041713Z-2cbc8fe5#0` (credit_sleeve.v1, DS-62945d51; recorded 2012-05-10..2026-10-02) |
| The credit control | the recorded static 100% HYG, `TR-20261007T041712Z-eb23cf97#0` (credit_sleeve_reference.v1, DS-62945d51; same dates) |
| Provider robustness (reported only) | FALN `TR-20261007T043055Z-b289eaaa#0`, ANGL `TR-20261007T043113Z-f6ceb5cb#0`, HYG `TR-20261007T043054Z-91da6309#0` (DS-1fc68b55; recorded 2016-07-21..2026-10-02) |
| Cash c | DTB3 from DS-32c992fb |
| Replica factors | SPY and IEF session returns from DS-32c992fb |
| Crisis proxy input | HYG session returns from DS-c6ac870a (private, option A) |

- **Session returns** from a snapshot are `(1 + night)(1 + day) − 1`, distributions reinvested
  at the open (the engine's convention, `daily_data.session_returns`).
- **Build sessions are dropped.** Each recorded series executes its build at the open of its
  first session, so that session is not a holding return (F366205's rule). It is dropped from
  every window, the replica grid and every regression. So:

  | Window | Dates |
  |---|---|
  | main | 2012-05-11..2026-10-02 |
  | negative correlation | 2012-05-11..2022-07-31 |
  | positive correlation | 2022-08-01..2026-10-02 (F46's cut, as in F366206) |
  | crisis stress | 2007-06-11..2012-05-09 |
  | provider robustness | 2016-07-22..2026-10-02 |

**Feasibility, checked before the first draft.** These checks computed no return statistic.
- Every recorded series verifies against its `returns_sha` on load.
- Each sleeve series covers the 60/40's sessions in its span exactly (3,620 and 2,565 sessions,
  counted before the build sessions are dropped), with none missing, none extra, and no
  forward fill.
- Cash, SPY and IEF cover every session.
- The private HYG covers all 1,241 sessions of 2007-06-08..2012-05-09, on the product's calendar.

## The arithmetic (fixed now)

- **The mix:** `m_t(x, s) = (1 − x) p_t + x s_t`, rebalanced each session to fixed weights. The
  carve comes pro rata from the 60/40. This is F366206's mix with the sleeve's realised series in
  place of benchmark + α.
- **Carve-outs:** x ∈ {5%, 10%, 20%}, F366206's grid.
  - The 2.5% carve a board member proposed is reported with statistics only and no verdict.
- **Daily statistics** are those of `tools/sleeve_break_even.py`:
  - excess Sharpe: the mean over the standard deviation of (r − c), × √252;
  - maximum drawdown: nominal, daily compounding, measured within the window from its first session.
- **Block statistics.** Credit ETFs price with a lag, which flatters daily Sharpe. So each window
  is also cut into consecutive 5-session blocks from its first session, with an incomplete final
  block dropped. The block excess Sharpe is the mean over the standard deviation of the block
  sums of (r − c), × √(252/5).
- **The replica sleeve (C4).** F366205's lagged-exposure convention:
  - `r^rep_t = c_t + Σ_{f ∈ {SPY, IEF}} [b0_f,k (F_t − c_t) + b1_f,k (F_{t−5} − c_{t−5})]`.
  - k is the block containing t, on a 5-session grid from the main window's first session.
  - The betas come from `beta_control.dimson_betas`: ANGL's block excess returns on SPY's and
    IEF's, same-block and previous-block. They are ex ante: blocks strictly before k only,
    window 104 blocks, minimum 52 usable blocks (F366205's product settings).
  - Block 0 has no previous block, so the first replica block is block 53. Sessions before it,
    and in an incomplete final block, have no replica.
  - C4 is evaluated on the replica's sessions, intersected with each regime window.
- **The crisis proxy (C5):**
  - **Regression.** ANGL's block excess return is regressed by OLS on HYG's same-block and
    previous-block excess returns, over the main window (in-sample, disclosed).
    - β̂ = b0 + b1;
    - α̂ = the intercept × 252/5, annualised.
  - **The proxy sleeve** is `s'_t = c_t + β̂ (H_t − c_t) + α̂/252` over the crisis window, where H
    is the private HYG series.
    - In-sample, ANGL drew down further than HYG (−29.3% vs −22.0%, F404731). β̂ carries the
      part of that difference that co-moves with HYG on average; a constant mean shift would
      hide it.
    - An idiosyncratic part (such as the 2020 downgrade wave) and any crisis-only rise in beta
      are not carried. That is one reason the direction of the proxy's remaining bias in 2008
      is not established; it is disclosed as unknown.
  - **Proxy screen, frozen.** Over the main window, H must have a correlation of at least 0.995
    with the recorded HYG series, and an annualised mean difference of at most 0.25%/yr in
    absolute value.
  - C5 is **NOT RUN** if the screen fails, or if H misses any of p's crisis-window sessions.

## Criteria for a carve x (all on the realised ANGL series)

**The noise band.** The band is δ(x) = 0.25·x in annualised Sharpe: 0.0125, 0.025 and 0.05 at
5, 10 and 20%. It is F38's ΔSharpe half-width at a 10% carve (about 0.025), scaled
proportionally with the carve.

**A Sharpe criterion** compares two Sharpes through Δ in each regime window. At one frequency it:
- **passes** if Δ ≥ +δ in both windows;
- **fails** if Δ ≤ −δ in either window;
- is **unresolved** otherwise.

It is read at both frequencies, daily and block:
- **pass** = pass at both;
- **fail** = fail at either;
- **unresolved** otherwise.

So a criterion that holds at only one frequency does not pass.

| | Criterion | Δ |
|---|---|---|
| **C1 Sharpe** | Sharpe criterion | Sh(m(x, ANGL)) − Sh(p) |
| **C3 Credit control** | Sharpe criterion | Sh(m(x, ANGL)) − Sh(m(x, HYG)) |
| **C4 Replica control** | Sharpe criterion, on replica sessions only | Sh(m(x, ANGL)) − Sh(m(x, replica)) |
| **C2 Drawdown** | MDD(m(x, ANGL)) ≥ MDD(p) (no deeper) in both regime windows, daily path | — |
| **C5 Crisis stress** | MDD(m(x, s')) ≥ MDD(p) over the crisis window, daily path | — |

**C2 and C5 are read at a zero budget, and that reading is final for this study.** No drawdown
budget ratified later (FORWARD_ROUTE_PROPOSAL Q3, whose default predates this study) re-reads
this verdict. This study's numbers must not be used to set that budget.

**Verdict for a carve x:**

| Verdict | When |
|---|---|
| **NO CREDIT** | C1, C3 or C4 fails |
| **NO MEASURABLE EFFECT** | none of C1, C3, C4 fails, and at least one is unresolved |
| **SHARPE ONLY** | C1, C3 and C4 pass, and C2 or C5 fails |
| **ADD** | C1, C3 and C4 pass, C2 passes, and C5 passes. "ADD (untested in a credit crisis)" if C5 is NOT RUN |

**Overall:** every carve's verdict is reported. The headline is the best carve's, ranked
ADD > SHARPE ONLY > NO MEASURABLE EFFECT > NO CREDIT.
- The three carves use the same series and are highly dependent. Taking the best of three is a
  mild multiplicity and is disclosed.
- ADD lists the carves that read ADD and recommends no size. Sizing is Hudson's decision.

## Consequences (stated now)

A consequence applies to the carves that read it. Any carve that reads NO CREDIT is named in
F404731's wording as "measurably worse at x%", whatever the headline.

- **ADD:** F404731's sleeve wording stands, naming the carves that read ADD. It becomes a
  static-product choice for Hudson. It is not an admission, and not evidence that the alpha
  persists.
- **ADD (untested in a credit crisis):** as ADD, with "untested in a credit crisis" carried into
  F404731's wording.
- **SHARPE ONLY:** the sleeve measurably raises the 60/40's Sharpe but deepens its drawdown at a
  zero budget, like the CEF sleeves (F366206). It suits a Sharpe-seeking product, not a
  capital-preservation one; which the product is remains D8 (open). F404731's wording is
  qualified to say so.
- **NO MEASURABLE EFFECT:** F404731's wording is qualified to "no measurable effect on the
  60/40", neither retracted nor confirmed. This is consistent with F38.
- **NO CREDIT:** F404731's sleeve wording is retracted, in agreement with F38.

## Reported, with no role in the verdict

- Every Δ, at both frequencies.
- The extra drawdown in percentage points.
- The 60/40-sleeve correlations.
- The replica's mean betas.
- α̂, β̂ and the screen statistics.
- C5's mix drawdown at α̂ = 0, and under the plain proxy HYG + (mean ANGL − HYG).
- The 2.5% carve, statistics only.
- The 2022 calendar year.
- **Provider robustness:** FALN and ANGL of DS-1fc68b55 against its own HYG, the C1 to C3
  statistics on the robustness window split at the regime cut.

## Limits

- **ANGL's alpha is in-sample (2012-26).** This decides a static choice. It is not evidence that
  the alpha persists.
- **A point estimate inside the band is not a test.**
  - The band is a pre-stated tolerance, not a confidence interval.
  - The positive-correlation window is 4.2 years.
- **The replica uses raw SPY/IEF returns.** The sleeve's recorded series carries its
  (initial-only) costs.
- **Ledger and invariants.** The tool checks these itself and refuses to write if any fails:
  - No trial is recorded, no portfolio weight is fitted, and the grid is fixed.
  - `trials.family_counts()` is recorded in full at start and end and must be unchanged.
  - H366200's evaluator hash must be unchanged.
  - This study adds files only, so it touches no source pinned by H366200 or H366201. H366201's
    spec lives on the watch branch, where its evaluator hash is checked when this commit is
    merged there.
  - `tools/sleeve_break_even.py` is not edited, and a test reproduces F366206's committed results.
- **Option A.**
  - DS-c6ac870a's observations stay private.
  - Only aggregates are written. The tool refuses to write any list longer than 10 entries,
    or any object keyed by date, and tests check both.
- **Real drawdown is not computed.** No CPI series is frozen in the repository.

## Implementation and review

- `tools/credit_sleeve_mix.py` is a sibling of `sleeve_break_even.py`. It reuses that tool's
  statistics and the beta-control block code.
- It is committed, with tests, before the run, in the same commit that freezes this
  protocol. The tests cover:
  - a lagged sleeve replicated lag for lag;
  - the pass/fail/unresolved table at both frequencies, including the one-frequency case;
  - every build session absent from the windows, the replica grid, the regression and the screen;
  - the refusal to write on a ledger or evaluator change, and on a series in the output;
  - F366206's reproduction.
- **Review.**
  - Round 1 of the adversarial review returned DISPUTE (1 blocker, 4 major, 4 minor). All were applied.
  - One deviation was the proposer's own: a criterion passing at one frequency and unresolved at the other is *unresolved*, not *failed*.
  - Round 2 returned CONCUR and accepted the deviation. A real contradiction still fails, since Δ ≤ −δ at either frequency fails. Its five minor items were applied.
- The result file is `docs/research/data/credit_sleeve_mix.json`.
