# Turbine-generator assembly package

Engineering study and manufacturing-ready CAD for a compact, waterproof generator unit around the
reviewed 8 in rotor (`../water_turbine_blade/`). **Not built or immersion-tested yet** - see `VALIDATION.md`.

| File | What it is |
|---|---|
| `REPORT.md` | The engineering report: generator selection, architecture comparison (A/B/C/D), recommended design, enclosure and seal engineering, loads, performance, risks, verified-vs-assumed, BOM. Start here. |
| `BOM.csv` | Bill of materials for configuration A with vendors, part numbers, prices and the basis of each price. |
| `VALIDATION.md` | Bench, static, rotating, electrical and in-water validation procedure and service intervals. |
| `cad_out/A_*.step`, `cad_out/A_assembly.step` | Configuration A (recommended): every part as STEP (mm) plus the positioned assembly. Printed parts also as `.stl`. |
| `cad_out/B_*.step`, `cad_out/B_assembly.step` | Configuration B (compact hub-integrated alternative). |
| `cad_out/A_section_view.png`, `cad_out/A_exploded_view.png` | Section through the axis with the waterproof boundary marked; exploded view. `B_*` likewise. |
| `make_assembly.py` | Parametric CadQuery generator for both configurations (`PARAMS`, `TO_MEASURE`), with interference checks. |
| `make_views.py` | Renders the section and exploded views (`python make_views.py A` or `B`). |
| `calcs.py` | Loads, bearing life, seal-friction sensitivity, thermal, depth stack-ups. |
| `calcs_electrical.py` | Generator/drivetrain operating points across 1-2 m/s for the candidate generators (writes `electrical_results.json`). |
| `make_report.py` | Assembles `REPORT.md` from the computed results. |
| `research/` | The three research notes (generators, sealing/bearings/enclosures, magnetic couplings and seals) with every URL and verified/assumed tags. |

Regenerate everything (after entering the measured motor dimensions in `make_assembly.py`):
```bash
pip install cadquery numpy matplotlib trimesh
python make_assembly.py && python make_views.py A && python make_views.py B
python calcs.py && python calcs_electrical.py && python make_report.py
```
