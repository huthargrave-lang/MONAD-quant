# Resolving objection O4 on H404702

Status: **FROZEN** (2026-10-09). Frozen before the calibration below ran, before the resolving
board was convened, and before any H404702 forward data was read. The forward window runs to
2027-10-07, and its weekly log has one line.

## The objection

- O4 (`docs/research/refutations/H404702.jsonl`) was filed mechanically by
  `BETA_TIMING_CONTROL_PROTOCOL.md`.
- H404702's own statistics read SURVIVES:
  - the beta-hedged α keeps 1.03 of +2.19%/yr, at t 7.3;
  - every robustness share is ≥ 0.88;
  - Treynor-Mazuy c has t −0.42.
- It was demoted to INCONCLUSIVE because the positive control (the F366204 tilt) read
  INCONCLUSIVE, not BETA. The control's R2 share was −0.45, with convexity at t 6.3.
- Admission's refutations stage BLOCKs while O4 is open. **Only a board other than the
  protocol's author may resolve it.**

## Why now

A ruling made today cannot be shaped by forward results. A ruling in 2027 would be made with
the forward log already in git (next-step board, 2026-10-09).

## The board

- **Three members with no role in either protocol.** None of them drafted, reviewed or
  amended `BETA_TIMING_CONTROL_PROTOCOL.md` or this file.
- **One member is assigned to argue for upholding O4**, whatever their own view.
- Each member reads the same evidence and answers the three questions in order. The outcome
  is the majority. A dissent is recorded in full.
- **Limit, stated:** the members are agents spawned by the same orchestrator, so their
  independence is weak. The owner may re-open the ruling by filing a new objection.

## The questions, in order

1. **The text.** Does the protocol, as frozen, demote H404702 when the positive control reads
   INCONCLUSIVE?
   - The requirement says the control "must read BETA EXPOSURE or BETA-LIKE". The consequence
     clause names SURVIVES and UNDERPOWERED only.
2. **The control's true answer.** Was the F366204 tilt's active return beta timing that this
   method should have labelled BETA? Or was it a convex payoff, which the method flagged
   through R2 and labels INCONCLUSIVE by design?
   - F366204 labelled it beta timing using fixed match betas, per-family free slopes and a free
     lag. The control protocol's board rejected that set-up, because a free slope can absorb
     the reversion itself.
3. **The method on known answers.** Does the method separate selection from linear timed beta,
   and does R2 flag convex payoffs? This is answered by the calibration below.

## Admissible evidence (pinned)

| Evidence | Pin |
|---|---|
| The control result | `docs/research/data/beta_timing_control.json`, sha256 3a8abd4c7ce8545963ca38918b9db8b419674dd80631ef1c2545eef5610a37fb |
| The two protocols | `BETA_TIMING_CONTROL_PROTOCOL.md` (with its disclosure) and `CEF_ETF_TILT_PROTOCOL.md` |
| The findings | F366204 and F366205 in RESEARCH_WEB.md |
| The control's code and synthetic suite | `src/research/beta_control.py`, `tests/test_beta_control.py` at commit aee09f6 |
| The calibration | `docs/research/data/o4_calibration.json` |

No market data is read for this resolution, and no trial is recorded.

## The calibration (specified before it runs)

- `tools/o4_calibration.py` runs the frozen method (`beta_control`: blocks, Dimson betas,
  g = 1, R0, R1a, R4, R2, R2b, and the verdict) on synthetic books with known answers.
  R1b and R3 need SPY and IEF, which the synthetic world does not have. They are not computed,
  as for the products.
- **The world (each seed).**
  - 5,460 sessions (1,092 blocks, H404702's sample) and 4 categories.
  - Category factors are daily normal with mean 0.0003 and sd 0.008, pairwise correlation 0.5.
  - 10 assets per category, each with a static beta drawn uniform [0.6, 1.4] and an
    idiosyncratic daily normal with sd 0.006.
  - The benchmark is equal weight across all 40 assets.
  - Betas are estimated by the frozen rule (156-block windows, minimum 48). The factor for each
    asset is its category's equal-weight return excluding itself, H404702's primary.
- **Book S, pure selection.**
  - Each asset carries an alpha that is constant within each 21-session period, drawn normal
    with sd σ_a, independent of the factors.
  - The candidate holds, within each category, the 5 assets with the highest current alpha, at
    equal weight, with category weights equal to the benchmark's.
  - σ_a is set so the expected active return is 2.2%/yr.
- **Book T, linear timed beta with a true kept share of 0.26.**
  - The candidate's weights are Book S's selection weights (scaled to 26% of S's expected
    active), plus a timing tilt.
  - The tilt is `k (b_i − b̄_cat) · sign(next block's category factor)`: overweight high beta
    before up blocks.
  - k is set so the timing part is 74% of the expected active.
  - The realised true share s* = selection part / total is computed per seed from the
    components.
- **Book C, convex payoff.**
  - Within each category, half the assets carry `g · max(F_cat, block, 0)` spread over the
    block's sessions, on top of their linear return.
  - The candidate overweights those assets: equal weight within the category, category
    weights equal.
  - g is set so the expected active return is 2.2%/yr.
  - There is no selection alpha.
- **Seeds:** 100 per book, seeded `numpy.random.default_rng(seed)` for seeds 0-99, plus the
  book's index.
- **Pass thresholds (fixed now):**

  | Book | Pass |
  |---|---|
  | S | verdict SURVIVES in ≥ 90% of seeds |
  | T | verdict neither SURVIVES nor UNDERPOWERED in ≥ 95% of seeds, and median \|s − s*\| ≤ 0.10 |
  | C | R2 "convexity detected" in ≥ 90% of seeds; the verdict distribution is reported |

  No threshold is set on Book C's verdict, because the frozen rule takes convexity into account
  only through s_R2.

## Outcomes

- **Refuted.** O4 is resolved `refuted`, with the board's file
  (`docs/research/O4_board_ruling.md`) as evidence. H404702's admission evidence then stands on
  this dimension.
  - That is not a validation of H404702. Its forward stage still needs P(Sharpe > 0) ≥ 0.9
    over a year, which passes only about 40-55% of the time even at its development Sharpe.
- **Upheld.** O4 is resolved `upheld`, and a successor positive control with a known answer
  must be specified before it runs. Admission's refutations stage then REJECTs on this ground
  unless a new protocol supersedes it.

## Ways this could mislead (stated)

- Wanting an admission can bias how the gap in the text is read. That is why one member argues
  for upholding.
- Effect sizes could be tuned so the method passes trivially. They are fixed above, at
  H404702's own active and the prior's s ≈ 0.26.
- A refuted O4 could be read as "H404702 validated". It is not.
