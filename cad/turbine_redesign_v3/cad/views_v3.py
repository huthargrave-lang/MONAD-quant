#!/usr/bin/env python
"""Section (with waterproof boundary + load paths), dimensioned section, and exploded views for a v3 variant."""
import json, math, os, sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_v3 as m
VAR = sys.argv[1] if len(sys.argv) > 1 else "min76"
parts, blade, L = m.build(VAR); P = m.P; V = m.VARIANTS[VAR]
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
            if a[1] * b[1] < 0:
                s_ = -a[1] / (b[1] - a[1]); pts.append(a + s_ * (b - a))
        if len(pts) == 2: segs.append([(pts[0][0], pts[0][2]), (pts[1][0], pts[1][2])])
    return segs

# ---------------- section with boundary and load paths
fig, ax = plt.subplots(figsize=(16, 9), facecolor=SURFACE); ax.set_facecolor(SURFACE)
for n, p in parts.items():
    segs = section_segs(p["solid"])
    if segs: ax.add_collection(LineCollection(segs, colors=[p["color"]], linewidths=1.3))
x0, x1 = L["x_tube"]; ro = P["tube_od"] / 2; ft = V["flange_t"]
for sgn in (1, -1):
    ax.plot([x0 - ft, x1 + ft], [sgn * (ro + 0.8)] * 2, "--", color=RED, lw=1.6)
    ax.plot([x0 - ft] * 2, [0, sgn * ro], "--", color=RED, lw=1.6)
    ax.plot([x1 + ft] * 2, [sgn * V["seal_od"] / 2, sgn * ro], "--", color=RED, lw=1.6)
    ax.plot([L["x_seal"], L["x_seal"] + V["seal_w"]], [sgn * (P["spindle_d"] / 2 + 0.28)] * 2, "--", color=RED, lw=2.5)
ax.annotate(f"WATERPROOF BOUNDARY (red): anodised tube + {V['n_orings']} static EPDM O-ring(s) per anodised 6061 cap + ONE rotary PTFE lip seal on the Speedi-Sleeved stationary spindle;\nleads run inside the spindle bore and leave through the O-ring potting plug in the recessed spindle end (static, demountable)",
            (x1 + ft, -ro), xytext=(x0 - 15, -98), color=RED, fontsize=8.5, arrowprops=dict(arrowstyle="->", color=RED))
ann = [("THRUST PATH: blade -> airfoil tongue (2 axial pins) -> carrier segment -> rear lip -> rear cap flange -> rear cap shoulder -> rear bearing -> shim -> split thrust ring -> spindle -> boss (cross pin) -> 3 struts -> duct clevises", (x1 - 3, 30), (x0 + 10, 92)),
       ("REVERSE LOAD: carrier front lip -> front cap -> front bearing -> front circlip (DIN 471-15, 0.1 mm gap, 24 mm recess) -> spindle", (x0 + 4, 25), (x0 - 60, 78)),
       ("TORQUE PATH: blades -> carrier lugs (in the flange notches) -> front cap -> TPU dog clutch (dogs 45 deg off the screws) -> GL60 bell; stator reaction -> integral spindle flange -> spindle -> boss pin -> struts", (L["x_disc"] + 1, -20), (x0 - 60, -62)),
       (f"GL60 KV25 in the dry drum; stator on the integral spindle flange (counterbored screws, 45 deg lead channel into the bore); metal heat path spindle -> boss -> water", (L["x_motor"][0] + 10, 15), (x1 + 8, 62)),
       (f"PTFE lip seal {V['seal']} on Speedi-Sleeve 99059; {V['brg']}-2RS bearings; split thrust ring + shim; labyrinth tongue/groove; counterbored M6 vent", (L["x_seal"] + 2, 8), (x1 + 10, -45)),
       ("stationary 6061 boss 10 mm: cross pin, recessed spindle end with potting plug, rear lead groove (soft-potted), strut tabs (pinned); profile-cut 6061 struts, 14 mm cranked jog", (L["x_boss"][0] + 4, -36), (x1 + 15, -80)),
       ("printed 3-segment carrier: lips capture both cap flanges; 6x M3 316 bolts in nut traps", (L["x_blade_centre"] - 10, -ro - 4), (x0 - 50, -40)),
       (f"duct / guard ring ID {P['duct_id']:.0f} ({(P['duct_id']-203.2)/2:.1f} mm tip clearance), strut clevises", (x0 - 10, P["duct_id"] / 2), (x0 - 45, 100))]
for txt, xy, xt in ann:
    ax.annotate(txt, xy, xytext=xt, color=INK, fontsize=8, arrowprops=dict(arrowstyle="->", color=INK2))
ax.set_aspect("equal"); ax.set_xlim(L["x_dome_tip"] - 60, L["x_boss"][1] + 50); ax.set_ylim(-112, 112)
ax.grid(True, color=GRID, lw=0.7); ax.set_axisbelow(True); ax.set_xlabel("X (mm), flow ->"); ax.set_ylabel("Z (mm)")
for s_ in ("top", "right"): ax.spines[s_].set_visible(False)
ax.set_title(f"v3 '{VAR}': section through the axis. Operating depth {L['axial_depth_mm']:.1f} mm (target 76). Hub radius {L['r_hub']:.1f} mm, rotor 203.2 mm", loc="left", fontweight="bold")
fig.savefig(os.path.join(m.OUT, f"{VAR}_section.png"), dpi=140, facecolor=SURFACE, bbox_inches="tight"); print("wrote section")

# ---------------- dimensioned section
fig2, ax2 = plt.subplots(figsize=(16, 9), facecolor=SURFACE); ax2.set_facecolor(SURFACE)
for n, p in parts.items():
    segs = section_segs(p["solid"])
    if segs: ax2.add_collection(LineCollection(segs, colors=["#9a9a9a"], linewidths=0.9))
def dim_h(xa, xb, y, txt, off=0):
    ax2.annotate("", (xa, y), (xb, y), arrowprops=dict(arrowstyle="<->", color=INK, lw=1.0)); ax2.text(0.5 * (xa + xb), y + 2 + off, txt, ha="center", color=INK, fontsize=8.5)
    for x in (xa, xb): ax2.plot([x, x], [y - 4, y + 4], color=INK, lw=0.6)
def dim_v(x, ya, yb, txt):
    ax2.annotate("", (x, ya), (x, yb), arrowprops=dict(arrowstyle="<->", color=INK, lw=1.0)); ax2.text(x + 2, 0.5 * (ya + yb), txt, va="center", color=INK, fontsize=8.5, rotation=90)
xd, xr = L["x_dome_tip"], L["x_boss"][1]
dim_h(xd, xr, -118, f"OPERATING DEPTH {L['axial_depth_mm']:.1f} (dome tip to boss rear; duct and strut feet inside)")
dim_h(x0 - ft, x1 + ft, -ro - 12, f"drum {x1 - x0 + 2*ft:.1f} (tube {L['L_tube']:.1f} + 2 x {ft} flange)")
dim_h(xd, x0 - ft, ro + 14, f"dome {V['dome_h']}")
dim_h(x1 + ft, L["x_boss"][0], ro + 22, f"lip {P['carrier_lip']} + gap {P['gap_drum_boss']}")
dim_h(L["x_boss"][0], L["x_boss"][1], ro + 14, f"boss {V['boss_t']}")
dim_h(L["x_motor"][0], L["x_motor"][1], 40, "GL60 22.3")
dim_h(L["x_brg_front"], L["x_brg_front"] + V["brg_w"], -17, f"{V['brg']}")
dim_h(L["x_brg_rear"], L["x_brg_rear"] + V["brg_w"], -17, f"{V['brg']}")
dim_h(L["x_seal"], L["x_seal"] + V["seal_w"], 14, f"seal {V['seal']}")
dim_h(L["x_brg_front"] + V["brg_w"] / 2, L["x_brg_rear"] + V["brg_w"] / 2, -30, f"bearing centres {L['x_brg_rear'] - L['x_brg_front']:.1f}")
dim_v(xr + 18, 0, P["tube_od"] / 2, f"tube OD {P['tube_od']} / ID {P['tube_id']}")
dim_v(xr + 30, 0, L["r_hub"], f"carrier OD {2*L['r_hub']:.1f} (hub ratio {L['r_hub']/101.6:.2f})")
dim_v(xr + 42, 0, 101.6, "rotor R 101.6 (dia 203.2)")
dim_v(xd - 14, -P["duct_id"] / 2, P["duct_id"] / 2, f"duct ID {P['duct_id']}")
dim_v(L["x_boss"][1] + 6, 0, P["spindle_d"] / 2, f"spindle 15 h6, bore {P['spindle_bore']}")
ax2.text(xd, 112, f"variant '{VAR}': plugs {V['plug_front']}/{V['plug_rear']} mm with {V['n_orings']} x AS568-147 EPDM (groove 3.6 x 2.08, lands {P['oring_land']}); carrier lips {P['carrier_lip']} mm; struts 4 mm 6061 plate with {V['strut_jog']} mm jog; boss {V['boss_t']} mm", color=INK2, fontsize=8)
ax2.set_aspect("equal"); ax2.set_xlim(xd - 60, xr + 60); ax2.set_ylim(-128, 118); ax2.set_axis_off()
ax2.set_title(f"v3 '{VAR}': dimensioned section (mm)", loc="left", fontweight="bold")
fig2.savefig(os.path.join(m.OUT, f"{VAR}_dimensioned.png"), dpi=140, facecolor=SURFACE, bbox_inches="tight"); print("wrote dimensioned")

# ---------------- exploded
explode = {"dome": -70, "front_cap": -40, "circlip_front": -34, "bearing_front": -28, "drive_disc": -20, "motor": -6, "spindle": 0, "shim_rear": 28, "split_collar": 32,
           "bearing_rear": 36, "rear_cap": 60, "lip_seal": 78, "speedi_sleeve": 70, "vent_screw": 66, "tube": 10, "carrier_0": 10, "carrier_1": 10, "carrier_2": 10,
           "blade_0": 10, "blade_1": 10, "blade_2": 10, "boss": 100, "potting_plug": 92, "plug_oring": 92, "strut_0": 100, "strut_1": 100, "strut_2": 100, "duct": 100}
fig3 = plt.figure(figsize=(17, 8.5), facecolor=SURFACE); ax3 = fig3.add_subplot(111, projection="3d", facecolor=SURFACE)
allx = []
for n, p in parts.items():
    off = explode.get(n, 10 if n.startswith("pin") else (explode["front_cap"] if n.startswith("oring") and p["solid"].BoundingBox().xmin < 0.5 * sum(L["x_tube"]) else explode["rear_cap"] if n.startswith("oring") else (-20 if n.startswith("screw_disc") else -6 if n.startswith("screw_stator") else 0)))
    tris = mesh(p["solid"]) + np.array([off, 0, 0]); allx += [tris[:, :, 0].min(), tris[:, :, 0].max()]
    ax3.add_collection3d(Poly3DCollection(tris, facecolors=shade(tris, p["color"]), edgecolors="none", alpha=0.25 if n == "duct" else 1.0))
xc = 0.5 * (min(allx) + max(allx)); half = 0.5 * (max(allx) - min(allx)) + 45
ax3.set_xlim(xc - half, xc + half); ax3.set_ylim(-110, 110); ax3.set_zlim(-110, 110); ax3.set_box_aspect((2 * half, 220, 220), zoom=1.15); ax3.view_init(elev=18, azim=-62); ax3.set_axis_off()
for txt, pn, zt in [("dome (print)", "dome", 40), (f"front cap (6061)\n{V['n_orings']} O-ring(s), bearing pocket", "front_cap", 48), ("TPU disc", "drive_disc", -40), ("GL60 KV25", "motor", 44), ("6061 spindle\n(flange, bore, split ring)", "spindle", -22),
                    ("rear cap (6061)\nbearing + PTFE lip seal", "rear_cap", 48), ("carrier segments + pinned blades\non the anodised tube", "carrier_0", 108), ("6061 boss + potting plug,\nprofile-cut 6061 struts, duct", "boss", 112)]:
    bb = parts[pn]["solid"].BoundingBox(); ax3.text(0.5 * (bb.xmin + bb.xmax) + explode.get(pn, 0), 0, zt + (6 if zt > 0 else -6), txt, color=INK2, fontsize=8, ha="center", va="bottom" if zt > 0 else "top")
fig3.suptitle(f"v3 '{VAR}': exploded view (water flows left to right)", x=0.03, ha="left", fontsize=13, fontweight="bold", color=INK)
fig3.savefig(os.path.join(m.OUT, f"{VAR}_exploded.png"), dpi=140, facecolor=SURFACE, bbox_inches="tight"); print("wrote exploded")
