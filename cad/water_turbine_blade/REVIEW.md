# Adversarial design review — 8 in / 3 in-wide hydrokinetic blade

**Scope.** Revision 1 of the blade (3 in hub, Reynolds-independent polar, plain-bore rotor) was handed to
three independent reviewers working from fresh context with only the files in this folder, each told to
recompute rather than trust the generator's output:

| Reviewer | Focus | Method |
|---|---|---|
| H — hydrodynamics | Schmitz/BEM equations, polar model, Cp claims, blade count, load matching | Wrote an independent BEM solver, derived the Buhl quadratic by hand, ran an XFOIL-class surrogate (NeuralFoil) for NACA 4412/4422 polars at Re 1e5–2e5, cross-checked with the Wilson–Lissaman Cp formula |
| C — CAD geometry | STEP/STL validity, measured geometry vs claims, orientation, wrap distortion, clearances, printability | Re-imported and sliced the solids with OpenCascade, regenerated the sections independently, checked meshes with trimesh (section C) |
| P — structure / practicality | Loads, stress, fatigue, hub/drivetrain, generator, self-start, runaway, cavitation, documentation | Polygon-integrated section properties, per-element BEM loads, inviscid panel method for Cp_min |

Plus the author's own sensitivity study (polar pessimism, root thickness, hub size). Reviewer scripts are
not shipped; their numbers are quoted below.

**Bottom line.** No blocker. The hydrodynamic method and the solid model were found correct (the
independent BEM reproduced Cp 0.3226 / Ct 0.6065 / 17.66 W / 22.13 N to four digits). The real problems
were optimism at the low-speed end (no Reynolds dependence), a hub that was the single largest loss, a rotor
hub that could not transmit torque, and several claims in the README that the numbers did not support.
All of these are fixed in revision 2; what remains open is listed at the end.

## Findings and resolution

Severity as assigned by the reviewers. "Fixed" = changed in revision 2 and re-verified; "Documented" =
cannot be fixed in geometry, now stated honestly in README.md.

| # | Source | Sev. | Finding (verified) | Resolution in revision 2 |
|---|---|---|---|---|
| 1 | H1, P4, author | Major | Polar model was Reynolds-independent. Actual section Re at TSR 3.5 is 0.9–1.3e5 at 1 m/s and 1.8–2.6e5 at 2 m/s (20 °C), never the "1e5–4e5" claimed; XFOIL-class drag at Re 1e5 is 1.5–1.8× the model's. Reviewer's Re-dependent BEM: Cp 0.292 / 0.315 / 0.325 at 1 / 1.5 / 2 m/s vs the single 0.323 claimed. | **Fixed.** Zero-lift drag now scales as (1.5e5/Re)^0.8 with Re computed per element (anchored on the surrogate data: NACA 4412 Cd 0.0182→0.0101 and 4422 0.0265→0.0149 from Re 1e5→2e5). Cp is reported per water speed; README Re range and "expect in the water" band corrected. |
| 2 | H3, P8, author | Major | The 3 in hub (hub ratio 0.375) was the dominant loss: 14 % of the disk area plus hub-loss; a 2 in hub gives +0.04–0.05 Cp. Published small hydrokinetic rotors use hub ratios 0.15–0.25. Also the hub-loss exponent used r instead of R_hub (non-standard, conservative by ~0.012). | **Fixed.** Hub reduced to 2 in (ratio 0.25); root chord tapered to 49 mm so three roots fit with 14.5 mm clearance (H5 showed root taper costs < 0.002 Cp). Hub loss switched to the AeroDyn/CCBlade form. Cp at 1.5 m/s: 0.323 → 0.368. |
| 3 | H2 | Major | BEM is outside its validity at the root (solidity ~0.9, axial induction 0.48–0.50, F 0.2) and in the tip-loss region; root sections ran at α = −2…−3° on 20–22 % thick NACA sections (lower-surface laminar separation territory). Impact is bounded: r/R < 0.55 carries 16 % of torque; doubling thick-section drag costs 0.006–0.012 Cp. | **Partly fixed, rest documented.** Root pitched down 2.5° (blending out by 50 % R): root α is now +0.5…+1.6° (hub station −1.0°). Induction at the first element is still 0.47 — accepted, since the inboard 20 % contributes little and the alternative (a narrower root) erodes the structural margin. README now quotes Cp as a band, not a point. |
| 4 | P1 | Major | The rotor's plain 10 mm through-bore had no way to transmit 0.6 N m (a printed press fit creeps when wet). | **Fixed.** Bore is now blind from the downstream face, with a 3.2 mm cross-pin hole and two M4 grub-screw pilot holes 90° from it, placed at X = 22.5 mm in the band clear of the blade roots. Verified by point probes in the STEP. |
| 5 | P2, H6 | Major | Self-start at 1 m/s doubtful: static torque ~0.06–0.09 N m vs slotted-PMG cogging 0.05–0.3 N m + seal friction. | **Documented.** Static torque is now computed and tabulated (0.09 / 0.20 / 0.37 N m at 1 / 1.5 / 2 m/s); README specifies a low-cogging (coreless / axial-flux) generator. Geometry already maximises static torque (high solidity). |
| 6 | P3 | Major | Generator advice was unusable (hobby outrunners of Kv 500–1000 give 1–2 V even geared; a gearmotor backwards adds 0.03–0.1 N m friction). | **Fixed in README:** Kv ≤ 50 direct / ≤ 150 with 1:3 step-up, or a 300–700 rpm PMG; shaft vs electrical power distinguished (expect ~70 % of shaft). |
| 7 | P5, H4 | Major | Runaway was not addressed: no-load TSR 6.6 → 1240 rpm at 2 m/s, tip 13 m/s, where the tip cavitates (σ 1.2 vs −Cp_min 1.4). The "8 m/s" cavitation statement holds only under load. | **Documented.** Runaway rpm computed per speed (587 / 952 / 1269); README asks for a dump load or brake and limits the cavitation statement to loaded operation. |
| 8 | H4, P10 | Major | "Fixed generator load works across 1–2 m/s" is true only for a load whose torque rises with speed (verified: TSR 2.8 / 3.5 / 4.0 → ≥ 97 % of peak Cp); a constant-torque load sized at 1.5 m/s stalls the rotor at 1 m/s. "Optimised for 1–2 m/s" was vacuous because V never entered the Re-free model. | **Fixed.** The polar is now Re-dependent so V enters; README states which load types work. |
| 9 | P6 | Major | Manufacturing text did not work: the single blade's root is a cylinder (cannot stand root-down, no hub attachment feature); printing the rotor hub-down puts every pressure face on supports; nylon absorbs ~9 % water; the 1.3 mm tip and 0.6 mm TE are fragile. | **Fixed.** Tip chord raised (10.7 → 15.4 mm) and tip thickness ratio 12 → 14 % (tip now 2.1 mm thick); trailing edge 0.8 mm (two 0.4 mm perimeters); README print orientation rewritten (rotor nose-down with tree supports; blade on its side or in a mould), nylon removed, spares and trash rack advised. A blade–hub fillet was attempted in OpenCascade on the 17 junction edges and refused; README tells the user to add 1.5–2 mm in Fusion. |
| 10 | P7 | Minor | "Far from strength limit" held (root 0.23 MPa at 2 m/s in rev 1) but the critical section was mid-span where the section thins (1.7 MPa at 2 m/s, 3.8 at 3 m/s); locked-rotor thrust is lower than operating, not higher. | **Documented, re-computed for rev 2.** The narrower root is now the critical section: 1.6 MPa at 2 m/s, 3.7 MPa in a 3 m/s flood, SF ≈ 8 against 30 MPa across-layer PETG, > 4 in fatigue. Stress table added to README. |
| 11 | P8 | Minor | No nose cone: a blunt 3 in cylinder faced the flow. | **Fixed.** 28 mm ellipsoidal nose on the upstream face. |
| 12 | P9, H7 | Minor | `blade_stations.csv` columns `design_alpha`/`design_CL`/`inflow_phi` were Schmitz inputs, not operating values; README said "3.5 mm near the tip" where the tip is 1.3 mm; rotation direction not given from the generator side; no Fusion pattern/combine steps; the blade was described as a "Schmitz optimum" when it is a scaled Schmitz shape. | **Fixed.** CSV now carries operating α / CL / Re / induction at 1.5 m/s and labels the Schmitz columns as design inputs; README wording corrected throughout. |
| 13 | H5 | Minor | Blade count: B = 4 gives +0.012 Cp but root c/s → 1.26 (beyond BEM); B = 2 gives −0.024…−0.04. Root taper 0.5–1.0 changes Cp ≤ 0.002; whole-chord ×0.75 only +0.006. | **Accepted.** 3 blades kept; taper used freely to make the small hub work. |
| 14 | author | Minor | Sensitivity of the rev 1 result: all-section drag ×1.5 → Cp 0.304, ×2 → 0.289, ×3 → 0.265; thick-root drag +0.015 → 0.316; root 18 % thick → 0.315; lift slope ×0.85 → 0.321. The design is not fragile to the polar. | Documented here. |
| 15 | H (optimiser) | Minor | The search in rev 1 ended on its grid edge (geometry TSR 5.4, pitch +8.75°); probing beyond (TSR 6–10, pitch 10–13°) found a flat ridge 0.318–0.324, and re-optimising the pitch with the surrogate polar moved it < 1°. | **Accepted.** Rev 2 re-ran the search with the new physics; optimum at geometry TSR 4.0, pitch +6.0°, interior to the grid. |

## C — CAD geometry review (findings on revision 1, resolved in revision 2)

The CAD reviewer re-imported both STEP files, sliced the solids with cylinders at fine radial steps,
regenerated every station independently from `blade_stations.csv`, and checked the STL meshes with
trimesh. No blocker: both files are single, valid, closed manifold solids (AP214, mm, 0 free edges,
0 self-interferences). The defects were all in how the loft was built, not in the design:

| # | Sev. | Finding (measured on rev 1) | Resolution in revision 2 |
|---|---|---|---|
| C1 | Major | The root stub was lofted *smoothly* through four near-identical inner stations, so the loft rang: chord 80.97 mm at r = 33.75 inside the hub (hub section 75.66), 4.27 mm surface deviation, then a 0.74 mm dip. Hidden in the rotor, wrong in the single-blade file. | **Fixed.** The smooth loft now starts 0.5 mm outside the hub and the stub is a *ruled* loft straight inward from that station. Acceptance check added: the as-built chord is sliced at 40 radii and compared with the analytical chord curve. |
| C2 | Major | `stations()` was dense at the **root**, not the tip as its comment claimed (1.45 mm vs 3.19 mm spacing), so the elliptical tip was under-sampled: the loft bulged up to +3.7 mm beyond the intended chord over the last 3 mm, with a crease at the cap (normals jumping 13–19°). | **Fixed.** Station spacing rewritten: 15 stations through the steep root taper, 7 mid-span, 9 through the tip spaced in the ellipse angle (dense at the tip); the acceptance check covers the tip. |
| C3 | Major | The root cap was a free "N-sided" filling over a wire wrapped 143° around the axis; it bulged outward to r = 32.83 and survived the cylinder trim, leaving a 0.83 mm dent in the root face. | **Fixed.** The root cap is now a plate surface seeded with the exact cylinder (OpenCascade `BRepFill_Filling.LoadInitSurface`), checked to lie on it within 0.05 mm, so no trim is needed. The tip cap (wire wraps only 9°) stays a free filling: a seeded tip cap lost half its area on STEP export, which a new **STEP round-trip check** (re-import; same face count, every face area within 2 %, volume within 0.2 %) now catches for both files. |
| C4 | Major | Blade STL not 2-manifold: 33 % sliver triangles along the 0.6 mm trailing-edge strip, 144 collapsing to zero area in float32, 9 open micro-slits near the tip; Fusion's Mesh→BRep would refuse it. | **Fixed.** STL export now merges vertices, drops degenerate faces and verifies watertightness with trimesh (result recorded in `design_spec.json`). |
| C5 | Minor | No fillet at the blade–hub junction (fluid-side wedge 50° at the TE, 70° at the LE). | Attempted automatically on the junction edges; OpenCascade refuses, so README asks for 1.5–2 mm in Fusion. |
| C6 | Minor | The blunt TE is a linear thickening over the whole chord, so t/c is ~0.5–1 % above nominal; 0.6 mm is 1.5 nozzle widths. | Documented; TE raised to 0.8 mm (two 0.4 mm perimeters). |
| C7 | Minor | Widest as-built chord 76.24 mm at r ≈ 40.2, not 76.20 at a station. | **Fixed.** Chord normalised on a dense curve so the true maximum is 76.20 mm. |
| C8 | Minor | The "elliptical" tip ends in a flat 10.7 × 1.5 mm cap. | Accepted and documented (tip chord raised to 15 mm for strength; round it with a 1 mm fillet in Fusion if wanted). |
| C9 | Minor | Hub solidity 0.95 — BEM doubtful inboard of r ≈ 50 mm. | Same as H2; see finding 3. |
| C10 | Minor | Stub angular span > 120° at r = 32 raised the question of neighbouring stubs intersecting; verified volumetrically: **no overlap** (0 of 632 interior points inside a neighbour; ≥ 12.8 mm apart). Rev 2 stubs are shallower (4 mm) and narrower. | Clearance now computed in the generator: 14.5 mm in rev 2. |
| C11 | Minor | `.edges().fillet()` on the hub also selected the cylinder seam; `CheckCompatibility(False)` relies on equal edge counts. | Hub fillet now selects the downstream face edges only; equal edge counts are by construction (3 per section). |

Verified correct by the CAD reviewer (rev 1, unchanged in method): tip radius 101.600 mm; chord, twist and t/c at all 26 stations within 0.01 mm / 0.06° / 0.0005 of an independently generated NACA 44xx placed per the CSV; wrapping onto the cylinder distorts the sections by ≤ 0.017 mm; trailing edge 0.600 mm everywhere; mid-span loft smooth (chord residual −0.04…+0.08 mm, normal waviness ≤ 0.38°); hub centred on the blade (4.789 vs 4.788 mm); orientation fully consistent (LE upstream and leading, camber toward +X, 30 %-chord point on the Z axis within 0.09 mm, CCW-from-upstream ⇒ positive torque); Fusion section CSVs are closed loops in cm on their cylinders.

## Claims verified as correct

- BEM formulation: induction factors, Prandtl tip loss, Buhl correction (quadratic derived by hand, single root in [0.4, 1)), Ning residual with no spurious sign changes at operating TSRs, α = φ − β, mm→m units, Cp/Ct normalised on the full disk. Reproduced to 4 digits by an independent solver (H).
- Schmitz chord and inflow-angle formulas (H).
- Lift model vs surrogate at Re 2e5: α0 −4.05° and slope 0.105–0.115/deg vs −4° and 0.100; CL within 0.05–0.1 at the operating angles (H).
- Wilson–Lissaman–Walker Cp_max for TSR 3.5, B = 3, L/D 25–40: 0.42–0.45; × (1 − hub area) → 0.36–0.39, so the BEM value is not optimistic by that measure (H).
- Cavitation under load: σ ≈ 3–4 at 0.2–0.3 m depth vs −Cp_min 0.7–1.25 at the operating CL (H, P independently).
- Rev 1 STEP files: single valid solids; tip 101.60 mm; max chord 76.20 mm; TE 0.600 mm; volume 22 160 mm³; rotor has three blades, 50.8 mm hub and 10 mm bore (P). Rev 2 re-verified by the author: blade 27286 mm³, rotor 213 550 mm³, single valid solids, max radius 101.60 mm, hub features present (point probes for bore, nose, pin and grub-screw holes), blade-to-blade clearance 14.5 mm, as-built chord within 0.23 mm (rms 0.10) of the design curve at 40 radii including the stub and the tip; both STEP files re-import with identical face counts and volumes (0.00 %); both STL meshes watertight.
- Performance arithmetic (rpm = 60·TSR·V/(2πR), P_avail = ½ρAV³, Q = P/ω, T = Ct·½ρAV²) and the "within 5 % of peak Cp over TSR 2.75–4.25" statement for rev 1 (P).
- Rotation direction is consistent with the camber-downstream geometry (P). Fusion menu path "File > Open > Open from my computer…" confirmed against Autodesk's knowledge base (P).
- In family with published 0.2–0.3 m hydrokinetic rotors: 3 blades, TSR 3–4, high solidity; Cp ~0.3 is at the optimistic end at Re ~1e5 (P).

## Still open / not independently verified

- **Measured polars** for NACA 4412/4422 at Re < 1.5e5 could not be fetched (airfoiltools, UIUC, NTRS, OSTI were unreachable from the review session); the Re model is anchored on an XFOIL surrogate, which shares XFOIL's weakness on thick sections at Re ≤ 1e5. Expect the 1 m/s numbers to be the least reliable.
- Cascade interference at root solidity ~0.9, hub/nacelle drag and root-junction losses are not in BEM. The honest expectation is Cp 0.25–0.33 in the water, not the 0.35–0.38 of the table.
- PETG S–N data: fatigue margins use a 0.2–0.3 fatigue ratio assumption.
- Whether the first-element axial induction of 0.47 matters: BEM cannot say; a tank test or CFD would.
- No blade–hub fillet in the rotor file (OpenCascade refused it); the user adds it in Fusion.

## Revision 1 → 2 at a glance

| | Rev 1 | Rev 2 |
|---|---|---|
| Hub | 3 in, plain through-bore, no nose | 2 in, nose cone, blind bore + cross-pin + 2 grub screws |
| Root chord / max chord | 75.6 / 76.2 mm | 48.6 / 76.2 mm (max at 40 mm radius; as built 76.29 mm) |
| Tip chord, thickness | 10.7 mm, 1.3 mm | 15.3 mm, 2.1 mm |
| Trailing edge | 0.6 mm | 0.8 mm |
| Root twist | 22.3° | 29.1° (incl. −2.5° root pitch-down) |
| Polar model | Re-independent | Cd0 ∝ Re^−0.8, per-element Re |
| Hub loss | exp(−B(r−Rh)/(2 r sinφ)) | AeroDyn form exp(−B(r−Rh)/(2 Rh sinφ)) |
| Peak Cp (BEM) | 0.323 at TSR 3.5 (all speeds) | 0.347 / 0.368 / 0.379 at 1 / 1.5 / 2 m/s, TSR 3.25 |
| Shaft power 1 / 1.5 / 2 m/s | 5.2 / 17.7 / 41.9 W | 5.6 / 20.1 / 49.1 W |
| Static torque, runaway rpm | not computed | 0.09 / 0.20 / 0.37 N m; 587 / 952 / 1269 rpm |
| Root stress 2 m/s / 3 m/s | 0.23 / 0.52 MPa | 1.6 / 3.5 MPa (SF ≈ 8) |
| Loft construction | smooth loft incl. inner stub stations, free filled caps + cylinder trim | smooth loft outboard, ruled stub, cylinder-seeded caps; as-built chord within 0.23 mm of the design curve |
| STL meshes | blade not watertight | blade watertight, rotor watertight (trimesh check after vertex merge and MeshFix repair, volume within 1 % of the solid) |
| Blade-to-blade clearance at the root | 22 mm (rev 1, 3 in hub) | 14.5 mm |
