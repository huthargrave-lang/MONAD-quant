# How the blade geometry was optimised for 0.5-1.0 m/s streams

**What this document is.** A self-contained account of the blade optimisation behind the v4 low-flow design (and the v5 simplified
prototype, which uses the same blade): the objective, the physics at this scale, the airfoil data, the design method, the search, the
selection, and how sure we are. Every number is written by `docs/make_blade_doc_v4.py` from the model's result files. Nothing has been
measured: all of it is prediction from an engineering model (blade-element momentum theory with surrogate airfoil polars, coupled to the
CubeMars GL60 KV25 generator and a buck-boost MPPT converter).

**The result in one paragraph.** 3 blades, NACA 4412 section blending to NACA 4418 over the inner 35 % of the span, designed at tip-speed
ratio 1.5 with a pitch offset of -3 deg, chord 50.1 mm at the 28 mm hub rising to 60.0 mm and tapering to 31.1 mm at the 101.6 mm tip, twist
32.7 deg at the root to 10.6 deg at the tip, solidity 0.41. It is a wide-chord, low-design-TSR rotor: that is what the objective
(net electrical energy with this generator at 0.5-1.0 m/s, counted as zero where the rotor cannot start itself) rewards, because wide
chords raise the Reynolds number and the starting torque at these speeds, while the actual Cp peak still sits at TSR 2.6.
Predicted net output 0.16 / 0.49 / 0.96 / 1.60 / 3.45 W at 0.5 / 0.6 / 0.7 / 0.8 / 1.0 m/s; self-start from 0.6 m/s (0.4-0.8 across the
optimistic-pessimistic bounds), sustained rotation from 0.5 m/s once spun.

## 1. What "optimised" means here

The brief asked for maximum usable electrical energy, not maximum rotor power coefficient. So the objective is the net 12 V output of
the whole chain (rotor -> seal and bearing friction -> GL60 -> three-phase bridge -> buck-boost MPPT), summed over the flow speeds with
two weightings:

- **J_uniform** = mean of P_net over 0.5, 0.6, 0.7, 0.8, 0.9, 1.0 m/s;
- **J_low-flow** = weighted sum with weights 0.5: 0.30, 0.6: 0.30, 0.7: 0.20, 0.8: 0.10, 0.9: 0.05, 1.0: 0.05 (an illustrative emphasis on 0.5-0.8 m/s; not a measured duty cycle).

P_net is counted as **zero** at a speed where the candidate (i) cannot start from rest against the generator's cogging plus the seal and
bearing breakaway, (ii) cannot keep turning along its unloaded path to the operating point, or (iii) would put less than 5 V on the bus
(the converter's input floor). The self-start gate uses the BEM torque at TSR 0.1 with induction (the first draft's no-induction
flat-plate estimate was 1.8x too high and is kept only as an upper bound). The final pick maximises the mean of the two normalised
objectives subject to a packaging rule (printable hub walls between blade pockets), ties going to lower solidity.

## 2. The flow regime, and why it drives the shape

| V (m/s) | hydraulic power in the 203.2 mm disc (W) | annulus outside the 28 mm hub (W) | Betz limit on the annulus (W) | chord Reynolds number at 30 % / 70 % span (operating point) | peak Cp of the selected blade |
|---|---|---|---|---|---|
| 0.5 | 2.03 | 1.87 | 1.11 | 5.1e+04 / 6.5e+04 | 0.255 |
| 0.6 | 3.50 | 3.24 | 1.92 | 5.9e+04 / 7.6e+04 | 0.278 |
| 0.7 | 5.56 | 5.14 | 3.05 | 7.2e+04 / 9.2e+04 | 0.296 |
| 0.8 | 8.30 | 7.67 | 4.55 | 8.4e+04 / 1.1e+05 | 0.309 |
| 1.0 | 16.21 | 14.98 | 8.88 | 1.1e+05 / 1.4e+05 | 0.327 |

Three things follow from these numbers.

1. **There is very little power to start with** (2.0 W in the whole disc at 0.5 m/s). Every fixed loss matters: the seal and bearing
   friction (about 7 mN m) and the converter's own overhead (about 0.13 W) are each a large fraction of what is available. That is why the
   objective is the net electrical output and not Cp.
2. **The chord Reynolds number is 5e+04 to 1e+05** across the span and the speed range (lower still at the tip taper and at the
   root at 0.5 m/s). Around 4e4-8e4 conventional sections lose most of their lift-to-drag ratio to laminar separation: NACA 4412 has
   L/D 10 at Re 4e4, 49 at Re 8e4 and 79 at Re 2e5. At a given flow speed the only lever on Re is the chord, so a wide
   chord is worth more here than the textbook high-TSR, narrow-blade shape of a large turbine.
3. **Starting matters as much as running.** The GL60's cogging torque (assumed 24 mN m) plus seal and bearing breakaway must be overcome by the
   rotor at rest, where lift is poor and the torque is roughly proportional to solidity. A rotor that only runs well once spun
   scores zero at the low speeds unless it is hand-started.

## 3. Airfoil data: surrogate polars with their confidence

Polars come from NeuralFoil (an XFOIL surrogate) on the UIUC coordinates, at angles -10 to +18 deg and Reynolds numbers 2e4 to 5e5,
extended past stall with the Viterna method, with the surrogate's own confidence recorded. Sections that the surrogate is not confident
about were excluded from the search rather than used.

| section | t/c | best L/D at Re 2e4 | Re 4e4 | Re 8e4 | Re 2e5 | surrogate confidence | in the search | note |
|---|---|---|---|---|---|---|---|---|
| naca4412 | 12 % | 5 at 7 deg (cl 0.44) | 10 at 11 deg (cl 1.01) | 49 at 9 deg (cl 1.33) | 79 at 7 deg (cl 1.20) | 0.98 | yes | baseline family of the original 1-2 m/s blade |
| naca4415 | 15 % | 4 at 11 deg (cl 0.59) | 5 at 8 deg (cl 0.54) | 42 at 10 deg (cl 1.40) | 73 at 7 deg (cl 1.21) | 0.98 | yes | thicker baseline family (root blend) |
| naca4418 | 18 % | 4 at 18 deg (cl 0.83) | 4 at 12 deg (cl 0.64) | 29 at 11 deg (cl 1.33) | 68 at 8 deg (cl 1.28) | 0.97 | yes | root section |
| sg6043 | 10 % | 7 at 5 deg (cl 0.51) | 28 at 10 deg (cl 1.48) | 56 at 8 deg (cl 1.42) | 99 at 5 deg (cl 1.26) | 0.92 | yes | Selig/Giguere low-Re high-lift small-wind-turbine section |
| e387 | 9 % | 7 at 6 deg (cl 0.47) | 23 at 9 deg (cl 1.12) | 51 at 7 deg (cl 1.12) | 83 at 6 deg (cl 1.05) | 0.84 | no | Eppler low-Re glider section, widely measured at Re 6e4-3e5 |
| fx63137 | 14 % | 6 at 5 deg (cl 0.52) | 7 at 6 deg (cl 0.73) | 49 at 9 deg (cl 1.68) | 88 at 6 deg (cl 1.51) | 0.96 | yes | Wortmann high-camber low-Re section |
| e818 | 12 % | 15 at 7 deg (cl 0.86) | 21 at 6 deg (cl 0.87) | 30 at 5 deg (cl 0.79) | 47 at 3 deg (cl 0.64) | 0.64 | no | Eppler hydrofoil requested by the brief: database coordinates are coarse (67 pts), surrogate confidence low |

The Eppler E818 asked for in the brief is listed but was not usable: the database coordinates are coarse and the surrogate confidence
(0.64) is far below the others; its polars would have been guesses. Figure 1 shows the tables.

## 4. Design method: from airfoil polar to blade shape

For each candidate (blade count B, section, design TSR, chord scale, pitch offset) the blade is generated the same way:

- **Chord (Schmitz planform).** At each radius the chord is the one that makes the section work at its best-L/D lift coefficient at the
  design TSR and the local Reynolds number, for the chosen blade count. The chord scale multiplies it (0.7 / 1.0 / 1.3 / 1.5), the chord
  is capped at 60 mm (print bed and hub packaging), eased to 85 % at the hub, and tapered elliptically to 55 % at the tip.
- **Twist.** The section's best-L/D angle at the local Reynolds number plus the inflow angle at the design TSR, plus a global pitch offset
  (-3 / 0 / +3 deg) that trades starting torque against running efficiency.
- **Root blend.** The outer section blends into NACA 4418 over the inner 35 % of span for printability and root bending; the loss of L/D
  there is in the polars, not ignored.
- **Evaluation.** Vectorised blade-element momentum theory (Prandtl tip and hub losses, Buhl high-induction correction, a 15 % inflow
  deficit inboard of r 38 mm behind the nacelle) gives Cp(TSR) and the torque curve at each flow speed; the generator model (V_oc = rpm / KV,
  I^2 R, commutation overlap, no-load loss) and the converter model (efficiency curve, 5 V floor, overhead) give the net output at the
  MPPT equilibrium; the starting torque is the BEM torque at TSR 0.1 against cogging + breakaway.

Figure 2 shows the Cp-TSR curves of the selected blade against the earlier designs; Figures 3 and 4 show the chord and twist.

## 5. The search

**Stage 1** (384 candidates): B = 2 / 3 / 4 / 5 x four sections (NACA 4412, NACA 4415, SG6043, FX63-137) x design TSR 1.5 / 2 / 2.5 / 3 / 3.5 / 4 / 5 / 6 x
chord scale 0.7 / 1.0 / 1.3, evaluated at 0.4-1.0 m/s with 40 blade elements.
**Stage 2** (124 candidates): refinements around the leaders (B = 3 / 4 / 5 x TSR 1.5 / 1.75 / 2 / 2.5 x chord scale 1.0 / 1.3 / 1.5 x pitch -3 / 0 / +3 deg,
plus two-blade and SG6043 checks).

Best candidate per blade count, per section, per design TSR (3 blades, NACA 4412) and per chord scale (3 blades, NACA 4412, TSR 1.5):

| group | B | airfoil | TSR_d | chord x | pitch | solidity | root / max chord (mm) | Cp peak 0.5 / 0.7 / 1.0 | net W 0.5 / 0.7 / 1.0 | J_uniform | J_low-flow | self-start (m/s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 blades | 2 | naca4412 | 2.0 | 1.3 | +0 | 0.32 | 68 / 68 | 0.255 / 0.290 / 0.312 | 0.17 / 0.96 / 3.45 | 1.403 | 0.645 | 0.7 |
| 3 blades | 3 | naca4412 | 1.75 | 1.3 | +0 | 0.43 | 57 / 60 | 0.258 / 0.299 / 0.328 | 0.17 / 0.97 / 3.48 | 1.506 | 0.803 | 0.6 |
| 4 blades | 4 | naca4412 | 1.5 | 1.3 | -3 | 0.53 | 49 / 58 | 0.262 / 0.304 / 0.335 | 0.17 / 0.98 / 3.50 | 1.511 | 0.807 | 0.6 |
| 5 blades | 5 | naca4412 | 1.5 | 1.3 | -3 | 0.57 | 42 / 50 | 0.242 / 0.292 / 0.330 | 0.13 / 0.92 / 3.39 | 1.473 | 0.808 | 0.5 |
| naca4412 | 4 | naca4412 | 1.5 | 1.3 | -3 | 0.53 | 49 / 58 | 0.262 / 0.304 / 0.335 | 0.17 / 0.98 / 3.50 | 1.511 | 0.807 | 0.6 |
| naca4415 | 3 | naca4415 | 2.0 | 1.3 | +0 | 0.36 | 49 / 57 | 0.185 / 0.274 / 0.326 | 0.05 / 0.90 / 3.59 | 1.431 | 0.644 | 0.7 |
| sg6043 | 5 | sg6043 | 2.5 | 0.7 | +0 | 0.35 | 26 / 36 | 0.249 / 0.272 / 0.306 | 0.15 / 0.86 / 3.17 | 1.356 | 0.716 | 0.6 |
| fx63137 | 3 | fx63137 | 1.5 | 1.3 | +0 | 0.41 | 51 / 60 | 0.222 / 0.263 / 0.304 | 0.09 / 0.83 / 3.19 | 1.340 | 0.697 | 0.6 |
| TSR_d 1.5 | 3 | naca4412 | 1.5 | 1.3 | +0 | 0.43 | 60 / 60 | 0.240 / 0.282 / 0.314 | 0.12 / 0.88 / 3.13 | 1.356 | 0.726 | 0.6 |
| TSR_d 2.0 | 3 | naca4412 | 2.0 | 1.3 | +0 | 0.39 | 50 / 58 | 0.251 / 0.297 / 0.329 | 0.16 / 0.98 / 3.61 | 1.463 | 0.669 | 0.7 |
| TSR_d 2.5 | 3 | naca4412 | 2.5 | 1.0 | +0 | 0.28 | 30 / 41 | 0.211 / 0.265 / 0.310 | 0.09 / 0.87 / 3.46 | 1.227 | 0.444 | 0.8 |
| TSR_d 3.0 | 3 | naca4412 | 3.0 | 1.3 | +0 | 0.39 | 38 / 60 | 0.230 / 0.269 / 0.293 | 0.13 / 0.87 / 3.20 | 1.148 | 0.417 | 0.8 |
| TSR_d 3.5 | 3 | naca4412 | 3.5 | 1.3 | +0 | 0.38 | 54 / 60 | 0.210 / 0.258 / 0.288 | 0.10 / 0.83 / 3.10 | 0.877 | 0.263 | 0.9 |
| TSR_d 4.0 | 3 | naca4412 | 4.0 | 1.3 | +0 | 0.35 | 55 / 60 | 0.181 / 0.246 / 0.282 | 0.06 / 0.78 / 3.04 | 0.507 | 0.152 | 1.0 |
| TSR_d 5.0 | 3 | naca4412 | 5.0 | 0.7 | +0 | 0.13 | 23 / 27 | 0.096 / 0.108 / 0.215 | 0.00 / 0.15 / 2.36 | 0.000 | 0.000 | None |
| TSR_d 6.0 | 3 | naca4412 | 6.0 | 0.7 | +0 | 0.10 | 17 / 19 | 0.065 / 0.068 / 0.137 | 0.00 / 0.00 / 1.29 | 0.000 | 0.000 | None |
| chord x0.7 | 3 | naca4412 | 1.5 | 0.7 | +0 | 0.29 | 35 / 43 | 0.167 / 0.230 / 0.278 | 0.02 / 0.70 / 2.82 | 1.167 | 0.594 | 0.6 |
| chord x1.0 | 3 | naca4412 | 1.5 | 1.0 | +0 | 0.41 | 50 / 60 | 0.236 / 0.279 / 0.313 | 0.12 / 0.88 / 3.13 | 1.351 | 0.720 | 0.6 |
| chord x1.3 | 3 | naca4412 | 1.5 | 1.3 | +0 | 0.43 | 60 / 60 | 0.240 / 0.282 / 0.314 | 0.12 / 0.88 / 3.13 | 1.356 | 0.726 | 0.6 |

What the table says:

- **Design TSR.** Everything at design TSR 3 and above starts late or not at all at 0.5-0.6 m/s and scores lower: the narrow chords
  of a high-TSR planform drop the Reynolds number and the starting torque. The best designs sit at TSR 1.5-2.5, yet they still run
  at TSR 2.8-3.1 at the MPPT point because the Cp peak of a wide-chord blade is broad.
- **Section.** NACA 4412 wins in the coupled result even though SG6043 and FX63-137 have better two-dimensional L/D: their higher
  design lift coefficient produces narrower chords (lower Re) and a sharper Cp peak, which the fixed-speed-ratio generator load
  does not sit on.
- **Blade count.** Two blades give the best Cp per unit solidity but start last; four and five start earliest but lose Cp to profile
  drag. Three is the compromise, and the margins are a few percent.
- **Chord scale.** Wider is better up to the 60 mm cap; beyond the cap the scale only widens the root, which the hub cannot take.

The eight best stage-2 candidates lie within 1.5 % of each other on J_uniform:

| group | B | airfoil | TSR_d | chord x | pitch | solidity | root / max chord (mm) | Cp peak 0.5 / 0.7 / 1.0 | net W 0.5 / 0.7 / 1.0 | J_uniform | J_low-flow | self-start (m/s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stage-2 #1 | 4 | naca4412 | 1.5 | 1.3 | -3 | 0.53 | 49 / 58 | 0.262 / 0.304 / 0.335 | 0.17 / 0.98 / 3.50 | 1.511 | 0.807 | 0.6 |
| stage-2 #2 | 3 | naca4412 | 1.75 | 1.3 | +0 | 0.43 | 57 / 60 | 0.258 / 0.299 / 0.328 | 0.17 / 0.97 / 3.48 | 1.506 | 0.803 | 0.6 |
| stage-2 #3 | 3 | naca4412 | 1.75 | 1.5 | +0 | 0.43 | 60 / 60 | 0.259 / 0.300 / 0.327 | 0.17 / 0.97 / 3.48 | 1.503 | 0.803 | 0.6 |
| stage-2 #4 | 4 | naca4412 | 1.5 | 1.5 | -3 | 0.58 | 56 / 60 | 0.265 / 0.306 / 0.334 | 0.17 / 0.98 / 3.47 | 1.503 | 0.806 | 0.6 |
| stage-2 #5 | 3 | naca4412 | 2.0 | 1.5 | +3 | 0.43 | 58 / 60 | 0.258 / 0.299 / 0.327 | 0.17 / 0.97 / 3.47 | 1.499 | 0.800 | 0.6 |
| stage-2 #6 | 3 | naca4412 | 1.5 | 1.0 | -3 | 0.41 | 50 / 60 | 0.256 / 0.296 / 0.327 | 0.16 / 0.96 / 3.46 | 1.492 | 0.794 | 0.6 |
| stage-2 #7 | 3 | naca4412 | 2.0 | 1.3 | +3 | 0.39 | 50 / 58 | 0.248 / 0.293 / 0.325 | 0.16 / 0.95 / 3.47 | 1.490 | 0.790 | 0.6 |
| stage-2 #8 | 4 | naca4412 | 1.75 | 1.5 | +0 | 0.55 | 50 / 60 | 0.259 / 0.301 / 0.331 | 0.16 / 0.97 / 3.44 | 1.488 | 0.796 | 0.6 |

## 6. Selection and why the winner won

Rule (`model/selection.json`): max 0.5*J_uniform/max + 0.5*J_lowflow/max (J gated by the induction-on starting torque, sustain and the 5 V converter floor) subject to hub wall >= 12 deg between pockets; ties to lower solidity.

The hub-wall rule exists because the v4 hub holds the blades in printed pockets; the v5 one-piece rotor does not need it, but the
same blade is kept because the candidates it excluded were within 1.3 % on J_uniform and 2.6 % on J_low-flow of the
unconstrained best (4 blades, NACA 4412, design TSR 1.5, chord x1.3, pitch -3 deg): inside the model's uncertainty.

Selected: 3 blades, NACA 4412, design TSR 1.5, chord x1.0, pitch -3 deg. Score 0.9808 against 0.9779 for the runner-up
(3 blades, NACA 4412, design TSR 2.0, chord x1.3, pitch +3 deg). The best candidate if the rotor is always hand-started (no self-start gate) is
3 blades, NACA 4412, design TSR 2.0, chord x1.3, pitch +0 deg: the same family with a wider chord.

It won because it (i) self-starts from 0.6 m/s under the baseline starting-torque model (at 0.5 m/s it makes 29 mN m against
36 mN m of breakaway; a start at 0.5 / 0.6 / 0.7 m/s needs the measured cogging below 17 / 30 / 45 mN m), (ii) has the highest net
output at 0.5-0.7 m/s once turning, (iii) stays within 4 % of the original 1-2 m/s rev-2 blade at 0.8-1.0 m/s, and (iv) fits three
pockets on a 28 mm hub. Against the previous designs at identical conditions (Figure 5):

| V (m/s) | selected blade: Cp peak / net W / self-start | original rev-2 blade on the same hub: Cp / W / start | v3.1 blade in its 48 mm drum: Cp / W / start |
|---|---|---|---|
| 0.5 | 0.255 / 0.16 / no | 0.174 / 0.02 / no | 0.181 / 0.00 / no |
| 0.6 | 0.278 / 0.49 / yes | 0.230 / 0.36 / no | 0.202 / 0.18 / no |
| 0.7 | 0.296 / 0.96 / yes | 0.266 / 0.87 / yes | 0.218 / 0.51 / no |
| 0.8 | 0.309 / 1.60 / yes | 0.293 / 1.58 / yes | 0.231 / 0.99 / no |
| 1.0 | 0.327 / 3.45 / yes | 0.322 / 3.61 / yes | 0.248 / 2.44 / yes |
| 1.5 | 0.347 / 12.02 / yes | 0.347 / 13.31 / yes | 0.267 / 9.68 / yes |
| 2.0 | 0.354 / 27.23 / yes | 0.359 / 31.25 / yes | 0.275 / 23.38 / yes |

What it gives up: about 13 % at 2.0 m/s against the rev-2 blade (a 1-2 m/s design), and a higher standstill drag.

**Robustness of the blade-count choice** under the model's main uncertainties (best candidate per blade count; J in W; hand-started = no
self-start gate):

| candidate | baseline J_uniform / J_low-flow (min start) | transition Re / 1.5 | Re x 1.5 | upper-bound starting torque | hand-started |
|---|---|---|---|---|---|
| selected: B3 naca4412 TSR_d 1.5 x1.0 | 1.487 / 0.792 (0.6) | 1.264 / 0.647 (0.6) | 1.625 / 0.887 (0.6) | 1.514 / 0.841 (0.5) | 1.514 / 0.841 |
| best B2: B2 naca4412 TSR_d 2.0 x1.3 | 1.399 / 0.642 (0.7) | 1.238 / 0.557 (0.7) | 1.487 / 0.690 (0.7) | 1.480 / 0.788 (0.6) | 1.508 / 0.838 |
| best B3: B3 naca4412 TSR_d 1.5 x1.0 | 1.487 / 0.792 (0.6) | 1.264 / 0.647 (0.6) | 1.625 / 0.887 (0.6) | 1.514 / 0.841 (0.5) | 1.514 / 0.841 |
| best B4: B4 naca4412 TSR_d 2.5 x1.3 | 1.451 / 0.773 (0.6) | 1.251 / 0.648 (0.6) | 1.598 / 0.867 (0.6) | 1.478 / 0.821 (0.5) | 1.478 / 0.821 |
| best B5: B5 naca4412 TSR_d 2.5 x1.0 | 1.442 / 0.761 (0.6) | 1.200 / 0.608 (0.6) | 1.625 / 0.878 (0.6) | 1.467 / 0.805 (0.5) | 1.467 / 0.805 |

The ordering is stable; the margins are not larger than the uncertainty, so the report does not claim three blades are superior beyond
that margin.

## 7. The selected geometry

Station data (every fifth of the 50 model stations; full table in `model/selected_design.json`; CAD follows it within 0.5 mm / 0.3 deg):

| radius (mm) | chord (mm) | twist from the rotor plane (deg) | NACA 4418 root blend |
|---|---|---|---|
| 28.7 | 50.1 | 32.7 | 94 % |
| 36.1 | 56.5 | 29.7 | 47 % |
| 43.5 | 60.0 | 26.9 | 16 % |
| 50.8 | 60.0 | 24.3 | 1 % |
| 58.2 | 60.0 | 21.9 | 0 % |
| 65.5 | 60.0 | 19.7 | 0 % |
| 72.9 | 57.3 | 17.3 | 0 % |
| 80.3 | 54.3 | 14.9 | 0 % |
| 87.6 | 52.4 | 13.1 | 0 % |
| 95.0 | 48.4 | 11.7 | 0 % |

Tip chord 31.1 mm with a 1.0 mm blunt trailing edge and 3.7 mm maximum thickness (printable); root section 18 % thick (9.0 mm) for bending.
Running point: TSR 2.8-3.1, 129-291 rpm over 0.5-1.0 m/s; 704 rpm and 46 V open-circuit at 2 m/s.

## 8. How sure we are

The one-at-a-time sensitivity study (Figure 6; polar drag +30 / +60 %, transition Reynolds number x 1.5 / 1.5, the high-induction
correction, seal friction x 0.5-3, cogging 8-40 mN m, no-load loss, nacelle inflow factor, generator constants, converter efficiency,
overhead and input floor) spans -39 % / +14 % at 0.7 m/s and -12 % / +8 % at 1.0 m/s around the baseline, and
-100 % / +45 % at 0.5 m/s, where the output is a small difference between hydraulic power and fixed losses. The largest single items are the
transition Reynolds number of a wet printed surface (0.35 vs 0.49 W at 0.6 m/s if transition comes 1.5x earlier) and the cogging torque,
which decides self-start. Combining the pessimistic choices gives 0.12 / 1.08 / 2.75 W at 0.6 / 0.8 / 1.0 m/s and self-start from 0.8 m/s; the optimistic
choices give 0.69 / 1.97 / 4.01 W and 0.4 m/s.

The four measurements that close the model, in order of effect: the GL60's cogging torque and KV convention (bench), the sealed-shaft
friction (bench), the rotor's starting torque at 0.5-0.7 m/s with the shaft locked (flume or tow), and the power curve itself. An
independent reviewer re-derived the BEM, the generator equations and the MPPT equilibria within 1.4 % and found the starting-torque
model and the polar transition behaviour to be the least certain parts; both are carried as bounds above, not as point values.

## 9. Files

`model/polars.py` (polar tables), `model/bem_lowflow.py` (BEM, design generator), `model/generator_lowflow.py` (GL60, friction, converter),
`model/optimize_blades.py` (stages 1-2 and the selection rule), `model/robustness_v4.py`, `model/coupled_eval.py` (final evaluation,
sensitivities, figures); results in `model/sweep_stage1.json`, `sweep_stage2.json`, `selection.json`, `selected_design.json`,
`robustness.json`, `coupled_results.json`. Figures reproduced below: 1 polars, 2 Cp-TSR, 3-4 chord and twist, 5 power vs flow, 6 sensitivity.
