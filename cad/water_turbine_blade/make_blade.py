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
R_HUB = 1.5 * IN               # 38.1 mm hub radius (3 in hub, hub ratio 0.375)
R_ROOT_EXT = 32.0              # root stub extends 6 mm inside the hub for a clean union
ROOT_TAPER = 0.80              # root chord / max chord
TAPER_START = 0.55             # root taper blends in from this fraction of the tip radius
B = 3                          # number of blades
RHO = 1000.0                   # kg/m^3 fresh water
V_DESIGN = 1.5                 # m/s  (middle of the 1-2 m/s band)
V_LIST = [1.0, 1.5, 2.0]
TE_THICK = 0.6                 # mm, blunt trailing edge (printable/machinable)
PITCH_AXIS = 0.30              # fraction of chord on the radial stacking axis
HUB_LEN = 2.0 * IN             # 50.8 mm hub length for the rotor file
HUB_BORE = 10.0                # mm through-bore in the rotor file
N_STATIONS = 26
N_PTS = 60                     # points per airfoil surface

# ------------------------------------------------------- airfoil polar ----
def polar(alpha, tc):
    """Approximate NACA 44xx lift/drag at Re ~ 1e5-4e5 as a function of
    thickness ratio tc.  Linear region + Viterna extrapolation past stall.
    Design-level model (no CFD / XFOIL)."""
    a_deg = 0.100 - 0.125 * (tc - 0.12)          # lift slope per degree
    alpha0 = -4.0 + 8.33 * (tc - 0.12)           # zero-lift angle (deg)
    clmax = 1.35 - 2.5 * (tc - 0.12)
    cd0 = 0.011 + 0.05 * (tc - 0.12)
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
    # negative stall: mirror about alpha0
    cl_s, cd_s = lin(al_sn)
    cl, cd = viterna(min(2 * alpha0 - al, 89.0), 2 * alpha0 - al_sn, -cl_s, cd_s)
    return -cl, cd


# ------------------------------------------------------- blade design -----
def tc_of_r(r):
    """Thickness ratio: 22 % at the hub blending to 12 % at 65 % radius."""
    s = np.clip((r - R_HUB) / (0.65 * R - R_HUB), 0, 1)
    return 0.12 + (0.22 - 0.12) * 0.5 * (1 + np.cos(np.pi * s))


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


def design_blade(lam=None, dbeta=0.0):
    """Chord/twist distribution.  Chord = Schmitz optimum shape at tip-speed ratio `lam`
    (capped, root-tapered, tip-rounded) scaled so the widest point is exactly C_MAX;
    twist = Schmitz inflow angle - design alpha + global pitch offset `dbeta` (deg).
    If lam is None, lam is solved so the un-scaled Schmitz optimum is exactly C_MAX wide."""
    r = stations()
    tc = tc_of_r(r)
    a_d = np.array([alpha_design(t) for t in tc])
    cl_d = np.array([polar(math.radians(a), t)[0] for a, t in zip(a_d, tc)])

    def shape(lam_):
        c, phi = schmitz_chord(r, lam_, cl_d)
        c = np.minimum(c, C_MAX)
        s = np.clip((r - 0.90 * R) / (0.10 * R), 0, 1)             # elliptical tip rounding
        c = c * np.sqrt(1 - (1 - 0.40 ** 2) * s ** 2)
        s = np.clip((TAPER_START * R - r) / (TAPER_START * R - R_HUB), 0, 1)     # gentle root taper
        c = c * (1 - (1 - ROOT_TAPER) * s ** 2)
        return c, phi

    if lam is None:
        lo, hi = 1.2, 8.0
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if schmitz_chord(r, mid, cl_d)[0].max() > C_MAX:
                lo = mid
            else:
                hi = mid
        lam = 0.5 * (lo + hi)
    c, phi = shape(lam)
    c = c * (C_MAX / c.max())
    twist = np.degrees(phi) - a_d + dbeta     # chord angle from the rotor plane
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

        def induction(phi):
            sphi, cphi = math.sin(phi), math.cos(phi)
            alpha = phi - beta[i]
            cl, cd = polar(alpha, tc[i])
            cn = cl * cphi + cd * sphi
            ct = cl * sphi - cd * cphi
            ftip = 2 / math.pi * math.acos(min(1.0, math.exp(-B * (Rm - r) / (2 * r * abs(sphi) + 1e-12))))
            fhub = 2 / math.pi * math.acos(min(1.0, math.exp(-B * (r - Rh) / (2 * r * abs(sphi) + 1e-12))))
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
        dist.append((rm[i], math.degrees(phi - beta[i]), a, ap, F))
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


def build_rotor(blade_solid):
    verts, _ = blade_solid.tessellate(0.05, 0.2)
    xs = [v.x for v in verts]
    hub_x0 = 0.5 * (min(xs) + max(xs))        # centre the hub on the blade's axial extent
    hub = (cq.Workplane("YZ").workplane(offset=hub_x0 - HUB_LEN / 2)
           .circle(R_HUB).extrude(HUB_LEN)
           .edges().fillet(4.0)
           .faces(">X").workplane().hole(HUB_BORE))
    rotor = hub
    for k in range(B):
        bl = blade_solid.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 360.0 * k / B)
        rotor = rotor.union(cq.Workplane("XY").add(bl))
    return rotor.val(), hub_x0


# ----------------------------------------------------------- main ---------
def main():
    import time
    t0 = time.time()
    lam_scan = np.arange(1.5, 6.01, 0.25)

    def peak_cp(bl):
        cps_ = [bem(bl, l, V_DESIGN, n_el=40)["cp"] for l in lam_scan]
        j = int(np.argmax(cps_))
        return cps_[j], lam_scan[j]

    base = design_blade()
    print(f"Schmitz-only design: TSR {base['lam']:.2f}, peak BEM Cp {peak_cp(base)[0]:.3f}")
    best = None
    for lam_try in np.arange(2.0, 6.01, 0.5):
        for db in np.arange(-4.0, 8.01, 1.5):
            bl = design_blade(lam_try, db)
            cp_pk, lam_pk = peak_cp(bl)
            if best is None or cp_pk > best[0]:
                best = (cp_pk, lam_try, db, lam_pk)
    # refine around the best cell
    cp0, lam0, db0, _ = best
    for lam_try in np.arange(lam0 - 0.4, lam0 + 0.41, 0.2):
        for db in np.arange(db0 - 1.25, db0 + 1.26, 0.5):
            bl = design_blade(lam_try, db)
            cp_pk, lam_pk = peak_cp(bl)
            if cp_pk > best[0]:
                best = (cp_pk, lam_try, db, lam_pk)
    cp_pk, lam_geom, dbeta, lam_pk = best
    print(f"optimised: geometry TSR {lam_geom:.2f}, pitch offset {dbeta:+.2f} deg -> peak Cp {cp_pk:.3f} "
          f"at TSR {lam_pk:.2f}   ({time.time()-t0:.0f} s)")
    blade = design_blade(lam_geom, dbeta)

    # BEM verification of the final blade (fine resolution)
    lams = np.arange(0.5, 7.01, 0.25)
    cp_curve = [bem(blade, l, V_DESIGN) for l in lams]
    cps = np.array([x["cp"] for x in cp_curve])
    i_best = int(np.argmax(cps))
    lam_d = float(lams[i_best])          # recommended operating TSR = BEM peak
    perf = {}
    for V in V_LIST:
        res_d = bem(blade, lam_d, V)
        res_b = bem(blade, lams[i_best], V)
        perf[str(V)] = dict(
            design_tsr=dict(tsr=lam_d, cp=res_d["cp"], ct=res_d["ct"], P_W=res_d["P"], Q_Nm=res_d["Q"],
                            T_N=res_d["T"], rpm=res_d["rpm"]),
            best_tsr=dict(tsr=float(lams[i_best]), cp=res_b["cp"], ct=res_b["ct"], P_W=res_b["P"],
                          Q_Nm=res_b["Q"], T_N=res_b["T"], rpm=res_b["rpm"]),
            available_W=0.5 * RHO * math.pi * (R / 1000) ** 2 * V ** 3,
        )

    # geometry
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
    print(f"blade: valid={solid.isValid()} volume={solid.Volume():.0f} mm^3")
    print(f"       X extent {bb.xmin:.1f}..{bb.xmax:.1f} mm = {(bb.xmax-bb.xmin)/IN:.3f} in axial")
    print(f"       max radius {rmax:.2f} mm = {rmax/IN:.3f} in  (spec 4.000 in)")

    cq.exporters.export(solid, os.path.join(OUT, "turbine_blade_8in.step"))
    cq.exporters.export(solid, os.path.join(OUT, "turbine_blade_8in.stl"), tolerance=0.05, angularTolerance=0.2)

    rotor, hub_x0 = build_rotor(solid)
    assert rotor.isValid(), "rotor solid is not valid"
    cq.exporters.export(rotor, os.path.join(OUT, "turbine_rotor_8in_3blade.step"))
    cq.exporters.export(rotor, os.path.join(OUT, "turbine_rotor_8in_3blade.stl"), tolerance=0.08, angularTolerance=0.25)
    rb = rotor.BoundingBox()
    print(f"rotor: valid={rotor.isValid()} volume={rotor.Volume():.0f} mm^3  "
          f"Y {rb.ymin:.1f}..{rb.ymax:.1f}  Z {rb.zmin:.1f}..{rb.zmax:.1f}  X {rb.xmin:.1f}..{rb.xmax:.1f}")

    # station table
    with open(os.path.join(OUT, "blade_stations.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["r_mm", "r_in", "r_over_R", "chord_mm", "chord_in", "twist_deg_from_rotor_plane",
                    "thickness_ratio", "airfoil", "design_alpha_deg", "design_CL", "inflow_phi_deg"])
        for r, c, tw, tc, a, cl, ph in zip(blade["r"], blade["chord"], blade["twist"], blade["tc"],
                                            blade["alpha_d"], blade["cl_d"], blade["phi"]):
            w.writerow([f"{r:.2f}", f"{r/IN:.3f}", f"{r/R:.3f}", f"{c:.2f}", f"{c/IN:.3f}", f"{tw:.2f}",
                        f"{tc:.3f}", f"NACA 44{int(round(tc*100)):02d}", f"{a:.2f}", f"{cl:.3f}", f"{ph:.2f}"])

    # per-station 3D section loops for Fusion's ImportSplineCSV script (cm units)
    sec_dir = os.path.join(OUT, "sections_for_fusion_csv")
    os.makedirs(sec_dir, exist_ok=True)
    for k, (r, loop) in enumerate(zip(blade["r"], loops)):
        closed = np.r_[loop, loop[:1]]
        np.savetxt(os.path.join(sec_dir, f"section_{k:02d}_r{r:.1f}mm.csv"), closed / 10.0,
                   delimiter=",", fmt="%.5f")

    spec = dict(
        rotor_diameter_in=D_IN, tip_radius_mm=R, hub_radius_mm=R_HUB, hub_diameter_in=2 * R_HUB / IN,
        max_chord_mm=float(blade["chord"].max()), max_chord_in=float(blade["chord"].max() / IN),
        axial_extent_mm=float(bb.xmax - bb.xmin), axial_extent_in=float((bb.xmax - bb.xmin) / IN),
        blades=B, operating_tsr=lam_d, geometry_schmitz_tsr=float(lam_geom), pitch_offset_deg=float(dbeta),
        cp_max_bem=float(cps[i_best]),
        power_curve={str(V): dict(rpm=[bem(blade, l, V)["rpm"] for l in lams],
                                  P_W=[bem(blade, l, V)["P"] for l in lams]) for V in V_LIST},
        airfoil="NACA 4412 (tip) -> NACA 4422 (root), 4% camber at 40% chord",
        trailing_edge_thickness_mm=TE_THICK, pitch_axis_fraction=PITCH_AXIS,
        rotation="counter-clockwise viewed from upstream (looking along +X)",
        flow_direction="+X (water enters from -X face)", units="mm (STEP AP214)",
        hub_length_mm=HUB_LEN, hub_bore_mm=HUB_BORE, hub_center_x_mm=hub_x0,
        blade_volume_mm3=float(solid.Volume()), blade_max_radius_mm=rmax,
        cp_curve=dict(tsr=lams.tolist(), cp=cps.tolist(), ct=[x["ct"] for x in cp_curve]),
        performance=perf,
    )
    with open(os.path.join(OUT, "design_spec.json"), "w") as f:
        json.dump(spec, f, indent=2)

    print(f"\nOperating TSR = {lam_d:.2f}   max chord = {blade['chord'].max():.2f} mm   "
          f"root chord = {blade['chord'][0]:.1f} mm  twist root/tip = {blade['twist'][0]:.1f}/{blade['twist'][-1]:.1f} deg")
    al = np.array([d[1] for d in bem(blade, lam_d, V_DESIGN)["dist"]])
    ax_ = np.array([d[2] for d in bem(blade, lam_d, V_DESIGN)["dist"]])
    print(f"angle of attack along span at operating TSR: {al.min():.1f} .. {al.max():.1f} deg; "
          f"axial induction {ax_.min():.2f} .. {ax_.max():.2f}")
    print("Cp(TSR): " + "  ".join(f"{l:.2f}:{c:.3f}" for l, c in zip(lams, cps) if l >= 1.0))
    for V in V_LIST:
        d = perf[str(V)]["design_tsr"]
        print(f"  V={V:.1f} m/s: {d['rpm']:.0f} rpm, P={d['P_W']:.1f} W, Q={d['Q_Nm']:.2f} N m, "
              f"thrust={d['T_N']:.0f} N, Cp={d['cp']:.3f}, Ct={d['ct']:.3f}")
    return blade, spec


if __name__ == "__main__":
    main()
