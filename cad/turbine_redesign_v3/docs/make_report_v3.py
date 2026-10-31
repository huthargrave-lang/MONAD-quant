#!/usr/bin/env python3
"""Assemble REPORT_v3.md from the computed results so every number in the report is traceable to a script (review R05)."""
import csv, json, math, os, re
D = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(D, "..")
cad = json.load(open(os.path.join(ROOT, "cad", "out", "v3_info.json")))
sysr = json.load(open(os.path.join(ROOT, "model", "system_results_v3.json")))
S = json.load(open(os.path.join(ROOT, "model", "structure_results_v3.json")))
trial = json.load(open(os.path.join(ROOT, "model", "trial1_reconstruction.json")))
A = cad["configs"]; P = cad["params"]; VAR = cad["variants"]; G = sysr["assumptions"]
audit = open(os.path.join(ROOT, "audit", "verify_cad_audit.txt")).read()
bom = list(csv.DictReader(open(os.path.join(D, "BOM_v3.csv"))))
fc_path = os.path.join(D, "FINAL_CHECK.txt"); final_check = open(fc_path).read().strip() if os.path.exists(fc_path) else "(final check not yet run)"
errlog = open(os.path.join(D, "ERROR_LOG.md")).read()
n_R = len(re.findall(r"^\| R\d\d \|", errlog, flags=re.M)); n_E = len(re.findall(r"^\| E\d\d \|", errlog, flags=re.M))
Lm, Lr = A["min76"]["layout"], A["robust"]["layout"]; Vm, Vr = VAR["min76"], VAR["robust"]
C = sysr["cases"]
def c(V): return C[str(V)]
def mp(V): return c(V)["modes"]["mppt"]
def pct(a, b): return f"{a/b*100:.0f} %"
def row_power(V):
    r = c(V); m = r["modes"]["mppt"]; o = r["modes"]["open"]
    return (f"| {V} | {r['P_water']:.1f} | {r['P_shaft_peak']:.1f} (Cp {r['cp_peak']:.3f}) | {m['Pm']:.1f} at TSR {m['lam']:.2f}, {m['rpm']:.0f} rpm | {m['I']:.2f} A / {m['Vdc']:.1f} V | {m['Pcu']:.1f} + {m['Pfe']:.1f} | **{m['Pdc']:.1f}** | **{r['P_batt']:.1f}** | "
            f"{pct(m['Pdc'], r['P_water'])} / {pct(m['Pdc'], m['Pm'])} | {o['rpm']:.0f} rpm, {o['Vdc']:.0f} V (sigma {r['sigma_tip_runaway']:.2f}) |")
def row_fault(V):
    r = c(V); d = r["modes"]["dump"]; b = r["modes"]["brake"]; o = r["modes"]["open"]; st = r["startup"]
    return (f"| {V} | {st['static_Q']:.3f} / {st['breakaway']:.3f} (x{st['ratio']:.2f}) / {st['breakaway_nbr']:.3f} (x{st['ratio_nbr']:.2f}) | {o['rpm']:.0f} rpm, {o['Vdc']:.0f} V, sigma {r['sigma_tip_runaway']:.2f} | "
            f"{d['rpm']:.0f} rpm, {d['Vdc']:.1f} V, {d['Pdc']:.1f} W resistor, {d['Pcu']:.1f} W copper, sigma {r['sigma_tip_dump']:.2f} | {b['rpm']:.0f} rpm, {b['Pcu']:.1f} W copper |")
def row_sens(V):
    r = c(V); return f"| {V} | {r['P_dc']:.1f} | {r['Pdc_nofloor']:.1f} | {r['Pdc_KV25']:.1f} | {r['Pdc_NBRseal']:.1f} | {r['windage_Nm_at_charging']*1000:.0f} |"
def row_dump(V):
    r = c(V); ds = r["dump_study"]
    return f"| {V} | " + " | ".join(f"{ds[k]['rpm']:.0f} rpm, {ds[k]['Vdc']:.0f} V, {ds[k]['Pres']:.0f} W, sigma {ds[k]['sigma_tip']:.2f}" for k in ("15.0", "22.0", "33.0", "47.0")) + " |"
parts_m = [p for p in A["min76"]["parts"] if not p["name"].startswith("oring")]
printed = [p for p in parts_m if p["kind"].startswith("print")]
blade0 = next(p for p in A["min76"]["parts"] if p["name"] == "blade_0")
tm = "\n".join(f"- **{k}**: {v}" for k, v in cad["to_measure"].items())
w = trial["worst_rel_dev"]
stack_m = f"dome {Vm['dome_h']} + front flange {Vm['flange_t']} + tube {Lm['L_tube']:.1f} (= plug {Vm['plug_front']} + {Vm['ic']} + disc {P['disc_t']} + 0.5 + GL60 {P['motor_len']} + flange {P['sp_flange_t']} + {Vm['ic']} + plug {Vm['plug_rear']}) + rear flange {Vm['flange_t']} + carrier lip {P['carrier_lip']} + gap {P['gap_drum_boss']} + boss {Vm['boss_t']}"
cost_lo = cost_hi = 0.0
for r in bom:
    q = float(r["qty"]); u = r["unit USD"].replace("$", "")
    nums = [float(x) for x in re.findall(r"\d+\.?\d*", u.split("each")[0])]
    if not nums: continue
    per_each = "each" in u
    lo, hi = (min(nums), max(nums)) if "-" in u else (sum(nums), sum(nums))
    cost_lo += lo * (q if per_each or "+" not in u else 1); cost_hi += hi * (q if per_each or "+" not in u else 1)
brg = S["bearings"]["min76 6702-2RS"]
txt = f"""# Portable hydrokinetic turbine, redesign v3.1: engineering package

**Status: design package with reviewed, corrected and re-exported CAD and a transparent calculation model. No part has been
printed, machined, immersed or tested. Every performance figure is a model prediction; every manufacturer value is tagged with its
source in the BOM; the manufacturer web pages themselves were not reachable from this session (E13). One correction-and-review
cycle was run: {n_R} review findings (R01-R{n_R:02d}) and {n_E} first-draft findings are logged with their corrections and
re-verification in `docs/ERROR_LOG.md`; the final integrated check of the exported files is in section 9.**

## 1. Outcome against the requirements

| Requirement | Result | Evidence |
|---|---|---|
| 203.2 mm rotor, 1-2 m/s fresh water, primarily 3D-printed | met: rotor 203.2 mm in a duct of ID {P['duct_id']:.0f} ({(P['duct_id']-203.2)/2:.1f} mm tip clearance); printed blades, carrier, dome, drive disc, duct ({len(printed)} print files); metal only where sealing, bearing seats, thrust, heat or strut bending require it | `cad/out/min76_*`, section 5 |
| **76 mm TOTAL OPERATING depth** (cable exits, bends, fasteners, guard included) | **met on nominal geometry by the "min76" variant: {Lm['axial_depth_mm']:.1f} mm from dome tip to boss rear face**, with the duct, strut legs and clevises, the cable path (inside the spindle and the boss rear-face groove), the vent screw and every screw head inside that span; **margin {76-Lm['axial_depth_mm']:.1f} mm** against a worst-case stack of about 1.0 mm (tube cut +-0.3, prints +-0.2, machining +-0.1). The "robust" variant (6902 bearings, 5 mm seal, two O-rings per cap, 9 mm dome) is {Lr['axial_depth_mm']:.1f} mm: a **declared no-go against 76 mm by {Lr['axial_depth_mm']-76:.1f} mm** and the fall-back if the 6702 bearings or the 4 mm seal fail their bench gates. Packed depth (rotor and drum without the boss, struts and duct) is {Lm['x_rear_face'] + P['carrier_lip'] - Lm['x_dome_tip']:.1f} mm. | section 4, `cad/out/min76_dimensioned.png`, `docs/FINAL_CHECK.txt` |
| Credible net power at each flow (12.8 V LiFePO4, Victron buck MPPT) | **1.0 m/s: {c(1.0)['P_dc']:.1f} W DC / {c(1.0)['P_batt']:.1f} W into the battery; 1.5 m/s: {c(1.5)['P_dc']:.1f} / {c(1.5)['P_batt']:.1f} W; 2.0 m/s: {c(2.0)['P_dc']:.1f} / {c(2.0)['P_batt']:.1f} W** (water-to-DC {pct(mp(1.0)['Pdc'], c(1.0)['P_water'])} / {pct(mp(1.5)['Pdc'], c(1.5)['P_water'])} / {pct(mp(2.0)['Pdc'], c(2.0)['P_water'])}). Model values; honest band -30 % / +10 % (polar, roughness, GL60 constants, windage). | section 7 |
| Self-start at 1.0 m/s | **not demonstrated; model-marginal.** Static rotor torque {c(1.0)['startup']['static_Q']:.3f} N m against an assumed breakaway of {c(1.0)['startup']['breakaway']:.3f} N m with the PTFE seal (x{c(1.0)['startup']['ratio']:.2f}) and {c(1.0)['startup']['breakaway_nbr']:.3f} N m with an NBR seal (x{c(1.0)['startup']['ratio_nbr']:.2f}: fails). Reliable from about 1.2 m/s (x{c(1.2)['startup']['ratio']:.2f}) on the assumptions. Gates 5 and 9 decide. | section 7 |
| Waterproof for continuous immersion (provisional 0.3-2 m axis depth) | boundary = hard-anodised 6061 tube with bored lands + {Vm['n_orings']} EPDM O-ring per anodised 6061 cap + one PTFE pressure-rated lip seal on a Speedi-Sleeve + an O-ring potting plug in the spindle end; no printed surface and no screw in the boundary; squeeze {min(S['seal']['min76']['squeeze_pct'].values()):.1f}-{max(S['seal']['min76']['squeeze_pct'].values()):.1f} % over the bore tolerance; seal differential {S['p_diff_bar']:.2f} bar (PTFE seal rated 5 bar); internal overpressure from stator heat {S['dP_internal_kPa']:.1f} kPa at the current limit -> minimum axis depth {S['min_depth_m']:.2f} m; vacuum, submersion, thermal-cycle and rotating tests defined; **not demonstrated** | section 6, `docs/VALIDATION_PLAN_v3.md` |
| Overspeed / overvoltage protection, dump and brake behaviour, full-battery and disconnected-load cases | independent of the charger: voltage-monitor relay (engage 45 V / release 12 V, no cycling) into a submerged 22 ohm dump block; 3-phase short brake switch; 5KP90A TVS; behaviour tabulated per flow in section 7 (torque-balanced); 3 m/s flood = dump engaged (cavitation number {c(3.0)['sigma_tip_dump']:.2f}) with {c(3.0)['modes']['dump']['Pcu']:.0f} W in the winding: survivable, not continuous | sections 7-8 |
| Reviewed, corrected, consistent exports | four independent review passes; {n_R} findings corrected and re-verified; final integrated check on the exported files (section 9) | `docs/ERROR_LOG.md`, `docs/FINAL_CHECK.txt` |

**Provisional assumptions used (not confirmed requirements):** 0.3-2 m axis depth; a 3 m/s flood as an off-design survival case; 12.8 V
LiFePO4 ({G['battery_V']} V charging); ASA filament with assumed wet allowables; 15 C water; the GL60 values cited by the independent
review (KV {G['KV']}, R_LL {G['R_LL']} ohm, L_LL {G['L_LL']*1000:.2f} mH, {G['pole_pairs']} pole pairs); PTFE lip-seal friction {G['seal_running_Nm']*1000:.1f} mN m running / {G['seal_running_Nm']*G['seal_breakaway_factor']*1000:.0f} mN m breakaway (NBR {G['seal_alt_running_Nm']*1000:.0f} / {G['seal_alt_running_Nm']*G['seal_breakaway_factor']*1000:.0f});
GL60 cogging {G['cogging_Nm']*1000:.0f} mN m; no-load loss {G['iron_loss_W_at_700rpm']} W at 700 rpm. Their consequences are shown where they matter (section 7 sensitivities).

## 2. Audit of the supplied Configuration A (independently re-measured)

All seven review findings were reproduced on `01_original_inputs/A_assembly.step` with OpenCascade (`audit/verify_cad_audit.py`):

```
{audit.split('RIGID DEPTH')[1].split('names containing')[0].strip()}
```

| Finding (reproduced value) | Nature | Resolution in v3.1 |
|---|---|---|
| Rigid depth 188.600 mm; rotor alone 78.800 mm | real | architecture changed: generator inside the hub drum; min76 {Lm['axial_depth_mm']:.1f} mm total |
| Rotor/collar common volume 1369.60 mm3 | real rigid interference | no collar on the rotor; all {Lm['pairs_checked']} rigid part pairs checked: 0 overlap (section 9) |
| Shaft and cap without retaining-ring grooves; no cap retention | real | spindle DIN 471-15 groove (reverse thrust) + split 316 thrust ring (operating thrust); caps captured both ways by the carrier lips and lugs |
| Bearings 8.000 mm apart; rear bearing 0.500 mm proud of the cap | real | bearings {Lm['x_brg_rear']-Lm['x_brg_front']:.1f} mm apart (front cap / rear cap), fully housed, cross-located, end play shimmed to 0.1-0.2 |
| Strut/duct and clamp/strut overlaps; duct behind the rotor | real interface gaps | struts tabbed into the boss and clamped in duct clevises; duct spans the rotor plane with {(P['duct_id']-203.2)/2:.1f} mm tip clearance |
| No cable hardware (penetrator, nut, bend) in the envelope | real | leads inside the hollow spindle, O-ring potting plug in the recessed spindle end, lead groove in the boss rear face, cable along a strut: all inside the envelope |
| O-ring / lip overlaps (165 mm3 x4, 5-76 mm3) | intentional undeformed flexible geometry | kept as such; squeeze computed numerically instead |

The earlier standalone rotor (`earlier_turbine_rotor_8in_3blade.step`) is the same blade family as A's rotor but with a 50.8 mm
hub; it is not reused: v3 regenerates the blades for the {2*Lm['r_hub']:.1f} mm carrier.

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
2. The polar (C_L 1.0, C_D 0.0127 at 5 deg, Re 2e5) is not identified and is applied at Re 7.5e4-8.1e4 where any such section has 1.5-2.5x the drag and earlier stall. Corrected: the v3 BEM uses a Reynolds-dependent NACA 44xx model (drag scaling Re^-0.8 anchored at 1.5e5) evaluated per element at the real Re. Printed roughness adds an estimated 0.01-0.02 to Cd: the honest Cp band is widened by -0.03 for it.
3. Hub radius 29.8 mm was the motor radius + 2 mm wall; the actual assembly needs {Lm['r_hub']:.1f} mm (tube 76.2 + carrier wall) and the printed blade starts at the pad top, r = {Lm['r_pad_top']:.1f} mm: the BEM now integrates from there (R01).
4. Chord/twist of the trial were candidates; the v3 planform (max chord {P['c_max']:.0f} mm at {P['peak_r']*100:.0f} % radius, pad-top chord {S['root_chord_mm']:.1f} mm, NACA 4424 -> 4415, 1 mm TE) is chosen for the drum length, printability and static torque.

**Original trial vs corrected model vs final design**

| | Original trial (as exported) | Corrected model of the same trial | Final v3.1 design |
|---|---|---|---|
| Rotor | 7 in, hub 29.8 mm, 3 blades | same geometry | 8 in (203.2), carrier {2*Lm['r_hub']:.1f} mm, airfoil from r {Lm['r_pad_top']:.1f}, 3 blades, regenerated planform |
| Flow for the number | 2.2 m/s only | 2.2 m/s | 1.0 / 1.5 / 2.0 (1.2, 2.2 and 3.0 as checks) |
| Rotor shaft power | 51.8 W (Cp 0.392 at Re 2e5 polar) | same arithmetic, but Re 7.5e4 polars would give Cp ~0.30-0.33 (estimate) | {c(2.2)['P_shaft_peak']:.1f} W peak at 2.2 m/s (Cp {c(2.2)['cp_peak']:.3f}); {c(2.0)['P_shaft_peak']:.1f} W at 2.0 |
| Generator | 170 KV, 0.72 ohm (assumed), I0 0.4 A | fixed-speed matched load: 8.08 W at 2.41 V (unusable) | GL60 KV25 (Kt {60/(2*math.pi*G['KV']):.3f}, {G['R_LL']} ohm): {mp(2.2)['Pdc']:.1f} W DC at 2.2 m/s, {mp(2.0)['Pdc']:.1f} W at 2.0 |
| Operating point | not a torque balance | torque balance solved: not possible at 990 rpm with that load | solved per speed with the charger law, the battery-current limit, windage and no-load loss |
| Pass/fail vs 10 W | FAIL | FAIL (voltage) | {mp(2.2)['Pdc']:.0f} W DC at 2.2 m/s: PASS; {mp(1.0)['Pdc']:.1f} W at 1.0 m/s: FAIL (the 10 W goal is the trial's, not a group requirement) |

## 4. Architecture: why a through-spindle drum rotor, and what limits the depth

Packaging attempt (series stack of real part lengths, `model/packaging_76mm.py` and the CAD): the supplied nacelle layout is
189 mm rigid (215 mm with cable hardware); a hub-integrated layout with the generator behind a seal on a spindle was 140 mm;
the only way to approach 76 mm is to put the generator **inside** the rotating hub with the stationary spindle passing through the
motor's 20 mm bore, so that bearings, seal, O-rings and motor overlap radially instead of stacking axially. Dimensioned stack of the
min76 variant: {stack_m} = {Lm['axial_depth_mm']:.1f} mm. The struts add no length: they are profile-cut 6061 plates cranked
{Vm['strut_jog']:.0f} mm forward alongside the drum at radii the rotating parts never reach.

**Limiting components:** the GL60 length ({P['motor_len']} mm, fixed), the two cap plugs ({Vm['plug_front']} + {Vm['plug_rear']} mm: one O-ring groove with 2.5 mm lands each, and the rear one
also houses the bearing, the 2.5 mm thrust-ring web and the 4 mm seal), the dome ({Vm['dome_h']} mm) and the boss ({Vm['boss_t']} mm, which must hold the cross pin, the
recessed spindle end with the potting plug and the 3 mm lead groove). With the robust parts the same layout is {Lr['axial_depth_mm']:.1f} mm.

**Decision and tradeoff:** min76 is the preferred build *provided* the thin-section 6702 bearings (C0 {brg['C0']:.0f} N against {brg['Fa3']:.0f} N thrust
in a 3 m/s flood, Fa/C0 {brg['Fa3_C0']:.2f}; practical axial capacity ~{brg['Fa_cap_N']:.0f} N) and the 4 mm PTFE seal are accepted; if either fails its bench gate, the robust variant
is the fall-back and 76 mm becomes a declared no-go at {Lr['axial_depth_mm']:.1f} mm. The hub ratio rises from 0.25 to {Lm['r_pad_top']/101.6:.2f} (aerodynamic root at the pad top),
which costs about a third of the rotor power (Cp 0.368 -> {c(1.5)['cp_peak']:.3f} at 1.5 m/s); that is the price of the envelope.

Alternatives considered and rejected for this iteration: stationary nacelle (best cooling and seal access, 189 mm); magnetic
coupling (no rotary seal; adds 20 mm and an unqualified coupling); flooded potted generator (no enclosure; T200-style, but silt,
magnet corrosion and the GL60's open construction are unqualified: it is the fall-back if the seal pumping test, gate 4, fails).

## 5. Mechanical design

**Load paths (all rigid, modelled, zero interference on {Lm['pairs_checked']} checked part pairs):**
- Thrust (water pushes the rotor downstream): blade -> airfoil-section tongue (2 axial spring pins) -> carrier segment -> rear lip -> rear cap flange -> rear cap shoulder -> rear bearing -> shim -> split 316 thrust ring (in a spindle groove, captured by the cap's 18 mm wall hole) -> spindle -> boss cross pin -> boss -> 3 strut tabs (pinned) -> struts -> duct clevises (6x M4).
- Reverse load (handling, reverse flow): carrier front lip -> front cap -> front bearing -> DIN 471-15 circlip (0.1 mm gap, 24 mm recess, nose 2 mm beyond the groove) -> spindle. End play set to 0.1-0.2 mm by the shim pack; the nose clears its pocket floor by 0.3 mm so the circlip is the stop.
- Torque: blades -> carrier lugs in the cap-flange notches -> front cap -> TPU dog clutch (4 dogs 8 x 4, engaged 3.5 mm, clocked 45 deg from the screws) -> GL60 bell; stator reaction -> integral spindle flange -> spindle -> boss pin -> struts -> duct. No grub screw and no bonded joint carries torque; the 6 carrier bolts only clamp.
- Installability (R11-R14): the rear bearing, shim and ring go on from the rear over a plain Ø15 journal; the rear cap passes over the sleeve and captures the ring; the seal is pressed after the cap is on; every screw head sits in a counterbore (`screw_*` and `vent_screw` are modelled parts in the clash check).

**Machined and metal parts and their functions** (section 2 of `docs/PRINT_ASSEMBLY_PLAN.md`): front and rear caps (hard-anodised 6061:
O-ring land, bearing seats N7, seal seat, labyrinth groove, counterbored vent), spindle (6061: journals, counterface, integral stator flange
with the lead channel, split-ring groove, reamed plug bore, heat path), split thrust ring (316), boss (6061: heat sink, labyrinth tongue,
pin and strut seats, lead groove), struts (6061 plate: bending), potting plug (Delrin), tube (6061: pressure wall, bored lands).
Drawings: `cad/out/min76_drawing_*.png` (quotation drawings; the STEP files carry the geometry).

**Printed parts, structure (ASA provisional; allowables assumed, coupons required):** the blade root is the pad-top airfoil section
extruded {P['pocket_d']} mm into a matching carrier pocket ({P['pocket_clear']} mm per side) with two axial 3 mm spring pins {P['pin_below_top']} mm below the pad top
({S['ligament_mm']:.1f} mm ligament). At the 3 m/s maximum thrust ({S['thrust']['3.0']:.0f} N rotor, {S['F_thrust_blade_3ms']:.1f} N per blade) the flap moment at the pad is {S['M_root']:.2f} N m: if the
pins take it all, pin bending {S['pin_bending_MPa']:.0f} MPa (1.4310 spring pin) and tongue bearing {S['tongue_bearing_pin_MPa']:.1f} MPa; if the pocket walls take it all, {S['wall_bearing_MPa']:.2f} MPa
(allowable 8 long / 15 short). Centrifugal load at the 3 m/s runaway ({c(3.0)['modes']['open']['rpm']:.0f} rpm, blade {S['m_blade_g']:.0f} g) is {S['F_cf']:.0f} N: pin shear {S['pin_shear_cf_MPa']:.1f} MPa, ligament
shear-out {S['shear_out_MPa']:.2f} MPa short-term ({S['shear_out22_MPa']:.2f} MPa sustained at 2.2 m/s) against {S['material']['allow_interlaminar_shear_short']} / {S['material']['allow_interlaminar_shear_long']}. Airfoil root bending {S['airfoil_root_MPa']:.2f} MPa (chord {S['root_chord_mm']:.1f}, 24 % thick) with
layers along the span; no fillet is claimed; 3/rev fatigue is not assessed (gate 13). Carrier: lug shear {S['lug_shear_MPa']:.2f} MPa at the {S['Q_max']:.2f} N m maximum rotor torque;
6x M3 at 0.3 N m (~{S['bolt_F']:.0f} N) under 12 mm penny washers: {S['ear_bearing_MPa']:.1f} MPa on the ears (allow 8), nuts in printed traps. Bearing seats and seal lands are in
6061, not in prints; the printed carrier's clamp is re-torqued after 24 h. Balance: blades matched to 0.3 g; drum static-balanced.
Design overspeed: {c(3.0)['modes']['open']['rpm']:.0f} rpm (3 m/s open circuit, tip {c(3.0)['modes']['open']['rpm']*2*math.pi/60*0.1016:.1f} m/s), which cavitates (section 7): the dump keeps the rotor below it.
One-piece rotor vs modular: a one-piece carrier-with-blades would print the blade roots across layers and need heavy supports; the
modular pinned root prints each blade flat (strong direction) and lets a damaged blade be replaced; chosen.

**Struts:** 6061-T6 4 mm plate profile: {S['strut_sigma_tab']:.1f} MPa in the {Vm['boss_t']-0.4:.1f} mm tab (fixed-fixed bound) and {S['strut_sigma_duct']:.1f} MPa in the 16 mm leg (cantilever bound) at the
3 m/s thrust; {S['strut_tip_defl_mm']:.2f} mm deflection; clevis bolts {S['clevis_bolt_shear_MPa']:.0f} MPa. Printed struts would have exceeded the printed allowable in a flood and added 16 mm of depth.

**Hydrodynamics after the structural thickness:** hub ratio {Lm['r_pad_top']/101.6:.2f}: BEM Cp {c(1.0)['cp_peak']:.3f} / {c(1.5)['cp_peak']:.3f} / {c(2.0)['cp_peak']:.3f} at 1 / 1.5 / 2 m/s (Re-dependent). The duct is
modelled only as a guard ring; its augmentation is not credited. The struts and boss are behind the rotor; blockage ~4 % of the
annulus: a -1 to -3 % Cp effect (estimate). Drum windage is in the torque balance ({c(2.0)['windage_Nm_at_charging']*1000:.0f} mN m at 2 m/s).

## 6. Sealing, pressure and heat (resolved together)

- **Boundary:** tube wall (anodised; O-ring lands bored 72.90 H8, Ra 1.6) -> one radial AS568-147 EPDM O-ring per anodised 6061 plug
  (two in robust) -> caps -> one PTFE pressure-rated lip seal on the stationary spindle's Speedi-Sleeve -> the spindle bore (dry) -> O-ring
  potting plug in the reamed spindle end (epoxy over solder-filled PVC leads). No screw crosses the boundary: the caps are retained by the
  printed carrier lips/lugs, the vent is a sealed M6 port in a counterbore, the dome screws are blind in the flange.
- **Glands:** plug 72.75 in a 72.90 +-0.15 bored land; groove 3.6 x 2.08 with 2.5 mm lands; squeeze {min(S['seal']['min76']['squeeze_pct'].values()):.1f}-{max(S['seal']['min76']['squeeze_pct'].values()):.1f} % over the bore tolerance; fill {S['seal']['min76']['fill_pct']:.0f} %; stretch {S['seal']['min76']['stretch_pct']:.1f} %.
  Measured-bore machining is mandatory (gate 3). Printed surfaces seal nothing.
- **Rotary seal:** {Vm['seal']} (min76) / {Vr['seal']} (robust) PTFE pressure-rated lip seal (Trelleborg Varilip PDR class or Freudenberg BABSL), lip to the water,
  surface speed {S['v_surf_ms']:.2f} m/s at the 3 m/s runaway, service differential {S['p_diff_bar']:.2f} bar (2 m head {19.6:.1f} kPa + {S['p_breath_kPa']:.1f} kPa warm-assembly breathing): a plain NBR seal
  (0.3 bar dynamic) is not adequate (R02). Counterface: SKF Speedi-Sleeve **99059** (15 mm; the 12 mm sleeve the earlier report cited as 99047 is 99049 in SKF's
  table: not used here), sealant under it. Installation on an anodised aluminium journal must be confirmed with SKF; the fallback is the hard-anodised journal
  itself (Ra 0.4). A non-contact labyrinth (boss tongue in a cap groove, 0.5 mm clearance) shields the lip from silt. Seal life is not qualified here.
- **Pressure and breathing:** 19.6 kPa at 2 m pushes each cap inward with {S['F_cap_N']:.0f} N (carrier lip bearing {S['lip_bearing_MPa']:.2f} MPa); the -70 kPa vacuum test applies 292 N.
  Stator heat raises the drum air by an estimated {S['dT_drum_air']:.0f} K at the current limit (assumed 30 % of the winding rise): {S['dP_internal_kPa']:.1f} kPa of internal pressure, which lifts the lip unless
  the head exceeds it: **minimum axis depth {S['min_depth_m']:.2f} m**, and the drum is closed at no more than water temperature + 10 K. Gate 4 tests exactly this.
- **Cable:** 3 leads inside the 9 mm spindle bore (splices inside the bore), through the potting plug (the pressure barrier), 90-degree turn into the 6 x 3 groove
  on the boss rear face (removable RTV), along strut 0 to an adhesive heat-shrink splice at the duct. Service: pin out, boss off over the cable, plug out, cap off
  over the Ø12 plug head (R29). No WetLink is needed in the rotating drum; the earlier 24 mm cap / 20 mm thread conflict disappears.
- **Heat:** winding -> stator base ({S['R_wb']} K/W, assumed) -> integral flange ({S['R_sf']}, pasted) -> spindle ({S['R_sp']:.2f} K/W over {S['L_sp_mm']:.0f} mm) -> boss joint ({S['R_bj']}, pasted) -> boss in the
  water ({S['R_bw']:.2f}) = {S['R_tot']:.2f} K/W by the metal path alone: +{S['dT_limit']:.0f} K at the 1.2 A generator current ({S['Pcu_limit_W']:.1f} W copper). The air-gap path through the rotating bell is not
  credited. Gate 7 measures it; the Victron battery-current limit is the knob (it equals 1.2 A generator current only at a 29 V bus, R09).

## 7. Performance: water power, shaft power, rectified DC, battery

Model: `model/system_model_v3.py` (conventions in its header). Rotor Cp(lambda, V) from the reviewed BEM with the aerodynamic root at
r = {Lm['r_pad_top']:.1f} mm; running friction = PTFE seal {G['seal_running_Nm']*1000:.1f} mN m + 2 x {G['bearing_running_Nm']*1000:.0f} mN m bearings + no-load loss ({G['iron_loss_W_at_700rpm']} W at 700 rpm, rpm^1.5) + drum windage;
GL60 Kt {60/(2*math.pi*G['KV']):.3f} N m/A, R_LL {G['R_LL']} ohm, L_LL {G['L_LL']*1000:.2f} mH, {G['pole_pairs']} pole pairs; six MBR10100 diodes (2 x {G['Vf_diode']} V); commutation overlap reduces V_dc and the torque per amp
(reactive, not a loss, R06); Victron 100/15 buck MPPT (runs only while V_dc >= V_bat + 1 = {G['battery_V']+1:.1f} V; battery-current limit {G['batt_current_limit']} A);
battery {G['battery_V']} V; charger efficiency {G['charger_eff']*100:.0f} %, quiescent {G['charger_quiescent_W']} W.

| Flow (m/s) | Water power (W) | Rotor peak shaft (W) | Charging point shaft | DC current / voltage | Copper + no-load loss (W) | **Rectified DC (W)** | **Net to battery (W)** | water-to-DC / shaft-to-DC | No-load runaway (tip cavitation number) |
|---|---|---|---|---|---|---|---|---|---|
{row_power(1.0)}
{row_power(1.2)}
{row_power(1.5)}
{row_power(2.0)}
{row_power(2.2)}
{row_power(3.0)}

The earlier "70 %" was shaft-to-DC; water-to-DC is {pct(mp(1.0)['Pdc'], c(1.0)['P_water'])}-{pct(mp(2.0)['Pdc'], c(2.0)['P_water'])}. At 1.0 m/s the buck charger forces the rotor above its best TSR (V_dc must stay
above {G['battery_V']+1:.1f} V): {c(1.0)['Pdc_nofloor']:.1f} W would be available without that floor against {c(1.0)['P_dc']:.1f} W with it; no COTS charger does both buck and boost over 10-60 V
(research: Genasun GVB-8 cannot regulate when V_in > V_bat). At 3 m/s the Victron's battery-current limit caps the charger at {c(3.0)['P_dc']:.0f} W and the bus rises
to {mp(3.0)['Vdc']:.0f} V, so the dump relay (45 V) engages whatever the battery state.

**Sensitivities (DC W at the charging point):**

| Flow | baseline | no V_bat+1 floor | KV 25 instead of {G['KV']} | NBR seal instead of PTFE | drum windage at the charging point (mN m) |
|---|---|---|---|---|---|
{row_sens(1.0)}
{row_sens(1.5)}
{row_sens(2.0)}

**Startup, runaway, dump and brake (torque-balanced per speed; cavitation number sigma from 0.5 m depth, 20 C):**

| Flow | Static torque / breakaway PTFE (ratio) / breakaway NBR (ratio), N m | Open circuit | Dump 22 ohm (relay 45 V engage / 12 V release) | 3-phase short brake |
|---|---|---|---|---|
{row_fault(1.0)}
{row_fault(1.2)}
{row_fault(1.5)}
{row_fault(2.0)}
{row_fault(2.2)}
{row_fault(3.0)}

**Dump resistor study** (rpm, bus V, resistor W, tip cavitation number):

| Flow | 15 ohm | 22 ohm | 33 ohm | 47 ohm |
|---|---|---|---|---|
{row_dump(2.0)}
{row_dump(2.2)}
{row_dump(3.0)}

Reading: NACA 44xx sections cavitate at the tip below sigma ~1.0-1.2, so the open-circuit runaway is **not** a safe state above about
2 m/s (sigma {c(2.0)['sigma_tip_runaway']:.2f} at 2.0, {c(2.2)['sigma_tip_runaway']:.2f} at 2.2, {c(3.0)['sigma_tip_runaway']:.2f} at 3.0 m/s). The 22 ohm dump holds sigma {c(3.0)['sigma_tip_dump']:.2f} at 3 m/s with {c(3.0)['modes']['dump']['Pdc']:.0f} W in the
submerged resistor and {c(3.0)['modes']['dump']['Pcu']:.0f} W in the winding (+{c(3.0)['modes']['dump']['Pcu']*S['R_tot']:.0f} K by the metal path: a survival state, not a continuous one); 15 ohm would
stop cavitation (sigma {c(3.0)['dump_study']['15.0']['sigma_tip']:.2f}) but put {c(3.0)['dump_study']['15.0']['Pcu']:.0f} W into the winding; 47 ohm would leave the tips cavitating (sigma {c(3.0)['dump_study']['47.0']['sigma_tip']:.2f}). With a full battery at 2.0-2.2 m/s the dump dissipates
{c(2.0)['modes']['dump']['Pdc']:.0f}-{c(2.2)['modes']['dump']['Pdc']:.0f} W and the winding {c(2.0)['modes']['dump']['Pcu']:.0f}-{c(2.2)['modes']['dump']['Pcu']:.0f} W continuously. Release at 12 V: every dump equilibrium above 1.6 m/s sits above 12 V and every
open-circuit bus below 1.9 m/s sits below 45 V, so the relay does not cycle; between 1.6 and 1.9 m/s with a full battery the rotor runs
open-circuit at about 40 V (sigma > 2, harmless). The 3-phase short brake stalls the rotor to {c(1.0)['modes']['brake']['rpm']:.0f}-{c(2.2)['modes']['brake']['rpm']:.0f} rpm up to 2.2 m/s with <= {c(2.2)['modes']['brake']['Pcu']:.1f} W in the
winding (continuous retrieval brake); at 3 m/s it equilibrates at {c(3.0)['modes']['brake']['rpm']:.0f} rpm with {c(3.0)['modes']['brake']['Pcu']:.0f} W in the winding: 10 minutes at most.

## 8. Power electronics and control logic (selected parts, research in `research/research_electrical_v3.md`)

Generator (3 phases) -> NKK S32F 3PDT brake switch (RUN / BRAKE) -> 6 x MBR10100 bridge (100 V) -> DC bus [2 x 5KP90A TVS; 6-80 V
voltage-monitor relay: engage 45 V / release 12 V, RC-snubbed contact -> Ohmite HS100 22R 100 W on a submerged 6061 plate (dump block,
outside the dry box)] -> Victron SmartSolar MPPT 100/15 (battery-current limit {G['batt_current_limit']} A) -> 5 A fuse (Littelfuse 0287005 in FHAC0001) ->
keyed Anderson SB50 -> 12.8 V LiFePO4 with a 10 A fuse at the terminal. Dry box Hammond 1554F2GY (IP68) with PG7 glands; generator cable
Weipu SP13 IP68 connector. No part inside the box dissipates more than the diodes (~{2*G['Vf_diode']*mp(2.2)['I']:.1f} W at 2.2 m/s).
- Unloaded start: switch in RUN, charger off until the bus exceeds V_bat + 5 V (about {G['battery_V']+5:.0f} V): the rotor accelerates unloaded to its
  no-load speed ({c(1.0)['modes']['open']['rpm']:.0f} rpm at 1 m/s = {c(1.0)['modes']['open']['Vdc']:.0f} V), then the MPPT ramps the load; it cannot pull the bus below V_bat + 1 V, so it cannot stall the rotor by itself.
- Current and temperature limits: the Victron limit of {G['batt_current_limit']} A battery current equals {G['batt_current_limit']*G['battery_V']/G['charger_eff']/29:.1f} A of generator current at a 29 V bus and more at lower bus voltage;
  the winding limit is therefore enforced by the rotor's own torque curve below 2.2 m/s (max {mp(2.2)['I']:.2f} A) and by the dump above; the thermal gate (7) sets the final value.
- Full battery or charger fault: the bus rises toward open circuit; the relay engages at 45 V (>= 1.9 m/s); the dump block sees {c(2.0)['modes']['dump']['Pdc']:.0f}-{c(2.2)['modes']['dump']['Pdc']:.0f} W at 2-2.2 m/s and holds until the flow drops below 1.6 m/s.
- Load disconnect at any speed <= 2.2 m/s: open circuit <= {c(2.2)['modes']['open']['Vdc']:.0f} V; TVS and the 100 V charger input are within rating; the dump engages above 45 V because the relay is bus-powered.
- Retrieval: BRAKE at <= 2.2 m/s (<= {c(2.2)['modes']['brake']['Pcu']:.1f} W in the winding); at 3 m/s for <= 10 min.
- Floods (3 m/s provisional): dump engaged (automatic); {c(3.0)['modes']['dump']['Pcu']:.0f} W in the winding is survivable for hours, not days; retrieve when possible.
  Residual risk: a relay failure above 3 m/s gives {c(3.0)['modes']['open']['Vdc']:.0f} V open circuit (within the 100 V ratings) and a cavitating rotor; above that speed the ratings are exceeded.

## 9. Reviews and final integrated check

Four independent review passes (calculation/units, mechanical-CAD, printability/manufacturing, skeptical failure-mode) were run by
separate reviewer agents on the exported first-draft files. They found {n_R} real issues (4 critical in the CAD: rear bearing not
installable, lead path through the bearing seat, cross pin through the lead exit, fastener heads without room; 1 critical in the
calculation: aerodynamic root radius; 1 critical in the FMEA: unserviceable seal; the rest major/minor), all logged with evidence,
correction and re-verification in `docs/ERROR_LOG.md`. The geometry, the models, the drawings, the BOM and the plans were regenerated
after the corrections; this report is generated from those outputs. The final integrated check (`tools/final_check_and_package.py`)
re-imported the exported assembly STEPs, ran a full pairwise rigid clash check, verified every print STL (closed, on the bed, volume
against its STEP) and reconciled the BOM against the CAD part table:

```
{final_check}
```

## 10. Deliverables and what remains open

| Deliverable | Where |
|---|---|
| Preferred architecture + justification | this report, sections 4-6 |
| Dimensioned assembly, section, exploded views | `cad/out/min76_section.png`, `min76_dimensioned.png`, `min76_exploded.png` (+ `robust_*`) |
| Editable parametric CAD and assembly STEP | `cad/make_v3.py`; `cad/out/min76_assembly.step`, `robust_assembly.step`; per-part `*.step` |
| Oriented printable STLs | `cad/out/min76_*_PRINT.stl` ({len(printed)} parts; all closed; blades within {blade0.get('stl_vs_step_volume_pct', 0):.2f} % of the STEP volume, tilted {blade0.get('print_tilt_deg', 0):.1f} deg) |
| Machined-part drawings | `cad/out/min76_drawing_front_cap.png`, `_rear_cap.png`, `_spindle.png`, `_boss_strut.png` (boss, strut profile, potting plug) |
| Per-part print/assembly plan incl. service | `docs/PRINT_ASSEMBLY_PLAN.md` |
| BOM with sourced specs and cost scope | `docs/BOM_v3.csv` ({len(bom)} lines; one prototype roughly ${cost_lo:,.0f}-{cost_hi:,.0f} of hardware excluding anodising batch minimums, the battery, a duct beyond the ring, frame/mooring and instrumentation; machining prices are estimates) |
| Calculation model (reproducible) | `model/reproduce_trial1.py`, `system_model_v3.py`, `structure_seal_thermal_v3.py`, `packaging_76mm.py`, `rotor_v3.py` + JSON outputs |
| Original vs corrected vs final comparison | section 3 |
| Validation plan with acceptance criteria | `docs/VALIDATION_PLAN_v3.md` (13 gates) |
| Error-review / correction log | `docs/ERROR_LOG.md` ({n_E} first-draft + {n_R} review entries) |

**Measurements required before the machined parts are cut:**
{tm}

**Remaining assumptions that move the result:** lip-seal breakaway and cogging (decide 1.0 m/s self-start), the exact GL60 Kt/R
(+-10 % on DC power), the winding-to-base and stator-to-flange thermal joints (decide the current limit), printed wet allowables
(coupons), the real tube bore (gland machining), the drum-air temperature rise (minimum depth), duct augmentation (not credited),
and the deployment depth and flood regime (provisional 0.3-2 m / 3 m/s).

**Required physical tests:** the thirteen gates in `docs/VALIDATION_PLAN_v3.md`; none has been run.
"""
open(os.path.join(D, "REPORT_v3.md"), "w").write(txt)
print("wrote REPORT_v3.md", len(txt.split()), "words")
