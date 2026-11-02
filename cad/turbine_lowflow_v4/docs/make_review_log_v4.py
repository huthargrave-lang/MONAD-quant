#!/usr/bin/env python3
"""Writes REVIEW_LOG_v4.md: the findings of the three independent reviewer agents (run on the exported first draft), the correction
applied, and the re-verification numbers read from the regenerated result files.  Finding texts are static (what the reviewers wrote);
verification values are computed."""
import json, os
D = os.path.dirname(os.path.abspath(__file__)); M = os.path.join(D, "..", "model")
C = json.load(open(os.path.join(M, "coupled_results.json"))); F = json.load(open(os.path.join(M, "feasibility.json"))); SEL = json.load(open(os.path.join(M, "selection.json"))); sel = json.load(open(os.path.join(M, "selected_design.json")))
QA = json.load(open(os.path.join(D, "qa_gates_v4.json"))) if os.path.exists(os.path.join(D, "qa_gates_v4.json")) else {"gates": [], "fails": None}
VS = C["VS"]; sens = C["sens"]; der = C.get("derived", {}); combos = C["combos"]; nd = C["designs"]["new_direct"]["res"]
def P(res, V): o = res["perV"][str(V)]["op"]; return o["Pout"] if o else 0.0
rows = []
# ---------------- reviewer 1: model code and numerics
rows += [
 ("C-M1", "code", "major", "coupled_eval evaluated the 'direct to battery' case as an unlimited-window lossless MPPT (mode 'mppt' with V_min 0, V_max 1e9) instead of a fixed 14.4 V bus; the report's executive summary and the section-6 table were wrong (e.g. 1.18 W instead of ~0.09 W at 0.7 m/s).",
  "full_eval selects mode 'cv' whenever the converter has a fixed bus voltage; the CV equilibrium is now solved by bisection on Vdc(lambda) = V_fixed (generator_lowflow._cv_solve).",
  f"direct-to-battery now {P(nd, 0.5):.2f} / {P(nd, 0.6):.2f} / {P(nd, 0.7):.2f} / {P(nd, 1.0):.2f} W at 0.5 / 0.6 / 0.7 / 1.0 m/s (first non-zero at {next((V for V in VS if P(nd, V) > 0), None)} m/s), consistent with feasibility.json"),
 ("C-M2", "code", "major", "The 'rectifier synchronous' sensitivity was a no-op: the Schottky dict was bound as a default argument at import, so swapping the module-level entry changed nothing; the sensitivity row printed the baseline.",
  "rect is passed explicitly from full_eval to operating_point/gen_point.",
  f"synchronous rectifier now {sens['rectifier synchronous'][VS.index(0.5)]:.2f} / {sens['rectifier synchronous'][VS.index(0.7)]:.2f} / {sens['rectifier synchronous'][VS.index(1.0)]:.2f} W vs baseline {sens['baseline'][VS.index(0.5)]:.2f} / {sens['baseline'][VS.index(0.7)]:.2f} / {sens['baseline'][VS.index(1.0)]:.2f} W ({(sens['rectifier synchronous'][VS.index(0.5)]/sens['baseline'][VS.index(0.5)]-1)*100:+.0f} % at 0.5 m/s): the largest single upside in the table"),
 ("C-M3", "code", "major", "The coded selection rule (no root-chord limit) would have picked the TSR 1.75 / 57 mm-root design, not the shipped one; selection.json was written by an ad-hoc step, so 'python optimize_blades.py 2' did not reproduce selected_design.json.",
  "The root chord <= 52 mm packaging constraint is encoded in optimize_blades stage 2, which now writes selection.json (rule, ranked list, unconstrained best); a QA gate re-applies the rule to the stored sweeps.",
  f"stage 2 re-run selects {SEL['ranked'][0]['spec']} (score {SEL['ranked'][0]['score']:.4f}); unconstrained best {SEL['unconstrained_best']['spec']}; QA gate 'selection reproducible' {next((g[1] for g in QA['gates'] if g[0].startswith('selection reproducible')), 'n/a')}"),
 ("C-M4", "code", "major", "QA gate 7 only checked that the report generator existed; five typed statements were wrong or unsupported (copper '< 0.1 W' at 0.7-1.0 m/s; 'two blades cannot self-start below 0.6'; 'nacelle deficit costs 3 % of Cp'; '1.75 m/s' clamp over-current; the '-30 % / +10 %' band).",
  "Gate 7 now scans the report text for numeric literals with result units outside f-string expressions; the five statements are computed (copper per flow, two-blade start and score, nacelle Cp cost with/without the deficit, clamp current scanned on a 0.05 m/s grid, band from the one-at-a-time envelope).",
  f"copper {C['designs']['new']['res']['perV']['0.5']['op']['Pcu']:.2f} / {C['designs']['new']['res']['perV']['0.7']['op']['Pcu']:.2f} / {C['designs']['new']['res']['perV']['1.0']['op']['Pcu']:.2f} W; nacelle Cp cost {der['nacelle_cp_cost']['0.5']*100:.1f} / {der['nacelle_cp_cost']['1.0']*100:.1f} %; clamp over-current from {der['clamp_overcurrent_from_V']} m/s; band at 0.7 m/s {der['band']['0.7']['lo']*100:+.0f} / {der['band']['0.7']['hi']*100:+.0f} %; gate 7 {next((g[1] for g in QA['gates'] if g[0].startswith('report text contains')), 'n/a')}"),
 ("C-M5", "code", "major", "The self-start verdict rests on a no-induction standstill estimate 1.5-1.7x the BEM torque at TSR 0.2, with the Viterna cdmax (1.8) fixed and absent from the sensitivity study; the verdict flips between cdmax 1.2 and 2.0.",
  "cdmax is a parameter of the polar tables; sensitivities 'standstill cdmax 1.2 / 2.0' and 'standstill = BEM at TSR 0.2' added, cdmax included in the optimistic/pessimistic combos, fig. 3 caption states the discontinuity.",
  f"min self-start: optimistic {combos['optimistic']['min_start']}, baseline {combos['baseline']['min_start']}, pessimistic {combos['pessimistic']['min_start']}, baseline with BEM-at-TSR-0.2 standstill {combos['baseline, standstill = BEM at TSR 0.2']['min_start']} m/s; standstill 0.5 m/s: Viterna {der['standstill_vs_bem02']['0.5']['viterna']*1000:.0f} vs BEM {der['standstill_vs_bem02']['0.5']['bem02']*1000:.0f} mN m"),
 ("C-m1", "code", "minor", "Gear study evaluated the motor no-load loss at rotor rpm instead of N x rpm.", "friction_running takes N; feasibility re-run.",
  f"gear 2:1 with the boost converter: {F['gear'][1]['0.5'][2]:.2f} W at 0.5 and {F['gear'][1]['1.0'][2]:.2f} W at 1.0 m/s vs direct drive {F['gear'][0]['0.5'][2]:.2f} / {F['gear'][0]['1.0'][2]:.2f} W (conclusion unchanged)"),
 ("C-m2", "code", "minor", "gen_point returned a non-physical point when the torque exceeded the pull-out limit (disc < 0).", "returns None; callers skip.", "no such point reached at any operating point (all points pass the balance gate)"),
 ("C-m3", "code", "minor", "The CV equilibrium used a nearest-grid-point acceptance window (+-0.3 V) that could miss the point at a coarser grid.", "replaced by bisection on the fine grid (highest-lambda crossing = stable branch).", "boost-clamp and direct cases re-solved; clamp branch at 1.25-2.0 m/s unchanged within 0.5 %"),
 ("C-m4", "code", "minor", "Sweep (40 elements, 0.5 TSR step) and final evaluation (50 elements, 0.2 step) differ in the second decimal.", "stated in the report (section 8).", f"3.61 (sweep) vs {P(C['designs']['new']['res'], 1.0):.2f} W (final) at 1.0 m/s"),
 ("C-m5", "code", "minor", "13 duplicate stage-2 candidates (c_max 60 vs 68 identical when the chord never reaches 60).", "left as is; noted.", "-"),
 ("C-m6", "code", "minor", "Polar.best() comment described a 0.97 x L/D rule the code did not implement (function unused by the model).", "comment corrected.", "-"),
 ("C-m7", "code", "minor", "The original rev-2 blade (NACA 4422 -> 4414) is evaluated with the NACA 4415 table.", "stated in the report (section 2).", "-"),
 ("C-m8", "code", "minor", "Converter sensitivity overrides mutated a module-level dict.", "each override gets its own key.", "-"),
 ("C-m9", "code", "minor", "Three QA gates were identity/regression checks presented as independent validation.", "relabelled; a genuinely independent gate (selection reproducibility from the stored sweeps) added.", f"{len(QA['gates'])} gates, {QA['fails']} failing"),
]
def table(rows):
    out = ["| ID | Pass | Severity | Finding (reviewer's evidence) | Correction | Re-verification on the regenerated files |", "|---|---|---|---|---|---|"]
    out += [f"| {a} | {b} | {c} | {d} | {e} | {f} |" for a, b, c, d, e, f in rows]; return "\n".join(out)
hdr = """# Independent adversarial review and corrections (v4 low-flow turbine)

Three reviewer agents, each a separate model instance with its own scratch directory and no write access to the package, reviewed the
exported first draft (commit 2add8bd): (1) hydrodynamics / BEM / electrical, (2) mechanical / CAD / deployment, (3) model implementation and
numerics. They re-computed numbers independently (own scripts under /home/user/review_v4_*). Their findings, the corrections and the
re-verification on the regenerated results are listed below. "Independent" here means a separate reviewer instance and separate
re-computation, not a separate physical method or an experiment: nothing has been measured.

"""
extra = os.path.join(D, "review_findings_extra.json")
if os.path.exists(extra):
    for r in json.load(open(extra)): rows.append(tuple(r))
open(os.path.join(D, "REVIEW_LOG_v4.md"), "w").write(hdr + table(rows) + "\n")
print("REVIEW_LOG_v4.md", len(rows), "entries")
