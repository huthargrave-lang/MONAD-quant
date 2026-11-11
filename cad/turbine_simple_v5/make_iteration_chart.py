#!/usr/bin/env python3
"""Standalone iteration power chart: net power vs water speed for each whole-turbine design, linear axes with plain numbers, a key,
and a zoomed inset of the 0.5-1.0 m/s target band (where the curves bunch on the full scale).
Reads out/slides/slide_numbers.json (written by make_slide_diagrams.py) and the v4 sweep files for the option cloud."""
import json, os
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); M = os.path.abspath(os.path.join(HERE, "..", "turbine_lowflow_v4", "model")); OUT = os.path.join(HERE, "out", "slides")
N = json.load(open(os.path.join(OUT, "slide_numbers.json")))
allS = json.load(open(os.path.join(M, "sweep_stage1.json"))) + json.load(open(os.path.join(M, "sweep_stage2.json")))
VS = sorted(float(v) for v in N["it5"]["P"])
def P(k): return np.array([N[k]["P"][str(V)] for V in VS])
INK, GRID = "#1a1a1a", "#e6e4de"
S = {  # key: (label, colour, linestyle, width, marker)
 "it12": ("1-2  rev-2 blade + GL60 (29-31 Oct)", "#b8860b", ":", 2.6, "^"),
 "it3":  ("3  v3.1 drum, 48 mm hub (31 Oct)", "#b84a3a", "--", 2.4, "s"),
 "it4a": ("4  first pick, TSR 2.0 x1.3 (2 Nov)", "#7fa6d6", "-.", 2.0, "D"),
 "it4b": ("4  final v4, TSR 1.5, -3 deg (2 Nov)", "#3d6fa8", "--", 2.0, "v"),
 "it5":  ("5  v5 prototype, current (3 Nov)", "#14365c", "-", 3.4, "o"),
}
def draw(a, ms=5.5):
    for k, (lab, c, ls, lw, mk) in S.items():
        a.plot(VS, P(k), ls, color=c, lw=lw, marker=mk, ms=ms, mfc="white" if k != "it5" else c, mew=1.3, label=lab, zorder=5 if k == "it5" else 4)
fig, ax = plt.subplots(figsize=(15, 8.5), facecolor="white"); fig.subplots_adjust(left=0.06, right=0.98, top=0.92, bottom=0.08)
ax.axvspan(1.0, 2.0, color="#f6ead6", alpha=0.7, lw=0); ax.axvspan(0.5, 1.0, color="#dce6f2", alpha=0.8, lw=0)
ax.text(0.75, 33.2, "target, iterations 4-5", ha="center", fontsize=11.5, color="#1f4e79", fontweight="bold")
ax.text(1.5, 33.2, "design target, iterations 1-3", ha="center", fontsize=11.5, color="#8a6510", fontweight="bold")
draw(ax)
ax.set_xlim(0.4, 2.0); ax.set_ylim(0, 35); ax.set_yticks(range(0, 36, 5)); ax.set_xticks(np.arange(0.4, 2.01, 0.2))
ax.grid(True, color=GRID, lw=0.7); ax.set_axisbelow(True)
ax.set_xlabel("water speed (m/s)", fontsize=12); ax.set_ylabel("net 12 V electrical power (W)", fontsize=12)
ax.set_title("Net power of each whole-turbine design across the iterations (model; all re-evaluated on one basis)", loc="left", fontsize=13.5, fontweight="bold", color=INK)
ax.plot([], [], color="#a7b2bf", lw=2.5, alpha=0.6, label=f"iteration 4 options ({len(allS)} rotors, inset only)")
ax.legend(loc="lower right", fontsize=10.5, title="Key", title_fontsize=11, frameon=True, framealpha=0.97, edgecolor="#cccccc", bbox_to_anchor=(0.995, 0.015))
# zoomed inset of the target band
axi = ax.inset_axes([0.045, 0.30, 0.43, 0.60])
axi.set_facecolor("#eef3f9")
vc = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
for r in allS: axi.plot(vc, [r["perV"][str(V)]["Pout"] for V in vc], color="#a7b2bf", lw=0.4, alpha=0.045, zorder=1)
draw(axi, ms=6)
axi.set_xlim(0.48, 1.02); axi.set_ylim(0, 3.9); axi.set_xticks([0.5, 0.6, 0.7, 0.8, 0.9, 1.0]); axi.set_yticks([0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5])
axi.grid(True, color="#d9dee6", lw=0.6); axi.tick_params(labelsize=9.5)
axi.set_title("zoom: 0.5-1.0 m/s target band (W)", loc="left", fontsize=10.5, fontweight="bold", color="#1f4e79")
for sp in axi.spines.values(): sp.set_edgecolor("#1f4e79"); sp.set_linewidth(1.2)
ind = ax.indicate_inset_zoom(axi, edgecolor="#1f4e79", alpha=0.6, lw=1.0)
conns = ind.connectors if hasattr(ind, "connectors") else ind[1]
for cn in conns: cn.set_visible(False)                          # keep only the outline of the zoomed region
p = os.path.join(OUT, "chart_iteration_power.png"); fig.savefig(p, dpi=170, facecolor="white"); fig.savefig(p.replace(".png", ".pdf"), facecolor="white")
print("written", p)
