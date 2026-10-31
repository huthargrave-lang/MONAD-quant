#!/usr/bin/env python
"""Rotor candidates for the v3 drum hub (r_hub set by the 76.2 mm drum + carrier wall).
Uses the reviewed BEM (make_blade.py, rev 2: Re-dependent NACA 44xx polar, Prandtl tip/hub loss).
Candidate planforms: Schmitz-shaped chord with the max chord capped so the root fits the drum."""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "water_turbine_blade"))
import numpy as np
import make_blade as mb
R_HUB = 42.0
mb.R_HUB = R_HUB; mb.R_ROOT_EXT = R_HUB - 3.0
mb.TC_ROOT = 0.24; mb.TC_TIP = 0.15; mb.TE_THICK = 1.0; mb.TIP_CHORD_FRAC = 0.55
lam_scan = np.arange(2.0, 5.51, 0.25)
results = []
for cmax in (50.0, 60.0, 70.0):
    mb.C_MAX = cmax
    for peak in (0.50, 0.58):
        mb.PEAK_R = peak
        best = None
        for lg in (3.0, 4.0, 5.0):
            for db in (2.0, 4.0, 6.0, 8.0):
                bl = mb.design_blade(lg, db)
                cps = [mb.bem(bl, l, 1.5, n_el=40)["cp"] for l in lam_scan]
                j = int(np.argmax(cps))
                if best is None or cps[j] > best[0]:
                    best = (cps[j], lg, db, lam_scan[j], bl)
        cp15, lg, db, lam, bl = best
        perf = {V: mb.bem(bl, lam, V) for V in (1.0, 1.5, 2.0)}
        root_ax = bl["chord"][0] * math.sin(math.radians(bl["twist"][0])) + bl["chord"][0] * bl["tc"][0] * math.cos(math.radians(bl["twist"][0]))
        results.append(dict(cmax=cmax, peak=peak, lg=lg, db=db, tsr=float(lam), cp15=cp15, root_chord=float(bl["chord"][0]), root_twist=float(bl["twist"][0]),
                            root_axial_extent=root_ax, tip_chord=float(bl["chord"][-1]),
                            perf={str(V): dict(rpm=p["rpm"], P=p["P"], Q=p["Q"], T=p["T"], cp=p["cp"]) for V, p in perf.items()},
                            static_Q={str(V): mb.bem(bl, 0.1, V)["Q"] for V in (1.0, 1.5, 2.0)}))
        print(f"cmax {cmax:.0f} peak {peak:.2f}: lg {lg} db {db:+.0f} -> TSR {lam:.2f} Cp(1.5) {cp15:.3f} | P 1/1.5/2 = {perf[1.0]['P']:.1f}/{perf[1.5]['P']:.1f}/{perf[2.0]['P']:.1f} W | root chord {bl['chord'][0]:.1f} mm twist {bl['twist'][0]:.1f} deg axial {root_ax:.1f} mm | static Q(1 m/s) {results[-1]['static_Q']['1.0']:.3f} N m")
json.dump(results, open("rotor_v3_candidates.json", "w"), indent=1)
