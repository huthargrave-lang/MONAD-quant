# Simplified prototype turbine v5 (three printed parts + the CubeMars GL60 KV25)

Read `REPORT_v5.md` (or `REPORT_v5.pdf`). The blade geometry is the v4 optimised low-flow design (`../turbine_lowflow_v4`), unchanged;
the mechanical design is reduced to a one-piece printed rotor, a printed housing and a printed mount (which is also the housing lid),
plus a small printed bell adapter and off-the-shelf hardware (one lip seal, one bearing, one stainless sleeve, screws, inserts, an O-ring,
a cable gland). Nothing has been printed or tested.

| file | what |
|---|---|
| `out/v5_assembly.step` | assembled model (all parts, motor envelope, hardware) |
| `out/v5_rotor.step`, `out/v5_rotor_PRINT.stl` | one-piece rotor (print nose down, supports under the blades) |
| `out/v5_housing.step`, `out/v5_housing_PRINT.stl` | housing (print open end down, internal supports under the front wall) |
| `out/v5_mount.step`, `out/v5_mount_PRINT.stl` | mount = rear lid + stator carrier + arm + stake socket (print lid face up) |
| `out/v5_adapter.step`, `out/v5_adapter_PRINT.stl` | bell adapter (print front face down) |
| `out/v5_motor.step` | GL60 envelope used in the assembly |
| `out/fig_v5_section.png`, `out/fig_v5_exploded.png`, `out/fig_v5_power.png` | section, exploded view, predicted power |
| `out/v5_info.json`, `out/v5_results.json` | geometry/check results, model results |
| `BOM_v5.csv` | parts list |

Regenerate (same venv as the v4 package): `python make_v5.py && python eval_v5.py && python make_report_v5.py && python build_pdf_v5.py`.
