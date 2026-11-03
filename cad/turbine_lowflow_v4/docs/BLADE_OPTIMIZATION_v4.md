# Blade Geometry Optimization for 0.5-1.0 m/s Streams

<p class="sub">8-inch (203.2 mm) hydrokinetic turbine, CubeMars GL60 KV25 generator, v4 blade (used unchanged in the v5 simplified prototype).
Status: model prediction, nothing measured. All numbers are generated from the v4 result files by <code>docs/make_blade_doc_v4.py</code>.</p>

## 1. Result

| Selected blade | |
|---|---|
| Blades, section | 3, NACA 4412 blending to NACA 4418 over the inner 35 % of span |
| Design tip-speed ratio, pitch offset | 1.5, -3 deg |
| Chord: hub / maximum / tip | 50.1 / 60.0 / 31.1 mm |
| Twist: hub / tip (from the rotor plane) | 32.7 / 10.6 deg |
| Solidity | 0.41 |
| Hub / tip radius | 28 / 101.6 mm |
| Predicted net 12 V output at 0.5 / 0.7 / 1.0 m/s | 0.16 / 0.96 / 3.45 W |
| Self-start / sustained rotation from | 0.6 / 0.5 m/s (self-start bounds 0.4-0.8 m/s) |
| Operating TSR and speed, 0.5-1.0 m/s | 2.8-3.1, 129-291 rpm |

The design is a wide-chord, low-design-TSR rotor. At these speeds the chord is the only lever on the Reynolds number and on the
starting torque, and both matter more than the last few points of peak Cp.

## 2. Objective

- **Maximise net electrical energy**, not rotor Cp: the output of the whole chain (rotor, seal and bearing friction, GL60, rectifier,
  buck-boost MPPT) is what the battery sees.
- **Two weightings:** J_uniform (mean over 0.5-1.0 m/s in 0.1 m/s steps) and J_low-flow (weights 0.30 / 0.30 / 0.20 / 0.10 / 0.05 / 0.05
  from 0.5 to 1.0 m/s).
- **Gates:** output counts as zero at a speed where the rotor cannot start against cogging plus breakaway, cannot keep turning
  to its operating point, or puts less than 5 V on the bus. The starting torque is the BEM torque at TSR 0.1 with induction.
- **Selection:** the mean of the two normalised objectives, subject to a printable hub wall between blade pockets; ties go to the
  lower solidity.

## 3. The flow regime

| V (m/s) | power in the disc (W) | Betz limit on the annulus (W) | chord Reynolds number, 30 % / 70 % span | peak Cp of the selected blade |
|---|---|---|---|---|
| 0.5 | 2.03 | 1.11 | 5.1e4 / 6.5e4 | 0.255 |
| 0.6 | 3.50 | 1.92 | 5.9e4 / 7.6e4 | 0.278 |
| 0.7 | 5.56 | 3.05 | 7.2e4 / 9.2e4 | 0.296 |
| 0.8 | 8.30 | 4.55 | 8.4e4 / 1.1e5 | 0.309 |
| 1.0 | 16.21 | 8.88 | 1.1e5 / 1.4e5 | 0.327 |

- **Little power to start with:** 2.0 W in the whole disc at 0.5 m/s. Seal and bearing friction (about 7 mN m) and the converter
  overhead (about 0.13 W) are each a large share of it, so the objective has to be the net output.
- **Low Reynolds numbers:** 5.1e4 to 1.4e5. NACA 4412 has L/D 10 at Re 4e4, 49 at 8e4 and 79 at 2e5. A wide chord
  buys Reynolds number directly.
- **Starting counts:** the GL60's assumed 24 mN m cogging plus 12 mN m of breakaway must be beaten by a rotor at rest, where the torque
  scales with solidity.

## 4. Airfoil data

Polars from NeuralFoil (an XFOIL surrogate) on UIUC coordinates, -10 to +18 deg, Re 2e4-5e5, Viterna post-stall extension. Sections
the surrogate is not confident about were excluded rather than guessed (Figure 1).

| section | t/c | best L/D at Re 4e4 | Re 8e4 | Re 2e5 | surrogate confidence | use |
|---|---|---|---|---|---|---|
| NACA 4412 | 12 % | 10 | 49 | 79 | 0.98 | searched |
| NACA 4415 | 15 % | 5 | 42 | 73 | 0.98 | searched |
| NACA 4418 | 18 % | 4 | 29 | 68 | 0.97 | root blend only |
| SG6043 | 10 % | 28 | 56 | 99 | 0.92 | searched |
| Eppler E387 | 9 % | 23 | 51 | 83 | 0.84 | excluded (low confidence) |
| FX 63-137 | 14 % | 7 | 49 | 88 | 0.96 | searched |
| Eppler E818 | 12 % | 21 | 30 | 47 | 0.64 | excluded (low confidence) |

## 5. Design method

Each candidate (blade count, section, design TSR, chord scale, pitch offset) is built and evaluated the same way:

- **Chord:** Schmitz planform at the design TSR, using each section's best-L/D lift coefficient at the local Reynolds number;
  scaled x0.7-1.5, capped at 60 mm, eased to 85 % at the hub, elliptical taper to 55 % at the tip.
- **Twist:** best-L/D angle at the local Reynolds number plus the design-TSR inflow angle, plus a global pitch offset of -3 / 0 / +3 deg.
- **Root:** blend to NACA 4418 over the inner 35 % of span for printability and bending strength.
- **Rotor model:** blade-element momentum theory with Prandtl tip and hub losses, Buhl high-induction correction, and a 15 % inflow
  deficit inboard of r 38 mm behind the nacelle.
- **Electrical model:** GL60 (V_oc = rpm / KV, copper loss, commutation overlap, no-load loss), three-phase bridge, buck-boost MPPT
  with efficiency curve, overhead and a 5 V floor; the operating point is the MPPT equilibrium.

Figure 2 shows the resulting Cp-TSR curves; Figure 3 the chord and twist against the earlier blades.

## 6. The search

Stage 1: 384 candidates (2-5 blades x 4 sections x design TSR 1.5-6 x chord scale 0.7 / 1.0 / 1.3). Stage 2: 124 refinements around
the leaders (3-5 blades x TSR 1.5-2.5 x chord scale 1.0-1.5 x pitch -3 / 0 / +3 deg, plus two-blade and SG6043 checks).

| group | candidate | solidity | net W at 0.5 / 0.7 / 1.0 m/s | J uniform / low-flow (W) | self-start (m/s) |
|---|---|---|---|---|---|
| 2 blades | 2 blades, NACA 4412, TSR 2.0, chord x1.3, pitch +0 deg | 0.32 | 0.17 / 0.96 / 3.45 | 1.40 / 0.64 | 0.7 |
| 3 blades | 3 blades, NACA 4412, TSR 1.75, chord x1.3, pitch +0 deg | 0.43 | 0.17 / 0.97 / 3.48 | 1.51 / 0.80 | 0.6 |
| 4 blades | 4 blades, NACA 4412, TSR 1.5, chord x1.3, pitch -3 deg | 0.53 | 0.17 / 0.98 / 3.50 | 1.51 / 0.81 | 0.6 |
| 5 blades | 5 blades, NACA 4412, TSR 1.5, chord x1.3, pitch -3 deg | 0.57 | 0.13 / 0.92 / 3.39 | 1.47 / 0.81 | 0.5 |
| NACA 4412 | 4 blades, NACA 4412, TSR 1.5, chord x1.3, pitch -3 deg | 0.53 | 0.17 / 0.98 / 3.50 | 1.51 / 0.81 | 0.6 |
| NACA 4415 | 3 blades, NACA 4415, TSR 2.0, chord x1.3, pitch +0 deg | 0.36 | 0.05 / 0.90 / 3.59 | 1.43 / 0.64 | 0.7 |
| SG6043 | 5 blades, SG6043, TSR 2.5, chord x0.7, pitch +0 deg | 0.35 | 0.15 / 0.86 / 3.17 | 1.36 / 0.72 | 0.6 |
| FX 63-137 | 3 blades, FX 63-137, TSR 1.5, chord x1.3, pitch +0 deg | 0.41 | 0.09 / 0.83 / 3.19 | 1.34 / 0.70 | 0.6 |
| design TSR 1.5 | 3 blades, NACA 4412, TSR 1.5, chord x1.3, pitch +0 deg | 0.43 | 0.12 / 0.88 / 3.13 | 1.36 / 0.73 | 0.6 |
| design TSR 2.0 | 3 blades, NACA 4412, TSR 2.0, chord x1.3, pitch +0 deg | 0.39 | 0.16 / 0.98 / 3.61 | 1.46 / 0.67 | 0.7 |
| design TSR 3.0 | 3 blades, NACA 4412, TSR 3.0, chord x1.3, pitch +0 deg | 0.39 | 0.13 / 0.87 / 3.20 | 1.15 / 0.42 | 0.8 |
| design TSR 4.0 | 3 blades, NACA 4412, TSR 4.0, chord x1.3, pitch +0 deg | 0.35 | 0.06 / 0.78 / 3.04 | 0.51 / 0.15 | 1.0 |
| design TSR 6.0 | 3 blades, NACA 4412, TSR 6.0, chord x0.7, pitch +0 deg | 0.10 | 0.00 / 0.00 / 1.29 | 0.00 / 0.00 | > 1.0 |
| chord x0.7 | 3 blades, NACA 4412, TSR 1.5, chord x0.7, pitch +0 deg | 0.29 | 0.02 / 0.70 / 2.82 | 1.17 / 0.59 | 0.6 |
| chord x1.0 | 3 blades, NACA 4412, TSR 1.5, chord x1.0, pitch +0 deg | 0.41 | 0.12 / 0.88 / 3.13 | 1.35 / 0.72 | 0.6 |
| chord x1.3 | 3 blades, NACA 4412, TSR 1.5, chord x1.3, pitch +0 deg | 0.43 | 0.12 / 0.88 / 3.13 | 1.36 / 0.73 | 0.6 |

- **Design TSR 1.5-2.5 wins.** Designs at TSR 3 and above start late or not at all: narrow chords mean low Reynolds number and low
  starting torque. The winner still runs at TSR 2.8-3.1 because its Cp peak (TSR 2.6) is broad.
- **NACA 4412 beats the higher-lift sections** in the coupled result: SG6043 and FX 63-137 have better two-dimensional L/D, but their higher
  design lift coefficient gives narrower chords and a sharper Cp peak.
- **Three blades** balance the two-blade Cp advantage against the four- and five-blade starting advantage; the margins are a few percent.
- **Wider chord helps up to the 60 mm cap.**

## 7. Selection

| candidate | J uniform / low-flow (W) | self-start (m/s) | note |
|---|---|---|---|
| **Selected:** 3 blades, NACA 4412, TSR 1.5, chord x1.0, pitch -3 deg | 1.492 / 0.794 | 0.6 | score 0.9808 |
| Runner-up: 3 blades, NACA 4412, TSR 2.0, chord x1.3, pitch +3 deg | 1.490 / 0.790 | 0.6 | score 0.9779 |
| Unconstrained best: 4 blades, NACA 4412, TSR 1.5, chord x1.3, pitch -3 deg | 1.511 / 0.807 | - | fails the hub-wall rule; 1.3 % better on J uniform |
| Hand-started best: 3 blades, NACA 4412, TSR 2.0, chord x1.3, pitch +0 deg | 1.573 / 0.867 (no start gate) | 0.7 | same family, wider chord |

Why the selected blade won:

- It self-starts from 0.6 m/s under the baseline model: at 0.5 m/s it makes 29 mN m against 36 mN m of breakaway; a start at
  0.5 / 0.6 / 0.7 m/s needs measured cogging below 17 / 30 / 45 mN m.
- It has the highest net output at 0.5-0.7 m/s once turning (Reynolds effect of the wide chord).
- It stays within 4 % of the original 1-2 m/s blade at 0.8-1.0 m/s and gives up 13 % at 2.0 m/s.
- The eight best stage-2 candidates lie within 1.5 % of each other, so the packaging rule decided among near-equals.

Robustness of the blade-count choice (best candidate per count; J uniform in W, self-start speed in brackets):

| candidate | baseline | transition Re / 1.5 | Re x 1.5 | upper-bound starting torque | hand-started |
|---|---|---|---|---|---|
| 2 blades, NACA 4412, TSR 2.0, chord x1.3, pitch +0 deg | 1.40 (0.7) | 1.24 (0.7) | 1.49 (0.7) | 1.48 (0.6) | 1.51 |
| 3 blades, NACA 4412, TSR 1.5, chord x1.0, pitch -3 deg | 1.49 (0.6) | 1.26 (0.6) | 1.63 (0.6) | 1.51 (0.5) | 1.51 |
| 4 blades, NACA 4412, TSR 2.5, chord x1.3, pitch +3 deg | 1.45 (0.6) | 1.25 (0.6) | 1.60 (0.6) | 1.48 (0.5) | 1.48 |
| 5 blades, NACA 4412, TSR 2.5, chord x1.0, pitch +3 deg | 1.44 (0.6) | 1.20 (0.6) | 1.63 (0.6) | 1.47 (0.5) | 1.47 |

The ordering is stable; the margins are inside the model uncertainty, so no claim is made that three blades are superior beyond that.

## 8. Comparison with the previous blades

| V (m/s) | selected: Cp peak / net W / self-start | original rev-2 blade on the same hub | v3.1 blade in its 48 mm drum |
|---|---|---|---|
| 0.5 | 0.255 / 0.16 / no | 0.174 / 0.02 / no | 0.181 / 0.00 / no |
| 0.6 | 0.278 / 0.49 / yes | 0.230 / 0.36 / no | 0.202 / 0.18 / no |
| 0.7 | 0.296 / 0.96 / yes | 0.266 / 0.87 / yes | 0.218 / 0.51 / no |
| 0.8 | 0.309 / 1.60 / yes | 0.293 / 1.58 / yes | 0.231 / 0.99 / no |
| 1.0 | 0.327 / 3.45 / yes | 0.322 / 3.61 / yes | 0.248 / 2.44 / yes |
| 1.5 | 0.347 / 12.02 / yes | 0.347 / 13.31 / yes | 0.267 / 9.68 / yes |
| 2.0 | 0.354 / 27.23 / yes | 0.359 / 31.25 / yes | 0.275 / 23.38 / yes |

Figure 4 plots the net output against flow speed.

## 9. Selected geometry

Every fifth of the 50 model stations (full table in `model/selected_design.json`; the CAD follows it within 0.5 mm and 0.3 deg).

| radius (mm) | chord (mm) | twist (deg) | NACA 4418 blend |
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

Tip: 31.1 mm chord, 1.0 mm blunt trailing edge, 3.7 mm maximum thickness. Root: 18 % thick (9.0 mm).
At 2 m/s: 704 rpm, 46 V open-circuit.

## 10. Uncertainty

- One-at-a-time sensitivities (polar drag, transition Reynolds number, induction model, friction, cogging, no-load loss, inflow
  factor, generator constants, converter) span -39 / +14 % at 0.7 m/s and -12 / +8 % at 1.0 m/s (Figure 5).
- Largest items: the transition Reynolds number of a wet printed surface (0.35 vs 0.49 W at 0.6 m/s if it comes 1.5x
  earlier) and the cogging torque, which decides self-start.
- Bounds: pessimistic 0.12 / 2.75 W at 0.6 / 1.0 m/s and self-start from 0.8 m/s; optimistic 0.69 / 4.01 W and 0.4 m/s.
- To close the model, measure in this order: GL60 cogging and KV convention, sealed-shaft friction, rotor starting torque at
  0.5-0.7 m/s (shaft locked), the power curve.

## 11. Source files

`model/polars.py`, `bem_lowflow.py`, `generator_lowflow.py`, `optimize_blades.py` (stages 1-2, selection), `robustness_v4.py`,
`coupled_eval.py`; results in `model/sweep_stage1.json`, `sweep_stage2.json`, `selection.json`, `selected_design.json`,
`robustness.json`, `coupled_results.json`.
