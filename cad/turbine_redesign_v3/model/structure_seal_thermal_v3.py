#!/usr/bin/env python3
"""Structural, sealing, pressure and thermal checks for redesign v3 (analytical screening; no FEA)."""
import json, math, os
HERE = os.path.dirname(os.path.abspath(__file__))
cad = json.load(open(os.path.join(HERE, "..", "cad", "out", "v3_info.json")))
P = cad["params"]; V_ = cad["variants"]
res = json.load(open(os.path.join(HERE, "system_results_v3.json")))
# ------------------------------------------------ printed-material allowables (ASSUMPTIONS)
mat = dict(name="ASA (provisional; PETG comparable)", E_GPa=1.8, tens_XY_MPa=38.0, tens_Z_MPa=22.0,
           allow_long_XY=8.0, allow_long_Z=4.5, allow_short_XY=15.0, allow_short_Z=8.0,
           note="bulk filament 40-45 MPa; printed XY ~85-95 %, Z ~50-60 %; wet/aged/creep/fatigue knockdown ~0.45 -> long-term allowables; short-term (flood, debris) x1.9")
print("Printed allowables (assumed):", mat)
T = {k: res["cases"][k] for k in ("1.0", "1.5", "2.0", "3.0")}
thrust = {k: T[k]["T_max"] for k in T}        # maximum thrust along the rotor curve (conservative for structure)
print("Maximum rotor thrust along the curve (N):", {k: round(v, 1) for k, v in thrust.items()}, " (at the charging point:", {k: round(T[k]["modes"]["mppt"]["T"], 1) if T[k]["modes"]["mppt"] else None for k in T}, ")")
# ------------------------------------------------ blade root (tongue joint)
F_thrust_blade = thrust["3.0"] / 3; r_cp = 0.072; M_root = F_thrust_blade * (r_cp - 0.048)
tongue_L, tongue_w, pin_x = P["pocket_len"] - 0.3, P["pocket_w"] - 0.3, P["pin_x"]
couple = M_root / (2 * pin_x / 1000)                           # pin pair reacts the flap moment
pin_shear = couple / (2 * math.pi * (P["pin_d"] / 2) ** 2)     # double shear, 316 pin
bearing_print = couple / (P["pin_d"] * tongue_w)                 # bearing on the printed tongue
m_blade = 0.030; rpm_run3 = T["3.0"]["modes"]["open"]["rpm"]; om = rpm_run3 * 2 * math.pi / 60
F_cf = m_blade * om ** 2 * 0.075
pin_cf_bearing = F_cf / (2 * P["pin_d"] * tongue_w)
print(f"Blade root (3 m/s flood): thrust/blade {F_thrust_blade:.1f} N, flap moment at the pad {M_root:.2f} N m -> pin couple {couple:.0f} N, pin shear {pin_shear:.1f} MPa (316 ~300), tongue bearing {bearing_print:.1f} MPa (allow 15 short / 8 long)")
print(f"Overspeed at 3 m/s runaway {rpm_run3:.0f} rpm: centrifugal {F_cf:.0f} N per blade -> pin bearing {pin_cf_bearing:.1f} MPa; tongue tension {F_cf/(tongue_L*tongue_w):.2f} MPa")
# airfoil root section stress just above the pad (chord ~36, t 0.24): I ~ 0.036 c t^3
c, t = 0.036, 0.0087; I = 0.036 * c * t ** 3; sig = M_root * (t / 2) / I / 1e6
print(f"Blade airfoil root (r 48 mm) bending: {sig:.2f} MPa at 3 m/s (allow 15 short-term, layers along the span when printed flat)")
# ------------------------------------------------ carrier: bolts, ears, pad walls
F_tang_blade = T["3.0"]["modes"]["open"]["Q"] / 3 / 0.07
print(f"Carrier: tangential blade force {F_tang_blade:.1f} N (jam 1.5 N m -> {1.5/3/0.07:.1f} N); 6x M3 316 through-bolts with nyloc; preload 400 N each -> ear bearing {400/(7*4):.1f} MPa under 7 mm washers (compression, OK)")
# ------------------------------------------------ struts: 6061-T6 flat bar 16x4
Fs = thrust["3.0"] / 3; L = (P["duct_id"] / 2 - P["boss_od"] / 2 + 6) / 1000
Z_outer = P["strut_t"] * P["strut_w"] ** 2 / 6; Z_inner = P["strut_t"] * (V_["min76"]["boss_t"] - 0.4) ** 2 / 6
M_duct = Fs * L; M_jog = Fs * ((P["r_jog1"] - P["boss_od"] / 2 + 6) / 1000)
print(f"Struts (3 m/s, {Fs:.1f} N each): moment at the duct foot {M_duct:.2f} N m -> {M_duct/Z_outer*1e3:.1f} MPa in the 16x4 bar; at the jog {M_jog:.2f} N m -> {M_jog/Z_inner*1e3:.1f} MPa in the 7.6x4 tab (6061-T6 yield 240; fatigue 95 MPa)")
tip_defl = Fs * L ** 3 / (3 * 69e9 * (P["strut_t"] * P["strut_w"] ** 3 / 12) * 1e-12)
print(f"   strut tip deflection (cantilever from the duct) {tip_defl*1000:.2f} mm at 3 m/s; generator reaction torque 1.5 N m -> {1.5/3/0.07:.1f} N tangential per strut -> {1.5/3/0.07*L/(P['strut_w']*P['strut_t']**2/6)*1e3:.1f} MPa weak-axis")
# ------------------------------------------------ bearings (6702 min76 / 6902 robust) and seats
for var, C, C0 in (("min76 6702-2RS", 1.08e3, 0.62e3), ("robust 6902-2RS", 2.70e3, 1.27e3)):
    Fa = thrust["2.0"]; Fa3 = thrust["3.0"]; Fr = 10.0
    Pq = 0.56 * Fr + 2.0 * Fa; L10 = (C / Pq) ** 3 * 1e6 / (500 * 60)
    print(f"Bearing {var}: C {C:.0f} N, C0 {C0:.0f} N; axial {Fa:.0f} N (2 m/s) / {Fa3:.0f} N (3 m/s) -> Fa/C0 {Fa3/C0:.2f} (keep < 0.5); L10 at 2 m/s {L10:.1e} h")
seat_stress = thrust["3.0"] / (math.pi * V_["min76"]["brg_od"] * 1.0)
print(f"Delrin bearing-seat shoulder bearing stress (1 mm shoulder, 3 m/s thrust): {seat_stress:.2f} MPa (POM creep limit ~10 MPa long-term)")
# ------------------------------------------------ sealing
for var in ("min76", "robust"):
    Vv = V_[var]
    bore_nom, bore_tol = P["tube_id"], 0.15
    plug = P["tube_id"] - P["plug_clear"]; g_od = plug - 2 * P["oring_groove_d"]
    for bore in (bore_nom - bore_tol, bore_nom, bore_nom + bore_tol):
        gland = (bore - g_od) / 2; sq = 1 - gland / P["oring_cs"]
        print(f"O-ring gland ({var}): bore {bore:.2f} -> gland depth {gland:.3f} mm -> squeeze {sq*100:.1f} % (target 15-25 %)")
    fill = (math.pi / 4 * P["oring_cs"] ** 2) / (P["oring_groove_w"] * ((bore_nom - g_od) / 2)) * 100
    print(f"   groove fill {fill:.0f} % (keep < 90 %); O-ring AS568-147 ID 67.95 on groove OD {g_od:.2f}: stretch {(g_od/67.95-1)*100:.1f} %")
p_depth = 1000 * 9.81 * 2.0; p_vac = 70e3
F_cap = p_depth * math.pi * (P["tube_id"] / 2000) ** 2
print(f"Pressure: 2 m depth -> {p_depth/1000:.1f} kPa, {F_cap:.0f} N inward on each cap (taken by the carrier lips: lip bearing {F_cap/(math.pi*P['tube_od']*2)/1:.2f} MPa); thermal breathing 40->5 C adds ~11 kPa; vacuum test -70 kPa -> {p_vac*math.pi*(P['tube_id']/2000)**2:.0f} N per cap")
print("Lip seal 15x22x4 / 15x24x5 NBR spring-loaded TC: rated typically 0.5 bar (static) / 0.3 bar at speed; service 0.2 bar + 0.11 kPa breathing: OK; speed 15 mm x 1270 rpm = 1.0 m/s surface speed (seals rated > 10 m/s)")
# ------------------------------------------------ thermal path (defined metal path only, no air-gap credit)
k_al = 167.0; L_sp = 0.050; A_sp = math.pi / 4 * ((P["spindle_d"] / 1000) ** 2 - (P["spindle_bore"] / 1000) ** 2)
R_sp = L_sp / (k_al * A_sp); R_joint = 0.8; R_boss = 1 / (800 * (2 * math.pi / 4 * (P["boss_od"] / 1000) ** 2))
R_tot = R_sp + R_joint + R_boss
for Ploss in (2.0, 5.0, 8.0, 11.6):
    print(f"Heat: {Ploss:4.1f} W stator loss -> spindle {R_sp:.2f} K/W + joint {R_joint:.1f} + boss/water {R_boss:.2f} = {R_tot:.2f} K/W -> winding +{Ploss*R_tot:.0f} K over water (metal path only); Delrin caps see the drum interior air, est. < +{Ploss*R_tot*0.3:.0f} K")
Pcu12 = 1.2 ** 2 * 5.5
print(f"GL60 stator limit: class B assumed (130 C); magnets on the bell cooler. Current limit 1.2 A -> {Pcu12:.1f} W copper -> about +{Pcu12*R_tot:.0f} K by the metal path alone (air-gap path not credited): acceptable, MUST be measured (winding-resistance method).")
json.dump(dict(material=mat, thrust=thrust), open(os.path.join(HERE, "structure_results_v3.json"), "w"), indent=1)
