# Objection O4 on H404702: board ruling (2026-10-09)

**Outcome: REFUTED, unanimously.**

- **Procedure:** `docs/research/O4_RESOLUTION_PROTOCOL.md`, frozen before the calibration and
  before the board was convened.
- **The board:** three members with no role in either protocol. Member 3 was assigned to argue
  for upholding.
- **Independence is weak** (the members were spawned by the same orchestrator), as the protocol
  states. The owner may re-open the ruling by filing a new objection.
- **Evidence checks.** Every member verified the pinned sha256 of `beta_timing_control.json`
  (3a8abd4c…). They also confirmed that `beta_control.py`'s verdict path is unchanged since
  aee09f6 (later commits touch only the reporting helper `within_category_part`), and that
  `tools/o4_calibration.py` did not change between its pre-run commit and the result.

## Answers, in the protocol's order

### 1. The text

**All three: the text does not demote H404702 on an INCONCLUSIVE control.**
- The consequence clause names SURVIVES and UNDERPOWERED: the two readings that would falsely
  certify a known-beta book as selection. INCONCLUSIVE certifies nothing.
- "Must read BETA EXPOSURE or BETA-LIKE" states a validity condition with no consequence
  attached. Questions 2 and 3 are what answer it.
- The demotion was the author's gap-fill. It was coded before the result (0840aa7, before
  e5b553a) and disclosed.
- **Upholding case (member 3):** without R2, the control's linear statistics read UNDERPOWERED.
  - The values: s 0.59; shares R0 0.53, R1b 0.47, R4 0.41, R2b 0.87; t_α 1.31.
  - That is the failure the clause names.
  - *Answer:* R2 is part of the frozen method and cannot be dropped to manufacture that reading.

### 2. The control's true answer

**All three: the positive control had no known answer, and its expected label (BETA) was
mis-specified.**
- F366204 labelled the whole tilt "beta timing" using free per-family slopes and a free lag. The
  control protocol's board rejected that set-up, and F366204 itself says reversion and rebound
  "cannot be separated".
- The control's within-family part (H404702's selection, seen again) keeps s 1.02 at t 4.8.
  The method put the beta where F366204 located it, in the category part.
- Timing and convexity are not alternatives. The calibration's pure linear-timing book T is
  flagged convex in 100/100 seeds.
- **The decisive point:** book T, at the protocol's own prior (true kept share 0.26), reads
  INCONCLUSIVE in 99/100 seeds. So even a correct method almost never reads BETA here. The
  requirement was set at a level a working method misses.

### 3. The method on known answers

| Book | Pre-stated pass | Result |
|---|---|---|
| S, pure selection | SURVIVES ≥ 90% | **100/100, pass** |
| T, linear timed beta, s\* 0.26 | never SURVIVES/UNDERPOWERED ≥ 95%; median \|s − s\*\| ≤ 0.10 | **0/100 SURVIVES or UNDERPOWERED; median 0.081, pass** (s biased up about 0.08) |
| C, convex payoff | R2 flags convexity ≥ 90% | **66%, FAIL.** The verdict is SURVIVES in 99/100 |

**What this means for H404702 (member 2's quantification).**
- The method's s, t_α and shares say nothing about convexity; only its own convexity terms do.
- H404702 reads Treynor-Mazuy c −0.035 (t −0.42) and R2b t −0.54: both near zero and of the
  wrong sign for convexity.
- Re-running the calibration's book() and control() in memory at its exact seeds:

  | Synthetic convex share | t_c mean | Seeds at or below −0.42 |
  |---|---|---|
  | full (book C) | 2.42 (sd 1.05) | 0/100; normal tail ≈ 0.35%, about 35:1 against |
  | half | 1.18 | 8% |
  | quarter | 0.54 | 18% |
  | none (book S) | 0.02 | 36% |

- **Result:** a mostly convex alpha is strongly disfavoured. The one-sided 95% upper bound on
  H404702's convex share is about 0.5; the point estimate is 0.
- **Scope:** this mapping holds in the synthetic world. Convexity against factors weakly tied to
  the CEF benchmark, against category factors directly, or against SPY or rates is untested.

## Caveats (required, recorded with the resolution)

1. **The method's SURVIVES does not certify selection against convex payoffs** (book C failed:
   R2 flags 66%, SURVIVES 99%).
   - This must be fixed before the method is relied on again.
   - **CEFS's SURVIVES (F366205) carries the same gap.**
2. **H404702's convexity exclusion rests only on its own t_c (−0.42) and R2b (t −0.54),** mapped
   through synthetic geometry. A convex share up to about 0.5 is not excluded at 95%.
   Category-level convexity is untested, because Treynor-Mazuy runs on the global benchmark only.
3. **The positive control had no known answer.** Any reuse of the protocol must state the
   INCONCLUSIVE consequence explicitly, and use a control with a known answer.
4. **This is not a validation of H404702.**
   - The forward stage still governs. It needs P(Sharpe > 0) ≥ 0.9 over a year, which passes
     only about 40-55% of the time even at the development Sharpe.
   - F404717's 1997-2003 read was +0.39.

## What would close the convexity gap (successor, specified before any run)

A convexity-robust control:
- **Terms:** max(F, 0) payoff terms on each fund's leave-one-out category factor and on the
  global factor, in addition to the linear Dimson exposure.
- **Verdict:** the kept share after the convexity terms must be ≥ 0.5.
- **Calibration first:** at least 90% detection on book C and at least 90% SURVIVES on book S,
  before it is run on H404702, CEFS, or F366204's within-family part.

The owner may file this as a new objection. The board did not vote to file it.

## Dissent

None on the outcome.

The upholding member's strongest case, for the record: the control reads UNDERPOWERED without
R2, and book C failed a threshold fixed in advance. The member concluded that this exposes a
**separate** convexity gap, not the ground O4 was filed on.
