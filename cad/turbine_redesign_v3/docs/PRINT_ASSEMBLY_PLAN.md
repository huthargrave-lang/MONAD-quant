# Print and assembly plan (redesign v3, variant min76 unless noted)

Provisional process assumptions (the printer, nozzle and filament are unspecified): FDM, 0.4 mm nozzle, 0.2 mm layers,
ASA (PETG acceptable; nylon excluded for water uptake; no carbon-filled filaments without coupons), enclosure or draft shield,
parts dried and annealed per the filament maker's guidance. Printed-part allowables used in the checks (ASSUMED, to be replaced by
coupons): long-term wet/aged 8 MPa in-plane (XY) and 4.5 MPa across layers (Z); short-term 15 / 8 MPa. Bulk filament strength is
not used anywhere as an allowable.

## Per-part print specification

| Part (file) | Qty | Material | Orientation (bed = -Z of the PRINT STL) | Walls / infill / local solid | Supports | Critical features and post-processing |
|---|---|---|---|---|---|---|
| Blade (`min76_blade_k_PRINT.stl`) | 3 | ASA | pressure side down, span along the bed X axis, tongue up: layers run along the span so flap bending is carried in-plane | 4 perimeters, 100 % infill (the part is thin) | tree supports under the leading-edge overhang and the tip only; none on the pressure face | ream the 2 pin holes to 3.0 H8 *with the blade seated in its pocket* (match-drill through the carrier pad); sand the pressure face; weigh and match the three blades to 0.3 g (add epoxy at the tip tongue if needed); 1.0 mm trailing edge is the minimum printable here |
| Carrier segment (`min76_carrier_k_PRINT.stl`) | 3 | ASA | lying on one parting-plane bolt-ear face (arc standing on its side) | 4 perimeters; 100 % infill in the pad/pocket/ear/lug zones (modifier volume); 40 % gyroid elsewhere | tree supports under the lips and under the pad side of the arc | print one segment first as a coupon: check the 76.4 bore on the tube (scrape to a snug slip fit), the lug fit in the cap notch (0.15 clearance) and the pocket on a blade tongue; pin holes printed 2.8 and reamed 3.0 H8; bolt holes 3.2 |
| Dome (`min76_dome_PRINT.stl`) | 1 | ASA | base face down | 100 % infill | none | 3 countersunk M3 holes; sand to the carrier lip |
| Drive disc (`min76_drive_disc_PRINT.stl`) | 1 | TPU 95A | flat, dogs up | 100 % infill, 3 perimeters | none | check dog fit in the cap pockets (0.3 mm clearance) |
| Duct / guard ring (`min76_duct_PRINT.stl`) | 1 (3 arcs) | ASA | ring axis vertical | 3 perimeters, 30 % infill | none | strut slots 16.6 x 4.6; join the arcs with M4 lap joints (not modelled) |

Tolerance coupons to print before the real parts: (1) a 20 mm tall ring with the carrier bore (76.4) to set the XY compensation;
(2) a pocket coupon (30 x 12 x 7) and a tongue coupon (29.7 x 11.7); (3) a 2.8 mm hole coupon to confirm the ream allowance.
Manufacturing variability: expect +-0.2 mm on printed dimensions and +-0.15 on the tube bore; all sealing dimensions are machined, no
printed surface seals anything.

## Machined and metal parts (each with its function)

| Part | Why it must be machined / metal | Drawing |
|---|---|---|
| Front cap (Delrin) | O-ring sealing lands (Ra 0.8) and a 21 H7 bearing seat; printed Delrin-substitutes are porous and creep under the bearing | `cad/out/min76_drawing_front_cap.png` |
| Rear cap (Delrin) | O-ring lands, 21 H7 bearing bore with the thrust shoulder, 22 H8 lip-seal seat concentric to the bearing (runout < 0.05) | `cad/out/min76_drawing_rear_cap.png` |
| Spindle (6061-T6, hard-anodised) | 15 h6 bearing journals, the lip-seal counterface (Speedi-Sleeve on it), the stator flange and the defined metal heat path to the water | `cad/out/min76_drawing_spindle.png` |
| Strut boss (6061-T6 plate) | wetted heat sink for the stator losses, 15 H7 spindle bore with a cross pin, strut pockets | `cad/out/min76_drawing_boss_strut.png` |
| Struts (6061-T6 flat bar) | bending from the rotor thrust (12-19 MPa at 3 m/s) exceeds the printed allowables; metal also gives the forward jog that keeps the struts inside the 76 mm envelope | drawing 5 (same file) |
| Pressure tube (6061-T6 stock) | the watertight wall: printed walls are porous | BOM item 2 |

## Assembly sequence (what goes on, in what order, and why)

1. **Measure the motor** (KV, R_LL, L, cogging, hole patterns, bore, bell runout). Enter `motor_pcd`, `motor_hole`, `bell_pcd` in `cad/make_v3.py`, regenerate, then machine the spindle flange and the caps.
2. **Spindle**: press the SKF Speedi-Sleeve 99059 onto the seal journal with its installation tool (or, if not approved on aluminium, fit the 316 journal sleeve alternative); check runout of the journals < 0.02 mm; fit the DIN 471-15 circlip loosely in its groove later.
3. **Stator to spindle**: thermal paste on the flange face; 4 screws (per measured pattern) with Loctite 243; route the three leads through the lead slot into the spindle bore and out of the rear side hole; leave 150 mm.
4. **Rear bearing and rear cap**: slide the rear bearing onto the spindle up to the collar; grease the O-rings (silicone) and seat them in the rear-cap grooves; press the lip seal into the rear cap from the wet face with the lip toward the water; slide the rear cap over the spindle from the rear (over the sleeve: a lead-in cone or tape protects the lip) until the bearing seats in the cap bore against the shoulder.
5. **Tube**: slide the anodised tube over the motor from the front, onto the rear cap plug (chamfered end first; do not twist the O-rings).
6. **Drive disc**: bolt the TPU disc to the bell face (4x M3), dogs forward.
7. **Front bearing and front cap**: front bearing onto the spindle nose, then the circlip into its groove; O-rings into the front-cap grooves; present the front cap so the dog pockets index on the dogs, push the cap into the tube and over the bearing until the flange meets the tube end. The drum is now sealed: do the vacuum test now (M6 port).
8. **Carrier**: fit the three blades (tongues into pockets, match-ream, pins pressed from the pad side); close the three segments around the tube with the lugs in the cap notches and the lips over both flanges; 6x M3 316 bolts + nyloc to 0.6 N m. Static-balance the rotor on the spindle (add tape/epoxy at a lip until it rests in any position).
9. **Dome**: 3x M3 into the front cap.
10. **Boss**: slide the boss onto the spindle rear, align the cross-pin hole, press the 3 x 36 pin; lay the leads in the cable channel; pot the spindle rear bore and channel entry (epoxy, 20 mm plug) with the leads in a 5 mm bend radius; check continuity and insulation.
11. **Struts and duct**: tabs into the boss pockets, pins pressed; feet bolted to the duct (6x M4 nyloc) with the jog forward; check that no strut touches the carrier or blades through a full rotation (> 2 mm clearance by design).
12. **Electrical**: leads to the junction at a duct foot (potted splice to the 3 x 18 AWG cable), cable to the dry box per the schematic in the report.

Disassembly for service is the reverse: pull the boss pin, slide the boss off, unbolt the carrier, pull the front cap (lever at the flange), slide the tube off, slide the rear cap off the spindle. Nothing is bonded.
