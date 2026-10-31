#!/usr/bin/env python
"""Coupled rotor / drivetrain / generator / rectifier / charger model for redesign v3.
Conventions (stated, see REPORT section 6):
  - Rotor: Cp(lambda, V) from the reviewed BEM (Re-dependent NACA 44xx polar, Prandtl tip+hub loss), r_hub 42 mm, R 101.6 mm.
  - Hobby KV = no-load rpm per volt of DC bus. Open-circuit DC after a 6-pulse bridge: V_oc = rpm / KV.
    With 14 pole pairs and sinusoidal back-EMF this equals the line-line PEAK; the bridge follows that peak at no load.
  - Energy-consistent torque constant: Kt = 60/(2 pi KV) N m per ampere of DC current (P_shaft = T w = V_oc I at no loss).
  - Loaded DC voltage: V_dc = V_oc - I R_LL - (3/pi) w_e (L_LL/2) I - 2 Vf   (copper, commutation overlap, two diode drops).
  - Copper loss = I^2 R_LL (the DC current flows through two phases in series at any instant).
  - Mechanical friction torque: lip seal + 2 bearings (running), from the assumptions table; breakaway = seal x2 + bearings + cogging.
Every number not from the BEM or the manufacturer is an ASSUMPTION and is listed in ASSUMPTIONS."""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "water_turbine_blade"))
import numpy as np
import make_blade as mb
HERE = os.path.dirname(os.path.abspath(__file__))
cad = json.load(open(os.path.join(HERE, "..", "cad", "out", "v3_info.json")))
bp = cad["params"]
mb.R_HUB = bp["r_hub"]; mb.R_ROOT_EXT = bp["r_hub"] - 3.0; mb.C_MAX = bp["c_max"]; mb.PEAK_R = bp["peak_r"]
mb.TC_ROOT = bp["tc_root"]; mb.TC_TIP = bp["tc_tip"]; mb.TE_THICK = bp["te"]; mb.TIP_CHORD_FRAC = bp["tip_frac"]
blade = mb.design_blade(bp["lg"], bp["db"])
R_AERO_HUB = cad["configs"]["min76"]["layout"]["r_pad_top"]      # 48.2 mm: the printed blade has no airfoil below the pad top (review R01)
mb.R_HUB = R_AERO_HUB                                              # BEM integrates (and applies hub loss) from the real blade root
R = mb.R / 1000; RHO = 1000.0; A = math.pi * R ** 2

ASSUMPTIONS = dict(
    generator="CubeMars GL60 KV25 (manufacturer values per the 31 Oct 2026 review citation; pages not reachable from this session)",
    KV=21.5, R_LL=5.5, L_LL=2.72e-3, pole_pairs=14, I_rated=1.35, I_peak=4.0, T_rated=0.6,
    Kt_note="Kt = 60/(2 pi 21.5) = 0.444 N m/A (energy-consistent); the page also quotes 0.45 (0.40 on one reseller)",
    Vf_diode=0.55, rectifier="6x MBR10100 (100 V Schottky), Vf ~0.55 V at 1-2 A (estimate)",
    seal_running_Nm=0.0075, seal_breakaway_factor=2.0, bearing_running_Nm=0.004, bearings=2, cogging_Nm=0.024,
    friction_note="PTFE lip seal (Varilip PDR / Dichta) 15 mm: ~half of an NBR seal: 7.5 mN m running, 15 breakaway (assumed; no measured value exists); NBR alternative 15 / 30 mN m; cogging 24 mN m inferred for the GL60 (II lists 2.4 cN m)",
    seal_alt_running_Nm=0.015,
    iron_loss_W_at_700rpm=1.0, iron_note="no-load (iron + bearing-seal) loss of the GL60 is not published; 1.0 W at 700 rpm scaling with rpm^1.5 assumed (the trial's Ke*I0 implied ~1.8 W)",
    charger="Victron SmartSolar MPPT 100/15 (buck): starts when V_pv >= V_bat + 5 V, runs while V_pv >= V_bat + 1 V; 100 V max input",
    battery_V=13.2, charger_eff=0.95, charger_quiescent_W=0.3,
    gen_current_limit=1.2, current_limit_note="target generator-side limit (thermal); implemented only as the Victron battery-side charge-current limit below",
    batt_current_limit=2.5, batt_limit_note="Victron charge-current limit: I_gen <= I_batt_lim * V_bat / (eta * V_dc); equals 1.2 A only at V_dc >= 29 V",
    dump_R=22.0, dump_engage_V=45.0, dump_release_V=12.0, dump_resistor="Ohmite HS100 22R J (100 W) on a submerged 6061 plate (potted terminals): compromise between tip cavitation (sigma 1.09 at 3 m/s) and winding copper loss (20 W at 3 m/s)",
    drum_len_m=0.058, drum_note="rotating drum wetted length (tube + cap flanges) for the windage estimate",
    dump_note="engage above the 2.2 m/s open-circuit voltage band is impossible (60 V), so engage 45 V catches >= ~1.7 m/s; release 12 V sits below every dump-equilibrium bus so the relay does not cycle",
    water_temp_note="BEM polars at 15 C",
)
import copy
BASE_G = copy.deepcopy(ASSUMPTIONS)
G = copy.deepcopy(ASSUMPTIONS)
def reset_G():
    G.clear(); G.update(copy.deepcopy(BASE_G))

def rotor_curve(V, n=48):
    lams = np.r_[np.linspace(0.05, 0.8, 12), np.linspace(0.9, 7.5, n - 12)]
    out = []
    for l in lams:
        r = mb.bem(blade, float(l), V, n_el=40)
        out.append((float(l), r["cp"], r["P"], r["Q"], r["T"]))
    return out

def rotor_at(curve, lam):
    ls = [c[0] for c in curve]
    j = int(np.clip(np.searchsorted(ls, lam), 1, len(ls) - 1))
    l0, l1 = ls[j - 1], ls[j]; f = (lam - l0) / (l1 - l0)
    return tuple(curve[j - 1][i] + f * (curve[j][i] - curve[j - 1][i]) for i in range(1, 5))   # cp, P, Q, T

def gen_point(rpm, I):
    """DC bus voltage and losses for a given rpm and DC current."""
    Kt = 60 / (2 * math.pi * G["KV"])
    Voc = rpm / G["KV"]
    w_e = rpm / 60 * 2 * math.pi * G["pole_pairs"]
    dV_comm = (3 / math.pi) * w_e * (G["L_LL"] / 2) * I                      # commutation-overlap voltage reduction: reactive, NOT a loss (review R06)
    Vdc = Voc - I * G["R_LL"] - dV_comm - 2 * G["Vf_diode"]
    Tgen = (Voc - dV_comm) * I / (rpm * 2 * math.pi / 60) if rpm > 0 else Kt * I   # torque from power balance: shaft = DC + copper + diode
    return dict(Kt=Kt, Voc=Voc, Vdc=max(Vdc, 0.0), Pcu=I * I * G["R_LL"], Pdiode=2 * G["Vf_diode"] * I, Tgen=Tgen, dV_comm=dV_comm)

def current_for_torque(rpm, Qg):
    """DC current that gives shaft torque Qg at this rpm with the overlap-reduced torque constant (quadratic in I)."""
    om = rpm * 2 * math.pi / 60; w_e = om * G["pole_pairs"]
    Voc = rpm / G["KV"]; a = (3 / math.pi) * w_e * (G["L_LL"] / 2)
    if a < 1e-9: return Qg * om / Voc
    disc = Voc * Voc - 4 * a * Qg * om
    if disc < 0: return Voc / (2 * a)                                              # torque beyond the pull-out limit at this speed
    return (Voc - math.sqrt(disc)) / (2 * a)

def drum_windage(rpm, V):
    """Skin-friction torque of the rotating drum (cylinder 76.2 x L_drum in axial flow + 2 end faces). ASSUMPTION: flat-plate
    turbulent Cf on the relative velocity; the blades' own drag is already in the BEM. (review m1)"""
    om = rpm * 2 * math.pi / 60; Rd = 0.0381; Ld = G["drum_len_m"]; nu = 1.0e-6
    Ut = om * Rd; Urel = math.sqrt(Ut * Ut + V * V)
    Re = max(Urel * Ld / nu, 1e4); Cf = 0.074 * Re ** -0.2
    tau = 0.5 * RHO * Cf * Urel * Urel
    Q_cyl = tau * (2 * math.pi * Rd * Ld) * Rd * (Ut / Urel) if Urel > 0 else 0.0
    Re_d = max(om * Rd * Rd / nu, 1.0); Cm = 3.87 * Re_d ** -0.5 if Re_d < 3e5 else 0.146 * Re_d ** -0.2
    Q_disc = 0.5 * Cm * RHO * om * om * Rd ** 5                                 # one face; the dome front + the rear cap annulus ~ 1.5 faces
    return Q_cyl + 1.5 * Q_disc

def friction_running(rpm=700.0, V=0.0):
    return G["seal_running_Nm"] + G["bearings"] * G["bearing_running_Nm"] + iron_torque(rpm) + drum_windage(rpm, V)

def iron_torque(rpm):
    """no-load generator loss as an equivalent torque (ASSUMPTION, see G['iron_note'])."""
    if rpm <= 1: return 0.0
    Pfe = G["iron_loss_W_at_700rpm"] * (rpm / 700.0) ** 1.5
    return Pfe / (rpm * 2 * math.pi / 60)

def operating_point(V, curve, mode):
    """Solve rotor torque = generator torque + friction along the rotor curve for a given load law.
    mode 'mppt': maximise DC power subject to the current limit and the charger's V_dc >= V_bat + 1 rule.
    mode 'dump': load = fixed resistor R_dump on the DC bus.  mode 'brake': 3-phase short.  mode 'open': no load."""
    best = None
    for lam, cp, P, Q, T in curve:
        om = lam * V / R; rpm = om * 60 / (2 * math.pi)
        Tf = friction_running(rpm, V)
        Qg = Q - Tf
        if Qg <= 0:
            continue
        gp0 = gen_point(rpm, 0.0)
        if mode == "open":
            cand = dict(lam=lam, rpm=rpm, I=0.0, Vdc=gp0["Voc"], Pdc=0.0, Pm=P, Q=Q, Qg=0.0, cp=cp, T=T)
            # open circuit: equilibrium where Qg == 0 i.e. Q == Tf -> pick the point with the smallest |Qg|
            score = -abs(Qg)
        elif mode == "mppt":
            I = current_for_torque(rpm, Qg)
            gp = gen_point(rpm, I)
            if gp["Vdc"] < G["battery_V"] + 1.0:
                continue                                     # buck charger cannot run below V_bat + 1 V
            if I * gp["Vdc"] * G["charger_eff"] / G["battery_V"] > G["batt_current_limit"]:
                continue                                     # Victron battery-current limit reached: this lambda is not an equilibrium
            Pdc = gp["Vdc"] * I
            cand = dict(lam=lam, rpm=rpm, I=I, Vdc=gp["Vdc"], Pdc=Pdc, Pm=P, Q=Q, Qg=Qg, cp=cp, T=T, Pcu=gp["Pcu"], Pdiode=gp["Pdiode"], Pfe=iron_torque(rpm) * om, I_batt=Pdc * G["charger_eff"] / G["battery_V"])
            score = Pdc
        elif mode == "dump":
            # resistor: I = Vdc / R_dump with Vdc from gen_point -> solve for I at this rpm, then check torque balance
            Kt = gp0["Kt"]; w_e = rpm / 60 * 2 * math.pi * G["pole_pairs"]
            Rtot = G["R_LL"] + (3 / math.pi) * w_e * (G["L_LL"] / 2) + G["dump_R"]
            I = max(gp0["Voc"] - 2 * G["Vf_diode"], 0) / Rtot
            Tg = gen_point(rpm, I)["Tgen"]
            score = -abs(Tg - Qg)
            cand = dict(lam=lam, rpm=rpm, I=I, Vdc=I * G["dump_R"], Pdc=I * I * G["dump_R"], Pm=P, Q=Q, Qg=Tg, cp=cp, T=T, Pcu=I * I * G["R_LL"], mismatch=Tg - Qg)
        elif mode == "brake":
            Kt = gp0["Kt"]; w_e = rpm / 60 * 2 * math.pi * G["pole_pairs"]
            # 3-phase short: per-phase |I| = E_ph / sqrt(R_ph^2 + (w_e L_ph)^2); torque = 3 E_ph I cos(phi)/w ... use the DC-equivalent: I_eq = Voc / sqrt(R_LL^2 + (w_e L_LL)^2)
            Z = math.sqrt(G["R_LL"] ** 2 + (w_e * G["L_LL"]) ** 2)
            I = gp0["Voc"] / Z
            Tb = Kt * I * (G["R_LL"] / Z)                    # only the in-phase (resistive) component produces torque
            score = -abs(Tb - Qg)
            cand = dict(lam=lam, rpm=rpm, I=I, Vdc=0.0, Pdc=0.0, Pm=P, Q=Q, Qg=Tb, cp=cp, T=T, Pcu=Tb * om, mismatch=Tb - Qg)
        if best is None or score > best[0]:
            best = (score, cand)
    return best[1] if best else None

def startup(V, curve):
    Qs = mb.bem(blade, 0.1, V)["Q"]
    Tb = G["seal_running_Nm"] * G["seal_breakaway_factor"] + G["bearings"] * G["bearing_running_Nm"] + G["cogging_Nm"]
    Tb_nbr = G["seal_alt_running_Nm"] * G["seal_breakaway_factor"] + G["bearings"] * G["bearing_running_Nm"] + G["cogging_Nm"]
    margin_run = min(c[3] - friction_running(c[0] * V / R * 60 / (2 * math.pi), V) for c in curve if c[0] <= 3.0)
    return dict(static_Q=Qs, breakaway=Tb, start_ok=Qs > Tb, ratio=Qs / Tb, breakaway_nbr=Tb_nbr, ratio_nbr=Qs / Tb_nbr, min_running_margin_Nm=margin_run)

def dump_study(V, curve):
    res = {}
    for Rd in (15.0, 22.0, 33.0, 47.0, 68.0):
        G["dump_R"] = Rd
        d = operating_point(V, curve, "dump")
        res[str(Rd)] = dict(rpm=d["rpm"], Vdc=d["Vdc"], I=d["I"], Pres=d["Pdc"], Pcu=d["Pcu"], sigma_tip=cavitation_sigma(d["rpm"], V))
    reset_G()
    return res

def cavitation_sigma(rpm, V, depth_m=0.5, T_C=20.0):
    """Tip cavitation number sigma = (p_atm + rho g h - p_v) / (0.5 rho W^2); NACA 44xx -Cp,min ~ 1.0-1.5 near design CL, so
    sigma < ~1.2 means tip cavitation is likely (review M8). ASSUMPTION: 0.5 m axis depth, 20 C water (p_v 2.3 kPa)."""
    om = rpm * 2 * math.pi / 60; W2 = V * V + (om * R) ** 2
    return (101.3e3 + RHO * 9.81 * depth_m - 2.3e3) / (0.5 * RHO * W2)

if __name__ == "__main__":
    out = dict(assumptions=ASSUMPTIONS, cases={}, aero_hub_radius_mm=R_AERO_HUB)
    print(f"Rotor: r_hub {bp['r_hub']} mm, hub ratio {bp['r_hub']/101.6:.3f}, max chord {max(blade['chord']):.1f} mm, root chord {blade['chord'][0]:.1f} mm; GL60 Kt {60/(2*math.pi*G['KV']):.3f} N m/A")
    for V in (1.0, 1.2, 1.5, 2.0, 2.2, 3.0):
        curve = rotor_curve(V)
        pk = max(curve, key=lambda c: c[1])
        Pw = 0.5 * RHO * A * V ** 3
        st = startup(V, curve)
        res = {m: operating_point(V, curve, m) for m in ("open", "mppt", "dump", "brake")}
        # sensitivity: KV 25 (gate-1 upper bound) and no V_bat+1 floor (ideal boost)
        G["KV"] = 25.0; mp_kv = operating_point(V, curve, "mppt"); reset_G()
        G["battery_V"] = -10.0; mp_nofloor = operating_point(V, curve, "mppt"); reset_G()
        G["seal_running_Nm"] = G["seal_alt_running_Nm"]; mp_nbr = operating_point(V, curve, "mppt"); reset_G()
        row = dict(V=V, P_water=Pw, cp_peak=pk[1], P_shaft_peak=pk[2], tsr_peak=pk[0], startup=st, modes=res, dump_study=dump_study(V, curve),
                   Pdc_KV25=(mp_kv["Pdc"] if mp_kv else 0.0), Pdc_nofloor=(mp_nofloor["Pdc"] if mp_nofloor else 0.0), Pdc_NBRseal=(mp_nbr["Pdc"] if mp_nbr else 0.0),
                   sigma_tip_runaway=cavitation_sigma(res["open"]["rpm"], V), sigma_tip_charging=(cavitation_sigma(res["mppt"]["rpm"], V) if res["mppt"] else None),
                   sigma_tip_dump=cavitation_sigma(res["dump"]["rpm"], V), windage_Nm_at_charging=(drum_windage(res["mppt"]["rpm"], V) if res["mppt"] else None),
                   T_max=max(c[4] for c in curve), Q_max=max(c[3] for c in curve), curve=[dict(tsr=c[0], cp=c[1], P=c[2], Q=c[3], T=c[4]) for c in curve])
        mp = res["mppt"]
        if mp:
            Pb = max(mp["Pdc"] * G["charger_eff"] - G["charger_quiescent_W"], 0)
            row.update(P_dc=mp["Pdc"], P_batt=Pb, eta_water_dc=mp["Pdc"] / Pw, eta_shaft_dc=mp["Pdc"] / mp["Pm"], note="")
            print(f"V={V:.1f}: water {Pw:6.1f} W | rotor peak Cp {pk[1]:.3f} ({pk[2]:.1f} W @ TSR {pk[0]:.2f}) | charging point: TSR {mp['lam']:.2f} {mp['rpm']:.0f} rpm shaft {mp['Pm']:.1f} W, I {mp['I']:.2f} A, Vdc {mp['Vdc']:.1f} V, Cu {mp['Pcu']:.1f} W -> DC {mp['Pdc']:.1f} W, battery {Pb:.1f} W | water->DC {mp['Pdc']/Pw*100:.0f} %, shaft->DC {mp['Pdc']/mp['Pm']*100:.0f} %")
        else:
            row.update(P_dc=0.0, P_batt=0.0, note="no charging point satisfies V_dc >= V_bat+1 V with the buck charger")
            print(f"V={V:.1f}: water {Pw:6.1f} W | rotor peak Cp {pk[1]:.3f} ({pk[2]:.1f} W) | NO CHARGING POINT (buck charger needs V_dc >= {G['battery_V']+1:.1f} V)")
        o = res["open"]; d = res["dump"]; b = res["brake"]
        print(f"        start: static {st['static_Q']:.3f} vs breakaway PTFE {st['breakaway']:.3f} (x{st['ratio']:.2f}) / NBR {st['breakaway_nbr']:.3f} (x{st['ratio_nbr']:.2f}) N m; runaway {o['rpm']:.0f} rpm -> {o['Vdc']:.0f} V; "
              f"dump {G['dump_R']:.0f} ohm: {d['rpm']:.0f} rpm, {d['Vdc']:.1f} V, {d['Pdc']:.1f} W resistor, Cu {d['Pcu']:.1f} W; brake: {b['rpm']:.0f} rpm, winding {b['Pcu']:.1f} W; KV25 -> {row['Pdc_KV25']:.1f} W; NBR seal -> {row['Pdc_NBRseal']:.1f} W; no floor -> {row['Pdc_nofloor']:.1f} W DC; "
              f"sigma_tip runaway {row['sigma_tip_runaway']:.2f} / dump {row['sigma_tip_dump']:.2f}")
        print("        dump study: " + "; ".join(f"{k} ohm: {v['rpm']:.0f} rpm {v['Vdc']:.0f} V {v['Pres']:.0f} W sig {v['sigma_tip']:.2f}" for k, v in row['dump_study'].items()))
        out["cases"][str(V)] = row
    json.dump(out, open(os.path.join(HERE, "system_results_v3.json"), "w"), indent=1, default=float)
