#!/usr/bin/env python
"""Low-flow turbine v4, arrangement A: rotor on a short 316 shaft in front of a stationary sealed nacelle holding the GL60.

Frame: +X = flow; rotor axis = X; Z radial up.  All dimensions mm.  Parts:
  rotor (detachable at the M5 shaft joint): nose plug, front hub half (with nose), rear hub half, 3 blades (airfoil-tongue roots), 3x M3 x 40
         through-bolts (counterbored heads, washers, nylocs in rear pockets), M3 hub screw + 13 mm washer, rotor shaft (316, 8 h6: D-flat, DIN 471-8
         groove A + 316 washer = hub thrust stop, 6 h7 spigot + M5 male thread)
  nacelle: stub shaft (316, 8 h6: M5 tapped joint, seal journal, integral collar B between the seal and the bearing, circlip groove, pinned tail),
           3 in 6061 tube (bored 73.1 at the lands), front cap (flange 80 for the clamp lips, 1 O-ring, 30 mm boss: 8x22x7 PTFE lip seal | collar B |
           608-2RS | DIN 472-22 ring), rear cap (1 O-ring, GL60 mount, WetLink M10 at 45 deg, M6 vent at 225 deg, splice pocket), TPU dog disc on
           the bell, printed dog hub on the stub tail
  support: printed full-length shell clamp (two halves, 4x M4 lugs) whose end lips trap both cap flanges; 3 printed L-struts bolted to shell bosses
           (2x M4 inserts each) whose feet splice the guard ring joints (2x M3 inserts per arc end); guard ring ID 214 x 40 as three 120-deg arcs,
           the bottom arc with a 40 mm stake socket (16.2 bore, 4 mm wall)
Selected blade geometry comes from ../model/selected_design.json (chord/twist/airfoil per station, blended to NACA 4418 at the root)."""
import json, math, os, sys, itertools
import numpy as np
import cadquery as cq
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "..", "water_turbine_blade")); import make_blade as mb
sys.path.insert(0, os.path.join(ROOT, "model"))
OUT = os.path.join(ROOT, "out"); os.makedirs(OUT, exist_ok=True)

P = dict(
    r_tip=101.6, r_hub=28.0, hub_len=36.0, hub_front_len=14.0, nose_len=22.0, pocket_floor_r=16.0, pocket_clear=0.25, bolt_r=22.0, bolt_d=3.4, bolt_cb_d=7.5, bolt_seat=3.5, nut_pocket_depth=5.5, bolt_len=40.0,
    shaft_d=8.0, flat_depth=1.0, collar_d=12.0, collar_w=3.0, seal_w=7.0, seal_od=22.0, brg_od=22.0, brg_w=7.0, brg_bore=8.0, circlip_w=0.9, circlip_groove_d=7.6,
    spigot_d=6.0, spigot_len=3.0, thread_d=5.0, thread_len=8.0, joint_setback=3.0,
    washer_t=1.0, washer_od=14.0, iring_w=1.0, iring_groove_w=1.1, iring_groove_d=23.0, iring_id=19.6, boss_od=30.0, boss_lip=1.0,
    tail_len=12.0, pin_d=3.0, hub_screw="M3", hub_screw_d=3.0, hub_screw_tap=2.5, hub_washer_d=13.0, hub_washer_t=1.5, nose_pocket_d=14.5,
    tube_od=76.2, tube_id=73.1, plug_clear=0.15, oring_cs=2.62, oring_groove_w=3.6, oring_groove_d=2.08, oring_land=1.5, flange_t=3.0, flange_od=80.0, plug_len=6.5,
    motor_od=69.0, motor_len=22.3, motor_bore=20.0, motor_pcd=50.0, bell_pcd=40.0, cb_d=6.0, cb_depth=2.2,
    disc_t=2.5, disc_od=50.0, dog_pcd=20.0, dog_d=6.0, dog_h=3.0, doghub_od=30.0, doghub_len=6.0,
    gap_rotor_cap=4.0, ic_front=1.0, ic_rear=4.5, wetlink_r=19.0, wetlink_deg=45.0, wetlink_thread=10.0, wetlink_nut_od=17.0, wetlink_nut_h=12.0, wetlink_cb_d=22.0, wetlink_cb_depth=6.5,
    wetlink_in_d=12.0, wetlink_in_h=3.0, vent_r=22.0, vent_deg=225.0, splice_d=20.0, splice_depth=4.0,
    clamp_w=14.0, clamp_t=6.0, shell_t=6.0, lip_t=3.0, lug_w=14.0, lug_h=10.0, lug_hole=4.4, boss_h=2.0, strut_w=18.0, strut_t=6.0, strut_pad=24.0, foot_w_deg=20.0, foot_t=3.0,
    duct_id=214.0, duct_od=226.0, duct_len=40.0, sock_len=40.0, sock_bore=16.2, sock_wall=4.0, insert_m3=4.0, insert_m4=5.6,
)
# ----------------------------------------------------------------- helpers (as make_v3)
def cyl(x0, L, d): return cq.Workplane("YZ").workplane(offset=x0).circle(d / 2).extrude(L).val()
def tube(x0, L, od, idia): return cq.Workplane("YZ").workplane(offset=x0).circle(od / 2).circle(idia / 2).extrude(L).val()
def torus(x, mean_d, cs): return cq.Workplane("XY").add(cq.Solid.makeTorus(mean_d / 2, cs / 2, cq.Vector(x, 0, 0), cq.Vector(1, 0, 0))).val()
def W(s): return cq.Workplane("XY").add(s)
def rotX(s, deg): return s.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), deg)
def hole_x(d, x0, L, y, z): return cq.Solid.makeCylinder(d / 2, L, cq.Vector(x0, y, z), cq.Vector(1, 0, 0))
def hole_dir(d, L, p, v): return cq.Solid.makeCylinder(d / 2, L, cq.Vector(*p), cq.Vector(*v))
def box_x_r(x0, x1, w, r0, r1, deg):
    b = cq.Workplane("XY").box(x1 - x0, w, r1 - r0, centered=(False, True, False)).translate((x0, 0, r0)).val(); return rotX(b, deg)

# ----------------------------------------------------------------- airfoil sections (general coordinates, root blend)
N_PTS = 60
def load_coords(name):
    tabs = json.load(open(os.path.join(ROOT, "model", "polars_cache.json")))
    return np.array(tabs[name]["coords"])
def resample(coords, n=N_PTS):
    """UIUC order (TE -> upper -> LE -> lower -> TE) to cosine-spaced upper/lower y(x) arrays on [0,1]"""
    c = np.asarray(coords, float); i_le = int(np.argmin(c[:, 0]))
    up = c[:i_le + 1][::-1]; lo = c[i_le:]
    x = 0.5 * (1 - np.cos(np.linspace(0, np.pi, n)))
    # normalise chord to [0,1]
    xmin, xmax = c[:, 0].min(), c[:, 0].max(); up = (up - [xmin, 0]) / (xmax - xmin); lo = (lo - [xmin, 0]) / (xmax - xmin)
    yu = np.interp(x, up[:, 0], up[:, 1]); yl = np.interp(x, lo[:, 0], lo[:, 1])
    return x, yu, yl
def section_pts(outer_xy, root_xy, w_root, r, chord, twist_deg, te_thick=1.0):
    """blend outer/root profiles (same x stations), scale to chord, blunt TE, place on the cylinder r (make_blade.place mapping).
    Returns the closed loop (upper TE->LE, lower LE->TE) as 3-D points, like make_blade.section_wire."""
    x, yu_o, yl_o = outer_xy; _, yu_r, yl_r = root_xy
    yu = (1 - w_root) * yu_o + w_root * yu_r; yl = (1 - w_root) * yl_o + w_root * yl_r
    yu = yu + 0.5 * (te_thick / chord) * x; yl = yl - 0.5 * (te_thick / chord) * x
    up = np.c_[x, yu] * chord; lo = np.c_[x, yl] * chord
    up3, lo3 = mb.place(up, r, chord, twist_deg), mb.place(lo, r, chord, twist_deg)
    return np.r_[up3[::-1], lo3[1:]]
def radial_ring(loop_at_ref, r_ref, r_eval):
    """loop points on the cylinder r_ref -> the same angular positions on the cylinder r_eval (radial projection: the tongue is a
    radial extrusion of the hub-surface section, not a constant-arc-length wrap, so it narrows toward the axis)"""
    p = np.asarray(loop_at_ref, float).copy(); p[:, 1:] *= r_eval / r_ref; return p

def wire_from_loop(pts):
    n = (len(pts) + 1) // 2; V = lambda q: cq.Vector(float(q[0]), float(q[1]), float(q[2]))
    e_up = cq.Edge.makeSpline([V(q) for q in pts[:n]]); e_lo = cq.Edge.makeSpline([V(q) for q in pts[n - 1:]]); e_te = cq.Edge.makeLine(V(pts[-1]), V(pts[0]))
    return cq.Wire.assembleEdges([e_up, e_lo, e_te])
def unrolled_outline(outer_xy, root_xy, w_root, chord, twist_deg, te_thick=1.0):
    x, yu_o, yl_o = outer_xy; _, yu_r, yl_r = root_xy
    yu = (1 - w_root) * yu_o + w_root * yu_r + 0.5 * (te_thick / chord) * x; yl = (1 - w_root) * yl_o + w_root * yl_r - 0.5 * (te_thick / chord) * x
    pts = np.r_[(np.c_[x, yu] * chord)[::-1], (np.c_[x, yl] * chord)[1:]]
    bt = math.radians(twist_deg); xi = pts[:, 0] - mb.PITCH_AXIS * chord; eta = pts[:, 1]
    return np.c_[xi * math.sin(bt) + eta * math.cos(bt), -xi * math.cos(bt) + eta * math.sin(bt)]

def blade_stations(sel):
    """station arrays from the selected design (element centres from the model) resampled to ~24 stations from r_hub to the tip"""
    r = np.array(sel["r_mm"]); c = np.array(sel["chord_mm"]); tw = np.array(sel["twist_deg"]); wr = np.array(sel["w_root"])
    rs = np.r_[np.linspace(P["r_hub"], 0.9 * P["r_tip"], 24), 0.9 * P["r_tip"] + 0.1 * P["r_tip"] * np.sin(0.5 * np.pi * np.linspace(0, 1, 9)[1:])]
    return rs, np.interp(rs, r, c), np.interp(rs, r, tw), np.interp(rs, r, wr)

def build_blade(sel, x_pad):
    outer = resample(load_coords(sel["airfoil"])); root = resample(load_coords(sel.get("root_airfoil", "naca4418")))
    rs, cs, tws, wrs = blade_stations(sel)
    wires = [wire_from_loop(section_pts(outer, root, w, r, c, tw)) for r, c, tw, w in zip(rs, cs, tws, wrs)]
    r_floor = P["pocket_floor_r"] + P["pocket_clear"]
    w_in = wire_from_loop(radial_ring(section_pts(outer, root, wrs[0], P["r_hub"], cs[0], tws[0]), P["r_hub"], r_floor))
    faces = mb.thru_sections(wires, ruled=False) + mb.thru_sections([w_in, wires[0]], ruled=True)
    caps = [cq.Face.makeNSidedSurface(w_in.Edges(), []), cq.Face.makeNSidedSurface(wires[-1].Edges(), [])]
    sol = mb.sew_solid(faces + caps)
    if not sol.isValid(): raise RuntimeError("blade solid invalid")
    b = W(sol.translate(cq.Vector(x_pad, 0, 0)))
    b = b.cut(W(hole_x(P["bolt_d"], x_pad - 40, 80, 0, P["bolt_r"])))          # axial through-bolt at r = bolt_r in the tongue
    outline = unrolled_outline(outer, root, wrs[0], cs[0], tws[0])
    return b.val(), dict(r=rs.tolist(), chord=cs.tolist(), twist=tws.tolist(), w_root=wrs.tolist(), outline=outline.tolist())

def pocket_solid(outline, clear, r_floor, r_top, r_above, x_shift):
    pts = np.asarray(outline); n = len(pts)
    area = 0.5 * np.sum(pts[:, 0] * np.roll(pts[:, 1], -1) - np.roll(pts[:, 0], -1) * pts[:, 1]); sgn = 1.0 if area > 0 else -1.0
    out = np.empty_like(pts)
    for i in range(n):
        t = pts[(i + 1) % n] - pts[i - 1]; t /= np.linalg.norm(t); out[i] = pts[i] + clear * sgn * np.array([t[1], -t[0]])
    def wrap(r):
        th = out[:, 1] / P["r_hub"]; p3 = np.c_[out[:, 0] + x_shift, r * np.sin(th), r * np.cos(th)]; return wire_from_loop(p3)   # radial projection of the hub-surface outline
    def piece(ra, rb):
        ws = [wrap(ra), wrap(rb)]; faces = mb.thru_sections(ws, ruled=True)
        caps = [cq.Face.makeNSidedSurface(ws[0].Edges(), []), cq.Face.makeNSidedSurface(ws[-1].Edges(), [])]
        sol = mb.sew_solid(faces + caps)
        if not sol.isValid(): raise RuntimeError("pocket piece invalid")
        return sol
    # one piece spanning the tongue's radii with the same ruled-surface parametrisation as the blade stub (uniform clearance), ending 0.3 mm
    # outside the hub cylinder so no wire coincides with it; the former second piece (from 0.5 mm below the surface) left a sliver face (review M10)
    return [piece(r_floor, r_top + 0.3)]

def blade_print_mesh(sel, x_pad, k=0):
    """closed structured mesh of the blade in print orientation (pressure side down, span along X, low line levelled)"""
    import trimesh
    outer = resample(load_coords(sel["airfoil"])); root = resample(load_coords(sel.get("root_airfoil", "naca4418")))
    rs, cs, tws, wrs = blade_stations(sel); r_floor = P["pocket_floor_r"] + P["pocket_clear"]
    rings = [radial_ring(section_pts(outer, root, wrs[0], P["r_hub"], cs[0], tws[0]), P["r_hub"], r_floor)] + [section_pts(outer, root, w, r, c, tw) for r, c, tw, w in zip(rs, cs, tws, wrs)]
    N = len(rings[0]); V = np.vstack(rings); V[:, 0] += x_pad; F = []
    for a in range(len(rings) - 1):
        o0, o1 = a * N, (a + 1) * N
        for i in range(N):
            j = (i + 1) % N; F.append((o0 + i, o0 + j, o1 + i)); F.append((o0 + j, o1 + j, o1 + i))
    n = (N + 1) // 2
    def zipper(o, flip):
        tri = []
        for j in range(n - 1):
            u0, u1 = o + (n - 1 - j), o + (n - 2 - j); l0, l1 = o + (n - 1 + j), o + (n + j)
            tri.append((u0, u1, l1)); 
            if j: tri.append((u0, l1, l0))
        return [t[::-1] for t in tri] if flip else tri
    F += zipper(0, False) + zipper((len(rings) - 1) * N, True)
    m = trimesh.Trimesh(V, np.array(F), process=True); m.update_faces(m.nondegenerate_faces(height=1e-7)); m.remove_unreferenced_vertices(); m.fix_normals()
    assert m.is_watertight
    pin = trimesh.creation.cylinder(radius=P["bolt_d"] / 2, height=80.0, sections=48, transform=trimesh.transformations.concatenate_matrices(
        trimesh.transformations.translation_matrix((x_pad, 0, P["bolt_r"])), trimesh.transformations.rotation_matrix(math.pi / 2, (0, 1, 0))))
    try:
        m2 = trimesh.boolean.difference([m, pin], engine="manifold")
        if m2.is_watertight and 0.9 * m.volume < m2.volume < m.volume: m = m2
    except Exception as e: print("bolt-hole boolean failed:", e)
    Rm = trimesh.transformations.rotation_matrix
    m.apply_transform(Rm(math.radians(90), (0, 1, 0))); m.apply_transform(Rm(math.pi, (1, 0, 0)))
    xmin, xmax = m.bounds[0][0], m.bounds[1][0]
    def zmin_in(x0, x1):
        sel_ = (m.vertices[:, 0] >= x0) & (m.vertices[:, 0] <= x1); return m.vertices[sel_, 2].min()
    xr0 = xmin + (P["r_hub"] - r_floor) + 2.0; zr = zmin_in(xr0, xr0 + 12.0); zt = zmin_in(xmax - 12.0, xmax)
    tilt = math.atan2(zr - zt, (xmax - 6.0) - (xr0 + 6.0)); m.apply_transform(Rm(-tilt, (0, 1, 0))); m.apply_transform(trimesh.transformations.translation_matrix(-m.bounds[0]))
    return m, math.degrees(tilt)

# ----------------------------------------------------------------- parts
def hub_halves(x_pad, outline, n_blades):
    """one-piece hub cylinder with nose, 3 radial airfoil pockets, D-bore, bolt holes, nose pocket; split at x = x_pad into front/rear halves"""
    L = P["hub_len"]; x0 = x_pad - P["hub_front_len"]; r = P["r_hub"]
    hub = W(cyl(x0, L, 2 * r))
    def cutc(a, b): return a.cut(b, clean=False)                       # the sewn airfoil pockets break CadQuery's post-Boolean face unification
    # nose: ellipsoidal cap (revolved) on the front face
    h = P["nose_len"]; t = np.linspace(0, np.pi / 2, 30)
    pts = [(x0 - h * math.sin(a), r * math.cos(a)) for a in t[1:]]
    nose = (cq.Workplane("XY").moveTo(x0, 0).lineTo(x0, r).spline(pts, includeCurrent=True).close().revolve(360, (0, 0, 0), (1, 0, 0))).val()
    hub = hub.union(W(nose), clean=False)
    for k in range(n_blades):
        for pc in pocket_solid(outline, P["pocket_clear"], P["pocket_floor_r"], r, r + 10, x_pad):
            hub = cutc(hub, W(rotX(pc, 360 * k / n_blades)))
        a = math.radians(360 * k / n_blades); yz = (P["bolt_r"] * math.sin(a), P["bolt_r"] * math.cos(a))
        hub = cutc(hub, W(hole_x(P["bolt_d"], x0 - h - 1, L + h + 2, *yz)))
        hub = cutc(hub, W(hole_x(P["bolt_cb_d"], x0 + L - P["nut_pocket_depth"], P["nut_pocket_depth"] + 1, *yz)))   # nut pocket on the rear face: 7 mm washer + M3 nyloc (held by a wrench)
        hub = cutc(hub, W(hole_x(P["bolt_cb_d"], x0 - h - 1, (h + 1) - P["bolt_seat"], *yz)))                       # head counterbore from the nose surface to a seat 3.5 mm ahead of the hub body (review M1)
    # D-bore through, nose pocket for the retaining screw head, front hole to reach it
    dbore = W(cyl(x0 - h - 1, L + h + 2, P["shaft_d"] + 0.2)).cut(W(cq.Workplane("XY").box(L + h + 4, 20, 10, centered=(False, True, False)).translate((x0 - h - 2, 0, P["shaft_d"] / 2 - P["flat_depth"] + 0.1)).val())).val()
    hub = cutc(hub, W(dbore))
    hub = cutc(hub, W(cyl(x0 - h - 1, h + 1 + 0.01, P["nose_pocket_d"])))                                        # 14.5 access hole from the nose tip to the hub front floor (13 mm washer passes; review C4)
    front = hub.val().intersect(cq.Solid.makeBox(200, 200, 200, cq.Vector(x_pad - 200, -100, -100)))
    rear = hub.val().intersect(cq.Solid.makeBox(200, 200, 200, cq.Vector(x_pad, -100, -100)))
    def tidy(sol):
        """unify same-domain faces after the un-cleaned Booleans (removes the sliver faces that failed BRepCheck in the review, M-m2);
        kept only if the result is a single valid solid of the same volume"""
        try:
            c = sol.clean()
            if c.isValid() and len(c.Solids()) == 1 and abs(c.Volume() - sol.Volume()) < 1e-3 * sol.Volume(): return c
        except Exception: pass
        return sol
    return tidy(front), tidy(rear)

def rotor_shaft(x_hub_rear, x_joint):
    """316, 8 h6, part of the detachable rotor: M3 tapped front end (hub retainer, 0.5 mm below the hub's front floor so the 13 mm washer clamps
    the hub), D-flat running out through the tip, DIN 471-8 groove A behind the hub washer (hub thrust stop), shoulder at x_joint bearing on the
    stub's front face, 6 h7 spigot x 3 and M5 male thread x 8 (RH thread: the generator reaction torque tightens it; Loctite 222)"""
    x_tip = x_hub_rear - P["hub_len"] + 0.5
    xA0 = x_hub_rear + P["washer_t"] + 0.1; xA1 = xA0 + P["circlip_w"]
    s = W(cyl(x_tip, x_joint - x_tip, P["shaft_d"]))
    s = s.union(W(cyl(x_joint - 0.01, P["spigot_len"] + 0.01, P["spigot_d"]))).union(W(cyl(x_joint + P["spigot_len"] - 0.01, P["thread_len"] + 0.01, P["thread_d"])))
    flat = cq.Workplane("XY").box(x_hub_rear + 0.5 - (x_tip - 1.0), 20, 10, centered=(False, True, False)).translate((x_tip - 1.0, 0, P["shaft_d"] / 2 - P["flat_depth"])).val()
    s = s.cut(W(flat))                                                                                               # D-flat from the tip to 0.5 mm behind the hub
    s = s.cut(W(tube(xA0, P["circlip_w"], P["shaft_d"] + 1, P["circlip_groove_d"])))                                 # DIN 471-8 groove A (d2 7.6)
    s = s.cut(W(cyl(x_tip - 1, 1 + 7.0, P["hub_screw_d"] + 0.05)))                                                   # M3 tapped 7 deep (hub retaining screw; modelled at the major diameter)
    return s.val(), dict(x_tip=x_tip, xA=[xA0, xA1], x_joint=x_joint, x_end=x_joint + P["spigot_len"] + P["thread_len"])

def stub_shaft(x_joint, x_brg0, x_tail0):
    """316, 8 h6, captive in the nacelle: front face at x_joint with a 6 H7 x 3 spigot bore and an M5 tapped hole (modelled at the major
    diameter), seal journal (Ra 0.2; hard-chrome or a hardened sleeve recommended under the PTFE lip), integral collar B between the seal and the
    bearing (bearing thrust stop; the stub enters the 22 mm bore from the dry side and the bearing is pressed over the tail), DIN 471-8 groove
    behind the bearing (reverse stop, 0.3 mm end play), tail ending inside the dog hub, cross-pin hole"""
    xB1 = x_brg0 - 0.1; xB0 = xB1 - P["collar_w"]
    x_end = x_tail0 + P["doghub_len"] - 0.5
    s = W(cyl(x_joint, x_end - x_joint, P["shaft_d"])).union(W(cyl(xB0, P["collar_w"], P["collar_d"])))
    s = s.cut(W(cyl(x_joint - 1, 1 + P["spigot_len"], P["spigot_d"] + 0.02)))                                          # 6 H7 spigot bore
    s = s.cut(W(cyl(x_joint + P["spigot_len"] - 0.01, P["thread_len"] + 1.0, P["thread_d"] + 0.05)))                   # M5 tapped (+1 mm drill point)
    s = s.cut(W(tube(x_brg0 + P["brg_w"] + 0.2, P["circlip_w"], P["shaft_d"] + 1, P["circlip_groove_d"])))             # DIN 471-8 groove behind the bearing
    s = s.cut(W(hole_dir(P["pin_d"] + 0.1, 30, (x_tail0 + P["doghub_len"] / 2, -15, 0), (0, 1, 0))))                   # coupling pin
    return s.val(), dict(xB=[xB0, xB1], x_end=x_end, x_front=x_joint)

def front_cap(x_wet):
    """flange 80 x 3 (wet side; the clamp's front lip bears on it) + plug 6.5 into the bored tube + rear boss (30 OD) that houses the bearing
    completely; one 22 mm bore from the wet face, open to the dry side: PTFE lip seal (7) | collar B zone (3.2) | 608 bearing (7) | DIN 472-22
    internal-ring groove (the rotor-thrust shoulder) | 1 mm lip; one O-ring (AS568-146, groove 3.6 x 2.08, 1.5 / 1.4 mm lands)"""
    t = P["flange_t"]; L = P["plug_len"]; rp = (P["tube_id"] - P["plug_clear"]) / 2
    x_brg = x_wet + P["seal_w"] + P["collar_w"] + 0.2
    x_ring = x_brg + P["brg_w"] + 0.1
    x_boss_end = x_ring + P["iring_groove_w"] + P["boss_lip"]
    c = W(cyl(x_wet, t, P["flange_od"])).union(W(cyl(x_wet + t, L, 2 * rp))).union(W(cyl(x_wet + t + L - 0.01, x_boss_end - (x_wet + t + L) + 0.01, P["boss_od"])))
    g_od = 2 * rp - 2 * P["oring_groove_d"]; xg = x_wet + t + P["oring_land"]
    c = c.cut(W(tube(xg, P["oring_groove_w"], P["tube_id"] + 1, g_od)))
    c = c.cut(W(cyl(x_wet - 1, x_boss_end - x_wet + 2, P["seal_od"])))         # 22 bore through (H8 in the seal zone, N7 in the bearing zone)
    c = c.cut(W(tube(x_ring, P["iring_groove_w"], P["iring_groove_d"], P["seal_od"] - 0.5)))   # DIN 472-22 groove: thrust shoulder for the outer race
    oring = torus(xg + P["oring_groove_w"] / 2, g_od + P["oring_cs"], P["oring_cs"])
    return c.val(), oring, dict(x_seal=x_wet, x_brg=x_brg, x_ring=x_ring, x_boss_end=x_boss_end, x_in=x_wet + t + L, groove_bottom_d=g_od)

def wetlink_yz(): a = math.radians(P["wetlink_deg"]); return -P["wetlink_r"] * math.sin(a), P["wetlink_r"] * math.cos(a)
def vent_yz(): a = math.radians(P["vent_deg"]); return -P["vent_r"] * math.sin(a), P["vent_r"] * math.cos(a)

def rear_cap(x_in):
    """plug 6.5 into the bored tube + flange 80 x 3 (the clamp's rear lip bears on it); 6061: 4x M3 PCD 40 and 4x M2.5 PCD 50 blind tapped
    5 deep from the inner face (GL60 stator, both patterns), WetLink M10 x 1.5 tapped through at r 19 on the 45 deg line with a 22 mm
    counterbore 6.5 deep outside (the nut's top 5.5 mm stands proud for an open-end wrench; the counterbore keeps 4 mm of wall to the O-ring groove), M6 vent at 225 deg, 20 x 4 splice pocket in the centre of the inner face (phase leads to the
    cable; the GL60 is hollow-bored); the leads run in the 4.5 mm gap between the stator base and the cap"""
    t = P["flange_t"]; L = P["plug_len"]; rp = (P["tube_id"] - P["plug_clear"]) / 2
    x_fl = x_in + L
    c = W(cyl(x_in, L, 2 * rp)).union(W(cyl(x_fl, t, P["flange_od"])))
    g_od = 2 * rp - 2 * P["oring_groove_d"]; xg = x_fl - P["oring_land"] - P["oring_groove_w"]
    c = c.cut(W(tube(xg, P["oring_groove_w"], P["tube_id"] + 1, g_od)))
    for k in range(4):
        a = math.radians(90 * k)
        for pcd in (P["bell_pcd"], P["motor_pcd"]):
            c = c.cut(W(hole_x(2.5, x_in - 1, 6.0, pcd / 2 * math.cos(a), pcd / 2 * math.sin(a))))      # M3 / M2.5 blind tapped 5 deep from the inner face
    yw, zw = wetlink_yz(); yv, zv = vent_yz()
    c = c.cut(W(hole_x(P["wetlink_thread"], x_in - 1, L + t + 2, yw, zw)))                               # M10 x 1.5 WetLink penetrator (tapped through), 45 deg
    c = c.cut(W(hole_x(P["wetlink_cb_d"], x_fl + t - P["wetlink_cb_depth"], P["wetlink_cb_depth"] + 1, yw, zw)))   # counterbore: nut + socket clearance
    c = c.cut(W(hole_x(5.2, x_in - 1, L + t + 2, yv, zv)))                                               # M6 vent at 225 deg
    c = c.cut(W(cyl(x_in - 1, 1 + P["splice_depth"], P["splice_d"])))                                    # splice pocket (centre, inner face)
    oring = torus(xg + P["oring_groove_w"] / 2, g_od + P["oring_cs"], P["oring_cs"])
    return c.val(), oring, dict(x_fl=x_fl, x_out=x_fl + t, groove_bottom_d=g_od)

def drive_parts(x_tail0, x_bell):
    """dog hub on the stub tail (printed ASA, cross-pinned) with 2 dogs 6 x 3; TPU disc 2.5 on the bell face with 2 through pockets;
    the dogs enter the disc by dog_h - ic_front = 2.0 mm and stop 0.5 mm short of the bell"""
    dh = W(cyl(x_tail0, P["doghub_len"], P["doghub_od"])).cut(W(cyl(x_tail0 - 1, P["doghub_len"] + 2, P["shaft_d"] + 0.2)))
    dh = dh.cut(W(hole_dir(P["pin_d"] + 0.1, 40, (x_tail0 + P["doghub_len"] / 2, -20, 0), (0, 1, 0))))
    for k in range(2):
        a = math.radians(90 + 180 * k); dog = cyl(x_tail0 + P["doghub_len"] - 0.5, P["dog_h"] + 0.5, P["dog_d"]).translate(cq.Vector(0, P["dog_pcd"] / 2 * math.cos(a), P["dog_pcd"] / 2 * math.sin(a)))
        dh = dh.union(W(dog))
    disc = W(tube(x_bell - P["disc_t"], P["disc_t"], P["disc_od"], P["motor_bore"] + 2))
    for k in range(4):
        a = math.radians(90 * k); disc = disc.cut(W(hole_x(3.4, x_bell - P["disc_t"] - 1, P["disc_t"] + 2, P["bell_pcd"] / 2 * math.cos(a), P["bell_pcd"] / 2 * math.sin(a))))
    for k in range(2):
        a = math.radians(90 + 180 * k); disc = disc.cut(W(hole_x(P["dog_d"] + 0.4, x_bell - P["disc_t"] - 1, P["disc_t"] + 2, P["dog_pcd"] / 2 * math.cos(a), P["dog_pcd"] / 2 * math.sin(a))))
    return dh.val(), disc.val()

def sector(x0, L, r_in, r_out, a0, a1):
    """annular sector solid between angles a0..a1 (deg, 0 = +Z, positive towards -Y like rotX), from x0 over L"""
    def pt(r, a): a = math.radians(a); return (-r * math.sin(a), r * math.cos(a))
    am = 0.5 * (a0 + a1)
    w = (cq.Workplane("YZ").workplane(offset=x0).moveTo(*pt(r_out, a0)).threePointArc(pt(r_out, am), pt(r_out, a1)).lineTo(*pt(r_in, a1))
         .threePointArc(pt(r_in, am), pt(r_in, a0)).close().extrude(L))
    return w.val()

def radial_hole(d, x, r0, r1, deg):
    """cylinder of diameter d along the radial direction at angle deg from r0 to r1 at axial position x"""
    return rotX(hole_dir(d, r1 - r0, (x, 0, r0), (0, 0, 1)), deg)

def support(x_wet, x_out, x_pad):
    """printed shell clamp (two halves split at z = 0, 4x M4 lugs on the parting plane) over the whole tube; its end lips trap both cap flanges
    (positive thrust path and cap retention, review M3); three bosses at 0 / 120 / 240 deg take the struts (2x M4 heat-set inserts each).
    Strut (printed, 3 off, identical): radial leg 18 x 6 from the shell boss to r 122, axial bar 18 x 6 along the outside of the guard ring from
    its front end to the leg, and a 3 mm curved foot 30 mm wide over the ring joint with 4x M3 holes (2 per arc, heat-set inserts in the arcs).
    Guard ring: three 120-deg arcs ID 214 / OD 226 x 40 (each fits a 220 mm bed); the bottom arc carries a 40 mm stake socket (16.2 bore, 4 mm
    wall).  Loads: device drag + thrust (50-60 N at 2 m/s) from the shell through the three struts to the ring and the stake."""
    t = P["shell_t"]; lip = P["lip_t"]; r_tube = P["tube_od"] / 2 + 0.15; r_fl = P["flange_od"] / 2 + 0.15; r_o = P["flange_od"] / 2 + t
    x0 = x_wet - lip; x1 = x_out + lip
    shell = W(cyl(x0, x1 - x0, 2 * r_o))
    # strut bosses (flat pads) at 0 / 120 / 240 deg near the rear, with M4 insert holes
    x_leg0 = x_out - lip - 24.0; x_leg1 = x_leg0 + P["strut_w"]; pad = P["strut_pad"]
    for k in range(3):
        a = 120 * k
        shell = shell.union(W(box_x_r(x_leg0 - 3.0, x_leg1 + 3.0, pad, r_tube + 1.0, r_o + P["boss_h"], a)))
    # lugs on the parting plane (both sides, front and rear)
    for xl in (x_wet + 5.0, x_out - 5.0 - P["lug_w"]):
        for sy in (-1, 1):
            lug = cq.Workplane("XY").box(P["lug_w"], P["lug_h"] + 1.0, 12.0, centered=(False, False, True)).translate((xl, (r_o - 1.0) if sy > 0 else -(r_o + P["lug_h"]), 0)).val()
            shell = shell.union(W(lug))
            shell = shell.cut(W(hole_dir(P["lug_hole"], 20, (xl + P["lug_w"] / 2, sy * (r_o - 1.0 + (P["lug_h"] + 1.0) / 2), -10), (0, 0, 1))))
    shell = shell.cut(W(cyl(x0 - 1, x1 - x0 + 2, 2 * r_tube)))                                  # tube bore through (the lips)
    shell = shell.cut(W(cyl(x_wet - 0.1, P["flange_t"] + 0.2, 2 * r_fl)))                       # front flange recess
    shell = shell.cut(W(cyl(x_out - P["flange_t"] - 0.1, P["flange_t"] + 0.2, 2 * r_fl)))       # rear flange recess
    for k in range(3):                                                                          # M4 insert holes in the bosses (2 per strut)
        a = 120 * k
        for dy in (-8.0, 8.0):
            shell = shell.cut(W(rotX(hole_dir(P["insert_m4"], 7.0, (x_leg0 + P["strut_w"] / 2, dy, r_o + P["boss_h"] - 6.5), (0, 0, 1)), a)))
    shell_top = shell.val().intersect(cq.Solid.makeBox(400, 400, 200, cq.Vector(-200, -200, 0)))
    shell_bot = shell.val().intersect(cq.Solid.makeBox(400, 400, 200, cq.Vector(-200, -200, -200)))
    # guard ring arcs (joints at 0 / 120 / 240 deg, under the strut feet); bottom arc (120..240) carries the socket
    xd0 = x_pad - 18.0; xd1 = xd0 + P["duct_len"]; r_do = P["duct_od"] / 2
    arcs = []
    for k in range(3):
        a0 = 120 * k; arc = W(sector(xd0, P["duct_len"], P["duct_id"] / 2, r_do, a0, a0 + 120))
        for aj in (a0 + 7.0, a0 + 120 - 7.0):                                                   # M3 insert holes 7 deg from each joint, at both ends of the ring length
            for xh in (xd0 + 8.0, xd1 - 8.0):
                arc = arc.cut(W(radial_hole(P["insert_m3"], xh, r_do - 5.0, r_do + 1.0, aj)))
        if k == 1:
            w_s = P["sock_bore"] + 2 * P["sock_wall"]
            arc = arc.union(W(box_x_r(xd0, xd1, w_s, r_do - 1.0, r_do + P["sock_len"], 180)))
            arc = arc.cut(W(radial_hole(P["sock_bore"], xd0 + P["duct_len"] / 2, r_do + 1.5, r_do + P["sock_len"] + 5.0, 180)))
        arcs.append(arc.val())
    # strut at angle 0 (the three are identical; rotated copies in the assembly)
    r_bar0 = r_do + P["foot_t"]; r_bar1 = r_bar0 + P["strut_t"]
    strut = W(sector(xd0, P["duct_len"], r_do + 0.1, r_do + P["foot_t"] + 0.1, -P["foot_w_deg"] / 2, P["foot_w_deg"] / 2))                  # curved foot over the joint
    strut = strut.union(W(box_x_r(xd0, x_leg1, P["strut_w"], r_bar0, r_bar1, 0)))                                                            # axial bar
    strut = strut.union(W(box_x_r(x_leg0, x_leg1, P["strut_t"], r_o + P["boss_h"] + 0.1 + P["strut_t"] - 0.01, r_bar1, 0)))                   # radial leg
    strut = strut.union(W(box_x_r(x_leg0 - 3.0, x_leg1 + 3.0, pad, r_o + P["boss_h"] + 0.1, r_o + P["boss_h"] + 0.1 + P["strut_t"], 0)))       # pad on the shell boss
    for dy in (-8.0, 8.0):                                                                                                                   # M4 clearance holes in the pad
        strut = strut.cut(W(hole_dir(4.4, 20, (x_leg0 + P["strut_w"] / 2, dy, r_o - 2.0), (0, 0, 1))))
    for aj in (-7.0, 7.0):                                                                                                                   # M3 clearance holes through foot + bar
        for xh in (xd0 + 8.0, xd1 - 8.0):
            strut = strut.cut(W(radial_hole(3.4, xh, r_do - 1.0, r_bar1 + 1.0, aj)))
    return shell_top, shell_bot, strut.val(), arcs, dict(x_leg=[x_leg0, x_leg1], x_shell=[x0, x1], xd=[xd0, xd1])

def build(sel):
    n_blades = sel["B"]
    parts = {}
    x_pad = 0.0
    bsol, bst = build_blade(sel, x_pad)
    front, rear = hub_halves(x_pad, np.array(bst["outline"]), n_blades)
    x_hub_rear = x_pad - P["hub_front_len"] + P["hub_len"]
    x_wet = x_hub_rear + P["washer_t"] + 0.1 + P["circlip_w"] + P["gap_rotor_cap"]   # washer + circlip A sit in the gap; wet face of the front cap
    x_joint = x_wet - P["joint_setback"]                                              # stub front face / rotor-shaft shoulder
    fc, fo, finfo = front_cap(x_wet)
    x_tail0 = finfo["x_boss_end"] + 1.0                                               # dog hub 1 mm behind the cap boss
    rsh, rinfo_s = rotor_shaft(x_hub_rear, x_joint)
    ssh, sinfo = stub_shaft(x_joint, finfo["x_brg"], x_tail0)
    x_tube0 = x_wet + P["flange_t"]
    x_bell = x_tail0 + P["doghub_len"] + P["ic_front"] + P["disc_t"]                   # bell face; the dogs reach (dog_h - ic_front) into the disc
    x_motor0 = x_bell; x_motor1 = x_motor0 + P["motor_len"]
    x_rc_in = x_motor1 + P["ic_rear"]
    rc, ro_, rinfo = rear_cap(x_rc_in)
    x_tube1 = rinfo["x_fl"]
    L_tube = x_tube1 - x_tube0
    dh, disc = drive_parts(x_tail0, x_bell)
    sh_top, sh_bot, strut0, arcs, suinfo = support(x_wet, rinfo["x_out"], x_pad)
    x0h = x_pad - P["hub_front_len"]
    parts["nose_plug"] = dict(solid=cyl(x0h - P["nose_len"] - 0.5, 6.0, P["nose_pocket_d"] - 0.1), kind="print", color=(0.3, 0.5, 0.8), note="ASA plug closing the 14.5 mm nose access hole (slip fit + silicone)")
    parts["hub_front"] = dict(solid=front, kind="print", color=(0.30, 0.50, 0.80), note="ASA front hub half with nose, half pockets, D-bore, bolt counterbores, 14.5 access hole")
    parts["hub_rear"] = dict(solid=rear, kind="print", color=(0.30, 0.50, 0.80), note="ASA rear hub half with half pockets, D-bore, nut pockets 7.5 x 5.5")
    for k in range(n_blades):
        parts[f"blade_{k}"] = dict(solid=rotX(bsol, 360 * k / n_blades), kind="print", color=(0.35, 0.55, 0.85), note=f"ASA blade ({sel['airfoil']} -> NACA 4418 root), airfoil tongue, 1 axial M3")
        a = math.radians(360 * k / n_blades); y, z = P["bolt_r"] * math.sin(a), P["bolt_r"] * math.cos(a)
        x_seat = x0h - P["bolt_seat"]; x_nut0 = x0h + P["hub_len"] - P["nut_pocket_depth"]
        b = W(hole_x(3.0, x_seat - 1.0, P["bolt_len"] + 1.0, y, z))                                                     # M3 x 40 shank (starts inside the head so the part is one solid)
        b = b.union(W(hole_x(7.0, x_seat - 0.5, 0.5, y, z))).union(W(hole_x(5.5, x_seat - 3.5, 3.0, y, z)))              # washer + socket head in the counterbore
        b = b.union(W(hole_x(7.0, x_nut0, 0.5, y, z))).union(W(hole_x(6.0, x_nut0 + 0.5, 4.0, y, z)))                   # washer + nyloc nut in the rear pocket
        parts[f"bolt_{k}"] = dict(solid=b.val(), kind="COTS", color=(0.4, 0.4, 0.4), note="M3 x 40 316 socket head + 2x 7 mm washers + nyloc (0.2 N m)")
    parts["rotor_shaft"] = dict(solid=rsh, kind="machined", color=(0.55, 0.6, 0.6), note="316 rotor shaft 8 h6: M3 tapped front, D-flat, groove A, 6 h7 spigot + M5 x 8 male thread (RH, Loctite 222)")
    parts["hub_washer"] = dict(solid=tube(x_hub_rear + 0.05, P["washer_t"], P["washer_od"], P["shaft_d"] + 0.4), kind="COTS", color=(0.4, 0.4, 0.4), note="316 washer 14 x 8.4 x 1 between the hub and circlip A")
    parts["circlip_A"] = dict(solid=tube(rinfo_s["xA"][0], P["circlip_w"], 11.0, P["circlip_groove_d"]), kind="COTS", color=(0.3, 0.3, 0.3), note="DIN 471-8 stainless: hub thrust stop (rotor thrust -> washer -> circlip -> shaft)")
    xt = rinfo_s["x_tip"]
    xw1 = x0h - 0.03                                                                                                      # washer face 0.03 mm ahead of the hub floor (model clearance)
    hs = W(cyl(xw1 - P["hub_washer_t"], P["hub_washer_t"], P["hub_washer_d"])).union(W(cyl(xw1 - P["hub_washer_t"] - 3.0, 3.0, 5.5))).union(W(cyl(xw1 - P["hub_washer_t"] + 0.01, (xt + 6.0) - (xw1 - P["hub_washer_t"]), P["hub_screw_d"])))
    parts["hub_screw"] = dict(solid=hs.val(), kind="COTS", color=(0.4, 0.4, 0.4), note="M3 x 10 316 + 13 x 1.5 washer: hub retainer (washer on the hub floor, shaft end 0.5 mm below it)")
    parts["stub_shaft"] = dict(solid=ssh, kind="machined", color=(0.55, 0.6, 0.6), note="316 stub shaft 8 h6 (captive): M5 tapped joint + 6 H7 spigot bore, seal journal Ra 0.2, collar B, rear groove, pin hole")
    parts["front_cap"] = dict(solid=fc, kind="machined", color=(0.85, 0.55, 0.2), note="6061 (anodised) front cap: flange 80, O-ring plug 6.5, 30 mm boss; 22 mm bore: PTFE lip seal 8x22x7 | collar B | 608-2RS | DIN 472-22 groove")
    parts["oring_front"] = dict(solid=fo, kind="COTS", color=(0.1, 0.1, 0.1), note=f"AS568-146 EPDM (ID 66.27 on the {finfo['groove_bottom_d']:.2f} groove bottom)")
    parts["iring"] = dict(solid=tube(finfo["x_ring"] + 0.05, P["iring_w"], P["iring_groove_d"] - 0.2, P["iring_id"]), kind="COTS", color=(0.3, 0.3, 0.3), note="DIN 472-22 stainless internal ring: outer-race thrust shoulder")
    parts["lip_seal"] = dict(solid=tube(finfo["x_seal"] + 0.01, P["seal_w"] - 0.02, P["seal_od"], P["shaft_d"] - 0.5), kind="COTS", color=(0.2, 0.2, 0.2), note="PTFE lip seal 8x22x7 (Varilip PDR class), lip to the water; pressed from the wet face before the stub goes in")
    parts["bearing"] = dict(solid=tube(finfo["x_brg"], P["brg_w"], P["brg_od"], P["brg_bore"]), kind="COTS", color=(0.5, 0.5, 0.55), note="608-2RS 440C stainless (pressed over the stub tail against collar B)")
    parts["circlip"] = dict(solid=tube(finfo["x_brg"] + P["brg_w"] + 0.2, P["circlip_w"], 11.0, P["circlip_groove_d"]), kind="COTS", color=(0.3, 0.3, 0.3), note="DIN 471-8 stainless (reverse-thrust stop, 0.3 mm end play)")
    parts["tube"] = dict(solid=tube(x_tube0, L_tube, P["tube_od"], P["tube_id"]), kind="COTS+machined", color=(0.75, 0.75, 0.78), note=f"6061 tube 3 in x 0.065 in, {L_tube:.1f} mm, ends faced, lands bored {P['tube_id']:.2f} H8, anodised")
    parts["dog_hub"] = dict(solid=dh, kind="print", color=(0.9, 0.3, 0.3), note="ASA dog hub 30 x 6 on the stub tail (3 mm cross pin), 2 dogs 6 x 3")
    parts["coupling_pin"] = dict(solid=hole_dir(3.0, 22, (x_tail0 + P["doghub_len"] / 2, -11, 0), (0, 1, 0)), kind="COTS", color=(0.4, 0.4, 0.4), note="3 x 22 316 dowel")
    parts["drive_disc"] = dict(solid=disc, kind="print", color=(0.9, 0.3, 0.3), note="TPU 95A disc 2.5 on the bell face (4x M3), 2 dog pockets (2.0 mm engagement)")
    parts["motor"] = dict(solid=W(cyl(x_motor0, P["motor_len"], P["motor_od"])).cut(W(cyl(x_motor0 - 1, P["motor_len"] + 2, P["motor_bore"]))).val(), kind="COTS", color=(0.25, 0.25, 0.3), note="CubeMars GL60 KV25 envelope (bell forward)")
    parts["rear_cap"] = dict(solid=rc, kind="machined", color=(0.85, 0.55, 0.2), note="6061 rear cap: flange 80, O-ring plug 6.5, GL60 mount (blind M3/M2.5), WetLink M10 at 45 deg (24 mm counterbore), M6 vent at 225 deg, splice pocket")
    parts["oring_rear"] = dict(solid=ro_, kind="COTS", color=(0.1, 0.1, 0.1), note="AS568-146 EPDM")
    yw, zw = wetlink_yz(); yv, zv = vent_yz()
    wl = W(cyl(rinfo["x_out"] - P["wetlink_cb_depth"] + 0.2, P["wetlink_nut_h"], P["wetlink_nut_od"]).translate(cq.Vector(0, yw, zw)))
    wl = wl.union(W(cyl(x_rc_in - P["wetlink_in_h"], P["wetlink_in_h"] - 0.02, P["wetlink_in_d"]).translate(cq.Vector(0, yw, zw))))        # assumed inner protrusion of the penetrator body (0.02 mm model gap to the cap)
    wl = wl.union(W(cyl(x_rc_in - P["wetlink_in_h"] + 0.5, (rinfo["x_out"] - P["wetlink_cb_depth"] + 0.3) - (x_rc_in - P["wetlink_in_h"] + 0.5), P["wetlink_thread"] - 0.1).translate(cq.Vector(0, yw, zw))))   # M10 body through the tapped hole (modelled 0.05 under the major diameter)
    parts["wetlink"] = dict(solid=wl.val(), kind="COTS", color=(0.2, 0.2, 0.25), note="Blue Robotics WetLink WLP-M10 penetrator (nut envelope outside + an ASSUMED 12 x 3 mm inner protrusion), 45 deg")
    parts["vent"] = dict(solid=W(cyl(rinfo["x_out"], 5.0, 10.0).translate(cq.Vector(0, yv, zv))).val(), kind="COTS", color=(0.3, 0.3, 0.3), note="M6 vent screw + Dowty washer, 225 deg")
    parts["shell_top"] = dict(solid=sh_top, kind="print", color=(0.6, 0.6, 0.65), note="ASA shell clamp, top half: end lips trap both cap flanges, 2 lugs, strut boss at 0 deg (2x M4 inserts)")
    parts["shell_bot"] = dict(solid=sh_bot, kind="print", color=(0.6, 0.6, 0.65), note="ASA shell clamp, bottom half: 2 lugs, strut bosses at 120 / 240 deg; 4x M4 x 35 + nylocs join the halves")
    for k in range(3):
        parts[f"strut_{k}"] = dict(solid=rotX(strut0, 120 * k), kind="print", color=(0.6, 0.6, 0.65), note="ASA L-strut: leg 18 x 6, bar 18 x 6, curved foot over the ring joint; 2x M4 x 12 to the shell, 4x M3 x 10 to the arcs", print_from="strut_0")
    for k in range(3):
        parts[f"duct_{k}"] = dict(solid=arcs[k], kind="print", color=(0.8, 0.8, 0.8), note="ASA guard-ring arc 120 deg, ID 214 / OD 226 x 40, 4x M3 heat-set inserts" + (" + 40 mm stake socket (16.2 bore, 4 mm wall)" if k == 1 else ""), print_from=None if k == 1 else "duct_0")
    rotor_names = ["nose_plug", "hub_front", "hub_rear", "rotor_shaft", "hub_washer", "circlip_A", "hub_screw"] + [f"blade_{k}" for k in range(n_blades)] + [f"bolt_{k}" for k in range(n_blades)]
    nacelle_names = ["stub_shaft", "front_cap", "oring_front", "iring", "lip_seal", "bearing", "circlip", "tube", "dog_hub", "coupling_pin", "drive_disc", "motor", "rear_cap", "oring_rear", "wetlink", "vent"]
    support_names = ["shell_top", "shell_bot", "strut_0", "strut_1", "strut_2", "duct_0", "duct_1", "duct_2"]
    def span(names): bbs = [parts[n]["solid"].BoundingBox() for n in names]; return max(b.xmax for b in bbs) - min(b.xmin for b in bbs)
    def thick(names): bbs = [parts[n]["solid"].BoundingBox() for n in names]; return max(min(b.xmax - b.xmin, b.ymax - b.ymin, b.zmax - b.zmin) for b in bbs)
    layout = dict(x_pad=x_pad, x_hub=[x0h, x_hub_rear], x_nose_tip=x0h - P["nose_len"], x_wet=x_wet, x_joint=x_joint, x_tube=[x_tube0, x_tube1], x_motor=[x_motor0, x_motor1],
                  x_rear_face=rinfo["x_out"], x_penetrator_end=rinfo["x_out"] - P["wetlink_cb_depth"] + 0.2 + P["wetlink_nut_h"],
                  shaft=dict(x_tip=rinfo_s["x_tip"], xA=rinfo_s["xA"], x_joint=x_joint, x_rotor_end=rinfo_s["x_end"], xB=sinfo["xB"], x_end=sinfo["x_end"]), cap=finfo, support=suinfo,
                  L_tube=L_tube, n_blades=n_blades, stations=bst, groups=dict(rotor=rotor_names, nacelle=nacelle_names, support=support_names))
    allx = [p["solid"].BoundingBox() for p in parts.values()]
    layout["operating_depth_mm"] = max(b.xmax for b in allx) - min(b.xmin for b in allx)
    layout["rotor_depth_mm"] = span(rotor_names)                       # nose plug tip to the thread end of the rotor shaft (bolts inside the hub)
    layout["nacelle_depth_mm"] = span(nacelle_names)                   # stub front face to the penetrator nut
    layout["support_max_part_mm"] = {n: [round(v, 1) for v in (parts[n]["solid"].BoundingBox().xlen, parts[n]["solid"].BoundingBox().ylen, parts[n]["solid"].BoundingBox().zlen)] for n in ("shell_top", "strut_0", "duct_1")}
    layout["support_pack_thickness_mm"] = thick(support_names)
    flexible = lambda n: n.startswith("oring")
    names = [n for n in parts if not flexible(n)]; bbs = {n: parts[n]["solid"].BoundingBox() for n in names}; inter = {}
    for a, b in itertools.combinations(names, 2):
        A, B = bbs[a], bbs[b]
        if A.xmax < B.xmin - 0.01 or B.xmax < A.xmin - 0.01 or A.ymax < B.ymin - 0.01 or B.ymax < A.ymin - 0.01 or A.zmax < B.zmin - 0.01 or B.zmax < A.zmin - 0.01: continue
        try: v = parts[a]["solid"].intersect(parts[b]["solid"]).Volume()
        except Exception: v = -1.0
        if v > 0.01 or v < 0: inter[f"{a}/{b}"] = round(v, 3)
    # the lip seal is modelled with its bore 0.5 mm under the journal (lip interference); the stub/lip_seal overlap must equal that annulus and nothing else
    lip_expected = math.pi / 4 * (P["shaft_d"] ** 2 - (P["shaft_d"] - 0.5) ** 2) * (P["seal_w"] - 0.02)
    v_lip = inter.pop("stub_shaft/lip_seal", 0.0)
    layout["seal_lip_overlap_mm3"] = dict(found=round(v_lip, 2), expected=round(lip_expected, 2), ok=abs(v_lip - lip_expected) < 2.0)
    layout["interference_mm3"] = inter; layout["pairs_checked"] = sum(1 for _ in itertools.combinations(names, 2))
    # clearances that matter (minimum distances between non-touching parts)
    def dist(a, b):
        try: return round(parts[a]["solid"].distance(parts[b]["solid"]), 3)
        except Exception: return None
    layout["clearances_mm"] = dict(dog_tip_to_bell=round((x_bell - P["disc_t"]) + P["disc_t"] - (x_tail0 + P["doghub_len"] + P["dog_h"]), 2), dog_engagement=round(P["dog_h"] - P["ic_front"], 2),
                                   wetlink_inner_to_stator=dist("wetlink", "motor"), stub_face_to_circlip_A=round(x_joint - rinfo_s["xA"][1], 2),
                                   front_lip_to_hub=round(x_wet - P["lip_t"] - x_hub_rear, 2), blade_tip_to_ring=round(P["duct_id"] / 2 - P["r_tip"], 2))
    return parts, layout

def print_orient(name, s):
    """rotate a printed part so its print face is at -Z (then move onto z = 0): hub halves on their parting faces, disc flat, shell halves on
    their flat parting plane, ring arcs on an end face, dog hub on its bare end, strut on the flat side of its leg"""
    if name == "hub_front": s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), 90)            # parting face is its +X face -> -Z
    elif name == "hub_rear": s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), -90)          # parting face is its -X face -> -Z
    elif name in ("drive_disc",): s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), 90)
    elif name in ("dog_hub",): s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), -90)
    elif name.startswith("duct"): s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), 90)
    elif name in ("nose_plug",): s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), 90)
    elif name == "shell_bot": s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 180)           # its flat parting plane (z = 0) becomes the bottom
    elif name.startswith("strut"): s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 90)       # leg plate flat on the bed, bar standing on its edge
    bb = s.BoundingBox(); return s.translate(cq.Vector(-bb.xmin, -bb.ymin, -bb.zmin))

SMALL_COTS = ("circlip", "circlip_A", "iring", "hub_washer", "coupling_pin", "hub_screw", "vent")

def export(parts, layout, sel, prefix="v4"):
    table = []; assy = cq.Assembly(name="v4_lowflow_A")
    for name, p in parts.items():
        s = p["solid"]; bb = s.BoundingBox()
        table.append(dict(name=name, kind=p["kind"], note=p["note"], valid=s.isValid(), volume_mm3=round(s.Volume(), 1), x=[round(bb.xmin, 2), round(bb.xmax, 2)], n_solids=len(s.Solids())))
        if not s.isValid(): print("WARNING invalid", name)
        dup = p.get("print_from")
        if not (name.startswith("oring") or name.startswith("bolt_") or name in SMALL_COTS or (dup and dup != name)):
            cq.exporters.export(s, os.path.join(OUT, f"{prefix}_{name}.step"))
        if p["kind"].startswith("print") and not (dup and dup != name):
            if name.startswith("blade"):
                m, tilt = blade_print_mesh(sel, layout["x_pad"], int(name.split("_")[1])); m.export(os.path.join(OUT, f"{prefix}_{name}_PRINT.stl"))
                table[-1].update(stl_watertight=bool(m.is_watertight), stl_volume_mm3=round(float(m.volume), 1), stl_vs_step_pct=round((m.volume / s.Volume() - 1) * 100, 2), print_tilt_deg=round(tilt, 2))
            else:
                wt, nf = mb.write_stl_watertight(print_orient(name, s), os.path.join(OUT, f"{prefix}_{name}_PRINT.stl"), 0.03, 0.1); table[-1]["stl_watertight"] = bool(wt)
        assy.add(cq.Workplane("XY").add(s), name=name, color=cq.Color(*p["color"]))
    assy.save(os.path.join(OUT, f"{prefix}_assembly.step"))
    bad = {k: v for k, v in layout["interference_mm3"].items() if v > 0.5 or v < 0}
    print(f"[{prefix}] operating depth {layout['operating_depth_mm']:.1f} mm (rotor {layout['rotor_depth_mm']:.1f} + nacelle {layout['nacelle_depth_mm']:.1f} detached; support pack {layout['support_pack_thickness_mm']:.1f}); tube {layout['L_tube']:.1f}; pairs {layout['pairs_checked']}; interference: {bad or 'none'}; seal lip {layout['seal_lip_overlap_mm3']}; clearances {layout['clearances_mm']}")
    return table

if __name__ == "__main__":
    sel = json.load(open(os.path.join(ROOT, "model", "selected_design.json")))
    parts, layout = build(sel)
    table = export(parts, layout, sel)
    json.dump(dict(params=P, layout=layout, parts=table, selected=sel), open(os.path.join(OUT, "v4_info.json"), "w"), indent=1, default=float)
