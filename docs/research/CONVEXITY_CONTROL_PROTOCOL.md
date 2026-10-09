# Convexity-robust control of the admission candidates (successor to F366205)

Status: **FROZEN** with the review record below (2026-10-09). This was before the calibration
on its seeds ran, and before any convexity statistic was computed on market data. The
reviewer explored a draft of this method on synthetic seeds 0-99. The calibration therefore
runs on **fresh seeds 1000-1099**, with held-out books.

## Why

- The O4 board ruled that the beta-exposure control's SURVIVES "does not certify selection
  against convex payoffs" (F366207). A pure convex book read SURVIVES in 99/100 seeds, and R2
  flagged it in only 66%.
- The gap must be closed before the method is relied on again: for H404702's admission
  (2027-10-07 on) and for a CEFS registration (about 2027-05 on).
- Done now, no forward data can shape it.

## The method

### Terms (per asset, per block)

| Term | What |
|---|---|
| `F_w`, `F_{w−1}` | the linear factor and its previous block (Dimson) |
| `K_w = max(F_w, 0)` | the call-like payoff on the asset's own factor |
| `G_w = max(B_w, 0)` | the call-like payoff on the global factor (H404702 and the synthetic books) |

- No lagged convex terms.
- **Factors:**

  | Candidate | F | B |
  |---|---|---|
  | H404702 | each fund's leave-one-out category equal weight | the recorded equal-weight benchmark |
  | Products | PCEF (K on PCEF) | none (no G) |

### Loadings (state-conditional, ex-ante)

- **The state** of asset i in block w is the sign of Δ_i at the block's first session (+, −
  or 0), known at the block's start.
- **The regression.** An asset's loadings for block w come from its block return regressed (with
  an intercept) on the terms. Only complete past blocks that are **in the same state** are used.
- **Windows:** the last 156 such blocks with at least 48; for the products, 104 with at least 52.
- **Falling back:** with too few same-state blocks, the state-free estimate (the last window of
  all complete past blocks, same minimum) is used. Below that, the loadings are 1 on `F_w`
  and 0 elsewhere.

### Exposure (g fixed at 1)

- `X_t = Σ_i Δ_i,t (b0 F_t + b1 F_{t−5}) + Σ_i Δ_i,start(w) (γ K_t + η G_t)`.
- The convex terms use the block-start Δ. K and G are spread evenly over the block's sessions,
  so they never read a later session's weight.

### Statistics

- `α = mean(a_w − X_w)` and `E = mean(X_w)`.
- **Their variances** are the Newey-West variance (both lags, as F366205) **plus the bootstrap
  variance of mean(X)** from re-estimating the loadings:
  - a moving-block bootstrap, blocks of 13, the same block indices for every asset;
  - it resamples the asset residuals from the state-free full-sample fit; Δ and the factors
    stay fixed;
  - B = 999 on market data and B = 199 in calibration; seed 20261009.
- `s = α / mean(a_w)`.
- **The convex share of E** is frozen as the `|·|/2` parts: `K = F/2 + |F|/2` and
  `G = B/2 + |B|/2`, so the convex part is `Σ Δ (γ |F|/2 + η |B|/2)`. The rest is linear.

### Downgrade (one)

- **Regression.** `u_w = a_w − X_w` on `B_w`, `max(B_w, 0)`, `D_w`, `max(D_w, 0)` and the
  one-block lags of all four, with Newey-West errors at the automatic lag.
  - `D` is the |Δ|-weighted fund factor, `Σ_i |Δ_i,t| F_i,t / Σ_i |Δ_i,t|`.
  - The products have no B, so they use `D` (= PCEF) only.
- **It downgrades to INCONCLUSIVE** when a convexity coefficient (on a max term) is positive at
  t ≥ 2, or the downgrade regression's kept share is < 0.25. It never establishes exposure.

### Verdict

| Verdict | Condition |
|---|---|
| **SURVIVES** | `s ≥ 0.5`, `t_α ≥ 2`, no downgrade |
| **UNDERPOWERED** | `s ≥ 0.5`, `t_α < 2`, no downgrade |
| **MARKET EXPOSURE** | `s < 0.25` and `t_E ≥ 2` (the finding states the convex and linear parts) |
| **EXPOSURE-LIKE (underpowered)** | `s < 0.25`, `t_E < 2` |
| **INCONCLUSIVE** | otherwise, a downgrade, or `mean(a_w) ≤ 0` |

## Calibration (fresh seeds 1000-1099; the method must pass before any market data)

**The world** is `tools/o4_calibration.py`'s, with a global factor B = the equal-weight
return of all assets. The expected active is 2.2%/yr.

**Books:**

| Book | What it is |
|---|---|
| S | pure selection, as O4 |
| T | linear timed beta, s\* 0.26, as O4 |
| C | block convexity on the asset's own factor, as O4 |
| Cglob | block convexity on B |
| Cday | daily `max(F_t, 0)` payoff |
| Cmon | convexity over 4-block windows: `max(Σ of 4 blocks' F, 0)` spread over the 20 sessions |
| Cdyn | convex only while overweighted: the candidate holds a rotating top-5 per category (re-drawn every 21 sessions at random), and a held asset carries `g · max(F_w, 0)` during the periods it is held |

All convex payoffs are non-anticipating: they are paid in the block whose factor they read.

**Pass thresholds (all required):**

| Book | Pass |
|---|---|
| S | SURVIVES in ≥ 90% of seeds, and MARKET EXPOSURE or EXPOSURE-LIKE in ≤ 5% |
| T | neither SURVIVES nor UNDERPOWERED in ≥ 95% of seeds; median \|s − s\*\| ≤ 0.10 |
| every convex book | SURVIVES or UNDERPOWERED in ≤ 10% of seeds |
| C, to establish exposure | median \|s\| ≤ 0.10. If this fails, the control may fail to certify but never files an objection |

- **If S, T or C fails, nothing runs on market data.** The gap stays open, and the finding says
  so.
- **If a held-out convex book fails**, the control runs, but every SURVIVES is scoped to exclude
  that shape, named in the finding.

**Product scale** (CEFS-sized: 423 blocks, windows 104/52, tracking error 9%/yr, active
5.4%/yr, 200 seeds from 2000):
- pure alpha must read MARKET EXPOSURE or EXPOSURE-LIKE in ≤ 5% of seeds;
- pure convex must read SURVIVES or UNDERPOWERED in ≤ 10%.

Otherwise CEFS and MDCEX are **NOT RUN**: the caveat stays open and no objection is filed. The
reviewer expects NOT RUN.

## Market data (only for what passes calibration)

- **H404702:** an exact replay (5245a64f#3, 86834435#0), with reproduction, book-identity and
  gate-invariance checks for every live registration, as F366205.
- **CEFS, MDCEX:** recorded series; only if the product calibration passes.
- **Planted positive control, on each candidate's own data** (O4 caveat 3).
  - A convex payoff the size of the candidate's raw active is injected into its actual
    overweights, in two forms:
    - static: every asset that is ever overweighted carries it always;
    - selection-conditional: it carries it only while overweighted.
  - The control must attribute ≥ 75% of each planted payoff to E (the rise in E against the
    planted mean). If it does not, the candidate's reading cannot certify, and reads
    INCONCLUSIVE.
- **The F366204 tilt** is reported but not gated on: it has no known answer.
- **Per-category Treynor-Mazuy:** dropped.

## Consequences (stated now)

- **MARKET EXPOSURE or EXPOSURE-LIKE**, with C's median-|s| condition met: an objection is filed
  (against H404702; against a CEFS registration on its registration day). It names the convex
  share. A board other than this protocol's author resolves it.
- **SURVIVES:** F366207's convexity caveat closes for that candidate, scoped to exclude any
  held-out shape that failed calibration. This is not a validation; the forward stage governs.
- **INCONCLUSIVE, UNDERPOWERED or NOT RUN:** the caveat stays open, and the finding records it.

## Review record (2026-10-09; statistics and adversary, one reviewer who explored seeds 0-99)

| Amendment | Status |
|---|---|
| Drop the lagged convex terms (the draft failed its own C gate, 13/100) | adopted |
| Loading-estimation error in t: a bootstrap | adopted |
| Held-out books (Cglob, Cday, Cmon, Cdyn) on fresh seeds 1000-1099 | adopted |
| State-conditional loadings (Cdyn read SURVIVES 100/100 under state-free loadings) | adopted |
| Product-scale calibration gate; the reviewer expects NOT RUN | adopted |
| Thresholds: S exposure ≤ 5%, T median error ≤ 0.10, C median \|s\| ≤ 0.10 to establish exposure | adopted |
| Planted positive control on the candidate's own data; the F366204 tilt not gated | adopted |
| One downgrade regression | adopted |
| Block-start Δ for the convex terms; non-anticipating payoffs | adopted (suggested) |
| A frozen \|·\|/2 convex split; per-category Treynor-Mazuy dropped | adopted (suggested) |

## Result (2026-10-09): calibration partly passes; H404702 INCONCLUSIVE; products NOT RUN

**Calibration** (`docs/research/data/convexity_calibration.json`, sha256 010b14cf…; fresh seeds
1000-1099, bootstrap B 199):

| Book | Certified (SURVIVES or UNDERPOWERED) | Exposure labels | Pass |
|---|---|---|---|
| S, selection | 97% (SURVIVES 93%) | 0% | **pass** |
| T, timed beta s\* 0.26 | 0% (median \|s − s\*\| 0.066) | 20% | **pass** |
| C, block convexity | 3% | 71% (median \|s\| 0.21) | **pass**, but cannot establish exposure (0.21 > 0.10) |
| Cglob | 2% | 79% | **pass** |
| Cdyn, convex only while overweighted (the CEF rebound mechanism) | 8% | 61% | **pass**: the state-conditional loadings catch it |
| Cday, daily convexity | 87% | 2% | **FAIL**: the SURVIVES scope excludes it |
| Cmon, 4-block convexity | 78% | 4% | **FAIL**: the SURVIVES scope excludes it |
| Product scale, pure alpha | n/a | 15% (needs ≤ 5%) | **FAIL** |
| Product scale, pure convex | 28% (needs ≤ 10%) | n/a | **FAIL** |

So **CEFS and MDCEX are NOT RUN**, as the reviewer expected: at their scale no tested design
separates alpha from convexity.

**H404702** (`docs/research/data/convexity_control.json`, sha256 86cd3468…). The exact replays
reproduced with identical returns shas, and the gate inputs of H404701 and H404702 were
unchanged.
- **The statistic:** raw active +2.19%/yr; beta-and-convexity-hedged α +0.45%/yr; explained
  +1.74%/yr, of which **convex +1.58%/yr**.
  - s 0.21, t_α 1.09, t_E 4.74.
  - The downgrade regression found no convexity left in the residual (max(B,0) t −1.19,
    max(D,0) t 1.21).
  - The statistic alone reads MARKET EXPOSURE.
- **Planted positive controls** (each the size of the raw active, injected into H404702's own
  overweights):
  - selection-conditional: 0.85 attributed (**pass**);
  - static: **0.743** attributed (needs ≥ 0.75: **fail**).
- **The verdict by the frozen rules is INCONCLUSIVE.** Book C's median |s| exceeds 0.10, so the
  control may not establish exposure. And the static planted control falls short, so it may not
  certify either. **No objection is filed. F366207's convexity caveat stays open.**
- **The F366204 tilt** (reported, not gated): EXPOSURE-LIKE (s 0.11); the downgrade finds global
  convexity at t 3.24.

**Reading.**
- The control attributes most of H404702's active to a **state-conditional call-like
  response**: while a fund is overweighted (cheap), it responds more to its category's up
  blocks than to its down blocks.
  - That is the discount-closing-in-rallies mechanism.
  - It is also consistent with F404724's crash resilience: a convex profile loses less than
    linear beta in drops.
- **It is not certified as market-independent selection, and it is not established as
  exposure.**
- **For a low-drawdown product,** a convex profile obtained without a premium is benign: it
  adds no drawdown. **For "selection" certification,** it means the edge is concentrated in
  large category moves.
- The forward stage governs.

**Disclosure.**
- The first market-data run (exact replays TR-20261009T104404Z, 104409Z, 111103Z and 111106Z,
  recorded) annualised the planted payoff by the per-block factor. That understated it fivefold,
  and its attributed shares (3.7, 4.2) are void.
- The fix (commit 10d5eae) changed only that line and its test. The clean rerun reproduced the
  main statistic exactly (seeded bootstrap).
