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
R = mb.R / 1000; RHO = 1000.0; A = math.pi * R ** 2

ASSUMPTIONS = dict(
    generator="CubeMars GL60 KV25 (manufacturer values per the 31 Oct 2026 review citation; pages not reachable from this session)",
    KV=21.5, R_LL=5.5, L_LL=2.72e-3, pole_pairs=14, I_rated=1.35, I_peak=4.0, T_rated=0.6,
    Kt_note="Kt = 60/(2 pi 21.5) = 0.444 N m/A (energy-consistent); the page also quotes 0.45 (0.40 on one reseller)",
    Vf_diode=0.55, rectifier="6x MBR10100 (100 V Schottky), Vf ~0.55 V at 1-2 A (estimate)",
    seal_running_Nm=0.015, seal_breakaway_factor=2.0, bearing_running_Nm=0.004, bearings=2, cogging_Nm=0.024,
    friction_note="lip seal 15 mm: 4-24 mN m running (no measured value exists); 15 mN m used; cogging 24 mN m inferred for the GL60 (II lists 2.4 cN m)",
    charger="Victron SmartSolar MPPT 100/15 (buck): starts when V_pv >= V_bat + 5 V, runs while V_pv >= V_bat + 1 V; 100 V max input",
    battery_V=13.2, charger_eff=0.95, charger_quiescent_W=0.3,
    gen_current_limit=1.2, current_limit_note="generator-side limit set below the 1.35 A rating until the spindle heat path is measured",
    dump_R=15.0, dump_engage_V=45.0, dump_release_V=35.0, dump_resistor="Ohmite HS100 15R J on a heatsink (100 W rated on sink, ~30 W bare)",
    water_temp_note="BEM polars at 15 C",
)
G = ASSUMPTIONS

def rotor_curve(V, n=28):
    lams = np.linspace(0.8, 7.5, n)
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
    Vdc = Voc - I * G["R_LL"] - (3 / math.pi) * w_e * (G["L_LL"] / 2) * I - 2 * G["Vf_diode"]
    return dict(Kt=Kt, Voc=Voc, Vdc=max(Vdc, 0.0), Pcu=I * I * G["R_LL"], Pdiode=2 * G["Vf_diode"] * I, Tgen=Kt * I)

def friction_running():
    return G["seal_running_Nm"] + G["bearings"] * G["bearing_running_Nm"]

def operating_point(V, curve, mode):
    """Solve rotor torque = generator torque + friction along the rotor curve for a given load law.
    mode 'mppt': maximise DC power subject to the current limit and the charger's V_dc >= V_bat + 1 rule.
    mode 'dump': load = fixed resistor R_dump on the DC bus.  mode 'brake': 3-phase short.  mode 'open': no load."""
    best = None
    Tf = friction_running()
    for lam, cp, P, Q, T in curve:
        om = lam * V / R; rpm = om * 60 / (2 * math.pi)
        Qg = Q - Tf
        if Qg <= 0:
            continue
        gp0 = gen_point(rpm, 0.0)
        if mode == "open":
            cand = dict(lam=lam, rpm=rpm, I=0.0, Vdc=gp0["Voc"], Pdc=0.0, Pm=P, Q=Q, Qg=0.0, cp=cp, T=T)
            # open circuit: equilibrium where Qg == 0 i.e. Q == Tf -> pick the point with the smallest |Qg|
            score = -abs(Qg)
        elif mode == "mppt":
            I = Qg / gp0["Kt"]
            if I > G["gen_current_limit"]:
                continue                                     # the charger holds the current at the limit: this lambda is not an equilibrium
            gp = gen_point(rpm, I)
            if gp["Vdc"] < G["battery_V"] + 1.0:
                continue                                     # buck charger cannot run below V_bat + 1 V
            Pdc = gp["Vdc"] * I
            cand = dict(lam=lam, rpm=rpm, I=I, Vdc=gp["Vdc"], Pdc=Pdc, Pm=P, Q=Q, Qg=Qg, cp=cp, T=T, Pcu=gp["Pcu"], Pdiode=gp["Pdiode"])
            score = Pdc
        elif mode == "dump":
            # resistor: I = Vdc / R_dump with Vdc from gen_point -> solve for I at this rpm, then check torque balance
            Kt = gp0["Kt"]; w_e = rpm / 60 * 2 * math.pi * G["pole_pairs"]
            Rtot = G["R_LL"] + (3 / math.pi) * w_e * (G["L_LL"] / 2) + G["dump_R"]
            I = max(gp0["Voc"] - 2 * G["Vf_diode"], 0) / Rtot
            score = -abs(Kt * I - Qg)
            cand = dict(lam=lam, rpm=rpm, I=I, Vdc=I * G["dump_R"], Pdc=I * I * G["dump_R"], Pm=P, Q=Q, Qg=Kt * I, cp=cp, T=T, Pcu=I * I * G["R_LL"], mismatch=Kt * I - Qg)
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
    # unloaded acceleration: rotor torque minus running friction must stay positive from TSR 0.1 up to the no-load point
    margin_run = min(c[3] - friction_running() for c in curve if c[0] <= 3.0)
    return dict(static_Q=Qs, breakaway=Tb, start_ok=Qs > Tb, ratio=Qs / Tb, min_running_margin_Nm=margin_run)

if __name__ == "__main__":
    out = dict(assumptions=ASSUMPTIONS, cases={})
    print(f"Rotor: r_hub {bp['r_hub']} mm, hub ratio {bp['r_hub']/101.6:.3f}, max chord {max(blade['chord']):.1f} mm, root chord {blade['chord'][0]:.1f} mm; GL60 Kt {60/(2*math.pi*G['KV']):.3f} N m/A")
    for V in (1.0, 1.2, 1.5, 2.0, 2.2, 3.0):
        curve = rotor_curve(V)
        pk = max(curve, key=lambda c: c[1])
        Pw = 0.5 * RHO * A * V ** 3
        st = startup(V, curve)
        res = {m: operating_point(V, curve, m) for m in ("open", "mppt", "dump", "brake")}
        row = dict(V=V, P_water=Pw, cp_peak=pk[1], P_shaft_peak=pk[2], tsr_peak=pk[0], startup=st, modes=res,
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
        print(f"        start: static {st['static_Q']:.3f} vs breakaway {st['breakaway']:.3f} N m -> {'OK' if st['start_ok'] else 'NO'} (ratio {st['ratio']:.2f}); runaway {o['rpm']:.0f} rpm -> {o['Vdc']:.0f} V open-circuit DC; "
              f"dump 15 ohm: {d['rpm']:.0f} rpm, {d['Vdc']:.1f} V, {d['Pdc']:.1f} W in the resistor, Cu {d['Pcu']:.1f} W; brake (3-ph short): {b['rpm']:.0f} rpm, winding {b['Pcu']:.1f} W")
        out["cases"][str(V)] = row
    json.dump(out, open(os.path.join(HERE, "system_results_v3.json"), "w"), indent=1, default=float)
