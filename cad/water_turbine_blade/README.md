# 8 in water turbine blade (3 in wide) for 1-2 m/s flow  -  revision 2 (reviewed)

Hydrokinetic (free-stream river / tidal) axial-flow turbine blade. Open `turbine_blade_8in.step`
in Fusion 360 with **File > Open > Open from my computer...** (or upload it to a project in the Data
Panel). It arrives as one solid body in millimetres; the tip sits at exactly 101.60 mm (4.000 in)
from the axis and the widest chord measures 76.20 mm (3.000 in).

Revision 2 incorporates an adversarial review by three independent reviewers (hydrodynamics,
CAD geometry, structure/practicality). The findings and what changed are in **`REVIEW.md`**.

| File | What it is |
|---|---|
| `turbine_blade_8in.step` | **One blade**, solid body, mm. Root is trimmed to a cylinder of radius 21.4 mm so it sinks 5 mm into the 2 in hub. |
| `turbine_rotor_8in_3blade.step` | Full rotor: 3 blades on a 2 in x 2 in hub with nose cone, blind 10 mm shaft bore, 3.2 mm cross-pin hole and two M4 grub-screw pilot holes. One solid (no blade-hub fillet: OpenCascade could not build one, add 1.5-2 mm in Fusion). |
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
| Hub | 2 in diameter (hub ratio 0.25), 2.0 in long, 28 mm ellipsoidal nose cone upstream |
| Blades | 3 |
| Max chord (blade width) | **76.2 mm = 3.00 in** at r = 40 mm (1.58 in) |
| Root chord (at hub surface) | 48.6 mm (1.91 in) - tapered so three roots fit the small hub with 15 mm between neighbours |
| Tip | elliptically rounded, 15.3 mm chord and 2.1 mm thick at the very tip |
| Twist | 29.1 deg at the root to 10.2 deg at the tip (chord angle from the rotor plane) |
| Airfoil | NACA 44xx family: 22 % thick at the root for strength, 14 % from 65 % radius outward |
| Max thickness | 10.7 mm at the root, 2.9 mm at 94 % radius |
| Trailing edge | 0.8 mm blunt (two 0.4 mm FDM perimeters) |
| Axial depth of the blade | 31.6 mm (1.24 in) - well inside the 3 in envelope |
| Stacking axis | 30 % chord, radial (Z axis) |
| Blade volume | 27.3 cm3 (about 35 g in PETG) |

**Coordinate frame:** +X is the flow direction (water enters on the -X face, where the nose cone is),
the blade runs along +Z, and the rotor axis is X. The camber (suction) side faces downstream. The rotor
turns **counter-clockwise when viewed from upstream**, which is **clockwise seen from the downstream /
generator side** - mind this when you wire a generator with a preferred direction.

**Building your own rotor in Fusion from the single blade:** import the blade, then
*Create > Pattern > Circular Pattern* (type Bodies, axis = X, quantity 3), model a hub of
50.8 mm diameter on the X axis, then *Modify > Combine* (Join) and add a 1.5-2 mm fillet
along the blade-hub junction. Or just open the rotor file, which already has all of this.

## Predicted performance (blade-element-momentum, 3 blades)

The polar model is Reynolds-dependent, so Cp varies with water speed. Operating tip-speed ratio
**3.25** (the Cp peak at 1.5 m/s). Cp stays within 5 % of its peak from
TSR 2.50 to 4.00.

| Water speed (m/s) | rpm | Shaft power (W) | Power in the stream (W) | Cp | Torque (N m) | Thrust (N) | Static torque at stall (N m) | Runaway rpm (no load) |
|---|---|---|---|---|---|---|---|---|
| 1.0 | 305 | 5.6 | 16 | 0.35 | 0.18 | 11 | 0.09 | 587 |
| 1.5 | 458 | 20.1 | 55 | 0.37 | 0.42 | 26 | 0.20 | 952 |
| 2.0 | 611 | 49.1 | 130 | 0.38 | 0.77 | 46 | 0.37 | 1269 |

Shaft power, not electrical: subtract generator, seal and bearing losses (typically 20-40 % at this size).

**What to expect in the water.** Treat the table as the upper end. Realistic Cp for a printed rotor of
this size is about **0.25-0.33** depending on surface finish, the nacelle behind the hub, generator
matching and water temperature (10 C water raises viscosity 30 % and costs a few points of Cp at 1 m/s).
Section Reynolds numbers at 1.5 m/s are 6.9e+04-1.5e+05 (4.6e+04-1.0e+05 at 1 m/s,
9.1e+04-2.0e+05 at 2 m/s) - low enough that the NACA 44xx sections run with laminar separation
bubbles, which the polar model approximates but does not resolve.

**Load matching.** A load whose torque rises with speed (a PM generator into a resistor or a battery
through a rectifier) keeps the rotor within 3 % of peak Cp from 1 to 2 m/s. A **constant-torque**
load sized for 1.5 m/s will stall the rotor at 1 m/s. With no load the rotor runs away to the rpm in
the last column (tip speed ~13 m/s at 2 m/s), where the tip can start to cavitate - fit a dump load
or a brake.

**Self-start.** Static torque at 1 m/s is only ~0.09 N m. Slotted PM generators have cogging torque of
0.05-0.3 N m and a lip seal adds 0.01-0.05 N m, which can exceed that. Use a low-cogging (coreless /
axial-flux) generator or accept that it starts only above ~1.3 m/s.

## How it was designed (honestly)

1. Planform: the outboard part follows a Schmitz optimum chord shape (momentum theory with wake
   rotation) at tip-speed ratio 4.0, scaled so the widest point is exactly 3 in at
   39 % radius; inboard the chord tapers smoothly to 64 % of that at the hub
   (the review showed root taper costs < 0.002 Cp and it makes the small hub work).
2. Twist: Schmitz inflow angle minus the design angle of attack, plus a global pitch offset
   (+6.0 deg) found by a BEM search for maximum peak Cp, plus -2.5 deg at the root
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

From the BEM thrust distribution (per blade: 15 N at 2 m/s, 34 N in a 3 m/s flood):

| Case | Root bending moment | Root stress | Peak stress (at r = 26 mm, where the section thins) |
|---|---|---|---|
| 2 m/s, operating | 0.66 N m | 1.55 MPa | 1.55 MPa |
| 3 m/s flood | 1.48 N m | 3.49 MPa | 3.49 MPa |

Against ~30 MPa for FDM PETG across layers the safety factor is > 8 even in a flood, and fatigue at
3e7 cycles (7-10 MPa endurance) still leaves > 4. Steady flow loads are not what breaks these blades:
a snag or a log strike at the 2.1 mm tip will. Print spares and fit a trash rack upstream
(it costs 10-20 % of the water speed, i.e. 30-50 % of the power, so size it generously).

## Making it

- Material: **PETG or ASA**. Not nylon (PA6 absorbs ~9 % water and loses most of its stiffness).
- Printing the single blade: it cannot stand on its root (the root face is a cylinder). Lay it on its
  flattest side with tree supports, or print it in a two-part mould. 4+ perimeters, 100 % infill.
- Printing the rotor: hub axis vertical, nose down, tree supports under the blades. The 0.8 mm
  trailing edge and the 2.1 mm tip survive support removal if you use tree supports with a
  0.2 mm gap; remove them with a knife, not pliers.
- Hub: the 10 mm bore is blind (shaft enters from the downstream face, 51 mm deep). Drive the
  rotor with the 3.2 mm cross-pin through a drilled shaft (pin shear ~120 N vs 0.6 N m load: fine) and
  lock it with two M4 grub screws in the pilot holes (tap them, or drill to 5.6 mm for heat-set
  inserts). Use a stainless shaft, two sealed bearings and a lip seal; the thrust is < 50 N.
- Balance the rotor after printing (equal blade mass to 0.5 g).

## Generator

Shaft speed 305-611 rpm at 0.18-0.77 N m. Direct drive needs a generator rated for
300-700 rpm (a 3-phase PMG, or a brushless outrunner with **Kv <= 50**); with a 1:3 step-up, Kv <= 150.
Common hobby outrunners (Kv 500-1000) give only 1-2 V even geared. A high-ratio gearmotor run
backwards adds 0.03-0.1 N m of gear friction, which hurts self-start. Expect 4-34 W electrical.
