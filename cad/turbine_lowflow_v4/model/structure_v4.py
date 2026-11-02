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
# ---- items from the mechanical review (M4, C4, M7, m4, joint): all analytical screening, not FEA
L = info["layout"]
# single 608 as the only rotor support (M4): overhang from the rotor CG (x ~ 4 mm) to the bearing centre; tilt from the radial clearance
x_brg_c = L["cap"]["x_brg"] + P["brg_w"] / 2; overhang = (x_brg_c - 4.0) / 1000
m_rotor = (3 * m_blade + sum(pp["volume_mm3"] for pp in info["parts"] if pp["name"] in ("hub_front", "hub_rear")) * 1.07e-6)   # kg (ASA)
M_weight = m_rotor * 9.81 * overhang; M_asym = 0.2 * T2 * 0.020                     # 20 % thrust asymmetry at 20 mm lever (assumed)
tilt_mrad = {cr: cr / 3.5 * 1e3 for cr in (0.005, 0.012)}                         # radial clearance (mm) over a ~7 mm race contact span -> mrad
tip_motion_mm = {k: v * 1e-3 * (101.6 + overhang * 1000) for k, v in tilt_mrad.items()}
seal_ecc_mm = {k: v * 1e-3 * abs(x_brg_c - (L["cap"]["x_seal"] + P["seal_w"] / 2)) for k, v in tilt_mrad.items()}
dog_motion_mm = {k: v * 1e-3 * abs((L["shaft"]["x_end"] - 3.0) - x_brg_c) for k, v in tilt_mrad.items()}
# hub retention (C4): circlip A load = thrust; bearing pressure of the circlip on the 316 washer and of the washer on the ASA hub rear face
A_washer_hub = math.pi / 4 * (P["washer_od"] ** 2 - (P["shaft_d"] + 0.4) ** 2); p_hub_rear = T2 / A_washer_hub
# nose screw: M3 at 0.5 N m -> ~830 N preload on the 13 mm washer -> pressure on the hub floor annulus (14.5 hole, 8.2 bore)
F_m3 = 0.5 / (0.2 * 0.003); A_floor = math.pi / 4 * (13.0 ** 2 - 8.2 ** 2); p_floor = F_m3 / A_floor
# hub bolts (m4): M3 at 0.2 N m under 7 mm washers
F_bolt = 0.2 / (0.2 * 0.003); A_w7 = math.pi / 4 * (7.0 ** 2 - 3.4 ** 2); p_bolt_washer = F_bolt / A_w7
# shaft joint: M5 thread in tension from the rotor thrust (plus preload), torsion of the stub tube (8 OD / 5.05 bore) under the seal, spigot shear
A_m5 = 14.2; sig_thread = (T2 + F_m3) / A_m5
J_stub = math.pi / 32 * (8.0 ** 4 - 5.05 ** 4); tau_stub = Q2 * 1e3 * 4.0 / J_stub
# stake socket (M7): device drag ~ thrust + cap step + ring (assumed +25 %) at the ring-centre height above the socket mouth
F_dev = 1.25 * T2; h_lever = (P["duct_od"] / 2 + P["sock_len"]) / 1000; M_sock = F_dev * h_lever
p_sock = 6 * M_sock * 1e3 / (P["sock_bore"] * P["sock_len"] ** 2)                 # peak bearing pressure 6M/(dL^2), MPa
# guard ring in-plane stiffness (thin ring, diametral point load): d = 0.149 F R^3 / (E I); 8 N of bed/debris contact
E_asa = 2000.0; I_ring = P["duct_len"] * (P["duct_od"] / 2 - P["duct_id"] / 2) ** 3 / 12; R_ring = (P["duct_od"] + P["duct_id"]) / 4
defl_per_N = 0.149 * R_ring ** 3 / (E_asa * I_ring); tip_gap = P["duct_id"] / 2 - 101.6
review_items = dict(overhang_mm=overhang * 1e3, m_rotor_kg=m_rotor, M_weight_Nm=M_weight, M_asym_Nm=M_asym, tilt_mrad=tilt_mrad, tip_motion_mm=tip_motion_mm, seal_ecc_mm=seal_ecc_mm, dog_motion_mm=dog_motion_mm,
                    p_hub_rear_MPa=p_hub_rear, p_floor_MPa=p_floor, p_bolt_washer_MPa=p_bolt_washer, sig_thread_MPa=sig_thread, tau_stub_MPa=tau_stub,
                    F_device_N=F_dev, M_socket_Nm=M_sock, p_socket_MPa=p_sock, ring_defl_mm_per_N=defl_per_N, ring_defl_8N_mm=8 * defl_per_N, tip_gap_mm=tip_gap)
out = dict(V=2.0, T_rotor_N=T2, Q_rotor_Nm=Q2, rpm_op=op2["rpm"], rpm_runaway=rpm_run, T_blade_N=T_blade, M_root_Nm=M_root, c_root_mm=c_root * 1000, t_root_mm=t_root * 1000, sig_root_MPa=sig_root,
           m_blade_g=m_blade * 1000, F_cf_N=F_cf, bolt_shear_MPa=bolt_shear, tongue_bearing_MPa=tongue_bearing, ligament_mm=ligament, shear_out_MPa=shear_out, wall_bearing_MPa=wall_bearing, end_bearing_MPa=end_bearing,
           pocket_arc_deg=math.degrees(ang), hub_wall_deg=wall_deg, hub_wall_mm_floor=wall_mm_floor, hub_wall_mm_top=wall_mm_top, strut_leg_MPa=sig_leg, strut_bar_MPa=sig_bar, tau_shaft_MPa=tau_shaft, tau_flat_MPa=d_flat_tau, Fa_C0=Fa_C0,
           allow=dict(long_XY=8, long_Z=4.5, short_XY=15, short_Z=8, ils_long=2.7, ils_short=4.8), review=review_items)
json.dump(out, open(os.path.join(HERE, "structure_v4.json"), "w"), indent=1)
print(f"2 m/s: thrust {T2:.1f} N ({T_blade:.1f}/blade), torque {Q2:.2f} N m at {op2['rpm']:.0f} rpm; runaway {rpm_run:.0f} rpm")
print(f"root bending {sig_root:.2f} MPa (NACA 4418 root, chord {c_root*1000:.0f}, t {t_root*1000:.1f}); CF {F_cf:.0f} N (blade {m_blade*1000:.0f} g) -> bolt double shear {bolt_shear:.1f} MPa, tongue bearing {tongue_bearing:.2f} MPa, ligament {ligament:.1f} mm shear-out {shear_out:.2f} MPa")
print(f"pocket walls: pocket arc {math.degrees(ang):.0f} deg -> wall {wall_deg:.0f} deg = {wall_mm_floor:.1f} mm at the floor / {wall_mm_top:.1f} mm at the surface; wall bearing {wall_bearing:.2f} MPa; end bearing {end_bearing:.2f} MPa")
print(f"review items: tilt {tilt_mrad} mrad -> tip {tip_motion_mm} mm, seal ecc {seal_ecc_mm} mm, dog {dog_motion_mm} mm; hub rear {p_hub_rear:.2f} MPa, floor {p_floor:.1f} MPa, bolt washer {p_bolt_washer:.1f} MPa; thread {sig_thread:.1f} MPa, stub torsion {tau_stub:.1f} MPa; socket {p_sock:.2f} MPa (M {M_sock:.2f} N m), ring {8*defl_per_N:.2f} mm per 8 N, tip gap {tip_gap:.1f} mm")
print(f"strut leg bending {sig_leg:.2f} MPa, bar tension {sig_bar:.2f} MPa; shaft torsion {tau_shaft:.1f} MPa (D-flat {d_flat_tau:.1f}); 608 Fa/C0 {Fa_C0:.3f}")
