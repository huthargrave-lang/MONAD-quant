# Waterproofing and mechanical validation procedure

Do not call the assembly waterproof until every step below has been done and logged. Each test names
the pass criterion and what to do on failure.

## 0. Bench measurements before any sealing work (configuration A; for B read "spindle" for "shaft")
1. Motor: KV (drive with a drill at a known rpm, read line-to-line AC voltage; KV = rpm / (V_rms x 1.414 ... use the convention in REPORT.md)), line resistance (4-wire or a known DC current), cogging torque (string + weights on a pulley, or a torque gauge), shaft diameter/protrusion, bell-face and base hole patterns, hollow-shaft bore, mass, axial play of the bell.
2. Shaft: 12 mm 316 shaft with the SKF Speedi-Sleeve pressed at the seal position (sleeve OD 12.56 mm, Ra <= 0.4 um, no axial scratches); bearing seats h6; cross-pin hole deburred.
3. Front cap: bearing bore 28 H7, seal bore 22 H8, O-ring grooves per the drawing (width 3.6, depth 2.05, Ra <= 1.6 um in the groove, no burr at the chamfer), flatness of the flange face.
4. Printed rotor: 12 mm bore reamed to 12.05 H8, pin hole aligned with the shaft, static balance to 0.5 g; the printed clamp ring must close on the tube without crushing it (torque the M4 bolts to 1.5 N m).

## 1. Static seal test of the drum (no spindle, blank rear cap or spindle with the seal fitted and the bore plugged)
1. Assemble the drum with lightly greased O-rings (silicone grease, NBR 70 O-rings) and the lip seal. Put a moisture indicator card and a small desiccant bag inside.
2. Vacuum test (preferred, Blue Robotics method): fit a vacuum plug/valve in the rear cap or spindle bore, pull -70 kPa (-10 psi), isolate, wait 15 minutes. Pass: pressure change < 1 kPa. Fail: find the leak with soapy water while applying +30 kPa air (no more: the caps are retained by the O-rings and the clips only).
3. Submersion test: 1 m depth (bucket/barrel), 24 h, drum stationary. Pass: card unchanged, no droplets. Repeat at 2 m if the site is deeper.
4. Thermal cycling: 3 cycles of 5 C water -> 40 C warm room -> 5 C water (each >= 1 h) then re-check the card. This exercises the breathing of the enclosure through the lip seal, which is the weakest point.

## 2. Rotating seal test (full rotor on the spindle, no generator load)
1. Spin the drum on the spindle in air with a drill on the strut-boss side at 300, 650 and 1300 rpm (runaway). Measure the breakaway and running friction torque with a string and spring scale on the ring (record in N m). Pass: breakaway < 0.03 N m with the PTFE seal (< 0.05 N m with NBR); otherwise the seal is too tight or the spindle finish is wrong.
2. Submerge to 0.5 m and spin at 650 rpm for 1 h, then 1300 rpm for 10 min, stop, pull the vacuum test again (step 1.2) and open the drum. Pass: dry card, no water line on the spindle inboard of the seal.
3. Pressure plus rotation: run at 650 rpm at 2 m depth for 8 h (a pond/tank or a weighted river deployment). Open and inspect. Pass: dry.
4. Hydrostatic-only check of the seal direction: the lip must face the water. If water is found inboard of the seal after rotation but not after static tests, the seal is installed backwards or the spindle is scored.

## 3. Generator and electrical checks
1. With the drum assembled and the generator connected, spin at 300 / 475 / 650 rpm and record open-circuit line voltage (should match KV x rpm), then connect the rectifier + resistive load and record DC voltage, current and the torque needed (string method) to verify the copper-loss model in REPORT.md.
2. 2 h run at 650 rpm with the load giving ~15 W of generator loss (the thermal worst case) and the drum in 20 C water: measure the winding resistance immediately after stopping (R rises 0.39 %/K for copper) to infer the winding temperature. Pass: rise < 50 K.
3. Insulation: 500 V DC megger between any phase and the drum/spindle before and after the immersion tests. Pass: > 20 Mohm.

## 4. Mechanical checks in the water
1. First deployment at ~1 m/s: confirm self-start (it may need a push below ~1.2 m/s with an NBR seal), record rpm (optical tachometer through the duct or from the generator frequency) and DC output versus a water-speed measurement (float method or a cheap flow probe). Compare to REPORT.md.
2. 24 h run, then inspect: bond line of the blade ring, cable potting, strut boss clamp, O-ring extrusion marks, any play at the bearings (axial play of the rotor < 0.1 mm).
3. Runaway: disconnect the load at the highest site speed for 5 minutes; listen for cavitation (crackling), check for vibration; reconnect. Fit a dump load or a brake switch before leaving the unit unattended.

## 5. Service intervals (prototype)
- Every 2 weeks for the first 2 months: vacuum test, open and inspect the desiccant card.
- Lip seal: replace at 6 months or at the first sign of moisture; keep the spindle track polished.
- Bearings: replace if any roughness; they are sealed 2RS and live on the dry side, so they should outlast the seal.
