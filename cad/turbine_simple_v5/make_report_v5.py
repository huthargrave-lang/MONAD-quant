#!/usr/bin/env python3
"""REPORT_v5.md for the simplified prototype: every number read from out/v5_info.json (geometry, checks) and out/v5_results.json (model)."""
import json, math, os, csv, io
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out")
info = json.load(open(os.path.join(OUT, "v5_info.json"))); R = json.load(open(os.path.join(OUT, "v5_results.json")))
lay = info["layout"]; Q = lay["Q"]; L = lay["L"]; parts = {p["name"]: p for p in info["parts"]}; sel = info["selected"]; VS = R["VS"]
kA = "v4 arrangement A (8 mm PTFE seal + 608)"; kS = "v5 simplified (12 mm PTFE seal + 6001)"; kN = "v5 with an NBR seal"; kC = "v5, cogging 40 mN m"; kI = "v5, inflow factor 0.70"
def P(k, V): return R["cases"][k]["P"][VS.index(V)]
def row(k): c = R["cases"][k]; return f"| {k} | " + " | ".join(f"{P(k, V):.2f}" for V in (0.5, 0.6, 0.7, 0.8, 1.0, 1.5, 2.0)) + f" | {c['min_start']} / {c['min_sustain']} | {c['Qstatic05']*1000:.0f} vs {c['breakaway05']*1000:.0f} |"
S = R["cases"][kS]; A = R["cases"][kA]
pr = parts["rotor"]; ph = parts["housing"]; pm = parts["mount"]; pa = parts["adapter"]
cl = lay["clearances_mm"]; bad = {k: v for k, v in lay["interference_mm3"].items() if v > 0.5 or v < 0}
min_depth = (abs(lay["mount"]["z_sock_mouth"]) + 30 + Q["r_tip"] + 50) / 1000
bom = [
 ("1", "1", "Rotor", "printed ASA (or PETG), one piece: nose, hub cup OD 56 / ID 42, 3 blades, 10 mm double-D neck; 100 % infill, 0.2 mm layers, nose down with tree supports under the blades", "out/v5_rotor_PRINT.stl", f"{pr['volume_mm3']/1000*1.07:.0f} g ASA"),
 ("2", "1", "Housing", "printed ASA, one piece: cup OD 78 x 4 wall, flat front wall, snout OD 40 with one 28 mm bore, rear flange OD 96 with 6 M4 heat-set inserts; open end down, internal supports under the front wall", "out/v5_housing_PRINT.stl", f"{ph['volume_mm3']/1000*1.07:.0f} g"),
 ("3", "1", "Mount", "printed ASA, one piece: rear lid OD 96 x 6 (face O-ring groove, 6 x M4 clearance), 4 stand-offs for the GL60 stator, PG7 gland hole, arm 30 x 16 and a 40 mm stake socket (16.2 bore); rear face down, arm along the bed", "out/v5_mount_PRINT.stl", f"{pm['volume_mm3']/1000*1.07:.0f} g"),
 ("4", "1", "Bell adapter", "printed ASA 46 x 8: double-D blind bore, 4 x M3 counterbored holes (bell PCD assumed 40 - measure), captive M3 nut boss inside the GL60 bore; front face down", "out/v5_adapter_PRINT.stl", f"{pa['volume_mm3']/1000*1.07:.0f} g"),
 ("5", "1", "Generator", "CubeMars GL60 KV25 (purchased): 69 x 22.3, 20 mm bore; bell forward", "-", "fixed"),
 ("6", "1", "Sleeve", "304/316 stainless tube 12 OD x 1 wall, cut 16.5 mm, deburred, epoxied on the rotor neck (seal and bearing journal)", "-", "cut from stock"),
 ("7", "1", "Lip seal", "12 x 28 x 7 (PTFE lip preferred; NBR 'TC' double-lip is the cheap fallback, +4 mN m)", "-", ""),
 ("8", "1", "Bearing", "6001-2RS stainless 12 x 28 x 8 (slip fit on the sleeve; radial load only)", "-", ""),
 ("9", "1", "Rotor bolt", "M3 x 50 316 socket head + M3 nyloc nut (captive in the adapter)", "-", "Loctite 243 on the nut side"),
 ("10", "4", "Bell screws", "M3 x 10 316 socket head into the GL60 bell face (thread/PCD per gate G1)", "-", ""),
 ("11", "4", "Stator screws", "M2.5 x 16 (or M3 x 16) 316 + bonded sealing washers, through the lid into the GL60 base; heads also covered with neutral-cure silicone", "-", "these four holes are the only penetrations besides the gland"),
 ("12", "6", "Lid screws", "M4 x 12 316 pan head + 6 M4 brass heat-set inserts (housing flange)", "-", "0.8 N m"),
 ("13", "1", "O-ring", "AS568-148 EPDM 70 (ID 72.6, cs 2.62) in the lid's face groove (ID 72.4 / OD 79.6 x 2.0 deep)", "-", "silicone grease"),
 ("14", "1", "Cable gland", "PG7 nylon gland (3-6.5 mm cable) + locknut; 3 m 3-core 18 AWG cable", "-", "locknut inside the 6 mm bay"),
 ("15", "1", "Stake", "16 mm aluminium / fibreglass tent pole or rebar, >= 0.6 m", "-", ""),
 ("16", "1", "Electronics", "3-phase bridge rectifier + buck-boost MPPT module (4-60 V in, 12-14.4 V out, battery current limit) + 60 V TVS, in a dry box on the bank (as in the v4 package, items 25-28)", "-", "unchanged from v4"),
 ("17", "-", "Consumables", "epoxy (sleeve), neutral-cure silicone, Loctite 243, silicone grease, 12 mm reamer or drill for the sleeve bore, 28 mm sanding drum for the seat", "-", ""),
]
w = io.StringIO(); cw = csv.writer(w, lineterminator="\n"); cw.writerow(["item", "qty", "part", "specification", "file", "notes"]); cw.writerows(bom); open(os.path.join(HERE, "BOM_v5.csv"), "w").write(w.getvalue())
txt = f"""# Simplified prototype turbine (v5): one-piece rotor, printed housing, printed mount, CubeMars GL60 KV25

**Status.** Model prediction and design intent; nothing printed or tested. The blade geometry is the v4 optimised low-flow design
({sel['B']} blades, {sel['airfoil']} blending to NACA 4418 at the root, design TSR {sel['spec']['lam_d']}, pitch {sel['spec'].get('dbeta', 0):+.0f} deg, hub radius {Q['r_hub']:.0f} mm, tip radius {Q['r_tip']:.1f} mm), unchanged.
Everything else was redesigned for printing and for the fewest parts. Numbers in this file are written by `make_report_v5.py` from
`out/v5_info.json` (geometry, checks) and `out/v5_results.json` (coupled rotor + generator model of the v4 package).

## 1. The three printed parts and how they go together

| part | what it is | attachment | file |
|---|---|---|---|
| **Rotor** (one print) | nose + hub cup (OD 56) + 3 blades + a 10 mm double-D neck that reaches back through the housing snout | one central M3 x 50 bolt through the nose into a captive nut in the bell adapter; the double-D carries the torque; the rotor unbolts for packing | `out/v5_rotor.step`, `out/v5_rotor_PRINT.stl` |
| **Housing** (one print) | cup OD {Q['body_od']:.0f}, flat front wall, a {Q['snout_od']:.0f} mm snout reaching {Q['hub_len'] - Q['snout_x0']:.0f} mm into the hub cup with ONE 12 x 28 x 7 lip seal and ONE 6001 bearing in a single 28 mm bore; rear flange with 6 M4 heat-set inserts | the GL60 sits dry inside; the rear is closed by the mount | `out/v5_housing.step`, `out/v5_housing_PRINT.stl` |
| **Mount** (one print) | the housing's rear lid (face O-ring, 6 x M4), four 6 mm stand-offs carrying the GL60 stator, the cable-gland hole, an arm and a 40 mm socket for a 16 mm stake | the same six screws close the housing and fix it to the mount | `out/v5_mount.step`, `out/v5_mount_PRINT.stl` |
| + bell adapter (small print) | 46 x 8 disc bolted to the GL60 bell face (4 x M3), double-D bore, captive M3 nut in a boss inside the GL60's 20 mm bore | needed because the bell's 4-hole face (46 mm across) cannot pass through a 12 mm seal: the adapter is the only "coupling" | `out/v5_adapter.step`, `out/v5_adapter_PRINT.stl` |

**Rotor to motor.** Rotor neck (double-D, {cl['dd_engagement']:.1f} mm engaged) into the adapter; adapter bolted to the bell. Rotor thrust: neck end -> adapter floor ->
bell -> GL60 bearings -> stator -> stand-offs -> mount (the GL60's axial play and bearing rating are gate G1 items: {S['T2']:.0f} N at 2 m/s, under
{S['T2']/4:.0f} N below 1 m/s). The one M3 bolt only holds the rotor on (handling, reverse surge). No shaft, no shaft collars, no circlips, no
machined parts: the only metal journal is a 12 mm stainless tube epoxied on the printed neck.

**Keeping the motor dry.** One rotating seal on the 12 mm sleeve at the front of the snout (lip to the water), one static face O-ring under
the lid, four stator screws through the lid with bonded washers (plus silicone over the heads), one PG7 gland. The seal and the bearing sit
in the same bore, bearing first (from the front), seal in front of it. The bearing takes radial and moment loads only.

**Housing to mount.** Six M4 x 12 into heat-set inserts in the housing flange (PCD {Q['insert_pcd']:.0f}). The lid is the mount, so there is no
clamp, no second seal and no separate bracket. The arm runs forward under the housing (clear of the flange by {abs(Q['arm_z_top']) - Q['flange_od']/2:.0f} mm) to a
{Q['sock_len']:.0f} mm socket with {Q['sock_wall']:.0f} mm walls, {abs(lay['mount']['z_sock_mouth']):.0f} mm below the axis.

## 2. Depth and size

| | mm |
|---|---|
| nose tip to lid (operating, gland excluded) | {lay['operating_depth_mm'] - Q['gland_body_len']:.1f} |
| nose tip to the gland's end | {lay['operating_depth_mm']:.1f} |
| rotor alone (unbolt one M3) | {lay['rotor_depth_mm']:.1f} |
| housing + mount (snout tip to the lid-screw heads) / with the gland | {lay['housing_mount_depth_mm']:.1f} / {lay['housing_mount_depth_with_gland_mm']:.1f} |
| rotor diameter / housing OD / lid OD | {2*Q['r_tip']:.1f} / {Q['body_od']:.0f} / {Q['flange_od']:.0f} |
| mount height below the axis (socket mouth) | {abs(lay['mount']['z_sock_mouth']):.0f} |
| print envelopes (x, y, z) rotor / housing / mount / adapter | {pr.get('print_size_mm')} / {ph.get('print_size_mm')} / {pm.get('print_size_mm')} / {pa.get('print_size_mm')} |

The 3-inch (76 mm) target is met by the rotor and by the housing + mount when the rotor is unbolted; the assembled unit is
{lay['operating_depth_mm'] - Q['gland_body_len']:.0f} mm from the nose to the lid. The stack is: nose {Q['nose_len']:.0f} + hub {Q['hub_len']:.0f} + gap {Q['gap_hub_wall']:.0f} + wall {Q['wall_t']:.0f} + adapter {Q['adapter_t']:.0f} + GL60 {Q['motor_len']:.1f} +
stator bay {Q['standoff']:.0f} + lid {Q['plate_t']:.0f}; the snout (seal + bearing) is inside the hub cup and costs no length. The only way to a 76 mm assembled
unit is the hub-integrated drum (motor inside the hub), which the v4 analysis showed costs 44-77 % of the output at 0.7-1.0 m/s because of
the 48 mm hub - that is the engineering reason for keeping the 28 mm hub ahead of the housing.

## 3. Predicted performance (same model as v4; hand-started where below the self-start speed)

| case | 0.5 | 0.6 | 0.7 | 0.8 | 1.0 | 1.5 | 2.0 m/s (W) | self-start / sustain (m/s) | starting torque vs breakaway at 0.5 m/s (mN m) |
|---|---|---|---|---|---|---|---|---|---|
{row(kA)}
{row(kS)}
{row(kN)}
{row(kC)}
{row(kI)}

The 12 mm seal (friction assumed {R['friction']['S_simple']['seal_run']*1000:.0f} mN m running / {R['friction']['S_simple']['seal_break']*1000:.0f} breakaway, PTFE) costs {(1 - P(kS, 0.6) / P(kA, 0.6)) * 100:.0f} % at 0.6 m/s and {(1 - P(kS, 1.0) / P(kA, 1.0)) * 100:.0f} % at 1.0 m/s against the
v4 8 mm seal; an NBR seal costs {(1 - P(kN, 0.6) / P(kS, 0.6)) * 100:.0f} % more at 0.6 m/s. Self-start is {S['min_start']} m/s (baseline cogging {24} mN m assumed; {R['cases'][kC]['min_start']} m/s with 40 mN m);
the rotor sustains itself from {S['min_sustain']} m/s once spun by hand. Open-circuit bus at 2 m/s: {S['Voc2']:.0f} V (TVS 60 V). Rotor torque at 2 m/s {S['Q2']:.2f} N m on a double-D
with {cl['dd_engagement']:.1f} mm engagement ({S['Q2'] / 0.004 / 2 / (6.0 * cl['dd_engagement']):.1f} MPa on the printed flats).

## 4. Assembly, in order

1. Print the four parts (orientations below). Ream the snout bore to 28.0 (seal/bearing push fit), the rotor neck to 10.0 for the sleeve, the
   adapter double-D to a snug fit on the neck. Fit the six M4 and no other inserts.
2. Epoxy the 16.5 mm stainless sleeve on the rotor neck ({Q['sleeve_x0']:.0f}-{Q['sleeve_x0'] + Q['sleeve_len']:.1f} mm behind the hub front face); wipe the outside clean.
3. Press the 6001 into the snout from the front to the lip, then the seal in front of it, lip facing the water (forward).
4. Push the rotor neck through the seal and bearing from the front until the hub face is {cl['hub_to_wall']:.0f} mm from the housing wall.
5. Bolt the adapter to the GL60 bell (4 x M3 x 10, counterbored heads on the adapter's front face), nyloc nut in the adapter's rear boss.
6. Bolt the GL60 stator to the mount's stand-offs (4 screws with bonded washers from the rear; silicone over the heads). Fit the gland,
   pass the cable, splice the three phase leads in the 6 mm bay, grease the O-ring into its groove.
7. Slide motor + mount into the housing: the double-D neck enters the adapter; tighten the six M4 x 12.
8. Through the nose: M3 x 50 into the captive nut, 1 N m. Vacuum test (-50 kPa, 15 min) before the water.
Packing: undo the one M3 and pull the rotor forward; the housing stays sealed.

## 5. Printing

- Rotor: nose down on a raft, tree supports under the blades and the hub rim (the blades are horizontal cantilevers), 100 % infill,
  0.2 mm layers; the neck prints as a vertical column with the M3 bore. Print size {pr.get('print_size_mm')} mm.
- Housing: open end down, 4-6 walls, internal supports under the flat front wall (reachable through the open end), snout vertical.
- Mount: lid face up (rear face on the bed), arm along the bed, socket bore horizontal (add a 45 deg roof or support in the slicer).
- Adapter: front face down.
- Material: ASA (UV, water); PETG works for a first test. Scale the rotor 100.3 % if the printed hub is undersize.

## 6. Checks performed on the generated geometry

| check | result |
|---|---|
| all printed solids valid, single bodies | {all(parts[n]['valid'] and parts[n]['n_solids'] == 1 for n in ('rotor', 'housing', 'mount', 'adapter'))} |
| rigid-part clash check ({lay['pairs_checked']} pairs, screws vs motor excluded) | {'none' if not bad else bad} |
| seal lip interference on the sleeve equals the modelled 0.25 mm lip | {lay['seal_lip_overlap_mm3']} |
| STLs watertight (rotor / housing / mount / adapter) | {[parts[n].get('stl_watertight') for n in ('rotor', 'housing', 'mount', 'adapter')]} ; rotor STL volume vs STEP {pr.get('stl_vs_step_pct')} % |
| clearances (mm) | {cl} |
| CAD stations follow the v4 blade arrays | the same `blade_stations()` of `make_v4.py` (chord {sel['chord_mm'][0]:.1f} -> {max(sel['chord_mm']):.1f} -> {sel['chord_mm'][-1]:.1f} mm, twist {sel['twist_deg'][0]:.1f} -> {sel['twist_deg'][-1]:.1f} deg) |

## 7. What is assumed and must be measured first

- GL60 bell-face hole pattern (adapter drilled for PCD 40, 4 x M3 at 45 deg), stator-base pattern (lid drilled for PCD 50, 4 x M2.5), the
  20 mm bore (the captive nut boss sits in it), and the bell's axial play / bearing rating (the rotor thrust now goes through the motor).
- Seal friction on a printed-neck sleeve, cogging torque (decides the self-start speed), converter minimum voltage and overhead.
- The flat housing front wall sits {cl['hub_to_wall']:.0f} mm behind the hub: the v4 reviewer's inflow-deficit concern applies unchanged (row "inflow factor 0.70").
- Minimum water depth with the stake under the arm: about {min_depth:.2f} m (socket + 30 mm of stake + rotor radius + 50 mm freeboard).
- No guard ring: keep hands and debris away from the rotor; add the v4 ring if needed.

Figures: `out/fig_v5_section.png`, `out/fig_v5_exploded.png`, `out/fig_v5_power.png`. BOM: `BOM_v5.csv`.
"""
open(os.path.join(HERE, "REPORT_v5.md"), "w").write(txt); print("REPORT_v5.md + BOM_v5.csv written")
