#!/usr/bin/env python
"""Exploded view and a sectional view (plane y=0) of the assembly, with the waterproof boundary marked."""
import json, math, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection, LineCollection
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import cadquery as cq
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import make_assembly as ma

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
CONFIG = sys.argv[1] if len(sys.argv) > 1 else "A"
if CONFIG == "A":
    parts, blade, rinfo, layout = ma.build_A()
else:
    parts, blade, rinfo, layout = ma.build()
TUBE_OD = ma.P["a_tube_od"] if CONFIG == "A" else ma.P["tube_od"]

def mesh(solid, tol=0.15, ang=0.3):
    v, t = solid.tessellate(tol, ang)
    V = np.array([(p.x, p.y, p.z) for p in v]); T = np.array(t)
    return V[T]

def shade(tris, base, light=(-0.4, -0.6, 0.7)):
    L = np.array(light) / np.linalg.norm(light)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]); n /= np.linalg.norm(n, axis=1)[:, None] + 1e-12
    s = 0.35 + 0.65 * np.clip(n @ L, 0, 1)
    return np.clip(np.array(base)[None, :] * s[:, None] + 0.08, 0, 1)

# ---------------------------------------------------------------- exploded view
if CONFIG == "A":
    explode = {"rotor": -95, "collar": -42, "speedi_sleeve": -34, "lip_seal": -26, "front_cap": 0, "bearing_0": 22, "bearing_1": 22, "shaft": -62,
               "coupling": 60, "bell_adapter": 85, "motor": 110, "rear_cap": 165, "nacelle_tube": 30, "clamp_ring": 30, "strut_0": 30, "strut_1": 30, "strut_2": 30, "duct_ring": 30}
else:
    explode = {"nose": -75, "front_cap": -45, "drive_disc": -28, "motor": -10, "adapter_plate": 6, "flanged_collar": 16,
               "rotor_ring": 0, "drum_tube": 0, "rear_cap": 50, "lip_seal": 68, "bearing_0": 40, "bearing_1": 40,
               "spindle": 100, "strut_hub": 130, "strut_0": 130, "strut_1": 130, "strut_2": 130, "duct_ring": 130}
fig = plt.figure(figsize=(17, 8.5), facecolor=SURFACE)
ax = fig.add_subplot(111, projection="3d", facecolor=SURFACE)
allx = []
for name, p in parts.items():
    if name.startswith("oring"):
        off = explode["front_cap"] if p["solid"].BoundingBox().xmin < 0.5 * sum(layout["x_tube"]) else explode["rear_cap"]
    else:
        off = explode.get(name, 0)
    tris = mesh(p["solid"]) + np.array([off, 0, 0])
    allx += [tris[:, :, 0].min(), tris[:, :, 0].max()]
    ax.add_collection3d(Poly3DCollection(tris, facecolors=shade(tris, p["color"]), edgecolors="none", alpha=1.0 if name != "duct_ring" else 0.2))
xc = 0.5 * (min(allx) + max(allx)); half = 0.5 * (max(allx) - min(allx)) + 45
ax.set_xlim(xc - half, xc + half); ax.set_ylim(-110, 110); ax.set_zlim(-110, 110)
ax.set_box_aspect((2 * half, 220, 220), zoom=1.15); ax.view_init(elev=18, azim=-62); ax.set_axis_off()
if CONFIG == "A":
    labels = [("rotor (rev 2)\n12 mm bore", "rotor", 108), ("316 shaft 12 h6", "shaft", -22), ("collar, Speedi-Sleeve,\nlip seal 12x22x7", "lip_seal", 30),
              ("front cap (machined):\n2 O-rings, 2x 6001-2RS", "front_cap", 50), ("jaw coupling", "coupling", -24), ("bell adapter", "bell_adapter", 40),
              ("GL60 KV25", "motor", 44), ("rear cap (machined):\nmotor mount, WetLink, vent", "rear_cap", 50), ("80 mm tube, clamp ring,\n3 struts, duct", "clamp_ring", 112)]
else:
    labels = [("nose cone\n(print)", "nose", 40), ("front cap +\n2 O-rings", "front_cap", 36), ("TPU drive\ndisc", "drive_disc", 30), ("49 mm gimbal motor\n(bell forward)", "motor", 32),
              ("adapter +\n316 collar", "flanged_collar", 30), ("blade ring on\n63.5 mm drum tube", "rotor_ring", 108), ("rear cap (machined):\n2 bearings + lip seal", "rear_cap", 36),
              ("316 hollow\nspindle", "spindle", 16), ("strut boss, 3 struts,\nduct interface", "strut_hub", 112)]
for txt, pname, zt in labels:
    bb = parts[pname]["solid"].BoundingBox(); off = explode.get(pname, 0)
    ax.text(0.5 * (bb.xmin + bb.xmax) + off, 0, zt + (6 if zt > 0 else -6), txt, color=INK2, fontsize=8, ha="center", va="bottom" if zt > 0 else "top")
title_e = ("Configuration A (recommended): stationary generator nacelle behind the rotor - exploded (water flows left to right)" if CONFIG == "A"
           else "Configuration B (compact alternative): hub-integrated generator in a rotating drum - exploded (water flows left to right)")
fig.suptitle(title_e, x=0.03, ha="left", fontsize=13, fontweight="bold", color=INK)
fig.savefig(os.path.join(ma.OUT, f"{CONFIG}_exploded_view.png"), dpi=140, facecolor=SURFACE, bbox_inches="tight")
print(f"wrote {CONFIG}_exploded_view.png")

# ---------------------------------------------------------------- section view at y = 0 (X horizontal, Z vertical)
def section_polys(solid, tol=0.08):
    """Polygons of the solid's cross-section in the plane y=0 (from the tessellation)."""
    v, t = solid.tessellate(tol, 0.25)
    V = np.array([(p.x, p.y, p.z) for p in v]); T = np.array(t)
    segs = []
    for tri in V[T]:
        y = tri[:, 1]
        pts = []
        for i in range(3):
            a, b = tri[i], tri[(i + 1) % 3]
            if (a[1] - 0) * (b[1] - 0) < 0:
                s = -a[1] / (b[1] - a[1]); pts.append(a + s * (b - a))
        if len(pts) == 2:
            segs.append([(pts[0][0], pts[0][2]), (pts[1][0], pts[1][2])])
    return segs

fig2, ax2 = plt.subplots(figsize=(17, 9), facecolor=SURFACE)
ax2.set_facecolor(SURFACE)
for name, p in parts.items():
    segs = section_polys(p["solid"])
    if not segs:
        continue
    col = p["color"] if name != "duct_ring" else (0.8, 0.8, 0.8)
    ax2.add_collection(LineCollection(segs, colors=[col], linewidths=1.4 if name not in ("rotor_ring",) else 1.0))
# waterproof boundary (dashed red)
bx0, bx1 = layout["x_tube"]
rt_o = TUBE_OD / 2
xs_ = layout["x_seal"]
ft = ma.P["cap_flange_t"]
if CONFIG == "A":
    shaft_r = ma.P["a_shaft_d"] / 2 + 0.28; seal_w = ma.P["a_seal_w"]
    for sgn in (1, -1):
        ax2.plot([bx0 - ft, bx1 + ft], [sgn * (rt_o + 0.8)] * 2, ls="--", color="#d62728", lw=1.6)
        ax2.plot([bx0 - ft] * 2, [sgn * ma.P["a_seal_od"] / 2, sgn * rt_o], ls="--", color="#d62728", lw=1.6)
        ax2.plot([bx1 + ft] * 2, [0, sgn * rt_o], ls="--", color="#d62728", lw=1.6)
        ax2.plot([xs_, xs_ + seal_w], [sgn * shaft_r] * 2, ls="--", color="#d62728", lw=2.5)
    ax2.annotate("WATERPROOF BOUNDARY (red dashed): anodised tube + two static O-rings per machined cap + one rotary lip seal on the Speedi-Sleeved 12 mm shaft",
                 (bx1 + ft, -rt_o), xytext=(bx0 - 30, -100), color="#d62728", fontsize=9, arrowprops=dict(arrowstyle="->", color="#d62728"))
    ax2.annotate("lip seal 12x22x7 on SKF Speedi-Sleeve\n(the only moving seal)", (xs_ + 3, shaft_r), xytext=(xs_ - 60, -60), color=INK, fontsize=8, arrowprops=dict(arrowstyle="->", color=INK2))
    ax2.annotate("2x 6001-2RS 440C bearings, DIN 472 circlip takes the thrust", (layout["x_bearings"][0] + 8, -ma.P["a_brg_od"] / 2), xytext=(layout["x_bearings"][0] - 10, -80), color=INK, fontsize=8, arrowprops=dict(arrowstyle="->", color=INK2))
    ax2.annotate("GL60 KV25: stator bolted to the aluminium rear cap (water-cooled);\nbell drives a Delrin adapter -> jaw coupling -> shaft", (layout["x_motor"][0] + 10, 22), xytext=(layout["x_motor"][0] - 40, 80), color=INK, fontsize=8, arrowprops=dict(arrowstyle="->", color=INK2))
    ax2.annotate("WetLink M10 penetrator (cable) + M6 vent/vacuum port", (bx1 + ft, ma.P["a_penetrator_r"]), xytext=(bx1 + 15, 55), color=INK, fontsize=8, arrowprops=dict(arrowstyle="->", color=INK2))
    ax2.annotate("rotor rev 2 on a 12 mm 316 shaft, 3.2 mm cross pin + grub screws", (layout["x_hub_rear"] - 25, 25), xytext=(layout["x_nose_tip"] - 10, 70), color=INK, fontsize=8, arrowprops=dict(arrowstyle="->", color=INK2))
    ax2.annotate("printed clamp ring + 3 struts (behind the rotor)", (layout["x_strut_centre"], 60), xytext=(layout["x_strut_centre"] + 20, 95), color=INK, fontsize=8, arrowprops=dict(arrowstyle="->", color=INK2))
    ax2.annotate("duct (reference)", (layout["x_duct"][0], 103), xytext=(layout["x_duct"][0] - 60, 100), color=INK, fontsize=8, arrowprops=dict(arrowstyle="->", color=INK2))
else:
    for sgn in (1, -1):
        ax2.plot([bx0 - ft, bx1 + ft], [sgn * rt_o + 0.8 * sgn] * 2, ls="--", color="#d62728", lw=1.6)
        ax2.plot([bx0 - ft] * 2, [0, sgn * rt_o], ls="--", color="#d62728", lw=1.6)
        ax2.plot([bx1 + ft] * 2, [sgn * ma.P["seal_od"] / 2, sgn * rt_o], ls="--", color="#d62728", lw=1.6)
        ax2.plot([xs_, xs_ + ma.P["seal_w"]], [sgn * ma.P["spindle_d"] / 2] * 2, ls="--", color="#d62728", lw=2.5)
    ax2.annotate("WATERPROOF BOUNDARY (red dashed): rotating anodised tube + two static O-rings per machined cap + one rotary lip seal on the stationary 15 mm spindle",
                 (bx1 + ft, -rt_o), xytext=(bx1 - 80, -100), color="#d62728", fontsize=9, arrowprops=dict(arrowstyle="->", color="#d62728"))
    ax2.annotate("rotary lip seal 15x24x5 on Speedi-Sleeve\n(the only moving seal)", (xs_ + 2, ma.P["spindle_d"] / 2), xytext=(xs_ + 30, -45), color=INK, fontsize=8, arrowprops=dict(arrowstyle="->", color=INK2))
    ax2.annotate("2x 6902-2RS SS bearings (dry side)", (layout["x_bearings"][0] + 7, -ma.P["brg_od"] / 2), xytext=(layout["x_bearings"][0] - 10, -70), color=INK, fontsize=8, arrowprops=dict(arrowstyle="->", color=INK2))
    ax2.annotate("49 mm gimbal motor: stator on the 316 flanged collar (stationary);\nbell bolted to the drum front cap through a TPU disc (rotates)", (layout["x_motor"][0] + 10, -18), xytext=(layout["x_nose_tip"] - 20, -75), color=INK, fontsize=8, arrowprops=dict(arrowstyle="->", color=INK2))
    ax2.annotate("cable inside the hollow spindle, potted at the strut boss", (layout["x_rear_end"] - 6, 0), xytext=(layout["x_rear_end"] + 10, -30), color=INK, fontsize=8, arrowprops=dict(arrowstyle="->", color=INK2))
    ax2.annotate("printed blade ring over the drum tube (2 halves, epoxied)", (layout["x_blade_centre"] + 8, -rinfo["r_hub"]), xytext=(layout["x_blade_centre"] + 20, -55), color=INK, fontsize=8, arrowprops=dict(arrowstyle="->", color=INK2))
    ax2.annotate("nose cone (print), bolted to the front cap", (layout["x_nose_tip"] + 6, 14), xytext=(layout["x_nose_tip"] - 15, 55), color=INK, fontsize=8, arrowprops=dict(arrowstyle="->", color=INK2))
    ax2.annotate("duct (reference), 2 mm tip clearance", (layout["x_duct"][0], 103), xytext=(layout["x_duct"][0] - 60, 95), color=INK, fontsize=8, arrowprops=dict(arrowstyle="->", color=INK2))
ax2.text(layout["x_nose_tip"], -108, f"flow ->   nose tip X = {layout['x_nose_tip']:.0f}, rear end X = {layout['x_rear_end']:.0f}; hub radius {rinfo['r_hub']:.1f} mm", color=INK2, fontsize=8)
ax2.set_aspect("equal"); ax2.set_xlim(layout["x_nose_tip"] - 25, layout["x_rear_end"] + 50); ax2.set_ylim(-112, 112)
ax2.set_xlabel("X (mm) - flow direction ->"); ax2.set_ylabel("Z (mm)")
ax2.grid(True, color=GRID, lw=0.7); ax2.set_axisbelow(True)
for s in ("top", "right"): ax2.spines[s].set_visible(False)
ax2.set_title(f"Configuration {CONFIG}: section through the rotor axis (plane y = 0). Axial depth {layout['axial_depth_mm']:.0f} mm ({layout['axial_depth_mm']/25.4:.1f} in)", loc="left", fontweight="bold")
fig2.savefig(os.path.join(ma.OUT, f"{CONFIG}_section_view.png"), dpi=140, facecolor=SURFACE, bbox_inches="tight")
print(f"wrote {CONFIG}_section_view.png")
