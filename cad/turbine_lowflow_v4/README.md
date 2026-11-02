# Low-flow turbine v4 (0.5-1.0 m/s, CubeMars GL60 KV25, arrangement A)

Start with `docs/REPORT_v4.md` (or `docs/REPORT_v4.pdf`). Status: model-based design package, reviewed by three independent reviewer
agents (`docs/REVIEW_LOG_v4.md`) and checked by manual quality gates (`docs/QA_LOG_v4.md`; the `/quality` skill is not installed in
this environment). Nothing has been built or tested.

| Folder | Contents |
|---|---|
| `model/` | `polars.py` (NeuralFoil polar tables + Viterna), `bem_lowflow.py` (vectorised BEM, standstill torque, parametric design), `generator_lowflow.py` (GL60, friction, rectifier, converters, equilibrium), `feasibility.py` (hydraulic bounds, loss shares, gear study), `optimize_blades.py` (stages 1-2, selection), `coupled_eval.py` (figures 2-9, comparison, sensitivities); JSON results |
| `cad/` | `make_v4.py` (parametric assembly: two-piece shaft, caps, shell clamp, struts, ring arcs; STEP/STL export, clash and clearance checks), `views_v4.py` (figure 10) |
| `out/` | figures `fig*.png`, `v4_assembly.step`, per-part `v4_*.step`, print-oriented `v4_*_PRINT.stl`, `v4_info.json` |
| `docs/` | report generator and report (md / html / pdf), `BOM_v4.csv`, `make_test_plan_v4.py` -> `TEST_PLAN_v4.md`, `make_review_log_v4.py` -> `REVIEW_LOG_v4.md`, `QA_LOG_v4.md` |
| `tools/` | `qa_gates_v4.py` (quality gates), `package_v4.py` (zip) |

Regenerate (venv with cadquery, numpy, scipy, matplotlib, trimesh, manifold3d, aerosandbox/neuralfoil, markdown, playwright):
`python model/polars.py && python model/optimize_blades.py 1 && python model/optimize_blades.py 2 && python model/feasibility.py &&
python model/coupled_eval.py && python model/robustness_v4.py && python cad/make_v4.py && python cad/views_v4.py && python model/structure_v4.py &&
python docs/make_test_plan_v4.py && python tools/qa_gates_v4.py && python docs/make_review_log_v4.py && python docs/make_report_v4.py && python docs/build_pdf_v4.py`
(stage 1 of the sweep takes ~10 min on 4 cores; the selection step in stage 2 applies the hub-wall packaging constraint and writes `selection.json`).
