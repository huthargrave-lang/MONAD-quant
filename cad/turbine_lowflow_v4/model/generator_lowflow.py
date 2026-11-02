#!/usr/bin/env python3
"""GL60 KV25 generator + drivetrain friction + rectifier + DC-DC converter model and the coupled equilibrium solver.

Conventions (stated, not verified on the delivered motor; gate G1 measures them):
  V_oc = rpm / KV  (KV 21.5 rpm/V: DC-link no-load voltage per rpm, from the listed 516 rpm at 24 V);  Kt = 60/(2 pi KV) = 0.444 N m per
  DC ampere (energy-consistent; the listed 0.45 and 0.40 bracket it); copper loss I^2 R with R = 5.5 ohm (the listed Km 0.1919 = 0.45/sqrt(5.5)
  reproduces the manufacturer's motor constant); commutation overlap (3/pi) w_e (L/2) I with L 2.72 mH and 14 pole pairs reduces the DC
  voltage (reactive, not a loss).  Rated 1.35 A continuous (0.6 N m); peak 4 A is NOT used as a generating capability.
Friction (assumptions, sensitivities in the report): PTFE lip seal on an 8 mm shaft 4 mN m running / 8 breakaway (15 mm: 7.5 / 15);
external 608-2RS bearing 3 mN m incl. its rubber seals; motor no-load (iron + own bearings) 0.5 W at 700 rpm scaling rpm^1.5;
cogging torque peak 24 mN m (breakaway only; it dissipates nothing on average).  Rectifier: Schottky bridge 2 x Vf(I).  Converter:
generic efficiency curve eta = eta_max - k/P_in with a quiescent draw; three topologies: boost MPPT with a battery-voltage clamp
(Genasun GVB-8-Li class), buck-boost MPPT (LT8390 class), and the direct rectifier-to-battery case."""
import json, math, os
import numpy as np
R_TIP = 0.1016
GEN = dict(KV=21.5, R_LL=5.5, L_LL=2.72e-3, pp=14, rated_I=1.35, rated_T=0.60, p0_700=0.5, p0_exp=1.5, cogging=0.024)
FRICTION = {
    "A_rear_nacelle": dict(seal_run=0.004, seal_break=0.008, brg_run=0.003, brg_break=0.004, note="8 mm PTFE lip seal + 608-2RS in the nacelle cap; motor's own bearings inside p0"),
    "B_hub_drum":     dict(seal_run=0.0075, seal_break=0.015, brg_run=0.008, brg_break=0.010, note="15 mm PTFE lip seal + 2 x 6702-2RS (v3.1 drum)"),
}
CONVERTERS = {
    "boost_clamp": dict(V_min=5.0, V_max=14.4, clamp=True, eta_max=0.92, k=0.06, P_q=0.02, note="boost MPPT into a 12.8 V LiFePO4 (Genasun GVB-8-Li-14.2V class, 5 V minimum input); above the battery voltage the boost cannot regulate and the bus clamps at V_bat + drops"),
    "buckboost":   dict(V_min=5.0, V_max=60.0, clamp=False, eta_max=0.94, k=0.08, P_q=0.05, note="4-60 V buck-boost with input-voltage (MPPT) regulation (LT8390/LT8705 class module); regulates over the whole 0.4-2 m/s range"),
    "direct":      dict(V_min=0.0, V_max=1e9, clamp=True, eta_max=1.0, k=0.0, P_q=0.0, fixed_V=14.4, note="rectifier straight into the 12.8 V LiFePO4 (14.4 V bus): no converter, no MPPT"),
    "ideal":       dict(V_min=0.0, V_max=1e9, clamp=False, eta_max=1.0, k=0.0, P_q=0.0, note="lossless converter with unlimited voltage range: upper bound only"),
}
RECTIFIER = {"schottky": dict(Vf0=0.30, Vf_slope=0.20, note="MBR10100-class Schottky bridge, Vf = 0.30 + 0.20 I (V), two diodes conduct"),
             "synchronous": dict(Vf0=0.03, Vf_slope=0.03, note="ideal-diode MOSFET bridge (LT4320 class), ~30 mV drop")}

def Kt(g=GEN): return 60 / (2 * math.pi * g["KV"])

def friction_running(rpm, fr, g=GEN, r_hub_m=0.028, V=0.7, N=1.0):
    """running friction torque (N m, referred to the rotor shaft) at rotor rpm: seal + external bearings + motor no-load loss (evaluated at
    the generator speed N*rpm) + rotating-hub windage"""
    om = rpm * 2 * math.pi / 60
    p0 = g["p0_700"] * (max(rpm * N, 1) / 700.0) ** g["p0_exp"]; t_fe = p0 / om if om > 1e-6 else 0.0
    # windage of the rotating hub (cylinder r_hub, length 0.04 m) in the stream: small but included
    Ut = om * r_hub_m; Urel = math.sqrt(Ut * Ut + V * V); Re = max(Urel * 0.04 / 1.14e-6, 1e4); Cf = 0.074 * Re ** -0.2
    t_w = 0.5 * 1000 * Cf * Urel * Urel * (2 * math.pi * r_hub_m * 0.04) * r_hub_m * (Ut / Urel if Urel > 0 else 0)
    return fr["seal_run"] + fr["brg_run"] + t_fe + t_w

def breakaway(fr, g=GEN): return fr["seal_break"] + fr["brg_break"] + g["cogging"]

def rectifier_drop(I, rect): return 2 * (rect["Vf0"] + rect["Vf_slope"] * I)

def gen_point(rpm, T_gen, g=GEN, rect=RECTIFIER["schottky"], N=1.0):
    """Generator electrical quantities for shaft speed rpm (rotor side) and generator torque T_gen referred to the ROTOR shaft.
    A gear ratio N > 1 multiplies the generator speed and divides its torque."""
    rpm_g = rpm * N; om_g = rpm_g * 2 * math.pi / 60; Tg = T_gen / N
    kt = Kt(g); Voc = rpm_g / g["KV"]; w_e = om_g * g["pp"]
    a = (3 / math.pi) * w_e * (g["L_LL"] / 2)
    # torque from power balance with the overlap-reduced torque constant: Tg * om = (Voc - a I) I  -> quadratic in I
    disc = Voc * Voc - 4 * a * Tg * om_g
    if Voc <= 0 or disc < 0:
        return None                                                            # torque beyond the pull-out limit at this speed: no physical point (review m2)
    I = (Voc - math.sqrt(disc)) / (2 * a) if a > 1e-9 else Tg * om_g / Voc
    dVc = a * I; Vd = rectifier_drop(I, rect)
    Vdc = Voc - I * g["R_LL"] - dVc - Vd
    Pcu = I * I * g["R_LL"]; Pd = Vd * I; Pdc = max(Vdc, 0) * I
    return dict(I=I, Voc=Voc, Vdc=Vdc, Pcu=Pcu, Pdiode=Pd, Pdc=Pdc, dV_comm=dVc, rpm_gen=rpm_g, T_gen=Tg)

def converter_out(Pdc, Vdc, conv):
    if Pdc <= 0: return -conv["P_q"]
    eta = max(conv["eta_max"] - conv["k"] / Pdc, 0.3)
    return eta * Pdc - conv["P_q"]

def rotor_curve_fn(curve):
    """curve: list of (lam, Q, P) -> interpolators on a fine lambda grid"""
    lams = np.array([c[0] for c in curve]); Q = np.array([c[1] for c in curve])
    return lams, Q

def _cv_solve(V, lams, Qrot, fr, V_fixed, rect, g, N, r_hub_m):
    """equilibrium at a fixed DC bus voltage: bisection in lambda on Vdc(lambda) - V_fixed along the stable branch (review m3)"""
    fine = np.linspace(lams.min(), lams.max(), 300); Qf = np.interp(fine, lams, Qrot)
    def state(lam):
        om = lam * V / R_TIP; rpm = om * 60 / (2 * math.pi); Q = float(np.interp(lam, lams, Qrot)); Tf = friction_running(rpm, fr, g, r_hub_m, V, N); Qg = Q - Tf
        if Qg <= 0: return None
        gp = gen_point(rpm, Qg, g, rect, N)
        if gp is None: return None
        return dict(lam=lam, rpm=rpm, Qrot=Q, Qg=Qg, gp=gp, Tf=Tf, om=om)
    vals = []
    for lam in fine:
        st = state(lam); vals.append((st["gp"]["Vdc"] - V_fixed) if st else np.nan)
    vals = np.array(vals)
    idx = [i for i in range(len(fine) - 1) if np.isfinite(vals[i]) and np.isfinite(vals[i + 1]) and vals[i] < 0 <= vals[i + 1]]
    if not idx: return None
    i = idx[-1]                                                                 # highest-lambda crossing = the stable branch (Vdc rises with speed)
    lo, hi = fine[i], fine[i + 1]
    for _ in range(40):
        mid = 0.5 * (lo + hi); st = state(mid)
        if st is None or st["gp"]["Vdc"] - V_fixed < 0: lo = mid
        else: hi = mid
    st = state(0.5 * (lo + hi))
    if st is None: return None
    gp = st["gp"]
    return dict(lam=st["lam"], rpm=st["rpm"], Qrot=st["Qrot"], Qg=st["Qg"], I=gp["I"], Vdc=gp["Vdc"], Voc=gp["Voc"], Pdc=gp["Pdc"], Pcu=gp["Pcu"], Pdiode=gp["Pdiode"], Pout=gp["Pdc"],
                Pshaft=st["Qrot"] * st["om"], Pfric=st["Tf"] * st["om"], Pgen_mech=st["Qg"] * st["om"], dV_comm=gp["dV_comm"], region="cv", overcurrent=bool(gp["I"] > g["rated_I"]))

def operating_point(V, lams, Qrot, fr, conv, rect=RECTIFIER["schottky"], g=GEN, N=1.0, r_hub_m=0.028, mode="mppt", R_load=None):
    """Equilibrium of rotor torque Qrot(lam) against friction + generator torque under the converter's load law.
    mode 'mppt': pick lambda maximising converter output within the converter's voltage window (clamped CV above V_max if clamp);
    mode 'cv': fixed bus voltage conv['fixed_V'] (rectifier into the battery); mode 'resistor': DC load R_load; mode 'open': no load.
    Returns the best point dict or None if no feasible point gives positive output."""
    fine = np.linspace(lams.min(), lams.max(), 300)
    Qf = np.interp(fine, lams, Qrot)
    best = None
    for lam, Q in zip(fine, Qf):
        om = lam * V / R_TIP; rpm = om * 60 / (2 * math.pi)
        Tf = friction_running(rpm, fr, g, r_hub_m, V, N)
        Qg = Q - Tf
        if mode == "open":
            cand = dict(lam=lam, rpm=rpm, Qrot=Q, Qg=0.0, I=0.0, Vdc=rpm * N / g["KV"], Pdc=0.0, Pout=0.0, Pfric=Tf * om)
            score = -abs(Qg)
            if best is None or score > best[0]: best = (score, cand)
            continue
        if Qg <= 0: continue
        if mode == "cv": continue                                           # handled by _cv_solve below
        gp = gen_point(rpm, Qg, g, rect, N)
        if gp is None or gp["Vdc"] <= 0: continue
        if gp["I"] > g["rated_I"] * 1.05 and mode == "mppt": continue       # an MPPT controller never commands more than the rating; CV modes report the overcurrent
        if mode == "mppt":
            if gp["Vdc"] < conv["V_min"]: continue
            if gp["Vdc"] > conv["V_max"]:
                if not conv["clamp"]: continue
                continue                                    # clamped region handled below as a CV solution
            Pout = converter_out(gp["Pdc"], gp["Vdc"], conv); score = Pout
        elif mode == "resistor":
            I_r = gp["Vdc"] / R_load; score = -abs(I_r - gp["I"]); Pout = gp["Pdc"]
            if abs(I_r - gp["I"]) > 0.05 * max(gp["I"], 0.02): continue
        cand = dict(lam=lam, rpm=rpm, Qrot=Q, Qg=Qg, I=gp["I"], Vdc=gp["Vdc"], Voc=gp["Voc"], Pdc=gp["Pdc"], Pcu=gp["Pcu"], Pdiode=gp["Pdiode"], Pout=Pout,
                    Pshaft=Q * om, Pfric=Tf * om, Pgen_mech=Qg * om, dV_comm=gp["dV_comm"], region="mppt" if mode == "mppt" else mode, overcurrent=bool(gp["I"] > g["rated_I"]))
        if best is None or score > best[0]: best = (score, cand)
    if mode == "cv":
        pc = _cv_solve(V, lams, Qrot, fr, conv["fixed_V"], rect, g, N, r_hub_m)
        return pc
    if mode == "mppt" and conv["clamp"]:
        # clamped CV branch at V_max (the boost cannot regulate above the battery): it competes with the MPPT branch
        pc = _cv_solve(V, lams, Qrot, fr, conv["V_max"], rect, g, N, r_hub_m)
        if pc and pc["I"] <= g["rated_I"] * 1.05:
            pc["Pout"] = converter_out(pc["Pdc"], pc["Vdc"], conv); pc["region"] = "clamp"
            if best is None or (best[1]["Pout"] < pc["Pout"]): best = (pc["Pout"], pc)
        elif pc:
            pc["Pout"] = converter_out(pc["Pdc"], pc["Vdc"], conv); pc["region"] = "clamp"
            if best is None: best = (pc["Pout"], pc)                            # over-current clamp equilibrium reported with its flag when nothing else exists
    if best is None: return None
    b = best[1]
    if mode != "open" and b.get("Pout", 0) <= 0: return None
    return b

def startup_check(Qstatic, fr, g=GEN):
    tb = breakaway(fr, g); return dict(Qstatic=Qstatic, breakaway=tb, ratio=Qstatic / tb if tb > 0 else 99, ok=Qstatic > tb)

def sustain_margin(V, lams, Qrot, fr, g=GEN, r_hub_m=0.028, lam_max=None, N=1.0):
    """minimum (rotor torque - running friction) along the unloaded acceleration path 0.3 <= lam <= lam_max"""
    fine = np.linspace(max(lams.min(), 0.3), lam_max if lam_max else lams.max(), 200); Qf = np.interp(fine, lams, Qrot)
    m = [Q - friction_running(l * V / R_TIP * 60 / (2 * math.pi), fr, g, r_hub_m, V, N) for l, Q in zip(fine, Qf)]
    return float(min(m))
