#!/usr/bin/env python3
"""Milestone 3 figure for the body of the Google Slides slide "Turbine Optimization and Generator Matching" (no slide title, ~2:1).
  left (~55 %)  predicted net electrical output vs stream velocity, 0.5-1.0 m/s: initial rotor (1-2 m/s design) vs current v5;
                dotted line + open markers below each rotor's predicted self-start speed (needs a manual start), as in the
                iteration-review graphic; self-start points labelled
  upper right   mean predicted net output over 0.5-1.0 m/s per hydrofoil (best rotor per section), NACA 4412 highlighted
  lower right   GL60 KV25 summary, each value tagged with its basis (manufacturer curve / model prediction / unverified)
Data: out/slides/slide_numbers.json (make_slide_diagrams.py) and out/slides/noload_sensitivity.json (make_slide5.py). No values are
typed in by hand except the manufacturer's rated torque (0.60 N·m), which only converts the predicted torque to a share of rated.
Writes out/slides/m3_turbine_optimization_generator_matching.{svg,png,pdf}; the SVG keeps live, editable text."""
import json, os, re
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out", "slides")
N = json.load(open(os.path.join(OUT, "slide_numbers.json"))); SN = json.load(open(os.path.join(OUT, "noload_sensitivity.json")))
RATED_Q = 0.60                                                                    # N·m, CubeMars GL60 KV25 rated torque (manufacturer)
plt.rcParams.update({"font.family": "Liberation Sans", "font.size": 11.5, "svg.fonttype": "none", "pdf.fonttype": 42,
                     "axes.edgecolor": "#8a8a8a", "axes.linewidth": 0.9, "axes.labelcolor": "#2b2b2b", "xtick.color": "#4a4a4a", "ytick.color": "#4a4a4a",
                     "xtick.labelsize": 11, "ytick.labelsize": 11, "axes.labelsize": 12})
INK, INK2, MUTE, GRID, NAVY, GREY, BAR_GREY = "#2b2b2b", "#4a4a4a", "#767676", "#ececec", "#1f3a5f", "#8c8c8c", "#c8c8c8"
fig = plt.figure(figsize=(11, 5.5), facecolor="white")
texts = []                                                                        # every figure-level text, for the overlap check
def T(x, y, s, **kw):
    t = fig.text(x, y, s, **kw); texts.append(t); return t
def heading(x, y, s): return T(x, y, s, fontsize=14, fontweight="bold", color=INK, va="baseline")
# ================================================================ 1  left: low-flow performance
heading(0.035, 0.925, "Low-flow performance")
ax = fig.add_axes([0.083, 0.155, 0.31, 0.715])
for s_ in ("top", "right"): ax.spines[s_].set_visible(False)
ax.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True); ax.tick_params(length=3)
V = np.array([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
K = lambda v: str(float(round(v, 2)))                                          # JSON keys: "0.5" ... "1.0"
def P(k): return np.array([N[k]["P"][K(v)] for v in V])
SER = [("it12", GREY, 2.2, "Initial rotor", "1–2 m/s design", None), ("it5", NAVY, 3.0, "Current v5 rotor", "0.5–1.0 m/s design", "bold")]
for k, c, lw, *_ in SER:
    p = P(k); st = N[k]["min_start"]; on = V >= st - 1e-9; e = int(np.argmax(on))
    ax.plot(V[:e + 1], p[:e + 1], color=c, lw=lw * 0.75, ls=(0, (1.2, 2.0)), dash_capstyle="round", zorder=3)   # below self-start: manual start
    ax.plot(V[on], p[on], color=c, lw=lw, zorder=4, solid_capstyle="round")
    ms = 8.5 if k == "it5" else 7.5
    for v, y, f in zip(V, p, on): ax.plot(v, y, "o", ms=ms, mfc=(c if f else "white"), mec=c, mew=1.6, zorder=5)
ax.set_xlim(0.47, 1.03); ax.set_ylim(0, 4.0); ax.set_xticks(V); ax.set_yticks(np.arange(0, 4.01, 0.5))
ax.set_xlabel("Stream velocity (m/s)", labelpad=6); ax.set_ylabel("Predicted net electrical output (W)", labelpad=8)
# direct series labels at the right end (they double as the legend)
ends = sorted([(P(k)[-1], k, c, a, b, w) for k, c, _, a, b, w in SER]); gap = 0.66; mid = np.mean([e[0] for e in ends])
for i, (y, k, c, a, b, w) in enumerate(ends):
    yy = mid + (i - 0.5) * gap
    t = ax.annotate(f"{a}\n{b}", xy=(1.0, y), xytext=(1.045, yy), color=(NAVY if k == "it5" else INK2), fontsize=11.5, va="center", linespacing=1.25,
                    fontweight=w, annotation_clip=False, arrowprops=dict(arrowstyle="-", color=c, lw=0.9, shrinkA=2, shrinkB=5)); texts.append(t)
# self-start points and the gain at 0.6 m/s
s5, s1 = N["it5"]["min_start"], N["it12"]["min_start"]; p5, p1 = N["it5"]["P"][K(s5)], N["it12"]["P"][K(s5)]
t = ax.annotate(f"Self-starts at {s5:g} m/s\n+{(p5 / p1 - 1) * 100:.0f} % vs initial rotor", xy=(s5, p5), xytext=(0.495, 1.55), fontsize=11.5, color=NAVY, linespacing=1.3,
                va="center", arrowprops=dict(arrowstyle="-", color=NAVY, lw=0.9, shrinkA=3, shrinkB=6)); texts.append(t)
t.set_text(f"Self-starts at {s5:g} m/s\n+{(p5 / p1 - 1) * 100:.0f} % vs initial rotor"); t.set_fontweight("bold")
t2 = ax.annotate(f"Self-starts at {s1:g} m/s", xy=(s1, N["it12"]["P"][K(s1)]), xytext=(0.738, 0.55), fontsize=11.5, color=INK2, va="center",
                 arrowprops=dict(arrowstyle="-", color=GREY, lw=0.9, shrinkA=3, shrinkB=6)); texts.append(t2)
dmax = max(abs(N["it5"]["P"][K(v)] / N["it12"]["P"][K(v)] - 1) for v in (0.8, 0.9, 1.0)) * 100
assert all(N["it5"]["P"][K(v)] < N["it12"]["P"][K(v)] for v in (0.9, 1.0))
texts.append(ax.text(1.045, 2.45, f"At 0.8–1.0 m/s,\nv5 is within {np.ceil(dmax):.0f} %\nof the initial rotor", fontsize=10.5, color=MUTE, va="center", linespacing=1.3, clip_on=False))
# encoding key (top left, inside the empty corner)
kx, ky = 0.495, 3.78
for i, (filled, ls, txt) in enumerate(((True, "-", "Self-starting"), (False, (0, (1.2, 2.0)), "Manual start needed"))):
    y = ky - i * 0.30
    ax.plot([kx, kx + 0.05], [y, y], color=INK2, lw=1.8, ls=ls, dash_capstyle="round", zorder=6)
    ax.plot(kx + 0.025, y, "o", ms=7, mfc=(INK2 if filled else "white"), mec=INK2, mew=1.4, zorder=7)
    texts.append(ax.text(kx + 0.065, y, txt, fontsize=10.5, color=INK2, va="center"))
# ================================================================ 2  upper right: hydrofoil comparison
X = 0.592
heading(X, 0.925, "Hydrofoil comparison")
foils = ["naca4412", "naca4415", "sg6043", "fx63137"]; name = {"naca4412": "NACA 4412", "naca4415": "NACA 4415", "sg6043": "SG6043", "fx63137": "FX 63-137"}
J = [N["foil_J"][k]["J_uniform"] for k in foils]; LD = {k: N["foils"][k]["LD_8e4"] for k in foils}
assert max(LD, key=LD.get) == "sg6043" and max(foils, key=lambda k: N["foil_J"][k]["J_uniform"]) == "naca4412"
axf = fig.add_axes([X + 0.088, 0.625, 0.19, 0.245]); yy = np.arange(len(foils))[::-1]
axf.barh(yy, J, height=0.62, color=[NAVY if k == "naca4412" else BAR_GREY for k in foils], zorder=3)
for y, j, k in zip(yy, J, foils):
    texts.append(axf.text(j + 0.04, y, f"{j:.2f} W", va="center", fontsize=11.5, color=INK, fontweight="bold" if k == "naca4412" else None))
axf.set_yticks(yy); axf.set_yticklabels([name[k] for k in foils], fontsize=11.5); axf.set_xlim(0, 1.75); axf.set_ylim(-0.55, 3.55)
for lab, k in zip(axf.get_yticklabels(), foils):
    lab.set_color(INK); lab.set_fontweight("bold" if k == "naca4412" else "normal")
for s_ in ("top", "right", "bottom"): axf.spines[s_].set_visible(False)
axf.set_xticks([]); axf.tick_params(axis="y", length=0, pad=6)
T(X, 0.575, "Mean predicted net output, 0.5–1.0 m/s", fontsize=10.5, color=MUTE, va="baseline")
T(X, 0.515, f"SG6043: highest 2-D lift-to-drag ratio ({LD['sg6043']:.0f} vs {LD['naca4412']:.0f})", fontsize=11.5, color=INK2, va="baseline")
T(X, 0.472, "NACA 4412 (selected): highest predicted system output", fontsize=11.5, color=INK, va="baseline", fontweight="bold")
# ================================================================ 3  lower right: generator matching
heading(X, 0.375, "Generator matching: CubeMars GL60 KV25")
mo = N["motor"]; q = mo["ops"]
rows = [("Speed constant", f"{mo['KV_chart']:.1f} rpm/V", "manufacturer curve"),
        ("Torque constant", f"{mo['Kt_chart'][0]:.2f}–{mo['Kt_chart'][1]:.2f} N·m/A", "manufacturer curve"),
        ("Operating torque", f"{q['0.5']['Qg'] / RATED_Q * 100:.0f}–{q['1.0']['Qg'] / RATED_Q * 100:.0f} % of rated", "model prediction"),
        ("No-load losses", "not yet measured", "unverified")]
y = 0.312; dy = 0.050; c1, c2 = X + 0.128, X + 0.258
for a, b, s in rows:
    last = a == "No-load losses"
    T(X, y, a, fontsize=11.5, color=INK, va="baseline", fontweight="bold" if last else None)
    T(c1, y, b, fontsize=11.5, color=INK, va="baseline", fontweight="bold" if last else None)
    T(c2, y, s, fontsize=10.5, color=MUTE, va="baseline"); y -= dy
b0 = next(r for r in SN["rows"] if abs(r["p0_516"] - SN["p_base"]) < 1e-3); up = SN["rows"][-1]
d10 = (up["P"]["1.0"] / b0["P"]["1.0"] - 1) * 100; d05 = up["P"]["0.5"]
assert d05 < 1e-6
T(X, y - 0.008, "Main uncertainty: at the upper-bound loss estimate,", fontsize=10.5, color=INK2, va="baseline")
T(X, y - 0.046, f"output falls {abs(d10):.0f} % at 1.0 m/s and to zero at 0.5 m/s.", fontsize=10.5, color=INK2, va="baseline")
# ================================================================ footer
T(0.035, 0.022, "Model predictions; experimental validation pending.", fontsize=10, color=MUTE, va="baseline")
# ================================================================ layout checks: no text overlaps another, nothing outside the margins
fig.canvas.draw(); rend = fig.canvas.get_renderer(); W, H = fig.bbox.width, fig.bbox.height
boxes = [(t.get_text().replace("\n", " ")[:38], matplotlib.text.Text.get_window_extent(t, rend)) for t in texts if t.get_text()]   # text only, not leader lines
for ax_ in (ax, axf):
    for lab in ax_.get_xticklabels() + ax_.get_yticklabels():
        if lab.get_text(): boxes.append((lab.get_text(), lab.get_window_extent(rend)))
    for lab in (ax_.xaxis.label, ax_.yaxis.label):
        if lab.get_text(): boxes.append((lab.get_text(), lab.get_window_extent(rend)))
bad = [(a, b) for i, (a, ba) in enumerate(boxes) for b, bb in boxes[i + 1:] if ba.overlaps(bb) and a != b]
out = [a for a, b_ in boxes if b_.x0 < 0.015 * W or b_.x1 > 0.985 * W or b_.y0 < 0.01 * H or b_.y1 > 0.99 * H]
print("overlapping text:", bad or "none"); print("outside margins:", out or "none")
print("right edge of right column: %.3f, of left section labels: %.3f" % (max(b_.x1 for a, b_ in boxes) / W, max(b_.x1 for a, b_ in boxes if b_.x1 < 0.6 * W) / W))
base = os.path.join(OUT, "m3_turbine_optimization_generator_matching")
fig.savefig(base + ".svg", facecolor="white"); fig.savefig(base + ".pdf", facecolor="white"); fig.savefig(base + ".png", dpi=300, facecolor="white")
s = re.sub(r"font-family:\s*'?Liberation Sans'?", "font-family: Arial, 'Liberation Sans', sans-serif", open(base + ".svg").read()); open(base + ".svg", "w").write(s)
print("written", base + ".{svg,png,pdf}")
