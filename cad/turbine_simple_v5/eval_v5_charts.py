#!/usr/bin/env python3
"""Charts and numbers for the v5 design summary: (1) mechanical and net electrical power vs water speed for the CURRENT design
(v5 simplified arrangement: 12 mm seal + 6001, same optimised blade) with the previous designs and the gating markers;
(2) diameter study (same blade scaled, 28 mm hub, GL60 fixed); (3) GL60 characteristic lines from the listed constants with the
model's operating points.  Writes out/v5_summary_results.json, out/fig_v5_power_full.png, out/fig_v5_diameter.png, out/fig_v5_motor.png."""
import json, math, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); V4 = os.path.abspath(os.path.join(HERE, "..", "turbine_lowflow_v4")); OUT = os.path.join(HERE, "out")
sys.path.insert(0, os.path.join(V4, "model"))
import coupled_eval as ce, optimize_blades as ob, generator_lowflow as gl, bem_lowflow as bm
ob.ARR["S"] = dict(r_hub=0.028, r_nac=0.039, vfac_nac=0.85, fr="S_simple")
gl.FRICTION["S_simple"] = dict(seal_run=0.006, seal_break=0.012, brg_run=0.003, brg_break=0.004, note="12 mm PTFE lip seal + 6001-2RS (v5)")
sel = json.load(open(os.path.join(V4, "model", "selected_design.json"))); spec = sel["spec"]; VS = ce.VS_ALL
orig, v31 = ce.previous_designs()
R = {"new": ce.full_eval(spec, "S"), "new_boost": ce.full_eval(spec, "S", conv_key="boost_clamp"), "v31": ce.full_eval(v31, "B"), "orig": ce.full_eval(orig, "A")}
def curves(r):
    Psh = [r["perV"][str(V)]["cp_peak"] * 0.5 * 1000 * math.pi * bm.R_TIP ** 2 * V ** 3 for V in VS]
    Pe = [(r["perV"][str(V)]["op"]["Pout"] if r["perV"][str(V)]["op"] else 0.0) for V in VS]
    Pg = [r["perV"][str(V)]["Pout_gated"] for V in VS]
    return Psh, Pe, Pg
# ---------------- figure: power vs speed (log), like v4 fig. 4
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
SURF = "#fbfaf7"; fig, ax = plt.subplots(figsize=(13, 7.2), facecolor=SURF); ax.set_facecolor(SURF)
names = {"new": f"current design: v5 simplified (B{spec['B']} {spec['airfoil']}, TSR_d {spec['lam_d']}, 12 mm seal + 6001)", "v31": "previous 1-2 m/s design (v3.1 blade, hub-integrated drum)", "orig": "original 8-in rev-2 blade on the same 28 mm hub"}
styles = {"new": ("-", "#2b4a6b"), "v31": ("--", "#b84a3a"), "orig": (":", "#b8860b")}
ax.axvspan(0.5, 1.0, color="#dfe7f1", alpha=0.45, lw=0)
for k in ("new", "v31", "orig"):
    Psh, Pe, Pg = curves(R[k]); ls, col = styles[k]
    ax.plot(VS, Psh, ls, color=col, lw=1.4, alpha=0.6, label=f"{names[k]}: rotor shaft (peak Cp)")
    ax.plot(VS, Pe, ls, color=col, lw=2.6, marker="o", ms=4, label=f"{names[k]}: net 12 V electrical (buck-boost MPPT)")
    if k == "new": ax.plot(VS, Pg, "x", color=col, ms=8, mew=1.8, label="current design: gated (zero where it cannot self-start or sustain)")
Psh, Pe, Pg = curves(R["new_boost"]); ax.plot(VS, Pe, "-", color="#4f8a5b", lw=1.3, label="current design with the boost + clamp converter (GVB-8 class)")
ax.set_yscale("log"); ax.set_ylim(0.05, 100); ax.set_xlim(0.35, 2.1); ax.grid(True, which="both", color="#e3e1da", lw=0.6); ax.set_axisbelow(True)
ax.set_xlabel("water speed (m/s)"); ax.set_ylabel("power (W)")
ax.set_title("Mechanical and net electrical power vs water speed: current v5 design and GL60 KV25 (model; x = zero where the rotor cannot self-start or sustain under baseline assumptions)", loc="left", fontsize=10.5, fontweight="bold")
ax.legend(fontsize=8, loc="lower right", framealpha=0.95); fig.savefig(os.path.join(OUT, "fig_v5_power_full.png"), dpi=140, facecolor=SURF, bbox_inches="tight"); plt.close(fig)
# ---------------- diameter study
R0 = bm.R_TIP; dia = {}
for Din in (8.0, 7.0, 6.0, 5.0):
    bm.R_TIP = Din * 25.4 / 2 / 1000; r = ce.full_eval(spec, "S"); s, u = ce.min_flows(r)
    bl = ce.make_blade(spec, "S"); r70 = 0.028 + 0.7 * (bm.R_TIP - 0.028); c70 = float(np.interp(r70, bl.r, bl.c)); o7 = r["perV"]["0.7"]["op"]
    dia[str(Din)] = dict(R_mm=bm.R_TIP * 1000, hub_ratio=0.028 / bm.R_TIP, P=[(r["perV"][str(V)]["op"]["Pout"] if r["perV"][str(V)]["op"] else 0.0) for V in VS], min_start=s, min_sustain=u,
                        cp_peak={str(V): r["perV"][str(V)]["cp_peak"] for V in (0.5, 0.7, 1.0)}, Qstatic05=r["perV"]["0.5"]["Qstatic"], breakaway=r["perV"]["0.5"]["breakaway"],
                        c70_mm=c70 * 1000, Re70_07=(0.7 * math.sqrt(1 + ((o7["lam"] if o7 else 3.0) * r70 / bm.R_TIP) ** 2) * c70 / 1e-6),
                        T2=float(np.interp(r["perV"]["2.0"]["op"]["lam"], r["perV"]["2.0"]["lam"], r["perV"]["2.0"]["T"])) if r["perV"]["2.0"]["op"] else None,
                        rpm10=(r["perV"]["1.0"]["op"]["rpm"] if r["perV"]["1.0"]["op"] else None))
bm.R_TIP = R0
fig, ax = plt.subplots(figsize=(9, 5.2), facecolor=SURF); ax.set_facecolor(SURF)
for (D, d), col in zip(dia.items(), ["#2b4a6b", "#b85c38", "#c28a2b", "#7a7a7a"]):
    ax.plot(VS, d["P"], "-o", ms=4, color=col, lw=2.2 if D == "8.0" else 1.4, label=f"{float(D):.0f} in (R {d['R_mm']:.0f} mm): self-start {d['min_start']} m/s, Cp peak {d['cp_peak']['1.0']:.2f} at 1 m/s")
ax.set_xlim(0.4, 1.0); ax.set_ylim(0, 3.8); ax.set_xlabel("water speed (m/s)"); ax.set_ylabel("net 12 V electrical power (W), hand-started where below the self-start speed")
ax.grid(True, color="#e3e1da"); ax.legend(fontsize=8.5, loc="upper left"); ax.set_title("Rotor diameter as an iteration variable: same optimised blade scaled, 28 mm hub and GL60 unchanged (model)", loc="left", fontsize=10, fontweight="bold")
fig.savefig(os.path.join(OUT, "fig_v5_diameter.png"), dpi=140, facecolor=SURF, bbox_inches="tight"); plt.close(fig)
# ---------------- motor chart: listed constants as lines, model operating points as markers
G = gl.GEN; Kt = 60 / (2 * math.pi * G["KV"]); rpm = np.linspace(0, 1200, 200)
ops = [(V, R["new"]["perV"][str(V)]["op"]) for V in VS if R["new"]["perV"][str(V)]["op"]]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5), facecolor=SURF)
for a in (a1, a2): a.set_facecolor(SURF); a.grid(True, color="#e3e1da")
a1.plot(rpm, rpm / G["KV"], color="#2b4a6b", lw=2, label=f"open-circuit DC voltage = rpm / KV (KV {G['KV']} rpm/V, from 516 rpm at 24 V)")
a1.plot([o["rpm"] for _, o in ops], [o["Vdc"] for _, o in ops], "o", color="#b85c38", ms=6, label="model operating points (bus voltage under MPPT load)")
for V, o in ops:
    if V in (0.5, 0.7, 1.0, 1.5, 2.0): a1.annotate(f"{V} m/s", (o["rpm"], o["Vdc"]), textcoords="offset points", xytext=(6, -10), fontsize=8, color="#b85c38")
a1.axhline(5.0, color="#7a7a7a", ls=":", lw=1); a1.text(20, 5.4, "5 V converter floor", fontsize=8, color="#555"); a1.axhline(60, color="#7a7a7a", ls="--", lw=1); a1.text(20, 61.5, "60 V TVS / converter limit", fontsize=8, color="#555")
a1.set_xlabel("generator speed (rpm)"); a1.set_ylabel("voltage (V)"); a1.set_xlim(0, 1200); a1.set_ylim(0, 65); a1.legend(fontsize=8, loc="upper left"); a1.set_title("Speed - voltage", loc="left", fontsize=10, fontweight="bold")
I = np.linspace(0, 1.75, 100)
a2.plot(I, Kt * I, color="#2b4a6b", lw=2, label=f"torque = Kt x I (Kt {Kt:.3f} N m/A from KV; listed 0.45)")
a2.plot([o["I"] for _, o in ops], [o["Qg"] for _, o in ops], "o", color="#b85c38", ms=6, label="model operating points (generator torque)")
for V, o in ops:
    if V in (0.5, 0.7, 1.0, 1.5, 2.0): a2.annotate(f"{V} m/s", (o["I"], o["Qg"]), textcoords="offset points", xytext=(6, -10), fontsize=8, color="#b85c38")
a2.axvline(G["rated_I"], color="#7a7a7a", ls="--", lw=1); a2.text(G["rated_I"] + 0.02, 0.05, f"rated {G['rated_I']} A / {G['rated_T']} N m", fontsize=8, color="#555", rotation=90, va="bottom")
a2.plot(I, I ** 2 * G["R_LL"] / 10, color="#c28a2b", lw=1.4, label=f"copper loss / 10 (W) = I^2 x {G['R_LL']} ohm / 10")
a2.set_xlabel("current (A)"); a2.set_ylabel("torque (N m)  |  copper loss / 10 (W)"); a2.set_xlim(0, 1.75); a2.set_ylim(0, 0.8); a2.legend(fontsize=8, loc="upper left"); a2.set_title("Current - torque", loc="left", fontsize=10, fontweight="bold")
fig.suptitle("CubeMars GL60 KV25 as modelled: lines from the listed constants (manufacturer page not reachable from this session), markers = where the turbine runs it", x=0.03, ha="left", fontsize=10.5, fontweight="bold")
fig.savefig(os.path.join(OUT, "fig_v5_motor.png"), dpi=140, facecolor=SURF, bbox_inches="tight"); plt.close(fig)
# ---------------- numbers
def summ(r):
    return dict(P=[(r["perV"][str(V)]["op"]["Pout"] if r["perV"][str(V)]["op"] else 0.0) for V in VS], Pg=[r["perV"][str(V)]["Pout_gated"] for V in VS],
                Psh=[r["perV"][str(V)]["cp_peak"] * 0.5 * 1000 * math.pi * bm.R_TIP ** 2 * V ** 3 for V in VS], cp=[r["perV"][str(V)]["cp_peak"] for V in VS],
                rpm=[(r["perV"][str(V)]["op"]["rpm"] if r["perV"][str(V)]["op"] else None) for V in VS], I=[(r["perV"][str(V)]["op"]["I"] if r["perV"][str(V)]["op"] else None) for V in VS],
                Vdc=[(r["perV"][str(V)]["op"]["Vdc"] if r["perV"][str(V)]["op"] else None) for V in VS], lam=[(r["perV"][str(V)]["op"]["lam"] if r["perV"][str(V)]["op"] else None) for V in VS],
                start=[r["perV"][str(V)]["start"] for V in VS], min_start=ce.min_flows(r)[0], min_sustain=ce.min_flows(r)[1],
                Voc2=r["perV"]["2.0"]["open"]["Vdc"] if r["perV"]["2.0"]["open"] else None, Qstatic05=r["perV"]["0.5"]["Qstatic"], breakaway05=r["perV"]["0.5"]["breakaway"])
json.dump(dict(VS=VS, designs={k: summ(v) for k, v in R.items()}, diameter=dia, GEN=G, Kt=Kt, friction=gl.FRICTION["S_simple"], spec=spec), open(os.path.join(OUT, "v5_summary_results.json"), "w"), indent=1)
print("written; current design P:", [round(p, 2) for p in summ(R["new"])["P"]], "start", summ(R["new"])["min_start"])
