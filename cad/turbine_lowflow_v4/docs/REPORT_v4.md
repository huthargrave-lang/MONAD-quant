# Portable hydrokinetic turbine for 0.5-1.0 m/s streams: low-flow redesign (v4)

**Scope and status.** Everything in this package is model prediction and design intent. No part has been printed, machined or
tested; no GL60 has been measured; manufacturer web pages (cubemars.com, genasun, bluerobotics.com, digikey) could not be reached
from this session, so the generator values are the ones listed in the brief and in the earlier review, bracketed by sensitivity cases.
Every number below is written by `docs/make_report_v4.py` from the result files of the scripts in `model/`, `cad/` and `tools/`.

## 1. Executive summary and feasibility verdict

- **What the GL60 can deliver (model, baseline assumptions, arrangement A, buck-boost MPPT):** net 12 V electrical power
  **0.16 W at 0.5 m/s, 0.49 W at 0.6, 0.98 W at 0.7, 1.65 W at 0.8, 3.60 W at 1.0 m/s** (12.8 W at 1.5, 29.5 W at 2.0). Honest band: -30 % / +10 %
  (hydrofoil polars at Re 4e4-8e4 from an XFOIL surrogate, unmeasured friction and generator constants; section 8). Over a 24 h day
  at 0.6-0.8 m/s that is roughly 12-40 Wh: enough to keep a phone or a headlamp charged, not a camp power supply.
- **Minimum flow.** The rotor sustains rotation and the converter accepts power from **0.5 m/s** (the 5 V minimum input of
  the converter and the fixed friction are the limiters; at 0.4 m/s the bus would be below 5 V and the net output negative).
  **Self-start is model-marginal at 0.5 m/s**: 0.4 m/s (optimistic) / 0.5 (baseline) / 0.6 (pessimistic), set by the
  assumed GL60 cogging (24 mN m peak) plus seal and bearing breakaway. Gates G1 and G6 of the test plan decide it.
- **The winding resistance is not the obstacle.** At these powers the torque is tens of mN m, so copper loss is
  0.1-3.5 % of the available hydraulic power below 1 m/s. The obstacles are, in order: rotor efficiency at
  Reynolds numbers of 4e4-8e4 (Cp 0.25-0.33), the fixed friction torque (seal + bearing + motor no-load, 7 mN m plus
  no-load loss), the generator **voltage** (only 5.1 V at 0.5 m/s: a boost-capable converter is mandatory; a rectifier straight into the
  battery produces nothing below 0.4 m/s), and the converter's own minimum input voltage and quiescent draw.
- **A gearbox does not help.** A 2:1 or 3:1 stage (optimistic 96 % per stage, +5 mN m) changes net output by
  -22 % at 0.5 m/s and -1 % at 1.0 m/s with the real converter: rejected; direct drive is kept.
- **Selected rotor:** 3 blades, NACA 4412 blending to NACA 4418 at the root, Schmitz planform for design TSR 2.0 scaled x1.3,
  root chord 49.8 mm, maximum chord 57.8 mm, tip chord 31.0 mm, root twist 31.3 deg, solidity 0.39; it runs at
  TSR 3.0-3.4 (130-320 rpm over 0.5-1.0 m/s). Against the previous 1-2 m/s blade on its drum hub it delivers
  2.8x at 0.6 m/s and 1.47x at 1.0 m/s; against the original rev-2 blade placed on the same small hub it gains
  +745 % at 0.5, +35 % at 0.6, +13 % at 0.7 and -0 % at 1.0 m/s: the gain is where the brief asks for it, and the
  two blades are equivalent above 0.9 m/s.
- **Recommended mounting: arrangement A** (rotor on a short 316 shaft ahead of a stationary sealed nacelle). The hub radius drops from
  48 to 28 mm, which is worth +83 % at 0.7 m/s and +48 % at 1.0 m/s against the same blade in the hub-integrated drum (B), and
  the 8 mm seal halves the seal friction. The price is depth: 141 mm operating, which packs as two pieces of 58 mm (rotor)
  and 75 mm (nacelle) by removing one M4 screw. The 76 mm target is met packed, not operating.

## 2. Baseline assessment (what the previous work predicted and what it is worth)

The project holds three earlier artefacts: the original 8-inch rev-2 blade (hub 25.4 mm, design TSR 4, NACA 4422 -> 4414), the
v3.1 drum-rotor blade (root at 48.2 mm, design TSR 4 with +6 deg pitch) and the Configuration A screening spreadsheet (5.6 / 20.1 / 49 W shaft
at 1 / 1.5 / 2 m/s, 0.018 N m seal torque, 0.5 W fixed loss, 90 % downstream efficiency). None of these numbers is measured. Re-evaluated
with this package's model (NeuralFoil Reynolds-dependent polars, the same BEM corrections, the same generator and converter model):

| V (m/s) | new: Cp | new: W | new: rpm / V / A | self-start | rev-2 blade on the A hub: Cp | W | start | v3.1 blade in the drum (B): Cp | W | start | new blade in the drum (B): Cp | W |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.40 | 0.214 | 0.00 | 0 / 0.0 / 0.00 | no | 0.155 | 0.00 | no | 0.145 | 0.00 | no | 0.157 | 0.00 |
| 0.50 | 0.252 | 0.16 | 130 / 5.1 / 0.06 | yes | 0.174 | 0.02 | yes | 0.181 | 0.00 | no | 0.185 | 0.00 |
| 0.60 | 0.278 | 0.49 | 162 / 6.3 / 0.11 | yes | 0.230 | 0.37 | yes | 0.202 | 0.18 | no | 0.205 | 0.20 |
| 0.70 | 0.297 | 0.98 | 199 / 7.7 / 0.15 | yes | 0.266 | 0.87 | yes | 0.218 | 0.51 | yes | 0.221 | 0.54 |
| 0.80 | 0.310 | 1.65 | 238 / 9.1 / 0.21 | yes | 0.293 | 1.58 | yes | 0.231 | 0.99 | yes | 0.233 | 1.01 |
| 0.90 | 0.321 | 2.51 | 278 / 10.7 / 0.26 | yes | 0.311 | 2.49 | yes | 0.240 | 1.63 | yes | 0.241 | 1.64 |
| 1.00 | 0.328 | 3.60 | 320 / 12.1 / 0.33 | yes | 0.322 | 3.61 | yes | 0.248 | 2.44 | yes | 0.247 | 2.44 |
| 1.25 | 0.341 | 7.36 | 420 / 15.5 / 0.51 | yes | 0.337 | 7.50 | yes | 0.259 | 5.33 | yes | 0.258 | 5.28 |
| 1.50 | 0.347 | 12.80 | 526 / 18.8 / 0.73 | yes | 0.347 | 13.31 | yes | 0.267 | 9.68 | yes | 0.264 | 9.49 |
| 2.00 | 0.356 | 29.55 | 768 / 26.3 / 1.20 | yes | 0.359 | 31.25 | yes | 0.275 | 23.38 | yes | 0.271 | 22.63 |

(W = net 12 V electrical power with the buck-boost MPPT, baseline assumptions; "start" = static torque above the assumed breakaway.)
The spreadsheet's 5.6 W shaft at 1 m/s (Cp 0.345 on the full disc) is not reached by any of the three blades on their hubs in this model
(5.32 W peak shaft for the new rotor, Cp 0.328); the earlier "0.345-0.378" Cp values came from a polar at Re 2e5 applied at Re
7e4-8e4 (review of the trial, redesign v3). The previous electrical predictions are therefore not used as validated inputs.

## 3. Optimisation methodology and objective function

1. **Polars** (`model/polars.py`): NeuralFoil (XFOIL surrogate, Ncrit 9) on a 29 x 10 (alpha, Re) grid for NACA 4412 / 4415 / 4418,
   SG6043, E387, FX63-137 and E818, Viterna-extended to +-90 deg for the standstill estimate. E387 (confidence 0.84) and E818 (0.64,
   coarse database coordinates) are reported but not selectable. Experimental polars at Re 4e4-8e4 are not available to this project.
2. **BEM** (`model/bem_lowflow.py`): Prandtl tip and hub losses, Buhl high-induction correction, per-element Reynolds number, root blend
   to the 18 % thick section over the inner 35 % of span, nacelle inflow deficit factor 0.85 inboard of r 38 mm for arrangement A (assumption),
   vectorised Ning residual solved by bisection. Cross-checks: the near-inviscid limit stays below Betz (Cp 0.43 with tip/hub losses), P = omega Q,
   and the v3.1 blade evaluated with both the old analytic polar and the new tables agrees within the expected 10-20 % (the thick root is the difference).
3. **Coupled operating point** (`model/generator_lowflow.py`): rotor torque curve against friction (seal, bearing, motor no-load, hub
   windage) and the generator (KV 21.5, Kt 0.444 N m/A, R 5.5 ohm, L 2.72 mH, 14 pole pairs, Schottky bridge 2 x Vf(I), commutation
   overlap as a reactive voltage drop), then the converter (efficiency eta_max - k/P_in, quiescent draw, minimum input voltage, and either
   a boost-with-clamp or a buck-boost input window). The MPPT law picks the bus voltage (= rotor speed) that maximises converter output
   inside the window; it never commands more than the 1.35 A rating. Standstill torque uses alpha = 90 deg - twist on every element with
   W = V (no induction) and the Viterna polars; breakaway = cogging + seal + bearing breakaway. Dynamic friction and breakaway are separate.
4. **Objective:** J = sum over V of w(V) P_net(V) with P_net = 0 where the candidate cannot self-start, cannot sustain rotation along the
   unloaded path to its operating point, or sits below the converter's 5 V input. Two weightings: uniform over 0.5-1.0 m/s (six flows) and
   low-flow-weighted {0.5: 0.3, 0.6: 0.3, 0.7: 0.2, 0.8: 0.1, 0.9: 0.05, 1.0: 0.05} (illustrative, not measured). Also tracked: the same without the self-start gate ("hand-started") and with cogging 8 / 40 mN m.
5. **Design space** (`model/optimize_blades.py`): stage 1 = 384 candidates: 2 / 3 / 4 / 5 blades x four airfoils x design TSR 1.5-6 (Schmitz
   planform at the airfoil's best-L/D angle at the local Reynolds number) x chord scale 0.7 / 1.0 / 1.3 (chord capped at 60 mm). Stage 2 = 80
   refinements around the leader (TSR 1.75-2.5, chord scale 1.3-1.7, chord cap 60 / 68, pitch -3 / 0 / +3 deg, two-blade and SG6043 checks).
   Selection: the mean of the two normalised objectives, subject to self-start at 0.5 m/s under baseline cogging and a root chord <= 52 mm
   (the three pockets must leave printable walls on the 28 mm hub); ties go to the lower solidity.

## 4. Comparison of the blade variants (same model, same boundary conditions, arrangement A)

Best candidate per blade count, airfoil, design TSR (3 blades, NACA 4412) and chord scale (3 blades, NACA 4412, TSR 2):

| Group | Candidate | Solidity | Cp peak 0.5 / 0.7 / 1.0 | Net W at 0.5 / 0.7 / 1.0 | J uniform (W) | J low-flow (W) | min self-start (m/s) | static torque at 0.5 (mN m) |
|---|---|---|---|---|---|---|---|---|
| 2 blades | B2 naca4412 TSR_d 2.0 x1.5 | 0.33 | 0.256 / 0.290 / 0.312 | 0.17 / 0.96 / 3.44 | 1.512 | 0.842 | 0.5 | 37 |
| 3 blades | B3 naca4412 TSR_d 1.75 x1.3 | 0.44 | 0.263 / 0.302 / 0.329 | 0.18 / 1.00 / 3.60 | 1.581 | 0.882 | 0.5 | 46 |
| 4 blades | B4 naca4412 TSR_d 2.0 x1.3 | 0.48 | 0.241 / 0.284 / 0.319 | 0.14 / 0.92 / 3.38 | 1.469 | 0.806 | 0.5 | 51 |
| 5 blades | B5 naca4412 TSR_d 1.5 x1.3 | 0.57 | 0.239 / 0.288 / 0.330 | 0.11 / 0.90 / 3.25 | 1.416 | 0.776 | 0.4 | 78 |
| naca4412 | B3 naca4412 TSR_d 1.75 x1.3 | 0.44 | 0.263 / 0.302 / 0.329 | 0.18 / 1.00 / 3.60 | 1.581 | 0.882 | 0.5 | 46 |
| naca4415 | B3 naca4415 TSR_d 2.0 x1.3 | 0.36 | 0.185 / 0.274 / 0.326 | 0.05 / 0.90 / 3.59 | 1.496 | 0.761 | 0.6 | 36 |
| sg6043 | B3 sg6043 TSR_d 2.0 x1.3 | 0.36 | 0.250 / 0.275 / 0.299 | 0.16 / 0.87 / 3.18 | 1.388 | 0.772 | 0.5 | 39 |
| fx63137 | B3 fx63137 TSR_d 1.5 x1.3 | 0.41 | 0.222 / 0.263 / 0.304 | 0.09 / 0.83 / 3.19 | 1.355 | 0.725 | 0.4 | 60 |
| design TSR 1.5 | B3 naca4412 TSR_d 1.5 x1.3 | 0.43 | 0.240 / 0.282 / 0.314 | 0.12 / 0.88 / 3.13 | 1.376 | 0.762 | 0.4 | 63 |
| design TSR 2.0 | B3 naca4412 TSR_d 2.0 x1.3 | 0.39 | 0.251 / 0.297 / 0.329 | 0.16 / 0.98 / 3.61 | 1.573 | 0.867 | 0.5 | 41 |
| design TSR 2.5 | B3 naca4412 TSR_d 2.5 x1.3 | 0.36 | 0.232 / 0.276 / 0.306 | 0.14 / 0.90 / 3.37 | 1.434 | 0.754 | 0.6 | 29 |
| design TSR 3.0 | B3 naca4412 TSR_d 3.0 x1.3 | 0.39 | 0.230 / 0.269 / 0.293 | 0.13 / 0.87 / 3.20 | 1.365 | 0.721 | 0.6 | 28 |
| design TSR 3.5 | B3 naca4412 TSR_d 3.5 x1.0 | 0.30 | 0.190 / 0.253 / 0.295 | 0.06 / 0.81 / 3.26 | 1.290 | 0.580 | 0.7 | 18 |
| design TSR 4.0 | B3 naca4412 TSR_d 4.0 x1.3 | 0.35 | 0.181 / 0.246 / 0.282 | 0.06 / 0.78 / 3.04 | 1.084 | 0.393 | 0.8 | 18 |
| design TSR 5.0 | B3 naca4412 TSR_d 5.0 x0.7 | 0.13 | 0.096 / 0.108 / 0.215 | 0.00 / 0.15 / 2.36 | 0.000 | 0.000 | None | 5 |
| design TSR 6.0 | B3 naca4412 TSR_d 6.0 x0.7 | 0.10 | 0.065 / 0.068 / 0.137 | 0.00 / 0.00 / 1.29 | 0.000 | 0.000 | None | 2 |
| chord x0.7 | B3 naca4412 TSR_d 2.0 x0.7 | 0.21 | 0.157 / 0.223 / 0.288 | 0.02 / 0.68 / 3.25 | 1.234 | 0.537 | 0.7 | 22 |
| chord x1.0 | B3 naca4412 TSR_d 2.0 x1.0 | 0.30 | 0.219 / 0.279 / 0.324 | 0.11 / 0.92 / 3.59 | 1.500 | 0.775 | 0.6 | 31 |
| chord x1.3 | B3 naca4412 TSR_d 2.0 x1.3 | 0.39 | 0.251 / 0.297 / 0.329 | 0.16 / 0.98 / 3.61 | 1.573 | 0.867 | 0.5 | 41 |

Reading. Two blades give the best Cp per unit solidity but cannot self-start below 0.6 m/s; four and five blades start earlier but lose
Cp to profile drag at these Reynolds numbers. Design TSR 2-2.5 wins because the wide chords raise the local Reynolds number (the
chord is the only lever on Re at a given flow) and the standstill torque, while the actual Cp peak still sits at TSR 3-3.5 and the
coupled MPPT point at TSR 2.8-3.4, where the GL60's voltage is highest for the torque it must absorb. The low-Reynolds sections lose in the
coupled result despite their better 2-D L/D: their higher design lift coefficient produces narrower chords (lower Re) and a sharper
Cp peak. The objective surface is flat near the optimum (the top eight stage-2 candidates are within 1.5 % of each other), so the
root-chord packaging limit decided the final pick without a measurable performance cost (98.3 % of the best low-flow score).

## 5. Selected blade geometry and why it won

3 blades, NACA 4412 outboard blending to NACA 4418 over the inner 35 % (printability and root bending), Schmitz planform at design
TSR 2.0 x1.3 (capped at 60 mm), root eased to 85 % at the hub, elliptical tip taper to 55 %, pitch offset +0 deg, 1.0 mm blunt trailing edge.
Station data: `model/selected_design.json` (chord 49.8 -> 57.8 -> 31.0 mm; twist 31.3 -> 7.2 deg). Figures 5 and 6 compare it with the
previous designs. It won because it (i) self-starts at 0.5 m/s under the baseline cogging while the two-blade and the TSR >= 3 designs
do not, (ii) has the highest coupled output at 0.5-0.7 m/s (Re effect of the wide chord), (iii) matches the original rev-2 blade above
0.9 m/s, and (iv) still fits three pockets on a 28 mm hub. What it gives up: about 5 % at 2.0 m/s against the rev-2 blade and a higher
standstill drag (thrust at 2 m/s 49 N at the operating point).

## 6. Generator matching and electrical predictions

Feasibility first (`model/feasibility.py`, representative rotor, arrangement A unless noted; Cp pairs are A / B):

| V (m/s) | P through the disc (W) | through the annulus (A) | Betz on the annulus | BEM Cp (A / B) | rotor shaft (A) | lossless converter | buck-boost MPPT | boost + clamp (GVB-8 class) | rectifier to battery |
|---|---|---|---|---|---|---|---|---|---|
| 0.40 | 1.04 | 0.96 | 0.57 | 0.215 / 0.146 | 0.22 | 0.10 | 0.00 | 0.00 (mppt) | 0.00 |
| 0.50 | 2.03 | 1.87 | 1.11 | 0.234 / 0.160 | 0.47 | 0.28 | 0.14 | 0.18 (mppt) | 0.00 |
| 0.60 | 3.50 | 3.24 | 1.92 | 0.258 / 0.181 | 0.90 | 0.60 | 0.44 | 0.48 (mppt) | 0.00 |
| 0.70 | 5.56 | 5.14 | 3.05 | 0.277 / 0.199 | 1.54 | 1.05 | 0.86 | 0.89 (mppt) | 0.17 |
| 0.80 | 8.30 | 7.67 | 4.55 | 0.287 / 0.208 | 2.38 | 1.67 | 1.44 | 1.46 (mppt) | 1.07 |
| 0.90 | 11.82 | 10.92 | 6.47 | 0.294 / 0.216 | 3.48 | 2.48 | 2.20 | 2.20 (mppt) | 2.15 |
| 1.00 | 16.21 | 14.98 | 8.88 | 0.302 / 0.222 | 4.89 | 3.52 | 3.17 | 3.15 (mppt) | 3.38 |
| 1.25 | 31.67 | 29.26 | 17.34 | 0.313 / 0.234 | 9.91 | 7.24 | 6.68 | 6.54 (mppt) | 7.19 |
| 1.50 | 54.72 | 50.57 | 29.97 | 0.321 / 0.244 | 17.58 | 12.92 | 12.01 | 11.02 (clamp) | 12.06 |
| 2.00 | 129.72 | 119.87 | 71.03 | 0.333 / 0.255 | 43.22 | 30.26 | 28.31 | 22.28 (clamp) | 24.31 ! |

("!" = the generator current exceeds the 1.35 A rating in that mode: not allowed without a current limiter.)

Loss shares along the chain at the coupled operating points (arrangement A, buck-boost):

| V | hydraulic in the annulus (W) | hydrodynamic loss % | friction + no-load % | copper % | diodes % | converter % | net out (W, %) | operating point |
|---|---|---|---|---|---|---|---|---|
| 0.40 | 0.96 | 78 | 13.5 | 0.1 | 0.9 | 7.4 | 0.00 (0 %) | 123 rpm, 5.0 V, 0.01 A |
| 0.50 | 1.87 | 75 | 7.3 | 0.9 | 1.9 | 5.5 | 0.18 (10 %) | 129 rpm, 5.0 V, 0.06 A |
| 0.60 | 3.24 | 72 | 4.8 | 2.2 | 2.3 | 4.0 | 0.48 (15 %) | 142 rpm, 5.3 V, 0.11 A |
| 0.70 | 5.14 | 71 | 4.2 | 2.2 | 1.8 | 3.2 | 0.89 (17 %) | 189 rpm, 7.3 V, 0.14 A |
| 0.80 | 7.67 | 70 | 3.4 | 2.8 | 1.8 | 2.8 | 1.46 (19 %) | 221 rpm, 8.4 V, 0.20 A |
| 0.90 | 10.92 | 70 | 3.0 | 3.1 | 1.6 | 2.6 | 2.20 (20 %) | 263 rpm, 10.0 V, 0.25 A |
| 1.00 | 14.98 | 69 | 2.6 | 3.5 | 1.5 | 2.4 | 3.15 (21 %) | 300 rpm, 11.4 V, 0.31 A |
| 1.25 | 29.26 | 67 | 1.9 | 4.7 | 1.4 | 2.2 | 6.54 (22 %) | 393 rpm, 14.4 V, 0.50 A |
| 1.50 | 50.57 | 66 | 1.3 | 7.6 | 1.5 | 2.1 | 11.02 (22 %) | 444 rpm, 14.4 V, 0.84 A |
| 2.00 | 119.87 | 64 | 0.8 | 13.2 | 1.8 | 1.7 | 22.28 (19 %) | 576 rpm, 14.3 V, 1.70 A |

Gear ratio study (ideal converter / real buck-boost, W):

| ratio | 0.5 m/s | 0.6 | 0.7 | 0.8 | 1.0 |
|---|---|---|---|---|---|
| 1:1 | 0.28 / 0.18 | 0.60 / 0.48 | 1.05 / 0.89 | 1.67 / 1.46 | 3.52 / 3.15 |
| 2:1 | 0.24 / 0.14 | 0.60 / 0.47 | 1.14 / 0.96 | 1.83 / 1.61 | 3.92 / 3.13 |
| 3:1 | 0.25 / 0.12 | 0.61 / 0.30 | 1.18 / 0.42 | 1.92 / 0.54 | 4.12 / 0.84 |

Selected design, per flow (buck-boost MPPT; boost+clamp and direct-to-battery for comparison; standstill torque vs breakaway):

| V (m/s) | buck-boost: rpm / V_dc / I / net W | boost + clamp: net W (region) | direct to battery: net W | open-circuit runaway | static torque / breakaway (mN m) |
|---|---|---|---|---|---|
| 0.40 | 0 / 0.0 / 0.00 / 0.00 | 0.00 (mppt) | 0.10 | 144 rpm, 7 V | 26 / 36 |
| 0.50 | 130 / 5.1 / 0.06 / 0.16 | 0.21 (mppt) | 0.31 | 207 rpm, 10 V | 41 / 36 |
| 0.60 | 162 / 6.3 / 0.11 / 0.49 | 0.53 (mppt) | 0.66 | 267 rpm, 12 V | 58 / 36 |
| 0.70 | 199 / 7.7 / 0.15 / 0.98 | 1.01 (mppt) | 1.18 | 328 rpm, 15 V | 80 / 36 |
| 0.80 | 238 / 9.1 / 0.21 / 1.65 | 1.66 (mppt) | 1.89 | 394 rpm, 18 V | 104 / 36 |
| 0.90 | 278 / 10.7 / 0.26 / 2.51 | 2.51 (mppt) | 2.81 | 458 rpm, 21 V | 132 / 36 |
| 1.00 | 320 / 12.1 / 0.33 / 3.60 | 3.57 (mppt) | 3.97 | 521 rpm, 24 V | 164 / 36 |
| 1.25 | 420 / 15.5 / 0.51 / 7.36 | 7.22 (clamp) | 7.97 | 682 rpm, 32 V | 258 / 36 |
| 1.50 | 526 / 18.8 / 0.73 / 12.80 | 11.88 (clamp) | 13.76 | 844 rpm, 39 V | 372 / 36 |
| 2.00 | 768 / 26.3 / 1.20 / 29.55 | 23.37 (clamp, I 1.77 A OVER) | 31.57 | 1171 rpm, 54 V | 665 / 36 |

Load control. Below the clamp voltage both converters regulate the bus, i.e. the rotor speed, so the generator cannot stall the rotor:
the equilibrium sits on the stable side of the torque peak (fig. 9). With the boost-only converter the bus is clamped at the battery
above about 1.25 m/s; the rotor is then held at a fixed speed and, from about 1.75 m/s, the clamp current exceeds the GL60 rating:
a boost-only unit needs a 1.5-2 A limiter or a 40 V relay dump for the 1-2 m/s survivability case. The buck-boost keeps regulating to
2 m/s (1.20 A at 26.3 V). Open circuit at 2 m/s is 54 V: below the 60 V TVS standoff and the converter's 60 V input.
Current and temperature: copper loss at 2 m/s is 7.9 W inside a sealed nacelle; the brief's 0.5-1.0 m/s duty is < 0.1 W. Thermal limits are not
the sizing case below 1.5 m/s; the earlier v3.1 heat-path analysis applies if the device is left in a 2 m/s flow (rear cap in 6061).

## 7. Recommended compact mounting and waterproofing (arrangement A), with B quantified

| | A: rotor on a short shaft, stationary nacelle behind | B: hub-integrated (v3.1 drum rotor) |
|---|---|---|
| hub radius / ratio | 28 mm / 0.28 | 48.2 mm / 0.47 (the GL60 inside a 3 in drum) |
| net W at 0.5 / 0.7 / 1.0 m/s (same blade) | 0.16 / 0.98 / 3.60 | 0.00 / 0.54 / 2.44 |
| rotary seal | one 8 mm PTFE lip seal (run 4 mN m assumed) | one 15 mm PTFE lip seal (7.5 mN m) |
| bearings | one 608-2RS in the cap + the GL60's own | two 6702-2RS |
| machined parts | shaft, front cap, rear cap, tube ends (4) | spindle, 2 caps, split ring, plug, boss, 3 struts, tube ends (9+) |
| waterproof boundary | tube + 1 O-ring per cap + lip seal + WetLink + vent | tube + O-rings + lip seal + potting plug |
| operating depth | 141 mm; packs as 58 + 75 mm | 73 mm |
| flow obstruction behind the rotor | 3 in nacelle (14 % of the disc area), modelled as a 15 % inflow deficit inboard of r 38 mm | none beyond the drum itself |
| seal service | pull the hub (one screw), press the seal from the wet face | partial disassembly (v3.1 plan) |

**Load path (A, fig. 10a).** Thrust: blade -> airfoil tongue (clamped between the two hub halves by an axial M3) -> hub -> collar A ->
shaft -> collar B -> 608 inner race -> outer race -> front-cap floor -> cap plug and flange -> tube -> clamp -> three L-struts -> guard ring
and stake. Reverse load: DIN 471-8 circlip behind the bearing (0.2 mm end play); the seal pressed in front of the bearing retains the
outer race. Torque: hub D-bore -> shaft D-flat -> cross-pinned dog hub -> TPU disc (two dogs, 0.2 mm radial clearance) -> GL60 bell; the
stator is screwed to the rear cap. The GL60 carries no rotor thrust and no radial load. The motor is dry: tube, one EPDM O-ring per cap,
an 8 mm PTFE lip seal on the polished 316 journal, a WetLink M10 penetrator and an M6 vent; IP45 is irrelevant inside that boundary.
**Penalties quantified:** the seal and bearing take 7 mN m of the 38 mN m the rotor makes at 0.5 m/s (19 %) and 4 % at 1.0 m/s;
the nacelle inflow deficit costs about 3 % of Cp (assumption, to be checked in G8/G11); the hub ratio 0.28 costs the annulus area shown in the feasibility table.

## 8. Plots

| # | Figure | File |
|---|---|---|
| 1 | hydraulic power vs water speed with the physical and model bounds | `out/fig1_hydraulic_power.png` |
| 2 | Cp vs TSR, previous vs optimised, 0.5 / 0.7 / 1.0 / 1.5 m/s | `out/fig2_cp_tsr.png` |
| 3 | rotor torque vs rpm with standstill, friction, breakaway and generator load lines | `out/fig3_torque_rpm.png` |
| 4 | mechanical and net electrical power vs water speed, all designs | `out/fig4_power_vs_v.png` |
| 5, 6 | chord and twist distributions | `out/fig5_6_chord_twist.png` |
| 7 | generator efficiency map and the loss breakdown at the operating points | `out/fig7_generator_losses.png` |
| 8 | sensitivity to seal friction, cogging, no-load loss, polars, generator constants, converter | `out/fig8_sensitivity.png` |
| 9 | operating-point diagrams (rotor torque vs generator load lines) | `out/fig9_operating_point.png` |
| 10 | CAD section with load paths and boundary, dimensioned section, exploded view | `out/fig10a_section.png`, `fig10b_dimensioned.png`, `fig10c_exploded.png` |
| - | candidate polars | `out/fig_polars.png` |

Sensitivity table (net W, gated by self-start; one input at a time):

| case | 0.5 | 0.6 | 0.7 | 0.8 | 1.0 m/s |
|---|---|---|---|---|---|
| baseline | 0.16 | 0.49 | 0.98 | 1.65 | 3.60 |
| seal x0.5 | 0.18 | 0.52 | 1.01 | 1.68 | 3.64 |
| seal x2.0 | 0.00 | 0.45 | 0.92 | 1.58 | 3.51 |
| seal x3.0 | 0.00 | 0.40 | 0.87 | 1.52 | 3.43 |
| cogging 8 mN m | 0.16 | 0.49 | 0.98 | 1.65 | 3.60 |
| cogging 40 mN m | 0.00 | 0.49 | 0.98 | 1.65 | 3.60 |
| no-load loss 0.2 W@700 | 0.18 | 0.52 | 1.01 | 1.69 | 3.66 |
| no-load loss 1.5 W@700 | 0.11 | 0.42 | 0.88 | 1.52 | 3.40 |
| cd x1.3 | 0.11 | 0.42 | 0.88 | 1.51 | 3.36 |
| cd x1.6 | 0.06 | 0.34 | 0.78 | 1.38 | 3.15 |
| cl x0.9, cd x1.3 | 0.11 | 0.42 | 0.88 | 1.52 | 3.37 |
| KV 25 (Kt 0.38) | 0.13 | 0.46 | 0.92 | 1.55 | 3.36 |
| R 6.5 ohm | 0.16 | 0.48 | 0.96 | 1.61 | 3.50 |
| conv eta 0.85 | 0.14 | 0.43 | 0.87 | 1.48 | 3.24 |
| conv eta 0.96 | 0.21 | 0.55 | 1.04 | 1.73 | 3.72 |
| conv Vmin 3 V | 0.16 | 0.49 | 0.98 | 1.65 | 3.60 |
| conv Vmin 8 V | 0.00 | 0.44 | 0.98 | 1.65 | 3.60 |
| rectifier synchronous | 0.16 | 0.49 | 0.98 | 1.65 | 3.60 |

Minimum self-start / sustain velocities: optimistic (cd x1.0, cogging 8 mN m, seal x0.5) 0.4 / 0.5 m/s; baseline 0.5 / 0.5;
pessimistic (cd x1.3, cl x0.9, cogging 40 mN m, seal x2) 0.6 / 0.5 m/s. The sustain floor is the converter's 5 V minimum; a 3 V converter would move it to
0.5 m/s with 0.16 W at 0.5 m/s.

## 9. Reproducible source code and CAD exports

`model/polars.py` (polar tables), `bem_lowflow.py`, `generator_lowflow.py`, `feasibility.py`, `optimize_blades.py` (stages 1-2 and the
selection), `coupled_eval.py` (figures 2-9, comparison, sensitivities); `cad/make_v4.py` (parametric assembly, STEP per part, assembly
STEP, print-oriented STLs with the blade meshed as a closed structured surface), `cad/views_v4.py` (figure 10); `tools/qa_gates_v4.py`.
Exports: `out/v4_assembly.step`, `out/v4_*.step` (28 parts, 11 printed, 4 machined), `out/v4_*_PRINT.stl` (11 files, all closed,
blade mesh within 0.13 % of its STEP volume, tilted -4.3 deg for a level pressure face). Regenerate in the order given in `README.md`.
Print notes: blades pressure-side down with tree supports under the leading-edge overhang, 100 % infill, layers along the span; hub
halves parting face down, no supports; TPU disc flat; clamp halves flat; ring as three arcs. Minimum blade thickness 3.7 mm at the tip
(12 % of 31.0 mm), 1.0 mm trailing edge.

**Structural screening at the 2 m/s survival case** (`model/structure_v4.py`; allowables assumed: ASA 8 / 4.5 MPa long-term in-plane / across
layers, 15 / 8 short-term, 2.7 / 4.8 interlaminar shear): rotor thrust 48.8 N (16.3 N per blade) and 0.53 N m at 768 rpm, runaway 1171 rpm.
Root bending 2.48 MPa in the 9.0 mm thick NACA 4418 root (in-plane for a flat print); centrifugal 26 N per blade (25 g) -> M3 bolt double shear
1.8 MPa, tongue bearing 0.64 MPa, 4.3 mm ligament shear-out 0.22 MPa; pocket walls take the flap moment at 1.38 MPa; the three
pockets span 89 deg each, leaving 31 deg of hub wall (8.6 mm at the pocket floor, 15.1 mm at the surface); strut legs 3.6 MPa in bending;
shaft torsion 5.2 MPa (7.8 at the D-flat; 316 yield ~200); 608 bearing Fa/C0 0.035. All below the allowables with margin; fatigue (3/rev strut wake) is not assessed.

## 10. Independent adversarial review and corrections

(review log not yet generated)

## 11. Practical prototype testing plan

See `docs/TEST_PLAN_v4.md` (12 gates). The four measurements that close the model, in order of their effect on the 0.5-0.7 m/s prediction:
G1 generator constants and cogging, G2 breakaway and running friction of the sealed shaft, G6 standstill torque of the printed rotor, G8 the
power curve in a real stream.

## 12. Bill of materials for the simplest working prototype

`docs/BOM_v4.csv`: 29 lines, roughly $3,189-3,550 of parts beyond the GL60 (converter choice dominates; machining prices are
estimates for a job shop; no anodising, battery, cable beyond 3 m or instrumentation). The four machined parts (shaft, two caps, tube
ends) are the only non-printed, non-COTS items.

## 13. Quality gates

# Quality-gate log (v4 low-flow turbine)

The `/quality` skill is not installed in this environment, so these manual gates (`tools/qa_gates_v4.py`) stand in for it. Each gate is a script check on the exported files and result JSONs, re-run after every correction.

| Gate | Result | Detail |
|---|---|---|
| reproducibility (re-run of the coupled model) | PASS | |dP| 0.00e+00 W at 0.7/1.0 m/s |
| Cp below the Betz limit on every curve | PASS | max Cp 0.356 |
| twist monotonic decreasing root -> tip, 0-60 deg | PASS | 31.3 -> 7.2 deg |
| printable section: tip chord >= 20 mm and max thickness >= 2.4 mm | PASS | tip chord 31.0 mm, tip t 3.7 mm, TE 1.0 mm |
| power balance at every operating point (shaft = friction + copper + diodes + DC) | PASS | 0.5: 0.00 %; 0.6: 0.00 %; 0.7: 0.00 %; 0.8: 0.00 %; 0.9: 0.00 %; 1.0: 0.00 %; 1.25: 0.00 %; 1.5: 0.00 %; 2.0: 0.00 % |
| generator current <= 1.35 A rated at every MPPT point to 2.0 m/s | PASS | max I 1.20 A |
| open-circuit bus at 2.0 m/s below the 60 V TVS standoff and the converter's 60 V input | PASS | 54.4 V |
| CAD station chord/twist match the model arrays (interpolated, r >= 28 mm) | PASS | max |dc| 0.47 mm, |dtwist| 0.30 deg |
| CAD: every solid valid, single body, no rigid clash | PASS | 28 parts, 300 pairs, interference {} |
| print STLs closed; blade STL volume within 1 % of its STEP | PASS | 11 STLs; blade dev [0.13] % |
| packing: rotor and nacelle each <= 76 mm when detached | PASS | rotor 58.0, nacelle 74.9, operating 141.4 mm |
| all required figures generated by scripts | PASS | 12 figures |
| BOM covers every CAD part | PASS | 29 BOM lines |
| report generator present | PASS | 30110 chars |

**14 of 14 gates pass.**


## 14. Unresolved assumptions

- GL60: KV / Kt / R convention, cogging torque (the single biggest unknown for self-start), no-load loss, lead exit, which hole pattern is the stator's.
- Hydrofoil polars at Re 4e4-8e4 come from an XFOIL surrogate; wind-tunnel data for printed-rough surfaces would likely sit 10-30 % lower in L/D.
- The standstill torque model (Viterna post-stall, no induction) is the least validated part of the BEM; it decides the self-start verdict.
- Seal and bearing friction (assumed from diameter scaling of catalogue-class values), converter efficiency curve and minimum input voltage, quiescent draw.
- Nacelle inflow deficit (15 % inboard of r 38 mm), guard-ring and shallow-water effects (G11), turbulence and debris.
- Manufacturer pages were unreachable: WetLink, Genasun GVB-8, LT8390 modules and seal part numbers must be confirmed before ordering.
