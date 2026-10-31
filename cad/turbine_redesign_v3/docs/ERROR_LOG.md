# Error-review and correction log (redesign v3)

Format: ID | review pass | severity (critical / major / minor) | finding and evidence | correction | verification. Entries E01-E16 were
found during the design work itself; R-entries come from the four review passes (calculation/units, mechanical-CAD, printability,
skeptical failure-mode), performed by independent reviewer agents on the exported files, then re-checked on the final files.

| ID | Pass | Sev. | Finding (evidence) | Correction | Verification |
|---|---|---|---|---|---|
| E01 | calc | minor | Spreadsheet reproduction script read the raw-input row (starts with "10") as strip 10: per-strip deviations of 98-1e6 % | select the 20 rows after the "Strip" header | all 14 columns within 0.43 % (chord, export rounding); totals exact (`model/reproduce_trial1.py`) |
| E02 | CAD | major | Carrier segment 0 not rotated to its flange notches: lugs 60 deg off, 42.6 mm3 rigid overlap with both caps | rotate every segment by 120k+60 | pairwise overlap 0.00 |
| E03 | CAD | critical | Rear bearing retained by a 19 mm circlip that cannot pass the cap's 16 mm bore (and sat inside the cap wall): no thrust path | integral 17.6 x 1.3 spindle collar inside an 18 mm wall hole; cross-located bearings | collar/cap, collar/bearing, collar/seal overlaps 0.00; thrust path listed in the section view |
| E04 | CAD | major | Front circlip modelled inside solid cap material (135 mm3) | stepped blind pocket: 21 H7 x 4.2 seat + 20 x 1.9 circlip recess; spindle nose shortened | overlap 0.00 |
| E05 | CAD | major | Dome base overlapped the carrier front lip (450-480 mm3) | dome base 67.8 mm inside the lip ring; dome mounting holes moved to r 29 | overlap 0.00 |
| E06 | CAD | major | Flat-topped blade pads protruded above the hub cylinder, intersecting the blade roots (207 mm3) | pad top trimmed to r = 48.2; tongue height = pocket depth + 1 | overlap 0.00 |
| E07 | packaging | critical | Printed NACA struts behind the boss put the operating depth at 93.3 mm (robust) / 83.3 mm (min) | 6061-T6 flat-bar struts with a 14 mm forward jog alongside the drum, inside the envelope; strut stress 12-19 MPa at 3 m/s | depth 85.3 / 75.1 mm; strut/carrier, strut/blade, strut/tube overlaps 0.00 |
| E08 | CAD | minor | Strut tab penetrated the boss pocket floor (1.8-3.4 mm3) | tab start radius +0.4 | overlap 0.00 |
| E09 | calc | major | Structural checks used thrust at the charging point (58 N at 3 m/s) instead of the maximum along the rotor curve (86 N) | `T_max` over the curve stored by the system model and used by the structure script | numbers in REPORT section 5 are the re-run values |
| E10 | calc | minor | Thermal summary hard-coded "+45 K" while the table computed +29 K at 1.2 A | computed in-line | both lines agree (+29 K) |
| E11 | CAD | minor | Hollow 6 mm dome shell failed as a Boolean in OpenCascade | solid printed dome | builds; 100 % infill in the print plan |
| E12 | electrical | critical | SB560 (60 V) rectifier below the 2 m/s runaway (55 V) and far below 3 m/s (85 V); 5KP60A TVS would conduct steadily at the 2 m/s runaway | MBR10100 bridge; 5KP85A TVS; dump at 45 V; 3 m/s = disconnect/retrieve case (dump 87 W + 32 W copper and brake 134 W copper are both unsafe there) | `system_model_v3.py` dump/brake/open rows per speed |
| E13 | process | major | Manufacturer pages (cubemars.com, skf.com, bluerobotics.com, diodes.com, victronenergy.com, digikey.com) are blocked from this session | values carried from the 31 Oct 2026 review citations and search extracts, tagged in the BOM; re-verification listed as a required action | BOM "price basis" column |
| E14 | CAD audit | - | All seven findings of the independent review reproduced on the packet STEP (188.600 / 78.800 mm, 1369.60 mm3, no grooves, 8.000 mm, 0.500 mm, no cable hardware, duct behind the rotor) | each addressed in v3 (REPORT section 2) | `audit/verify_cad_audit.txt` |
| E15 | calc | minor | GL60 Kt quoted as 0.45 (page) and 0.40 (reseller) | energy-consistent Kt = 60/(2 pi 21.5) = 0.444 used; +-10 % sensitivity noted | REPORT section 6 |
| E16 | CAD | major | Drive disc screwed to both the bell and the cap could not be assembled (screws inaccessible once the cap is on) | TPU dog clutch: disc bolted to the bell face only; 4 dogs into blind cap pockets | assembly sequence step 7; overlap 0.00 |
