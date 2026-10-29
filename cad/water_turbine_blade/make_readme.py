#!/usr/bin/env python
"""Write README.md for the blade package from design_spec.json / blade_stations.csv."""
import csv, json, os
OUT = os.path.dirname(os.path.abspath(__file__)); IN = 25.4
s = json.load(open(os.path.join(OUT, "design_spec.json")))
rows = list(csv.DictReader(open(os.path.join(OUT, "blade_stations.csv"))))
root, tip = rows[0], rows[-1]
perf = s["performance"]
def pr(V):
    d = perf[V]["design_tsr"]
    return f"| {V} | {d['rpm']:.0f} | {d['P_W']:.1f} | {perf[V]['available_W']:.0f} | {d['Q_Nm']:.2f} | {d['T_N']:.0f} |"
cp = s["cp_curve"]; tsr = cp["tsr"]; cpv = cp["cp"]
plateau = [t for t, c in zip(tsr, cpv) if c >= 0.95 * max(cpv)]
txt = f"""# 8 in water turbine blade (3 in wide) for 1-2 m/s flow

Hydrokinetic (free-stream river / tidal) axial-flow turbine blade. Open `turbine_blade_8in.step`
in Fusion 360 with **File > Open > Open from my computer...** (or upload it to a project in the Data
Panel). It arrives as one solid body in millimetres; the tip sits at exactly 101.60 mm (4.000 in)
from the axis and the widest chord measures 76.20 mm (3.000 in).

| File | What it is |
|---|---|
| `turbine_blade_8in.step` | **One blade**, solid body, mm. Root is trimmed to a cylinder of radius {s['hub_radius_mm'] - 6.1:.0f} mm so it sinks ~6 mm into a 3 in hub. |
| `turbine_rotor_8in_3blade.step` | Full rotor: 3 blades + 3 in x 2 in hub with a {s['hub_bore_mm']:.0f} mm bore, single solid, ready to print or modify. |
| `turbine_blade_8in.stl`, `turbine_rotor_8in_3blade.stl` | Same blade / rotor as meshes for slicers (or Fusion *Insert > Insert Mesh*). |
| `blade_stations.csv` | Radius, chord, twist, thickness and airfoil at every section. |
| `sections_for_fusion_csv/` | Each 3-D section outline as x,y,z in **cm**, one closed loop per file, for Fusion's built-in *ImportSplineCSV* script if you want to re-loft natively. |
| `design_spec.json` | Every number below plus the Cp(TSR) and power curves. |
| `make_blade.py`, `make_preview.py`, `make_readme.py` | Regenerate everything (`pip install cadquery numpy matplotlib`). |

## Geometry

| | |
|---|---|
| Rotor diameter | 8.000 in (203.2 mm) |
| Hub | 3.0 in diameter (hub ratio 0.375), 2.0 in long in the rotor file |
| Blades | {s['blades']} |
| Max chord (blade width) | **{s['max_chord_mm']:.1f} mm = {s['max_chord_in']:.2f} in** at ~{[r for r in rows if abs(float(r['chord_mm'])-s['max_chord_mm'])<0.05][0]['r_in']} in radius |
| Root chord (at hub surface) | {float(root['chord_mm']):.1f} mm ({float(root['chord_in']):.2f} in) |
| Tip | elliptically rounded, {float(tip['chord_mm']):.1f} mm chord at the very tip |
| Twist | {float(root['twist_deg_from_rotor_plane']):.1f} deg at the root to {float(tip['twist_deg_from_rotor_plane']):.1f} deg at the tip (chord angle from the rotor plane) |
| Airfoil | NACA 4422 at the root (22 % thick for strength) blending to NACA 4412 from 65 % radius outward |
| Max thickness | {float(root['chord_mm'])*float(root['thickness_ratio']):.1f} mm at the root, {float(rows[-4]['chord_mm'])*float(rows[-4]['thickness_ratio']):.1f} mm near the tip |
| Trailing edge | {s['trailing_edge_thickness_mm']:.1f} mm blunt (printable / machinable) |
| Axial depth of the blade | {s['axial_extent_mm']:.1f} mm ({s['axial_extent_in']:.2f} in) - well inside the 3 in envelope |
| Stacking axis | {s['pitch_axis_fraction']*100:.0f} % chord, radial (Z axis) |
| Blade volume | {s['blade_volume_mm3']/1000:.1f} cm3 (about {s['blade_volume_mm3']/1000*1.25:.0f} g in PETG) |

**Coordinate frame:** +X is the flow direction (water enters on the -X face), the blade runs along +Z,
and the rotor axis is X. The camber (suction) side faces downstream. The rotor turns
**counter-clockwise when viewed from upstream**. To build your own rotor from the single blade,
circular-pattern it 3x about the X axis and join it to a hub of 3 in diameter (or edit the hub in the rotor file).

## Predicted performance (blade-element-momentum, 3 blades)

Recommended operating point: tip-speed ratio **{s['operating_tsr']:.2f}** (peak Cp = **{s['cp_max_bem']:.2f}**).
The Cp curve is flat: within 5 % of peak from TSR {min(plateau):.2f} to {max(plateau):.2f}, so a fixed
generator load works across the 1-2 m/s band.

| Water speed (m/s) | rpm | Shaft power (W) | Power in the stream (W) | Torque (N m) | Thrust (N) |
|---|---|---|---|---|---|
{pr('1.0')}
{pr('1.5')}
{pr('2.0')}

Cp vs TSR: """ + ", ".join(f"{t:.2f}: {c:.2f}" for t, c in zip(tsr, cpv) if 1.5 <= t <= 6.0 and abs(t*4 - round(t*4)) < 1e-9 and round(t*2) == t*2) + f"""

## How it was designed

1. Schmitz optimum chord and twist (momentum theory including wake rotation) for 3 blades, with the
   design angle of attack 4-5.5 deg so that the widest point of the optimum blade is exactly 3 in.
2. A short BEM-driven search over the planform taper (Schmitz shape at TSR {s['geometry_schmitz_tsr']:.1f},
   scaled to 3 in max chord) and a global pitch offset ({s['pitch_offset_deg']:+.2f} deg) to maximise peak Cp.
3. Verification with a full BEM solver: Prandtl tip and hub loss, Buhl high-induction correction,
   NACA 44xx lift/drag model with Viterna post-stall extrapolation, 80 radial elements.

A 3 in wide blade on an 8 in, 3-blade rotor is a **high-solidity** design: the sections only need
CL ~ 0.3-0.4 (about 0 deg angle of attack on the cambered NACA 44xx) to load the rotor optimally,
which is why the twist looks flat. The upside is strong starting torque at 1 m/s; the downside is a
slightly lower peak Cp than a slender high-TSR blade would reach. Blade Reynolds numbers are
1e5-4e5, fine for these airfoils. Cavitation is not a concern below ~8 m/s tip speed in open water.

**Caveats.** The polar model is analytic (no CFD / XFOIL / tank test); expect real Cp of roughly
0.25-0.35 depending on surface finish, hub/nacelle shape and generator matching. Add a 2-3 mm fillet
where the blade meets the hub, and balance the rotor after printing.

## Making it

- FDM: print each blade root-down with the chord on the bed diagonal, 100 % infill or 4+ walls, in
  PETG / ASA / nylon; or print the whole rotor hub-down with supports under the blades.
- Loads are small: at 2 m/s the whole rotor sees ~{perf['2.0']['design_tsr']['T_N']:.0f} N of thrust ({perf['2.0']['design_tsr']['T_N']/3:.0f} N per blade), so a printed
  blade is far from its strength limit.
- Match the generator so the shaft spins {perf['1.0']['design_tsr']['rpm']:.0f}-{perf['2.0']['design_tsr']['rpm']:.0f} rpm at {perf['1.0']['design_tsr']['Q_Nm']:.2f}-{perf['2.0']['design_tsr']['Q_Nm']:.2f} N m
  (a small gearmotor used backwards, or a brushless outrunner with ~1:3 step-up).
"""
open(os.path.join(OUT, "README.md"), "w").write(txt)
print("wrote README.md")
