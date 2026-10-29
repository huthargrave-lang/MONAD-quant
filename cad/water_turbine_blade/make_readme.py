#!/usr/bin/env python
"""Write README.md for the blade package from design_spec.json / blade_stations.csv."""
import csv, json, os
OUT = os.path.dirname(os.path.abspath(__file__)); IN = 25.4
s = json.load(open(os.path.join(OUT, "design_spec.json")))
rows = list(csv.DictReader(open(os.path.join(OUT, "blade_stations.csv"))))
root, tip = rows[0], rows[-1]
perf, st = s["performance"], s["structural"]
tsr = s["cp_curve"]["tsr"]
def pr(V):
    d = perf[V]["operating"]; b = perf[V]["best_at_this_speed"]
    return (f"| {V} | {d['rpm']:.0f} | {d['P_W']:.1f} | {perf[V]['available_W']:.0f} | {d['cp']:.2f} | {d['Q_Nm']:.2f} | {d['T_N']:.0f} "
            f"| {perf[V]['static_torque_Nm']:.2f} | {perf[V]['runaway_rpm']:.0f} |")
cp15 = s["cp_curve"]["cp_1.5"]
plateau = [t for t, c in zip(tsr, cp15) if c >= 0.95 * max(cp15)]
re_vals = [float(r["operating_Re_1p5ms"]) for r in rows[:-3]]
fil = s["junction_fillet_mm"]
txt = f"""# 8 in water turbine blade (3 in wide) for 1-2 m/s flow  -  revision 2 (reviewed)

Hydrokinetic (free-stream river / tidal) axial-flow turbine blade. Open `turbine_blade_8in.step`
in Fusion 360 with **File > Open > Open from my computer...** (or upload it to a project in the Data
Panel). It arrives as one solid body in millimetres; the tip sits at exactly 101.60 mm (4.000 in)
from the axis and the widest chord measures {s['max_chord_mm']:.2f} mm (3.000 in).

Revision 2 incorporates an adversarial review by three independent reviewers (hydrodynamics,
CAD geometry, structure/practicality). The findings and what changed are in **`REVIEW.md`**.

| File | What it is |
|---|---|
| `turbine_blade_8in.step` | **One blade**, solid body, mm. Root is trimmed to a cylinder of radius {s['root_trim_radius_mm']:.1f} mm so it sinks 5 mm into the {s['hub_diameter_in']:.0f} in hub. |
| `turbine_rotor_8in_3blade.step` | Full rotor: 3 blades on a {s['hub_diameter_in']:.0f} in x 2 in hub with nose cone, blind {s['hub_bore_mm']:.0f} mm shaft bore, {s['pin_hole_mm']:.1f} mm cross-pin hole and two M4 grub-screw pilot holes. One solid{', blade-hub fillet ' + str(fil) + ' mm' if fil else ' (no blade-hub fillet: OpenCascade could not build one, add 1.5-2 mm in Fusion)'}. |
| `turbine_blade_8in.stl`, `turbine_rotor_8in_3blade.stl` | Same blade / rotor as meshes for slicers (or Fusion *Insert > Insert Mesh*). |
| `blade_stations.csv` | Radius, chord, twist, thickness, airfoil and the **operating** angle of attack / CL / Reynolds number at every section (plus the Schmitz design inputs, labelled as such). |
| `sections_for_fusion_csv/` | Each 3-D section outline as x,y,z in **cm**, one closed loop per file, for Fusion's built-in *ImportSplineCSV* script if you want to re-loft natively. |
| `design_spec.json` | Every number below plus the Cp(TSR) and power curves at 1, 1.5 and 2 m/s. |
| `REVIEW.md` | The independent review findings and their resolution. |
| `make_blade.py`, `make_preview.py`, `make_readme.py` | Regenerate everything (`pip install cadquery numpy matplotlib`, ~2 min). |

## Geometry

| | |
|---|---|
| Rotor diameter | 8.000 in (203.2 mm) |
| Hub | {s['hub_diameter_in']:.0f} in diameter (hub ratio {s['hub_ratio']:.2f}), 2.0 in long, {s['nose_cone_length_mm']:.0f} mm ellipsoidal nose cone upstream |
| Blades | {s['blades']} |
| Max chord (blade width) | **{s['max_chord_mm']:.1f} mm = {s['max_chord_in']:.2f} in** at r = {s['max_chord_r_mm']:.0f} mm ({s['max_chord_r_mm']/IN:.2f} in) |
| Root chord (at hub surface) | {s['root_chord_mm']:.1f} mm ({s['root_chord_mm']/IN:.2f} in) - tapered so three roots fit the small hub with {s['blade_to_blade_clearance_mm']:.0f} mm between neighbours |
| Tip | elliptically rounded, {s['tip_chord_mm']:.1f} mm chord and {s['tip_thickness_mm']:.1f} mm thick at the very tip |
| Twist | {s['twist_root_deg']:.1f} deg at the root to {s['twist_tip_deg']:.1f} deg at the tip (chord angle from the rotor plane) |
| Airfoil | NACA 44xx family: 22 % thick at the root for strength, 14 % from 65 % radius outward |
| Max thickness | {s['root_thickness_mm']:.1f} mm at the root, {float(rows[-4]['max_thickness_mm']):.1f} mm at 94 % radius |
| Trailing edge | {s['trailing_edge_thickness_mm']:.1f} mm blunt (two 0.4 mm FDM perimeters) |
| Axial depth of the blade | {s['axial_extent_mm']:.1f} mm ({s['axial_extent_in']:.2f} in) - well inside the 3 in envelope |
| Stacking axis | {s['pitch_axis_fraction']*100:.0f} % chord, radial (Z axis) |
| Blade volume | {s['blade_volume_mm3']/1000:.1f} cm3 (about {s['blade_volume_mm3']/1000*1.27:.0f} g in PETG) |

**Coordinate frame:** +X is the flow direction (water enters on the -X face, where the nose cone is),
the blade runs along +Z, and the rotor axis is X. The camber (suction) side faces downstream. The rotor
turns **counter-clockwise when viewed from upstream**, which is **clockwise seen from the downstream /
generator side** - mind this when you wire a generator with a preferred direction.

**Building your own rotor in Fusion from the single blade:** import the blade, then
*Create > Pattern > Circular Pattern* (type Bodies, axis = X, quantity 3), model a hub of
{2*s['hub_radius_mm']:.1f} mm diameter on the X axis, then *Modify > Combine* (Join) and add a 1.5-2 mm fillet
along the blade-hub junction. Or just open the rotor file, which already has all of this.

## Predicted performance (blade-element-momentum, 3 blades)

The polar model is Reynolds-dependent, so Cp varies with water speed. Operating tip-speed ratio
**{s['operating_tsr']:.2f}** (the Cp peak at 1.5 m/s). Cp stays within 5 % of its peak from
TSR {min(plateau):.2f} to {max(plateau):.2f}.

| Water speed (m/s) | rpm | Shaft power (W) | Power in the stream (W) | Cp | Torque (N m) | Thrust (N) | Static torque at stall (N m) | Runaway rpm (no load) |
|---|---|---|---|---|---|---|---|---|
{pr('1.0')}
{pr('1.5')}
{pr('2.0')}

Shaft power, not electrical: subtract generator, seal and bearing losses (typically 20-40 % at this size).

**What to expect in the water.** Treat the table as the upper end. Realistic Cp for a printed rotor of
this size is about **0.25-0.33** depending on surface finish, the nacelle behind the hub, generator
matching and water temperature (10 C water raises viscosity 30 % and costs a few points of Cp at 1 m/s).
Section Reynolds numbers at 1.5 m/s are {min(re_vals):.1e}-{max(re_vals):.1e} ({min(re_vals)*0.67:.1e}-{max(re_vals)*0.67:.1e} at 1 m/s,
{min(re_vals)*1.33:.1e}-{max(re_vals)*1.33:.1e} at 2 m/s) - low enough that the NACA 44xx sections run with laminar separation
bubbles, which the polar model approximates but does not resolve.

**Load matching.** A load whose torque rises with speed (a PM generator into a resistor or a battery
through a rectifier) keeps the rotor within 3 % of peak Cp from 1 to 2 m/s. A **constant-torque**
load sized for 1.5 m/s will stall the rotor at 1 m/s. With no load the rotor runs away to the rpm in
the last column (tip speed ~13 m/s at 2 m/s), where the tip can start to cavitate - fit a dump load
or a brake.

**Self-start.** Static torque at 1 m/s is only ~{perf['1.0']['static_torque_Nm']:.2f} N m. Slotted PM generators have cogging torque of
0.05-0.3 N m and a lip seal adds 0.01-0.05 N m, which can exceed that. Use a low-cogging (coreless /
axial-flux) generator or accept that it starts only above ~1.3 m/s.

## How it was designed (honestly)

1. Planform: the outboard part follows a Schmitz optimum chord shape (momentum theory with wake
   rotation) at tip-speed ratio {s['geometry_schmitz_tsr']:.1f}, scaled so the widest point is exactly 3 in at
   {s['max_chord_r_mm']/s['tip_radius_mm']*100:.0f} % radius; inboard the chord tapers smoothly to {s['root_chord_mm']/s['max_chord_mm']*100:.0f} % of that at the hub
   (the review showed root taper costs < 0.002 Cp and it makes the small hub work).
2. Twist: Schmitz inflow angle minus the design angle of attack, plus a global pitch offset
   ({s['pitch_offset_deg']:+.1f} deg) found by a BEM search for maximum peak Cp, plus {s['root_twist_adjust_deg']:+.1f} deg at the root
   (blending out by 50 % radius) so the thick root sections run at positive angle of attack.
3. Verification: BEM with Prandtl tip loss, AeroDyn-form hub loss, Buhl high-induction correction,
   Reynolds-dependent NACA 44xx polar (anchored on XFOIL-class data at Re 1.5e5, drag scaling as
   Re^-0.8), Viterna post-stall, 80 radial elements. An independent BEM written by a reviewer
   reproduced the original numbers to four digits.

A 3 in wide blade on an 8 in, 3-blade rotor is a **high-solidity** rotor: the sections only need
CL ~ 0.3-0.5 (about 0 deg angle of attack on the cambered NACA 44xx) to load the rotor optimally,
which is why the twist looks flat. The upside is strong torque at low speed; the downside is that
BEM is at the edge of its validity at the root (solidity ~0.9) - the inboard 20 % of the blade
contributes little power either way.

## Structure

From the BEM thrust distribution (per blade: {st['2.0']['thrust_per_blade_N']:.0f} N at 2 m/s, {st['3.0']['thrust_per_blade_N']:.0f} N in a 3 m/s flood):

| Case | Root bending moment | Root stress | Peak stress (at r = {st['2.0']['max_stress_r_mm']:.0f} mm, where the section thins) |
|---|---|---|---|
| 2 m/s, operating | {st['2.0']['root_moment_Nm']:.2f} N m | {st['2.0']['root_stress_MPa']:.2f} MPa | {st['2.0']['max_stress_MPa']:.2f} MPa |
| 3 m/s flood | {st['3.0']['root_moment_Nm']:.2f} N m | {st['3.0']['root_stress_MPa']:.2f} MPa | {st['3.0']['max_stress_MPa']:.2f} MPa |

Against ~30 MPa for FDM PETG across layers the safety factor is > 8 even in a flood, and fatigue at
3e7 cycles (7-10 MPa endurance) still leaves > 4. Steady flow loads are not what breaks these blades:
a snag or a log strike at the {s['tip_thickness_mm']:.1f} mm tip will. Print spares and fit a trash rack upstream
(it costs 10-20 % of the water speed, i.e. 30-50 % of the power, so size it generously).

## Making it

- Material: **PETG or ASA**. Not nylon (PA6 absorbs ~9 % water and loses most of its stiffness).
- Printing the single blade: it cannot stand on its root (the root face is a cylinder). Lay it on its
  flattest side with tree supports, or print it in a two-part mould. 4+ perimeters, 100 % infill.
- Printing the rotor: hub axis vertical, nose down, tree supports under the blades. The {s['trailing_edge_thickness_mm']:.1f} mm
  trailing edge and the {s['tip_thickness_mm']:.1f} mm tip survive support removal if you use tree supports with a
  0.2 mm gap; remove them with a knife, not pliers.
- Hub: the {s['hub_bore_mm']:.0f} mm bore is blind (shaft enters from the downstream face, {s['hub_length_mm']:.0f} mm deep). Drive the
  rotor with the {s['pin_hole_mm']:.1f} mm cross-pin through a drilled shaft (pin shear ~120 N vs 0.6 N m load: fine) and
  lock it with two M4 grub screws in the pilot holes (tap them, or drill to 5.6 mm for heat-set
  inserts). Use a stainless shaft, two sealed bearings and a lip seal; the thrust is < 50 N.
- Balance the rotor after printing (equal blade mass to 0.5 g).

## Generator

Shaft speed {perf['1.0']['operating']['rpm']:.0f}-{perf['2.0']['operating']['rpm']:.0f} rpm at {perf['1.0']['operating']['Q_Nm']:.2f}-{perf['2.0']['operating']['Q_Nm']:.2f} N m. Direct drive needs a generator rated for
300-700 rpm (a 3-phase PMG, or a brushless outrunner with **Kv <= 50**); with a 1:3 step-up, Kv <= 150.
Common hobby outrunners (Kv 500-1000) give only 1-2 V even geared. A high-ratio gearmotor run
backwards adds 0.03-0.1 N m of gear friction, which hurts self-start. Expect {perf['1.0']['operating']['P_W']*0.7:.0f}-{perf['2.0']['operating']['P_W']*0.7:.0f} W electrical.
"""
open(os.path.join(OUT, "README.md"), "w").write(txt)
print("wrote README.md")
