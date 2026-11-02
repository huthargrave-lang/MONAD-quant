#!/usr/bin/env python3
"""Coupled rotor-generator evaluation of the selected design against the two previous designs, with the figures 2-9 of the brief,
the comparison table, sensitivities and the minimum self-start / sustain velocities with bounds.  Reads selected_design.json
(written by optimize_blades.py stage 2) and writes coupled_results.json + figures to ../out."""
import csv, json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bem_lowflow as bm, generator_lowflow as gl, optimize_blades as ob
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "..", "out"); ROOT = os.path.join(HERE, "..", "..")
TABS = ob.TABS
SURF = "#fcfcfb"; C_NEW, C_OLD, C_ORIG, INK2 = "#1d5fa8", "#c4342d", "#b06f00", "#52514e"
VS_ALL = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.25, 1.5, 2.0]
LAMS = np.arange(0.4, 7.01, 0.2)

def previous_designs():
    """(1) original 8-inch rev-2 blade (hub 25.4 mm, TSR 4, NACA 4422->4414), from blade_stations.csv; (2) the v3.1 drum-rotor blade."""
    rows = list(csv.DictReader(open(os.path.join(ROOT, "water_turbine_blade", "blade_stations.csv"))))
    orig = dict(name="original 8-in rev 2 (1-2 m/s, hub 25.4)", from_arrays=True, airfoil="naca4415", B=3, r_mm=[float(r["r_mm"]) for r in rows], chord_mm=[float(r["chord_mm"]) for r in rows],
                twist_deg=[float(r["twist_deg_from_rotor_plane"]) for r in rows])
    sys.path.insert(0, os.path.join(ROOT, "water_turbine_blade")); import make_blade as mb
    mb.R_HUB = 42.0; mb.R_ROOT_EXT = 39.0; mb.C_MAX = 60.0; mb.PEAK_R = 0.58; mb.TC_ROOT = 0.24; mb.TC_TIP = 0.15; mb.TE_THICK = 1.0; mb.TIP_CHORD_FRAC = 0.55
    bl = mb.design_blade(4.0, 6.0)
    v31 = dict(name="v3.1 drum rotor blade (1-2 m/s, root 48.2)", from_arrays=True, airfoil="naca4412", B=3, r_mm=bl["r"].tolist(), chord_mm=bl["chord"].tolist(), twist_deg=bl["twist"].tolist())
    return orig, v31

def make_blade(spec, arr_key, n_el=50, cd_mult=1.0, cl_fac=1.0):
    arr = ob.ARR[arr_key]; r, _ = bm.elements(arr["r_hub"], n_el); vf = ob.vfac_for(r, arr)
    if spec.get("from_arrays"):
        return bm.blade_from_arrays(TABS, spec["airfoil"], spec["B"], spec["r_mm"], spec["chord_mm"], spec["twist_deg"], arr["r_hub"], n=n_el, vfac=vf, cd_mult=cd_mult, cl_fac=cl_fac)
    return bm.design(TABS, spec["airfoil"], spec["B"], spec["lam_d"], spec.get("c_scale", 1.0), spec.get("dbeta", 0.0), arr["r_hub"], spec.get("c_max", 0.060), spec.get("tip_frac", 0.55),
                     spec.get("root_blend", 0.35), n=n_el, vfac=vf, cd_mult=cd_mult, cl_fac=cl_fac)

def full_eval(spec, arr_key, conv_key="buckboost", gen=None, fr=None, cd_mult=1.0, cl_fac=1.0, vs=VS_ALL, lams=LAMS, cog=None):
    g = dict(gl.GEN if gen is None else gen); 
    if cog is not None: g["cogging"] = cog
    arr = ob.ARR[arr_key]; frd = gl.FRICTION[arr["fr"]] if fr is None else fr
    bl = make_blade(spec, arr_key, cd_mult=cd_mult, cl_fac=cl_fac); conv = gl.CONVERTERS[conv_key]
    res = dict(perV={}, meta=bl.meta, r=bl.r.tolist(), c=bl.c.tolist(), beta=np.degrees(bl.beta).tolist())
    for V in vs:
        cur = [bm.bem(bl, l, V) for l in lams]; Q = np.array([c["Q"] for c in cur]); cp = np.array([c["cp"] for c in cur]); T = np.array([c["T"] for c in cur])
        Qs = bm.static_torque(bl, V)
        op = gl.operating_point(V, lams, Q, frd, conv, g=g, r_hub_m=arr["r_hub"])
        op_open = gl.operating_point(V, lams, Q, frd, conv, g=g, r_hub_m=arr["r_hub"], mode="open")
        sus = gl.sustain_margin(V, lams, Q, frd, g, arr["r_hub"], lam_max=(op["lam"] if op else (op_open["lam"] if op_open else None)))   # unloaded path up to the operating point (or the runaway point when no load engages)
        res["perV"][str(V)] = dict(lam=lams.tolist(), cp=cp.tolist(), Q=Q.tolist(), T=T.tolist(), Qstatic=Qs, breakaway=gl.breakaway(frd, g), start=bool(Qs > gl.breakaway(frd, g)), sustain=sus,
                                   op=op, open=op_open, cp_peak=float(cp.max()), lam_peak=float(lams[cp.argmax()]), P_ann=0.5 * 1000 * math.pi * (bm.R_TIP ** 2 - arr["r_hub"] ** 2) * V ** 3,
                                   Pout_gated=(op["Pout"] if (op and Qs > gl.breakaway(frd, g) and sus > 0) else 0.0))
    return res

def min_flows(res):
    s = next((float(V) for V in res["perV"] if res["perV"][V]["start"]), None); u = next((float(V) for V in res["perV"] if res["perV"][V]["op"] and res["perV"][V]["sustain"] > 0), None)
    return s, u

if __name__ == "__main__" and "--replot" in sys.argv:
    Cst = json.load(open(os.path.join(HERE, "coupled_results.json"))); R = {k: v["res"] for k, v in Cst["designs"].items()}; names = {k: v["name"] for k, v in Cst["designs"].items()}
    spec_new = Cst["selected"]["spec"]; sens = Cst["sens"]; gmap = Cst["gmap"]; combos = Cst["combos"]
if __name__ == "__main__" and "--replot" not in sys.argv:
    sel = json.load(open(os.path.join(HERE, "selected_design.json")))
    spec_new = sel["spec"]; orig, v31 = previous_designs()
    designs = {"new": (spec_new, "A"), "v31": (v31, "B"), "orig": (orig, "A"), "new_in_B": (spec_new, "B")}
    R = {k: full_eval(s, a) for k, (s, a) in designs.items()}
    R["new_boost"] = full_eval(spec_new, "A", conv_key="boost_clamp")
    R["new_direct"] = full_eval(spec_new, "A", conv_key="direct")
    names = {"new": f"new low-flow design (B{spec_new['B']} {spec_new['airfoil']}, TSR_d {spec_new['lam_d']}, arrangement A)", "v31": "previous 1-2 m/s design (v3.1 blade, arrangement B)", "orig": "original 8-in rev-2 blade on the A hub", "new_in_B": "new blade on the B hub (48.2 mm)"}
    # ---------------- comparison table
    table = []
    for V in VS_ALL:
        row = dict(V=V)
        for k in ("new", "v31", "orig", "new_in_B"):
            p = R[k]["perV"][str(V)]; op = p["op"]
            row[k] = dict(cp=p["cp_peak"], lam_peak=p["lam_peak"], Pshaft_peak=p["cp_peak"] * 0.5 * 1000 * math.pi * bm.R_TIP ** 2 * V ** 3, Pout=(op["Pout"] if op else 0.0), Pout_gated=p["Pout_gated"],
                          rpm=(op["rpm"] if op else 0.0), Vdc=(op["Vdc"] if op else 0.0), I=(op["I"] if op else 0.0), start=p["start"], Qstatic=p["Qstatic"], breakaway=p["breakaway"], region=(op["region"] if op else "-"), overcurrent=(op.get("overcurrent", False) if op else False))
        table.append(row)
    print("V    | new: Cp  Pout  rpm  Vdc  start | v3.1: Cp Pout start | orig: Cp Pout start | new-in-B: Cp Pout")
    for row in table:
        n, o, g, b = row["new"], row["v31"], row["orig"], row["new_in_B"]
        print(f"{row['V']:.2f} | {n['cp']:.3f} {n['Pout']:5.2f} {n['rpm']:4.0f} {n['Vdc']:5.1f} {'Y' if n['start'] else 'n'} | {o['cp']:.3f} {o['Pout']:5.2f} {'Y' if o['start'] else 'n'} | {g['cp']:.3f} {g['Pout']:5.2f} {'Y' if g['start'] else 'n'} | {b['cp']:.3f} {b['Pout']:5.2f}")
    # ---------------- sensitivities (new design, arrangement A, buck-boost)
    sens = {}
    base_fr = gl.FRICTION["A_rear_nacelle"]
    def P_curve(res): return [res["perV"][str(V)]["Pout_gated"] for V in VS_ALL]
    sens["baseline"] = P_curve(R["new"])
    for f in (0.5, 2.0, 3.0):
        fr = dict(base_fr); fr["seal_run"] *= f; fr["seal_break"] *= f; sens[f"seal x{f}"] = P_curve(full_eval(spec_new, "A", fr=fr))
    for cm in (1.3, 1.6):
        sens[f"cd x{cm}"] = P_curve(full_eval(spec_new, "A", cd_mult=cm))
    sens["cl x0.9, cd x1.3"] = P_curve(full_eval(spec_new, "A", cd_mult=1.3, cl_fac=0.9))
    for cog in (0.008, 0.040):
        sens[f"cogging {cog*1000:.0f} mN m"] = P_curve(full_eval(spec_new, "A", cog=cog))
    for p0 in (0.2, 1.5):
        g = dict(gl.GEN); g["p0_700"] = p0; sens[f"no-load loss {p0} W@700"] = P_curve(full_eval(spec_new, "A", gen=g))
    for key, etam, k, vmin in (("conv eta 0.85", 0.85, 0.08, 5.0), ("conv eta 0.96", 0.96, 0.04, 5.0), ("conv Vmin 3 V", 0.94, 0.08, 3.0), ("conv Vmin 8 V", 0.94, 0.08, 8.0)):
        gl.CONVERTERS["tmp"] = dict(gl.CONVERTERS["buckboost"]); gl.CONVERTERS["tmp"].update(eta_max=etam, k=k, V_min=vmin)
        sens[key] = P_curve(full_eval(spec_new, "A", conv_key="tmp"))
    g = dict(gl.GEN); g["KV"] = 25.0; sens["KV 25 (Kt 0.38)"] = P_curve(full_eval(spec_new, "A", gen=g))
    g = dict(gl.GEN); g["R_LL"] = 6.5; sens["R 6.5 ohm"] = P_curve(full_eval(spec_new, "A", gen=g))
    sens["rectifier synchronous"] = None
    try:
        rs = gl.RECTIFIER["synchronous"]
        # re-evaluate with the synchronous rectifier by temporarily swapping the default
        import generator_lowflow as g2; old = g2.RECTIFIER["schottky"]; g2.RECTIFIER["schottky"] = rs
        sens["rectifier synchronous"] = P_curve(full_eval(spec_new, "A")); g2.RECTIFIER["schottky"] = old
    except Exception as e: print("sync rectifier sensitivity failed", e)
    # worst / best combinations for the minimum-flow bounds
    combos = {}
    for lab, kw in (("optimistic", dict(cd_mult=1.0, cog=0.008, fr={**base_fr, "seal_run": base_fr["seal_run"] * 0.5, "seal_break": base_fr["seal_break"] * 0.5})),
                    ("baseline", dict()), ("pessimistic", dict(cd_mult=1.3, cl_fac=0.9, cog=0.040, fr={**base_fr, "seal_run": base_fr["seal_run"] * 2, "seal_break": base_fr["seal_break"] * 2}))):
        rr = full_eval(spec_new, "A", **kw); combos[lab] = dict(min_start=min_flows(rr)[0], min_sustain=min_flows(rr)[1], P=P_curve(rr))
    print("minimum self-start / sustain (m/s):", {k: (v["min_start"], v["min_sustain"]) for k, v in combos.items()})
    # ---------------- generator efficiency map (plot 7 data)
    gmap = {}
    for T in (0.02, 0.05, 0.1, 0.2, 0.4):
        rows = []
        for rpm in np.arange(50, 801, 25):
            gp = gl.gen_point(rpm, T); om = rpm * 2 * math.pi / 60; Pm = T * om
            rows.append(dict(rpm=rpm, Pmech=Pm, Pdc=gp["Pdc"], Pcu=gp["Pcu"], Pdiode=gp["Pdiode"], Vdc=gp["Vdc"], I=gp["I"], eta=(gp["Pdc"] / Pm if Pm > 0 else 0)))
        gmap[str(T)] = rows
    json.dump(dict(designs={k: dict(name=names.get(k, k), res=R[k]) for k in R}, table=table, sens=sens, combos=combos, gmap=gmap, VS=VS_ALL, selected=sel),
              open(os.path.join(HERE, "coupled_results.json"), "w"), indent=0, default=float)
if __name__ == "__main__":
    # ======================================================================= figures
    def fig_cp_tsr():
        fig, axs = plt.subplots(1, 4, figsize=(18, 4.6), facecolor=SURF, sharey=True)
        for ax, V in zip(axs, (0.5, 0.7, 1.0, 1.5)):
            for k, col, ls in (("new", C_NEW, "-"), ("v31", C_OLD, "--"), ("orig", C_ORIG, ":")):
                p = R[k]["perV"][str(V)]; ax.plot(p["lam"], p["cp"], ls, color=col, lw=2, label=names[k] if V == 0.5 else None)
                if p["op"]: ax.plot(p["op"]["lam"], np.interp(p["op"]["lam"], p["lam"], p["cp"]), "o", color=col, ms=6)
            ax.set_title(f"V = {V} m/s", fontsize=10); ax.set_xlabel("tip-speed ratio"); ax.grid(alpha=0.3); ax.set_ylim(0, 0.45)
        axs[0].set_ylabel("Cp (on the full 203.2 mm disc)"); axs[0].legend(fontsize=7, loc="upper left")
        fig.suptitle("Fig. 2  Cp vs TSR: previous designs vs the low-flow design (BEM, NeuralFoil Re-dependent polars; dots = coupled operating points, buck-boost MPPT)", fontsize=10, x=0.01, ha="left")
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig2_cp_tsr.png"), dpi=130, facecolor=SURF)
    def fig_torque_rpm():
        fig, ax = plt.subplots(figsize=(11, 6.5), facecolor=SURF)
        rs = R["new"]; fr = gl.FRICTION["A_rear_nacelle"]
        for V, col in ((0.5, "#9ecae1"), (0.7, "#4292c6"), (1.0, "#08519c"), (1.5, "#6a3d9a"), (2.0, "#b15928")):
            p = rs["perV"][str(V)]; rpm = np.array(p["lam"]) * V / bm.R_TIP * 60 / (2 * math.pi)
            ax.plot(np.r_[0, rpm], np.r_[p["Qstatic"], p["Q"]] * 1000, "-", color=col, lw=2, label=f"rotor torque, V = {V} m/s (TSR 0 point = standstill estimate)")
            if p["op"]: ax.plot(p["op"]["rpm"], p["op"]["Qrot"] * 1000, "o", color=col, ms=7, mec="k")
        rpms = np.arange(0, 1300, 10); ax.plot(rpms, [gl.friction_running(x, fr) * 1000 for x in rpms], "k--", lw=1.2, label="running friction (seal + bearing + motor no-load + windage)")
        ax.axhline(gl.breakaway(fr) * 1000, color="k", ls=":", lw=1.2, label=f"breakaway (cogging {gl.GEN['cogging']*1000:.0f} + seal + bearing) = {gl.breakaway(fr)*1000:.0f} mN m")
        for Vb, lab in ((14.4, "generator load at a fixed 14.4 V bus (rectifier into the battery / boost clamp)"), (5.0, "generator load at the 5 V converter minimum")):
            Tl = [max(0, (x / gl.GEN["KV"] - Vb - 0.7) / gl.GEN["R_LL"]) * gl.Kt() * 1000 for x in rpms]; ax.plot(rpms, Tl, "-.", lw=1.2, color="#2a8a4a" if Vb > 10 else "#888", label=lab)
        ax.axhline(gl.GEN["rated_T"] * 1000, color="#c4342d", ls="-", lw=1, alpha=0.6, label="GL60 rated torque 0.60 N m (1.35 A)")
        ax.set_xlim(0, 1250); ax.set_ylim(0, 700); ax.set_xlabel("rotor speed (rpm)"); ax.set_ylabel("torque (mN m)"); ax.grid(alpha=0.3); ax.legend(fontsize=7.5, loc="upper right")
        ax.set_title("Fig. 3  Rotor torque vs rpm with the standstill estimate, friction, breakaway and the generator load lines (dots: buck-boost MPPT operating points)", fontsize=10, loc="left")
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig3_torque_rpm.png"), dpi=130, facecolor=SURF)
    def fig_power_v():
        fig, ax = plt.subplots(figsize=(10, 6), facecolor=SURF)
        for k, col, ls in (("new", C_NEW, "-"), ("v31", C_OLD, "--"), ("orig", C_ORIG, ":")):
            res = R[k]; Psh = [res["perV"][str(V)]["cp_peak"] * 0.5 * 1000 * math.pi * bm.R_TIP ** 2 * V ** 3 for V in VS_ALL]
            Pe = [(res["perV"][str(V)]["op"]["Pout"] if res["perV"][str(V)]["op"] else 0) for V in VS_ALL]; Pg = [res["perV"][str(V)]["Pout_gated"] for V in VS_ALL]
            ax.plot(VS_ALL, Psh, ls, color=col, lw=1.5, alpha=0.6, label=f"{names[k]}: rotor shaft (peak Cp)")
            ax.plot(VS_ALL, Pe, ls, color=col, lw=2.5, marker="o", ms=4, label=f"{names[k]}: net 12 V electrical (buck-boost MPPT)")
            ax.plot(VS_ALL, Pg, "x", color=col, ms=7, label=f"{names[k]}: gated by self-start / sustain" if k == "new" else None)
        ax.plot(VS_ALL, [(R["new_boost"]["perV"][str(V)]["op"]["Pout"] if R["new_boost"]["perV"][str(V)]["op"] else 0) for V in VS_ALL], "-", color="#2a8a4a", lw=1.2, label="new design with the boost+clamp converter (GVB-8 class)")
        ax.set_yscale("log"); ax.set_ylim(0.05, 100); ax.set_xlabel("water speed (m/s)"); ax.set_ylabel("power (W)"); ax.grid(True, which="both", alpha=0.3); ax.legend(fontsize=7.5, loc="lower right"); ax.axvspan(0.5, 1.0, color=C_NEW, alpha=0.05)
        ax.set_title("Fig. 4  Mechanical and net electrical power vs water speed (model; x = gated value)", fontsize=10, loc="left")
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig4_power_vs_v.png"), dpi=130, facecolor=SURF)
    def fig_chord_twist():
        fig, axs = plt.subplots(1, 2, figsize=(13, 5), facecolor=SURF)
        for k, col, ls in (("new", C_NEW, "-"), ("v31", C_OLD, "--"), ("orig", C_ORIG, ":")):
            r = np.array(R[k]["r"]) * 1000; axs[0].plot(r, np.array(R[k]["c"]) * 1000, ls, color=col, lw=2, label=names[k]); axs[1].plot(r, R[k]["beta"], ls, color=col, lw=2, label=names[k])
        axs[0].set_xlabel("radius (mm)"); axs[0].set_ylabel("chord (mm)"); axs[0].grid(alpha=0.3); axs[0].legend(fontsize=7.5); axs[0].set_title("Fig. 5  Chord distribution", fontsize=10, loc="left")
        axs[1].set_xlabel("radius (mm)"); axs[1].set_ylabel("twist from the rotor plane (deg)"); axs[1].grid(alpha=0.3); axs[1].set_title("Fig. 6  Twist distribution", fontsize=10, loc="left")
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig5_6_chord_twist.png"), dpi=130, facecolor=SURF)
    def fig_gen_losses():
        fig, axs = plt.subplots(1, 2, figsize=(15, 5.5), facecolor=SURF)
        for T, col in zip((0.02, 0.05, 0.1, 0.2, 0.4), ("#9ecae1", "#6baed6", "#3182bd", "#08519c", "#542788")):
            rows = gmap[str(T)]; axs[0].plot([r["rpm"] for r in rows], [r["eta"] * 100 for r in rows], color=col, lw=2, label=f"T = {T*1000:.0f} mN m ({T/gl.Kt():.2f} A)")
        axs[0].set_xlabel("generator speed (rpm)"); axs[0].set_ylabel("rectified DC / shaft power (%)"); axs[0].set_ylim(0, 100); axs[0].grid(alpha=0.3); axs[0].legend(fontsize=8)
        axs[0].set_title("Fig. 7a  GL60 + Schottky bridge efficiency vs speed at constant torque (copper I^2 R, diode 2 Vf; no-load loss excluded here)", fontsize=9, loc="left")
        rs = R["new"]; Vs = [V for V in VS_ALL if rs["perV"][str(V)]["op"]]
        comp = {"rotor-to-shaft (hydrodynamic)": [], "friction + no-load": [], "copper": [], "diodes": [], "converter": [], "net 12 V output": []}
        for V in Vs:
            p = rs["perV"][str(V)]; op = p["op"]; Ph = p["P_ann"]
            comp["rotor-to-shaft (hydrodynamic)"].append(Ph - op["Pshaft"]); comp["friction + no-load"].append(op["Pfric"]); comp["copper"].append(op["Pcu"]); comp["diodes"].append(op["Pdiode"]); comp["converter"].append(op["Pdc"] - op["Pout"]); comp["net 12 V output"].append(op["Pout"])
        bottom = np.zeros(len(Vs)); cols = ["#d9d9d9", "#fdae6b", "#e6550d", "#a63603", "#9e9ac8", "#2a8a4a"]
        for (lab, vals), col in zip(comp.items(), cols):
            vals = np.array(vals) / np.array([rs["perV"][str(V)]["P_ann"] for V in Vs]) * 100; axs[1].bar([str(V) for V in Vs], vals, bottom=bottom, color=col, label=lab); bottom += vals
        axs[1].set_xlabel("water speed (m/s)"); axs[1].set_ylabel("share of the hydraulic power through the blade annulus (%)"); axs[1].legend(fontsize=7.5, loc="lower right"); axs[1].grid(alpha=0.3, axis="y")
        axs[1].set_title("Fig. 7b  Loss breakdown along the chain at the operating points (new design, arrangement A, buck-boost)", fontsize=9, loc="left")
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig7_generator_losses.png"), dpi=130, facecolor=SURF)
    def fig_sens():
        fig, axs = plt.subplots(1, 3, figsize=(17, 5), facecolor=SURF, sharey=True)
        groups = [("seal friction / cogging / no-load loss", ["baseline", "seal x0.5", "seal x2.0", "seal x3.0", "cogging 8 mN m", "cogging 40 mN m", "no-load loss 0.2 W@700", "no-load loss 1.5 W@700"]),
                  ("polar (Reynolds) uncertainty / generator constants", ["baseline", "cd x1.3", "cd x1.6", "cl x0.9, cd x1.3", "KV 25 (Kt 0.38)", "R 6.5 ohm"]),
                  ("converter efficiency and minimum input voltage / rectifier", ["baseline", "conv eta 0.85", "conv eta 0.96", "conv Vmin 3 V", "conv Vmin 8 V", "rectifier synchronous"])]
        for ax, (title, keys) in zip(axs, groups):
            for key in keys:
                if sens.get(key) is None: continue
                ax.plot(VS_ALL, sens[key], "-o" if key == "baseline" else "-", lw=2.5 if key == "baseline" else 1.3, ms=4, label=key)
            ax.set_xlim(0.45, 1.05); ax.set_yscale("log"); ax.set_ylim(0.05, 6); ax.set_xlabel("water speed (m/s)"); ax.grid(alpha=0.3, which="both"); ax.legend(fontsize=7.5, loc="lower right"); ax.set_title(title, fontsize=9)
        axs[0].set_ylabel("net 12 V electrical power (W, log), gated by self-start")
        fig.suptitle("Fig. 8  Sensitivity of the net output of the selected design to the unmeasured inputs (one at a time; arrangement A, buck-boost MPPT)", fontsize=10, x=0.01, ha="left")
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig8_sensitivity.png"), dpi=130, facecolor=SURF)
    def fig_operating_point():
        fig, axs = plt.subplots(1, 3, figsize=(17, 5.2), facecolor=SURF)
        rs = R["new"]; fr = gl.FRICTION["A_rear_nacelle"]
        for ax, V in zip(axs, (0.5, 0.7, 1.0)):
            p = rs["perV"][str(V)]; rpm = np.array(p["lam"]) * V / bm.R_TIP * 60 / (2 * math.pi)
            Qn = np.array(p["Q"]) * 1000; fr_l = np.array([gl.friction_running(x, fr, V=V) * 1000 for x in rpm])
            ax.plot(rpm, Qn, "-", color=C_NEW, lw=2.5, label="rotor torque (BEM)"); ax.plot(rpm, Qn - fr_l, "--", color=C_NEW, lw=1.5, label="rotor torque minus running friction")
            ax.plot(rpm, fr_l, "k--", lw=1, label="running friction")
            for Vb, col, lab in ((5.0, "#888", "generator load at 5 V bus (converter minimum)"), (8.0, "#2a8a4a", "generator load at 8 V bus"), (14.4, "#b06f00", "generator load at 14.4 V bus (battery clamp)")):
                Tl = np.array([max(0, (x / gl.GEN["KV"] - Vb - 0.7) / gl.GEN["R_LL"]) * gl.Kt() * 1000 for x in rpm]); ax.plot(rpm, Tl, "-.", color=col, lw=1.2, label=lab)
            if p["op"]:
                ax.plot(p["op"]["rpm"], p["op"]["Qg"] * 1000, "o", color="k", ms=9, label=f"MPPT equilibrium: {p['op']['rpm']:.0f} rpm, {p['op']['Vdc']:.1f} V, {p['op']['Pout']:.2f} W out")
                Tl_op = np.array([max(0, (x / gl.GEN["KV"] - p["op"]["Vdc"] - 0.7) / gl.GEN["R_LL"]) * gl.Kt() * 1000 for x in rpm]); ax.plot(rpm, Tl_op, "-", color="k", lw=1.2, alpha=0.6, label=f"generator load line at the MPPT bus {p['op']['Vdc']:.1f} V")
            if p["open"]: ax.plot(p["open"]["rpm"], 0, "s", color="#c4342d", ms=7, label=f"open circuit (runaway) {p['open']['rpm']:.0f} rpm")
            ax.set_xlim(0, max(rpm) * 1.02); ax.set_ylim(-2, max(Qn.max() * 1.25, 30)); ax.set_xlabel("rotor speed (rpm)"); ax.set_ylabel("torque (mN m)"); ax.set_title(f"V = {V} m/s", fontsize=10); ax.grid(alpha=0.3); ax.legend(fontsize=6.8, loc="upper right")
        fig.suptitle("Fig. 9  Operating-point diagrams: rotor torque curve against the generator load lines (the controller sets the bus voltage, i.e. the load line, to reach the MPPT equilibrium)", fontsize=10, x=0.01, ha="left")
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig9_operating_point.png"), dpi=130, facecolor=SURF)
    for f in (fig_cp_tsr, fig_torque_rpm, fig_power_v, fig_chord_twist, fig_gen_losses, fig_sens, fig_operating_point):
        f(); print("figure", f.__name__)
