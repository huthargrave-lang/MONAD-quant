#!/usr/bin/env python3
"""Robustness of the blade-count / selection conclusion (review M2): the best candidate per blade count (from the sweeps) re-evaluated
with the final model under the baseline, Re/1.5, Re x1.5, the no-induction (upper-bound) start model and the hand-started objective.
Writes robustness.json."""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coupled_eval as ce, optimize_blades as ob
HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(HERE, "sweep_stage1.json"))) + json.load(open(os.path.join(HERE, "sweep_stage2.json"))); sel = json.load(open(os.path.join(HERE, "selected_design.json")))
VOBJ = ob.VOBJ; W_LOW = ob.W_LOW
def J(res, weights, gate=True):
    tot = 0.0
    for V, w in weights.items():
        p = res["perV"][str(V)]; tot += w * (p["Pout_gated"] if gate else (p["op"]["Pout"] if p["op"] else 0.0))
    return tot
cands = {"selected": sel["spec"]}
for B in (2, 3, 4, 5):
    best = max((r for r in S if r["spec"]["B"] == B and r["meta"].get("hub_wall_deg", 0) >= 12), key=lambda r: r["J"]["lowflow"], default=None)
    if best: cands[f"best B{B}"] = best["spec"]
out = {}
for name, spec in cands.items():
    row = dict(spec=spec)
    for case, kw in (("baseline", {}), ("Re/1.5", dict(re_shift=1 / 1.5)), ("Re x1.5", dict(re_shift=1.5)), ("upper-bound standstill", dict(static="viterna"))):
        res = ce.full_eval(spec, "A", vs=[0.5, 0.6, 0.7, 0.8, 0.9, 1.0], **kw)
        row[case] = dict(J_uniform=J(res, {V: 1 / 6 for V in VOBJ}), J_lowflow=J(res, W_LOW), J_uniform_hand=J(res, {V: 1 / 6 for V in VOBJ}, False), J_lowflow_hand=J(res, W_LOW, False),
                         min_start=ce.min_flows(res)[0])
    out[name] = row
    print(name, spec, {c: (round(row[c]["J_uniform"], 3), round(row[c]["J_lowflow"], 3), row[c]["min_start"]) for c in row if c != "spec"})
json.dump(out, open(os.path.join(HERE, "robustness.json"), "w"), indent=1)
