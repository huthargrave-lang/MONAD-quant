#!/usr/bin/env python3
"""Slide 5, "Turbine Optimization & Generator Matching": 16:9 engineering slide, vector PDF + SVG (live text) + PNG preview.
  left        predicted net output vs stream velocity, 0.5-1.0 m/s: initial rotor (rev-2, 1-2 m/s design), intermediate (v3.1 drum hub),
              current v5; open markers below each design's predicted self-start speed
  upper right predicted system net output per hydrofoil (v4 sweep: best rotor per section, mean of 0.5-1.0 m/s) with the 2-D L/D (NeuralFoil)
  lower right GL60 KV25: sensitivity of predicted net output to the unverified no-load loss, and the generator parameters with their basis
Data: out/slides/slide_numbers.json (make_slide_diagrams.py), v4 polar cache, and a no-load-loss sweep of the coupled model computed here
(cached in out/slides/noload_sensitivity.json; only the no-load loss is varied, every other input at its baseline)."""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); V4 = os.path.abspath(os.path.join(HERE, "..", "turbine_lowflow_v4")); M = os.path.join(V4, "model")
OUT = os.path.join(HERE, "out", "slides"); N = json.load(open(os.path.join(OUT, "slide_numbers.json"))); T = json.load(open(os.path.join(M, "polars_cache.json")))
# ---------------------------------------------------------------- no-load loss sweep (model; cached)
SENS = os.path.join(OUT, "noload_sensitivity.json")
if not os.path.exists(SENS) or "--recompute" in sys.argv:
    sys.path.insert(0, M)
    import coupled_eval as ce, optimize_blades as ob, generator_lowflow as gl
    ob.ARR["S"] = dict(r_hub=0.028, r_nac=0.039, vfac_nac=0.85, fr="S_simple")
    gl.FRICTION["S_simple"] = dict(seal_run=0.006, seal_break=0.012, brg_run=0.003, brg_break=0.004, note="12 mm PTFE lip seal + 6001-2RS (v5)")
    spec = json.load(open(os.path.join(M, "selected_design.json")))["spec"]; G = dict(gl.GEN)
    p_base = G["p0_700"] * (516 / 700) ** G["p0_exp"]; p_up = N["motor"]["p0_516_chart"]
    grid = sorted(set([round(p_base, 4)] + [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0] + [round(p_up, 4)]))
    rows = []
    for p516 in grid:
        g = dict(G); g["p0_700"] = p516 * (700 / 516) ** G["p0_exp"]
        r = ce.full_eval(spec, "S", gen=g, vs=[0.5, 0.7, 1.0])
        rows.append(dict(p0_516=p516, P={str(V): (r["perV"][str(V)]["op"]["Pout"] if r["perV"][str(V)]["op"] else 0.0) for V in (0.5, 0.7, 1.0)}))
        print("no-load", p516, rows[-1]["P"])
    json.dump(dict(p_base=p_base, p_upper=p_up, rows=rows), open(SENS, "w"), indent=1)
SN = json.load(open(SENS))
# ---------------------------------------------------------------- style
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
plt.rcParams.update({"font.family": "Liberation Sans", "font.size": 12, "svg.fonttype": "none", "pdf.fonttype": 42,
                     "axes.edgecolor": "#8a8a8a", "axes.linewidth": 0.9, "axes.labelcolor": "#2b2b2b", "xtick.color": "#4a4a4a", "ytick.color": "#4a4a4a",
                     "xtick.labelsize": 11.5, "ytick.labelsize": 11.5, "axes.labelsize": 12.5})
INK, INK2, MUTE, RULE, GRID, NAVY = "#2b2b2b", "#4a4a4a", "#7a7a7a", "#c9ced6", "#ececec", "#1f3a5f"
GREY1, GREY2 = "#8a8a8a", "#b4b4b4"
fig = plt.figure(figsize=(16, 9), facecolor="white")
def clean(ax):
    for s_ in ("top", "right"): ax.spines[s_].set_visible(False)
    ax.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True); ax.tick_params(length=3)
def heading(x, y, title, sub):
    fig.text(x, y, title, fontsize=15, fontweight="bold", color=INK, va="baseline")
    fig.text(x, y - 0.030, sub, fontsize=11, color=MUTE, va="baseline")
fig.text(0.045, 0.925, "Turbine Optimization & Generator Matching", fontsize=27, fontweight="bold", color=INK, va="baseline")
fig.lines.append(Line2D([0.045, 0.955], [0.895, 0.895], transform=fig.transFigure, color=NAVY, lw=1.2))
# ================================================================ left: net output vs velocity
heading(0.045, 0.845, "Low-flow refinement raises predicted output at 0.5–0.7 m/s",
        f"Current v5 vs initial rotor: +{(N['it5']['P']['0.6'] - N['it12']['P']['0.6']):.2f} W ({(N['it5']['P']['0.6'] / N['it12']['P']['0.6'] - 1) * 100:.0f} %) at 0.6 m/s; self-start {N['it5']['min_start']} vs {N['it12']['min_start']} m/s")
ax = fig.add_axes([0.075, 0.115, 0.37, 0.64]); clean(ax)
V = np.array([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
series = [("it3", "Intermediate (v3.1, drum hub)", GREY2, (0, (1.5, 2.2)), "s", 2.2),
          ("it12", "Initial rotor (1–2 m/s design)", GREY1, (0, (6, 3)), "^", 2.2),
          ("it5", "Current v5", NAVY, "-", "o", 3.2)]
ends = []
for k, lab, c, ls, mk, lw in series:
    p = np.array([N[k]["P"][f"{v:g}" if f"{v:g}" in N[k]["P"] else str(v)] for v in V]); st = N[k]["min_start"]
    ax.plot(V, p, color=c, lw=lw, ls=ls, zorder=3 if k == "it5" else 2)
    for v, y in zip(V, p):
        filled = v >= st - 1e-9
        ax.plot(v, y, marker=mk, ms=8 if k == "it5" else 7, mfc=(c if filled else "white"), mec=c, mew=1.6, zorder=4)
    ends.append((p[-1], k, lab, c, st))
ax.set_xlim(0.48, 1.02); ax.set_ylim(0, 4.0); ax.set_xticks(V); ax.set_yticks(np.arange(0, 4.01, 0.5))
ax.set_xlabel("Stream velocity (m/s)"); ax.set_ylabel("Predicted net electrical output (W)")
ends.sort(); placed = []
for y, *_ in ends: placed.append(max(y, placed[-1] + 0.36) if placed else y)
for (y, k, lab, c, st), yy in zip(ends, placed):
    ax.annotate(f"{lab}\nself-start {st} m/s", xy=(1.0, y), xytext=(1.035, yy), fontsize=11.5, color=c if k != "it5" else NAVY, va="center",
                fontweight="bold" if k == "it5" else None, annotation_clip=False, linespacing=1.15,
                arrowprops=dict(arrowstyle="-", color=c, lw=0.8, shrinkA=0, shrinkB=4))
ax.text(0.03, 0.97, "Open markers: below predicted self-start speed (manual start)\nAll designs: same GL60 + buck-boost MPPT model",
        transform=ax.transAxes, fontsize=10.5, color=MUTE, va="top", linespacing=1.4)
# ================================================================ upper right: hydrofoil system output
XR = 0.595
heading(XR, 0.845, "NACA 4412 gives the highest predicted system output", "Mean net output over 0.5–1.0 m/s, best rotor per section")
foils = ["naca4412", "naca4415", "sg6043", "fx63137"]; name = {"naca4412": "NACA 4412", "naca4415": "NACA 4415", "sg6043": "SG6043", "fx63137": "FX 63-137"}
J = [N["foil_J"][k]["J_uniform"] for k in foils]; LD = [N["foils"][k]["LD_8e4"] for k in foils]
axf = fig.add_axes([XR + 0.075, 0.585, 0.20, 0.205]); yy = np.arange(len(foils))[::-1]
axf.barh(yy, J, height=0.58, color=[NAVY if k == "naca4412" else "#c4ccd6" for k in foils], zorder=3)
for y, j, k in zip(yy, J, foils): axf.text(j + 0.03, y, f"{j:.2f} W", va="center", fontsize=11.5, color=INK, fontweight="bold" if k == "naca4412" else None)
axf.set_yticks(yy); axf.set_yticklabels([name[k] for k in foils], fontsize=12); axf.set_xlim(0, 1.8); axf.set_xticks([0, 0.5, 1.0, 1.5])
axf.set_xlabel("Predicted net output (W)", fontsize=11.5); clean(axf); axf.grid(True, axis="x", color=GRID); axf.grid(False, axis="y"); axf.tick_params(axis="y", length=0)
# 2-D L/D column aligned with the bars
xc = XR + 0.338
fig.text(xc, 0.800, "2-D L/D", fontsize=11, color=MUTE, ha="center", va="bottom")
fig.text(xc, 0.785, "Re 8×10⁴", fontsize=9.5, color=MUTE, ha="center", va="bottom")
pos = axf.get_position()
for y, ld, k in zip(yy, LD, foils):
    yf = pos.y0 + (y - axf.get_ylim()[0]) / (axf.get_ylim()[1] - axf.get_ylim()[0]) * pos.height
    fig.text(xc, yf, f"{ld:.0f}", fontsize=12, color=INK, ha="center", va="center", fontweight="bold" if ld == max(LD) else None)
fig.text(XR, 0.522, "Airfoil polars: NeuralFoil (XFOIL surrogate), not measured.", fontsize=10, color=MUTE)
# ================================================================ lower right: generator
heading(XR, 0.445, "GL60 KV25: no-load loss is the main open uncertainty",
        "Upper bound: manufacturer no-load current (may include driver draw)")
axs = fig.add_axes([XR + 0.042, 0.115, 0.118, 0.215]); clean(axs)
rows = SN["rows"]; px = np.array([r["p0_516"] for r in rows]); hs = []
for v, c, ls in (("1.0", NAVY, "-"), ("0.7", GREY1, (0, (6, 3))), ("0.5", GREY2, (0, (1.5, 2.2)))):
    base = next(r["P"][v] for r in rows if abs(r["p0_516"] - SN["p_base"]) < 1e-3); d = np.array([(r["P"][v] / base - 1) * 100 for r in rows])
    hs.append(axs.plot(px, d, color=c, ls=ls, lw=2.4 if v == "1.0" else 2.0, label=f"{v} m/s")[0])
axs.axvline(SN["p_base"], color=INK2, lw=0.9); axs.axvline(SN["p_upper"], color=INK2, lw=0.9, ls=(0, (3, 2)))
axs.text(SN["p_base"], 7, "assumed", fontsize=10, color=INK2, ha="center", va="bottom", clip_on=False)
axs.text(SN["p_upper"], 7, "upper bound", fontsize=10, color=INK2, ha="center", va="bottom", clip_on=False)
axs.set_xlim(0, 2.4); axs.set_ylim(-105, 5); axs.set_xticks([0, 0.5, 1.0, 1.5, 2.0]); axs.set_yticks([0, -25, -50, -75, -100])
axs.set_xlabel("No-load loss at 516 rpm (W)", fontsize=11.5); axs.set_ylabel("Change in predicted output (%)", fontsize=11.5)
axs.legend(handles=hs, loc="lower left", fontsize=10, frameon=False, handlelength=2.0, borderaxespad=0.3, labelspacing=0.3)
# parameter groups: manufacturer data / prediction / unverified assumptions
mo = N["motor"]; q = mo["ops"]
groups = [("MANUFACTURER DATA", [("Rated torque", "0.60 N·m"), ("Rated current", "1.35 A"), ("Speed constant", f"{mo['KV_chart']:.1f} rpm/V"),
                                 ("Torque constant", f"{mo['Kt_chart'][0]:.2f}–{mo['Kt_chart'][1]:.2f} N·m/A")]),
          ("PREDICTED, CURRENT V5, 0.5–1.0 m/s", [("Operating torque", f"{q['0.5']['Qg']:.2f}–{q['1.0']['Qg']:.2f} N·m"), ("Share of rated torque", f"{q['0.5']['Qg'] / 0.6 * 100:.0f}–{q['1.0']['Qg'] / 0.6 * 100:.0f} %")]),
          ("ASSUMED, UNVERIFIED", [("No-load loss, 516 rpm", f"{mo['p0_516_model']:.2f} W"), ("Cogging torque", "24 mN·m")])]
xq, xv, y, dy = XR + 0.195, 0.958, 0.362, 0.0262
fig.lines.append(Line2D([xq, xv], [y + 0.012, y + 0.012], transform=fig.transFigure, color=RULE, lw=0.9))
for g, items in groups:
    fig.text(xq, y, g, fontsize=9.5, color=MUTE, va="center", fontweight="bold"); y -= dy
    for a, b in items:
        fig.text(xq, y, a, fontsize=10.8, color=INK, va="center"); fig.text(xv, y, b, fontsize=10.8, color=INK, va="center", ha="right"); y -= dy
    y -= 0.006
fig.lines.append(Line2D([xq, xv], [y + 0.010, y + 0.010], transform=fig.transFigure, color=RULE, lw=0.9))
# ================================================================ footer
fig.text(0.045, 0.030, "Model predictions; experimental validation pending", fontsize=10, color=MUTE)
fig.text(0.955, 0.030, "5", fontsize=10, color=MUTE, ha="right")
base = os.path.join(OUT, "slide5_turbine_optimization_generator_matching")
fig.savefig(base + ".pdf", facecolor="white"); fig.savefig(base + ".png", dpi=150, facecolor="white"); fig.savefig(base + ".svg", facecolor="white")
import re; s = re.sub(r"font-family:\s*'?Liberation Sans'?", "font-family: Arial, 'Liberation Sans', sans-serif", open(base + ".svg").read())
open(base + ".svg", "w").write(s)
print("written", base + ".{pdf,svg,png}")
