#!/usr/bin/env python3
"""Engineering calculations for the turbine-generator assembly (pure Python).
Loads, bearings, seal-friction sensitivity, thermal, depth stack-ups and a
generator load-line model that is evaluated with measured/published Kv and R."""
import json, math, os
HERE = os.path.dirname(os.path.abspath(__file__))
spec = json.load(open(os.path.join(HERE, "..", "water_turbine_blade", "design_spec.json")))
R = spec["tip_radius_mm"] / 1000; R_HUB = spec["hub_radius_mm"] / 1000; RHO = 1000.0
perf = spec["performance"]; tsr = spec["cp_curve"]["tsr"]

print("=== Rotor operating points (BEM, shaft side, before losses) ===")
for V in ("1.0", "1.5", "2.0"):
    d = perf[V]["operating"]
    print(f"V={V} m/s: {d['rpm']:.0f} rpm  P={d['P_W']:.1f} W  Q={d['Q_Nm']:.2f} N m  thrust={d['T_N']:.0f} N  "
          f"static Q={perf[V]['static_torque_Nm']:.3f} N m  runaway {perf[V]['runaway_rpm']:.0f} rpm")

# ------------------------------------------------------------------ loads
print("\n=== Load path ===")
T2, T3 = perf["2.0"]["operating"]["T_N"], perf["2.0"]["operating"]["T_N"] * (3.0 / 2.0) ** 2 * (0.75 / 0.705)
Q2 = perf["2.0"]["operating"]["Q_Nm"]
m_rotor = 3 * spec["blade_volume_mm3"] * 1.27e-6 + 0.10          # kg: 3 PETG blades + printed hub ~100 g
rpm_run = perf["2.0"]["runaway_rpm"]; om_run = rpm_run * 2 * math.pi / 60
e_unbal = 0.5e-3                                                   # 0.5 mm residual unbalance eccentricity
F_unbal = m_rotor * om_run ** 2 * e_unbal
# shear-flow / yaw asymmetry: crude 10 % thrust imbalance across the disk -> side force and moment
F_side = 0.10 * T2; M_yaw = 0.10 * T2 * 0.5 * R
print(f"rotor thrust: {perf['1.0']['operating']['T_N']:.0f} / {perf['1.5']['operating']['T_N']:.0f} / {T2:.0f} N at 1/1.5/2 m/s; ~{T3:.0f} N in a 3 m/s flood")
print(f"shaft torque: {perf['1.0']['operating']['Q_Nm']:.2f} .. {Q2:.2f} N m; jam/flood case ~{Q2*2:.1f} N m")
print(f"rotor mass ~{m_rotor*1000:.0f} g; unbalance force at runaway {rpm_run:.0f} rpm with 0.5 mm eccentricity: {F_unbal:.1f} N")
print(f"shear-flow asymmetry (10 % of thrust): side force {F_side:.1f} N, yaw moment {M_yaw:.2f} N m")
# two-bearing shaft: overhang a from front bearing to rotor centre, span b between bearings
a, b = 0.035, 0.030
F_rad = F_side + F_unbal; M = M_yaw + F_rad * a
R_front = F_rad * (a + b) / b + M_yaw / b; R_rear = F_rad * a / b + M_yaw / b
print(f"two-bearing shaft (overhang {a*1000:.0f} mm, span {b*1000:.0f} mm): front bearing radial {R_front:.0f} N, rear {R_rear:.0f} N; axial {T2:.0f} N on the thrust bearing")
d_sh = 0.010; sigma_b = M * (d_sh / 2) / (math.pi * d_sh ** 4 / 64)
print(f"10 mm 316 shaft bending at the front bearing: M={M:.2f} N m -> {sigma_b/1e6:.1f} MPa (316 yield ~ 200-240 MPa)")
tau = Q2 * 2 * (d_sh / 2) / (math.pi * d_sh ** 4 / 32)
print(f"10 mm shaft torsion at 2x jam torque {Q2*2:.1f} N m: {tau/1e6:.1f} MPa; 3 mm 316 cross pin double shear at {Q2*2:.1f} N m / 5 mm radius: "
      f"{(Q2*2/0.005)/(2*math.pi*0.0015**2)/1e6:.0f} MPa (316 shear ~ 300 MPa)")

# ------------------------------------------------------------------ bearings
print("\n=== Bearing L10 (ISO 281, P = X Fr + Y Fa with e~0.22, X=0.56, Y=2.0 for small Fa/C0) ===")
bearings = {"6000-2RS (10x26x8)": (4.55e3, 1.96e3), "6900-2RS (10x22x6)": (2.70e3, 1.27e3), "608-2RS (8x22x7)": (3.30e3, 1.37e3),
            "6200-2RS (10x30x9)": (5.10e3, 2.36e3), "SS 6000 (440C, ~0.8x)": (3.6e3, 1.6e3), "ZrO2 full ceramic 6000 (~0.5x)": (2.3e3, 1.0e3)}
Fr, Fa = 15.0, T2
for name, (C, C0) in bearings.items():
    P = max(Fr, 0.56 * Fr + 2.0 * Fa)
    L10_rev = (C / P) ** 3 * 1e6; L10_h = L10_rev / (475 * 60)
    print(f"{name:32s} C={C/1000:.2f} kN C0={C0/1000:.2f} kN  P={P:.0f} N  L10={L10_h:.2e} h  (Fa/C0={Fa/C0:.3f})")
print("-> bearing fatigue life is not a design driver; contamination, corrosion and seal condition are.")

# ------------------------------------------------------------------ seal friction sensitivity
print("\n=== Rotary seal friction vs. the 1 m/s start and output ===")
Qs1 = perf["1.0"]["static_torque_Nm"]; P1 = perf["1.0"]["operating"]["P_W"]; w1 = perf["1.0"]["operating"]["rpm"] * 2 * math.pi / 60
for name, Tf in [("none (magnetic coupling)", 0.0), ("PTFE lip seal, 10 mm", 0.012), ("NBR single lip, 8 mm", 0.025), ("NBR double lip, 10 mm", 0.045), ("V-ring + bearing drag", 0.008)]:
    print(f"{name:28s} friction {Tf:.3f} N m = {Tf/Qs1*100:4.0f} % of the 1 m/s static torque; running loss {Tf*w1:.2f} W = {Tf*w1/P1*100:3.0f} % of the 1 m/s shaft power")

# ------------------------------------------------------------------ thermal
print("\n=== Thermal: generator losses inside a sealed, water-cooled cartridge ===")
for Ploss in (3.0, 8.0, 15.0):
    # path: winding -> motor base -> aluminium end cap (negligible) -> water (h ~ 500-2000 W/m2K on a 55 mm cap)
    A_cap = math.pi * 0.0275 ** 2; dT_water = Ploss / (800 * A_cap)
    # alternative: through a 3 mm PETG tube wall, k=0.2, area 0.012 m2 (tube 57 mm x 70 mm)
    dT_petg = Ploss * 0.003 / (0.2 * 0.012)
    print(f"loss {Ploss:4.1f} W: water-side film rise on an aluminium cap ~{dT_water:4.1f} K; through a 3 mm PETG wall ~{dT_petg:4.1f} K; "
          f"motor base-to-case contact adds ~{Ploss*1.0:4.1f} K at 1 K/W")

# ------------------------------------------------------------------ depth stack-ups
print("\n=== Axial depth stack-ups (mm) ===")
stack = {
 "A  nacelle behind rotor, lip seal": [("nose cone", 20), ("hub/blades", 45), ("seal + front bearing block", 22), ("coupling to motor shaft", 12), ("GB5015 motor", 29), ("rear cap + penetrator", 14)],
 "B  hub-integrated outrunner":      [("nose cone", 18), ("hub shell incl. motor 29 + bearings/seal 20", 60), ("rear spindle boss + struts", 12)],
 "C  mag-coupled static cartridge":  [("nose cone", 20), ("hub/blades", 45), ("outer magnet rotor + wet bearing", 18), ("can wall + gap", 4), ("inner magnet rotor", 12), ("GB5015 motor", 29), ("rear cap + penetrator", 14)],
}
for k, items in stack.items():
    tot = sum(v for _, v in items)
    print(f"{k:36s} total {tot:4.0f} mm = {tot/25.4:.2f} in  ({tot/76.2*100:.0f} % of the 76.2 mm target)   " + ", ".join(f"{n} {v}" for n, v in items))

# ------------------------------------------------------------------ generator load-line model (parametrised)
def generator_points(Kv_rpm_per_V, R_line_ohm, V_batt=None, I_max=None, label=""):
    """Kv: no-load rpm per volt of *line-to-line* back-EMF (hobby convention). Kt = 60/(2 pi Kv) N m/A.
    Returns per water speed the equilibrium point of rotor torque curve vs generator torque for
    (a) MPPT (ideal: generator sits at the rotor's peak-Cp TSR) and (b) a plain rectifier into a battery."""
    Kt = 60 / (2 * math.pi * Kv_rpm_per_V)
    out = {}
    for V in ("1.0", "1.5", "2.0"):
        Vw = float(V); cps = spec["cp_curve"][f"cp_{V}"]
        A = math.pi * R ** 2
        # (a) MPPT: operate at peak Cp, generator absorbs the rotor torque unless I_max limits it
        j = max(range(len(cps)), key=lambda i: cps[i]); lam = tsr[j]; om = lam * Vw / R; rpm = om * 60 / (2 * math.pi)
        Pm = cps[j] * 0.5 * RHO * A * Vw ** 3; Q = Pm / om; I = Q / Kt
        limited = I_max is not None and I > I_max
        if limited:  # generator cannot absorb the torque: find TSR above peak where rotor torque = Kt*I_max
            Qg = Kt * I_max
            for i in range(j, len(cps)):
                om_i = tsr[i] * Vw / R; Qr = cps[i] * 0.5 * RHO * A * Vw ** 3 / om_i
                if Qr <= Qg:
                    lam, om, rpm = tsr[i], om_i, om_i * 60 / (2 * math.pi); Pm = cps[i] * 0.5 * RHO * A * Vw ** 3; Q = Pm / om; I = Q / Kt
                    break
        E = rpm / Kv_rpm_per_V                     # line-to-line back-EMF (RMS-ish, hobby Kv convention)
        Pcu = 1.5 * I ** 2 * R_line_ohm            # three phases, line resistance R_line = 2 R_phase -> 1.5 I^2 R_line
        Pe = Pm - Pcu - 0.5                        # ~0.5 W iron/rectifier/bearing allowance
        out[V] = dict(mode="MPPT" + (" (current-limited)" if limited else ""), tsr=lam, rpm=rpm, Pm=Pm, Q=Q, I=I, E_ll=E, Vdc=1.35 * E - 1.0, Pcu=Pcu, Pe=max(Pe, 0), eta=max(Pe, 0) / Pm if Pm > 0 else 0)
    return Kt, out

if __name__ == "__main__":
    print("\n=== Generator model: illustrative Kv/R pairs (replace with published/measured values) ===")
    for Kv, Rl, lab in [(30, 10.0, "gimbal-class 5015, 30 rpm/V, 10 ohm line"), (30, 5.0, "same, 5 ohm"), (60, 2.5, "fewer turns: 60 rpm/V, 2.5 ohm"), (100, 1.0, "100 rpm/V, 1 ohm")]:
        Kt, pts = generator_points(Kv, Rl)
        print(f"-- {lab}: Kt={Kt:.3f} N m/A")
        for V, p in pts.items():
            print(f"   {V} m/s: {p['rpm']:.0f} rpm, Q={p['Q']:.2f} N m, I={p['I']:.2f} A, E_ll={p['E_ll']:.1f} V, Vdc~{p['Vdc']:.1f} V, Pcu={p['Pcu']:.1f} W, Pelec={p['Pe']:.1f} W of {p['Pm']:.1f} W (eta {p['eta']*100:.0f} %)")
