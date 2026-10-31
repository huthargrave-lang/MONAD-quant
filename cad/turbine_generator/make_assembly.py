#!/usr/bin/env python
"""
Parametric turbine-generator assembly (architecture B: hub-integrated generator in a rotating
COTS watertight drum on a stationary spindle).  Every dimension lives in PARAMS; values that
must be measured on the physical motor or confirmed against vendor drawings are flagged in
TO_MEASURE.  Exports STEP per part + one assembly STEP, STL for printed parts, and a parts
table used by the BOM/report generators.

Frame: +X = flow direction (water enters at the nose, -X side), rotor axis = X, Z radial up.
"""
import json, math, os, sys
import numpy as np
import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
BLADE_DIR = os.path.join(HERE, "..", "water_turbine_blade")
sys.path.insert(0, BLADE_DIR)
import make_blade as mb                      # blade generator (reviewed rev 2)

OUT = os.path.join(HERE, "cad_out"); os.makedirs(OUT, exist_ok=True)

PARAMS = dict(
    # ---- pressure tube: stock 6061-T6 2.5 in OD x 0.065 in wall (the 49 mm motor does not fit a BR 2 in tube) ----
    tube_od=63.5, tube_id=60.2,                              # mm; tube length is derived from the stack
    cap_flange_od=63.5, cap_flange_t=6.0, cap_plug_len=18.0, # machined cap: flange outside, plug inside with 2 radial O-rings
    oring_cs=2.62, oring_groove_w=3.6, oring_groove_d=2.08,  # AS568 -1xx radial gland, Parker: depth 2.06-2.11 (17-24 % squeeze)
    oring_pitch=7.0,                                         # two radial O-rings per plug (AS568-139 EPDM 70)
    cap_screw_d=3.2, cap_screws=3,                           # 3x M3 316 radial screws through the tube into the plug, dry side of the O-rings
    # ---- configuration A (stationary nacelle behind the rotor), generator CubeMars GL60 KV25 ----
    a_tube_od=80.0, a_tube_id=75.0, a_cap_plug_len=18.0,     # 6061/6060 tube 80 x 2.5 mm (or 3.0 in x 0.049 in, ID 73.7)
    a_motor_od=69.0, a_motor_len=22.3, a_motor_bore=20.0, a_motor_pcd=48.0, a_motor_hole=3.4,   # GL60: 69 x 22.3, 20 mm bore [verified]; PCD/thread TO MEASURE
    a_bell_pcd=30.0, a_bell_adapter_t=6.0,                   # bell-face bolt PCD TO MEASURE; Delrin adapter with 12 mm stub
    a_shaft_d=12.0, a_shaft_hub_in=42.0, a_seal_od=22.0, a_seal_w=7.0, a_brg_od=28.0, a_brg_w=8.0, a_brg_n=2,   # 6001-2RS, seal 12x22x7, Speedi-Sleeve 99047
    a_sleeve_w=8.0, a_coup_od=20.0, a_coup_len=25.0, a_gap_hub_cap=3.0, a_collar_od=20.0, a_collar_len=8.0,
    a_penetrator_d=10.0, a_penetrator_r=24.0, a_clamp_w=16.0, a_clamp_t=5.0, a_oring_pitch=7.0,
    # ---- rotary seal + bearings on the stationary spindle (rear cap) ----
    spindle_d=15.0, spindle_bore=9.0, spindle_len=78.0,      # 316 tube; cable runs through the bore
    seal_od=24.0, seal_w=5.0,                                # lip seal 15x24x5 (NBR or PTFE)
    brg_od=28.0, brg_w=7.0, brg_n=2,                         # 2x 6902-2RS (15x28x7) back to back
    circlip_groove_w=1.1, circlip_groove_d=0.6,              # DIN 471 for d=15 (14.3 groove dia)
    # ---- motor placeholder (GB5015) ----
    motor_od=49.0, motor_len=29.0, motor_base_t=4.0,         # published: ~49 x 29 mm
    motor_pcd=25.0, motor_hole=3.2, motor_shaft_d=8.0, motor_shaft_l=8.0,   # TO MEASURE
    motor_hollow_d=0.0,                                      # TO MEASURE (0 = not hollow)
    # ---- stator mount: flanged 316 shaft collar on the spindle + printed/Delrin adapter plate ----
    collar_od=22.0, collar_len=10.0, collar_flange_od=40.0, collar_flange_t=4.0,
    adapter_od=48.0, adapter_t=5.0,
    # ---- drive from the motor bell to the drum front cap: compliant (TPU) drive disc on the bell face ----
    disc_od=40.0, disc_t=2.5, bell_pcd=19.0,                 # bell-face holes PCD TO MEASURE
    # ---- rotor (blade ring + 3 blades), nose ----
    ring_wall=3.6, ring_len=52.0, nose_len=18.0,
    # ---- strut hub, struts, duct interface ----
    hub_boss_od=38.0, hub_boss_len=22.0, strut_chord=18.0, strut_tc=0.15, n_struts=3,
    duct_id=206.0, duct_od=214.0, duct_len=40.0, pad_w=22.0, pad_len=30.0,
    gap_rotor_boss=3.0, rear_plug_len=17.0, internal_clearance=1.5,
)
P = PARAMS
TO_MEASURE = {
    "motor_pcd": "GB5015 base mounting hole pitch circle (4 holes?) - from the motor or vendor drawing",
    "motor_hole": "mounting hole thread/size (M2.5 or M3)",
    "motor_shaft_d / motor_shaft_l": "shaft diameter and protrusion on the bell side (and any flat/thread)",
    "motor_hollow_d": "bore of the hollow shaft if present (decides whether the spindle can pass through)",
    "motor_od / motor_len": "confirm 49 x 29 mm overall and where the cable exits the base",
    "tube_* / cap_*": "Blue Robotics 2 inch series tube ID/OD and end-cap flange/plug dimensions from the vendor drawing",
    "motor Kv, line resistance, cogging torque, mass": "electrical model inputs (see REPORT)",
}

# =============================================================== rotor (blades on the drum)
def build_rotor_ring():
    """Blade set regenerated for the larger hub radius (tube OD/2 + ring wall), fused to a printed
    ring that slips over the drum tube.  Returns (ring_with_blades, blade_design, cp15)."""
    r_hub = P["tube_od"] / 2 + P["ring_wall"]
    mb.R_HUB = r_hub; mb.R_ROOT_EXT = r_hub - 3.5
    # quick re-optimisation of the pitch/planform for the new hub (coarse, like the reviewed generator)
    lam_scan = np.arange(2.0, 5.51, 0.25)
    best = None
    for lg in (3.0, 4.0, 5.0):
        for db in (4.0, 6.0, 8.0):
            bl = mb.design_blade(lg, db)
            cps = [mb.bem(bl, l, 1.5, n_el=40)["cp"] for l in lam_scan]
            j = int(np.argmax(cps))
            if best is None or cps[j] > best[0]:
                best = (cps[j], lg, db, lam_scan[j])
    cp15, lg, db, lam_op = best
    blade = mb.design_blade(lg, db)
    blade_solid, loops, cap_kind = mb.build_blade(blade)
    x_c = 0.5 * (blade["r"][0] and 0 or 0)  # placeholder (unused)
    verts, _ = blade_solid.tessellate(0.1, 0.3)
    xs = [v.x for v in verts]; x0 = 0.5 * (min(xs) + max(xs))     # blade axial centre
    ring = (cq.Workplane("YZ").workplane(offset=x0 - P["ring_len"] / 2)
            .circle(r_hub).circle(P["tube_od"] / 2 + 0.15).extrude(P["ring_len"]))
    rotor = ring
    for k in range(3):
        rotor = rotor.union(cq.Workplane("XY").add(blade_solid.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 120 * k)))
    # trim anything inside the ring bore (blade stubs) and outside the ring length
    bore = cq.Workplane("YZ").workplane(offset=-200).circle(P["tube_od"] / 2 + 0.15).extrude(400)
    rotor = rotor.cut(bore)
    perf = {V: mb.bem(blade, lam_op, V) for V in (1.0, 1.5, 2.0)}
    return rotor.val(), blade, dict(cp15=cp15, lam=float(lam_op), lg=lg, db=db, r_hub=r_hub, x0=x0,
                                   perf={str(V): dict(rpm=r["rpm"], P=r["P"], Q=r["Q"], T=r["T"], cp=r["cp"]) for V, r in perf.items()})

# =============================================================== drum (tube + caps), seals, bearings
def tube(x0, length, od, idia):
    return cq.Workplane("YZ").workplane(offset=x0).circle(od / 2).circle(idia / 2).extrude(length).val()

def cylinder(x0, length, d):
    return cq.Workplane("YZ").workplane(offset=x0).circle(d / 2).extrude(length).val()

def oring_torus(x, mean_d, cs):
    return cq.Workplane("XY").add(cq.Solid.makeTorus(mean_d / 2, cs / 2, cq.Vector(x, 0, 0), cq.Vector(1, 0, 0))).val()

def end_cap(x_face, facing, plug_len=None):
    """COTS-style end cap: flange (outside the tube) + plug (inside, 2 radial O-ring grooves).
    facing=+1: plug extends toward +X from the flange (front cap); -1: toward -X (rear cap)."""
    f = facing
    plug_len = plug_len or P["cap_plug_len"]
    # x_face is the tube end; the flange sits OUTSIDE the tube, the plug inside it
    flange = cylinder(x_face - P["cap_flange_t"] if f > 0 else x_face, P["cap_flange_t"], P["cap_flange_od"])
    plug_x0 = x_face if f > 0 else x_face - plug_len
    plug = cylinder(plug_x0, plug_len, P["tube_id"] - 0.1)
    cap = cq.Workplane("XY").add(flange).union(cq.Workplane("XY").add(plug))
    # two O-ring grooves
    g_d = P["tube_id"] - 0.1 - 2 * P["oring_groove_d"]
    xs = [plug_x0 + 3.0, plug_x0 + 3.0 + P["oring_pitch"]]
    for xg in xs:
        groove = tube(xg, P["oring_groove_w"], P["tube_id"] + 1, g_d)
        cap = cap.cut(cq.Workplane("XY").add(groove))
    orings = [oring_torus(xg + P["oring_groove_w"] / 2, g_d + P["oring_cs"], P["oring_cs"]) for xg in xs]
    return cap.val(), orings, plug_x0

def rear_cap(x_face):
    """Custom machined rear cap (Delrin or 6061): same flange/plug/O-rings as a COTS cap, plus the
    spindle bore with a lip-seal seat (wet side, outboard) and the bearing bore (dry side)."""
    cap, orings, plug_x0 = end_cap(x_face, -1, P["rear_plug_len"])
    w = cq.Workplane("XY").add(cap)
    x_wet = x_face + P["cap_flange_t"]                                        # wet face of the rear cap
    through = cylinder(x_face - 60, 120, P["spindle_d"] + 1.0)              # clearance bore
    w = w.cut(cq.Workplane("XY").add(through))
    seal_seat = cylinder(x_wet - P["seal_w"], P["seal_w"] + 0.01, P["seal_od"])   # lip seal from the wet face
    w = w.cut(cq.Workplane("XY").add(seal_seat))
    brg_len = P["brg_n"] * P["brg_w"]
    brg_seat = cylinder(x_wet - P["seal_w"] - 1.5 - brg_len, brg_len, P["brg_od"])  # 1.5 mm wall between seal and bearings
    w = w.cut(cq.Workplane("XY").add(brg_seat))
    x_seal = x_wet - P["seal_w"]; x_brg = x_wet - P["seal_w"] - 1.5 - brg_len
    return w.val(), orings, dict(x_seal=x_seal, x_brg=x_brg, brg_len=brg_len)

def lip_seal(x0):
    return tube(x0, P["seal_w"], P["seal_od"], P["spindle_d"] - 0.6)

def bearing(x0):
    return tube(x0, P["brg_w"], P["brg_od"], P["spindle_d"])

# =============================================================== spindle, collar, adapter, motor, coupling
def spindle(x_rear_end):
    sp = tube(x_rear_end - P["spindle_len"], P["spindle_len"], P["spindle_d"], P["spindle_bore"])
    # side hole for the stator leads to enter the bore (dry side), 4 mm
    hole = cq.Solid.makeCylinder(2.0, 20, cq.Vector(x_rear_end - P["spindle_len"] + 24, 0, 0), cq.Vector(0, 0, 1))
    return cq.Workplane("XY").add(sp).cut(cq.Workplane("XY").add(hole)).val()

def flanged_collar(x0):
    body = cylinder(x0, P["collar_len"], P["collar_od"])
    fl = cylinder(x0, P["collar_flange_t"], P["collar_flange_od"])
    c = cq.Workplane("XY").add(body).union(cq.Workplane("XY").add(fl)).cut(cq.Workplane("XY").add(cylinder(x0 - 1, P["collar_len"] + 2, P["spindle_d"])))
    return c.val()

def adapter_plate(x0):
    pl = cq.Workplane("YZ").workplane(offset=x0).circle(P["adapter_od"] / 2).extrude(P["adapter_t"])
    pl = pl.cut(cq.Workplane("XY").add(cylinder(x0 - 1, P["adapter_t"] + 2, P["collar_od"] + 0.4)))
    for k in range(4):   # motor holes (PCD TO MEASURE) and collar flange holes
        a = math.radians(45 + 90 * k)
        for pcd, d in ((P["motor_pcd"], P["motor_hole"]), (P["collar_flange_od"] - 8, 3.4)):
            h = cq.Solid.makeCylinder(d / 2, P["adapter_t"] + 2, cq.Vector(x0 - 1, pcd / 2 * math.cos(a), pcd / 2 * math.sin(a)), cq.Vector(1, 0, 0))
            pl = pl.cut(cq.Workplane("XY").add(h))
    return pl.val()

def motor(x_base):
    """Placeholder GB5015: base plate (stator side) at x_base, bell toward -X, shaft further -X."""
    base = cylinder(x_base - P["motor_base_t"], P["motor_base_t"], P["motor_od"] - 2)
    bell = cylinder(x_base - P["motor_len"], P["motor_len"] - P["motor_base_t"] - 0.5, P["motor_od"])
    shaft = cylinder(x_base - P["motor_len"] - P["motor_shaft_l"], P["motor_shaft_l"] + 1, P["motor_shaft_d"])
    m = cq.Workplane("XY").add(base).union(cq.Workplane("XY").add(bell)).union(cq.Workplane("XY").add(shaft))
    if P["motor_hollow_d"] > 0:
        m = m.cut(cq.Workplane("XY").add(cylinder(x_base - 60, 120, P["motor_hollow_d"])))
    return m.val()

def drive_disc(x0):
    """TPU/elastomer disc bolted to the motor bell face and to the front-cap plug: transmits torque,
    tolerates ~0.3 mm radial/axial mismatch between the motor's own bearings and the drum bearings."""
    d = cq.Workplane("YZ").workplane(offset=x0).circle(P["disc_od"] / 2).circle(P["motor_shaft_d"] / 2 + 1).extrude(P["disc_t"])
    for k in range(4):
        a = math.radians(45 + 90 * k)
        for pcd in (P["bell_pcd"], P["disc_od"] - 8):
            d = d.cut(cq.Workplane("XY").add(cq.Solid.makeCylinder(1.7, P["disc_t"] + 2, cq.Vector(x0 - 1, pcd / 2 * math.cos(a), pcd / 2 * math.sin(a)), cq.Vector(1, 0, 0))))
    return d.val()

# =============================================================== nose, strut hub, struts, duct ring
def nose(x_face):
    t = np.linspace(0, np.pi / 2, 40)
    r0 = P["tube_od"] / 2 + P["ring_wall"]
    pts = [(x_face - P["nose_len"] * math.sin(a), r0 * math.cos(a)) for a in t[1:]]
    n = (cq.Workplane("XY").moveTo(x_face, 0).lineTo(x_face, r0).spline(pts, includeCurrent=True).close()
         .revolve(360, (0, 0, 0), (1, 0, 0)))
    # hollow it (3 mm wall) and leave a flat for the cap bolts
    inner = (cq.Workplane("XY").moveTo(x_face, 0).lineTo(x_face, r0 - 3)
             .spline([(x_face - (P["nose_len"] - 3) * math.sin(a), (r0 - 3) * math.cos(a)) for a in t[1:]], includeCurrent=True).close()
             .revolve(360, (0, 0, 0), (1, 0, 0)))
    return n.cut(inner).val()

def strut_hub(x0):
    boss = cylinder(x0, P["hub_boss_len"], P["hub_boss_od"])
    w = cq.Workplane("XY").add(boss).cut(cq.Workplane("XY").add(cylinder(x0 - 1, P["hub_boss_len"] + 2, P["spindle_d"] + 0.2)))
    # split-clamp slot and two M4 clamp bolts (represented as holes)
    slot = cq.Workplane("XY").box(P["hub_boss_len"] + 2, 1.5, P["hub_boss_od"] / 2 + 2, centered=(False, True, False)).translate((x0 - 1, 0, 0)).val()
    w = w.cut(cq.Workplane("XY").add(slot))
    for xb in (x0 + 7, x0 + P["hub_boss_len"] - 7):
        h = cq.Solid.makeCylinder(2.2, P["hub_boss_od"], cq.Vector(xb, -P["hub_boss_od"] / 2, P["hub_boss_od"] / 2 - 6), cq.Vector(0, 1, 0))
        w = w.cut(cq.Workplane("XY").add(h))
    # potting cavity for the cable exit at the rear
    pot = cylinder(x0 + P["hub_boss_len"] - 8, 9, 14.0)
    w = w.cut(cq.Workplane("XY").add(pot))
    return w.val()

def strut(x_c, k):
    """NACA 00xx strut from the boss to the duct pad, at angle 120*k about X (k=0 points +Z)."""
    c = P["strut_chord"]; tc = P["strut_tc"]
    up, lo = mb.naca4(0.0, 0.4, tc, c, n=40, te_thick=0.6)
    prof = np.r_[up[::-1], lo[1:]]
    pts = [(float(x_c - 0.4 * c + p[0]), float(p[1])) for p in prof]
    r_in = P["hub_boss_od"] / 2 - 2; r_out = P["duct_id"] / 2 + 3
    s = (cq.Workplane("XY").workplane(offset=r_in).polyline(pts).close().extrude(r_out - r_in))
    # duct pad at the outer end
    pad = cq.Workplane("XY").box(P["pad_len"], P["pad_w"], 5, centered=(True, True, False)).translate((x_c, 0, P["duct_id"] / 2 - 1))
    for dx in (-10, 10):
        pad = pad.cut(cq.Workplane("XY").add(cq.Solid.makeCylinder(2.2, 20, cq.Vector(x_c + dx, 0, P["duct_id"] / 2 - 5), cq.Vector(0, 0, 1))))
    st = s.union(pad).val()
    return st.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 120 * k)

def duct_ring(x_c):
    ring = tube(x_c - P["duct_len"] / 2, P["duct_len"], P["duct_od"], P["duct_id"])
    w = cq.Workplane("XY").add(ring)
    for k in range(P["n_struts"]):
        for dx in (-10, 10):
            h = cq.Solid.makeCylinder(2.2, 30, cq.Vector(x_c + dx, 0, P["duct_id"] / 2 - 5), cq.Vector(0, 0, 1))
            w = w.cut(cq.Workplane("XY").add(h.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 120 * k)))
    return w.val()

# =============================================================== configuration A parts
def a_rotor():
    """Reviewed rev-2 rotor (hub 50.8 mm) with the shaft bore opened to 12 mm."""
    mb.R_HUB = 25.4; mb.R_ROOT_EXT = mb.R_HUB - 4.0; mb.HUB_BORE = P["a_shaft_d"] + 0.05
    blade = mb.design_blade(4.0, 6.0)
    blade_solid, loops, _ = mb.build_blade(blade)
    rotor, hubinfo = mb.build_rotor(blade_solid, loops[0])
    perf = {V: mb.bem(blade, 3.25, V) for V in (1.0, 1.5, 2.0)}
    return rotor, blade, dict(hubinfo=hubinfo, perf={str(V): dict(rpm=r["rpm"], P=r["P"], Q=r["Q"], T=r["T"], cp=r["cp"]) for V, r in perf.items()},
                              cp15=perf[1.5]["cp"], lam=3.25, r_hub=25.4)

def a_end_cap(x_face, facing):
    """Machined cap for the 80 x 2.5 tube: flange outside, plug inside with 2 radial O-rings (AS568-153 EPDM)."""
    f = facing
    flange = cylinder(x_face - P["cap_flange_t"] if f > 0 else x_face, P["cap_flange_t"], P["a_tube_od"])
    plug_x0 = x_face if f > 0 else x_face - P["a_cap_plug_len"]
    plug = cylinder(plug_x0, P["a_cap_plug_len"], P["a_tube_id"] - 0.1)
    cap = cq.Workplane("XY").add(flange).union(cq.Workplane("XY").add(plug))
    g_d = P["a_tube_id"] - 0.1 - 2 * P["oring_groove_d"]
    xs = [plug_x0 + 3.0, plug_x0 + 3.0 + P["a_oring_pitch"]]
    for xg in xs:
        cap = cap.cut(cq.Workplane("XY").add(tube(xg, P["oring_groove_w"], P["a_tube_id"] + 1, g_d)))
    orings = [oring_torus(xg + P["oring_groove_w"] / 2, g_d + P["oring_cs"], P["oring_cs"]) for xg in xs]
    return cap.val(), orings, plug_x0

def a_front_cap(x_face, x_pin_hole=None):
    """Machined front cap (6061 anodised or Delrin): flange outside, plug with 2 radial O-rings inside the tube;
    from the wet face: lip-seal bore (22 H8 x 7), 1.5 mm wall, bearing bore (28 H7 x 16) open to the dry side
    with an internal circlip groove (DIN 472-28) that takes the rotor thrust."""
    cap, orings, plug_x0 = a_end_cap(x_face, +1)        # flange at x_face-6..x_face, plug x_face..x_face+18
    w = cq.Workplane("XY").add(cap)
    x_wet = x_face - P["cap_flange_t"]
    w = w.cut(cq.Workplane("XY").add(cylinder(x_wet - 1, 60, P["a_shaft_d"] + 4.0)))                    # 16 mm clearance bore
    w = w.cut(cq.Workplane("XY").add(cylinder(x_wet - 0.01, P["a_seal_w"] + 0.01, P["a_seal_od"])))     # seal seat from the wet face
    brg_len = P["a_brg_n"] * P["a_brg_w"]
    x_brg = x_wet + P["a_seal_w"] + 1.5
    w = w.cut(cq.Workplane("XY").add(cylinder(x_brg, 60, P["a_brg_od"])))                                 # bearing bore, open to the dry side
    w = w.cut(cq.Workplane("XY").add(tube(x_brg + brg_len + 0.3, 1.3, P["a_brg_od"] + 2.4, P["a_brg_od"] - 1)))  # DIN 472 circlip groove
    return w.val(), orings, dict(x_seal=x_wet, x_brg=x_brg, brg_len=brg_len, x_dry=x_face + P["a_cap_plug_len"])

def a_rear_cap(x_face):
    """Machined rear cap (6061 anodised: it is the generator's heat sink): flange outside, plug with 2 O-rings;
    motor base bolted to its dry face (PCD TO MEASURE), WetLink M10 penetrator hole off-centre, M6 vent/vacuum port."""
    cap, orings, plug_x0 = a_end_cap(x_face, -1)        # plug x_face-18..x_face, flange x_face..x_face+6
    w = cq.Workplane("XY").add(cap)
    for k in range(4):
        a = math.radians(45 + 90 * k)
        h = cq.Solid.makeCylinder(P["a_motor_hole"] / 2, 12, cq.Vector(x_face - 18 - 1, P["a_motor_pcd"] / 2 * math.cos(a), P["a_motor_pcd"] / 2 * math.sin(a)), cq.Vector(1, 0, 0))
        w = w.cut(cq.Workplane("XY").add(h))
    w = w.cut(cq.Workplane("XY").add(cylinder(x_face - 19, 6, P["a_motor_bore"] + 2)))   # recess under the motor bore (lead exit)
    pen = cq.Solid.makeCylinder(P["a_penetrator_d"] / 2, 40, cq.Vector(x_face - 30, 0, P["a_penetrator_r"]), cq.Vector(1, 0, 0))
    w = w.cut(cq.Workplane("XY").add(pen))
    vent = cq.Solid.makeCylinder(2.5, 40, cq.Vector(x_face - 30, 0, -P["a_penetrator_r"]), cq.Vector(1, 0, 0))
    w = w.cut(cq.Workplane("XY").add(vent))
    return w.val(), orings, dict(x_dry=x_face - P["a_cap_plug_len"])

def a_shaft(x_front, length, x_pin):
    """316 ground shaft 12 h6: cross-pin hole at the hub, Speedi-Sleeve zone at the seal, DIN 471 groove behind the rear bearing."""
    s = cq.Workplane("XY").add(cylinder(x_front, length, P["a_shaft_d"]))
    s = s.cut(cq.Workplane("XY").add(cq.Solid.makeCylinder(1.6, 30, cq.Vector(x_pin, -15, 0), cq.Vector(0, 1, 0))))
    return s.val()

def a_sleeve(x0):   # SKF Speedi-Sleeve 99047 (11.99-12.09 mm shaft), 0.28 mm wall
    return tube(x0, P["a_sleeve_w"], P["a_shaft_d"] + 0.56, P["a_shaft_d"])

def a_coupling(x0):  # jaw coupling 12 mm x motor shaft, D20 L25 (aluminium, with spider)
    return tube(x0, P["a_coup_len"], P["a_coup_od"], P["a_shaft_d"])

def a_collar(x0):
    return tube(x0, P["a_collar_len"], P["a_collar_od"], P["a_shaft_d"])

def a_motor_gl60(x_front):
    """CubeMars GL60 placeholder: bell (rotor) at the front, stator base at the rear, 20 mm through-bore."""
    body = cylinder(x_front, P["a_motor_len"], P["a_motor_od"])
    m = cq.Workplane("XY").add(body).cut(cq.Workplane("XY").add(cylinder(x_front - 1, P["a_motor_len"] + 2, P["a_motor_bore"])))
    m = m.cut(cq.Workplane("XY").add(tube(x_front + 9, 1.0, P["a_motor_od"] + 1, P["a_motor_od"] - 2)))   # visual split bell/stator
    return m.val()

def a_bell_adapter(x0):
    """Delrin disc bolted to the GL60 bell face, with a 12 mm stub for the jaw coupling."""
    d = cylinder(x0, P["a_bell_adapter_t"], P["a_motor_od"] - 10)
    stub = cylinder(x0 - 11, 11.5, P["a_shaft_d"])
    w = cq.Workplane("XY").add(d).union(cq.Workplane("XY").add(stub))
    for k in range(4):
        a = math.radians(45 + 90 * k)
        w = w.cut(cq.Workplane("XY").add(cq.Solid.makeCylinder(1.7, 20, cq.Vector(x0 - 1, P["a_bell_pcd"] / 2 * math.cos(a), P["a_bell_pcd"] / 2 * math.sin(a)), cq.Vector(1, 0, 0))))
    return w.val()

def a_clamp_ring(x_c):
    """Printed split clamp ring around the tube, carrying the three struts (2 halves, 4x M4 316 bolts)."""
    ring = tube(x_c - P["a_clamp_w"] / 2, P["a_clamp_w"], P["a_tube_od"] + 2 * P["a_clamp_t"] + 8, P["a_tube_od"] + 0.2)
    w = cq.Workplane("XY").add(ring)
    for sgn in (1, -1):
        slot = cq.Workplane("XY").box(P["a_clamp_w"] + 2, 1.2, 60, centered=(True, True, False)).translate((x_c, 0, 0 if sgn > 0 else -60)).val()
        w = w.cut(cq.Workplane("XY").add(slot))
    return w.val()

def a_strut(x_c, k):
    c = P["strut_chord"]; tc = P["strut_tc"]
    up, lo = mb.naca4(0.0, 0.4, tc, c, n=40, te_thick=0.6)
    prof = np.r_[up[::-1], lo[1:]]
    pts = [(float(x_c - 0.4 * c + p[0]), float(p[1])) for p in prof]
    r_in = P["a_tube_od"] / 2 + P["a_clamp_t"] + 2; r_out = P["duct_id"] / 2 + 3
    s = cq.Workplane("XY").workplane(offset=r_in).polyline(pts).close().extrude(r_out - r_in)
    pad = cq.Workplane("XY").box(P["pad_len"], P["pad_w"], 5, centered=(True, True, False)).translate((x_c, 0, P["duct_id"] / 2 - 1))
    for dx in (-10, 10):
        pad = pad.cut(cq.Workplane("XY").add(cq.Solid.makeCylinder(2.2, 20, cq.Vector(x_c + dx, 0, P["duct_id"] / 2 - 5), cq.Vector(0, 0, 1))))
    st = s.union(pad).val()
    return st.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 120 * k + 60)

def build_A():
    parts = {}
    rotor, blade, rinfo = a_rotor()
    hub = rinfo["hubinfo"]
    x_hub_rear = hub["hub_x_downstream_face_mm"]
    x_face = x_hub_rear + P["a_gap_hub_cap"] + P["cap_flange_t"]         # tube front end
    fcap, fo, finfo = a_front_cap(x_face)
    # interior stack: front plug 18 | 1.5 | collar? (collar sits on the shaft inside, in front of the coupling) | coupling 25 | motor 29 | adapter 0 (motor on the rear cap) | rear plug 18
    ic = P["internal_clearance"]
    x_coup = finfo["x_brg"] + finfo["brg_len"] + 2.5 + 1.0                # behind the circlip
    x_adapter = x_coup + P["a_coup_len"]                                  # adapter disc behind the coupling; its 11 mm stub enters the rear half
    x_motor_front = x_adapter + P["a_bell_adapter_t"] + ic
    x_base = x_motor_front + P["a_motor_len"]                             # stator base plane
    x_rear_face = x_base + P["a_cap_plug_len"]                            # motor base bolted to the rear cap's dry face
    tube_len = x_rear_face - x_face
    parts["rotor"] = dict(solid=rotor, kind="print", color=(0.30, 0.50, 0.80), note="reviewed rev-2 rotor, 12 mm bore, 3.2 mm cross pin, 2x M4 grub screws")
    parts["nacelle_tube"] = dict(solid=tube(x_face, tube_len, P["a_tube_od"], P["a_tube_id"]), kind="COTS", color=(0.75, 0.75, 0.78), note=f"6061-T6 tube 80 x 2.5 mm (or 3.0 in x 0.049 in), {tube_len:.0f} mm, anodised")
    parts["front_cap"] = dict(solid=fcap, kind="machined", color=(0.85, 0.55, 0.2), note="machined cap: 2 radial O-rings, lip seal 12x22x7, 2x 6001-2RS SS, DIN 472-28 circlip")
    rcap, ro, rr = a_rear_cap(x_rear_face)
    parts["rear_cap"] = dict(solid=rcap, kind="machined", color=(0.85, 0.55, 0.2), note="machined 6061 cap: motor mount (PCD TO MEASURE), WetLink M10 hole, M6 vent port")
    for i, o in enumerate(fo + ro):
        parts[f"oring_{i}"] = dict(solid=o, kind="COTS", color=(0.1, 0.1, 0.1), note="AS568-152 EPDM 70 radial O-ring (ID 82.2 -> groove OD 70.7: use -151, ID 75.9... see BOM)")
    parts["lip_seal"] = dict(solid=tube(finfo["x_seal"], P["a_seal_w"], P["a_seal_od"], P["a_shaft_d"] + 0.56 - 0.6), kind="COTS", color=(0.2, 0.2, 0.2), note="rotary lip seal 12x22x7 (NBR spring-loaded, or PTFE)")
    for i in range(P["a_brg_n"]):
        parts[f"bearing_{i}"] = dict(solid=tube(finfo["x_brg"] + i * P["a_brg_w"], P["a_brg_w"], P["a_brg_od"], P["a_shaft_d"]), kind="COTS", color=(0.5, 0.5, 0.55), note="6001-2RS 440C stainless 12x28x8")
    x_sh0 = x_hub_rear - P["a_shaft_hub_in"]
    sh_len = x_coup + 11 - x_sh0
    parts["shaft"] = dict(solid=a_shaft(x_sh0, sh_len, hub["pin_x_mm"]), kind="COTS+machined", color=(0.55, 0.6, 0.6), note=f"316 ground shaft 12 h6 x {sh_len:.0f} mm, cross-pin hole, circlip groove, D-flat")
    parts["speedi_sleeve"] = dict(solid=a_sleeve(finfo["x_seal"] - 0.5), kind="COTS", color=(0.8, 0.8, 0.85), note="SKF Speedi-Sleeve 99047 hardened seal track on the 316 shaft")
    parts["collar"] = dict(solid=a_collar(finfo["x_seal"] - 2 - P["a_collar_len"]), kind="COTS", color=(0.55, 0.6, 0.6), note="316 clamp collar 12 mm (wet side): axial stop + slinger")
    parts["coupling"] = dict(solid=a_coupling(x_coup), kind="COTS", color=(0.9, 0.3, 0.3), note="jaw coupling 12 x 12 mm, D20 L25, polyurethane spider")
    parts["bell_adapter"] = dict(solid=a_bell_adapter(x_adapter), kind="machined/print", color=(0.9, 0.8, 0.3), note="Delrin adapter on the GL60 bell face (PCD TO MEASURE) with 12 mm stub")
    parts["motor"] = dict(solid=a_motor_gl60(x_motor_front), kind="COTS", color=(0.25, 0.25, 0.3), note="CubeMars GL60 KV25 (69 x 22.3, 20 mm bore), stator base bolted to the rear cap (heat sink)")
    x_cl = x_face + tube_len * 0.45
    parts["clamp_ring"] = dict(solid=a_clamp_ring(x_cl), kind="print", color=(0.35, 0.65, 0.45), note="printed split clamp ring, 2 halves, 4x M4 316")
    for k in range(P["n_struts"]):
        parts[f"strut_{k}"] = dict(solid=a_strut(x_cl, k), kind="print", color=(0.35, 0.65, 0.45), note="NACA 0015 strut to duct pad (cable runs along one strut)")
    parts["duct_ring"] = dict(solid=duct_ring(x_cl), kind="reference", color=(0.8, 0.8, 0.8), note="reference duct segment (user's duct), 2 mm tip clearance")
    layout = dict(arch="A", x_nose_tip=hub["hub_x_upstream_face_mm"] - mb.NOSE_LEN, x_hub_rear=x_hub_rear, x_tube=[x_face, x_rear_face], tube_len=tube_len,
                  x_seal=finfo["x_seal"], x_bearings=[finfo["x_brg"], finfo["x_brg"] + finfo["brg_len"]], x_motor=[x_base - P["motor_len"], x_base],
                  x_rear_end=x_rear_face + P["cap_flange_t"], x_strut_centre=x_cl, r_hub=25.4, x_duct=[x_cl - P["duct_len"] / 2, x_cl + P["duct_len"] / 2])
    layout["axial_depth_mm"] = layout["x_rear_end"] - layout["x_nose_tip"]
    checks = [("motor", "front_cap"), ("motor", "rear_cap"), ("motor", "nacelle_tube"), ("coupling", "front_cap"), ("coupling", "motor"), ("shaft", "front_cap"),
              ("shaft", "motor"), ("shaft", "bell_adapter"), ("bell_adapter", "motor"), ("rotor", "front_cap"), ("rotor", "clamp_ring"), ("strut_0", "rotor"),
              ("front_cap", "nacelle_tube"), ("rear_cap", "nacelle_tube"), ("collar", "front_cap"), ("speedi_sleeve", "front_cap"), ("clamp_ring", "nacelle_tube"), ("coupling", "bell_adapter")]
    inter = {}
    for a, b in checks:
        try:
            inter[f"{a}/{b}"] = round(parts[a]["solid"].intersect(parts[b]["solid"]).Volume(), 2)
        except Exception:
            inter[f"{a}/{b}"] = -1.0
    layout["interference_mm3"] = inter
    return parts, blade, rinfo, layout


# =============================================================== assemble (configuration B)
def build():
    parts = {}   # name -> dict(solid, kind, color, qty, note)
    rotor, blade, rinfo = build_rotor_ring()
    x0 = rinfo["x0"]                                   # blade axial centre
    # ---- interior stack, front to back (all inside the tube) ----
    ic = P["internal_clearance"]
    L_int = P["cap_plug_len"] + ic + P["disc_t"] + P["motor_len"] + P["adapter_t"] + P["collar_len"] + ic + P["rear_plug_len"]
    tube_len = L_int
    x_tube0 = x0 - tube_len / 2 + 6.0                   # bias the drum slightly aft so the blades sit over the front half
    x_tube1 = x_tube0 + tube_len
    parts["drum_tube"] = dict(solid=tube(x_tube0, tube_len, P["tube_od"], P["tube_id"]), kind="COTS", color=(0.75, 0.75, 0.78),
                              note=f"6061-T6 tube 2.5 in OD x 0.065 in wall (rotating drum), {tube_len:.0f} mm, anodised")
    parts["rotor_ring"] = dict(solid=rotor, kind="print", color=(0.30, 0.50, 0.80), note="printed in 2 halves, epoxied + clamped on the tube")
    fcap, fo, fplug = end_cap(x_tube0, +1)
    pocket = cylinder(x_tube0 + P["cap_plug_len"] - P["motor_shaft_l"] - 1.5, P["motor_shaft_l"] + 2, P["motor_shaft_d"] + 2)
    fcap = cq.Workplane("XY").add(fcap).cut(cq.Workplane("XY").add(pocket)).val()
    parts["front_cap"] = dict(solid=fcap, kind="COTS", color=(0.6, 0.6, 0.65), note="machined front cap (6061/Delrin), 2 radial O-rings; blind pocket for the motor shaft")
    rcap, ro, rinfo2 = rear_cap(x_tube1)
    parts["rear_cap"] = dict(solid=rcap, kind="machined", color=(0.85, 0.55, 0.2), note="Delrin/6061, lip-seal seat + bearing bore, 2 radial O-rings")
    for i, o in enumerate(fo + ro):
        parts[f"oring_{i}"] = dict(solid=o, kind="COTS", color=(0.1, 0.1, 0.1), note="AS568-1xx NBR 70 radial O-ring")
    parts["lip_seal"] = dict(solid=lip_seal(rinfo2["x_seal"]), kind="COTS", color=(0.2, 0.2, 0.2), note="rotary lip seal 15x24x5 on an SKF Speedi-Sleeve 99059, lip toward water")
    for i in range(P["brg_n"]):
        parts[f"bearing_{i}"] = dict(solid=bearing(rinfo2["x_brg"] + i * P["brg_w"]), kind="COTS", color=(0.5, 0.5, 0.55), note="6902-2RS stainless 15x28x7")
    # ---- front to back inside the drum ----
    x_disc = x_tube0 + P["cap_plug_len"] + ic
    parts["drive_disc"] = dict(solid=drive_disc(x_disc), kind="print", color=(0.9, 0.3, 0.3), note="TPU compliant drive disc, bell face to front cap")
    x_motor_front = x_disc + P["disc_t"]
    x_base = x_motor_front + P["motor_len"]              # stator base plane (motor extends -X from here)
    parts["motor"] = dict(solid=motor(x_base), kind="COTS", color=(0.25, 0.25, 0.3), note="GB5015 gimbal motor (placeholder envelope 49 x 29, shaft into the cap pocket)")
    parts["adapter_plate"] = dict(solid=adapter_plate(x_base), kind="print/Delrin", color=(0.9, 0.8, 0.3), note="motor base to collar adapter (PCD TO MEASURE)")
    x_col = x_base + P["adapter_t"]
    parts["flanged_collar"] = dict(solid=flanged_collar(x_col), kind="COTS", color=(0.55, 0.6, 0.6), note="316 flanged shaft collar 15 mm (stator mount)")
    # spindle: from the strut boss (rear) forward to the collar front
    x_boss0 = x_tube1 + P["cap_flange_t"] + P["gap_rotor_boss"]
    x_sp_rear = x_boss0 + P["hub_boss_len"] - 4
    P["spindle_len"] = x_sp_rear - (x_col - 2.0)
    parts["spindle"] = dict(solid=spindle(x_sp_rear), kind="COTS+machined", color=(0.55, 0.6, 0.6), note=f"316 tube 15 OD x 9 ID x {P['spindle_len']:.0f} mm, polished seal track, circlip grooves")
    parts["nose"] = dict(solid=nose(x_tube0 - P["cap_flange_t"]), kind="print", color=(0.30, 0.50, 0.80), note="printed nose cone, bolts to front cap")
    parts["strut_hub"] = dict(solid=strut_hub(x_boss0), kind="print", color=(0.35, 0.65, 0.45), note="split-clamp boss on the spindle, cable potting cavity")
    x_sc = x_boss0 + P["hub_boss_len"] / 2
    for k in range(P["n_struts"]):
        parts[f"strut_{k}"] = dict(solid=strut(x_sc, k), kind="print", color=(0.35, 0.65, 0.45), note="NACA 0015 strut, chord 18, to duct pad")
    parts["duct_ring"] = dict(solid=duct_ring(x_sc), kind="reference", color=(0.8, 0.8, 0.8), note="reference duct segment (user's duct), 2 mm tip clearance")
    layout = dict(x_blade_centre=x0, tube_len=tube_len, x_tube=[x_tube0, x_tube1], x_nose_tip=x_tube0 - P["cap_flange_t"] - P["nose_len"], x_rear_end=x_boss0 + P["hub_boss_len"],
                  x_seal=rinfo2["x_seal"], x_bearings=[rinfo2["x_brg"], rinfo2["x_brg"] + rinfo2["brg_len"]], x_motor=[x_motor_front, x_base],
                  x_strut_centre=x_sc, r_hub=rinfo["r_hub"], x_duct=[x_sc - P["duct_len"] / 2, x_sc + P["duct_len"] / 2])
    layout["axial_depth_mm"] = layout["x_rear_end"] - layout["x_nose_tip"]
    # ---- interference check between solids that must not touch (volume of pairwise intersection) ----
    checks = [("motor", "front_cap"), ("motor", "rear_cap"), ("motor", "drum_tube"), ("motor", "spindle"), ("flanged_collar", "rear_cap"),
              ("rotor_ring", "strut_hub"), ("rotor_ring", "duct_ring"), ("nose", "rotor_ring"), ("strut_0", "rotor_ring"), ("spindle", "front_cap"),
              ("adapter_plate", "drum_tube"), ("flanged_collar", "bearing_0"), ("front_cap", "drum_tube"), ("rear_cap", "drum_tube"),
              ("nose", "front_cap"), ("drive_disc", "front_cap"), ("motor", "drive_disc"), ("spindle", "rear_cap"), ("spindle", "motor"), ("rotor_ring", "drum_tube")]
    inter = {}
    for a, b in checks:
        try:
            v = parts[a]["solid"].intersect(parts[b]["solid"]).Volume()
        except Exception:
            v = -1.0
        inter[f"{a}/{b}"] = round(v, 2)
    layout["interference_mm3"] = inter
    return parts, blade, rinfo, layout

def export(parts, layout, rinfo, prefix):
    table = []
    assy = cq.Assembly(name=f"turbine_generator_{prefix}")
    for name, p in parts.items():
        s = p["solid"]; ok = s.isValid(); bb = s.BoundingBox()
        table.append(dict(name=name, kind=p["kind"], note=p["note"], valid=ok, volume_mm3=round(s.Volume(), 1),
                          x=[round(bb.xmin, 2), round(bb.xmax, 2)], rmax=round(max(abs(bb.ymin), abs(bb.ymax), abs(bb.zmin), abs(bb.zmax)), 2)))
        if not ok:
            print("WARNING: invalid solid", name)
        if not name.startswith("oring") and not name.startswith("bearing"):
            cq.exporters.export(s, os.path.join(OUT, f"{prefix}_{name}.step"))
        if p["kind"].startswith("print"):
            cq.exporters.export(s, os.path.join(OUT, f"{prefix}_{name}.stl"), tolerance=0.05, angularTolerance=0.2)
        assy.add(cq.Workplane("XY").add(s), name=name, color=cq.Color(*p["color"]))
    assy.save(os.path.join(OUT, f"{prefix}_assembly.step"))
    bad = {k: v for k, v in layout["interference_mm3"].items() if v > 0.5 or v < 0}
    print(f"[{prefix}] axial depth {layout['axial_depth_mm']:.1f} mm ({layout['axial_depth_mm']/25.4:.2f} in); tube {layout['tube_len']:.0f} mm; interference: {'none' if not bad else bad}")
    return table

def main():
    info = {}
    parts, blade, rinfo, layout = build_A()
    print(f"[A] rotor hub 50.8 mm: Cp(1.5) {rinfo['cp15']:.3f}; " + "; ".join(f"{V} m/s {p['P']:.1f} W {p['Q']:.2f} N m" for V, p in rinfo["perf"].items()))
    info["A"] = dict(layout=layout, rotor=dict(cp15=rinfo["cp15"], tsr=rinfo["lam"], perf=rinfo["perf"], r_hub=25.4), parts=export(parts, layout, rinfo, "A"))
    parts, blade, rinfo, layout = build()
    print(f"[B] rotor hub {rinfo['r_hub']:.1f} mm: Cp(1.5) {rinfo['cp15']:.3f}; " + "; ".join(f"{V} m/s {p['P']:.1f} W {p['Q']:.2f} N m" for V, p in rinfo["perf"].items()))
    layout["arch"] = "B"
    info["B"] = dict(layout=layout, rotor=dict(cp15=rinfo["cp15"], tsr=rinfo["lam"], perf=rinfo["perf"], r_hub=rinfo["r_hub"]), parts=export(parts, layout, rinfo, "B"))
    json.dump(dict(params=PARAMS, to_measure=TO_MEASURE, configs=info), open(os.path.join(OUT, "assembly_info.json"), "w"), indent=2)
    print("exported to", OUT)

if __name__ == "__main__":
    main()
