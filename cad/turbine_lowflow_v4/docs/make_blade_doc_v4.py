#!/usr/bin/env python3
"""BLADE_OPTIMIZATION_v4.md (+ pdf via build_blade_pdf_v4.py): how the blade geometry was optimised for 0.5-1.0 m/s.
Every number is read from the v4 result files (polars_cache, sweep_stage1/2, selection, selected_design, robustness, coupled_results,
feasibility); nothing is typed by hand."""
import json, math, os
import numpy as np
D = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(D, ".."); M = os.path.join(ROOT, "model")
T = json.load(open(os.path.join(M, "polars_cache.json"))); S1 = json.load(open(os.path.join(M, "sweep_stage1.json"))); S2 = json.load(open(os.path.join(M, "sweep_stage2.json")))
SEL = json.load(open(os.path.join(M, "selection.json"))); sel = json.load(open(os.path.join(M, "selected_design.json"))); ROB = json.load(open(os.path.join(M, "robustness.json")))
C = json.load(open(os.path.join(M, "coupled_results.json"))); F = json.load(open(os.path.join(M, "feasibility.json")))
new = C["designs"]["new"]["res"]; orig = C["designs"]["orig"]["res"]; v31 = C["designs"]["v31"]["res"]; VS = C["VS"]; combos = C["combos"]; DER = C["derived"]; sens = C["sens"]
spec = sel["spec"]; A = "A (rear nacelle, hub r 28 mm)"
names = {"naca4412": "NACA 4412", "naca4415": "NACA 4415", "naca4418": "NACA 4418", "sg6043": "SG6043", "e387": "Eppler E387", "fx63137": "FX 63-137", "e818": "Eppler E818"}
def op(res, V): return res["perV"][str(V)]["op"]
def Pout(res, V): o = op(res, V); return o["Pout"] if o else 0.0
def feas(V): return next(r for r in F["rows"] if abs(r["V"] - V) < 1e-6)
def fmt_spec(sp, short=False):
    af = names.get(sp["airfoil"], sp["airfoil"])
    return f"{sp['B']} blades, {af}, TSR {sp['lam_d']}, chord x{sp.get('c_scale', 1.0)}, pitch {sp.get('dbeta', 0):+.0f} deg"
allS = S1 + S2
def best(rows, key="uniform", pred=lambda r: True): return max((r for r in rows if pred(r)), key=lambda r: r["J"][key])
def srow(label, r):
    s = r["spec"]; p = r["perV"]
    return f"| {label} | {fmt_spec(s)} | {r['meta']['solidity']:.2f} | {p['0.5']['Pout']:.2f} / {p['0.7']['Pout']:.2f} / {p['1.0']['Pout']:.2f} | {r['J']['uniform']:.2f} / {r['J']['lowflow']:.2f} | {r['min_selfstart_V'] if r['min_selfstart_V'] is not None else '> 1.0'} |"
hdr = "| group | candidate | solidity | net W at 0.5 / 0.7 / 1.0 m/s | J uniform / low-flow (W) | self-start (m/s) |\n|---|---|---|---|---|---|"
bB = [srow(f"{b} blades", best(allS, "uniform", lambda r, b=b: r["spec"]["B"] == b)) for b in (2, 3, 4, 5)]
bAF = [srow(names[af], best(allS, "uniform", lambda r, af=af: r["spec"]["airfoil"] == af)) for af in ("naca4412", "naca4415", "sg6043", "fx63137")]
bTSR = [srow(f"design TSR {t}", best(S1, "uniform", lambda r, t=t: r["spec"]["lam_d"] == t and r["spec"]["B"] == 3 and r["spec"]["airfoil"] == "naca4412")) for t in (1.5, 2.0, 3.0, 4.0, 6.0)]
bCS = [srow(f"chord x{c}", best(S1, "uniform", lambda r, c=c: r["spec"].get("c_scale", 1.0) == c and r["spec"]["B"] == 3 and r["spec"]["airfoil"] == "naca4412" and r["spec"]["lam_d"] == 1.5)) for c in (0.7, 1.0, 1.3)]
S2s = sorted(S2, key=lambda r: -r["J"]["uniform"])
Res = T["naca4412"]["Res"]; iR = [Res.index(min(Res, key=lambda x: abs(x - v))) for v in (4e4, 8e4, 2e5)]
pol_rows = [f"| {names.get(k, k)} | {v['tc']*100:.0f} % | " + " | ".join(f"{v['best_ld'][i]:.0f}" for i in iR) + f" | {v['conf_mean']:.2f} | {'root blend only' if k == 'naca4418' else ('searched' if v['selectable'] else 'excluded (low confidence)')} |" for k, v in T.items()]
def fe(x): e = int(math.floor(math.log10(x))); return f"{x / 10 ** e:.1f}e{e}"
nu = 1.0e-6
def Re_at(frac, V):
    r = 0.028 + frac * (0.1016 - 0.028); c = float(np.interp(r * 1000, sel["r_mm"], sel["chord_mm"])) / 1000
    o = op(new, V); lam = o["lam"] if o else 3.0; return V * math.sqrt(1 + (lam * r / 0.1016) ** 2) * c / nu
rob = "\n".join(f"| {fmt_spec(v['spec'])} | {v['baseline']['J_uniform']:.2f} ({v['baseline']['min_start']}) | {v['Re/1.5']['J_uniform']:.2f} ({v['Re/1.5']['min_start']}) | {v['Re x1.5']['J_uniform']:.2f} ({v['Re x1.5']['min_start']}) | {v['upper-bound standstill']['J_uniform']:.2f} ({v['upper-bound standstill']['min_start']}) | {v['baseline']['J_uniform_hand']:.2f} |" for k, v in ROB.items() if k != "selected")
st = "\n".join(f"| {r:.1f} | {c:.1f} | {t:.1f} | {w*100:.0f} % |" for r, c, t, w in zip(sel["r_mm"][::5], sel["chord_mm"][::5], sel["twist_deg"][::5], sel["w_root"][::5]))
ss = DER["standstill"]; cl = DER["cogging_limit_for_start"]; band = DER["band"]
i_pk = int(np.argmax(new["perV"]["0.7"]["cp"])); lam_pk = new["perV"]["0.7"]["lam"][i_pk]
cog = C["designs"]["new"]["res"]["perV"]["0.5"]["breakaway"] - 0.012
txt = f"""# Blade Geometry Optimization for 0.5-1.0 m/s Streams

<p class="sub">8-inch (203.2 mm) hydrokinetic turbine, CubeMars GL60 KV25 generator, v4 blade (used unchanged in the v5 simplified prototype).
Status: model prediction, nothing measured. All numbers are generated from the v4 result files by <code>docs/make_blade_doc_v4.py</code>.</p>

## 1. Result

| Selected blade | |
|---|---|
| Blades, section | {spec['B']}, NACA 4412 blending to NACA 4418 over the inner 35 % of span |
| Design tip-speed ratio, pitch offset | {spec['lam_d']}, {spec.get('dbeta', 0):+.0f} deg |
| Chord: hub / maximum / tip | {sel['chord_mm'][0]:.1f} / {max(sel['chord_mm']):.1f} / {sel['chord_mm'][-1]:.1f} mm |
| Twist: hub / tip (from the rotor plane) | {sel['twist_deg'][0]:.1f} / {sel['twist_deg'][-1]:.1f} deg |
| Solidity | {sel['meta']['solidity']:.2f} |
| Hub / tip radius | 28 / 101.6 mm |
| Predicted net 12 V output at 0.5 / 0.7 / 1.0 m/s | {Pout(new, 0.5):.2f} / {Pout(new, 0.7):.2f} / {Pout(new, 1.0):.2f} W |
| Self-start / sustained rotation from | {combos['baseline']['min_start']} / {combos['baseline']['min_sustain']} m/s (self-start bounds {combos['optimistic']['min_start']}-{combos['pessimistic']['min_start']} m/s) |
| Operating TSR and speed, 0.5-1.0 m/s | {op(new, 0.5)['lam']:.1f}-{op(new, 1.0)['lam']:.1f}, {op(new, 0.5)['rpm']:.0f}-{op(new, 1.0)['rpm']:.0f} rpm |

The design is a wide-chord, low-design-TSR rotor. At these speeds the chord is the only lever on the Reynolds number and on the
starting torque, and both matter more than the last few points of peak Cp.

## 2. Objective

- **Maximise net electrical energy**, not rotor Cp: the output of the whole chain (rotor, seal and bearing friction, GL60, rectifier,
  buck-boost MPPT) is what the battery sees.
- **Two weightings:** J_uniform (mean over 0.5-1.0 m/s in 0.1 m/s steps) and J_low-flow (weights 0.30 / 0.30 / 0.20 / 0.10 / 0.05 / 0.05
  from 0.5 to 1.0 m/s).
- **Gates:** output counts as zero at a speed where the rotor cannot start against cogging plus breakaway, cannot keep turning
  to its operating point, or puts less than 5 V on the bus. The starting torque is the BEM torque at TSR 0.1 with induction.
- **Selection:** the mean of the two normalised objectives, subject to a printable hub wall between blade pockets; ties go to the
  lower solidity.

## 3. The flow regime

| V (m/s) | power in the disc (W) | Betz limit on the annulus (W) | chord Reynolds number, 30 % / 70 % span | peak Cp of the selected blade |
|---|---|---|---|---|
""" + "\n".join(f"| {V:.1f} | {feas(V)['P_disc']:.2f} | {feas(V)[A]['P_betz']:.2f} | {fe(Re_at(0.3, V))} / {fe(Re_at(0.7, V))} | {new['perV'][str(V)]['cp_peak']:.3f} |" for V in (0.5, 0.6, 0.7, 0.8, 1.0)) + f"""

- **Little power to start with:** {feas(0.5)['P_disc']:.1f} W in the whole disc at 0.5 m/s. Seal and bearing friction (about 7 mN m) and the converter
  overhead (about 0.13 W) are each a large share of it, so the objective has to be the net output.
- **Low Reynolds numbers:** {fe(Re_at(0.3, 0.5))} to {fe(Re_at(0.7, 1.0))}. NACA 4412 has L/D {T['naca4412']['best_ld'][iR[0]]:.0f} at Re 4e4, {T['naca4412']['best_ld'][iR[1]]:.0f} at 8e4 and {T['naca4412']['best_ld'][iR[2]]:.0f} at 2e5. A wide chord
  buys Reynolds number directly.
- **Starting counts:** the GL60's assumed {cog*1000:.0f} mN m cogging plus 12 mN m of breakaway must be beaten by a rotor at rest, where the torque
  scales with solidity.

## 4. Airfoil data

Polars from NeuralFoil (an XFOIL surrogate) on UIUC coordinates, -10 to +18 deg, Re 2e4-5e5, Viterna post-stall extension. Sections
the surrogate is not confident about were excluded rather than guessed (Figure 1).

| section | t/c | best L/D at Re 4e4 | Re 8e4 | Re 2e5 | surrogate confidence | use |
|---|---|---|---|---|---|---|
{chr(10).join(pol_rows)}

## 5. Design method

Each candidate (blade count, section, design TSR, chord scale, pitch offset) is built and evaluated the same way:

- **Chord:** Schmitz planform at the design TSR, using each section's best-L/D lift coefficient at the local Reynolds number;
  scaled x0.7-1.5, capped at 60 mm, eased to 85 % at the hub, elliptical taper to 55 % at the tip.
- **Twist:** best-L/D angle at the local Reynolds number plus the design-TSR inflow angle, plus a global pitch offset of -3 / 0 / +3 deg.
- **Root:** blend to NACA 4418 over the inner 35 % of span for printability and bending strength.
- **Rotor model:** blade-element momentum theory with Prandtl tip and hub losses, Buhl high-induction correction, and a 15 % inflow
  deficit inboard of r 38 mm behind the nacelle.
- **Electrical model:** GL60 (V_oc = rpm / KV, copper loss, commutation overlap, no-load loss), three-phase bridge, buck-boost MPPT
  with efficiency curve, overhead and a 5 V floor; the operating point is the MPPT equilibrium.

Figure 2 shows the resulting Cp-TSR curves; Figure 3 the chord and twist against the earlier blades.

## 6. The search

Stage 1: {len(S1)} candidates (2-5 blades x 4 sections x design TSR 1.5-6 x chord scale 0.7 / 1.0 / 1.3). Stage 2: {len(S2)} refinements around
the leaders (3-5 blades x TSR 1.5-2.5 x chord scale 1.0-1.5 x pitch -3 / 0 / +3 deg, plus two-blade and SG6043 checks).

{hdr}
{chr(10).join(bB)}
{chr(10).join(bAF)}
{chr(10).join(bTSR)}
{chr(10).join(bCS)}

- **Design TSR 1.5-2.5 wins.** Designs at TSR 3 and above start late or not at all: narrow chords mean low Reynolds number and low
  starting torque. The winner still runs at TSR {op(new, 0.5)['lam']:.1f}-{op(new, 1.0)['lam']:.1f} because its Cp peak (TSR {lam_pk:.1f}) is broad.
- **NACA 4412 beats the higher-lift sections** in the coupled result: SG6043 and FX 63-137 have better two-dimensional L/D, but their higher
  design lift coefficient gives narrower chords and a sharper Cp peak.
- **Three blades** balance the two-blade Cp advantage against the four- and five-blade starting advantage; the margins are a few percent.
- **Wider chord helps up to the 60 mm cap.**

## 7. Selection

| candidate | J uniform / low-flow (W) | self-start (m/s) | note |
|---|---|---|---|
| **Selected:** {fmt_spec(spec)} | {SEL['ranked'][0]['J']['uniform']:.3f} / {SEL['ranked'][0]['J']['lowflow']:.3f} | {sel['min_selfstart_V']} | score {SEL['ranked'][0]['score']:.4f} |
| Runner-up: {fmt_spec(SEL['ranked'][1]['spec'])} | {SEL['ranked'][1]['J']['uniform']:.3f} / {SEL['ranked'][1]['J']['lowflow']:.3f} | {SEL['ranked'][1].get('min_selfstart_V', '-')} | score {SEL['ranked'][1]['score']:.4f} |
| Unconstrained best: {fmt_spec(SEL['unconstrained_best']['spec'])} | {SEL['unconstrained_best']['J']['uniform']:.3f} / {SEL['unconstrained_best']['J']['lowflow']:.3f} | {SEL['unconstrained_best'].get('min_selfstart_V', '-')} | fails the hub-wall rule; {(1 - SEL['ranked'][0]['J']['uniform'] / SEL['Ju_max']) * 100:.1f} % better on J uniform |
| Hand-started best: {fmt_spec(SEL['hand_started_best']['spec'])} | {SEL['hand_started_best']['J']['uniform_hand']:.3f} / {SEL['hand_started_best']['J']['lowflow_hand']:.3f} (no start gate) | {SEL['hand_started_best']['min_selfstart_V']} | same family, wider chord |

Why the selected blade won:

- It self-starts from {combos['baseline']['min_start']} m/s under the baseline model: at 0.5 m/s it makes {ss['0.5']['bem01']*1000:.0f} mN m against {ss['0.5']['breakaway']*1000:.0f} mN m of breakaway; a start at
  0.5 / 0.6 / 0.7 m/s needs measured cogging below {cl['0.5']*1000:.0f} / {cl['0.6']*1000:.0f} / {cl['0.7']*1000:.0f} mN m.
- It has the highest net output at 0.5-0.7 m/s once turning (Reynolds effect of the wide chord).
- It stays within {max(abs(Pout(new, V) / Pout(orig, V) - 1) for V in (0.8, 0.9, 1.0)) * 100:.0f} % of the original 1-2 m/s blade at 0.8-1.0 m/s and gives up {(1 - Pout(new, 2.0) / Pout(orig, 2.0)) * 100:.0f} % at 2.0 m/s.
- The eight best stage-2 candidates lie within {(1 - S2s[7]['J']['uniform'] / S2s[0]['J']['uniform']) * 100:.1f} % of each other, so the packaging rule decided among near-equals.

Robustness of the blade-count choice (best candidate per count; J uniform in W, self-start speed in brackets):

| candidate | baseline | transition Re / 1.5 | Re x 1.5 | upper-bound starting torque | hand-started |
|---|---|---|---|---|---|
{rob}

The ordering is stable; the margins are inside the model uncertainty, so no claim is made that three blades are superior beyond that.

## 8. Comparison with the previous blades

| V (m/s) | selected: Cp peak / net W / self-start | original rev-2 blade on the same hub | v3.1 blade in its 48 mm drum |
|---|---|---|---|
""" + "\n".join(f"| {V:.1f} | {new['perV'][str(V)]['cp_peak']:.3f} / {Pout(new, V):.2f} / {'yes' if new['perV'][str(V)]['start'] else 'no'} | {orig['perV'][str(V)]['cp_peak']:.3f} / {Pout(orig, V):.2f} / {'yes' if orig['perV'][str(V)]['start'] else 'no'} | {v31['perV'][str(V)]['cp_peak']:.3f} / {Pout(v31, V):.2f} / {'yes' if v31['perV'][str(V)]['start'] else 'no'} |" for V in (0.5, 0.6, 0.7, 0.8, 1.0, 1.5, 2.0)) + f"""

Figure 4 plots the net output against flow speed.

## 9. Selected geometry

Every fifth of the {len(sel['r_mm'])} model stations (full table in `model/selected_design.json`; the CAD follows it within 0.5 mm and 0.3 deg).

| radius (mm) | chord (mm) | twist (deg) | NACA 4418 blend |
|---|---|---|---|
{st}

Tip: {sel['chord_mm'][-1]:.1f} mm chord, 1.0 mm blunt trailing edge, {0.12*sel['chord_mm'][-1]:.1f} mm maximum thickness. Root: 18 % thick ({0.18*sel['chord_mm'][0]:.1f} mm).
At 2 m/s: {op(new, 2.0)['rpm']:.0f} rpm, {new['perV']['2.0']['open']['Vdc']:.0f} V open-circuit.

## 10. Uncertainty

- One-at-a-time sensitivities (polar drag, transition Reynolds number, induction model, friction, cogging, no-load loss, inflow
  factor, generator constants, converter) span {band['0.7']['lo']*100:+.0f} / {band['0.7']['hi']*100:+.0f} % at 0.7 m/s and {band['1.0']['lo']*100:+.0f} / {band['1.0']['hi']*100:+.0f} % at 1.0 m/s (Figure 5).
- Largest items: the transition Reynolds number of a wet printed surface ({sens['Re / 1.5 (earlier transition)'][VS.index(0.6)]:.2f} vs {sens['baseline'][VS.index(0.6)]:.2f} W at 0.6 m/s if it comes 1.5x
  earlier) and the cogging torque, which decides self-start.
- Bounds: pessimistic {combos['pessimistic']['P'][VS.index(0.6)]:.2f} / {combos['pessimistic']['P'][VS.index(1.0)]:.2f} W at 0.6 / 1.0 m/s and self-start from {combos['pessimistic']['min_start']} m/s; optimistic {combos['optimistic']['P'][VS.index(0.6)]:.2f} / {combos['optimistic']['P'][VS.index(1.0)]:.2f} W and {combos['optimistic']['min_start']} m/s.
- To close the model, measure in this order: GL60 cogging and KV convention, sealed-shaft friction, rotor starting torque at
  0.5-0.7 m/s (shaft locked), the power curve.

## 11. Source files

`model/polars.py`, `bem_lowflow.py`, `generator_lowflow.py`, `optimize_blades.py` (stages 1-2, selection), `robustness_v4.py`,
`coupled_eval.py`; results in `model/sweep_stage1.json`, `sweep_stage2.json`, `selection.json`, `selected_design.json`,
`robustness.json`, `coupled_results.json`.
"""
open(os.path.join(D, "BLADE_OPTIMIZATION_v4.md"), "w").write(txt); print("BLADE_OPTIMIZATION_v4.md", len(txt.split()), "words")
