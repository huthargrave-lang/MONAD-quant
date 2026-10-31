#!/usr/bin/env python3
"""Reconstruct the group member's values-only CSV (Trial 1: 7 in, 2.2 m/s, 3 blades, 20 strips) from
first principles and compare every exported number.  ALL equations here are RECONSTRUCTED (the
original workbook formulas were not supplied); a match within display rounding supports but does not
prove the reconstruction."""
import csv, math, json, os
CSV = "/home/user/packet_in/p1/Claude_turbine_redesign_packet/01_original_inputs/IED_HW7_Focused_Analytical_apporach_Final(Trial 1).csv"
rows = list(csv.reader(open(CSV, encoding="cp1252")))
raw = dict(zip(rows[2], rows[3]))                      # Raw Inputs row -> values
P = dict(Preq=10.0, Vd=2.2, D_in=7.0, B=3, N=20, rho=998.6, nu=1.053e-6, Re_polar=2e5, alpha_d=5.0, CL=1.0, CD=0.0127,
         Kv=170.0, Rg=0.72, I0=0.4, dmotor=0.0556, twall=0.002, Vf=0.5, Tseal=0.01, Vin_min=3.0)
hdr = next(i for i, r in enumerate(rows) if r and r[0].strip() == "Strip")
strips = rows[hdr + 1: hdr + 21]                       # the 20 strip rows that follow the "Strip" header
exp = [dict(strip=int(r[0]), r=float(r[1]), lam_r=float(r[2]), phi=float(r[3]), a=float(r[4]), ap=float(r[5]), c=float(r[6]), twist=float(r[7]),
            F=float(r[8]), dragf=float(r[9]), mdot=float(r[10]), swirl=float(r[11]), dT=float(r[12]), W=float(r[13]), Re=float(r[14])) for r in strips]
res_row = [r for r in rows if r and r[0].strip() == "0.4995"][0]
exp_res = dict(T=float(res_row[0]), Pw=float(res_row[1]), Cp=float(res_row[2]), Ke=float(res_row[3]), Tp=float(res_row[4]), E=float(res_row[5]), Pe=float(res_row[6]))
calc_row = [r for r in rows if r and r[0].startswith("4.1887")][0]
exp_calc = dict(lam=float(calc_row[0]), R=float(calc_row[1]), rh=float(calc_row[2]), dr_disp=float(calc_row[3]), om=float(calc_row[4]), rpm=float(calc_row[5]), CDCL=float(calc_row[6]), lam_run=float(calc_row[7]), q=float(calc_row[8]), ratio=float(calc_row[9]))

# ---------------- reconstructed model ----------------
R = P["D_in"] * 0.0254 / 2                              # 0.0889 m
rh = P["dmotor"] / 2 + P["twall"]                       # 0.0298 m  (hub radius = motor radius + wall)
dr = (R - rh) / P["N"]                                  # 2.955 mm (the CSV shows 0.003 under a "[mm]" label: value is metres, display-rounded)
om = exp_calc["om"]                                     # 103.66 rad/s is an INPUT of the trial (exported, not derived here)
rpm = om * 60 / (2 * math.pi); lam = om * R / P["Vd"]
def glauert_a(lam_r):
    """Glauert optimum axial induction with wake rotation: lam_r^2 = (1-a)(4a-1)^2/(1-3a)  (RECONSTRUCTED)."""
    lo, hi = 0.25 + 1e-9, 1 / 3 - 1e-9
    for _ in range(100):
        a = 0.5 * (lo + hi)
        f = (1 - a) * (4 * a - 1) ** 2 / (1 - 3 * a) - lam_r ** 2
        if f > 0: hi = a
        else: lo = a
    return 0.5 * (lo + hi)
out = []; T = 0.0
for k in range(P["N"]):
    r = rh + (k + 0.5) * dr
    lam_r = om * r / P["Vd"]
    a = glauert_a(lam_r)
    ap = (-1 + math.sqrt(1 + 4 * a * (1 - a) / lam_r ** 2)) / 2      # a'(1+a') lam_r^2 = a(1-a)   (RECONSTRUCTED)
    phi = math.atan((1 - a) / ((1 + ap) * lam_r))
    c = 8 * math.pi * r * a * math.sin(phi) ** 2 / (P["B"] * P["CL"] * (1 - a) * math.cos(phi))   # momentum-matched chord, no tip loss (RECONSTRUCTED)
    twist = math.degrees(phi) - P["alpha_d"]
    ftip = P["B"] * (R - r) / (2 * r * math.sin(phi)); fhub = P["B"] * (r - rh) / (2 * rh * math.sin(phi))
    F = (2 / math.pi) * math.acos(math.exp(-ftip)) * (2 / math.pi) * math.acos(math.exp(-fhub))   # Prandtl tip x hub loss (RECONSTRUCTED; hub form uses rh in the denominator)
    dragf = 1 - (P["CD"] / P["CL"]) / math.tan(phi)                    # torque reduction by drag (RECONSTRUCTED)
    mdot = P["rho"] * 2 * math.pi * r * dr * P["Vd"] * (1 - a)           # annulus mass flow
    swirl = 2 * ap * om * r                                              # wake tangential velocity
    dT = mdot * swirl * r * F * dragf                                    # strip torque (RECONSTRUCTED)
    W = math.sqrt((P["Vd"] * (1 - a)) ** 2 + (om * r * (1 + ap)) ** 2)
    Re = W * c / P["nu"]
    T += dT
    out.append(dict(strip=k + 1, r=r, lam_r=lam_r, phi=math.degrees(phi), a=a, ap=ap, c=c, twist=twist, F=F, dragf=dragf, mdot=mdot, swirl=swirl, dT=dT, W=W, Re=Re))
Pw = 0.5 * P["rho"] * math.pi * R ** 2 * P["Vd"] ** 3
Cp = T * om / Pw
Ke = 60 / (2 * math.pi * P["Kv"]); E = Ke * om; Tp = Ke * P["I0"] + P["Tseal"]
Pe_max = (E - 2 * P["Vf"]) ** 2 / (4 * P["Rg"])                          # fixed-speed maximum into a matched load (RECONSTRUCTED)
I_pm = (E - 2 * P["Vf"]) / (2 * P["Rg"]); V_pm = (E - 2 * P["Vf"]) / 2

# ---------------- comparison ----------------
keys = ["r","lam_r","phi","a","ap","c","twist","F","dragf","mdot","swirl","dT","W","Re"]
worst = {}
for e, o in zip(exp, out):
    for k in keys:
        err = abs(o[k] - e[k]) / (abs(e[k]) if e[k] else 1)
        if err > worst.get(k, (0, 0))[0]: worst[k] = (err, e["strip"])
print("Per-column worst relative deviation (reconstruction vs export, after the export's rounding):")
for k in keys:
    print(f"  {k:6s}: {worst[k][0]*100:6.3f} % (strip {worst[k][1]})")
print(f"\nTotals: T recon {T:.4f} vs exported {exp_res['T']}  | Pw {Pw:.4f} vs {exp_res['Pw']} | Cp {Cp:.6f} vs {exp_res['Cp']} | Ke {Ke:.6f} vs {exp_res['Ke']} | Tp {Tp:.6f} vs {exp_res['Tp']} | E {E:.3f} vs {exp_res['E']} | Pe,max {Pe_max:.3f} vs {exp_res['Pe']}")
print(f"Calculated inputs: lam {lam:.6f} vs {exp_calc['lam']} | rpm {rpm:.2f} vs {exp_calc['rpm']} | R {R:.9f} vs {exp_calc['R']} | rh {rh} vs {exp_calc['rh']} | dr {dr*1000:.3f} mm (export shows {exp_calc['dr_disp']} under a [mm] label -> metres, display-rounded)")
print(f"Fixed-speed max-power load point: I = {I_pm:.3f} A, V_load = {V_pm:.3f} V (below the 3 V charger minimum), generator torque Ke*I = {Ke*I_pm:.3f} N m vs rotor torque {T:.3f} N m -> NOT a torque balance")
print(f"Shaft power T*omega = {T*om:.2f} W; electrical fixed-speed bound {Pe_max:.2f} W = {Pe_max/(T*om)*100:.1f} % of shaft power (the rest is not absorbed: the rotor would accelerate)")
print("Not reconstructed: 'lam_run' 6.493, the 0.1646 cell and the 1.55 ratio (no supporting equation found).")
json.dump(dict(inputs=P, R=R, rh=rh, dr=dr, omega=om, rpm=rpm, lam=lam, strips=out, T=T, Pw=Pw, Cp=Cp, Ke=Ke, E=E, Tp=Tp, Pe_max=Pe_max, I_pm=I_pm, V_pm=V_pm,
               worst_rel_dev=worst), open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "trial1_reconstruction.json"), "w"), indent=1)
