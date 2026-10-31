#!/usr/bin/env python3
"""Dimensioned axial stack-ups for the candidate architectures against the 76 mm TOTAL OPERATING depth.
Every entry is a real component length (manufacturer or catalogue) or a stated design allowance."""
stacks = {
 "A  current Configuration A (as audited)": [("nose", 28.0), ("hub", 50.8), ("gap", 3.0), ("front flange", 6.0), ("tube", 94.8), ("rear flange", 6.0), ("WetLink penetrator + nut + cable bend (not modelled)", 26.0)],
 "D1 through-spindle drum rotor (GL60 inside the hub), all parts in series": [
     ("dome / nose over the front cap (print)", 8.0), ("front cap outside the tube: 0 (cap flange = dome base)", 0.0),
     ("front cap plug: 2 x O-ring (3.6 groove + 2 land) + front bearing 6702 (4 mm) seat", 13.0),
     ("clearance + TPU drive disc", 3.0), ("GL60 KV25 length (manufacturer 22.3)", 22.3), ("clearance stator/collar", 1.5),
     ("stator mount collar flange (part of spindle) inside the drum", 4.0),
     ("rear cap plug: rear bearing 6902 (7) + 1.5 wall + 2 x O-ring grooves", 14.0), ("rear cap outer: lip seal 15x22x4 (4) + 1 lip-side land", 5.0),
     ("running gap drum/boss", 2.0), ("stationary boss: spindle clamp + cable 90 deg exit + 3 strut roots", 12.0)],
 "D1 with every allowance minimised (bearings 6702/6702, seal 4 mm, grooves at 5 mm pitch)": [
     ("dome", 7.0), ("front cap plug (O-rings + 6702)", 11.0), ("disc", 2.5), ("GL60", 22.3), ("clearance", 1.0), ("collar flange", 3.0),
     ("rear cap plug (6702 + O-rings)", 11.0), ("seal 15x22x4 + land", 5.0), ("gap", 1.5), ("boss", 10.0)],
}
for name, items in stacks.items():
    tot = sum(v for _, v in items)
    print(f"{name}\n   TOTAL {tot:.1f} mm  ({tot/25.4:.2f} in; target 76: {'OVER by %.1f' % (tot-76) if tot > 76 else 'within, margin %.1f' % (76-tot)})")
    for n, v in items: print(f"      {v:5.1f}  {n}")
print("\nItems that cannot shrink: GL60 22.3 mm (manufacturer); two O-rings per cap need >= 2 x 3.6 groove + 3 lands ~ 10 mm of plug; a lip seal needs 4-5 mm plus a land; two bearings; a dome of some kind.")
print("Blade axial extent must also fit inside the drum length: root chord c at twist beta -> c*sin(beta) + t: e.g. 45 mm x sin(28 deg) + 6 = 27 mm -> fits a 55 mm drum.")
