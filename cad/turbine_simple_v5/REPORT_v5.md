# Simplified prototype turbine (v5): one-piece rotor, printed housing, printed mount, CubeMars GL60 KV25

**Status.** Model prediction and design intent; nothing printed or tested. The blade geometry is the v4 optimised low-flow design
(3 blades, naca4412 blending to NACA 4418 at the root, design TSR 1.5, pitch -3 deg, hub radius 28 mm, tip radius 101.6 mm), unchanged.
Everything else was redesigned for printing and for the fewest parts. Numbers in this file are written by `make_report_v5.py` from
`out/v5_info.json` (geometry, checks) and `out/v5_results.json` (coupled rotor + generator model of the v4 package).

## 1. The three printed parts and how they go together

| part | what it is | attachment | file |
|---|---|---|---|
| **Rotor** (one print) | nose + hub cup (OD 56) + 3 blades + a 10 mm double-D neck that reaches back through the housing snout | one central M3 x 50 bolt through the nose into a captive nut in the bell adapter; the double-D carries the torque; the rotor unbolts for packing | `out/v5_rotor.step`, `out/v5_rotor_PRINT.stl` |
| **Housing** (one print) | cup OD 78, flat front wall, a 40 mm snout reaching 23 mm into the hub cup with ONE 12 x 28 x 7 lip seal and ONE 6001 bearing in a single 28 mm bore; rear flange with 6 M4 heat-set inserts | the GL60 sits dry inside; the rear is closed by the mount | `out/v5_housing.step`, `out/v5_housing_PRINT.stl` |
| **Mount** (one print) | the housing's rear lid (face O-ring, 6 x M4), four 6 mm stand-offs carrying the GL60 stator, the cable-gland hole, an arm and a 40 mm socket for a 16 mm stake | the same six screws close the housing and fix it to the mount | `out/v5_mount.step`, `out/v5_mount_PRINT.stl` |
| + bell adapter (small print) | 46 x 8 disc bolted to the GL60 bell face (4 x M3), double-D bore, captive M3 nut in a boss inside the GL60's 20 mm bore | needed because the bell's 4-hole face (46 mm across) cannot pass through a 12 mm seal: the adapter is the only "coupling" | `out/v5_adapter.step`, `out/v5_adapter_PRINT.stl` |

**Rotor to motor.** Rotor neck (double-D, 6.5 mm engaged) into the adapter; adapter bolted to the bell. Rotor thrust: neck end -> adapter floor ->
bell -> GL60 bearings -> stator -> stand-offs -> mount (the GL60's axial play and bearing rating are gate G1 items: 38 N at 2 m/s, under
9 N below 1 m/s). The one M3 bolt only holds the rotor on (handling, reverse surge). No shaft, no shaft collars, no circlips, no
machined parts: the only metal journal is a 12 mm stainless tube epoxied on the printed neck.

**Keeping the motor dry.** One rotating seal on the 12 mm sleeve at the front of the snout (lip to the water), one static face O-ring under
the lid, four stator screws through the lid with bonded washers (plus silicone over the heads), one PG7 gland. The seal and the bearing sit
in the same bore, bearing first (from the front), seal in front of it. The bearing takes radial and moment loads only.

**Housing to mount.** Six M4 x 12 into heat-set inserts in the housing flange (PCD 88). The lid is the mount, so there is no
clamp, no second seal and no separate bracket. The arm runs forward under the housing (clear of the flange by 2 mm) to a
40 mm socket with 4 mm walls, 170 mm below the axis.

## 2. Depth and size

| | mm |
|---|---|
| nose tip to lid (operating, gland excluded) | 90.8 |
| nose tip to the gland's end | 102.8 |
| rotor alone (unbolt one M3) | 59.0 |
| housing + mount (snout tip to the lid-screw heads) / with the gland | 75.8 / 83.8 |
| rotor diameter / housing OD / lid OD | 203.2 / 78 / 96 |
| mount height below the axis (socket mouth) | 170 |
| print envelopes (x, y, z) rotor / housing / mount / adapter | [174.4, 188.9, 54.5] / [96.0, 96.0, 65.8] / [218.0, 96.0, 30.0] / [46.0, 46.0, 12.0] |

The 3-inch (76 mm) target is met by the rotor and by the housing + mount when the rotor is unbolted; the assembled unit is
91 mm from the nose to the lid. The stack is: nose 12 + hub 30 + gap 2 + wall 4 + adapter 8 + GL60 22.3 +
stator bay 6 + lid 6; the snout (seal + bearing) is inside the hub cup and costs no length. The only way to a 76 mm assembled
unit is the hub-integrated drum (motor inside the hub), which the v4 analysis showed delivers 30-44 % less output at 0.7-1.0 m/s because of
the 48 mm hub - that is the engineering reason for keeping the 28 mm hub ahead of the housing.

## 3. Predicted performance (same model as v4; hand-started where below the self-start speed)

| case | 0.5 | 0.6 | 0.7 | 0.8 | 1.0 | 1.5 | 2.0 m/s (W) | self-start / sustain (m/s) | starting torque vs breakaway at 0.5 m/s (mN m) |
|---|---|---|---|---|---|---|---|---|---|
| v4 arrangement A (8 mm PTFE seal + 608) | 0.16 | 0.49 | 0.96 | 1.60 | 3.45 | 12.02 | 27.23 | 0.6 / 0.5 | 29 vs 36 |
| v5 simplified (12 mm PTFE seal + 6001) | 0.14 | 0.47 | 0.93 | 1.57 | 3.41 | 11.97 | 27.16 | 0.6 / 0.5 | 29 vs 40 |
| v5 with an NBR seal | 0.11 | 0.42 | 0.88 | 1.51 | 3.34 | 11.86 | 27.03 | 0.7 / 0.5 | 29 vs 48 |
| v5, cogging 40 mN m | 0.14 | 0.47 | 0.93 | 1.57 | 3.41 | 11.97 | 27.16 | 0.7 / 0.5 | 29 vs 56 |
| v5, inflow factor 0.70 | 0.14 | 0.46 | 0.92 | 1.54 | 3.36 | 11.77 | 26.73 | 0.6 / 0.5 | 29 vs 40 |

The 12 mm seal (friction assumed 6 mN m running / 12 breakaway, PTFE) costs 4 % at 0.6 m/s and 1 % at 1.0 m/s against the
v4 8 mm seal; an NBR seal costs 9 % more at 0.6 m/s. Self-start is 0.6 m/s (baseline cogging 24 mN m assumed; 0.7 m/s with 40 mN m);
the rotor sustains itself from 0.5 m/s once spun by hand. Open-circuit bus at 2 m/s: 46 V (TVS 60 V). Rotor torque at 2 m/s 0.55 N m on a double-D
with 6.5 mm engagement (1.8 MPa on the printed flats).

## 4. Assembly, in order

1. Print the four parts (orientations below). Ream the snout bore to 28.0 (seal/bearing push fit), the rotor neck to 10.0 for the sleeve, the
   adapter double-D to a snug fit on the neck. Fit the six M4 and no other inserts.
2. Epoxy the 16.5 mm stainless sleeve on the rotor neck (6-22.5 mm behind the hub front face); wipe the outside clean.
3. Press the 6001 into the snout from the front to the lip, then the seal in front of it, lip facing the water (forward).
4. Push the rotor neck through the seal and bearing from the front until the hub face is 2 mm from the housing wall.
5. Bolt the adapter to the GL60 bell (4 x M3 x 10, counterbored heads on the adapter's front face), nyloc nut in the adapter's rear boss.
6. Bolt the GL60 stator to the mount's stand-offs (4 screws with bonded washers from the rear; silicone over the heads). Fit the gland,
   pass the cable, splice the three phase leads in the 6 mm bay, grease the O-ring into its groove.
7. Slide motor + mount into the housing: the double-D neck enters the adapter; tighten the six M4 x 12.
8. Through the nose: M3 x 50 into the captive nut, 1 N m. Vacuum test (-50 kPa, 15 min) before the water.
Packing: undo the one M3 and pull the rotor forward; the housing stays sealed.

## 5. Printing

- Rotor: nose down on a raft, tree supports under the blades and the hub rim (the blades are horizontal cantilevers), 100 % infill,
  0.2 mm layers; the neck prints as a vertical column with the M3 bore. Print size [174.4, 188.9, 54.5] mm.
- Housing: open end down, 4-6 walls, internal supports under the flat front wall (reachable through the open end), snout vertical.
- Mount: lid face up (rear face on the bed), arm along the bed, socket bore horizontal (add a 45 deg roof or support in the slicer).
- Adapter: front face down.
- Material: ASA (UV, water); PETG works for a first test. Scale the rotor 100.3 % if the printed hub is undersize.

## 6. Checks performed on the generated geometry

| check | result |
|---|---|
| all printed solids valid, single bodies | True |
| rigid-part clash check (465 pairs, screws vs motor excluded) | none |
| seal lip interference on the sleeve equals the modelled 0.25 mm lip | {'found': 64.41, 'expected': 64.41, 'ok': True} |
| STLs watertight (rotor / housing / mount / adapter) | [True, True, True, True] ; rotor STL volume vs STEP -0.12 % |
| clearances (mm) | {'hub_to_wall': 2.0, 'snout_to_cup_floor': 2.0, 'snout_radial': 1.0, 'neck_end_to_dd_floor': 0.05, 'adapter_to_wall': 0.5, 'dd_engagement': 6.45, 'stator_bay': 6.0, 'blade_tip_to_arm': None} |
| CAD stations follow the v4 blade arrays | the same `blade_stations()` of `make_v4.py` (chord 50.1 -> 60.0 -> 31.1 mm, twist 32.7 -> 10.6 deg) |

## 7. What is assumed and must be measured first

- GL60 bell-face hole pattern (adapter drilled for PCD 40, 4 x M3 at 45 deg), stator-base pattern (lid drilled for PCD 50, 4 x M2.5), the
  20 mm bore (the captive nut boss sits in it), and the bell's axial play / bearing rating (the rotor thrust now goes through the motor).
- Seal friction on a printed-neck sleeve, cogging torque (decides the self-start speed), converter minimum voltage and overhead.
- The flat housing front wall sits 2 mm behind the hub: the v4 reviewer's inflow-deficit concern applies unchanged (row "inflow factor 0.70").
- Minimum water depth with the stake under the arm: about 0.35 m (socket + 30 mm of stake + rotor radius + 50 mm freeboard).
- No guard ring: keep hands and debris away from the rotor; add the v4 ring if needed.

Figures: `out/fig_v5_section.png`, `out/fig_v5_exploded.png`, `out/fig_v5_power.png`. BOM: `BOM_v5.csv`.
