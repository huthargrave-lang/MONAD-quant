#!/usr/bin/env python3
"""Structural, sealing, pressure and thermal checks for redesign v3.1 (analytical screening; no FEA).
Every number the report quotes is computed here and written to structure_results_v3.json (review R05: no hand-typed values)."""
import json, math, os
HERE = os.path.dirname(os.path.abspath(__file__))
cad = json.load(open(os.path.join(HERE, "..", "cad", "out", "v3_info.json")))
P = cad["params"]; V_ = cad["variants"]; lay = cad["configs"]["min76"]["layout"]
res = json.load(open(os.path.join(HERE, "system_results_v3.json")))
out = {}
# ------------------------------------------------ printed-material allowables (ASSUMPTIONS, to be replaced by coupon tests: gate 1)
mat = dict(name="ASA (provisional; PETG comparable)", E_GPa=1.8, tens_XY_MPa=38.0, tens_Z_MPa=22.0,
           allow_long_XY=8.0, allow_long_Z=4.5, allow_short_XY=15.0, allow_short_Z=8.0, allow_interlaminar_shear_long=2.7, allow_interlaminar_shear_short=4.8,
           note="bulk filament 40-45 MPa; printed XY ~85-95 %, Z ~50-60 %; wet/aged/creep/fatigue knockdown ~0.45 -> long-term allowables; short-term (flood, debris) x1.9; "
                "interlaminar shear taken as 0.6 x Z tensile (assumption)")
print("Printed allowables (assumed):", mat)
T = {k: res["cases"][k] for k in ("1.0", "1.5", "2.0", "2.2", "3.0")}
thrust = {k: T[k]["T_max"] for k in T}
print("Maximum rotor thrust along the curve (N):", {k: round(v, 1) for k, v in thrust.items()}, " (at the charging point:", {k: round(T[k]["modes"]["mppt"]["T"], 1) if T[k]["modes"]["mppt"] else None for k in T}, ")")
# ------------------------------------------------ blade root: airfoil-section tongue, 2 axial pins (ISO 8752 3 x 36, 1.4310 spring steel)
r_top = lay["r_pad_top"] / 1000; r_cp = 0.072
F_thrust_blade = thrust["3.0"] / 3; M_root = F_thrust_blade * (r_cp - r_top)
F_thrust_blade_2 = thrust["2.0"] / 3; M_root_2 = F_thrust_blade_2 * (r_cp - r_top)
pin_len_in_tongue = min(lay["pin_material_mm"]) / 1000              # material along each pin inside the tongue
pocket_depth = P["pocket_d"] / 1000; d_pin = P["pin_d"] / 1000
# bound (a): the pins take the whole flap moment -> couple on each pin over its embedded length (triangular bearing: lever 2/3 L)
F_pin_couple = (M_root / 2) / (2 / 3 * pin_len_in_tongue)
tongue_bearing_pin = F_pin_couple / (d_pin * pin_len_in_tongue / 3) / 1e6             # bearing over the loaded third of the embedded length
pin_bending = (M_root / 2) / (math.pi * (d_pin / 2) ** 3 / 4) / 1e6                   # pin as a beam carrying half the root moment
# bound (b): the pocket walls take the whole flap moment -> couple over the pocket depth, bearing on the thin trailing/leading regions
F_wall = M_root / (2 / 3 * pocket_depth)
tongue_w_wrapped = lay["tongue_tangential_extent"] / 1000 * 0.6                        # ~60 % of the section bears (airfoil faces inclined ~20 deg)
wall_bearing = F_wall / (tongue_w_wrapped * pocket_depth / 3) / 1e6
# centrifugal: pins in double shear + tongue ligament shear-out (across the layers of a flat-printed blade)
m_blade = next(p["volume_mm3"] for p in cad["configs"]["min76"]["parts"] if p["name"] == "blade_0") * 1.07e-3 / 1000   # kg at 1.07 g/cm3
rpm_run3 = T["3.0"]["modes"]["open"]["rpm"]; om3 = rpm_run3 * 2 * math.pi / 60
rpm_run22 = T["2.2"]["modes"]["open"]["rpm"]; om22 = rpm_run22 * 2 * math.pi / 60
r_cg = 0.070
F_cf = m_blade * om3 ** 2 * r_cg; F_cf22 = m_blade * om22 ** 2 * r_cg
pin_shear_cf = F_cf / (2 * 2 * math.pi * (P["pin_d"] / 2) ** 2)
ligament = (lay["pin_z"] - P["pin_d"] / 2 - lay["pocket_floor_r"] - P["pocket_clear"]) / 1000
shear_out = F_cf / (2 * 2 * ligament * pin_len_in_tongue) / 1e6
shear_out22 = F_cf22 / (2 * 2 * ligament * pin_len_in_tongue) / 1e6
# torque: tangential blade force bears on the pocket's thin end
Q_max = max(T[k]["Q_max"] for k in T)
F_tang_blade = Q_max / 3 / 0.07
end_bearing = F_tang_blade / (3.0e-3 * pocket_depth) / 1e6
print(f"Blade root (3 m/s): thrust/blade {F_thrust_blade:.1f} N, flap moment at the pad top {M_root:.2f} N m (2 m/s: {M_root_2:.2f}).")
print(f"   bound (a) pins take it all: pin bending {pin_bending:.0f} MPa (1.4310 spring pin yield > 1000, plain 316 dowel ~200); tongue bearing at the pins {tongue_bearing_pin:.1f} MPa (allow 15 short / 8 long)")
print(f"   bound (b) pocket walls take it all: wall bearing {wall_bearing:.2f} MPa over the loaded third of the {pocket_depth*1000:.1f} mm depth")
print(f"   centrifugal at 3 m/s runaway ({rpm_run3:.0f} rpm, blade {m_blade*1000:.0f} g, r_cg 70 mm): {F_cf:.0f} N -> pin double shear {pin_shear_cf:.1f} MPa; ligament {ligament*1000:.1f} mm below the pins -> shear-out {shear_out:.2f} MPa short-term (allow {mat['allow_interlaminar_shear_short']}); at 2.2 m/s runaway {F_cf22:.0f} N -> {shear_out22:.2f} MPa sustained (allow {mat['allow_interlaminar_shear_long']})")
print(f"   torque: {F_tang_blade:.1f} N tangential per blade on the pocket end (3 x {pocket_depth*1000:.1f} mm) -> {end_bearing:.2f} MPa")
# airfoil root section just above the pad: NACA 44xx, chord c, t/c -> I ~ 0.036 c t^3 (thin-section estimate)
c = lay["root_chord_at_pad"] / 1000; tc = float(P["tc_root"]); t = tc * c; I = 0.036 * c * t ** 3; sig_root = M_root * (t / 2) / I / 1e6
print(f"Blade airfoil root (r {lay['r_pad_top']:.1f} mm, chord {c*1000:.1f}, t {t*1000:.1f}) bending: {sig_root:.2f} MPa at 3 m/s (allow 15 short-term, layers along the span when printed flat); 3/rev strut-wake fatigue NOT assessed (gate 7)")
# ------------------------------------------------ carrier: lugs, bolts, ears
lug_shear = Q_max / (P["tube_od"] / 2000) / (3 * P["lug_w"] * P["lug_h"])
bolt_T = 0.3; bolt_F = bolt_T / (0.2 * 0.003)
washer_od, washer_id = 12.0, 3.4; A_w = math.pi / 4 * (washer_od ** 2 - washer_id ** 2)
ear_bearing = bolt_F / A_w
print(f"Carrier: max rotor torque {Q_max:.2f} N m (3 m/s) -> lug shear (3 printed lugs 6 x 3 in the 6061 flange notches, r 38.1) {lug_shear:.2f} MPa; "
      f"6x M3 316 bolts at {bolt_T} N m -> ~{bolt_F:.0f} N each; under 12 mm penny washers {ear_bearing:.1f} MPa on the ears (allow 8 long-term); nut traps on the +60 deg ears")
# ------------------------------------------------ struts: 6061-T6 4 mm profile-cut plate
Fs = thrust["3.0"] / 3; L = (P["duct_id"] / 2 - P["boss_od"] / 2 + 6) / 1000
tab_w = V_["min76"]["boss_t"] - 0.4
Z_outer = P["strut_t"] * P["strut_w"] ** 2 / 6; Z_tab = P["strut_t"] * tab_w ** 2 / 6
M_fixed_fixed = Fs * L / 2                                      # boss pocket constrains the tab rotation, duct clevis fixes the outer end
M_cantilever = Fs * L                                          # bound: pinned boss end, cantilever from the duct
strut_sigma_tab = M_fixed_fixed / Z_tab * 1e3; strut_sigma_duct = M_cantilever / Z_outer * 1e3
tip_defl = Fs * L ** 3 / (3 * 69e9 * (P["strut_t"] * P["strut_w"] ** 3 / 12) * 1e-12)
clevis_bolt_shear = (M_cantilever / 0.0055) / (2 * math.pi * 2 ** 2) if True else 0   # couple over the 5.5 mm bolt spacing, 2 bolts in double shear (A4-70)
print(f"Struts (3 m/s, {Fs:.1f} N each, span {L*1000:.0f} mm): tab (fixed-fixed bound) {M_fixed_fixed:.2f} N m -> {strut_sigma_tab:.1f} MPa in the {tab_w:.1f} x 4 tab; duct end (cantilever bound) {M_cantilever:.2f} N m -> {strut_sigma_duct:.1f} MPa in the 16 x 4 leg "
      f"(6061-T6 yield 240, fatigue ~95); tip deflection {tip_defl*1000:.2f} mm; clevis M4 bolts {clevis_bolt_shear:.0f} MPa shear (A4-70 ~ 450)")
# ------------------------------------------------ bearings and 6061 seats
brg = {}
for var, C, C0 in (("min76 6702-2RS", 1.08e3, 0.62e3), ("robust 6902-2RS", 2.70e3, 1.27e3)):
    Fa = thrust["2.0"]; Fa3 = thrust["3.0"]; Fr = 10.0
    Pq = 0.56 * Fr + 2.0 * Fa; L10 = (C / Pq) ** 3 * 1e6 / (500 * 60)
    brg[var] = dict(C=C, C0=C0, Fa2=Fa, Fa3=Fa3, Fa3_C0=Fa3 / C0, L10_h=L10, Fa_cap_N=0.25 * C0)
    print(f"Bearing {var}: C {C:.0f} N, C0 {C0:.0f} N; axial {Fa:.0f} N (2 m/s) / {Fa3:.0f} N (3 m/s) -> Fa/C0 {Fa3/C0:.2f} (keep < 0.5; practical axial capacity ~0.25 C0 = {0.25*C0:.0f} N bounds handling/reverse loads); L10 at 2 m/s {L10:.1e} h")
seat_stress = thrust["3.0"] / (math.pi * V_["min76"]["brg_od"] * 1.0)
print(f"6061 bearing-seat shoulder bearing stress (1 mm shoulder, 3 m/s thrust): {seat_stress:.2f} MPa; caps are 6061 (CTE matched to the tube and the bearings: no POM creep or thermal fit change, review M5)")
# ------------------------------------------------ sealing: O-rings, lip seal, pressure, breathing
seal = {}
for var in ("min76", "robust"):
    Vv = V_[var]; bore_nom, bore_tol = P["tube_id"], 0.15
    plug = P["tube_id"] - P["plug_clear"]; g_od = plug - 2 * P["oring_groove_d"]
    sq = {}
    for bore in (bore_nom - bore_tol, bore_nom, bore_nom + bore_tol):
        gland = (bore - g_od) / 2; sq[round(bore, 2)] = (1 - gland / P["oring_cs"]) * 100
        print(f"O-ring gland ({var}, {Vv['n_orings']} ring(s)): bore {bore:.2f} -> gland depth {gland:.3f} mm -> squeeze {sq[round(bore,2)]:.1f} % (target 15-25 %)")
    fill = (math.pi / 4 * P["oring_cs"] ** 2) / (P["oring_groove_w"] * ((bore_nom - g_od) / 2)) * 100
    stretch = (g_od / 67.95 - 1) * 100
    print(f"   groove fill {fill:.0f} % (keep < 90 %); AS568-147 ID 67.95 on groove OD {g_od:.2f}: stretch {stretch:.1f} %; lands {P['oring_land']} mm (review R18)")
    seal[var] = dict(squeeze_pct=sq, fill_pct=fill, stretch_pct=stretch, n_orings=Vv["n_orings"])
p_depth = 1000 * 9.81 * 2.0; p_vac = 70e3
F_cap = p_depth * math.pi * (P["tube_id"] / 2000) ** 2
lip_bearing = F_cap / (math.pi * P["tube_od"] * 2)
print(f"Pressure: 2 m depth -> {p_depth/1000:.1f} kPa, {F_cap:.0f} N inward on each cap (carrier lips: {lip_bearing:.2f} MPa); vacuum test -70 kPa -> {p_vac*math.pi*(P['tube_id']/2000)**2:.0f} N per cap")
p_breath = 101.3e3 * (1 - (273.15 + 5) / (273.15 + 40))
p_diff = (p_depth + p_breath) / 1e5
v_surf = math.pi * 0.015 * rpm_run3 / 60
print(f"Lip seal differential: 2 m depth {p_depth/1e3:.1f} kPa + warm-assembly/cold-water breathing {p_breath/1e3:.1f} kPa = {p_diff:.2f} bar -> a plain NBR oil seal (0.3 bar at speed) is NOT adequate; "
      f"PTFE pressure-rated lip seal (Trelleborg Varilip PDR class, 5 bar) or Freudenberg BABSL (10 bar at < 1 m/s) specified. Surface speed 15 mm x {rpm_run3:.0f} rpm = {v_surf:.2f} m/s.")
# internal overpressure from stator heating (lifts the lip): drum air rise assumed <= 30 % of the winding rise
# ------------------------------------------------ thermal path (defined metal path; no air-gap or drum-air credit)
k_al = 167.0; L_sp = (lay["x_boss"][0] - lay["x_motor"][1]) / 1000 + 0.004
A_sp = math.pi / 4 * ((P["spindle_d"] / 1000) ** 2 - (P["spindle_bore"] / 1000) ** 2)
R_wb = 1.5          # winding -> stator base (ASSUMED, typical for a potted/varnished gimbal stator; review m6)
R_sf = 0.3          # stator base -> integral flange, bolted with thermal paste (ASSUMED)
R_sp = L_sp / (k_al * A_sp)
R_bj = 0.3          # spindle -> boss slip fit with thermal paste (ASSUMED; ~1.0 dry)
A_boss_wet = math.pi / 4 * (P["boss_od"] / 1000) ** 2 + math.pi * (P["boss_od"] / 1000) * (V_["min76"]["boss_t"] / 1000)
R_bw = 1 / (800 * A_boss_wet)
R_tot = R_wb + R_sf + R_sp + R_bj + R_bw
Pcu12 = 1.2 ** 2 * 5.5
print(f"Heat path: winding->base {R_wb} + base->flange {R_sf} + spindle {R_sp:.2f} ({L_sp*1000:.0f} mm) + boss joint {R_bj} + boss->water {R_bw:.2f} = {R_tot:.2f} K/W")
for Ploss in (2.0, 5.0, Pcu12, 11.6):
    print(f"   {Ploss:4.1f} W stator loss -> winding +{Ploss*R_tot:.0f} K over water; drum air est. <= +{Ploss*R_tot*0.3:.0f} K -> internal overpressure {101.3*Ploss*R_tot*0.3/300:.1f} kPa (vs 4.9 kPa head at 0.5 m)")
dT_drum_air = Pcu12 * R_tot * 0.3; dP_internal = 101.3e3 * dT_drum_air / 300
min_depth_m = dP_internal / (1000 * 9.81)
print(f"GL60 stator limit: class B assumed (130 C). 1.2 A -> {Pcu12:.1f} W copper -> +{Pcu12*R_tot:.0f} K (metal path only): acceptable, MUST be measured (winding-resistance method, gate 9). "
      f"Minimum operating depth {min_depth_m:.2f} m keeps the net seal differential external at full current (lip-lift / pumping review M4); close the drum at <= water temperature + 10 K.")
out = dict(material=mat, thrust=thrust, Q_max=Q_max, F_thrust_blade_3ms=F_thrust_blade, M_root=M_root, M_root_2ms=M_root_2, pin_bending_MPa=pin_bending, tongue_bearing_pin_MPa=tongue_bearing_pin,
           wall_bearing_MPa=wall_bearing, F_cf=F_cf, F_cf22=F_cf22, pin_shear_cf_MPa=pin_shear_cf, ligament_mm=ligament * 1000, shear_out_MPa=shear_out, shear_out22_MPa=shear_out22,
           end_bearing_MPa=end_bearing, m_blade_g=m_blade * 1000, airfoil_root_MPa=sig_root, root_chord_mm=c * 1000, lug_shear_MPa=lug_shear, bolt_F=bolt_F, ear_bearing_MPa=ear_bearing,
           strut_sigma_tab=strut_sigma_tab, strut_sigma_duct=strut_sigma_duct, strut_tip_defl_mm=tip_defl * 1000, strut_span_mm=L * 1000, clevis_bolt_shear_MPa=clevis_bolt_shear, bearings=brg,
           seat_stress_MPa=seat_stress, seal=seal, F_cap_N=F_cap, lip_bearing_MPa=lip_bearing, p_breath_kPa=p_breath / 1e3, p_diff_bar=p_diff, v_surf_ms=v_surf,
           R_wb=R_wb, R_sf=R_sf, R_sp=R_sp, R_bj=R_bj, R_bw=R_bw, R_tot=R_tot, L_sp_mm=L_sp * 1000, Pcu_limit_W=Pcu12, dT_limit=Pcu12 * R_tot, dT_drum_air=dT_drum_air, dP_internal_kPa=dP_internal / 1e3, min_depth_m=min_depth_m)
json.dump(out, open(os.path.join(HERE, "structure_results_v3.json"), "w"), indent=1)
