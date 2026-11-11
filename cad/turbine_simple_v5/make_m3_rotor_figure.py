#!/usr/bin/env python3
"""Milestone 3 body figure (no title, 2:1) for the slide "Turbine Optimization and Generator Matching":
  left    predicted mean net power per hydrofoil, 0.5-1.0 m/s (best rotor per section), NACA 4412 highlighted
  right   rendering of the final v5 rotor from its own mesh (out/v5_rotor_PRINT.stl, written by make_v5.py)
  bottom  three predicted results: gain at 0.6 m/s vs the initial rotor, self-start velocity, output at 0.7 m/s
          + one technical note (modeled generator, unverified no-load losses)
Numbers: out/slides/slide_numbers.json (make_slide_diagrams.py).  Rotor image: out/slides/v5_rotor_render.png, rendered by
render/render_rotor.sh (three.js in headless Chromium; geometry only re-centred on its axis, never modified).
Writes out/slides/m3_rotor_hydrofoil_results.{png,svg,pdf}."""
import json, os, re
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out", "slides")
N = json.load(open(os.path.join(OUT, "slide_numbers.json"))); IMG = os.path.join(OUT, "v5_rotor_render.png")
plt.rcParams.update({"font.family": "Liberation Sans", "svg.fonttype": "none", "pdf.fonttype": 42})
INK, INK2, MUTE, RULE, NAVY, BAR_GREY = "#2b2b2b", "#4a4a4a", "#767676", "#d5d8dc", "#1f3a5f", "#c9cdd2"
# ---------------------------------------------------------------- numbers (all from the model results file)
P5, P1 = N["it5"]["P"], N["it12"]["P"]
gain06 = (P5["0.6"] / P1["0.6"] - 1) * 100; v_start = N["it5"]["min_start"]; p07 = P5["0.7"]
foils = ["naca4412", "naca4415", "sg6043", "fx63137"]; name = {"naca4412": "NACA 4412", "naca4415": "NACA 4415", "sg6043": "SG6043", "fx63137": "FX 63-137"}
J = [N["foil_J"][k]["J_uniform"] for k in foils]
assert f"{gain06:.0f}" == "28" and v_start == 0.6 and f"{p07:.2f}" == "0.93" and [f"{j:.2f}" for j in J] == ["1.51", "1.43", "1.36", "1.34"]
fig = plt.figure(figsize=(12, 6), facecolor="white")
# ---------------------------------------------------------------- left: hydrofoil comparison
fig.text(0.045, 0.880, "Hydrofoil comparison", fontsize=16, fontweight="bold", color=INK, va="baseline")
fig.text(0.045, 0.837, "Predicted net power, mean of 0.5–1.0 m/s", fontsize=12, color=MUTE, va="baseline")
axb = fig.add_axes([0.150, 0.390, 0.215, 0.385]); y = np.arange(len(foils))[::-1]
axb.barh(y, J, height=0.64, color=[NAVY if k == "naca4412" else BAR_GREY for k in foils], zorder=3)
for yi, j, k in zip(y, J, foils):
    axb.text(j + 0.05, yi, f"{j:.2f} W", va="center", fontsize=14, color=INK, fontweight="bold" if k == "naca4412" else "normal")
axb.set_yticks(y); axb.set_yticklabels([name[k] for k in foils], fontsize=14)
for lab, k in zip(axb.get_yticklabels(), foils): lab.set_color(INK); lab.set_fontweight("bold" if k == "naca4412" else "normal")
axb.set_xlim(0, 1.75); axb.set_ylim(-0.6, 3.6); axb.set_xticks([])
for s in ("top", "right", "bottom"): axb.spines[s].set_visible(False)
axb.spines["left"].set_color("#9a9a9a"); axb.tick_params(axis="y", length=0, pad=8)
# ---------------------------------------------------------------- right: the rotor
im = Image.open(IMG); ar = im.width / im.height
axr = fig.add_axes([0.50, 0.262, 0.46, 0.705]); axr.imshow(np.asarray(im), interpolation="lanczos"); axr.set_axis_off()
axr.set_xlim(-0.5 * (axr.get_position().width * 12 / (axr.get_position().height * 6) * im.height - im.width), im.width + 0.5 * (axr.get_position().width * 12 / (axr.get_position().height * 6) * im.height - im.width))
XC = 0.475                                                                            # right-column caption, aligned with the left heading
fig.text(XC, 0.880, "Final v5 rotor", fontsize=16, fontweight="bold", color=INK, va="baseline")
fig.canvas.draw(); rend0 = fig.canvas.get_renderer(); x = XC
for part, c, w in (("3 blades", MUTE, "normal"), ("·", MUTE, "normal"), ("NACA 4412", NAVY, "bold"), ("·", MUTE, "normal"), ("Ø 203.2 mm", MUTE, "normal")):
    t = fig.text(x, 0.837, part, fontsize=12, color=c, fontweight=w, va="baseline"); x = t.get_window_extent(rend0).x1 / fig.bbox.width + 0.009   # no edge spaces: SVG collapses them
# ---------------------------------------------------------------- bottom: three predicted results
fig.add_artist(plt.Line2D([0.045, 0.955], [0.235, 0.235], color=RULE, lw=1.0))
K = [(f"+{gain06:.0f} %", "predicted power at 0.6 m/s", "vs initial rotor"),
     (f"{v_start:.1f} m/s", "predicted self-start", "velocity"),
     (f"{p07:.2f} W", "predicted output", "at 0.7 m/s")]
fig.canvas.draw(); rend0 = fig.canvas.get_renderer(); WF = fig.bbox.width; GAPI = 0.014        # number-to-label gap
def wid(t): return t.get_window_extent(rend0).width / WF
groups = []
for big, l1, l2 in K:
    tb = fig.text(0, 0.118, big, fontsize=31, fontweight="bold", color=NAVY, va="baseline")
    ta = fig.text(0, 0.150, l1, fontsize=12.5, color=INK, va="baseline"); tc = fig.text(0, 0.115, l2, fontsize=12.5, color=INK, va="baseline")
    groups.append((tb, ta, tc, wid(tb) + GAPI + max(wid(ta), wid(tc))))
gap = (0.955 - 0.045 - sum(g[3] for g in groups)) / (len(groups) - 1); x = 0.045           # equal gaps, flush to both margins
for tb, ta, tc, w in groups:
    tb.set_x(x); ta.set_x(x + wid(tb) + GAPI); tc.set_x(x + wid(tb) + GAPI); x += w + gap
fig.text(0.045, 0.035, "All values are model predictions (BEM rotor model, NeuralFoil polars), not yet experimentally verified.  Modeled generator: CubeMars GL60 KV25; no-load losses unverified.",
         fontsize=10, color=MUTE, va="baseline")
# ---------------------------------------------------------------- checks + export
fig.canvas.draw(); rend = fig.canvas.get_renderer(); Wp, Hp = fig.bbox.width, fig.bbox.height
tx = [t for t in fig.texts] + list(axb.texts) + [l for l in axb.get_yticklabels() if l.get_text()]
bx = [(t.get_text()[:30], t.get_window_extent(rend)) for t in tx]
CAP = {"3 blades", "·", "NACA 4412", "Ø 203.2 mm"}                                   # caption pieces abut by design
print("overlaps:", [(a, b) for i, (a, p) in enumerate(bx) for b, q in bx[i + 1:] if p.overlaps(q) and not (a in CAP and b in CAP)] or "none")
print("outside margins:", [a for a, p in bx if p.x0 < 0.02 * Wp or p.x1 > 0.98 * Wp or p.y0 < 0.01 * Hp or p.y1 > 0.99 * Hp] or "none")
A = np.asarray(im)[:, :, 3]; hit = []
for a, p in bx:
    (u0, v0), (u1, v1) = axr.transData.inverted().transform([(p.x0, p.y0), (p.x1, p.y1)])
    i0, i1 = int(max(0, min(v0, v1))), int(min(A.shape[0], max(v0, v1))); j0, j1 = int(max(0, u0)), int(min(A.shape[1], u1))
    if i1 > i0 and j1 > j0 and (A[i0:i1, j0:j1] > 8).any(): hit.append(a)
print("text over the rotor:", hit or "none")
rb = axr.get_window_extent(rend); print("rotor image area: %.2f x %.2f in" % (min(rb.width, rb.height * ar) / fig.dpi, rb.height / fig.dpi))
base = os.path.join(OUT, "m3_rotor_hydrofoil_results")
fig.savefig(base + ".png", dpi=300, facecolor="white"); fig.savefig(base + ".pdf", facecolor="white", dpi=300); fig.savefig(base + ".svg", facecolor="white", dpi=300)
s = re.sub(r"font-family:\s*'?Liberation Sans'?", "font-family: Arial, 'Liberation Sans', sans-serif", open(base + ".svg").read()); open(base + ".svg", "w").write(s)
print("written", base + ".{png,svg,pdf}")
