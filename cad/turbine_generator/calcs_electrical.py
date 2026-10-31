#!/usr/bin/env python3
"""Generator + drivetrain performance across the flow range for the candidate generators.
Convention (hobby): E_LL,peak [V] = rpm / KV;  Kt [N m/A] = 60/(2 pi KV) with I = rectifier DC current;
copper loss ~ I_dc^2 * R_LL (R_LL measured between two leads);  V_dc = E - I R_LL - 0.8 V (two Schottky drops).
Mechanical losses: lip seal + 2 dry bearings + (B only) extra drum bearings.  Rotor curves from the reviewed BEM."""
import json, math, os
HERE = os.path.dirname(os.path.abspath(__file__))
spec = json.load(open(os.path.join(HERE, "..", "water_turbine_blade", "design_spec.json")))
R = spec["tip_radius_mm"] / 1000; RHO = 1000.0; A = math.pi * R ** 2; tsr = spec["cp_curve"]["tsr"]
gens = {
  "CubeMars GL60 KV25 (primary; published KV 21.5-25, R_LL 4.6-5.5 ohm; using 21.5 / 5.5)": dict(KV=21.5, R=5.5, Imax=1.5, Pth=20.0, cog=0.024),
  "iPower GM5208-24 (backup; KV ~20.8, R_LL 13.7 ohm per iFlight; 25.6 per RobotShop -> conflicting)": dict(KV=20.8, R=13.7, Imax=1.2, Pth=10.0, cog=0.008),
  "GB5015 if it measures like a GM5208-24 winding (KV 21, 13.7 ohm) - UNVERIFIED": dict(KV=21.0, R=13.7, Imax=1.0, Pth=8.0, cog=0.006),
  "GB5015 if '220 mN m @ 14.8 V' is stall torque (Km <= 0.08): KV 25 / 25 ohm": dict(KV=25.0, R=25.0, Imax=0.8, Pth=8.0, cog=0.006),
}
mech = {"A (nacelle, lip seal on 12 mm Speedi-Sleeve)": dict(seal=0.012, brg=0.006, extra=0.0, hub="50.8 mm"),
        "B (hub drum, lip seal on 15 mm spindle)": dict(seal=0.015, brg=0.006, extra=0.004, hub="70.8 mm")}

def rotor_curve(V, cp_key):
    cps = spec["cp_curve"][cp_key]
    return [(l, cps[i] * 0.5 * RHO * A * V ** 3 if cps[i] > 0 else 0.0) for i, l in enumerate(tsr)]

def operate(V, cp_key, g, m, mode="mppt"):
    """Find the operating point: generator torque + mechanical friction = rotor torque.
    mppt: track the rotor peak; cap the DC current at Imax (then the rotor speeds up along its curve)."""
    Kt = 60 / (2 * math.pi * g["KV"])
    curve = rotor_curve(V, cp_key)
    best = max(curve, key=lambda t: t[1]); lam_pk = best[0]
    Tfric = m["seal"] + m["brg"] + m["extra"]
    # walk from the peak to higher TSR until the generator can absorb the net torque
    for lam, Pm in [c for c in curve if c[0] >= lam_pk]:
        om = lam * V / R; Q = Pm / om if om > 0 else 0
        Qg = Q - Tfric
        if Qg <= 0:
            continue
        I = Qg / Kt
        if I <= g["Imax"]:
            break
    else:
        return None
    rpm = om * 60 / (2 * math.pi); E = rpm / g["KV"]
    Pcu = I * I * g["R"]; Vdc = max(E - I * g["R"] - 0.8, 0.0)
    Pfric = Tfric * om; Pgen_in = Qg * om; Pe = Vdc * I
    return dict(tsr=lam, rpm=rpm, Pm=Pm, Q=Q, Qg=Qg, I=I, E=E, Vdc=Vdc, Pcu=Pcu, Pfric=Pfric, Pe=Pe, eta_gen=Pe / Pgen_in if Pgen_in > 0 else 0,
                eta_total=Pe / Pm if Pm > 0 else 0, Ploss_cu_th=Pcu, limited=I >= g["Imax"] - 1e-9)

def static_check(V, g, m):
    Qs = spec["performance"][V]["static_torque_Nm"]
    Tb = m["seal"] * 2 + m["brg"] + m["extra"] + g["cog"]        # breakaway: seal ~2x running, cogging
    return Qs, Tb

if __name__ == "__main__":
    out = {}
    for mname, m in mech.items():
        cpk = {"1.0": "cp_1.0", "1.5": "cp_1.5", "2.0": "cp_2.0"}
        print(f"\n=== {mname} ===")
        for gname, g in gens.items():
            Kt = 60 / (2 * math.pi * g["KV"]); Km = Kt / math.sqrt(g["R"])
            print(f"-- {gname}\n   Kt={Kt:.3f} N m/A, Km={Km:.3f} N m/sqrt(W)")
            rows = []
            for V in ("1.0", "1.5", "2.0"):
                Vw = float(V)
                hub_scale = 1.0 if mname.startswith("A") else 0.90      # B's larger hub (BEM: Cp 0.332 vs 0.368 at 1.5 m/s)
                r = operate(Vw, cpk[V], g, m)
                if r is None:
                    print(f"   {V} m/s: generator cannot absorb the rotor torque at any TSR"); continue
                for k in ("Pm", "Q", "Qg", "Pcu", "Pfric", "Pe"):
                    r[k] *= hub_scale
                Qs, Tb = static_check(V, g, m)
                rows.append(dict(V=V, **r, Qs=Qs, Tb=Tb))
                print(f"   {V} m/s: TSR {r['tsr']:.2f} {r['rpm']:.0f} rpm | shaft {r['Pm']:.1f} W | friction {r['Pfric']:.2f} W | I {r['I']:.2f} A{' (limit)' if r['limited'] else ''} "
                      f"| Vdc {r['Vdc']:.1f} V | Cu loss {r['Pcu']:.1f} W | DC out {r['Pe']:.1f} W | eta gen {r['eta_gen']*100:.0f} % | water->DC {r['eta_total']*100:.0f} % "
                      f"| start: static {Qs:.3f} vs breakaway {Tb:.3f} N m {'OK' if Qs > Tb else 'MARGINAL/NO'}")
            out[f"{mname} | {gname}"] = rows
    json.dump(out, open(os.path.join(HERE, "electrical_results.json"), "w"), indent=1)
    # runaway open-circuit voltage
    print("\nRunaway (no load) open-circuit DC for the GL60: " + ", ".join(f"{V} m/s: {spec['performance'][V]['runaway_rpm']/21.5*1.0:.0f} V" for V in ("1.0", "1.5", "2.0")))
