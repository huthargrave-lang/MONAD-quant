#!/usr/bin/env python3
"""Coupled rotor + GL60 + converter prediction for the simplified v5 arrangement (same optimised blade, 28 mm hub, housing front wall 78 mm
2 mm behind the hub, ONE 12 mm lip seal + ONE 6001 bearing), compared with the v4 arrangement A (8 mm seal + 608).  Writes out/v5_results.json
and out/fig_v5_power.png.  Nothing here is measured."""
import json, math, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); V4 = os.path.abspath(os.path.join(HERE, "..", "turbine_lowflow_v4")); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(V4, "model"))
import coupled_eval as ce, optimize_blades as ob, generator_lowflow as gl
ob.ARR["S"] = dict(r_hub=0.028, r_nac=0.039, vfac_nac=0.85, fr="S_simple")
gl.FRICTION["S_simple"] = dict(seal_run=0.006, seal_break=0.012, brg_run=0.003, brg_break=0.004, note="12 mm PTFE lip seal on a stainless sleeve + 6001-2RS (v5)")
gl.FRICTION["S_nbr"] = dict(seal_run=0.010, seal_break=0.020, brg_run=0.003, brg_break=0.004, note="12 mm NBR TC lip seal + 6001-2RS (v5 fallback seal)")
sel = json.load(open(os.path.join(V4, "model", "selected_design.json"))); spec = sel["spec"]
VS = ce.VS_ALL
cases = {"v4 arrangement A (8 mm PTFE seal + 608)": ce.full_eval(spec, "A"),
         "v5 simplified (12 mm PTFE seal + 6001)": ce.full_eval(spec, "S", fr=gl.FRICTION["S_simple"]),
         "v5 with an NBR seal": ce.full_eval(spec, "S", fr=gl.FRICTION["S_nbr"]),
         "v5, cogging 40 mN m": ce.full_eval(spec, "S", fr=gl.FRICTION["S_simple"], cog=0.040),
         "v5, inflow factor 0.70": ce.full_eval(spec, "S", fr=gl.FRICTION["S_simple"], vfac_nac=0.70)}
out = {}
for k, r in cases.items():
    P = [(r["perV"][str(V)]["op"]["Pout"] if r["perV"][str(V)]["op"] else 0.0) for V in VS]
    s, u = ce.min_flows(r)
    out[k] = dict(P=P, min_start=s, min_sustain=u, Qstatic05=r["perV"]["0.5"]["Qstatic"], breakaway05=r["perV"]["0.5"]["breakaway"],
                  rpm=[(r["perV"][str(V)]["op"]["rpm"] if r["perV"][str(V)]["op"] else 0.0) for V in VS], Vdc=[(r["perV"][str(V)]["op"]["Vdc"] if r["perV"][str(V)]["op"] else 0.0) for V in VS],
                  I=[(r["perV"][str(V)]["op"]["I"] if r["perV"][str(V)]["op"] else 0.0) for V in VS], Voc2=r["perV"]["2.0"]["open"]["Vdc"] if r["perV"]["2.0"]["open"] else None,
                  T2=float(np.interp(r["perV"]["2.0"]["op"]["lam"], r["perV"]["2.0"]["lam"], r["perV"]["2.0"]["T"])) if r["perV"]["2.0"]["op"] else None, Q2=r["perV"]["2.0"]["op"]["Qrot"] if r["perV"]["2.0"]["op"] else None)
    print(f"{k}: P(0.5..1.0) {[round(p, 2) for p in P[1:7]]} W; start {s} sustain {u} m/s; standstill 0.5 m/s {out[k]['Qstatic05']*1000:.0f} vs breakaway {out[k]['breakaway05']*1000:.0f} mN m")
json.dump(dict(VS=VS, cases=out, friction=dict(S_simple=gl.FRICTION["S_simple"], S_nbr=gl.FRICTION["S_nbr"], A=gl.FRICTION["A_rear_nacelle"]), spec=spec), open(os.path.join(OUT, "v5_results.json"), "w"), indent=1)
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(9, 5.2), facecolor="#fbfaf7"); ax.set_facecolor("#fbfaf7")
cols = ["#5b6b8a", "#b85c38", "#c28a2b", "#7a7a7a", "#4f8a5b"]
for (k, r), c in zip(out.items(), cols):
    ax.plot(VS, r["P"], "-o", ms=4, color=c, lw=2 if "simplified" in k else 1.3, label=f"{k}: self-start from {r['min_start']} m/s")
ax.set_xlim(0.4, 1.0); ax.set_ylim(0, 4); ax.set_xlabel("stream speed (m/s)"); ax.set_ylabel("net 12 V electrical power (W)")
ax.grid(True, color="#e3e1da"); ax.legend(fontsize=8, loc="upper left"); ax.set_title("v5 simplified prototype vs v4 arrangement A (same optimised blade, buck-boost MPPT, hand-started below the self-start speed; model prediction)", loc="left", fontsize=9.5, fontweight="bold")
fig.savefig(os.path.join(OUT, "fig_v5_power.png"), dpi=140, facecolor="#fbfaf7", bbox_inches="tight"); print("fig_v5_power.png written")
