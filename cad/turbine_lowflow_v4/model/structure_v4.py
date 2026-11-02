#!/usr/bin/env python3
"""Basic structural feasibility of the printed rotor and support at the 2 m/s survival case (analytical screening; no FEA).
Allowables (ASSUMED, as in redesign v3.1; coupons G3 replace them): ASA long-term wet 8 MPa in-plane / 4.5 MPa across layers, short-term 15 / 8;
interlaminar shear 2.7 / 4.8 MPa.  Writes structure_v4.json."""
import json, math, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, "..")
C = json.load(open(os.path.join(HERE, "coupled_results.json"))); info = json.load(open(os.path.join(ROOT, "out", "v4_info.json"))); P = info["params"]; sel = json.load(open(os.path.join(HERE, "selected_design.json")))
new = C["designs"]["new"]["res"]; p2 = new["perV"]["2.0"]; op2 = p2["op"]; oc2 = p2["open"]
lam = np.array(p2["lam"]); T2 = float(np.interp(op2["lam"], lam, p2["T"])); Q2 = op2["Qrot"]
T_blade = T2 / 3; r_cp = 0.072; r_hub = P["r_hub"] / 1000
M_root = T_blade * (r_cp - r_hub)                                              # flap moment at the hub surface
c_root = sel["chord_mm"][0] / 1000; t_root = 0.18 * c_root                     # NACA 4418 root section
I_root = 0.036 * c_root * t_root ** 3; sig_root = M_root * (t_root / 2) / I_root / 1e6
m_blade = next(p["volume_mm3"] for p in info["parts"] if p["name"] == "blade_0") * 1.07e-3 / 1000
rpm_run = oc2["rpm"]; om = rpm_run * 2 * math.pi / 60; F_cf = m_blade * om ** 2 * 0.070
bolt_d = 3.0; A_bolt = math.pi * bolt_d ** 2 / 4
bolt_shear = F_cf / (2 * A_bolt)                                               # double shear (two hub halves)
tongue_len_axial = float(np.ptp(np.array(info["layout"]["stations"]["outline"])[:, 0]))
bear_len = min(tongue_len_axial, P["hub_len"]) * 0.5                            # bolt bearing length in the tongue (half the axial pocket width, conservatively)
tongue_bearing = F_cf / (bolt_d * bear_len)
ligament = P["bolt_r"] - bolt_d / 2 - P["pocket_floor_r"] - P["pocket_clear"]
shear_out = F_cf / (2 * ligament * bear_len)
# flap moment taken by the pocket walls (bound) over the pocket depth
depth = P["r_hub"] - P["pocket_floor_r"]; F_wall = M_root / (2 / 3 * depth / 1000); wall_bearing = F_wall / (0.6 * tongue_len_axial * depth / 3)
# torque: tangential force on the pocket end
F_tan = Q2 / 3 / 0.07; end_bearing = F_tan / (3.0 * depth)
# minimum hub wall between adjacent pockets: angular extent of the pocket outline at r_hub
outl = np.array(info["layout"]["stations"]["outline"]); ang = np.ptp(outl[:, 1]) / P["r_hub"] + 2 * P["pocket_clear"] / P["r_hub"]
wall_deg = 360 / 3 - math.degrees(ang); wall_mm_floor = math.radians(wall_deg) * P["pocket_floor_r"]; wall_mm_top = math.radians(wall_deg) * P["r_hub"]
# struts: radial leg 18 x 6 at the clamp, thrust shared by 3, lever from the clamp to the ring bar junction
Fs = T2 / 3; L_leg = (P["duct_od"] / 2 + 6.0 - P["tube_od"] / 2 - P["clamp_t"]) / 1000
Z_leg = P["strut_t"] * P["strut_w"] ** 2 / 6; sig_leg = Fs * L_leg / Z_leg * 1e3
sig_bar = Fs / (P["strut_w"] * P["strut_t"])                                   # axial bar in tension
# shaft: bending between collar B and the hub from the rotor thrust eccentricity is nil (axial); torsion 0.5 N m in 8 mm 316: tau = 16 T / (pi d^3)
tau_shaft = 16 * Q2 / (math.pi * 0.008 ** 3) / 1e6; d_flat_tau = 16 * Q2 / (math.pi * 0.007 ** 3) / 1e6
# bearing: 608 C0 1.4 kN
Fa_C0 = T2 / 1400
out = dict(V=2.0, T_rotor_N=T2, Q_rotor_Nm=Q2, rpm_op=op2["rpm"], rpm_runaway=rpm_run, T_blade_N=T_blade, M_root_Nm=M_root, c_root_mm=c_root * 1000, t_root_mm=t_root * 1000, sig_root_MPa=sig_root,
           m_blade_g=m_blade * 1000, F_cf_N=F_cf, bolt_shear_MPa=bolt_shear, tongue_bearing_MPa=tongue_bearing, ligament_mm=ligament, shear_out_MPa=shear_out, wall_bearing_MPa=wall_bearing, end_bearing_MPa=end_bearing,
           pocket_arc_deg=math.degrees(ang), hub_wall_deg=wall_deg, hub_wall_mm_floor=wall_mm_floor, hub_wall_mm_top=wall_mm_top, strut_leg_MPa=sig_leg, strut_bar_MPa=sig_bar, tau_shaft_MPa=tau_shaft, tau_flat_MPa=d_flat_tau, Fa_C0=Fa_C0,
           allow=dict(long_XY=8, long_Z=4.5, short_XY=15, short_Z=8, ils_long=2.7, ils_short=4.8))
json.dump(out, open(os.path.join(HERE, "structure_v4.json"), "w"), indent=1)
print(f"2 m/s: thrust {T2:.1f} N ({T_blade:.1f}/blade), torque {Q2:.2f} N m at {op2['rpm']:.0f} rpm; runaway {rpm_run:.0f} rpm")
print(f"root bending {sig_root:.2f} MPa (NACA 4418 root, chord {c_root*1000:.0f}, t {t_root*1000:.1f}); CF {F_cf:.0f} N (blade {m_blade*1000:.0f} g) -> bolt double shear {bolt_shear:.1f} MPa, tongue bearing {tongue_bearing:.2f} MPa, ligament {ligament:.1f} mm shear-out {shear_out:.2f} MPa")
print(f"pocket walls: pocket arc {math.degrees(ang):.0f} deg -> wall {wall_deg:.0f} deg = {wall_mm_floor:.1f} mm at the floor / {wall_mm_top:.1f} mm at the surface; wall bearing {wall_bearing:.2f} MPa; end bearing {end_bearing:.2f} MPa")
print(f"strut leg bending {sig_leg:.2f} MPa, bar tension {sig_bar:.2f} MPa; shaft torsion {tau_shaft:.1f} MPa (D-flat {d_flat_tau:.1f}); 608 Fa/C0 {Fa_C0:.3f}")
