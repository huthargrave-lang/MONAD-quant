#!/usr/bin/env python
"""Low-flow turbine v4, arrangement A: rotor on a short 316 shaft in front of a stationary sealed nacelle holding the GL60.

Frame: +X = flow; rotor axis = X; Z radial up.  All dimensions mm.  Parts:
  rotor: nose plug, front hub half (with nose), rear hub half, 3 blades (airfoil-tongue roots), 3x M3 x 45 through-bolts, hub screw
  shaft: 316, 8 h6, D-flat, integral collars (hub stop A, bearing thrust stop B), circlip DIN 471-8 behind the bearing, coupling pin
  nacelle: 3 in 6061 tube, front cap (1 O-ring; 8x22x7 PTFE lip seal + 608-2RS in one 22 mm bore), rear cap (1 O-ring, GL60 mount,
           WetLink M10 penetrator, M6 vent), TPU dog disc on the bell, printed dog hub on the shaft tail
  support: printed clamp (2 halves) around the tube, 3 printed struts, guard ring ID 210 with a stake socket
Selected blade geometry comes from ../model/selected_design.json (chord/twist/airfoil per station, blended to NACA 4418 at the root)."""
import json, math, os, sys, itertools
import numpy as np
import cadquery as cq
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "..", "water_turbine_blade")); import make_blade as mb
sys.path.insert(0, os.path.join(ROOT, "model"))
OUT = os.path.join(ROOT, "out"); os.makedirs(OUT, exist_ok=True)

P = dict(
    r_tip=101.6, r_hub=28.0, hub_len=36.0, hub_front_len=14.0, nose_len=22.0, pocket_floor_r=16.0, pocket_clear=0.15, bolt_r=22.0, bolt_d=3.4, bolt_head_d=6.0, bolt_head_h=3.2,
    shaft_d=8.0, flat_depth=1.0, collar_d=12.0, collar_w=3.0, seal_w=7.0, seal_od=22.0, brg_od=22.0, brg_w=7.0, brg_bore=8.0, circlip_w=0.9, circlip_groove_d=7.4,
    tail_len=12.0, pin_d=3.0, hub_screw="M4", hub_screw_d=4.0, nose_pocket_d=9.0,
    tube_od=76.2, tube_id=72.9, plug_clear=0.15, oring_cs=2.62, oring_groove_w=3.6, oring_groove_d=2.08, oring_land=2.5, flange_t=3.0, plug_len=8.0,
    motor_od=69.0, motor_len=22.3, motor_bore=20.0, motor_pcd=50.0, bell_pcd=40.0, cb_d=6.0, cb_depth=2.2,
    disc_t=2.5, disc_od=50.0, dog_pcd=20.0, dog_d=6.0, dog_h=3.0, doghub_od=30.0, doghub_len=8.0,
    gap_rotor_cap=5.0, ic_front=2.0, ic_rear=1.0, wetlink_r=22.0, wetlink_thread=10.0, wetlink_nut_od=17.0, wetlink_nut_h=12.0, wetlink_cb_d=20.0, wetlink_cb_depth=6.0, vent_r=-22.0,
    clamp_w=14.0, clamp_t=6.0, strut_w=18.0, strut_t=6.0, duct_id=210.0, duct_od=218.0, duct_len=40.0,
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
    # two pieces: the lower one spans exactly the tongue's radii (same ruled-surface parametrisation as the blade stub, so the 0.15 mm
    # clearance is uniform); the upper one starts 0.5 mm below the hub surface so no wire coincides with the hub cylinder
    return [piece(r_floor, r_top + 0.3), piece(r_top - 0.5, r_above)]

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
        hub = cutc(hub, W(hole_x(P["bolt_head_d"], x0 + L - P["bolt_head_h"], P["bolt_head_h"] + 1, *yz)))      # nut pocket on the rear face (hex nut sits in a round pocket: nyloc, held by the wrench)
        hub = cutc(hub, W(hole_x(P["bolt_head_d"], x0 - h - 1, 1 + (h + 3.0), *yz)) ) if False else hub
    # D-bore through, nose pocket for the retaining screw head, front hole to reach it
    dbore = W(cyl(x0 - h - 1, L + h + 2, P["shaft_d"] + 0.2)).cut(W(cq.Workplane("XY").box(L + h + 4, 20, 10, centered=(False, True, False)).translate((x0 - h - 2, 0, P["shaft_d"] / 2 - P["flat_depth"] + 0.1)).val())).val()
    hub = cutc(hub, W(dbore))
    hub = cutc(hub, W(cyl(x0 - h - 1, (h - 6.0) + 1, P["nose_pocket_d"])))                                       # access pocket from the nose tip
    hub = cutc(hub, W(cyl(x0 - 6.0, 6.0 + 0.01, 10.0)))                                                          # washer/screw-head pocket at the shaft end
    front = hub.val().intersect(cq.Solid.makeBox(200, 200, 200, cq.Vector(x_pad - 200, -100, -100)))
    rear = hub.val().intersect(cq.Solid.makeBox(200, 200, 200, cq.Vector(x_pad, -100, -100)))
    return front, rear

def shaft(x_hub_rear, x_cap_wet, x_brg0):
    """316: front end (screw tapping) ... D-flat under the hub ... collar A ... seal journal ... collar B ... bearing journal ... circlip groove ... tail with pin hole"""
    x_tip = x_hub_rear - P["hub_len"] - 2.0
    xA0 = x_hub_rear; xA1 = xA0 + P["collar_w"]
    xB1 = x_brg0 - 0.1; xB0 = xB1 - P["collar_w"]
    x_end = x_brg0 + P["brg_w"] + 2.0 + P["circlip_w"] + P["tail_len"]
    s = W(cyl(x_tip, x_end - x_tip, P["shaft_d"]))
    s = s.union(W(cyl(xA0, P["collar_w"], P["collar_d"]))).union(W(cyl(xB0, P["collar_w"], P["collar_d"])))
    flat = cq.Workplane("XY").box(P["hub_len"] + 1.0, 20, 10, centered=(False, True, False)).translate((x_tip + 1.0, 0, P["shaft_d"] / 2 - P["flat_depth"])).val()
    s = s.cut(W(flat))
    s = s.cut(W(tube(x_brg0 + P["brg_w"] + 0.2, P["circlip_w"], P["shaft_d"] + 1, P["circlip_groove_d"])))        # DIN 471-8 groove behind the bearing (reverse stop, 0.2 end play)
    s = s.cut(W(hole_dir(P["pin_d"] + 0.1, 30, (x_end - P["tail_len"] / 2, -15, 0), (0, 1, 0))))                  # coupling pin
    s = s.cut(W(cyl(x_tip - 1, 9.0, 3.3)))                                                                          # M4 tapped 8 deep in the front end (hub retaining screw)
    return s.val(), dict(xA=[xA0, xA1], xB=[xB0, xB1], x_tip=x_tip, x_end=x_end)

def front_cap(x_wet):
    """flange (wet side) + plug into the tube; central 22 mm bore from the wet face: seal (7) then bearing (7), floor with a 10 mm hole; 1 O-ring"""
    t = P["flange_t"]; L = P["plug_len"]; rp = (P["tube_id"] - P["plug_clear"]) / 2
    c = W(cyl(x_wet, t, P["tube_od"])).union(W(cyl(x_wet + t, L, 2 * rp)))
    g_od = 2 * rp - 2 * P["oring_groove_d"]; xg = x_wet + t + P["oring_land"]
    c = c.cut(W(tube(xg, P["oring_groove_w"], P["tube_id"] + 1, g_od)))
    depth = P["seal_w"] + P["brg_w"]
    c = c.cut(W(cyl(x_wet - 1, 1 + depth, P["seal_od"])))                      # seal + bearing bore from the wet face (22 N7 for the bearing zone, 22 H8 for the seal zone: same nominal)
    c = c.cut(W(cyl(x_wet - 1, 100, 10.0)))                                   # through hole for the shaft tail
    for k in range(3):                                                        # 3x M3 for the clamp/strut interface? no: the clamp is on the tube. Cap-to-tube retention: 3x M3 radial? kept simple: O-ring plug + the clamp ring straddling the flange
        pass
    oring = torus(xg + P["oring_groove_w"] / 2, g_od + P["oring_cs"], P["oring_cs"])
    return c.val(), oring, dict(x_seal=x_wet, x_brg=x_wet + P["seal_w"], x_floor=x_wet + depth, x_in=x_wet + t + L)

def rear_cap(x_in):
    """plug into the tube (from x_in to the tube end) + flange; GL60 stator bolted to the inner face (both patterns, counterbored from the outside?) ->
    screws from the OUTSIDE face through the cap into the stator base (heads outside, Dowty washers: they cross the boundary) is simpler but each is a leak path;
    chosen: blind tapped holes in the cap inner face? the cap is Delrin: M3 helicoil... -> stator screws from the inside through the stator base into
    4 blind M3 brass inserts... Decision: 6061 cap, 4x M3 blind tapped from the inner face (no through holes), WetLink M10 hole at r=wetlink_r, M6 vent at r=vent_r."""
    t = P["flange_t"]; L = P["plug_len"]; rp = (P["tube_id"] - P["plug_clear"]) / 2
    x_fl = x_in + L
    c = W(cyl(x_in, L, 2 * rp)).union(W(cyl(x_fl, t, P["tube_od"])))
    g_od = 2 * rp - 2 * P["oring_groove_d"]; xg = x_fl - P["oring_land"] - P["oring_groove_w"]
    c = c.cut(W(tube(xg, P["oring_groove_w"], P["tube_id"] + 1, g_od)))
    for k in range(4):
        a = math.radians(90 * k)
        for pcd in (P["bell_pcd"], P["motor_pcd"]):
            c = c.cut(W(hole_x(2.5, x_in - 1, 6.0, pcd / 2 * math.cos(a), pcd / 2 * math.sin(a))))      # M3 / M2.5 blind tapped 5 deep from the inner face
    c = c.cut(W(hole_x(P["wetlink_thread"], x_in - 1, L + t + 2, 0, P["wetlink_r"])))                  # M10 x 1.5 WetLink penetrator (tapped through)
    c = c.cut(W(hole_x(P["wetlink_cb_d"], x_fl + t - P["wetlink_cb_depth"], P["wetlink_cb_depth"] + 1, 0, P["wetlink_r"])))   # counterbore: the penetrator nut sits mostly inside the cap
    c = c.cut(W(hole_x(5.2, x_in - 1, L + t + 2, 0, P["vent_r"])))                                       # M6 vent
    c = c.cut(W(box_x_r(x_in - 0.01, x_in + 2.5, 5.0, 10.0, P["wetlink_r"] + 4, 0.0)))                   # lead channel on the inner face from the stator to the penetrator
    oring = torus(xg + P["oring_groove_w"] / 2, g_od + P["oring_cs"], P["oring_cs"])
    return c.val(), oring, dict(x_fl=x_fl, x_out=x_fl + t)

def drive_parts(x_tail0, x_bell):
    """dog hub on the shaft tail (printed ASA, cross-pinned) with 2 dogs; TPU disc on the bell face with 2 pockets"""
    dh = W(cyl(x_tail0, P["doghub_len"], P["doghub_od"])).cut(W(cyl(x_tail0 - 1, P["doghub_len"] + 2, P["shaft_d"] + 0.2)))
    dh = dh.cut(W(hole_dir(P["pin_d"] + 0.1, 40, (x_tail0 + P["doghub_len"] / 2, -20, 0), (0, 1, 0))))
    for k in range(2):
        a = math.radians(90 + 180 * k); dog = cyl(x_tail0 + P["doghub_len"] - 0.5, P["dog_h"] + 0.5, P["dog_d"]).translate(cq.Vector(0, P["dog_pcd"] / 2 * math.cos(a), P["dog_pcd"] / 2 * math.sin(a)))
        dh = dh.union(W(dog))
    disc = W(tube(x_bell - P["disc_t"], P["disc_t"], P["disc_od"], P["motor_bore"] + 2))
    for k in range(4):
        a = math.radians(90 * k); disc = disc.cut(W(hole_x(3.4, x_bell - P["disc_t"] - 1, P["disc_t"] + 2, P["bell_pcd"] / 2 * math.cos(a), P["bell_pcd"] / 2 * math.sin(a))))
    for k in range(2):
        a = math.radians(90 + 180 * k); disc = disc.cut(W(hole_x(P["dog_d"] + 0.4, x_bell - P["disc_t"] - 1, P["dog_h"] + 1.5, P["dog_pcd"] / 2 * math.cos(a), P["dog_pcd"] / 2 * math.sin(a))))
    return dh.val(), disc.val()

def support(x_tube0, x_tube1, x_clamp, x_pad):
    """printed clamp ring (two halves) around the tube; 3 L-struts: a radial leg at the clamp (18 x 6) out to r 115 and an axial bar
    (18 wide x 6 radial) along the outside of the guard ring back to the clamp; guard ring ID 210 x 40 centred on the blade plane with a
    16 mm stake socket.  Loads: 35 N thrust at 2 m/s shared by three struts (axial bars in tension, radial legs in bending ~3 MPa)."""
    cw, ct = P["clamp_w"], P["clamp_t"]
    r_out = P["duct_od"] / 2 + 6.0
    xd0 = x_pad - 18.0; xd1 = xd0 + P["duct_len"]
    ring = W(tube(x_clamp, cw, P["tube_od"] + 2 * ct, P["tube_od"] + 0.3))
    for k in range(3):
        a = 120 * k
        ring = ring.union(W(box_x_r(x_clamp - 2, x_clamp + cw + 2, P["strut_t"], P["tube_od"] / 2 + ct - 1, r_out, a)))                 # radial leg
        ring = ring.union(W(box_x_r(xd1 - 6.0, x_clamp + cw + 2, P["strut_w"], r_out - 6.0, r_out, a)))                                # axial bar along the ring outside
    clamp_top = ring.val().intersect(cq.Solid.makeBox(400, 400, 200, cq.Vector(-200, -200, 0)))
    clamp_bot = ring.val().intersect(cq.Solid.makeBox(400, 400, 200, cq.Vector(-200, -200, -200)))
    duct = W(tube(xd0, P["duct_len"], P["duct_od"], P["duct_id"]))
    for k in range(3):
        duct = duct.union(W(box_x_r(xd1 - 6.0, xd1 + 0.01, P["strut_w"] + 8, P["duct_od"] / 2 - 1, r_out - 6.0 - 0.02, 120 * k)))                    # lap pads where the axial bars land (2x M3 each, not modelled)
    sock = box_x_r(xd0, xd1, 22, P["duct_od"] / 2 - 1, P["duct_od"] / 2 + 14, 180)
    duct = duct.union(W(sock)).cut(W(rotX(hole_dir(16.2, 40, (xd0 + P["duct_len"] / 2, 0, P["duct_od"] / 2 - 2), (0, 0, 1)), 180)))
    return clamp_top, clamp_bot, duct.val()

def build(sel):
    n_blades = sel["B"]
    parts = {}
    x_pad = 0.0
    bsol, bst = build_blade(sel, x_pad)
    front, rear = hub_halves(x_pad, np.array(bst["outline"]), n_blades)
    x_hub_rear = x_pad - P["hub_front_len"] + P["hub_len"]
    x_wet = x_hub_rear + P["collar_w"] + P["gap_rotor_cap"]                     # collar A sits in the gap; wet face of the front cap
    fc, fo, finfo = front_cap(x_wet)
    shp, sinfo = shaft(x_hub_rear, x_wet, finfo["x_brg"])
    x_tube0 = x_wet + P["flange_t"]
    x_tail0 = sinfo["x_end"] - P["tail_len"] + 2.0
    x_bell = x_tail0 + P["doghub_len"] + P["dog_h"] + P["ic_front"] + P["disc_t"]           # bell face; disc between
    x_motor0 = x_bell; x_motor1 = x_motor0 + P["motor_len"]
    x_rc_in = x_motor1 + P["ic_rear"]
    rc, ro_, rinfo = rear_cap(x_rc_in)
    x_tube1 = rinfo["x_fl"]
    L_tube = x_tube1 - x_tube0
    dh, disc = drive_parts(x_tail0, x_bell)
    ct, cb, duct = support(x_tube0, x_tube1, x_tube1 - P["clamp_w"] - 12.0, x_pad)
    parts["nose_plug"] = dict(solid=cyl(x_pad - P["hub_front_len"] - P["nose_len"] - 0.5, 6.0, P["nose_pocket_d"] - 0.1), kind="print", color=(0.3, 0.5, 0.8), note="ASA press plug closing the nose access hole")
    parts["hub_front"] = dict(solid=front, kind="print", color=(0.30, 0.50, 0.80), note="ASA front hub half with nose, half pockets, D-bore, screw pocket")
    parts["hub_rear"] = dict(solid=rear, kind="print", color=(0.30, 0.50, 0.80), note="ASA rear hub half with half pockets, D-bore, nut pockets")
    for k in range(n_blades):
        parts[f"blade_{k}"] = dict(solid=rotX(bsol, 360 * k / n_blades), kind="print", color=(0.35, 0.55, 0.85), note=f"ASA blade ({sel['airfoil']} -> NACA 4418 root), airfoil tongue, 1 axial M3")
        a = math.radians(360 * k / n_blades)
        parts[f"bolt_{k}"] = dict(solid=hole_x(3.0, x_pad - P["hub_front_len"] - 3.0, P["hub_len"] + 6.0, P["bolt_r"] * math.sin(a), P["bolt_r"] * math.cos(a)), kind="COTS", color=(0.4, 0.4, 0.4), note="M3 x 45 316 + nyloc")
    parts["shaft"] = dict(solid=shp, kind="machined", color=(0.55, 0.6, 0.6), note="316 shaft 8 h6 from 12 mm bar: D-flat, collars A/B, seal journal Ra 0.2, circlip groove, pin hole, M4 tapped front")
    parts["hub_screw"] = dict(solid=W(cyl(sinfo["x_tip"] - 1.0 - 3.0, 3.0, 7.0)).union(W(cyl(sinfo["x_tip"] - 1.0, 8.0, 3.2))).val(), kind="COTS", color=(0.4, 0.4, 0.4), note="M4 x 8 316 + washer: hub retainer")
    parts["front_cap"] = dict(solid=fc, kind="machined", color=(0.85, 0.55, 0.2), note="6061 (anodised) or Delrin front cap: flange, O-ring plug, 22 mm bore: PTFE lip seal 8x22x7 + 608-2RS, floor")
    parts["oring_front"] = dict(solid=fo, kind="COTS", color=(0.1, 0.1, 0.1), note="AS568-147 EPDM")
    parts["lip_seal"] = dict(solid=tube(finfo["x_seal"] + 0.01, P["seal_w"] - 0.02, P["seal_od"], P["shaft_d"] - 0.5), kind="COTS", color=(0.2, 0.2, 0.2), note="PTFE lip seal 8x22x7 (Varilip PDR class), lip to the water")
    parts["bearing"] = dict(solid=tube(finfo["x_brg"], P["brg_w"], P["brg_od"], P["brg_bore"]), kind="COTS", color=(0.5, 0.5, 0.55), note="608-2RS 440C stainless")
    parts["circlip"] = dict(solid=tube(finfo["x_brg"] + P["brg_w"] + 0.2, P["circlip_w"], 11.0, P["circlip_groove_d"]), kind="COTS", color=(0.3, 0.3, 0.3), note="DIN 471-8 stainless (reverse-thrust stop, 0.2 mm end play)")
    parts["tube"] = dict(solid=tube(x_tube0, L_tube, P["tube_od"], P["tube_id"]), kind="COTS+machined", color=(0.75, 0.75, 0.78), note=f"6061 tube 3 in x 0.065 in, {L_tube:.1f} mm, ends faced, lands bored 72.90 H8, anodised")
    parts["dog_hub"] = dict(solid=dh, kind="print", color=(0.9, 0.3, 0.3), note="ASA dog hub on the shaft tail (3 mm cross pin), 2 dogs")
    parts["coupling_pin"] = dict(solid=hole_dir(3.0, 22, (x_tail0 + P["doghub_len"] / 2, -11, 0), (0, 1, 0)), kind="COTS", color=(0.4, 0.4, 0.4), note="3 x 22 316 dowel")
    parts["drive_disc"] = dict(solid=disc, kind="print", color=(0.9, 0.3, 0.3), note="TPU 95A disc on the bell face (4x M3), 2 dog pockets")
    parts["motor"] = dict(solid=W(cyl(x_motor0, P["motor_len"], P["motor_od"])).cut(W(cyl(x_motor0 - 1, P["motor_len"] + 2, P["motor_bore"]))).val(), kind="COTS", color=(0.25, 0.25, 0.3), note="CubeMars GL60 KV25 envelope (bell forward)")
    parts["rear_cap"] = dict(solid=rc, kind="machined", color=(0.85, 0.55, 0.2), note="6061 rear cap: O-ring plug, GL60 mount (blind M3/M2.5), WetLink M10 port, M6 vent, lead channel")
    parts["oring_rear"] = dict(solid=ro_, kind="COTS", color=(0.1, 0.1, 0.1), note="AS568-147 EPDM")
    parts["wetlink"] = dict(solid=W(cyl(rinfo["x_out"] - P["wetlink_cb_depth"] + 0.2, P["wetlink_nut_h"], P["wetlink_nut_od"]).translate(cq.Vector(0, 0, P["wetlink_r"]))).val(), kind="COTS", color=(0.2, 0.2, 0.25), note="Blue Robotics WetLink WLP-M10 penetrator (nut envelope)")
    parts["vent"] = dict(solid=W(cyl(rinfo["x_out"], 5.0, 10.0).translate(cq.Vector(0, 0, P["vent_r"]))).val(), kind="COTS", color=(0.3, 0.3, 0.3), note="M6 vent screw + Dowty washer")
    parts["clamp_top"] = dict(solid=ct, kind="print", color=(0.6, 0.6, 0.65), note="ASA clamp half + 2 struts (18 x 6)")
    parts["clamp_bot"] = dict(solid=cb, kind="print", color=(0.6, 0.6, 0.65), note="ASA clamp half + strut")
    parts["duct"] = dict(solid=duct, kind="print", color=(0.8, 0.8, 0.8), note="ASA guard ring ID 210 x 40 with a 16 mm stake socket (3 arcs)")
    layout = dict(x_pad=x_pad, x_hub=[x_pad - P["hub_front_len"], x_hub_rear], x_nose_tip=x_pad - P["hub_front_len"] - P["nose_len"], x_wet=x_wet, x_tube=[x_tube0, x_tube1], x_motor=[x_motor0, x_motor1],
                  x_rear_face=rinfo["x_out"], x_penetrator_end=rinfo["x_out"] - P["wetlink_cb_depth"] + 0.2 + P["wetlink_nut_h"], shaft=sinfo, cap=finfo, L_tube=L_tube, n_blades=n_blades, stations=bst)
    allx = [p["solid"].BoundingBox() for p in parts.values()]
    layout["operating_depth_mm"] = max(b.xmax for b in allx) - min(b.xmin for b in allx)
    layout["rotor_depth_mm"] = x_hub_rear - layout["x_nose_tip"]
    layout["nacelle_depth_mm"] = layout["x_penetrator_end"] - x_wet
    flexible = lambda n: n.startswith("oring") or n in ("lip_seal",)
    names = [n for n in parts if not flexible(n)]; bbs = {n: parts[n]["solid"].BoundingBox() for n in names}; inter = {}
    for a, b in itertools.combinations(names, 2):
        A, B = bbs[a], bbs[b]
        if A.xmax < B.xmin - 0.01 or B.xmax < A.xmin - 0.01 or A.ymax < B.ymin - 0.01 or B.ymax < A.ymin - 0.01 or A.zmax < B.zmin - 0.01 or B.zmax < A.zmin - 0.01: continue
        try: v = parts[a]["solid"].intersect(parts[b]["solid"]).Volume()
        except Exception: v = -1.0
        if v > 0.01 or v < 0: inter[f"{a}/{b}"] = round(v, 3)
    layout["interference_mm3"] = inter; layout["pairs_checked"] = sum(1 for _ in itertools.combinations(names, 2))
    return parts, layout

def print_orient(name, s):
    """rotate a printed part so its print face is at -Z (then move onto z = 0): hub halves on their parting faces, disc flat, clamp halves
    on their flat parting plane, ring on its end face, dog hub on its bare end"""
    if name == "hub_front": s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), 90)            # parting face is its +X face -> -Z
    elif name == "hub_rear": s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), -90)          # parting face is its -X face -> -Z
    elif name in ("drive_disc",): s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), 90)
    elif name in ("dog_hub",): s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), -90)
    elif name in ("duct",): s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), 90)
    elif name in ("nose_plug",): s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), 90)
    elif name == "clamp_bot": s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 180)           # its flat parting plane (z = 0) becomes the bottom
    bb = s.BoundingBox(); return s.translate(cq.Vector(-bb.xmin, -bb.ymin, -bb.zmin))

def export(parts, layout, sel, prefix="v4"):
    table = []; assy = cq.Assembly(name="v4_lowflow_A")
    for name, p in parts.items():
        s = p["solid"]; bb = s.BoundingBox()
        table.append(dict(name=name, kind=p["kind"], note=p["note"], valid=s.isValid(), volume_mm3=round(s.Volume(), 1), x=[round(bb.xmin, 2), round(bb.xmax, 2)], n_solids=len(s.Solids())))
        if not s.isValid(): print("WARNING invalid", name)
        if not (name.startswith("oring") or name.startswith("bolt_") or name in ("circlip", "coupling_pin", "hub_screw", "vent")):
            cq.exporters.export(s, os.path.join(OUT, f"{prefix}_{name}.step"))
        if p["kind"].startswith("print"):
            if name.startswith("blade"):
                m, tilt = blade_print_mesh(sel, layout["x_pad"], int(name.split("_")[1])); m.export(os.path.join(OUT, f"{prefix}_{name}_PRINT.stl"))
                table[-1].update(stl_watertight=bool(m.is_watertight), stl_volume_mm3=round(float(m.volume), 1), stl_vs_step_pct=round((m.volume / s.Volume() - 1) * 100, 2), print_tilt_deg=round(tilt, 2))
            else:
                wt, nf = mb.write_stl_watertight(print_orient(name, s), os.path.join(OUT, f"{prefix}_{name}_PRINT.stl"), 0.03, 0.1); table[-1]["stl_watertight"] = bool(wt)
        assy.add(cq.Workplane("XY").add(s), name=name, color=cq.Color(*p["color"]))
    assy.save(os.path.join(OUT, f"{prefix}_assembly.step"))
    bad = {k: v for k, v in layout["interference_mm3"].items() if v > 0.5 or v < 0}
    print(f"[{prefix}] operating depth {layout['operating_depth_mm']:.1f} mm (rotor {layout['rotor_depth_mm']:.1f} + nacelle {layout['nacelle_depth_mm']:.1f} detached); tube {layout['L_tube']:.1f}; pairs {layout['pairs_checked']}; interference: {'none' if not bad else bad}")
    return table

if __name__ == "__main__":
    sel = json.load(open(os.path.join(ROOT, "model", "selected_design.json")))
    parts, layout = build(sel)
    table = export(parts, layout, sel)
    json.dump(dict(params=P, layout=layout, parts=table, selected=sel), open(os.path.join(OUT, "v4_info.json"), "w"), indent=1, default=float)
