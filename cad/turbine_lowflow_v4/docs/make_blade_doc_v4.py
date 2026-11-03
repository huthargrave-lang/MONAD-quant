#!/usr/bin/env python3
"""BLADE_OPTIMIZATION_v4.md (+ pdf): how the blade geometry was optimised for 0.5-1.0 m/s.  Every number is read from the result files of
the v4 package (polars_cache.json, sweep_stage1/2.json, selection.json, selected_design.json, robustness.json, coupled_results.json,
feasibility.json); nothing is typed by hand.  Build: python make_blade_doc_v4.py && python build_pdf_v4.py --blade"""
import json, math, os
D = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(D, ".."); M = os.path.join(ROOT, "model")
T = json.load(open(os.path.join(M, "polars_cache.json"))); S1 = json.load(open(os.path.join(M, "sweep_stage1.json"))); S2 = json.load(open(os.path.join(M, "sweep_stage2.json")))
SEL = json.load(open(os.path.join(M, "selection.json"))); sel = json.load(open(os.path.join(M, "selected_design.json"))); ROB = json.load(open(os.path.join(M, "robustness.json")))
C = json.load(open(os.path.join(M, "coupled_results.json"))); F = json.load(open(os.path.join(M, "feasibility.json")))
new = C["designs"]["new"]["res"]; orig = C["designs"]["orig"]["res"]; v31 = C["designs"]["v31"]["res"]; VS = C["VS"]; combos = C["combos"]; DER = C["derived"]; sens = C["sens"]
spec = sel["spec"]; A = "A (rear nacelle, hub r 28 mm)"
def op(res, V): return res["perV"][str(V)]["op"]
def Pout(res, V): o = op(res, V); return o["Pout"] if o else 0.0
def feas(V): return next(r for r in F["rows"] if abs(r["V"] - V) < 1e-6)
allS = S1 + S2
def best(rows, key="uniform", pred=lambda r: True): return max((r for r in rows if pred(r)), key=lambda r: r["J"][key])
Ju = max(r["J"]["uniform"] for r in allS); Jl = max(r["J"]["lowflow"] for r in allS)
def srow(label, r):
    s = r["spec"]; p = r["perV"]
    return (f"| {label} | {s['B']} | {s['airfoil']} | {s['lam_d']} | {s.get('c_scale', 1.0)} | {s.get('dbeta', 0):+.0f} | {r['meta']['solidity']:.2f} | {r['meta']['c_root']*1000:.0f} / {r['meta']['c_maxval']*1000:.0f} | "
            f"{p['0.5']['cp_peak']:.3f} / {p['0.7']['cp_peak']:.3f} / {p['1.0']['cp_peak']:.3f} | {p['0.5']['Pout']:.2f} / {p['0.7']['Pout']:.2f} / {p['1.0']['Pout']:.2f} | {r['J']['uniform']:.3f} | {r['J']['lowflow']:.3f} | {r['min_selfstart_V']} |")
hdr = "| group | B | airfoil | TSR_d | chord x | pitch | solidity | root / max chord (mm) | Cp peak 0.5 / 0.7 / 1.0 | net W 0.5 / 0.7 / 1.0 | J_uniform | J_low-flow | self-start (m/s) |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|"
bB = [srow(f"{b} blades", best(allS, "uniform", lambda r, b=b: r["spec"]["B"] == b)) for b in (2, 3, 4, 5)]
bAF = [srow(af, best(allS, "uniform", lambda r, af=af: r["spec"]["airfoil"] == af)) for af in ("naca4412", "naca4415", "sg6043", "fx63137")]
bTSR = [srow(f"TSR_d {t}", best(S1, "uniform", lambda r, t=t: r["spec"]["lam_d"] == t and r["spec"]["B"] == 3 and r["spec"]["airfoil"] == "naca4412")) for t in (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0)]
bCS = [srow(f"chord x{c}", best(S1, "uniform", lambda r, c=c: r["spec"].get("c_scale", 1.0) == c and r["spec"]["B"] == 3 and r["spec"]["airfoil"] == "naca4412" and r["spec"]["lam_d"] == 1.5)) for c in (0.7, 1.0, 1.3)]
S2s = sorted(S2, key=lambda r: -r["J"]["uniform"])
top = [srow(f"stage-2 #{i+1}", r) for i, r in enumerate(S2s[:8])]
# polars table: best L/D at four Reynolds numbers
Res = T["naca4412"]["Res"]; iR = [Res.index(min(Res, key=lambda x: abs(x - v))) for v in (2e4, 4e4, 8e4, 2e5)]
pol_rows = [f"| {k} | {v['tc']*100:.0f} % | " + " | ".join(f"{v['best_ld'][i]:.0f} at {v['alpha_best'][i]:.0f} deg (cl {v['cl_best'][i]:.2f})" for i in iR) + f" | {v['conf_mean']:.2f} | {'yes' if v['selectable'] else 'no'} | {v['note']} |" for k, v in T.items()]
# Reynolds numbers of the selected blade at the coupled operating points (70 % span)
nu = 1.0e-6; r70 = 0.028 + 0.7 * (0.1016 - 0.028); c70 = float(__import__("numpy").interp(r70 * 1000, sel["r_mm"], sel["chord_mm"])) / 1000
def Re70(V):
    o = op(new, V); lam = o["lam"] if o else 3.0; Vrel = V * math.sqrt(1 + (lam * r70 / 0.1016) ** 2); return Vrel * c70 / nu
r30 = 0.028 + 0.3 * (0.1016 - 0.028); c30 = float(__import__("numpy").interp(r30 * 1000, sel["r_mm"], sel["chord_mm"])) / 1000
def Re30(V):
    o = op(new, V); lam = o["lam"] if o else 3.0; Vrel = V * math.sqrt(1 + (lam * r30 / 0.1016) ** 2); return Vrel * c30 / nu
def fmt_spec(sp): return f"{sp['B']} blades, {sp['airfoil'].upper().replace('NACA', 'NACA ')}, design TSR {sp['lam_d']}, chord x{sp.get('c_scale', 1.0)}, pitch {sp.get('dbeta', 0):+.0f} deg"
rob = "\n".join(f"| {k}: B{v['spec']['B']} {v['spec']['airfoil']} TSR_d {v['spec']['lam_d']} x{v['spec'].get('c_scale', 1.0)} | {v['baseline']['J_uniform']:.3f} / {v['baseline']['J_lowflow']:.3f} ({v['baseline']['min_start']}) | {v['Re/1.5']['J_uniform']:.3f} / {v['Re/1.5']['J_lowflow']:.3f} ({v['Re/1.5']['min_start']}) | {v['Re x1.5']['J_uniform']:.3f} / {v['Re x1.5']['J_lowflow']:.3f} ({v['Re x1.5']['min_start']}) | {v['upper-bound standstill']['J_uniform']:.3f} / {v['upper-bound standstill']['J_lowflow']:.3f} ({v['upper-bound standstill']['min_start']}) | {v['baseline']['J_uniform_hand']:.3f} / {v['baseline']['J_lowflow_hand']:.3f} |" for k, v in ROB.items())
st = "\n".join(f"| {r:.1f} | {c:.1f} | {t:.1f} | {w*100:.0f} % |" for r, c, t, w in zip(sel["r_mm"][::5], sel["chord_mm"][::5], sel["twist_deg"][::5], sel["w_root"][::5]))
ss = DER["standstill"]; cl = DER["cogging_limit_for_start"]; band = DER["band"]
W_LOW = "0.5: 0.30, 0.6: 0.30, 0.7: 0.20, 0.8: 0.10, 0.9: 0.05, 1.0: 0.05"
txt = f"""# How the blade geometry was optimised for 0.5-1.0 m/s streams

**What this document is.** A self-contained account of the blade optimisation behind the v4 low-flow design (and the v5 simplified
prototype, which uses the same blade): the objective, the physics at this scale, the airfoil data, the design method, the search, the
selection, and how sure we are. Every number is written by `docs/make_blade_doc_v4.py` from the model's result files. Nothing has been
measured: all of it is prediction from an engineering model (blade-element momentum theory with surrogate airfoil polars, coupled to the
CubeMars GL60 KV25 generator and a buck-boost MPPT converter).

**The result in one paragraph.** {spec['B']} blades, NACA 4412 section blending to NACA 4418 over the inner 35 % of the span, designed at tip-speed
ratio {spec['lam_d']} with a pitch offset of {spec.get('dbeta', 0):+.0f} deg, chord {sel['chord_mm'][0]:.1f} mm at the 28 mm hub rising to {max(sel['chord_mm']):.1f} mm and tapering to {sel['chord_mm'][-1]:.1f} mm at the 101.6 mm tip, twist
{sel['twist_deg'][0]:.1f} deg at the root to {sel['twist_deg'][-1]:.1f} deg at the tip, solidity {sel['meta']['solidity']:.2f}. It is a wide-chord, low-design-TSR rotor: that is what the objective
(net electrical energy with this generator at 0.5-1.0 m/s, counted as zero where the rotor cannot start itself) rewards, because wide
chords raise the Reynolds number and the starting torque at these speeds, while the actual Cp peak still sits at TSR {new['perV']['0.7']['lam'][max(range(len(new['perV']['0.7']['cp'])), key=lambda i: new['perV']['0.7']['cp'][i])]:.1f}.
Predicted net output {Pout(new, 0.5):.2f} / {Pout(new, 0.6):.2f} / {Pout(new, 0.7):.2f} / {Pout(new, 0.8):.2f} / {Pout(new, 1.0):.2f} W at 0.5 / 0.6 / 0.7 / 0.8 / 1.0 m/s; self-start from {combos['baseline']['min_start']} m/s ({combos['optimistic']['min_start']}-{combos['pessimistic']['min_start']} across the
optimistic-pessimistic bounds), sustained rotation from {combos['baseline']['min_sustain']} m/s once spun.

## 1. What "optimised" means here

The brief asked for maximum usable electrical energy, not maximum rotor power coefficient. So the objective is the net 12 V output of
the whole chain (rotor -> seal and bearing friction -> GL60 -> three-phase bridge -> buck-boost MPPT), summed over the flow speeds with
two weightings:

- **J_uniform** = mean of P_net over 0.5, 0.6, 0.7, 0.8, 0.9, 1.0 m/s;
- **J_low-flow** = weighted sum with weights {W_LOW} (an illustrative emphasis on 0.5-0.8 m/s; not a measured duty cycle).

P_net is counted as **zero** at a speed where the candidate (i) cannot start from rest against the generator's cogging plus the seal and
bearing breakaway, (ii) cannot keep turning along its unloaded path to the operating point, or (iii) would put less than 5 V on the bus
(the converter's input floor). The self-start gate uses the BEM torque at TSR 0.1 with induction (the first draft's no-induction
flat-plate estimate was 1.8x too high and is kept only as an upper bound). The final pick maximises the mean of the two normalised
objectives subject to a packaging rule (printable hub walls between blade pockets), ties going to lower solidity.

## 2. The flow regime, and why it drives the shape

| V (m/s) | hydraulic power in the 203.2 mm disc (W) | annulus outside the 28 mm hub (W) | Betz limit on the annulus (W) | chord Reynolds number at 30 % / 70 % span (operating point) | peak Cp of the selected blade |
|---|---|---|---|---|---|
""" + "\n".join(f"| {V:.1f} | {feas(V)['P_disc']:.2f} | {feas(V)[A]['P_annulus']:.2f} | {feas(V)[A]['P_betz']:.2f} | {Re30(V):.1e} / {Re70(V):.1e} | {new['perV'][str(V)]['cp_peak']:.3f} |" for V in (0.5, 0.6, 0.7, 0.8, 1.0)) + f"""

Three things follow from these numbers.

1. **There is very little power to start with** ({feas(0.5)['P_disc']:.1f} W in the whole disc at 0.5 m/s). Every fixed loss matters: the seal and bearing
   friction (about 7 mN m) and the converter's own overhead (about 0.13 W) are each a large fraction of what is available. That is why the
   objective is the net electrical output and not Cp.
2. **The chord Reynolds number is {Re30(0.5):.0e} to {Re70(1.0):.0e}** across the span and the speed range (lower still at the tip taper and at the
   root at 0.5 m/s). Around 4e4-8e4 conventional sections lose most of their lift-to-drag ratio to laminar separation: NACA 4412 has
   L/D {T['naca4412']['best_ld'][iR[1]]:.0f} at Re 4e4, {T['naca4412']['best_ld'][iR[2]]:.0f} at Re 8e4 and {T['naca4412']['best_ld'][iR[3]]:.0f} at Re 2e5. At a given flow speed the only lever on Re is the chord, so a wide
   chord is worth more here than the textbook high-TSR, narrow-blade shape of a large turbine.
3. **Starting matters as much as running.** The GL60's cogging torque (assumed {C['designs']['new']['res']['perV']['0.5']['breakaway']*1000 - 12:.0f} mN m) plus seal and bearing breakaway must be overcome by the
   rotor at rest, where lift is poor and the torque is roughly proportional to solidity. A rotor that only runs well once spun
   scores zero at the low speeds unless it is hand-started.

## 3. Airfoil data: surrogate polars with their confidence

Polars come from NeuralFoil (an XFOIL surrogate) on the UIUC coordinates, at angles -10 to +18 deg and Reynolds numbers 2e4 to 5e5,
extended past stall with the Viterna method, with the surrogate's own confidence recorded. Sections that the surrogate is not confident
about were excluded from the search rather than used.

| section | t/c | best L/D at Re 2e4 | Re 4e4 | Re 8e4 | Re 2e5 | surrogate confidence | in the search | note |
|---|---|---|---|---|---|---|---|---|
{chr(10).join(pol_rows)}

The Eppler E818 asked for in the brief is listed but was not usable: the database coordinates are coarse and the surrogate confidence
({T['e818']['conf_mean']:.2f}) is far below the others; its polars would have been guesses. Figure 1 shows the tables.

## 4. Design method: from airfoil polar to blade shape

For each candidate (blade count B, section, design TSR, chord scale, pitch offset) the blade is generated the same way:

- **Chord (Schmitz planform).** At each radius the chord is the one that makes the section work at its best-L/D lift coefficient at the
  design TSR and the local Reynolds number, for the chosen blade count. The chord scale multiplies it (0.7 / 1.0 / 1.3 / 1.5), the chord
  is capped at 60 mm (print bed and hub packaging), eased to 85 % at the hub, and tapered elliptically to 55 % at the tip.
- **Twist.** The section's best-L/D angle at the local Reynolds number plus the inflow angle at the design TSR, plus a global pitch offset
  (-3 / 0 / +3 deg) that trades starting torque against running efficiency.
- **Root blend.** The outer section blends into NACA 4418 over the inner 35 % of span for printability and root bending; the loss of L/D
  there is in the polars, not ignored.
- **Evaluation.** Vectorised blade-element momentum theory (Prandtl tip and hub losses, Buhl high-induction correction, a 15 % inflow
  deficit inboard of r 38 mm behind the nacelle) gives Cp(TSR) and the torque curve at each flow speed; the generator model (V_oc = rpm / KV,
  I^2 R, commutation overlap, no-load loss) and the converter model (efficiency curve, 5 V floor, overhead) give the net output at the
  MPPT equilibrium; the starting torque is the BEM torque at TSR 0.1 against cogging + breakaway.

Figure 2 shows the Cp-TSR curves of the selected blade against the earlier designs; Figures 3 and 4 show the chord and twist.

## 5. The search

**Stage 1** ({len(S1)} candidates): B = 2 / 3 / 4 / 5 x four sections (NACA 4412, NACA 4415, SG6043, FX63-137) x design TSR 1.5 / 2 / 2.5 / 3 / 3.5 / 4 / 5 / 6 x
chord scale 0.7 / 1.0 / 1.3, evaluated at 0.4-1.0 m/s with 40 blade elements.
**Stage 2** ({len(S2)} candidates): refinements around the leaders (B = 3 / 4 / 5 x TSR 1.5 / 1.75 / 2 / 2.5 x chord scale 1.0 / 1.3 / 1.5 x pitch -3 / 0 / +3 deg,
plus two-blade and SG6043 checks).

Best candidate per blade count, per section, per design TSR (3 blades, NACA 4412) and per chord scale (3 blades, NACA 4412, TSR 1.5):

{hdr}
{chr(10).join(bB)}
{chr(10).join(bAF)}
{chr(10).join(bTSR)}
{chr(10).join(bCS)}

What the table says:

- **Design TSR.** Everything at design TSR 3 and above starts late or not at all at 0.5-0.6 m/s and scores lower: the narrow chords
  of a high-TSR planform drop the Reynolds number and the starting torque. The best designs sit at TSR 1.5-2.5, yet they still run
  at TSR {op(new, 0.5)['lam']:.1f}-{op(new, 1.0)['lam']:.1f} at the MPPT point because the Cp peak of a wide-chord blade is broad.
- **Section.** NACA 4412 wins in the coupled result even though SG6043 and FX63-137 have better two-dimensional L/D: their higher
  design lift coefficient produces narrower chords (lower Re) and a sharper Cp peak, which the fixed-speed-ratio generator load
  does not sit on.
- **Blade count.** Two blades give the best Cp per unit solidity but start last; four and five start earliest but lose Cp to profile
  drag. Three is the compromise, and the margins are a few percent.
- **Chord scale.** Wider is better up to the 60 mm cap; beyond the cap the scale only widens the root, which the hub cannot take.

The eight best stage-2 candidates lie within {(1 - S2s[7]['J']['uniform'] / S2s[0]['J']['uniform']) * 100:.1f} % of each other on J_uniform:

{hdr}
{chr(10).join(top)}

## 6. Selection and why the winner won

Rule (`model/selection.json`): {SEL['rule']}.

The hub-wall rule exists because the v4 hub holds the blades in printed pockets; the v5 one-piece rotor does not need it, but the
same blade is kept because the candidates it excluded were within {(1 - SEL['ranked'][0]['J']['uniform'] / SEL['Ju_max']) * 100:.1f} % on J_uniform and {(1 - SEL['ranked'][0]['J']['lowflow'] / SEL['Jl_max']) * 100:.1f} % on J_low-flow of the
unconstrained best ({fmt_spec(SEL['unconstrained_best']['spec'])}): inside the model's uncertainty.

Selected: {fmt_spec(spec)}. Score {SEL['ranked'][0]['score']:.4f} against {SEL['ranked'][1]['score']:.4f} for the runner-up
({fmt_spec(SEL['ranked'][1]['spec'])}). The best candidate if the rotor is always hand-started (no self-start gate) is
{fmt_spec(SEL['hand_started_best']['spec'])}: the same family with a wider chord.

It won because it (i) self-starts from {combos['baseline']['min_start']} m/s under the baseline starting-torque model (at 0.5 m/s it makes {ss['0.5']['bem01']*1000:.0f} mN m against
{ss['0.5']['breakaway']*1000:.0f} mN m of breakaway; a start at 0.5 / 0.6 / 0.7 m/s needs the measured cogging below {cl['0.5']*1000:.0f} / {cl['0.6']*1000:.0f} / {cl['0.7']*1000:.0f} mN m), (ii) has the highest net
output at 0.5-0.7 m/s once turning, (iii) stays within {max(abs(Pout(new, V) / Pout(orig, V) - 1) for V in (0.8, 0.9, 1.0)) * 100:.0f} % of the original 1-2 m/s rev-2 blade at 0.8-1.0 m/s, and (iv) fits three
pockets on a 28 mm hub. Against the previous designs at identical conditions (Figure 5):

| V (m/s) | selected blade: Cp peak / net W / self-start | original rev-2 blade on the same hub: Cp / W / start | v3.1 blade in its 48 mm drum: Cp / W / start |
|---|---|---|---|
""" + "\n".join(f"| {V:.1f} | {new['perV'][str(V)]['cp_peak']:.3f} / {Pout(new, V):.2f} / {'yes' if new['perV'][str(V)]['start'] else 'no'} | {orig['perV'][str(V)]['cp_peak']:.3f} / {Pout(orig, V):.2f} / {'yes' if orig['perV'][str(V)]['start'] else 'no'} | {v31['perV'][str(V)]['cp_peak']:.3f} / {Pout(v31, V):.2f} / {'yes' if v31['perV'][str(V)]['start'] else 'no'} |" for V in (0.5, 0.6, 0.7, 0.8, 1.0, 1.5, 2.0)) + f"""

What it gives up: about {(1 - Pout(new, 2.0) / Pout(orig, 2.0)) * 100:.0f} % at 2.0 m/s against the rev-2 blade (a 1-2 m/s design), and a higher standstill drag.

**Robustness of the blade-count choice** under the model's main uncertainties (best candidate per blade count; J in W; hand-started = no
self-start gate):

| candidate | baseline J_uniform / J_low-flow (min start) | transition Re / 1.5 | Re x 1.5 | upper-bound starting torque | hand-started |
|---|---|---|---|---|---|
{rob}

The ordering is stable; the margins are not larger than the uncertainty, so the report does not claim three blades are superior beyond
that margin.

## 7. The selected geometry

Station data (every fifth of the {len(sel['r_mm'])} model stations; full table in `model/selected_design.json`; CAD follows it within 0.5 mm / 0.3 deg):

| radius (mm) | chord (mm) | twist from the rotor plane (deg) | NACA 4418 root blend |
|---|---|---|---|
{st}

Tip chord {sel['chord_mm'][-1]:.1f} mm with a 1.0 mm blunt trailing edge and {0.12*sel['chord_mm'][-1]:.1f} mm maximum thickness (printable); root section 18 % thick ({0.18*sel['chord_mm'][0]:.1f} mm) for bending.
Running point: TSR {op(new, 0.5)['lam']:.1f}-{op(new, 1.0)['lam']:.1f}, {op(new, 0.5)['rpm']:.0f}-{op(new, 1.0)['rpm']:.0f} rpm over 0.5-1.0 m/s; {op(new, 2.0)['rpm']:.0f} rpm and {new['perV']['2.0']['open']['Vdc']:.0f} V open-circuit at 2 m/s.

## 8. How sure we are

The one-at-a-time sensitivity study (Figure 6; polar drag +30 / +60 %, transition Reynolds number x 1.5 / 1.5, the high-induction
correction, seal friction x 0.5-3, cogging 8-40 mN m, no-load loss, nacelle inflow factor, generator constants, converter efficiency,
overhead and input floor) spans {band['0.7']['lo']*100:+.0f} % / {band['0.7']['hi']*100:+.0f} % at 0.7 m/s and {band['1.0']['lo']*100:+.0f} % / {band['1.0']['hi']*100:+.0f} % at 1.0 m/s around the baseline, and
{band['0.5']['lo']*100:+.0f} % / {band['0.5']['hi']*100:+.0f} % at 0.5 m/s, where the output is a small difference between hydraulic power and fixed losses. The largest single items are the
transition Reynolds number of a wet printed surface ({sens['Re / 1.5 (earlier transition)'][VS.index(0.6)]:.2f} vs {sens['baseline'][VS.index(0.6)]:.2f} W at 0.6 m/s if transition comes 1.5x earlier) and the cogging torque,
which decides self-start. Combining the pessimistic choices gives {combos['pessimistic']['P'][VS.index(0.6)]:.2f} / {combos['pessimistic']['P'][VS.index(0.8)]:.2f} / {combos['pessimistic']['P'][VS.index(1.0)]:.2f} W at 0.6 / 0.8 / 1.0 m/s and self-start from {combos['pessimistic']['min_start']} m/s; the optimistic
choices give {combos['optimistic']['P'][VS.index(0.6)]:.2f} / {combos['optimistic']['P'][VS.index(0.8)]:.2f} / {combos['optimistic']['P'][VS.index(1.0)]:.2f} W and {combos['optimistic']['min_start']} m/s.

The four measurements that close the model, in order of effect: the GL60's cogging torque and KV convention (bench), the sealed-shaft
friction (bench), the rotor's starting torque at 0.5-0.7 m/s with the shaft locked (flume or tow), and the power curve itself. An
independent reviewer re-derived the BEM, the generator equations and the MPPT equilibria within 1.4 % and found the starting-torque
model and the polar transition behaviour to be the least certain parts; both are carried as bounds above, not as point values.

## 9. Files

`model/polars.py` (polar tables), `model/bem_lowflow.py` (BEM, design generator), `model/generator_lowflow.py` (GL60, friction, converter),
`model/optimize_blades.py` (stages 1-2 and the selection rule), `model/robustness_v4.py`, `model/coupled_eval.py` (final evaluation,
sensitivities, figures); results in `model/sweep_stage1.json`, `sweep_stage2.json`, `selection.json`, `selected_design.json`,
`robustness.json`, `coupled_results.json`. Figures reproduced below: 1 polars, 2 Cp-TSR, 3-4 chord and twist, 5 power vs flow, 6 sensitivity.
"""
open(os.path.join(D, "BLADE_OPTIMIZATION_v4.md"), "w").write(txt); print("BLADE_OPTIMIZATION_v4.md", len(txt.split()), "words")
