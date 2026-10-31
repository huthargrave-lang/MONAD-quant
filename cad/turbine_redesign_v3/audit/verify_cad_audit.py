#!/usr/bin/env python
"""Independent re-measurement of the packet's A_assembly.step (Open CASCADE via cadquery)."""
import json, math, sys
import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder
STEP = "/home/user/packet_in/p1/Claude_turbine_redesign_packet/01_original_inputs/A_assembly.step"
names = ["rotor","nacelle_tube","front_cap","rear_cap","oring_0","oring_1","oring_2","oring_3","lip_seal","bearing_0","bearing_1","shaft","speedi_sleeve","collar","coupling","bell_adapter","motor","clamp_half_1","clamp_half_2","strut_0","strut_1","strut_2","duct_ring"]
shape = cq.importers.importStep(STEP)
sol = shape.solids().vals()
print(f"solids imported: {len(sol)}")
rows = []
for i, s in enumerate(sol):
    bb = s.BoundingBox(); n = names[i] if i < len(names) else f"solid_{i}"
    rows.append((n, s, bb))
    print(f"{i+1:2d} {n:14s} X {bb.xmin:8.3f}..{bb.xmax:8.3f}  r_max {max(abs(bb.ymin),abs(bb.ymax),abs(bb.zmin),abs(bb.zmax)):7.2f}  vol {s.Volume():10.1f}  valid {s.isValid()}")
d = {n: (s, bb) for n, s, bb in rows}
xmin = min(bb.xmin for _, _, bb in rows); xmax = max(bb.xmax for _, _, bb in rows)
print(f"\nRIGID DEPTH (all solids incl. duct ref): {xmax - xmin:.3f} mm  (review: 188.6)")
rb = d["rotor"][1]; print(f"rotor alone: {rb.xmax - rb.xmin:.3f} mm (review: 78.8)")
def common(a, b):
    try: return d[a][0].intersect(d[b][0]).Volume()
    except Exception as e: return float("nan")
for a, b in [("rotor","collar"),("nacelle_tube","oring_0"),("lip_seal","speedi_sleeve"),("lip_seal","shaft"),("strut_0","duct_ring"),("clamp_half_1","strut_2"),("clamp_half_2","strut_0"),("bearing_1","front_cap"),("coupling","bell_adapter"),("shaft","coupling")]:
    print(f"common volume {a}/{b}: {common(a,b):9.2f} mm3")
b0, b1 = d["bearing_0"][1], d["bearing_1"][1]; fc = d["front_cap"][1]
print(f"bearing centres: {0.5*(b0.xmin+b0.xmax):.3f} and {0.5*(b1.xmin+b1.xmax):.3f} -> spacing {0.5*(b1.xmin+b1.xmax)-0.5*(b0.xmin+b0.xmax):.3f} mm (review: 8)")
print(f"rear bearing protrudes past front-cap end by {b1.xmax - fc.xmax:.3f} mm (review: 0.5)")
# cylindrical faces of the shaft and front cap: any groove radii?
def cyl_radii(s):
    out = []
    for f in s.Faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() == GeomAbs_Cylinder:
            out.append(round(ad.Cylinder().Radius(), 3))
    return sorted(set(out))
print("shaft cylindrical radii:", cyl_radii(d["shaft"][0]), " -> circlip groove (r=5.75) present?", 5.75 in cyl_radii(d["shaft"][0]))
print("front cap cylindrical radii:", cyl_radii(d["front_cap"][0]), " -> internal circlip groove (r~14.6-15.2)?", any(14.5 < r < 15.5 for r in cyl_radii(d["front_cap"][0])))
print("nacelle tube cylindrical radii:", cyl_radii(d["nacelle_tube"][0]), " -> radial screw holes (r=1.6)?", 1.6 in cyl_radii(d["nacelle_tube"][0]))
print("rear cap radii:", cyl_radii(d["rear_cap"][0]))
print("motor radii:", cyl_radii(d["motor"][0]), " (no mounting holes modelled if only 10/33.5/34.5)")
print("names containing 'cable'/'gland'/'vent':", [n for n, _, _ in rows if any(k in n for k in ("cable","gland","vent","penetr"))], "-> none modelled")
duct = d["duct_ring"][1]; print(f"duct ring X {duct.xmin:.1f}..{duct.xmax:.1f} vs rotor X {rb.xmin:.1f}..{rb.xmax:.1f}: duct entirely behind rotor plane -> {duct.xmin > rb.xmax}")
