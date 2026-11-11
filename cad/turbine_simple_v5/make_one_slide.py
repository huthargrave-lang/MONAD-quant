#!/usr/bin/env python3
"""One 16:9 summary slide combining the three iteration diagrams, each cut to one chart and one takeaway:
  1 foil choice (system output per searched foil, 2-D L/D noted, foil shapes), 2 design history (dated timeline + net power in the
  0.5-1.0 m/s target band, dotted where a hand spin is needed), 3 generator (CubeMars GL60 KV25 @ 24 VDC chart with the turbine's
  operating window and three checks).  Numbers from out/slides/slide_numbers.json (make_slide_diagrams.py) and the v4 polar cache;
  the manufacturer chart is ref/gl60_kv25_24vdc_chart.png (supplied by the user)."""
import json, os
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); M = os.path.abspath(os.path.join(HERE, "..", "turbine_lowflow_v4", "model")); OUT = os.path.join(HERE, "out", "slides")
N = json.load(open(os.path.join(OUT, "slide_numbers.json"))); T = json.load(open(os.path.join(M, "polars_cache.json")))
IMG = os.path.join(HERE, "ref", "gl60_kv25_24vdc_chart.png")
INK, INK2, MUTE, GRID, NAVY, BLUE = "#1a1a1a", "#444444", "#7a7a7a", "#e6e4de", "#14365c", "#1f4e79"
GOLD, RED, OK_, WARN = "#b8860b", "#b84a3a", "#2e7d32", "#b84a3a"
plt.rcParams.update({"font.size": 11, "axes.edgecolor": "#999999", "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2})
fig = plt.figure(figsize=(16, 9), facecolor="white")
fig.text(0.03, 0.948, "Iteration review: foil choice, design history, generator check", fontsize=23, fontweight="bold", color=INK)
fig.text(0.03, 0.908, "8-in hydrokinetic turbine for 0.5-1.0 m/s with the CubeMars GL60 KV25. Model predictions; nothing measured yet.", fontsize=12.5, color=INK2)
COLX, COLW = (0.03, 0.355, 0.68), 0.295
def header(i, title, takeaway):
    x = COLX[i]
    fig.patches.append(FancyBboxPatch((x, 0.842), 0.026, 0.040, boxstyle="round,pad=0.002,rounding_size=0.006", transform=fig.transFigure, fc=BLUE, ec="none"))
    fig.text(x + 0.013, 0.862, str(i + 1), fontsize=14, fontweight="bold", color="white", ha="center", va="center")
    fig.text(x + 0.034, 0.862, title, fontsize=15.5, fontweight="bold", color=INK, va="center")
    fig.text(x, 0.822, takeaway, fontsize=11.5, color=BLUE, fontweight="bold", va="top", linespacing=1.3)
# ======================= 1 foil choice
foils = ["naca4412", "naca4415", "sg6043", "fx63137"]; name = {"naca4412": "NACA 4412", "naca4415": "NACA 4415", "sg6043": "SG6043", "fx63137": "FX 63-137"}
J = {k: N["foil_J"][k]["J_uniform"] for k in foils}; LD = {k: N["foils"][k]["LD_8e4"] for k in foils}
best2d = max(foils, key=lambda k: LD[k])
header(0, "Foil choice: NACA 4412", f"The best 2-D foil ({name[best2d]}) is not the best turbine:\nNACA 4412 makes {(J['naca4412'] / J[best2d] - 1) * 100:.0f} % more power")
ax1 = fig.add_axes([0.158, 0.30, 0.16, 0.44])
yy = np.arange(len(foils))[::-1]
ax1.barh(yy, [J[k] for k in foils], height=0.58, color=[NAVY if k == "naca4412" else "#b7c7da" for k in foils])
for y, k in zip(yy, foils):
    ax1.text(J[k] + 0.02, y + 0.07, f"{J[k]:.2f} W", va="center", fontsize=11.5, fontweight="bold" if k == "naca4412" else None, color=INK)
    ax1.text(J[k] + 0.02, y - 0.22, f"2-D L/D {LD[k]:.0f}" + ("  (best)" if k == best2d else ""), va="center", fontsize=9.5, color="#c8692b" if k == best2d else MUTE)
ax1.set_yticks(yy); ax1.set_yticklabels([name[k] for k in foils], fontsize=11.5); ax1.set_xlim(0, max(J.values()) * 1.42); ax1.set_xticks([])
for s_ in ("top", "right", "bottom"): ax1.spines[s_].set_visible(False)
ax1.set_title("turbine output, mean of 0.5-1.0 m/s", loc="left", fontsize=10.5, color=INK2)
for y, k in zip(yy, foils):                                     # foil shapes left of the names
    c = np.array(T[k]["coords"]); c = (c - [c[:, 0].min(), 0]) / (c[:, 0].max() - c[:, 0].min())
    pos = ax1.get_position(); yf = pos.y0 + (y + 0.5) / len(foils) * pos.height
    a = fig.add_axes([0.030, yf - 0.022, 0.044, 0.044]); a.fill(c[:, 0], c[:, 1], color=NAVY if k == "naca4412" else "#9fb3cc", lw=0); a.set_aspect("equal"); a.set_xlim(-0.02, 1.02); a.set_ylim(-0.12, 0.2); a.set_axis_off()
fig.text(COLX[0], 0.245, "How it was chosen", fontsize=11, fontweight="bold", color=INK)
fig.text(COLX[0], 0.222, "- 7 open-source foils screened (NeuralFoil, an XFOIL\n  surrogate); E387 and E818 dropped (low confidence)\n- each foil built into rotors and scored as a whole\n  turbine with the GL60\n- NACA 4418 (18 % thick) used at the root to print",
         fontsize=10, color=INK2, va="top", linespacing=1.35)
# ======================= 2 design history
P = lambda k: np.array([N[k]["P"][str(V)] for V in (0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)])
gain06 = (N["it5"]["P"]["0.6"] / N["it12"]["P"]["0.6"] - 1) * 100
header(1, "Design history", f"Re-targeting to 0.5-1.0 m/s: self-starts at {N['it5']['min_start']} m/s\n(was {N['it12']['min_start']}-{N['it3']['min_start']}) and {gain06:+.0f} % power at 0.6 m/s")
# timeline strip
tl = [("29 Oct", "1-2 m/s\nblade", GOLD), ("31 Oct", "generator\n+ housing", GOLD), ("31 Oct", "76 mm\ndrum", RED), ("2 Nov", "low-flow\noptimum", BLUE), ("3 Nov", "printable\nv5", NAVY)]
x0, x1, ytl = COLX[1] + 0.022, COLX[1] + COLW - 0.022, 0.700
fig.lines.append(matplotlib.lines.Line2D([x0, x1], [ytl, ytl], transform=fig.transFigure, color="#b9b9b9", lw=2, zorder=1))
xs = np.linspace(x0, x1, len(tl))
for x, (d, lab, c) in zip(xs, tl):
    fig.lines.append(matplotlib.lines.Line2D([x], [ytl], transform=fig.transFigure, marker="o", ms=11, mfc=c, mec="white", mew=1.5, zorder=3))
    fig.text(x, ytl + 0.018, d, fontsize=9.5, color=INK2, ha="center", va="bottom", fontweight="bold")
    fig.text(x, ytl - 0.020, lab, fontsize=9.5, color=c, ha="center", va="top", linespacing=1.15)
xp = 0.5 * (xs[2] + xs[3]); fig.lines.append(matplotlib.lines.Line2D([xp, xp], [ytl - 0.012, ytl + 0.012], transform=fig.transFigure, color=BLUE, lw=2, ls="--"))
fig.text(xp, ytl - 0.075, "pivot to 0.5-1.0 m/s", fontsize=9.5, color=BLUE, ha="center", fontweight="bold", va="top")
ax2 = fig.add_axes([0.395, 0.155, 0.25, 0.43])
V = np.array([0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
lines = [("it12", "1-2 m/s blade (29-31 Oct)", GOLD, 2.4, "^"), ("it3", "76 mm drum (31 Oct)", RED, 2.4, "s"), ("it5", "current v5 (3 Nov)", NAVY, 3.4, "o")]
for k, lab, c, lw, mk in lines:
    p = P(k); s = N[k]["min_start"]; on = V >= s - 1e-9; edge = int(np.argmax(on)) if on.any() else len(V)
    ax2.plot(V[:edge + 1], p[:edge + 1], ":", color=c, lw=lw * 0.8)                     # needs a hand spin
    ax2.plot(V[on], p[on], "-", color=c, lw=lw, marker=mk, ms=6, mfc="white" if k != "it5" else c, mew=1.4, label=lab)
    if on.any(): ax2.plot(V[edge], p[edge], marker="*", ms=15, color=c, mec="white", mew=0.8, zorder=6)
ax2.plot([], [], ":", color=MUTE, lw=2, label="dotted: needs a hand spin"); ax2.plot([], [], "*", color=MUTE, ms=12, ls="none", label="star: self-start speed")
ax2.set_xlim(0.4, 1.02); ax2.set_ylim(0, 3.8); ax2.set_xticks([0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]); ax2.grid(True, color=GRID); ax2.set_axisbelow(True)
ax2.set_xlabel("water speed (m/s)"); ax2.set_ylabel("net 12 V power (W)")
ax2.legend(loc="upper left", fontsize=9.5, frameon=False, handlelength=2.2)
for s_ in ("top", "right"): ax2.spines[s_].set_visible(False)
ax2.text(1.0, 0.25, f"v4 final within {abs(N['it4b']['P']['0.7'] / N['it5']['P']['0.7'] - 1) * 100:.0f} % of v5", fontsize=9, color=MUTE, ha="right", style="italic")
# ======================= 3 generator
mo = N["motor"]; ops = {float(k): v for k, v in mo["ops"].items()}
q05, q10 = ops[0.5]["Qg"], ops[1.0]["Qg"]
header(2, "Generator: GL60 KV25", f"The turbine uses only {q05 / 0.6 * 100:.0f}-{q10 / 0.6 * 100:.0f} % of its rated torque;\nthe motor's own drag is the open risk")
img = np.asarray(Image.open(IMG).convert("RGB")); cx0, cx1, cy0, cy1 = 220, 930, 190, 760
ax3 = fig.add_axes([0.672, 0.305, 0.315, 0.475]); ax3.imshow(img[cy0:cy1, cx0:cx1], extent=(cx0, cx1, cy1, cy0)); ax3.set_axis_off()
X0p, PXNM, Y0p, PXS = 267.6, 63.4 / 0.2, 719.5, 51.33
xT = lambda t: X0p + t * PXNM; yN = lambda n: Y0p - n / 60.0 * PXS
ax3.add_patch(Rectangle((xT(q05) - 2, yN(600)), xT(q10) - xT(q05) + 2, Y0p - yN(600), fc=BLUE, alpha=0.25, ec="none"))
ax3.plot([xT(0.6)] * 2, [Y0p, yN(600)], "--", color=BLUE, lw=1.3); ax3.text(xT(0.6) + 6, yN(585), "rated 0.6 N m", fontsize=9, color=BLUE, fontweight="bold", va="top")
for Vk in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
    o = ops[Vk]; ax3.plot(xT(o["Qg"]), yN(o["rpm"]), "o", ms=6.5, mfc=BLUE, mec="white", mew=1.2, zorder=5)
ax3.annotate("turbine runs here (0.5-1.0 m/s)", xy=(xT(0.17), yN(140)), xytext=(xT(0.66), yN(48)), fontsize=10, color=BLUE, fontweight="bold", va="center",
             arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=1.2))
fig.text(COLX[2], 0.292, "CubeMars GL60 KV25 @ 24 VDC chart (supplied); lines:", fontsize=8.8, color=MUTE)
rend = fig.canvas.get_renderer(); xk = COLX[2]
for lab, c in (("speed (rpm, axis shown)", "#e07b20"), ("current", "#d64545"), ("efficiency", "#5aa832"), ("output power", "#2b4a9b")):
    t_ = fig.text(xk, 0.272, lab, fontsize=8.8, color=c, fontweight="bold")
    xk += t_.get_window_extent(rend).width / fig.bbox.width + 0.010
checks = [(OK_, "OK", f"speed constant 21.5 rpm/V (516 rpm at 24 V; nameplate 25)"),
          (OK_, "OK", f"torque per amp {mo['Kt_chart'][0]:.2f}-{mo['Kt_chart'][1]:.2f} N m/A, model {mo['Kt_model']:.3f}"),
          (WARN, "RISK", f"no-load draw up to {mo['p0_516_chart']:.1f} W at 516 rpm (model {mo['p0_516_model']:.2f} W);\nif it is all motor drag, 0.7 m/s output falls {mo['P_cases']['model']['0.7']:.2f} -> {mo['P_cases']['RL']['0.7']:.2f} W")]
y = 0.243
for c, tag, txt in checks:
    fig.patches.append(FancyBboxPatch((COLX[2], y - 0.017), 0.040, 0.024, boxstyle="round,pad=0.002,rounding_size=0.005", transform=fig.transFigure, fc=c, ec="none"))
    fig.text(COLX[2] + 0.020, y - 0.005, tag, fontsize=9, color="white", fontweight="bold", ha="center", va="center")
    fig.text(COLX[2] + 0.047, y, txt, fontsize=10, color=INK2, va="top", linespacing=1.3); y -= 0.034 + 0.020 * txt.count("\n")
# ======================= next steps + column separators
for x in (0.343, 0.668):
    fig.lines.append(matplotlib.lines.Line2D([x, x], [0.13, 0.885], transform=fig.transFigure, color="#e2e2e2", lw=1.2))
fig.patches.append(FancyBboxPatch((0.03, 0.025), 0.955, 0.052, boxstyle="round,pad=0.003,rounding_size=0.008", transform=fig.transFigure, fc="#eef6ee", ec="#4f8a5b", lw=1.2))
fig.text(0.045, 0.051, "Next", fontsize=12.5, fontweight="bold", color="#2f6b3e", va="center")
fig.text(0.095, 0.051, "bench-test the GL60 (no-load drag, cogging)   ->   print the rotor   ->   flume test at 0.5-1.0 m/s   ->   refit the model; revisit diameter if motor losses are high",
         fontsize=11.5, color=INK, va="center")
p = os.path.join(OUT, "slide_iteration_review_one_page.png"); fig.savefig(p, dpi=150, facecolor="white"); fig.savefig(p.replace(".png", ".pdf"), facecolor="white")
print("written", p)
