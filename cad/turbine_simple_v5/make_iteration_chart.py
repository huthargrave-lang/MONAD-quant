#!/usr/bin/env python3
"""Standalone iteration power chart (readable version of the slide-2 chart): top = net power vs water speed (log), with direct labels;
bottom = each design's difference from the current v5 design (%), which separates the near-coincident curves.
Reads out/slides/slide_numbers.json (written by make_slide_diagrams.py) and the v4 sweep files for the option cloud."""
import json, math, os
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); M = os.path.abspath(os.path.join(HERE, "..", "turbine_lowflow_v4", "model")); OUT = os.path.join(HERE, "out", "slides")
N = json.load(open(os.path.join(OUT, "slide_numbers.json")))
allS = json.load(open(os.path.join(M, "sweep_stage1.json"))) + json.load(open(os.path.join(M, "sweep_stage2.json")))
VS = sorted(float(v) for v in N["it5"]["P"])
def P(k): return np.array([N[k]["P"][str(V)] for V in VS])
INK, INK2, GRID = "#1a1a1a", "#444444", "#e6e4de"
S = {  # key: (label, colour, linestyle, width, marker)
 "it12": ("1-2  rev-2 blade + GL60 (29-31 Oct)", "#b8860b", ":", 2.4, "^"),
 "it3":  ("3  v3.1 drum, 48 mm hub (31 Oct)", "#b84a3a", "--", 2.4, "s"),
 "it4a": ("4  first pick, TSR 2.0 x1.3 (2 Nov)", "#7fa6d6", "-.", 1.9, "D"),
 "it4b": ("4  final v4, TSR 1.5 -3 deg (2 Nov)", "#3d6fa8", "--", 1.9, "v"),
 "it5":  ("5  v5 prototype, current (3 Nov)", "#14365c", "-", 3.4, "o"),
}
fig, (ax, axr) = plt.subplots(2, 1, figsize=(15, 8.8), sharex=True, gridspec_kw=dict(height_ratios=[2.3, 1.0], hspace=0.07), facecolor="white")
fig.subplots_adjust(left=0.065, right=0.735, top=0.93, bottom=0.08)
for a in (ax, axr):
    a.axvspan(1.0, 2.0, color="#f6ead6", alpha=0.7, lw=0); a.axvspan(0.5, 1.0, color="#dce6f2", alpha=0.8, lw=0)
    a.grid(True, which="both", color=GRID, lw=0.6); a.set_axisbelow(True)
ax.text(0.75, 36, "target, iterations 4-5", ha="center", fontsize=11, color="#1f4e79", fontweight="bold")
ax.text(1.4, 36, "design target, iterations 1-3", ha="center", fontsize=11, color="#8a6510", fontweight="bold")
vc = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
for r in allS: ax.plot(vc, [r["perV"][str(V)]["Pout"] for V in vc], color="#a7b2bf", lw=0.4, alpha=0.06, zorder=1)
ax.text(0.97, 0.62, f"iteration 4 options\n({len(allS)} rotors)", fontsize=9.5, color="#7d8996", ha="right", va="center", style="italic")
for k, (lab, c, ls, lw, mk) in S.items():
    ax.plot(VS, P(k), ls, color=c, lw=lw, marker=mk, ms=5 if k != "it5" else 5.5, mfc="white" if k != "it5" else c, mew=1.3, zorder=5 if k == "it5" else 4)
ax.set_yscale("log"); ax.set_ylim(0.05, 50); ax.set_xlim(0.4, 2.0); ax.set_ylabel("net 12 V electrical power (W)", fontsize=11.5)
# direct labels at the right edge, spread so they do not collide (log space)
ends = sorted(((math.log10(P(k)[-1]), k) for k in S), key=lambda t: t[0]); placed = []; gap = 0.115
for y, k in ends:
    yy = max(y, placed[-1] + gap) if placed else y; placed.append(yy)
shift = max(0.0, placed[-1] - math.log10(48)); placed = [p - shift for p in placed]
for (y, k), yy in zip(ends, placed):
    lab, c = S[k][0], S[k][1]
    ax.annotate(f"{lab}: {P(k)[-1]:.1f} W at 2 m/s", xy=(2.0, 10 ** y), xytext=(2.04, 10 ** yy), textcoords="data", fontsize=10, color=c, fontweight="bold" if k == "it5" else None,
                va="center", annotation_clip=False, arrowprops=dict(arrowstyle="-", color=c, lw=0.8, shrinkA=0, shrinkB=2))
ax.set_title("Net power of each whole-turbine design across the iterations (model; all re-evaluated on one basis)", loc="left", fontsize=13, fontweight="bold", color=INK)
# relative panel
base = P("it5"); m = base > 0
axr.axhline(0, color=S["it5"][1], lw=S["it5"][3]); axr.text(1.05, -5, "current v5 design = 0", fontsize=9.5, color=S["it5"][1], va="top", fontweight="bold")
rel_end = []
for k in ("it12", "it3", "it4a", "it4b"):
    lab, c, ls, lw, mk = S[k]; d = (P(k)[m] / base[m] - 1) * 100
    axr.plot(np.array(VS)[m], d, ls, color=c, lw=lw, marker=mk, ms=5, mfc="white", mew=1.3); rel_end.append((d[-1], k))
rel_end.sort(); placed = []
for y, k in rel_end:
    yy = max(y, placed[-1] + 11) if placed else y; placed.append(yy)
for (y, k), yy in zip(rel_end, placed):
    c = S[k][1]; short = S[k][0].split(" (")[0]
    axr.annotate(f"{short}: {y:+.0f} %", xy=(2.0, y), xytext=(2.04, yy), fontsize=9.5, color=c, va="center", annotation_clip=False, arrowprops=dict(arrowstyle="-", color=c, lw=0.8, shrinkA=0, shrinkB=2))
axr.set_ylim(-105, 30); axr.set_yticks([-100, -75, -50, -25, 0, 25]); axr.set_ylabel("difference from\ncurrent design (%)", fontsize=11)
axr.set_xlabel("water speed (m/s)", fontsize=11.5)
axr.text(1.05, -90, "below zero = less power than the current design", fontsize=9.5, color=INK2, style="italic", va="bottom")
p = os.path.join(OUT, "chart_iteration_power.png"); fig.savefig(p, dpi=170, facecolor="white"); fig.savefig(p.replace(".png", ".pdf"), facecolor="white")
print("written", p)
