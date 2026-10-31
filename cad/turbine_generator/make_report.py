#!/usr/bin/env python3
"""Assemble REPORT.md from the computed results (assembly_info.json, electrical_results.json, design_spec.json, BOM.csv)."""
import csv, json, math, os
HERE = os.path.dirname(os.path.abspath(__file__))
info = json.load(open(os.path.join(HERE, "cad_out", "assembly_info.json")))
el = json.load(open(os.path.join(HERE, "electrical_results.json")))
spec = json.load(open(os.path.join(HERE, "..", "water_turbine_blade", "design_spec.json")))
bom = list(csv.DictReader(open(os.path.join(HERE, "BOM.csv"))))
A, B = info["configs"]["A"], info["configs"]["B"]
LA, LB = A["layout"], B["layout"]
def el_rows(cfg_prefix, gen_sub):
    for k, rows in el.items():
        if k.startswith(cfg_prefix) and gen_sub in k:
            return rows
    return []
gl_A = el_rows("A", "GL60"); gm_A = el_rows("A", "GM5208"); gb_A1 = el_rows("A", "measures like"); gb_A2 = el_rows("A", "stall torque"); gl_B = el_rows("B", "GL60")
def perf_table(rows, label):
    out = [f"| Water speed | TSR | rpm | Shaft power (W) | Friction (W) | Generator torque (N m) | DC current (A) | DC voltage (V) | Copper loss (W) | **DC output (W)** | Water-to-DC |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['V']} m/s | {r['tsr']:.2f} | {r['rpm']:.0f} | {r['Pm']:.1f} | {r['Pfric']:.2f} | {r['Qg']:.2f} | {r['I']:.2f} | {r['Vdc']:.1f} | {r['Pcu']:.1f} | **{r['Pe']:.1f}** | {r['eta_total']*100:.0f} % |")
    return "\n".join(out)
bom_lines = ["| # | Qty | Item | Spec | Vendor / part | Unit USD | Basis |", "|---|---|---|---|---|---|---|"]
for r in bom:
    bom_lines.append(f"| {r['item']} | {r['qty']} | {r['description']} | {r['spec / drawing']} | {r['vendor / part no.']} | {r['unit price USD']} | {r['price basis']} |")
tm = "\n".join(f"- **{k}**: {v}" for k, v in info["to_measure"].items())
parts_A = [p for p in A["parts"] if not p["name"].startswith("oring")]
files_A = "\n".join(f"| `cad_out/A_{p['name']}.step`{' / `.stl`' if p['kind'].startswith('print') else ''} | {p['kind']} | {p['note']} |" for p in parts_A)

txt = f"""# Compact waterproof hydrokinetic turbine-generator: engineering report

**Status: design study with manufacturing-ready CAD. Nothing in this package has been built or
immersion-tested; the assembly must not be called waterproof until the procedure in `VALIDATION.md`
has been completed.** Every number is tagged as verified (from a cited vendor/standard page, see
`research/`), calculated (from the reviewed BEM/mechanical models in this folder) or assumed.

## 1. Summary and recommendation

| | Recommended: **A, stationary generator nacelle** | Compact alternative: **B, hub-integrated rotating drum** | Target |
|---|---|---|---|
| Axial depth, nose tip to rear | **{LA['axial_depth_mm']:.0f} mm ({LA['axial_depth_mm']/25.4:.1f} in)** | {LB['axial_depth_mm']:.0f} mm ({LB['axial_depth_mm']/25.4:.1f} in) | 76 mm (3 in) |
| Rotor diameter | 203.2 mm | 203.2 mm | 203.2 mm |
| Hub diameter / ratio | 50.8 mm / 0.25 (reviewed rev-2 rotor unchanged) | {2*B['rotor']['r_hub']:.1f} mm / {B['rotor']['r_hub']/101.6:.2f} (blade set regenerated) | - |
| Rotor Cp at 1.5 m/s (BEM) | {A['rotor']['cp15']:.3f} | {B['rotor']['cp15']:.3f} | - |
| Generator | CubeMars GL60 KV25 (69 x 22 mm) | 49-60 mm gimbal class (GB5015 only if it measures well, else GM5208-24 with a 70 mm tube) | - |
| Waterproof boundary | anodised 80 x 2.5 mm tube, 2 machined caps with 2 radial EPDM O-rings each, **one** lip seal on a Speedi-Sleeved 12 mm shaft, WetLink cable penetrator | anodised 63.5 x 1.65 mm rotating tube, 2 machined caps, one lip seal on a stationary Speedi-Sleeved 15 mm spindle, potted cable in the spindle | - |
| DC output at 1 / 1.5 / 2 m/s (GL60, after all losses) | **{gl_A[0]['Pe']:.1f} / {gl_A[1]['Pe']:.1f} / {gl_A[2]['Pe']:.1f} W** | {gl_B[0]['Pe']:.1f} / {gl_B[1]['Pe']:.1f} / {gl_B[2]['Pe']:.1f} W (if the GL60 fitted; it does not, see 3.2) | - |
| Generator cooling | stator bolted to the aluminium rear cap in the water (< 10 K rise at 12 W) | stator inside the rotating drum, ~0.3 W/K path: 30-50 K rise at 10-15 W | - |
| Rotary seal friction at start | 1 lip, 12 mm: 0.012-0.024 N m (13-26 % of the 0.091 N m stall torque at 1 m/s) | 1 lip, 15 mm: 0.015-0.03 N m | - |
| Machined parts | 2 caps (+ Delrin bell adapter) | 2 caps + flanged collar adapter | - |
| Prototype cost (BOM) | about $550-1,030 incl. generator and charger | similar, cheaper motor, extra tube/spindle parts | - |

**Recommendation.** Build configuration A. It is the only layout that (a) takes the only generator with
published data that reaches ~70 % water-to-DC efficiency at 1 m/s, (b) keeps the reviewed rotor and its
0.25 hub ratio, (c) puts the generator losses straight into a water-cooled aluminium cap, and (d) uses
one small, standard, serviceable rotary seal with a hardened track. It misses the 76 mm depth target by
2.5x; configuration B (139.5 mm, 1.8x) is the smallest layout that keeps the same sealing quality, and
it is fully modelled here as the fallback if portability outranks the ~10 % energy penalty and the
thermal margin it gives up. Neither layout can reach 76 mm with any 22-30 mm long generator, dry
bearings, a rotary seal and a nose cone in series (section 5.5).

The GB5015 is **not** recommended as the generator: no KV, resistance, current rating or thermal data is
published, its "220 mN m @ 14.8 V" figure (if it is the usual stall-torque meaning) implies a motor
constant too low to absorb even the 1 m/s torque, and no IP65 variant could be found. If one is already
on hand, measure it (section 2.4) and keep it only if Kt/sqrt(R_LL) >= 0.11 N m/sqrt(W).

## 2. Generator selection

### 2.1 What the GB5015 listing gives and what it does not
Published (Copterlab / SMC Powers pages, via search snippets - re-check on the live page): body 49 x 29 mm,
stator 43 x 15 mm, 24N28P, "220 mN m @ 14.8 V", 12-24 V input, hollow shaft "supports slip ring" (bore
~12.5 mm inferred, not stated), M4 mounting, mass quoted as 120-165 g on different pages, $38-55.
**Not published:** KV / back-EMF constant, phase or line resistance, inductance, continuous and peak
current, bearing type and load rating, wire gauge, lead time. **No IP65 page exists**; the nearest sealed
gimbal motors (CubeMars GL) are IP45. An IP rating is irrelevant inside a sealed housing anyway: the
housing and shaft seal carry the sealing duty.

### 2.2 Generator model and convention
Hobby convention: open-circuit line-to-line peak voltage E = rpm / KV; torque constant Kt = 60 / (2 pi KV)
N m per ampere of **rectifier DC current**; copper loss = I_dc^2 x R_LL where R_LL is the resistance
measured between two motor leads; V_dc = E - I_dc R_LL - 0.8 V (two Schottky drops). Iron, bearing and
commutation-inductance losses are folded into a 0.5 W allowance; gimbal motors have 3-5 mH of inductance,
so at 100-150 Hz electrical the reactance is comparable to R and the real DC voltage will be a little
lower than the table - measure under load. The decisive figure of merit is the motor constant
Km = Kt / sqrt(R_LL): copper loss = (torque / Km)^2. To lose less than 20 % of the 1 m/s power (0.18 N m)
needs Km >= 0.17 N m/sqrt(W); to absorb 0.72 N m at 2 m/s with less than 15 W loss needs Km >= 0.19.

### 2.3 Candidates (published data, see `research/research_generators.md` for every URL)

| Generator | Size, mass | KV (rpm/V) | R_LL (ohm) | Km | Price | Water-to-DC at 1 / 2 m/s (config A) |
|---|---|---|---|---|---|---|
| **CubeMars GL60 KV25** (primary) | 69 x 22.3 mm, 230 g, 20 mm bore, IP45 | 21.5 (one page says 25) | 5.5 (one page says 4.6) | 0.19 | $142-185 | **{gl_A[0]['eta_total']*100:.0f} % / {gl_A[2]['eta_total']*100:.0f} %** |
| iPower GM5208-24 (backup) | 59.5 x 31.2 mm, 204 g | ~20.8 | 13.7 (iFlight) or 25.6 (RobotShop) - conflicting | 0.12 / 0.09 | $43 | {gm_A[0]['eta_total']*100:.0f} % / {gm_A[2]['eta_total']*100:.0f} % (13.7 ohm case) |
| GB5015 if it is a GM5208-like winding | 49 x 29 mm | ~21 (assumed) | ~13.7 (assumed) | 0.12 | $38-55 | {gb_A1[0]['eta_total']*100:.0f} % / {gb_A1[2]['eta_total']*100:.0f} % |
| GB5015 if "220 mN m @ 14.8 V" is stall torque | 49 x 29 mm | any consistent winding | - | <= 0.08 | $38-55 | {gb_A2[0]['eta_total']*100:.0f} % / {gb_A2[2]['eta_total']*100:.0f} % (cannot hold the rotor at 1-1.5 m/s) |
| T-Motor GB54-1 / GB54-2, GB36, GM4108, BGM5208-75T | 42-63 mm | 26-50 | 11-16 | 0.05-0.11 | $70-75 | cannot absorb the 1 m/s torque or < 45 % |
| T-Motor U8 / MN8012 KV100 | 87-90 mm | 100 | 0.09-0.14 | 0.26-0.33 | n/a | 65-78 % but only 2-5 V DC: needs a boost from 2 V, and too large |
| Hoverboard hub motor | 165 mm, 3 kg | 16 | 0.56 | 0.77 | $30 used | 95 % - but 3 kg and 165 mm: no |
| 100-300 W "micro wind" PMGs | 3-9 kg | - | - | - | $100-650 | start torque > 0.09 N m: will not self-start |

Cogging: GL60-class peak cogging is ~15-25 mN m (CubeMars quotes 2.4 -> 1.5 cN m for the GL60 II; units
are ambiguous on reseller pages), GB5015-class ~2-10 mN m. Both are below the 0.091 N m static torque at
1 m/s, but cogging adds to seal and bearing breakaway (section 7.2).

Thermal: the GL60 is rated 0.6 N m continuous at 1.35 A in free air; at 2 m/s the turbine wants 0.66 N m
and 1.45 A (11.6 W copper). With the stator bolted to the aluminium rear cap in flowing water the winding
rise is ~10-15 K (section 4.6), so the 2 m/s point is thermally acceptable; the charger must still
current-limit at 1.5 A so that a 3 m/s flood cannot push 3 A (46 W) into the winding - the rotor then
simply runs at a higher tip-speed ratio.

### 2.4 Measurements required on the physical generator (before the caps are machined)
1. KV: spin with a drill at a known rpm (optical tachometer, or rpm = 60 x f / pole-pairs from the AC frequency) and read the line-to-line voltage on all three pairs; KV = rpm / (1.414 x V_LL,rms).
2. R_LL between each pair of leads (4-wire, or 0.5-1 A DC injection); expect 4.6-5.5 ohm (GL60).
3. Inductance (LCR meter) - sets the voltage droop at speed.
4. Cogging torque (thread on a drum + spring scale over a full turn) and, later, total breakaway with the seal fitted.
5. Bell-face bolt pattern (PCD, thread, depth) and stator-base pattern - these drive `a_bell_pcd`, `a_motor_pcd`, `a_motor_hole` in `make_assembly.py`.
6. Overall diameter and length, bore, axial play of the bell, mass.
7. 30-60 min loaded run at 0.4 N m in air logging voltage, current and winding resistance rise.

## 3. Generator architectures

### 3.1 The three (plus one) candidates
- **A. Stationary generator nacelle behind the rotor** (recommended, fully modelled): rotor on a 12 mm 316 shaft; shaft crosses the front cap through one lip seal; two sealed stainless bearings on the dry side; jaw coupling to the GL60 bell; stator on the rear cap; WetLink cable exit; three NACA struts on a printed clamp ring carry the nacelle to the duct.
- **B. Hub-integrated outrunner** (fully modelled as the compact fallback): the hub is a rotating anodised aluminium tube with two machined O-ring caps; the generator stator sits on a stationary hollow 316 spindle that enters through the rear cap via one lip seal on a Speedi-Sleeve; two bearings on the spindle inside the dry drum carry the rotor; the bell drives the drum front cap through a compliant TPU disc; cable runs inside the spindle and is potted at the strut boss.
- **C. Magnetic coupling with a fully static-sealed cartridge** (upgrade path, not modelled): A's cartridge with the front cap replaced by a non-conductive cup and a coaxial magnetic coupling; wet ceramic bearings carry the rotor.
- **D. Flooded, potted generator** (Blue Robotics T200 practice): no enclosure at all; stator epoxy-potted, coated magnets, water-lubricated bearings. Rejected for a generator in silty water: the T200's plastic bearings deform when run dry and had a continuous-duty wear recall; potting a 69 mm stator reliably is a process the team would have to qualify; magnet corrosion is unforgiving.

### 3.2 Comparison

| Criterion | A nacelle | B hub drum | C magnetic coupling |
|---|---|---|---|
| Waterproofing reliability | 4 static O-rings on machined caps + 1 small lip seal on a hardened sleeve: standard, serviceable | same seal count; the sealed drum rotates (static O-rings are indifferent to that); lip runs on a stationary sleeve | **no rotary seal at all** (5 static seals); best |
| Rotary-seal friction at 1 m/s start | 0.012-0.024 N m (13-26 % of stall torque) | 0.015-0.030 N m | 0 (wet ceramic bearings ~0.005) |
| Generator efficiency / cooling | GL60 fits; stator on a water-cooled cap: < 15 K rise | 69 mm GL60 would force a 0.43 hub ratio (Cp ~0.28) so B is limited to 49-60 mm motors (Km <= 0.12, 50-57 % at 1 m/s); stator inside the drum: 30-50 K rise | as A, minus the seal; eddy loss 0 with a plastic cup (316 cup ~1-2 %, aluminium cup 16-33 %: not allowed) |
| Hydrodynamic obstruction | hub 0.25 unchanged; 80 mm nacelle in the wake (15 % of disk area, section 5.4) | hub ratio 0.35: Cp 0.368 -> 0.332 (-10 %); nothing behind the rotor but the strut boss | as A plus ~20 mm length |
| Axial depth | {LA['axial_depth_mm']:.0f} mm | {LB['axial_depth_mm']:.0f} mm | ~210 mm |
| Manufacturing complexity | 2 machined caps, 1 Delrin adapter, stock tube, printed rotor/struts | 2 machined caps, machined/printed collar adapter, stock tube, 316 tube spindle, printed blade ring halves + nose + TPU disc; compliant bell mount must be tuned | A plus a DIY or lab-stirrer magnetic coupling (0.9 N m class, $30-150) and encapsulated magnets |
| Cost | $550-1,030 | $500-950 | A + $60-200 |
| Maintenance | unclamp struts, slide cartridge out, swap seal/bearings from the front cap | pull the rotor/drum off the spindle, open the front cap | open the cartridge; wet bearings replaced yearly |
| Packaging / portability | 80 mm nacelle, 189 mm long | compact; rotating mass higher (balance needed) | longest |
| Load path | thrust -> shaft -> rear bearing -> circlip -> cap -> tube -> struts | thrust -> drum rear cap -> bearing pair -> spindle -> strut boss | thrust -> wet bearings -> cup -> cap |

### 3.3 Why A
B's single real advantage is 50 mm of length. For that it gives up 10 % of rotor power (hub ratio),
excludes the only generator with adequate published data (the GL60 does not fit a hub), halves the
thermal margin, and adds an over-constrained bell mount (the motor's own bearings and the drum bearings
both locate the bell; the TPU disc absorbs the mismatch but has to be tuned). Its sealing is as good as
A's, not better - which is the point of using the same machined-cap/Speedi-Sleeve solution in both. C is
the right second iteration once A has run: the same tube, rear cap and generator carry over, only the front
cap becomes a non-conductive cup with a coupling, so the 13-26 % starting-torque tax and the only wearing
seal disappear. The magnetic-coupling research (`research/research_magcoupling.md`) found no COTS
coupling with published data in exactly this class except laboratory stirrer heads (0.2-0.9 N m); a DIY
coaxial coupling of 8-12 N42 magnets at a 3-4 mm gap is estimated at 0.8-1.5 N m pull-out, must be
bench-tested, and a **face** (disc) coupling is not acceptable because it pulls the halves together with
~80-120 N, which would load the bearings and bow a plastic wall.

## 4. Waterproof enclosure engineering (configuration A)

### 4.1 The boundary
Anodised 6061-T6 tube (80 x 2.5 mm, 95 mm long) closed by two machined caps. Each cap is a flange outside
the tube and an 18 mm plug inside it carrying **two radial O-rings** 7 mm apart (the second is redundancy
and a wiper for silt). The only rotating crossing is the 12 mm shaft through the front cap: one spring-loaded
lip seal running on an SKF Speedi-Sleeve. The cable leaves through a Blue Robotics WetLink M10 penetrator
in the rear cap (static, FKM-sealed, rated 95 m for the HC version). An M6 vent port in the rear cap is used
for the vacuum leak test and closed with an O-ring plug. The caps are retained by three M3 radial 316
screws each, placed on the dry side of the inner O-ring so the screw holes never see water. The section
view `cad_out/A_section_view.png` draws the boundary in red.

### 4.2 Static O-ring glands (Parker O-Ring Handbook values, verified in the research notes)
Cross-section 2.62 mm (AS568 -1xx): radial gland depth 2.06-2.11 mm (17-24 % squeeze), groove width
3.56-3.61 mm, groove corner radii 0.2-0.4 mm, groove surface Ra <= 1.6 um, bore Ra <= 0.8 um with a
15 deg x 1.5 mm lead-in chamfer on the tube. Plug diameter 74.9 mm in a 75.0 (+0.2/-0) bore gives
0.05-0.15 mm diametral clearance (extrusion is not a concern at 0.3 bar). Groove OD 70.7 mm takes an
**AS568-148 (69.5 mm ID) EPDM 70** ring at 1.8 % stretch. EPDM is the right material for continuous fresh
water (NBR is acceptable at 0-25 C but ages faster in water; FKM is fine cold); lubricate EPDM only with
silicone or PFPE grease. **Measure the real tube bore and cut the groove depth to it** - stock tube ID is
+-0.2 mm. The caps may be Delrin (acetal) instead of aluminium for the front cap; the rear cap must be
aluminium because it is the generator's heat sink.

### 4.3 Rotary seal
Lip seal 12 x 22 x 7 mm, single lip with garter spring, lip facing the water (the pressure side), bore 22 H8
in the cap, 7 mm deep from the wet face. **316 is too soft for a lip-seal track** (HRB 83; SKF asks for
>= 45 HRC for long life in contaminated media), so the shaft wears an SKF Speedi-Sleeve 99047 (hardened
stainless, 0.28 mm wall) at the seal position - Speedi-Sleeves exist from 11.99 mm up, which is why the
shaft is 12 mm and not 10 mm. Pressure: a standard oil seal holds 0.3-0.5 bar; our maximum is 0.2 bar at
2 m depth. Friction: no published figure exists for this size; SKF's model (T = (F_lub + F_material) x d/2)
with a 3-8 N lip force gives 4-24 mN m running and about twice that at breakaway. A PTFE lip (Dichta C-O
or Trelleborg Varilip PDR, $40-120) halves it; a V-ring is not a pressure seal; ferrofluid seals fail in
water. The seal is the one wearing part: plan to replace it at 6-12 months, inspect at 2 weeks.

### 4.4 Bearings and alignment
Two 6001-2RS 440C stainless bearings (12 x 28 x 8) back-to-back in a 28 H7 bore, dry side, grease-sealed.
Thrust (46 N at 2 m/s, 110 N in a 3 m/s flood) passes shaft -> DIN 471 circlip -> rear bearing inner race
-> balls -> outer race -> DIN 472-28 internal circlip -> cap -> tube -> struts. ISO 281 L10 at 46 N axial
+ 22 N radial is > 10^6 h: fatigue is irrelevant, contamination and corrosion decide bearing life, which
is why they sit behind the seal. The jaw coupling (D20 x L25, 98A spider) absorbs the mismatch between the
shaft axis (defined by the front cap) and the GL60 bell axis (defined by its own bearings in the stator on
the rear cap): 0.2 mm radial, 1 deg angular. Rotor overhang from the front bearing is 35 mm; bending stress
in the 12 mm shaft is < 5 MPa, torsion < 8 MPa at the 1.5 N m jam case; the 3 mm 316 cross pin sees 22 MPa
in double shear (316 shear strength ~300 MPa).

### 4.5 Materials, corrosion, fasteners
Tube and caps 6061-T6 hard-anodised (type III) and sealed; 316 shaft, collar, pin, screws; 440C bearings
(dry side); EPDM O-rings; FKM penetrator seal. Galvanic pairs that matter in fresh water: 316 screws in
aluminium (~670 mV apart) - coat the threads with Tef-Gel and use nylon washers under the heads; keep brass
heat-set inserts out of wetted aluminium (use them only in the printed clamp ring and struts, or use 316
through-bolts with nyloc nuts, which the CAD does). The Speedi-Sleeve is 302 stainless on a 316 shaft:
acceptable. No dissimilar-metal contact inside the dry volume matters.

### 4.6 Thermal management
GL60 copper loss is 0.8 / 4.5 / 11.6 W at 1 / 1.5 / 2 m/s (current-limited to 1.5 A, 12 W, in a flood).
Heat path: winding -> stator core -> aluminium rear cap (bolted, thermal paste) -> water. The cap's wet
face (0.005 m2) with h ~ 800 W/m2K in moving water rises < 4 K at 12 W; the stator-to-cap joint adds
~1 K/W -> winding ~15-20 K above the water. The air volume inside stays cool; the front cap and the seal
see no generator heat. If a GM5208 (13.7 ohm) were used instead, copper loss at 2 m/s is 19 W and the
same path still holds the winding below 50 K rise.

### 4.7 Pressure, breathing and leak paths
External pressure (0.03-0.2 bar) pushes both caps into the tube and the lip onto the shaft: the geometry
is self-energising. Breathing: a 20 K temperature swing changes the internal air pressure by 7 %; the lip
seal will relieve an internal over-pressure (it lifts) and resists under-pressure (it tightens), so a
long cold soak after a warm assembly pulls the lip harder onto the sleeve - assemble at or below water
temperature, or fit the vent plug after a few minutes in the water. Leak paths in order of likelihood:
(1) lip seal (wear, scored sleeve, backwards installation), (2) penetrator (wrong cable size, under-torqued),
(3) O-rings (nicked at assembly, groove burr, wrong size for the measured bore), (4) anodising pores on a
cap face (negligible with two rings). A desiccant bag and a moisture-indicator card inside make the
first three detectable at the 2-week inspection.

### 4.8 Assembly / disassembly
Generator cartridge = tube + rear cap + GL60 + adapter: assemble on the bench, vacuum-test, then slide the
front cap (with shaft, bearings, seal pre-assembled) in, fit the three M3 screws, vacuum-test again. To
swap the generator: unclamp the strut ring (4 x M4), pull the whole cartridge out of the duct, remove the
three rear-cap screws and withdraw the rear cap with the motor on it. To swap the seal: pull the rotor
(cross pin + grub screws), remove the collar and Speedi-Sleeve, press out the seal from the dry side after
removing the front cap. Nothing requires breaking a bonded joint.

## 5. Mechanical and hydrodynamic design

### 5.1 Loads (reviewed BEM rev 2, `calcs.py`)
| Case | Thrust on rotor | Shaft torque | Notes |
|---|---|---|---|
| 1.0 m/s | 11 N | 0.18 N m | static (stall) torque 0.091 N m |
| 1.5 m/s | 26 N | 0.42 N m | |
| 2.0 m/s | 46 N | 0.77 N m | runaway (no load) 1269 rpm, 59 V DC open circuit |
| 3.0 m/s flood | ~110 N | ~1.5 N m (jam) | current limit keeps the generator at <= 0.7 N m |
Radial loads: unbalance 2 N at runaway with 0.5 mm eccentricity, shear-flow asymmetry ~5 N and 0.23 N m
yaw moment (10 % thrust asymmetry assumed). Front bearing ~22 N radial, rear ~15 N.

### 5.2 Rotor
Unchanged from the reviewed revision 2 except the shaft bore (10 -> 12 mm to allow the Speedi-Sleeve).
The hub's blind bore, 3.2 mm cross pin and two M4 grub screws remain the torque path; the nose cone is
integral. Printed PETG/ASA, 4+ perimeters, balanced to 0.5 g.

### 5.3 Nacelle, struts, duct interface
Nacelle 80 mm OD x 95 mm behind a 3 mm gap from the hub. Three NACA 0015 struts (chord 18 mm, 2.7 mm thick)
on a printed split clamp ring at 45 % of the tube length, i.e. ~55 mm behind the rotor plane, 120 deg apart
and clocked 60 deg from the blades' rest position. Outer pads 30 x 22 mm with two M4 holes on a 206 mm
duct bore (2 mm tip clearance); a 40 mm long reference duct ring is included in the CAD only to show the
interface - replace it with your duct. The cable runs in a groove along one strut.

### 5.4 Effect of the nacelle and struts on the blades
The nacelle (80 mm) is larger than the hub (50.8 mm): its frontal area is 15 % of the rotor disk, all of it
in the hub wake. Actuator-disk reasoning puts the induced velocity deficit at the blade root at a few
percent and at mid-span at < 1 %; the three struts (18 x 2.7 mm) are 55 mm downstream of the rotor and
block < 2 % of the annulus, producing a weak 3-per-revolution load ripple on the blades. Expected effect on
Cp: -2 to -4 %, within the BEM's own uncertainty (reviewed as +-0.02). **No new BEM or CFD is required
before the prototype**; measure rpm and DC power against water speed at the first deployment and compare
with section 7. If a later iteration shrinks the nacelle (e.g. a 60 mm generator), the penalty halves.

### 5.5 The 76 mm depth target
| Layout | Stack (mm) | Depth |
|---|---|---|
| A | nose 28 + hub 51 + gap 3 + front cap 6 + tube 95 + rear cap 6 | {LA['axial_depth_mm']:.0f} |
| B | nose 18 + front cap 6 + drum 84 + rear cap 6 + gap 3 + strut boss 22 | {LB['axial_depth_mm']:.0f} |
| What 76 mm would need | motor <= 15 mm long **inside** the hub, no nose cone, bearings and seal inside the motor's length, and a hub ratio > 0.4 | not with any motor found |
The honest minimum with a sealed dry generator is B at ~{LB['axial_depth_mm']:.0f} mm, and B only works with a
49-60 mm motor. Shaving B further (12-15 mm) is possible by machining the front cap thinner and shortening
the nose, at the price of the nose's drag benefit.

## 6. CAD and fabrication

All geometry is generated by `make_assembly.py` (CadQuery, parametric; every dimension in `PARAMS`), the
blade set by the reviewed `../water_turbine_blade/make_blade.py`. Run both scripts after entering the
measured motor dimensions. Exports in `cad_out/`:

| File | Kind | What it is |
|---|---|---|
| `cad_out/A_assembly.step` | assembly | configuration A, all parts positioned, coloured |
{files_A}
| `cad_out/B_*.step`, `cad_out/B_assembly.step` | alternative | configuration B parts and assembly |
| `cad_out/A_section_view.png`, `cad_out/A_exploded_view.png` | drawings | section through the axis with the waterproof boundary marked; exploded view |
| `cad_out/B_section_view.png`, `cad_out/B_exploded_view.png` | drawings | same for B |

Printed parts (PETG or ASA, 0.4 mm nozzle, 4 perimeters, 40 % gyroid unless noted): rotor (100 % infill
in the hub, root-down is impossible: lay on the flattest face with tree supports), clamp ring halves,
three struts, bell adapter (or machine it from Delrin). Machined parts: front cap, rear cap, shaft features
(cross-pin hole, circlip groove, D-flat - bench operations on a ground 316 rod). COTS: everything in `BOM.csv`.
FDM surfaces are never used as an O-ring or lip-seal sealing face in this design.

**Measurements required before the caps are machined** (the CAD uses placeholders for these):
{tm}

## 7. Expected performance

### 7.1 Configuration A with the CubeMars GL60 KV25 (KV 21.5, R_LL 5.5 ohm; MPPT load; seal 12 mN m, bearings 6 mN m)
{perf_table(gl_A, "A/GL60")}

Runaway (no load) open-circuit DC: 27 V at 1 m/s, 44 V at 1.5 m/s, 59 V at 2 m/s - the charger input
must be rated >= 60 V or a crowbar/dump load must clamp it. With the lower-resistance GL60 reading (4.6 ohm)
the DC output rises ~1-3 %; with a PTFE seal the 1 m/s output rises ~0.3 W.

### 7.2 Starting
Static rotor torque at 1 m/s is 0.091 N m. Breakaway budget: seal 2 x 12 = 24 mN m + bearings 6 + GL60
cogging ~24 = **54 mN m, i.e. 60 % of what the water offers** - it should start, but not with a stiff
seal, a scored sleeve or an un-greased bearing. Measure breakaway on the bench (`VALIDATION.md` 2.1) and
keep it under 45 mN m; a PTFE seal or a GB5015-class low-cogging motor each buy ~15 mN m. Below ~0.9 m/s
expect no self-start.

### 7.3 Backup generator, iPower GM5208-24 (if R_LL = 13.7 ohm; the 25.6 ohm reading would halve these)
{perf_table(gm_A, "A/GM5208")}

### 7.4 Load matching
A PM generator into a rectifier and a resistive or battery load has a torque that rises with speed, which
keeps the rotor within 3 % of peak Cp from 1 to 2 m/s (verified in the blade review). An MPPT boost charger
does the same actively. A constant-torque or constant-current load sized at 1.5 m/s stalls the rotor at
1 m/s. Set the charger's current limit at 1.5 A (GL60) so that it can never stall the rotor and the
winding cannot exceed 12 W; above 2 m/s the rotor then drifts up its Cp curve harmlessly.

## 8. Validation
`VALIDATION.md` gives the full procedure: bench measurements of the motor, shaft and caps; static vacuum
(-70 kPa, 15 min, < 1 kPa drift) and 24 h submersion tests of the sealed cartridge with a moisture card;
thermal cycling; rotating tests at 650 and 1300 rpm submerged with breakaway-torque measurement; electrical
verification of KV, resistance and the loss model; insulation resistance; in-water commissioning with rpm
and DC power logged against water speed; and the service intervals.

## 9. Unresolved engineering risks and the measurements that close them

| # | Risk | Severity | Closing measurement / action |
|---|---|---|---|
| 1 | GL60 electrical data conflict (KV 21.5 vs 25; 5.5 vs 4.6 ohm) and no measured cogging | medium | measure KV, R_LL, cogging on the delivered motor (2.4) before machining the caps |
| 2 | Bell-face and base hole patterns of the GL60 not published | high for CAD | measure; enter `a_bell_pcd`, `a_motor_pcd`, `a_motor_hole`; regenerate |
| 3 | Lip-seal breakaway torque unknown for a 12 mm seal | high for 1 m/s start | bench breakaway with the sleeve fitted; if > 30 mN m fit a PTFE seal or move to C |
| 4 | Seal life in silt on a Speedi-Sleeve | medium | 2-week inspections, 6-month replacement; keep the collar as a slinger |
| 5 | Real nacelle/strut effect on Cp (-2 to -4 % estimated) | low | rpm/power vs water speed at commissioning |
| 6 | Runaway voltage (59 V) vs charger rating | high for electronics | choose a >= 60 V input charger and fit a dump load; test no-load at site speed |
| 7 | Self-start below ~1.2 m/s | medium | measure; accept a push-start, or a low-cogging motor / PTFE seal |
| 8 | Tube bore tolerance vs O-ring squeeze | medium | measure the bore, machine grooves to it; vacuum test |
| 9 | Printed rotor on a 12 mm shaft: pin hole alignment, balance | low | ream the bore, drill the pin hole through the fitted shaft, balance |
| 10 | Thermal path stator-to-cap depends on the GL60 base geometry | medium | measure winding rise after a 2 h run at 1.5 A |
| 11 | Galvanic attack of 316 screws in anodised aluminium | low | Tef-Gel + nylon washers; inspect at 2 months |
| 12 | Debris / log strike on the blades | medium | trash rack upstream; printed spares |
| 13 | No published data for the GB5015 at all | n/a | do not use it unmeasured |

## 10. What is verified and what is assumed
**Verified from cited pages (see `research/`):** GL60 dimensions, KV/Kt, resistance range, rated torque,
inductance, bore, price; GB5015 dimensions, pole count, price and the absence of electrical data and of an
IP65 variant; Blue Robotics 2 in and 3 in tube dimensions, WetLink sizes and prices; Parker gland
dimensions for 2.62 mm O-rings; SKF shaft-hardness and finish requirements and the Speedi-Sleeve size
range; stainless bearing ratings; Tef-Gel, screw, insert and potting prices; T200 flooded-motor practice;
magnetic-coupling product classes and the axial-pull problem of disc couplings.
**Calculated here:** rotor loads and Cp (reviewed BEM), bearing life, shaft stresses, thermal rises,
generator operating points, depth stack-ups, interference-free CAD.
**Assumed:** lip-seal friction (4-24 mN m), GL60 cogging (~24 mN m), GM5208 resistance (13.7 ohm),
GB5015 winding, stator-to-cap thermal resistance (1 K/W), nacelle/strut Cp penalty (-2 to -4 %),
machining and anodising prices, 10 % thrust asymmetry.

## 11. Bill of materials (configuration A, one prototype)
{chr(10).join(bom_lines)}

Prototype total about **$550-1,030** including the generator ($142-185), two machined caps ($120-260) and
a 60 V-input charger ($40-150). Configuration B substitutes a 63.5 x 1.65 mm tube, a 316 tube spindle,
a flanged 316 collar, Speedi-Sleeve 99059, 2 x S6902-2RS and a 49-60 mm motor.
"""
open(os.path.join(HERE, "REPORT.md"), "w").write(txt)
print("wrote REPORT.md", len(txt.split()), "words")
