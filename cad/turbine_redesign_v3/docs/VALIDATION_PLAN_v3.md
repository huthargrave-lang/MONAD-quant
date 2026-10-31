# Validation plan with acceptance criteria (redesign v3)

Analytical checks in this package are NOT tests. Nothing below has been performed. Each gate names the measurement, the
pass criterion and the action on failure. Instrument: optical tachometer (through the duct), DC V/I logger (10 Hz), thermocouples
or the winding-resistance method, a vacuum pump with gauge, a spring scale and thread for torque, a float or probe for water speed.

| # | Gate | Measurement | Acceptance | On failure |
|---|---|---|---|---|
| 1 | Generator characterisation (bench, before machining) | KV (3 speeds, 3 line pairs), R_LL, L_LL, cogging torque (full turn), bell runout, hole patterns, bore, mass | KV 20-26 rpm/V; R_LL 4.5-6.5 ohm; cogging <= 30 mN m; runout <= 0.05 mm | update the model (`system_model_v3.py` ASSUMPTIONS) and the CAD placeholders; if Kt/sqrt(R) < 0.17 reject the motor |
| 2 | Printed coupons | tube-fit ring, pocket/tongue, 2.8 mm hole; tensile bars XY and Z, wet-conditioned 7 days | slip fit on the tube; tongue 0.1-0.3 clearance; wet Z tensile >= 18 MPa, XY >= 32 MPa | change XY compensation / material; re-run `structure_seal_thermal_v3.py` with measured allowables |
| 3 | Machined parts | plug OD vs measured tube bore; groove depth; bearing bores; seal seat; journal diameters after anodising; sleeve fit | gland squeeze 15-25 % computed from the measured pair; bores H7/H8; journal 15 h6; runout < 0.03 | rework / re-anodise |
| 4 | Static seal | vacuum -70 kPa (292 N per cap), hold 15 min; then 24 h submersion at 1 m; thermal cycle 5-40 C x3; moisture card inside | pressure decay < 1 kPa / 15 min; card dry | find the leak with +30 kPa and soap; check the lip orientation and the O-rings |
| 5 | Breakaway and running friction | thread-and-scale on the carrier, in air and submerged, cold (5 C) and after 24 h in silty water; all shaft angles | breakaway <= 0.045 N m (NBR seal) / <= 0.035 N m (PTFE); running <= 0.020 N m | PTFE seal; lower cogging motor; check sleeve finish |
| 6 | Rotating seal | 650 rpm 1 h and 1300 rpm 10 min at 0.5 m; then 8 h at 650 rpm at 2 m; vacuum test and open | dry; no water line inboard of the seal | seal backwards or journal scored: replace |
| 7 | Thermal | 2 h at 1.2 A generator current (load bank) with the drum in 20 C water; winding resistance before/after; boss temperature | winding rise <= 50 K; boss <= 35 C | lower the current limit; improve the stator-flange joint (paste, flatness) |
| 8 | Drum balance and overspeed | static balance; spin to 1300 rpm in air (drill) and 1900 rpm in water (no load, 3 m/s equivalent only if a flume allows) | no visible vibration; no blade or pin movement; runout unchanged | rebalance; check pins |
| 9 | Self-start | in the river or flume at 0.9, 1.0, 1.2 m/s, controller in RUN, generator open: does the rotor start from rest at every stop angle? | starts within 60 s at >= 1.0 m/s (target); report the measured minimum | PTFE seal; accept push-start; redesign the root chord |
| 10 | Power curve | rpm and DC V/I vs water speed at 1.0 / 1.5 / 2.0 m/s with the real duct; battery current | within -30 % / +10 % of REPORT table 7 (water-to-DC 17 / 21 / 22 %) | update the model; revisit hub ratio or blade design |
| 11 | Protection | full battery (charger stops): bus rises, dump engages <= 45 V, holds < 50 V; disconnected load at 2 m/s: open-circuit bus <= 60 V; brake switch at <= 1.5 m/s stops the rotor within 10 s; fuse opens on a shorted output | as stated; no part above 70 C | re-tune the relay module thresholds; larger heatsink |
| 12 | Endurance | 100 h in representative water; 2-week inspections (vacuum test, card, seal track, pins, bolts, bond lines, blade tips) | dry; no loosening; no cracks at blade roots or lips | redesign the flagged feature |

Service intervals (prototype): 2 weeks for the first 2 months; lip seal at 6 months or first moisture; carrier bolts re-torqued after
the first 24 h in the water (creep of the printed ears).
