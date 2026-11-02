#!/usr/bin/env python3
"""Manual quality gates for the v4 package (the /quality skill is not installed in this environment; this script is the substitute).
Gates: reproducibility (re-computes the selected design's key numbers from the model and compares with the stored results), physical
plausibility (Cp < Betz on every curve; chord/thickness printable; positive twist monotonic), units and power balance at every
operating point (shaft = friction + copper + diode + DC, within 1 %), generator constraints (current <= rated at the MPPT points),
consistency between model arrays and CAD stations, CAD validity / clash / STL closure and volume, figures present, BOM vs CAD parts,
and no hand-typed numbers in the report generator's result sentences.  Writes docs/QA_LOG_v4.md."""
import csv, json, math, os, re, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "model"))
import bem_lowflow as bm, generator_lowflow as gl, optimize_blades as ob, coupled_eval as ce
log = []; fails = 0
def gate(name, ok, detail):
    global fails; log.append((name, "PASS" if ok else "FAIL", detail)); fails += 0 if ok else 1; print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
sel = json.load(open(os.path.join(ROOT, "model", "selected_design.json"))); C = json.load(open(os.path.join(ROOT, "model", "coupled_results.json")))
new = C["designs"]["new"]["res"]
# 1. reproducibility: re-evaluate the selected design at 0.7 and 1.0 m/s and compare Pout
rr = ce.full_eval(sel["spec"], "A", vs=[0.7, 1.0], lams=ce.LAMS)
d = {V: abs(rr["perV"][str(V)]["op"]["Pout"] - new["perV"][str(V)]["op"]["Pout"]) for V in (0.7, 1.0)}
gate("reproducibility (re-run of the coupled model at 0.7 / 1.0 m/s) [regression check: same code, same inputs]", max(d.values()) < 1e-6, f"|dP| {max(d.values()):.2e} W at 0.7/1.0 m/s")
# reproducibility of the SELECTION: the coded rule applied to the stored sweeps must return the shipped design
SELJ = json.load(open(os.path.join(ROOT, "model", "selection.json"))); S1 = json.load(open(os.path.join(ROOT, "model", "sweep_stage1.json"))); S2 = json.load(open(os.path.join(ROOT, "model", "sweep_stage2.json")))
allc = S1 + S2; Ju = max(r["J"]["uniform"] for r in allc); Jl = max(r["J"]["lowflow"] for r in allc)
ok = [r for r in allc if r["meta"].get("hub_wall_deg", 0) >= 12.0]                       # the coded rule (optimize_blades stage 2): hub wall >= 12 deg; J already gated
best = max(ok, key=lambda r: (0.5 * r["J"]["uniform"] / Ju + 0.5 * r["J"]["lowflow"] / Jl, -r["meta"]["solidity"]))
gate("selection reproducible: the coded rule on the stored sweeps returns the shipped design", best["spec"] == sel["spec"], f"rule -> {best['spec']}; shipped {sel['spec']}")
# 2. physical plausibility
cps = [max(new["perV"][V]["cp"]) for V in new["perV"]]
gate("Cp below the Betz limit on every curve", max(cps) < 0.593, f"max Cp {max(cps):.3f}")
tw = np.array(sel["twist_deg"]); ch = np.array(sel["chord_mm"])
gate("twist monotonic decreasing root -> tip, 0-60 deg", np.all(np.diff(tw) <= 0.05) and tw.max() < 60 and tw.min() > 0, f"{tw[0]:.1f} -> {tw[-1]:.1f} deg")
tmin = 0.12 * ch.min() * (1 - 0) ; gate("printable section: tip chord >= 20 mm and max thickness >= 2.4 mm", ch.min() >= 20 and 0.12 * ch[-1] >= 2.4, f"tip chord {ch[-1]:.1f} mm, tip t {0.12*ch[-1]:.1f} mm, TE 1.0 mm")
# 3. power balance and units at every operating point of the new design
worst = 0.0; detail = []
for V, p in new["perV"].items():
    op = p["op"]
    if not op: continue
    lhs = op["Pshaft"]; rhs = op["Pfric"] + op["Pcu"] + op["Pdiode"] + op["Pdc"]       # the commutation-overlap term is reactive: generator torque x speed = DC + copper + diode exactly (no overlap term)
    err = abs(lhs - rhs) / lhs; worst = max(worst, err); detail.append(f"{V}: {err*100:.2f} %")
gate("power balance at every operating point (shaft = friction + copper + diodes + DC) [identity check of the stored points]", worst < 1e-6, "; ".join(detail))
# 4. generator constraints
over = [(V, p["op"]["I"]) for V, p in new["perV"].items() if p["op"] and float(V) <= 2.0 and p["op"]["I"] > gl.GEN["rated_I"]]
gate("generator current <= 1.35 A rated at every MPPT point to 2.0 m/s [enforced by the MPPT law; regression check]", not over, f"max I {max(p['op']['I'] for p in new['perV'].values() if p['op']):.2f} A" + (f"; over: {over}" if over else ""))
vmax = max(p["open"]["Vdc"] for p in new["perV"].values() if p["open"]); gate("open-circuit bus at 2.0 m/s below the 60 V TVS standoff and the converter's 60 V input", vmax < 60, f"{vmax:.1f} V")
# 5. model <-> CAD consistency
info = json.load(open(os.path.join(ROOT, "out", "v4_info.json"))); st = info["layout"]["stations"]
cad_c = np.interp(np.array(sel["r_mm"]), st["r"], st["chord"]); cad_t = np.interp(np.array(sel["r_mm"]), st["r"], st["twist"])
m = (np.array(sel["r_mm"]) >= 28.0)
gate("CAD station chord/twist match the model arrays (interpolated, r >= 28 mm)", np.abs(cad_c[m] - ch[m]).max() < 0.5 and np.abs(cad_t[m] - tw[m]).max() < 0.5, f"max |dc| {np.abs(cad_c[m]-ch[m]).max():.2f} mm, |dtwist| {np.abs(cad_t[m]-tw[m]).max():.2f} deg")
gate("CAD: every solid valid, single body, no rigid clash", all(p["valid"] for p in info["parts"]) and all(p.get("n_solids", 1) == 1 for p in info["parts"]) and not {k: v for k, v in info["layout"]["interference_mm3"].items() if v > 0.5 or v < 0},
     f"{len(info['parts'])} parts, {info['layout']['pairs_checked']} pairs, interference {info['layout']['interference_mm3']}")
lip = info["layout"].get("seal_lip_overlap_mm3", {})
gate("CAD: shaft/lip-seal overlap equals the modelled lip interference only (collar B clear of the seal)", bool(lip.get("ok")), f"found {lip.get('found')} mm3, expected {lip.get('expected')} mm3")
PP = info["params"]; eng = PP["dog_h"] - PP["ic_front"]
gate("CAD: dog coupling engages the TPU disc by >= 1.5 mm and clears the bell", 1.5 <= eng < PP["disc_t"], f"engagement {eng:.1f} mm of a {PP['disc_t']:.1f} mm disc")
import math as _m
_a = _m.radians(PP["wetlink_deg"]); _yw, _zw = -PP["wetlink_r"] * _m.sin(_a), PP["wetlink_r"] * _m.cos(_a)
_dmin = min(_m.hypot(_yw - pcd / 2 * _m.cos(_m.radians(90 * k)), _zw - pcd / 2 * _m.sin(_m.radians(90 * k))) for pcd in (PP["bell_pcd"], PP["motor_pcd"]) for k in range(4))
gate("CAD: penetrator counterbore clears every stator hole by >= 2 mm of wall", _dmin - PP["wetlink_cb_d"] / 2 - 1.25 >= 2.0, f"wall {_dmin - PP['wetlink_cb_d'] / 2 - 1.25:.1f} mm")
gate("CAD: rotor thrust shoulder present (DIN 472-22 groove behind the bearing inside the cap boss)", info["layout"]["cap"]["x_ring"] > info["layout"]["cap"]["x_brg"] + PP["brg_w"] and info["layout"]["cap"]["x_boss_end"] > info["layout"]["cap"]["x_ring"] + 1.0,
     f"bearing ends x {info['layout']['cap']['x_brg'] + PP['brg_w']:.1f}, groove x {info['layout']['cap']['x_ring']:.1f}, boss end x {info['layout']['cap']['x_boss_end']:.1f}")
# BRep validity of the re-imported STEP solids (the reviewer's check: cadquery isValid on the exported file, not on the in-memory solid)
try:
    import cadquery as cq
    from OCP.BRepCheck import BRepCheck_Analyzer
    badstep = []
    for nm in ("hub_front", "hub_rear", "blade_0", "front_cap", "rear_cap", "rotor_shaft", "stub_shaft", "dog_hub", "drive_disc", "shell_top", "shell_bot", "strut_0", "duct_0", "duct_1"):
        f = os.path.join(ROOT, "out", f"v4_{nm}.step")
        if os.path.exists(f):
            for sld in cq.importers.importStep(f).solids().vals():
                if not BRepCheck_Analyzer(sld.wrapped).IsValid(): badstep.append(nm)
    gate("CAD: re-imported STEP solids pass BRepCheck (hub halves, blade, caps, shafts, drive, shell, strut, arcs)", not badstep, f"invalid {badstep}" if badstep else "all valid")
except Exception as e:
    gate("CAD: re-imported STEP solids pass BRepCheck", False, f"check could not run: {e}")
stls = [p for p in info["parts"] if "stl_watertight" in p]
gate("print STLs closed; blade STL volume within 1 % of its STEP", all(p["stl_watertight"] for p in stls) and all(abs(p.get("stl_vs_step_pct", 0)) < 1.0 for p in stls), f"{len(stls)} STLs; blade dev {[p.get('stl_vs_step_pct') for p in stls if p['name']=='blade_0']} %")
gate("packing: rotor and nacelle each <= 76 mm when detached", info["layout"]["rotor_depth_mm"] <= 76 and info["layout"]["nacelle_depth_mm"] <= 76, f"rotor {info['layout']['rotor_depth_mm']:.1f}, nacelle {info['layout']['nacelle_depth_mm']:.1f}, operating {info['layout']['operating_depth_mm']:.1f} mm")
# 5b. hub packaging from the CAD outline and consistency of the self-start verdict between the sweep and the final evaluation
ST = json.load(open(os.path.join(ROOT, "model", "structure_v4.json")))
gate("hub wall between pockets >= 12 deg (measured from the CAD root outline)", ST["hub_wall_deg"] >= 12.0, f"pocket arc {ST['pocket_arc_deg']:.0f} deg, wall {ST['hub_wall_deg']:.0f} deg = {ST['hub_wall_mm_floor']:.1f} mm at the floor")
gate("minimum self-start flow: sweep (40 elements) and final evaluation (50 elements) agree", sel.get("min_selfstart_V") == C["combos"]["baseline"]["min_start"], f"sweep {sel.get('min_selfstart_V')} vs final {C['combos']['baseline']['min_start']} m/s")
# 6. figures and BOM
figs = ["fig1_hydraulic_power.png", "fig2_cp_tsr.png", "fig3_torque_rpm.png", "fig4_power_vs_v.png", "fig5_6_chord_twist.png", "fig7_generator_losses.png", "fig8_sensitivity.png", "fig9_operating_point.png", "fig10a_section.png", "fig10b_dimensioned.png", "fig10c_exploded.png", "fig_polars.png"]
missing = [f for f in figs if not os.path.exists(os.path.join(ROOT, "out", f))]; gate("all required figures generated by scripts", not missing, f"missing {missing}" if missing else f"{len(figs)} figures")
bom = list(csv.DictReader(open(os.path.join(ROOT, "docs", "BOM_v4.csv")))); bt = " ".join((r["part"] + " " + r["specification"] + " " + r["file / drawing"]).lower() for r in bom)
keys = {"hub_front": "front hub", "hub_rear": "rear hub", "blade": "blades", "shaft": "shaft", "front_cap": "front cap", "rear_cap": "rear cap", "tube": "tube", "bearing": "608", "lip_seal": "lip seal", "circlip": "din 471-8", "oring": "as568-146", "iring": "din 472-22", "hub_washer": "washer 14 x 8.4", "wetlink": "wetlink", "vent": "vent",
        "dog_hub": "dog hub", "drive_disc": "drive disc", "coupling_pin": "dowel", "motor": "gl60", "shell": "shell clamp", "strut": "strut", "duct": "guard ring", "rotor_shaft": "rotor shaft", "stub_shaft": "stub shaft", "nose_plug": "nose plug", "bolt": "m3 x 40", "hub_screw": "m3 x 10"}
miss = [n for n, k in keys.items() if k not in bt]; gate("BOM covers every CAD part", not miss, f"missing {miss}" if miss else f"{len(bom)} BOM lines")
# 7. report generator: result sentences must not contain hand-typed numbers (numeric literals outside f-string expressions in the key sections)
rep = open(os.path.join(ROOT, "docs", "make_report_v4.py")).read() if os.path.exists(os.path.join(ROOT, "docs", "make_report_v4.py")) else ""
# gate 7: numeric literals followed by a result unit (W, %, rpm, mN m, N m, A) in the report TEXT (outside {} expressions) are hand-typed results
body = rep[rep.index('txt = f"""'):] if 'txt = f"""' in rep else ""
text_only = re.sub(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", "", body)                      # strip f-string expressions (one nesting level)
typed = re.findall(r"(?<![\w.])(\d+\.?\d*)\s?(W|%|rpm|mN m|N m| A\b)(?![\w])", text_only)
allow = {("12", "W"), ("5", "W"), ("4", "W"), ("1", "W"), ("3", "W"), ("0.1", "W"), ("50", "W"), ("10", "W"), ("8", "W"), ("100", "W"), ("0.5", "W"), ("2", "W")}
# literals that are INPUTS or GEOMETRY, not results (each is an assumption stated as such in the text: gear-stage efficiency and friction, cogging cases,
# converter-overhead cases, the previous package's quoted spreadsheet numbers, blade-geometry fractions, infill, the listed 516 rpm at 24 V)
allow |= {("96", "%"), ("5", "mN m"), ("8", "mN m"), ("40", "mN m"), ("49", "W"), ("5.6", "W"), ("0.018", "N m"), ("90", "%"), ("18", "%"), ("35", "%"), ("85", "%"), ("55", "%"), ("12", "%"), ("15", "%"), ("100", "%"),
          ("0.30", "W"), ("0.20", "W"), ("0.50", "W"), ("0.15", "W"), ("0.13", "W"), ("0.3", "W"), ("516", "rpm"), ("0.5", "N m"), ("0.2", "N m"), ("100.5", "%")}
typed = [(a, b.strip()) for a, b in typed]
typed = [t for t in typed if (t[0], t[1]) not in allow and not (t[1] == "A" and t[0] in ("1.35", "2", "1.5", "8"))]
gate("report text contains no hand-typed result numbers (W / % / rpm / torque / current outside f-string expressions; unit literals allow-listed)", not typed, f"found {typed[:12]}" if typed else "none found")
json.dump(dict(gates=log, fails=fails), open(os.path.join(ROOT, "docs", "qa_gates_v4.json"), "w"), indent=1)
with open(os.path.join(ROOT, "docs", "QA_LOG_v4.md"), "w") as f:
    f.write("# Quality-gate log (v4 low-flow turbine)\n\nThe `/quality` skill is not installed in this environment, so these manual gates (`tools/qa_gates_v4.py`) stand in for it. Each gate is a script check on the exported files and result JSONs, re-run after every correction.\n\n| Gate | Result | Detail |\n|---|---|---|\n")
    for n, r, dd in log: f.write(f"| {n} | {r} | {dd} |\n")
    f.write(f"\n**{len(log) - fails} of {len(log)} gates pass.**\n")
print("fails:", fails)
