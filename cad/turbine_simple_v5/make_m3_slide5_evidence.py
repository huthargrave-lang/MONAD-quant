#!/usr/bin/env python3
"""Slide 5 (Milestone 3) evidence figure, placed under the slide title "Turbine Optimization and Generator Matching"; no title of its own.
  left  (~60 %)  predicted net electrical output vs stream velocity, 0.5-1.0 m/s: initial rotor (1-2 m/s design, gray) vs current
                 v5 (navy); dotted line + open markers below each rotor's predicted self-start speed, solid + filled at and above it
  right (~40 %)  predicted mean net output over 0.5-1.0 m/s per hydrofoil, NACA 4412 highlighted, one note on 2-D L/D
Data: out/slides/slide_numbers.json (make_slide_diagrams.py; the same file behind every earlier slide). Nothing is typed in by hand.
Writes out/slides/m3_slide5_evidence.{png,svg,pdf}; the SVG keeps editable text."""
import json, os, re
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out", "slides")
N = json.load(open(os.path.join(OUT, "slide_numbers.json")))
plt.rcParams.update({"font.family": "Liberation Sans", "font.size": 13, "svg.fonttype": "none", "pdf.fonttype": 42,
                     "axes.edgecolor": "#8a8a8a", "axes.linewidth": 1.0, "axes.labelcolor": "#2b2b2b", "xtick.color": "#3a3a3a", "ytick.color": "#3a3a3a",
                     "xtick.labelsize": 13, "ytick.labelsize": 13, "axes.labelsize": 14})
INK, INK2, MUTE, GRID, NAVY, GREY, BAR_GREY = "#2b2b2b", "#4a4a4a", "#6e6e6e", "#e9e9e9", "#1f3a5f", "#8f8f8f", "#c9cdd2"
fig = plt.figure(figsize=(11, 5.5), facecolor="white")
# ================================================================ left: output vs stream velocity
ax = fig.add_axes([0.085, 0.185, 0.47, 0.775])
for s in ("top", "right"): ax.spines[s].set_visible(False)
ax.grid(True, color=GRID, lw=0.9); ax.set_axisbelow(True); ax.tick_params(length=4)
V = np.array([0.5, 0.6, 0.7, 0.8, 0.9, 1.0]); K = lambda v: str(float(round(v, 2)))
DOT = (0, (1.2, 2.2))
for k, c, lw, ms in (("it12", GREY, 2.4, 8), ("it5", NAVY, 3.0, 9)):
    p = np.array([N[k]["P"][K(v)] for v in V]); on = V >= N[k]["min_start"] - 1e-9; e = int(np.argmax(on))
    ax.plot(V[:e + 1], p[:e + 1], color=c, lw=lw * 0.8, ls=DOT, dash_capstyle="round", zorder=3)   # below predicted self-start
    ax.plot(V[on], p[on], color=c, lw=lw, solid_capstyle="round", zorder=4)
    for v, y, f in zip(V, p, on): ax.plot(v, y, "o", ms=ms, mfc=(c if f else "white"), mec=c, mew=1.8, zorder=5)
ax.set_xlim(0.47, 1.03); ax.set_ylim(0, 4.0); ax.set_xticks(V); ax.set_yticks(np.arange(0, 4.01, 0.5))
ax.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%.1f"))
ax.set_xlabel("Stream velocity (m/s)", labelpad=8); ax.set_ylabel("Predicted net electrical output (W)", labelpad=10)
H = [Line2D([], [], color=NAVY, lw=3.0, marker="o", ms=8, mfc=NAVY, mec=NAVY, label="Current v5 rotor (0.5–1.0 m/s design)"),
     Line2D([], [], color=GREY, lw=2.4, marker="o", ms=7.5, mfc=GREY, mec=GREY, label="Initial rotor (1–2 m/s design)"),
     Line2D([], [], color=INK2, lw=2.0, ls=DOT, marker="o", ms=7.5, mfc="white", mec=INK2, mew=1.6, label="Below predicted self-start speed")]
leg = ax.legend(handles=H, loc="upper left", bbox_to_anchor=(0.0, 1.0), fontsize=12, frameon=False, handlelength=2.6, handletextpad=0.7, labelspacing=0.55, borderaxespad=0.4)
for t in leg.get_texts(): t.set_color(INK)
# ================================================================ right: hydrofoil comparison
XR = 0.655
foils = ["naca4412", "naca4415", "sg6043", "fx63137"]; name = {"naca4412": "NACA 4412", "naca4415": "NACA 4415", "sg6043": "SG6043", "fx63137": "FX 63-137"}
J = [N["foil_J"][k]["J_uniform"] for k in foils]; LD = {k: N["foils"][k]["LD_8e4"] for k in foils}
assert max(foils, key=lambda k: N["foil_J"][k]["J_uniform"]) == "naca4412" and max(LD, key=LD.get) == "sg6043"
fig.text(XR, 0.900, "Predicted mean electrical output", fontsize=14, color=INK, va="baseline")
fig.text(XR, 0.855, "0.5–1.0 m/s, by hydrofoil section", fontsize=12.5, color=MUTE, va="baseline")
axb = fig.add_axes([XR + 0.098, 0.355, 0.155, 0.445]); yy = np.arange(len(foils))[::-1]
axb.barh(yy, J, height=0.62, color=[NAVY if k == "naca4412" else BAR_GREY for k in foils], zorder=3)
for y, j, k in zip(yy, J, foils):
    axb.text(j + 0.05, y, f"{j:.2f} W", va="center", fontsize=14, color=INK, fontweight="bold" if k == "naca4412" else "normal")
axb.set_yticks(yy); axb.set_yticklabels([name[k] for k in foils], fontsize=14)
for lab, k in zip(axb.get_yticklabels(), foils): lab.set_color(INK); lab.set_fontweight("bold" if k == "naca4412" else "normal")
axb.set_xlim(0, 1.6); axb.set_ylim(-0.6, 3.6); axb.set_xticks([])
for s in ("top", "right", "bottom"): axb.spines[s].set_visible(False)
axb.tick_params(axis="y", length=0, pad=8)
fig.text(XR, 0.270, "SG6043: higher 2-D lift-to-drag than NACA 4412", fontsize=12, color=INK2, va="baseline")
fig.text(XR, 0.228, f"({LD['sg6043']:.0f} vs {LD['naca4412']:.0f}) but lower predicted output.", fontsize=12, color=INK2, va="baseline")
# ================================================================ footer
fig.text(0.02, 0.020, "Model predictions; experimental validation pending.", fontsize=10.5, color=MUTE, va="baseline")
# ================================================================ checks + export
fig.canvas.draw(); rend = fig.canvas.get_renderer(); Wp, Hp = fig.bbox.width, fig.bbox.height
items = [(t.get_text()[:34], t.get_window_extent(rend)) for t in list(fig.texts) + list(axb.texts) + list(leg.get_texts())]
for a_ in (ax, axb):
    items += [(l.get_text(), l.get_window_extent(rend)) for l in a_.get_xticklabels() + a_.get_yticklabels() + [a_.xaxis.label, a_.yaxis.label] if l.get_text()]
print("text overlaps:", [(a, b) for i, (a, p) in enumerate(items) for b, q in items[i + 1:] if p.overlaps(q)] or "none")
print("outside margins:", [a for a, p in items if p.x0 < 0.012 * Wp or p.x1 > 0.988 * Wp or p.y0 < 0.008 * Hp or p.y1 > 0.992 * Hp] or "none")
lb = leg.get_window_extent(rend); inv = ax.transData.inverted(); (lx0, ly0), (lx1, ly1) = inv.transform([(lb.x0, lb.y0), (lb.x1, lb.y1)])
clash = [(k, v) for k in ("it5", "it12") for v in V if lx0 - 0.02 <= v <= lx1 + 0.02 and N[k]["P"][K(v)] >= ly0 - 0.08]
print("legend over data:", clash or "none")
base = os.path.join(OUT, "m3_slide5_evidence")
fig.savefig(base + ".png", dpi=300, facecolor="white"); fig.savefig(base + ".pdf", facecolor="white"); fig.savefig(base + ".svg", facecolor="white")
s = re.sub(r"font-family:\s*'?Liberation Sans'?", "font-family: Arial, 'Liberation Sans', sans-serif", open(base + ".svg").read()); open(base + ".svg", "w").write(s)
print("written", base + ".{png,svg,pdf}")
