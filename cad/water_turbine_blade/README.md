# 8 in water turbine blade (3 in wide) for 1-2 m/s flow

Hydrokinetic (free-stream river / tidal) axial-flow turbine blade. Open `turbine_blade_8in.step`
in Fusion 360 with **File > Open > Open from my computer...** (or upload it to a project in the Data
Panel). It arrives as one solid body in millimetres; the tip sits at exactly 101.60 mm (4.000 in)
from the axis and the widest chord measures 76.20 mm (3.000 in).

| File | What it is |
|---|---|
| `turbine_blade_8in.step` | **One blade**, solid body, mm. Root is trimmed to a cylinder of radius 32 mm so it sinks ~6 mm into a 3 in hub. |
| `turbine_rotor_8in_3blade.step` | Full rotor: 3 blades + 3 in x 2 in hub with a 10 mm bore, single solid, ready to print or modify. |
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
| Blades | 3 |
| Max chord (blade width) | **76.2 mm = 3.00 in** at ~1.557 in radius |
| Root chord (at hub surface) | 75.6 mm (2.98 in) |
| Tip | elliptically rounded, 10.7 mm chord at the very tip |
| Twist | 22.3 deg at the root to 10.2 deg at the tip (chord angle from the rotor plane) |
| Airfoil | NACA 4422 at the root (22 % thick for strength) blending to NACA 4412 from 65 % radius outward |
| Max thickness | 16.6 mm at the root, 3.5 mm near the tip |
| Trailing edge | 0.6 mm blunt (printable / machinable) |
| Axial depth of the blade | 31.4 mm (1.24 in) - well inside the 3 in envelope |
| Stacking axis | 30 % chord, radial (Z axis) |
| Blade volume | 22.2 cm3 (about 28 g in PETG) |

**Coordinate frame:** +X is the flow direction (water enters on the -X face), the blade runs along +Z,
and the rotor axis is X. The camber (suction) side faces downstream. The rotor turns
**counter-clockwise when viewed from upstream**. To build your own rotor from the single blade,
circular-pattern it 3x about the X axis and join it to a hub of 3 in diameter (or edit the hub in the rotor file).

## Predicted performance (blade-element-momentum, 3 blades)

Recommended operating point: tip-speed ratio **3.50** (peak Cp = **0.32**).
The Cp curve is flat: within 5 % of peak from TSR 2.75 to 4.25, so a fixed
generator load works across the 1-2 m/s band.

| Water speed (m/s) | rpm | Shaft power (W) | Power in the stream (W) | Torque (N m) | Thrust (N) |
|---|---|---|---|---|---|
| 1.0 | 329 | 5.2 | 16 | 0.15 | 10 |
| 1.5 | 493 | 17.7 | 55 | 0.34 | 22 |
| 2.0 | 658 | 41.9 | 130 | 0.61 | 39 |

Cp vs TSR: 1.50: 0.18, 2.00: 0.27, 2.50: 0.30, 3.00: 0.32, 3.50: 0.32, 4.00: 0.32, 4.50: 0.30, 5.00: 0.26, 5.50: 0.20, 6.00: 0.13

## How it was designed

1. Schmitz optimum chord and twist (momentum theory including wake rotation) for 3 blades, with the
   design angle of attack 4-5.5 deg so that the widest point of the optimum blade is exactly 3 in.
2. A short BEM-driven search over the planform taper (Schmitz shape at TSR 5.4,
   scaled to 3 in max chord) and a global pitch offset (+8.75 deg) to maximise peak Cp.
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
- Loads are small: at 2 m/s the whole rotor sees ~39 N of thrust (13 N per blade), so a printed
  blade is far from its strength limit.
- Match the generator so the shaft spins 329-658 rpm at 0.15-0.61 N m
  (a small gearmotor used backwards, or a brushless outrunner with ~1:3 step-up).
