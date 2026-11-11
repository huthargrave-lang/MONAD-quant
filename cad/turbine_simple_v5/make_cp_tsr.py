#!/usr/bin/env python3
"""Rotor power coefficient vs tip-speed ratio for the CURRENT v5 rotor (3-blade NACA 4412, 203.2 mm, 28 mm hub, v5 arrangement "S"),
at 0.5 / 0.7 / 1.0 m/s, from the same BEM model (NeuralFoil Re-dependent polars, Buhl correction) used for every other v5 number.
Marks the Cp peak and the coupled operating point (GL60 + Schottky bridge + buck-boost MPPT) at each speed.
Cp is normalised on the full 203.2 mm disc: Cp = P_shaft / (0.5 rho pi R^2 V^3).
Writes out/slides/chart_v5_cp_tsr.{png,pdf,svg} (SVG text editable) and out/slides/cp_tsr_v5.json (the plotted data)."""
import json, os, re, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); V4 = os.path.abspath(os.path.join(HERE, "..", "turbine_lowflow_v4")); OUT = os.path.join(HERE, "out", "slides")
sys.path.insert(0, os.path.join(V4, "model"))
import coupled_eval as ce, optimize_blades as ob, generator_lowflow as gl, bem_lowflow as bm
ob.ARR["S"] = dict(r_hub=0.028, r_nac=0.039, vfac_nac=0.85, fr="S_simple")
gl.FRICTION["S_simple"] = dict(seal_run=0.006, seal_break=0.012, brg_run=0.003, brg_break=0.004, note="12 mm PTFE lip seal + 6001-2RS (v5)")
spec = json.load(open(os.path.join(V4, "model", "selected_design.json")))["spec"]
VS = (0.5, 0.7, 1.0); LAM = np.round(np.arange(0.1, 5.301, 0.05), 3)
# ---------------------------------------------------------------- data (model)
res = ce.full_eval(spec, "S", vs=list(VS)); bl = ce.make_blade(spec, "S")
D = {}
for V in VS:
    cp = np.array([bm.bem(bl, l, V)["cp"] for l in LAM]); i = int(cp.argmax())
    y0, y1, y2 = cp[i - 1:i + 2]; d = 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2)                       # parabolic refinement of the peak
    lam_pk = float(LAM[i] + d * (LAM[1] - LAM[0])); cp_pk = float(y1 - 0.25 * (y0 - y2) * d)
    op = res["perV"][str(V)]["op"]
    D[str(V)] = dict(lam=LAM.tolist(), cp=cp.tolist(), lam_peak=lam_pk, cp_peak=cp_pk, lam_op=op["lam"], cp_op=float(np.interp(op["lam"], LAM, cp)), Pout_op=op["Pout"])
json.dump(dict(spec=spec, note="BEM model prediction; Cp on the full 203.2 mm disc", curves=D), open(os.path.join(OUT, "cp_tsr_v5.json"), "w"), indent=1)
# ---------------------------------------------------------------- figure
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
plt.rcParams.update({"font.family": "Liberation Sans", "font.size": 12, "svg.fonttype": "none", "pdf.fonttype": 42, "axes.unicode_minus": True})
INK, INK2, MUTE, RULE, GRID, NAVY = "#2b2b2b", "#4a4a4a", "#7a7a7a", "#c9ced6", "#ececec", "#1f3a5f"
STY = {"0.5": ("#7493bb", (0, (2.2, 1.6))), "0.7": ("#3d5f8f", (0, (6, 2.2))), "1.0": ("#14263f", "-")}   # one hue light->dark (speed is ordinal) + line style
fig = plt.figure(figsize=(13.333, 7.5), facecolor="white")
fig.text(0.055, 0.925, "Current v5 rotor: power coefficient vs tip-speed ratio", fontsize=22, fontweight="bold", color=INK)
fig.text(0.055, 0.877, "3 blades, NACA 4412, 203.2 mm diameter, 28 mm hub  ·  BEM model with NeuralFoil polars", fontsize=13.5, color=INK2)
fig.add_artist(Line2D([0.055, 0.965], [0.852, 0.852], color=NAVY, lw=1.4))
ax = fig.add_axes([0.085, 0.135, 0.555, 0.665])
for k, (c, ls) in STY.items():
    d = D[k]; ax.plot(d["lam"], d["cp"], color=c, ls=ls, lw=2.4, zorder=3, solid_capstyle="round")
    ax.plot(d["lam_peak"], d["cp_peak"], "o", ms=9, mfc="white", mec=c, mew=2.0, zorder=5)
    ax.plot(d["lam_op"], d["cp_op"], "o", ms=9, mfc=c, mec="white", mew=1.5, zorder=6)
ax.set_xlim(0, 5.2); ax.set_ylim(0, 0.36); ax.set_xticks(np.arange(0, 5.01, 0.5)); ax.set_yticks(np.arange(0, 0.351, 0.05))
# direct labels: each sits just above or below its own curve, in a spot every other curve, marker and label clears (searched, not hand-placed)
fig.canvas.draw(); rend = fig.canvas.get_renderer(); inv = ax.transData.inverted()
M = 0.009                                                                            # gap to the own curve (Cp units)
pts = [(D[k][a], D[k][b]) for k in D for a, b in (("lam_peak", "cp_peak"), ("lam_op", "cp_op"))]
placed = []
for k in ("1.0", "0.7", "0.5"):
    t = ax.text(0, 0, f"{float(k):.1f} m/s", fontsize=12.5, fontweight="bold", color=INK, ha="center", va="center")
    bb = t.get_window_extent(rend); (x0, y0), (x1, y1) = inv.transform([(bb.x0, bb.y0), (bb.x1, bb.y1)]); w, h = x1 - x0, y1 - y0
    best = None
    for lc in np.arange(1.2, 4.7, 0.02):
        xs = np.linspace(lc - w / 2, lc + w / 2, 25); own = np.interp(xs, D[k]["lam"], D[k]["cp"])
        for mode, (bot, top) in (("above", (own.max() + M, own.max() + M + h)), ("below", (own.min() - M - h, own.min() - M))):
            if bot < 0.005 or top > 0.355: continue
            clear = min(min(np.min(np.where(o >= top, o - top, np.where(o <= bot, bot - o, -1.0))) for o in [np.interp(xs, D[j]["lam"], D[j]["cp"]) for j in D if j != k]), 1.0)
            if clear < 0.012: continue                                             # another curve too close or crossing the label
            if any(lc - w / 2 - 0.05 < px < lc + w / 2 + 0.05 and bot - 0.008 < py < top + 0.008 for px, py in pts): continue
            if any(not (lc + w / 2 < a or lc - w / 2 > b or top < c or bot > e) for a, b, c, e in placed): continue
            score = min(clear, 0.03) - 0.05 * abs(lc - D[k]["lam_peak"])                  # enough clearance, then as near the peak as possible
            if best is None or score > best[0]: best = (score, lc, (bot + top) / 2, bot, top)
    assert best, f"no clear label spot for {k} m/s"
    t.set_position((best[1], best[2])); placed.append((best[1] - w / 2, best[1] + w / 2, best[3], best[4]))
ax.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%.2f"))
ax.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True)
for s in ("top", "right"): ax.spines[s].set_visible(False)
for s in ("left", "bottom"): ax.spines[s].set_color(MUTE)
ax.tick_params(colors=INK2, labelsize=12, length=4)
ax.set_xlabel("Tip-speed ratio  λ = ωR / V", fontsize=14, color=INK, labelpad=8)
ax.set_ylabel("Power coefficient  Cp = P_shaft / (½ρAV³)", fontsize=14, color=INK, labelpad=10)
# ---------------------------------------------------------------- right column: values per speed + marker key + notes
X0 = 0.675; y = 0.775
fig.text(X0, y, "Predicted values", fontsize=14, fontweight="bold", color=INK); y -= 0.06
cols = [(X0 + 0.000, "Water speed", "left"), (X0 + 0.152, "Peak Cp", "right"), (X0 + 0.222, "λ at peak", "right"), (X0 + 0.300, "λ operating", "right")]
for x, h, ha in cols: fig.text(x, y, h, fontsize=11, color=MUTE, ha=ha)
y -= 0.016; fig.add_artist(Line2D([X0, X0 + 0.300], [y, y], color=RULE, lw=0.9)); y -= 0.045
for k, (c, ls) in STY.items():
    d = D[k]
    fig.add_artist(Line2D([X0, X0 + 0.036], [y + 0.009, y + 0.009], color=c, ls=ls, lw=2.4))
    fig.text(X0 + 0.046, y, f"{float(k):.1f} m/s", fontsize=12.5, color=INK)
    fig.text(cols[1][0], y, f"{d['cp_peak']:.2f}", fontsize=12.5, color=INK, ha="right", fontweight="bold")
    fig.text(cols[2][0], y, f"{d['lam_peak']:.1f}", fontsize=12.5, color=INK, ha="right")
    fig.text(cols[3][0], y, f"{d['lam_op']:.1f}", fontsize=12.5, color=INK, ha="right"); y -= 0.05
y += 0.022; fig.add_artist(Line2D([X0, X0 + 0.300], [y, y], color=RULE, lw=0.9)); y -= 0.058
for mk, txt in ((dict(mfc="white", mec=INK2, mew=2.0), "Peak Cp (maximum rotor efficiency)"),
                (dict(mfc=INK2, mec="white", mew=1.5), "Operating point (GL60 + MPPT model)")):
    fig.add_artist(Line2D([X0 + 0.018], [y + 0.010], marker="o", ms=9, ls="none", **mk)); fig.text(X0 + 0.046, y, txt, fontsize=12, color=INK); y -= 0.05
y -= 0.025
NOTES = ["Peak Cp rises with speed: the blade Reynolds",
         "number rises, so section drag falls.",
         "",
         "The operating point sits slightly above the",
         "peak λ: MPPT maximises electrical output, and",
         "lower torque means lower winding loss.",
         "",
         "Cp is referred to the full 203.2 mm disc area."]
for line in NOTES:
    fig.text(X0, y, line, fontsize=11.5, color=INK2); y -= 0.034
fig.text(0.055, 0.035, "Model predictions; experimental validation pending", fontsize=11, color=MUTE)
base = os.path.join(OUT, "chart_v5_cp_tsr")
fig.savefig(base + ".pdf", facecolor="white"); fig.savefig(base + ".png", dpi=150, facecolor="white"); fig.savefig(base + ".svg", facecolor="white")
s = re.sub(r"font-family:\s*'?Liberation Sans'?", "font-family: Arial, 'Liberation Sans', sans-serif", open(base + ".svg").read()); open(base + ".svg", "w").write(s)
for k in D: print(k, "m/s: peak Cp %.3f at lambda %.2f | operating lambda %.2f (Cp %.3f, net %.3f W)" % (D[k]["cp_peak"], D[k]["lam_peak"], D[k]["lam_op"], D[k]["cp_op"], D[k]["Pout_op"]))
print("written", base + ".{pdf,svg,png}")
