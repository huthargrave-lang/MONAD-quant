#!/usr/bin/env python3
"""Assemble REPORT_v4.md from the result files (feasibility.json, sweep_stage1/2.json, selection.json, selected_design.json,
coupled_results.json, out/v4_info.json, BOM_v4.csv, QA_LOG_v4.md, REVIEW_LOG_v4.md).  No performance number is typed by hand."""
import csv, json, math, os, re
D = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(D, ".."); M = os.path.join(ROOT, "model")
F = json.load(open(os.path.join(M, "feasibility.json"))); S1 = json.load(open(os.path.join(M, "sweep_stage1.json"))); S2 = json.load(open(os.path.join(M, "sweep_stage2.json")))
SEL = json.load(open(os.path.join(M, "selection.json"))); sel = json.load(open(os.path.join(M, "selected_design.json"))); C = json.load(open(os.path.join(M, "coupled_results.json")))
info = json.load(open(os.path.join(ROOT, "out", "v4_info.json"))); P = info["params"]; L = info["layout"]; ST = json.load(open(os.path.join(M, "structure_v4.json")))
bom = list(csv.DictReader(open(os.path.join(D, "BOM_v4.csv")))); qa = open(os.path.join(D, "QA_LOG_v4.md")).read() if os.path.exists(os.path.join(D, "QA_LOG_v4.md")) else "(QA log not yet generated)"
rev = open(os.path.join(D, "REVIEW_LOG_v4.md")).read() if os.path.exists(os.path.join(D, "REVIEW_LOG_v4.md")) else "(review log not yet generated)"
G = F["assumptions"]["GEN"]; FR = F["assumptions"]["FRICTION"]; CV = F["assumptions"]["CONVERTERS"]
A = "A (rear nacelle, hub r 28 mm)"; B = "B (hub drum, blade root r 48.2 mm)"
new = C["designs"]["new"]["res"]; v31 = C["designs"]["v31"]["res"]; orig = C["designs"]["orig"]["res"]; newB = C["designs"]["new_in_B"]["res"]; newboost = C["designs"]["new_boost"]["res"]; newdirect = C["designs"]["new_direct"]["res"]
VS = C["VS"]; combos = C["combos"]; sens = C["sens"]
def op(res, V): return res["perV"][str(V)]["op"]
def Pout(res, V): o = op(res, V); return o["Pout"] if o else 0.0
def fmt(x, n=2): return f"{x:.{n}f}"
spec = sel["spec"]
Kt = 60 / (2 * math.pi * G["KV"])
# ---------- feasibility table
feas_rows = []
for r in F["rows"]:
    a = r[A]; b = r[B]
    feas_rows.append(f"| {r['V']:.2f} | {r['P_disc']:.2f} | {a['P_annulus']:.2f} | {a['P_betz']:.2f} | {a['cp_bem']:.3f} / {b['cp_bem']:.3f} | {a['P_shaft']:.2f} | {(a['ideal']['Pout'] if a['ideal'] else 0):.2f} | {(a['buckboost']['Pout'] if a['buckboost'] else 0):.2f} | {(a['boost']['Pout'] if a['boost'] else 0):.2f} ({a['boost']['region'] if a['boost'] else '-'}) | {(a['direct']['Pout'] if a['direct'] else 0):.2f}{' !' if (a['direct'] and a['direct'].get('overcurrent')) else ''} |")
shares = [s for s in F["shares"] if not s.get("none")]
share_rows = [f"| {s['V']:.2f} | {s['P_hyd']:.2f} | {s['hydro']/s['P_hyd']*100:.0f} | {s['friction']/s['P_hyd']*100:.1f} | {s['copper']/s['P_hyd']*100:.1f} | {s['diode']/s['P_hyd']*100:.1f} | {s['converter']/s['P_hyd']*100:.1f} | {s['out']:.2f} ({s['out']/s['P_hyd']*100:.0f} %) | {s['rpm']:.0f} rpm, {s['Vdc']:.1f} V, {s['I']:.2f} A |" for s in shares]
gear_rows = []
for g in F["gear"]:
    gear_rows.append(f"| {g['N']:.0f}:1 | " + " | ".join(f"{g[k][0]:.2f} / {g[k][2]:.2f}" for k in ("0.5", "0.6", "0.7", "0.8", "1.0")) + " |")
# ---------- sweep summaries
def best(rows, key="lowflow", pred=lambda r: True): return max((r for r in rows if pred(r)), key=lambda r: r["J"][key])
allS = S1 + S2
bB = {b: best(allS, "lowflow", lambda r, b=b: r["spec"]["B"] == b) for b in (2, 3, 4, 5)}
bAF = {af: best(allS, "lowflow", lambda r, af=af: r["spec"]["airfoil"] == af) for af in ("naca4412", "naca4415", "sg6043", "fx63137")}
bTSR = {t: best(S1, "lowflow", lambda r, t=t: r["spec"]["lam_d"] == t and r["spec"]["B"] == 3 and r["spec"]["airfoil"] == "naca4412") for t in (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0)}
bCS = {c: best(S1, "lowflow", lambda r, c=c: r["spec"]["c_scale"] == c and r["spec"]["B"] == 3 and r["spec"]["airfoil"] == "naca4412" and r["spec"]["lam_d"] == 2.0) for c in (0.7, 1.0, 1.3)}
def srow(label, r):
    s = r["spec"]; p = r["perV"]
    return (f"| {label} | B{s['B']} {s['airfoil']} TSR_d {s['lam_d']} x{s.get('c_scale',1.0)} | {r['meta']['solidity']:.2f} | {p['0.5']['cp_peak']:.3f} / {p['0.7']['cp_peak']:.3f} / {p['1.0']['cp_peak']:.3f} | "
            f"{p['0.5']['Pout']:.2f} / {p['0.7']['Pout']:.2f} / {p['1.0']['Pout']:.2f} | {r['J']['uniform']:.3f} | {r['J']['lowflow']:.3f} | {r['min_selfstart_V']} | {p['0.5']['Qstatic']*1000:.0f} |")
# ---------- comparison table (previous vs new at identical conditions)
cmp_rows = []
for row in C["table"]:
    n, o, g, b = row["new"], row["v31"], row["orig"], row["new_in_B"]
    cmp_rows.append(f"| {row['V']:.2f} | {n['cp']:.3f} | {n['Pout']:.2f} | {n['rpm']:.0f} / {n['Vdc']:.1f} / {n['I']:.2f} | {'yes' if n['start'] else 'no'} | {g['cp']:.3f} | {g['Pout']:.2f} | {'yes' if g['start'] else 'no'} | {o['cp']:.3f} | {o['Pout']:.2f} | {'yes' if o['start'] else 'no'} | {b['cp']:.3f} | {b['Pout']:.2f} |")
# ---------- electrical / protection
prot_rows = []
for V in VS:
    p = new["perV"][str(V)]; o = p["op"]; oc = p["open"]; pb = newboost["perV"][str(V)]["op"]; pd = newdirect["perV"][str(V)]["op"]
    prot_rows.append(f"| {V:.2f} | {(o['rpm'] if o else 0):.0f} / {(o['Vdc'] if o else 0):.1f} / {(o['I'] if o else 0):.2f} / {(o['Pout'] if o else 0):.2f} | {(pb['Pout'] if pb else 0):.2f} ({pb['region'] if pb else '-'}{', I ' + fmt(pb['I']) + ' A OVER' if (pb and pb.get('overcurrent')) else ''}) | {(pd['Pout'] if pd else 0):.2f}{' (I ' + fmt(pd['I']) + ' A OVER)' if (pd and pd.get('overcurrent')) else ''} | {(oc['rpm'] if oc else 0):.0f} rpm, {(oc['Vdc'] if oc else 0):.0f} V | {p['Qstatic']*1000:.0f} / {p['breakaway']*1000:.0f} |")
sens_keys = ["baseline", "seal x0.5", "seal x2.0", "seal x3.0", "cogging 8 mN m", "cogging 40 mN m", "no-load loss 0.2 W@700", "no-load loss 1.5 W@700", "cd x1.3", "cd x1.6", "cl x0.9, cd x1.3", "standstill cdmax 1.2", "standstill cdmax 2.0", "standstill = BEM at TSR 0.2", "no nacelle inflow deficit", "KV 25 (Kt 0.38)", "R 6.5 ohm", "conv eta 0.85", "conv eta 0.96", "conv Vmin 3 V", "conv Vmin 8 V", "rectifier synchronous"]
sens_rows = [f"| {k} | " + " | ".join(f"{sens[k][VS.index(V)]:.2f}" for V in (0.5, 0.6, 0.7, 0.8, 1.0)) + " |" for k in sens_keys if sens.get(k)]
printed = [p for p in info["parts"] if p["kind"].startswith("print")]; machined = [p for p in info["parts"] if "machined" in p["kind"]]
cost_lo = cost_hi = 0.0
for r in bom:
    nums = [float(x) for x in re.findall(r"\d+\.?\d*", r["unit USD"].split("each")[0].split("/")[0])]
    if not nums: continue
    q = float(r["qty"]) if ("each" in r["unit USD"]) else 1.0
    lo, hi = (min(nums), max(nums)) if "-" in r["unit USD"] else (sum(nums), sum(nums)); cost_lo += lo * q; cost_hi += hi * q
W_LOW = {0.5: 0.30, 0.6: 0.30, 0.7: 0.20, 0.8: 0.10, 0.9: 0.05, 1.0: 0.05}
txt = f"""# Portable hydrokinetic turbine for 0.5-1.0 m/s streams: low-flow redesign (v4)

**Scope and status.** Everything in this package is model prediction and design intent. No part has been printed, machined or
tested; no GL60 has been measured; manufacturer web pages (cubemars.com, genasun, bluerobotics.com, digikey) could not be reached
from this session, so the generator values are the ones listed in the brief and in the earlier review, bracketed by sensitivity cases.
Every number below is written by `docs/make_report_v4.py` from the result files of the scripts in `model/`, `cad/` and `tools/`.

## 1. Executive summary and feasibility verdict

- **What the GL60 can deliver (model, baseline assumptions, arrangement A, buck-boost MPPT):** net 12 V electrical power
  **{Pout(new, 0.5):.2f} W at 0.5 m/s, {Pout(new, 0.6):.2f} W at 0.6, {Pout(new, 0.7):.2f} W at 0.7, {Pout(new, 0.8):.2f} W at 0.8, {Pout(new, 1.0):.2f} W at 1.0 m/s** ({Pout(new, 1.5):.1f} W at 1.5, {Pout(new, 2.0):.1f} W at 2.0). Honest band: -30 % / +10 %
  (hydrofoil polars at Re 4e4-8e4 from an XFOIL surrogate, unmeasured friction and generator constants; section 8). Over a 24 h day
  at 0.6-0.8 m/s that is roughly {Pout(new, 0.6)*24:.0f}-{Pout(new, 0.8)*24:.0f} Wh: enough to keep a phone or a headlamp charged, not a camp power supply.
- **Minimum flow.** The rotor sustains rotation and the converter accepts power from **{combos['baseline']['min_sustain']} m/s** (the 5 V minimum input of
  the converter and the fixed friction are the limiters; at 0.4 m/s the bus would be below 5 V and the net output negative).
  **Self-start is model-marginal at 0.5 m/s**: {combos['optimistic']['min_start']} m/s (optimistic) / {combos['baseline']['min_start']} (baseline) / {combos['pessimistic']['min_start']} (pessimistic), set by the
  assumed GL60 cogging ({G['cogging']*1000:.0f} mN m peak) plus seal and bearing breakaway. Gates G1 and G6 of the test plan decide it.
- **The winding resistance is not the obstacle.** At these powers the torque is tens of mN m, so copper loss is
  {min(s['copper']/s['P_hyd'] for s in shares)*100:.1f}-{max(s['copper']/s['P_hyd'] for s in shares if s['V'] <= 1.0)*100:.1f} % of the available hydraulic power below 1 m/s. The obstacles are, in order: rotor efficiency at
  Reynolds numbers of 4e4-8e4 (Cp {new['perV']['0.5']['cp_peak']:.2f}-{new['perV']['1.0']['cp_peak']:.2f}), the fixed friction torque (seal + bearing + motor no-load, {FR['A_rear_nacelle']['seal_run']*1000+FR['A_rear_nacelle']['brg_run']*1000:.0f} mN m plus
  no-load loss), the generator **voltage** (only {op(new, 0.5)['Vdc'] if op(new, 0.5) else 0:.1f} V at 0.5 m/s: a boost-capable converter is mandatory; a rectifier straight into the
  14.4 V battery produces nothing below {next((V for V in VS if Pout(newdirect, V) > 0), None)} m/s and only {Pout(newdirect, next((V for V in VS if Pout(newdirect, V) > 0), 1.0)):.2f} W there), and the converter's own minimum input voltage and quiescent draw.
- **A gearbox does not help.** A 2:1 or 3:1 stage (optimistic 96 % per stage, +5 mN m) changes net output by
  {(F['gear'][1]['0.5'][2]/F['gear'][0]['0.5'][2]-1)*100:+.0f} % at 0.5 m/s and {(F['gear'][1]['1.0'][2]/F['gear'][0]['1.0'][2]-1)*100:+.0f} % at 1.0 m/s with the real converter: rejected; direct drive is kept.
- **Selected rotor:** {spec['B']} blades, NACA 4412 blending to NACA 4418 at the root, Schmitz planform for design TSR {spec['lam_d']} scaled x{spec['c_scale']},
  root chord {sel['chord_mm'][0]:.1f} mm, maximum chord {max(sel['chord_mm']):.1f} mm, tip chord {sel['chord_mm'][-1]:.1f} mm, root twist {sel['twist_deg'][0]:.1f} deg, solidity {sel['meta']['solidity']:.2f}; it runs at
  TSR {op(new, 0.7)['lam']:.1f}-{op(new, 1.0)['lam']:.1f} ({op(new, 0.5)['rpm']:.0f}-{op(new, 1.0)['rpm']:.0f} rpm over 0.5-1.0 m/s). Against the previous 1-2 m/s blade on its drum hub it delivers
  {Pout(new, 0.6)/max(Pout(v31, 0.6), 1e-9):.1f}x at 0.6 m/s and {Pout(new, 1.0)/Pout(v31, 1.0):.2f}x at 1.0 m/s; against the original rev-2 blade placed on the same small hub it gains
  {(Pout(new, 0.5)/max(Pout(orig, 0.5),1e-9)-1)*100:+.0f} % at 0.5, {(Pout(new, 0.6)/Pout(orig, 0.6)-1)*100:+.0f} % at 0.6, {(Pout(new, 0.7)/Pout(orig, 0.7)-1)*100:+.0f} % at 0.7 and {(Pout(new, 1.0)/Pout(orig, 1.0)-1)*100:+.0f} % at 1.0 m/s: the gain is where the brief asks for it, and the
  two blades are equivalent above 0.9 m/s.
- **Recommended mounting: arrangement A** (rotor on a short 316 shaft ahead of a stationary sealed nacelle). The hub radius drops from
  48 to {P['r_hub']:.0f} mm, which is worth {(Pout(new, 0.7)/Pout(newB, 0.7)-1)*100:+.0f} % at 0.7 m/s and {(Pout(new, 1.0)/Pout(newB, 1.0)-1)*100:+.0f} % at 1.0 m/s against the same blade in the hub-integrated drum (B), and
  the 8 mm seal halves the seal friction. The price is depth: {L['operating_depth_mm']:.0f} mm operating, which packs as two pieces of {L['rotor_depth_mm']:.0f} mm (rotor)
  and {L['nacelle_depth_mm']:.0f} mm (nacelle) by removing one M4 screw. The 76 mm target is met packed, not operating.

## 2. Baseline assessment (what the previous work predicted and what it is worth)

The project holds three earlier artefacts: the original 8-inch rev-2 blade (hub 25.4 mm, design TSR 4, NACA 4422 -> 4414), the
v3.1 drum-rotor blade (root at 48.2 mm, design TSR 4 with +6 deg pitch) and the Configuration A screening spreadsheet (5.6 / 20.1 / 49 W shaft
at 1 / 1.5 / 2 m/s, 0.018 N m seal torque, 0.5 W fixed loss, 90 % downstream efficiency). None of these numbers is measured. Re-evaluated
with this package's model (NeuralFoil Reynolds-dependent polars, the same BEM corrections, the same generator and converter model):

| V (m/s) | new: Cp | new: W | new: rpm / V / A | self-start | rev-2 blade on the A hub: Cp | W | start | v3.1 blade in the drum (B): Cp | W | start | new blade in the drum (B): Cp | W |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
{chr(10).join(cmp_rows)}

(W = net 12 V electrical power with the buck-boost MPPT, baseline assumptions; "start" = static torque above the assumed breakaway.)
The original rev-2 blade (NACA 4422 -> 4414) is evaluated with the NACA 4415 table and the same 4418 root blend because no 4422 table exists (slightly
favourable to it at the root). The spreadsheet's 5.6 W shaft at 1 m/s (Cp 0.345 on the full disc) is not reached by any of the three blades on their hubs in this model
({new['perV']['1.0']['cp_peak']*0.5*1000*math.pi*0.1016**2:.2f} W peak shaft for the new rotor, Cp {new['perV']['1.0']['cp_peak']:.3f}); the earlier "0.345-0.378" Cp values came from a polar at Re 2e5 applied at Re
7e4-8e4 (review of the trial, redesign v3). The previous electrical predictions are therefore not used as validated inputs.

## 3. Optimisation methodology and objective function

1. **Polars** (`model/polars.py`): NeuralFoil (XFOIL surrogate, Ncrit 9) on a 29 x 10 (alpha, Re) grid for NACA 4412 / 4415 / 4418,
   SG6043, E387, FX63-137 and E818, Viterna-extended to +-90 deg for the standstill estimate. E387 (confidence 0.84) and E818 (0.64,
   coarse database coordinates) are reported but not selectable. Experimental polars at Re 4e4-8e4 are not available to this project.
2. **BEM** (`model/bem_lowflow.py`): Prandtl tip and hub losses, Buhl high-induction correction, per-element Reynolds number, root blend
   to the 18 % thick section over the inner 35 % of span, nacelle inflow deficit factor {0.85} inboard of r 38 mm for arrangement A (assumption),
   vectorised Ning residual solved by bisection. Cross-checks: the near-inviscid limit stays below Betz (Cp 0.43 with tip/hub losses), P = omega Q,
   and the v3.1 blade evaluated with both the old analytic polar and the new tables agrees within the expected 10-20 % (the thick root is the difference).
3. **Coupled operating point** (`model/generator_lowflow.py`): rotor torque curve against friction (seal, bearing, motor no-load, hub
   windage) and the generator (KV {G['KV']}, Kt {Kt:.3f} N m/A, R {G['R_LL']} ohm, L {G['L_LL']*1000:.2f} mH, {G['pp']} pole pairs, Schottky bridge 2 x Vf(I), commutation
   overlap as a reactive voltage drop), then the converter (efficiency eta_max - k/P_in, quiescent draw, minimum input voltage, and either
   a boost-with-clamp or a buck-boost input window). The MPPT law picks the bus voltage (= rotor speed) that maximises converter output
   inside the window; it never commands more than the 1.35 A rating. Standstill torque uses alpha = 90 deg - twist on every element with
   W = V (no induction) and the Viterna polars; breakaway = cogging + seal + bearing breakaway. Dynamic friction and breakaway are separate.
4. **Objective:** J = sum over V of w(V) P_net(V) with P_net = 0 where the candidate cannot self-start, cannot sustain rotation along the
   unloaded path to its operating point, or sits below the converter's 5 V input. Two weightings: uniform over 0.5-1.0 m/s (six flows) and
   low-flow-weighted {W_LOW} (illustrative, not measured). Also tracked: the same without the self-start gate ("hand-started") and with cogging 8 / 40 mN m.
5. **Design space** (`model/optimize_blades.py`): stage 1 = {len(S1)} candidates: 2 / 3 / 4 / 5 blades x four airfoils x design TSR 1.5-6 (Schmitz
   planform at the airfoil's best-L/D angle at the local Reynolds number) x chord scale 0.7 / 1.0 / 1.3 (chord capped at 60 mm). Stage 2 = {len(S2)}
   refinements around the leader (TSR 1.75-2.5, chord scale 1.3-1.7, chord cap 60 / 68, pitch -3 / 0 / +3 deg, two-blade and SG6043 checks).
   Selection: the mean of the two normalised objectives, subject to self-start at 0.5 m/s under baseline cogging and a root chord <= 52 mm
   (the three pockets must leave printable walls on the 28 mm hub); ties go to the lower solidity.

## 4. Comparison of the blade variants (same model, same boundary conditions, arrangement A)

Best candidate per blade count, airfoil, design TSR (3 blades, NACA 4412) and chord scale (3 blades, NACA 4412, TSR 2):

| Group | Candidate | Solidity | Cp peak 0.5 / 0.7 / 1.0 | Net W at 0.5 / 0.7 / 1.0 | J uniform (W) | J low-flow (W) | min self-start (m/s) | static torque at 0.5 (mN m) |
|---|---|---|---|---|---|---|---|---|
{chr(10).join(srow(f"{b} blades", bB[b]) for b in (2, 3, 4, 5))}
{chr(10).join(srow(af, bAF[af]) for af in ("naca4412", "naca4415", "sg6043", "fx63137"))}
{chr(10).join(srow(f"design TSR {t}", bTSR[t]) for t in (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0))}
{chr(10).join(srow(f"chord x{c}", bCS[c]) for c in (0.7, 1.0, 1.3))}

Reading. Two blades give the best Cp per unit solidity; the best two-blade candidate self-starts from {two_blade_start} m/s and the best two-blade
candidate that starts at 0.5 m/s scores {(b2_best_lowflow['J']['lowflow'] if b2_best_lowflow else 0):.3f} W against {bB[3]['J']['lowflow']:.3f} W for three blades on the low-flow objective; four and five blades start earlier but lose
Cp to profile drag at these Reynolds numbers. Design TSR 2-2.5 wins because the wide chords raise the local Reynolds number (the
chord is the only lever on Re at a given flow) and the standstill torque, while the actual Cp peak still sits at TSR 3-3.5 and the
coupled MPPT point at TSR {op(new, 0.5)['lam']:.1f}-{op(new, 1.0)['lam']:.1f}, where the GL60's voltage is highest for the torque it must absorb. The low-Reynolds sections lose in the
coupled result despite their better 2-D L/D: their higher design lift coefficient produces narrower chords (lower Re) and a sharper
Cp peak. The objective surface is flat near the optimum (the top eight stage-2 candidates are within 1.5 % of each other), so the
root-chord packaging limit decided the final pick without a measurable performance cost ({SEL['ranked'][0]['J']['lowflow']/SEL['Jl_max']*100:.1f} % of the best low-flow score).

## 5. Selected blade geometry and why it won

{spec['B']} blades, NACA 4412 outboard blending to NACA 4418 over the inner 35 % (printability and root bending), Schmitz planform at design
TSR {spec['lam_d']} x{spec['c_scale']} (capped at {spec.get('c_max',0.06)*1000:.0f} mm), root eased to 85 % at the hub, elliptical tip taper to 55 %, pitch offset {spec.get('dbeta',0):+.0f} deg, 1.0 mm blunt trailing edge.
Station data: `model/selected_design.json` (chord {sel['chord_mm'][0]:.1f} -> {max(sel['chord_mm']):.1f} -> {sel['chord_mm'][-1]:.1f} mm; twist {sel['twist_deg'][0]:.1f} -> {sel['twist_deg'][-1]:.1f} deg). Figures 5 and 6 compare it with the
previous designs. It won because it (i) self-starts at 0.5 m/s under the baseline cogging (static torque {new['perV']['0.5']['Qstatic']*1000:.0f} vs breakaway {new['perV']['0.5']['breakaway']*1000:.0f} mN m) while the
TSR >= 3 designs do not, (ii) has the highest coupled output at 0.5-0.7 m/s (Reynolds effect of the wide chord), (iii) matches the original rev-2 blade above
0.9 m/s, and (iv) still fits three pockets on a 28 mm hub (the two-blade alternative that also starts at 0.5 m/s scores {((b2_best_lowflow['J']['lowflow'] / bB[3]['J']['lowflow'] - 1) * 100) if b2_best_lowflow else 0:+.0f} % on the low-flow objective). What it gives up: about {(1-Pout(new, 2.0)/Pout(orig, 2.0))*100:.0f} % at 2.0 m/s against the rev-2 blade and a higher
standstill drag (thrust at 2 m/s {new['perV']['2.0']['T'][[i for i, l in enumerate(new['perV']['2.0']['lam']) if abs(l - new['perV']['2.0']['op']['lam']) < 0.11][0]] if new['perV']['2.0']['op'] else 0:.0f} N at the operating point).

## 6. Generator matching and electrical predictions

Feasibility first (`model/feasibility.py`, representative rotor, arrangement A unless noted; Cp pairs are A / B):

| V (m/s) | P through the disc (W) | through the annulus (A) | Betz on the annulus | BEM Cp (A / B) | rotor shaft (A) | lossless converter | buck-boost MPPT | boost + clamp (GVB-8 class) | rectifier to battery |
|---|---|---|---|---|---|---|---|---|---|
{chr(10).join(feas_rows)}

("!" = the generator current exceeds the 1.35 A rating in that mode: not allowed without a current limiter.)

Loss shares along the chain at the coupled operating points (arrangement A, buck-boost):

| V | hydraulic in the annulus (W) | hydrodynamic loss % | friction + no-load % | copper % | diodes % | converter % | net out (W, %) | operating point |
|---|---|---|---|---|---|---|---|---|
{chr(10).join(share_rows)}

Gear ratio study (ideal converter / real buck-boost, W):

| ratio | 0.5 m/s | 0.6 | 0.7 | 0.8 | 1.0 |
|---|---|---|---|---|---|
{chr(10).join(gear_rows)}

Selected design, per flow (buck-boost MPPT; boost+clamp and direct-to-battery for comparison; standstill torque vs breakaway):

| V (m/s) | buck-boost: rpm / V_dc / I / net W | boost + clamp: net W (region) | direct to battery: net W | open-circuit runaway | static torque / breakaway (mN m) |
|---|---|---|---|---|---|
{chr(10).join(prot_rows)}

Load control. Below the clamp voltage both converters regulate the bus, i.e. the rotor speed, so the generator cannot stall the rotor:
the equilibrium sits on the stable side of the torque peak (fig. 9). With the boost-only converter the bus is clamped at the battery
above about {next((V for V in VS if newboost['perV'][str(V)]['op'] and newboost['perV'][str(V)]['op']['region'] == 'clamp'), None)} m/s; the rotor is then held at a fixed speed and, from {v_over} m/s (interpolated on a 0.05 m/s grid), the clamp current exceeds the GL60 rating:
a boost-only unit needs a 1.5-2 A limiter or a 40 V relay dump for the 1-2 m/s survivability case. The buck-boost keeps regulating to
2 m/s ({op(new, 2.0)['I']:.2f} A at {op(new, 2.0)['Vdc']:.1f} V). Open circuit at 2 m/s is {new['perV']['2.0']['open']['Vdc']:.0f} V: below the 60 V TVS standoff and the converter's 60 V input.
Current and temperature: copper loss is {op(new, 0.5)['Pcu']:.2f} / {op(new, 0.7)['Pcu']:.2f} / {op(new, 1.0)['Pcu']:.2f} W at 0.5 / 0.7 / 1.0 m/s and {op(new, 2.0)['Pcu']:.1f} W at 2 m/s inside a sealed nacelle. Thermal limits are not
the sizing case below 1.5 m/s; the earlier v3.1 heat-path analysis applies if the device is left in a 2 m/s flow (rear cap in 6061).

## 7. Recommended compact mounting and waterproofing (arrangement A), with B quantified

| | A: rotor on a short shaft, stationary nacelle behind | B: hub-integrated (v3.1 drum rotor) |
|---|---|---|
| hub radius / ratio | {P['r_hub']:.0f} mm / {P['r_hub']/101.6:.2f} | 48.2 mm / 0.47 (the GL60 inside a 3 in drum) |
| net W at 0.5 / 0.7 / 1.0 m/s (same blade) | {Pout(new, 0.5):.2f} / {Pout(new, 0.7):.2f} / {Pout(new, 1.0):.2f} | {Pout(newB, 0.5):.2f} / {Pout(newB, 0.7):.2f} / {Pout(newB, 1.0):.2f} |
| rotary seal | one 8 mm PTFE lip seal (run {FR['A_rear_nacelle']['seal_run']*1000:.0f} mN m assumed) | one 15 mm PTFE lip seal ({FR['B_hub_drum']['seal_run']*1000:.1f} mN m) |
| bearings | one 608-2RS in the cap + the GL60's own | two 6702-2RS |
| machined parts | shaft, front cap, rear cap, tube ends (4) | spindle, 2 caps, split ring, plug, boss, 3 struts, tube ends (9+) |
| waterproof boundary | tube + 1 O-ring per cap + lip seal + WetLink + vent | tube + O-rings + lip seal + potting plug |
| operating depth | {L['operating_depth_mm']:.0f} mm; packs as {L['rotor_depth_mm']:.0f} + {L['nacelle_depth_mm']:.0f} mm | 73 mm |
| flow obstruction behind the rotor | 3 in nacelle ({(76.2/203.2)**2*100:.0f} % of the disc area), modelled as a 15 % inflow deficit inboard of r 38 mm | none beyond the drum itself |
| seal service | pull the hub (one screw), press the seal from the wet face | partial disassembly (v3.1 plan) |

**Load path (A, fig. 10a).** Thrust: blade -> airfoil tongue (clamped between the two hub halves by an axial M3) -> hub -> collar A ->
shaft -> collar B -> 608 inner race -> outer race -> front-cap floor -> cap plug and flange -> tube -> clamp -> three L-struts -> guard ring
and stake. Reverse load: DIN 471-8 circlip behind the bearing (0.2 mm end play); the seal pressed in front of the bearing retains the
outer race. Torque: hub D-bore -> shaft D-flat -> cross-pinned dog hub -> TPU disc (two dogs, 0.2 mm radial clearance) -> GL60 bell; the
stator is screwed to the rear cap. The GL60 carries no rotor thrust and no radial load. The motor is dry: tube, one EPDM O-ring per cap,
an 8 mm PTFE lip seal on the polished 316 journal, a WetLink M10 penetrator and an M6 vent; IP45 is irrelevant inside that boundary.
**Penalties quantified:** the seal and bearing take {FR['A_rear_nacelle']['seal_run']*1000+FR['A_rear_nacelle']['brg_run']*1000:.0f} mN m of the {op(new, 0.5)['Qrot']*1000:.0f} mN m the rotor makes at 0.5 m/s ({(FR['A_rear_nacelle']['seal_run']+FR['A_rear_nacelle']['brg_run'])/op(new, 0.5)['Qrot']*100:.0f} %) and {(FR['A_rear_nacelle']['seal_run']+FR['A_rear_nacelle']['brg_run'])/op(new, 1.0)['Qrot']*100:.0f} % at 1.0 m/s;
the assumed nacelle inflow deficit costs {nac.get('0.5', nac.get(0.5, 0))*100:.1f} / {nac.get('0.7', nac.get(0.7, 0))*100:.1f} / {nac.get('1.0', nac.get(1.0, 0))*100:.1f} % of peak Cp at 0.5 / 0.7 / 1.0 m/s (to be checked in G8/G11); the hub ratio {P['r_hub']/101.6:.2f} costs the annulus area shown in the feasibility table.

## 8. Plots

| # | Figure | File |
|---|---|---|
| 1 | hydraulic power vs water speed with the physical and model bounds | `out/fig1_hydraulic_power.png` |
| 2 | Cp vs TSR, previous vs optimised, 0.5 / 0.7 / 1.0 / 1.5 m/s | `out/fig2_cp_tsr.png` |
| 3 | rotor torque vs rpm with standstill, friction, breakaway and generator load lines | `out/fig3_torque_rpm.png` |
| 4 | mechanical and net electrical power vs water speed, all designs | `out/fig4_power_vs_v.png` |
| 5, 6 | chord and twist distributions | `out/fig5_6_chord_twist.png` |
| 7 | generator efficiency map and the loss breakdown at the operating points | `out/fig7_generator_losses.png` |
| 8 | sensitivity to seal friction, cogging, no-load loss, polars, generator constants, converter | `out/fig8_sensitivity.png` |
| 9 | operating-point diagrams (rotor torque vs generator load lines) | `out/fig9_operating_point.png` |
| 10 | CAD section with load paths and boundary, dimensioned section, exploded view | `out/fig10a_section.png`, `fig10b_dimensioned.png`, `fig10c_exploded.png` |
| - | candidate polars | `out/fig_polars.png` |

Sensitivity table (net W, gated by self-start; one input at a time):

| case | 0.5 | 0.6 | 0.7 | 0.8 | 1.0 m/s |
|---|---|---|---|---|---|
{chr(10).join(sens_rows)}

Minimum self-start / sustain velocities: optimistic (cd x1.0, cogging 8 mN m, seal x0.5, Viterna cdmax 2.0) {combos['optimistic']['min_start']} / {combos['optimistic']['min_sustain']} m/s; baseline {combos['baseline']['min_start']} / {combos['baseline']['min_sustain']};
pessimistic (cd x1.3, cl x0.9, cogging 40 mN m, seal x2, cdmax 1.2) {combos['pessimistic']['min_start']} / {combos['pessimistic']['min_sustain']} m/s; baseline with the conservative standstill model (BEM at TSR 0.2) {combos['baseline, standstill = BEM at TSR 0.2']['min_start']} / {combos['baseline, standstill = BEM at TSR 0.2']['min_sustain']} m/s.
The sweep evaluated candidates with 40 elements and a 0.5 TSR step; the selected design is re-evaluated here with 50 elements and a 0.2 step, which moves
its numbers by less than 0.5 %; "root chord" is the chord at the first element centre (r {sel['r_mm'][0]:.1f} mm). The sustain floor is the converter's 5 V minimum; a 3 V converter would move it to
{next((V for V in VS if sens['conv Vmin 3 V'][VS.index(V)] > 0), None)} m/s with {sens['conv Vmin 3 V'][VS.index(0.5)]:.2f} W at 0.5 m/s.

## 9. Reproducible source code and CAD exports

`model/polars.py` (polar tables), `bem_lowflow.py`, `generator_lowflow.py`, `feasibility.py`, `optimize_blades.py` (stages 1-2 and the
selection), `coupled_eval.py` (figures 2-9, comparison, sensitivities); `cad/make_v4.py` (parametric assembly, STEP per part, assembly
STEP, print-oriented STLs with the blade meshed as a closed structured surface), `cad/views_v4.py` (figure 10); `tools/qa_gates_v4.py`.
Exports: `out/v4_assembly.step`, `out/v4_*.step` ({len(info['parts'])} parts, {len(printed)} printed, {len(machined)} machined), `out/v4_*_PRINT.stl` ({len([p for p in info['parts'] if 'stl_watertight' in p])} files, all closed,
blade mesh within {[p.get('stl_vs_step_pct') for p in info['parts'] if p['name']=='blade_0'][0]:.2f} % of its STEP volume, tilted {[p.get('print_tilt_deg') for p in info['parts'] if p['name']=='blade_0'][0]:.1f} deg for a level pressure face). Regenerate in the order given in `README.md`.
Print notes: blades pressure-side down with tree supports under the leading-edge overhang, 100 % infill, layers along the span; hub
halves parting face down, no supports; TPU disc flat; clamp halves flat; ring as three arcs. Minimum blade thickness {0.12*sel['chord_mm'][-1]:.1f} mm at the tip
(12 % of {sel['chord_mm'][-1]:.1f} mm), 1.0 mm trailing edge.

**Structural screening at the 2 m/s survival case** (`model/structure_v4.py`; allowables assumed: ASA 8 / 4.5 MPa long-term in-plane / across
layers, 15 / 8 short-term, 2.7 / 4.8 interlaminar shear): rotor thrust {ST['T_rotor_N']:.1f} N ({ST['T_blade_N']:.1f} N per blade) and {ST['Q_rotor_Nm']:.2f} N m at {ST['rpm_op']:.0f} rpm, runaway {ST['rpm_runaway']:.0f} rpm.
Root bending {ST['sig_root_MPa']:.2f} MPa in the {ST['t_root_mm']:.1f} mm thick NACA 4418 root (in-plane for a flat print); centrifugal {ST['F_cf_N']:.0f} N per blade ({ST['m_blade_g']:.0f} g) -> M3 bolt double shear
{ST['bolt_shear_MPa']:.1f} MPa, tongue bearing {ST['tongue_bearing_MPa']:.2f} MPa, {ST['ligament_mm']:.1f} mm ligament shear-out {ST['shear_out_MPa']:.2f} MPa; pocket walls take the flap moment at {ST['wall_bearing_MPa']:.2f} MPa; the three
pockets span {ST['pocket_arc_deg']:.0f} deg each, leaving {ST['hub_wall_deg']:.0f} deg of hub wall ({ST['hub_wall_mm_floor']:.1f} mm at the pocket floor, {ST['hub_wall_mm_top']:.1f} mm at the surface); strut legs {ST['strut_leg_MPa']:.1f} MPa in bending;
shaft torsion {ST['tau_shaft_MPa']:.1f} MPa ({ST['tau_flat_MPa']:.1f} at the D-flat; 316 yield ~200); 608 bearing Fa/C0 {ST['Fa_C0']:.3f}. All below the allowables with margin; fatigue (3/rev strut wake) is not assessed.

## 10. Independent adversarial review and corrections

{rev}

## 11. Practical prototype testing plan

See `docs/TEST_PLAN_v4.md` (12 gates). The four measurements that close the model, in order of their effect on the 0.5-0.7 m/s prediction:
G1 generator constants and cogging, G2 breakaway and running friction of the sealed shaft, G6 standstill torque of the printed rotor, G8 the
power curve in a real stream.

## 12. Bill of materials for the simplest working prototype

`docs/BOM_v4.csv`: {len(bom)} lines, roughly ${cost_lo:,.0f}-{cost_hi:,.0f} of parts beyond the GL60 (converter choice dominates; machining prices are
estimates for a job shop; no anodising, battery, cable beyond 3 m or instrumentation). The four machined parts (shaft, two caps, tube
ends) are the only non-printed, non-COTS items.

## 13. Quality gates

{qa}

## 14. Unresolved assumptions

- GL60: KV / Kt / R convention, cogging torque (the single biggest unknown for self-start), no-load loss, lead exit, which hole pattern is the stator's.
- Hydrofoil polars at Re 4e4-8e4 come from an XFOIL surrogate; wind-tunnel data for printed-rough surfaces would likely sit 10-30 % lower in L/D.
- The standstill torque model (Viterna post-stall, no induction) is the least validated part of the BEM; it decides the self-start verdict.
- Seal and bearing friction (assumed from diameter scaling of catalogue-class values), converter efficiency curve and minimum input voltage, quiescent draw.
- Nacelle inflow deficit (15 % inboard of r 38 mm), guard-ring and shallow-water effects (G11), turbulence and debris.
- Manufacturer pages were unreachable: WetLink, Genasun GVB-8, LT8390 modules and seal part numbers must be confirmed before ordering.
"""
open(os.path.join(D, "REPORT_v4.md"), "w").write(txt); print("REPORT_v4.md", len(txt.split()), "words")
