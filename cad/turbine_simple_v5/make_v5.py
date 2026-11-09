#!/usr/bin/env python
"""Simplified prototype v5 of the 0.5-1.0 m/s turbine: THREE primary printed parts around the (fixed) CubeMars GL60 KV25.

  ROTOR   one print: nose + hub cup + 3 blades (the v4 optimised low-flow geometry: NACA 4412 -> 4418 root, design TSR 1.5, -3 deg pitch,
          root chord 50, max chord 60) + an integral 10 mm neck with a double-D end.  A 12 mm stainless tube (COTS, 16.5 mm long) is glued
          on the neck as the seal / bearing journal.  One central M3 x 50 bolt (through the nose) holds the rotor on the bell adapter.
  HOUSING one print: cup (OD 78) open to the rear, flat front wall, 40 mm snout that reaches into the hub cup and carries ONE 12x28x7 lip
          seal and ONE 6001-2RS bearing in a single 28 mm bore; rear flange with 6 M4 heat-set inserts.  The GL60 sits dry inside.
  MOUNT   one print: the housing's rear lid (face O-ring, 6 x M4) with the GL60 stator bolted to it on 6 mm stand-offs, a PG7 cable gland,
          and an arm down to a 40 mm stake socket.  Securing the housing to the mount and closing it are the same six screws.
  + bell adapter (small print): 46 x 8 disc bolted to the GL60 bell face (4 x M3, PCD assumed 40 - gate G1), double-D bore for the neck,
    captive M3 nut in a boss that sits inside the GL60's 20 mm bore.
Frame: +X = flow; rotor axis = X; Z up.  Hub front face at x = 0.  All mm.  Depends on ../turbine_lowflow_v4 (blade geometry + helpers)."""
import json, math, os, sys, itertools
import numpy as np
import cadquery as cq
import trimesh
HERE = os.path.dirname(os.path.abspath(__file__)); V4 = os.path.abspath(os.path.join(HERE, "..", "turbine_lowflow_v4"))
sys.path.insert(0, os.path.join(V4, "cad")); import make_v4 as m4
from make_v4 import W, cyl, tube, rotX, hole_x, hole_dir, resample, load_coords, section_pts, wire_from_loop, blade_stations
mb = m4.mb
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)

Q = dict(
    r_tip=101.6, r_hub=28.0, hub_len=30.0, cup_id=42.0, cup_floor=5.0, nose_len=12.0, nose_tip_d=16.0, blade_r0=23.0,
    neck_d=10.0, neck_af=8.0, neck_x0=4.0, dd_x0=36.0, bolt_d=3.0, bore_d=3.4, head_pocket_d=7.0, head_pocket_x1=-3.0,
    sleeve_od=12.0, sleeve_id=10.0, sleeve_x0=6.0, sleeve_len=16.5,
    gap_hub_wall=2.0, snout_od=40.0, snout_x0=7.0, seal_w=7.0, brg_w=8.0, seat_d=28.0, seal_id=11.5, brg_bore=12.0, lip_id=20.0, lip_t=3.0,
    wall_open_d=14.0, wall_t=4.0, body_od=78.0, body_id=70.0, flange_od=96.0, flange_t=8.0, insert_pcd=88.0, insert_d=5.6, insert_depth=7.0, insert_a0=30.0,
    oring_id=72.4, oring_od=79.6, oring_depth=2.0, plate_t=6.0, plate_screw_d=4.4, plate_screw_head_d=7.0, plate_screw_head_h=4.0,
    adapter_od=46.0, adapter_t=8.0, adapter_gap=0.5, dd_bore=10.2, dd_bore_af=8.2, dd_depth=6.0, bell_pcd=40.0, bell_screw_cl=3.4, bell_cb_d=6.0, bell_cb_depth=3.0,
    nut_boss_d=12.0, nut_boss_len=4.0, nut_af=5.7, nut_depth=4.2,
    motor_od=69.0, motor_len=22.3, motor_bore=20.0, base_pcd=50.0, base_screw_cl=2.7, base_cb_d=5.5, base_cb_depth=2.5, standoff=6.0, standoff_d=8.0,
    gland_d=12.5, gland_r=24.0, gland_deg=45.0, gland_body_d=15.0, gland_body_len=12.0, gland_nut_af=18.0, gland_nut_t=4.0,
    arm_w=16.0, arm_x0=48.8, tab_w=24.0, arm_z_top=-50.0, sock_bore=16.2, sock_wall=4.0, sock_len=40.0, sock_z_top=-128.0,
)

# ----------------------------------------------------------------- layout (x positions)
def layout():
    L = {}
    L["x_hub0"] = 0.0; L["x_hub1"] = Q["hub_len"]; L["x_nose"] = -Q["nose_len"]
    L["x_wall0"] = Q["hub_len"] + Q["gap_hub_wall"]; L["x_wall1"] = L["x_wall0"] + Q["wall_t"]
    L["x_seal0"] = Q["snout_x0"]; L["x_brg0"] = L["x_seal0"] + Q["seal_w"]; L["x_brg1"] = L["x_brg0"] + Q["brg_w"]; L["x_lip1"] = L["x_brg1"] + Q["lip_t"]
    L["x_ad0"] = L["x_wall1"] + Q["adapter_gap"]; L["x_ad1"] = L["x_ad0"] + Q["adapter_t"]
    L["x_dd_floor"] = L["x_ad0"] + Q["dd_depth"]; L["x_neck1"] = L["x_dd_floor"] - 0.05
    L["x_bell"] = L["x_ad1"]; L["x_motor1"] = L["x_bell"] + Q["motor_len"]
    L["x_plate0"] = L["x_motor1"] + Q["standoff"]; L["x_plate1"] = L["x_plate0"] + Q["plate_t"]
    L["x_flange0"] = L["x_plate0"] - Q["flange_t"]
    return L

# ----------------------------------------------------------------- rotor (one print) + its mesh
def rotor_profile():
    """2-D (x, r) outline of the body of revolution: nose (elliptical from r_hub at x=0 to the flat tip), hub cylinder, cup, neck"""
    rh, ln, rt = Q["r_hub"], Q["nose_len"], Q["nose_tip_d"] / 2
    t = np.linspace(0, 1, 25)
    nose = [(-ln * math.sin(0.5 * math.pi * u), rt + (rh - rt) * math.cos(0.5 * math.pi * u)) for u in t]      # from (0, rh) to (-ln, rt)
    return nose

def rotor_solid(sel):
    rh, ln = Q["r_hub"], Q["nose_len"]
    nose = rotor_profile()
    prof = cq.Workplane("XY").moveTo(0, 0).lineTo(0, rh).spline(nose[1:], includeCurrent=True).lineTo(-ln, 0).close()
    body = W(prof.revolve(360, (0, 0, 0), (1, 0, 0)).val())
    body = body.union(W(cyl(0, Q["hub_len"], 2 * rh)))
    body = body.cut(W(cyl(Q["cup_floor"], Q["hub_len"] - Q["cup_floor"] + 1, Q["cup_id"])))                           # cup, open to the rear
    L = layout()
    body = body.union(W(cyl(Q["neck_x0"], L["x_neck1"] - Q["neck_x0"], Q["neck_d"])))                                  # neck
    for s in (1, -1):                                                                                                   # double-D flats on the neck end
        body = body.cut(W(cq.Workplane("XY").box(L["x_neck1"] - Q["dd_x0"] + 1, 30, 10, centered=(False, True, False)).translate((Q["dd_x0"], 0, Q["neck_af"] / 2 if s > 0 else -Q["neck_af"] / 2 - 10)).val()))
    body = body.cut(W(cyl(-ln - 1, L["x_neck1"] + ln + 3, Q["bore_d"])))                                               # central bolt bore, through the neck end
    body = body.cut(W(cyl(-ln - 1, Q["head_pocket_x1"] + ln + 1, Q["head_pocket_d"])))                                 # bolt-head pocket in the nose
    # blades: lofted from inside the cup wall (r = blade_r0) to the tip, root chord/twist held constant inboard of r_hub
    outer = resample(load_coords(sel["airfoil"])); root = resample(load_coords(sel.get("root_airfoil", "naca4418")))
    rs, cs, tws, wrs = blade_stations(sel)
    rs_in = [Q["blade_r0"], 0.5 * (Q["blade_r0"] + rh)]
    R = np.r_[rs_in, rs]; C = np.r_[[cs[0]] * 2, cs]; T = np.r_[[tws[0]] * 2, tws]; Wr = np.r_[[wrs[0]] * 2, wrs]
    wires = [wire_from_loop(section_pts(outer, root, w, r, c, tw)) for r, c, tw, w in zip(R, C, T, Wr)]
    faces = mb.thru_sections(wires, ruled=False)
    caps = [cq.Face.makeNSidedSurface(wires[0].Edges(), []), cq.Face.makeNSidedSurface(wires[-1].Edges(), [])]
    blade = mb.sew_solid(faces + caps)
    if not blade.isValid(): raise RuntimeError("blade solid invalid")
    for k in range(sel["B"]):
        body = body.union(W(rotX(blade, 360 * k / sel["B"])), clean=False)
    sol = body.val()
    return sol, dict(R=R.tolist(), C=C.tolist(), T=T.tolist(), Wr=Wr.tolist())

def rotor_mesh(sel, st):
    """watertight mesh of the one-piece rotor: body of revolution (trimesh.revolve) + structured blade meshes, united with manifold3d, minus
    the bolt bore, the head pocket and the double-D flats"""
    L = layout(); rh, ln = Q["r_hub"], Q["nose_len"]
    nose = rotor_profile()
    # revolve profile in (r, x) as a closed polyline from the axis: axis points first/last
    prof = [(0.0, -ln - 0.0)] + [(r, x) for x, r in nose[::-1]] + [(rh, Q["hub_len"]), (Q["cup_id"] / 2, Q["hub_len"]), (Q["cup_id"] / 2, Q["cup_floor"]),
            (Q["neck_d"] / 2, Q["cup_floor"]), (Q["neck_d"] / 2, L["x_neck1"]), (0.0, L["x_neck1"])]
    body = trimesh.creation.revolve(np.array(prof), sections=180)                                   # revolve about the local z axis (x of the part)
    body.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, (0, 1, 0)))           # local z -> part x
    assert body.is_watertight
    outer = resample(load_coords(sel["airfoil"])); root = resample(load_coords(sel.get("root_airfoil", "naca4418")))
    rings = [section_pts(outer, root, w, r, c, tw) for r, c, tw, w in zip(st["R"], st["C"], st["T"], st["Wr"])]
    N = len(rings[0]); Vb = np.vstack(rings); F = []
    for a in range(len(rings) - 1):
        o0, o1 = a * N, (a + 1) * N
        for i in range(N):
            j = (i + 1) % N; F.append((o0 + i, o0 + j, o1 + i)); F.append((o0 + j, o1 + j, o1 + i))
    n = (N + 1) // 2
    def zipper(o, flip):
        tri = []
        for j in range(n - 1):
            u0, u1 = o + (n - 1 - j), o + (n - 2 - j); l0, l1 = o + (n - 1 + j), o + (n + j)
            tri.append((u0, u1, l1))
            if j: tri.append((u0, l1, l0))
        return [t[::-1] for t in tri] if flip else tri
    F += zipper(0, False) + zipper((len(rings) - 1) * N, True)
    bl = trimesh.Trimesh(Vb, np.array(F), process=True); bl.update_faces(bl.nondegenerate_faces(height=1e-7)); bl.remove_unreferenced_vertices(); bl.fix_normals()
    assert bl.is_watertight
    parts = [body] + [bl.copy().apply_transform(trimesh.transformations.rotation_matrix(math.radians(360 * k / sel["B"]), (1, 0, 0))) for k in range(sel["B"])]
    m = trimesh.boolean.union(parts, engine="manifold")
    Tm = trimesh.transformations
    def xcyl(d, x0, x1): return trimesh.creation.cylinder(radius=d / 2, height=x1 - x0, sections=64, transform=Tm.concatenate_matrices(Tm.translation_matrix((0.5 * (x0 + x1), 0, 0)), Tm.rotation_matrix(math.pi / 2, (0, 1, 0))))
    cuts = [xcyl(Q["bore_d"], -ln - 1, L["x_neck1"] + 1), xcyl(Q["head_pocket_d"], -ln - 1, Q["head_pocket_x1"])]
    for s in (1, -1):
        b = trimesh.creation.box(extents=(L["x_neck1"] - Q["dd_x0"] + 2, 30, 10)); b.apply_translation((0.5 * (Q["dd_x0"] + L["x_neck1"] + 2), 0, s * (Q["neck_af"] / 2 + 5)))
        cuts.append(b)
    m = trimesh.boolean.difference([m] + cuts, engine="manifold")
    assert m.is_watertight
    return m

# ----------------------------------------------------------------- housing (one print)
def housing_solid():
    L = layout()
    h = W(cyl(L["x_wall0"], Q["wall_t"], Q["body_od"]))                                                                 # front wall
    h = h.union(W(tube(L["x_wall1"] - 0.01, L["x_plate0"] - L["x_wall1"] + 0.01, Q["body_od"], Q["body_id"])))         # body
    h = h.union(W(tube(L["x_flange0"], Q["flange_t"], Q["flange_od"], Q["body_id"])))                                  # rear flange
    h = h.union(W(cyl(Q["snout_x0"], L["x_wall0"] - Q["snout_x0"] + 0.01, Q["snout_od"])))                              # snout into the hub cup
    h = h.cut(W(cyl(Q["snout_x0"] - 1, 1 + Q["seal_w"] + Q["brg_w"], Q["seat_d"])))                                     # one 28 mm bore: seal then bearing
    h = h.cut(W(cyl(L["x_brg1"] - 0.01, Q["lip_t"] + 0.02, Q["lip_id"])))                                               # lip behind the bearing (outer-race stop)
    h = h.cut(W(cyl(L["x_lip1"] - 0.01, L["x_wall1"] - L["x_lip1"] + 1, Q["wall_open_d"])))                            # neck clearance through the wall
    for k in range(6):
        a = math.radians(Q["insert_a0"] + 60 * k); y, z = -Q["insert_pcd"] / 2 * math.sin(a), Q["insert_pcd"] / 2 * math.cos(a)
        h = h.cut(W(hole_x(Q["insert_d"], L["x_plate0"] - Q["insert_depth"], Q["insert_depth"] + 1, y, z)))             # M4 heat-set inserts from the rear face
    return h.val()

# ----------------------------------------------------------------- mount = rear lid + stator carrier + arm + stake socket (one print)
def mount_solid():
    L = layout(); x0, x1 = L["x_plate0"], L["x_plate1"]
    m = W(cyl(x0, Q["plate_t"], Q["flange_od"]))
    m = m.union(W(cq.Workplane("XY").box(Q["plate_t"], Q["tab_w"], 16.0, centered=(False, True, False)).translate((x0, 0, -Q["flange_od"] / 2 - 8.0)).val()))   # tab joining the arm
    m = m.cut(W(tube(x0 - 1, 1 + Q["oring_depth"], Q["oring_od"], Q["oring_id"])))                                     # face O-ring groove
    for k in range(6):
        a = math.radians(Q["insert_a0"] + 60 * k); y, z = -Q["insert_pcd"] / 2 * math.sin(a), Q["insert_pcd"] / 2 * math.cos(a)
        m = m.cut(W(hole_x(Q["plate_screw_d"], x0 - 1, Q["plate_t"] + 2, y, z)))                                        # M4 clearance
    for k in range(4):
        a = math.radians(90 * k); y, z = Q["base_pcd"] / 2 * math.cos(a), Q["base_pcd"] / 2 * math.sin(a)
        m = m.union(W(hole_x(Q["standoff_d"], x0 - Q["standoff"], Q["standoff"] + 0.01, y, z)))                        # stand-offs for the GL60 stator base
        m = m.cut(W(hole_x(Q["base_screw_cl"], x0 - Q["standoff"] - 1, Q["standoff"] + Q["plate_t"] + 2, y, z)))        # M2.5 clearance (M3 if G1 says so)
        m = m.cut(W(hole_x(Q["base_cb_d"], x1 - Q["base_cb_depth"], Q["base_cb_depth"] + 1, y, z)))                    # head counterbore (sealed with a bonded washer / silicone)
    ag = math.radians(Q["gland_deg"]); yg, zg = -Q["gland_r"] * math.sin(ag), Q["gland_r"] * math.cos(ag)
    m = m.cut(W(hole_x(Q["gland_d"], x0 - 1, Q["plate_t"] + 2, yg, zg)))                                                # PG7 gland hole
    # arm: forward of the plate (under the housing), full height only ahead of the flange
    arm = cq.Workplane("XY").box(x1 - Q["arm_x0"], Q["arm_w"], Q["arm_z_top"] - Q["sock_z_top"], centered=(False, True, False)).translate((Q["arm_x0"], 0, Q["sock_z_top"])).val()
    tab = cq.Workplane("XY").box(Q["plate_t"], Q["arm_w"], 10.0, centered=(False, True, False)).translate((x0, 0, Q["arm_z_top"] - 1)).val()
    m = m.union(W(arm)).union(W(tab))
    xc = 0.5 * (Q["arm_x0"] + x1); wsock = Q["sock_bore"] + 2 * Q["sock_wall"]
    sock = cq.Workplane("XY").box(wsock, wsock, Q["sock_len"] + 2.0, centered=(True, True, False)).translate((xc, 0, Q["sock_z_top"] - Q["sock_len"] - 2.0)).val()
    m = m.union(W(sock))
    m = m.cut(W(hole_dir(Q["sock_bore"], Q["sock_len"] + 1, (xc, 0, Q["sock_z_top"] - Q["sock_len"] - 3.0), (0, 0, 1))))   # stake bore from the bottom
    return m.val(), dict(x_sock=xc, z_sock_mouth=Q["sock_z_top"] - Q["sock_len"] - 2.0, gland_yz=(yg, zg))

# ----------------------------------------------------------------- bell adapter (small print)
def adapter_solid():
    L = layout(); x0, x1 = L["x_ad0"], L["x_ad1"]
    a = W(cyl(x0, Q["adapter_t"], Q["adapter_od"])).union(W(cyl(x1 - 0.01, Q["nut_boss_len"] + 0.01, Q["nut_boss_d"])))
    dd = W(cyl(x0 - 1, Q["dd_depth"] + 1, Q["dd_bore"])).intersect(W(cq.Workplane("XY").box(Q["dd_depth"] + 3, 20, Q["dd_bore_af"], centered=(False, True, True)).translate((x0 - 1.5, 0, 0)).val()))
    a = a.cut(dd)                                                                                                      # double-D blind bore
    a = a.cut(W(cyl(x0 - 1, Q["adapter_t"] + Q["nut_boss_len"] + 2, Q["bore_d"])))                                      # bolt hole
    hexp = cq.Workplane("YZ").workplane(offset=x1 + Q["nut_boss_len"] - Q["nut_depth"]).polygon(6, Q["nut_af"] / math.cos(math.pi / 6)).extrude(Q["nut_depth"] + 1).val()
    a = a.cut(W(hexp))                                                                                                 # captive M3 nyloc pocket (inside the GL60's 20 mm bore)
    for k in range(4):
        ang = math.radians(45 + 90 * k); y, z = Q["bell_pcd"] / 2 * math.cos(ang), Q["bell_pcd"] / 2 * math.sin(ang)
        a = a.cut(W(hole_x(Q["bell_screw_cl"], x0 - 1, Q["adapter_t"] + 2, y, z))).cut(W(hole_x(Q["bell_cb_d"], x0 - 1, Q["bell_cb_depth"] + 1, y, z)))   # 4 x M3 to the bell, heads counterbored on the front face
    return a.val()

def adapter_mesh():
    """watertight adapter mesh from primitives (the sewn B-rep tessellation was not closed): disc + nut boss - double-D - bolt hole - hex pocket - 4 screw holes/counterbores"""
    L = layout(); x0, x1 = L["x_ad0"], L["x_ad1"]; Tm = trimesh.transformations
    def xcyl(d, xa, xb, sections=96): return trimesh.creation.cylinder(radius=d / 2, height=xb - xa, sections=sections, transform=Tm.concatenate_matrices(Tm.translation_matrix((0.5 * (xa + xb), 0, 0)), Tm.rotation_matrix(math.pi / 2, (0, 1, 0))))
    def xcyl_at(d, xa, xb, y, z, sections=48): c = xcyl(d, xa, xb, sections); c.apply_translation((0, y, z)); return c
    body = trimesh.boolean.union([xcyl(Q["adapter_od"], x0, x1), xcyl(Q["nut_boss_d"], x1 - 0.5, x1 + Q["nut_boss_len"])], engine="manifold")
    slab = trimesh.creation.box(extents=(Q["dd_depth"] + 3, 30, Q["dd_bore_af"])); slab.apply_translation((x0 - 1.5 + 0.5 * (Q["dd_depth"] + 3), 0, 0))
    dd = trimesh.boolean.intersection([xcyl(Q["dd_bore"], x0 - 1, x0 + Q["dd_depth"]), slab], engine="manifold")
    hexp = xcyl(Q["nut_af"] / math.cos(math.pi / 6), x1 + Q["nut_boss_len"] - Q["nut_depth"], x1 + Q["nut_boss_len"] + 1, sections=6)
    cuts = [dd, xcyl(Q["bore_d"], x0 - 1, x1 + Q["nut_boss_len"] + 2), hexp]
    for k in range(4):
        ang = math.radians(45 + 90 * k); y, z = Q["bell_pcd"] / 2 * math.cos(ang), Q["bell_pcd"] / 2 * math.sin(ang)
        cuts += [xcyl_at(Q["bell_screw_cl"], x0 - 1, x1 + 1, y, z), xcyl_at(Q["bell_cb_d"], x0 - 1, x0 + Q["bell_cb_depth"], y, z)]
    m = trimesh.boolean.difference([body] + cuts, engine="manifold"); assert m.is_watertight
    return m

# ----------------------------------------------------------------- COTS envelopes, assembly, checks
def build(sel):
    L = layout(); parts = {}
    rot, st = rotor_solid(sel)
    parts["rotor"] = dict(solid=rot, kind="print", color=(0.35, 0.55, 0.85), note="ASA one-piece rotor: nose, hub cup, 3 blades, 10 mm double-D neck; central M3 bore")
    parts["sleeve"] = dict(solid=tube(Q["sleeve_x0"], Q["sleeve_len"], Q["sleeve_od"], Q["sleeve_id"]), kind="COTS", color=(0.6, 0.6, 0.65), note="304/316 tube 12 x 1 x 16.5, epoxied on the neck: seal + bearing journal")
    parts["housing"] = dict(solid=housing_solid(), kind="print", color=(0.6, 0.6, 0.65), note="ASA housing: cup OD 78, snout 40 with one 28 mm bore (seal + 6001), rear flange with 6 M4 inserts")
    mnt, minfo = mount_solid()
    parts["mount"] = dict(solid=mnt, kind="print", color=(0.8, 0.5, 0.2), note="ASA mount: rear lid (face O-ring, 6 x M4), stator stand-offs, PG7 gland hole, arm, 40 mm stake socket")
    parts["adapter"] = dict(solid=adapter_solid(), kind="print", color=(0.9, 0.3, 0.3), note="ASA bell adapter 46 x 8: double-D bore, 4 x M3 to the bell face, captive M3 nut in the bell bore")
    parts["seal"] = dict(solid=tube(L["x_seal0"] + 0.01, Q["seal_w"] - 0.02, Q["seat_d"], Q["seal_id"]), kind="COTS", color=(0.2, 0.2, 0.2), note="lip seal 12 x 28 x 7 (PTFE preferred; NBR TC fallback), lip to the water")
    parts["bearing"] = dict(solid=tube(L["x_brg0"], Q["brg_w"], Q["seat_d"], Q["brg_bore"]), kind="COTS", color=(0.5, 0.5, 0.55), note="6001-2RS stainless 12 x 28 x 8")
    parts["motor"] = dict(solid=W(cyl(L["x_bell"], Q["motor_len"], Q["motor_od"])).cut(W(cyl(L["x_bell"] - 1, Q["motor_len"] + 2, Q["motor_bore"]))).val(), kind="COTS", color=(0.25, 0.25, 0.3), note="CubeMars GL60 KV25 envelope 69 x 22.3, 20 mm bore; bell forward")
    hb = W(cyl(Q["head_pocket_x1"] - 3.0, 3.0, 5.5)).union(W(cyl(Q["head_pocket_x1"] - 0.01, (L["x_ad1"] + 2.5) - Q["head_pocket_x1"], Q["bolt_d"])))
    parts["rotor_bolt"] = dict(solid=hb.val(), kind="COTS", color=(0.4, 0.4, 0.4), note="M3 x 50 316 socket head: rotor to adapter, through the nose")
    x_nut0 = max(L["x_ad1"] + Q["nut_boss_len"] - Q["nut_depth"], L["x_ad1"]) + 0.05
    nut = cq.Workplane("YZ").workplane(offset=x_nut0).polygon(6, Q["nut_af"] / math.cos(math.pi / 6) - 0.2).extrude(L["x_ad1"] + Q["nut_boss_len"] - x_nut0 - 0.05).val()
    parts["rotor_nut"] = dict(solid=W(nut).cut(W(cyl(L["x_ad1"] - 1, 12, Q["bolt_d"] + 0.1))).val(), kind="COTS", color=(0.4, 0.4, 0.4), note="M3 nyloc, captive in the adapter")
    for k in range(4):
        ang = math.radians(45 + 90 * k); y, z = Q["bell_pcd"] / 2 * math.cos(ang), Q["bell_pcd"] / 2 * math.sin(ang)
        parts[f"bell_screw_{k}"] = dict(solid=W(hole_x(5.5, L["x_ad0"] + 0.01, Q["bell_cb_depth"] - 0.01, y, z)).union(W(hole_x(3.0, L["x_ad0"] + Q["bell_cb_depth"] - 0.5, 10.5, y, z))).val(), kind="COTS", color=(0.4, 0.4, 0.4), note="M3 x 10 316 socket head into the GL60 bell (4)")
    for k in range(6):
        a = math.radians(Q["insert_a0"] + 60 * k); y, z = -Q["insert_pcd"] / 2 * math.sin(a), Q["insert_pcd"] / 2 * math.cos(a)
        parts[f"plate_screw_{k}"] = dict(solid=W(hole_x(7.0, L["x_plate1"], 4.0, y, z)).union(W(hole_x(4.0, L["x_plate1"] - 12.0, 12.01, y, z))).val(), kind="COTS", color=(0.4, 0.4, 0.4), note="M4 x 12 316 pan head into M4 heat-set inserts (6)")
        parts[f"insert_{k}"] = dict(solid=tube(L["x_plate0"] - Q["insert_depth"] + 0.02, Q["insert_depth"] - 0.04, Q["insert_d"] - 0.02, 4.1).translate(cq.Vector(0, y, z)), kind="COTS", color=(0.7, 0.6, 0.2), note="M4 brass heat-set insert (6)")
    for k in range(4):
        a = math.radians(90 * k); y, z = Q["base_pcd"] / 2 * math.cos(a), Q["base_pcd"] / 2 * math.sin(a)
        parts[f"base_screw_{k}"] = dict(solid=W(hole_x(4.5, L["x_plate1"] - Q["base_cb_depth"] + 0.02, Q["base_cb_depth"] - 0.04, y, z)).union(W(hole_x(2.5, L["x_plate1"] - Q["base_cb_depth"] - 16.0, 16.1, y, z))).val(), kind="COTS", color=(0.4, 0.4, 0.4), note="M2.5 x 16 316 + bonded washer into the GL60 stator base (4; M3 if G1 says so)")
    yg, zg = minfo["gland_yz"]
    gl_ = W(hole_x(Q["gland_body_d"], L["x_plate1"], Q["gland_body_len"], yg, zg)).union(W(hole_x(Q["gland_d"] - 0.1, L["x_plate0"] - Q["gland_nut_t"], Q["gland_nut_t"] + Q["plate_t"] + 0.01, yg, zg)))
    gl_ = gl_.union(W(cq.Workplane("YZ").workplane(offset=L["x_plate0"] - Q["gland_nut_t"]).polygon(6, Q["gland_nut_af"] / math.cos(math.pi / 6)).extrude(Q["gland_nut_t"] - 0.02).val().translate(cq.Vector(0, yg, zg))))
    parts["gland"] = dict(solid=gl_.val(), kind="COTS", color=(0.3, 0.3, 0.3), note="PG7 nylon cable gland + locknut (inside the 6 mm stator bay)")
    parts["oring"] = dict(solid=m4.torus(L["x_plate0"] + 1.3, 0.5 * (Q["oring_id"] + Q["oring_od"]), 2.62), kind="COTS", color=(0.1, 0.1, 0.1), note="AS568-148 EPDM face O-ring")
    # ---- checks
    names = [n for n in parts if n != "oring"]; bbs = {n: parts[n]["solid"].BoundingBox() for n in names}; inter = {}
    def excluded(a, b):   # screws threaded INTO the GL60 (its envelope is a solid cylinder): expected overlap
        return (a == "motor" and b.startswith(("bell_screw", "base_screw"))) or (b == "motor" and a.startswith(("bell_screw", "base_screw")))
    for a, b in itertools.combinations(names, 2):
        if excluded(a, b): continue
        A, B = bbs[a], bbs[b]
        if A.xmax < B.xmin - 0.01 or B.xmax < A.xmin - 0.01 or A.ymax < B.ymin - 0.01 or B.ymax < A.ymin - 0.01 or A.zmax < B.zmin - 0.01 or B.zmax < A.zmin - 0.01: continue
        try: v = parts[a]["solid"].intersect(parts[b]["solid"]).Volume()
        except Exception: v = -1.0
        if v > 0.01 or v < 0: inter[f"{a}/{b}"] = round(v, 3)
    lip_expected = math.pi / 4 * (Q["sleeve_od"] ** 2 - Q["seal_id"] ** 2) * (Q["seal_w"] - 0.02); v_lip = inter.pop("sleeve/seal", 0.0)
    groups = dict(rotor=["rotor", "sleeve", "rotor_bolt"], housing_mount=["housing", "mount", "adapter", "seal", "bearing", "motor", "rotor_nut", "gland", "oring"] + [n for n in parts if n.startswith(("bell_screw", "plate_screw", "insert_", "base_screw"))])
    def span(ns): bb = [parts[n]["solid"].BoundingBox() for n in ns]; return max(b.xmax for b in bb) - min(b.xmin for b in bb)
    lay = dict(Q=Q, L=L, mount=minfo, interference_mm3=inter, pairs_checked=sum(1 for _ in itertools.combinations(names, 2)), nose_to_lid_mm=L["x_plate1"] - L["x_nose"],
               seal_lip_overlap_mm3=dict(found=round(v_lip, 2), expected=round(lip_expected, 2), ok=abs(v_lip - lip_expected) < 2.0),
               operating_depth_mm=span(list(parts)), rotor_depth_mm=span(groups["rotor"]), housing_mount_depth_mm=span([n for n in groups["housing_mount"] if n != "gland"]),
               housing_mount_depth_with_gland_mm=span(groups["housing_mount"]), stations=st,
               clearances_mm=dict(hub_to_wall=L["x_wall0"] - Q["hub_len"], snout_to_cup_floor=Q["snout_x0"] - Q["cup_floor"], snout_radial=(Q["cup_id"] - Q["snout_od"]) / 2,
                                  neck_end_to_dd_floor=round(L["x_dd_floor"] - L["x_neck1"], 2), adapter_to_wall=Q["adapter_gap"], dd_engagement=round(L["x_neck1"] - Q["dd_x0"], 2),
                                  stator_bay=Q["standoff"], blade_tip_to_arm=None))
    return parts, lay

def print_orient(name, s):
    """print orientation: rotor nose down (flat 16 mm tip on the bed, supports under the blades), housing open end down, mount rear face
    down (arm lying along the bed), adapter front face down"""
    if name == "rotor": s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), -90)
    elif name in ("housing", "mount"): s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), 90)
    elif name == "adapter": s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), -90)
    bb = s.BoundingBox(); return s.translate(cq.Vector(-bb.xmin, -bb.ymin, -bb.zmin))

def export(parts, lay, sel):
    table = []; assy = cq.Assembly(name="v5_simple")
    rm = rotor_mesh(sel, lay["stations"])
    for name, p in parts.items():
        s = p["solid"]; bb = s.BoundingBox()
        row = dict(name=name, kind=p["kind"], note=p["note"], valid=s.isValid(), n_solids=len(s.Solids()), volume_mm3=round(s.Volume(), 1), x=[round(bb.xmin, 2), round(bb.xmax, 2)])
        if name in ("rotor", "housing", "mount", "adapter", "motor"):
            cq.exporters.export(s, os.path.join(OUT, f"v5_{name}.step"))
        if p["kind"] == "print":
            if name == "rotor":
                m = rm.copy(); m.apply_transform(trimesh.transformations.rotation_matrix(-math.pi / 2, (0, 1, 0))); m.apply_translation(-m.bounds[0]); m.export(os.path.join(OUT, "v5_rotor_PRINT.stl"))
                row.update(stl_watertight=bool(m.is_watertight), stl_volume_mm3=round(float(m.volume), 1), stl_vs_step_pct=round((m.volume / s.Volume() - 1) * 100, 2), print_size_mm=[round(v, 1) for v in m.extents])
            elif name == "adapter":
                m = adapter_mesh(); m.apply_transform(trimesh.transformations.rotation_matrix(-math.pi / 2, (0, 1, 0))); m.apply_translation(-m.bounds[0]); m.export(os.path.join(OUT, "v5_adapter_PRINT.stl"))
                row.update(stl_watertight=bool(m.is_watertight), stl_volume_mm3=round(float(m.volume), 1), stl_vs_step_pct=round((m.volume / s.Volume() - 1) * 100, 2), print_size_mm=[round(v, 1) for v in m.extents])
            else:
                so = print_orient(name, s); wt, nf = mb.write_stl_watertight(so, os.path.join(OUT, f"v5_{name}_PRINT.stl"), 0.03, 0.1); bbo = so.BoundingBox()
                row.update(stl_watertight=bool(wt), print_size_mm=[round(bbo.xlen, 1), round(bbo.ylen, 1), round(bbo.zlen, 1)])
        table.append(row); assy.add(cq.Workplane("XY").add(s), name=name, color=cq.Color(*p["color"]))
    assy.save(os.path.join(OUT, "v5_assembly.step"))
    return table

# ----------------------------------------------------------------- figures
def figures(parts, lay):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    L = lay["L"]
    def mesh_of(s, tol=0.15):
        v, t = s.tessellate(tol, 0.2); return trimesh.Trimesh(np.array([(q.x, q.y, q.z) for q in v]), np.array(t), process=True)
    fig, ax = plt.subplots(figsize=(15, 8), facecolor="#fbfaf7"); ax.set_facecolor("#fbfaf7")
    for n, p in parts.items():
        if n == "oring": continue
        m = mesh_of(p["solid"]); sec = m.section(plane_origin=(0, 0, 0), plane_normal=(0, 1, 0))
        if sec is None: continue
        for seg in sec.discrete: ax.plot(seg[:, 0], seg[:, 2], color=p["color"], lw=1.4 if p["kind"] == "print" else 0.9)
    ax.set_aspect("equal"); ax.grid(True, color="#e3e1da", lw=0.7); ax.set_axisbelow(True); ax.set_xlabel("X (mm), flow ->"); ax.set_ylabel("Z (mm)")
    ax.set_title(f"v5 simplified prototype, section through the axis.  Nose tip to lid {L['x_plate1'] - L['x_nose']:.0f} mm ({lay['operating_depth_mm']:.0f} to the gland's end); unbolted: rotor {lay['rotor_depth_mm']:.0f} mm, housing + mount {lay['housing_mount_depth_mm']:.0f} mm ({lay['housing_mount_depth_with_gland_mm']:.0f} with the gland)", loc="left", fontsize=10.5, fontweight="bold")
    notes = [("ROTOR (one print): nose, hub cup, 3 blades, double-D neck; 12 mm stainless sleeve glued on the neck", (-5, 60), (-90, 118)),
             ("central M3 x 50 bolt through the nose into the captive nut in the adapter: rotor thrust goes neck end -> adapter -> bell -> GL60 bearings -> stand-offs -> mount", (L['x_ad1'], 0), (30, -118)),
             ("HOUSING (one print): snout with ONE 12x28x7 lip seal + ONE 6001 bearing, flat front wall, flange with 6 M4 inserts", (Q['snout_x0'] + 6, 20), (-90, 95)),
             ("MOUNT (one print): rear lid with face O-ring + 6 x M4, GL60 stator on 6 mm stand-offs, PG7 gland, arm to a 40 mm stake socket", (L['x_plate1'], -30), (60, -75)),
             ("GL60 KV25 (dry): bell bolted to the adapter (4 x M3), stator bolted to the lid (4 x M2.5 + bonded washers)", (L['x_bell'] + 11, 30), (100, 80))]
    for txt, p0, p1 in notes:
        ax.annotate(txt, xy=p0, xytext=p1, fontsize=8.5, color="#333", arrowprops=dict(arrowstyle="->", color="#555", lw=0.8))
    ax.set_xlim(-110, 160); ax.set_ylim(-180, 125)
    fig.savefig(os.path.join(OUT, "fig_v5_section.png"), dpi=140, facecolor="#fbfaf7", bbox_inches="tight"); plt.close(fig)
    # exploded isometric
    explode = {"rotor": -45, "sleeve": -45, "rotor_bolt": -60, "housing": 0, "seal": -20, "bearing": -12, "adapter": 25, "rotor_nut": 30, "motor": 40, "mount": 75, "gland": 75, "oring": 75}
    fig = plt.figure(figsize=(15, 9), facecolor="#fbfaf7"); ax3 = fig.add_subplot(111, projection="3d", facecolor="#fbfaf7"); allx = []
    for n, p in parts.items():
        if n.startswith(("plate_screw", "insert_", "base_screw", "bell_screw", "oring")): continue
        m = mesh_of(p["solid"], 0.3); tris = m.triangles + np.array([explode.get(n, 0), 0, 0]); allx += [tris[:, :, 0].min(), tris[:, :, 0].max()]
        nrm = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]); nrm /= np.linalg.norm(nrm, axis=1)[:, None] + 1e-12
        sh = 0.55 + 0.45 * np.clip(nrm @ np.array([0.4, -0.5, 0.77]), 0, 1); cols = np.c_[np.outer(sh, p["color"]), np.full(len(sh), 0.35 if n == "housing" else 1.0)]
        ax3.add_collection3d(Poly3DCollection(tris, facecolors=cols, edgecolors="none"))
    ax3.set_xlim(min(allx) - 10, max(allx) + 10); ax3.set_ylim(-175, 110); ax3.set_zlim(-175, 110); ax3.set_box_aspect((max(allx) - min(allx) + 20, 285, 285), zoom=1.5); ax3.view_init(elev=22, azim=-55); ax3.set_axis_off()
    fig.suptitle("v5 simplified prototype, exploded (water flows left to right): rotor | seal + bearing | housing | adapter + nut | GL60 | mount (lid + stand-offs + arm + socket)", x=0.03, ha="left", fontsize=12, fontweight="bold")
    fig.savefig(os.path.join(OUT, "fig_v5_exploded.png"), dpi=140, facecolor="#fbfaf7", bbox_inches="tight"); plt.close(fig)

if __name__ == "__main__":
    sel = json.load(open(os.path.join(V4, "model", "selected_design.json")))
    parts, lay = build(sel)
    table = export(parts, lay, sel)
    bad = {k: v for k, v in lay["interference_mm3"].items() if v > 0.5 or v < 0}
    print(f"[v5] depth nose->plate {lay['operating_depth_mm']:.1f} mm; rotor {lay['rotor_depth_mm']:.1f}, housing+mount {lay['housing_mount_depth_mm']:.1f} ({lay['housing_mount_depth_with_gland_mm']:.1f} with gland); pairs {lay['pairs_checked']}; interference {bad or 'none'}; seal lip {lay['seal_lip_overlap_mm3']}; clearances {lay['clearances_mm']}")
    for r in table:
        if r["kind"] == "print": print("  ", r["name"], "valid", r["valid"], "solids", r["n_solids"], "stl", r.get("stl_watertight"), "size", r.get("print_size_mm"), "vol", r["volume_mm3"], r.get("stl_vs_step_pct", ""))
    figures(parts, lay)
    json.dump(dict(layout=lay, parts=table, selected=sel), open(os.path.join(OUT, "v5_info.json"), "w"), indent=1, default=float)
    print("figures + v5_info.json written")
