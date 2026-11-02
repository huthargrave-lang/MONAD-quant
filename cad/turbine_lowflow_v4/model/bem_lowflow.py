#!/usr/bin/env python3
"""Blade-element momentum model for the low-flow study (vectorized; Ning-2014 residual with bisection per element).
Corrections: Prandtl tip and hub losses (AeroDyn hub form), Buhl high-induction correction, Reynolds-dependent polars per
element (tables from polars.py), Viterna post-stall extension, optional nacelle inflow deficit for a body behind the rotor.
Standstill (starting) torque: alpha = 90 deg - twist on every element with W = V (no induction), post-stall polars.
Units: SI inside (m, m/s, N, N m, W); the blade dict carries r, chord, twist(deg) in mm/deg for the CAD scripts."""
import json, math, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
RHO, NU = 1000.0, 1.14e-6          # fresh water ~15 C
R_TIP = 0.1016                      # m (203.2 mm rotor)
EXT_AL = np.arange(-90.0, 90.01, 1.0)

def _viterna_row(al, cl, cd, al_s, al_sn=-8.0, cdmax=1.8):   # cdmax = post-stall flat-plate drag coefficient (1.2-2.0 in the literature; sensitivity in the report)
    from polars import viterna_extend
    f = viterna_extend(al, cl, cd, al_s, al_sn, cdmax)
    vals = np.array([f(a) for a in EXT_AL]); return vals[:, 0], vals[:, 1]

class PolarTable:
    """Extended (alpha -90..90 deg) x Re table with vectorized bilinear lookup; cd multiplier / cl factor for sensitivities."""
    def __init__(self, tab, cd_mult=1.0, cl_fac=1.0, cd_add=0.0, cdmax=1.8, re_shift=1.0):
        self.re_shift = re_shift                       # multiplies the lookup Reynolds number: Re/1.5 mimics an earlier-separating (wet, printed) section (review M1)
        al = np.array(tab["alphas"]); self.logRe = np.log(np.array(tab["Res"]))
        self.cl = np.zeros((len(self.logRe), len(EXT_AL))); self.cd = np.zeros_like(self.cl)
        for i in range(len(self.logRe)):
            c, d = _viterna_row(al, np.array(tab["cl"][i]) * cl_fac, np.array(tab["cd"][i]) * cd_mult + cd_add, tab["alpha_stall"][i], cdmax=cdmax)
            self.cl[i], self.cd[i] = c, d
        self.tc = tab["tc"]; self.alpha_best = np.array(tab["alpha_best"]); self.cl_best = np.array(tab["cl_best"]) * cl_fac
    def __call__(self, alpha_rad, Re):
        a = np.clip(np.degrees(alpha_rad), -90, 90); lr = np.clip(np.log(np.maximum(Re * self.re_shift, 1.0)), self.logRe[0], self.logRe[-1])
        j = np.clip(np.searchsorted(self.logRe, lr, side="right") - 1, 0, len(self.logRe) - 2)
        w = (lr - self.logRe[j]) / (self.logRe[j + 1] - self.logRe[j])
        ia = np.clip(np.searchsorted(EXT_AL, a, side="right") - 1, 0, len(EXT_AL) - 2); wa = (a - EXT_AL[ia]) / 1.0
        def pick(T):
            v0 = T[j, ia] * (1 - wa) + T[j, ia + 1] * wa; v1 = T[j + 1, ia] * (1 - wa) + T[j + 1, ia + 1] * wa
            return (1 - w) * v0 + w * v1
        return pick(self.cl), pick(self.cd)
    def design_point(self, Re):
        lr = np.clip(math.log(Re), self.logRe[0], self.logRe[-1]); return float(np.interp(lr, self.logRe, self.alpha_best)), float(np.interp(lr, self.logRe, self.cl_best))

class Blade:
    """Element-wise description: r (m, element centres), dr, c (m), beta (rad, from the rotor plane), root blend weight w_root,
    polars (outer, root), B blades, r_hub (m), optional nacelle factor per element (axial inflow multiplier)."""
    def __init__(self, r, dr, c, beta, w_root, outer, root, B, r_hub, vfac=None, meta=None, hi_a="buhl"):
        self.r, self.dr, self.c, self.beta, self.w_root = map(np.asarray, (r, dr, c, beta, w_root))
        self.outer, self.root, self.B, self.r_hub = outer, root, B, r_hub
        self.vfac = np.ones_like(self.r) if vfac is None else np.asarray(vfac); self.meta = meta or {}
        self.hi_a = hi_a                               # high-induction model: 'buhl' (baseline), 'spera' (Glauert-Spera a_c 0.2), 'momentum' (uncorrected, a <= 0.95)
    def polar(self, alpha, Re):
        clo, cdo = self.outer(alpha, Re); clr, cdr = self.root(alpha, Re)
        return (1 - self.w_root) * clo + self.w_root * clr, (1 - self.w_root) * cdo + self.w_root * cdr

def elements(r_hub, n=50):
    re_ = np.linspace(r_hub, R_TIP, n + 1); rm = 0.5 * (re_[1:] + re_[:-1]); return rm, re_[1:] - re_[:-1]

def bem(blade, lam, V, n_iter=50):
    """Returns dict(cp, cq, ct, P, Q, T, rpm, a, ap, alpha, Re, phi) at tip-speed ratio lam and water speed V (m/s)."""
    r, dr, c, beta, B = blade.r, blade.dr, blade.c, blade.beta, blade.B
    om = lam * V / R_TIP
    Vloc = V * blade.vfac
    sigma = B * c / (2 * np.pi * r)
    lam_r = om * r / Vloc
    Rh = blade.r_hub
    def induction(phi):
        sphi, cphi = np.sin(phi), np.cos(phi)
        alpha = phi - beta
        W_est = np.sqrt((0.7 * Vloc) ** 2 + (om * r) ** 2); Re = c * W_est / NU
        cl, cd = blade.polar(alpha, Re)
        cn = cl * cphi + cd * sphi; ct = cl * sphi - cd * cphi
        sp = np.maximum(np.abs(sphi), 1e-6)
        ftip = 2 / np.pi * np.arccos(np.clip(np.exp(-B * (R_TIP - r) / (2 * r * sp)), 0, 1))
        fhub = 2 / np.pi * np.arccos(np.clip(np.exp(-B * (r - Rh) / (2 * Rh * sp)), 0, 1))
        F = np.maximum(ftip * fhub, 1e-3)
        kappa = 4 * F * sphi ** 2 / np.maximum(sigma * cn, 1e-9)
        a = np.where(cn > 0, 1 / (kappa + 1), 0.0)
        if blade.hi_a == "buhl":
            # Buhl correction for a > 0.4
            K = sigma * cn / np.maximum(sphi ** 2, 1e-9)
            A = K - 50 / 9 + 4 * F; Bq = -2 * K - 4 * F + 40 / 9; C = K - 8 / 9
            disc = Bq * Bq - 4 * A * C
            with np.errstate(divide="ignore", invalid="ignore"):
                root1 = (-Bq + np.sqrt(np.maximum(disc, 0))) / (2 * A); root2 = (-Bq - np.sqrt(np.maximum(disc, 0))) / (2 * A)
            cand = np.where((root1 >= 0.4) & (root1 < 1.0), root1, np.where((root2 >= 0.4) & (root2 < 1.0), root2, 0.4))
            a = np.where((a > 0.4) & (disc >= 0), cand, a)
        elif blade.hi_a == "spera":
            # Glauert-Spera: for a > a_c the thrust is linear in a: CT = 4 a_c^2 + 4 (1 - 2 a_c) a; with CT = sigma cn (1-a)^2 / sin^2 phi (F folded in)
            ac = 0.2; Kk = np.maximum(sigma * cn, 1e-9) / (4 * F * np.maximum(sphi ** 2, 1e-9))     # = a/(1-a)^2 relation constant
            # momentum side CT = 4F[ac^2 + (1-2ac) a], blade side CT = 4F K (1-a)^2 with K = sigma cn / (4 F sin^2 phi):
            # K (1-a)^2 = ac^2 + (1-2ac) a  ->  K a^2 - (2K + 1 - 2ac) a + (K - ac^2) = 0 (take the smaller root)
            Aq = Kk; Bq = -(2 * Kk + (1 - 2 * ac)); Cq = Kk - ac * ac
            with np.errstate(invalid="ignore", divide="ignore"):
                a_sp = (-Bq - np.sqrt(np.maximum(Bq * Bq - 4 * Aq * Cq, 0))) / (2 * Aq)
            a = np.where(a > ac, np.clip(a_sp, ac, 0.95), a)
        else:
            a = np.clip(a, 0, 0.95)
        kp = 4 * F * sphi * cphi / np.where(np.abs(ct) > 1e-9, sigma * ct, 1e-9)
        ap = np.where(np.abs(ct) > 1e-9, 1 / np.where(np.abs(kp - 1) > 1e-9, kp - 1, 1e-9), 0.0)
        ap = np.clip(ap, -0.4, 0.9)
        return a, ap, cn, ct, F, cl, cd, Re
    def resid(phi):
        a, ap, *_ = induction(phi)
        return np.sin(phi) / (1 - a + 1e-9) - np.cos(phi) / (lam_r * (1 + ap) + 1e-9)
    # bracket on a coarse grid, then bisection (vectorized); elements with no sign change are skipped (deep stall / no solution)
    grid = np.linspace(1e-3, np.pi / 2, 50)
    vals = np.array([resid(np.full_like(r, p)) for p in grid])          # (50, n)
    sgn = np.sign(vals); change = (sgn[:-1] <= 0) & (sgn[1:] >= 0)
    has = change.any(axis=0); first = np.argmax(change, axis=0)
    lo = grid[first]; hi = grid[np.minimum(first + 1, len(grid) - 1)]
    for _ in range(n_iter):
        m = 0.5 * (lo + hi); rv = resid(m); lo = np.where(rv < 0, m, lo); hi = np.where(rv < 0, hi, m)
    phi = 0.5 * (lo + hi)
    a, ap, cn, ct, F, cl, cd, Re = induction(phi)
    W = Vloc * (1 - a) / np.maximum(np.sin(phi), 1e-6)
    q = 0.5 * RHO * W * W * c
    dT = np.where(has, B * q * cn * dr, 0.0); dQ = np.where(has, B * q * ct * r * dr, 0.0)
    T, Q = dT.sum(), dQ.sum(); P = om * Q
    A = np.pi * R_TIP ** 2
    return dict(cp=P / (0.5 * RHO * A * V ** 3), cq=Q / (0.5 * RHO * A * R_TIP * V ** 2), ct=T / (0.5 * RHO * A * V ** 2), P=P, Q=Q, T=T,
                rpm=om * 60 / (2 * np.pi), lam=lam, a=a, ap=ap, alpha=np.degrees(phi - beta), Re=Re, phi=np.degrees(phi), solved=has, dQ=dQ)

def static_torque(blade, V):
    """Standstill torque: no induction, W = V, phi = 90 deg -> ct = cl(alpha = 90 - beta). Post-stall polars (Viterna)."""
    r, dr, c, beta, B = blade.r, blade.dr, blade.c, blade.beta, blade.B
    Vloc = V * blade.vfac
    alpha = np.pi / 2 - beta; Re = c * Vloc / NU
    cl, cd = blade.polar(alpha, Re)
    q = 0.5 * RHO * Vloc ** 2 * c
    return float((B * q * cl * r * dr).sum())

def static_torque_bem_low_lambda(blade, V, lam=0.1):
    """BASELINE starting-torque estimate (review C1): the BEM torque at a very low tip-speed ratio with momentum induction on, same polars.
    The no-induction, 2-D-flat-plate standstill value (static_torque) is ~1.6-1.8x this and is treated as an UPPER bound only: it ignores the
    inflow deceleration of a stalled, high-solidity disc and the finite span (AR ~1.4) of the blade."""
    return bem(blade, lam, V)["Q"]

def curve(blade, V, lams):
    return [bem(blade, l, V) for l in lams]

# --------------------------------------------------------------------------- blade design (parametric)
def schmitz_chord(r, lam, cl_d, B):
    lam_r = lam * r / R_TIP; phi = 2.0 / 3.0 * np.arctan(1.0 / lam_r)
    return 8 * np.pi * r * (1 - np.cos(phi)) / (B * cl_d), phi

def design(tabs, airfoil, B, lam_d, c_scale=1.0, dbeta=0.0, r_hub=0.028, c_max=0.060, tip_frac=0.55, root_blend=0.35, root_airfoil="naca4418",
           V_design=0.7, n=50, vfac=None, cd_mult=1.0, cl_fac=1.0, cd_add=0.0, c_min=0.012, cdmax=1.8, re_shift=1.0, hi_a="buhl"):
    """Schmitz-optimum planform at lam_d for the airfoil's best-L/D design point (Re evaluated at V_design with the resulting chord,
    one fixed-point pass), scaled by c_scale, capped at c_max, root chord eased (0.85 x at the hub), elliptical tip taper to tip_frac,
    twist = Schmitz inflow angle - design alpha + dbeta; the inner root_blend of the span blends toward the thick root section."""
    outer = PolarTable(tabs[airfoil], cd_mult, cl_fac, cd_add, cdmax, re_shift); root = PolarTable(tabs[root_airfoil], cd_mult, cl_fac, cd_add, cdmax, re_shift)
    r, dr = elements(r_hub, n)
    om = lam_d * V_design / R_TIP
    Re_guess = 0.04 * np.sqrt((0.7 * V_design) ** 2 + (om * r) ** 2) / NU
    a_d = np.array([outer.design_point(Re)[0] for Re in Re_guess]); cl_d = np.array([outer.design_point(Re)[1] for Re in Re_guess])
    c, phi = schmitz_chord(r, lam_d, cl_d, B)
    Re2 = c * np.sqrt((0.7 * V_design) ** 2 + (om * r) ** 2) / NU
    a_d = np.array([outer.design_point(Re)[0] for Re in Re2]); cl_d = np.array([outer.design_point(Re)[1] for Re in Re2])
    c, phi = schmitz_chord(r, lam_d, cl_d, B)
    c = c * c_scale
    # root easing: inboard of 0.3 R the Schmitz chord keeps growing; hold it to 0.85 x the chord at 0.3 R to keep the hub packable
    r30 = max(0.30 * R_TIP, r_hub + 0.01); c30 = np.interp(r30, r, c)
    c = np.where(r < r30, c30 * (0.85 + 0.15 * (r - r_hub) / (r30 - r_hub)), c)
    c = np.minimum(c, c_max)
    s = np.clip((r - 0.90 * R_TIP) / (0.10 * R_TIP), 0, 1); c = c * np.sqrt(1 - (1 - tip_frac ** 2) * s ** 2)
    c = np.maximum(c, c_min)
    beta = phi - np.radians(a_d) + math.radians(dbeta)
    w_root = np.clip(1 - (r - r_hub) / (root_blend * (R_TIP - r_hub)), 0, 1) ** 2
    tc_root = tabs[root_airfoil]["tc"]
    pocket_arc = (c[0] * math.cos(beta[0]) + tc_root * c[0] * math.sin(beta[0])) / r_hub          # tangential extent of the root section / hub radius (rad)
    blade = Blade(r, dr, c, beta, w_root, outer, root, B, r_hub, vfac,
                  meta=dict(airfoil=airfoil, B=B, lam_d=lam_d, c_scale=c_scale, dbeta=dbeta, r_hub=r_hub, c_max=c_max, tip_frac=tip_frac, root_airfoil=root_airfoil,
                            solidity=float((B * c * dr).sum() / (np.pi * (R_TIP ** 2 - r_hub ** 2))), c_root=float(c[0]), c_maxval=float(c.max()), alpha_d=a_d.tolist(), cl_d=cl_d.tolist(),
                            pocket_arc_deg=float(math.degrees(pocket_arc)), hub_wall_deg=float(360 / B - math.degrees(pocket_arc))), hi_a=hi_a)
    return blade

def blade_from_arrays(tabs, airfoil, B, r_mm, chord_mm, twist_deg, r_hub, root_airfoil="naca4418", root_blend=0.35, n=50, vfac=None, cd_mult=1.0, cl_fac=1.0, cd_add=0.0, cdmax=1.8, re_shift=1.0, hi_a="buhl"):
    """Blade from explicit station arrays (e.g. the previous designs) evaluated with the same polars and corrections."""
    outer = PolarTable(tabs[airfoil], cd_mult, cl_fac, cd_add, cdmax, re_shift); root = PolarTable(tabs[root_airfoil], cd_mult, cl_fac, cd_add, cdmax, re_shift)
    r, dr = elements(r_hub, n)
    c = np.interp(r * 1000, r_mm, chord_mm) / 1000; beta = np.radians(np.interp(r * 1000, r_mm, twist_deg))
    w_root = np.clip(1 - (r - r_hub) / (root_blend * (R_TIP - r_hub)), 0, 1) ** 2
    return Blade(r, dr, c, beta, w_root, outer, root, B, r_hub, vfac, meta=dict(airfoil=airfoil, B=B, r_hub=r_hub, from_arrays=True,
                 solidity=float((B * c * dr).sum() / (np.pi * (R_TIP ** 2 - r_hub ** 2)))), hi_a=hi_a)

if __name__ == "__main__":
    import sys, time
    sys.path.insert(0, os.path.join(HERE, "..", "..", "water_turbine_blade")); import make_blade as mb
    tabs = json.load(open(os.path.join(HERE, "polars_cache.json")))
    # cross-check 1: the v3.1 blade (make_blade design at R_HUB 42, lam 4, dbeta 6, C_MAX 60) with the old analytic polar vs the new BEM + NeuralFoil NACA polars
    mb.R_HUB = 42.0; mb.R_ROOT_EXT = 39.0; mb.C_MAX = 60.0; mb.PEAK_R = 0.58; mb.TC_ROOT = 0.24; mb.TC_TIP = 0.15; mb.TE_THICK = 1.0; mb.TIP_CHORD_FRAC = 0.55
    bl = mb.design_blade(4.0, 6.0)
    for V in (0.6, 1.0, 1.5):
        old = max((mb.bem(bl, l, V)["cp"], l) for l in np.arange(2, 6.01, 0.5))
        nb = blade_from_arrays(tabs, "naca4412", 3, bl["r"], bl["chord"], bl["twist"], 0.0482)
        t0 = time.time(); new = max((bem(nb, l, V)["cp"], l) for l in np.arange(2, 6.01, 0.5)); dt = time.time() - t0
        print(f"v3.1 blade at {V} m/s (hub 48.2): old model Cp {old[0]:.3f} @TSR {old[1]} | new model (NeuralFoil NACA4412 + 4418 root) Cp {new[0]:.3f} @TSR {new[1]}  [{dt*1000/9:.0f} ms per BEM]")
    # cross-check 2: Betz sanity with an inviscid-like polar (cd x 0.01) and many blades -> Cp must stay below 0.593
    nb = design(tabs, "sg6043", 3, 5.0, r_hub=0.028, cd_mult=0.01)
    print("near-inviscid Cp (must be < 0.593):", round(max(bem(nb, l, 1.0)["cp"] for l in np.arange(3, 9, 0.5)), 3))
    # cross-check 3: energy consistency: P = om*Q from the element sums
    res = bem(nb, 5.0, 1.0); print("P - om Q:", round(res["P"] - res["lam"] * 1.0 / R_TIP * res["Q"], 9))
    # static torque sample
    nb2 = design(tabs, "sg6043", 3, 3.0, r_hub=0.028)
    print(f"design TSR 3, 3 blades sg6043, hub 28: solidity {nb2.meta['solidity']:.3f}, c_root {nb2.meta['c_root']*1000:.1f} mm, c_max {nb2.meta['c_maxval']*1000:.1f} mm; static torque at 0.5 m/s {static_torque(nb2, 0.5)*1000:.1f} mN m; Cp(1 m/s) peak {max(bem(nb2, l, 1.0)['cp'] for l in np.arange(1.5, 6, 0.25)):.3f}")
