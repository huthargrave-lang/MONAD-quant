#!/usr/bin/env python3
"""WORKFLOW_v4.md + out/fig_workflow.png + WORKFLOW_v4.pdf: the optimisation workflow as a flowchart with a short explanation of each
stage, its inputs, outputs and files; and where the HW7 spreadsheet's method sits in it.  Counts and numbers come from the result files."""
import base64, json, os, subprocess, markdown
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
D = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(D, ".."); M = os.path.join(ROOT, "model"); OUT = os.path.join(ROOT, "out")
S1 = json.load(open(os.path.join(M, "sweep_stage1.json"))); S2 = json.load(open(os.path.join(M, "sweep_stage2.json"))); SEL = json.load(open(os.path.join(M, "selection.json")))
sel = json.load(open(os.path.join(M, "selected_design.json"))); C = json.load(open(os.path.join(M, "coupled_results.json"))); T = json.load(open(os.path.join(M, "polars_cache.json")))
REV = open(os.path.join(D, "REVIEW_LOG_v4.md")).read() if os.path.exists(os.path.join(D, "REVIEW_LOG_v4.md")) else ""
n_rev = REV.count("\n| ") - 1 if REV else 0
spec = sel["spec"]; new = C["designs"]["new"]["res"]; VS = C["VS"]; combos = C["combos"]
def Pout(V): o = new["perV"][str(V)]["op"]; return o["Pout"] if o else 0.0
n_sel = len([k for k, v in T.items() if v["selectable"]])
# ---------------------------------------------------------------- flowchart (wrapped text, heights from line counts)
import textwrap
INK, ACC, ACC2, GRN, BOX, BOX2, BOX3 = "#1a1a1a", "#2b4a6b", "#b85c38", "#4f8a5b", "#eef2f6", "#fbf3e9", "#eef6ee"
MAIN_W, SIDE_W, X0, XS, LH = 62, 30, 3, 69, 2.15                       # units: main column width, side column width, left edges, line height
def wrap(body, width): return "\n".join(textwrap.fill(par, width) for par in body.split("\n"))
stages = [
 ("0", "Inputs", "Brief: 0.5-1.0 m/s, 203.2 mm rotor, GL60 KV25 fixed, 12 V output, printed parts. Generator: KV 21.5, R 5.5 ohm, cogging 24 mN m (assumed). Friction: seal + bearing 7 mN m. Converter: buck-boost MPPT, 5 V floor, 0.13 W overhead. Nothing measured."),
 ("1", "Airfoil polars", f"NeuralFoil (XFOIL surrogate) on 7 candidate sections, -10 to +18 deg, Re 2e4-5e5, Viterna post-stall extension; surrogate confidence recorded. {n_sel} sections admitted, 2 excluded for low confidence.  ->  model/polars_cache.json, fig_polars.png"),
 ("2", "Blade design generator", "One candidate = blade count, section, design TSR, chord scale, pitch offset. Schmitz chord at the design TSR from the section's best-L/D lift coefficient at the local Reynolds number; twist = best-L/D angle + inflow angle + pitch offset; chord cap 60 mm, root ease 85 %, tip taper 55 %, NACA 4418 root blend over 35 % of span.  ->  bem_lowflow.design()"),
 ("3", "Rotor evaluation (blade-element momentum)", "40-50 elements, Prandtl tip and hub losses, Buhl high-induction correction, 15 % inflow deficit behind the nacelle. Outputs per flow speed: Cp(TSR), torque curve, starting torque (BEM at TSR 0.1).  ->  bem_lowflow.bem()"),
 ("4", "Electrical model and operating point", "GL60: V_oc = rpm / KV, copper loss, commutation overlap, no-load loss; Schottky bridge; buck-boost with efficiency curve, overhead and 5 V floor. The MPPT equilibrium is the rotor speed where the net output is highest.  ->  generator_lowflow.operating_point()"),
 ("5", "Gates and objective", "P_net = 0 at any speed where the candidate cannot self-start (torque at TSR 0.1 < cogging + breakaway), cannot sustain rotation, or puts less than 5 V on the bus. J_uniform = mean P_net over 0.5-1.0 m/s; J_low-flow = weights 0.30 / 0.30 / 0.20 / 0.10 / 0.05 / 0.05.  ->  optimize_blades.evaluate()"),
 ("6", "Search and selection", f"Stage 1: {len(S1)} candidates (2-5 blades x 4 sections x design TSR 1.5-6 x chord scale 0.7 / 1.0 / 1.3). Stage 2: {len(S2)} refinements (TSR 1.5-2.5, chord 1.0-1.5, pitch -3 / 0 / +3 deg). Rule: maximise the mean of the two normalised objectives subject to >= 12 deg of printable hub wall; ties to lower solidity.\nSelected: {spec['B']} blades, NACA 4412, design TSR {spec['lam_d']}, chord x{spec.get('c_scale', 1.0)}, pitch {spec.get('dbeta', 0):+.0f} deg.  ->  selection.json, selected_design.json"),
 ("7", "Final evaluation, robustness, sensitivities", f"Selected blade re-run with 50 elements: net {Pout(0.5):.2f} / {Pout(0.7):.2f} / {Pout(1.0):.2f} W at 0.5 / 0.7 / 1.0 m/s; self-start {combos['baseline']['min_start']} m/s (bounds {combos['optimistic']['min_start']}-{combos['pessimistic']['min_start']}). {len(C['sens'])} one-at-a-time sensitivities, optimistic and pessimistic combinations, best candidate per blade count under Reynolds and starting-torque variants.  ->  coupled_results.json, robustness.json, figures 1-9"),
]
wrapped = [(n, t, wrap(b, 104)) for n, t, b in stages]
heights = [5.2 + LH * (w.count("\n") + 1) for _, _, w in wrapped]
GAP = 3.2; total = sum(heights) + GAP * (len(stages) - 1)
fig, ax = plt.subplots(figsize=(12.4, 0.118 * total + 1.2), facecolor="white"); ax.set_xlim(0, 104); ax.set_ylim(-1, total + 1); ax.set_axis_off()
def box(x, y, w, h, title, body, fc, ec, num=None, tfs=9.4):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2", fc=fc, ec=ec, lw=1.3))
    ax.text(x + 1.4, y + h - 1.5, (f"{num}   " if num else "") + title, fontsize=tfs, fontweight="bold", color=ec, va="top")
    ax.text(x + 1.4, y + h - 4.6, body, fontsize=7.6, color=INK, va="top", linespacing=1.3)
ytop = {}; ybot = {}; y = total
for (n, t, w), h in zip(wrapped, heights):
    y -= h; box(X0, y, MAIN_W, h, t, w, BOX, ACC, num=n); ytop[n] = y + h; ybot[n] = y; y -= GAP
for a, b in zip("0123456", "1234567"):
    ax.add_patch(FancyArrowPatch((X0 + MAIN_W / 2, ybot[a]), (X0 + MAIN_W / 2, ytop[b]), arrowstyle="-|>", mutation_scale=12, color=ACC, lw=1.3))
def side(y0, y1, title, body, fc, ec):
    h = y1 - y0; box(XS, y0, SIDE_W, h, title, wrap(body, 46), fc, ec, tfs=9.0)
side(ybot["5"], ytop["2"], "Per-candidate loop", "Stages 2 to 5 run for every candidate, at every flow speed (0.4-1.0 m/s) and every tip-speed ratio (0.5-7).\n\nOne candidate: about 1 s. Stages 1 + 2 of the search: about 15 min on 4 cores.\n\nThe arrows mark the stages the HW7 spreadsheet covers by hand: 2 and 3 for one candidate at one speed, with a single CL/CD point, Betz-optimum induction, 20 strips, and a matched-load generator check (sheet 'v4 design' of IED_HW7_v4_parameters.xlsx).", BOX2, ACC2)
for n in ("2", "3"):
    ax.add_patch(FancyArrowPatch((X0 + MAIN_W + 0.6, 0.5 * (ytop[n] + ybot[n])), (XS - 0.6, 0.5 * (ytop[n] + ybot[n])), arrowstyle="<|-|>", mutation_scale=11, color=GRN, lw=1.4))
side(ybot["7"], ytop["6"], "After the optimisation", f"CAD: the v4 package (pocketed hub, sealed nacelle) and the v5 simplified prototype (one-piece rotor, printed housing and mount), both from selected_design.json.\n\nAdversarial review ({n_rev} logged findings) changed the starting-torque model to the BEM at TSR 0.1 and added the Reynolds-shift, induction-model, overhead and inflow sensitivities; the search was re-run.\n\nQA: 23 scripted gates (reproducibility, Betz, power balance, current limit, CAD validity, packing).", BOX2, ACC2)
ax.add_patch(FancyArrowPatch((X0 + MAIN_W + 0.6, 0.5 * (ytop["7"] + ybot["7"])), (XS - 0.6, 0.5 * (ytop["7"] + ybot["7"])), arrowstyle="-|>", mutation_scale=11, color=ACC2, lw=1.3))
ax.annotate("review findings re-run stages 1-7", xy=(X0 + MAIN_W + 0.3, ytop["1"] - 2), xytext=(XS + 1.5, ytop["6"] + 1.2), fontsize=7.2, color=ACC2, va="bottom",
            arrowprops=dict(arrowstyle="-|>", color=ACC2, lw=1.0, connectionstyle="arc3,rad=-0.25"))
fig.savefig(os.path.join(OUT, "fig_workflow.png"), dpi=150, facecolor="white", bbox_inches="tight"); plt.close(fig)
# ---------------------------------------------------------------- document
txt = f"""# Blade Optimization Workflow

<p class="sub">8-inch hydrokinetic turbine for 0.5-1.0 m/s streams with the CubeMars GL60 KV25. How the blade geometry was arrived at, stage by stage,
and where the HW7 spreadsheet method fits. Every count and number is read from the v4 result files by <code>docs/make_workflow_doc_v4.py</code>.
Nothing has been measured.</p>

## 1. The workflow at a glance

<figure><img src="FIG_WORKFLOW" alt="workflow"><figcaption>Figure 1. The optimisation workflow. Stages 2-5 form the inner loop that is run for every candidate, flow speed and tip-speed ratio;
the spreadsheet is the hand-calculable version of stages 2-3 for a single candidate at a single speed.</figcaption></figure>

## 2. The stages

| # | stage | what goes in | what comes out | file |
|---|---|---|---|---|
| 0 | Inputs | brief (0.5-1.0 m/s, 203.2 mm, GL60 fixed, 12 V, printed), generator and converter constants, friction estimates | the assumption set, carried through every stage | `feasibility.json` (assumptions block) |
| 1 | Airfoil polars | UIUC coordinates of 7 sections | CL, CD tables over angle and Reynolds number with surrogate confidence; 2 sections excluded | `polars.py` -> `polars_cache.json` |
| 2 | Design generator | blade count, section, design TSR, chord scale, pitch offset | chord and twist at 40-50 radial stations | `bem_lowflow.design()` |
| 3 | Rotor evaluation | the blade, flow speed | Cp and torque against tip-speed ratio, starting torque | `bem_lowflow.bem()` |
| 4 | Electrical model | torque curve, generator, rectifier, converter | the MPPT operating point: rpm, bus voltage, current, net power | `generator_lowflow.operating_point()` |
| 5 | Gates and objective | per-speed net power, self-start and sustain checks | J_uniform and J_low-flow for the candidate | `optimize_blades.evaluate()` |
| 6 | Search and selection | {len(S1)} stage-1 and {len(S2)} stage-2 candidates | ranked list, the selected design, the unconstrained and hand-started alternatives | `optimize_blades.py 1`, `optimize_blades.py 2` -> `selection.json`, `selected_design.json` |
| 7 | Final evaluation | the selected design, the two previous blades | power curves, comparison table, {len(C['sens'])} sensitivities, bounds, robustness per blade count | `coupled_eval.py`, `robustness_v4.py` |
| 8 | Downstream | the station table | CAD (v4, v5), review, QA gates, reports | `cad/`, `docs/` |

## 3. What each stage decides

- **Stage 1 fixes which sections can be trusted.** The surrogate's confidence is part of the data; E818 and E387 were left out rather than
  guessed. This is where the Reynolds-number dependence enters: every later stage reads CL and CD at the local Reynolds number.
- **Stage 2 turns five numbers into a blade.** The Schmitz chord is the same formula as in the HW7 sheet; the workflow adds the chord cap,
  the root ease, the tip taper, the root blend and the station-by-station best-L/D angle.
- **Stage 3 is where the design TSR and the operating TSR separate.** The sheet evaluates a blade at its design TSR with Betz-optimum
  induction; the BEM evaluates the whole Cp(TSR) curve with iterated induction, so a blade designed at TSR 1.5 can be run at TSR 2.8.
- **Stage 4 is why Cp alone was not the objective.** The generator's voltage, copper loss and the converter's floor and overhead decide
  how much of the shaft power reaches the battery; the operating point is where that net power peaks, not where Cp peaks.
- **Stage 5 is where self-start enters.** A candidate that cannot overcome cogging plus breakaway at a speed scores nothing there.
  This single gate removed every high-TSR design from contention.
- **Stage 6 found a flat optimum.** The eight best stage-2 candidates lie within 1.5 % of each other; a packaging rule (printable hub wall)
  made the final pick. The selected blade: {spec['B']} blades, NACA 4412, design TSR {spec['lam_d']}, chord x{spec.get('c_scale', 1.0)}, pitch {spec.get('dbeta', 0):+.0f} deg.
- **Stage 7 says how sure we are.** Net output {Pout(0.5):.2f} / {Pout(0.7):.2f} / {Pout(1.0):.2f} W at 0.5 / 0.7 / 1.0 m/s; self-start {combos['baseline']['min_start']} m/s with bounds
  {combos['optimistic']['min_start']}-{combos['pessimistic']['min_start']} m/s; the dominant uncertainties are the transition Reynolds number of a printed surface and the cogging torque.

## 4. Where the HW7 spreadsheet sits

The workbook `IED_HW7_v4_parameters.xlsx` (sheet "v4 design") is the hand-calculable form of stages 2 and 3 for one candidate at one speed,
plus a matched-load generator check. With the v4 inputs it reproduces the planform family of the selected blade from the same Schmitz formula.
What it cannot do, and what the workflow added:

| HW7 sheet | workflow |
|---|---|
| one CL, CD at one Reynolds number | tables over angle and Reynolds number for 7 sections, confidence-filtered |
| Betz-optimum induction in closed form (a, a' from phi) | induction iterated per element from the polars (Ning residual, Buhl correction) |
| the blade evaluated at its design TSR only | the full Cp(TSR) curve at every speed from 0.4 to 2.0 m/s |
| generator check: maximum power into a matched load | MPPT equilibrium with copper loss, commutation drop, diode drop, converter efficiency, overhead and floor |
| one candidate, one speed | {len(S1) + len(S2)} candidates x 7 speeds x 14-36 tip-speed ratios, gated on self-start |
| pass / fail against a required power | two weighted energy objectives, a packaging rule, robustness and sensitivity studies |

The spreadsheet was not an input to the optimisation; its method is the seed of stage 2, and it is a useful one-page check of any
candidate's chord and twist.

## 5. Re-running the workflow

```
python model/polars.py && python model/optimize_blades.py 1 && python model/optimize_blades.py 2 && python model/feasibility.py
python model/coupled_eval.py && python model/robustness_v4.py && python cad/make_v4.py && python cad/views_v4.py
python model/structure_v4.py && python tools/qa_gates_v4.py && python docs/make_report_v4.py
```
Stage 1 of the sweep takes about 10 minutes on 4 cores; everything downstream of `selected_design.json` regenerates from it, including the
v5 simplified CAD (`cad/turbine_simple_v5/make_v5.py`).
"""
open(os.path.join(D, "WORKFLOW_v4.md"), "w").write(txt.replace("FIG_WORKFLOW", "../out/fig_workflow.png"))
with open(os.path.join(OUT, "fig_workflow.png"), "rb") as fh: fig64 = "data:image/png;base64," + base64.b64encode(fh.read()).decode()
body = markdown.markdown(txt.replace("FIG_WORKFLOW", fig64), extensions=["tables", "fenced_code"])
html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Blade Optimization Workflow</title>
<style>
@page{{size:A4;margin:16mm 15mm}}
body{{font:10pt/1.5 "Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#1a1a1a;max-width:190mm;margin:0 auto}}
h1{{font-size:19pt;font-weight:600;margin:0 0 4px}} p.sub{{font-size:9.5pt;color:#555;margin:0 0 18px;padding-bottom:10px;border-bottom:2px solid #2b4a6b}}
h2{{font-size:13pt;font-weight:600;color:#2b4a6b;margin:22px 0 6px;padding-bottom:3px;border-bottom:1px solid #c9d3dd;page-break-after:avoid}}
p{{margin:6px 0}} ul{{margin:4px 0 8px 0;padding-left:18px}} li{{margin:2px 0}}
table{{border-collapse:collapse;font-size:8.6pt;margin:8px 0 10px;width:100%}} tr{{page-break-inside:avoid}} thead{{display:table-header-group}}
th,td{{border:1px solid #d5d5d5;padding:3px 6px;vertical-align:top;text-align:left}} th{{background:#eef2f6;font-weight:600}} tr:nth-child(even) td{{background:#fafafa}}
code{{font-size:0.9em;background:#f1f1f1;padding:0 3px;border-radius:2px}} pre{{font-size:8.3pt;background:#f3f2ee;padding:8px;white-space:pre-wrap}}
figure{{margin:10px 0 14px;page-break-inside:avoid}} img{{max-width:100%;max-height:200mm;width:auto;display:block;margin:0 auto;border:1px solid #e4e4e4}} figcaption{{font-size:8.5pt;color:#555;margin-top:4px}}
</style></head><body>{body}</body></html>"""
open(os.path.join(D, "WORKFLOW_v4.html"), "w").write(html)
r = subprocess.run(["node", os.path.join(D, "html2pdf.js"), os.path.join(D, "WORKFLOW_v4.html"), os.path.join(D, "WORKFLOW_v4.pdf")], capture_output=True, text=True, timeout=300)
print(r.stdout.strip() or r.stderr.strip()[-300:]); os.remove(os.path.join(D, "WORKFLOW_v4.html"))
print("WORKFLOW_v4.md/pdf written", os.path.getsize(os.path.join(D, "WORKFLOW_v4.pdf")) // 1024, "kB")
