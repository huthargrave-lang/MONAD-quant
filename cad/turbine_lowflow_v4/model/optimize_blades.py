#!/usr/bin/env python3
"""Blade-design sweep for maximum net electrical energy over 0.5-1.0 m/s (not peak Cp).
Stage 1: B in {2,3,4,5} x airfoil in {naca4412, naca4415, sg6043, fx63137} x design TSR in {1.5..6} x chord scale in {0.7,1.0,1.3},
arrangement A hub (r 28 mm, nacelle inflow factor 0.85 inboard of r 38 mm), buck-boost MPPT converter, baseline friction/cogging.
Each candidate: Re-dependent Cp-lambda curves at V = 0.4..1.0, static torque, self-start, sustain, coupled operating points.
Objectives: J_uniform (mean P_out over 0.5-1.0) and J_lowflow (weights 0.30/0.30/0.20/0.10/0.05/0.05 for 0.5..1.0); P_out = 0 where the
candidate cannot self-start (static torque < breakaway), cannot sustain rotation, or sits below the converter's 5 V input minimum.
Also reported: J under 'hand-started' rules (no self-start gate) and with cogging 8 / 40 mN m.  Stage 2 refines the leaders."""
import json, math, os, sys, time, itertools
from multiprocessing import Pool
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bem_lowflow as bm, generator_lowflow as gl
HERE = os.path.dirname(os.path.abspath(__file__))
TABS = json.load(open(os.path.join(HERE, "polars_cache.json")))
VS = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
VOBJ = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
W_LOW = {0.5: 0.30, 0.6: 0.30, 0.7: 0.20, 0.8: 0.10, 0.9: 0.05, 1.0: 0.05}
LAMS1 = np.arange(0.5, 7.01, 0.5)
ARR = {"A": dict(r_hub=0.028, r_nac=0.038, vfac_nac=0.85, fr="A_rear_nacelle"), "B": dict(r_hub=0.0482, r_nac=0.0, vfac_nac=1.0, fr="B_hub_drum")}

def vfac_for(r, arr):
    return np.where(r < arr["r_nac"], arr["vfac_nac"], 1.0)

def evaluate(spec, lams=LAMS1, vs=VS, arr_key="A", conv_key="buckboost", cog_list=(0.008, 0.024, 0.040), n_el=40, cd_mult=1.0, cl_fac=1.0):
    arr = ARR[arr_key]
    r, _ = bm.elements(arr["r_hub"], n_el)
    if spec.get("from_arrays"):
        bl = bm.blade_from_arrays(TABS, spec["airfoil"], spec["B"], spec["r_mm"], spec["chord_mm"], spec["twist_deg"], arr["r_hub"], n=n_el, vfac=vfac_for(r, arr), cd_mult=cd_mult, cl_fac=cl_fac)
    else:
        bl = bm.design(TABS, spec["airfoil"], spec["B"], spec["lam_d"], spec.get("c_scale", 1.0), spec.get("dbeta", 0.0), arr["r_hub"], spec.get("c_max", 0.060), spec.get("tip_frac", 0.55),
                       spec.get("root_blend", 0.35), n=n_el, vfac=vfac_for(r, arr), cd_mult=cd_mult, cl_fac=cl_fac)
    fr = gl.FRICTION[arr["fr"]]; conv = gl.CONVERTERS[conv_key]
    out = dict(spec=spec, meta=bl.meta, arr=arr_key, conv=conv_key, perV={})
    for V in vs:
        cur = [bm.bem(bl, l, V) for l in lams]
        Q = np.array([c["Q"] for c in cur]); cp = np.array([c["cp"] for c in cur]); T = np.array([c["T"] for c in cur])
        Qs_up = bm.static_torque(bl, V)                                   # no-induction upper bound
        Qs = bm.static_torque_bem_low_lambda(bl, V)                       # baseline (induction on), review C1
        op = gl.operating_point(V, lams, Q, fr, conv, r_hub_m=arr["r_hub"])
        op_open = gl.operating_point(V, lams, Q, fr, conv, r_hub_m=arr["r_hub"], mode="open")
        sus = gl.sustain_margin(V, lams, Q, fr, r_hub_m=arr["r_hub"], lam_max=(op["lam"] if op else (op_open["lam"] if op_open else None)))
        starts = {}
        for cog in cog_list:
            g = dict(gl.GEN); g["cogging"] = cog
            starts[str(cog)] = bool(Qs > gl.breakaway(fr, g))
        out["perV"][str(V)] = dict(cp_peak=float(cp.max()), lam_peak=float(lams[cp.argmax()]), Qstatic=Qs, Qstatic_upper=Qs_up, breakaway=gl.breakaway(fr), starts=starts, sustain=sus,
                                   op=({k: (float(v) if isinstance(v, (int, float, np.floating)) else v) for k, v in op.items()} if op else None),
                                   curve=dict(lam=lams.tolist(), cp=cp.tolist(), Q=Q.tolist(), T=T.tolist()))
    def J(weights, gate_start=True, cog="0.024"):
        tot = 0.0
        for V, w in weights.items():
            pv = out["perV"][str(V)]; op = pv["op"]
            P = op["Pout"] if op else 0.0
            if gate_start and not pv["starts"][cog]: P = 0.0
            if pv["sustain"] <= 0: P = 0.0
            tot += w * P
        return tot
    wu = {V: 1 / len(VOBJ) for V in VOBJ}
    out["J"] = dict(uniform=J(wu), lowflow=J(W_LOW), uniform_hand=J(wu, False), lowflow_hand=J(W_LOW, False),
                    uniform_cog8=J(wu, True, "0.008"), lowflow_cog8=J(W_LOW, True, "0.008"), uniform_cog40=J(wu, True, "0.04"), lowflow_cog40=J(W_LOW, True, "0.04"))
    out["min_selfstart_V"] = next((V for V in vs if out["perV"][str(V)]["starts"]["0.024"]), None)
    out["min_sustain_V"] = next((V for V in vs if out["perV"][str(V)]["op"] and out["perV"][str(V)]["sustain"] > 0), None)
    return out

def _work(spec):
    try:
        return evaluate(spec)
    except Exception as e:
        return dict(spec=spec, error=str(e))

if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "1"
    if stage == "1":
        specs = [dict(B=B, airfoil=af, lam_d=ld, c_scale=cs) for B in (2, 3, 4, 5) for af in ("naca4412", "naca4415", "sg6043", "fx63137") for ld in (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0) for cs in (0.7, 1.0, 1.3)]
        t0 = time.time()
        with Pool(4) as pool:
            res = pool.map(_work, specs, chunksize=4)
        print(f"stage 1: {len(res)} candidates in {(time.time()-t0)/60:.1f} min; errors: {sum(1 for r in res if 'error' in r)}")
        slim = []
        for r in res:
            if "error" in r: print("ERR", r["spec"], r["error"]); continue
            slim.append(dict(spec=r["spec"], meta={k: v for k, v in r["meta"].items() if k not in ("alpha_d", "cl_d")}, J=r["J"], min_selfstart_V=r["min_selfstart_V"], min_sustain_V=r["min_sustain_V"],
                             perV={V: dict(cp_peak=p["cp_peak"], lam_peak=p["lam_peak"], Qstatic=p["Qstatic"], Qstatic_upper=p["Qstatic_upper"], starts=p["starts"], sustain=p["sustain"],
                                           Pout=(p["op"]["Pout"] if p["op"] else 0.0), Vdc=(p["op"]["Vdc"] if p["op"] else 0.0), rpm=(p["op"]["rpm"] if p["op"] else 0.0), lam=(p["op"]["lam"] if p["op"] else 0.0)) for V, p in r["perV"].items()}))
        json.dump(slim, open(os.path.join(HERE, "sweep_stage1.json"), "w"), indent=0)
        for key in ("uniform", "lowflow", "uniform_hand", "lowflow_hand", "lowflow_cog8", "lowflow_cog40"):
            top = sorted(slim, key=lambda r: -r["J"][key])[:6]
            print(f"\nTop by J_{key}:")
            for r in top:
                s = r["spec"]; print(f"  B{s['B']} {s['airfoil']:9s} TSR_d {s['lam_d']:.1f} cs {s['c_scale']:.1f} | J_u {r['J']['uniform']:.3f} J_low {r['J']['lowflow']:.3f} (hand {r['J']['uniform_hand']:.3f}/{r['J']['lowflow_hand']:.3f}) | "
                      f"sol {r['meta']['solidity']:.2f} c_max {r['meta']['c_maxval']*1000:.0f} | start@ {r['min_selfstart_V']} sustain@ {r['min_sustain_V']} | P 0.5/0.7/1.0: {r['perV']['0.5']['Pout']:.2f}/{r['perV']['0.7']['Pout']:.2f}/{r['perV']['1.0']['Pout']:.2f} W; Cp(0.7) {r['perV']['0.7']['cp_peak']:.3f}")

def write_selected(res, path):
    """station arrays for the CAD (element centres -> mm/deg) + the spec"""
    spec = res["spec"]; arr = ARR["A"]; r, _ = bm.elements(arr["r_hub"], 50)
    bl = bm.design(TABS, spec["airfoil"], spec["B"], spec["lam_d"], spec.get("c_scale", 1.0), spec.get("dbeta", 0.0), arr["r_hub"], spec.get("c_max", 0.060), spec.get("tip_frac", 0.55), spec.get("root_blend", 0.35), n=50)
    json.dump(dict(spec=spec, B=spec["B"], airfoil=spec["airfoil"], lam_d=spec["lam_d"], root_airfoil="naca4418", r_mm=(bl.r * 1000).tolist(), chord_mm=(bl.c * 1000).tolist(), twist_deg=np.degrees(bl.beta).tolist(),
                   w_root=bl.w_root.tolist(), meta={k: v for k, v in bl.meta.items() if k not in ("alpha_d", "cl_d")}, J=res["J"], min_selfstart_V=res["min_selfstart_V"], min_sustain_V=res["min_sustain_V"]), open(path, "w"), indent=1)

if __name__ == "__main__" and (len(sys.argv) > 1 and sys.argv[1] == "2"):
    specs = [dict(B=B, airfoil="naca4412", lam_d=ld, c_scale=cs, c_max=0.060, dbeta=db) for B in (3, 4, 5) for ld in (1.5, 1.75, 2.0, 2.5) for cs in (1.0, 1.3, 1.5) for db in (-3.0, 0.0, 3.0)]
    specs += [dict(B=3, airfoil="sg6043", lam_d=ld, c_scale=cs, c_max=0.060, dbeta=0.0) for ld in (2.0, 2.5) for cs in (1.3, 1.5)]
    specs += [dict(B=2, airfoil="naca4412", lam_d=ld, c_scale=cs, c_max=0.068, dbeta=db) for ld in (2.0, 2.5) for cs in (1.3, 1.5, 1.7) for db in (-3.0, 0.0)]
    t0 = time.time()
    with Pool(4) as pool: res = pool.map(_work, specs, chunksize=2)
    print(f"stage 2: {len(res)} candidates in {(time.time()-t0)/60:.1f} min")
    slim = [dict(spec=r["spec"], meta={k: v for k, v in r["meta"].items() if k not in ("alpha_d", "cl_d")}, J=r["J"], min_selfstart_V=r["min_selfstart_V"], min_sustain_V=r["min_sustain_V"],
                 perV={V: dict(cp_peak=p["cp_peak"], lam_peak=p["lam_peak"], Qstatic=p["Qstatic"], Qstatic_upper=p["Qstatic_upper"], starts=p["starts"], sustain=p["sustain"], Pout=(p["op"]["Pout"] if p["op"] else 0.0), Vdc=(p["op"]["Vdc"] if p["op"] else 0.0), rpm=(p["op"]["rpm"] if p["op"] else 0.0), lam=(p["op"]["lam"] if p["op"] else 0.0)) for V, p in r["perV"].items()}) for r in res if "error" not in r]
    json.dump(slim, open(os.path.join(HERE, "sweep_stage2.json"), "w"), indent=0)
    for key in ("lowflow", "uniform"):
        print(f"\nStage 2 top by J_{key}:")
        for r in sorted(slim, key=lambda r: -r["J"][key])[:8]:
            s = r["spec"]; print(f"  B{s['B']} {s['airfoil']} TSR_d {s['lam_d']} cs {s['c_scale']} cmax {s['c_max']*1000:.0f} db {s['dbeta']:+.0f} | J_u {r['J']['uniform']:.3f} J_low {r['J']['lowflow']:.3f} | sol {r['meta']['solidity']:.2f} c_root {r['meta']['c_root']*1000:.0f} c_max {r['meta']['c_maxval']*1000:.0f} | start {r['min_selfstart_V']} | P 0.5/0.7/1.0: {r['perV']['0.5']['Pout']:.2f}/{r['perV']['0.7']['Pout']:.2f}/{r['perV']['1.0']['Pout']:.2f}")
    # selection rule: maximise the mean of the two normalised objectives (uniform and low-flow), ties to the lower solidity (printability, cost); must self-start at 0.5 m/s under baseline cogging
    # selection over stages 1+2 (review C1/M2): the objectives already zero the output at flows where the candidate cannot self-start under the
    # BASELINE (induction-on) starting torque, so no separate self-start constraint is imposed; the only hard constraint is hub packaging:
    # the three (or B) root pockets must leave >= 12 deg of printed wall between them on the 28 mm hub (pocket arc <= 360/B - 12 deg).
    S1 = json.load(open(os.path.join(HERE, "sweep_stage1.json"))); allc = S1 + slim
    Ju = max(r["J"]["uniform"] for r in allc); Jl = max(r["J"]["lowflow"] for r in allc)
    WALL_MIN_DEG = 12.0
    ok = [r for r in allc if r["meta"].get("hub_wall_deg", 0) >= WALL_MIN_DEG]
    score = lambda r: (0.5 * r["J"]["uniform"] / Ju + 0.5 * r["J"]["lowflow"] / Jl, -r["meta"]["solidity"])
    ok.sort(key=score, reverse=True); best = ok[0]
    hand = max(ok, key=lambda r: 0.5 * r["J"]["uniform_hand"] / max(x["J"]["uniform_hand"] for x in allc) + 0.5 * r["J"]["lowflow_hand"] / max(x["J"]["lowflow_hand"] for x in allc))
    print("\nSELECTED:", best["spec"], "J", best["J"], "start", best["min_selfstart_V"], "c_root", best["meta"]["c_root"], "wall", best["meta"].get("hub_wall_deg"))
    print("hand-started best:", hand["spec"], hand["J"]["uniform_hand"], hand["J"]["lowflow_hand"])
    json.dump(dict(rule=f"max 0.5*J_uniform/max + 0.5*J_lowflow/max (J gated by the induction-on starting torque, sustain and the 5 V converter floor) subject to hub wall >= {WALL_MIN_DEG:.0f} deg between pockets; ties to lower solidity",
                   ranked=[dict(spec=r["spec"], J=r["J"], c_root=r["meta"]["c_root"], solidity=r["meta"]["solidity"], hub_wall_deg=r["meta"].get("hub_wall_deg"), min_selfstart_V=r["min_selfstart_V"], score=score(r)[0]) for r in ok[:15]], Ju_max=Ju, Jl_max=Jl,
                   unconstrained_best=dict(spec=max(allc, key=lambda r: score(r)[0])["spec"], J=max(allc, key=lambda r: score(r)[0])["J"]),
                   hand_started_best=dict(spec=hand["spec"], J=hand["J"], min_selfstart_V=hand["min_selfstart_V"])), open(os.path.join(HERE, "selection.json"), "w"), indent=1)
    full = evaluate(best["spec"]); write_selected(full, os.path.join(HERE, "selected_design.json")); print("selected_design.json and selection.json written")
