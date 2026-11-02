# Portable hydrokinetic turbine for 0.5-1.0 m/s streams: low-flow redesign (v4)

**Scope and status.** Everything in this package is model prediction and design intent. No part has been printed, machined or
tested; no GL60 has been measured; manufacturer web pages (cubemars.com, genasun, bluerobotics.com, digikey) could not be reached
from this session, so the generator values are the ones listed in the brief and in the earlier review, bracketed by sensitivity cases.
Every number below is written by `docs/make_report_v4.py` from the result files of the scripts in `model/`, `cad/` and `tools/`.

## 1. Executive summary and feasibility verdict

- **What the GL60 can deliver (model, baseline assumptions, arrangement A, buck-boost MPPT):** net 12 V electrical power
  **0.16 W at 0.5 m/s, 0.49 W at 0.6, 0.96 W at 0.7, 1.60 W at 0.8, 3.45 W at 1.0 m/s** (12.0 W at 1.5, 27.2 W at 2.0). One-at-a-time sensitivity envelope: -39 % / +14 % at 0.7 m/s and -12 % / +8 % at 1.0 m/s
  (hydrofoil polars at Re 4e4-8e4 from an XFOIL surrogate, unmeasured friction and generator constants; section 8). Over a 24 h day
  at 0.6-0.8 m/s that is roughly 12-38 Wh: enough to keep a phone or a headlamp charged, not a camp power supply.
- **Minimum flow.** The rotor sustains rotation and the converter accepts power from **0.5 m/s** (the 5 V minimum input of
  the converter and the fixed friction are the limiters; at 0.4 m/s the bus would be below 5 V and the net output negative).
  **Self-start from rest is NOT predicted at 0.5 m/s under the baseline model.** The starting torque is the BEM torque at TSR 0.1 with induction
  (the no-induction flat-plate estimate used in the first draft was 1.8x too high and is kept only as an upper bound): at 0.5 m/s the rotor makes
  29 mN m (upper bound 51) against a breakaway of 36 mN m (assumed GL60 cogging 24 mN m + seal + bearing). Model minimum self-start:
  **0.6 m/s baseline**, 0.4 optimistic, 0.8 pessimistic (0.5 with the upper-bound torque). A start at 0.5 / 0.6 / 0.7 m/s needs the measured cogging
  to be below 17 / 30 / 45 mN m. Once turning, the rotor sustains itself from 0.5 m/s (cogging averages out), so a hand spin at
  deployment covers the gap; gates G1 (cogging) and G6 (starting torque) decide it.
- **The winding resistance is not the obstacle.** At these powers the torque is tens of mN m, so copper loss is
  0.1-3.5 % of the available hydraulic power below 1 m/s. The obstacles are, in order: rotor efficiency at
  Reynolds numbers of 4e4-8e4 (Cp 0.25-0.33), the fixed friction torque (seal + bearing + motor no-load, 7 mN m plus
  no-load loss), the generator **voltage** (only 5.0 V at 0.5 m/s: a boost-capable converter is mandatory; a rectifier straight into the
  14.4 V battery produces nothing below 0.8 m/s and only 0.50 W there), and the converter's own minimum input voltage and quiescent draw.
- **A gearbox does not help.** A 2:1 stage (optimistic 96 % per stage, +5 mN m running, +8 mN m breakaway) changes net output with the selected
  buck-boost by -69 % at 0.5 m/s, +1 % at 0.7 and +8 % at 1.0 m/s, and raises the
  self-start threshold of the feasibility study's representative rotor from 0.8 to 0.9 m/s (the extra breakaway is a fifth of the 0.7 m/s starting torque): rejected; direct drive is kept.
- **Selected rotor:** 3 blades, NACA 4412 blending to NACA 4418 at the root, Schmitz planform for design TSR 1.5 scaled x1.0,
  root chord 50.1 mm, maximum chord 60.0 mm, tip chord 31.1 mm, root twist 32.7 deg, solidity 0.41; it runs at
  TSR 2.8-3.1 (129-291 rpm over 0.5-1.0 m/s). Against the previous 1-2 m/s blade on its drum hub it delivers
  2.7x at 0.6 m/s and 1.41x at 1.0 m/s; against the original rev-2 blade placed on the same small hub it gains
  +749 % at 0.5 (net; +46 % in peak shaft power), +34 % at 0.6, +10 % at 0.7 and -4 % at 1.0 m/s: the gain is where the brief asks for it, and the
  two blades are within 4 % of each other over 0.8-1.0 m/s (the new blade gives up 13 % at 2.0 m/s).
- **Recommended mounting: arrangement A** (rotor on a short 316 shaft ahead of a stationary sealed nacelle). The hub radius drops from
  48 to 28 mm, which is worth +77 % at 0.7 m/s and +44 % at 1.0 m/s against the same blade in the hub-integrated drum (B), and
  the 8 mm seal halves the seal friction. The price is depth: 136 mm operating, which packs as two pieces of 72 mm (rotor
  assembly with its own shaft, unscrewed at the M5 joint) and 75 mm (nacelle including the captive stub shaft and the penetrator nut); the
  shell clamp, three struts and three ring arcs pack flat (thickest part 61 mm). The 76 mm target is met packed, not operating.

## 2. Baseline assessment (what the previous work predicted and what it is worth)

The project holds three earlier artefacts: the original 8-inch rev-2 blade (hub 25.4 mm, design TSR 4, NACA 4422 -> 4414), the
v3.1 drum-rotor blade (root at 48.2 mm, design TSR 4 with +6 deg pitch) and the Configuration A screening spreadsheet (5.6 / 20.1 / 49 W shaft
at 1 / 1.5 / 2 m/s, 0.018 N m seal torque, 0.5 W fixed loss, 90 % downstream efficiency). None of these numbers is measured. Re-evaluated
with this package's model (NeuralFoil Reynolds-dependent polars, the same BEM corrections, the same generator and converter model):

| V (m/s) | new: Cp | new: W | new: rpm / V / A | self-start | rev-2 blade on the A hub: Cp | W | start | v3.1 blade in the drum (B): Cp | W | start | new blade in the drum (B): Cp | W |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.40 | 0.219 | 0.00 | 0 / 0.0 / 0.00 | no | 0.155 | 0.00 | no | 0.145 | 0.00 | no | 0.161 | 0.00 |
| 0.50 | 0.255 | 0.16 | 129 / 5.0 / 0.06 | no | 0.174 | 0.02 | no | 0.181 | 0.00 | no | 0.187 | 0.00 |
| 0.60 | 0.278 | 0.49 | 150 / 5.7 / 0.12 | yes | 0.230 | 0.36 | no | 0.202 | 0.18 | no | 0.205 | 0.21 |
| 0.70 | 0.296 | 0.96 | 184 / 6.9 / 0.17 | yes | 0.266 | 0.87 | yes | 0.218 | 0.51 | no | 0.220 | 0.54 |
| 0.80 | 0.309 | 1.60 | 221 / 8.3 / 0.22 | yes | 0.293 | 1.58 | yes | 0.231 | 0.99 | no | 0.231 | 1.01 |
| 0.90 | 0.319 | 2.43 | 254 / 9.4 / 0.29 | yes | 0.311 | 2.49 | yes | 0.240 | 1.63 | no | 0.240 | 1.63 |
| 1.00 | 0.327 | 3.45 | 291 / 10.6 / 0.36 | yes | 0.322 | 3.61 | yes | 0.248 | 2.44 | yes | 0.245 | 2.40 |
| 1.25 | 0.339 | 6.98 | 383 / 13.5 / 0.56 | yes | 0.337 | 7.50 | yes | 0.259 | 5.33 | yes | 0.255 | 5.13 |
| 1.50 | 0.347 | 12.02 | 486 / 16.7 / 0.77 | yes | 0.347 | 13.31 | yes | 0.267 | 9.68 | yes | 0.261 | 9.12 |
| 2.00 | 0.354 | 27.23 | 704 / 23.0 / 1.27 | yes | 0.359 | 31.25 | yes | 0.275 | 23.38 | yes | 0.268 | 21.48 |

(W = net 12 V electrical power with the buck-boost MPPT, baseline assumptions; "start" = static torque above the assumed breakaway.)
The original rev-2 blade (NACA 4422 -> 4414) is evaluated with the NACA 4415 table and the same 4418 root blend because no 4422 table exists (slightly
favourable to it at the root). The spreadsheet's 5.6 W shaft at 1 m/s (Cp 0.345 on the full disc) is not reached by any of the three blades on their hubs in this model
(5.30 W peak shaft for the new rotor, Cp 0.327); the earlier "0.345-0.378" Cp values came from a polar at Re 2e5 applied at Re
7e4-8e4 (review of the trial, redesign v3). The previous electrical predictions are therefore not used as validated inputs.

## 3. Optimisation methodology and objective function

1. **Polars** (`model/polars.py`): NeuralFoil (XFOIL surrogate, Ncrit 9) on a 29 x 10 (alpha, Re) grid for NACA 4412 / 4415 / 4418,
   SG6043, E387, FX63-137 and E818, Viterna-extended to +-90 deg for the standstill estimate. E387 (confidence 0.84) and E818 (0.64,
   coarse database coordinates) are reported but not selectable. Experimental polars at Re 4e4-8e4 are not available to this project.
2. **BEM** (`model/bem_lowflow.py`): Prandtl tip and hub losses, Buhl high-induction correction, per-element Reynolds number, root blend
   to the 18 % thick section over the inner 35 % of span, nacelle inflow deficit factor 0.85 inboard of r 38 mm for arrangement A (assumption),
   vectorised Ning residual solved by bisection. Cross-checks: the near-inviscid limit stays below Betz (Cp 0.43 with tip/hub losses), P = omega Q,
   and the v3.1 blade evaluated with both the old analytic polar and the new tables agrees within the polar uncertainty (the thick root is the difference).
3. **Coupled operating point** (`model/generator_lowflow.py`): rotor torque curve against friction (seal, bearing, motor no-load, hub
   windage) and the generator (KV 21.5, Kt 0.444 N m/A, R 5.5 ohm, L 2.72 mH, 14 pole pairs, Schottky bridge 2 x Vf(I), commutation
   overlap as a reactive voltage drop), then the converter (efficiency eta_max - k/P_in, quiescent draw, minimum input voltage, and either
   a boost-with-clamp or a buck-boost input window). The MPPT law picks the bus voltage (= rotor speed) that maximises converter output
   inside the window; it is required (BOM 26) never to command more than the 1.35 A rating. Starting torque = the BEM torque at TSR 0.1 with
   momentum induction (baseline); the no-induction estimate (alpha = 90 deg - twist, W = V, Viterna polars) is 1.6-1.8x higher and is reported
   only as an upper bound (review C1); breakaway = cogging + seal + bearing breakaway. Dynamic friction and breakaway are separate.
4. **Objective:** J = sum over V of w(V) P_net(V) with P_net = 0 where the candidate cannot self-start, cannot sustain rotation along the
   unloaded path to its operating point, or sits below the converter's 5 V input. Two weightings: uniform over 0.5-1.0 m/s (six flows) and
   low-flow-weighted {0.5: 0.3, 0.6: 0.3, 0.7: 0.2, 0.8: 0.1, 0.9: 0.05, 1.0: 0.05} (illustrative, not measured). Also tracked: the same without the self-start gate ("hand-started") and with cogging 8 / 40 mN m.
5. **Design space** (`model/optimize_blades.py`): stage 1 = 384 candidates: 2 / 3 / 4 / 5 blades x four airfoils x design TSR 1.5-6 (Schmitz
   planform at the airfoil's best-L/D angle at the local Reynolds number) x chord scale 0.7 / 1.0 / 1.3 (chord capped at 60 mm). Stage 2 = 124
   refinements around the leaders (3 / 4 / 5 blades x design TSR 1.5 / 1.75 / 2 / 2.5 x chord scale 1.0 / 1.3 / 1.5 x pitch -3 / 0 / +3 deg, plus
   two-blade and SG6043 checks). Selection (`selection.json`): the mean of the two normalised objectives (self-start gate inside the objective,
   baseline starting torque = BEM at TSR 0.1), subject to >= 12 deg of printed hub wall between adjacent pockets (pocket arc from the root
   chord and twist on the 28 mm hub); ties go to the lower solidity. The best candidate without the self-start gate is recorded separately.

## 4. Comparison of the blade variants (same model, same boundary conditions, arrangement A)

Best candidate per blade count, airfoil, design TSR (3 blades, NACA 4412) and chord scale (3 blades, NACA 4412, TSR 2):

| Group | Candidate | Solidity | Cp peak 0.5 / 0.7 / 1.0 | Net W at 0.5 / 0.7 / 1.0 | J uniform (W) | J low-flow (W) | min self-start (m/s) | static torque at 0.5 (mN m) |
|---|---|---|---|---|---|---|---|---|
| 2 blades | B2 naca4412 TSR_d 2.0 x1.3 | 0.32 | 0.255 / 0.290 / 0.312 | 0.17 / 0.96 / 3.45 | 1.403 | 0.645 | 0.7 | 20 |
| 3 blades | B3 naca4412 TSR_d 1.75 x1.3 | 0.43 | 0.258 / 0.299 / 0.328 | 0.17 / 0.97 / 3.48 | 1.506 | 0.803 | 0.6 | 29 |
| 4 blades | B4 naca4412 TSR_d 1.5 x1.5 | 0.58 | 0.259 / 0.300 / 0.333 | 0.14 / 0.94 / 3.29 | 1.456 | 0.814 | 0.5 | 42 |
| 5 blades | B5 naca4412 TSR_d 1.5 x1.5 | 0.66 | 0.252 / 0.296 / 0.328 | 0.15 / 0.94 / 3.34 | 1.467 | 0.815 | 0.5 | 39 |
| naca4412 | B5 naca4412 TSR_d 1.5 x1.5 | 0.66 | 0.252 / 0.296 / 0.328 | 0.15 / 0.94 / 3.34 | 1.467 | 0.815 | 0.5 | 39 |
| naca4415 | B4 naca4415 TSR_d 1.5 x1.3 | 0.52 | 0.196 / 0.276 / 0.329 | 0.07 / 0.87 / 3.34 | 1.421 | 0.750 | 0.5 | 37 |
| sg6043 | B5 sg6043 TSR_d 2.0 x1.0 | 0.55 | 0.263 / 0.283 / 0.303 | 0.13 / 0.86 / 2.92 | 1.302 | 0.735 | 0.5 | 40 |
| fx63137 | B3 fx63137 TSR_d 1.5 x1.3 | 0.41 | 0.222 / 0.263 / 0.304 | 0.09 / 0.83 / 3.19 | 1.340 | 0.697 | 0.6 | 34 |
| design TSR 1.5 | B3 naca4412 TSR_d 1.5 x1.3 | 0.43 | 0.240 / 0.282 / 0.314 | 0.12 / 0.88 / 3.13 | 1.356 | 0.726 | 0.6 | 35 |
| design TSR 2.0 | B3 naca4412 TSR_d 2.0 x1.3 | 0.39 | 0.251 / 0.297 / 0.329 | 0.16 / 0.98 / 3.61 | 1.463 | 0.669 | 0.7 | 23 |
| design TSR 2.5 | B3 naca4412 TSR_d 2.5 x1.0 | 0.28 | 0.211 / 0.265 / 0.310 | 0.09 / 0.87 / 3.46 | 1.227 | 0.444 | 0.8 | 14 |
| design TSR 3.0 | B3 naca4412 TSR_d 3.0 x1.3 | 0.39 | 0.230 / 0.269 / 0.293 | 0.13 / 0.87 / 3.20 | 1.148 | 0.417 | 0.8 | 16 |
| design TSR 3.5 | B3 naca4412 TSR_d 3.5 x1.3 | 0.38 | 0.210 / 0.258 / 0.288 | 0.10 / 0.83 / 3.10 | 0.877 | 0.263 | 0.9 | 13 |
| design TSR 4.0 | B3 naca4412 TSR_d 4.0 x1.3 | 0.35 | 0.181 / 0.246 / 0.282 | 0.06 / 0.78 / 3.04 | 0.507 | 0.152 | 1.0 | 10 |
| design TSR 5.0 | B3 naca4412 TSR_d 5.0 x0.7 | 0.13 | 0.096 / 0.108 / 0.215 | 0.00 / 0.15 / 2.36 | 0.000 | 0.000 | None | 3 |
| design TSR 6.0 | B3 naca4412 TSR_d 6.0 x0.7 | 0.10 | 0.065 / 0.068 / 0.137 | 0.00 / 0.00 / 1.29 | 0.000 | 0.000 | None | 2 |
| chord x0.7 | B3 naca4412 TSR_d 2.0 x0.7 | 0.21 | 0.157 / 0.223 / 0.288 | 0.02 / 0.68 / 3.25 | 1.121 | 0.402 | 0.8 | 16 |
| chord x1.0 | B3 naca4412 TSR_d 2.0 x1.0 | 0.30 | 0.219 / 0.279 / 0.324 | 0.11 / 0.92 / 3.59 | 1.427 | 0.645 | 0.7 | 20 |
| chord x1.3 | B3 naca4412 TSR_d 2.0 x1.3 | 0.39 | 0.251 / 0.297 / 0.329 | 0.16 / 0.98 / 3.61 | 1.463 | 0.669 | 0.7 | 23 |

Reading. Two blades give the best Cp per unit solidity; four and five blades reach their starting torque earlier but lose Cp to profile
drag at these Reynolds numbers. Low design TSR (1.5 for the pick; 1.5-2 for the whole top group) wins because the wide chords raise the local
Reynolds number (the chord is the only lever on Re at a given flow) and the starting torque, while the actual Cp peak sits at TSR 2.6
and the coupled MPPT point at TSR 2.8-3.1, where the GL60's voltage is highest for the torque it must absorb. The low-Reynolds sections lose in the
coupled result despite their better 2-D L/D: their higher design lift coefficient produces narrower chords (lower Re) and a sharper Cp peak. The
objective surface is flat near the optimum (the top eight stage-2 candidates lie within 1.5 % of each other on J_uniform), so the hub-packaging
constraint (>= 12 deg of printed wall between pockets) decided among near-equal candidates: the pick scores 98.7 % of the best unconstrained
J_uniform and 97.4 % of the best J_low-flow (unconstrained best: {'B': 4, 'airfoil': 'naca4412', 'lam_d': 1.5, 'c_scale': 1.3, 'c_max': 0.06, 'dbeta': -3.0}).

**Robustness of the blade-count conclusion** (`model/robustness_v4.py`: best candidate per blade count under the final model; J in W, gated by self-start):

| candidate | baseline J_uniform / J_low-flow (min start) | Re / 1.5 | Re x 1.5 | upper-bound starting torque | hand-started J_uniform / J_low-flow |
|---|---|---|---|---|---|
| selected: B3 naca4412 TSR_d 1.5 x1.0 | 1.487 / 0.792 (0.6) | 1.264 / 0.647 (0.6) | 1.625 / 0.887 (0.6) | 1.514 / 0.841 (0.5) | 1.514 / 0.841 |
| best B2: B2 naca4412 TSR_d 2.0 x1.3 | 1.399 / 0.642 (0.7) | 1.238 / 0.557 (0.7) | 1.487 / 0.690 (0.7) | 1.480 / 0.788 (0.6) | 1.508 / 0.838 |
| best B3: B3 naca4412 TSR_d 1.5 x1.0 | 1.487 / 0.792 (0.6) | 1.264 / 0.647 (0.6) | 1.625 / 0.887 (0.6) | 1.514 / 0.841 (0.5) | 1.514 / 0.841 |
| best B4: B4 naca4412 TSR_d 2.5 x1.3 | 1.451 / 0.773 (0.6) | 1.251 / 0.648 (0.6) | 1.598 / 0.867 (0.6) | 1.478 / 0.821 (0.5) | 1.478 / 0.821 |
| best B5: B5 naca4412 TSR_d 2.5 x1.0 | 1.442 / 0.761 (0.6) | 1.200 / 0.608 (0.6) | 1.625 / 0.878 (0.6) | 1.467 / 0.805 (0.5) | 1.467 / 0.805 |

The margins between blade counts are a few percent, inside the polar uncertainty; the choice is therefore made on the baseline objective and
packaging, and the report does not claim that three blades are superior beyond that margin. The best candidate without the self-start gate
(hand-started at deployment) is {'B': 3, 'airfoil': 'naca4412', 'lam_d': 2.0, 'c_scale': 1.3}.

## 5. Selected blade geometry and why it won

3 blades, NACA 4412 outboard blending to NACA 4418 over the inner 35 % (printability and root bending), Schmitz planform at design
TSR 1.5 x1.0 (capped at 60 mm), root eased to 85 % at the hub, elliptical tip taper to 55 %, pitch offset -3 deg, 1.0 mm blunt trailing edge.
Station data: `model/selected_design.json` (chord 50.1 -> 60.0 -> 31.1 mm; twist 32.7 -> 10.6 deg). Figures 5 and 6 compare it with the
previous designs. It won because it (i) has the highest gated objective: under the baseline starting-torque model it self-starts from 0.6 m/s
(at 0.5 m/s it makes 29 mN m against 36 mN m of breakaway; the TSR >= 3 designs start later still), (ii) has the highest coupled output at
0.5-0.7 m/s once turning (Reynolds effect of the wide chord), (iii) stays within 4 % of the original rev-2 blade over 0.8-1.0 m/s, and (iv) fits 3 pockets on a
28 mm hub with 31 deg of wall between them. What it gives up: about 13 % at 2.0 m/s against the rev-2 blade and a higher
standstill drag (thrust at 2 m/s 38 N at the operating point).

## 6. Generator matching and electrical predictions

Feasibility first (`model/feasibility.py`, representative rotor, arrangement A unless noted; Cp pairs are A / B):

| V (m/s) | P through the disc (W) | through the annulus (A) | Betz on the annulus | BEM Cp (A / B) | rotor shaft (A) | lossless converter | buck-boost MPPT | boost + clamp (GVB-8 class) | rectifier to battery |
|---|---|---|---|---|---|---|---|---|---|
| 0.40 | 1.04 | 0.96 | 0.57 | 0.215 / 0.146 | 0.22 | 0.10 | 0.00 | 0.00 (mppt) | 0.00 |
| 0.50 | 2.03 | 1.87 | 1.11 | 0.234 / 0.160 | 0.47 | 0.28 | 0.14 | 0.18 (mppt) | 0.00 |
| 0.60 | 3.50 | 3.24 | 1.92 | 0.258 / 0.181 | 0.90 | 0.60 | 0.44 | 0.48 (mppt) | 0.00 |
| 0.70 | 5.56 | 5.14 | 3.05 | 0.277 / 0.199 | 1.54 | 1.05 | 0.86 | 0.89 (mppt) | 0.17 |
| 0.80 | 8.30 | 7.67 | 4.55 | 0.287 / 0.208 | 2.38 | 1.67 | 1.44 | 1.46 (mppt) | 1.08 |
| 0.90 | 11.82 | 10.92 | 6.47 | 0.294 / 0.216 | 3.48 | 2.48 | 2.20 | 2.20 (mppt) | 2.15 |
| 1.00 | 16.21 | 14.98 | 8.88 | 0.302 / 0.222 | 4.89 | 3.52 | 3.17 | 3.15 (mppt) | 3.38 |
| 1.25 | 31.67 | 29.26 | 17.34 | 0.313 / 0.234 | 9.91 | 7.24 | 6.68 | 6.54 (clamp) | 7.19 |
| 1.50 | 54.72 | 50.57 | 29.97 | 0.321 / 0.244 | 17.58 | 12.92 | 12.01 | 11.01 (clamp) | 12.06 |
| 2.00 | 129.72 | 119.87 | 71.03 | 0.333 / 0.255 | 43.22 | 30.26 | 28.31 | 22.34 (clamp) | 24.37 ! |

("!" = the generator current exceeds the 1.35 A rating in that mode: not allowed without a current limiter. Cp is referred to the full 203.2 mm disc; the
Betz column is 16/27 of the annulus power, so a Cp referred to the annulus would be higher by the disc/annulus area ratio 1.082.)

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
| 1.25 | 29.26 | 67 | 1.9 | 4.7 | 1.4 | 2.2 | 6.54 (22 %) | 394 rpm, 14.4 V, 0.50 A |
| 1.50 | 50.57 | 66 | 1.3 | 7.6 | 1.5 | 2.1 | 11.01 (22 %) | 444 rpm, 14.4 V, 0.84 A |
| 2.00 | 119.87 | 64 | 0.8 | 13.1 | 1.8 | 1.7 | 22.34 (19 %) | 577 rpm, 14.4 V, 1.69 A |

Gear ratio study (W: ideal converter / selected buck-boost / boost+clamp; "start" = induction-on starting torque above the geared breakaway at that flow):

| ratio | 0.5 m/s | 0.6 | 0.7 | 0.8 | 1.0 |
|---|---|---|---|---|---|
| 1:1 | 0.28 / 0.14 / 0.18 (no start) | 0.60 / 0.44 / 0.48 (no start) | 1.05 / 0.86 / 0.89 (no start) | 1.67 / 1.44 / 1.46 (start) | 3.52 / 3.17 / 3.15 (start) |
| 2:1 | 0.18 / 0.04 / 0.09 (no start) | 0.52 / 0.36 / 0.40 (no start) | 1.06 / 0.86 / 0.89 (no start) | 1.74 / 1.51 / 1.52 (no start) | 3.79 / 3.43 / 3.05 (start) |
| 3:1 | 0.11 / 0.00 / 0.01 (no start) | 0.44 / 0.28 / 0.19 (no start) | 0.99 / 0.80 / 0.31 (no start) | 1.71 / 1.47 / 0.43 (no start) | 3.81 / 3.46 / 0.73 (start) |

Selected design, per flow (buck-boost MPPT; boost+clamp and direct-to-battery for comparison; standstill torque vs breakaway):

| V (m/s) | buck-boost: rpm / V_dc / I / net W | boost + clamp: net W (region) | direct to battery: net W | open-circuit runaway | static torque / breakaway (mN m) |
|---|---|---|---|---|---|
| 0.40 | 0 / 0.0 / 0.00 / 0.00 | 0.00 (-) | 0.00 | 133 rpm, 6 V | 19 / 36 |
| 0.50 | 129 / 5.0 / 0.06 / 0.16 | 0.21 (mppt) | 0.00 | 186 rpm, 9 V | 29 / 36 |
| 0.60 | 150 / 5.7 / 0.12 / 0.49 | 0.52 (mppt) | 0.00 | 237 rpm, 11 V | 42 / 36 |
| 0.70 | 184 / 6.9 / 0.17 / 0.96 | 0.99 (mppt) | 0.00 | 290 rpm, 14 V | 57 / 36 |
| 0.80 | 221 / 8.3 / 0.22 / 1.60 | 1.61 (mppt) | 0.50 | 346 rpm, 16 V | 75 / 36 |
| 0.90 | 254 / 9.4 / 0.29 / 2.43 | 2.42 (mppt) | 1.80 | 401 rpm, 19 V | 95 / 36 |
| 1.00 | 291 / 10.6 / 0.36 / 3.45 | 3.42 (mppt) | 3.25 | 454 rpm, 21 V | 118 / 36 |
| 1.25 | 383 / 13.5 / 0.56 / 6.98 | 6.88 (mppt) | 7.53 | 592 rpm, 28 V | 188 / 36 |
| 1.50 | 486 / 16.7 / 0.77 / 12.02 | 11.59 (clamp) | 12.69 | 730 rpm, 34 V | 276 / 36 |
| 2.00 | 704 / 23.0 / 1.27 / 27.23 | 23.11 (clamp, I 1.75 A OVER) | 25.21 (I 1.75 A OVER) | 999 rpm, 46 V | 503 / 36 |

Load control. Below the clamp voltage both converters regulate the bus, i.e. the rotor speed, so the generator cannot stall the rotor:
the equilibrium sits on the stable side of the torque peak (fig. 9). With the boost-only converter the bus is clamped at the battery
above about 1.5 m/s; the rotor is then held at a fixed speed and, from 1.8 m/s (interpolated on a 0.05 m/s grid), the clamp current exceeds the GL60 rating:
a boost-only unit needs a 1.5-2 A limiter or a 40 V relay dump for the 1-2 m/s survivability case. The buck-boost keeps regulating to
2 m/s (1.27 A at 23.0 V). Open circuit at 2 m/s is 46 V: below the 60 V TVS standoff and the converter's 60 V input.
Current and temperature: copper loss is 0.02 / 0.15 / 0.70 W at 0.5 / 0.7 / 1.0 m/s and 8.8 W at 2 m/s inside a sealed nacelle. Thermal limits are not
the sizing case below 1.5 m/s; the earlier v3.1 heat-path analysis applies if the device is left in a 2 m/s flow (rear cap in 6061).

## 7. Recommended compact mounting and waterproofing (arrangement A), with B quantified

| | A: rotor on a short shaft, stationary nacelle behind | B: hub-integrated (v3.1 drum rotor) |
|---|---|---|
| hub radius / ratio | 28 mm / 0.28 | 48.2 mm / 0.47 (the GL60 inside a 3 in drum) |
| net W at 0.5 / 0.7 / 1.0 m/s (same blade) | 0.16 / 0.96 / 3.45 | 0.00 / 0.54 / 2.40 |
| rotary seal | one 8 mm PTFE lip seal (run 4 mN m assumed) | one 15 mm PTFE lip seal (7.5 mN m) |
| bearings | one 608-2RS in the cap + the GL60's own | two 6702-2RS |
| machined parts | shaft, front cap, rear cap, tube ends (4) | spindle, 2 caps, split ring, plug, boss, 3 struts, tube ends (9+) |
| waterproof boundary | tube + 1 O-ring per cap + lip seal + WetLink + vent | tube + O-rings + lip seal + potting plug |
| operating depth | 136 mm; packs as 72 + 75 mm | 73 mm |
| flow obstruction behind the rotor | 3 in nacelle (14 % of the disc area), modelled as a 15 % inflow deficit inboard of r 38 mm | none beyond the drum itself |
| seal service | pull the hub (one screw), press the seal from the wet face | partial disassembly (v3.1 plan) |

**Load path (A, fig. 10a).** Thrust: blade -> airfoil tongue (clamped between the two hub halves by an axial M3) -> hub -> 316 washer ->
circlip A (DIN 471-8) -> rotor shaft -> its shoulder on the stub's front face (the M5 joint is in tension only under handling loads) -> stub shaft ->
collar B (between the seal and the bearing) -> 608 inner race -> outer race -> DIN 472-22 internal ring in the cap boss -> cap plug and flange -> front
flange -> front lip of the shell clamp -> three L-struts -> guard ring and stake. Reverse load: DIN 471-8 circlip behind the bearing (0.3 mm end play)
-> inner race -> outer race -> bearing press fit (N7) in the boss; the rear flange is held by the shell's rear lip; the only forward loads are handling
and a snagged cable. Assembly order: seal pressed from the wet face; stub in from the dry side (collar B passes through the 22 mm bore, the 8 mm
journal through the seal with a bullet); bearing pressed over the tail to collar B; DIN 472-22 ring; rear circlip; dog hub pinned; caps into the
tube; shell clamp closed (4x M4). Rotor: circlip A and washer on the rotor shaft, hub halves and blades bolted, nose screw and plug; the rotor
screws onto the stub (M5, right-hand: the generator reaction torque tightens it; Loctite 222) and unscrews for packing.
The mechanical review (M-C1..C4, M-M1..M11) found the first draft's integral collar A and collar-inside-the-seal layout uninstallable, the cap bore
without a thrust shoulder, the dog coupling not engaging, the hub and both caps unretained and the packing claim false (captive shaft); this is the
corrected arrangement. Single rotor bearing (review M4, accepted with analysis): the rotor's centre of mass sits 38 mm ahead of the bearing
centre; the radial clearance of a 608 (0.005-0.012 mm) allows 1.4-3.4 mrad of tilt, i.e. 0.20-0.48 mm at the blade tip,
0.035 mm at the seal lip and 0.032 mm at the dogs (0.2 mm radial clearance), with the rotor thrust pre-loading the bearing axially; the
GL60 therefore stays radially unloaded and gate G5 measures the tip motion (a second bearing, 698 in a 7 mm longer boss, is the fallback). Hub
retention: the M3 nose screw clamps the hub between its 13 mm washer on the hub floor (10.4 MPa under 0.5 N m) and circlip A
(0.38 MPa on the hub rear face at 2 m/s thrust). Hub bolts: M3 x 40 in 7.5 mm counterbores from the nose surface, 7 mm washers at both
ends, nylocs in 5.5 mm rear pockets, 0.2 N m (11 MPa under the washers). Stake socket: 40 mm engagement, 4 mm wall, 1.7 MPa peak
bearing pressure under 7.2 N m (device drag taken as 1.25x the rotor thrust at 2 m/s); guard ring 6 mm wall, 0.14 mm/N in-plane compliance
against a 5.4 mm tip gap (gate G10). Minimum deployment depth with the socket below the ring is about 0.35 m (socket mouth +
30 mm of exposed stake + ring + 50 mm freeboard); a two-stake yoke or a base plate is the shallow-water alternative (not designed). Torque: hub D-bore -> shaft D-flat -> cross-pinned dog hub -> TPU disc (two dogs, 0.2 mm radial clearance) -> GL60 bell; the
stator is screwed to the rear cap. The GL60 carries no rotor thrust and no radial load. The motor is dry: tube, one EPDM O-ring per cap,
an 8 mm PTFE lip seal on the polished 316 journal, a WetLink M10 penetrator and an M6 vent; IP45 is irrelevant inside that boundary.
**Penalties quantified:** the seal and bearing take 7 mN m of the 38 mN m the rotor makes at 0.5 m/s (19 %) and 4 % at 1.0 m/s;
the assumed nacelle inflow deficit costs 1.8 / 1.7 / 1.8 % of peak Cp at 0.5 / 0.7 / 1.0 m/s (to be checked in G8/G11); the hub ratio 0.28 costs the annulus area shown in the feasibility table.

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

Net power once turning (hand-started where the model predicts no self-start); the last column is the model's minimum self-start flow in that case.

| case | 0.5 | 0.6 | 0.7 | 0.8 | 1.0 m/s | min self-start (m/s) |
|---|---|---|---|---|---|---|
| baseline | 0.16 | 0.49 | 0.96 | 1.60 | 3.45 | 0.6 |
| seal x0.5 | 0.18 | 0.51 | 0.98 | 1.63 | 3.49 | 0.6 |
| seal x2.0 | 0.12 | 0.45 | 0.91 | 1.54 | 3.38 | 0.7 |
| seal x3.0 | 0.09 | 0.40 | 0.86 | 1.48 | 3.31 | 0.7 |
| cogging 8 mN m | 0.16 | 0.49 | 0.96 | 1.60 | 3.45 | 0.5 |
| cogging 40 mN m | 0.16 | 0.49 | 0.96 | 1.60 | 3.45 | 0.7 |
| no-load loss 0.2 W@700 | 0.18 | 0.51 | 0.99 | 1.63 | 3.50 | 0.6 |
| no-load loss 1.5 W@700 | 0.11 | 0.42 | 0.87 | 1.49 | 3.29 | 0.6 |
| cd x1.3 | 0.11 | 0.42 | 0.87 | 1.48 | 3.26 | 0.6 |
| cd x1.6 | 0.07 | 0.36 | 0.79 | 1.37 | 3.08 | 0.6 |
| cl x0.9, cd x1.3 | 0.11 | 0.41 | 0.86 | 1.47 | 3.22 | 0.6 |
| Re / 1.5 (earlier transition) | 0.06 | 0.35 | 0.76 | 1.33 | 3.05 | 0.6 |
| Re x 1.5 | 0.24 | 0.59 | 1.09 | 1.76 | 3.68 | 0.6 |
| high-induction model: Glauert-Spera | 0.19 | 0.55 | 1.06 | 1.75 | 3.73 | 0.6 |
| high-induction model: uncorrected momentum | 0.16 | 0.48 | 0.95 | 1.59 | 3.42 | 0.6 |
| standstill = no-induction estimate (upper bound) | 0.16 | 0.49 | 0.96 | 1.60 | 3.45 | 0.5 |
| no nacelle inflow deficit | 0.17 | 0.50 | 0.98 | 1.63 | 3.52 | 0.6 |
| nacelle inflow factor 0.70 inboard of r 38 mm | 0.16 | 0.48 | 0.94 | 1.57 | 3.39 | 0.6 |
| nacelle inflow factor 0.60 inboard of r 38 mm | 0.15 | 0.47 | 0.93 | 1.56 | 3.36 | 0.6 |
| KV 25 (Kt 0.38) | 0.11 | 0.45 | 0.89 | 1.49 | 3.17 | 0.6 |
| KV 26.2 (line-line-peak reading of 'KV 25') | 0.08 | 0.43 | 0.87 | 1.44 | 3.08 | 0.6 |
| R 6.5 ohm | 0.16 | 0.48 | 0.93 | 1.55 | 3.33 | 0.6 |
| conv eta 0.85 | 0.14 | 0.43 | 0.85 | 1.43 | 3.11 | 0.6 |
| conv eta 0.96 | 0.21 | 0.54 | 1.02 | 1.68 | 3.57 | 0.6 |
| converter fixed overhead 0.20 W | 0.09 | 0.42 | 0.89 | 1.53 | 3.38 | 0.6 |
| converter fixed overhead 0.30 W | 0.00 | 0.32 | 0.79 | 1.43 | 3.28 | 0.6 |
| converter fixed overhead 0.50 W | 0.00 | 0.12 | 0.59 | 1.23 | 3.08 | 0.6 |
| conv Vmin 3 V | 0.17 | 0.49 | 0.96 | 1.60 | 3.45 | 0.6 |
| conv Vmin 8 V | 0.00 | 0.36 | 0.93 | 1.60 | 3.45 | 0.6 |
| rectifier synchronous | 0.21 | 0.55 | 1.05 | 1.73 | 3.68 | 0.6 |

Minimum self-start / sustain velocities: baseline 0.6 / 0.5 m/s; optimistic (upper-bound starting torque, cogging 8 mN m, seal x0.5, Re x1.5, Glauert-Spera)
0.4 / 0.4; pessimistic (cogging 40 mN m, Re/1.5, uncorrected momentum, 0.30 W converter overhead, seal x2) 0.8 / 0.6; baseline with the upper-bound
starting torque 0.5 / 0.5. Net power in the pessimistic combination: 0.00 / 0.53 / 2.75 W at 0.5 / 0.7 / 1.0 m/s; optimistic
0.30 / 1.24 / 4.01 W. A self-start at 0.5 / 0.6 / 0.7 m/s requires the measured GL60 cogging to be below
17 / 30 / 45 mN m (gate G1).
The sweep evaluated candidates with 40 elements and a 0.5 TSR step; the selected design is re-evaluated here with 50 elements and a 0.2 step, which moves
its numbers by 0.4 % at most over 0.6-1.0 m/s; "root chord" is the chord at the first element centre (r 28.7 mm). The sustain floor is the converter's 5 V minimum; a 3 V converter would move it to
0.5 m/s with 0.17 W at 0.5 m/s.

Converter overhead and generator convention (reviews M5, M6). The converter's fixed overhead (gate drive, housekeeping, quiescent) is assumed
0.13 W; it takes 48 % of the DC power at 0.5 m/s, and with 0.20 / 0.30 / 0.50 W of overhead the net output at 0.5 m/s is 0.09 / 0.00 / 0.00 W
(0.7 m/s: 0.89 / 0.79 / 0.59 W): the 0.5-0.6 m/s numbers are conditional on a converter with <= 0.15 W of overhead (gate G9). The generator convention
(V_oc,dc = rpm / KV with KV 21.5 from the listed 516 rpm at 24 V) is 4.5 % optimistic against a 3-phase bridge average; if the listed "KV 25" is rpm per volt of
line-line peak EMF, the rectified constant is about 26.2 and the output falls to 0.08 / 0.87 / 3.08 W at 0.5 / 0.7 / 1.0 m/s. Gate G1 measures V_dc/rpm through the bridge.

## 9. Reproducible source code and CAD exports

`model/polars.py` (polar tables), `bem_lowflow.py`, `generator_lowflow.py`, `feasibility.py`, `optimize_blades.py` (stages 1-2 and the
selection), `coupled_eval.py` (figures 2-9, comparison, sensitivities); `cad/make_v4.py` (parametric assembly, STEP per part, assembly
STEP, print-oriented STLs with the blade meshed as a closed structured surface), `cad/views_v4.py` (figure 10); `tools/qa_gates_v4.py`.
Exports: `out/v4_assembly.step`, `out/v4_*.step` (37 parts, 16 printed, 5 machined), `out/v4_*_PRINT.stl` (13 files, all closed,
blade mesh within 0.07 % of its STEP volume, tilted -4.0 deg for a level pressure face). Regenerate in the order given in `README.md`.
Print notes: blades pressure-side down on a raft with full tree supports under the pressure side (the review measured 4,228 mm2 of
down-facing surface inside 45 deg and a 27 mm2 line of bed contact: the twisted blade cannot be levelled; the alternative root-down print puts
the root bending across the layers, 1.9 MPa against the assumed 2.7 MPa interlaminar allowable), 100 % infill, layers along the span;
hub halves parting face down (the pockets print as bridged tunnels: gate G3 uses the real hub half), no supports; TPU disc flat; shell
halves on the parting plane; struts on the flat of the leg; ring arcs on an end face (each arc fits a 220 mm bed; scale the arcs 100.5 % for
ASA shrink and check the tip gap). Fasteners modelled: hub bolts, hub screw, circlips, rings, pin; listed but not modelled: shell M4 x 35, strut
M4 x 12 + inserts, ring M3 x 10 + inserts, stator screws. Minimum blade thickness 3.7 mm at the tip
(12 % of 31.1 mm), 1.0 mm trailing edge.

**Structural screening at the 2 m/s survival case** (`model/structure_v4.py`; allowables assumed: ASA 8 / 4.5 MPa long-term in-plane / across
layers, 15 / 8 short-term, 2.7 / 4.8 interlaminar shear): rotor thrust 37.8 N (12.6 N per blade) and 0.55 N m at 704 rpm, runaway 999 rpm.
Root bending 1.89 MPa in the 9.0 mm thick NACA 4418 root (in-plane for a flat print); centrifugal 20 N per blade (26 g) -> M3 bolt double shear
1.4 MPa, tongue bearing 0.48 MPa, 4.2 mm ligament shear-out 0.17 MPa; pocket walls take the flap moment at 1.03 MPa; the three
pockets span 89 deg each, leaving 31 deg of hub wall (8.7 mm at the pocket floor, 15.2 mm at the surface); strut legs 2.9 MPa in bending;
shaft torsion 5.5 MPa (8.2 at the D-flat; 316 yield ~200); 608 bearing Fa/C0 0.027. All below the allowables with margin; fatigue (3/rev strut wake) is not assessed.

## 10. Independent adversarial review and corrections

# Independent adversarial review and corrections (v4 low-flow turbine)

Three reviewer agents, each a separate model instance with its own scratch directory and no write access to the package, reviewed the
exported first draft (commit 2add8bd): (1) hydrodynamics / BEM / electrical, (2) mechanical / CAD / deployment, (3) model implementation and
numerics. They re-computed numbers independently (own scripts under /home/user/review_v4_*). Their findings, the corrections and the
re-verification on the regenerated results are listed below. "Independent" here means a separate reviewer instance and separate
re-computation, not a separate physical method or an experiment: nothing has been measured.

| ID | Pass | Severity | Finding (reviewer's evidence) | Correction | Re-verification on the regenerated files |
|---|---|---|---|---|---|
| C-M1 | code | major | coupled_eval evaluated the 'direct to battery' case as an unlimited-window lossless MPPT (mode 'mppt' with V_min 0, V_max 1e9) instead of a fixed 14.4 V bus; the report's executive summary and the section-6 table were wrong (e.g. 1.18 W instead of ~0.09 W at 0.7 m/s). | full_eval selects mode 'cv' whenever the converter has a fixed bus voltage; the CV equilibrium is now solved by bisection on Vdc(lambda) = V_fixed (generator_lowflow._cv_solve). | direct-to-battery now 0.00 / 0.00 / 0.00 / 3.25 W at 0.5 / 0.6 / 0.7 / 1.0 m/s (first non-zero at 0.8 m/s), consistent with feasibility.json |
| C-M2 | code | major | The 'rectifier synchronous' sensitivity was a no-op: the Schottky dict was bound as a default argument at import, so swapping the module-level entry changed nothing; the sensitivity row printed the baseline. | rect is passed explicitly from full_eval to operating_point/gen_point. | synchronous rectifier now 0.21 / 1.05 / 3.68 W vs baseline 0.16 / 0.96 / 3.45 W (+27 % at 0.5 m/s): the largest single upside in the table |
| C-M3 | code | major | The coded selection rule (no root-chord limit) would have picked the TSR 1.75 / 57 mm-root design, not the shipped one; selection.json was written by an ad-hoc step, so 'python optimize_blades.py 2' did not reproduce selected_design.json. | The root chord <= 52 mm packaging constraint is encoded in optimize_blades stage 2, which now writes selection.json (rule, ranked list, unconstrained best); a QA gate re-applies the rule to the stored sweeps. | stage 2 re-run selects {'B': 3, 'airfoil': 'naca4412', 'lam_d': 1.5, 'c_scale': 1.0, 'c_max': 0.06, 'dbeta': -3.0} (score 0.9808); unconstrained best {'B': 4, 'airfoil': 'naca4412', 'lam_d': 1.5, 'c_scale': 1.3, 'c_max': 0.06, 'dbeta': -3.0}; QA gate 'selection reproducible' PASS |
| C-M4 | code | major | QA gate 7 only checked that the report generator existed; five typed statements were wrong or unsupported (copper '< 0.1 W' at 0.7-1.0 m/s; 'two blades cannot self-start below 0.6'; 'nacelle deficit costs 3 % of Cp'; '1.75 m/s' clamp over-current; the '-30 % / +10 %' band). | Gate 7 now scans the report text for numeric literals with result units outside f-string expressions; the five statements are computed (copper per flow, two-blade start and score, nacelle Cp cost with/without the deficit, clamp current scanned on a 0.05 m/s grid, band from the one-at-a-time envelope). | copper 0.02 / 0.15 / 0.70 W; nacelle Cp cost 1.8 / 1.8 %; clamp over-current from 1.8 m/s; band at 0.7 m/s -39 / +14 %; gate 7 PASS |
| C-M5 | code | major | The self-start verdict rests on a no-induction standstill estimate 1.5-1.7x the BEM torque at TSR 0.2, with the Viterna cdmax (1.8) fixed and absent from the sensitivity study; the verdict flips between cdmax 1.2 and 2.0. | Superseded by H-C1: the BEM torque at TSR 0.1 (induction on) is the baseline starting torque everywhere; the no-induction estimate is carried only as an upper-bound sensitivity and combination. | min self-start: baseline 0.6, optimistic 0.4, pessimistic 0.8, baseline with the upper-bound torque 0.5 m/s; at 0.5 m/s: BEM 29 vs upper bound 51 mN m |
| C-m1 | code | minor | Gear study evaluated the motor no-load loss at rotor rpm instead of N x rpm. | friction_running takes N; feasibility re-run. | gear 2:1 with the boost converter: 0.09 W at 0.5 and 3.05 W at 1.0 m/s vs direct drive 0.18 / 3.15 W (conclusion unchanged) |
| C-m2 | code | minor | gen_point returned a non-physical point when the torque exceeded the pull-out limit (disc < 0). | returns None; callers skip. | no such point reached at any operating point (all points pass the balance gate) |
| C-m3 | code | minor | The CV equilibrium used a nearest-grid-point acceptance window (+-0.3 V) that could miss the point at a coarser grid. | replaced by bisection on the fine grid (highest-lambda crossing = stable branch). | boost-clamp and direct cases re-solved; clamp branch at 1.25-2.0 m/s unchanged within 0.5 % |
| C-m4 | code | minor | Sweep (40 elements, 0.5 TSR step) and final evaluation (50 elements, 0.2 step) differ in the second decimal. | stated in the report (section 8). | 3.61 (sweep) vs 3.45 W (final) at 1.0 m/s |
| C-m5 | code | minor | 13 duplicate stage-2 candidates (c_max 60 vs 68 identical when the chord never reaches 60). | left as is; noted. | - |
| C-m6 | code | minor | Polar.best() comment described a 0.97 x L/D rule the code did not implement (function unused by the model). | comment corrected. | - |
| C-m7 | code | minor | The original rev-2 blade (NACA 4422 -> 4414) is evaluated with the NACA 4415 table. | stated in the report (section 2). | - |
| C-m8 | code | minor | Converter sensitivity overrides mutated a module-level dict. | each override gets its own key. | - |
| C-m9 | code | minor | Three QA gates were identity/regression checks presented as independent validation. | relabelled; a genuinely independent gate (selection reproducibility from the stored sweeps) added. | 22 gates, 0 failing |
| H-C1 | hydro | critical | The self-start verdict rested on a no-induction, 2-D flat-plate standstill torque (40.5 mN m at 0.5 m/s) that the package's own BEM contradicts by 1.8x (22.9 mN m at TSR 0.02-0.2); independent estimates (finite-plate normal force, Viterna cdmax from the aspect-ratio rule, induction) all give 18-26 mN m. The 14 % start margin was inside a -45 % model error. | The BEM torque at TSR 0.1 (induction on) is now the BASELINE starting torque in the sweep gating, the selection and the final evaluation; the no-induction value is reported as an upper bound only; fig. 3 is drawn without the kink; the cogging torque that would still allow a start at each flow is computed. | baseline start 0.6 m/s (upper-bound model 0.5); at 0.5 m/s: BEM 29 vs upper 51 mN m vs breakaway 36; a start at 0.5 / 0.6 / 0.7 m/s needs cogging <= 17 / 30 / 45 mN m |
| H-M1 | hydro | major | The -30 %/+10 % band was far too narrow at 0.5-0.6 m/s: the 0.5 m/s point sits on the polar 'cliff' (NACA 4412 best L/D 10 at Re 4e4 vs 39 at 6e4); shifting the transition Reynolds number by 1.5 moves the 0.5 m/s output by -62 %/+46 %. | Re/1.5 and Re x1.5 sensitivities added (polar lookup Reynolds number scaled); the band is now computed per flow from the full one-at-a-time envelope and quoted per flow. | band -100/+45 % at 0.5, -39/+14 % at 0.7, -12/+8 % at 1.0 m/s; Re/1.5: 0.06 / 3.05 W at 0.5 / 1.0 |
| H-M2 | hydro | major | The 3-vs-2-blade margin (4 %) is inside the polar uncertainty and the selection flips under the corrected start gate (TSR 1.75 three-blade or five-blade designs win when self-start at 0.5-0.6 m/s is required). | Both sweep stages re-run with the corrected start gate and a per-blade-count hub-packaging constraint; stage 2 broadened to 3/4/5 blades; the selection and the hand-started alternative are both reported; model/robustness_v4.py re-evaluates the best candidate per blade count under the baseline, Re/1.5, Re x1.5 and the upper-bound start model. | see REPORT section 4 (robustness table) and selection.json |
| H-M3 | hydro | major | Same as C-M1 (direct-to-battery column evaluated as an ideal MPPT). | fixed (full_eval mode 'cv'). | see C-M1 |
| H-M4 | hydro | major | At every MPPT point 19-22 of 50 elements run above a = 0.4, so the empirical high-induction correction is load-bearing: Glauert-Spera gives +16-19 %, uncorrected momentum -5-10 %; this model-form uncertainty was absent from the sensitivity study. | The BEM carries a selectable high-induction model (Buhl baseline, Glauert-Spera, uncorrected momentum); both alternatives are in the sensitivity table and in the optimistic/pessimistic combinations. | Spera 1.06 W / momentum 0.95 W vs baseline 0.96 W at 0.7 m/s |
| H-M5 | hydro | major | The converter's fixed overhead (0.13 W assumed) decides the 0.5 m/s number (47 % of the DC power there) and is unsubstantiated for a 4-switch buck-boost module (0.1-0.3 W is common). | Fixed-overhead sensitivities 0.20 / 0.30 / 0.50 W added; the pessimistic combination uses 0.30 W; the 0.5-0.6 m/s output is stated as conditional on <= 0.15 W; gate G9 measures it. | overhead 0.20 / 0.30 / 0.50 W -> 0.09 / 0.00 / 0.00 W at 0.5 m/s; 0.79 W at 0.7 |
| H-M6 | hydro | major | Generator-constant convention: V_oc,dc = rpm/KV with KV 21.5 and Kt = 60/(2 pi KV) is 4.5 % inconsistent with a 3-phase bridge (3/pi of the line-line peak); if the listed 'KV 25' is rpm per volt of line-line peak EMF the rectified constant is ~26.2 (-27 % at 0.5 m/s). | KV 26.2 sensitivity added; gate G1 now requires V_dc,oc/rpm measured THROUGH the bridge. | KV 26.2 -> 0.08 / 3.08 W at 0.5 / 1.0 m/s |
| H-M7 | hydro | major | The gear study judged N = 2, 3 with the ideal and boost+clamp converters, not the selected buck-boost; with the buck-boost a 2:1 stage is -22 % at 0.5 m/s and +2 to +9 % at 0.7-1.0 m/s (a wash under the low-flow weighting); the decisive reason is the added breakaway (self-start). | Gear table re-run with the buck-boost column and a self-start flag per ratio; the executive summary states the breakaway reason. | 2:1 buck-boost 0.04 / 3.43 W vs direct 0.14 / 3.17 W at 0.5 / 1.0; self-start with 2:1 at 0.7 m/s: False |
| H-m1 | hydro | minor | The friction share sentence omitted the motor no-load loss and windage (running friction is 27 % of shaft power at 0.5 m/s, not 19 %). | sentence computed from Pfric/Pshaft. | friction 27 % of shaft power at 0.5 m/s |
| H-m3 | hydro | minor | The '+745 % at 0.5 m/s vs rev-2' compared against a 0.02 W point pinned at the converter floor; the shaft-power ratio is +45 %. | both ratios are stated. | - |
| H-m4 | hydro | minor | The feasibility table mixes Betz on the annulus with Cp on the full disc. | Cp on the annulus added to the table caption. | - |
| H-m8 | hydro | minor | 'The MPPT never commands more than 1.35 A' is a requirement on the converter, not a property of COTS units. | stated as a requirement (BOM 26, gate G10). | - |
| H-ok | hydro | - | Verified correct by independent re-derivation: BEM discretisation converged (n 25-200, TSR step 0.5-0.05: <= 1.5 %), Prandtl/Ning/Buhl forms, generator equations and the MPPT equilibria (within 1.4 %), stability at fixed bus voltage (the generator cannot stall the rotor), hydraulic accounting to the cent, open-circuit 54 V at 2 m/s, report arithmetic. | - | - |
| M-C1 | mech | critical | Collar B (12 mm, the bearing thrust stop) sat inside the 8x22x7 lip seal's envelope (shaft/lip_seal interference 231 mm3 in the assembly STEP; the package's own clash check excluded the seal), and with an integral collar A ahead of the seal the shaft could not be installed through an 8 mm seal bore from either end; BOM line 7 and section 7 described an impossible assembly. | Two-piece shaft: a captive stub (seal journal, collar B between the seal and the bearing, enters the 22 mm bore from the dry side; the bearing is pressed over its tail) and a rotor shaft (D-flat, DIN 471-8 circlip A + 316 washer as the hub thrust stop, 6 h7 spigot + M5 male thread into the stub). The seal is in the clash check with its lip interference as the only allowed overlap. | regenerated: stub/lip_seal overlap 42.49 mm3 vs the lip annulus 42.49 mm3 (ok=True); other interferences {}; collar B at x [35.1, 38.1] vs bearing from x 38.2; stub face to circlip A 1.0 mm |
| M-C2 | mech | critical | The front-cap bore was a plain 22 mm through-bore in an 11 mm cap: the 608 bearing overhung the cap by 3 mm and nothing but its press fit took the rotor thrust (35-49 N); the 'front-cap floor' named in the load path did not exist; end play was 0.3 mm, not 0.2. | Rear boss (30 OD) on the front cap housing the whole bearing, DIN 472-22 internal-ring groove behind the bearing as the thrust shoulder; load path, end play (0.3 mm) and assembly order rewritten in section 7. | regenerated: bearing x 38.2-45.2, ring groove at x 45.300000000000004, boss end x 47.400000000000006; nacelle depth 74.9 mm (budget 76) |
| M-C3 | mech | critical | The dog coupling never engaged: the dog tips ended 2.0 mm short of the TPU disc (ic_front was applied between the dog tip and the disc face), so there was no torque path to the GL60 and every electrical prediction was moot. | Bell position = dog-hub face + 1.0 mm gap + disc; dogs 3.0 mm into a 2.5 mm disc (2.0 mm engagement, 0.5 mm clearance to the bell); QA gate on the engagement added. | regenerated: engagement 2.0 mm, dog tip to bell 0.5 mm; TPU bearing stress at 0.55 N m: 2.3 MPa |
| M-C4 | mech | critical | The hub was not retained on the shaft: the shaft end stood 2.0 mm proud of the hub's front pocket floor, so the M4 washer never touched the hub; the hub could slide forward off the slip D-bore whenever thrust was absent (carrying, lowering, surge); the M4 tap under the D-flat left 1.0-1.35 mm of 316. | Rotor-shaft tip 0.5 mm below the hub floor; 14.5 mm nose access hole; M3 x 10 screw with a 13 x 1.5 washer clamping the hub between the washer and circlip A. | regenerated: shaft tip at x -13.5 vs hub front floor at x -14.0 (-0.5 mm below); washer pressure on the floor 10.4 MPa at 0.5 N m; circlip-A washer pressure on the hub 0.38 MPa at 2 m/s |
| M-M1 | mech | major | Hub bolts could not be fitted: the 3.4 mm holes exited the nose obliquely with no head seat (the counterbore line was dead code), the modelled bolt started inside solid material, and the nut pocket (6.0 x 3.2) was smaller than an M3 nyloc + washer; at 0.5 N m the 7 mm washers would load the ASA to 28 MPa. | 7.5 mm counterbores from the nose surface to a seat 3.5 mm ahead of the hub body; 7.5 x 5.5 rear nut pockets; M3 x 40 with 7 mm washers at both ends at 0.2 N m; bolts, washers, heads and nuts are modelled and in the clash check. | regenerated: counterbore 7.5 mm to x -17.5, nut pocket 7.5 x 5.5 mm, bolt length 40.0 mm; washer pressure 11 MPa at 0.2 N m |
| M-M2 | mech | major | The WetLink M10 bore, the M6 vent and the lead channel lay on the stator's hole lines (0 / 180 deg): a section at x 88.5 showed the holes at (0, +-20) and (0, +-25) merged into the penetrator and vent voids, so two screws per pattern had no material; with the stator 1.0 mm from the cap, the penetrator's dry side, the splice and the 6 mm cable had no room. | Penetrator at r 19 on the 45 deg line (22 mm counterbore, 4 mm wall to the O-ring groove), vent at 225 deg, lead channel deleted; stator-to-cap gap 4.5 mm with a 20 x 4 splice pocket in the cap centre; an ASSUMED 12 x 3 mm inner protrusion of the penetrator is modelled and clash-checked against the stator. | regenerated: nearest stator hole centre to the penetrator centre 15.0 mm (wall 2.7 mm); penetrator protrusion to stator 1.5 mm |
| M-M3 | mech | major | Neither cap was retained in the tube (only O-ring friction): the test plan's +20 kPa leak test would push 83 N on each plug, and a snagged cable would pull the rear cap out; the clamp did not touch either flange, so the thrust path 'tube -> clamp' was friction only. | Full-length printed shell clamp (two halves, 4x M4 lugs) whose end lips trap both cap flanges (now 80 mm diameter): positive thrust stop on the front flange, retention of both caps, and the strut bosses on the shell. | regenerated: shell x [25.0, 97.2] vs front flange at x 28.0 and rear face at x 94.2; front lip to hub rear face 3.0 mm |
| M-M4 | mech | major | One 608 is the only rotor support, ~40 mm behind the rotor CG; its radial clearance (5-12 um) allows 1.4-3.4 mrad of tilt (0.2-0.4 mm at the tip), moment loads of ~0.1-0.3 N m, a seal running on a tilting shaft and dogs loading the GL60 bell. | Accepted with analysis (a second bearing does not fit the 76 mm budget): the rotor thrust pre-loads the bearing axially; tilt, tip motion, seal eccentricity and dog motion are computed in structure_v4.py and bounded by gate G5 (dial indicator with a 10 N side load); the fallback is a 698 in a 7 mm longer boss. | regenerated: overhang 38 mm, tilt {'0.005': 1.4285714285714286, '0.012': 3.428571428571429} mrad, tip motion {'0.005': 0.199, '0.012': 0.4776000000000001} mm, seal eccentricity {'0.005': 0.014571428571428575, '0.012': 0.034971428571428584} mm, dog motion {'0.005': 0.013142857142857147, '0.012': 0.03154285714285716} mm vs 0.2 mm radial clearance; moments 0.072 (weight) + 0.15 (assumed inflow asymmetry) N m |
| M-M5 | mech | major | The packing claim was false: the shaft was captive (collar B ahead of the bearing, circlip behind), so the nacelle with its shaft spanned 120.9 mm, not 74.9; the rotor with bolts was 61.5 mm; the ring + struts (103.7 mm) were not counted. | Two-piece shaft (M5 joint ahead of the cap): the rotor assembly carries its own shaft, the stub stays in the nacelle; depths are measured from the part bounding boxes of each group, bolts included; the support set is reported separately. | regenerated: rotor assembly 72.5 mm (nose plug to thread end), nacelle 74.9 mm (stub face to penetrator nut), operating 136.4 mm; support parts {'shell_top': [72.2, 112.0, 48.0], 'strut_0': [106.2, 40.3, 73.9], 'duct_1': [40.0, 195.7, 99.5]} (x, y, z extents), thickest 61 mm |
| M-M6 | mech | major | Clamp, struts and ring had no fasteners or joints: the clamp halves had no lugs or holes, the ring was a single 232 x 218 mm body (no 220 mm bed takes it), the lap joints and strut-to-ring screws existed only in comments, and thrust entered the clamp by friction. | Shell with 4 M4 lugs and three strut bosses (M4 heat-set inserts); three separate L-struts (identical print) whose curved feet splice the three ring joints with 4x M3 into heat-set inserts in the arcs; ring as three 120-deg arcs; all holes modelled, screws listed in the BOM (not modelled). | regenerated: arc extents [40.0, 195.7, 99.5] mm (bed <= 220), strut [106.2, 40.3, 73.9] mm, shell half [72.2, 112.0, 48.0] mm; 595 part pairs clash-free |
| M-M7 | mech | major | Stake socket: 16 mm engagement and 2.9 mm wall gave 9.7 MPa peak bearing pressure (> the 8 MPa wet allowable) under the 6.6 N m device moment; the 4 mm ring (0.43 mm/N in-plane compliance) and ASA shrink could close the 3.4 mm tip gap. | Socket 40 mm long with a 4 mm wall under the bottom arc; ring wall 6 mm (ID 214: tip gap 5.4 mm, print at 100.5 % for shrink); tip-gap-under-load check in G10; minimum deployment depth stated. | regenerated: socket bearing pressure 1.7 MPa under 7.2 N m; ring compliance 0.14 mm/N (1.10 mm per 8 N); tip gap 5.4 mm |
| M-M8 | mech | major | The 0.85 inflow factor inboard of r 38 mm is optimistic for a bluff forward-facing cap step 8-15 mm behind the inner blade sections (potential-flow u/U 0.35-0.8 on the axis within one radius); 0.6-0.75 chord-averaged is more defensible, and the sharp shoulder adds ~4 N of drag at 2 m/s. | Inflow factor 0.70 and 0.60 added as sensitivities and 0.70 to the pessimistic combination (the baseline sweep keeps 0.85 so the candidate ranking is unchanged: all candidates share the inboard deficit); the cap step is kept (a fairing does not fit the packing budget) and G11 tests a temporary foam fairing. | regenerated: 0.70 / 0.60 give 0.94 / 0.93 W at 0.7 m/s vs baseline 0.96 W; pessimistic min self-start 0.8 m/s |
| M-M9 | mech | major | Blade print orientation (pressure side down, 40 deg chord inclination at the root) rests on a 27 mm2 line with 4228 mm2 of down-facing surface inside 45 deg; 'tree supports under the leading edge' understated it. | Section 9 states full support on a raft and the root-down alternative with its interlaminar stress; a printed blade is part of gate G3. | root bending 1.9 MPa vs the assumed 2.7 MPa interlaminar allowable for the root-down alternative |
| M-M10 | mech | major | hub_rear failed BRepCheck after STEP re-import (a zero-area cylindrical sliver from the upper pocket piece cut with clean=False) while the package reported it valid (in-memory check only). | Same-domain face unification after the hub Booleans (kept only when the result is one valid solid of unchanged volume); QA gate re-imports the STEP files and runs BRepCheck. | see QA_LOG_v4.md ('re-imported STEP solids pass BRepCheck') |
| M-M11 | mech | major | Minimum deployable depth is ~0.3 m, not 0.15: the ring OD and the socket put the axis >= 123 mm above the bed and the ring top 109 mm above the axis; in 0.15-0.2 m streams part of the rotor is out of the water, and a leaf wrapped on one wide-chord leading edge erases the self-start margin. | Minimum deployment depth computed from the geometry and stated in the report and test plan (G11); debris bar and two-point mounting recommended, not designed. | regenerated: minimum depth 0.35 m |
| M-m1 | mech | minor | AS568-147 (ID 69.44) on the 68.60 groove bottom is -1.2 % stretch; -146 (ID 66.27) gives +3.5 %; 'bored 72.90 H8' is the raw tube nominal (ID 72.57-73.23 with the wall tolerance). | AS568-146; lands bored 73.10 H8 and the plugs resized (groove bottom recomputed). | groove bottom 68.79 mm -> stretch +3.8 %, squeeze 18 % |
| M-m2 | mech | minor | Circlip groove 7.4 vs DIN 471 d2 = 7.6 for d = 8; nose plug 8.9 in 9.0 is a slip fit; WetLink counterbore 20 x 6 leaves no socket room; part notes of the clamp halves were swapped; D-flat backlash ~2 deg; PTFE lip on soft 316 wears the journal. | Groove 7.6; nose plug noted as slip fit + silicone; counterbore 22 mm with the nut's top 5.5 mm proud for an open-end wrench; part notes regenerated; backlash and journal hardening (hard chrome or hardened sleeve) noted in the BOM. | groove d2 7.6 mm; counterbore 22.0 x 6.5 mm |
| M-m3 | mech | minor | Pocket clearance 0.15 nominal measured 0.085 mm normal to the surfaces (interference in FDM practice); the tongue bolt crosses the tongue obliquely with a 2.08 mm lateral ligament; the BOM's '~17 g' blade is 24.6 g measured; the pocket wall (17.5 mm measured) made the root-chord <= 52 mm constraint unnecessarily tight. | Pocket clearance 0.25 mm; blade mass in the BOM from the structure script; the selection constraint is now the measured-geometry hub wall >= 12 deg (section 3). | pocket clearance 0.25 mm; blade 26 g; hub wall 31 deg |
| M-m4 | mech | minor | BOM_v4.csv had unquoted commas in four specification fields, shifting the columns of rows 18, 23, 24, 26 when parsed; several BOM texts (shaft 8 h6 x 73, seal journal x 10, bearing housing) disagreed with the model. | BOM regenerated with proper quoting and texts derived from the model where they are numbers. | parses to 9 columns (QA gate 'BOM covers every CAD part') |
| M-ok | mech | - | Verified by independent measurement on the first draft: assembly solids matched the parts table within 0.01 %; no interference among the 25 rigid parts other than the seal (C1); all 11 print STLs closed within 0.13 % of their STEPs; blade t/c 17.6 % at the root, 4.0 mm tip, 1.0-1.3 mm trailing edge, tip radius 101.60; pocket-to-pocket wall 17.5 mm; shaft features aligned with the dog hub; O-ring gland geometry sound; strut, root-bending and bearing screening numbers re-derived within rounding. | none needed | - |


## 11. Practical prototype testing plan

See `docs/TEST_PLAN_v4.md` (12 gates). The four measurements that close the model, in order of their effect on the 0.5-0.7 m/s prediction:
G1 generator constants and cogging, G2 breakaway and running friction of the sealed shaft, G6 standstill torque of the printed rotor, G8 the
power curve in a real stream.

## 12. Bill of materials for the simplest working prototype

`docs/BOM_v4.csv`: 33 lines, roughly $446-903 of parts beyond the GL60 (converter choice dominates; machining prices are
estimates for a job shop; no anodising, battery, cable beyond 3 m or instrumentation). The four machined parts (shaft, two caps, tube
ends) are the only non-printed, non-COTS items.

## 13. Quality gates

# Quality-gate log (v4 low-flow turbine)

The `/quality` skill is not installed in this environment, so these manual gates (`tools/qa_gates_v4.py`) stand in for it. Each gate is a script check on the exported files and result JSONs, re-run after every correction.

| Gate | Result | Detail |
|---|---|---|
| reproducibility (re-run of the coupled model at 0.7 / 1.0 m/s) [regression check: same code, same inputs] | PASS | |dP| 0.00e+00 W at 0.7/1.0 m/s |
| selection reproducible: the coded rule on the stored sweeps returns the shipped design | PASS | rule -> {'B': 3, 'airfoil': 'naca4412', 'lam_d': 1.5, 'c_scale': 1.0, 'c_max': 0.06, 'dbeta': -3.0}; shipped {'B': 3, 'airfoil': 'naca4412', 'lam_d': 1.5, 'c_scale': 1.0, 'c_max': 0.06, 'dbeta': -3.0} |
| Cp below the Betz limit on every curve | PASS | max Cp 0.354 |
| twist monotonic decreasing root -> tip, 0-60 deg | PASS | 32.7 -> 10.6 deg |
| printable section: tip chord >= 20 mm and max thickness >= 2.4 mm | PASS | tip chord 31.1 mm, tip t 3.7 mm, TE 1.0 mm |
| power balance at every operating point (shaft = friction + copper + diodes + DC) [identity check of the stored points] | PASS | 0.5: 0.00 %; 0.6: 0.00 %; 0.7: 0.00 %; 0.8: 0.00 %; 0.9: 0.00 %; 1.0: 0.00 %; 1.25: 0.00 %; 1.5: 0.00 %; 2.0: 0.00 % |
| generator current <= 1.35 A rated at every MPPT point to 2.0 m/s [enforced by the MPPT law; regression check] | PASS | max I 1.27 A |
| open-circuit bus at 2.0 m/s below the 60 V TVS standoff and the converter's 60 V input | PASS | 46.5 V |
| CAD station chord/twist match the model arrays (interpolated, r >= 28 mm) | PASS | max |dc| 0.47 mm, |dtwist| 0.24 deg |
| CAD: every solid valid, single body, no rigid clash | PASS | 37 parts, 595 pairs, interference {} |
| CAD: shaft/lip-seal overlap equals the modelled lip interference only (collar B clear of the seal) | PASS | found 42.49 mm3, expected 42.49 mm3 |
| CAD: dog coupling engages the TPU disc by >= 1.5 mm and clears the bell | PASS | engagement 2.0 mm of a 2.5 mm disc |
| CAD: penetrator counterbore clears every stator hole by >= 2 mm of wall | PASS | wall 2.7 mm |
| CAD: rotor thrust shoulder present (DIN 472-22 groove behind the bearing inside the cap boss) | PASS | bearing ends x 45.2, groove x 45.3, boss end x 47.4 |
| CAD: re-imported STEP solids pass BRepCheck (hub halves, blade, caps, shafts, drive, shell, strut, arcs) | PASS | all valid |
| print STLs closed; blade STL volume within 1 % of its STEP | PASS | 13 STLs; blade dev [0.07] % |
| packing: rotor and nacelle each <= 76 mm when detached | PASS | rotor 72.5, nacelle 74.9, operating 136.4 mm |
| hub wall between pockets >= 12 deg (measured from the CAD root outline) | PASS | pocket arc 89 deg, wall 31 deg = 8.7 mm at the floor |
| minimum self-start flow: sweep (40 elements) and final evaluation (50 elements) agree | PASS | sweep 0.6 vs final 0.6 m/s |
| all required figures generated by scripts | PASS | 12 figures |
| BOM covers every CAD part | PASS | 33 BOM lines |
| report text contains no hand-typed result numbers (W / % / rpm / torque / current outside f-string expressions; unit literals allow-listed) | PASS | none found |

**22 of 22 gates pass.**


## 14. Unresolved assumptions

- GL60: KV / Kt / R convention, cogging torque (the single biggest unknown for self-start), no-load loss, lead exit, which hole pattern is the stator's.
- Hydrofoil polars at Re 4e4-8e4 come from an XFOIL surrogate; the transition Reynolds number of a wet printed surface is the dominant uncertainty at 0.5-0.6 m/s (Re/1.5 case).
- The rotor runs at axial induction 0.4-0.6 over the outer third of the blade, where the empirical high-induction correction (Buhl baseline; Glauert-Spera and uncorrected momentum as alternatives) is load-bearing.
- The starting-torque model (BEM at TSR 0.1 baseline; no-induction estimate as upper bound) decides the self-start verdict; neither is validated by data at this scale.
- Converter fixed overhead (0.13 W assumed; 0.1-0.3 W plausible) decides the 0.5-0.6 m/s output; the KV convention (21.5 vs ~26 rectified) is unverified.
- Seal and bearing friction (assumed from diameter scaling of catalogue-class values), converter efficiency curve and minimum input voltage, quiescent draw.
- Nacelle inflow deficit (15 % inboard of r 38 mm assumed; the review's potential-flow estimate for the bluff cap step is 0.6-0.75, carried as a
  sensitivity and in the pessimistic combination: 0.94 / 0.93 W at 0.7 m/s for 0.70 / 0.60 against 0.96 W), guard-ring and shallow-water effects (G11), turbulence and debris.
- WetLink dry-side geometry (a 12 x 3 mm inner protrusion is assumed in the model; the 4.5 mm stator-to-cap gap and the splice pocket depend on it).
- Single rotor bearing tilt (G5) and the minimum deployment depth with the stake socket below the ring.
- Manufacturer pages were unreachable: WetLink, Genasun GVB-8, LT8390 modules and seal part numbers must be confirmed before ordering.
