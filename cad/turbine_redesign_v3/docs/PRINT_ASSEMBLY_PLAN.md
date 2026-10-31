# Print and assembly plan (redesign v3.1, variant min76 unless noted)

Provisional process assumptions (the printer, nozzle and filament are unspecified): FDM, 0.4 mm nozzle, 0.2 mm layers,
ASA (PETG acceptable; nylon excluded for water uptake; no carbon-filled filaments without coupons), enclosure or draft shield,
parts dried and annealed per the filament maker's guidance. Printed-part allowables used in the checks (ASSUMED, to be replaced by
coupons, gate 2): long-term wet/aged 8 MPa in-plane (XY), 4.5 MPa across layers (Z), 2.7 MPa interlaminar shear; short-term 15 / 8 / 4.8 MPa.
Bulk filament strength is not used anywhere as an allowable. Printed volume: ~300 cm3 ASA + 8 cm3 TPU (~330 g + supports), roughly 30-40 h.

## 1. Per-part print specification

| Part (file) | Qty | Material | Orientation (bed = -Z of the PRINT STL, already applied) | Walls / infill / local solid | Supports | Critical features and post-processing |
|---|---|---|---|---|---|---|
| Blade (`min76_blade_k_PRINT.stl`) | 3 | ASA | pressure side down, span along the bed X, tilted -4.5 deg about Y so the root and tip low points are level; the airfoil-section tongue lies flat at the root end (no box, nothing protrudes) | 4 perimeters, 100 % infill | organic/tree supports with an interface layer under the leading- and trailing-edge overhangs; brim 5 mm | layers run along the span (flap bending in-plane); the two 3.0 mm axial pin holes are in the STL: clean them with a 3.0 drill *with the blade seated in its pocket* through the carrier holes; sand the pressure face; weigh and match the three blades to 0.3 g; 1.0 mm trailing edge is the minimum printable |
| Carrier segment (`min76_carrier_k_PRINT.stl`) | 3 | ASA | pad up, the 120-degree arc standing like a bridge with its axis along the bed X; the airfoil pocket opens upward and prints with vertical walls and no internal support (axis-vertical was rejected: the pocket roof would be a 39 mm flat overhang in a 0.15 mm fit) | 4 perimeters; 100 % infill in the pad / pocket / ears / lugs (modifier volume); 40 % gyroid elsewhere | brim; tree supports under the arc (bore), the lips and the ears; support interface 0.2 mm; the support scars sit on the bore, which is scraped to fit anyway | print one segment first as a coupon: 76.6 bore on the tube (scrape to a snug slip fit), lug in the cap notch (0.15), a blade tongue in the pocket (0.15 per side), nut trap on an M3 nyloc; pin holes 3.0 printed horizontal (drill-clean); bolt holes 3.2 |
| Dome (`min76_dome_PRINT.stl`) | 1 | ASA | base face down | 100 % infill | none | countersink the 3 M3 holes 90 deg x 6.5; sand to the carrier lip |
| Drive disc (`min76_drive_disc_PRINT.stl`) | 1 | TPU 95A | flat, dogs up; the screw counterbores print as holes from the top | 100 % infill, 3 perimeters | none | dogs engage 3.5 mm into the cap pockets with 0.3 mm radial clearance; check on the cap before fitting the bell |
| Duct / guard ring (`min76_duct_PRINT.stl`) | 1 (3 arcs) | ASA | ring axis vertical; split into three 120-degree arcs (the ring is 237 mm over the clevis bosses) with 20 mm lap joints, 2x M3 each (laps not modelled) | 3 perimeters, 30 % infill; clevis bosses 100 % | none | strut slots 16.6 x 4.6 through the ring into the clevis; 2x Ø4.3 per clevis; ID 210 gives 3.4 mm tip clearance |

Tolerance coupons before the real parts: (1) a 20 mm ring with the carrier bore (76.6) to set the XY compensation; (2) a pocket coupon
(the airfoil pocket in a 40 x 60 x 12 block, same STL profile) and a blade root stub; (3) a 3.0 mm horizontal hole coupon for the spring
pins; (4) tensile bars XY and Z, wet-conditioned 7 days (gate 2). Expect +-0.2 mm on printed dimensions and +-0.15 on the tube bore;
all sealing dimensions are machined, no printed surface seals anything.

## 2. Machined and metal parts (each with its function)

| Part | Why it must be machined / metal | Drawing |
|---|---|---|
| Front cap (6061-T6, hard-anodised) | O-ring sealing land (Ra 0.8), 21 N7 bearing seat for a rotating outer ring, circlip recess, dog pockets; 6061 keeps the plug clearance and the bearing fit over temperature (POM would not, R26/R33) | `cad/out/min76_drawing_front_cap.png` |
| Rear cap (6061-T6, hard-anodised) | O-ring land, 21 N7 bearing bore with the thrust shoulder, 22 H8 lip-seal seat concentric to the bearing (runout < 0.03), labyrinth groove, counterbored vent | `cad/out/min76_drawing_rear_cap.png` |
| Spindle (6061-T6, hard-anodised) | 15 h6 bearing journals, the lip-seal counterface (Speedi-Sleeve on it), the integral stator flange with the lead channel, the split-ring groove, the reamed plug bore, and the defined metal heat path to the water | `cad/out/min76_drawing_spindle.png` |
| Split thrust ring (316) | carries the whole rotor thrust from the rear bearing into the spindle; split so the bearing can be installed (R11) | BOM 13 |
| Strut boss (6061-T6) | wetted heat sink, 15 H7 spindle bore with the cross pin, labyrinth tongue, strut pockets, lead groove | `cad/out/min76_drawing_boss_strut.png` |
| Struts (6061-T6 4 mm plate, profile-cut) | bending from the rotor thrust (16 / 11 MPa at 3 m/s) exceeds the printed allowables; the cranked profile keeps the struts inside the 76 mm envelope; no bending operation (R24) | drawing 5 (same file) |
| Potting plug (Delrin) | the demountable pressure barrier of the cable path (O-ring + epoxy) | drawing 6 (same file) |
| Pressure tube (6061-T6 stock, ends machined) | the watertight wall: printed walls are porous; the bored lands are the O-ring counterface | BOM item 2 |

## 3. Assembly sequence (what goes on, in what order, and why)

1. **Measure the motor** (gate 1: KV, R_LL, L, cogging, hole patterns and which is stator/bell, lead exit position, bore, bell runout). Enter the measured values in `cad/make_v3.py` (`motor_pcd`, `motor_hole`, `bell_pcd`) and `model/system_model_v3.py`, regenerate, then machine the spindle flange and the caps. Print the coupons (section 1) and the coupon segment.
2. **Spindle**: check the journals (15 h6 after anodising, runout < 0.02); apply Loctite 574 and press the SKF Speedi-Sleeve 99059 onto the seal journal with its installation tool, flange toward the rear, then break the flange off (or fit the 316 journal-sleeve alternative). Tef-Gel in the pin holes.
3. **Stator to spindle**: thermal paste on the flange front face; lay the GL60 pigtail in the 45-degree lead channel toward the bore; 4 screws (per the measured pattern, low-head, Loctite 243) from the counterbored rear face; feed the three leads through the 4.5 hole into the bore and out of the rear end. Inside the bore, splice each silicone pigtail lead to a 20 AWG PVC lead (solder + adhesive heat-shrink, staggered 10 mm apart so three splices fit in the 9 mm bore). Leave 200 mm of PVC lead out of the rear end.
4. **Potting plug**: thread the three PVC leads through the plug; strip 6 mm of each inside the plug body and solder-fill the strands; pot the plug with epoxy (Loctite EA E-30CL or 3M DP270), cure; fit the AS568-010 O-ring (silicone grease). Do not insert yet.
5. **Rear bearing, shim, thrust ring**: slide the 6702 bearing onto the spindle from the rear up to 4 mm behind the flange (it stops nowhere yet: hold it); slide the shim (start with 0.3) behind it; place the two halves of the split thrust ring in the groove with a smear of grease (they are captured once the cap is on).
6. **Rear cap**: grease and seat the O-ring in the rear-cap groove; slide the rear cap over the spindle from the rear (its 18 mm wall hole passes over the sleeve and surrounds the thrust ring) and press its bearing bore onto the bearing until the inner shoulder meets the bearing; now press the PTFE lip seal into the seat from the wet face, lip toward the water, over the sleeve (the seal is pressed AFTER the cap is on: it never passes the ring). Check the end play later (step 9).
7. **Tube**: slide the anodised tube over the motor from the front onto the rear cap plug (bored end first; do not twist the O-ring).
8. **Drive disc**: bolt the TPU disc to the bell face (4 low-head screws in the counterbores, Loctite 243), dogs forward, dogs clocked 45 deg from the screws (the holes enforce it).
9. **Front bearing and front cap**: front bearing onto the spindle nose, then the DIN 471-15 circlip into its groove (0.1 mm nominal gap); O-ring into the front-cap groove; present the front cap so the dog pockets index on the dogs, push the cap into the tube and over the bearing until the flange meets the tube end. Measure the drum end play (dial indicator on the drum, push/pull): 0.1-0.2 mm; if more, pull the front cap and change the shim (step 5) by the excess. The drum is now sealed: do the vacuum test now (M6 port, gate 4) and close the vent with the Dowty washer.
10. **Carrier**: fit the three blades (airfoil tongues into the pockets, drill-clean the pin holes through the pad, press the two 3 x 36 spring pins per blade from the front face, Tef-Gel); close the three segments around the tube with the lugs in the cap notches and the lips over both flanges; 6x M3 x 20 316 bolts through 12 mm penny washers into the nut traps, 0.3 N m. Static-balance the rotor on the spindle (add tape/epoxy at a lip until it rests in any position).
11. **Dome**: 3x M3 countersunk into the front cap.
12. **Boss and plug**: push the potting plug into the reamed spindle end (head against the spindle end face); slide the boss onto the spindle rear with its labyrinth tongue entering the cap groove, align the cross-pin hole, press the 3 x 36 pin (Tef-Gel); lay the three leads in the rear-face groove (6 x 3) to the OD and fill the groove with Dow 3145 RTV (removable) flush with the face; check continuity and insulation (> 20 Mohm at 250 V between phases and the spindle).
13. **Struts and duct**: tabs into the boss pockets, 3 x 20 pins pressed; legs through the duct slots into the clevises, 2x M4 x 25 + nyloc each; turn the rotor a full turn: nothing touches (3.4 mm tip, 2 mm labyrinth, > 20 mm strut-to-blade by design).
14. **Electrical**: leads along strut 0 (cable ties through 3 mm holes drilled in the strut leg) to a splice at the duct (adhesive heat-shrink solder splices to the 3 x 18 AWG cable), cable to the dry box per the schematic in the report; dump block and battery per BOM 35-38.

## 4. Service and disassembly

Seal replacement (6 months or first moisture): cut out the RTV in the boss groove and lift the leads out; pull the boss cross pin; slide
the boss rearward off the spindle (the leads pass through its bore); pull the potting plug out of the spindle end (its O-ring only);
unbolt the carrier (step 10 in reverse), remove the dome, pull the front cap and the tube; slide the rear cap rearward off the spindle:
it passes over the Ø12 plug head and the leads; press the old seal out from the inside, press the new one in from the wet face.
Reassemble from step 6. Nothing in this path is epoxy-bonded; the only cut-and-redo item is the RTV in the boss groove.
