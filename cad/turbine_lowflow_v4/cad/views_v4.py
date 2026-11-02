#!/usr/bin/env python
"""Section (waterproof boundary + load paths), dimensioned section and exploded view of the v4 arrangement-A assembly (figure 10)."""
import json, math, os, sys
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import make_v4 as m
sel = json.load(open(os.path.join(m.ROOT, "model", "selected_design.json")))
parts, L = m.build(sel); P = m.P
SURFACE, INK, INK2, GRID, RED = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#c4342d"
def mesh(s, tol=0.15, ang=0.3):
    v, t = s.tessellate(tol, ang); Vv = np.array([(p.x, p.y, p.z) for p in v]); return Vv[np.array(t)]
def shade(tris, base, light=(-0.4, -0.6, 0.7)):
    Lv = np.array(light) / np.linalg.norm(light); n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]); n /= np.linalg.norm(n, axis=1)[:, None] + 1e-12
    return np.clip(np.array(base)[None, :] * (0.35 + 0.65 * np.clip(n @ Lv, 0, 1))[:, None] + 0.08, 0, 1)
def section_segs(s, tol=0.08):
    v, t = s.tessellate(tol, 0.25); Vv = np.array([(p.x, p.y, p.z) for p in v]); segs = []
    for tri in Vv[np.array(t)]:
        pts = []
        for i in range(3):
            a, b = tri[i], tri[(i + 1) % 3]
            if a[1] * b[1] < 0: s_ = -a[1] / (b[1] - a[1]); pts.append(a + s_ * (b - a))
        if len(pts) == 2: segs.append([(pts[0][0], pts[0][2]), (pts[1][0], pts[1][2])])
    return segs
# ---------------- section
fig, ax = plt.subplots(figsize=(16, 9), facecolor=SURFACE); ax.set_facecolor(SURFACE)
for n, p in parts.items():
    segs = section_segs(p["solid"])
    if segs: ax.add_collection(LineCollection(segs, colors=[p["color"]], linewidths=1.3))
x0, x1 = L["x_tube"]; ro = P["tube_od"] / 2; xw = L["x_wet"]; xr = L["x_rear_face"]
for sgn in (1, -1):
    ax.plot([xw, xr], [sgn * (ro + 0.8)] * 2, "--", color=RED, lw=1.6); ax.plot([xw] * 2, [sgn * P["seal_od"] / 2, sgn * ro], "--", color=RED, lw=1.6); ax.plot([xr] * 2, [0, sgn * ro], "--", color=RED, lw=1.6)
    ax.plot([xw, xw + P["seal_w"]], [sgn * (P["shaft_d"] / 2 + 0.3)] * 2, "--", color=RED, lw=2.5)
ann = [("WATERPROOF BOUNDARY (red): anodised 3 in tube + 1 EPDM O-ring per cap + ONE 8 mm PTFE lip seal on the polished 316 shaft + WetLink M10 penetrator + M6 vent in the rear cap; the GL60 is dry inside", (xr, -ro), (x0 - 20, -100)),
       ("THRUST PATH: blades -> airfoil tongues (axial M3) -> hub halves -> collar A -> shaft -> collar B -> 608 inner race -> outer race -> front-cap floor -> cap plug/flange -> tube -> clamp -> struts -> guard ring / stake", (xw + 9, 8), (x0 - 40, 95)),
       ("REVERSE LOAD: DIN 471-8 circlip behind the bearing (0.2 mm end play); seal pressed in front of the bearing retains the outer race", (xw + 15, -6), (x0 - 40, -78)),
       ("TORQUE PATH: blades -> hub D-bore -> shaft D-flat -> cross-pinned dog hub -> TPU disc (2 dogs, 0.2 mm radial clearance) -> GL60 bell; stator bolted to the rear cap (blind M3/M2.5)", (L["x_motor"][0] - 5, -14), (x0 - 40, -60)),
       (f"GL60 KV25 inside the nacelle; leads along the rear-cap channel to the WetLink penetrator (counterbored)", (L["x_motor"][0] + 10, 20), (x1 + 10, 70)),
       (f"rotor: nose plug, 2-piece printed hub (r {P['r_hub']:.0f}), {L['n_blades']} blades with radial airfoil tongues", (L["x_hub"][0] + 5, P['r_hub'] + 2), (x0 - 80, 60)),
       ("printed clamp halves + 3 struts 18 x 6 to the guard ring ID 210 (stake socket)", (x1 - 20, -ro - 8), (x1 + 15, -92))]
for txt, xy, xt in ann: ax.annotate(txt, xy, xytext=xt, color=INK, fontsize=8, arrowprops=dict(arrowstyle="->", color=INK2))
ax.set_aspect("equal"); ax.set_xlim(L["x_nose_tip"] - 70, L["x_penetrator_end"] + 60); ax.set_ylim(-115, 115); ax.grid(True, color=GRID, lw=0.7); ax.set_axisbelow(True); ax.set_xlabel("X (mm), flow ->"); ax.set_ylabel("Z (mm)")
for s_ in ("top", "right"): ax.spines[s_].set_visible(False)
ax.set_title(f"Fig. 10a  v4 arrangement A: section through the axis. Operating depth {L['operating_depth_mm']:.1f} mm; detached: rotor {L['rotor_depth_mm']:.1f} + nacelle {L['nacelle_depth_mm']:.1f} mm (packing target 76)", loc="left", fontweight="bold", fontsize=10)
fig.savefig(os.path.join(m.OUT, "fig10a_section.png"), dpi=140, facecolor=SURFACE, bbox_inches="tight"); print("section")
# ---------------- dimensioned
fig2, ax2 = plt.subplots(figsize=(16, 9), facecolor=SURFACE); ax2.set_facecolor(SURFACE)
for n, p in parts.items():
    segs = section_segs(p["solid"])
    if segs: ax2.add_collection(LineCollection(segs, colors=["#9a9a9a"], linewidths=0.9))
def dim_h(xa, xb, y, txt, off=0):
    ax2.annotate("", (xa, y), (xb, y), arrowprops=dict(arrowstyle="<->", color=INK, lw=1.0)); ax2.text(0.5 * (xa + xb), y + 2 + off, txt, ha="center", color=INK, fontsize=8.5)
    for x in (xa, xb): ax2.plot([x, x], [y - 4, y + 4], color=INK, lw=0.6)
def dim_v(x, ya, yb, txt):
    ax2.annotate("", (x, ya), (x, yb), arrowprops=dict(arrowstyle="<->", color=INK, lw=1.0)); ax2.text(x + 2, 0.5 * (ya + yb), txt, va="center", color=INK, fontsize=8.5, rotation=90)
xn, xe = L["x_nose_tip"], L["x_penetrator_end"]
dim_h(xn, xe, -120, f"OPERATING DEPTH {L['operating_depth_mm']:.1f} (nose tip to penetrator nut)")
dim_h(xn, L["x_hub"][1], ro + 30, f"rotor {L['rotor_depth_mm']:.1f} (detachable: one M4 screw)"); dim_h(xw, xe, ro + 30, f"nacelle {L['nacelle_depth_mm']:.1f}")
dim_h(L["x_hub"][1], xw, ro + 18, f"collar + gap {xw - L['x_hub'][1]:.1f}"); dim_h(x0, x1, ro + 10, f"tube {L['L_tube']:.1f}")
dim_h(L["x_motor"][0], L["x_motor"][1], 40, "GL60 22.3"); dim_h(L["cap"]["x_seal"], L["cap"]["x_seal"] + P["seal_w"], 14, "seal 7"); dim_h(L["cap"]["x_brg"], L["cap"]["x_brg"] + P["brg_w"], 14, "608 7")
dim_v(xe + 18, 0, P["tube_od"] / 2, f"tube OD {P['tube_od']} / ID {P['tube_id']}"); dim_v(xe + 30, 0, P["r_hub"], f"hub r {P['r_hub']:.0f} (ratio {P['r_hub']/101.6:.2f})"); dim_v(xe + 42, 0, 101.6, "rotor R 101.6 (dia 203.2)")
dim_v(xn - 14, -P["duct_id"] / 2, P["duct_id"] / 2, f"guard ring ID {P['duct_id']:.0f}"); dim_v(L["x_hub"][1] + 2, 0, P["shaft_d"] / 2, f"shaft 8 h6 (collars 12)")
ax2.text(xn, 118, f"blades: {sel['airfoil']} -> NACA 4418 root, root chord {sel['chord_mm'][0]:.1f} mm, max chord {max(sel['chord_mm']):.1f} mm, root twist {sel['twist_deg'][0]:.1f} deg; pocket floor r {P['pocket_floor_r']:.0f}; bolt r {P['bolt_r']:.0f}", color=INK2, fontsize=8)
ax2.set_aspect("equal"); ax2.set_xlim(xn - 60, xe + 60); ax2.set_ylim(-130, 125); ax2.set_axis_off(); ax2.set_title("Fig. 10b  v4 dimensioned section (mm)", loc="left", fontweight="bold", fontsize=10)
fig2.savefig(os.path.join(m.OUT, "fig10b_dimensioned.png"), dpi=140, facecolor=SURFACE, bbox_inches="tight"); print("dimensioned")
# ---------------- exploded
explode = {"nose_plug": -60, "hub_front": -40, "blade_0": -20, "blade_1": -20, "blade_2": -20, "hub_rear": -10, "shaft": 10, "hub_screw": -70, "lip_seal": 28, "bearing": 36, "circlip": 44, "front_cap": 20,
           "oring_front": 20, "tube": 40, "dog_hub": 46, "coupling_pin": 46, "drive_disc": 56, "motor": 66, "rear_cap": 90, "oring_rear": 90, "wetlink": 100, "vent": 100, "clamp_top": 40, "clamp_bot": 40, "duct": 0}
fig3 = plt.figure(figsize=(17, 8.5), facecolor=SURFACE); ax3 = fig3.add_subplot(111, projection="3d", facecolor=SURFACE); allx = []
for n, p in parts.items():
    off = explode.get(n, 0 if not n.startswith("bolt") else -20)
    tris = mesh(p["solid"]) + np.array([off, 0, 0]); allx += [tris[:, :, 0].min(), tris[:, :, 0].max()]
    ax3.add_collection3d(Poly3DCollection(tris, facecolors=shade(tris, p["color"]), edgecolors="none", alpha=0.25 if n == "duct" else 1.0))
xc = 0.5 * (min(allx) + max(allx)); half = 0.5 * (max(allx) - min(allx)) + 40
ax3.set_xlim(xc - half, xc + half); ax3.set_ylim(-115, 115); ax3.set_zlim(-115, 115); ax3.set_box_aspect((2 * half, 230, 230), zoom=1.15); ax3.view_init(elev=18, azim=-62); ax3.set_axis_off()
for txt, pn, zt in [("nose plug + front hub half", "hub_front", 40), ("blades (airfoil tongues)", "blade_0", 108), ("rear hub half", "hub_rear", -40), ("316 shaft (D-flat, 2 collars)", "shaft", -22), ("front cap: PTFE seal + 608", "front_cap", 48),
                    ("3 in tube", "tube", 50), ("dog hub + TPU disc", "drive_disc", -44), ("GL60 KV25", "motor", 46), ("rear cap: motor mount, WetLink, vent", "rear_cap", 50), ("clamp + struts + guard ring", "duct", 112)]:
    bb = parts[pn]["solid"].BoundingBox(); ax3.text(0.5 * (bb.xmin + bb.xmax) + explode.get(pn, 0), 0, zt + (6 if zt > 0 else -6), txt, color=INK2, fontsize=8, ha="center", va="bottom" if zt > 0 else "top")
fig3.suptitle("Fig. 10c  v4 exploded view (water flows left to right)", x=0.03, ha="left", fontsize=13, fontweight="bold", color=INK)
fig3.savefig(os.path.join(m.OUT, "fig10c_exploded.png"), dpi=140, facecolor=SURFACE, bbox_inches="tight"); print("exploded")
