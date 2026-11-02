# Practical prototype testing plan (v4 low-flow turbine)

Nothing in this package has been measured. The gates below convert the model's assumptions into numbers, in the order that
unblocks the next decision. Instruments: optical tachometer (through the guard ring), DC V/I logger (10 Hz), bench supply and load
bank, a spring scale + thread for torque, a vacuum pump with gauge, a float / probe for water speed, a thermometer.

| # | Gate | Measurement | Acceptance / what it updates | On failure |
|---|---|---|---|---|
| G1 | GL60 characterisation (bench, BEFORE machining) | KV (3 speeds, 3 line pairs, scope on the DC after a bridge), R_LL, L_LL, cogging torque over a full turn (thread + scale on a 50 mm arm), no-load loss at 200 / 400 / 700 rpm (drive with a drill, measure the torque), hole patterns (stator / bell), lead exit, bell runout | KV 20-26; R 4.5-6.5 ohm; cogging <= 30 mN m (model 24); no-load <= 0.3 W at 300 rpm | update `generator_lowflow.GEN`, re-run the selection; cogging > 40 mN m moves the self-start to >= 0.6 m/s |
| G2 | Breakaway and running friction of the sealed shaft | front cap + shaft + seal + bearing on the bench, wet: breakaway and running torque at 100 / 300 / 600 rpm | breakaway <= 12 mN m (model 12 without cogging); running <= 7 mN m | NBR seal excluded; polish the journal; check seal squeeze |
| G3 | Printed coupons | hub-pocket coupon with one blade tongue (0.15 clearance); 3.4 mm hole; tensile XY/Z wet 7 days | slip fit with no play; wet Z tensile >= 18 MPa | adjust XY compensation; thicker root |
| G4 | Static seal | nacelle assembled, vacuum -50 kPa 15 min; 24 h at 1 m; thermal cycle 35 C -> 5 C | decay < 1 kPa / 15 min; card dry | find the leak with +20 kPa and soap; re-seat the penetrator |
| G5 | Rotating seal | 1 h at 400 rpm in a bucket at 0.3 m, then 8 h at 300 rpm; open and inspect | dry inside; no scoring | replace the seal; polish |
| G6 | Static (starting) torque of the rotor | rotor on the bench in a flume or towed at 0.5 / 0.6 / 0.7 m/s with the shaft locked: torque by thread + scale at 3 stop angles | >= 35 / 50 / 70 mN m (model 41 / 59 / 80 at 0.5 / 0.6 / 0.7 with the Viterna standstill model; +-30 %) | the standstill model is the least certain part of the BEM: re-fit `static_torque` and re-run the selection |
| G7 | Self-start | in the stream at 0.5, 0.6, 0.7 m/s (measured 0.3 m ahead of the rotor), converter in MPPT, from rest at 3 stop angles | starts within 60 s at the model's minimum (0.5 m/s baseline; bounds 0.4-0.6) | report the measured minimum; the device is still usable hand-started |
| G8 | Power curve | rpm, bus V/I, battery current at 0.5 / 0.6 / 0.7 / 0.8 / 1.0 m/s; log 10 min each | within -30 % / +10 % of REPORT table 6 (0.16 / 0.49 / 0.98 / 1.65 / 3.6 W net) | update the polar knockdown (fig. 8) and the friction; revisit chord scale |
| G9 | Converter behaviour | minimum input voltage at which it draws power; efficiency at 0.5 / 1 / 3 W input; quiescent current; MPPT hunting around the rotor's torque peak | V_min <= 5 V; eta >= 80 % at 1 W; quiescent <= 30 mW | choose the other converter candidate; add a bulk capacitor |
| G10 | Survivability 1.0-2.0 m/s | at the fastest available flow: open-circuit bus (must stay <= 60 V TVS standoff: model 52 V at 2 m/s), bus current with the converter clamped (<= 1.35 A), blade tip clearance to the ring, no vibration | as stated | current limiter / relay dump; stiffer struts |
| G11 | Shallow-water effects | run at 0.6-0.8 m/s with the axis at 0.15 / 0.25 / 0.4 m depth and with the ring 50 mm above the bed; note air entrainment and surface dimpling | output within 20 % of the deep case at >= 0.25 m | restrict the minimum deployment depth in the instructions |
| G12 | Endurance | 50 h in the stream; inspect the seal, pins, bolts, blade roots, silt in the ring; moisture card | dry; no loosening; no cracks | redesign the flagged feature |

Minimum data set to close the model: G1 (generator), G2 (friction), G6 (starting torque), G8 (power curve). These four replace the
largest assumptions in order of their effect on the 0.5-0.7 m/s prediction.
