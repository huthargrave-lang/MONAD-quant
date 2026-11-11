#!/usr/bin/env python3
"""Three 16:9 slide diagrams (PNG + one PDF) for the iteration review:
  1  hydrofoil selection (7 open-source UIUC sections, NeuralFoil polars, selection criteria, 2-D vs system ranking)
  2  design iterations over time (dated cards from the git history + net power of each whole-turbine design, re-evaluated with
     today's coupled model on one basis; the v4 option cloud; next steps)
  3  generator: the CubeMars GL60 KV25 @ 24 VDC curve (manufacturer image supplied by the user, digitized) with the turbine's
     operating window overlaid, a constants check, and the effect of the chart-implied losses on net output.
Every number is computed here or read from the result files; out/slides/slide_numbers.json records them."""
import json, math, os, sys, textwrap
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); V4 = os.path.abspath(os.path.join(HERE, "..", "turbine_lowflow_v4")); M = os.path.join(V4, "model")
OUT = os.path.join(HERE, "out", "slides"); os.makedirs(OUT, exist_ok=True)
CHART_IMG = sys.argv[1] if len(sys.argv) > 1 else None             # the user's GL60 chart (PNG); digitized curves in sys.argv[2]
CHART_DIG = sys.argv[2] if len(sys.argv) > 2 else None
sys.path.insert(0, M)
import coupled_eval as ce, optimize_blades as ob, generator_lowflow as gl, bem_lowflow as bm
ob.ARR["S"] = dict(r_hub=0.028, r_nac=0.039, vfac_nac=0.85, fr="S_simple")
gl.FRICTION["S_simple"] = dict(seal_run=0.006, seal_break=0.012, brg_run=0.003, brg_break=0.004, note="12 mm PTFE lip seal + 6001-2RS (v5)")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, FancyArrowPatch
from matplotlib.backends.backend_pdf import PdfPages
from PIL import Image
INK, INK2, MUTE, GRID, BG = "#1a1a1a", "#444444", "#777777", "#e6e4de", "white"
plt.rcParams.update({"font.size": 11, "axes.edgecolor": "#888888", "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2})
T = json.load(open(os.path.join(M, "polars_cache.json"))); S1 = json.load(open(os.path.join(M, "sweep_stage1.json"))); S2 = json.load(open(os.path.join(M, "sweep_stage2.json")))
SEL = json.load(open(os.path.join(M, "selection.json"))); sel = json.load(open(os.path.join(M, "selected_design.json"))); spec = sel["spec"]; allS = S1 + S2
VS = ce.VS_ALL; NUM = {}
def P(r, V): o = r["perV"][str(V)]["op"]; return o["Pout"] if o else 0.0
# ======================================================================== evaluations on one basis
orig, v31 = ce.previous_designs()
first = next(r["spec"] for r in S1 if r["spec"]["B"] == 3 and r["spec"]["airfoil"] == "naca4412" and r["spec"]["lam_d"] == 2.0 and r["spec"].get("c_scale") == 1.3)
EV = {"it12": ce.full_eval(orig, "A"), "it3": ce.full_eval(v31, "B"), "it4a": ce.full_eval(first, "A"), "it4b": ce.full_eval(spec, "A"), "it5": ce.full_eval(spec, "S")}
for k, r in EV.items():
    s, u = ce.min_flows(r); NUM[k] = dict(P={str(V): P(r, V) for V in VS}, min_start=s, min_sustain=u)
print("evaluated:", {k: (round(v["P"]["0.7"], 2), round(v["P"]["1.5"], 2), v["min_start"]) for k, v in NUM.items()})
# ======================================================================== SLIDE 1: hydrofoil selection
names = {"naca4412": "NACA 4412", "naca4415": "NACA 4415", "naca4418": "NACA 4418", "sg6043": "SG6043", "fx63137": "FX 63-137", "e387": "Eppler E387", "e818": "Eppler E818"}
order = ["naca4412", "naca4415", "sg6043", "fx63137", "naca4418", "e387", "e818"]
col = {"naca4412": "#1f4e79", "naca4415": "#6f9bc8", "sg6043": "#c8692b", "fx63137": "#8e5aa8", "naca4418": "#4f8a5b", "e387": "#9a9a9a", "e818": "#bdbdbd"}
def status(k):
    if k == "naca4412": return "SELECTED", "#1f4e79", "white"
    if k == "naca4418": return "root section", "#4f8a5b", "white"
    if T[k]["selectable"]: return "searched", "#dce6f2", INK
    return "excluded", "#e4e4e4", INK2
best_af = {k: max((r for r in allS if r["spec"]["airfoil"] == k), key=lambda r: r["J"]["uniform"]) for k in ("naca4412", "naca4415", "sg6043", "fx63137")}
Res = T["naca4412"]["Res"]; i8 = Res.index(80000.0); i4 = Res.index(40000.0)
def Re_at(frac, V, r):
    rr = 0.028 + frac * (bm.R_TIP - 0.028); c = float(np.interp(rr * 1000, sel["r_mm"], sel["chord_mm"])) / 1000
    o = r["perV"][str(V)]["op"]; lam = o["lam"] if o else 3.0; return V * math.sqrt(1 + (lam * rr / bm.R_TIP) ** 2) * c / 1e-6
Re_lo, Re_hi = Re_at(0.3, 0.5, EV["it5"]), Re_at(0.7, 1.0, EV["it5"])
NUM["foils"] = {k: dict(tc=T[k]["tc"], conf=T[k]["conf_mean"], LD_4e4=T[k]["best_ld"][i4], LD_8e4=T[k]["best_ld"][i8], selectable=T[k]["selectable"]) for k in order}
NUM["foil_J"] = {k: dict(J_uniform=v["J"]["uniform"], J_lowflow=v["J"]["lowflow"], spec=v["spec"]) for k, v in best_af.items()}
NUM["Re_band"] = [Re_lo, Re_hi]
fig1 = plt.figure(figsize=(16, 9), facecolor=BG)
fig1.text(0.03, 0.945, "Hydrofoil selection", fontsize=24, fontweight="bold", color=INK)
fig1.text(0.03, 0.905, "7 open-source sections (UIUC), polars from NeuralFoil (open-source XFOIL surrogate); each section built into rotors and scored as a whole turbine with the GL60", fontsize=12.5, color=INK2)
def fe(x): e = int(math.floor(math.log10(x))); return f"{x / 10 ** e:.1f}e{e}"
# --- foil shapes
ax0 = fig1.add_axes([0.025, 0.215, 0.30, 0.655]); ax0.set_axis_off(); ax0.set_aspect("equal")
dy = 0.66
for i, k in enumerate(order):
    y0 = -i * dy; c = np.array(T[k]["coords"]); c = (c - [c[:, 0].min(), 0]) / (c[:, 0].max() - c[:, 0].min())
    st, fc, tc_ = status(k); excl = st == "excluded"
    ax0.fill(c[:, 0], c[:, 1] + y0, color=col[k], alpha=0.35 if excl else 0.9, lw=0)
    ax0.plot(c[:, 0], c[:, 1] + y0, color=col[k], lw=1.0, ls=":" if excl else "-")
    ax0.text(1.10, y0 + 0.13, names[k], fontsize=13.5, fontweight="bold", color=INK if not excl else MUTE, va="center")
    ax0.text(1.10, y0 - 0.07, f"t/c {T[k]['tc']*100:.0f} %   conf. {T[k]['conf_mean']:.2f}", fontsize=10.5, color=INK2, va="center")
    ax0.add_patch(FancyBboxPatch((2.55, y0 - 0.11), 0.70, 0.25, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec="none"))
    ax0.text(2.90, y0 + 0.015, st, fontsize=10, fontweight="bold", color=tc_, ha="center", va="center")
ax0.set_xlim(-0.03, 3.3); ax0.set_ylim(-(len(order) - 1) * dy - 0.3, 0.32)
# --- L/D vs Re
ax1 = fig1.add_axes([0.385, 0.30, 0.30, 0.56])
ax1.axvspan(Re_lo, Re_hi, color="#dce6f2", alpha=0.8, lw=0)
ax1.text(math.sqrt(Re_lo * Re_hi), 152, f"turbine operating range\nRe {fe(Re_lo)} to {fe(Re_hi)}", ha="center", va="top", fontsize=10.5, color="#1f4e79")
for k in order:
    t = T[k]; excl = not t["selectable"] and k != "naca4418"
    ax1.plot(t["Res"], t["best_ld"], ":" if excl else "-", color=col[k], lw=3.2 if k == "naca4412" else 1.7, marker="o", ms=3.5, label=names[k], zorder=3 if k == "naca4412" else 2)
ax1.set_xscale("log"); ax1.set_xlim(2e4, 5e5); ax1.set_ylim(0, 155)
ax1.set_xticks([2e4, 5e4, 1e5, 2e5, 5e5]); ax1.set_xticklabels(["2e4", "5e4", "1e5", "2e5", "5e5"]); ax1.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter()); ax1.grid(True, which="both", color=GRID, lw=0.7); ax1.set_axisbelow(True)
ax1.set_xlabel("chord Reynolds number"); ax1.set_ylabel("best lift-to-drag ratio (2-D section)")
ax1.set_title("Section performance falls steeply below Re 1e5", loc="left", fontsize=13, fontweight="bold", color=INK)
ax1.legend(fontsize=9.5, loc="upper left", frameon=False)
# --- 2-D vs system ranking
srch = ["naca4412", "naca4415", "sg6043", "fx63137"]
ax2 = fig1.add_axes([0.775, 0.635, 0.20, 0.205]); ax3 = fig1.add_axes([0.775, 0.315, 0.20, 0.205])
ld = [T[k]["best_ld"][i8] for k in srch]; J = [best_af[k]["J"]["uniform"] for k in srch]
for ax, vals, ttl, fmt in ((ax2, ld, "2-D ranking: best L/D at Re 8e4", "{:.0f}"), (ax3, J, "System ranking: mean net 12 V power\n0.5-1.0 m/s, best rotor per section (W)", "{:.2f}")):
    yy = np.arange(len(srch))[::-1]
    ax.barh(yy, vals, color=[col[k] if k == "naca4412" else "#c9c9c9" if ax is ax2 else "#9bb6d6" for k in srch], height=0.62)
    ax.set_yticks(yy); ax.set_yticklabels([names[k] for k in srch], fontsize=10.5)
    for y_, v in zip(yy, vals): ax.text(v * 1.01, y_, fmt.format(v), va="center", fontsize=10.5, fontweight="bold" if v == max(vals) else None)
    ax.set_xlim(0, max(vals) * 1.22); ax.set_title(ttl, loc="left", fontsize=11.5, fontweight="bold", color=INK); ax.set_xticks([])
    for s_ in ("top", "right", "bottom"): ax.spines[s_].set_visible(False)
ax2.text(0.0, -0.13, "SG6043 is best in 2-D ...", transform=ax2.transAxes, fontsize=10.5, color="#c8692b", style="italic", va="top")
ax3.text(0.0, -0.13, "... but NACA 4412 makes the most electricity", transform=ax3.transAxes, fontsize=10.5, color="#1f4e79", style="italic", fontweight="bold", va="top")
# --- criteria strip
crit = [("1  Trust gate", f"surrogate confidence >= 0.90\nE387 ({T['e387']['conf_mean']:.2f}), E818 ({T['e818']['conf_mean']:.2f}) excluded"),
        ("2  2-D performance", f"L/D over Re {fe(Re_lo)} to {fe(Re_hi)}\nSG6043 best: {T['sg6043']['best_ld'][i8]:.0f} at Re 8e4"),
        ("3  Decider: system output", f"{len(allS)} rotors built from the sections,\nscored on net power with the GL60"),
        ("4  Printability", "t/c >= 12 % on the blade;\n18 % NACA 4418 at the root")]
for i, (h, b) in enumerate(crit):
    x0 = 0.03 + i * 0.178; fig1.patches.append(FancyBboxPatch((x0, 0.045), 0.165, 0.135, boxstyle="round,pad=0.004,rounding_size=0.008", transform=fig1.transFigure, fc="#f3f5f8", ec="#c9d3dd", lw=1))
    fig1.text(x0 + 0.008, 0.158, h, fontsize=12, fontweight="bold", color="#1f4e79", va="top"); fig1.text(x0 + 0.008, 0.118, b, fontsize=10.5, color=INK2, va="top", linespacing=1.35)
fig1.patches.append(FancyBboxPatch((0.745, 0.045), 0.23, 0.135, boxstyle="round,pad=0.004,rounding_size=0.008", transform=fig1.transFigure, fc="#1f4e79", ec="none"))
fig1.text(0.753, 0.158, "Why NACA 4412 won", fontsize=12, fontweight="bold", color="white", va="top")
fig1.text(0.753, 0.118, "High-lift sections need narrower chords:\nlower Re and a sharper Cp peak the\ngenerator load cannot stay on.", fontsize=10.5, color="white", va="top", linespacing=1.35)
# ======================================================================== SLIDE 2: iterations
it_col = {"it12": "#b8860b", "it3": "#b84a3a", "it4a": "#8fb1d9", "it4b": "#3d6fa8", "it5": "#14365c"}
cards = [
 ("it12", "29 Oct", "1  Blade for 1-2 m/s", "1-2 m/s, 8-in blade", "BEM design; review rev 1 → rev 2", "NACA 44xx, TSR 4, +6° pitch", "rotor Cp 0.37 at 1.5 m/s"),
 ("it12", "31 Oct", "2  Generator + housing", "1-2 m/s, waterproof unit", "8 generators, 4 layouts (A-D)", "GL60 KV25, sealed nacelle", "2.5x the 76 mm depth target"),
 ("it3", "31 Oct", "3  76 mm redesign (v3.1)", "1-2 m/s, ≤ 76 mm deep", "6 rotor variants; HW7 sheet", "motor inside 48 mm drum hub", f"{NUM['it3']['P']['1.5']:.1f} W at 1.5 m/s; {NUM['it3']['P']['0.7']:.2f} W at 0.7"),
 ("it4b", "2 Nov", "4  Low-flow optimisation (v4)", "0.5-1.0 m/s, max net energy", f"{len(allS)} rotors: 2-5 blades, 4 foils, TSR 1.5-6", "TSR 2.0 ×1.3 → after review TSR 1.5, −3°", f"{NUM['it4b']['P']['0.7']:.2f} W at 0.7; starts {NUM['it4b']['min_start']} m/s"),
 ("it5", "3 Nov", "5  Simplified prototype (v5)", "printable, fewest parts", "one-piece rotor, housing, mount", "one 12 mm seal + one 6001", f"{NUM['it5']['P']['0.7']:.2f} W at 0.7; 91 mm deep"),
]
fig2 = plt.figure(figsize=(16, 9), facecolor=BG)
fig2.text(0.03, 0.945, "Design iterations: net power of each whole-turbine design", fontsize=24, fontweight="bold", color=INK)
fig2.text(0.03, 0.905, "Dates from the project history. All designs re-evaluated with today's coupled model (BEM + GL60 + buck-boost MPPT) so the curves are comparable. Model predictions; nothing measured yet.", fontsize=12, color=INK2)
cw, ch, cy, gap = 0.148, 0.305, 0.565, 0.012
for i, (key, date, title, tgt, expl, chose, res) in enumerate(cards):
    x0 = 0.03 + i * (cw + gap); c = it_col[key]
    fig2.patches.append(FancyBboxPatch((x0, cy), cw, ch, boxstyle="round,pad=0.003,rounding_size=0.008", transform=fig2.transFigure, fc="#fafafa", ec=c, lw=1.6))
    fig2.patches.append(Rectangle((x0, cy + ch - 0.058), cw, 0.058, transform=fig2.transFigure, fc=c, ec="none"))
    fig2.text(x0 + 0.007, cy + ch - 0.012, date, fontsize=10.5, color="white", va="top", fontweight="bold")
    fig2.text(x0 + 0.007, cy + ch - 0.034, title, fontsize=11.2, color="white", va="top", fontweight="bold")
    yy = cy + ch - 0.072
    for lab, txt in (("Target", tgt), ("Explored", expl), ("Chose", chose), ("Result", res)):
        fig2.text(x0 + 0.007, yy, lab, fontsize=9.3, color=c if key != "it4a" else "#3d6fa8", fontweight="bold", va="top")
        w = textwrap.fill(txt, 29); fig2.text(x0 + 0.007, yy - 0.019, w, fontsize=9.8, color=INK, va="top", linespacing=1.2); yy -= 0.024 + 0.019 * (w.count("\n") + 1)
    if i < len(cards):
        fig2.patches.append(FancyArrowPatch((x0 + cw + 0.0005, cy + ch / 2), (x0 + cw + gap - 0.0005, cy + ch / 2), transform=fig2.transFigure, arrowstyle="-|>", mutation_scale=12, color=MUTE, lw=1.2))
x0 = 0.03 + 5 * (cw + gap)
fig2.patches.append(FancyBboxPatch((x0, cy), cw, ch, boxstyle="round,pad=0.003,rounding_size=0.008", transform=fig2.transFigure, fc="#eef6ee", ec="#4f8a5b", lw=1.6))
fig2.patches.append(Rectangle((x0, cy + ch - 0.058), cw, 0.058, transform=fig2.transFigure, fc="#4f8a5b", ec="none"))
fig2.text(x0 + 0.007, cy + ch - 0.012, "Next", fontsize=10.5, color="white", va="top", fontweight="bold"); fig2.text(x0 + 0.007, cy + ch - 0.034, "Test and recalibrate", fontsize=11.2, color="white", va="top", fontweight="bold")
nxt = ["Bench the GL60: no-load loss, cogging, volts per rpm", "Print the rotor; flume or tow test at 0.5-1.0 m/s", "Refit the model to the data", "If motor losses are high: revisit rotor diameter"]
yy = cy + ch - 0.075
for t_ in nxt:
    w = textwrap.fill(t_, 28); fig2.text(x0 + 0.007, yy, "- " + w.replace("\n", "\n  "), fontsize=9.8, color=INK, va="top", linespacing=1.25); yy -= 0.012 + 0.0195 * (w.count("\n") + 1)
# pivot marker between cards 3 and 4
xp = 0.03 + 3 * (cw + gap) - gap / 2
fig2.lines.append(matplotlib.lines.Line2D([xp, xp], [cy - 0.005, cy + ch + 0.012], transform=fig2.transFigure, color="#3d6fa8", lw=1.6, ls="--"))
fig2.text(xp, cy - 0.022, "PIVOT: flow target lowered to 0.5-1.0 m/s", fontsize=10.5, color="#3d6fa8", fontweight="bold", ha="center", va="top",
          bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#3d6fa8", lw=1.2))
# power chart
ax = fig2.add_axes([0.065, 0.07, 0.555, 0.40])
ax.axvspan(1.0, 2.0, color="#f6ead6", alpha=0.7, lw=0); ax.axvspan(0.5, 1.0, color="#dce6f2", alpha=0.8, lw=0)
ax.text(1.5, 32, "design target, iterations 1-3", ha="center", fontsize=10.5, color="#8a6510", fontweight="bold")
ax.text(0.75, 32, "target, iterations 4-5", ha="center", fontsize=10.5, color="#1f4e79", fontweight="bold")
vc = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
for r in allS:
    ax.plot(vc, [r["perV"][str(V)]["Pout"] for V in vc], color="#9aa7b5", lw=0.5, alpha=0.12, zorder=1)
ax.plot([], [], color="#9aa7b5", lw=2, alpha=0.5, label=f"iteration 4 options ({len(allS)} rotors)")
lab = {"it12": "1-2  rev-2 blade + GL60", "it3": "3  v3.1 drum (48 mm hub)", "it4a": "4  first pick (TSR 2.0 x1.3)", "it4b": "4  final v4 (TSR 1.5, -3 deg)", "it5": "5  v5 prototype (current)"}
sty = {"it12": (":", 2.4), "it3": ("--", 2.4), "it4a": ("-.", 1.8), "it4b": ("--", 2.0), "it5": ("-", 3.6)}
for k in ("it12", "it3", "it4a", "it4b", "it5"):
    ls, lw = sty[k]; ax.plot(VS, [NUM[k]["P"][str(V)] for V in VS], ls, color=it_col[k], lw=lw, marker="o" if k == "it5" else None, ms=4.5, label=lab[k], zorder=4 if k == "it5" else 3)
ax.set_yscale("log"); ax.set_ylim(0.05, 45); ax.set_xlim(0.4, 2.0); ax.grid(True, which="both", color=GRID, lw=0.6); ax.set_axisbelow(True)
ax.set_xlabel("water speed (m/s)"); ax.set_ylabel("net 12 V electrical power (W)")
ax.legend(loc="lower right", fontsize=9.5, framealpha=0.95)
# results table
axt = fig2.add_axes([0.645, 0.07, 0.335, 0.40]); axt.set_axis_off()
hdr = ["", "iteration", "0.5", "0.7", "1.0", "1.5 m/s", "starts"]
xs = [0.0, 0.06, 0.53, 0.63, 0.73, 0.84, 0.95]
axt.text(0.0, 0.97, "Net power (W) and self-start speed (m/s)", fontsize=12, fontweight="bold", color=INK, transform=axt.transAxes, va="top")
for x_, h in zip(xs, hdr): axt.text(x_, 0.86, h, fontsize=10, color=MUTE, fontweight="bold", transform=axt.transAxes, ha="left" if x_ < 0.5 else "right" if False else "center")
rows = [("it12", "1-2  rev-2 blade + GL60"), ("it3", "3  v3.1 drum"), ("it4a", "4  first pick"), ("it4b", "4  final v4"), ("it5", "5  v5 (current)")]
for j, (k, nm) in enumerate(rows):
    y_ = 0.76 - j * 0.115; c = it_col[k]
    axt.plot([0.0, 0.045], [y_, y_], color=c, lw=4 if k == "it5" else 3, transform=axt.transAxes, solid_capstyle="butt")
    axt.text(0.06, y_, nm, fontsize=10.5, color=INK, va="center", transform=axt.transAxes, fontweight="bold" if k == "it5" else None)
    for x_, V in zip(xs[2:6], (0.5, 0.7, 1.0, 1.5)):
        axt.text(x_, y_, f"{NUM[k]['P'][str(V)]:.2f}" if NUM[k]["P"][str(V)] < 10 else f"{NUM[k]['P'][str(V)]:.1f}", fontsize=10.5, ha="center", va="center", transform=axt.transAxes, fontweight="bold" if k == "it5" else None)
    axt.text(xs[6], y_, f"{NUM[k]['min_start']}", fontsize=10.5, ha="center", va="center", transform=axt.transAxes, fontweight="bold" if k == "it5" else None)
axt.text(0.0, 0.135, textwrap.fill("Lesson per pivot: the 1-2 m/s designs lose most of their output below 0.8 m/s and start late. Optimising the whole chain for 0.5-1.0 m/s "
                                   f"gained {(NUM['it5']['P']['0.6'] / NUM['it12']['P']['0.6'] - 1) * 100:.0f} % at 0.6 m/s over the rev-2 blade and lowered self-start to {NUM['it5']['min_start']} m/s, "
                                   f"at a cost of {(1 - NUM['it5']['P']['2.0'] / NUM['it12']['P']['2.0']) * 100:.0f} % at 2 m/s.", 62), fontsize=10, color=INK2, transform=axt.transAxes, va="top", linespacing=1.3)
# ======================================================================== SLIDE 3: motor
dig = json.load(open(CHART_DIG)) if CHART_DIG else None
G = dict(gl.GEN); Kt = 60 / (2 * math.pi * G["KV"])
r5 = EV["it5"]; ops = [(V, r5["perV"][str(V)]["op"]) for V in VS if r5["perV"][str(V)]["op"]]
Ti = np.array(dig["current"]["T"]); Ii = np.array(dig["current"]["v"]); mfit = (Ti > 0.05) & (Ti < 0.6)
kfit, I0 = np.polyfit(Ti[mfit], Ii[mfit], 1); Kt_lo, Kt_hi = sorted([1 / kfit, 0.2 / (np.interp(0.4, Ti, Ii) - np.interp(0.2, Ti, Ii)) * 1.0, 1.6 / (np.interp(1.8, Ti, Ii) - np.interp(0.2, Ti, Ii))])[0::2]
Tn = np.array(dig["speed"]["T"]); nn = np.array(dig["speed"]["v"])
Reff = float(np.mean([(24 - np.interp(t, Tn, nn) / G["KV"]) / np.interp(t, Ti, Ii) for t in (0.1, 0.2, 0.3, 0.4, 0.5)]))
p0_516_chart = 24 * I0 - I0 ** 2 * G["R_LL"]; p0_516_model = G["p0_700"] * (516 / 700) ** G["p0_exp"]
gR = dict(G); gR["R_LL"] = Reff
gRL = dict(gR); gRL["p0_700"] = p0_516_chart * (700 / 516) ** G["p0_exp"]
EVm = {"model": r5, "R": ce.full_eval(spec, "S", gen=gR), "RL": ce.full_eval(spec, "S", gen=gRL)}
NUM["motor"] = dict(Kt_model=Kt, Kt_chart=[Kt_lo, Kt_hi], I0_chart=I0, Reff_chart=Reff, p0_516_chart=p0_516_chart, p0_516_model=p0_516_model, KV_chart=516 / 24,
                    ops={str(V): dict(rpm=o["rpm"], Qg=o["Qg"], I=o["I"], Vdc=o["Vdc"]) for V, o in ops},
                    P_cases={k: {str(V): P(r, V) for V in (0.5, 0.6, 0.7, 0.8, 1.0)} for k, r in EVm.items()}, start_cases={k: ce.min_flows(r) for k, r in EVm.items()})
fig3 = plt.figure(figsize=(16, 9), facecolor=BG)
fig3.text(0.03, 0.945, "Generator: CubeMars GL60 KV25 curve vs how the turbine uses it", fontsize=24, fontweight="bold", color=INK)
fig3.text(0.03, 0.905, "Manufacturer curve at 24 VDC (motoring), digitized; the turbine runs it as a generator in the shaded corner", fontsize=12.5, color=INK2)
img = np.asarray(Image.open(CHART_IMG).convert("RGB")); cx0, cx1, cy0, cy1 = 40, 930, 55, 830
axi = fig3.add_axes([0.015, 0.035, 0.52, 0.84]); axi.imshow(img[cy0:cy1, cx0:cx1], extent=(cx0, cx1, cy1, cy0)); axi.set_axis_off()
X0p, PXNM, Y0p, PXS = 267.6, 63.4 / 0.2, 719.5, 51.33
xT = lambda t: X0p + t * PXNM; yN = lambda n: Y0p - n / 60.0 * PXS
q = {V: o["Qg"] for V, o in ops}
axi.add_patch(Rectangle((xT(q[0.5]) - 2, yN(600)), xT(q[1.0]) - xT(q[0.5]) + 2, Y0p - yN(600), fc="#1f4e79", alpha=0.22, ec="none"))
axi.add_patch(Rectangle((xT(q[1.0]), yN(600)), xT(q[2.0]) - xT(q[1.0]), Y0p - yN(600), fc="#1f4e79", alpha=0.09, ec="none"))
axi.plot([xT(0.6)] * 2, [Y0p, yN(600)], "--", color="#1f4e79", lw=1.3); axi.text(xT(0.6) + 5, yN(18), "rated 0.6 N m", fontsize=9.5, color="#1f4e79", va="bottom", fontweight="bold")
for V, o in ops:
    if o["rpm"] <= 600:
        axi.plot(xT(o["Qg"]), yN(o["rpm"]), "o", ms=7.5, mfc="#1f4e79", mec="white", mew=1.4, zorder=5)
        if V in (0.5, 0.7, 1.0, 1.5): axi.text(xT(o["Qg"]) + 7, yN(o["rpm"]) + 3, f"{V} m/s", fontsize=9.5, color="#1f4e79", fontweight="bold", va="center")
o2 = dict(ops)[2.0]
axi.annotate(f"2 m/s: {o2['rpm']:.0f} rpm, {o2['Qg']:.2f} N m (off scale)", xy=(xT(o2["Qg"]), yN(600) + 2), xytext=(xT(0.63), yN(583)), fontsize=9.5, color="#1f4e79",
             arrowprops=dict(arrowstyle="-|>", color="#1f4e79", lw=1))
axi.text(0.5 * (xT(q[0.5]) + xT(q[1.0])), yN(603), "0.5-1.0\nm/s", fontsize=9.5, color="#1f4e79", fontweight="bold", ha="center", va="bottom")
axi.text(0.5 * (xT(q[1.0]) + xT(q[2.0])), yN(603), "1-2 m/s", fontsize=9.5, color="#1f4e79", ha="center", va="bottom")
axi.plot(xT(1.43), yN(652), "o", ms=7.5, mfc="#1f4e79", mec="white", mew=1.4)
axi.text(xT(1.47), yN(652), "turbine operating points\n(generator torque vs rpm)", fontsize=10, color="#1f4e79", fontweight="bold", ha="left", va="center")
axi.text(cx0 + 10, cy1 - 8, "Chart: CubeMars GL60 KV25 @ 24 VDC (supplied); overlays added", fontsize=8.5, color=MUTE, va="bottom")
# constants check
axc = fig3.add_axes([0.55, 0.47, 0.435, 0.40]); axc.set_axis_off()
axc.text(0.0, 1.0, "Constants check: listed vs chart vs model", fontsize=13, fontweight="bold", color=INK, va="top", transform=axc.transAxes)
cols_x = [0.0, 0.25, 0.43, 0.70, 0.86]
for x_, h in zip(cols_x, ("quantity", "listed", "from the chart", "model", "verdict")): axc.text(x_, 0.86, h, fontsize=10, color=MUTE, fontweight="bold", transform=axc.transAxes)
crow = [("speed constant KV", "25 rpm/V", f"516 rpm at 24 V = {516/24:.1f}", f"{G['KV']}", "match", "#2e7d32"),
        ("torque per amp Kt", "0.45 N m/A", f"{Kt_lo:.2f}-{Kt_hi:.2f}", f"{Kt:.3f}", "match", "#2e7d32"),
        ("resistance", "5.5 ohm", f"~{Reff:.1f} ohm effective", f"{G['R_LL']}", "small effect", "#b8860b"),
        ("no-load loss", "not listed", f"<= {p0_516_chart:.1f} W at 516 rpm", f"{p0_516_model:.2f} W", "KEY RISK", "#b84a3a"),
        ("turbine load", "0.6 N m, 1.35 A", "-", f"{q[0.5]:.2f}-{q[1.0]:.2f} N m", f"{q[0.5]/0.6*100:.0f}-{q[1.0]/0.6*100:.0f} % rated", "#1f4e79")]
for j, (a, b, c, d, e, ec) in enumerate(crow):
    y_ = 0.73 - j * 0.135
    if j % 2 == 0: axc.add_patch(Rectangle((-0.01, y_ - 0.06), 1.02, 0.12, transform=axc.transAxes, fc="#f6f6f4", ec="none"))
    for x_, t_ in zip(cols_x[:4], (a, b, c, d)): axc.text(x_, y_, t_, fontsize=10.6, color=INK, va="center", transform=axc.transAxes, fontweight="bold" if x_ == 0 else None)
    axc.text(cols_x[4], y_, e, fontsize=10.6, color=ec, va="center", fontweight="bold", transform=axc.transAxes)
axc.text(0.0, -0.04, textwrap.fill(f"KV and Kt confirm the constants behind every prediction. The open question is the chart's {I0:.2f} A at near-zero torque: it may include the controller's own draw, so it is an upper bound on the motor's drag (model assumes {p0_516_model:.2f} W at 516 rpm).", 92), fontsize=10, color=INK2, transform=axc.transAxes, va="top", linespacing=1.3)
axc.text(0.0, -0.245, "Next step: bench-measure the GL60's no-load drag at 100-700 rpm (gate G1).", fontsize=10.5, color="#b84a3a", fontweight="bold", transform=axc.transAxes, va="top")
# effect on output
axb = fig3.add_axes([0.585, 0.07, 0.395, 0.245])
Vb = [0.5, 0.6, 0.7, 0.8, 1.0]; wbar = 0.26; xb = np.arange(len(Vb))
cases = [("model", f"model as used (R {G['R_LL']} ohm, no-load {p0_516_model:.2f} W)", "#1f4e79"), ("R", f"chart resistance (R {Reff:.1f} ohm)", "#6f9bc8"),
         ("RL", f"chart resistance + chart no-load (upper bound)", "#b84a3a")]
for i, (k, labt, c) in enumerate(cases):
    vals = [P(EVm[k], V) for V in Vb]; axb.bar(xb + (i - 1) * wbar, vals, wbar * 0.95, color=c, label=labt)
    for x_, v in zip(xb + (i - 1) * wbar, vals): axb.text(x_, v + 0.04, f"{v:.2f}", ha="center", fontsize=8.6, color=INK2)
axb.set_xticks(xb); axb.set_xticklabels([f"{V} m/s" for V in Vb]); axb.set_ylabel("net 12 V power (W)"); axb.set_ylim(0, max(P(EVm['model'], 1.0), 0.1) * 1.28)
axb.grid(True, axis="y", color=GRID); axb.set_axisbelow(True); axb.legend(fontsize=9, loc="upper left", frameon=False)
for s_ in ("top", "right"): axb.spines[s_].set_visible(False)
axb.set_title("Effect on the current design's net output", loc="left", fontsize=12.5, fontweight="bold", color=INK)
# ======================================================================== save
paths = []
for f, nm in ((fig1, "slide1_hydrofoil_selection"), (fig2, "slide2_design_iterations"), (fig3, "slide3_generator_curve")):
    p = os.path.join(OUT, nm + ".png"); f.savefig(p, dpi=150, facecolor=BG); paths.append(p)
with PdfPages(os.path.join(OUT, "iteration_slides.pdf")) as pdf:
    for f in (fig1, fig2, fig3): pdf.savefig(f, facecolor=BG)
json.dump(NUM, open(os.path.join(OUT, "slide_numbers.json"), "w"), indent=1, default=float)
print("written:", paths, "+ iteration_slides.pdf, slide_numbers.json")
print("motor:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in NUM["motor"].items() if k not in ("ops", "P_cases")})
print("motor P cases:", {k: {V: round(x, 2) for V, x in d.items()} for k, d in NUM["motor"]["P_cases"].items()})
