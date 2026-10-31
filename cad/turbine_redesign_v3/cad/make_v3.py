#!/usr/bin/env python
"""
Redesign v3.1: through-spindle drum rotor ("D1").  The hub IS a rotating watertight drum (COTS 6061
tube + two machined hard-anodised 6061 caps + static O-rings) containing a CubeMars GL60 KV25
generator whose stator is bolted to the integral flange of a stationary aluminium spindle that passes
through the motor's 20 mm bore and leaves the drum through ONE rotary lip seal at the rear.
Printed 3-segment blade carrier with pinned modular blades (airfoil-section tongues), printed dome,
profile-cut 6061 struts, aluminium strut boss (heat sink, labyrinth, potted cable plug).

Frame: +X = flow (water enters at the dome, -X side); rotor axis = X; Z radial up.
Every dimension is in BASE/VARIANTS; TO_MEASURE lists placeholders.  Variants: "robust" and "min76".
Rev 3.1 changes (review cycle 1, see docs/ERROR_LOG.md R11-R30): split thrust ring instead of the
integral collar (rear bearing installable), lead channel in the flange + spindle hole under the flange,
recessed spindle end with an O-ring potting plug and a rear-face lead groove (cross pin clear of the
leads, seal serviceable), counterbored stator/disc screws, dogs clocked 45 deg from the screws,
counterbored vent, nose +2 mm with a 0.1 mm circlip gap and a 24 mm recess, shim pack, single O-ring
per cap in min76 (2.5 mm lands), boss 10 mm with a labyrinth tongue, 6061 caps, airfoil tongues with
axial pins, profile-cut struts in duct clevises, duct ID 210 (3.4 mm tip clearance).
"""
import json, math, os, sys, itertools
import numpy as np
import cadquery as cq
HERE = os.path.dirname(os.path.abspath(__file__))
BLADE_DIR = os.path.join(HERE, "..", "..", "water_turbine_blade")
sys.path.insert(0, BLADE_DIR)
import make_blade as mb
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)

VARIANTS = {
    "robust": dict(brg="6902", brg_od=28.0, brg_w=7.0, dome_h=9.0, boss_t=10.0, flange_t=2.5, ic=1.0, plug_front=13.5, plug_rear=13.5, n_orings=2, oring_pitch=5.6,
                   seal="15x24x5", seal_od=24.0, seal_w=5.0, strut_jog=14.0),
    "min76":  dict(brg="6702", brg_od=21.0, brg_w=4.0, dome_h=6.0, boss_t=10.0, flange_t=2.0, ic=0.5, plug_front=8.6,  plug_rear=9.6,  n_orings=1, oring_pitch=0.0,
                   seal="15x22x4", seal_od=22.0, seal_w=4.0, strut_jog=14.0),
}
BASE = dict(
    # pressure tube: 6061-T6 3.0 in OD x 0.065 in wall (ID 72.9); both ends faced and the O-ring lands bored H8; length derived
    tube_od=76.2, tube_id=72.9, plug_clear=0.15,
    oring_cs=2.62, oring_groove_w=3.6, oring_groove_d=2.08, oring_land=2.5,     # AS568-147 EPDM 70 (ID 67.95) in a 68.5 mm groove OD
    # generator CubeMars GL60 KV25 (manufacturer per review citation: 69 x 22.3, bore 20, 230 g)
    motor_od=69.0, motor_len=22.3, motor_bore=20.0, motor_pcd=50.0, motor_hole=2.6, bell_pcd=40.0,   # GL60: 4xM3 PCD40 + 4xM2.5 PCD50 (which is stator/bell: TO MEASURE -> both patterns provided)
    disc_t=3.0, disc_od=62.0, disc_pcd_out=48.0, dog_d=8.0, dog_h=4.0, screw_cb_d=6.0, screw_cb_depth=2.2, screw_head_d=5.5, screw_head_h=2.0,
    # spindle: 6061-T6 hard-anodised, 15 h6 journals (after coating), 9 mm cable bore, integral stator flange
    spindle_d=15.0, spindle_bore=9.0, sp_flange_od=58.0, sp_flange_t=4.0, circlip_w=1.1, circlip_d=14.3, circlip_edge=2.0, circlip_gap=0.1,
    collar_od=17.6, collar_w=2.0, collar_groove_d=13.5, shim_t=0.3, cap_web=2.5, lead_hole_d=4.5, lead_channel_w=5.0, lead_channel_d=2.5, lead_angle=45.0,
    sleeve_len=6.0, sleeve_od=15.56,
    # blade carrier (printed, 3 segments) and blade root joint: airfoil-section tongue, 2 axial pins
    carrier_wall=3.9, carrier_lip=2.0, lug_w=6.0, lug_h=3.0, pad_h=6.0, pad_len=36.0, pad_w=58.0, pocket_d=8.7, pocket_clear=0.15,
    pin_d=3.0, pin_y=8.0, pin_below_top=4.5, seg_bolt_d=3.2, seg_bolt_n=2, nut_af=5.7, nut_h=2.6,
    # strut boss (aluminium), struts (profile-cut 6061 plate), duct/guard
    boss_od=72.0, strut_w=16.0, strut_t=4.0, n_struts=3, duct_id=210.0, duct_od=216.0, r_jog0=52.0, r_jog1=58.0, clevis_len=20.0, clevis_w=14.0,
    cable_d=4.5, vent_r=24.0, vent_cb_d=11.0, vent_cb_depth=3.0, lab_r0=14.5, lab_r1=16.5, lab_h=5.5, lab_groove_r0=14.0, lab_groove_r1=17.0, lab_groove_d=2.5,
    spindle_recess=3.0, plug_d=9.0, plug_len=10.0, plug_head_d=12.0, plug_head_t=2.0, lead_groove_w=6.0, lead_groove_d=3.0, lead_groove_angle=60.0,
    gap_drum_boss=2.0, boss_pin_x=3.5,
    # rotor (blade generator settings; the aerodynamic root is the pad top r = 48.2, see system_model_v3)
    r_hub=42.0, c_max=60.0, peak_r=0.58, lg=4.0, db=6.0, tc_root=0.24, tc_tip=0.15, te=1.0, tip_frac=0.55,
)
TO_MEASURE = {
    "motor_pcd / motor_hole / bell_pcd": "GL60 stator-base and bell mounting hole PCDs and threads (manufacturer drawing could not be fetched): the flange and the disc carry BOTH patterns",
    "GL60 lead exit": "where the three phase leads leave the stator base (OD or bore side); the flange channel runs from the OD to the bore so either works",
    "motor_od / motor_len / motor_bore": "confirm 69.0 x 22.3 mm and the 20 mm through-bore on the delivered revision",
    "tube_id": "measure the real 3.0 x 0.065 in tube bore (+-0.15); bore both ends 72.90 H8 x 12 deep and cut the cap O-ring grooves to that",
    "Speedi-Sleeve 99059": "confirm the sleeve width (modelled 6.0) and SKF's advice on an anodised aluminium journal; fallback = run the PTFE lip on the hard-anodised 15 h6 journal (Ra 0.4)",
    "lip seal": "PTFE pressure-rated lip seal in the 15x22x4 (min76) / 15x24x5 (robust) envelope (Trelleborg Varilip PDR or equivalent); confirm availability, else Freudenberg BABSL 15x24x5",
    "DIN 471-15 lug envelope": "confirm the installed outside dimension across the lugs fits the 24 mm recess",
}
P = dict(BASE)

# ----------------------------------------------------------------- helpers
def cyl(x0, L, d): return cq.Workplane("YZ").workplane(offset=x0).circle(d / 2).extrude(L).val()
def tube(x0, L, od, idia): return cq.Workplane("YZ").workplane(offset=x0).circle(od / 2).circle(idia / 2).extrude(L).val()
def torus(x, mean_d, cs): return cq.Workplane("XY").add(cq.Solid.makeTorus(mean_d / 2, cs / 2, cq.Vector(x, 0, 0), cq.Vector(1, 0, 0))).val()
def W(s): return cq.Workplane("XY").add(s)
def rotX(s, deg): return s.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), deg)
def hole_x(d, x0, L, y, z): return cq.Solid.makeCylinder(d / 2, L, cq.Vector(x0, y, z), cq.Vector(1, 0, 0))
def hole_dir(d, L, p, v): return cq.Solid.makeCylinder(d / 2, L, cq.Vector(*p), cq.Vector(*v))
def radial(deg):
    a = math.radians(deg); return (0.0, math.sin(a), math.cos(a))          # unit radial vector at angle deg from +Z toward +Y
def box_x_r(x0, x1, w, r0, r1, deg):
    """box spanning x0..x1, tangential width w (centred), radial r0..r1 at the +Z angle 0, rotated to deg about X"""
    b = cq.Workplane("XY").box(x1 - x0, w, r1 - r0, centered=(False, True, False)).translate((x0, 0, r0)).val()
    return rotX(b, deg)

# ----------------------------------------------------------------- rotor blades (reviewed BEM generator)
def design_blades():
    mb.R_HUB = P["r_hub"]; mb.R_ROOT_EXT = P["r_hub"] - 3.0; mb.C_MAX = P["c_max"]; mb.PEAK_R = P["peak_r"]
    mb.TC_ROOT = P["tc_root"]; mb.TC_TIP = P["tc_tip"]; mb.TE_THICK = P["te"]; mb.TIP_CHORD_FRAC = P["tip_frac"]
    blade = mb.design_blade(P["lg"], P["db"])
    solid, loops, cap_kind = mb.build_blade(blade)
    return blade, solid

def root_section_2d(blade, r):
    """Unrolled (axial X, tangential y) outline of the blade section at radius r (same placement as make_blade.place)."""
    c = float(np.interp(r, blade["r"], blade["chord"])); tw = float(np.interp(r, blade["r"], blade["twist"])); tc = float(np.interp(r, blade["r"], blade["tc"]))
    up, lo = mb.naca4(0.04, 0.40, tc, c)
    pts = np.r_[up[::-1], lo[1:]]
    bt = math.radians(tw)
    xi = pts[:, 0] - mb.PITCH_AXIS * c; eta = pts[:, 1]
    X = xi * math.sin(bt) + eta * math.cos(bt); y = -xi * math.cos(bt) + eta * math.sin(bt)
    return np.c_[X, y], c, tw, tc

def prism_from_outline(pts, x_shift, z0, h, offset=0.0):
    """Planar prism (along +Z from z0, height h) of a closed outline given as (X, y) points; optional 2D offset."""
    wp = cq.Workplane("XY").workplane(offset=z0).polyline([(float(p[0]) + x_shift, float(p[1])) for p in pts]).close()
    if offset:
        wp = wp.offset2D(offset, kind="arc")
    return wp.extrude(h).val()

def offset_outline(pts, d):
    """offset a closed 2D polygon outward by d (vertex-normal offset; the outline is smooth so this is accurate to < 1 % of d)"""
    P2 = np.asarray(pts, float); n = len(P2)
    area = 0.5 * np.sum(P2[:, 0] * np.roll(P2[:, 1], -1) - np.roll(P2[:, 0], -1) * P2[:, 1])
    sgn = 1.0 if area > 0 else -1.0
    out = np.empty_like(P2)
    for i in range(n):
        t = P2[(i + 1) % n] - P2[i - 1]; t /= np.linalg.norm(t)
        nrm = sgn * np.array([t[1], -t[0]])                     # outward normal for a CCW polygon
        out[i] = P2[i] + d * nrm
    return out

def wrap_pts(pts, r):
    """unrolled (X, y) -> 3D on the cylinder of radius r (same mapping as make_blade.place)"""
    X = np.asarray(pts)[:, 0]; y = np.asarray(pts)[:, 1]; th = y / r
    return np.c_[X, r * np.sin(th), r * np.cos(th)]

def resample_outline(pts, min_seg=0.35):
    """drop polygon vertices closer than min_seg to the previous kept vertex (removes the trailing-edge slivers that break Booleans)"""
    out = [pts[0]]
    for q in pts[1:]:
        if np.linalg.norm(np.asarray(q) - np.asarray(out[-1])) >= min_seg:
            out.append(q)
    if np.linalg.norm(np.asarray(out[-1]) - np.asarray(out[0])) < min_seg:
        out.pop()
    return np.asarray(out)

def wrap_wire(pts, r, x_shift=0.0):
    p3 = wrap_pts(resample_outline(pts), r); p3[:, 0] += x_shift
    return cq.Wire.makePolygon([cq.Vector(*map(float, q)) for q in p3], close=True)

def wrapped_spline_wire(pts2d, r, x_shift=0.0):
    """closed wire (upper spline TE->LE, lower spline LE->TE, blunt-TE line) of an unrolled outline wrapped on radius r,
    built like make_blade.section_wire so ruled lofts and filled caps behave the same way as the blade's own root stub"""
    p3 = wrap_pts(pts2d, r); p3[:, 0] += x_shift
    n = (len(p3) + 1) // 2
    V = lambda q: cq.Vector(float(q[0]), float(q[1]), float(q[2]))
    e_up = cq.Edge.makeSpline([V(q) for q in p3[:n]])          # TE(upper) -> LE
    e_lo = cq.Edge.makeSpline([V(q) for q in p3[n - 1:]])      # LE -> TE(lower)
    e_te = cq.Edge.makeLine(V(p3[-1]), V(p3[0]))
    return cq.Wire.assembleEdges([e_up, e_lo, e_te])

def pocket_solid(outline, clear, r_floor, r_top, r_above, x_shift=0.0):
    """airfoil pocket: the outline offset outward by `clear`, ruled between the wrapped rings at r_floor and r_top (the SAME
    ruling span as the blade's tongue, so the clearance is uniform) and on to r_above (through the pad surface); filled end
    caps, sewn (the rings are not planar, so makeLoft's planar caps fail)"""
    po = offset_outline(outline, clear)
    ws = [wrapped_spline_wire(po, r, x_shift) for r in (r_floor, r_top, r_above)]
    faces = mb.thru_sections(ws, ruled=True)
    caps = [cq.Face.makeNSidedSurface(ws[0].Edges(), []), cq.Face.makeNSidedSurface(ws[-1].Edges(), [])]
    sol = mb.sew_solid(faces + caps)
    if not sol.isValid():
        raise RuntimeError("pocket solid invalid")
    return sol

def blade_solid_v3(st, r_floor):
    """blade B-rep from the station wires (smooth loft) + the tongue as a ruled stub from the pad-top ring straight to the
    floor ring, with filled end caps (the generator's cylindrical root cap fails on this wrap and its fallback rules the
    stub from 4 mm below the floor, which no longer matches the pocket)."""
    wires = [mb.section_wire(float(r), float(c), float(tw), float(tc))[0] for r, c, tw, tc in zip(st["r"], st["chord"], st["twist"], st["tc"])]
    w_in = mb.section_wire(r_floor, float(st["chord"][0]), float(st["twist"][0]), float(st["tc"][0]))[0]
    faces = mb.thru_sections(wires, ruled=False) + mb.thru_sections([w_in, wires[0]], ruled=True)
    caps = [cq.Face.makeNSidedSurface(w_in.Edges(), []), cq.Face.makeNSidedSurface(wires[-1].Edges(), [])]
    sol = mb.sew_solid(faces + caps)
    if not sol.isValid():
        raise RuntimeError("blade solid invalid")
    return sol

def blade_root_stations(blade, r_top):
    """blade station arrays restricted to r >= r_top with an interpolated station exactly at r_top"""
    keep = blade["r"] > r_top + 0.3
    out = {}
    for key in ("r", "chord", "twist", "tc"):
        v0 = r_top if key == "r" else float(np.interp(r_top, blade["r"], blade[key]))
        out[key] = np.r_[v0, np.asarray(blade[key])[keep]]
    return out

def outline_extent_at_y(pts, y):
    """length of the outline's interior along X at tangential position y (pin material check)"""
    xs = []
    n = len(pts)
    for i in range(n):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
        if (y1 - y) * (y2 - y) < 0:
            xs.append(x1 + (y - y1) / (y2 - y1) * (x2 - x1))
    return (max(xs) - min(xs)) if len(xs) >= 2 else 0.0

# ----------------------------------------------------------------- caps (hard-anodised 6061-T6)
def cap(x_face, facing, V, kind):
    """facing=+1 front (flange at x_face-t..x_face, plug x_face..+L); facing=-1 rear (plug x_face-L..x_face, flange x_face..x_face+t)."""
    t = V["flange_t"]; L = V["plug_front"] if kind == "front" else V["plug_rear"]; gw = P["oring_groove_w"]; land = P["oring_land"]
    if facing > 0:
        flange = cyl(x_face - t, t, P["tube_od"]); plug_x0 = x_face
    else:
        flange = cyl(x_face, t, P["tube_od"]); plug_x0 = x_face - L
    plug = cyl(plug_x0, L, P["tube_id"] - P["plug_clear"])
    c = W(flange).union(W(plug))
    g_od = P["tube_id"] - P["plug_clear"] - 2 * P["oring_groove_d"]
    if facing > 0:
        xs = [plug_x0 + land + i * V["oring_pitch"] for i in range(V["n_orings"])]
    else:
        xs = [plug_x0 + L - land - gw - i * V["oring_pitch"] for i in range(V["n_orings"])]
    for xg in xs:
        c = c.cut(W(tube(xg, gw, P["tube_id"] + 1, g_od)))
    orings = [torus(xg + gw / 2, g_od + P["oring_cs"], P["oring_cs"]) for xg in xs]
    # lug notches in the flange rim (3x), confined to the flange thickness (do not nick the plug OD)
    for k in range(3):
        xf0 = x_face - t if facing > 0 else x_face
        c = c.cut(W(box_x_r(xf0 - 0.01, xf0 + t + 0.01, P["lug_w"] + 0.3, P["tube_od"] / 2 - P["lug_h"] - 0.3, P["tube_od"] / 2 + 1, 120 * k + 60)))
    if kind == "front":
        x_in = plug_x0 + L
        x_brg = x_in - V["brg_w"] - 0.2
        c = c.cut(W(cyl(x_brg, V["brg_w"] + 0.2 + 1, V["brg_od"])))                        # blind bearing seat, shoulder on the front side, open to the inside
        c = c.cut(W(cyl(x_brg - 2.0, 2.0 + 0.01, 24.0)))                                       # circlip recess (DIN 471-15 incl. lugs) in front of the bearing
        c = c.cut(W(cyl(x_brg - 3.5, 1.5 + 0.01, 16.0)))                                       # nose clearance pocket (nose end 0.3 mm from the floor; the circlip is the stop)
        for k in range(4):   # 4 blind dog pockets in the inner face (drive disc dogs, 0.3 mm clearance), clocked 45 deg from the screws
            a = math.radians(45 + 90 * k)
            c = c.cut(W(hole_x(P["dog_d"] + 0.3, x_in - P["dog_h"] - 0.8, P["dog_h"] + 2, P["disc_pcd_out"] / 2 * math.cos(a), P["disc_pcd_out"] / 2 * math.sin(a))))
        for k in range(3):   # 3x M3 blind tapped in the flange for the dome (4 deep)
            a = math.radians(120 * k)
            c = c.cut(W(hole_x(2.5, x_face - t - 1, 5, (P["tube_od"] / 2 - 9) * math.cos(a), (P["tube_od"] / 2 - 9) * math.sin(a))))
        info = dict(x_brg=x_brg, x_in=x_in)
    else:
        x_in = plug_x0; x_wet = x_face + t
        x_brg = x_wet - V["seal_w"] - P["cap_web"] - V["brg_w"]
        c = c.cut(W(cyl(x_face - 60, 120, 18.0)))                                          # 18 mm wall hole through the web: clears the split thrust ring (17.6) and the sleeve
        c = c.cut(W(cyl(x_wet - V["seal_w"] - 0.01, V["seal_w"] + 1, V["seal_od"])))         # lip-seal seat from the wet face
        c = c.cut(W(cyl(x_in - 1, x_brg + V["brg_w"] - x_in + 1, V["brg_od"])))               # bearing bore open to the inside, shoulder at the rear (thrust)
        c = c.cut(W(tube(x_wet - P["lab_groove_d"], P["lab_groove_d"] + 1, 2 * P["lab_groove_r1"], 2 * P["lab_groove_r0"])))   # labyrinth groove in the wet face
        c = c.cut(W(hole_x(5.2, x_face - 60, 120, 0, P["vent_r"])))                          # M6 vent/vacuum port (Dowty-washer screw)
        c = c.cut(W(hole_x(P["vent_cb_d"], x_wet - P["vent_cb_depth"], P["vent_cb_depth"] + 1, 0, P["vent_r"])))   # vent counterbore (head + washer inside it)
        info = dict(x_brg=x_brg, x_seal=x_wet - V["seal_w"], x_wet=x_wet, x_in=x_in)
    return c.val(), orings, info

# ----------------------------------------------------------------- spindle, boss, plug, drive disc, motor
def spindle(x_front, x_rear, x_flange, x_collar, V):
    s = W(tube(x_front, x_rear - x_front, P["spindle_d"], P["spindle_bore"]))
    s = s.union(W(tube(x_flange, P["sp_flange_t"], P["sp_flange_od"], P["spindle_bore"])))
    for k in range(4):  # stator mount: both GL60 patterns, clearance holes + counterbores on the rear face (screw heads recessed)
        a = math.radians(90 * k)
        for pcd, dh in ((P["bell_pcd"], 3.4), (P["motor_pcd"], 2.9)):
            yz = (pcd / 2 * math.cos(a), pcd / 2 * math.sin(a))
            s = s.cut(W(hole_x(dh, x_flange - 1, P["sp_flange_t"] + 2, *yz)))
            s = s.cut(W(hole_x(P["screw_cb_d"], x_flange + P["sp_flange_t"] - P["screw_cb_depth"], P["screw_cb_depth"] + 1, *yz)))
    # lead channel on the flange FRONT face (under the stator base) from the OD to the bore, and the lead hole into the bore under the flange
    s = s.cut(W(box_x_r(x_flange - 0.01, x_flange + P["lead_channel_d"], P["lead_channel_w"], 5.0, P["sp_flange_od"] / 2 + 1, P["lead_angle"])))
    s = s.cut(W(hole_dir(P["lead_hole_d"], 9.5, (x_flange + P["lead_channel_d"] / 2, 0, 0), radial(P["lead_angle"]))))
    s = s.cut(W(tube(P["x_circlip_front"], P["circlip_w"], P["spindle_d"] + 1, P["circlip_d"])))      # DIN 471-15 groove (14.3 x 1.1), 2.0 mm from the nose end
    s = s.cut(W(tube(x_collar, P["collar_w"], P["spindle_d"] + 1, P["collar_groove_d"])))            # split thrust-ring groove 13.5 x 2.0 behind the rear bearing (+ shim)
    s = s.cut(W(hole_dir(3.1, 40, (P["x_boss_pin"], -20, 0), (0, 1, 0))))                              # boss cross pin (clear of the leads: they leave axially)
    return s.val()

def boss(x0, V):
    b = W(cyl(x0, V["boss_t"], P["boss_od"]))
    b = b.union(W(tube(x0 - P["lab_h"], P["lab_h"] + 0.01, 2 * P["lab_r1"], 2 * P["lab_r0"])))        # labyrinth tongue into the rear-cap groove (non-contact silt excluder)
    b = b.cut(W(cyl(x0 - 10, V["boss_t"] + 20, P["spindle_d"] + 0.05)))
    b = b.cut(W(hole_dir(3.1, 80, (P["x_boss_pin"], -40, 0), (0, 1, 0))))
    # lead groove on the REAR face from the bore to the OD, between struts 0 and 1 (soft-potted; the pressure barrier is the plug)
    b = b.cut(W(box_x_r(x0 + V["boss_t"] - P["lead_groove_d"], x0 + V["boss_t"] + 1, P["lead_groove_w"], 4.0, P["boss_od"] / 2 + 1, P["lead_groove_angle"])))
    for k in range(P["n_struts"]):   # 3 radial strut pockets (through the thickness) with a root pin each
        b = b.cut(W(box_x_r(x0 - 1, x0 + V["boss_t"] + 1, P["strut_t"] + 0.4, P["boss_od"] / 2 - 6, P["boss_od"] / 2 + 1, 120 * k)))
        b = b.cut(W(rotX(hole_dir(3.1, 30, (x0 + V["boss_t"] / 2, -15, P["boss_od"] / 2 - 3), (0, 1, 0)), 120 * k)))
    return b.val()

def potting_plug(x_end):
    """Delrin plug in the reamed 9 H7 spindle rear bore: 3 leads epoxy-potted through a 4.5 mm bore, AS568-010 O-ring, 12 mm head
    captured between the spindle end face and the boss lead groove.  Removable rearward for seal service."""
    pl = W(cyl(x_end - P["plug_len"], P["plug_len"], P["plug_d"] - 0.05)).union(W(cyl(x_end, P["plug_head_t"], P["plug_head_d"])))
    pl = pl.cut(W(cyl(x_end - P["plug_len"] - 1, P["plug_len"] + P["plug_head_t"] + 2, 4.5)))
    pl = pl.cut(W(tube(x_end - P["plug_len"] + 3.0, 2.4, P["plug_d"] + 1, 6.08)))                      # O-ring groove 2.4 wide, 6.08 bottom
    oring = torus(x_end - P["plug_len"] + 3.0 + 1.2, 6.08 + 1.78, 1.78)
    return pl.val(), oring

def drive_disc(x0):
    """TPU 95A disc 3.0 mm bolted to the GL60 bell face (both bell patterns, counterbored heads on the front face) with four dogs
    on disc_pcd_out (clocked 45 deg from the screws) that engage blind pockets in the front cap."""
    d = W(tube(x0, P["disc_t"], P["disc_od"], P["motor_bore"] + 2))
    for k in range(4):
        a = math.radians(90 * k)
        for pcd, dh, cb in ((P["bell_pcd"], 3.4, 6.0), (P["motor_pcd"], 2.9, 5.5)):
            yz = (pcd / 2 * math.cos(a), pcd / 2 * math.sin(a))
            d = d.cut(W(hole_x(dh, x0 - 1, P["disc_t"] + 2, *yz))).cut(W(hole_x(cb, x0 - 1, 1 + P["screw_cb_depth"], *yz)))
        a2 = math.radians(45 + 90 * k)
        dog = cyl(x0 - P["dog_h"], P["dog_h"] + 0.01, P["dog_d"]).translate(cq.Vector(0, P["disc_pcd_out"] / 2 * math.cos(a2), P["disc_pcd_out"] / 2 * math.sin(a2)))
        d = d.union(W(dog))
    return d.val()

def motor(x_front):
    m = W(cyl(x_front, P["motor_len"], P["motor_od"])).cut(W(cyl(x_front - 1, P["motor_len"] + 2, P["motor_bore"])))
    m = m.cut(W(tube(x_front + 9, 1.0, P["motor_od"] + 1, P["motor_od"] - 2)))
    return m.val()

# ----------------------------------------------------------------- carrier segments, blades, dome, struts, duct
def carrier_segment(x0, L, k, V, x_pad, pocket_outline, pin_z):
    """120-degree printed segment with end lips over the cap flanges, a lug at each end, a blade pad with an airfoil-section
    root pocket (2 axial pins), and bolt ears (nut traps on one side) at both parting edges."""
    ri = P["tube_od"] / 2 + 0.2; ro = ri + P["carrier_wall"]
    full = W(tube(x0, L, 2 * ro, 2 * ri))
    lip_in = P["tube_od"] / 2 - 4.0   # lips reach inward over the flange faces
    full = full.union(W(tube(x0, P["carrier_lip"], 2 * ro, 2 * lip_in))).union(W(tube(x0 + L - P["carrier_lip"], P["carrier_lip"], 2 * ro, 2 * lip_in)))
    pad = cq.Workplane("XY").box(P["pad_len"], P["pad_w"], ro + P["pad_h"] + 2 - 30.0, centered=(True, True, False)).translate((x_pad, 0, 30.0)).val()
    full = full.union(W(pad))
    full = full.cut(W(tube(x0 - 5, L + 10, 400, 2 * (ro + P["pad_h"]))))                         # pad top trimmed to the cylinder r = ro + pad_h
    full = full.cut(W(cyl(x0 + P["carrier_lip"], L - 2 * P["carrier_lip"], 2 * ri)))              # bore between the lips (the pad box fills down to the bore)
    r_floor = ro + P["pad_h"] - P["pocket_d"]
    pocket = pocket_solid(pocket_outline, P["pocket_clear"], r_floor, ro + P["pad_h"], ro + P["pad_h"] + 12.0, x_pad)   # airfoil pocket, 0.15 mm clearance per side
    full = full.cut(W(pocket))
    for sgn in (1, -1):   # axial pin holes through both pad walls and the tongue, 3.0 (spring pins 3 x 36, ISO 8752 stainless)
        full = full.cut(W(hole_x(P["pin_d"], x_pad - P["pad_len"] / 2 - 2, P["pad_len"] + 4, sgn * P["pin_y"], pin_z)))
    lugL = V["flange_t"] - 0.4
    for xl in (x0 + P["carrier_lip"], x0 + L - P["carrier_lip"] - lugL):
        lug = cq.Workplane("XY").box(lugL, P["lug_w"], P["lug_h"], centered=(False, True, False)).translate((xl, 0, P["tube_od"] / 2 - P["lug_h"])).val()
        full = full.union(W(lug))
    sector = (cq.Workplane("YZ").workplane(offset=x0 - 5).moveTo(0, 0).lineTo(200 * math.sin(math.radians(-60)), 200 * math.cos(math.radians(-60)))
              .lineTo(0, 200).lineTo(200 * math.sin(math.radians(60)), 200 * math.cos(math.radians(60))).close().extrude(L + 10)).val()
    seg = full.intersect(sector)
    earL = L - 2 * P["carrier_lip"] - 10
    for sgn in (1, -1):
        e = cq.Workplane("XY").box(earL, 7.0, P["carrier_wall"] + 4, centered=(True, True, False)).translate((x0 + L / 2, sgn * 3.5, ri)).val()
        seg = W(seg).union(W(rotX(e, sgn * 60))).val()
        for xb in (x0 + L / 2 - earL / 4, x0 + L / 2 + earL / 4):
            zb = ri + (P["carrier_wall"] + 4) / 2
            seg = W(seg).cut(W(rotX(hole_dir(P["seg_bolt_d"], 20, (xb, -10, zb), (0, 1, 0)), sgn * 60))).val()
            if sgn > 0:   # nut trap on the outer face of the +60 deg ear
                hexp = cq.Workplane("XZ").workplane(offset=-(7.0 + 0.1)).center(xb, zb).polygon(6, P["nut_af"] / math.cos(math.radians(30))).extrude(-(P["nut_h"] + 0.1)).val()
                seg = W(seg).cut(W(rotX(hexp, 60))).val()
    return rotX(seg, 120 * k + 60), ro

def blade_with_tongue(blade, x_pad, ro, pin_z):
    """Blade rebuilt by the reviewed generator from the pad-top station outward; its ruled root stub (the pad-top airfoil
    section extruded radially inward) IS the tongue and fits the radially-extruded carrier pocket with 0.15 mm per side."""
    r_top = ro + P["pad_h"]; r_floor = r_top - P["pocket_d"] + P["pocket_clear"]
    st = blade_root_stations(blade, r_top)
    solid = blade_solid_v3(st, r_floor); cap_kind = "filled caps, stub ruled floor->pad top"
    b = W(solid.translate(cq.Vector(x_pad, 0, 0)))
    for sgn in (1, -1):
        b = b.cut(W(hole_x(P["pin_d"], x_pad - 30, 60, sgn * P["pin_y"], pin_z)))
    return b.val(), st, cap_kind

def blade_print_mesh(blade, outline, x_pad, r_top, z_floor, pin_z, k):
    """Closed structured surface mesh of blade k built directly from the analytic sections (the same NACA/placement code
    as the B-rep loft): rings at r_top (pad top) and every outboard station, tip fan, then the tongue as the unrolled
    r_top outline projected onto the pad cylinder and extruded to the pocket floor.  Avoids the T-junctions the OCC
    tessellation leaves between the loft and the ~100 prism facets.  Pin holes cut with a mesh Boolean (manifold3d).
    Returned in print orientation (pressure side down, span along X, low line levelled, on z = 0)."""
    import trimesh
    st = blade_root_stations(blade, r_top)
    rings = [mb.section_wire(z_floor, float(st["chord"][0]), float(st["twist"][0]), float(st["tc"][0]))[1]]        # tongue floor ring: pad-top section wrapped on the floor cylinder
    for r, c, tw, tc in zip(st["r"], st["chord"], st["twist"], st["tc"]):
        rings.append(mb.section_wire(float(r), float(c), float(tw), float(tc))[1])
    N = len(rings[0])
    seq = rings                                                                                   # bottom (floor) -> top (tip)
    V = np.vstack(seq); V[:, 0] += x_pad
    F = []
    for a in range(len(seq) - 1):
        o0, o1 = a * N, (a + 1) * N
        for i in range(N):
            j = (i + 1) % N
            F.append((o0 + i, o0 + j, o1 + i)); F.append((o0 + j, o1 + j, o1 + i))
    # caps: zipper triangulation between the upper (TE->LE, indices 0..n-1) and lower (LE->TE, n-1..N-1) surface points; the
    # triangles stay on the ring's cylinder within ~0.3 mm (a centroid fan would bulge 3.6 mm inward and add ~4 % volume)
    n = (N + 1) // 2                                        # index of the LE point
    def zipper(o, flip):
        tri = []
        for j in range(n - 1):
            u0, u1 = o + (n - 1 - j), o + (n - 2 - j)        # upper: LE -> TE
            l0, l1 = o + (n - 1 + j), o + (n + j)            # lower: LE -> TE  (l0 == u0 at the LE when j == 0)
            if j == 0:
                tri.append((u0, u1, l1))
            else:
                tri.append((u0, u1, l1)); tri.append((u0, l1, l0))
        return [t[::-1] for t in tri] if flip else tri
    F += zipper(0, flip=False)                               # floor cap
    F += zipper((len(seq) - 1) * N, flip=True)               # tip cap
    m = trimesh.Trimesh(V, np.array(F), process=True)
    m.update_faces(m.nondegenerate_faces(height=1e-7)); m.remove_unreferenced_vertices(); m.fix_normals()
    assert m.is_watertight, "structured blade mesh not closed"
    pins = [trimesh.creation.cylinder(radius=P["pin_d"] / 2, height=80.0, sections=48, transform=trimesh.transformations.concatenate_matrices(
                trimesh.transformations.translation_matrix((x_pad, s_ * P["pin_y"], pin_z)), trimesh.transformations.rotation_matrix(math.pi / 2, (0, 1, 0)))) for s_ in (1, -1)]
    try:
        m2 = trimesh.boolean.difference([m] + pins, engine="manifold")
        if m2.is_watertight and 0.9 * m.volume < m2.volume < m.volume:
            m = m2
        else:
            print("pin-hole boolean rejected; blade STL without pin holes (drill through the carrier)")
    except Exception as exc:
        print(f"pin-hole boolean unavailable ({exc}); blade STL without pin holes (drill through the carrier)")
    # print orientation (same sequence as print_orient for the B-rep)
    R = trimesh.transformations.rotation_matrix
    # the mesh is built un-rotated (blade at +Z) for every k: the three blades are identical prints
    m.apply_transform(R(math.radians(90), (0, 1, 0)))
    m.apply_transform(R(math.pi, (1, 0, 0)))
    xmin, xmax = m.bounds[0][0], m.bounds[1][0]
    def zmin_in(x0, x1):
        sel = (m.vertices[:, 0] >= x0) & (m.vertices[:, 0] <= x1)
        return m.vertices[sel, 2].min()
    xr0 = xmin + P["pocket_d"] + 2.0
    zr = zmin_in(xr0, xr0 + 12.0); zt = zmin_in(xmax - 12.0, xmax)
    tilt = math.atan2(zr - zt, (xmax - 6.0) - (xr0 + 6.0))
    m.apply_transform(R(-tilt, (0, 1, 0)))
    m.apply_transform(trimesh.transformations.translation_matrix(-m.bounds[0]))
    return m, math.degrees(tilt)

def dome(x_base, V):
    r0 = P["tube_od"] / 2 - 4.0 - 0.3; h = V["dome_h"]     # base sits inside the carrier lip ring (lip ID = tube OD - 8)
    t = np.linspace(0, np.pi / 2, 40)
    pts = [(x_base - h * math.sin(a), r0 * math.cos(a)) for a in t[1:]]
    d = (cq.Workplane("XY").moveTo(x_base, 0).lineTo(x_base, r0).spline(pts, includeCurrent=True).close().revolve(360, (0, 0, 0), (1, 0, 0)))   # solid print
    for k in range(3):
        a = math.radians(120 * k)
        yz = ((P["tube_od"] / 2 - 9) * math.cos(a), (P["tube_od"] / 2 - 9) * math.sin(a))
        d = d.cut(W(hole_x(3.4, x_base - 10, 12, *yz)))
        d = d.cut(W(cq.Solid.makeCone(3.4, 0.01, 3.4, cq.Vector(x_base - h * 0.999 + 0.0, yz[0], yz[1]), cq.Vector(1, 0, 0))) ) if False else d
    return d.val()

def strut(k, V):
    """6061-T6 4 mm plate, profile-cut (water-jet/laser), all in one plane: tab in the boss pocket (pinned), cranked jog of strut_jog
    between r_jog0 and r_jog1, 16 mm outer leg through the duct slot into the duct clevis (2x M4 through the thickness)."""
    xc = P["x_boss_c"]; t = P["strut_t"]; w = P["strut_w"]; jog = V["strut_jog"]
    tw = V["boss_t"] - 0.4
    r_in = P["boss_od"] / 2 - 5.8
    r_end = P["duct_od"] / 2 + 10.0
    pts = [(xc - tw / 2, r_in), (xc + tw / 2, r_in), (xc + tw / 2, P["r_jog0"]), (xc - jog + w / 2, P["r_jog1"]), (xc - jog + w / 2, r_end),
           (xc - jog - w / 2, r_end), (xc - jog - w / 2, P["r_jog1"]), (xc - tw / 2, P["r_jog0"])]
    s = cq.Workplane("XZ").polyline(pts).close().extrude(t / 2, both=True)
    for zr in (P["duct_od"] / 2 + 2.5, P["duct_od"] / 2 + 8.0):
        s = s.cut(W(hole_dir(4.3, 20, (xc - jog, -10, zr), (0, 1, 0))))
    s = s.cut(W(hole_dir(3.0, 30, (xc, -15, P["boss_od"] / 2 - 3), (0, 1, 0))))   # root pin
    return rotX(s.val(), 120 * k)

def duct_ring(x0, x1, V):
    ring = W(tube(x0, x1 - x0, P["duct_od"], P["duct_id"]))
    xs = P["x_boss_c"] - V["strut_jog"]
    for k in range(P["n_struts"]):
        cl = box_x_r(xs - P["clevis_len"] / 2, xs + P["clevis_len"] / 2, P["clevis_w"], P["duct_od"] / 2 - 0.5, P["duct_od"] / 2 + 10.5, 120 * k)
        ring = ring.union(W(cl))
        ring = ring.cut(W(box_x_r(xs - P["strut_w"] / 2 - 0.3, xs + P["strut_w"] / 2 + 0.3, P["strut_t"] + 0.6, P["duct_id"] / 2 - 1, P["duct_od"] / 2 + 11, 120 * k)))
        for zr in (P["duct_od"] / 2 + 2.5, P["duct_od"] / 2 + 8.0):
            ring = ring.cut(W(rotX(hole_dir(4.3, 30, (xs, -15, zr), (0, 1, 0)), 120 * k)))
    return ring.val()

# ----------------------------------------------------------------- assembly
def build(variant):
    V = VARIANTS[variant]
    parts = {}
    blade, blade_solid = design_blades()
    x_bc = 0.0                                                       # blade axial centre (defined as X = 0)
    L_tube = V["plug_front"] + V["ic"] + P["disc_t"] + 0.5 + P["motor_len"] + P["sp_flange_t"] + V["ic"] + V["plug_rear"]
    carrier_L = L_tube + 2 * V["flange_t"] + 2 * P["carrier_lip"]
    x_car0 = x_bc - carrier_L / 2 + 4.0                              # bias: blades sit 4 mm forward of the drum centre
    x_ff = x_car0 + P["carrier_lip"] + V["flange_t"]                 # front tube end
    x_fr = x_ff + L_tube                                             # rear tube end
    parts["tube"] = dict(solid=tube(x_ff, L_tube, P["tube_od"], P["tube_id"]), kind="COTS+machined", color=(0.75, 0.75, 0.78),
                         note=f"6061-T6 tube 3.0 in OD x 0.065 in wall, {L_tube:.1f} mm, ends faced, O-ring lands bored 72.90 H8 x 12, hard-anodised")
    fc, fo, finfo = cap(x_ff, +1, V, "front")
    rc, ro_, rinfo = cap(x_fr, -1, V, "rear")
    parts["front_cap"] = dict(solid=fc, kind="machined", color=(0.85, 0.55, 0.2), note=f"6061-T6 front cap (hard-anodised): {V['n_orings']} radial O-ring(s), blind {V['brg']} pocket, 24 mm circlip recess, 4 dog pockets, 3x M3 (dome), 3 lug notches")
    parts["rear_cap"] = dict(solid=rc, kind="machined", color=(0.85, 0.55, 0.2), note=f"6061-T6 rear cap (hard-anodised): {V['n_orings']} radial O-ring(s), {V['brg']} bore, lip seal {V['seal']} seat, labyrinth groove, counterbored M6 vent, 3 lug notches")
    for i, o in enumerate(fo + ro_):
        parts[f"oring_{i}"] = dict(solid=o, kind="COTS", color=(0.1, 0.1, 0.1), note="AS568-147 EPDM 70")
    # spindle from the nose (2 mm beyond the circlip groove) to 3 mm inside the boss rear face
    x_boss0 = x_fr + V["flange_t"] + P["carrier_lip"] + P["gap_drum_boss"]
    x_brg_f = finfo["x_brg"]
    P["x_circlip_front"] = x_brg_f - P["circlip_gap"] - P["circlip_w"]
    x_sp_front = P["x_circlip_front"] - P["circlip_edge"]
    x_sp_rear = x_boss0 + V["boss_t"] - P["spindle_recess"]
    P["x_boss_pin"] = x_boss0 + P["boss_pin_x"]
    P["x_boss_c"] = x_boss0 + V["boss_t"] / 2
    x_disc = x_ff + V["plug_front"] + V["ic"]
    x_motor = x_disc + P["disc_t"] + 0.5
    x_flange = x_motor + P["motor_len"]
    x_brg_r = rinfo["x_brg"]
    x_shim = x_brg_r + V["brg_w"]
    x_collar = x_shim + P["shim_t"]
    parts["spindle"] = dict(solid=spindle(x_sp_front, x_sp_rear, x_flange, x_collar, V), kind="machined", color=(0.55, 0.6, 0.6),
                            note=f"6061-T6 spindle 15 h6 x {x_sp_rear-x_sp_front:.1f} mm, 9 mm bore (rear 15 mm reamed 9 H7), integral stator flange with lead channel, split-ring groove, hard-anodised")
    parts["bearing_front"] = dict(solid=tube(x_brg_f, V["brg_w"], V["brg_od"], P["spindle_d"]), kind="COTS", color=(0.5, 0.5, 0.55), note=f"{V['brg']}-2RS 440C stainless")
    parts["bearing_rear"] = dict(solid=tube(x_brg_r, V["brg_w"], V["brg_od"], P["spindle_d"]), kind="COTS", color=(0.5, 0.5, 0.55), note=f"{V['brg']}-2RS 440C stainless")
    parts["shim_rear"] = dict(solid=tube(x_shim, P["shim_t"], P["collar_od"], P["spindle_d"] + 0.2), kind="COTS", color=(0.7, 0.7, 0.4), note="316 shim 15.2 x 17.6 x 0.3 (pack 0.1/0.2/0.3: sets end play 0.1-0.2)")
    parts["split_collar"] = dict(solid=tube(x_collar + 0.01, P["collar_w"] - 0.02, P["collar_od"], P["collar_groove_d"]), kind="machined", color=(0.55, 0.6, 0.6),
                                 note="316 split thrust ring 17.6 x 13.5 x 2.0 (two halves) in the spindle groove, captured by the cap's 18 mm wall hole")
    x_sleeve = x_collar + P["collar_w"] + 0.1
    parts["speedi_sleeve"] = dict(solid=tube(x_sleeve, P["sleeve_len"], P["sleeve_od"], P["spindle_d"]), kind="COTS", color=(0.8, 0.8, 0.85), note="SKF Speedi-Sleeve 99059 (15 mm), sealant under it")
    parts["lip_seal"] = dict(solid=tube(rinfo["x_seal"], V["seal_w"], V["seal_od"], P["sleeve_od"] - 0.6), kind="COTS", color=(0.2, 0.2, 0.2), note=f"PTFE pressure-rated lip seal {V['seal']} (Varilip PDR class), lip to the water")
    parts["circlip_front"] = dict(solid=tube(P["x_circlip_front"], P["circlip_w"], 19.0, P["circlip_d"]), kind="COTS", color=(0.3, 0.3, 0.3), note="DIN 471-15 stainless circlip (reverse-thrust stop, 0.1 mm gap)")
    pl, plo = potting_plug(x_sp_rear)
    parts["potting_plug"] = dict(solid=pl, kind="machined", color=(0.9, 0.9, 0.6), note="Delrin potting plug 9 f7 x 10 + 12 mm head, leads epoxy-potted (solder-filled strands), AS568-010 O-ring")
    parts["plug_oring"] = dict(solid=plo, kind="COTS", color=(0.1, 0.1, 0.1), note="AS568-010 EPDM")
    parts["drive_disc"] = dict(solid=drive_disc(x_disc), kind="print", color=(0.9, 0.3, 0.3), note="TPU 95A drive disc 3.0 mm with 4 dogs (8 x 4) into the front-cap pockets; counterbored M3/M2.5 to the bell face")
    parts["motor"] = dict(solid=motor(x_motor), kind="COTS", color=(0.25, 0.25, 0.3), note="CubeMars GL60 KV25 envelope 69 x 22.3, 20 mm bore (bell forward)")
    parts["boss"] = dict(solid=boss(x_boss0, V), kind="machined", color=(0.6, 0.6, 0.65), note=f"6061-T6 boss {P['boss_od']:.0f} x {V['boss_t']:.0f}: cross pin, labyrinth tongue, rear lead groove, 3 strut pockets (heat sink)")
    # screw heads (modelled to prove the room): 4 stator (flange rear face), 4 disc (front face), vent
    for k in range(4):
        a = math.radians(90 * k); yz = (P["bell_pcd"] / 2 * math.cos(a), P["bell_pcd"] / 2 * math.sin(a))
        parts[f"screw_stator_{k}"] = dict(solid=hole_x(P["screw_head_d"], x_flange + P["sp_flange_t"] - P["screw_cb_depth"] + 0.1, P["screw_head_h"], *yz), kind="COTS", color=(0.3, 0.3, 0.3), note="M3 low-head cap screw (DIN 7984) head, stator to flange")
        parts[f"screw_disc_{k}"] = dict(solid=hole_x(P["screw_head_d"], x_disc + 0.1, P["screw_head_h"], *yz), kind="COTS", color=(0.3, 0.3, 0.3), note="M3 low-head cap screw head, disc to bell")
    xw = rinfo["x_wet"]
    vent = W(hole_x(10.0, xw - P["vent_cb_depth"] + 0.1, 4.0 + 1.0, 0, P["vent_r"])).union(W(hole_x(5.0, xw - 9.0, 6.5, 0, P["vent_r"]))).val()   # shank overlaps the head: one solid
    parts["vent_screw"] = dict(solid=vent, kind="COTS", color=(0.3, 0.3, 0.3), note="M6 low-head 316 screw + Dowty washer (vent/vacuum port), head in the counterbore")
    # carrier, blades, pins
    x_pad = x_bc
    ri = P["tube_od"] / 2 + 0.2; ro = ri + P["carrier_wall"]; r_top = ro + P["pad_h"]
    outline, c_root, tw_root, tc_root = root_section_2d(blade, r_top)
    pin_z = r_top - P["pin_below_top"]
    th_pin = math.atan2(P["pin_y"], pin_z)
    pin_mat = [outline_extent_at_y(outline, sg * r_top * th_pin) for sg in (1, -1)]                 # material along the axial pin at its angle (unrolled y = r_top * theta)
    seg_x0 = x_car0
    for k in range(3):
        s, _ = carrier_segment(seg_x0, carrier_L, k, V, x_pad, outline, pin_z)
        parts[f"carrier_{k}"] = dict(solid=s, kind="print", color=(0.30, 0.50, 0.80), note="ASA carrier segment (120 deg) with lips, lugs, airfoil root pocket, bolt ears + nut traps")
    for k in range(3):
        b, st_root, cap_kind = blade_with_tongue(blade, x_pad, ro, pin_z)
        parts[f"blade_{k}"] = dict(solid=rotX(b, 120 * k + 60), kind="print", color=(0.35, 0.55, 0.85), note=f"ASA blade with airfoil-section tongue root (2 axial spring pins); root cap {cap_kind}",
                                   blade=blade, outline=outline, x_pad=x_pad, r_top=r_top, z_floor=r_top - P["pocket_d"] + P["pocket_clear"], pin_z=pin_z)
        for sgn in (1, -1):
            pin = hole_x(P["pin_d"], x_pad - P["pad_len"] / 2, P["pad_len"], sgn * P["pin_y"], pin_z)
            parts[f"pin_{k}_{'a' if sgn>0 else 'b'}"] = dict(solid=rotX(pin, 120 * k + 60), kind="COTS", color=(0.4, 0.4, 0.4), note="ISO 8752 3 x 36 stainless spring pin")
    parts["dome"] = dict(solid=dome(x_ff - V["flange_t"], V), kind="print", color=(0.30, 0.50, 0.80), note="ASA dome, 3x M3 316 into the front cap flange")
    for k in range(3):
        parts[f"strut_{k}"] = dict(solid=strut(k, V), kind="metal (profile-cut plate)", color=(0.6, 0.6, 0.65), note=f"6061-T6 4 mm plate strut (water-jet profile): tab in the boss (pinned), {V['strut_jog']:.0f} mm cranked jog, leg into the duct clevis (2x M4)")
    x_duct0 = x_ff - V["flange_t"] - V["dome_h"] + 2.0
    parts["duct"] = dict(solid=duct_ring(x_duct0, x_boss0 + V["boss_t"], V), kind="print/reference", color=(0.8, 0.8, 0.8), note=f"duct/guard ring ID {P['duct_id']:.0f} ({(P['duct_id']-203.2)/2:.1f} mm tip clearance), 3 strut slots + clevises; 3 arcs with lap joints")
    layout = dict(variant=variant, x_blade_centre=x_bc, L_tube=L_tube, carrier_L=carrier_L, x_tube=[x_ff, x_fr], x_front_face=x_ff - V["flange_t"], x_rear_face=x_fr + V["flange_t"],
                  x_dome_tip=x_ff - V["flange_t"] - V["dome_h"], x_boss=[x_boss0, x_boss0 + V["boss_t"]], x_motor=[x_motor, x_flange], x_disc=x_disc, x_spindle=[x_sp_front, x_sp_rear],
                  x_brg_front=x_brg_f, x_brg_rear=x_brg_r, x_seal=rinfo["x_seal"], x_wet=xw, x_collar=x_collar, x_shim=x_shim, x_sleeve=[x_sleeve, x_sleeve + P["sleeve_len"]],
                  x_circlip=P["x_circlip_front"], x_boss_pin=P["x_boss_pin"], x_pad=x_pad, r_hub=ro, r_pad_top=r_top, pin_z=pin_z, pin_material_mm=pin_mat,
                  root_chord_at_pad=c_root, root_twist_at_pad=tw_root, tongue_axial_extent=float(outline[:, 0].max() - outline[:, 0].min()),
                  tongue_tangential_extent=float(outline[:, 1].max() - outline[:, 1].min()), pocket_floor_r=r_top - P["pocket_d"])
    allx = [p["solid"].BoundingBox() for p in parts.values()]
    layout["axial_depth_mm"] = max(b.xmax for b in allx) - min(b.xmin for b in allx)
    layout["axial_depth_no_duct_mm"] = max(b.xmax for n, b in zip(parts, allx) if n != "duct") - min(b.xmin for n, b in zip(parts, allx) if n != "duct")
    layout["axial_depth_duct_mm"] = parts["duct"]["solid"].BoundingBox().xmax - parts["duct"]["solid"].BoundingBox().xmin
    # full pairwise interference check of rigid parts (bounding-box prefilter); flexible/overlapping-by-design parts excluded
    flexible = lambda n: n.startswith("oring") or n in ("lip_seal", "plug_oring")
    names = [n for n in parts if not flexible(n)]
    bbs = {n: parts[n]["solid"].BoundingBox() for n in names}
    inter = {}
    for a, b in itertools.combinations(names, 2):
        A, B = bbs[a], bbs[b]
        if A.xmax < B.xmin - 0.01 or B.xmax < A.xmin - 0.01 or A.ymax < B.ymin - 0.01 or B.ymax < A.ymin - 0.01 or A.zmax < B.zmin - 0.01 or B.zmax < A.zmin - 0.01:
            continue
        try: v = parts[a]["solid"].intersect(parts[b]["solid"]).Volume()
        except Exception: v = -1.0
        if v > 0.01 or v < 0: inter[f"{a}/{b}"] = round(v, 3)
    layout["interference_mm3"] = inter
    layout["pairs_checked"] = sum(1 for _ in itertools.combinations(names, 2))
    return parts, blade, layout

PRINT_ORIENTATION = {
    "dome": "base face down on the bed, no supports; 100 % infill (solid); ASA",
    "drive_disc": "flat on the bed, dogs up (TPU 95A, 100 % infill, no supports; counterbores print as holes from the top)",
    "carrier": "pad up, arc standing like a bridge with its axis along the bed X (the airfoil pocket opens upward and prints without internal support); "
               "brim; tree supports under the arc (bore), lips and ears; ASA, 4 perimeters, 100 % infill in the pad/pocket/ears zone, 40 % gyroid elsewhere. "
               "Axis-vertical was rejected: the pocket roof would be a 39 mm flat overhang needing internal support in a 0.15 mm fit.",
    "blade": "pressure side down with the span along the bed X, tilted about Y so the root and tip low points are level (done in the STL); tongue at the root end lies flat; "
             "organic/tree supports with an interface layer under the leading- and trailing-edge overhangs, brim; ASA, 100 % infill; layers run along the span",
    "duct": "ring axis vertical; three 120-degree arcs with 20 mm lap joints (2x M3 each, laps not modelled) because the ring is 237 mm over the clevises; ASA, 3 perimeters, 30 % infill",
}
def print_orient(name, solid):
    """Rotate a printed part into its print orientation (bed = -Z) and move it onto z = 0."""
    base = name.split("_")[0]; s = solid
    if base == "dome":
        s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), 90)         # +X -> -Z: the dome tip (most -X) points up, base down
    elif base == "drive":
        s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), 90)         # dogs (at -X) end up at +Z (up)
    elif base == "carrier":
        k = int(name.split("_")[1]); s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), -(120 * k + 60))   # pad up (+Z), arc like a bridge, axis along X
    elif base == "duct":
        s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), 90)         # ring axis vertical
    elif base == "blade":
        k = int(name.split("_")[1]); s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), -(120 * k + 60))   # blade along +Z
        s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), 90)         # span -> +X on the bed; downstream (suction) side -> -Z
        s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 180)        # flip: suction side up, pressure side down
        bb = s.BoundingBox()
        # level the pressure-face low line: lowest point of the root region (just outboard of the tongue) vs the tip region
        def zmin_in(x0, x1):
            slab = cq.Workplane("XY").box(x1 - x0, 400, 400, centered=(False, True, True)).translate((x0, 0, 0)).val()
            return s.intersect(slab).BoundingBox().zmin
        xr0 = bb.xmin + P["pocket_d"] + 2.0
        zr = zmin_in(xr0, xr0 + 12.0); zt = zmin_in(bb.xmax - 12.0, bb.xmax)
        tilt = math.degrees(math.atan2(zr - zt, (bb.xmax - 6.0) - (xr0 + 6.0)))
        s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), -tilt)
    bb = s.BoundingBox()
    return s.translate(cq.Vector(-bb.xmin, -bb.ymin, -bb.zmin))

def export(parts, layout, prefix):
    table = []
    assy = cq.Assembly(name=f"v3_{prefix}")
    for name, p in parts.items():
        s = p["solid"]; bb = s.BoundingBox()
        table.append(dict(name=name, kind=p["kind"], note=p["note"], valid=s.isValid(), volume_mm3=round(s.Volume(), 1), x=[round(bb.xmin, 2), round(bb.xmax, 2)],
                          rmax=round(max(abs(bb.ymin), abs(bb.ymax), abs(bb.zmin), abs(bb.zmax)), 2)))
        if not s.isValid(): print("WARNING invalid solid", name)
        if not name.startswith("oring") and not name.startswith("pin_") and not name.startswith("circlip") and not name.startswith("screw_"):
            cq.exporters.export(s, os.path.join(OUT, f"{prefix}_{name}.step"))
        if p["kind"].startswith("print"):
            if name.startswith("blade"):
                k = int(name.split("_")[1])
                m, tilt = blade_print_mesh(p["blade"], p["outline"], p["x_pad"], p["r_top"], p["z_floor"], p["pin_z"], k)
                m.export(os.path.join(OUT, f"{prefix}_{name}_PRINT.stl"))
                table[-1]["stl_watertight"] = bool(m.is_watertight); table[-1]["stl_volume_mm3"] = round(float(m.volume), 1); table[-1]["print_tilt_deg"] = round(tilt, 2)
                table[-1]["stl_vs_step_volume_pct"] = round((m.volume / s.Volume() - 1) * 100, 2)
            else:
                tol, ang = (0.02, 0.05) if name == "dome" else (0.05, 0.2)        # the shallow spline dome needs the fine angular tolerance (0.23 % volume vs 2.4 %)
                wt, nf = mb.write_stl_watertight(print_orient(name, s), os.path.join(OUT, f"{prefix}_{name}_PRINT.stl"), tol, ang)
                table[-1]["stl_watertight"] = bool(wt)
        assy.add(cq.Workplane("XY").add(s), name=name, color=cq.Color(*p["color"]))
    assy.save(os.path.join(OUT, f"{prefix}_assembly.step"))
    bad = {k: v for k, v in layout["interference_mm3"].items() if v > 0.5 or v < 0}
    print(f"[{prefix}] depth incl. duct {layout['axial_depth_mm']:.1f} mm; excl. duct {layout['axial_depth_no_duct_mm']:.1f} mm; tube {layout['L_tube']:.1f}; carrier {layout['carrier_L']:.1f}; "
          f"r_pad_top {layout['r_pad_top']:.1f}; pin material {layout['pin_material_mm'][0]:.1f}/{layout['pin_material_mm'][1]:.1f} mm; tongue {layout['tongue_axial_extent']:.1f} x {layout['tongue_tangential_extent']:.1f}; "
          f"pairs {layout['pairs_checked']}; interference: {'none' if not bad else bad}")
    return table

if __name__ == "__main__":
    info = {}
    for var in ("robust", "min76"):
        parts, blade, layout = build(var)
        info[var] = dict(layout=layout, parts=export(parts, layout, var))
    json.dump(dict(params=BASE, variants=VARIANTS, to_measure=TO_MEASURE, print_orientation=PRINT_ORIENTATION, configs=info), open(os.path.join(OUT, "v3_info.json"), "w"), indent=1)
