#!/usr/bin/env python
"""
Hydrokinetic (free-stream water) turbine blade generator.

Spec: 8 in rotor diameter, 3 in maximum blade width (chord), optimized for
1-2 m/s water flow.  Design method: Schmitz optimum chord/twist (includes
wake rotation) with the design tip-speed ratio chosen so the optimum blade
is exactly 3 in wide at its widest point, then verified with a full
blade-element-momentum (BEM) solver (Prandtl tip+hub loss, Buhl high-induction
correction, NACA 44xx polar model with Viterna post-stall extrapolation).

Geometry: NACA 44xx sections (22 % thick at the root for strength, 12 % at
the tip), wrapped onto cylindrical surfaces (as a real propeller/turbine blade
is built), lofted into a solid with CadQuery and exported as STEP (mm).

Coordinate frame of the output:
  +X = flow direction (water enters from the -X side and leaves toward +X)
  +Z = radial (blade root at the hub, tip at Z = 101.6 mm)
  rotor axis = X axis.  Rotation: counter-clockwise when viewed from upstream.
"""
import csv
import json
import math
import os
import sys

import numpy as np
import cadquery as cq

OUT = os.path.dirname(os.path.abspath(__file__))
IN = 25.4

# ------------------------------------------------------------------ spec ---
D_IN = 8.0
R = D_IN / 2 * IN              # 101.6 mm tip radius
C_MAX = 3.0 * IN               # 76.2 mm max chord ("3 in wide")
R_HUB = 1.0 * IN               # 25.4 mm hub radius (2 in hub, hub ratio 0.25)
R_ROOT_EXT = R_HUB - 5.0       # root stub extends 5 mm inside the hub for a clean union
ROOT_TAPER = 0.62              # root chord / max chord (root taper costs <0.002 Cp, review F5)
PEAK_R = 0.42                  # fraction of tip radius where the chord is widest (3 in)
ROOT_TWIST_ADJ = -2.5          # deg added to the twist at the hub (blends to 0 at 50 % R): keeps the thick root at positive alpha
TIP_CHORD_FRAC = 0.50          # tip chord / chord at 90 % R after elliptical rounding
TC_TIP = 0.14                  # thickness ratio outboard of 65 % R (thicker tip for printability)
TC_ROOT = 0.22                 # thickness ratio at the hub
B = 3                          # number of blades
RHO = 1000.0                   # kg/m^3 fresh water
NU = 1.14e-6                   # m^2/s kinematic viscosity, ~15 C water
RE_REF = 1.5e5                 # Reynolds number at which the drag model is anchored
V_DESIGN = 1.5                 # m/s  (middle of the 1-2 m/s band)
V_LIST = [1.0, 1.5, 2.0]
TE_THICK = 0.8                 # mm, blunt trailing edge (two 0.4 mm FDM perimeters)
PITCH_AXIS = 0.30              # fraction of chord on the radial stacking axis
HUB_LEN = 2.0 * IN             # 50.8 mm hub length for the rotor file
HUB_BORE = 10.0                # mm shaft bore in the rotor file (blind: enters from the downstream face)
PIN_D = 3.2                    # mm cross-pin hole through hub and shaft (torque transmission)
SET_SCREW_D = 3.3              # mm M4 tapping-size pilot holes for grub screws, 90 deg from the pin
NOSE_LEN = 28.0                # mm ellipsoidal nose cone on the upstream face
N_STATIONS = 26
N_PTS = 60                     # points per airfoil surface

# ------------------------------------------------------- airfoil polar ----
def polar(alpha, tc, re=RE_REF):
    """Approximate NACA 44xx lift/drag as a function of thickness ratio tc and chord
    Reynolds number re.  Linear lift region + Viterna extrapolation past stall.
    Anchored on XFOIL-class data at Re 1.5e5 (NACA 4412: Cd ~0.012 at alpha 0;
    NACA 4422: ~0.018); zero-lift drag scales as (RE_REF/Re)^0.8 between 4e4 and 6e5,
    which reproduces the published 1e5 -> 2e5 drag ratio of ~1.8 for these sections.
    Design-level model (no CFD); see REVIEW.md."""
    re = min(max(re, 4e4), 6e5)
    re_fac = (RE_REF / re) ** 0.8
    a_deg = 0.100 - 0.125 * (tc - 0.12)          # lift slope per degree
    alpha0 = -4.0 + 8.33 * (tc - 0.12)           # zero-lift angle (deg)
    clmax = (1.35 - 2.5 * (tc - 0.12)) * min(max((re / RE_REF) ** 0.1, 0.85), 1.05)
    cd0 = (0.0121 + 0.053 * (tc - 0.12)) * re_fac
    k = 0.015
    cdmax = 1.8
    al = math.degrees(alpha)
    al_s = alpha0 + clmax / a_deg                # positive stall angle
    al_sn = alpha0 - 0.8 * clmax / a_deg         # negative stall angle

    def lin(a):
        cl = a_deg * (a - alpha0)
        return cl, cd0 + k * (cl - 0.5) ** 2

    def viterna(a, a_s, cl_s, cd_s):
        a, a_s = math.radians(a), math.radians(a_s)
        kl = (cl_s - cdmax * math.sin(a_s) * math.cos(a_s)) * math.sin(a_s) / math.cos(a_s) ** 2
        kd = (cd_s - cdmax * math.sin(a_s) ** 2) / math.cos(a_s)
        sa = max(math.sin(a), 1e-6)
        cl = cdmax / 2 * math.sin(2 * a) + kl * math.cos(a) ** 2 / sa
        cd = cdmax * sa ** 2 + kd * math.cos(a)
        return cl, cd

    if al_sn <= al <= al_s:
        return lin(al)
    if al > al_s:
        cl_s, cd_s = lin(al_s)
        return viterna(min(al, 89.0), al_s, cl_s, cd_s)
    cl_s, cd_s = lin(al_sn)
    cl, cd = viterna(min(2 * alpha0 - al, 89.0), 2 * alpha0 - al_sn, -cl_s, cd_s)
    return -cl, cd


# ------------------------------------------------------- blade design -----
def tc_of_r(r):
    """Thickness ratio: TC_ROOT at the hub blending to TC_TIP at 65 % radius."""
    s = np.clip((r - R_HUB) / (0.65 * R - R_HUB), 0, 1)
    return TC_TIP + (TC_ROOT - TC_TIP) * 0.5 * (1 + np.cos(np.pi * s))


def alpha_design(tc):
    """Design angle of attack (deg): 5.5 deg on the thin tip, 4 deg on the thick root."""
    return 5.5 - 1.5 * (tc - 0.12) / 0.10


def schmitz_chord(r, lam, cl_d):
    lam_r = lam * r / R
    phi = 2.0 / 3.0 * np.arctan(1.0 / lam_r)
    return 8 * np.pi * r * (1 - np.cos(phi)) / (B * cl_d), phi


def stations():
    """Radial stations, cosine-clustered toward the tip (where the rounding is)."""
    s = np.linspace(0, 1, N_STATIONS)
    t = 1 - np.cos(0.5 * np.pi * s)     # dense near s=1 (tip)
    t = 0.55 * s + 0.45 * t
    return R_HUB + (R - R_HUB) * t


def design_blade(lam=5.4, dbeta=0.0):
    """Chord/twist distribution.
    Chord: outboard of PEAK_R the Schmitz optimum shape at tip-speed ratio `lam`, scaled so the
    chord at PEAK_R is exactly C_MAX; inboard a smooth quadratic taper to ROOT_TAPER x C_MAX at the
    hub; the two are blended with a tanh switch, then renormalised so max chord == C_MAX exactly;
    elliptical tip rounding over the outer 10 %.
    Twist: Schmitz inflow angle at `lam` minus the design alpha, plus a global pitch offset `dbeta`
    (deg) and a root pitch-down ROOT_TWIST_ADJ that blends out by 50 % R."""
    r = stations()
    tc = tc_of_r(r)
    a_d = np.array([alpha_design(t) for t in tc])
    cl_d = np.array([polar(math.radians(a), t)[0] for a, t in zip(a_d, tc)])

    c_s, phi = schmitz_chord(r, lam, cl_d)
    r_pk = PEAK_R * R
    c_out = c_s * (C_MAX / np.interp(r_pk, r, c_s))
    s = np.clip((r_pk - r) / (r_pk - R_HUB), 0, 1)
    c_in = C_MAX * (1 - (1 - ROOT_TAPER) * s ** 2)
    w = 0.5 * (1 - np.tanh((r - r_pk) / (0.05 * R)))
    c = w * c_in + (1 - w) * c_out
    s = np.clip((r - 0.90 * R) / (0.10 * R), 0, 1)             # elliptical tip rounding
    c = c * np.sqrt(1 - (1 - TIP_CHORD_FRAC ** 2) * s ** 2)
    c = c * (C_MAX / c.max())

    twist = np.degrees(phi) - a_d + dbeta     # chord angle from the rotor plane
    s = np.clip((0.50 * R - r) / (0.50 * R - R_HUB), 0, 1)
    twist = twist + ROOT_TWIST_ADJ * 0.5 * (1 - np.cos(np.pi * s))   # root pitch-down (review F2)
    return dict(r=r, chord=c, twist=twist, tc=tc, alpha_d=a_d, cl_d=cl_d, lam=lam, dbeta=dbeta,
                phi=np.degrees(phi))


# ------------------------------------------------------------- BEM --------
def bem(blade, lam, V, n_el=80):
    """Full BEM evaluation of the finished blade. Returns Cp, Ct, P[W], Q[N m], rpm."""
    om = lam * V / (R / 1000.0)
    re = np.linspace(R_HUB, R, n_el + 1)
    rm = 0.5 * (re[1:] + re[:-1])
    dr = (re[1:] - re[:-1]) / 1000.0
    c = np.interp(rm, blade["r"], blade["chord"]) / 1000.0
    beta = np.radians(np.interp(rm, blade["r"], blade["twist"]))
    tc = np.interp(rm, blade["r"], blade["tc"])
    Rm, Rh = R / 1000.0, R_HUB / 1000.0
    T = Q = 0.0
    dist = []
    for i in range(n_el):
        r = rm[i] / 1000.0
        sigma = B * c[i] / (2 * np.pi * r)
        lam_r = om * r / V
        re_i = c[i] * math.sqrt((0.67 * V) ** 2 + (om * r) ** 2) / NU   # local chord Reynolds number

        def induction(phi):
            sphi, cphi = math.sin(phi), math.cos(phi)
            alpha = phi - beta[i]
            cl, cd = polar(alpha, tc[i], re_i)
            cn = cl * cphi + cd * sphi
            ct = cl * sphi - cd * cphi
            ftip = 2 / math.pi * math.acos(min(1.0, math.exp(-B * (Rm - r) / (2 * r * abs(sphi) + 1e-12))))
            fhub = 2 / math.pi * math.acos(min(1.0, math.exp(-B * (r - Rh) / (2 * Rh * abs(sphi) + 1e-12))))  # AeroDyn form
            F = max(ftip * fhub, 1e-3)
            if cn <= 0:
                a = 0.0
            else:
                kappa = 4 * F * sphi ** 2 / (sigma * cn)
                a = 1 / (kappa + 1)
                if a > 0.4:   # Buhl high-induction correction
                    K = sigma * cn / sphi ** 2
                    A = K - 50 / 9 + 4 * F
                    Bq = -2 * K - 4 * F + 40 / 9
                    C = K - 8 / 9
                    disc = Bq * Bq - 4 * A * C
                    if disc >= 0 and abs(A) > 1e-12:
                        roots = [(-Bq + s * math.sqrt(disc)) / (2 * A) for s in (1, -1)]
                        cand = [x for x in roots if 0.4 <= x < 1.0]
                        a = min(cand) if cand else 0.4
                    else:
                        a = 0.4
            if ct == 0:
                ap = 0.0
            else:
                kp = 4 * F * sphi * cphi / (sigma * ct)
                ap = 1 / (kp - 1) if abs(kp - 1) > 1e-9 else 0.0
            ap = max(min(ap, 0.9), -0.4)
            return a, ap, cn, ct, F

        def resid(phi):
            a, ap, *_ = induction(phi)
            return math.sin(phi) / (1 - a + 1e-9) - math.cos(phi) / (lam_r * (1 + ap) + 1e-9)

        # bracket + bisection on phi in (0, pi/2]  (Ning 2014 residual)
        phis = np.linspace(1e-3, math.pi / 2, 60)
        vals = [resid(p) for p in phis]
        lo = hi = None
        for j in range(len(phis) - 1):
            if vals[j] < 0 <= vals[j + 1] or vals[j] <= 0 < vals[j + 1]:
                lo, hi = phis[j], phis[j + 1]
                break
        if lo is None:
            continue
        for _ in range(60):
            m = 0.5 * (lo + hi)
            if resid(m) < 0:
                lo = m
            else:
                hi = m
        phi = 0.5 * (lo + hi)
        a, ap, cn, ct, F = induction(phi)
        W = V * (1 - a) / max(math.sin(phi), 1e-6)
        q = 0.5 * RHO * W * W * c[i]
        T += B * q * cn * dr[i]
        Q += B * q * ct * r * dr[i]
        cl_i = polar(phi - beta[i], tc[i], re_i)[0]
        dist.append((rm[i], math.degrees(phi - beta[i]), a, ap, F, re_i, cl_i))
    A = math.pi * Rm ** 2
    P = om * Q
    return dict(cp=P / (0.5 * RHO * A * V ** 3), ct=T / (0.5 * RHO * A * V ** 2),
                P=P, Q=Q, T=T, rpm=om * 60 / (2 * math.pi), dist=dist)


# -------------------------------------------------------- geometry --------
def naca4(m, p, tc, chord, n=N_PTS, te_thick=TE_THICK):
    """NACA 4-digit section (closed-TE thickness eq.) with a blunt trailing edge.
    Returns upper and lower surfaces, each LE -> TE, in mm, chord along +x."""
    b = np.linspace(0, np.pi, n)
    x = 0.5 * (1 - np.cos(b))
    yt = 5 * tc * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4)
    yt = yt + 0.5 * (te_thick / chord) * x
    yc = np.where(x < p, m / p ** 2 * (2 * p * x - x ** 2),
                  m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x ** 2))
    dyc = np.where(x < p, 2 * m / p ** 2 * (p - x), 2 * m / (1 - p) ** 2 * (p - x))
    th = np.arctan(dyc)
    xu, yu = x - yt * np.sin(th), yc + yt * np.cos(th)
    xl, yl = x + yt * np.sin(th), yc - yt * np.cos(th)
    return np.c_[xu, yu] * chord, np.c_[xl, yl] * chord


def place(pts2d, r, chord, twist_deg):
    """Local (xi, eta) [mm] -> 3D on the cylinder of radius r.
    Chord line at `twist` degrees from the rotor plane; camber (suction) side faces downstream."""
    bt = math.radians(twist_deg)
    xi = pts2d[:, 0] - PITCH_AXIS * chord
    eta = pts2d[:, 1]
    X = xi * math.sin(bt) + eta * math.cos(bt)
    y = -xi * math.cos(bt) + eta * math.sin(bt)     # tangential distance in the unrolled plane
    th = y / r
    Y = r * np.sin(th)
    Z = r * np.cos(th)
    return np.c_[X, Y, Z]


def section_wire(r, chord, twist, tc):
    up, lo = naca4(0.04, 0.40, tc, chord)
    up3, lo3 = place(up, r, chord, twist), place(lo, r, chord, twist)
    V = lambda p: cq.Vector(float(p[0]), float(p[1]), float(p[2]))
    # identical spline parameters on every section -> identical knot vectors -> compact loft surfaces
    prm = list(np.linspace(0.0, 1.0, len(up3)))
    e_up = cq.Edge.makeSpline([V(p) for p in up3[::-1]], parameters=prm, scale=False)   # TE(upper) -> LE
    e_lo = cq.Edge.makeSpline([V(p) for p in lo3], parameters=prm, scale=False)         # LE -> TE(lower)
    e_te = cq.Edge.makeLine(V(lo3[-1]), V(up3[-1]))               # blunt TE closure
    return cq.Wire.assembleEdges([e_up, e_lo, e_te]), np.r_[up3[::-1], lo3[1:]]


from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing
from OCP.ShapeFix import ShapeFix_Solid


def loft_capped(wires):
    """Smooth loft through non-planar (cylinder-wrapped) wires -> closed solid.
    ThruSections' own solid mode needs planar end wires, so we build the shell,
    fill the two end caps and sew."""
    ts = BRepOffsetAPI_ThruSections(False, False, 0.01)
    ts.CheckCompatibility(False)
    for w in wires:
        ts.AddWire(w.wrapped)
    ts.Build()
    shell = cq.Shape.cast(ts.Shape())
    caps = [cq.Face.makeNSidedSurface(wires[0].Edges(), []),
            cq.Face.makeNSidedSurface(wires[-1].Edges(), [])]
    sew = BRepBuilderAPI_Sewing(1e-4)
    for f in shell.Faces() + caps:
        sew.Add(f.wrapped)
    sew.Perform()
    sh = cq.Shape.cast(sew.SewedShape())
    sh = sh if isinstance(sh, cq.Shell) else sh.Shells()[0]
    solid = cq.Solid.makeSolid(sh)
    fx = ShapeFix_Solid(solid.wrapped)
    fx.Perform()
    return cq.Shape.cast(fx.Solid())


def build_blade(blade):
    # extra stations inside the hub carry the hub section radially inward
    r_in = np.array([R_ROOT_EXT - 4.0, R_ROOT_EXT - 1.0, 0.5 * (R_ROOT_EXT + R_HUB)])
    rs = np.r_[r_in, blade["r"]]
    cs = np.r_[[blade["chord"][0]] * 3, blade["chord"]]
    tws = np.r_[[blade["twist"][0]] * 3, blade["twist"]]
    tcs = np.r_[[blade["tc"][0]] * 3, blade["tc"]]
    wires, loops = [], []
    for r, c, tw, tc in zip(rs, cs, tws, tcs):
        w, loop = section_wire(r, c, tw, tc)
        wires.append(w)
        if r >= R_HUB:
            loops.append(loop)
    raw = loft_capped(wires)
    assert raw.isValid(), "raw loft invalid"
    # trim the root to an exact cylinder r = R_ROOT_EXT (the tip is untouched)
    annulus = (cq.Workplane("YZ").workplane(offset=-150).circle(R + 10).circle(R_ROOT_EXT).extrude(300)).val()
    solid = raw.intersect(annulus)
    if not isinstance(solid, cq.Solid):
        solid = max(solid.Solids(), key=lambda s: s.Volume())
    return solid, loops


def build_rotor(blade_solid, root_loop):
    """Hub (2 in dia x 2 in) + ellipsoidal nose cone + blind 10 mm bore from the downstream face
    + 3.2 mm cross-pin hole + two M4 grub-screw pilot holes, with three blades joined on."""
    verts, _ = blade_solid.tessellate(0.05, 0.2)
    xs = [v.x for v in verts]
    hub_x0 = 0.5 * (min(xs) + max(xs))        # centre the hub on the blade's axial extent
    x_up, x_dn = hub_x0 - HUB_LEN / 2, hub_x0 + HUB_LEN / 2
    x_pin = min(float(root_loop[:, 0].max()) + 6.0, x_dn - 6.0)   # clear of the blade roots

    hub = cq.Workplane("YZ").workplane(offset=x_up).circle(R_HUB).extrude(HUB_LEN)
    hub = hub.faces(">X").edges().fillet(3.0)
    t = np.linspace(0, np.pi / 2, 40)
    pts = [(x_up - NOSE_LEN * math.sin(a), R_HUB * math.cos(a)) for a in t[1:]]
    nose = (cq.Workplane("XY").moveTo(x_up, 0).lineTo(x_up, R_HUB).spline(pts, includeCurrent=True)
            .close().revolve(360, (0, 0, 0), (1, 0, 0)))
    hub = hub.union(nose)
    hub = hub.faces(">X").workplane().hole(HUB_BORE, depth=HUB_LEN)        # blind bore
    pin = cq.Solid.makeCylinder(PIN_D / 2, 2 * R_HUB + 10, cq.Vector(x_pin, -R_HUB - 5, 0), cq.Vector(0, 1, 0))
    ss1 = cq.Solid.makeCylinder(SET_SCREW_D / 2, R_HUB + 5, cq.Vector(x_pin, 0, 0), cq.Vector(0, 0, 1))
    ss2 = cq.Solid.makeCylinder(SET_SCREW_D / 2, R_HUB + 5, cq.Vector(x_pin, 0, 0), cq.Vector(0, 0, -1))
    hub = hub.cut(cq.Workplane("XY").add(pin)).cut(cq.Workplane("XY").add(ss1)).cut(cq.Workplane("XY").add(ss2))

    rotor = hub
    for k in range(B):
        bl = blade_solid.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 360.0 * k / B)
        rotor = rotor.union(cq.Workplane("XY").add(bl))
    solid = rotor.val()

    # try a small fillet on the blade/hub junction edges (OCC may refuse; then we ship without it)
    fillet_r = 0.0
    junction = []
    for e in solid.Edges():
        ps = [e.positionAt(u) for u in (0.1, 0.35, 0.6, 0.9)]
        rr = [math.hypot(p.y, p.z) for p in ps]
        xx = [p.x for p in ps]
        if all(abs(q - R_HUB) < 0.3 for q in rr) and (max(xx) - min(xx)) > 1.0 and x_up + 0.5 < min(xx) and max(xx) < x_dn - 0.5:
            junction.append(e)
    for fr in (1.5, 1.0):
        try:
            cand = solid.fillet(fr, junction)
            if cand.isValid() and abs(cand.Volume() - solid.Volume()) < 0.02 * solid.Volume():
                solid, fillet_r = cand, fr
                break
        except Exception:
            pass
    return solid, dict(hub_center_x_mm=hub_x0, hub_x_upstream_face_mm=x_up, hub_x_downstream_face_mm=x_dn,
                       pin_x_mm=x_pin, junction_fillet_mm=fillet_r, junction_edges=len(junction))


def blade_clearance(blade_solid):
    """Minimum distance between a blade and its neighbour (rotated 120 deg about X) near the root."""
    verts, _ = blade_solid.tessellate(0.1, 0.3)
    A = np.array([(v.x, v.y, v.z) for v in verts])
    A = A[np.hypot(A[:, 1], A[:, 2]) < 0.55 * R]
    if len(A) > 6000:
        A = A[np.random.default_rng(0).choice(len(A), 6000, replace=False)]
    th = 2 * np.pi / B
    Bv = A.copy()
    Bv[:, 1] = A[:, 1] * np.cos(th) - A[:, 2] * np.sin(th)
    Bv[:, 2] = A[:, 1] * np.sin(th) + A[:, 2] * np.cos(th)
    best = 1e9
    for i in range(0, len(A), 2000):
        d = np.sqrt(((A[i:i + 2000, None, :] - Bv[None, :, :]) ** 2).sum(-1))
        best = min(best, float(d.min()))
    return best


def naca_section_props(tc, chord):
    """Area and flapwise second moment (about the chord-parallel centroidal axis) of a NACA 44xx section."""
    up, lo = naca4(0.04, 0.40, tc, chord, n=120, te_thick=0.0)
    poly = np.r_[up[::-1], lo[1:]]
    x, y = poly[:, 0], poly[:, 1]
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cross = x * y1 - x1 * y
    A = 0.5 * cross.sum()
    cy = (y + y1).dot(cross) / (6 * A)
    Ixx = ((y * y + y * y1 + y1 * y1) * cross).sum() / 12 - A * cy * cy
    ymax = max(y.max() - cy, cy - y.min())
    return abs(A), abs(Ixx), ymax


def root_stress(blade, lam, V):
    """Flapwise bending stress along the span from the BEM thrust distribution (per blade)."""
    res = bem(blade, lam, V, n_el=120)
    rm = np.array([d[0] for d in res["dist"]]) / 1000.0
    om = lam * V / (R / 1000.0)
    c = np.interp(rm * 1000, blade["r"], blade["chord"]) / 1000.0
    tcs = np.interp(rm * 1000, blade["r"], blade["tc"])
    beta = np.radians(np.interp(rm * 1000, blade["r"], blade["twist"]))
    dr = (R - R_HUB) / 1000.0 / len(rm)
    # per-element normal force (thrust direction) per blade
    dT = []
    for d, ci, tci, bi in zip(res["dist"], c, tcs, beta):
        r, al, a, ap, F, re_i, cl_i = d
        phi = math.radians(al) + bi
        cl, cd = polar(math.radians(al), tci, re_i)
        W = V * (1 - a) / max(math.sin(phi), 1e-6)
        dT.append(0.5 * RHO * W * W * ci * (cl * math.cos(phi) + cd * math.sin(phi)) * dr)
    dT = np.array(dT)
    out = []
    for k in range(0, len(rm), 6):
        M = float(((rm[k:] - rm[k]) * dT[k:]).sum())
        A_, I, ymax = naca_section_props(tcs[k], c[k])
        out.append((rm[k] * 1000, M, M * ymax / I / 1e6 if I > 0 else 0.0))
    return out, float(dT.sum())


# ----------------------------------------------------------- main ---------
def main():
    import time
    t0 = time.time()
    lam_scan = np.arange(1.5, 6.01, 0.25)

    def peak_cp(bl):
        cps_ = [bem(bl, l, V_DESIGN, n_el=40)["cp"] for l in lam_scan]
        j = int(np.argmax(cps_))
        return cps_[j], lam_scan[j]

    best = None
    for lam_try in np.arange(3.0, 6.01, 1.0):
        for db in np.arange(2.0, 10.01, 2.0):
            bl = design_blade(lam_try, db)
            cp_pk, lam_pk = peak_cp(bl)
            if best is None or cp_pk > best[0]:
                best = (cp_pk, lam_try, db, lam_pk)
    cp0, lam0, db0, _ = best
    for lam_try in np.arange(lam0 - 0.5, lam0 + 0.51, 0.5):
        for db in np.arange(db0 - 1.0, db0 + 1.01, 1.0):
            bl = design_blade(lam_try, db)
            cp_pk, lam_pk = peak_cp(bl)
            if cp_pk > best[0]:
                best = (cp_pk, lam_try, db, lam_pk)
    cp_pk, lam_geom, dbeta, lam_pk = best
    print(f"optimised: geometry TSR {lam_geom:.2f}, pitch offset {dbeta:+.2f} deg -> peak Cp {cp_pk:.3f} "
          f"at TSR {lam_pk:.2f} at {V_DESIGN} m/s   ({time.time()-t0:.0f} s)")
    blade = design_blade(lam_geom, dbeta)

    # BEM verification of the final blade at each speed (fine resolution)
    print(f"[{time.time()-t0:.0f} s] BEM curves...", flush=True)
    lams = np.arange(0.5, 7.01, 0.25)
    curves = {str(V): [bem(blade, l, V) for l in lams] for V in V_LIST}
    cps15 = np.array([x["cp"] for x in curves[str(V_DESIGN)]])
    i_best = int(np.argmax(cps15))
    lam_d = float(lams[i_best])          # recommended operating TSR = BEM peak at 1.5 m/s
    perf = {}
    for V in V_LIST:
        res_d = bem(blade, lam_d, V)
        cpsV = np.array([x["cp"] for x in curves[str(V)]])
        jV = int(np.argmax(cpsV))
        static = bem(blade, 0.1, V)
        # runaway: first TSR above the peak where the shaft torque reaches zero
        run = next((float(l) for l, x in zip(lams, curves[str(V)]) if l > lams[jV] and x["cp"] <= 0), 7.0)
        perf[str(V)] = dict(
            operating=dict(tsr=lam_d, cp=res_d["cp"], ct=res_d["ct"], P_W=res_d["P"], Q_Nm=res_d["Q"],
                           T_N=res_d["T"], rpm=res_d["rpm"]),
            best_at_this_speed=dict(tsr=float(lams[jV]), cp=float(cpsV[jV]), rpm=curves[str(V)][jV]["rpm"]),
            static_torque_Nm=static["Q"], runaway_tsr=run, runaway_rpm=run * V / (R / 1000.0) * 60 / (2 * math.pi),
            available_W=0.5 * RHO * math.pi * (R / 1000) ** 2 * V ** 3,
        )

    # structural estimate (flapwise bending from the BEM thrust distribution)
    stress = {}
    for V in (2.0, 3.0):
        prof, thrust_blade = root_stress(blade, lam_d, V)
        k = int(np.argmax([p[2] for p in prof]))
        stress[str(V)] = dict(thrust_per_blade_N=thrust_blade, root_moment_Nm=prof[0][1], root_stress_MPa=prof[0][2],
                              max_stress_MPa=prof[k][2], max_stress_r_mm=prof[k][0])

    # geometry
    print(f"[{time.time()-t0:.0f} s] building blade...", flush=True)
    solid, loops = build_blade(blade)
    assert solid.isValid(), "blade solid is not valid"
    verts, tris = solid.tessellate(0.02, 0.1)
    vv = np.array([(v.x, v.y, v.z) for v in verts])
    rmax = float(np.sqrt(vv[:, 1] ** 2 + vv[:, 2] ** 2).max())

    class _BB:   # tight extents from the tessellation
        xmin, xmax = float(vv[:, 0].min()), float(vv[:, 0].max())
        ymin, ymax = float(vv[:, 1].min()), float(vv[:, 1].max())
        zmin, zmax = float(vv[:, 2].min()), float(vv[:, 2].max())
    bb = _BB()
    print(f"[{time.time()-t0:.0f} s] clearance check...", flush=True)
    clearance = blade_clearance(solid)
    print(f"blade: valid={solid.isValid()} volume={solid.Volume():.0f} mm^3")
    print(f"       X extent {bb.xmin:.1f}..{bb.xmax:.1f} mm = {(bb.xmax-bb.xmin)/IN:.3f} in axial")
    print(f"       max radius {rmax:.2f} mm = {rmax/IN:.3f} in  (spec 4.000 in);  blade-to-blade clearance near root {clearance:.1f} mm")

    cq.exporters.export(solid, os.path.join(OUT, "turbine_blade_8in.step"))
    cq.exporters.export(solid, os.path.join(OUT, "turbine_blade_8in.stl"), tolerance=0.05, angularTolerance=0.2)

    print(f"[{time.time()-t0:.0f} s] building rotor...", flush=True)
    rotor, hubinfo = build_rotor(solid, loops[0])
    print(f"[{time.time()-t0:.0f} s] rotor done", flush=True)
    assert rotor.isValid(), "rotor solid is not valid"
    cq.exporters.export(rotor, os.path.join(OUT, "turbine_rotor_8in_3blade.step"))
    cq.exporters.export(rotor, os.path.join(OUT, "turbine_rotor_8in_3blade.stl"), tolerance=0.08, angularTolerance=0.25)
    print(f"rotor: valid={rotor.isValid()} volume={rotor.Volume():.0f} mm^3  solids={len(rotor.Solids())}  "
          f"junction fillet {hubinfo['junction_fillet_mm']} mm on {hubinfo['junction_edges']} edges; pin at X={hubinfo['pin_x_mm']:.1f}")

    # station table with operating-point columns (BEM at the operating TSR, 1.5 m/s)
    d15 = bem(blade, lam_d, V_DESIGN, n_el=120)["dist"]
    rr = np.array([d[0] for d in d15])
    op_al = np.interp(blade["r"], rr, [d[1] for d in d15]); op_cl = np.interp(blade["r"], rr, [d[6] for d in d15])
    op_re = np.interp(blade["r"], rr, [d[5] for d in d15]); op_a = np.interp(blade["r"], rr, [d[2] for d in d15])
    with open(os.path.join(OUT, "blade_stations.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["r_mm", "r_in", "r_over_R", "chord_mm", "chord_in", "twist_deg_from_rotor_plane",
                    "thickness_ratio", "max_thickness_mm", "airfoil",
                    "operating_alpha_deg_1p5ms", "operating_CL_1p5ms", "operating_Re_1p5ms", "operating_axial_induction",
                    "schmitz_design_alpha_deg", "schmitz_design_CL"])
        for i, (r, c, tw, tc) in enumerate(zip(blade["r"], blade["chord"], blade["twist"], blade["tc"])):
            w.writerow([f"{r:.2f}", f"{r/IN:.3f}", f"{r/R:.3f}", f"{c:.2f}", f"{c/IN:.3f}", f"{tw:.2f}",
                        f"{tc:.3f}", f"{c*tc:.2f}", f"NACA 44{int(round(tc*100)):02d}",
                        f"{op_al[i]:.2f}", f"{op_cl[i]:.3f}", f"{op_re[i]:.3g}", f"{op_a[i]:.3f}",
                        f"{blade['alpha_d'][i]:.2f}", f"{blade['cl_d'][i]:.3f}"])

    sec_dir = os.path.join(OUT, "sections_for_fusion_csv")
    os.makedirs(sec_dir, exist_ok=True)
    for fn in os.listdir(sec_dir):
        os.remove(os.path.join(sec_dir, fn))
    for k, (r, loop) in enumerate(zip(blade["r"], loops)):
        closed = np.r_[loop, loop[:1]]
        np.savetxt(os.path.join(sec_dir, f"section_{k:02d}_r{r:.1f}mm.csv"), closed / 10.0, delimiter=",", fmt="%.5f")

    spec = dict(
        rotor_diameter_in=D_IN, tip_radius_mm=R, hub_radius_mm=R_HUB, hub_diameter_in=2 * R_HUB / IN,
        hub_ratio=R_HUB / R, root_trim_radius_mm=R_ROOT_EXT,
        max_chord_mm=float(blade["chord"].max()), max_chord_in=float(blade["chord"].max() / IN),
        max_chord_r_mm=float(blade["r"][int(np.argmax(blade["chord"]))]),
        root_chord_mm=float(blade["chord"][0]), tip_chord_mm=float(blade["chord"][-1]),
        root_thickness_mm=float(blade["chord"][0] * blade["tc"][0]), tip_thickness_mm=float(blade["chord"][-1] * blade["tc"][-1]),
        twist_root_deg=float(blade["twist"][0]), twist_tip_deg=float(blade["twist"][-1]),
        axial_extent_mm=float(bb.xmax - bb.xmin), axial_extent_in=float((bb.xmax - bb.xmin) / IN),
        blades=B, operating_tsr=lam_d, geometry_schmitz_tsr=float(lam_geom), pitch_offset_deg=float(dbeta),
        root_twist_adjust_deg=ROOT_TWIST_ADJ, cp_peak_1p5ms=float(cps15[i_best]),
        airfoil=f"NACA 4412-type camber (4 % at 40 %), thickness {TC_ROOT*100:.0f} % at the hub to {TC_TIP*100:.0f} % from 65 % radius",
        trailing_edge_thickness_mm=TE_THICK, pitch_axis_fraction=PITCH_AXIS,
        rotation="counter-clockwise viewed from upstream (looking along +X); clockwise viewed from the downstream/generator side",
        flow_direction="+X (water enters from -X face)", units="mm (STEP AP214)",
        water=dict(rho=RHO, nu=NU, note="~15 C fresh water"), reynolds_model=dict(re_ref=RE_REF, cd0_exponent=0.8),
        hub_length_mm=HUB_LEN, hub_bore_mm=HUB_BORE, hub_bore="blind from downstream face", pin_hole_mm=PIN_D,
        set_screw_pilot_mm=SET_SCREW_D, nose_cone_length_mm=NOSE_LEN, **hubinfo,
        blade_volume_mm3=float(solid.Volume()), blade_max_radius_mm=rmax, blade_to_blade_clearance_mm=clearance,
        cp_curve=dict(tsr=lams.tolist(), **{f"cp_{V}": [x["cp"] for x in curves[str(V)]] for V in V_LIST},
                      **{f"ct_{V}": [x["ct"] for x in curves[str(V)]] for V in V_LIST}),
        power_curve={str(V): dict(rpm=[x["rpm"] for x in curves[str(V)]], P_W=[x["P"] for x in curves[str(V)]]) for V in V_LIST},
        performance=perf, structural=stress,
    )
    with open(os.path.join(OUT, "design_spec.json"), "w") as f:
        json.dump(spec, f, indent=2)

    print(f"\nOperating TSR = {lam_d:.2f}   max chord = {blade['chord'].max():.2f} mm at r={spec['max_chord_r_mm']:.1f}   "
          f"root chord = {blade['chord'][0]:.1f} mm  tip chord {blade['chord'][-1]:.1f} mm  twist root/tip = {blade['twist'][0]:.1f}/{blade['twist'][-1]:.1f} deg")
    al = np.array([d[1] for d in d15]); ax_ = np.array([d[2] for d in d15]); re_ = np.array([d[5] for d in d15])
    print(f"operating point 1.5 m/s: alpha {al.min():.1f}..{al.max():.1f} deg; axial induction {ax_.min():.2f}..{ax_.max():.2f}; Re {re_.min():.2g}..{re_.max():.2g}")
    for V in V_LIST:
        print(f"Cp(TSR) at {V} m/s: " + "  ".join(f"{l:.2f}:{x['cp']:.3f}" for l, x in zip(lams, curves[str(V)]) if 1.5 <= l <= 6 and (l * 2) % 1 == 0))
    for V in V_LIST:
        d = perf[str(V)]["operating"]; p = perf[str(V)]
        print(f"  V={V:.1f} m/s: {d['rpm']:.0f} rpm, P={d['P_W']:.1f} W, Q={d['Q_Nm']:.2f} N m, thrust={d['T_N']:.0f} N, Cp={d['cp']:.3f}, Ct={d['ct']:.3f}; "
              f"static torque {p['static_torque_Nm']:.3f} N m; runaway TSR {p['runaway_tsr']:.2f} = {p['runaway_rpm']:.0f} rpm")
    for V, s in stress.items():
        print(f"  stress at {V} m/s: thrust/blade {s['thrust_per_blade_N']:.1f} N, root M {s['root_moment_Nm']:.2f} N m, root {s['root_stress_MPa']:.2f} MPa, "
              f"max {s['max_stress_MPa']:.2f} MPa at r={s['max_stress_r_mm']:.0f} mm")
    return blade, spec


if __name__ == "__main__":
    main()
