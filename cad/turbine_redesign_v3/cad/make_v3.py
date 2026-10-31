#!/usr/bin/env python
"""
Redesign v3: through-spindle drum rotor ("D1").  The hub IS a rotating watertight drum (COTS 6061
tube + two machined Delrin caps + static O-rings) containing a CubeMars GL60 KV25 generator whose
stator is fixed to a stationary aluminium spindle that passes through the motor's 20 mm bore and
leaves the drum through ONE rotary lip seal at the rear.  Printed 3-segment blade carrier with
pinned modular blades, printed dome and struts, aluminium strut boss (heat sink + cable exit).

Frame: +X = flow (water enters at the dome, -X side); rotor axis = X; Z radial up.
Every dimension is in PARAMS; TO_MEASURE lists placeholders.  Two variants: "robust" and "min76".
"""
import json, math, os, sys
import numpy as np
import cadquery as cq
HERE = os.path.dirname(os.path.abspath(__file__))
BLADE_DIR = os.path.join(HERE, "..", "..", "water_turbine_blade")
sys.path.insert(0, BLADE_DIR)
import make_blade as mb
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)

VARIANTS = {
    "robust": dict(brg="6902", brg_od=28.0, brg_w=7.0, dome_h=9.0, boss_t=10.0, flange_t=2.5, ic=1.0, plug_len=13.0, oring_pitch=5.6, seal="15x24x5", seal_od=24.0, seal_w=5.0, strut_jog=14.0),
    "min76":  dict(brg="6702", brg_od=21.0, brg_w=4.0, dome_h=6.0, boss_t=8.0,  flange_t=2.0, ic=0.5, plug_len=11.4, oring_pitch=5.2, seal="15x22x4", seal_od=22.0, seal_w=4.0, strut_jog=14.0),
}
BASE = dict(
    # pressure tube: 6061-T6 3.0 in OD x 0.065 in wall (ID 72.9); length derived
    tube_od=76.2, tube_id=72.9, plug_clear=0.15,
    oring_cs=2.62, oring_groove_w=3.6, oring_groove_d=2.08,      # AS568-147 EPDM 70 (ID 67.95) in a 68.5 mm groove OD
    # generator CubeMars GL60 KV25 (manufacturer per review citation: 69 x 22.3, bore 20, 230 g)
    motor_od=69.0, motor_len=22.3, motor_bore=20.0, motor_pcd=50.0, motor_hole=2.6, bell_pcd=40.0,   # GL60: 4xM3 PCD40 + 4xM2.5 PCD50 (which is stator/bell: TO MEASURE)
    disc_t=2.5, disc_od=62.0, disc_pcd_out=48.0, dog_d=8.0, dog_h=4.0,
    # spindle: 6061-T6 hard-anodised, 15 h6 journals, 9 mm cable bore, integral stator flange
    spindle_d=15.0, spindle_bore=9.0, sp_flange_od=58.0, sp_flange_t=4.0, circlip_w=1.1, circlip_d=14.3,
    # blade carrier (printed, 3 segments) and blade root joint
    carrier_wall=3.9, carrier_lip=2.0, lug_w=6.0, lug_h=3.0, pad_h=6.0, pad_len=36.0, pad_w=30.0, pocket_len=30.0, pocket_w=12.0, pocket_d=7.0,
    pin_d=3.0, pin_x=10.0, seg_bolt_d=3.2, seg_bolt_n=2,
    # strut boss (aluminium), struts (printed), duct/guard
    boss_od=72.0, strut_w=16.0, strut_t=4.0, strut_tab_w=None, n_struts=3, duct_id=207.0, duct_od=213.0, foot_len=22.0, r_jog0=50.0, r_jog1=56.0,
    cable_d=4.5, vent_r=24.0,
    gap_drum_boss=2.0,
    # rotor (blade generator settings)
    r_hub=42.0, c_max=60.0, peak_r=0.58, lg=4.0, db=6.0, tc_root=0.24, tc_tip=0.15, te=1.0, tip_frac=0.55,
)
TO_MEASURE = {
    "motor_pcd / motor_hole": "GL60 stator-base mounting hole PCD and thread (manufacturer drawing could not be fetched in this session)",
    "bell_pcd": "GL60 rotor (bell) face mounting PCD/thread for the TPU drive disc",
    "motor_od / motor_len / motor_bore": "confirm 69.0 x 22.3 mm and the 20 mm through-bore on the delivered revision",
    "tube_id": "measure the real 3.0 x 0.065 in tube bore (+-0.15) and cut the cap O-ring grooves to it",
    "Speedi-Sleeve 99059 on an anodised aluminium journal": "confirm with SKF; fallback = run the lip on the hard-anodised 15 h6 journal (Ra 0.4) and inspect at 2 weeks",
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

# ----------------------------------------------------------------- rotor blades (reviewed BEM generator)
def design_blades():
    mb.R_HUB = P["r_hub"]; mb.R_ROOT_EXT = P["r_hub"] - 3.0; mb.C_MAX = P["c_max"]; mb.PEAK_R = P["peak_r"]
    mb.TC_ROOT = P["tc_root"]; mb.TC_TIP = P["tc_tip"]; mb.TE_THICK = P["te"]; mb.TIP_CHORD_FRAC = P["tip_frac"]
    blade = mb.design_blade(P["lg"], P["db"])
    solid, loops, cap_kind = mb.build_blade(blade)
    return blade, solid

# ----------------------------------------------------------------- caps
def cap(x_face, facing, V, kind):
    """Machined Delrin cap. facing=+1 front (flange at x_face-t..x_face, plug x_face..+plug_len);
    facing=-1 rear (plug x_face-plug_len..x_face, flange x_face..x_face+t). kind: 'front' or 'rear'."""
    t = V["flange_t"]; L = V["plug_len"]
    if facing > 0:
        flange = cyl(x_face - t, t, P["tube_od"]); plug_x0 = x_face
    else:
        flange = cyl(x_face, t, P["tube_od"]); plug_x0 = x_face - L
    plug = cyl(plug_x0, L, P["tube_id"] - P["plug_clear"])
    c = W(flange).union(W(plug))
    g_od = P["tube_id"] - P["plug_clear"] - 2 * P["oring_groove_d"]
    xs = [plug_x0 + 2.0, plug_x0 + 2.0 + V["oring_pitch"]]
    if facing < 0:
        xs = [plug_x0 + L - 2.0 - P["oring_groove_w"], plug_x0 + L - 2.0 - P["oring_groove_w"] - V["oring_pitch"]]
    for xg in xs:
        c = c.cut(W(tube(xg, P["oring_groove_w"], P["tube_id"] + 1, g_od)))
    orings = [torus(xg + P["oring_groove_w"] / 2, g_od + P["oring_cs"], P["oring_cs"]) for xg in xs]
    # lug notches in the flange rim (3x) for the carrier keys
    for k in range(3):
        ang = math.radians(120 * k)
        notch = cq.Workplane("XY").box(t + 2, P["lug_w"] + 0.3, P["lug_h"] + 0.3, centered=(True, True, False)).translate(
            (x_face - t / 2 if facing > 0 else x_face + t / 2, 0, P["tube_od"] / 2 - P["lug_h"] - 0.3)).val()
        c = c.cut(W(rotX(notch, 120 * k + 60)))
    if kind == "front":
        # bearing pocket from the inner face: blind (no through hole = no leak path); shoulder toward the flange
        x_in = plug_x0 + L
        c = c.cut(W(cyl(x_in - V["brg_w"] - 0.2, V["brg_w"] + 0.2 + 1, V["brg_od"])))      # bearing seat, shoulder on the front side
        c = c.cut(W(cyl(x_in - V["brg_w"] - 0.2 - 1.8, 1.9, 20.0)))                        # circlip recess (DIN 471-15 OD 19) in front of the bearing
        for k in range(4):   # 4 blind dog pockets in the inner face (drive disc dogs, 0.3 mm clearance)
            a = math.radians(45 + 90 * k)
            c = c.cut(W(hole_x(P["dog_d"] + 0.3, x_in - P["dog_h"] - 0.8, P["dog_h"] + 2, P["disc_pcd_out"] / 2 * math.cos(a), P["disc_pcd_out"] / 2 * math.sin(a))))
        for k in range(3):   # 3x M3 blind tapped in the flange for the dome
            a = math.radians(120 * k)
            c = c.cut(W(hole_x(2.5, x_face - t - 1, 5, (P["tube_od"] / 2 - 9) * math.cos(a), (P["tube_od"] / 2 - 9) * math.sin(a))))
        info = dict(x_brg=x_in - V["brg_w"] - 0.2)
    else:
        x_in = plug_x0; x_wet = x_face + t
        c = c.cut(W(cyl(x_face - 60, 120, 18.0)))                                          # 18 mm wall hole: clears the spindle collar
        c = c.cut(W(cyl(x_wet - V["seal_w"] - 0.01, V["seal_w"] + 1, V["seal_od"])))         # lip-seal seat from the wet face
        x_brg = x_wet - V["seal_w"] - 1.5 - V["brg_w"]
        c = c.cut(W(cyl(x_in - 1, x_brg + V["brg_w"] - x_in + 1, V["brg_od"])))               # bearing bore open to the inside, shoulder at the rear
        c = c.cut(W(hole_x(5.2, x_face - 60, 120, 0, P["vent_r"])))                          # M6 vent/vacuum port (Dowty-washer screw)
        info = dict(x_brg=x_brg, x_seal=x_wet - V["seal_w"])
    return c.val(), orings, info

# ----------------------------------------------------------------- spindle, boss, drive disc, motor
def spindle(x_front, x_rear, x_flange, V):
    s = W(tube(x_front, x_rear - x_front, P["spindle_d"], P["spindle_bore"]))
    fl = tube(x_flange, P["sp_flange_t"], P["sp_flange_od"], P["spindle_bore"])
    s = s.union(W(fl))
    for k in range(4):  # stator mount holes in the flange (GL60 base PCD, TO MEASURE)
        a = math.radians(45 + 90 * k)
        s = s.cut(W(hole_x(P["motor_hole"] - 0.6, x_flange - 1, P["sp_flange_t"] + 2, P["motor_pcd"] / 2 * math.cos(a), P["motor_pcd"] / 2 * math.sin(a))))
    s = s.cut(W(hole_dir(4.5, 20, (x_flange + P["sp_flange_t"] + 3.5, 0, 0), (0, 0, 1))))     # lead entry into the bore (inside the drum)
    s = s.cut(W(hole_dir(4.5, 20, (x_rear - 4.5, 0, 0), (0, 0, 1))))                          # lead exit inside the boss (potted)
    s = s.cut(W(hole_dir(3.1, 40, (x_rear - V["boss_t"] / 2, -20, 0), (0, 1, 0))))             # boss cross pin
    s = s.cut(W(tube(P["x_circlip_front"], P["circlip_w"], P["spindle_d"] + 1, P["circlip_d"])))   # DIN 471-15 groove (14.3 x 1.1)
    return s.val()

def boss(x0, V):
    b = W(cyl(x0, V["boss_t"], P["boss_od"]))
    b = b.cut(W(cyl(x0 - 1, V["boss_t"] + 2, P["spindle_d"] + 0.05)))
    b = b.cut(W(hole_dir(3.1, 80, (x0 + V["boss_t"] / 2, -40, 0), (0, 1, 0))))
    # cable channel on the rear face from the spindle to strut 0 (at +Z) and 3 strut pockets
    ch = cq.Workplane("XY").box(P["cable_d"] + 1, P["cable_d"] + 1, P["boss_od"] / 2, centered=(True, True, False)).translate((x0 + V["boss_t"] - (P["cable_d"] + 1) / 2, 0, 0)).val()
    b = b.cut(W(ch))
    for k in range(P["n_struts"]):
        pk = cq.Workplane("XY").box(V["boss_t"] + 2, P["strut_t"] + 0.4, 7, centered=(True, True, False)).translate((x0 + V["boss_t"] / 2, 0, P["boss_od"] / 2 - 6)).val()
        b = b.cut(W(rotX(pk, 120 * k)))
        b = b.cut(W(rotX(hole_dir(3.1, 30, (x0 + V["boss_t"] / 2, -15, P["boss_od"] / 2 - 3), (0, 1, 0)), 120 * k)))
    return b.val()

def drive_disc(x0):
    """TPU 95A disc bolted to the GL60 bell face (4x M3 on bell_pcd, heads on the front face) with four dogs
    on disc_pcd_out that engage blind pockets in the front cap: torque transfer with no screws across the cap."""
    d = W(tube(x0, P["disc_t"], P["disc_od"], P["motor_bore"] + 2))
    for k in range(4):
        a = math.radians(45 + 90 * k)
        d = d.cut(W(hole_x(3.4, x0 - 1, P["disc_t"] + 2, P["bell_pcd"] / 2 * math.cos(a), P["bell_pcd"] / 2 * math.sin(a))))
        dog = cyl(x0 - P["dog_h"], P["dog_h"] + 0.01, P["dog_d"]).translate(cq.Vector(0, P["disc_pcd_out"] / 2 * math.cos(a), P["disc_pcd_out"] / 2 * math.sin(a)))
        d = d.union(W(dog))
    return d.val()

def motor(x_front):
    m = W(cyl(x_front, P["motor_len"], P["motor_od"])).cut(W(cyl(x_front - 1, P["motor_len"] + 2, P["motor_bore"])))
    m = m.cut(W(tube(x_front + 9, 1.0, P["motor_od"] + 1, P["motor_od"] - 2)))
    return m.val()

# ----------------------------------------------------------------- carrier segments, blades, dome, struts, duct
def carrier_segment(x0, L, k, V):
    """120-degree printed segment with end lips over the cap flanges, a lug at each end, a blade pad with a
    pinned root pocket, and bolt ears at both parting edges."""
    ri = P["tube_od"] / 2 + 0.2; ro = ri + P["carrier_wall"]
    full = W(tube(x0, L, 2 * ro, 2 * ri))
    lip_in = P["tube_od"] / 2 - 4.0   # lips reach inward over the flange faces
    full = full.union(W(tube(x0, P["carrier_lip"], 2 * ro, 2 * lip_in))).union(W(tube(x0 + L - P["carrier_lip"], P["carrier_lip"], 2 * ro, 2 * lip_in)))
    # blade pad (local solid) at the segment centre
    pad = cq.Workplane("XY").box(P["pad_len"], P["pad_w"], P["pad_h"] + 2, centered=(True, True, False)).translate((x0 + L / 2, 0, ro - 2)).val()
    full = full.union(W(pad))
    full = full.cut(W(tube(x0 - 5, L + 10, 400, 2 * (ro + P["pad_h"]))))      # pad top trimmed to the cylinder r = ro + pad_h
    pocket = cq.Workplane("XY").box(P["pocket_len"], P["pocket_w"], P["pocket_d"] + 1, centered=(True, True, False)).translate((x0 + L / 2, 0, ro + P["pad_h"] - P["pocket_d"])).val()
    full = full.cut(W(pocket))
    for sgn in (1, -1):   # pin holes through the pad walls (tangential), 3.0 H8 after reaming
        full = full.cut(W(hole_dir(3.0, P["pad_w"] + 4, (x0 + L / 2 + sgn * P["pin_x"], -P["pad_w"] / 2 - 2, ro + P["pad_h"] - P["pocket_d"] / 2), (0, 1, 0))))
    # lugs into the flange notches (at the segment centre angle)
    lugL = V["flange_t"] - 0.4
    for xl in (x0 + P["carrier_lip"], x0 + L - P["carrier_lip"] - lugL):
        lug = cq.Workplane("XY").box(lugL, P["lug_w"], P["lug_h"], centered=(False, True, False)).translate((xl, 0, P["tube_od"] / 2 - P["lug_h"])).val()
        full = full.union(W(lug))
    # keep only the 120-degree sector (+-60 deg about +Z), then bolt ears at the two parting planes
    sector = (cq.Workplane("YZ").workplane(offset=x0 - 5).moveTo(0, 0).lineTo(200 * math.sin(math.radians(-60)), 200 * math.cos(math.radians(-60)))
              .lineTo(0, 200).lineTo(200 * math.sin(math.radians(60)), 200 * math.cos(math.radians(60))).close().extrude(L + 10)).val()
    seg = full.intersect(sector)
    for sgn in (1, -1):
        ear = cq.Workplane("XY").box(L - 2 * P["carrier_lip"] - 10, 8.0, P["carrier_wall"] + 5, centered=(True, False, False)).translate((x0 + L / 2, 0, ri)).val()
        ear = rotX(ear, sgn * 60 - (0 if sgn > 0 else 0))
        # ear sits just inside its parting plane
        seg = W(seg).union(W(rotX(ear.translate((0, 0, 0)), 0))).val() if False else seg
    ears = cq.Workplane("XY")
    for sgn in (1, -1):
        e = cq.Workplane("XY").box(L - 2 * P["carrier_lip"] - 10, 7.0, P["carrier_wall"] + 4, centered=(True, True, False)).translate((x0 + L / 2, sgn * 3.5, ri)).val()
        e = rotX(e, sgn * 60)
        seg = W(seg).union(W(e)).val()
        for xb in (x0 + L / 2 - (L - 2 * P["carrier_lip"] - 10) / 4, x0 + L / 2 + (L - 2 * P["carrier_lip"] - 10) / 4):
            h = hole_dir(P["seg_bolt_d"], 20, (xb, -10, ri + (P["carrier_wall"] + 4) / 2), (0, 1, 0))
            seg = W(seg).cut(W(rotX(h, sgn * 60))).val()
    return rotX(seg, 120 * k + 60), ro

def blade_with_tongue(blade_solid, x_c, ro):
    """Blade (from the BEM generator, root trimmed at r_hub-3) fused to a tongue that fits the carrier pocket;
    the blade's own root region below r = ro + pad_h is replaced by the tongue + a solid root block."""
    tongue = cq.Workplane("XY").box(P["pocket_len"] - 0.3, P["pocket_w"] - 0.3, P["pocket_d"] + 1.0, centered=(True, True, False)).translate((x_c, 0, ro + P["pad_h"] - P["pocket_d"] + 0.15)).val()
    keep = cq.Workplane("YZ").workplane(offset=-200).circle(300).circle(ro + P["pad_h"]).extrude(400).val()   # keep blade outside the pad top radius
    bl = blade_solid.intersect(keep)
    b = W(bl).union(W(tongue))
    for sgn in (1, -1):
        b = b.cut(W(hole_dir(3.0, 40, (x_c + sgn * P["pin_x"], -20, ro + P["pad_h"] - P["pocket_d"] / 2), (0, 1, 0))))
    return b.val()

def dome(x_base, V):
    r0 = P["tube_od"] / 2 - 4.0 - 0.3; h = V["dome_h"]     # base sits inside the carrier lip ring (lip ID = tube OD - 8)
    t = np.linspace(0, np.pi / 2, 40)
    pts = [(x_base - h * math.sin(a), r0 * math.cos(a)) for a in t[1:]]
    d = (cq.Workplane("XY").moveTo(x_base, 0).lineTo(x_base, r0).spline(pts, includeCurrent=True).close().revolve(360, (0, 0, 0), (1, 0, 0)))   # solid print
    for k in range(3):
        a = math.radians(120 * k)
        d = d.cut(W(hole_x(3.4, x_base - 10, 12, (P["tube_od"] / 2 - 9) * math.cos(a), (P["tube_od"] / 2 - 9) * math.sin(a))))
    return d.val()

def strut(k, V):
    """6061-T6 flat bar 16 x 4 mm: inner tab (boss_t-0.4 wide) in the boss pocket, a forward jog of strut_jog
    between r_jog0 and r_jog1, outer leg alongside the drum's rear end, a 90-degree foot on the duct outside."""
    xc = P["x_boss_c"]; t = P["strut_t"]; w = P["strut_w"]; jog = V["strut_jog"]
    tab_w = V["boss_t"] - 0.4
    r_in = P["boss_od"] / 2 - 5.8
    inner = cq.Workplane("XY").box(tab_w, t, P["r_jog0"] - r_in, centered=(True, True, False)).translate((xc, 0, r_in))
    # jog: a 45-degree dog-leg approximated by a box spanning the offset
    jogbox = cq.Workplane("XY").box(jog + tab_w, t, P["r_jog1"] - P["r_jog0"], centered=(True, True, False)).translate((xc - jog / 2, 0, P["r_jog0"]))
    r_foot = P["duct_od"] / 2
    outer = cq.Workplane("XY").box(w, t, r_foot + t - P["r_jog1"], centered=(True, True, False)).translate((xc - jog, 0, P["r_jog1"]))
    foot = cq.Workplane("XY").box(w, P["foot_len"], t, centered=(True, False, False)).translate((xc - jog, 0, r_foot + 0.2))
    s = inner.union(jogbox).union(outer).union(foot)
    for dy in (6.0, P["foot_len"] - 6.0):
        s = s.cut(W(hole_dir(4.3, 20, (xc - jog, dy, r_foot - 5), (0, 0, 1))))
    s = s.cut(W(hole_dir(3.0, 30, (xc, -15, P["boss_od"] / 2 - 3), (0, 1, 0))))   # root pin
    return rotX(s.val(), 120 * k)

def duct_ring(x0, x1, V):
    ring = W(tube(x0, x1 - x0, P["duct_od"], P["duct_id"]))
    for k in range(P["n_struts"]):
        slot = cq.Workplane("XY").box(P["strut_w"] + 0.6, P["strut_t"] + 0.6, 12, centered=(True, True, False)).translate((P["x_boss_c"] - V["strut_jog"], 0, P["duct_id"] / 2 - 1)).val()
        ring = ring.cut(W(rotX(slot, 120 * k)))
        for dy in (6.0, P["foot_len"] - 6.0):
            ring = ring.cut(W(rotX(hole_dir(4.3, 30, (P["x_boss_c"] - V["strut_jog"], dy, P["duct_id"] / 2 - 5), (0, 0, 1)), 120 * k)))
    return ring.val()

# ----------------------------------------------------------------- assembly
def build(variant):
    V = VARIANTS[variant]
    parts = {}
    blade, blade_solid = design_blades()
    x_bc = 0.0                                                       # blade axial centre (defined as X = 0)
    # interior stack
    L_tube = V["plug_len"] + V["ic"] + P["disc_t"] + 0.5 + P["motor_len"] + P["sp_flange_t"] + V["ic"] + V["plug_len"]   # dogs overlap the plug (pockets), no extra length
    carrier_L = L_tube + 2 * V["flange_t"] + 2 * P["carrier_lip"]
    x_car0 = x_bc - carrier_L / 2 + 4.0                              # bias: blades sit slightly forward of the drum centre
    x_ff = x_car0 + P["carrier_lip"] + V["flange_t"]                 # front tube end (front flange outer face at x_ff - flange_t)
    x_fr = x_ff + L_tube                                             # rear tube end
    parts["tube"] = dict(solid=tube(x_ff, L_tube, P["tube_od"], P["tube_id"]), kind="COTS", color=(0.75, 0.75, 0.78), note=f"6061-T6 tube 3.0 in OD x 0.065 in wall, {L_tube:.1f} mm, hard-anodised")
    fc, fo, finfo = cap(x_ff, +1, V, "front")
    rc, ro_, rinfo = cap(x_fr, -1, V, "rear")
    parts["front_cap"] = dict(solid=fc, kind="machined", color=(0.85, 0.55, 0.2), note=f"Delrin front cap: 2 radial O-rings, blind {V['brg']} bearing pocket, 4x M3 (disc), 3x M3 (dome), 3 lug notches")
    parts["rear_cap"] = dict(solid=rc, kind="machined", color=(0.85, 0.55, 0.2), note=f"Delrin rear cap: 2 radial O-rings, {V['brg']} bearing bore, lip seal {V['seal']} seat, M6 vent port, 3 lug notches")
    for i, o in enumerate(fo + ro_):
        parts[f"oring_{i}"] = dict(solid=o, kind="COTS", color=(0.1, 0.1, 0.1), note="AS568-147 EPDM 70")
    # spindle from the front bearing to the boss rear
    x_boss0 = x_fr + V["flange_t"] + P["carrier_lip"] + P["gap_drum_boss"]
    x_sp_front = finfo["x_brg"] - 1.7                                # spindle nose reaches through the front circlip
    P["x_circlip_front"] = finfo["x_brg"] - 1.5
    x_sp_rear = x_boss0 + V["boss_t"]
    x_disc = x_ff + V["plug_len"] + V["ic"]
    x_motor = x_disc + P["disc_t"] + 0.5
    x_flange = x_motor + P["motor_len"]
    parts["spindle"] = dict(solid=spindle(x_sp_front, x_sp_rear, x_flange, V), kind="machined", color=(0.55, 0.6, 0.6), note=f"6061-T6 spindle 15 h6 x {x_sp_rear-x_sp_front:.0f} mm, 9 mm bore, integral stator flange, hard-anodised; Speedi-Sleeve 99059 at the seal")
    parts["bearing_front"] = dict(solid=tube(finfo["x_brg"], V["brg_w"], V["brg_od"], P["spindle_d"]), kind="COTS", color=(0.5, 0.5, 0.55), note=f"{V['brg']}-2RS 440C stainless")
    parts["bearing_rear"] = dict(solid=tube(rinfo["x_brg"], V["brg_w"], V["brg_od"], P["spindle_d"]), kind="COTS", color=(0.5, 0.5, 0.55), note=f"{V['brg']}-2RS 440C stainless")
    parts["lip_seal"] = dict(solid=tube(rinfo["x_seal"], V["seal_w"], V["seal_od"], P["spindle_d"] + 0.56 - 0.6), kind="COTS", color=(0.2, 0.2, 0.2), note=f"rotary lip seal {V['seal']} NBR+spring, lip to the water")
    parts["speedi_sleeve"] = dict(solid=tube(rinfo["x_seal"] - 1.0, V["seal_w"] + 2.0, P["spindle_d"] + 0.56, P["spindle_d"]), kind="COTS", color=(0.8, 0.8, 0.85), note="SKF Speedi-Sleeve 99059 (15 mm)")
    parts["circlip_front"] = dict(solid=tube(finfo["x_brg"] - 1.5, P["circlip_w"], 19.0, P["circlip_d"]), kind="COTS", color=(0.3, 0.3, 0.3), note="DIN 471-15 stainless circlip (reverse-thrust stop)")
    parts["spindle_collar"] = dict(solid=tube(rinfo["x_brg"] + V["brg_w"] + 0.1, 1.3, 17.6, P["spindle_d"] - 0.01), kind="machined", color=(0.55, 0.6, 0.6), note="integral spindle collar 17.6 x 1.3 behind the rear bearing (thrust stop), inside the cap's 18 mm wall hole")
    parts["drive_disc"] = dict(solid=drive_disc(x_disc), kind="print", color=(0.9, 0.3, 0.3), note="TPU 95A drive disc 2.5 mm with 4 dogs (8 x 4) into the front-cap pockets; 4x M3 to the bell face")
    parts["motor"] = dict(solid=motor(x_motor), kind="COTS", color=(0.25, 0.25, 0.3), note="CubeMars GL60 KV25 envelope 69 x 22.3, 20 mm bore (bell forward)")
    parts["boss"] = dict(solid=boss(x_boss0, V), kind="machined", color=(0.6, 0.6, 0.65), note=f"6061-T6 boss {P['boss_od']:.0f} x {V['boss_t']:.0f}: spindle clamp pin, cable channel, strut pockets (heat sink)")
    seg_x0 = x_car0
    ro = None
    for k in range(3):
        s, ro = carrier_segment(seg_x0, carrier_L, k, V)
        parts[f"carrier_{k}"] = dict(solid=s, kind="print", color=(0.30, 0.50, 0.80), note="ASA carrier segment (120 deg) with lips, lugs, blade pad/pocket, bolt ears")
    x_pad_c = seg_x0 + carrier_L / 2
    for k in range(3):
        b = blade_with_tongue(blade_solid, x_pad_c, ro)
        parts[f"blade_{k}"] = dict(solid=rotX(b, 120 * k + 60) if k else rotX(b, 60), kind="print", color=(0.35, 0.55, 0.85), note="ASA blade with pinned tongue root")
        for sgn in (1, -1):
            pin = hole_dir(3.0, P["pad_w"] + 2, (x_pad_c + sgn * P["pin_x"], -P["pad_w"] / 2 - 1, ro + P["pad_h"] - P["pocket_d"] / 2), (0, 1, 0))
            parts[f"pin_{k}_{'a' if sgn>0 else 'b'}"] = dict(solid=rotX(pin, 120 * k + 60), kind="COTS", color=(0.4, 0.4, 0.4), note="3 x 32 mm 316 dowel pin")
    parts["dome"] = dict(solid=dome(x_ff - V["flange_t"], V), kind="print", color=(0.30, 0.50, 0.80), note="ASA dome, 3x M3 316 into the front cap flange")
    P["x_boss_c"] = x_boss0 + V["boss_t"] / 2
    for k in range(3):
        parts[f"strut_{k}"] = dict(solid=strut(k, V), kind="metal (cut+bent flat bar)", color=(0.6, 0.6, 0.65), note=f"6061-T6 flat bar 16 x 4: tab in the boss (pinned), {V['strut_jog']:.0f} mm forward jog, foot bolted outside the duct (2x M4)")
    parts["duct"] = dict(solid=duct_ring(x_bc - 22.0, x_sp_rear, V), kind="print/reference", color=(0.8, 0.8, 0.8), note="duct/guard ring ID 207 (1.9 mm tip clearance), strut slots, feet outside")
    layout = dict(variant=variant, x_blade_centre=x_bc, L_tube=L_tube, carrier_L=carrier_L, x_tube=[x_ff, x_fr], x_front_face=x_ff - V["flange_t"], x_rear_face=x_fr + V["flange_t"],
                  x_dome_tip=x_ff - V["flange_t"] - V["dome_h"], x_boss=[x_boss0, x_sp_rear], x_motor=[x_motor, x_flange], x_disc=x_disc,
                  x_brg_front=finfo["x_brg"], x_brg_rear=rinfo["x_brg"], x_seal=rinfo["x_seal"], r_hub=ro, r_pad_top=ro + P["pad_h"])
    allx = [p["solid"].BoundingBox() for p in parts.values()]
    layout["axial_depth_mm"] = max(b.xmax for b in allx) - min(b.xmin for b in allx)
    layout["axial_depth_no_duct_mm"] = max(b.xmax for n, b in zip(parts, allx) if n != "duct") - min(b.xmin for n, b in zip(parts, allx) if n != "duct")
    layout["axial_depth_duct_mm"] = parts["duct"]["solid"].BoundingBox().xmax - parts["duct"]["solid"].BoundingBox().xmin
    # interference checks (rigid parts only; O-rings and seal lips are intentionally undeformed)
    pairs = [("motor","front_cap"),("motor","rear_cap"),("motor","tube"),("motor","spindle"),("drive_disc","front_cap"),("drive_disc","motor"),("spindle","front_cap"),("spindle","rear_cap"),
             ("front_cap","tube"),("rear_cap","tube"),("carrier_0","tube"),("carrier_0","front_cap"),("carrier_0","rear_cap"),("carrier_0","carrier_1"),("carrier_1","carrier_2"),
             ("blade_0","carrier_0"),("blade_1","carrier_1"),("blade_0","tube"),("dome","front_cap"),("dome","carrier_0"),("boss","rear_cap"),("boss","spindle"),("strut_0","boss"),
             ("strut_0","duct"),("strut_1","duct"),("bearing_front","front_cap"),("bearing_rear","rear_cap"),("bearing_front","spindle"),("circlip_front","front_cap"),
             ("pin_0_a","carrier_0"),("pin_0_a","blade_0"),("blade_0","duct"),("blade_0","dome"),("lip_seal","rear_cap"),("speedi_sleeve","rear_cap"),("spindle","bearing_rear"),("spindle_collar","rear_cap"),
             ("spindle_collar","bearing_rear"),("spindle_collar","lip_seal"),("strut_0","carrier_0"),("strut_0","blade_0"),("strut_0","carrier_1"),("strut_1","blade_1"),("boss","carrier_0"),("dome","blade_0"),("carrier_0","blade_1"),("circlip_front","spindle"),("strut_0","tube"),("strut_1","blade_0"),("strut_2","blade_2")]
    inter = {}
    for a, b in pairs:
        try: inter[f"{a}/{b}"] = round(parts[a]["solid"].intersect(parts[b]["solid"]).Volume(), 2)
        except Exception: inter[f"{a}/{b}"] = -1.0
    layout["interference_mm3"] = inter
    return parts, blade, layout

PRINT_ORIENTATION = {
    "dome": "base face down on the bed, no supports; 100 % infill (solid); ASA",
    "drive_disc": "flat on the bed, dogs up (TPU 95A, 100 % infill, no supports)",
    "carrier": "pad up, arc standing like a bridge with its axis along the bed X (pocket opening faces up); tree supports under the arc, lips and ears; ASA, 4 perimeters, 100 % infill in the pad/pocket/ears zone, 40 % gyroid elsewhere",
    "blade": "pressure side down with the span along the bed X axis and the tongue up; tree supports only under the leading-edge overhang; ASA, 100 % infill; layers run along the span",
    "duct": "ring axis vertical; print as three 120-degree arcs if the bed is smaller than 215 mm; ASA, 3 perimeters, 30 % infill",
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
        s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), 90)         # span -> +X on the bed; chord plane ~ horizontal; tongue toward +Z? check
        bb = s.BoundingBox()
        # make the tongue face up: the tongue is at the smallest radius -> after rotation at the smallest x; flip about X so the pressure side is down
        s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 180)
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
        if not name.startswith("oring") and not name.startswith("pin_") and not name.startswith("circlip"):
            cq.exporters.export(s, os.path.join(OUT, f"{prefix}_{name}.step"))
        if p["kind"].startswith("print"):
            tol, ang = (0.02, 0.1) if name.startswith("blade") else (0.05, 0.2)     # blades: finer tessellation so the repair keeps the volume
            wt, nf = mb.write_stl_watertight(print_orient(name, s), os.path.join(OUT, f"{prefix}_{name}_PRINT.stl"), tol, ang)
            table[-1]["stl_watertight"] = wt
        assy.add(cq.Workplane("XY").add(s), name=name, color=cq.Color(*p["color"]))
    assy.save(os.path.join(OUT, f"{prefix}_assembly.step"))
    bad = {k: v for k, v in layout["interference_mm3"].items() if v > 0.5 or v < 0}
    print(f"[{prefix}] depth incl. duct {layout['axial_depth_mm']:.1f} mm; excl. duct {layout['axial_depth_no_duct_mm']:.1f} mm; tube {layout['L_tube']:.1f}; carrier {layout['carrier_L']:.1f}; r_hub {layout['r_hub']:.1f}; "
          f"interference: {'none' if not bad else bad}")
    return table

if __name__ == "__main__":
    info = {}
    for var in ("robust", "min76"):
        parts, blade, layout = build(var)
        info[var] = dict(layout=layout, parts=export(parts, layout, var))
    json.dump(dict(params=BASE, variants=VARIANTS, to_measure=TO_MEASURE, configs=info), open(os.path.join(OUT, "v3_info.json"), "w"), indent=1)
