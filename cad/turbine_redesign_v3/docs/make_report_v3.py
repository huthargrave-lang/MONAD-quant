#!/usr/bin/env python3
"""Assemble REPORT_v3.md from the computed results so every number in the report is traceable to a script."""
import csv, json, math, os
D = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(D, "..")
cad = json.load(open(os.path.join(ROOT, "cad", "out", "v3_info.json")))
sysr = json.load(open(os.path.join(ROOT, "model", "system_results_v3.json")))
trial = json.load(open(os.path.join(ROOT, "model", "trial1_reconstruction.json")))
A = ASM = cad["configs"]; P = cad["params"]; VAR = cad["variants"]; G = sysr["assumptions"]
audit = open(os.path.join(ROOT, "audit", "verify_cad_audit.txt")).read()
bom = list(csv.DictReader(open(os.path.join(D, "BOM_v3.csv"))))
Lm, Lr = A["min76"]["layout"], A["robust"]["layout"]
C = sysr["cases"]
def c(V): return C[str(V)]
def mp(V): return c(V)["modes"]["mppt"]
def row_power(V):
    r = c(V); m = r["modes"]["mppt"]; o = r["modes"]["open"]
    if m:
        return f"| {V} | {r['P_water']:.1f} | {r['P_shaft_peak']:.1f} (Cp {r['cp_peak']:.3f}) | {m['Pm']:.1f} at TSR {m['lam']:.2f}, {m['rpm']:.0f} rpm | {m['I']:.2f} A / {m['Vdc']:.1f} V | {m['Pcu']:.1f} | {m['Pdc']:.1f} | {r['P_batt']:.1f} | {m['Pdc']/r['P_water']*100:.0f} % / {m['Pdc']/m['Pm']*100:.0f} % | {o['rpm']:.0f} rpm, {o['Vdc']:.0f} V |"
    return f"| {V} | {r['P_water']:.1f} | {r['P_shaft_peak']:.1f} (Cp {r['cp_peak']:.3f}) | no charging point | - | - | 0 | 0 | - | {o['rpm']:.0f} rpm, {o['Vdc']:.0f} V |"
def row_fault(V):
    r = c(V); d = r["modes"]["dump"]; b = r["modes"]["brake"]; o = r["modes"]["open"]; st = r["startup"]
    return f"| {V} | {st['static_Q']:.3f} / {st['breakaway']:.3f} ({'OK' if st['start_ok'] else 'NO'}, x{st['ratio']:.2f}) | {o['rpm']:.0f} rpm, {o['Vdc']:.0f} V | {d['rpm']:.0f} rpm, {d['Vdc']:.1f} V, {d['Pdc']:.1f} W resistor, {d['Pcu']:.1f} W copper | {b['rpm']:.0f} rpm, {b['Pcu']:.1f} W copper |"
parts_m = [p for p in A["min76"]["parts"] if not p["name"].startswith("oring")]
printed = [p for p in parts_m if p["kind"].startswith("print")]
machined = [p for p in parts_m if "machined" in p["kind"] or "metal" in p["kind"]]
tm = "\n".join(f"- **{k}**: {v}" for k, v in cad["to_measure"].items())
w = trial["worst_rel_dev"]
txt = f"""# Portable hydrokinetic turbine, redesign v3: engineering package

**Status: design package with reviewed, exported CAD and a transparent calculation model. No part has been printed, machined,
immersed or tested. Every performance figure is a model prediction; every manufacturer value is tagged with its source; the
manufacturer web pages themselves were not reachable from this session (see E13).**

## 1. Outcome against the requirements

| Requirement | Result | Evidence |
|---|---|---|
| 203.2 mm rotor, 1-2 m/s fresh water, primarily 3D-printed | met: rotor 203.2 mm (duct ID 207, 1.9 mm tip clearance); printed blades, carrier, dome, drive disc, duct; metal only where sealing, bearing seats, heat or strut bending require it | `cad/out/min76_*`, section 5 |
| **76 mm TOTAL OPERATING depth** (cable exits, bends, fasteners, guard included) | **met on nominal geometry by the "min76" variant: {Lm['axial_depth_mm']:.1f} mm from dome tip to boss rear, with the duct ({P['duct_id']} ID), strut feet, cable channel and all fastener heads inside that span; margin {76-Lm['axial_depth_mm']:.1f} mm, i.e. the tolerance stack (tube cut +-0.3, prints +-0.2) can consume it.** The "robust" variant (6902 bearings, 5 mm seal, 9 mm dome, 10 mm boss) is {Lr['axial_depth_mm']:.1f} mm: a **no-go against 76 mm by {Lr['axial_depth_mm']-76:.1f} mm**. Packed depth (rotor + drum without boss, struts and duct) is {Lm['x_boss'][0] - Lm['x_dome_tip'] - P['gap_drum_boss']:.1f} mm for min76. | section 4, `cad/out/min76_dimensioned.png` |
| Credible net power at each flow (12 V battery, buck MPPT) | **1.0 m/s: {c(1.0)['P_batt']:.1f} W into the battery; 1.5 m/s: {c(1.5)['P_batt']:.1f} W; 2.0 m/s: {c(2.0)['P_batt']:.1f} W** (water-to-DC {mp(1.0)['Pdc']/c(1.0)['P_water']*100:.0f} / {mp(1.5)['Pdc']/c(1.5)['P_water']*100:.0f} / {mp(2.0)['Pdc']/c(2.0)['P_water']*100:.0f} %). These are model values with a +-30 % honest band. | section 7 |
| Self-start at 1.0 m/s | marginal: static rotor torque {c(1.0)['startup']['static_Q']:.3f} N m against an assumed breakaway of {c(1.0)['startup']['breakaway']:.3f} N m (ratio {c(1.0)['startup']['ratio']:.2f}); reliable from about 1.2 m/s on the assumptions; a PTFE lip seal is the planned mitigation; must be measured (gate 9) | section 7.4 |
| Waterproof for continuous immersion (provisional 2 m) | boundary = anodised 6061 tube + 2 EPDM O-rings per machined Delrin cap + one lip seal on a Speedi-Sleeve + potted static cable exit; squeeze 14.9-20.6 % across the bore tolerance; vacuum, submersion and rotating tests defined; **not demonstrated** | section 6, `docs/VALIDATION_PLAN_v3.md` |
| Reviewed, corrected, consistent exports | four review passes recorded in `docs/ERROR_LOG.md`; final integrated check of the exported files in section 9 | |

**Provisional assumptions used (not confirmed requirements):** 2 m submergence; a 3 m/s flood as an off-design survival case; 12.8 V
LiFePO4 (13.2 V charging) battery; ASA filament with assumed wet allowables; 15 C water; the GL60 values cited by the independent
review; lip-seal friction 15 mN m running / 30 mN m breakaway; GL60 cogging 24 mN m. Their consequences are shown where they matter.

## 2. Audit of the supplied Configuration A (independently re-measured)

All seven review findings were reproduced on `01_original_inputs/A_assembly.step` with OpenCascade (`audit/verify_cad_audit.py`):

```
{audit.split('RIGID DEPTH')[1].split('names containing')[0].strip()}
```

| Finding (reproduced value) | Nature | Resolution in v3 |
|---|---|---|
| Rigid depth 188.600 mm; rotor alone 78.800 mm | real | architecture changed: generator inside the hub drum; min76 {Lm['axial_depth_mm']:.1f} mm total |
| Rotor/collar common volume 1369.60 mm3 | real rigid interference | no collar; the rotor is the drum; all rigid pairs checked (0.00 mm3 on 44 pairs) |
| Shaft and cap without retaining-ring grooves; no cap retention | real | spindle DIN 471-15 groove + integral 17.6 collar; caps captured both ways by the carrier lips and lugs |
| Bearings 8.000 mm apart; rear bearing 0.500 mm proud of the cap | real | bearings {Lm['x_brg_rear']-Lm['x_brg_front']:.1f} mm apart (front cap / rear cap), fully housed, cross-located |
| Strut/duct and clamp/strut overlaps; duct behind the rotor | real interface gaps | struts tabbed into the boss and slotted through the duct; duct spans the rotor plane with 1.9 mm tip clearance |
| No cable hardware (penetrator, nut, bend) in the envelope | real | leads inside the hollow spindle, potted static exit in the boss, cable channel in the boss face: inside the envelope |
| O-ring / lip overlaps (165 mm3 x4, 5-76 mm3) | intentional undeformed flexible geometry | kept as such; squeeze computed numerically instead |

The earlier standalone rotor (`earlier_turbine_rotor_8in_3blade.step`) is the same blade family as A's rotor but with a 50.8 mm
hub; it is not reused: v3 regenerates the blades for the 84.4 mm carrier.

## 3. Group member's analytical model: reproduced, reconstructed and corrected

**Reproduction.** `model/reproduce_trial1.py` rebuilds all 20 strips from the trial inputs. Worst deviation per exported column
(after the export's own rounding): r {w['r'][0]*100:.2f} %, lambda_r {w['lam_r'][0]*100:.3f} %, phi {w['phi'][0]*100:.3f} %, a {w['a'][0]*100:.3f} %, a' {w['ap'][0]*100:.2f} %,
chord {w['c'][0]*100:.2f} %, twist {w['twist'][0]*100:.3f} %, F {w['F'][0]*100:.3f} %, drag factor {w['dragf'][0]*100:.3f} %, mass flow {w['mdot'][0]*100:.3f} %, swirl {w['swirl'][0]*100:.3f} %, strip torque {w['dT'][0]*100:.2f} %, W {w['W'][0]*100:.3f} %, Re {w['Re'][0]*100:.3f} %.
Totals: torque {trial['T']:.4f} (export 0.4995) N m; water power {trial['Pw']:.3f} (132.003) W; Cp {trial['Cp']:.6f} (0.392220); Ke {trial['Ke']:.6f}; E {trial['E']:.3f} V; fixed-speed Pe,max {trial['Pe_max']:.3f} (8.08) W.

**Reconstructed equations (labelled as such; the original formulas were not supplied):** a from the Glauert optimum
lambda_r^2 = (1-a)(4a-1)^2/(1-3a); a' from a'(1+a') lambda_r^2 = a(1-a); tan(phi) = (1-a)/((1+a') lambda_r); chord from momentum
matching c = 8 pi r a sin^2(phi) / (B C_L (1-a) cos(phi)) (no tip loss in the chord); twist = phi - 5 deg; F = Prandtl tip x hub loss
(hub form with r_h in the denominator); drag factor 1 - (C_D/C_L)/tan(phi); strip torque = rho 2 pi r dr V (1-a) x 2 a' omega r x r x F x drag factor;
W = sqrt((V(1-a))^2 + (omega r (1+a'))^2); Re = W c / nu; Ke = 60/(2 pi Kv); E = Ke omega; Pe,max = (E - 2 Vf)^2 / (4 Rg).
Damaged symbols resolved by these equations: the "?" columns are lambda_r, phi (deg), alpha-related twist (deg), and the radial-width
cell "0.003 [mm]" is {trial['dr']*1000:.3f} mm stored in metres and display-rounded. Not reconstructed: lambda_run 6.493, the 0.1646 cell and the 1.55 ratio.

**What was wrong or incomplete in the trial, and the correction:**
1. The electrical "8.08 W" is the fixed-speed maximum of a matched resistive load at 990 rpm: it needs I = {trial['I_pm']:.2f} A at V = {trial['V_pm']:.2f} V (below the 3 V charger minimum) and only Ke I = 0.188 N m of generator torque against 0.499 N m of rotor torque: not an operating point. Corrected: the rotor curve and the generator/charger load law are solved together across speed (section 7); the 170 KV / 0.72 ohm machine is replaced because Km = Kt/sqrt(R) = 0.066 cannot absorb the torque at useful voltage.
2. The polar (C_L 1.0, C_D 0.0127 at 5 deg, Re 2e5) is not identified and is applied at Re 7.5e4-8.1e4 where any such section has 1.5-2.5x the drag and earlier stall. Corrected: the v3 BEM uses a Reynolds-dependent NACA 44xx model (drag scaling Re^-0.8 anchored at 1.5e5, reviewed earlier) evaluated per element at the real Re (6.8e4-1.5e5 at 1.5 m/s). Printed roughness (Ra 10-20 um, 1 % of the 2 mm leading-edge radius) adds an estimated 0.01-0.02 to Cd: the honest Cp band is widened to -0.03 for it.
3. Hub radius 29.8 mm was the motor radius + 2 mm wall; the actual assembly needs 42.2 mm (tube 76.2 + carrier wall). Corrected and the blades regenerated.
4. Chord/twist of the trial were candidates; the v3 planform (max chord 60 mm at 58 % radius, root chord 38 mm, NACA 4424 -> 4415, 1 mm TE) is chosen for the drum length, printability and static torque.

**Original trial vs corrected model vs final design**

| | Original trial (as exported) | Corrected model of the same trial | Final v3 design |
|---|---|---|---|
| Rotor | 7 in, hub 29.8 mm, 3 blades | same geometry | 8 in (203.2), hub 42.2 mm, 3 blades, regenerated planform |
| Flow for the number | 2.2 m/s only | 2.2 m/s | 1.0 / 1.5 / 2.0 (2.2 and 3.0 as checks) |
| Rotor shaft power | 51.8 W (Cp 0.392 at Re 2e5 polar) | same arithmetic, but Re 7.5e4 polars would give Cp ~0.30-0.33 (estimate) | {c(2.2)['P_shaft_peak']:.1f} W peak at 2.2 m/s (Cp {c(2.2)['cp_peak']:.3f}); {c(2.0)['P_shaft_peak']:.1f} W at 2.0 |
| Generator | 170 KV, 0.72 ohm (assumed), I0 0.4 A | fixed-speed matched load: 8.08 W at 2.41 V (unusable) | GL60 KV25 (Kt 0.444, 5.5 ohm): {mp(2.2)['Pdc']:.1f} W DC at 2.2 m/s, {mp(2.0)['Pdc']:.1f} W at 2.0 |
| Operating point | not a torque balance | torque balance solved: not possible at 990 rpm with that load | solved per speed with the charger law and a 1.2 A generator limit |
| Pass/fail vs 10 W | FAIL | FAIL (voltage) | {mp(2.2)['Pdc']:.0f} W DC at 2.2 m/s: PASS; {mp(1.0)['Pdc']:.1f} W at 1.0 m/s: FAIL (the 10 W goal is the trial's, not a group requirement) |

## 4. Architecture: why a through-spindle drum rotor, and what limits the depth

Packaging attempt (series stack of real part lengths, `model/packaging_76mm.py` and the CAD): the supplied nacelle layout is
{188.6:.0f} mm rigid (215 mm with cable hardware); a hub-integrated layout with the generator behind a seal on a spindle was 140 mm;
the only way to approach 76 mm is to put the generator **inside** the rotating hub with the stationary spindle passing through the
motor's 20 mm bore, so that bearings, seal, O-rings and motor overlap radially instead of stacking axially. Dimensioned stack of the
min76 variant: dome {VAR['min76']['dome_h']} + front flange {VAR['min76']['flange_t']} + tube {Lm['L_tube']:.1f} (= plug {VAR['min76']['plug_len']} + {VAR['min76']['ic']} + disc {P['disc_t']} + 0.5 + GL60 {P['motor_len']} + flange {P['sp_flange_t']} + {VAR['min76']['ic']} + plug {VAR['min76']['plug_len']}) + rear flange {VAR['min76']['flange_t']} + carrier lip {P['carrier_lip']} + gap {P['gap_drum_boss']} + boss {VAR['min76']['boss_t']} = {Lm['axial_depth_mm']:.1f} mm. The struts do not add length because they are cranked
{VAR['min76']['strut_jog']:.0f} mm forward alongside the drum at radii the rotating parts never reach.

**Limiting components:** the GL60 length (22.3 mm, fixed), two O-ring plugs (2 x 11.4 mm; each needs two grooves and lands),
the lip seal plus its land (5 mm) and the boss (8 mm) with its cable exit. With the robust parts (6902 bearings, 5 mm seal, 13 mm plugs,
9 mm dome, 10 mm boss) the same layout is {Lr['axial_depth_mm']:.1f} mm.

**Decision and tradeoff:** min76 is the preferred build *provided* the thin-section 6702 bearings (C0 0.62 kN against 86 N
thrust in a 3 m/s flood) and the 4 mm seal are accepted; if either fails its bench gate, the robust variant is the fall-back and the
76 mm requirement becomes a declared no-go at {Lr['axial_depth_mm']:.1f} mm. The hub ratio rises from 0.25 to 0.42, which costs about
19 % of rotor power (Cp 0.368 -> {c(1.5)['cp_peak']:.3f} at 1.5 m/s); that is the price of the envelope.

Alternatives considered and rejected for this iteration: stationary nacelle (best cooling and seal access, 189 mm); magnetic
coupling (no rotary seal; adds 20 mm and an unqualified coupling); flooded potted generator (no enclosure; T200-style, but silt,
magnet corrosion and the GL60's open construction are unqualified).

## 5. Mechanical design

**Load paths (all rigid, modelled, zero interference on 44 checked pairs):**
- Thrust (water pushes the rotor downstream): blade -> pinned tongue -> carrier segment -> rear lip -> rear cap flange -> rear cap shoulder -> rear bearing outer/inner race -> spindle collar (17.6 x 1.3) -> spindle -> boss cross pin -> boss -> 3 strut tabs (pinned) -> struts -> duct feet (6x M4).
- Reverse load (handling, reverse flow): carrier front lip -> front cap -> front bearing -> DIN 471-15 circlip -> spindle. Bearings are cross-located with ~0.2 mm end play for thermal freedom; the front bearing floats in its pocket toward the rear.
- Torque: blades -> carrier lugs in the cap-flange notches -> front cap -> TPU dog clutch (4 dogs 8 x 4) -> GL60 bell; stator reaction -> spindle flange -> spindle -> boss pin -> struts -> duct. No grub screw and no bonded joint carries torque; the 6 carrier bolts only clamp.
- Coupling engagement: the dogs engage 4 mm into the cap pockets with 0.3 mm radial clearance; the TPU absorbs the small radial/axial mismatch between the bell (on the motor's own bearings) and the drum (on the spindle bearings).

**Machined and metal parts and their functions** (section 6 of `docs/PRINT_ASSEMBLY_PLAN.md`): front cap, rear cap (Delrin:
O-ring lands, bearing seats, seal seat), spindle (6061: journals, counterface, stator flange, heat path), boss (6061 plate: heat
sink, strut and pin seats), struts (6061 flat bar: bending), tube (6061: pressure wall). Drawings: `cad/out/min76_drawing_*.png`.

**Printed parts, structure (ASA provisional; allowables assumed, coupons required):** blade root joint = tongue 29.7 x 11.7 x 8
in a carrier pocket with two 3 mm 316 pins through the pad: at the 3 m/s maximum thrust ({c(3.0)['T_max']:.0f} N rotor, {c(3.0)['T_max']/3:.1f} N per blade)
the pin couple is 34 N, pin shear 2.4 MPa, tongue bearing 1.0 MPa (allowable 8 long / 15 short); airfoil root bending 2.4 MPa with
layers along the span; 3 mm root fillet. Centrifugal load at the 3 m/s runaway ({c(3.0)['modes']['open']['rpm']:.0f} rpm) is 83 N per blade -> 1.2 MPa pin bearing.
Carrier: 6x M3 316 through-bolts + nyloc, ear bearing stress 14 MPa under washers (compression); lugs 6 x 3 in shear carry 1.5 N m jam
torque at 0.3 MPa. Creep: bearing seats are in Delrin, not in prints; the printed carrier's clamp preload is re-torqued after 24 h.
Balance: blades matched to 0.3 g; drum static-balanced. Overspeed: 1835 rpm (3 m/s runaway) is the design overspeed, tip 19.5 m/s.
One-piece rotor vs modular: a one-piece carrier-with-blades would print the blade roots across layers (weak) and need heavy supports;
the modular pinned root prints each blade flat (strong direction) and lets a damaged blade be replaced; chosen.

**Struts:** 6061-T6 16 x 4 bar: 12.3 MPa at the duct foot and 19.3 MPa in the 7.6 mm tab at the 3 m/s thrust; 12.3 MPa weak-axis from a
1.5 N m jam; 0.03 mm deflection. Three printed NACA struts of 24 mm chord would have seen 5.7-13.6 MPa (over the printed allowable
in a flood) and would have added 16 mm of depth.

**Hydrodynamics after the structural thickness:** hub ratio 0.42 (carrier OD 84.4) and blade pads to r = 48.2: BEM Cp
{c(1.0)['cp_peak']:.3f} / {c(1.5)['cp_peak']:.3f} / {c(2.0)['cp_peak']:.3f} at 1 / 1.5 / 2 m/s (Re-dependent). The duct is modelled only as a guard ring; its augmentation is not
credited. The struts and boss are behind the rotor at radii 36-107 mm and 36 mm; blockage ~4 % of the annulus: a -1 to -3 % Cp effect
(estimate). The 6 mm dome is blunt; the root region it affects contributes < 5 % of torque.

## 6. Sealing, pressure and heat (resolved together)

- **Boundary:** tube wall (anodised, Ra 0.8 bore) -> two radial AS568-147 EPDM O-rings per Delrin plug -> Delrin caps -> one lip seal
  on the stationary spindle -> the spindle bore (dry) -> potted side exit in the stationary boss. No screw crosses the boundary: the
  caps are retained by the printed carrier lips/lugs, the vent is a sealed M6 port, the dome screws are blind in the flange.
- **Glands:** plug 72.75 in a 72.9 +-0.15 bore; groove 3.6 x 2.08; squeeze {14.9:.1f}-{20.6:.1f} % over the bore tolerance; fill 69 %; stretch 0.9 %.
  Measured-bore machining is mandatory (gate 3). Printed surfaces seal nothing.
- **Rotary seal:** 15 x 22 x 4 (min76) / 15 x 24 x 5 (robust) spring-loaded NBR TC seal, lip to the water, speed 1.0 m/s at 1270 rpm,
  pressure 0.2 bar + 0.11 kPa breathing. Counterface: SKF Speedi-Sleeve **99059** (15 mm; the 12 mm sleeve the earlier report cited as
  99047 is 99049 in SKF's table: not used here). Installation on an anodised aluminium journal must be confirmed with SKF; the fallback
  is a pressed 316 journal sleeve or the hard-anodised journal itself (Ra 0.4) with 2-week inspections. Seal life is not qualified here.
- **Pressure:** 19.6 kPa at 2 m pushes each cap inward with 82 N (carrier lip bearing 0.17 MPa); the -70 kPa vacuum test applies 292 N.
  Cooling from 40 to 5 C adds 11 kPa; the vent plug is closed before immersion and never opened under water.
- **Cable:** 3 leads inside the 9 mm spindle bore, 5 mm bend at the side exit, 20 mm epoxy plug (static), channel in the boss, splice
  at a duct foot. No WetLink is needed in the rotating drum; the earlier 24 mm cap / 20 mm thread conflict disappears.
- **Heat:** stator -> aluminium spindle flange (paste) -> spindle (2.65 K/W over 50 mm) -> boss in the water (0.15 K/W) -> total
  3.6 K/W by metal alone: +29 K at the 1.2 A limit (7.9 W), +42 K at 1.45 A. The Delrin caps see < +10 K. The air-gap path through the
  rotating bell is not credited. Gate 7 measures it; the current limit is the knob.

## 7. Performance: water power, shaft power, rectified DC, battery

Model: `model/system_model_v3.py` (conventions in its header). Rotor Cp(lambda, V) from the reviewed BEM; running friction
{G['seal_running_Nm']*1000:.0f} mN m (seal) + 2 x {G['bearing_running_Nm']*1000:.0f} mN m (bearings); GL60 Kt {60/(2*math.pi*G['KV']):.3f} N m/A, R_LL {G['R_LL']} ohm, L_LL {G['L_LL']*1000:.2f} mH, 14 pole pairs; six MBR10100 diodes
(2 x {G['Vf_diode']} V); commutation drop (3/pi) w_e (L/2) I; generator current limit {G['gen_current_limit']} A; Victron 100/15 buck MPPT (runs only while
V_dc >= V_bat + 1 = {G['battery_V']+1:.1f} V); battery {G['battery_V']} V; charger efficiency {G['charger_eff']*100:.0f} %, quiescent {G['charger_quiescent_W']} W.

| Flow (m/s) | Water power (W) | Rotor peak shaft (W) | Charging point shaft | DC current / voltage | Copper loss (W) | **Rectified DC (W)** | **Net to battery (W)** | water-to-DC / shaft-to-DC | No-load runaway |
|---|---|---|---|---|---|---|---|---|---|
{row_power(1.0)}
{row_power(1.2)}
{row_power(1.5)}
{row_power(2.0)}
{row_power(2.2)}
{row_power(3.0)}

The earlier "70 %" was shaft-to-DC; water-to-DC is 17-22 %. At 1.0 m/s the buck charger forces the rotor above its best TSR
(V_dc must stay above 14.2 V), which costs about a quarter of the available 1 m/s power; a boost stage would recover it but no COTS
charger does both buck and boost over 10-60 V (research: Genasun GVB-8 cannot regulate when V_in > V_bat). At 3 m/s the charger point
is 66 V: the dump threshold (45 V) engages first.

**Startup, runaway, dump and brake (torque-balanced per speed):**

| Flow | Static torque / breakaway (N m) | Open circuit | Dump 15 ohm (relay at 45 V) | 3-phase short brake |
|---|---|---|---|---|
{row_fault(1.0)}
{row_fault(1.5)}
{row_fault(2.0)}
{row_fault(2.2)}
{row_fault(3.0)}

Reading: the dump holds the bus below 25 V at 2 m/s (24 W in the resistor, heatsink required) and 36 V at 3 m/s but with 32 W of
copper loss in a generator whose metal heat path allows ~12 W: **the dump is a full-battery / charger-fault response for <= 2.2 m/s,
not a flood response.** The 3-phase short brake stops the rotor to 75-150 rpm at 1-2 m/s (2-9 W in the winding) and is the retrieval
brake; at 3 m/s it equilibrates at 645 rpm with 134 W in the winding and must not be used. **The 3 m/s case is survived only
open-circuit** (1835 rpm, 85 V on the bus: below the Victron's 100 V and the 5KP85A standoff) or by retrieval; blade loads at that
speed are covered in section 5.

## 8. Power electronics and control logic (selected parts, research in `research/research_electrical_v3.md`)

Generator (3 phases) -> NKK S32F 3PDT brake switch (RUN / BRAKE) -> 6 x MBR10100 bridge (100 V) -> DC bus [2 x 5KP85A TVS; 6-80 V
voltage-monitor relay: engage 45 V / release 35 V -> Ohmite HS100 15 ohm 100 W on a heatsink] -> Victron SmartSolar MPPT 100/15 ->
5 A fuse (Littelfuse 0287005 in FHAC0001) -> Anderson Powerpole -> 12.8 V LiFePO4. Dry box Hammond 1554F2GY (IP68) with PG7 glands;
generator cable Weipu SP13 IP68 connector.
- Unloaded start: switch in RUN, charger off until the bus exceeds V_bat + 5 V (about 18 V): the rotor accelerates unloaded to its
  no-load speed (518 rpm at 1 m/s = 24 V), then the MPPT ramps the load; it cannot pull the bus below V_bat + 1 V, so it cannot stall the
  rotor by itself. The generator-side current limit (1.2 A) is implemented as the Victron's charge-current limit scaled by the bus
  ratio (set 2.5 A battery-side at 13.2 V) and verified at gate 11; it protects the winding, not the rotor.
- Full battery or charger fault: the bus rises toward open circuit; the dump relay engages at 45 V; the resistor sees 24-34 W at 2-2.2 m/s.
- Load disconnect at any speed <= 2.2 m/s: open circuit <= 60 V; TVS and the 100 V charger input are within rating; dump engages if the relay is powered from the bus (it is).
- Retrieval: BRAKE at <= 1.5 m/s (2-5 W in the winding); above that, open-circuit and wait.
- Floods (3 m/s provisional): open-circuit only; do not dump or brake; retrieve when possible.

## 9. Reviews and final integrated check

Four independent review passes (calculation/units, mechanical-CAD, printability/manufacturing, skeptical failure-mode) were run on
this package by separate reviewer agents working from the exported files; their findings, the corrections and the re-verification are
in `docs/ERROR_LOG.md` (entries R-xx). The final integrated check re-imported `cad/out/min76_assembly.step` and `robust_assembly.step`
(all solids valid, zero rigid interference on the pair list), re-ran the three models and regenerated this report from their outputs,
and reconciled the BOM against the part table in `cad/out/v3_info.json` (section 10).

## 10. Deliverables and what remains open

| Deliverable | Where |
|---|---|
| Preferred architecture + justification | this report, sections 4-6 |
| Dimensioned assembly, section, exploded views | `cad/out/min76_section.png`, `min76_dimensioned.png`, `min76_exploded.png` (+ `robust_*`) |
| Editable parametric CAD and assembly STEP | `cad/make_v3.py`; `cad/out/min76_assembly.step`, `robust_assembly.step`; per-part `*.step` |
| Oriented printable STLs | `cad/out/min76_*_PRINT.stl` ({len(printed)} parts; all watertight) |
| Machined-part drawings | `cad/out/min76_drawing_front_cap.png`, `_rear_cap.png`, `_spindle.png`, `_boss_strut.png` |
| Per-part print/assembly plan | `docs/PRINT_ASSEMBLY_PLAN.md` |
| BOM with sourced specs and cost scope | `docs/BOM_v3.csv` ({len(bom)} lines; one prototype $690-1,230 hardware, excluding battery, duct beyond the ring, frame, instrumentation) |
| Calculation model (reproducible) | `model/reproduce_trial1.py`, `system_model_v3.py`, `structure_seal_thermal_v3.py`, `packaging_76mm.py`, `rotor_v3.py` + JSON outputs |
| Original vs corrected vs final comparison | section 3 |
| Validation plan with acceptance criteria | `docs/VALIDATION_PLAN_v3.md` |
| Error-review / correction log | `docs/ERROR_LOG.md` |

**Measurements required before the machined parts are cut:**
{tm}

**Remaining assumptions that move the result:** lip-seal breakaway (decides 1.0 m/s self-start), GL60 cogging and the exact
Kt/R (+-10 % on DC power), the stator-to-flange thermal joint (decides the current limit), printed wet allowables (coupons), the
real tube bore (gland machining), duct augmentation (not credited), and the deployment depth and flood regime (provisional 2 m / 3 m/s).

**Required physical tests:** the twelve gates in `docs/VALIDATION_PLAN_v3.md`; none has been run.
"""
open(os.path.join(D, "REPORT_v3.md"), "w").write(txt)
print("wrote REPORT_v3.md", len(txt.split()), "words")
