#!/usr/bin/env python
"""Preview figure: 3D render of the blade, rotor front view, design curves and BEM performance."""
import csv, json, os, struct
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.collections import PolyCollection
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

OUT = os.path.dirname(os.path.abspath(__file__))
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"          # validated categorical slots 1-3

spec = json.load(open(os.path.join(OUT, "design_spec.json")))
rows = list(csv.DictReader(open(os.path.join(OUT, "blade_stations.csv"))))
r = np.array([float(x["r_mm"]) for x in rows]); chord = np.array([float(x["chord_mm"]) for x in rows])
twist = np.array([float(x["twist_deg_from_rotor_plane"]) for x in rows]); tc = np.array([float(x["thickness_ratio"]) for x in rows])

def read_stl(path):
    with open(path, "rb") as f:
        f.read(80); n = struct.unpack("<I", f.read(4))[0]
        data = np.frombuffer(f.read(n * 50), dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]))
    return data["v"].reshape(-1, 3, 3).astype(float)

def shaded(tris, light, base):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]); n /= np.linalg.norm(n, axis=1)[:, None] + 1e-12
    sh = 0.30 + 0.70 * np.clip(n @ light, 0, 1)
    return np.clip(np.array(base)[None, :] * sh[:, None] + 0.10, 0, 1), n

blade = read_stl(os.path.join(OUT, "turbine_blade_8in.stl"))
rotor = read_stl(os.path.join(OUT, "turbine_rotor_8in_3blade.stl"))

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK, "axes.titleweight": "bold",
                     "axes.titlesize": 10, "axes.spines.top": False, "axes.spines.right": False})
fig = plt.figure(figsize=(15, 8.6), facecolor=SURFACE)
gs = GridSpec(2, 3, figure=fig, width_ratios=[1.25, 1, 1], hspace=0.40, wspace=0.28, left=0.03, right=0.98, top=0.89, bottom=0.07)

# ---- 3D blade render ----------------------------------------------------------
ax = fig.add_subplot(gs[0, 0], projection="3d", facecolor=SURFACE)
light = np.array([-0.5, -0.5, 0.7]); light /= np.linalg.norm(light)
cols, _ = shaded(blade, light, [0.30, 0.50, 0.80])
ax.add_collection3d(Poly3DCollection(blade, facecolors=cols, edgecolors="none"))
th = np.linspace(0, 2 * np.pi, 120); hx0 = spec["hub_center_x_mm"]; rh = spec["hub_radius_mm"]; hl = spec["hub_length_mm"]
for x in (hx0 - hl / 2, hx0 + hl / 2):
    ax.plot(np.full_like(th, x), rh * np.sin(th), rh * np.cos(th), color=INK2, lw=0.7, alpha=0.5)
for t in np.linspace(0, 2 * np.pi, 9)[:-1]:
    ax.plot([hx0 - hl / 2, hx0 + hl / 2], [rh * np.sin(t)] * 2, [rh * np.cos(t)] * 2, color=INK2, lw=0.5, alpha=0.35)
ax.set_xlim(-35, 45); ax.set_ylim(-55, 45); ax.set_zlim(-10, 105)
ax.set_box_aspect((80, 100, 115), zoom=1.55)
ax.view_init(elev=18, azim=-140)
ax.set_axis_off()
ax.set_title("Blade on a 3 in hub (wireframe)", loc="left", pad=0)
ax.text2D(0.02, 0.02, "flow enters from the left (-X)\nNACA 4422 root → NACA 4412 tip, 0.6 mm trailing edge", transform=ax.transAxes, color=INK2, fontsize=8)

# ---- rotor front view (looking downstream along +X) ---------------------------------
af = fig.add_subplot(gs[1, 0], facecolor=SURFACE)
order = np.argsort(rotor[:, :, 0].mean(axis=1))[::-1]        # far (downstream) first, near last
tri = rotor[order]
cols, n = shaded(tri, np.array([-0.8, 0.3, 0.5]) / np.linalg.norm([-0.8, 0.3, 0.5]), [0.30, 0.50, 0.80])
front = n[:, 0] < 0                                          # faces whose normal points upstream
af.add_collection(PolyCollection(tri[front][:, :, [1, 2]] * [-1, 1], facecolors=cols[front], edgecolors="none"))
af.set_aspect("equal"); af.set_xlim(-115, 115); af.set_ylim(-115, 115); af.set_axis_off()
af.set_title("Rotor from upstream (turns counter-clockwise)", loc="left")
af.text(0, -108, "8.00 in diameter", color=INK2, fontsize=8, ha="center")
c = plt.Circle((0, 0), 101.6, fill=False, color=INK2, lw=0.8, ls="--"); af.add_patch(c)
af.annotate("", xy=(72, 72), xytext=(92, 46), arrowprops=dict(arrowstyle="->", color=INK, lw=1.2, connectionstyle="arc3,rad=-0.3"))

def style(a, title, xl, yl):
    a.set_facecolor(SURFACE); a.set_title(title, loc="left"); a.set_xlabel(xl); a.set_ylabel(yl)
    a.grid(True, color=GRID, lw=0.8); a.set_axisbelow(True)

# ---- chord & thickness ----------------------------------------------------------
a1 = fig.add_subplot(gs[0, 1]); style(a1, "Chord and max thickness vs radius (mm)", "radius r (mm)", "mm")
a1.plot(r, chord, color=S1, lw=2); a1.plot(r, chord * tc, color=S2, lw=2)
a1.axvline(spec["hub_radius_mm"], color=GRID, lw=1.2); a1.text(spec["hub_radius_mm"] + 1, 1.5, "hub surface", color=INK2, fontsize=7.5)
a1.text(r[-1] + 1.5, chord[-1], "chord", color=INK, fontsize=8, va="center"); a1.text(r[-1] + 1.5, chord[-1] * tc[-1], "thickness", color=INK, fontsize=8, va="center")
a1.set_xlim(spec["hub_radius_mm"] - 5, 114); a1.set_ylim(0, 82)
a1.legend(["chord", "max thickness"], frameon=False, loc="upper right", fontsize=8)

# ---- twist --------------------------------------------------------------------------
a2 = fig.add_subplot(gs[0, 2]); style(a2, "Twist (chord angle from rotor plane)", "radius r (mm)", "degrees")
a2.plot(r, twist, color=S1, lw=2); a2.set_xlim(spec["hub_radius_mm"] - 5, 105); a2.set_ylim(8, 24)
a2.text(r[0] + 2, twist[0] - 0.2, f"{twist[0]:.1f}° at root", color=INK, fontsize=8, va="top")
a2.text(r[-1] - 1, twist[-1] + 0.6, f"{twist[-1]:.1f}° at tip", color=INK, fontsize=8, ha="right")

# ---- Cp vs TSR -------------------------------------------------------------------
a3 = fig.add_subplot(gs[1, 1]); style(a3, "Power coefficient vs tip-speed ratio (BEM)", "tip-speed ratio λ = ωR / V", "Cp")
tsr = np.array(spec["cp_curve"]["tsr"]); cp = np.array(spec["cp_curve"]["cp"])
m = (tsr >= 1.0) & (cp > 0)
a3.plot(tsr[m], cp[m], color=S1, lw=2); a3.set_xlim(1, 7); a3.set_ylim(0, 0.65)
j = int(np.argmax(cp)); a3.plot([tsr[j]], [cp[j]], "o", color=S1, ms=7, mec=SURFACE, mew=2)
a3.annotate(f"peak Cp {cp[j]:.2f} at λ = {tsr[j]:.2f}", (tsr[j], cp[j]), xytext=(tsr[j] + 0.3, cp[j] + 0.07), color=INK, fontsize=8)
a3.axhline(16 / 27, color=GRID, lw=1, ls="--"); a3.text(1.1, 16 / 27 - 0.035, "Betz limit 0.59", color=INK2, fontsize=7)

# ---- power vs rpm ---------------------------------------------------------------
a4 = fig.add_subplot(gs[1, 2]); style(a4, "Shaft power vs rotor speed", "rpm", "watts")
for V, col in zip(["1.0", "1.5", "2.0"], [S1, S2, S3]):
    pcv = spec["power_curve"][V]; rpm = np.array(pcv["rpm"]); P = np.array(pcv["P_W"])
    mm = (tsr >= 1.0) & (P > 0)
    a4.plot(rpm[mm], P[mm], color=col, lw=2)
    k = int(np.argmax(P)); a4.text(rpm[k] + 10, P[k] + 0.8, f"{V} m/s", color=INK, fontsize=8)
a4.legend(["1.0 m/s", "1.5 m/s", "2.0 m/s"], frameon=False, loc="upper left", fontsize=8)
a4.set_xlim(0, 950); a4.set_ylim(0, 48)

fig.suptitle("Water turbine blade — 8 in diameter, 3 in wide, designed for 1–2 m/s flow", x=0.03, ha="left", fontsize=13, fontweight="bold", color=INK)
fig.text(0.03, 0.925, "Blade-element-momentum design with Prandtl tip/hub loss; NACA 44xx polar model (approximate, not CFD).", color=INK2, fontsize=9)
fig.savefig(os.path.join(OUT, "blade_preview.png"), dpi=150, facecolor=SURFACE)
print("wrote blade_preview.png")
