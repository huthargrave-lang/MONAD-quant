#!/usr/bin/env python3
"""Physical feasibility before any blade optimisation: hydraulic power, Betz and practical bounds, the GL60 winding-resistance
question, loss shares along the chain, direct drive vs a modest gear ratio.  Writes feasibility.json and fig1_hydraulic_power.png."""
import json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bem_lowflow as bm, generator_lowflow as gl
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "..", "out")
tabs = json.load(open(os.path.join(HERE, "polars_cache.json")))
VS = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.25, 1.5, 2.0]
RHO = 1000.0; R = bm.R_TIP; A_disc = math.pi * R * R
hubs = {"A (rear nacelle, hub r 28 mm)": 0.028, "B (hub drum, blade root r 48.2 mm)": 0.0482}
rows = []
# representative rotor for the bound: 3-blade SG6043 design at TSR 3 (the optimiser refines this later; the bound is insensitive)
blades = {k: bm.design(tabs, "sg6043", 3, 3.0, r_hub=rh) for k, rh in hubs.items()}
lams = np.arange(0.5, 7.01, 0.25)
res = {}
for V in VS:
    row = dict(V=V, P_disc=0.5 * RHO * A_disc * V ** 3)
    for k, rh in hubs.items():
        A_ann = math.pi * (R * R - rh * rh); P_ann = 0.5 * RHO * A_ann * V ** 3
        cur = [bm.bem(blades[k], l, V) for l in lams]
        cp = max(c["cp"] for c in cur)
        Qs = [c["Q"] for c in cur]
        fr = gl.FRICTION["A_rear_nacelle"] if k.startswith("A") else gl.FRICTION["B_hub_drum"]
        op_ideal = gl.operating_point(V, lams, np.array(Qs), fr, gl.CONVERTERS["ideal"], r_hub_m=rh)
        op_boost = gl.operating_point(V, lams, np.array(Qs), fr, gl.CONVERTERS["boost_clamp"], r_hub_m=rh)
        op_bb = gl.operating_point(V, lams, np.array(Qs), fr, gl.CONVERTERS["buckboost"], r_hub_m=rh)
        op_direct = gl.operating_point(V, lams, np.array(Qs), fr, gl.CONVERTERS["direct"], r_hub_m=rh, mode="cv")
        row[k] = dict(P_annulus=P_ann, P_betz=16 / 27 * P_ann, cp_bem=cp, P_shaft=cp * 0.5 * RHO * A_disc * V ** 3,
                      ideal=op_ideal, boost=op_boost, buckboost=op_bb, direct=op_direct)
    rows.append(row)
# winding-resistance question: copper loss share at the rotor's own torque/speed, and the voltage at the MPP
A = "A (rear nacelle, hub r 28 mm)"
print("V   P_disc  P_ann(A) Betz(A)  Cp(A)  Pshaft  | ideal: Vdc  I     Pout  | boost+clamp Pout (region) | buck-boost Pout | direct-battery Pout")
for row in rows:
    a = row[A]; i, b, bb, d = a["ideal"], a["boost"], a["buckboost"], a["direct"]
    print(f"{row['V']:.2f} {row['P_disc']:7.2f} {a['P_annulus']:7.2f} {a['P_betz']:7.2f} {a['cp_bem']:.3f} {a['P_shaft']:6.2f}  | "
          f"{(i['Vdc'] if i else 0):5.1f} {(i['I'] if i else 0):5.2f} {(i['Pout'] if i else 0):6.2f} | {(b['Pout'] if b else 0):6.2f} ({b['region'] if b else '-'}) | {(bb['Pout'] if bb else 0):6.2f} | {(d['Pout'] if d else 0):6.2f}")
# loss shares at each V for arrangement A with the boost converter (ideal MPPT inside the window)
shares = []
for row in rows:
    a = row[A]; b = a["boost"]
    if not b: shares.append(dict(V=row["V"], none=True)); continue
    P_hyd = a["P_annulus"]; Psh = b["Pshaft"]
    hydro = P_hyd - Psh; fric = b["Pfric"]; cu = b["Pcu"]; dio = b["Pdiode"]; conv = b["Pdc"] - b["Pout"]
    shares.append(dict(V=row["V"], P_hyd=P_hyd, hydro=hydro, friction=fric, copper=cu, diode=dio, converter=conv, out=b["Pout"], region=b["region"], Vdc=b["Vdc"], I=b["I"], rpm=b["rpm"], lam=b["lam"]))
    print(f"V {row['V']:.2f}: hydraulic(annulus) {P_hyd:6.2f} W -> hydro loss {hydro/P_hyd*100:4.0f} % | friction {fric/P_hyd*100:4.1f} % | copper {cu/P_hyd*100:4.1f} % | diodes {dio/P_hyd*100:4.1f} % | converter {conv/P_hyd*100:4.1f} % | OUT {b['Pout']:5.2f} W ({b['Pout']/P_hyd*100:.0f} %) at {b['rpm']:.0f} rpm, {b['Vdc']:.1f} V, {b['I']:.2f} A [{b['region']}]")
# gear ratio study (arrangement A, ideal MPPT, gear efficiency 0.96 per stage + 5 mN m extra friction referred to the rotor)
gear = []
for N in (1.0, 2.0, 3.0):
    rowg = dict(N=N)
    for row in rows:
        if row["V"] > 1.0: continue
        a = row[A]; cur = [bm.bem(blades[A], l, row["V"]) for l in lams]; Qs = np.array([c["Q"] for c in cur])
        fr = dict(gl.FRICTION["A_rear_nacelle"]); 
        if N > 1: fr["brg_run"] += 0.005; fr["brg_break"] += 0.008
        Qs_eff = Qs * (0.96 if N > 1 else 1.0)
        op = gl.operating_point(row["V"], lams, Qs_eff, fr, gl.CONVERTERS["ideal"], N=N, r_hub_m=0.028)
        ob = gl.operating_point(row["V"], lams, Qs_eff, fr, gl.CONVERTERS["boost_clamp"], N=N, r_hub_m=0.028)
        rowg[str(row["V"])] = (op["Pout"] if op else 0.0, op["Vdc"] if op else 0.0, ob["Pout"] if ob else 0.0)
    gear.append(rowg)
    print(f"gear ratio {N:.0f}: " + "  ".join(f"{k}: ideal {v[0]:.2f} W ({v[1]:.1f} V) / boost {v[2]:.2f} W" for k, v in rowg.items() if k != "N"))
json.dump(dict(rows=rows, shares=shares, gear=gear, hubs=hubs, assumptions=dict(GEN=gl.GEN, FRICTION=gl.FRICTION, CONVERTERS=gl.CONVERTERS, RECTIFIER=gl.RECTIFIER)),
          open(os.path.join(HERE, "feasibility.json"), "w"), indent=1, default=float)
# ---------------- figure 1
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(10, 6), facecolor="#fcfcfb")
Vv = np.array([r["V"] for r in rows])
ax.plot(Vv, [r["P_disc"] for r in rows], "k-", lw=2, label="hydraulic power through the 203.2 mm disc, 1/2 rho A V^3")
ax.plot(Vv, [r[A]["P_annulus"] for r in rows], "k--", lw=1.5, label="through the blade annulus (hub r 28 mm, arrangement A)")
ax.plot(Vv, [r[A]["P_betz"] for r in rows], "-", color="#7a7a7a", lw=1.5, label="Betz limit on the annulus (16/27)")
ax.plot(Vv, [r[A]["P_shaft"] for r in rows], "-o", color="#1d5fa8", ms=4, label="BEM rotor shaft power, representative 3-blade SG6043 (Re-dependent polars)")
ax.plot(Vv, [(r[A]["ideal"]["Pout"] if r[A]["ideal"] else 0) for r in rows], "-s", color="#2a8a4a", ms=4, label="electrical, lossless converter (upper bound: friction + copper + diodes only)")
ax.plot(Vv, [(r[A]["boost"]["Pout"] if r[A]["boost"] else 0) for r in rows], "-^", color="#c4342d", ms=5, label="electrical at 12 V, boost MPPT + clamp (GVB-8 class), model")
ax.plot(Vv, [(r[A]["direct"]["Pout"] if r[A]["direct"] else 0) for r in rows], ":d", color="#b06f00", ms=5, label="electrical, rectifier straight into the 12.8 V battery (no converter)")
ax.set_yscale("log"); ax.set_ylim(0.05, 500); ax.set_xlabel("water speed (m/s)"); ax.set_ylabel("power (W, log scale)"); ax.grid(True, which="both", alpha=0.3)
ax.axvspan(0.5, 1.0, color="#1d5fa8", alpha=0.06); ax.text(0.52, 300, "primary range 0.5-1.0 m/s", fontsize=9, color="#1d5fa8")
ax.set_title("Fig. 1  Available hydraulic power vs water speed and the model's electrical bounds (GL60 KV25, assumptions in the report)", fontsize=10, loc="left")
ax.legend(fontsize=8, loc="lower right"); fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig1_hydraulic_power.png"), dpi=130, facecolor="#fcfcfb"); print("fig1 written")
